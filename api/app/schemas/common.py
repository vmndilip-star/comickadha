"""Shared value types. Literals become string unions in the generated TypeScript types."""

from datetime import UTC, datetime
from typing import Annotated, Literal, get_args

from pydantic import AfterValidator, BaseModel, StringConstraints

MAX_CAST = 3

Role = Literal["hero", "sidekick", "friend"]
CharacterKind = Literal["kid", "grown_up", "animal", "robot"]
Trait = Literal["brave", "curious", "shy", "funny", "grumpy", "loud", "clever", "kind"]
LockStatus = Literal["draft", "generating", "locked", "failed"]

Mood = Literal["mystery", "funny", "adventure", "spooky"]
PanelCount = Literal[4, 6, 8]
StudioStep = Literal[1, 2, 3]
ComicStatus = Literal["draft", "finished"]

Expression = Literal["happy", "sad", "angry", "surprised", "scared", "laughing"]
# Body sheet cells in 4x4 grid order.
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
]
Position = Literal["left", "center", "right"]
BubbleType = Literal["talk", "think", "shout", "narrator"]
PanelStatus = Literal["planned", "rendering", "ready", "blocked", "failed"]
PanelMode = Literal["composite", "redraw"]

POSES: tuple[Pose, ...] = get_args(Pose)
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
