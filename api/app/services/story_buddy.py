"""The Story Buddy: helps a kid think about their story, but never writes it for them.

- idea: 1-2 short questions ("What clue could Mira find first?").
- spelling: the text with spelling, capitals and full stops fixed, plus a list of changes; the kid
  accepts or ignores it.
- name_scene: 3 fun titles for a scene.

Answers come from Meta's API through the shared Guard (input and output both go through safety,
with the offline buddy as the fallback) or from the offline buddy below. Story sparks for the
Home page are hand-written here.
"""

import random
import re
import zlib
from dataclasses import dataclass, field, replace
from typing import Any

from sqlmodel import Session

from app.moods import mood_info, mood_line
from app.prompts import render
from app.providers.llm import LLMProvider
from app.schemas.studio import BuddyAction, BuddyReply, Spark, SpellingChange
from app.services.ai_guard import RESTING, Guard, InvalidReply, label
from app.services.ai_limits import LIMITS
from app.services.kid_fields import KidFields, check_before_meta
from app.services.strict_schema import strict_object

Raw = dict[str, Any]

SPARKS: list[str] = [
    "A dragon who is scared of the dark gets a nightlight from a surprising friend.",
    "Your hero wakes up and every cat in town can suddenly talk.",
    "A robot tries to bake a birthday cake for the first time.",
    "The school goldfish goes missing the night before the science fair.",
    "Two best friends find a door in a tree that wasn't there yesterday.",
    "A grandma who used to be a pirate tells one last treasure story.",
    "It rains jelly beans, and nobody knows why.",
    "A shy ghost wants to join the school play.",
    "Your hero's shadow decides to go on an adventure without them.",
    "A lost puppy leads everyone on a chase across the park.",
    "The moon falls asleep and forgets to come out.",
    "A snowman wants to see the summer beach.",
    "The class pet hamster becomes the school's best detective.",
    "A treasure map is hidden inside a library book.",
    "Someone keeps leaving kind notes, and nobody knows who.",
    "A bear opens a pancake café in the woods.",
    "Your hero shrinks to the size of a pea for one whole day.",
    "A rocket made of cardboard boxes really takes off.",
    "The world's slowest snail enters the big race.",
    "A wizard's spell goes wrong and turns homework into butterflies.",
    "Two rival robots have to work together to fix the town clock.",
    "A cloud that loves to draw makes pictures in the sky.",
    "The new kid at school can speak to plants.",
    "A dinosaur egg hatches in the classroom.",
    "Everyone's socks go missing on the same morning.",
    "A friendly monster under the bed is afraid of kids.",
    "Your hero finds a remote control that pauses time.",
    "A seagull steals a sandwich and starts a beach adventure.",
    "A giant turnip grows in the school garden overnight.",
    "A superhero loses their cape right before saving the day.",
]

# Common spelling slips by young writers: wrong -> right (lower case).
SPELLINGS: dict[str, str] = {
    "teh": "the", "freind": "friend", "freinds": "friends", "frend": "friend", "frends": "friends",
    "becuase": "because", "becasue": "because", "becaus": "because", "beacuse": "because",
    "wierd": "weird", "recieve": "receive", "alot": "a lot", "untill": "until",
    "beleive": "believe", "belive": "believe", "definately": "definitely",
    "tommorow": "tomorrow", "tomorow": "tomorrow", "thier": "their", "wich": "which",
    "realy": "really", "finaly": "finally", "sudenly": "suddenly", "suddenley": "suddenly",
    "begining": "beginning", "dont": "don't", "cant": "can't", "wont": "won't", "didnt": "didn't",
    "isnt": "isn't", "wasnt": "wasn't", "im": "I'm", "ive": "I've", "i": "I", "scool": "school",
    "skool": "school", "monky": "monkey", "monkys": "monkeys", "favourit": "favourite",
    "favorit": "favorite", "beutiful": "beautiful", "butiful": "beautiful", "wen": "when",
    "wat": "what", "becos": "because", "peple": "people", "evry": "every", "evryone": "everyone",
    "togehter": "together", "togather": "together", "dosent": "doesn't", "probly": "probably",
    "mistery": "mystery", "adventur": "adventure", "spooki": "spooky", "planit": "planet",
}  # fmt: skip


@dataclass(frozen=True)
class BuddyContext:
    title: str
    synopsis: str
    mood: str
    cast_names: list[str]
    place_names: list[str]
    # Ids in the same order as the names (for field names in safety blocks).
    cast_ids: list[str] = field(default_factory=list)
    place_ids: list[str] = field(default_factory=list)


