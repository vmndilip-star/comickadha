from pydantic import BaseModel, ConfigDict

from app.schemas.avatar import AvatarSpec
from app.schemas.common import CharacterKind, LockStatus, Name, Role, UtcDatetime
from app.schemas.manifest import CharacterManifest


class CharacterCreate(BaseModel):
    name: Name = "New hero"
    # Omitted: a default kid, with a card colour for the cast slot.
    spec: AvatarSpec | None = None


class CharacterUpdate(BaseModel):
    name: Name | None = None
    # The whole spec, checked against the parts catalog (unknown parts are a 422 unknown_part).
    spec: AvatarSpec | None = None


class CharacterRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    # Both are written from the spec: kind from body_type (cat, dog and bear are "animal").
    role: Role
    kind: CharacterKind
    spec: AvatarSpec
    status: LockStatus
    seed: int
    style: str
    sheet_version: int
    manifest: CharacterManifest | None
    # The latest lock job: reconnect to its events after a refresh.
    last_job_id: str | None
    # Deleted characters still resolve by id for comics that use them.
    deleted: bool = False
    created_at: UtcDatetime
    updated_at: UtcDatetime
