from fastapi.testclient import TestClient

from tests.conftest import IDS, wait_for_job


def test_fourth_character_returns_cast_full(client: TestClient) -> None:
    assert len(client.get("/api/characters").json()) == 3

    res = client.post("/api/characters", json={"name": "Zara"})

    assert res.status_code == 409
    body = res.json()
    assert body["code"] == "cast_full"
    assert "3 characters" in body["message"]


def test_deleting_a_character_frees_a_slot(client: TestClient) -> None:
    assert client.delete(f"/api/characters/{IDS['robo']}").status_code == 204

    listed = client.get("/api/characters").json()
    assert [c["name"] for c in listed] == ["Mira", "Raju"]
    # Still resolves by id (for comics that use it), flagged as deleted.
    assert client.get(f"/api/characters/{IDS['robo']}").json()["deleted"] is True

    res = client.post("/api/characters", json={"name": "Zara"})
    assert res.status_code == 201
    assert res.json()["status"] == "draft"
    assert len(client.get("/api/characters").json()) == 3


def test_patch_locked_character_returns_409(client: TestClient) -> None:
    res = client.patch(f"/api/characters/{IDS['mira']}", json={"name": "Mia"})

    assert res.status_code == 409
    assert res.json()["code"] == "locked"
    assert "Unlock Mira" in res.json()["message"]


def test_patch_locked_background_returns_409(client: TestClient) -> None:
    res = client.patch(f"/api/backgrounds/{IDS['kitchen']}", json={"name": "Cafe"})

    assert res.status_code == 409
    assert res.json()["code"] == "locked"


def test_patch_draft_character_merges_spec_and_persists(client: TestClient) -> None:
    res = client.patch(
        f"/api/characters/{IDS['robo']}",
        json={"name": "Robo-Tok", "spec": {"catchphrase": "Bleep!"}},
    )
    assert res.status_code == 200

    again = client.get(f"/api/characters/{IDS['robo']}").json()
    assert again["name"] == "Robo-Tok"
    assert again["spec"]["catchphrase"] == "Bleep!"
    assert again["spec"]["outfit"] == "Shiny blue panels with an orange antenna"  # untouched


def test_unlock_then_edit_then_lock(client: TestClient) -> None:
    path = f"/api/characters/{IDS['raju']}"
    assert client.post(f"{path}/unlock").json()["status"] == "draft"
    assert client.patch(path, json={"role": "hero"}).status_code == 200
    job = client.post(f"{path}/lock")
    assert job.status_code == 202
    assert wait_for_job(client, job.json()["job_id"])["status"] == "done"
    assert client.get(path).json()["status"] == "locked"
    assert client.patch(path, json={"role": "friend"}).status_code == 409


def test_locked_characters_have_a_placeholder_manifest(client: TestClient) -> None:
    manifest = client.get(f"/api/characters/{IDS['mira']}/manifest").json()

    assert manifest["locked"] is True
    assert manifest["body_sheet"]["grid"] == [4, 4]
    assert manifest["body_sheet"]["cells"]["front"] == [0, 0]
    assert manifest["body_sheet"]["cells"]["celebrate"] == [3, 3]
    assert manifest["face_sheet"]["grid"] == [2, 3]
    assert len(manifest["face_sheet"]["cells"]) == 6

    sheet = client.get(manifest["body_sheet"]["url"])
    assert sheet.status_code == 200
    assert sheet.headers["content-type"] == "image/png"


def test_draft_character_has_no_manifest(client: TestClient) -> None:
    res = client.get(f"/api/characters/{IDS['robo']}/manifest")

    assert res.status_code == 404
    assert res.json()["code"] == "no_manifest"
