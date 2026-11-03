from fastapi.testclient import TestClient

from app.services import imaging
from tests.conftest import sse_events, wait_for_job


def test_locking_a_place_paints_its_image(client: TestClient) -> None:
    created = client.post(
        "/api/backgrounds",
        json={"name": "Treehouse", "description": "A wooden treehouse with a rope ladder."},
    ).json()

    res = client.post(f"/api/backgrounds/{created['id']}/lock")
    assert res.status_code == 202
    job_id = res.json()["job_id"]
    assert wait_for_job(client, job_id)["status"] == "done"

    place = client.get(f"/api/backgrounds/{created['id']}").json()
    assert place["status"] == "locked"
    assert place["version"] == 1
    assert imaging.load(client.get(place["image_url"]).content).size == (1024, 768)
    assert client.get(place["thumb_url"]).status_code == 200
    assert [kind for _, kind, _ in sse_events(client, job_id)][-2:] == ["cell_ready", "done"]


def test_an_unsafe_place_is_blocked(client: TestClient) -> None:
    created = client.post(
        "/api/backgrounds", json={"name": "Armoury", "description": "A room full of guns."}
    ).json()

    res = client.post(f"/api/backgrounds/{created['id']}/lock")

    assert res.status_code == 422
    assert res.json()["code"] == "unsafe"
    assert client.get(f"/api/backgrounds/{created['id']}").json()["status"] == "draft"
