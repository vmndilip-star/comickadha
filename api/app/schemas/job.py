from typing import Literal

from pydantic import BaseModel

from app.schemas.common import UtcDatetime

JobStatus = Literal["queued", "running", "done", "failed"]
JobKind = Literal["character_sheet", "background_image"]


class JobStarted(BaseModel):
    """Returned with 202 by lock endpoints. Follow it on GET /api/jobs/{job_id}/events."""

    job_id: str
    kind: JobKind
    target_id: str


class JobRead(BaseModel):
    id: str
    kind: str
    target_id: str
    status: JobStatus
    progress: float
    error: str | None
    event_count: int
    created_at: UtcDatetime
    updated_at: UtcDatetime
