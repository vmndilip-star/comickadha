"""The builder helper: checks safety, asks Meta (or the offline helper), returns a valid spec.

The safety and fallback flow is the shared Guard (services/ai_guard.py): the kid's words are
checked before any model sees them, Meta's answer is used only if well-formed and safe, and
otherwise the offline helper answers ("Our helper is resting. Here's an offline idea!").
Every suggestion is turned into a full spec that the catalog can draw (normalize).
"""

import logging
import random
import re
import zlib
from collections.abc import Callable, Collection, Iterable
from typing import Any

from PIL import Image
from sqlalchemy import and_, or_
from sqlmodel import Session, col, select

from app.avatar.catalog import load_catalog
from app.avatar.spec import nearest, normalize, palette, with_leggings
from app.errors import ApiError
from app.models import Character
from app.providers.llm import LLMError, LLMProvider
from app.schemas.builder import Ideas, Suggestion
from app.services import character_safety, helper_meta, helper_offline, safety
from app.services.ai_guard import (
    META_LABEL,
    OFFLINE_LABEL,
    RESTING,
    UNSAFE,
    Guard,
    InvalidReply,
    label,
)
from app.services.safety import SafetyUnavailable, Verdict

__all__ = ["META_LABEL", "OFFLINE_LABEL", "RESTING", "UNSAFE", "Helper", "build_spec", "label"]

log = logging.getLogger(__name__)

NOT_A_DRAWING = "That looks like a photo. Please upload a drawing, not a photo of a person!"
UNSAFE_DRAWING = "Let's keep Comickatha friendly for everyone! Please try a different drawing."
NEEDS_CONSENT = "Drawings are sent to Meta AI, so a grown-up needs to say OK first."
TRAITS = set(helper_offline.TRAITS)
# How a kid would call each field the Lab helper checks before asking Meta.
LABELS = {
    "description": "your description",
    "name": "the name",
    "catchphrase": "your character's catchphrase",
}


def _kid_words(spec: dict[str, Any]) -> dict[str, str]:
    """The kid-written words in a spec that helper_meta.current() puts in the prompt."""
    return {"catchphrase": str(spec.get("personality", {}).get("catchphrase", ""))}


Raw = dict[str, Any]


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
    if new["parts"].get("top") == "dress" and spec["parts"].get("top") != "dress":
        new = with_leggings(new)
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


def _respectful(raw: Raw) -> Raw:
    """Surprise me never pairs cultural or religious headwear with silly items."""
    parts, extras = raw.get("parts"), raw.get("extras")
    if isinstance(parts, dict) and isinstance(extras, list):
        raw["extras"] = character_safety.respectful_extras(parts, [str(e) for e in extras])
    return raw


def names_in_use(session: Session, user_id: str) -> set[str]:
    """The names a name idea must not repeat (lower case): the kid's own characters and the
    starter characters, so a new character never shares a name with one already in a story."""
    stmt = select(Character.name).where(
        or_(
            and_(col(Character.user_id) == user_id, col(Character.deleted_at).is_(None)),
            col(Character.starter).is_(True),
        )
    )
    return {name.strip().lower() for name in session.exec(stmt)}


def fresh_names(
    names: Iterable[str], taken: Collection[str], body_type: str, seed: int, count: int = 3
) -> list[str]:
    """Name ideas that no character already has, Meta's or the offline helper's alike: each name in
    use is swapped for a fresh one from the offline list (never one in use either), and an empty
    list gets `count` of them. (Unsafe names are dropped before this, as before.)"""
    given = list(dict.fromkeys(names))[:count]
    kept = [n for n in given if n.strip().lower() not in taken]
    want = len(given) if kept else count
    if len(kept) < want:
        avoid = set(taken) | {n.lower() for n in kept}
        pool = helper_offline.NAMES.get(body_type, helper_offline.NAMES["kid"])
        spare = helper_offline.offline_names(body_type, seed, count=len(pool), avoid=avoid)
        kept += [n for n in spare if not character_safety.name_problem(n)][: want - len(kept)]
    return kept


def named(intro: str, who: str, names: Iterable[str]) -> str:
    """The intro line with the character's name: any name idea it mentions becomes `who` (the
    name the kid picked, or the first idea), so it never introduces a name the kid didn't pick."""
    for name in sorted({n for n in names if n and n != who}, key=len, reverse=True):
        intro = re.sub(rf"(?<!\w){re.escape(name)}(?!\w)", who, intro)
    return intro


