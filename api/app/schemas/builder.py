"""The builder helper: describe, surprise, ideas and from-drawing."""

from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints

from app.schemas.avatar import AvatarSpec, BodyType
from app.schemas.common import Trait

HelperSource = Literal["meta", "mock"]
Description = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]


class DescribeRequest(BaseModel):
    text: Description
    spec: AvatarSpec


class SurpriseRequest(BaseModel):
    # Keep this body type; empty lets the helper pick one.
    body_type: BodyType | None = None
    # The current character: its role is kept.
    spec: AvatarSpec | None = None


class IdeasRequest(BaseModel):
    spec: AvatarSpec
    name: str = Field(default="", max_length=24)


class DrawingRequest(BaseModel):
    # A data URL (data:image/png;base64,...). Processed in memory and never stored. Over 5 MB is a
    # 413 too_big (checked in services/drawing.py, not here, so it isn't a 422).
    image: str
    spec: AvatarSpec


class Suggestion(BaseModel):
    """A new spec to apply in the builder (the kid can still tweak or undo it)."""

    spec: AvatarSpec
    # What changed: "body_type", a part category ("hair"), "colors.<slot>", "extras", "personality".
    changed: list[str]
    name_ideas: list[str]
    reply: str
    # Wishes the parts library can't draw yet.
    unmatched: list[str]
    source: HelperSource
    # True when Meta's API couldn't be reached and the offline helper answered instead.
    fallback: bool
    label: str


class Ideas(BaseModel):
    name_ideas: list[str]
    traits: list[Trait]
    catchphrase: str
    reply: str
    source: HelperSource
    fallback: bool
    label: str


class HelperInfo(BaseModel):
    source: HelperSource
    label: str
    # Drawings go to Meta's API, so a grown-up says OK once per profile first.
    drawing_needs_consent: bool
    drawing_consent: bool
