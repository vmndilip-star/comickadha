from typing import Any

from fastapi.testclient import TestClient
from PIL import Image
from sqlmodel import Session, select

from app.models import ModerationLog
from app.providers.mock import MockImageProvider
from app.schemas.common import EXPRESSIONS, POSES
from app.schemas.manifest import CharacterManifest
from app.services import imaging
from app.services.builder_sheet import BuilderSheets
from app.services.character_sheet import ImageSheets
from tests.conftest import IDS, app_state, sse_events, wait_for_job


def use_image_sheets(client: TestClient, provider: Any) -> None:
    """SHEET_PROVIDER=image with this image provider (the default is the builder)."""
    app_state(client).sheet_provider = ImageSheets(provider)


class FlakyProvider:
    """Returns a blank (all-magenta) image for the batch containing `when`, `fail_times` times."""

    name = "flaky"

    def __init__(self, fail_times: int, when: str = "three_quarter_left") -> None:
        self.inner = MockImageProvider()
        self.fail_times = fail_times
        self.when = when
        self.calls = 0

    def generate(
        self,
        prompt: str,
        size: tuple[int, int],
        seed: int,
        reference_images: list[bytes] | None = None,
    ) -> bytes:
        self.calls += 1
        if self.when in prompt and self.fail_times > 0:
            self.fail_times -= 1
            return imaging.to_png(Image.new("RGB", size, (255, 0, 255)))
        return self.inner.generate(prompt, size, seed, reference_images)


def lock(client: TestClient, character_id: str) -> str:
    res = client.post(f"/api/characters/{character_id}/lock")
    assert res.status_code == 202, res.json()
    job_id: str = res.json()["job_id"]
    return job_id


def character(client: TestClient, key: str) -> dict[str, Any]:
    data: dict[str, Any] = client.get(f"/api/characters/{IDS[key]}").json()
    return data


def test_lock_builds_a_full_sheet_with_the_image_pipeline(client: TestClient) -> None:
    use_image_sheets(client, MockImageProvider())
    job_id = lock(client, IDS["robo"])
    assert character(client, "robo")["status"] in ("generating", "locked")

    assert wait_for_job(client, job_id)["status"] == "done"

    robo = character(client, "robo")
    assert robo["status"] == "locked"
    assert robo["sheet_version"] == 1
    assert robo["last_job_id"] == job_id
    manifest = CharacterManifest.model_validate(robo["manifest"])
    body, face = manifest.body_sheet, manifest.face_sheet
    assert set(body.cells) == set(body.cell_urls) == set(body.heads) == set(POSES)
    assert set(face.cells) == set(face.cell_urls) == set(EXPRESSIONS)
    assert body.cells["celebrate"] == (3, 3)
    assert face.cells["laughing"] == (1, 2)
    assert all(head.source == "exact" for head in body.heads.values())
    assert "back" not in body.face_visible and "front" in body.face_visible

    cell = imaging.load(client.get(body.cell_urls["wave"]).content)
    assert cell.size == (256, 256)
    assert cell.mode == "RGBA"
    assert cell.getchannel("A").getpixel((0, 0)) == 0  # keyed to transparency

    events = sse_events(client, job_id)
    cells = [data for _, kind, data in events if kind == "cell_ready"]
    assert len(cells) == 16 + 6
    assert cells[0]["cell"] == "front"  # the front view comes first
    assert events[-1][1] == "done"


def test_a_failed_batch_is_retried_once(client: TestClient) -> None:
    flaky = FlakyProvider(fail_times=1)
    use_image_sheets(client, flaky)

    job = wait_for_job(client, lock(client, IDS["robo"]))

    assert job["status"] == "done"
    assert flaky.calls == 1 + 4 + 1 + 1  # front, 4 pose batches, faces, plus one retry


def test_a_batch_that_fails_twice_fails_the_job_and_can_be_retried(client: TestClient) -> None:
    use_image_sheets(client, FlakyProvider(fail_times=2))

    job_id = lock(client, IDS["robo"])
    job = wait_for_job(client, job_id)

    assert job["status"] == "failed"
    assert "Tap Lock to try again" in job["error"]
    assert character(client, "robo")["status"] == "failed"
    assert sse_events(client, job_id)[-1][1] == "error"

    use_image_sheets(client, MockImageProvider())
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


def test_head_position_can_be_nudged(client: TestClient) -> None:
    url = f"/api/characters/{IDS['mira']}/heads/front"

    res = client.patch(url, json={"dx": 0.02, "dy": -0.01, "scale": 1.1})

    assert res.status_code == 200
    offset = res.json()["manifest"]["body_sheet"]["heads"]["front"]["offset"]
    assert offset == {"dx": 0.02, "dy": -0.01, "scale": 1.1}
    stored = client.get(f"/api/characters/{IDS['mira']}/manifest?version=1")  # the file, not the DB
    assert stored.json()["body_sheet"]["heads"]["front"]["offset"]["scale"] == 1.1
    assert client.patch(url, json={"scale": 5}).status_code == 422
    assert client.patch(url.replace("front", "moonwalk"), json={"dx": 0}).status_code == 422


def test_a_character_being_drawn_cannot_change(client: TestClient) -> None:
    app_state(client).sheet_provider = BuilderSheets(reveal_seconds=0.03)  # about 0.7 s in all
    job_id = lock(client, IDS["robo"])
    path = f"/api/characters/{IDS['robo']}"

    assert client.post(f"{path}/unlock").json()["code"] == "busy"
    assert client.patch(path, json={"name": "X"}).json()["code"] == "busy"
    assert client.delete(path).status_code == 409
    assert lock(client, IDS["robo"]) == job_id  # locking again reconnects to the same job

    assert wait_for_job(client, job_id)["status"] == "done"
