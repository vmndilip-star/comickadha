"""Character safety (docs/character-safety.md): checks on a kid's description and on names.

A description is checked in this order, stopping at the first block: length, personal info, the
word list, real people, rule-bending. Then words about weight or body shape are taken out (not
blocked): the character is made without them, with a kind note. Blocks are a 422 "unsafe" with a
message under the field; nothing is sent to any model. Every decision goes to moderation_log.
With Meta on, the classifier runs next (Guard.check_input), including its real_person category.
"""

import re
from dataclasses import dataclass, field
from typing import Any

from sqlmodel import Session

from app.avatar.catalog import load_catalog
from app.errors import ApiError
from app.models import ModerationLog
from app.services import safety
from app.services.safety import REAL_PERSON, Verdict

MAX_DESCRIPTION = 300
TOO_LONG = "That's a lot of words! Keep your description under 300 letters."
RULE_BENDING = "Let's stick to the Comickadha rules and keep building together!"
BODY_NOTE = "Every character is awesome just as they are!"
LABELS = {"description": "description", "name": "name"}

RELATIONS = (
    r"(?:baby\s+|big\s+|little\s+|best\s+|step)?"
    r"(?:sister|brother|sis|bro|mum|mom|mummy|mommy|mother|dad|daddy|father|parents?|teacher|"
    r"miss|sir|friend|bestie|classmate|cousin|aunt|auntie|aunty|uncle|grandma|grandpa|granny|"
    r"grandad|granddad|grandmother|grandfather|nana|nani|dadi|nanu|dada|neighbou?r|coach|"
    r"principal|headteacher|boyfriend|girlfriend|crush|babysitter|nanny)"
)
# "look like my sister", "be like my teacher", "based on my friend", "my classmate Priya".
_REAL_PERSON = [
    re.compile(
        rf"\b(?:look|looks|looking|be|is|act|acts|dressed|dress|dresses)\s+(?:just\s+|exactly\s+)?"
        rf"like\s+(?:my|our)\s+(?:\w+\s+)?{RELATIONS}\b",
        re.IGNORECASE,
    ),
    re.compile(
        rf"\b(?:based\s+on|copy\s+of|same\s+as|version\s+of|just\s+like|exactly\s+like|"
        rf"looks\s+the\s+same\s+as)\s+(?:my|our)\s+(?:\w+\s+)?{RELATIONS}\b",
        re.IGNORECASE,
    ),
    # A relation followed by a capitalised name names a real person: "my classmate Priya".
    re.compile(rf"\b(?i:my|our)\s+(?i:{RELATIONS})\s+[A-Z][a-z]+"),
    # "looks like Taylor Swift": a capitalised full name after "look like".
    re.compile(
        r"\b(?i:look|looks|looking)\s+(?i:just\s+|exactly\s+)?(?i:like)\s+[A-Z][a-z]+\s+[A-Z][a-z]+"
    ),
]
# Well-known real people kids might name. Short on purpose: the classifier covers the rest.
FAMOUS = {
    *("taylor swift", "beyonce", "beyoncé", "rihanna", "ariana grande", "billie eilish"),
    *("selena gomez", "justin bieber", "harry styles", "ed sheeran", "michael jackson"),
    *("lionel messi", "messi", "cristiano ronaldo", "ronaldo", "neymar", "mbappe", "mbappé"),
    *("virat kohli", "sachin tendulkar", "dhoni", "lebron james", "serena williams"),
    *("usain bolt", "simone biles", "shah rukh khan", "salman khan", "amitabh bachchan"),
    *("priyanka chopra", "deepika padukone", "zendaya", "tom holland", "dwayne johnson"),
    *("mrbeast", "mr beast", "pewdiepie", "elon musk", "bill gates", "mark zuckerberg"),
    *("jeff bezos", "donald trump", "joe biden", "barack obama", "narendra modi"),
    *("king charles", "queen elizabeth", "prince harry", "kim kardashian", "kylie jenner"),
    *("greta thunberg", "kamala harris", "rishi sunak", "keir starmer"),
}
_FAMOUS = re.compile(
    r"\b(?:" + "|".join(re.escape(n) for n in sorted(FAMOUS)) + r")\b", re.IGNORECASE
)
_RULE_BENDING = re.compile(
    r"\bignore\s+(?:(?:all|the|your|any|previous|those|these|every)\s+)*"
    r"(?:rules?|instructions?|guidelines?|filters?)\b"
    r"|\b(?:forget|break|bypass|skip|disable|turn\s+off)\s+(?:(?:all|the|your|any)\s+)*"
    r"(?:rules?|instructions?|filters?|safety)\b"
    r"|\bpretend(?:ing|s)?\b"
    r"|\bwithout\s+(?:(?:any|his|her|their|its)\s+)?(?:clothes|clothing|a\s+top|a\s+shirt|pants|trousers)\b"
    r"|\bno\s+(?:clothes|clothing)\b"
    r"|\b(?:undressed|topless|underwear|lingerie|bikini)\b"
    r"|\b(?:jailbreak|developer\s+mode|system\s+prompt|disregard)\b"
    r"|\byou\s+are\s+now\b|\bact\s+as\b",
    re.IGNORECASE,
)
# Weight and body-shape words: taken out, never sent on ("thin eyebrows" stays: a real part).
_BODY = re.compile(
    r"\s*\b(?:(?:very|really|super|so|too|a\s+bit|kind\s+of|quite|extra|a\s+little)\s+)?"
    r"(?:fat|fatter|fattest|fatty|skinny|skinnier|chubby|chubbier|plump|podgy|pudgy|tubby|"
    r"overweight|obese|scrawny|bony|chunky|curvy|thin(?!\s+(?:eye)?brows)|thinner|"
    r"slim(?!\s+(?:eye)?brows)|slender|big\s+belly|big\s+tummy|beer\s+belly|weight|weighs)\b",
    re.IGNORECASE,
)


