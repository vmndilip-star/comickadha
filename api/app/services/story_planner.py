"""The story planner: a kid's story -> scenes (step 1->2) -> a panel plan (step 2->3).

Two planners return the same Planned* models (schemas/studio.py):
- offline (the default, and the fallback when Meta is down): deterministic and always valid. It
  splits the synopsis into beats, walks through the cast and the scenes' places, and picks poses
  and expressions with keyword rules ("scared", "found", "laughed", ...).
- Meta (LLM_PROVIDER=meta): structured output whose JSON schema enums are the catalog's poses and
  expressions and this comic's own locked ids, so it can only name things that exist.

Every plan goes through Pydantic and then the semantic checks below. An invalid Meta plan is
retried once with the problems sent back; a second failure raises PlanFailed for scenes (the
router turns it into a friendly 422 and changes nothing) and falls back to the offline planner for
a part of the panel plan. An outage, or words that don't pass safety, fall back to the offline
planner, labelled as such. The server, not the model, adds ids, sheet versions, scale and bubble
boxes.

Panels are planned a part at a time (Phase 7 part C; one call can't write 30 panels): each scene,
or a run of a big scene's panels, is its own call with its own checks, a few at once
(services/plan_job.py). Each catchphrase is given to one part beforehand, so parts planned at the
same time can't both use it; a comic-wide pass then asks again only the parts whose line openings
clash with another part's, and `repair_dialogue` settles anything left.
"""

import json
import re
from collections import Counter
from collections.abc import Callable, Collection, Mapping, Sequence
from dataclasses import dataclass, field, replace
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ValidationError

from app.avatar.catalog import load_catalog
from app.moods import mood_info, mood_line
from app.prompts import render
from app.props import PROP_IDS, PROPS, STATES
from app.providers.llm import LLMError, LLMProvider
from app.schemas.studio import (
    PanelPlan,
    PlannedBubble,
    PlannedCharacter,
    PlannedPanel,
    PlannedProp,
    PlannedScene,
    ScenePlan,
)
from app.services.ai_guard import Guard
from app.services.ai_limits import LIMITS, PANELS_PER_CALL
from app.services.kid_fields import KidFields
from app.services.prop_rules import add_named_props, prop_problems
from app.services.strict_schema import strict_object

T = TypeVar("T")

# About a scene per 4 panels, at most 8, with a clear beginning, middle and end (part C). Any
# panel count from 4 to MAX_PANELS works (Phase 8): it takes the scenes of the nearest count below.
# Above 30 the scenes stay at 8, the most the scene call's limits were measured on (decision 128):
# the scenes just get longer, and plan_parts writes a long scene PANELS_PER_CALL panels at a time.
SCENES_FOR = {4: 2, 6: 3, 8: 4, 10: 3, 16: 4, 20: 5, 25: 7, 30: 8}


def scenes_for(panel_count: int) -> int:
    """How many scenes the scene planner makes for a comic of this many panels."""
    return SCENES_FOR[max(k for k in SCENES_FOR if k <= max(panel_count, 4))]


MAX_WORDS = 12
POSITIONS_FOR = {
    1: ["center"],
    2: ["left", "right"],
    3: ["left", "center", "right"],
    4: ["far_left", "left", "right", "far_right"],
    5: ["far_left", "left", "center", "right", "far_right"],
}
POSITIONS = ["far_left", "left", "center", "right", "far_right"]
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
    # Phase 8: kept exactly as the kid set them.
    time_of_day: str = "day"
    key_moment: str = ""
    panel_count: int | None = None


def scene_position(index: int, count: int) -> str:
    """Where a scene sits in the story: "beginning" (about the first quarter), "end" (the second
    half: in a mystery the reveal comes there) or "middle". The first scene is always the
    beginning and the last the end."""
    if index == 0 or count <= 1:
        return "beginning"
    if index == count - 1:
        return "end"
    share = index / count
    return "beginning" if share < 0.25 else "end" if share >= 0.5 else "middle"


POSITION_BRIEF = {
    "beginning": "This scene is at the beginning of the story: set things up (who, where, what the "
    "problem is). Nothing gets solved yet.",
    "middle": "This scene is in the middle of the story: build it up with clues, tries and "
    "surprises. Nobody solves the mystery or finds out who did it yet.",
    "end": "This scene is near the end of the story: now it may reveal what happened and settle "
    "it, but only the way the child's scene says.",
}
TIME_BRIEF = {
    "day": "",
    "sunset": "It happens at sunset (the place is drawn at sunset).",
    "night": "It happens at night (the place is drawn at night): a torch helps people see.",
}
ASLEEP = "asleep"


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


def dialogue_problems(
    plan: PanelPlan,
    ctx: StoryContext,
    *,
    catchphrase_ok: Collection[str] | None = None,
    avoid: Mapping[str, Collection[str]] | None = None,
) -> list[str]:
    """The rules that keep dialogue fresh (Phase 7, A3 and A5):
    - a character in the thinking pose has a think bubble or none (never talk or shout);
    - each character's catchphrase at most once in the comic (when a part of the comic is checked,
      only the characters in `catchphrase_ok` may say theirs there);
    - the same two opening words start at most OPENING_MAX of a character's lines, and never two of
      their lines in a row (`avoid`: openings other parts use, when a part is asked again)."""
    problems: list[str] = []
    said: dict[str, list[tuple[int, str]]] = {}
    for i, panel in enumerate(plan.panels, start=1):
        thinking = {c.id for c in panel.characters if c.pose == THINKING}
        asleep = {c.id for c in panel.characters if c.pose == ASLEEP}
        for b in panel.bubbles:
            if b.speaker == NARRATOR:
                continue
            if b.speaker in asleep:
                name = member.name if (member := ctx.member(b.speaker)) else b.speaker
                problems.append(
                    f"panel {i}: {name} is asleep, so they can't have a bubble: give the words to "
                    "someone awake, or to the narrator"
                )
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
            if used and catchphrase_ok is not None and member.id not in catchphrase_ok:
                problems.append(
                    f"panel {used[0]}: {member.name}'s catchphrase is saved for another scene: "
                    "don't use it here"
                )
            elif len(used) > 1:
                problems.append(
                    f"panel {used[-1]}: {member.name}'s catchphrase is used in panels "
                    f"{', '.join(map(str, used))}: use it at most once in the whole comic"
                )
        taken = set((avoid or {}).get(member.id, ()))
        counts: dict[str, list[int]] = {}
        previous = ""
        for i, text in lines:
            start = opening(text)
            if not start:
                continue
            if start in taken:
                problems.append(
                    f"panel {i}: other scenes already start {member.name}'s lines with {start!r}: "
                    "start this one differently"
                )
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
                    f"panel {panels[-1]}: {member.name} starts {len(panels)} lines with {start!r} "
                    f"(panels {', '.join(map(str, panels))}): use those words at most "
                    f"{OPENING_MAX} times"
                )
    return problems


