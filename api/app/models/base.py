"""Shared helpers for table models."""

from datetime import UTC, datetime
from uuid import uuid4

DEFAULT_STYLE = "sunday-funnies-v1"


def new_id() -> str:
    return str(uuid4())


def utcnow() -> datetime:
    """Timezone-aware UTC timestamp (SQLModel stores and returns datetimes with their zone)."""
    return datetime.now(UTC)
