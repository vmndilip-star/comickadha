"""The avatar spec: everything a kid picks in the Bitmoji-style builder.

Part and colour choices are checked against the shared parts catalog (app/avatar/spec.py), so the
schema itself only fixes the shape; `parts` maps a category (hair, top, ...) to an option id.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import HexColor, Role, Trait

BodyType = Literal["kid", "grown_up", "robot", "cat", "dog", "bear"]


class Personality(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # A plain default (Pydantic copies it) keeps the field required in the generated types.
    traits: list[Trait] = Field(default=[], max_length=3)
    catchphrase: str = Field(default="", max_length=60)


class AvatarSpec(BaseModel):
    # Unknown keys are an error, not ignored: a spec is always sent whole, so an old-style partial
    # spec ({"outfit": ...}) must not quietly turn the character back into the default kid.
    model_config = ConfigDict(extra="forbid")

    body_type: BodyType = "kid"
    # category -> option id, e.g. {"hair": "curly", "top": "hoodie"}
    parts: dict[str, str] = {}
    # colour slot -> palette hex, e.g. {"skin": "#CF8D5B", "top": "#FF6B4A"}
    colors: dict[str, HexColor] = {}
    extras: list[str] = Field(default=[], max_length=8)
    personality: Personality = Personality()
    role: Role = "friend"
