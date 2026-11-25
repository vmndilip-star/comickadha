from datetime import datetime

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel

from app.models.base import new_id, utcnow


class PaintLog(SQLModel, table=True):
    """One picture an image model was asked to paint (a portrait, or later a panel), whatever came
    of it (decision 134). The daily caps add up `attempts` (each one is an image model call)."""

    __tablename__ = "paint_log"

    id: str = Field(default_factory=new_id, primary_key=True)
    user_id: str = Field(index=True)
    kind: str = Field(max_length=16)  # "portrait" (Phase B adds "panel")
    target: str = Field(max_length=120)
    provider: str = Field(max_length=16)  # "mock" never counts toward the caps
    attempts: int = 0
    ms: int = 0
    # "saved", "blocked" (image check), "look_failed" (look check) or "error" (no usable picture).
    outcome: str = Field(max_length=16)
    # What the look check saw differ: hard ones failed the picture, the rest are only logged.
    findings: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    # Painted by `seed --portraits`: logged, but never counted toward the caps.
    seed_run: bool = False
    created_at: datetime = Field(default_factory=utcnow, index=True)