@dataclass
class Checked:
    """A description that passed: the text to use (body words taken out) and kind notes."""

    text: str
    notes: list[str] = field(default_factory=list)


def is_real_person(text: str) -> bool:
    return bool(_FAMOUS.search(text)) or any(p.search(text) for p in _REAL_PERSON)


def is_rule_bending(text: str) -> bool:
    return bool(_RULE_BENDING.search(text))


def strip_body_words(text: str) -> tuple[str, bool]:
    """(text without weight or body-shape words, whether any were taken out)."""
    cleaned = _BODY.sub("", text)
    if cleaned == text:
        return text, False
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    cleaned = re.sub(r"\s+([,.!?])", r"\1", cleaned).strip(" ,")
    return cleaned, True


def _block(
    session: Session, user_id: str, target: str, field_name: str, verdict: Verdict
) -> ApiError:
    verdict.field_name = field_name
    safety.log_verdict(session, user_id, target, verdict, "text")
    return ApiError(422, "unsafe", verdict.message(LABELS), field_name)


def check_description(
    session: Session, user_id: str, target: str, text: str, field_name: str = "description"
) -> Checked:
    """The local description checks, in order. Raises 422 "unsafe" on a block."""
    if len(text) > MAX_DESCRIPTION:
        raise _block(
            session, user_id, target, field_name, Verdict(False, None, ["length"], TOO_LONG)
        )
    verdict = safety.check_personal({field_name: text})
    if verdict.allowed:
        verdict = safety.check_words({field_name: text})
    if not verdict.allowed:
        raise _block(session, user_id, target, field_name, verdict)
    if is_real_person(text):
        raise _block(
            session, user_id, target, field_name, Verdict(False, None, ["real_person"], REAL_PERSON)
        )
    if is_rule_bending(text):
        raise _block(
            session,
            user_id,
            target,
            field_name,
            Verdict(False, None, ["rule_bending"], RULE_BENDING),
        )
    cleaned, removed = strip_body_words(text)
    if removed:
        log(session, user_id, target, "filtered", ["body_comment"])
        return Checked(cleaned, [BODY_NOTE])
    return Checked(text)


def name_problem(name: str) -> str | None:
    """Why a name can't be used ("word_list", "personal_info", "famous", "real_person"), or None."""
    verdict = safety.check_local({"name": name})
    if not verdict.allowed:
        return verdict.categories[0] if verdict.categories else "word_list"
    if _FAMOUS.search(name):
        return "famous"
    if is_real_person(name) or re.search(rf"\b(?i:my|our)\s+(?i:{RELATIONS})\b", name):
        return "real_person"
    return None


def check_name(session: Session, user_id: str, target: str, name: str) -> None:
    """A name the kid typed: 422 "unsafe" (under the name field) if it can't be used."""
    problem = name_problem(name)
    if problem is None:
        return
    message = REAL_PERSON if problem in ("famous", "real_person") else None
    if problem == "personal_info":
        message = safety.check_personal({"name": name}).kid_message
    raise _block(session, user_id, target, "name", Verdict(False, None, [problem], message))


def log(session: Session, user_id: str, target: str, verdict: str, categories: list[str]) -> None:
    """A moderation_log row for a decision that isn't allow/block: "filtered", "replaced"."""
    session.add(
        ModerationLog(
            user_id=user_id,
            kind="text",
            target=target[:120],
            verdict=verdict,
            categories=categories,
        )
    )
    session.commit()


def tagged(group: str, option_id: str, tag: str) -> bool:
    """Whether a catalog option ("headwear"/"hijab", "extras"/"glasses_star") carries a tag."""
    cat = load_catalog()
    options: dict[str, Any] = (
        cat["extras"] if group == "extras" else cat["categories"][group]["options"]
    )
    return tag in options.get(option_id, {}).get("tags", [])


def respectful_extras(parts: dict[str, str], extras: list[str]) -> list[str]:
    """Surprise me: cultural or religious headwear is never paired with silly items."""
    if not tagged("headwear", parts.get("headwear", "none"), "cultural"):
        return extras
    return [e for e in extras if not tagged("extras", e, "silly")]
