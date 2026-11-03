from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel

from app.models.base import new_id, utcnow


class Comic(SQLModel, table=True):
    id: str = Field(default_factory=new_id, primary_key=True)
    user_id: str = Field(foreign_key="user.id", index=True)
    title: str = Field(default="", max_length=60)
    synopsis: str = Field(default="", max_length=600)
    mood: str = Field(default="adventure", max_length=16)
    panel_count: int = 6
    cast_ids: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    studio_step: int = 1
    status: str = Field(default="draft", max_length=16)
    cover_key: str | None = None
    deleted_at: datetime | None = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class Scene(SQLModel, table=True):
    id: str = Field(default_factory=new_id, primary_key=True)
    comic_id: str = Field(foreign_key="comic.id", index=True)
    idx: int
    background_id: str = Field(foreign_key="background.id")
    character_ids: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    summary: str = Field(default="", max_length=200)


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
    updated_at: datetime = Field(default_factory=utcnow)
