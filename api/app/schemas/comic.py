from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.schemas.avatar import AvatarSpec
from app.schemas.background import BackgroundRead
from app.schemas.character import CharacterRead
from app.schemas.common import (
    MAX_COMIC_CAST,
    MAX_PANEL_PROPS,
    MAX_PANELS,
    MAX_SYNOPSIS,
    BubbleType,
    ComicStatus,
    Expression,
    FieldNote,
    Mood,
    PanelCount,
    PanelMode,
    PanelSize,
    PanelStatus,
    Pose,
    Position,
    PropId,
    PropState,
    StudioStep,
    TimeOfDay,
    UtcDatetime,
)
from app.schemas.props import check_prop

TextCheck = Literal["checked", "pending", "blocked"]


class PanelCharacter(BaseModel):
    id: str  # character id
    sheet_version: int = 0
    pose: Pose = "front"
    expression: Expression = "happy"
    position: Position = "center"
    scale: float = Field(default=1.0, ge=0.5, le=1.5)


class PanelProp(BaseModel):
    """A prop in a panel (app/props): on the ground at a spot, or held or worn by `held_by` (a
    character in the panel; a turban can also be worn by the scarecrow)."""

    id: PropId
    state: PropState
    position: Position | None = None
    held_by: str | None = Field(default=None, max_length=64)

    @model_validator(mode="after")
    def _fits(self) -> "PanelProp":
        problem = check_prop(self.id, self.state, self.position, self.held_by)
        if problem:
            raise ValueError(problem)
        return self


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


MAX_SUMMARY = 300  # a scene's "What happens?" (200 cut kids' scenes short: Phase 8)
MAX_KEY_MOMENT = 160


class SceneWrite(BaseModel):
    # Send the id to keep a scene; leave it out (or send a new UUID) to create one.
    id: str | None = Field(default=None, pattern=r"^[0-9a-f-]{36}$")
    background_id: str
    character_ids: list[str] = Field(default_factory=list, max_length=MAX_COMIC_CAST)
    summary: str = Field(default="", max_length=MAX_SUMMARY)
    # Phase 8: when it happens (panels draw the place at that time), the moment that must become a
    # panel, and the panels the kid gives it (null: an even share).
    time_of_day: TimeOfDay = "day"
    key_moment: str = Field(default="", max_length=MAX_KEY_MOMENT)
    panel_count: int | None = Field(default=None, ge=1, le=MAX_PANELS)


class SceneRead(BaseModel):
    id: str
    idx: int
    background_id: str
    character_ids: list[str]
    summary: str
    time_of_day: TimeOfDay
    key_moment: str
    panel_count: int | None


class PanelUpdate(BaseModel):
    beat: str | None = Field(default=None, max_length=120)
    characters: list[PanelCharacter] | None = Field(default=None, max_length=MAX_COMIC_CAST)
    bubbles: list[Bubble] | None = Field(default=None, max_length=3)
    props: list[PanelProp] | None = Field(default=None, max_length=MAX_PANEL_PROPS)
    size: PanelSize | None = None


class StageLayer(BaseModel):
    """One thing the panel draws, where services/stage.py placed it, in draw order (back to
    front): a character (its square cell), a prop (its drawing's box) or a "Zzz"."""

    kind: Literal["character", "prop", "effect"]
    id: str  # a character id, a prop id, or the effect ("zzz")
    box: tuple[float, float, float, float]  # x, y, w, h as fractions of the panel
    flip: bool = False  # drawn mirrored left-right
    rotate: float = 0.0  # degrees, about `origin`
    origin: tuple[float, float] = (0.5, 1.0)  # a share of the box
    pose: Pose | None = None  # characters: the pose as drawn (a front pose may turn)
    expression: Expression | None = None
    state: PropState | None = None  # props
    image_url: str | None = None  # props: the cached transparent picture


class PanelStage(BaseModel):
    """What the panel draws and where, so the Studio and the Reader's sketches show exactly what
    the art will (characters, props held in hands, a sleeping "Zzz")."""

    aspect: float  # width / height of the panel's art
    layers: list[StageLayer]
    # Who stands where, the props and the size it was placed for (services/staging.stage_key):
    # while an edit to those is on its way, the web app draws the panel roughly instead.
    source: str


class PanelRead(BaseModel):
    id: str
    idx: int
    scene_id: str | None
    background_id: str
    beat: str
    characters: list[PanelCharacter]
    bubbles: list[Bubble]
    props: list[PanelProp]
    # The size the planner or the kid chose, and the size it is shown and drawn at on its page
    # (a normal panel left alone in its row is shown wide).
    size: PanelSize
    shown_size: PanelSize
    # When it happens (its scene's time of day): which version of the place it draws.
    time_of_day: TimeOfDay
    # The panel that shows its scene's key moment.
    key_moment: bool
    # The place picture the panel draws (its pinned version, at its time of day): the painted
    # sunset or night picture, or the day one with `place_tone` set, for the web app to tint the
    # way the art is (the server tints the day picture until that time is painted).
    place_url: str | None = None
    place_tone: TimeOfDay | None = None
    stage: PanelStage | None = None
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


class PageRead(BaseModel):
    """One page of the comic, as the Reader and the PDF lay it out (services/pages.py)."""

    number: int  # as printed in the PDF (page 1 is the cover)
    rows: list[list[int]]  # panel indexes (0-based): two normal panels, or one wide panel
    splash: int | None  # a splash page: this panel fills it
    the_end: bool  # a "The End" tile fills the last row(s)


class ComicCreate(BaseModel):
    title: str = Field(default="", max_length=60)
    synopsis: str = Field(default="", max_length=MAX_SYNOPSIS)


class ComicUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=60)
    synopsis: str | None = Field(default=None, max_length=MAX_SYNOPSIS)
    mood: Mood | None = None
    panel_count: PanelCount | None = None
    cast_ids: list[str] | None = Field(default=None, max_length=MAX_COMIC_CAST)
    studio_step: StudioStep | None = None
    status: ComicStatus | None = None


class ComicRead(BaseModel):
    id: str
    title: str
    synopsis: str
    # A panel plan being made right now (a job): the Studio follows it after a refresh.
    plan_job_id: str | None = None
    mood: Mood
    panel_count: PanelCount
    cast_ids: list[str]
    studio_step: StudioStep
    status: ComicStatus
    cover_url: str | None
    scenes: list[SceneRead]
    panels: list[PanelRead]
    # The pages the panels fill, by slots (6 a page: normal 1, wide 2, splash 6).
    pages: list[PageRead]
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
