"""The builder helper: checks safety, asks Meta (or the offline helper), returns a valid spec.

- The kid's words go through the word list, then (with Meta) the model classifier, before any model
  sees them. Unsafe words are a 422 "unsafe".
- Meta's answer is only used if it is well-formed (one retry if not) and its words pass the same
  checks. If Meta can't be reached, or the classifier can't answer, the offline helper answers
  instead ("Our helper is resting. Here's an offline idea!"), so the builder never breaks.
- Every suggestion is turned into a full spec that the catalog can draw (normalize).
"""

import logging
import random
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from PIL import Image
from sqlmodel import Session

from app.avatar.catalog import load_catalog
from app.avatar.spec import nearest, normalize, palette
from app.errors import ApiError
from app.providers.llm import LLMError, LLMProvider
from app.schemas.builder import Ideas, Suggestion
from app.services import helper_meta, helper_offline, safety
from app.services.safety import SafetyUnavailable, Verdict

log = logging.getLogger(__name__)

META_LABEL = "Made with Meta AI"
OFFLINE_LABEL = "Made by the offline helper"
RESTING = "Our helper is resting. Here's an offline idea!"
UNSAFE = "Let's keep Comickatha friendly for everyone! Please try different words."
NOT_A_DRAWING = "That looks like a photo. Please upload a drawing, not a photo of a person!"
UNSAFE_DRAWING = "Let's keep Comickatha friendly for everyone! Please try a different drawing."
NEEDS_CONSENT = "Drawings are sent to Meta AI, so a grown-up needs to say OK first."
TRAITS = set(helper_offline.TRAITS)

Raw = dict[str, Any]


class InvalidReply(ValueError):
    """The model's reply doesn't have the shape we asked for."""


def label(source: str) -> str:
    return META_LABEL if source == "meta" else OFFLINE_LABEL


def build_spec(spec: dict[str, Any], raw: Raw) -> tuple[dict[str, Any], list[str]]:
    """Applies a raw suggestion to the current spec. Returns the full spec and what changed."""
    cat = load_catalog()
    if not isinstance(raw.get("parts", {}), dict) or not isinstance(raw.get("colors", {}), dict):
        raise InvalidReply("parts and colors must be objects")
    body_type = raw.get("body_type") or spec["body_type"]
    if body_type not in cat["body_types"]:
        raise InvalidReply("unknown body type")

    parts = {**spec["parts"], **{k: str(v) for k, v in raw.get("parts", {}).items()}}
    colors = dict(spec["colors"])
    for slot, value in raw.get("colors", {}).items():
        if slot not in cat["color_slots"] or not isinstance(value, str):
            continue
        entries = palette(slot, body_type, cat)
        if value.startswith("#"):
            colors[slot] = nearest(value, entries)["hex"]
        elif entry := next((e for e in entries if e["id"] == value), None):
            colors[slot] = entry["hex"]
    extras = raw.get("extras", spec["extras"])
    if not isinstance(extras, list):
        raise InvalidReply("extras must be a list")
    traits = [t for t in raw.get("traits", spec["personality"]["traits"]) if t in TRAITS][:3]
    catchphrase = str(raw.get("catchphrase") or spec["personality"]["catchphrase"])[:60]

    new = normalize(
        {
            "body_type": body_type,
            "parts": parts,
            "colors": colors,
            "extras": [str(e) for e in extras],
            "personality": {"traits": traits, "catchphrase": catchphrase},
            "role": spec["role"],
        }
    )
    changed = []
    if new["body_type"] != spec["body_type"]:
        changed.append("body_type")
    changed += [c for c in new["parts"] if new["parts"][c] != spec["parts"].get(c)]
    changed += [f"colors.{s}" for s in new["colors"] if new["colors"][s] != spec["colors"].get(s)]
    if new["extras"] != spec["extras"]:
        changed.append("extras")
    if new["personality"] != spec["personality"]:
        changed.append("personality")
    return new, changed


def _texts(raw: Raw) -> tuple[list[str], str, str, list[str]]:
    names = [str(n).strip()[:24] for n in raw.get("name_ideas", []) if str(n).strip()][:3]
    reply = str(raw.get("reply", "")).strip()[:200]
    catchphrase = str(raw.get("catchphrase", "")).strip()[:60]
    unmatched = [str(u).strip()[:60] for u in raw.get("unmatched", []) if str(u).strip()][:5]
    return names, reply, catchphrase, unmatched