def spark(after: int | None = None) -> Spark:
    """A random spark, never the same one twice in a row."""
    choices = [i for i in range(len(SPARKS)) if i != after]
    index = random.choice(choices)
    return Spark(index=index, text=SPARKS[index])


# ---- the offline buddy ----------------------------------------------------------------------


def _pick(options: list[str], seed: int, count: int) -> list[str]:
    return random.Random(seed).sample(options, k=min(count, len(options)))


def offline_idea(text: str, ctx: BuddyContext) -> Raw:
    name = ctx.cast_names[0] if ctx.cast_names else "your hero"
    other = ctx.cast_names[1] if len(ctx.cast_names) > 1 else "a new friend"
    place = ctx.place_names[0] if ctx.place_names else "the first place"
    by_mood = [q.format(name=name, place=place) for q in mood_info(ctx.mood).questions]
    general = [
        f"What does {name} want most of all?",
        f"How could {name} and {other} work together?",
        f"How does {name} feel when things go wrong?",
        f"What surprise is waiting at {place}?",
        "How does your story end: a laugh, a hug or a new mystery?",
    ]
    seed = zlib.crc32(f"{text}|{ctx.title}".encode())
    questions = _pick(by_mood, seed, 1) + _pick(general, seed, 1)
    return {"questions": questions, "reply": "Here are some questions to think about:"}


def offline_spelling(text: str) -> Raw:
    changes: list[dict[str, str]] = []

    def fix(match: re.Match[str]) -> str:
        word = match.group(0)
        right = SPELLINGS.get(word.lower())
        if right is None or right == word:
            return word
        if word[:1].isupper() and right[:1].islower():
            right = right[:1].upper() + right[1:]
        changes.append({"before": word, "after": right})
        return right

    fixed = re.sub(r"[A-Za-z']+", fix, text)
    # Capital letters at the start of sentences, and a full stop at the end.
    capped = re.sub(r"(^|[.!?]\s+)([a-z])", lambda m: m.group(1) + m.group(2).upper(), fixed)
    if capped != fixed:
        changes.append({"before": "small letters", "after": "capital letters at the start"})
    if capped.strip() and capped.rstrip()[-1] not in ".!?\"'":
        capped = capped.rstrip() + "."
        changes.append({"before": "no full stop", "after": "a full stop at the end"})
    reply = (
        "I fixed a few things. Tap Use it if you like it!"
        if changes
        else ("Your spelling looks great! Nothing to fix.")
    )
    return {"corrected": capped, "changes": changes, "reply": reply}


def offline_name_scene(text: str, ctx: BuddyContext) -> Raw:
    words = mood_info(ctx.mood).title_words
    place = next((p for p in ctx.place_names if p.lower() in text.lower()), None)
    noun = (place or (ctx.place_names[0] if ctx.place_names else "Day")).split()[-1].title()
    name = next((n for n in ctx.cast_names if n.lower() in text.lower()), None) or (
        ctx.cast_names[0] if ctx.cast_names else "The Hero"
    )
    seed = zlib.crc32(text.encode())
    rng = random.Random(seed)
    titles = [
        f"The {rng.choice(words)} {noun}",
        f"{name}'s Big {rng.choice(['Surprise', 'Discovery', 'Plan', 'Idea'])}",
        f"Trouble at the {noun}" if ctx.mood != "funny" else f"Chaos at the {noun}",
    ]
    return {"titles": titles, "reply": "How about one of these?"}


# ---- with Meta, through the Guard -----------------------------------------------------------


STRINGS = {"type": "array", "items": {"type": "string"}}
SCHEMAS: dict[str, dict[str, Any]] = {
    "idea": strict_object({"questions": STRINGS, "reply": {"type": "string"}}),
    "spelling": strict_object(
        {
            "corrected": {"type": "string"},
            "changes": {
                "type": "array",
                "items": strict_object({"before": {"type": "string"}, "after": {"type": "string"}}),
            },
            "reply": {"type": "string"},
        }
    ),
    "name_scene": strict_object({"titles": STRINGS, "reply": {"type": "string"}}),
}


def _check(action: str, text: str) -> Any:
    def check(raw: Raw) -> bool:
        if action == "idea":
            qs = raw["questions"]
            # Questions only, never story text.
            if not 1 <= len(qs) <= 2 or not all(str(q).strip().endswith("?") for q in qs):
                raise InvalidReply("questions")
            return all(len(str(q).split()) <= 25 for q in qs)
        if action == "spelling":
            corrected = str(raw["corrected"])
            # A spelling fix keeps the kid's words: no rewrites.
            return bool(corrected.strip()) and abs(len(corrected) - len(text)) <= max(
                20, len(text) // 4
            )
        return len(raw["titles"]) == 3 and all(len(str(t).split()) <= 8 for t in raw["titles"])

    return check


