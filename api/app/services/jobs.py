"""Background jobs on the server's asyncio loop (no Celery), with events stored for SSE replay.

A job's work is an async function that emits events (progress, cell_ready) and returns the data for
the final `done` event. Every event is saved on the job row, so a client that reconnects gets the
whole history replayed before it sees live events.
"""

import asyncio
import logging
from collections import defaultdict
from collections.abc import AsyncIterator, Awaitable, Callable
from concurrent.futures import Future
from dataclasses import dataclass
from typing import Any, ParamSpec, TypeVar

from sqlalchemy import Engine
from sqlmodel import Session, col, select

from app.models import Background, Character, Job, Panel
from app.models.base import utcnow

log = logging.getLogger(__name__)

FAILED_MESSAGE = "Oops, the drawing didn't work. Tap Lock to try again!"
INTERRUPTED_MESSAGE = "Oops, the drawing got interrupted. Tap Lock to try again!"
PANEL_INTERRUPTED = "Oops, this panel got interrupted. Tap Try again!"
KEEPALIVE_SECONDS = 15.0
FINAL_EVENTS = ("done", "error")

P = ParamSpec("P")
T = TypeVar("T")


class JobFailed(Exception):
    """Raise from job work to fail with a kid-friendly message."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


@dataclass(frozen=True)
class JobEvent:
    id: int
    type: str
    data: dict[str, Any]


class JobContext:
    """Handed to job work: emit events and run blocking code off the event loop."""

    def __init__(self, runner: "JobRunner", job_id: str) -> None:
        self.runner = runner
        self.job_id = job_id

    def emit(
        self, type: str, data: dict[str, Any] | None = None, progress: float | None = None
    ) -> None:
        self.runner.emit(self.job_id, type, data or {}, progress)

    def emit_threadsafe(
        self, type: str, data: dict[str, Any] | None = None, progress: float | None = None
    ) -> None:
        """emit() for code running in a worker thread (the sheet pipeline)."""
        self.runner.loop.call_soon_threadsafe(self.emit, type, data, progress)

    async def run(self, fn: Callable[P, T], *args: P.args, **kwargs: P.kwargs) -> T:
        return await asyncio.to_thread(fn, *args, **kwargs)


Work = Callable[[JobContext], Awaitable[dict[str, Any]]]


class JobRunner:
    def __init__(self, engine: Engine, loop: asyncio.AbstractEventLoop) -> None:
        self.engine = engine
        self.loop = loop
        self._subscribers: defaultdict[str, set[asyncio.Queue[JobEvent]]] = defaultdict(set)
        self._running: set[Future[None]] = set()

    def create(self, kind: str, target_id: str) -> Job:
        with Session(self.engine) as session:
            job = Job(kind=kind, target_id=target_id)
            session.add(job)
            session.commit()
            session.refresh(job)
            return job

    def start(self, job_id: str, work: Work, on_error: Callable[[str], None] | None = None) -> None:
        """Schedules the work on the server loop. Safe to call from request threads."""
        future = asyncio.run_coroutine_threadsafe(self._run(job_id, work, on_error), self.loop)
        self._running.add(future)
        future.add_done_callback(self._running.discard)

    async def _run(self, job_id: str, work: Work, on_error: Callable[[str], None] | None) -> None:
        self._update(job_id, status="running")
        try:
            result = await work(JobContext(self, job_id))
        except Exception as exc:
            message = exc.message if isinstance(exc, JobFailed) else FAILED_MESSAGE
            log.exception("job %s failed", job_id)
            if on_error:
                on_error(message)
            self.emit(job_id, "error", {"message": message}, status="failed", error=message)
            return
        self.emit(job_id, "done", {**result, "progress": 1.0}, progress=1.0, status="done")

    def emit(
        self,
        job_id: str,
        type: str,
        data: dict[str, Any],
        progress: float | None = None,
        *,
        status: str | None = None,
        error: str | None = None,
    ) -> JobEvent:
        """Saves the event on the job (for replay), then tells live listeners. Loop thread only."""
        with Session(self.engine) as session:
            job = session.get(Job, job_id)
            if job is None:
                raise LookupError(job_id)
            if progress is not None:
                job.progress = progress
                data = {**data, "progress": progress}
            event = JobEvent(id=len(job.events) + 1, type=type, data=data)
            job.events = [*job.events, {"id": event.id, "type": type, "data": data}]
            if status:
                job.status = status
            if error:
                job.error = error
            job.updated_at = utcnow()
            session.add(job)
            session.commit()
        for queue in self._subscribers[job_id]:
            queue.put_nowait(event)
        return event

    def _update(self, job_id: str, **fields: Any) -> None:
        with Session(self.engine) as session:
            job = session.get(Job, job_id)
            if job is None:
                return
            for key, value in fields.items():
                setattr(job, key, value)
            job.updated_at = utcnow()
            session.add(job)
            session.commit()

    def snapshot(self, job_id: str) -> Job | None:
        with Session(self.engine) as session:
            return session.get(Job, job_id)

    async def stream(self, job_id: str, after: int = 0) -> AsyncIterator[JobEvent | None]:
        """Past events after `after`, then live ones until done/error. None means keep-alive."""
        queue: asyncio.Queue[JobEvent] = asyncio.Queue()
        self._subscribers[job_id].add(
            queue
        )  # subscribe first, so nothing slips between replay and live
        try:
            job = self.snapshot(job_id)
            if job is None:
                return
            for raw in job.events:
                if raw["id"] > after:
                    after = raw["id"]
                    yield JobEvent(id=raw["id"], type=raw["type"], data=raw["data"])
            if job.status in ("done", "failed"):
                return
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=KEEPALIVE_SECONDS)
                except TimeoutError:
                    yield None
                    continue
                if event.id <= after:
                    continue
                after = event.id
                yield event
                if event.type in FINAL_EVENTS:
                    return
        finally:
            self._subscribers[job_id].discard(queue)

    def cancel_all(self) -> None:
        for future in list(self._running):
            future.cancel()


def fail_interrupted_jobs(engine: Engine) -> int:
    """At startup: jobs left queued/running by a restart can never finish, so fail them kindly."""
    with Session(engine) as session:
        stuck = list(session.exec(select(Job).where(col(Job.status).in_(("queued", "running")))))
        for job in stuck:
            event = {
                "id": len(job.events) + 1,
                "type": "error",
                "data": {"message": INTERRUPTED_MESSAGE},
            }
            job.events = [*job.events, event]
            job.status = "failed"
            job.error = INTERRUPTED_MESSAGE
            job.updated_at = utcnow()
            session.add(job)
            if job.kind == "comic":
                fail_rendering_panels(session, job.target_id, PANEL_INTERRUPTED)
                continue
            target = (
                session.get(Character, job.target_id)
                if job.kind == "character_sheet"
                else session.get(Background, job.target_id)
            )
            if target is not None and target.status == "generating":
                target.status = "failed"
                session.add(target)
        session.commit()
        return len(stuck)


def fail_rendering_panels(session: Session, comic_id: str, message: str) -> None:
    """Panels a comic job left mid-drawing (restart or crash) become failed, so Try again shows."""
    stmt = select(Panel).where(Panel.comic_id == comic_id, Panel.status == "rendering")
    for panel in session.exec(stmt):
        panel.status, panel.error = "failed", message
        session.add(panel)
