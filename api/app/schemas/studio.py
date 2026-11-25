"""Story Studio: the planner (scenes, then panels), the Story Buddy and story sparks.

The Planned* models are what a planner (Meta's model or the offline one) returns. They never
carry coordinates or ids the server owns: the server adds idx, ids, sheet versions, scale and the
bubble layout. Semantic checks (locked ids, catalog names, counts, positions, bubble length,
speakers) live in services/story_planner.py.
"""

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.schemas.comic import SceneRead
from app.schemas.common import (
    MAX_COMIC_CAST,
    MAX_PANELS,
    MAX_SCENES,
    MAX_SYNOPSIS,
    BubbleType,
    Expression,
    PanelSize,
    Pose,
    Position,
    PropId,
    PropState,
    TimeOfDay,
)
from app.schemas.props import check_prop

PlanSource = Literal["meta", "mock"]


class PlannedScene(BaseModel):
    background_id: str
    character_ids: list[str] = Field(min_length=1, max_length=MAX_COMIC_CAST)
    summary: str = Field(min_length=1, max_length=200)
    time_of_day: TimeOfDay = "day"
    # The moment that must become a panel ("" when the scene has none).
    key_moment: str = Field(default="", max_length=160)


class ScenePlan(BaseModel):
    scenes: list[PlannedScene] = Field(min_length=2, max_length=MAX_SCENES)


class PlannedCharacter(BaseModel):
    id: str
    pose: Pose
    expression: Expression
    position: Position


class PlannedProp(BaseModel):
    """A prop the planner puts in a panel: on the ground at `position`, or held or worn by
    `held_by`. Meta's strict schema sends "" for the one it doesn't use."""

    id: PropId
    state: PropState
    position: Position | None = None
    held_by: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _blanks(cls, data: object) -> object:
        if isinstance(data, dict):
            return {k: (None if v == "" else v) for k, v in data.items()}
        return data

    @model_validator(mode="after")
    def _fits(self) -> "PlannedProp":
        problem = check_prop(self.id, self.state, self.position, self.held_by)
        if problem:
            raise ValueError(problem)
        return self

    def saved(self) -> dict[str, str]:
        """As a panel stores it (only the placement it uses)."""
        out: dict[str, str] = {"id": self.id, "state": self.state}
        if self.position:
            out["position"] = self.position
        if self.held_by:
            out["held_by"] = self.held_by
        return out


class PlannedBubble(BaseModel):
    speaker: str  # a character in the panel, or "narrator"
    type: BubbleType
    text: str = Field(min_length=1, max_length=120)


class PlannedPanel(BaseModel):
    scene_id: str
    beat: str = Field(min_length=1, max_length=120)
    # Whoever the panel needs: up to the whole cast (Phase 8: no 3-character limit).
    characters: list[PlannedCharacter] = Field(min_length=1, max_length=MAX_COMIC_CAST)
    bubbles: list[PlannedBubble] = Field(default=[], max_length=3)
    props: list[PlannedProp] = Field(default=[], max_length=6)
    # The panel that shows its scene's key moment (Phase 8).
    key_moment: bool = False
    # normal, wide (a full row) or splash (a whole page): for the story's biggest moments.
    size: PanelSize = "normal"


class PanelPlan(BaseModel):
    # A whole comic (the offline planner's) or one part of it (planned a part at a time).
    panels: list[PlannedPanel] = Field(min_length=1, max_length=MAX_PANELS)


class PlanRequest(BaseModel):
    # The kid confirmed "Start scenes over?" / "Start panels over?": their edits are replaced too.
    start_over: bool = False


class ScenesPlanned(BaseModel):
    scenes: list[SceneRead]
    # Cast members left out because they aren't locked yet (names, for a friendly note).
    skipped: list[str]
    # Locked places left out because their words didn't pass the safety check (names, for a note
    # that says to delete them and describe new ones).
    left_out_places: list[str]
    source: PlanSource
    # True when Meta was set up but couldn't help, so the offline planner made this plan.
    fallback: bool
    label: str


BuddyAction = Literal["idea", "spelling", "name_scene"]


class BuddyRequest(BaseModel):
    action: BuddyAction
    text: str = Field(default="", max_length=MAX_SYNOPSIS)  # the synopsis, at most
    comic_id: str


class SpellingChange(BaseModel):
    before: str
    after: str


class BuddyReply(BaseModel):
    action: BuddyAction
    # idea: 1-2 questions that help the kid think (never story text).
    questions: list[str]
    # spelling: the corrected text and what changed; the kid accepts or ignores it.
    corrected: str | None
    changes: list[SpellingChange]
    # name_scene: 3 title ideas.
    titles: list[str]
    reply: str
    source: PlanSource
    fallback: bool
    label: str


class Spark(BaseModel):
    index: int
    text: str
