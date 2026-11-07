from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Column, UniqueConstraint
from sqlmodel import Field, SQLModel

from app.models.base import new_id, utcnow


class CharacterVersion(SQLModel, table=True):
    """The look a character was locked with, frozen per sheet version.

    Panels pin a sheet_version and are always drawn from this spec, never the character's current
    one, so old comics never change when a character is unlocked, edited and locked again.
    """

    __tablename__ = "character_version"
    __table_args__ = (UniqueConstraint("character_id", "version"),)

    id: str = Field(default_factory=new_id, primary_key=True)
    character_id: str = Field(foreign_key="character.id", index=True)
    version: int
    # A full avatar spec (schemas/avatar.py).
    spec: dict[str, Any] = Field(sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utcnow)