def _texts(raw: Raw) -> dict[str, str]:
    return {
        "reply": str(raw.get("reply", "")),
        "questions": " / ".join(str(q) for q in raw.get("questions", [])),
        "corrected": str(raw.get("corrected", "")),
        "titles": " / ".join(str(t) for t in raw.get("titles", [])),
    }


def buddy_fields(text: str, ctx: BuddyContext) -> KidFields:
    """Every kid-written field _prompt() puts in the prompt (the synopsis isn't in it), for one
    classifier call before Meta sees any of it (services/kid_fields.py)."""
    fields = KidFields()
    fields.add("buddy", text, "your words")
    fields.add_title_and_story(ctx.title)
    for i, name in enumerate(ctx.cast_names):
        fields.add_character(i, ctx.cast_ids[i] if i < len(ctx.cast_ids) else str(i), name)
    for i, name in enumerate(ctx.place_names):
        fields.add_place(i, ctx.place_ids[i] if i < len(ctx.place_ids) else str(i), name)
    return fields


def _prompt(text: str, ctx: BuddyContext) -> str:
    return "\n".join(
        [
            f"Title: {ctx.title or '(no title yet)'}",
            f"Mood: {mood_line(ctx.mood)}",
            f"Characters: {', '.join(ctx.cast_names) or 'none yet'}",
            f"Places: {', '.join(ctx.place_names) or 'none yet'}",
            f"The child's text: {text!r}",
        ]
    )


class Buddy:
    def __init__(self, llm: LLMProvider | None, session: Session, user_id: str) -> None:
        self.guard = Guard(llm, session, user_id)

    def answer(self, action: BuddyAction, text: str, ctx: BuddyContext) -> BuddyReply:
        text = text.strip()
        if action == "spelling" and not text:
            return self._reply(
                action, {"corrected": "", "changes": [], "reply": NOTHING}, "mock", False
            )
        # The kid's words and every story word the prompt carries, in one classifier call. The
        # title may still be "pending" from autosave (decision 55): it's checked here, before Meta.
        guard = self.guard
        checked = check_before_meta(
            guard.session, guard.user_id, f"buddy:{action}", buddy_fields(text, ctx), guard.llm
        )
        guard.offline_only = checked.pending
        if checked.left_out:  # places whose words didn't pass stay out of the prompt (decision 89)
            keep = [i for i, pid in enumerate(ctx.place_ids) if pid not in checked.left_out]
            ctx = replace(
                ctx,
                place_names=[ctx.place_names[i] for i in keep],
                place_ids=[ctx.place_ids[i] for i in keep],
            )

        def offline() -> Raw:
            if action == "idea":
                return offline_idea(text, ctx)
            if action == "spelling":
                return offline_spelling(text)
            return offline_name_scene(text, ctx)

        raw, source, fallback = self.guard.ask(
            lambda llm: llm.complete_json(
                render(f"buddy_{action}"),
                _prompt(text, ctx),
                SCHEMAS[action],
                schema_name=f"buddy_{action}",
                max_tokens=LIMITS[f"buddy_{action}"].max_tokens,
                timeout=LIMITS[f"buddy_{action}"].timeout,
            ),
            offline,
            check=_check(action, text),
            texts=_texts,
            target=f"buddy:{action}:reply",
        )
        return self._reply(action, raw, source, fallback)

    def _reply(self, action: BuddyAction, raw: Raw, source: str, fallback: bool) -> BuddyReply:
        reply = str(raw.get("reply", "")).strip()[:200]
        if fallback:
            reply = f"{RESTING} {reply}".strip()
        corrected = raw.get("corrected")
        return BuddyReply(
            action=action,
            questions=[str(q).strip()[:160] for q in raw.get("questions", [])][:2],
            corrected=str(corrected)[:600] if corrected is not None else None,
            changes=[SpellingChange.model_validate(c) for c in raw.get("changes", [])][:20],
            titles=[str(t).strip()[:60] for t in raw.get("titles", [])][:3],
            reply=reply,
            source="meta" if source == "meta" else "mock",
            fallback=fallback,
            label=label(source),
        )


NOTHING = "Write a little of your story first, then I'll check the spelling!"
