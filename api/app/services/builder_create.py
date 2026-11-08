"""POST /builder/create: a brand-new character from a few choices and an optional description.

The rules are docs/character-safety.md:
1. The request fits the catalog (kind, age, face shape, follow-up answer); unknown fields are a 422.
2. The name and the description get the local checks (services/character_safety.py), then the
   classifier through the Guard. Nothing unchecked reaches Meta.
3. Meta (prompts/builder_create.md) or the offline helper answers.
4. The answer is checked field by field: looks (catalog ids that fit the body, people clothed, a
   dress comes with leggings), traits on the list, text lengths, and every text through the local
   checks and, for Meta's words, the classifier (fails closed). Anything failing is replaced with
   a safe default and logged as "replaced"; the kid always gets a friendly result.
"""

import json
import zlib
from typing import Any

from sqlmodel import Session

from app.avatar.catalog import Catalog, load_catalog
from app.avatar.spec import (
    SpecError,
    categories_for,
    default_spec,
    normalize,
    options_for,
    palette,
    validate,
    with_leggings,
)
from app.errors import ApiError, invalid
from app.providers.llm import LLMProvider
from app.schemas.builder import CatalogChoice, Created, CreateRequest
from app.schemas.common import TRAITS
from app.services import character_safety, helper_meta, helper_offline, safety
from app.services.ai_guard import RESTING, Guard, label
from app.services.builder_helper import build_spec

Raw = dict[str, Any]
Spec = dict[str, Any]

TARGET = "builder:create"
HUMAN = ("kid", "grown_up")
AGE_BODY = {
    "little_kid": "kid",
    "big_kid": "kid",
    "grown_up": "grown_up",
    "grandparent": "grown_up",
}
DEFAULT_AGE = "big_kid"
CLOTHES = ("top", "bottom", "shoes")
MAX_NAME = 24
MAX_CATCHPHRASE_WORDS = 12
MAX_INTRO_WORDS = 15
MAX_REPLY = 200
MAX_QUESTION = 120
MAX_UNMATCHED = 60
SAFE_CATCHPHRASE = "Let's go on an adventure!"
SAFE_REPLY = "Here's your new character!"
NO_AGE = "Only people have an age. Leave the age out for robots and animals."
WRONG_FACE = "That face doesn't fit this kind of character. Pick another one!"
WRONG_CHOICE = "That choice isn't in our parts box. Pick one of the options!"
LOOK_NEEDS_ANSWER = "The look can only come with an answer to a question."
LOOK_WRONG_BODY = "That look is for a different kind of character."
ROLES = ("hero", "sidekick", "friend")


def body_type_for(kind: str, age: str | None) -> str:
    return AGE_BODY[age or DEFAULT_AGE] if kind == "person" else kind


def choice_ok(target: str, value: str, body: str, cat: Catalog | None = None) -> bool:
    """A part or palette colour that exists and fits this body type."""
    cat = cat or load_catalog()
    if target.startswith("colors."):
        slot = target.removeprefix("colors.")
        return slot in cat["color_slots"] and any(
            e["id"] == value for e in palette(slot, body, cat)
        )
    return target in categories_for(body, cat) and value in options_for(target, body, cat)


def apply_choice(spec: Spec, choice: CatalogChoice) -> Spec:
    if choice.target.startswith("colors."):
        slot = choice.target.removeprefix("colors.")
        hex_color = next(
            e["hex"] for e in palette(slot, spec["body_type"]) if e["id"] == choice.value
        )
        return normalize({**spec, "colors": {**spec["colors"], slot: hex_color}})
    new = normalize({**spec, "parts": {**spec["parts"], choice.target: choice.value}})
    return with_leggings(new) if choice.target == "top" else new


