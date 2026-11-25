from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel

from app.models.base import new_id, utcnow


class Comic(SQLModel, table=True):
    id: str = Field(default_factory=new_id, primary_key=True)
    user_id: str = Field(foreign_key="user.id", index=True)
    title: str = Field(default="", max_length=60)
    # SQLite doesn't enforce lengths; the API checks MAX_SYNOPSIS (raised from 600 in Phase 7).
    synopsis: str = Field(default="", max_length=1000)
    mood: str = Field(default="adventure", max_length=16)
    panel_count: int = 6
    cast_ids: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    studio_step: int = 1
    status: str = Field(default="draft", max_length=16)
    cover_key: str | None = None
    # The latest "Make my comic!" job, so the Reader can reconnect after a refresh.
    last_job_id: str | None = None
    # Title, synopsis and scene summaries: "checked" by every available check, or "pending" when
    # Meta's classifier couldn't look yet (decision 55). None counts as checked (older comics).
    text_check: str | None = None
    # A classifier block found later (background re-check): {"field", "message"}.
    check_note: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    deleted_at: datetime | None = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class Scene(SQLModel, table=True):
    id: str = Field(default_factory=new_id, primary_key=True)
    comic_id: str = Field(foreign_key="comic.id", index=True)
    idx: int
    background_id: str = Field(foreign_key="background.id")
    character_ids: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    summary: str = Field(default="", max_length=300)
    # When the kid last changed it (None: as the planner made it). Re-planning asks first.
    edited_at: datetime | None = None
    # Phase 8. When it happens ("day" when None), the moment that must become a panel, and the
    # panels the kid gave it (None: an even share of the comic's panels).
    time_of_day: str | None = Field(default=None, max_length=8)
    key_moment: str | None = Field(default=None, max_length=160)
    panel_count: int | None = None


class Panel(SQLModel, table=True):
    id: str = Field(default_factory=new_id, primary_key=True)
    comic_id: str = Field(foreign_key="comic.id", index=True)
    # Cleared when the kid removes the scene; the panel keeps its background.
    scene_id: str | None = Field(default=None, foreign_key="scene.id")
    idx: int
    background_id: str = Field(foreign_key="background.id")
    beat: str = Field(default="", max_length=120)
    # [{id, sheet_version, pose, expression, position, scale}]
    characters: list[dict[str, Any]] = Field(
        default_factory=list, sa_column=Column(JSON, nullable=False)
    )
    # [{id, speaker, type, text, box, tail}]
    bubbles: list[dict[str, Any]] = Field(
        default_factory=list, sa_column=Column(JSON, nullable=False)
    )
    status: str = Field(default="planned", max_length=16)
    mode: str = Field(default="composite", max_length=16)
    art_key: str | None = None
    image_key: str | None = None
    error: str | None = None
    # Bubble words: "checked" or "pending" (decision 55). None counts as checked.
    text_check: str | None = None
    # Bumped on every re-draw, so browsers fetch the new art (art.png?v=n).
    art_version: int | None = None
    thumb_key: str | None = None
    # final.png (art + bubbles), and the hash of what it was made from (stale when it differs).
    final_key: str | None = None
    final_hash: str | None = None
    # When the kid last changed it (None: as the planner made it). Re-planning keeps edited panels.
    edited_at: datetime | None = None
    updated_at: datetime = Field(default_factory=utcnow)
    # Phase 8. [{id, state, position | held_by}]: story objects drawn as their own layer.
    props: list[dict[str, Any]] | None = Field(default=None, sa_column=Column(JSON))
    # The version of the place it draws (pinned like a character's sheet_version, so repainting a
    # place never changes an old comic). None only before the first startup that added it.
    place_version: int | None = None
    size: str | None = Field(default=None, max_length=8)  # normal (None), wide or splash
    # The size it is shown and drawn at on its page (services/pages.py: a normal panel alone in
    # its row is shown wide...). Its bubbles are laid out and its art drawn at this size.
    shown_size: str | None = Field(default=None, max_length=8)
    time_of_day: str | None = Field(default=None, max_length=8)  # day (None), sunset or night
    key_moment: bool | None = None  # the panel that shows its scene's key moment
