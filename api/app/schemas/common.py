"""Shared value types. Literals become string unions in the generated TypeScript types."""

from datetime import UTC, datetime
from typing import Annotated, Literal, get_args

from pydantic import AfterValidator, BaseModel, Field, StringConstraints

MAX_CAST = 40  # a kid's own characters, any number up to this (decision 130; starters don't count)
MAX_COMIC_CAST = 5  # characters in one comic, own and starters mixed (a panel can hold them all)
MAX_PANEL_PROPS = 6  # props in one panel

Role = Literal["hero", "sidekick", "friend"]
CharacterKind = Literal["kid", "grown_up", "animal", "robot"]
# Positive or neutral traits only (docs/character-safety.md); a kid picks up to 3.
Trait = Literal[
    "brave", "curious", "funny", "kind", "clever", "creative", "calm", "cheerful", "helpful",
    "honest", "adventurous", "caring", "energetic", "gentle", "patient", "playful", "shy",
    "silly", "sporty", "thoughtful",
]  # fmt: skip
TRAITS: tuple[str, ...] = get_args(Trait)
LockStatus = Literal["draft", "generating", "locked", "failed"]

# What each mood means to the planner and the Story Buddy: app/moods.py (decision 128).
Mood = Literal[
    "mystery", "funny", "adventure", "spooky",
    "magical", "fairy_tale", "folk_tale", "underwater", "dinosaur", "jungle_safari", "pirate",
    "space", "robots_future", "time_travel", "sporty", "school_days", "festival", "nature_hero",
]  # fmt: skip
# Any number of panels from 4 to 200 (decision 128; the Studio still offers quick picks). Default 6.
MIN_PANELS, MAX_PANELS = 4, 200
PanelCount = Annotated[int, Field(ge=MIN_PANELS, le=MAX_PANELS)]
MAX_SCENES = 12
# The story a kid writes: room for a 30-panel comic's 8 scenes (Phase 7 part C; was 600).
MAX_SYNOPSIS = 1000
StudioStep = Literal[1, 2, 3]
ComicStatus = Literal["draft", "finished"]
# Who designed a character in the Create character flow (the badge on its card).
DesignedBy = Literal["meta", "offline"]

# "sleepy" (Phase 8): closed eyes, for a sleeping character.
Expression = Literal["happy", "sad", "angry", "surprised", "scared", "laughing", "sleepy"]
# The 16 body sheet cells in 4x4 grid order, then "asleep" (Phase 8: panels only, never a sheet
# cell): a sleeping character, drawn with the sleepy face and a "Zzz", who never speaks.
Pose = Literal[
    "front",
    "three_quarter_left",
    "side_left",
    "back",
    "three_quarter_right",
    "side_right",
    "walk",
    "run",
    "point",
    "sit",
    "jump",
    "wave",
    "hands_on_hips",
    "thinking",
    "scared_pose",
    "celebrate",
    "asleep",
]
# Where a character or a prop on the ground stands. Up to 3 characters at left/center/right
# stand where they always have; far_left and far_right make room for bigger groups (Phase 8).
Position = Literal["far_left", "left", "center", "right", "far_right"]
# Panel sizes (Phase 8): normal is one slot of a page, wide a full row (2 slots), splash a whole
# page (6 slots).
PanelSize = Literal["normal", "wide", "splash"]
# When a scene happens; panels draw their place's matching version (Phase 8).
TimeOfDay = Literal["day", "sunset", "night"]
# The prop library (app/props/library.py): story objects drawn as their own layer.
PropId = Literal[
    "scarecrow", "pole", "red_turban", "orange_turban", "torch", "notebook", "tiffin", "laddoos",
    "paw_prints",
]  # fmt: skip
PropState = Literal["on_pole", "lying_down", "held", "standing", "worn", "on_ground"]
BubbleType = Literal["talk", "think", "shout", "narrator"]
PanelStatus = Literal["planned", "rendering", "ready", "blocked", "failed"]
PanelMode = Literal["composite", "redraw"]

POSES: tuple[Pose, ...] = get_args(Pose)
# Character sheets keep their 16 poses (4x4) and 6 faces (2x3); the sleeping pose and face are for
# panels only.
SHEET_POSES: tuple[Pose, ...] = POSES[:16]
SHEET_EXPRESSIONS: tuple[Expression, ...] = (
    "happy", "sad", "angry", "surprised", "scared", "laughing",
)  # fmt: skip
POSITIONS: tuple[Position, ...] = get_args(Position)
EXPRESSIONS: tuple[Expression, ...] = get_args(Expression)

HexColor = Annotated[str, StringConstraints(pattern=r"^#[0-9A-Fa-f]{6}$")]
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=24)]
PlaceName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)]


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


# Stored as naive UTC; sent to the browser with an explicit UTC offset.
UtcDatetime = Annotated[datetime, AfterValidator(_as_utc)]


class ErrorBody(BaseModel):
    """Every error response has this shape. Messages are written for kids."""

    code: str
    message: str
    # The input the message is about ("synopsis", "scenes.<id>.summary", "bubbles.<id>.text"),
    # so the web app shows it under that field instead of as a toast.
    field: str | None = None


class FieldNote(BaseModel):
    """A gentle note shown under one field (a draft that was saved but won't go further)."""

    field: str
    message: str
