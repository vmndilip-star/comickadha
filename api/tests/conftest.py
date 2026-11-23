import json
import shutil
import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.seed import GARDEN, KITCHEN, MANGO, MIRA, RAJU, ROBO, ROBO_DAY, SPACE, SPACE_PICNIC
from app.starters import STARTER_IDS

# Re-exported so tests read naturally.
IDS = {
    "mira": MIRA,
    "raju": RAJU,
    "robo": ROBO,
    "kitchen": KITCHEN,
    "garden": GARDEN,
    "space": SPACE,
    "mango": MANGO,
    "robo_day": ROBO_DAY,
    "space_picnic": SPACE_PICNIC,
}


def make_settings(storage: Path, **overrides: Any) -> Settings:
    """Offline providers, pinned: a developer's .env (say LLM_PROVIDER=meta) must not leak in."""
    values: dict[str, Any] = {
        "storage_dir": storage,
        "database_url": "",
        "seed_on_startup": True,
        "mock_delay_seconds": 0,
        "llm_provider": "mock",
        "image_provider": "mock",
        "builder_reveal_seconds": 0,
        "panel_reveal_seconds": 0,
        "plan_reveal_seconds": 0,
        "recheck_seconds": 0,
    }
    return Settings(_env_file=None, **(values | overrides))


@pytest.fixture(scope="session")
def seeded_storage(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Seeds once (drawing the demo sheets takes a moment); each test gets a copy."""
    storage = tmp_path_factory.mktemp("seeded") / "storage"
    with TestClient(create_app(make_settings(storage))):
        pass
    return storage


# What each test's copy keeps of a starter character's sheet: the API reads only the manifest
# (comics draw every character from its frozen spec, never from sheet images).
STARTER_FILES = {"manifest.json", "thumb.png"}


def copy_storage(source: Path, target: Path) -> None:
    """Copies the seeded database and media, but only the manifest and thumbnail of each starter
    character's sheet: their 22 cells (12 x 26 files) would make every test's copy 10 times slower.
    Starters can't change, and test_starters checks that a fresh install draws every cell."""

    def ignore(folder: str, names: list[str]) -> list[str]:
        parts = Path(folder).relative_to(source).parts
        if len(parts) == 4 and parts[:2] == ("media", "characters") and parts[2] in STARTER_IDS:
            return [name for name in names if name not in STARTER_FILES]  # media/characters/<id>/v1
        return []

    shutil.copytree(source, target, ignore=ignore)


@pytest.fixture
def settings(tmp_path: Path, seeded_storage: Path) -> Settings:
    """A fresh copy of the seeded SQLite file and media folder per test."""
    storage = tmp_path / "storage"
    copy_storage(seeded_storage, storage)
    return make_settings(storage)


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    with TestClient(create_app(settings)) as c:
        yield c


def own_cast(client: TestClient) -> list[dict[str, Any]]:
    """The kid's own characters from GET /api/characters (the starter characters left out)."""
    return [c for c in client.get("/api/characters").json() if not c["starter"]]


def app_state(client: TestClient) -> Any:
    return client.app.state  # type: ignore[attr-defined]


def wait_for_job(client: TestClient, job_id: str, timeout: float = 30.0) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        job: dict[str, Any] = client.get(f"/api/jobs/{job_id}").json()
        if job["status"] in ("done", "failed"):
            return job
        time.sleep(0.05)
    raise AssertionError(f"job {job_id} did not finish in {timeout}s")


def sse_events(
    client: TestClient, job_id: str, *, after: int | None = None, last_event_id: int | None = None
) -> list[tuple[int, str, dict[str, Any]]]:
    """Reads a finished job's event stream as (id, type, data) tuples."""
    url = f"/api/jobs/{job_id}/events" + (f"?after={after}" if after is not None else "")
    headers = {"Last-Event-ID": str(last_event_id)} if last_event_id is not None else {}
    events: list[tuple[int, str, dict[str, Any]]] = []
    current: dict[str, Any] = {}
    with client.stream("GET", url, headers=headers) as res:
        assert res.headers["content-type"].startswith("text/event-stream")
        for line in res.iter_lines():
            if line.startswith("id: "):
                current["id"] = int(line[4:])
            elif line.startswith("event: "):
                current["type"] = line[7:]
            elif line.startswith("data: "):
                current["data"] = json.loads(line[6:])
            elif line == "" and current:
                events.append((current["id"], current["type"], current["data"]))
                current = {}
    return events


@dataclass
class Planned:
    """POST plan-panels as the tests knew it before it became a job (Phase 7 part C): the error
    response if the plan didn't start, else a 200 with the finished job's summary and the panels
    as saved. `events` is the job's whole event stream."""

    status_code: int
    body: dict[str, Any]
    job_id: str | None = None
    events: list[tuple[int, str, dict[str, Any]]] = field(default_factory=list)

    def json(self) -> dict[str, Any]:
        return self.body


def plan_panels(client: TestClient, comic_id: str, start_over: bool = False) -> Planned:
    """Starts the panel plan job and waits for it."""
    res = client.post(f"/api/studio/{comic_id}/plan-panels", json={"start_over": start_over})
    if res.status_code != 202:
        return Planned(res.status_code, res.json())
    job_id: str = res.json()["job_id"]
    wait_for_job(client, job_id)
    events = sse_events(client, job_id)
    _id, kind, data = events[-1]
    if kind != "done":
        return Planned(500, {"code": "job_failed", "message": data.get("message")}, job_id, events)
    panels = client.get(f"/api/comics/{comic_id}").json()["panels"]
    return Planned(200, {**data, "panels": panels}, job_id, events)