def check_panels(
    plan: PanelPlan,
    ctx: StoryContext,
    *,
    catchphrase_ok: Collection[str] | None = None,
    avoid: Mapping[str, Collection[str]] | None = None,
) -> list[str]:
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
        problems += [f"panel {i}: {p}" for p in panel_prop_problems(panel)]
        for b in panel.bubbles:
            if b.speaker != NARRATOR and b.speaker not in ids:
                problems.append(f"panel {i}: speaker {b.speaker} is not in this panel")
            if (b.speaker == NARRATOR) != (b.type == "narrator"):
                problems.append(f"panel {i}: only the narrator uses narrator bubbles")
            if words(b.text) > MAX_WORDS:
                problems.append(f"panel {i}: bubble text must be {MAX_WORDS} words or fewer")
    return problems + dialogue_problems(plan, ctx, catchphrase_ok=catchphrase_ok, avoid=avoid)


PROP_NAMES = {p.id: p.name.lower() for p in PROPS.values()}


def panel_prop_problems(panel: PlannedPanel) -> list[str]:
    """A panel's props: held or worn by someone in it (a turban may sit on the scarecrow), and
    every prop its bubbles and captions name is drawn (services/prop_rules.py)."""
    problems: list[str] = []
    here = {c.id for c in panel.characters}
    ids = [p.id for p in panel.props]
    for prop in panel.props:
        holder = prop.held_by
        if (
            holder
            and holder not in here
            and not (holder in ids and holder in PROPS[prop.id].worn_by_props)
        ):
            problems.append(
                f"the {PROP_NAMES[prop.id]} is held by {holder}, who isn't in this panel"
            )
    saved = [p.saved() for p in panel.props]
    return problems + prop_problems(panel.bubbles, saved, PROP_NAMES)


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


@dataclass(frozen=True)
class ScenePart:
    """A slice of the panel plan that one Meta call writes: a scene's panels, or a run of them
    when the scene has more than PANELS_PER_CALL. Parts are planned a few at once (part C)."""

    scene: SceneInfo
    scene_no: int  # 1-based
    scene_total: int
    first: int  # the comic-wide index of the part's first panel
    count: int
    piece: int  # which run of the scene's panels, 1-based
    pieces: int
    scene_first: int  # the comic-wide index of the scene's first panel
    scene_count: int  # the scene's share of the panels
    # Cast ids whose catchphrase may be said here (once): each catchphrase belongs to one part.
    catchphrases: frozenset[str] = frozenset()
    # The scene's key moment, given to the scene's last run: one of its panels must show it.
    key_moment: str = ""

    @property
    def indexes(self) -> range:
        return range(self.first, self.first + self.count)


def scene_shares(
    panel_count: int, scene_count: int, chosen: Sequence[int | None] | None = None
) -> list[int]:
    """Each scene's panels: the number the kid gave a scene (Phase 8), and the rest shared out as
    evenly as possible among the others, earlier scenes first. They add up to panel_count (the
    router checks there are enough panels to go round)."""
    picked = list(chosen) if chosen is not None else [None] * scene_count
    free = [i for i, n in enumerate(picked) if not n]
    left = max(0, panel_count - sum(n for n in picked if n))
    shares = [len(g) for g in split_into(list(range(left)), len(free))] if free else []
    out = [n or 0 for n in picked]
    for i, share in zip(free, shares, strict=True):
        out[i] = share
    return out