class Creator:
    def __init__(self, llm: LLMProvider | None, session: Session, user_id: str) -> None:
        self.llm = llm
        self.session = session
        self.user_id = user_id
        self.guard = Guard(llm, session, user_id)

    def create(self, req: CreateRequest) -> Created:
        cat = load_catalog()
        body = body_type_for(req.kind, req.age)
        self._check_request(req, body, cat)
        if req.name:
            character_safety.check_name(self.session, self.user_id, TARGET, req.name)
        description, notes = "", []
        if req.description:
            checked = character_safety.check_description(
                self.session, self.user_id, TARGET, req.description
            )
            description, notes = checked.text, checked.notes
        if description:
            self.guard.check_input(TARGET, {"description": description}, field_name="description")

        age = (req.age or DEFAULT_AGE) if req.kind == "person" else None
        look = self._look(req, body)
        # With a look, that's the character so far, minus its personality (never sent to Meta).
        base = (
            normalize({**look, "personality": {"traits": [], "catchphrase": ""}, "role": req.role})
            if look
            else self._base(body, age, req)
        )
        answer = req.follow_up_answer
        # The answer isn't part of the seed: answering a question keeps the same character.
        inputs = [body, age, req.face_shape, description, req.name]
        seed = zlib.crc32(json.dumps(inputs).encode())
        raw, source, fallback = self.guard.ask(
            lambda llm: helper_meta.create(
                llm,
                body_type=body,
                age=age,
                face_shape=req.face_shape,
                description=description,
                answer=f"{answer.target}={answer.value}" if answer else None,
                name=req.name,
                role=req.role,
                base=base,
                keep=look is not None,
            ),
            lambda: helper_offline.create(
                body, age, description, base, name=req.name, answered=answer is not None, seed=seed
            ),
            check=lambda r: build_spec(base, {**r, "body_type": body}),
            texts=lambda _r: {},  # every text is checked field by field in _finish
            target=TARGET,
        )
        return self._finish(req, body, base, raw, source, fallback, notes, seed, look)

    # ---- request ----------------------------------------------------------------------------

    def _check_request(self, req: CreateRequest, body: str, cat: Catalog) -> None:
        if req.age is not None and req.kind != "person":
            raise invalid(NO_AGE, "age")
        if req.face_shape and req.face_shape not in options_for("face_shape", body, cat):
            raise ApiError(422, "unknown_part", WRONG_FACE, "face_shape")
        answer = req.follow_up_answer
        if answer and not choice_ok(answer.target, answer.value, body, cat):
            raise ApiError(422, "unknown_part", WRONG_CHOICE, "follow_up_answer")

    def _look(self, req: CreateRequest, body: str) -> Spec | None:
        """The character so far (only with an answer), checked like a saved look."""
        if req.look is None:
            return None
        if req.follow_up_answer is None:
            raise invalid(LOOK_NEEDS_ANSWER, "look")
        try:
            look = validate(req.look.model_dump())
        except SpecError as error:
            raise ApiError(422, "unknown_part", str(error), "look") from error
        if look["body_type"] != body:
            raise invalid(LOOK_WRONG_BODY, "look")
        return look

    def _base(self, body: str, age: str | None, req: CreateRequest) -> Spec:
        spec = default_spec(body)
        spec["role"] = req.role
        if req.face_shape:
            spec["parts"]["face_shape"] = req.face_shape
        if age == "grandparent":
            spec["colors"]["hair"] = next(
                e["hex"] for e in palette("hair", body) if e["id"] == "grey"
            )
        return normalize(spec)

    # ---- answer -----------------------------------------------------------------------------

    def _replaced(self, what: str, reason: str) -> None:
        character_safety.log(self.session, self.user_id, TARGET, "replaced", [f"{what}:{reason}"])

    def _finish(
        self,
        req: CreateRequest,
        body: str,
        base: Spec,
        raw: Raw,
        source: str,
        fallback: bool,
        notes: list[str],
        seed: int,
        look: Spec | None = None,
    ) -> Created:
        raw = {**raw, "body_type": body}
        given = raw.get("parts")
        parts: dict[str, Any] = given if isinstance(given, dict) else {}
        # People are always clothed: a missing or unknown garment means the default outfit.
        if body in HUMAN and any(
            c in parts and parts[c] not in options_for(c, body) for c in CLOTHES
        ):
            defaults = load_catalog()["body_types"][body]["defaults"]["parts"]
            raw["parts"] = {**parts, **{c: defaults[c] for c in CLOTHES}}
            self._replaced("outfit", "not_clothed")
        picked = raw.get("traits")
        traits: list[Any] = picked if isinstance(picked, list) else []
        if any(t not in TRAITS for t in traits):
            self._replaced("traits", "not_on_list")  # build_spec drops them

        spec, _ = build_spec(base, raw)
        if req.face_shape:
            spec = normalize({**spec, "parts": {**spec["parts"], "face_shape": req.face_shape}})
        if req.follow_up_answer:
            spec = apply_choice(spec, req.follow_up_answer)
        if look is not None and req.follow_up_answer is not None:
            # No drift, whatever the model did: the look as sent, with only the answered choice
            # applied. Traits stay too (they're from the list); words come from this answer.
            kept = apply_choice({**look, "role": req.role}, req.follow_up_answer)
            traits = look["personality"]["traits"] or spec["personality"]["traits"]
            spec = {**kept, "personality": {**spec["personality"], "traits": traits}}
        role = str(raw.get("role_suggestion") or "")
        role_suggestion = (
            role if role in ROLES else helper_offline.role_for(spec["personality"]["traits"])
        )

        texts = self._texts(raw, body, source, seed, req.name, spec["personality"]["traits"])
        spec["personality"] = {**spec["personality"], "catchphrase": texts["catchphrase"]}
        reply = " ".join(
            part for part in (*notes, RESTING if fallback else "", texts["reply"]) if part
        )
        return Created.model_validate(
            {
                "spec": spec,
                "name_ideas": texts["names"],
                "catchphrase": texts["catchphrase"],
                "intro_line": texts["intro_line"],
                "follow_up": texts["follow_up"],
                "role_suggestion": role_suggestion,
                "notes": notes,
                "reply": reply,
                "unmatched": texts["unmatched"],
                "source": "meta" if source == "meta" else "mock",
                "fallback": fallback,
                "label": label(source),
            }
        )

    def _texts(
        self, raw: Raw, body: str, source: str, seed: int, name: str, traits: list[str]
    ) -> dict[str, Any]:
        names = [str(n).strip() for n in raw.get("name_ideas") or [] if str(n).strip()][:3]
        catchphrase = str(raw.get("catchphrase") or "").strip()
        intro = str(raw.get("intro_line") or "").strip()
        reply = str(raw.get("reply") or "").strip()
        unmatched = [str(u).strip() for u in raw.get("unmatched") or [] if str(u).strip()][:5]
        follow_up = self._follow_up(raw.get("follow_up"), body)

        # Lengths first.
        for n in [n for n in names if len(n) > MAX_NAME]:
            names.remove(n)
            self._replaced("name", "too_long")
        if len(catchphrase.split()) > MAX_CATCHPHRASE_WORDS or len(catchphrase) > 60:
            catchphrase = self._safe_catchphrase(traits, body, "too_long")
        if len(intro.split()) > MAX_INTRO_WORDS or len(intro) > 120:
            intro = ""
            self._replaced("intro_line", "too_long")
        if len(reply) > MAX_REPLY:
            reply = SAFE_REPLY
            self._replaced("reply", "too_long")
        unmatched = [u for u in unmatched if len(u) <= MAX_UNMATCHED]

        # Then the local checks, and the name rules.
        for n in list(names):
            if problem := character_safety.name_problem(n):
                names.remove(n)
                self._replaced("name", problem)
        if catchphrase and not safety.check_local({"catchphrase": catchphrase}).allowed:
            catchphrase = self._safe_catchphrase(traits, body, "word_list")
        if intro and not safety.check_local({"intro_line": intro}).allowed:
            intro = ""
            self._replaced("intro_line", "word_list")
        if reply and not safety.check_local({"reply": reply}).allowed:
            reply = SAFE_REPLY
            self._replaced("reply", "word_list")
        unmatched = [u for u in unmatched if safety.check_local({"unmatched": u}).allowed]
        if follow_up and not safety.check_local(self._follow_up_texts(follow_up)).allowed:
            follow_up = None
            self._replaced("follow_up", "word_list")

        # Meta's words also go through the classifier; if it can't answer, they count as unsafe.
        if source == "meta" and self.llm is not None:
            fields = {f"name.{i}": n for i, n in enumerate(names)}
            fields |= {"catchphrase": catchphrase, "intro_line": intro, "reply": reply}
            fields |= {f"unmatched.{i}": u for i, u in enumerate(unmatched)}
            if follow_up:
                fields |= self._follow_up_texts(follow_up)
            try:
                verdicts = safety.classify_each(self.llm, fields)
                bad = {
                    k: (v.categories or ["other"])[0] for k, v in verdicts.items() if not v.allowed
                }
            except safety.SafetyUnavailable:
                bad = {k: "unchecked" for k, v in fields.items() if v.strip()}
            for key, reason in bad.items():
                self._replaced(key.split(".")[0], reason)
            names = [n for i, n in enumerate(names) if f"name.{i}" not in bad]
            unmatched = [u for i, u in enumerate(unmatched) if f"unmatched.{i}" not in bad]
            if "catchphrase" in bad:
                catchphrase = self._fallback_catchphrase(traits, body)
            if "intro_line" in bad:
                intro = ""
            if "reply" in bad:
                reply = SAFE_REPLY
            if follow_up and any(k.startswith("follow_up") for k in bad):
                follow_up = None

        if not names:
            pool = helper_offline.offline_names(body, seed)
            names = [n for n in pool if not character_safety.name_problem(n)]
        who = name or names[0]
        return {
            "names": names,
            "catchphrase": catchphrase or self._fallback_catchphrase(traits, body),
            "intro_line": intro or f"Meet {who}, ready for adventure!",
            "reply": reply or SAFE_REPLY,
            "follow_up": follow_up,
            "unmatched": unmatched,
        }

    def _safe_catchphrase(self, traits: list[str], body: str, reason: str) -> str:
        self._replaced("catchphrase", reason)
        return self._fallback_catchphrase(traits, body)

    @staticmethod
    def _fallback_catchphrase(traits: list[str], body: str) -> str:
        return helper_offline.catchphrase_for(traits, body) or SAFE_CATCHPHRASE

    def _follow_up(self, value: Any, body: str) -> dict[str, Any] | None:
        """A follow-up whose every option is a catalog choice that fits, else None (logged)."""
        if not isinstance(value, dict):
            return None
        question = str(value.get("question") or "").strip()
        given = value.get("options")
        options: list[Any] = given if isinstance(given, list) else []
        if not question and not options:
            return None  # no question asked
        ok = (
            question
            and len(question) <= MAX_QUESTION
            and 2 <= len(options) <= 4
            and all(
                isinstance(o, dict)
                and 0 < len(str(o.get("label") or "").strip()) <= 40
                and choice_ok(str(o.get("target")), str(o.get("value")), body)
                for o in options
            )
        )
        if not ok:
            self._replaced("follow_up", "not_catalog")
            return None
        return {
            "question": question,
            "options": [
                {"label": str(o["label"]).strip(), "target": o["target"], "value": o["value"]}
                for o in options
            ],
        }

    @staticmethod
    def _follow_up_texts(follow_up: dict[str, Any]) -> dict[str, str]:
        texts = {"follow_up.question": follow_up["question"]}
        texts |= {f"follow_up.option.{i}": o["label"] for i, o in enumerate(follow_up["options"])}
        return texts
