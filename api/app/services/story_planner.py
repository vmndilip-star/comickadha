"""The story planner: a kid's story -> scenes (step 1->2) -> a panel plan (step 2->3).

Two planners return the same Planned* models (schemas/studio.py):
- offline (the default, and the fallback when Meta is down): deterministic and always valid. It
  splits the synopsis into beats, walks through the cast and the scenes' places, and picks poses
  and expressions with keyword rules ("scared", "found", "laughed", ...).
- Meta (LLM_PROVIDER=meta): structured output whose JSON schema enums are the catalog's poses and
  expressions and this comic's own locked ids, so it can only name things that exist.

Every plan goes through Pydantic and then the semantic checks below. An invalid Meta plan is
retried once with the problems sent back; a second failure raises PlanFailed (the router turns it
into a friendly 422 and changes nothing). An outage, or words that don't pass safety, fall back
to the offline planner, labelled as such. The server, not the model, adds ids, sheet versions,
scale and bubble boxes.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ValidationError

from app.avatar.catalog import load_catalog
from app.prompts import render
from app.providers.llm import LLMError, LLMProvider
from app.schemas.common import MAX_PANEL_CAST
from app.schemas.studio import (
    PanelPlan,
    PlannedBubble,
    PlannedCharacter,
    PlannedPanel,
    PlannedScene,
    ScenePlan,
)
from app.services.ai_guard import Guard
from app.services.ai_limits import LIMITS
from app.services.kid_fields import KidFields
from app.services.strict_schema import strict_object

T = TypeVar("T")

SCENES_FOR = {4: 2, 6: 3, 8: 4}
MAX_WORDS = 12
POSITIONS_FOR = {1: ["center"], 2: ["left", "right"], 3: ["left", "center", "right"]}
NARRATOR = "narrator"


@dataclass(frozen=True)
class CastMember:
    id: str
    name: str
    sheet_version: int
    catchphrase: str = ""
    traits: tuple[str, ...] = ()


@dataclass(frozen=True)
class Place:
    id: str
    name: str
    description: str = ""


@dataclass(frozen=True)
class SceneInfo:
    id: str
    background_id: str
    character_ids: tuple[str, ...]
    summary: str


@dataclass
class StoryContext:
    title: str
    synopsis: str
    mood: str
    panel_count: int
    cast: list[CastMember]
    places: list[Place]
    scenes: list[SceneInfo] = field(default_factory=list)

    @property
    def cast_ids(self) -> list[str]:
        return [c.id for c in self.cast]

    @property
    def place_ids(self) -> list[str]:
        return [p.id for p in self.places]

    def member(self, character_id: str) -> CastMember | None:
        return next((c for c in self.cast if c.id == character_id), None)

    def place(self, place_id: str) -> Place | None:
        return next((p for p in self.places if p.id == place_id), None)


class PlanFailed(Exception):
    """The model's plan was invalid twice."""

    def __init__(self, problems: list[str]) -> None:
        super().__init__("; ".join(problems))
        self.problems = problems


def catalog_poses() -> list[str]:
    return list(load_catalog()["poses"])


def catalog_expressions() -> list[str]:
    return list(load_catalog()["expressions"])


def words(text: str) -> int:
    return len(text.split())


def clip_words(text: str, limit: int = MAX_WORDS) -> str:
    parts = text.split()
    return text if len(parts) <= limit else " ".join(parts[:limit]).rstrip(",;:") + "..."


# ---- semantic checks -----------------------------------------------------------------------------


def check_scenes(plan: ScenePlan, ctx: StoryContext) -> list[str]:
    problems: list[str] = []
    seen: set[str] = set()
    for i, scene in enumerate(plan.scenes, start=1):
        if scene.background_id not in ctx.place_ids:
            problems.append(f"scene {i}: background_id must be one of the locked places")
        if len(set(scene.character_ids)) != len(scene.character_ids):
            problems.append(f"scene {i}: a character is listed twice")
        for cid in scene.character_ids:
            if cid not in ctx.cast_ids:
                problems.append(f"scene {i}: {cid} is not a locked character in the cast")
        seen.update(scene.character_ids)
    for member in ctx.cast:
        if member.id not in seen:
            problems.append(f"{member.name} ({member.id}) must appear in at least one scene")
    return problems


