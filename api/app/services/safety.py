"""Safety checks on kids' words and on what the AI helper says back.

First a local word list; then, when a real LLM is set (LLM_PROVIDER=meta), a model-based
classifier. It fails closed: a hit blocks, and if the classifier can't answer, SafetyUnavailable is
raised so the caller never uses unchecked text. Every verdict is logged in moderation_log.

Story text is the exception (decision 55): during a Meta outage, words that pass the local checks
are allowed but `pending` ("not yet AI-checked"). They are drawn by the offline planner only, never
sent to Meta, re-checked in the background (services/recheck.py), and PDF export waits for that.
"""

import logging
import re
from dataclasses import dataclass, field

from sqlmodel import Session

from app.models import ModerationLog
from app.prompts import render
from app.providers.llm import LLMError, LLMProvider
from app.services.ai_limits import LIMITS

log = logging.getLogger(__name__)

# Whole words only, matched case-insensitively. Kept short and clear-cut on purpose.
BLOCKLIST: dict[str, set[str]] = {
    "violence": {
        "kill",
        "killed",
        "killing",
        "murder",
        "blood",
        "bloody",
        "gore",
        "gory",
        "stab",
        "stabbed",
        "torture",
    },
    "weapons": {"gun", "guns", "pistol", "rifle", "bomb", "bombs", "weapon", "weapons"},
    "adult": {"sexy", "naked", "nude", "porn"},
    "drugs": {
        "drugs",
        "cocaine",
        "heroin",
        "weed",
        "beer",
        "vodka",
        "whiskey",
        "alcohol",
        "cigarette",
        "cigarettes",
        "vape",
        "smoking",
    },
    "self_harm": {"suicide"},
}

_WORD = re.compile(r"[a-z]+")


@dataclass
class Verdict:
    allowed: bool
    field_name: str | None = None
    categories: list[str] = field(default_factory=list)
    # A message about this kind of block (personal info, safety helper resting), if any.
    kid_message: str | None = None
    # Story text that passed the local checks while the classifier couldn't answer (decision 55):
    # allowed for drawing, "not yet AI-checked", re-checked in the background.
    pending: bool = False

    def message(self, labels: dict[str, str]) -> str:
        if self.kid_message:
            return self.kid_message
        what = labels.get(self.field_name or "", "words")
        return (
            f"Let's keep Comickatha friendly for everyone! Please change the {what} and try again."
        )


# ---- personal info a kid shouldn't share -------------------------------------------------------

SECRET_ADDRESS = "Let's keep real addresses secret! Try a made-up place instead."
SECRET_PHONE = "Let's keep phone numbers secret! Please take it out of your story."
SECRET_EMAIL = "Let's keep email addresses secret! Please take it out of your story."
SECRET_SCHOOL = 'Let\'s keep school names secret! Call it "the school" or "Class 3B" instead.'
SECRET_NAME = "Let's keep real full names secret! First names or made-up names are great."
SECRET_DETAILS = "Let's keep personal details secret! Please take them out and try again."
REAL_PERSON = "Let's make up a brand-new character instead!"

_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
# Runs of digits with spaces, dots, dashes or brackets between them; 7+ digits is a phone number.
_PHONE = re.compile(r"\+?\(?\d[\d\s().-]{5,}\d")
_STREET = (
    r"Street|St|Road|Rd|Avenue|Ave|Lane|Ln|Drive|Dr|Close|Way|Court|Ct|Crescent|Place|"
    r"Boulevard|Blvd|Terrace|Nagar|Marg|Gali"
)
_ADDRESS = re.compile(
    rf"\b\d{{1,5}}[a-z]?,?\s+(?:[A-Za-z][\w'-]*\s+){{1,3}}(?i:{_STREET})\b"
    r"|(?i:\b(?:i|we|they|he|she)\s+lives?\s+(?:at|on)\s+\d)"
)
# A capitalised name followed by a school word: "Sunnyhill Primary", "St Mary's School".
_SCHOOL = re.compile(
    r"\b(?:[A-Z][\w'.-]*\s+){1,4}(?:School|Academy|Primary|Elementary|High School|College|"
    r"Vidyalaya|Convent)\b"
)
# Self-identifying full names: "my name is Priya Sharma", "my teacher is Anna Bello".
_FULL_NAME = re.compile(
    r"(?i:\b(?:my\s+name\s+is|i\s+am|i'm|im|my\s+(?:mum|mom|dad|teacher|friend|brother|sister|"
    r"grandma|grandpa)(?:'s\s+name)?\s+is))\s+[A-Z][a-z]+\s+[A-Z][a-z]+"
)


