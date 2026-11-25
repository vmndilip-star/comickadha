import secrets
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel

from app.models.base import DEFAULT_STYLE, new_id, utcnow


def new_seed() -> int:
    return secrets.randbelow(2**31)


class Character(SQLModel, table=True):
    id: str = Field(default_factory=new_id, primary_key=True)
    user_id: str = Field(foreign_key="user.id", index=True)
    name: str = Field(max_length=24)
    role: str = Field(max_length=16)
    kind: str = Field(max_length=16)
    # The avatar spec (schemas/avatar.py): body_type, parts, colors, extras, personality, role.
    spec: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    status: str = Field(default="draft", max_length=16)
    seed: int = Field(default_factory=new_seed)
    style: str = Field(default=DEFAULT_STYLE, max_length=40)
    sheet_version: int = 0
    # Manifest of the current sheet version (see schemas/manifest.py).
    manifest: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    # The latest lock job, so the Lab can reconnect to it after a refresh.
    last_job_id: str | None = None
    # "meta" or "offline" when the Create character flow made it; cleared by the first look edit.
    designed_by: str | None = Field(default=None, max_length=8)
    # True for the ready-made starter characters (app/starters.py), which kids can't change.
    # None or False: a kid's own character (older databases get the column empty).
    starter: bool | None = None
    # The kid's choice for the painted portrait (decision 132): False shows the builder drawing
    # instead ("Use my drawing"). None or True: the painting, when there is one.
    show_portrait: bool | None = None
    deleted_at: datetime | None = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
