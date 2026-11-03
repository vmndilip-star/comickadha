from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import (
    CharacterKind,
    HairStyle,
    HexColor,
    LockStatus,
    Name,
    Role,
    Trait,
    UtcDatetime,
)
from app.schemas.manifest import CharacterManifest


class CharacterSpec(BaseModel):
    skin: HexColor = "#F2C29B"
    hair_style: HairStyle = "curly"
    hair_color: HexColor = "#3B2314"
    outfit: str = Field(default="", max_length=80)
    # A plain default (Pydantic copies it) keeps the field required in the generated types.
    traits: list[Trait] = Field(default=[], max_length=3)
    catchphrase: str = Field(default="", max_length=60)
    tint: HexColor = "#FFE9A8"


class CharacterSpecPatch(BaseModel):
    """Partial spec update: only the fields sent are changed."""

    skin: HexColor | None = None
    hair_style: HairStyle | None = None
    hair_color: HexColor | None = None
    outfit: str | None = Field(default=None, max_length=80)
    traits: list[Trait] | None = Field(default=None, max_length=3)
    catchphrase: str | None = Field(default=None, max_length=60)
    tint: HexColor | None = None


class CharacterCreate(BaseModel):
    name: Name = "New hero"
    role: Role = "friend"
    kind: CharacterKind = "kid"
    # Omitted: the server picks defaults and a tint for the cast slot.
    spec: CharacterSpec | None = None


class CharacterUpdate(BaseModel):
    name: Name | None = None
    role: Role | None = None
    kind: CharacterKind | None = None
    spec: CharacterSpecPatch | None = None


class CharacterRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    role: Role
    kind: CharacterKind
    spec: CharacterSpec
    status: LockStatus
    seed: int
    style: str
    sheet_version: int
    manifest: CharacterManifest | None
    created_at: UtcDatetime
    updated_at: UtcDatetime
