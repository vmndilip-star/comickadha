"""Safety checks before anything is drawn. Phase 3: a local word list; Phase 4 adds an LLM.

It fails closed: anything on the list blocks the request, and every verdict is logged.
"""

import re
from dataclasses import dataclass, field

from sqlmodel import Session

from app.models import ModerationLog

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


def check_text(fields: dict[str, str]) -> Verdict:
    """Checks each named text field; returns the first field that hits the list."""
    for name, text in fields.items():
        words = set(_WORD.findall(text.lower()))
        hits = sorted(category for category, bad in BLOCKLIST.items() if words & bad)
        if hits:
            return Verdict(allowed=False, field_name=name, categories=hits)
    return Verdict(allowed=True)


def check_and_log(session: Session, user_id: str, target: str, fields: dict[str, str]) -> Verdict:
    verdict = check_text(fields)
    session.add(
        ModerationLog(
            user_id=user_id,
            kind="text",
            target=target[:120],
            verdict="allow" if verdict.allowed else "block",
            categories=verdict.categories,
        )
    )
    session.commit()
    return verdict