@dataclass
class Helper:
    llm: LLMProvider | None
    session: Session
    user_id: str
    # Set when the classifier couldn't check the kid's words: only the offline helper may answer.
    offline_only: bool = field(default=False, init=False)

    @property
    def source(self) -> str:
        return "meta" if self.llm is not None else "mock"

    # ---- endpoints ------------------------------------------------------------------------------

    def describe(self, text: str, spec: dict[str, Any]) -> Suggestion:
        spec = normalize(spec)
        self._check_input("builder:describe", {"description": text})
        return self._suggest(
            spec,
            lambda llm: helper_meta.describe(llm, text, spec),
            lambda: helper_offline.describe(text, spec),
        )

    def surprise(self, body_type: str | None, spec: dict[str, Any]) -> Suggestion:
        spec = normalize(spec)
        seed = random.randrange(2**31)
        return self._suggest(
            spec,
            lambda llm: helper_meta.surprise(llm, body_type, spec),
            lambda: helper_offline.surprise(body_type, seed),
        )

    def ideas(self, spec: dict[str, Any], name: str) -> Ideas:
        spec = normalize(spec)
        if name.strip():
            self._check_input("builder:ideas", {"name": name})
        seed = random.randrange(2**31)
        raw, source, fallback = self._ask(
            lambda llm: helper_meta.ideas(llm, spec, name),
            lambda: helper_offline.ideas(spec, name, seed),
            check=lambda r: (r.get("name_ideas") and isinstance(r.get("traits"), list)) or None,
        )
        names, reply, catchphrase, _ = _texts(raw)
        traits = [t for t in raw.get("traits", []) if t in TRAITS][:3]
        if fallback:
            reply = f"{RESTING} {reply}"
        return Ideas(
            name_ideas=names,
            traits=traits,
            catchphrase=catchphrase,
            reply=reply,
            source="meta" if source == "meta" else "mock",
            fallback=fallback,
            label=label(source),
        )

    def from_drawing(
        self, png: bytes, image: Image.Image, spec: dict[str, Any], consent: bool
    ) -> Suggestion:
        spec = normalize(spec)
        if self.llm is not None:
            if not consent:
                raise ApiError(403, "consent_needed", NEEDS_CONSENT)
            try:
                raw = helper_meta.from_drawing(self.llm, png, spec)
                self._check_drawing_verdict(raw)
                return self._finish(spec, raw, "meta", fallback=False)
            except (LLMError, InvalidReply, KeyError, TypeError, SafetyUnavailable, ValueError):
                log.warning("meta drawing helper unavailable; using the offline helper")
        if helper_offline.looks_like_photo(image):
            self._log("builder:drawing", Verdict(False, None, ["photo"]), "image")
            raise ApiError(422, "not_a_drawing", NOT_A_DRAWING)
        self._log("builder:drawing", Verdict(True), "image")
        fallback = self.llm is not None
        return self._finish(spec, helper_offline.from_drawing(image, spec), "mock", fallback)

    # ---- internals ------------------------------------------------------------------------------

    def _log(self, target: str, verdict: Verdict, kind: str = "text") -> None:
        safety.log_verdict(self.session, self.user_id, target, verdict, kind)

    def _check_input(self, target: str, fields: dict[str, str]) -> None:
        verdict = safety.check_words(fields)
        if verdict.allowed and self.llm is not None:
            try:
                verdict = safety.classify(self.llm, fields)
            except SafetyUnavailable:
                # Unchecked words never go to the model: the offline helper answers instead.
                self.offline_only = True
                self._log(target, Verdict(False, None, ["unavailable"]))
                return
        self._log(target, verdict)
        if not verdict.allowed:
            raise ApiError(422, "unsafe", UNSAFE)

    def _output_ok(self, raw: Raw) -> bool:
        """The model's words pass the word list and the classifier (fails closed)."""
        names, reply, catchphrase, unmatched = _texts(raw)
        fields = {
            "reply": reply,
            "catchphrase": catchphrase,
            "names": ", ".join(names),
            "unmatched": ", ".join(unmatched),
        }
        try:
            verdict = safety.check_text(fields, self.llm)
        except SafetyUnavailable:
            verdict = Verdict(False, None, ["unavailable"])
        self._log("builder:reply", verdict)
        return verdict.allowed

    def _ask(
        self,
        meta: Callable[[LLMProvider], Raw],
        offline: Callable[[], Raw],
        check: Callable[[Raw], object],
    ) -> tuple[Raw, str, bool]:
        """Meta's reply if it's usable and safe; otherwise the offline helper's. -> raw, source,
        fallback."""
        if self.llm is not None and not self.offline_only:
            for _attempt in range(2):  # one retry for a malformed reply
                try:
                    raw = meta(self.llm)
                    if not check(raw):
                        raise InvalidReply("missing fields")
                except (InvalidReply, KeyError, TypeError, ValueError):
                    continue
                except LLMError:
                    break
                if self._output_ok(raw):
                    return raw, "meta", False
                break
        return offline(), "mock", self.llm is not None

    def _suggest(
        self,
        spec: dict[str, Any],
        meta: Callable[[LLMProvider], Raw],
        offline: Callable[[], Raw],
    ) -> Suggestion:
        # build_spec raises InvalidReply for a malformed reply, which _ask retries once.
        raw, source, fallback = self._ask(meta, offline, lambda r: build_spec(spec, r))
        return self._finish(spec, raw, source, fallback)

    def _finish(self, spec: dict[str, Any], raw: Raw, source: str, fallback: bool) -> Suggestion:
        new, changed = build_spec(spec, raw)
        names, reply, _, unmatched = _texts(raw)
        if fallback:
            reply = f"{RESTING} {reply}".strip()
        # The offline helper echoes the kid's words (already checked); check the rest cheaply.
        if (
            source == "mock"
            and not safety.check_words({"reply": reply, "names": ", ".join(names)}).allowed
        ):
            reply, names = "Here's an idea!", []
        return Suggestion.model_validate(
            {
                "spec": new,
                "changed": changed,
                "name_ideas": names,
                "reply": reply,
                "unmatched": unmatched,
                "source": "meta" if source == "meta" else "mock",
                "fallback": fallback,
                "label": label(source),
            }
        )

    def _check_drawing_verdict(self, raw: Raw) -> None:
        if raw.get("is_drawing") is not True or raw.get("shows_real_person") is not False:
            self._log("builder:drawing", Verdict(False, None, ["photo"]), "image")
            raise ApiError(422, "not_a_drawing", NOT_A_DRAWING)
        if raw.get("safe_for_kids") is not True:
            self._log("builder:drawing", Verdict(False, None, ["unsafe"]), "image")
            raise ApiError(422, "unsafe", UNSAFE_DRAWING)
        self._log("builder:drawing", Verdict(True), "image")
        if not self._output_ok(raw):
            raise SafetyUnavailable()
