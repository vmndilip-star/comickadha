from pydantic import BaseModel, Field

from app.schemas.background import BackgroundRead
from app.schemas.character import CharacterRead
from app.schemas.common import (
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


class SceneWrite(BaseModel):
    # Send the id to keep a scene; leave it out (or send a new UUID) to create one.
    id: str | None = Field(default=None, pattern=r"^[0-9a-f-]{36}$")
    background_id: str
    character_ids: list[str] = Field(default_factory=list, max_length=3)
    summary: str = Field(default="", max_length=200)


class SceneRead(BaseModel):
    id: str
    idx: int
    background_id: str
    character_ids: list[str]
    summary: str


class PanelUpdate(BaseModel):
    beat: str | None = Field(default=None, max_length=120)
    characters: list[PanelCharacter] | None = Field(default=None, max_length=3)
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
    art_url: str | None
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
    cast_ids: list[str] | None = Field(default=None, max_length=3)
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
    created_at: UtcDatetime
    updated_at: UtcDatetime
