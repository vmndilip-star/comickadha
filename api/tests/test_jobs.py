import asyncio
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.config import Settings
from app.db import init_db, make_engine
from app.main import create_app
from app.models import Background, Character, Job
from app.services.jobs import JobContext, JobEvent, JobRunner
from tests.conftest import IDS, sse_events, wait_for_job


def test_stream_replays_past_events_then_streams_live_ones(tmp_path: Path) -> None:
    async def scenario() -> list[JobEvent | None]:
        engine = make_engine(f"sqlite:///{(tmp_path / 'jobs.db').as_posix()}")
        init_db(engine)
        runner = JobRunner(engine, asyncio.get_running_loop())
        gate = asyncio.Event()

        async def work(ctx: JobContext) -> dict[str, Any]:
            for step in range(3):
                ctx.emit("progress", {"step": step}, progress=step / 10)
            await gate.wait()  # hold the job open until the listener has caught up
            ctx.emit("cell_ready", {"cell": "front"})
            return {"ok": True}

        job = runner.create("test", "nobody")
        runner.start(job.id, work)
        for _ in range(200):
            snapshot = runner.snapshot(job.id)
            if snapshot is not None and len(snapshot.events) == 3:
                break
            await asyncio.sleep(0.01)

        stream = runner.stream(job.id)  # connects after 3 events
        replayed = [await anext(stream) for _ in range(3)]
        gate.set()
        live = [event async for event in stream]
        return [*replayed, *live]

    events = asyncio.run(scenario())

    assert all(e is not None for e in events)
    assert [e.type for e in events if e] == [
        "progress",
        "progress",
        "progress",
        "cell_ready",
        "done",
    ]
    assert [e.id for e in events if e] == [1, 2, 3, 4, 5]


def test_sse_replays_from_after_or_last_event_id(client: TestClient) -> None:
    job_id = client.post(f"/api/characters/{IDS['robo']}/lock").json()["job_id"]
    wait_for_job(client, job_id)

    everything = sse_events(client, job_id)
    from_after = sse_events(client, job_id, after=5)
    reconnect = sse_events(client, job_id, last_event_id=20)

    assert [e[0] for e in everything] == list(range(1, len(everything) + 1))
    assert from_after[0][0] == 6
    assert reconnect[0][0] == 21
    assert everything[-1][1] == from_after[-1][1] == reconnect[-1][1] == "done"


@pytest.mark.parametrize(
    ("kind", "target", "message"),
    [
        ("character_sheet", "robo", "Oops, the drawing got interrupted. Tap Lock to try again!"),
        ("background_image", "kitchen", "Oops, the painting got interrupted. Tap Paint it again!"),
    ],
)
def test_restart_marks_running_jobs_failed(
    settings: Settings, kind: str, target: str, message: str
) -> None:
    model = Character if kind == "character_sheet" else Background
    with (
        TestClient(create_app(settings)) as client,
        Session(client.app.state.engine) as session,  # type: ignore[attr-defined]
    ):
        job = Job(kind=kind, target_id=IDS[target], status="running")
        session.add(job)
        row = session.get(model, IDS[target])
        assert row is not None
        row.status = "generating"
        row.last_job_id = job.id
        session.add(row)
        session.commit()
        job_id = job.id

    # A new server process starts: that job can never finish.
    with TestClient(create_app(settings)) as client:
        job_read = client.get(f"/api/jobs/{job_id}").json()
        assert job_read["status"] == "failed"
        assert job_read["error"] == message  # places have Paint it again, characters Lock
        path = "characters" if kind == "character_sheet" else "backgrounds"
        # A place that already had a picture keeps it (a new version or its times of day were
        # being painted: Phase 8); a character sheet that didn't finish has to be locked again.
        expected = "locked" if kind == "background_image" else "failed"
        assert client.get(f"/api/{path}/{IDS[target]}").json()["status"] == expected
        last = sse_events(client, job_id)[-1]
        assert last[1] == "error" and last[2]["message"] == message