def _texts(raw: Raw) -> tuple[list[str], str, str, list[str]]:
    names = [str(n).strip()[:24] for n in raw.get("name_ideas", []) if str(n).strip()][:3]
    reply = str(raw.get("reply", "")).strip()[:200]
    catchphrase = str(raw.get("catchphrase", "")).strip()[:60]
    unmatched = [str(u).strip()[:60] for u in raw.get("unmatched", []) if str(u).strip()][:5]
    return names, reply, catchphrase, unmatched


def _reply_texts(raw: Raw) -> dict[str, str]:
    names, reply, catchphrase, unmatched = _texts(raw)
    return {
        "reply": reply,
        "catchphrase": catchphrase,
        "names": ", ".join(names),
        "unmatched": ", ".join(unmatched),
    }


class Helper:
    def __init__(self, llm: LLMProvider | None, session: Session, user_id: str) -> None:
        self.llm = llm
        self.guard = Guard(llm, session, user_id)

    @property
    def taken(self) -> set[str]:
        """Names already in use: never suggested again (the kid's cast and the starters)."""
        return names_in_use(self.guard.session, self.guard.user_id)

    @property
    def source(self) -> str:
        return self.guard.source

    # ---- endpoints ------------------------------------------------------------------------------

    def describe(self, text: str, spec: dict[str, Any]) -> Suggestion:
        spec = normalize(spec)
        # The character-safety description checks (docs/character-safety.md), then the classifier.
        checked = character_safety.check_description(
            self.guard.session, self.guard.user_id, "builder:describe", text
        )
        text = checked.text
        # The prompt also carries the current catchphrase (helper_meta.current): check it too.
        self._check_input("builder:describe", {"description": text, **_kid_words(spec)})
        suggestion = self._suggest(
            spec,
            lambda llm: helper_meta.describe(llm, text, spec),
            lambda: helper_offline.describe(text, spec),
        )
        if checked.notes:
            suggestion.reply = " ".join([*checked.notes, suggestion.reply]).strip()
        return suggestion

    def surprise(self, body_type: str | None, spec: dict[str, Any]) -> Suggestion:
        spec = normalize(spec)
        seed = random.randrange(2**31)
        self._check_input("builder:surprise", _kid_words(spec))
        return self._suggest(
            spec,
            lambda llm: _respectful(helper_meta.surprise(llm, body_type, spec)),
            lambda: helper_offline.surprise(body_type, seed),
        )

    def ideas(self, spec: dict[str, Any], name: str) -> Ideas:
        spec = normalize(spec)
        self._check_input("builder:ideas", {"name": name, **_kid_words(spec)})
        seed = random.randrange(2**31)
        raw, source, fallback = self._ask(
            lambda llm: helper_meta.ideas(llm, spec, name),
            lambda: helper_offline.ideas(spec, name, seed),
            check=lambda r: (r.get("name_ideas") and isinstance(r.get("traits"), list)) or None,
        )
        names, reply, catchphrase, _ = _texts(raw)
        names = fresh_names([n for n in names if n != name], self.taken, spec["body_type"], seed)
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
            self._check_input("builder:drawing", _kid_words(spec))
        if self.guard.may_ask_meta and self.llm is not None:
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
        self.guard.log(target, verdict, kind)

    def _check_input(self, target: str, fields: dict[str, str]) -> None:
        """Every kid-written word the Meta prompt will carry; nothing to check, no call."""
        fields = {k: v for k, v in fields.items() if v.strip()}
        if fields:
            self.guard.check_input(target, fields, labels=LABELS)

    def _output_ok(self, raw: Raw) -> bool:
        return self.guard.output_ok("builder:reply", _reply_texts(raw))

    def _ask(
        self,
        meta: Callable[[LLMProvider], Raw],
        offline: Callable[[], Raw],
        check: Callable[[Raw], object],
    ) -> tuple[Raw, str, bool]:
        return self.guard.ask(
            meta, offline, check=check, texts=_reply_texts, target="builder:reply"
        )

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
        # Never a name already in use: each one swapped for a fresh idea (as many as before).
        seed = zlib.crc32("|".join(names).encode())
        names = fresh_names(names, self.taken, new["body_type"], seed, count=len(names))
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
