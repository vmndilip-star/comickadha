"""The Lock job around the sheet provider: versions, safety, failures, and no edits while drawing.
(What the builder draws is tested in test_builder_sheet.py.)"""

from typing import Any

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import ModerationLog
from app.schemas.manifest import CharacterManifest
from app.services.builder_sheet import BuilderSheets
from app.services.character_sheet import Emit, SheetSpec
from app.services.jobs import FAILED_MESSAGE
from app.services.storage import Storage
from tests.conftest import IDS, app_state, sse_events, wait_for_job


class BrokenSheets:
    """A sheet provider that fails, as a real one might."""

    name = "broken"

    def build(self, spec: SheetSpec, storage: Storage, emit: Emit) -> dict[str, Any]:
        raise RuntimeError("the drawing broke")


def lock(client: TestClient, character_id: str) -> str:
    res = client.post(f"/api/characters/{character_id}/lock")
    assert res.status_code == 202, res.json()
    job_id: str = res.json()["job_id"]
    return job_id


def character(client: TestClient, key: str) -> dict[str, Any]:
    data: dict[str, Any] = client.get(f"/api/characters/{IDS[key]}").json()
    return data


def test_a_failed_sheet_fails_the_job_and_lock_works_again(client: TestClient) -> None:
    app_state(client).sheet_provider = BrokenSheets()

    job_id = lock(client, IDS["robo"])
    job = wait_for_job(client, job_id)

    assert (job["status"], job["error"]) == ("failed", FAILED_MESSAGE)
    assert character(client, "robo")["status"] == "failed"
    assert sse_events(client, job_id)[-1][1] == "error"

    app_state(client).sheet_provider = BuilderSheets()
    assert wait_for_job(client, lock(client, IDS["robo"]))["status"] == "done"
    assert character(client, "robo")["status"] == "locked"


def test_relock_makes_a_new_version_and_keeps_the_old_one(client: TestClient) -> None:
    v1 = CharacterManifest.model_validate(character(client, "mira")["manifest"])
    assert v1.version == 1

    client.post(f"/api/characters/{IDS['mira']}/unlock")
    spec = character(client, "mira")["spec"]
    spec["parts"]["top"] = "superhero"
    spec["extras"] = ["cape"]
    assert client.patch(f"/api/characters/{IDS['mira']}", json={"spec": spec}).status_code == 200
    assert wait_for_job(client, lock(client, IDS["mira"]))["status"] == "done"

    mira = character(client, "mira")
    assert mira["sheet_version"] == 2
    assert "/v2/" in mira["manifest"]["body_sheet"]["url"]
    assert mira["manifest"]["spec"]["extras"] == ["cape"]
    old = client.get(f"/api/characters/{IDS['mira']}/manifest?version=1")
    assert old.status_code == 200
    assert old.json()["spec"]["parts"]["top"] == "raincoat"
    assert old.json()["spec"]["extras"] == ["backpack"]
    assert client.get(v1.body_sheet.cell_urls["front"]).status_code == 200

    # The comic still points at the version it was drawn with.
    mango = client.get(f"/api/comics/{IDS['mango']}").json()
    versions = {
        pc["sheet_version"]
        for p in mango["panels"]
        for pc in p["characters"]
        if pc["id"] == IDS["mira"]
    }
    assert versions == {1}


def test_an_unsafe_catchphrase_is_blocked_before_drawing(client: TestClient) -> None:
    spec = character(client, "robo")["spec"]
    spec["personality"]["catchphrase"] = "I love beer!"
    assert client.patch(f"/api/characters/{IDS['robo']}", json={"spec": spec}).status_code == 200

    res = client.post(f"/api/characters/{IDS['robo']}/lock")

    assert res.status_code == 422
    assert res.json()["code"] == "unsafe"
    assert "catchphrase" in res.json()["message"]
    assert character(client, "robo")["status"] == "draft"
    with Session(app_state(client).engine) as session:
        logs = list(session.exec(select(ModerationLog).where(ModerationLog.verdict == "block")))
    assert [log.categories for log in logs] == [["drugs"]]


def test_a_character_being_drawn_cannot_change(client: TestClient) -> None:
    app_state(client).sheet_provider = BuilderSheets(reveal_seconds=0.03)  # about 0.7 s in all
    job_id = lock(client, IDS["robo"])
    path = f"/api/characters/{IDS['robo']}"

    assert client.post(f"{path}/unlock").json()["code"] == "busy"
    assert client.patch(path, json={"name": "X"}).json()["code"] == "busy"
    assert client.delete(path).status_code == 409
    assert lock(client, IDS["robo"]) == job_id  # locking again reconnects to the same job

    assert wait_for_job(client, job_id)["status"] == "done"
