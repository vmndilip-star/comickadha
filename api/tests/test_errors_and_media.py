from fastapi.testclient import TestClient

from tests.conftest import IDS


def test_unknown_route_uses_error_shape(client: TestClient) -> None:
    res = client.get("/api/nope")

    assert res.status_code == 404
    assert set(res.json()) == {"code", "message"}


def test_validation_errors_are_kid_friendly(client: TestClient) -> None:
    client.delete(f"/api/characters/{IDS['robo']}")

    res = client.post("/api/characters", json={"name": "A" * 30})

    assert res.status_code == 422
    assert res.json() == {
        "code": "invalid",
        "message": "The name is too long. Keep it under 24 letters.",
    }


def test_missing_character_is_not_found(client: TestClient) -> None:
    res = client.get("/api/characters/does-not-exist")

    assert res.status_code == 404
    assert res.json()["code"] == "not_found"


def test_profile(client: TestClient) -> None:
    me = client.get("/api/me").json()

    assert me["display_name"] == "Aarav"
    assert me["max_cast"] == 3


def test_place_images_are_served(client: TestClient) -> None:
    places = client.get("/api/backgrounds").json()

    assert [p["name"] for p in places] == ["Grandma's kitchen", "School garden", "Outer space"]
    assert all(p["status"] == "locked" for p in places)
    res = client.get(places[0]["thumb_url"])
    assert res.status_code == 200
    assert res.headers["content-type"] == "image/png"


def test_media_cannot_escape_storage(client: TestClient) -> None:
    for path in (
        "/media/../comickatha.db",
        "/media/%2e%2e/comickatha.db",
        "/media/.hidden",
        "/media/x//y",
    ):
        res = client.get(path)
        assert res.status_code == 404, path
        assert res.headers["content-type"].startswith("application/json")
