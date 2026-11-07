import json
import shutil
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.seed import GARDEN, KITCHEN, MANGO, MIRA, RAJU, ROBO, ROBO_DAY, SPACE, SPACE_PICNIC

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
        "sheet_provider": "builder",
        "builder_reveal_seconds": 0,
    }
    return Settings(_env_file=None, **(values | overrides))


@pytest.fixture(scope="session")
def seeded_storage(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Seeds once (drawing the demo sheets takes a moment); each test gets a copy."""
    storage = tmp_path_factory.mktemp("seeded") / "storage"
    with TestClient(create_app(make_settings(storage))):
        pass
    return storage


@pytest.fixture
def settings(tmp_path: Path, seeded_storage: Path) -> Settings:
    """A fresh copy of the seeded SQLite file and media folder per test."""
    storage = tmp_path / "storage"
    shutil.copytree(seeded_storage, storage)
    return make_settings(storage)


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    with TestClient(create_app(settings)) as c:
        yield c


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
