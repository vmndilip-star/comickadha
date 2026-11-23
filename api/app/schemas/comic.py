from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.avatar import AvatarSpec
from app.schemas.background import BackgroundRead
from app.schemas.character import CharacterRead
from app.schemas.common import (
    MAX_COMIC_CAST,
    MAX_PANEL_CAST,
    BubbleType,
    ComicStatus,
    Expression,
    FieldNote,
    Mood,
    PanelCount,
    PanelMode,
    PanelStatus,
    Pose,
    Position,
    StudioStep,
    UtcDatetime,
)

TextCheck = Literal["checked", "pending", "blocked"]


class PanelCharacter(BaseModel):
    id: str  # character id
    sheet_version: int = 0
    pose: Pose = "front"
    expression: Expression = "happy"
    position: Position = "center"
    scale: float = Field(default=1.0, ge=0.5, le=1.5)


class Bubble(BaseModel):
    id: str = Field(min_length=1, max_length=64)  # clients create ids for new bubbles
    speaker: str  # character id or "narrator"
    type: BubbleType = "talk"
    text: str = Field(max_length=120)
    # Phase 5: bubble box (x, y, w, h) and tail tip (x, y), as fractions of the panel.
    box: tuple[float, float, float, float] | None = None
    tail: tuple[float, float] | None = None
    # The kid moved or resized it: its box is kept; only its tail is re-aimed.
    fixed: bool = False


class SceneWrite(BaseModel):
    # Send the id to keep a scene; leave it out (or send a new UUID) to create one.
    id: str | None = Field(default=None, pattern=r"^[0-9a-f-]{36}$")
    background_id: str
    character_ids: list[str] = Field(default_factory=list, max_length=MAX_COMIC_CAST)
    summary: str = Field(default="", max_length=200)


class SceneRead(BaseModel):
    id: str
    idx: int
    background_id: str
    character_ids: list[str]
    summary: str


class PanelUpdate(BaseModel):
    beat: str | None = Field(default=None, max_length=120)
    characters: list[PanelCharacter] | None = Field(default=None, max_length=MAX_PANEL_CAST)
    bubbles: list[Bubble] | None = Field(default=None, max_length=3)


class PanelRead(BaseModel):
    id: str
    idx: int
    scene_id: str | None
    background_id: str
    beat: str
    characters: list[PanelCharacter]
    bubbles: list[Bubble]
    status: PanelStatus
    mode: PanelMode
    # art.png (background + characters, no bubbles), with ?v= so a re-draw shows at once.
    art_url: str | None
    thumb_url: str | None
    # final.png (art + bubbles baked in), made on demand when stale.
    final_url: str | None
    # Bubble words checked by every available check, still waiting for Meta (decision 55), or
    # blocked by that later check (the message is in `error`).
    text_check: TextCheck
    image_url: str | None
    error: str | None
    updated_at: UtcDatetime


class ComicCreate(BaseModel):
    title: str = Field(default="", max_length=60)
    synopsis: str = Field(default="", max_length=600)


class ComicUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=60)
    synopsis: str | None = Field(default=None, max_length=600)
    mood: Mood | None = None
    panel_count: PanelCount | None = None
    cast_ids: list[str] | None = Field(default=None, max_length=MAX_COMIC_CAST)
    studio_step: StudioStep | None = None
    status: ComicStatus | None = None


class ComicRead(BaseModel):
    id: str
    title: str
    synopsis: str
    mood: Mood
    panel_count: PanelCount
    cast_ids: list[str]
    studio_step: StudioStep
    status: ComicStatus
    cover_url: str | None
    scenes: list[SceneRead]
    panels: list[PanelRead]
    # Every character and place the comic uses, including deleted ones, so it never changes.
    characters: list[CharacterRead]
    backgrounds: list[BackgroundRead]
    # Notes from the instant local safety checks on the title and synopsis (a draft is still
    # saved; it just can't be planned until it's changed).
    safety_notes: list[FieldNote]
    # The frozen look of every character sheet version the panels use: {character_id:
    # {"version": spec}}. Panels are drawn from these, never the current spec.
    looks: dict[str, dict[str, AvatarSpec]]
    # The latest Make my comic! job, to follow (and reconnect to) over SSE.
    last_job_id: str | None
    # Title and synopsis: checked, waiting for Meta (decision 55), or blocked by that later check
    # (the message is in safety_notes). PDF export needs "checked" here and on every panel.
    text_check: TextCheck
    created_at: UtcDatetime
    updated_at: UtcDatetime
