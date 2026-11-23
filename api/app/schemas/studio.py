"""Story Studio: the planner (scenes, then panels), the Story Buddy and story sparks.

The Planned* models are what a planner (Meta's model or the offline one) returns. They never
carry coordinates or ids the server owns: the server adds idx, ids, sheet versions, scale and the
bubble layout. Semantic checks (locked ids, catalog names, counts, positions, bubble length,
speakers) live in services/story_planner.py.
"""

from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.comic import PanelRead, SceneRead
from app.schemas.common import (
    MAX_COMIC_CAST,
    MAX_PANEL_CAST,
    BubbleType,
    Expression,
    Pose,
    Position,
)

PlanSource = Literal["meta", "mock"]


class PlannedScene(BaseModel):
    background_id: str
    character_ids: list[str] = Field(min_length=1, max_length=MAX_COMIC_CAST)
    summary: str = Field(min_length=1, max_length=200)


class ScenePlan(BaseModel):
    scenes: list[PlannedScene] = Field(min_length=2, max_length=4)


class PlannedCharacter(BaseModel):
    id: str
    pose: Pose
    expression: Expression
    position: Position


class PlannedBubble(BaseModel):
    speaker: str  # a character in the panel, or "narrator"
    type: BubbleType
    text: str = Field(min_length=1, max_length=120)


class PlannedPanel(BaseModel):
    scene_id: str
    beat: str = Field(min_length=1, max_length=120)
    characters: list[PlannedCharacter] = Field(min_length=1, max_length=MAX_PANEL_CAST)
    bubbles: list[PlannedBubble] = Field(default=[], max_length=3)


class PanelPlan(BaseModel):
    panels: list[PlannedPanel] = Field(min_length=4, max_length=8)


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


class PanelsPlanned(BaseModel):
    panels: list[PanelRead]
    # How many edited or drawn panels were kept as they were.
    kept: int
    left_out_places: list[str]
    source: PlanSource
    fallback: bool
    label: str


BuddyAction = Literal["idea", "spelling", "name_scene"]


class BuddyRequest(BaseModel):
    action: BuddyAction
    text: str = Field(default="", max_length=600)
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
