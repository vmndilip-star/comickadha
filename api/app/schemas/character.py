from pydantic import BaseModel, ConfigDict

from app.schemas.avatar import AvatarSpec
from app.schemas.common import CharacterKind, DesignedBy, LockStatus, Name, Role, UtcDatetime
from app.schemas.manifest import CharacterManifest


class CharacterCreate(BaseModel):
    name: Name = "New hero"
    # Omitted: a default kid, with a card colour for the cast slot.
    spec: AvatarSpec | None = None
    # Set by the Create character flow: which helper designed it (shown as a badge).
    designed_by: DesignedBy | None = None


class CharacterUpdate(BaseModel):
    name: Name | None = None
    # The painted portrait or the builder drawing (decision 132). Allowed on a locked character:
    # it changes what the cards show, never the look.
    show_portrait: bool | None = None
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
    # "meta" until the kid edits the look: the "Designed by Meta AI" badge.
    designed_by: DesignedBy | None = None
    seed: int
    style: str
    sheet_version: int
    manifest: CharacterManifest | None
    # The latest lock job: reconnect to its events after a refresh.
    last_job_id: str | None
    # A ready-made starter character: read-only for every kid ("Make it mine" copies it).
    starter: bool = False
    # Deleted characters still resolve by id for comics that use them.
    deleted: bool = False
    # The kid's choice: the painted portrait (when there is one) or the builder drawing.
    show_portrait: bool = True
    # A portrait being painted now: reconnect to its events after a refresh.
    portrait_job_id: str | None = None
    created_at: UtcDatetime
    updated_at: UtcDatetime