def plan_parts(ctx: StoryContext) -> list[ScenePart]:
    """The comic's panels as parts, in order. Each catchphrase goes to one part its character is
    in: the part with the fewest so far, then the earliest."""
    parts: list[ScenePart] = []
    first = 0
    total = len(ctx.scenes)
    chosen = [s.panel_count for s in ctx.scenes]
    for n, (scene, share) in enumerate(
        zip(ctx.scenes, scene_shares(ctx.panel_count, total, chosen), strict=True), start=1
    ):
        runs = split_into(list(range(share)), max(1, -(-share // PANELS_PER_CALL)))
        start = first
        for piece, run in enumerate(runs, start=1):
            if run:
                moment = scene.key_moment.strip() if piece == len(runs) else ""
                parts.append(
                    ScenePart(
                        scene,
                        n,
                        total,
                        start,
                        len(run),
                        piece,
                        len(runs),
                        first,
                        share,
                        key_moment=moment,
                    )  # fmt: skip
                )
            start += len(run)
        first += share
    owners: list[set[str]] = [set() for _ in parts]
    for member in ctx.cast:
        if not 0 < words(member.catchphrase) <= MAX_WORDS:
            continue
        options = [i for i, p in enumerate(parts) if member.id in p.scene.character_ids]
        if options:
            owners[min(options, key=lambda i: (len(owners[i]), i))].add(member.id)
    return [replace(p, catchphrases=frozenset(owners[i])) for i, p in enumerate(parts)]


def part_context(ctx: StoryContext, part: ScenePart) -> StoryContext:
    """The story as one part sees it: its own scene and its own number of panels."""
    return replace(ctx, panel_count=part.count, scenes=[part.scene])


def check_part(
    plan: PanelPlan,
    ctx: StoryContext,
    part: ScenePart,
    avoid: Mapping[str, Collection[str]] | None = None,
) -> list[str]:
    """check_panels for one part: its count, its scene's characters, its catchphrases, and its
    scene's key moment when this part shows it."""
    problems = check_panels(
        plan, part_context(ctx, part), catchphrase_ok=part.catchphrases, avoid=avoid
    )
    if part.key_moment and plan.panels and not any(p.key_moment for p in plan.panels):
        k = key_panel(len(plan.panels))
        problems.append(
            f"panel {k}: show the scene's key moment here and set key_moment true: "
            f"{part.key_moment}"
        )
    return problems


def key_panel(count: int) -> int:
    """Where a part shows its key moment when it must choose (1-based): about two thirds in."""
    return max(1, min(count, round(count * 2 / 3 + 0.34)))


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
    n = scenes_for(ctx.panel_count)
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
            members = list(cast)  # the story starts with everyone
        else:
            members = [cast[i % len(cast)], cast[(i + 1) % len(cast)]]
        summary = _shorten(text, 180) if text else _template_summary(i, n, members, place)
        scenes.append(
            PlannedScene(
                background_id=place.id,
                character_ids=[m.id for m in members],
                summary=summary,
                time_of_day=time_of(text),
                key_moment=moment_of(chunk),
            )
        )
    # Everyone in the cast appears at least once: anyone left out joins the smallest scene (a
    # scene, and a panel, can hold the whole cast).
    for member in cast:
        if not any(member.id in s.character_ids for s in scenes):
            min(scenes, key=lambda s: len(s.character_ids)).character_ids.append(member.id)
    return ScenePlan(scenes=scenes)


TIMES = {
    "night": ("night", "midnight", "moon", "moonlight", "stars", "dark"),
    "sunset": ("sunset", "evening", "dusk", "twilight"),
}
REVEALS = (
    "reveal",
    "finds",
    "found",
    "discover",
    "catch",
    "caught",
    "spots",
    "sees",
    "show",
    "unmask",
)


def time_of(text: str) -> str:
    """When a part of the story happens, from its words ("At sunset" -> sunset)."""
    said = _words_of(text)
    for time, starts in TIMES.items():
        if any(word.startswith(start) for word in said for start in starts):
            return time
    return "day"


def moment_of(chunk: list[str]) -> str:
    """A scene's key moment offline: its first sentence that reveals or finds something."""
    for sentence in chunk:
        if any(word.startswith(r) for word in _words_of(sentence) for r in REVEALS):
            return _shorten(sentence.strip().rstrip("."), 150)
    return ""


# Middle scenes the synopsis doesn't reach (long comics have up to 8 scenes): all different.
MIDDLES = [
    "Something surprising happens at {place}!", "{who} find a clue at {place}.",
    "A big problem pops up at {place}!", "{who} try a clever plan at {place}.",
    "{who} work together at {place}.", "{who} get a surprise at {place}.",
]  # fmt: skip


def _template_summary(i: int, n: int, members: list[CastMember], place: Place) -> str:
    who = _names(members)
    if i == 0:
        return f"{who} arrive at {place.name}."
    if i == n - 1:
        return f"{who} fix everything, and it all works out."
    return MIDDLES[(i - 1) % len(MIDDLES)].format(who=who, place=place.name)


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
    (("sad", "lost", "cry", "miss", "sorry", "gone", "disappear", "vanish", "stole", "steal"),
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

EXTRA_LINES = [
    "Let's do this!", "What should we do next?", "Come on, follow me!", "I knew it!",
    "That was close!", "Good thinking!", "Wait for me!", "You can do it!", "Watch this!",
    "Are you ready?", "We make a great team!", "Just one more try!",
]  # fmt: skip


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


# Filler beats when a scene's summary has fewer moments than panels: one per panel slot of the
# longest comic (30), so none repeats in a comic.
FILLERS = [
    "{who} looks around {place}", "{who} has an idea", "{who} spots something odd",
    "{who} asks what happens next", "{who} tries a new plan", "{who} takes a closer look",
    "{who} makes a funny face", "{who} waves to everyone", "{who} gets a big surprise",
    "{who} decides what to do", "{who} cheers the team on", "{who} points the way",
    "{who} listens carefully", "{who} hums a happy tune", "{who} counts to three",
    "{who} peeks around the corner", "{who} shares a secret", "{who} jumps for joy",
    "{who} tiptoes closer", "{who} gives a thumbs up", "{who} scratches their head",
    "{who} finds a better way", "{who} tells a joke", "{who} keeps watch",
    "{who} draws a quick map", "{who} hears a strange noise", "{who} takes a deep breath",
    "{who} makes a wish", "{who} remembers something", "{who} smiles at {place}",
]  # fmt: skip
# Narrator captions linking one scene to the next.
LINKS = [
    "Later, at {place}...", "Meanwhile, at {place}...", "Soon after, at {place}...",
    "Next stop: {place}!", "A little later, at {place}...", "Then, at {place}...",
]  # fmt: skip
BACK_TO = "Back at {place}..."  # a place the story left and comes back to
SAME_PLACE = ["A little later...", "Soon after...", "Then..."]  # the same place as the scene before
# Everyone who isn't leading reacts: their own pose and a face that differs from the lead's.
REACTION_POSES = [
    "front", "three_quarter_right", "wave", "point", "three_quarter_left", "hands_on_hips",
]  # fmt: skip
REACTIONS: dict[str, tuple[str, str]] = {
    "happy": ("laughing", "surprised"), "laughing": ("happy", "surprised"),
    "surprised": ("happy", "scared"), "scared": ("surprised", "sad"),
    "sad": ("surprised", "scared"), "angry": ("surprised", "sad"),
}  # fmt: skip


def _beats(
    summary: str, k: int, members: list[CastMember], place: Place, offset: int = 0
) -> list[str]:
    """k beats for a scene: its summary's moments in order, spread out from the first panel to
    the last, with filler beats (taking turns between the characters) in the gaps."""
    parts = [p for s in sentences(summary) for p in _CLAUSE.split(s) if p.strip()]
    parts = [p.strip().rstrip(".!?") for p in parts] or [summary.strip().rstrip(".!?")]
    if len(parts) >= k:
        return [_capitalised(_shorten(" ".join(g), 100)) for g in split_into(parts, k)]
    slots: list[str | None] = [None] * k
    if len(parts) == 1:
        slots[0] = parts[0]
    else:
        for j, part in enumerate(parts):
            slots[int(j * (k - 1) / (len(parts) - 1) + 0.5)] = part
    return [
        _capitalised(_shorten(beat, 100)) if beat else _filler(offset + i, members, place)
        for i, beat in enumerate(slots)
    ]


def _filler(index: int, members: list[CastMember], place: Place) -> str:
    """The filler beat for this panel of the comic (one template per panel slot: no repeats)."""
    names = [m.name for m in members] or ["Everyone"]
    text = FILLERS[index % len(FILLERS)].format(
        who=names[(index + 1) % len(names)], place=place.name
    )
    return _capitalised(_shorten(text, 100))


def on_stage(
    members: list[T], lead: T, turn: int, named: Collection[T] = (), everyone: bool = False
) -> list[T]:
    """Who is in a panel (Phase 8: no 3-character limit): the whole scene in its big panels
    (`everyone`: the first, the key moment, the last) or when it's small (3 or fewer); otherwise
    the lead, whoever the beat names, and one more taking turns, so everyone gets on stage. In
    the scene's order."""
    if everyone or len(members) <= 3:
        return list(members)
    shown = {id(m) for m in (lead, *named)}
    others = [m for m in members if id(m) not in shown]
    if len(shown) < 3 and others:
        shown.add(id(others[turn % len(others)]))
    return [m for m in members if id(m) in shown]


class Voices:
    """What each character has said so far, so the offline planner keeps the dialogue rules: a
    catchphrase once, the same two opening words at most OPENING_MAX times, never twice in a row,
    and (when a part is planned again) none of the openings other parts already use."""

    def __init__(self, avoid: Mapping[str, Collection[str]] | None = None) -> None:
        self.openings: dict[str, list[str]] = {}
        self.catchphrase_said: set[str] = set()
        self.beats: set[str] = set()  # so two scenes with the same summary don't repeat a beat
        self.avoid = {speaker: set(starts) for speaker, starts in (avoid or {}).items()}

    def fresh(self, speaker: str, text: str) -> bool:
        start = opening(text)
        used = self.openings.get(speaker, [])
        return (
            bool(start)
            and start not in self.avoid.get(speaker, ())
            and (not used or used[-1] != start)
            and used.count(start) < OPENING_MAX
        )

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
    lead: CastMember,
    line: str | None,
    kind: str,
    index: int,
    voices: Voices,
    beat: str,
    catchphrase_ok: Collection[str] | None = None,
) -> PlannedBubble:
    """The lead's bubble: their catchphrase once, in its own part (if the beat has no line of its
    own), else a fresh line. When every line is used up, the narrator tells the beat instead."""
    catchphrase = lead.catchphrase if 0 < words(lead.catchphrase) <= MAX_WORDS else ""
    allowed = catchphrase_ok is None or lead.id in catchphrase_ok
    fresh = catchphrase and allowed and lead.id not in voices.catchphrase_said
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


def _link(ctx: StoryContext, part: ScenePart, place: Place) -> PlannedBubble:
    """The narrator caption that opens a scene after the first: "Later, at the garden...", "Back
    at the kitchen..." (a place the story left), or "A little later..." (the same place)."""
    before = [s.background_id for s in ctx.scenes[: part.scene_no - 1]]
    n = part.scene_no - 2
    if before and before[-1] == place.id:
        template = SAME_PLACE[n % len(SAME_PLACE)]
    elif place.id in before:
        template = BACK_TO
    else:
        template = LINKS[n % len(LINKS)]
    return PlannedBubble(
        speaker=NARRATOR, type="narrator", text=clip_words(template.format(place=place.name))
    )


def offline_part(ctx: StoryContext, part: ScenePart, voices: Voices) -> PanelPlan:
    """One part's panels from the offline planner: the scene's moments as beats (fillers when the
    summary is short), a lead who speaks while the others react with their own pose and face,
    sides that swap from panel to panel, a narrator opening, links between scenes and a closing
    line. `voices` carries what was said before, so the dialogue rules hold."""
    scene = part.scene
    members = [m for cid in scene.character_ids if (m := ctx.member(cid))] or ctx.cast[:1]
    place = ctx.place(scene.background_id) or Place(scene.background_id, "the scene")
    beats = _beats(scene.summary, part.scene_count, members, place, part.scene_first)
    offset = part.first - part.scene_first
    key = key_panel(part.count) - 1 if part.key_moment else -1  # the key moment's panel (0-based)
    panels: list[PlannedPanel] = []
    for j, beat in enumerate(beats[offset : offset + part.count]):
        index = part.first + j  # in the comic
        turn = offset + j  # in the scene
        if j == key:
            beat = _capitalised(_shorten(part.key_moment.rstrip(".!?"), 100))
        elif beat in voices.beats:  # an earlier scene said the same: never repeat a beat
            beat = _filler(index, members, place)
        voices.beats.add(beat)
        pose, expression, line, kind = mood_for(beat)
        # Whoever the beat, or (after the scene's first panel) the scene, says is asleep sleeps.
        sleepers = asleep_in(beat, members) | (asleep_in(scene.summary, members) if turn else set())
        awake = [m for m in members if m.id not in sleepers] or members
        # The one the beat is about leads (and speaks); otherwise take turns. Sleepers never lead.
        named = [m for m in awake if mentions(beat, m.name)]
        lead = named[0] if named else awake[turn % len(awake)]
        last = turn == part.scene_count - 1
        big = j == key or turn == 0 or last
        sleeping = [m for m in members if m.id in sleepers]
        shown = on_stage(members, lead, turn, [*named, *sleeping], everyone=big)
        if index % 2:
            shown = shown[::-1]  # characters swap sides now and then
        positions = POSITIONS_FOR[len(shown)]
        characters: list[PlannedCharacter] = []
        for k, m in enumerate(shown):
            if m.id in sleepers:
                look = (ASLEEP, "sleepy")
            elif m is lead:
                look = (pose, expression)
            else:
                face = REACTIONS[expression][(index + k) % 2]
                moving = pose in ("walk", "run")
                look = (pose if moving else REACTION_POSES[(index + k) % len(REACTION_POSES)], face)
            characters.append(
                PlannedCharacter(id=m.id, pose=look[0], expression=look[1], position=positions[k])
            )
        bubbles: list[PlannedBubble] = []
        if index == 0:
            text = mood_info(ctx.mood).opener.format(place=place.name)
            bubbles.append(PlannedBubble(speaker=NARRATOR, type="narrator", text=clip_words(text)))
        elif index == ctx.panel_count - 1:
            text = mood_info(ctx.mood).closer
            bubbles.append(PlannedBubble(speaker=NARRATOR, type="narrator", text=clip_words(text)))
        else:
            if turn == 0:  # a new scene (not the first): the narrator links it to the last one
                bubbles.append(_link(ctx, part, place))
            speech = _speech(lead, line, kind, index, voices, beat, part.catchphrases)
            if speech.speaker in sleepers:  # everyone is asleep: the narrator tells it
                speech = PlannedBubble(
                    speaker=NARRATOR, type="narrator", text=clip_words(beat + ".")
                )
            # A thinking character thinks in a cloud (A3): never a talk or shout bubble.
            if (
                speech.speaker == lead.id
                and speech.type in ("talk", "shout")
                and any(c.id == lead.id and c.pose == THINKING for c in characters)
            ):
                speech = speech.model_copy(update={"type": "think"})
            bubbles.append(speech)
        here = [m for m in shown]
        props = offline_props(beat, bubbles, lead.id, here)
        panels.append(
            PlannedPanel(
                scene_id=scene.id,
                beat=beat,
                characters=characters,
                bubbles=bubbles,
                props=props,
                key_moment=j == key,
                size=big_size(part) if j == key else "normal",
            )
        )
    return PanelPlan(panels=panels)


def big_size(part: ScenePart) -> str:
    """How big a key moment is drawn: a splash page in an end scene (the big reveal), else a
    wide panel."""
    return "splash" if scene_position(part.scene_no - 1, part.scene_total) == "end" else "wide"


def splash_limit(panel_count: int) -> int:
    """Splash pages a comic may have: 1, and 1 more for every 12 panels after the first 12."""
    return 1 + max(0, panel_count - 1) // 12


def limit_splashes(
    plans: Sequence[PanelPlan | None],
    parts: Sequence[ScenePart],
    ctx: StoryContext,
    skip: Collection[int] = (),
) -> dict[int, PanelPlan]:
    """Splash pages stay rare (Phase 8): past splash_limit, the extra ones become wide panels
    (key moments in end scenes keep theirs first, then the latest). Returns the parts changed."""
    found: list[tuple[int, int]] = [
        (i, j)
        for i, plan in enumerate(plans)
        if plan is not None
        for j, panel in enumerate(plan.panels)
        if panel.size == "splash" and parts[i].first + j not in skip
    ]

    def rank(ij: tuple[int, int]) -> tuple[bool, bool, int]:
        i, j = ij
        panel = plans[i].panels[j]  # type: ignore[union-attr]
        end = scene_position(parts[i].scene_no - 1, parts[i].scene_total) == "end"
        return (panel.key_moment and end, panel.key_moment, parts[i].first + j)

    keep = set(sorted(found, key=rank, reverse=True)[: splash_limit(ctx.panel_count)])
    changed: dict[int, PanelPlan] = {}
    for i, j in found:
        if (i, j) in keep:
            continue
        current = changed.get(i) or plans[i]
        assert current is not None
        panels = list(current.panels)
        panels[j] = panels[j].model_copy(update={"size": "wide"})
        changed[i] = PanelPlan(panels=panels)
    return changed


def mentions(text: str, name: str) -> bool:
    """Whether a text names a character ("Mr Hari" names "Mr. Hari")."""
    said, wanted = " ".join(_words_of(text)), " ".join(_words_of(name))
    return bool(wanted) and f" {wanted} " in f" {said} "


_SLEEP = r"(?:snor\w*|sleep\w*|asleep|nap|naps|napping|doz\w*|falls asleep)"


def asleep_in(beat: str, members: Sequence[CastMember]) -> set[str]:
    """Who a beat says is sleeping ("Mr Hari snores, Leo naps, Sniffy keeps watch" -> Mr. Hari and
    Leo): a name followed within a few words by a sleepy word."""
    said = " ".join(_words_of(beat))
    out: set[str] = set()
    for m in members:
        name = " ".join(_words_of(m.name))
        if name and re.search(rf"\b{re.escape(name)}\b(?: \w+){{0,3}}? {_SLEEP}\b", said):
            out.add(m.id)
    return out


def offline_props(
    beat: str, bubbles: list[PlannedBubble], lead: str, here: Sequence[CastMember]
) -> list[PlannedProp]:
    """The offline planner's props: whatever the beat and the words name, held by whoever the
    words say holds it ("Barnaby hugging the scarecrow"), else by the one who names it when it can
    be held, else on the ground."""
    said = [PlannedBubble(speaker=lead, type="talk", text=beat), *bubbles]
    names = {m.name: m.id for m in here}
    found = add_named_props(said, [], [m.id for m in here], names)
    return [PlannedProp.model_validate(p) for p in found]


def offline_panels(ctx: StoryContext) -> PanelPlan:
    """The whole comic from the offline planner, part by part with one record of who said what,
    so the dialogue rules hold across every scene."""
    voices = Voices()
    return PanelPlan(
        panels=[p for part in plan_parts(ctx) for p in offline_part(ctx, part, voices).panels]
    )


# ---- Meta's planner -------------------------------------------------------------------------


def scenes_schema(ctx: StoryContext) -> dict[str, Any]:
    scene = strict_object(
        {
            "background_id": {"type": "string", "enum": ctx.place_ids},
            "character_ids": {"type": "array", "items": {"type": "string", "enum": ctx.cast_ids}},
            "summary": {"type": "string"},
            "time_of_day": {"type": "string", "enum": ["day", "sunset", "night"]},
            "key_moment": {"type": "string"},
        }
    )
    return strict_object({"scenes": {"type": "array", "items": scene}})


def panels_schema(ctx: StoryContext) -> dict[str, Any]:
    character = strict_object(
        {
            "id": {"type": "string", "enum": ctx.cast_ids},
            "pose": {"type": "string", "enum": catalog_poses()},
            "expression": {"type": "string", "enum": catalog_expressions()},
            "position": {"type": "string", "enum": POSITIONS},
        }
    )
    bubble = strict_object(
        {
            "speaker": {"type": "string", "enum": [*ctx.cast_ids, NARRATOR]},
            "type": {"type": "string", "enum": ["talk", "think", "shout", "narrator"]},
            "text": {"type": "string"},
        }
    )
    prop = strict_object(
        {
            "id": {"type": "string", "enum": list(PROP_IDS)},
            "state": {"type": "string", "enum": list(STATES)},
            "position": {"type": "string", "enum": ["", *POSITIONS]},
            "held_by": {"type": "string", "enum": ["", *ctx.cast_ids, *PROP_IDS]},
        }
    )
    panel = strict_object(
        {
            "scene_id": {"type": "string", "enum": [s.id for s in ctx.scenes]},
            "beat": {"type": "string"},
            "characters": {"type": "array", "items": character},
            "bubbles": {"type": "array", "items": bubble},
            "props": {"type": "array", "items": prop},
            "key_moment": {"type": "boolean"},
            "size": {"type": "string", "enum": ["normal", "wide", "splash"]},
        }
    )
    return strict_object({"panels": {"type": "array", "items": panel}})


def fix_schema(ctx: StoryContext, numbers: list[int]) -> dict[str, Any]:
    """Meta's answer when only some panels are asked for again: each with the number it replaces."""
    schema = panels_schema(ctx)
    item = schema["properties"]["panels"]["items"]
    item["properties"] = {"panel": {"type": "integer", "enum": numbers}, **item["properties"]}
    item["required"] = ["panel", *item["required"]]
    return schema


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
    lines = [f"Title: {ctx.title or '(no title yet)'}", f"Mood: {mood_line(ctx.mood)}"]
    lines.append(f"Synopsis: {ctx.synopsis}")
    lines.append("Cast:")
    for c in ctx.cast:
        traits = ", ".join(c.traits) or "none"
        lines.append(f"- id {c.id}: {c.name} (traits: {traits}; catchphrase: {c.catchphrase!r})")
    lines.append("Places:")
    for p in ctx.places:
        lines.append(f"- id {p.id}: {p.name}. {p.description}".rstrip())
    return lines


def prop_lines() -> list[str]:
    """The prop library for the panel prompt (no kid-written words)."""
    lines = ["Props you can draw (id: states):"]
    for prop in PROPS.values():
        lines.append(f"- {prop.id} ({prop.name}): {prop.notes}")
    return lines


def _retry_lines(problems: list[str]) -> list[str]:
    if not problems:
        return []
    return ["", "Your last answer had these problems. Fix them:", *(f"- {p}" for p in problems)]


def ask_scenes(llm: LLMProvider, ctx: StoryContext, problems: list[str]) -> dict[str, Any]:
    n = scenes_for(ctx.panel_count)
    prompt = "\n".join([*story_lines(ctx), *_retry_lines(problems)])
    return llm.complete_json(
        render("planner_scenes", scene_count=n),
        prompt,
        scenes_schema(ctx),
        schema_name="scene_plan",
        max_tokens=LIMITS["plan_scenes"].max_tokens,
        timeout=LIMITS["plan_scenes"].timeout,
    )


def part_brief(
    ctx: StoryContext, part: ScenePart, avoid: Mapping[str, Collection[str]] | None = None
) -> list[str]:
    """What one call plans: which scene (or run of it), where it sits in the story, whose
    catchphrase it may use and, when it's asked again, the openings other parts already use."""
    out = [
        f"Plan scene {part.scene_no} of {part.scene_total} now: exactly {part.count} panels, "
        f"every one with scene_id {part.scene.id}."
    ]
    if part.pieces > 1:
        a = part.first - part.scene_first + 1
        out.append(
            f"This scene has {part.scene_count} panels in all: plan panels {a} to "
            f"{a + part.count - 1} of them, carrying on from the ones before."
        )
    out.append(POSITION_BRIEF[scene_position(part.scene_no - 1, part.scene_total)])
    if TIME_BRIEF.get(part.scene.time_of_day):
        out.append(TIME_BRIEF[part.scene.time_of_day])
    if part.key_moment:
        big = big_size(part)
        out.append(
            "This scene's key moment must be one of these panels (set key_moment true on it, "
            f"false on the others), drawn {big} (size {big!r}): {part.key_moment}"
        )
    else:
        out.append("Set key_moment false on every panel.")
    last = part.first + part.count == ctx.panel_count
    if part.first == 0:
        out.append("This is the start of the story: the first panel sets the scene.")
    if last:
        out.append("This is the end of the story: the last panel resolves it.")
    if part.first > 0 and not last:
        out.append("This is the middle of the story: keep it moving.")
    if part.first > 0 and part.piece == 1:
        out.append(
            "Its first panel may open with a short narrator caption linking from the scene "
            'before (like "Later, at the garden...").'
        )
    sayers = [m for m in ctx.cast if m.id in part.catchphrases]
    if sayers:
        offers = "; ".join(f"{m.name}: {m.catchphrase!r}" for m in sayers)
        out.append(
            "Catchphrases you may use in this part, at most once each and only where one truly "
            f"fits the moment (otherwise leave it out): {offers}. Nobody else says their "
            "catchphrase here."
        )
    else:
        out.append("Nobody says their catchphrase in this part: they belong to other scenes.")
    taken = [
        (m.name, sorted(starts))
        for cid, starts in (avoid or {}).items()
        if starts and (m := ctx.member(cid))
    ]
    if taken:
        listed = "; ".join(f"{name}: " + ", ".join(map(repr, starts)) for name, starts in taken)
        out.append(
            "Other scenes already start these characters' lines like this, so start theirs "
            f"differently here: {listed}."
        )
    return out


def scene_lines(ctx: StoryContext) -> list[str]:
    """The kid's scenes, in order, exactly as they set them: place, cast, what happens, where it
    sits in the story, its time of day and its key moment."""
    lines = ["Scenes (in order):"]
    total = len(ctx.scenes)
    for i, s in enumerate(ctx.scenes, start=1):
        place = ctx.place(s.background_id)
        who = ", ".join(f"{m.name} ({m.id})" for cid in s.character_ids if (m := ctx.member(cid)))
        line = (
            f"{i}. id {s.id}: at {place.name if place else s.background_id}; "
            f"characters: {who}; what happens: {s.summary}; story position: "
            f"{scene_position(i - 1, total)}; time of day: {s.time_of_day}"
        )
        if s.key_moment.strip():
            line += f"; key moment: {s.key_moment.strip()}"
        lines.append(line)
    return lines


def ask_part(
    llm: LLMProvider,
    ctx: StoryContext,
    part: ScenePart,
    problems: list[str],
    avoid: Mapping[str, Collection[str]] | None = None,
) -> dict[str, Any]:
    """One part's panels from Meta: the whole story for context, then this part's brief."""
    lines = [*story_lines(ctx), *scene_lines(ctx)]
    brief = part_brief(ctx, part, avoid)
    prompt = "\n".join([*lines, *prop_lines(), "", *brief, *_retry_lines(problems)])
    return llm.complete_json(
        render("planner_panels", panel_count=part.count),
        prompt,
        panels_schema(part_context(ctx, part)),
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
    *,
    offline_when_wrong: bool = False,
) -> Outcome[Plan]:
    """Meta's plan if it passes the checks (one retry with the problems) and the safety check,
    else the offline plan. Wrong twice: PlanFailed, or the offline plan if `offline_when_wrong`."""

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
    if offline_when_wrong:
        return from_offline(fallback=True)
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


FIX_TRIES = 2  # a panel that breaks a rule is asked for again at most this many times (Phase 8)


def split_problems(problems: list[str]) -> tuple[dict[int, list[str]], list[str]]:
    """Problems by the panel they're about (1-based), and the ones about the part as a whole."""
    per: dict[int, list[str]] = {}
    rest: list[str] = []
    for problem in problems:
        found = re.match(r"panel (\d+): (.+)", problem)
        if found:
            per.setdefault(int(found[1]), []).append(found[2])
        else:
            rest.append(problem)
    return per, rest


def ask_fix(
    llm: LLMProvider,
    ctx: StoryContext,
    part: ScenePart,
    plan: PanelPlan,
    failing: Mapping[int, list[str]],
    avoid: Mapping[str, Collection[str]] | None = None,
) -> dict[str, Any]:
    """Only the panels that broke a rule, asked for again with what was wrong (the rest of the
    part is shown so the new ones fit in)."""
    numbers = sorted(failing)
    shown = json.dumps(
        [{"panel": i, **panel.model_dump(mode="json")} for i, panel in enumerate(plan.panels, 1)],
        ensure_ascii=False,
    )
    fixes = [f"- panel {n}: {problem}" for n in numbers for problem in failing[n]]
    lines = [
        *story_lines(ctx),
        *scene_lines(ctx),
        *prop_lines(),
        "",
        *part_brief(ctx, part, avoid),
        "",
        f"The {len(plan.panels)} panels planned for this part so far (JSON):",
        shown,
        "",
        f"Write panel{'s' if len(numbers) > 1 else ''} {', '.join(map(str, numbers))} again (and "
        "only those), keeping the story and the other panels the same, so these problems are "
        "gone:",
        *fixes,
    ]
    return llm.complete_json(
        render("planner_panels", panel_count=len(numbers)),
        "\n".join(lines),
        fix_schema(part_context(ctx, part), numbers),
        schema_name="panel_fix",
        max_tokens=LIMITS["fix_panels"].max_tokens,
        timeout=LIMITS["fix_panels"].timeout,
    )


def merge_fixes(plan: PanelPlan, raw: object, numbers: Collection[int]) -> PanelPlan:
    """The plan with Meta's new panels in place of the ones asked for (anything else ignored)."""
    panels = list(plan.panels)
    items = raw.get("panels", []) if isinstance(raw, dict) else []
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        try:
            number = int(item.get("panel", 0))
            fixed = PlannedPanel.model_validate({k: v for k, v in item.items() if k != "panel"})
        except (TypeError, ValueError, ValidationError):
            continue
        if number in numbers and 1 <= number <= len(panels):
            panels[number - 1] = fixed
    return PanelPlan(panels=panels)


SPOTS = ["left", "center", "right", "far_left", "far_right"]


def repair_part(plan: PanelPlan, ctx: StoryContext, part: ScenePart) -> PanelPlan:
    """The last word when panels still break a rule after being asked again: only the scene's
    characters, each once, each in their own spot; a bubble from someone who isn't there or is
    asleep becomes the narrator's (or goes, when there's a caption already); bubbles of 12 words at
    most; a thinker thinks; props held by someone here, and every prop the words name drawn; the
    key moment shown."""
    scene_cast = [cid for cid in part.scene.character_ids if cid in ctx.cast_ids]
    names = {m.name: m.id for m in ctx.cast}
    panels: list[PlannedPanel] = []
    for panel in plan.panels:
        characters: list[PlannedCharacter] = []
        for c in panel.characters:
            if c.id in scene_cast and all(c.id != x.id for x in characters):
                taken = {x.position for x in characters}
                spot = c.position if c.position not in taken else next(
                    x for x in SPOTS if x not in taken)  # fmt: skip
                characters.append(c.model_copy(update={"position": spot}))
        if not characters and scene_cast:
            characters = [PlannedCharacter(id=scene_cast[0], pose="front", expression="happy",
                                           position="center")]  # fmt: skip
        here = {c.id for c in characters}
        asleep = {c.id for c in characters if c.pose == ASLEEP}
        thinking = {c.id for c in characters if c.pose == THINKING}
        bubbles: list[PlannedBubble] = []
        for b in panel.bubbles:
            b = b.model_copy(update={"text": clip_words(b.text)})
            if b.speaker == NARRATOR or b.type == "narrator":
                bubbles.append(b.model_copy(update={"speaker": NARRATOR, "type": "narrator"}))
            elif b.speaker not in here or b.speaker in asleep:
                if not any(x.speaker == NARRATOR for x in [*panel.bubbles, *bubbles]):
                    caption = clip_words(panel.beat.rstrip(".!?") + ".")
                    bubbles.append(PlannedBubble(speaker=NARRATOR, type="narrator", text=caption))
            elif b.speaker in thinking and b.type in ("talk", "shout"):
                bubbles.append(b.model_copy(update={"type": "think"}))
            else:
                bubbles.append(b)
        prop_ids = {x.id for x in panel.props}
        props = [x.saved() for x in panel.props if not x.held_by or x.held_by in here
                 or x.held_by in prop_ids]  # fmt: skip
        found = add_named_props(bubbles, props, [c.id for c in characters], names)
        panels.append(
            panel.model_copy(
                update={
                    "characters": characters,
                    "bubbles": bubbles,
                    "props": [PlannedProp.model_validate(x) for x in found],
                }
            )
        )
    if part.key_moment and panels and not any(x.key_moment for x in panels):
        k = key_panel(len(panels)) - 1
        beat = _capitalised(_shorten(part.key_moment.rstrip(".!?"), 100))
        panels[k] = panels[k].model_copy(update={"key_moment": True, "beat": beat})
    return PanelPlan(panels=panels)


def plan_part(
    guard: Guard,
    ctx: StoryContext,
    part: ScenePart,
    avoid: Mapping[str, Collection[str]] | None = None,
) -> Outcome[PanelPlan]:
    """One part of the panel plan from Meta, checked (Phase 8):

    1. The part (asked once more, with the problems, if it's wrong as a whole: the wrong number of
       panels, or not valid at all).
    2. Each panel that still breaks a rule (a speaker who isn't there or is asleep, more than 12
       words, a prop named but not drawn, the key moment missing...) is asked for again on its
       own, at most FIX_TRIES times.
    3. Whatever is left is repaired by hand (repair_part), then checked once more.

    The offline planner makes the part when Meta is off, down, unsafe, or still wrong after all
    that (labelled a fallback)."""
    target = f"studio:panels:{part.scene_no}"

    def from_offline(fallback: bool) -> Outcome[PanelPlan]:
        plan = offline_part(ctx, part, Voices(avoid))
        problems = check_part(plan, ctx, part, avoid)
        if problems:  # a bug, never the kid's fault
            raise PlanFailed(problems)
        return Outcome(plan, "mock", fallback)

    llm = guard.llm
    if not guard.may_ask_meta or llm is None:
        return from_offline(fallback=llm is not None)
    problems: list[str] = []
    plan: PanelPlan | None = None
    for _attempt in range(2):
        try:
            raw = ask_part(llm, ctx, part, problems, avoid)
        except LLMError:
            return from_offline(fallback=True)  # Meta is down
        try:
            plan = PanelPlan.model_validate(raw)
            problems = check_part(plan, ctx, part, avoid)
        except ValidationError as error:
            plan, problems = None, validation_problems(error)
        if plan is not None and not split_problems(problems)[1]:
            break  # right as a whole: any panel that breaks a rule is fixed on its own
    if plan is None or split_problems(problems)[1]:
        return from_offline(fallback=True)
    tries: Counter[int] = Counter()
    per = split_problems(problems)[0]
    while per:
        failing = {n: found for n, found in per.items() if tries[n] < FIX_TRIES}
        if not failing:
            break
        try:
            raw = ask_fix(llm, ctx, part, plan, failing, avoid)
        except LLMError:
            break
        tries.update(failing.keys())  # one more try for each of these panels
        plan = merge_fixes(plan, raw, failing)
        per, rest = split_problems(check_part(plan, ctx, part, avoid))
        if rest:
            break
    if check_part(plan, ctx, part, avoid):
        plan = repair_part(plan, ctx, part)
        if check_part(plan, ctx, part, avoid):
            repaired = repair_dialogue([plan], [replace(part, first=0)], ctx)
            plan = repaired.get(0, plan)
    if check_part(plan, ctx, part, avoid):
        return from_offline(fallback=True)
    if guard.output_ok(target, panel_texts(plan)):
        return Outcome(plan, "meta", False)
    return from_offline(fallback=True)  # words that didn't pass safety are never shown


def ensure_scene_casts(
    plans: Sequence[PanelPlan | None],
    parts: Sequence[ScenePart],
    ctx: StoryContext,
    skip: Collection[int] = (),
) -> dict[int, PanelPlan]:
    """Nobody the kid put in a scene is left out of it (Phase 8): someone in none of their scene's
    panels joins the one with the fewest characters (and a free spot). Returns the parts it
    changed."""
    changed: dict[int, PanelPlan] = {}
    current = {i: plan for i, plan in enumerate(plans) if plan is not None}
    for scene in ctx.scenes:
        mine = [i for i, part in enumerate(parts) if part.scene.id == scene.id and i in current]
        slots = [
            (i, j)
            for i in mine
            for j in range(len(current[i].panels))
            if parts[i].first + j not in skip
        ]
        shown = {c.id for i, j in slots for c in current[i].panels[j].characters}
        for cid in scene.character_ids:
            if cid in shown or cid not in ctx.cast_ids:
                continue
            room = slots  # a panel can hold the whole scene (Phase 8)
            if not room:
                continue
            i, j = min(room, key=lambda ij: len(current[ij[0]].panels[ij[1]].characters))
            panel = current[i].panels[j]
            taken = {c.position for c in panel.characters}
            spot = next(x for x in SPOTS if x not in taken)
            joined = PlannedCharacter(id=cid, pose="front", expression="surprised", position=spot)
            panels = list(current[i].panels)
            panels[j] = panel.model_copy(update={"characters": [*panel.characters, joined]})
            current[i] = changed[i] = PanelPlan(panels=panels)
            shown.add(cid)
    return changed


# ---- the comic-wide pass ------------------------------------------------------------------------


@dataclass(frozen=True)
class Line:
    part: int  # which part (index into the parts list)
    panel: int  # the comic-wide panel index
    speaker: str
    text: str


def lines_of(
    plans: Sequence[PanelPlan | None], parts: Sequence[ScenePart], skip: Collection[int] = ()
) -> list[Line]:
    """Every character's line in comic order (panels in `skip`, the kid's kept ones, left out)."""
    out: list[Line] = []
    for i, (plan, part) in enumerate(zip(plans, parts, strict=True)):
        for j, panel in enumerate(plan.panels if plan else []):
            if part.first + j in skip:
                continue
            out += [
                Line(i, part.first + j, b.speaker, b.text)
                for b in panel.bubbles
                if b.speaker != NARRATOR
            ]
    return out


def dialogue_clashes(
    plans: Sequence[PanelPlan | None], parts: Sequence[ScenePart], skip: Collection[int] = ()
) -> dict[int, dict[str, set[str]]]:
    """Parts whose line openings break the comic-wide rules once the parts are put together (a
    character's opening used more than OPENING_MAX times, or twice in a row across parts). For
    each, the openings to avoid: everything that speaker says in the other parts."""
    by_speaker: dict[str, list[Line]] = {}
    for line in lines_of(plans, parts, skip):
        by_speaker.setdefault(line.speaker, []).append(line)
    clashes: dict[int, dict[str, set[str]]] = {}
    for speaker, said in by_speaker.items():
        counts: Counter[str] = Counter()
        previous = ""
        for line in said:
            start = opening(line.text)
            if not start:
                continue
            if counts[start] >= OPENING_MAX or start == previous:
                elsewhere = {opening(x.text) for x in said if x.part != line.part} - {""}
                clashes.setdefault(line.part, {}).setdefault(speaker, set()).update(elsewhere)
            counts[start] += 1
            previous = start
    return clashes


def repair_dialogue(
    plans: Sequence[PanelPlan | None],
    parts: Sequence[ScenePart],
    ctx: StoryContext,
    skip: Collection[int] = (),
) -> dict[int, PanelPlan]:
    """The last word on the comic-wide rules (after the parts that clashed were asked once more):
    a line that still repeats an opening or a catchphrase is told by the narrator instead (the
    panel's beat), or left out if the panel already has a caption. Returns the parts it changed."""
    voices = Voices()
    said_catchphrase: set[str] = set()
    changed: dict[int, PanelPlan] = {}
    for i, (plan, part) in enumerate(zip(plans, parts, strict=True)):
        if plan is None:
            continue
        panels: list[PlannedPanel] = []
        touched = False
        for j, panel in enumerate(plan.panels):
            if part.first + j in skip:
                panels.append(panel)
                continue
            bubbles: list[PlannedBubble] = []
            for b in panel.bubbles:
                member = ctx.member(b.speaker)
                catchphrase = bool(member and uses_catchphrase(b.text, member.catchphrase))
                if b.speaker == NARRATOR or not opening(b.text):
                    bubbles.append(b)
                    continue
                if voices.fresh(b.speaker, b.text) and not (
                    catchphrase and b.speaker in said_catchphrase
                ):
                    voices.say(b.speaker, b.text)
                    if catchphrase:
                        said_catchphrase.add(b.speaker)
                    bubbles.append(b)
                    continue
                touched = True
                if not any(x.speaker == NARRATOR for x in panel.bubbles):
                    caption = clip_words(panel.beat.rstrip(".!?") + ".")
                    bubbles.append(PlannedBubble(speaker=NARRATOR, type="narrator", text=caption))
            panels.append(panel.model_copy(update={"bubbles": bubbles}))
        if touched:
            changed[i] = PanelPlan(panels=panels)
    return changed