def _has_phone(text: str) -> bool:
    return any(sum(ch.isdigit() for ch in m.group()) >= 7 for m in _PHONE.finditer(text))


def check_personal(fields: dict[str, str]) -> Verdict:
    """Phone numbers, emails, street addresses, school names and real full names."""
    for name, text in fields.items():
        for found, message in (
            (_has_phone(text), SECRET_PHONE),
            (bool(_EMAIL.search(text)), SECRET_EMAIL),
            (bool(_ADDRESS.search(text)), SECRET_ADDRESS),
            (bool(_SCHOOL.search(text)), SECRET_SCHOOL),
            (bool(_FULL_NAME.search(text)), SECRET_NAME),
        ):
            if found:
                return Verdict(False, name, ["personal_info"], message)
    return Verdict(allowed=True)


CLASSIFIER_CATEGORIES = [
    "violence",
    "weapons",
    "adult",
    "drugs",
    "self_harm",
    "hate",
    "bullying",
    "personal_info",
    "real_person",
    "scary",
    "other",
]
KID_MESSAGES = {"personal_info": SECRET_DETAILS, "real_person": REAL_PERSON}


class SafetyUnavailable(Exception):
    """The classifier couldn't answer, so the text can't be called safe."""


def check_words(fields: dict[str, str]) -> Verdict:
    """Checks each named text field against the word list; returns the first field that hits."""
    for name, text in fields.items():
        words = set(_WORD.findall(text.lower()))
        hits = sorted(category for category, bad in BLOCKLIST.items() if words & bad)
        if hits:
            return Verdict(allowed=False, field_name=name, categories=hits)
    return Verdict(allowed=True)


def classify(llm: LLMProvider, fields: dict[str, str]) -> Verdict:
    """The model-based check. Raises SafetyUnavailable if the model doesn't answer properly."""
    for verdict in classify_each(llm, fields).values():
        if not verdict.allowed:
            return verdict
    return Verdict(allowed=True)


def classify_each(llm: LLMProvider, fields: dict[str, str]) -> dict[str, Verdict]:
    """One classifier call for every field; a verdict per (non-empty) field, in order.
    Raises SafetyUnavailable if the model doesn't answer properly."""
    names = [name for name, text in fields.items() if text.strip()]
    if not names:
        return {}
    schema = {
        "type": "object",
        "properties": {
            "verdicts": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "safe": {"type": "boolean"},
                        "categories": {
                            "type": "array",
                            "items": {"type": "string", "enum": CLASSIFIER_CATEGORIES},
                        },
                    },
                    "required": ["safe", "categories"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["verdicts"],
        "additionalProperties": False,
    }
    prompt = "\n".join(f"{i}. {fields[name]!r}" for i, name in enumerate(names, start=1))
    out: dict[str, Verdict] = {}
    try:
        reply = llm.complete_json(
            render("safety_classifier"),
            prompt,
            schema,
            schema_name="safety_verdicts",
            max_tokens=LIMITS["classifier"].max_tokens,
            timeout=LIMITS["classifier"].timeout,
        )
        verdicts = reply["verdicts"]
        if not isinstance(verdicts, list) or len(verdicts) != len(names):
            raise LLMError("The safety reply didn't cover every text.")
        for name, verdict in zip(names, verdicts, strict=True):
            if verdict.get("safe") is True:
                out[name] = Verdict(allowed=True)
                continue
            categories = sorted({str(c) for c in verdict.get("categories") or ["other"]})
            message = next((KID_MESSAGES[c] for c in categories if c in KID_MESSAGES), None)
            out[name] = Verdict(False, name, categories, message)
    except (LLMError, KeyError, TypeError, AttributeError) as error:
        log.warning("safety classifier unavailable: %s", type(error).__name__)
        raise SafetyUnavailable() from error
    return out


def check_local(fields: dict[str, str]) -> Verdict:
    """The instant, free checks: personal info, then the word list. Nothing leaves the machine."""
    verdict = check_personal(fields)
    return check_words(fields) if verdict.allowed else verdict


def check_text(fields: dict[str, str], llm: LLMProvider | None = None) -> Verdict:
    """The local checks, then the classifier when an LLM is set (may raise SafetyUnavailable)."""
    verdict = check_local(fields)
    if verdict.allowed and llm is not None:
        verdict = classify(llm, fields)
    return verdict


def log_verdict(session: Session, user_id: str, target: str, verdict: Verdict, kind: str) -> None:
    session.add(
        ModerationLog(
            user_id=user_id,
            kind=kind,
            target=target[:120],
            verdict="pending" if verdict.pending else ("allow" if verdict.allowed else "block"),
            categories=verdict.categories,
        )
    )
    session.commit()


def check_and_log(
    session: Session,
    user_id: str,
    target: str,
    fields: dict[str, str],
    llm: LLMProvider | None = None,
) -> Verdict:
    """check_text plus a moderation_log row. A classifier outage is logged as a block."""
    try:
        verdict = check_text(fields, llm)
    except SafetyUnavailable:
        log_verdict(session, user_id, target, Verdict(False, None, ["unavailable"]), "text")
        raise
    log_verdict(session, user_id, target, verdict, "text")
    return verdict


def check_story(
    session: Session,
    user_id: str,
    target: str,
    fields: dict[str, str],
    llm: LLMProvider | None = None,
) -> Verdict:
    """For story text: the local checks, then the classifier when an LLM is set, logged.
    A classifier outage doesn't block (decision 55): text that passed the local checks comes back
    allowed but `pending` ("not yet AI-checked"), and must not be sent to Meta until re-checked."""
    try:
        verdict = check_text(fields, llm)
    except SafetyUnavailable:
        verdict = Verdict(True, None, ["unavailable"], pending=True)
    log_verdict(session, user_id, target, verdict, "text")
    return verdict


PNG_SIGNATURE = bytes.fromhex("89504e470d0a1a0a")
IMAGE_UNCHECKED = "That picture couldn't be checked. Try painting the place again!"
IMAGE_FLAGS = ("safe_for_kids", "shows_real_person", "has_text_or_logos", "is_scary")
IMAGE_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {flag: {"type": "boolean"} for flag in IMAGE_FLAGS},
    "required": list(IMAGE_FLAGS),
    "additionalProperties": False,
}