THINKING = "thinking"
OPENING_MAX = 2  # how many of a character's lines may start with the same two words


def _words_of(text: str) -> list[str]:
    return re.findall(r"[a-z0-9']+", text.lower())


def opening(text: str) -> str:
    """How a line starts: its first two words, lower case, without punctuation."""
    return " ".join(_words_of(text)[:2])


def uses_catchphrase(text: str, catchphrase: str) -> bool:
    phrase = " ".join(_words_of(catchphrase))
    return bool(phrase) and f" {phrase} " in f" {' '.join(_words_of(text))} "


def dialogue_problems(plan: PanelPlan, ctx: StoryContext) -> list[str]:
    """The rules that keep dialogue fresh (Phase 7, A3 and A5), for the whole comic:
    - a character in the thinking pose has a think bubble or none (never talk or shout);
    - each character's catchphrase at most once in the comic;
    - the same two opening words start at most OPENING_MAX of a character's lines, and never two of
      their lines in a row."""
    problems: list[str] = []
    said: dict[str, list[tuple[int, str]]] = {}
    for i, panel in enumerate(plan.panels, start=1):
        thinking = {c.id for c in panel.characters if c.pose == THINKING}
        for b in panel.bubbles:
            if b.speaker == NARRATOR:
                continue
            if b.speaker in thinking and b.type in ("talk", "shout"):
                name = member.name if (member := ctx.member(b.speaker)) else b.speaker
                problems.append(
                    f"panel {i}: {name} is in the thinking pose, so their bubble must be a think "
                    "bubble (or no bubble)"
                )
            said.setdefault(b.speaker, []).append((i, b.text))
    for member in ctx.cast:
        lines = said.get(member.id, [])
        if member.catchphrase.strip():
            used = [i for i, text in lines if uses_catchphrase(text, member.catchphrase)]
            if len(used) > 1:
                problems.append(
                    f"{member.name}'s catchphrase is used in panels {', '.join(map(str, used))}: "
                    "use it at most once in the whole comic"
                )
        counts: dict[str, list[int]] = {}
        previous = ""
        for i, text in lines:
            start = opening(text)
            if not start:
                continue
            if start == previous:
                problems.append(
                    f"panel {i}: {member.name}'s line starts like their last one ({start!r}): "
                    "start it differently"
                )
            counts.setdefault(start, []).append(i)
            previous = start
        for start, panels in counts.items():
            if len(panels) > OPENING_MAX:
                problems.append(
                    f"{member.name} starts {len(panels)} lines with {start!r} (panels "
                    f"{', '.join(map(str, panels))}): use those words at most {OPENING_MAX} times"
                )
    return problems


def check_panels(plan: PanelPlan, ctx: StoryContext) -> list[str]:
    problems: list[str] = []
    poses, expressions = set(catalog_poses()), set(catalog_expressions())
    scene_cast = {s.id: (n, set(s.character_ids)) for n, s in enumerate(ctx.scenes, start=1)}
    if len(plan.panels) != ctx.panel_count:
        problems.append(f"there must be exactly {ctx.panel_count} panels, not {len(plan.panels)}")
    for i, panel in enumerate(plan.panels, start=1):
        if panel.scene_id not in scene_cast:
            problems.append(f"panel {i}: scene_id must be one of the scenes")
        else:
            n, in_scene = scene_cast[panel.scene_id]
            for c in panel.characters:
                if c.id in ctx.cast_ids and c.id not in in_scene:
                    name = member.name if (member := ctx.member(c.id)) else c.id
                    problems.append(
                        f"panel {i}: {name} isn't in scene {n}; use only that scene's characters"
                    )
        ids = [c.id for c in panel.characters]
        if len(set(ids)) != len(ids):
            problems.append(f"panel {i}: a character appears twice")
        positions = [c.position for c in panel.characters]
        if len(set(positions)) != len(positions):
            problems.append(f"panel {i}: two characters stand in the same position")
        for c in panel.characters:
            if c.id not in ctx.cast_ids:
                problems.append(f"panel {i}: {c.id} is not a locked character in the cast")
            if c.pose not in poses:
                problems.append(f"panel {i}: pose {c.pose!r} is not one of the catalog poses")
            if c.expression not in expressions:
                problems.append(f"panel {i}: expression {c.expression!r} is not in the catalog")
        for b in panel.bubbles:
            if b.speaker != NARRATOR and b.speaker not in ids:
                problems.append(f"panel {i}: speaker {b.speaker} is not in this panel")
            if (b.speaker == NARRATOR) != (b.type == "narrator"):
                problems.append(f"panel {i}: only the narrator uses narrator bubbles")
            if words(b.text) > MAX_WORDS:
                problems.append(f"panel {i}: bubble text must be {MAX_WORDS} words or fewer")
    return problems + dialogue_problems(plan, ctx)


