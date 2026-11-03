"""Deleting a character or place must never change an existing comic."""

from fastapi.testclient import TestClient

from tests.conftest import IDS


def test_deleted_character_still_resolves_for_its_comics(client: TestClient) -> None:
    raju = IDS["raju"]
    assert client.delete(f"/api/characters/{raju}").status_code == 204

    # Hidden from the cast list...
    assert raju not in [c["id"] for c in client.get("/api/characters").json()]
    # ...but the comic still carries it, flagged as deleted.
    comic = client.get(f"/api/comics/{IDS['mango']}").json()
    used = {c["id"]: c for c in comic["characters"]}
    assert used[raju]["name"] == "Raju"
    assert used[raju]["deleted"] is True
    assert used[IDS["mira"]]["deleted"] is False
    # Panels are unchanged and the character still resolves by id.
    assert any(pc["id"] == raju for p in comic["panels"] for pc in p["characters"])
    direct = client.get(f"/api/characters/{raju}")
    assert direct.status_code == 200
    assert direct.json()["deleted"] is True


def test_deleted_character_is_read_only(client: TestClient) -> None:
    client.delete(f"/api/characters/{IDS['robo']}")

    assert client.patch(f"/api/characters/{IDS['robo']}", json={"name": "X"}).status_code == 404
    assert client.delete(f"/api/characters/{IDS['robo']}").status_code == 404


def test_comic_keeps_a_deleted_cast_member_but_cannot_add_one(client: TestClient) -> None:
    client.delete(f"/api/characters/{IDS['raju']}")
    mango = client.get(f"/api/comics/{IDS['mango']}").json()

    # Autosaving the comic with its existing cast (which includes Raju) still works.
    keep = client.patch(f"/api/comics/{IDS['mango']}", json={"cast_ids": mango["cast_ids"]})
    assert keep.status_code == 200

    # A comic that never had Raju cannot add him now.
    picnic = client.get(f"/api/comics/{IDS['space_picnic']}").json()
    client.patch(f"/api/comics/{IDS['space_picnic']}", json={"cast_ids": [IDS["mira"]]})
    add = client.patch(
        f"/api/comics/{IDS['space_picnic']}", json={"cast_ids": [IDS["mira"], IDS["raju"]]}
    )
    assert add.status_code == 422
    assert picnic["cast_ids"]  # sanity: the seed comic had a cast


def test_deleted_place_still_resolves_for_its_comics(client: TestClient) -> None:
    kitchen = IDS["kitchen"]
    assert client.delete(f"/api/backgrounds/{kitchen}").status_code == 204

    assert kitchen not in [b["id"] for b in client.get("/api/backgrounds").json()]
    comic = client.get(f"/api/comics/{IDS['mango']}").json()
    used = {b["id"]: b for b in comic["backgrounds"]}
    assert used[kitchen]["deleted"] is True
    assert used[kitchen]["name"] == "Grandma's kitchen"
    assert client.get(f"/api/backgrounds/{kitchen}").json()["deleted"] is True
