from pydantic import BaseModel, Field

from app.schemas.common import HexColor, LockStatus, PlaceName, TimeOfDay, UtcDatetime


class BackgroundCreate(BaseModel):
    name: PlaceName
    description: str = Field(default="", max_length=240)
    # Omitted: the server picks a placeholder colour.
    tint: HexColor | None = None


class BackgroundUpdate(BaseModel):
    name: PlaceName | None = None
    description: str | None = Field(default=None, max_length=240)
    tint: HexColor | None = None


class BackgroundRead(BaseModel):
    id: str
    name: str
    description: str
    status: LockStatus
    seed: int
    style: str
    version: int
    tint: str
    image_url: str | None
    thumb_url: str | None
    last_job_id: str | None
    # Deleted places still resolve by id for comics that use them.
    deleted: bool = False
    # The times of day this version has real pictures for (Phase 8): "day", and "sunset" and
    # "night" once painted (until then panels tint the day picture).
    times: list[TimeOfDay] = ["day"]
    created_at: UtcDatetime
    updated_at: UtcDatetime