def classify_image(llm: LLMProvider, png: bytes) -> Verdict:
    """One vision call (META_VISION_MODEL). A block lists why: "unsafe", "real_person", "text",
    "scary". Raises SafetyUnavailable if the model doesn't answer properly."""
    limit = LIMITS["image_check"]
    try:
        reply = llm.complete_json(
            render("image_safety"),
            "Check this picture.",
            IMAGE_SCHEMA,
            schema_name="image_safety",
            image_png=png,
            max_tokens=limit.max_tokens,
            timeout=limit.timeout,
        )
        flags = {flag: reply[flag] for flag in IMAGE_FLAGS}
    except (LLMError, KeyError, TypeError) as error:
        log.warning("image check unavailable: %s", type(error).__name__)
        raise SafetyUnavailable() from error
    if not all(isinstance(value, bool) for value in flags.values()):
        raise SafetyUnavailable()
    # Each flag must be exactly the safe answer, so anything unexpected blocks.
    categories = [
        name
        for name, bad in (
            ("unsafe", not flags["safe_for_kids"]),
            ("real_person", flags["shows_real_person"]),
            ("text", flags["has_text_or_logos"]),
            ("scary", flags["is_scary"]),
        )
        if bad
    ]
    return Verdict(allowed=not categories, categories=categories)


def check_image(
    session: Session,
    user_id: str,
    target: str,
    png: bytes | None,
    llm: LLMProvider | None = None,
) -> Verdict:
    """A picture before a kid sees it, logged like text verdicts (kind "image").

    With an LLM: one vision call that fails closed (a block or an outage is not allowed; an outage
    is the category "unavailable"). Without one: only "is it a PNG?". Pictures from the mock image
    provider are drawn on this machine from words that already passed the checks, so callers pass
    an LLM only for pictures from a real image model (Phase 6a)."""
    if png is not None and not png.startswith(PNG_SIGNATURE):
        verdict = Verdict(False, None, ["not_png"], IMAGE_UNCHECKED)
    elif png is None or llm is None:
        verdict = Verdict(allowed=True)
    else:
        try:
            verdict = classify_image(llm, png)
        except SafetyUnavailable:
            verdict = Verdict(False, None, ["unavailable"], IMAGE_UNCHECKED)
    log_verdict(session, user_id, target, verdict, "image")
    return verdict
