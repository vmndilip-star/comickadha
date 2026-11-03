from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel

from app.models.base import new_id, utcnow


class Job(SQLModel, table=True):
    """Background work (sheet generation, comic generation, redraw). Used from Phase 3."""

    id: str = Field(default_factory=new_id, primary_key=True)
    kind: str = Field(max_length=32)
    target_id: str = Field(index=True)
    status: str = Field(default="queued", max_length=16)
    progress: float = 0.0
    # Every SSE event sent so far, replayed when a client reconnects.
    events: list[dict[str, Any]] = Field(
        default_factory=list, sa_column=Column(JSON, nullable=False)
    )
    error: str | None = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
