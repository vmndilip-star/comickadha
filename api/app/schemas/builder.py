"""The builder helper: create, describe, surprise, ideas and from-drawing."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.schemas.avatar import AvatarSpec, BodyType
from app.schemas.common import Role, Trait, UtcDatetime

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


class LastCall(BaseModel):
    """The last call to Meta's API (dev-only indicator): when, whether it worked, the error type."""

    ok: bool
    at: UtcDatetime
    error: str | None


class HelperInfo(BaseModel):
    source: HelperSource
    label: str
    # Meta only: the last call's outcome (None before the first call, and offline).
    last_call: LastCall | None = None
    # Drawings go to Meta's API, so a grown-up says OK once per profile first.
    drawing_needs_consent: bool
    drawing_consent: bool


# ---- create (docs/character-safety.md) -------------------------------------------------------

Kind = Literal["person", "robot", "cat", "dog", "bear"]
# People only: kids (little or big) get the kid body, grown-ups and grandparents the grown-up body.
Age = Literal["little_kid", "big_kid", "grown_up", "grandparent"]
# The catalog's face shapes (a test keeps this list in step with catalog.json).
FaceShape = Literal[
    "round", "oval", "square", "heart", "box", "dome", "screen", "cat", "dog", "bear"
]


class CatalogChoice(BaseModel):
    """One catalog choice: a part category ("hair") or a colour slot ("colors.hair"), and the id
    of a part or palette colour. Never free text."""

    model_config = ConfigDict(extra="forbid")
    target: str = Field(pattern=r"^(colors\.)?[a-z_]{2,20}$")
    value: str = Field(pattern=r"^[a-z0-9_]{1,30}$")


class CreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Kind
    age: Age | None = None
    face_shape: FaceShape | None = None
    description: Annotated[str, StringConstraints(strip_whitespace=True, max_length=300)] = ""
    # The answer to the last follow-up question: any catalog choice that fits the body type.
    follow_up_answer: CatalogChoice | None = None
    # Only with follow_up_answer: the character so far, so the answer changes just that choice.
    # Checked like a saved look; its personality never reaches Meta.
    look: AvatarSpec | None = None
    name: Annotated[str, StringConstraints(strip_whitespace=True, max_length=24)] = ""
    role: Role = "hero"


class FollowUpOption(CatalogChoice):
    label: str = Field(max_length=40)


class FollowUp(BaseModel):
    """One question about the character's looks or personality, with 2-4 catalog choices."""

    question: str
    options: list[FollowUpOption]


class Created(BaseModel):
    spec: AvatarSpec
    name_ideas: list[str]
    catchphrase: str
    intro_line: str
    follow_up: FollowUp | None
    # The role the helper thinks fits (the kid picks the final one).
    role_suggestion: Role
    # Kind notes about the description (e.g. body words that were left out).
    notes: list[str]
    reply: str
    unmatched: list[str]
    source: HelperSource
    fallback: bool
    label: str
