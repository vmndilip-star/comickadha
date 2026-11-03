from datetime import datetime

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel

from app.models.base import new_id, utcnow


class ModerationLog(SQLModel, table=True):
    """One safety verdict on a piece of text or an image. Used from Phase 4."""

    __tablename__ = "moderation_log"

    id: str = Field(default_factory=new_id, primary_key=True)
    user_id: str = Field(foreign_key="user.id", index=True)
    kind: str = Field(max_length=8)
    target: str = Field(max_length=120)
    verdict: str = Field(max_length=8)
    categories: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utcnow)
