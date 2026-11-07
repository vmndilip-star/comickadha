"""Safety checks on kids' words and on what the AI helper says back.

First a local word list; then, when a real LLM is set (LLM_PROVIDER=meta), a model-based
classifier. It fails closed: a hit blocks, and if the classifier can't answer, SafetyUnavailable is
raised so the caller never uses unchecked text. Every verdict is logged in moderation_log.
"""

import logging
import re
from dataclasses import dataclass, field

from sqlmodel import Session

from app.models import ModerationLog
from app.providers.llm import LLMError, LLMProvider

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

    def message(self, labels: dict[str, str]) -> str:
        what = labels.get(self.field_name or "", "words")
        return (
            f"Let's keep Comickatha friendly for everyone! Please change the {what} and try again."
        )


CLASSIFIER_CATEGORIES = [
    "violence",
    "weapons",
    "adult",
    "drugs",
    "self_harm",
    "hate",
    "bullying",
    "personal_info",
    "scary",
    "other",
]
CLASSIFIER_SYSTEM = (
    "You check text for Comickatha, a comic-making app for children under 16. "
    "Mark a text unsafe if it has violence or gore, weapons, adult or romantic content, drugs, "
    "alcohol or smoking, self-harm, hate or insults, bullying, personal information (real full "
    "names, addresses, phone numbers, schools, emails), or content too scary for young children. "
    "Silly, cartoon mischief, mild peril and everyday kid stuff are fine. "
    "Reply with one verdict for each numbered text, in order."
)


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
    names = [name for name, text in fields.items() if text.strip()]
    if not names:
        return Verdict(allowed=True)
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
    try:
        reply = llm.complete_json(
            CLASSIFIER_SYSTEM, prompt, schema, schema_name="safety_verdicts", max_tokens=300
        )
        verdicts = reply["verdicts"]
        if not isinstance(verdicts, list) or len(verdicts) != len(names):
            raise LLMError("The safety reply didn't cover every text.")
        for name, verdict in zip(names, verdicts, strict=True):
            if verdict.get("safe") is not True:
                categories = [str(c) for c in verdict.get("categories") or ["other"]]
                return Verdict(allowed=False, field_name=name, categories=sorted(set(categories)))
    except (LLMError, KeyError, TypeError, AttributeError) as error:
        log.warning("safety classifier unavailable: %s", type(error).__name__)
        raise SafetyUnavailable() from error
    return Verdict(allowed=True)


def check_text(fields: dict[str, str], llm: LLMProvider | None = None) -> Verdict:
    """The word list, then the classifier when an LLM is set (may raise SafetyUnavailable)."""
    verdict = check_words(fields)
    if verdict.allowed and llm is not None:
        verdict = classify(llm, fields)
    return verdict


def log_verdict(session: Session, user_id: str, target: str, verdict: Verdict, kind: str) -> None:
    session.add(
        ModerationLog(
            user_id=user_id,
            kind=kind,
            target=target[:120],
            verdict="allow" if verdict.allowed else "block",
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
