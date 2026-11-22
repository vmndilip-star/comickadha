import json
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Header
from fastapi.responses import StreamingResponse
from sqlmodel import Session

from app.deps import JobsDep, SessionDep, UserDep
from app.errors import ERROR_RESPONSES, not_found
from app.models import Background, Character, Comic, Job, User
from app.schemas.job import JobRead

router = APIRouter(prefix="/api/jobs", tags=["jobs"], responses=ERROR_RESPONSES)


def _owned_job(session: Session, user: User, job: Job | None) -> Job:
    if job is None:
        raise not_found("drawing")
    target: Character | Background | Comic | None
    if job.kind == "character_sheet":
        target = session.get(Character, job.target_id)
    elif job.kind == "comic":
        target = session.get(Comic, job.target_id)
    else:
        target = session.get(Background, job.target_id)
    if target is None or target.user_id != user.id:
        raise not_found("drawing")
    return job


@router.get("/{job_id}")
def read_job(job_id: str, session: SessionDep, user: UserDep, jobs: JobsDep) -> JobRead:
    job = _owned_job(session, user, jobs.snapshot(job_id))
    return JobRead.model_validate({**job.model_dump(), "event_count": len(job.events)})


@router.get(
    "/{job_id}/events",
    response_class=StreamingResponse,
    responses={200: {"content": {"text/event-stream": {}}, "description": "Server-sent events"}},
)
async def job_events(
    job_id: str,
    session: SessionDep,
    user: UserDep,
    jobs: JobsDep,
    after: int | None = None,
    last_event_id: Annotated[str | None, Header(alias="Last-Event-ID")] = None,
) -> StreamingResponse:
    """Server-sent events: progress | cell_ready | panel_ready | panel_failed | done | error
    (panel_ready and panel_failed come from "Make my comic!" jobs).

    Replays every event after `after` (or the browser's Last-Event-ID on reconnect), then streams
    live ones until the job ends.
    """
    _owned_job(session, user, jobs.snapshot(job_id))
    if after is not None:
        start = after
    elif last_event_id and last_event_id.isdigit():
        start = int(last_event_id)
    else:
        start = 0

    async def events() -> AsyncIterator[str]:
        async for event in jobs.stream(job_id, start):
            if event is None:
                yield ": keep-alive\n\n"
            else:
                yield f"id: {event.id}\nevent: {event.type}\ndata: {json.dumps(event.data)}\n\n"

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