def validation_problems(error: ValidationError) -> list[str]:
    return [f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in error.errors()][:10]


# ---- the offline planner -------------------------------------------------------------------------

_SENTENCE = re.compile(r"(?<=[.!?])\s+")
_CLAUSE = re.compile(r",\s+|\s+(?:and then|then|but|so)\s+")


def sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENTENCE.split(text.strip()) if s.strip()]


def split_into(items: list[T], n: int) -> list[list[T]]:
    """n groups in order, as even as possible (empty groups when there are too few items)."""
    out: list[list[T]] = []
    start = 0
    for i in range(n):
        size = len(items) // n + (1 if i < len(items) % n else 0)
        out.append(items[start : start + size])
        start += size
    return out


def _names(members: list[CastMember]) -> str:
    names = [m.name for m in members]
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]


def _shorten(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    cut = text[: limit - 1].rsplit(" ", 1)[0]
    return cut.rstrip(",;:") + "…"


def _place_for(text: str, ctx: StoryContext, fallback: Place) -> Place:
    lowered = text.lower()
    for place in ctx.places:
        keys = [w for w in re.findall(r"[a-z']+", place.name.lower()) if len(w) >= 4]
        if any(k in lowered for k in keys):
            return place
    return fallback


def offline_scenes(ctx: StoryContext) -> ScenePlan:
    n = SCENES_FOR.get(ctx.panel_count, 3)
    chunks = split_into(sentences(ctx.synopsis), n)
    scenes: list[PlannedScene] = []
    cast = ctx.cast
    for i, chunk in enumerate(chunks):
        text = " ".join(chunk)
        place = _place_for(text, ctx, ctx.places[i % len(ctx.places)])
        mentioned = [c for c in cast if c.name.lower() in text.lower()]
        if mentioned:
            members = mentioned
        elif len(cast) <= 2 or i == 0:
            members = cast[:MAX_PANEL_CAST]
        else:
            members = [cast[i % len(cast)], cast[(i + 1) % len(cast)]]
        summary = _shorten(text, 180) if text else _template_summary(i, n, members, place)
        scenes.append(
            PlannedScene(
                background_id=place.id, character_ids=[m.id for m in members], summary=summary
            )
        )
    # Everyone in the cast appears at least once: anyone left out joins the smallest scene (a
    # scene holds the whole cast if need be; a panel shows at most 3 of them).
    for member in cast:
        if not any(member.id in s.character_ids for s in scenes):
            min(scenes, key=lambda s: len(s.character_ids)).character_ids.append(member.id)
    return ScenePlan(scenes=scenes)


def _template_summary(i: int, n: int, members: list[CastMember], place: Place) -> str:
    who = _names(members)
    if i == 0:
        return f"{who} arrive at {place.name}."
    if i == n - 1:
        return f"{who} fix everything, and it all works out."
    return f"Something surprising happens at {place.name}!"


# Keyword rules: (word starts, pose, expression, line, bubble type). Each rule's lines are in
# LINES below: several, each starting differently, so long comics don't repeat themselves (A5).
RULES: list[tuple[tuple[str, ...], str, str, str, str]] = [
    (("scare", "afraid", "monster", "ghost", "dark", "spook", "scream", "shiver"),
     "scared_pose", "scared", "What was that?!", "shout"),
    (("found", "find", "discover", "clue", "spot", "footprint", "notice"),
     "point", "surprised", "Look what I found!", "talk"),
    (("laugh", "funny", "joke", "party", "danc", "silly", "giggl"),
     "jump", "laughing", "Ha ha! This is the best!", "talk"),
    (("win", "won", "saved", "hooray", "celebrat", "festival", "yay", "solved"),
     "celebrate", "laughing", "Hooray! We did it!", "shout"),
    (("sad", "lost", "cry", "miss", "sorry", "gone", "disappear"),
     "front", "sad", "Oh no... where did it go?", "talk"),
    (("angry", "grumpy", "mad", "cross", "unfair", "forgot"),
     "hands_on_hips", "angry", "Hmph! That's not fair!", "shout"),
    (("think", "wonder", "plan", "idea", "maybe", "puzzl", "confess", "explain"),
     "thinking", "surprised", "Hmm... I have an idea.", "think"),
    (("run", "chase", "race", "hurr", "escap", "fly", "blast"),
     "run", "surprised", "Quick, this way!", "shout"),
    (("walk", "follow", "go", "went", "arriv", "trail", "explor", "lead"),
     "walk", "happy", "Let's go and see!", "talk"),
    (("hello", "hi", "wave", "meet", "welcome", "start"),
     "wave", "happy", "Hello, everyone!", "talk"),
    (("sit", "rest", "picnic", "eat", "lunch", "snack"),
     "sit", "happy", "Time for a snack!", "talk"),
]  # fmt: skip
# More lines for each rule's first line, every one starting with different words.
LINES: dict[str, list[str]] = {
    "What was that?!": ["Did you hear that?", "Eek! Something moved!", "Stay close to me!"],
    "Look what I found!": ["Hey, come and see!", "Over here, a clue!", "Wow, check this out!"],
    "Ha ha! This is the best!": ["That's so funny!", "Hee hee, stop it!", "Best day ever!"],
    "Hooray! We did it!": ["Yes! We solved it!", "Woo-hoo, we won!", "Three cheers for us!"],
    "Oh no... where did it go?": ["This is so sad.", "I really miss it.", "Where could it be?"],
    "Hmph! That's not fair!": ["Hey, that's mine!", "Not again!", "That makes me cross!"],
    "Hmm... I have an idea.": ["What if we try this?", "Let me think...", "Maybe it's nearby?"],
    "Quick, this way!": ["Run, run, run!", "Hurry up, everyone!", "Faster, we're close!"],
    "Let's go and see!": ["Follow me, team!", "This way, friends!", "Keep going, nearly there!"],
    "Hello, everyone!": ["Hi there, friends!", "Welcome, welcome!", "Nice to meet you!"],
    "Time for a snack!": ["Yum, I'm hungry!", "Pass the sandwiches, please!", "Picnic time!"],
}

OPENERS = {
    "mystery": "Something strange was happening at {place}...",
    "funny": "It was a very silly day at {place}.",
    "adventure": "An adventure was about to begin at {place}!",
    "spooky": "It was a spooky evening at {place}...",
}
EXTRA_LINES = [
    "Let's do this!", "What should we do next?", "Come on, follow me!", "I knew it!",
    "That was close!", "Good thinking!", "Wait for me!", "You can do it!", "Watch this!",
    "Are you ready?", "We make a great team!", "Just one more try!",
]  # fmt: skip
CLOSERS = {
    "mystery": "And that is how the mystery was solved!",
    "funny": "Everyone laughed all the way home. The end!",
    "adventure": "What an adventure! The end.",
    "spooky": "And the spooky night ended with big smiles.",
}


def mood_for(beat: str) -> tuple[str, str, str | None, str]:
    """(pose, expression, line or None for the default, bubble type) for a beat. The keyword
    that comes first in the beat wins ("disappears before the festival" is sad, not a party)."""
    for word in re.findall(r"[a-z']+", beat.lower()):
        for starts, pose, expression, line, kind in RULES:
            if any(word.startswith(s) for s in starts):
                return pose, expression, line, kind
    return "front", "happy", None, "talk"


def _capitalised(text: str) -> str:
    return text[:1].upper() + text[1:]


def _beats(
    summary: str, k: int, members: list[CastMember], place: Place, offset: int = 0
) -> list[str]:
    parts = [p for s in sentences(summary) for p in _CLAUSE.split(s) if p.strip()]
    parts = [p.strip().rstrip(".!?") for p in parts] or [summary.strip().rstrip(".!?")]
    if len(parts) >= k:
        return [_capitalised(_shorten(" ".join(g), 100)) for g in split_into(parts, k)]
    # Filler beats take turns between the scene's characters, so everyone gets a moment.
    names = [m.name for m in members] or ["Everyone"]
    templates = ["{who} explores {place}", "{who} has an idea", "{who} decides what to do"]
    extra = [
        templates[(offset + i) % len(templates)].format(
            who=names[(offset + i + 1) % len(names)], place=place.name
        )
        for i in range(k)
    ]
    return [_capitalised(_shorten(p, 100)) for p in (parts + extra)[:k]]


def on_stage(members: list[T], lead: T, turn: int) -> list[T]:
    """Who is in a panel: the whole scene if it fits (3), else 3 of them taking turns from panel
    to panel so everyone gets on stage, always with the lead, in the scene's order."""
    if len(members) <= MAX_PANEL_CAST:
        return members
    start = turn * MAX_PANEL_CAST
    shown = [members[(start + k) % len(members)] for k in range(MAX_PANEL_CAST)]
    if lead not in shown:
        shown[-1] = lead
    return sorted(shown, key=members.index)


class Voices:
    """What each character has said so far, so the offline planner keeps the dialogue rules: a
    catchphrase once, the same two opening words at most OPENING_MAX times, never twice in a row."""

    def __init__(self) -> None:
        self.openings: dict[str, list[str]] = {}
        self.catchphrase_said: set[str] = set()

    def fresh(self, speaker: str, text: str) -> bool:
        start = opening(text)
        used = self.openings.get(speaker, [])
        return bool(start) and (not used or used[-1] != start) and used.count(start) < OPENING_MAX

    def say(self, speaker: str, text: str) -> None:
        self.openings.setdefault(speaker, []).append(opening(text))

    def pick(self, speaker: str, options: list[str]) -> str | None:
        """The first option that keeps the rules (then remembered), or None if none does."""
        for text in options:
            if self.fresh(speaker, text):
                self.say(speaker, text)
                return text
        return None


def _speech(
    lead: CastMember, line: str | None, kind: str, index: int, voices: Voices, beat: str
) -> PlannedBubble:
    """The lead's bubble: their catchphrase once (if the beat has no line of its own), else a fresh
    line. When every line is used up, the narrator tells the beat instead."""
    catchphrase = lead.catchphrase if 0 < words(lead.catchphrase) <= MAX_WORDS else ""
    fresh = catchphrase and lead.id not in voices.catchphrase_said
    if not line and fresh and voices.fresh(lead.id, catchphrase):
        voices.catchphrase_said.add(lead.id)
        voices.say(lead.id, catchphrase)
        return PlannedBubble(speaker=lead.id, type="talk", text=clip_words(catchphrase))
    if line:
        options = [line, *LINES.get(line, [])]
    else:
        start = index % len(EXTRA_LINES)
        options = EXTRA_LINES[start:] + EXTRA_LINES[:start]
        kind = "talk"
    said = voices.pick(lead.id, options)
    if said is None:
        return PlannedBubble(speaker=NARRATOR, type="narrator", text=clip_words(beat + "."))
    return PlannedBubble(speaker=lead.id, type=kind, text=clip_words(said))


def offline_panels(ctx: StoryContext) -> PanelPlan:
    scenes = ctx.scenes
    counts = [len(group) for group in split_into(list(range(ctx.panel_count)), len(scenes))]
    panels: list[PlannedPanel] = []
    voices = Voices()
    for scene, count in zip(scenes, counts, strict=True):
        members = [m for cid in scene.character_ids if (m := ctx.member(cid))] or ctx.cast[:1]
        place = ctx.place(scene.background_id) or Place(scene.background_id, "the scene")
        for j, beat in enumerate(_beats(scene.summary, count, members, place, len(panels))):
            pose, expression, line, kind = mood_for(beat)
            # The one the beat is about leads (and speaks); otherwise take turns.
            named = [m for m in members if m.name.lower() in beat.lower()]
            lead = named[0] if named else members[j % len(members)]
            shown = on_stage(members, lead, j)
            positions = POSITIONS_FOR[len(shown)]
            characters = [
                PlannedCharacter(
                    id=m.id,
                    pose=pose if m is lead or pose in ("walk", "run") else "front",
                    expression=expression,
                    position=positions[k],
                )
                for k, m in enumerate(shown)
            ]
            index = len(panels)
            if index == 0:
                text = OPENERS.get(ctx.mood, OPENERS["adventure"]).format(place=place.name)
                bubble = PlannedBubble(speaker=NARRATOR, type="narrator", text=clip_words(text))
            elif index == ctx.panel_count - 1:
                text = CLOSERS.get(ctx.mood, CLOSERS["adventure"])
                bubble = PlannedBubble(speaker=NARRATOR, type="narrator", text=text)
            else:
                bubble = _speech(lead, line, kind, index, voices, beat)
                # A thinking character thinks in a cloud (A3): never a talk or shout bubble.
                if lead.id == bubble.speaker and bubble.type in ("talk", "shout"):
                    for c in characters:
                        if c.id == lead.id and c.pose == THINKING:
                            bubble = bubble.model_copy(update={"type": "think"})
            panels.append(
                PlannedPanel(scene_id=scene.id, beat=beat, characters=characters, bubbles=[bubble])
            )
    return PanelPlan(panels=panels)


# ---- Meta's planner -------------------------------------------------------------------------


def scenes_schema(ctx: StoryContext) -> dict[str, Any]:
    scene = strict_object(
        {
            "background_id": {"type": "string", "enum": ctx.place_ids},
            "character_ids": {"type": "array", "items": {"type": "string", "enum": ctx.cast_ids}},
            "summary": {"type": "string"},
        }
    )
    return strict_object({"scenes": {"type": "array", "items": scene}})


def panels_schema(ctx: StoryContext) -> dict[str, Any]:
    character = strict_object(
        {
            "id": {"type": "string", "enum": ctx.cast_ids},
            "pose": {"type": "string", "enum": catalog_poses()},
            "expression": {"type": "string", "enum": catalog_expressions()},
            "position": {"type": "string", "enum": ["left", "center", "right"]},
        }
    )
    bubble = strict_object(
        {
            "speaker": {"type": "string", "enum": [*ctx.cast_ids, NARRATOR]},
            "type": {"type": "string", "enum": ["talk", "think", "shout", "narrator"]},
            "text": {"type": "string"},
        }
    )
    panel = strict_object(
        {
            "scene_id": {"type": "string", "enum": [s.id for s in ctx.scenes]},
            "beat": {"type": "string"},
            "characters": {"type": "array", "items": character},
            "bubbles": {"type": "array", "items": bubble},
        }
    )
    return strict_object({"panels": {"type": "array", "items": panel}})


def planner_fields(ctx: StoryContext) -> KidFields:
    """Every kid-written field story_lines() and ask_panels() put in the prompt, for one classifier
    call before Meta sees any of it (services/kid_fields.py)."""
    fields = KidFields()
    fields.add_title_and_story(ctx.title, ctx.synopsis)
    for i, s in enumerate(ctx.scenes, start=1):
        fields.add(f"scenes.{s.id}.summary", s.summary, f"the summary of scene {i}")
    for i, c in enumerate(ctx.cast):
        fields.add_character(i, c.id, c.name, c.catchphrase)
    for i, p in enumerate(ctx.places):
        fields.add_place(i, p.id, p.name, p.description)
    return fields


def story_lines(ctx: StoryContext) -> list[str]:
    """The story facts for the prompt; every kid-written one is in planner_fields()."""
    lines = [f"Title: {ctx.title or '(no title yet)'}", f"Mood: {ctx.mood}"]
    lines.append(f"Synopsis: {ctx.synopsis}")
    lines.append("Cast:")
    for c in ctx.cast:
        traits = ", ".join(c.traits) or "none"
        lines.append(f"- id {c.id}: {c.name} (traits: {traits}; catchphrase: {c.catchphrase!r})")
    lines.append("Places:")
    for p in ctx.places:
        lines.append(f"- id {p.id}: {p.name}. {p.description}".rstrip())
    return lines


def _retry_lines(problems: list[str]) -> list[str]:
    if not problems:
        return []
    return ["", "Your last answer had these problems. Fix them:", *(f"- {p}" for p in problems)]


def ask_scenes(llm: LLMProvider, ctx: StoryContext, problems: list[str]) -> dict[str, Any]:
    n = SCENES_FOR.get(ctx.panel_count, 3)
    prompt = "\n".join([*story_lines(ctx), *_retry_lines(problems)])
    return llm.complete_json(
        render("planner_scenes", scene_count=n),
        prompt,
        scenes_schema(ctx),
        schema_name="scene_plan",
        max_tokens=LIMITS["plan_scenes"].max_tokens,
        timeout=LIMITS["plan_scenes"].timeout,
    )


def ask_panels(llm: LLMProvider, ctx: StoryContext, problems: list[str]) -> dict[str, Any]:
    lines = [*story_lines(ctx), "Scenes (in order):"]
    for i, s in enumerate(ctx.scenes, start=1):
        place = ctx.place(s.background_id)
        who = ", ".join(f"{m.name} ({m.id})" for cid in s.character_ids if (m := ctx.member(cid)))
        lines.append(
            f"{i}. id {s.id}: at {place.name if place else s.background_id}; "
            f"characters: {who}; what happens: {s.summary}"
        )
    prompt = "\n".join([*lines, *_retry_lines(problems)])
    return llm.complete_json(
        render("planner_panels", panel_count=ctx.panel_count),
        prompt,
        panels_schema(ctx),
        schema_name="panel_plan",
        max_tokens=LIMITS["plan_panels"].max_tokens,
        timeout=LIMITS["plan_panels"].timeout,
    )


# ---- planning with fallback ------------------------------------------------------------------

Plan = TypeVar("Plan", bound=BaseModel)


@dataclass
class Outcome(Generic[Plan]):
    plan: Plan
    source: str  # "meta" or "mock"
    fallback: bool


def _plan(
    guard: Guard,
    ctx: StoryContext,
    model: type[Plan],
    ask: Callable[[LLMProvider, StoryContext, list[str]], dict[str, Any]],
    check: Callable[[Plan, StoryContext], list[str]],
    offline: Callable[[StoryContext], Plan],
    texts: Callable[[Plan], dict[str, str]],
    target: str,
) -> Outcome[Plan]:
    def from_offline(fallback: bool) -> Outcome[Plan]:
        plan = offline(ctx)
        problems = check(plan, ctx)
        if problems:  # a bug, never the kid's fault
            raise PlanFailed(problems)
        return Outcome(plan, "mock", fallback)

    if not guard.may_ask_meta or guard.llm is None:
        return from_offline(fallback=guard.llm is not None)
    problems: list[str] = []
    for _attempt in range(2):
        try:
            raw = ask(guard.llm, ctx, problems)
        except LLMError:
            return from_offline(fallback=True)  # Meta is down
        try:
            plan = model.model_validate(raw)
            problems = check(plan, ctx)
        except ValidationError as error:
            problems = validation_problems(error)
        if not problems:
            if guard.output_ok(target, texts(plan)):
                return Outcome(plan, "meta", False)
            return from_offline(fallback=True)  # words that didn't pass safety are never shown
    raise PlanFailed(problems)


def scene_texts(plan: ScenePlan) -> dict[str, str]:
    return {f"scene {i}": s.summary for i, s in enumerate(plan.scenes, start=1)}


def panel_texts(plan: PanelPlan) -> dict[str, str]:
    out: dict[str, str] = {}
    for i, p in enumerate(plan.panels, start=1):
        out[f"panel {i} beat"] = p.beat
        out[f"panel {i} bubbles"] = " / ".join(b.text for b in p.bubbles)
    return out


def plan_scenes(guard: Guard, ctx: StoryContext) -> Outcome[ScenePlan]:
    return _plan(guard, ctx, ScenePlan, ask_scenes, check_scenes, offline_scenes, scene_texts,
                 "studio:scenes")  # fmt: skip


def plan_panels(guard: Guard, ctx: StoryContext) -> Outcome[PanelPlan]:
    return _plan(guard, ctx, PanelPlan, ask_panels, check_panels, offline_panels, panel_texts,
                 "studio:panels")  # fmt: skip
