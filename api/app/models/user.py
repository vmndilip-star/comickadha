from datetime import datetime

from sqlmodel import Field, SQLModel

from app.models.base import new_id, utcnow


class User(SQLModel, table=True):
    """The kid's profile. The hackathon build has one seeded profile and no auth."""

    id: str = Field(default_factory=new_id, primary_key=True)
    display_name: str = Field(max_length=40)
    avatar_color: str = Field(max_length=7)
    created_at: datetime = Field(default_factory=utcnow)
