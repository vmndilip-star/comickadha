from datetime import datetime

from sqlmodel import Field, SQLModel

from app.models.base import DEFAULT_STYLE, new_id, utcnow
from app.models.character import new_seed


class Background(SQLModel, table=True):
    """A place. Locked places have one reference image used in every panel."""

    id: str = Field(default_factory=new_id, primary_key=True)
    user_id: str = Field(foreign_key="user.id", index=True)
    name: str = Field(max_length=40)
    description: str = Field(default="", max_length=240)
    status: str = Field(default="draft", max_length=16)
    seed: int = Field(default_factory=new_seed)
    style: str = Field(default=DEFAULT_STYLE, max_length=40)
    version: int = 0
    # Placeholder colour shown until (or instead of) the reference image.
    tint: str = Field(default="#B7E4A7", max_length=7)
    image_key: str | None = None
    thumb_key: str | None = None
    last_job_id: str | None = None
    deleted_at: datetime | None = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
