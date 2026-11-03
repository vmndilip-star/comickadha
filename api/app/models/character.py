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
    # {skin, hair_style, hair_color, outfit, traits[], catchphrase, tint}
    spec: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    status: str = Field(default="draft", max_length=16)
    seed: int = Field(default_factory=new_seed)
    style: str = Field(default=DEFAULT_STYLE, max_length=40)
    sheet_version: int = 0
    # Manifest of the current sheet version (see schemas/manifest.py).
    manifest: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    deleted_at: datetime | None = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
