from typing import Any

from fastapi.testclient import TestClient

from tests.conftest import IDS


def titles(client: TestClient, query: str = "") -> list[str]:
    return [c["title"] for c in client.get(f"/api/comics{query}").json()]


def test_filter_by_status(client: TestClient) -> None:
    assert titles(client, "?status=draft") == ["The Missing Mango Mystery"]
    assert sorted(titles(client, "?status=finished")) == ["Robo-Tik's First Day", "Space Picnic"]
    assert len(titles(client)) == 3


def test_title_search_is_case_insensitive(client: TestClient) -> None:
    assert titles(client, "?q=mango") == ["The Missing Mango Mystery"]
    assert titles(client, "?q=MANGO") == ["The Missing Mango Mystery"]
    assert titles(client, "?q=picnic&status=draft") == []
    assert titles(client, "?q=zzz") == []
    assert titles(client, "?q=%25") == []  # a literal % is not a wildcard


def test_sort_by_updated_puts_latest_edit_first(client: TestClient) -> None:
    assert titles(client)[0] == "The Missing Mango Mystery"

    client.patch(f"/api/comics/{IDS['space_picnic']}", json={"title": "Space Picnic 2"})

    assert titles(client, "?sort=updated")[0] == "Space Picnic 2"


def test_comic_includes_scenes_and_panels(client: TestClient) -> None:
    mango = client.get(f"/api/comics/{IDS['mango']}").json()

    assert mango["studio_step"] == 3
    assert len(mango["scenes"]) == 2
    assert len(mango["panels"]) == 6
    assert [p["status"] for p in mango["panels"]].count("ready") == 4
    assert mango["created_at"].endswith("Z") or mango["created_at"].endswith("+00:00")


def test_cast_must_come_from_active_characters(client: TestClient) -> None:
    res = client.patch(f"/api/comics/{IDS['mango']}", json={"cast_ids": ["not-a-character"]})

    assert res.status_code == 422
    assert res.json() == {"code": "invalid", "message": "Pick characters from your cast."}


def test_deleted_comic_is_hidden(client: TestClient) -> None:
    assert client.delete(f"/api/comics/{IDS['robo_day']}").status_code == 204
    assert "Robo-Tik's First Day" not in titles(client)
    assert client.get(f"/api/comics/{IDS['robo_day']}").status_code == 404


def scene(bg: str, summary: str, scene_id: str | None = None) -> dict[str, Any]:
    body: dict[str, Any] = {"background_id": bg, "character_ids": [IDS["mira"]], "summary": summary}
    if scene_id:
        body["id"] = scene_id
    return body


def test_replace_scenes_keeps_the_order(client: TestClient) -> None:
    url = f"/api/comics/{IDS['mango']}/scenes"
    first, second = client.get(f"/api/comics/{IDS['mango']}").json()["scenes"]
    new_id = "0b6c1d2e-3f40-4152-8a6b-7c8d9e0f1a2b"

    res = client.put(
        url,
        json=[
            scene(IDS["space"], "Brand new scene", new_id),
            scene(second["background_id"], "Was second", second["id"]),
            scene(first["background_id"], "Was first", first["id"]),
        ],
    )

    assert res.status_code == 200
    assert [s["summary"] for s in res.json()] == ["Brand new scene", "Was second", "Was first"]
    assert [s["idx"] for s in res.json()] == [0, 1, 2]
    stored = client.get(f"/api/comics/{IDS['mango']}").json()["scenes"]
    assert [s["id"] for s in stored] == [new_id, second["id"], first["id"]]


def test_removing_a_scene_detaches_its_panels(client: TestClient) -> None:
    first, second = client.get(f"/api/comics/{IDS['mango']}").json()["scenes"]

    res = client.put(
        f"/api/comics/{IDS['mango']}/scenes",
        json=[scene(second["background_id"], second["summary"], second["id"])],
    )

    assert res.status_code == 200
    panels = client.get(f"/api/comics/{IDS['mango']}").json()["panels"]
    assert len(panels) == 6  # panels are kept
    assert {p["scene_id"] for p in panels} == {None, second["id"]}


def test_scene_place_must_be_yours(client: TestClient) -> None:
    res = client.put(f"/api/comics/{IDS['mango']}/scenes", json=[scene("nope", "x")])

    assert res.status_code == 422
    assert res.json()["code"] == "invalid"


def test_patch_panel_bubble_and_face(client: TestClient) -> None:
    panel = client.get(f"/api/comics/{IDS['mango']}").json()["panels"][1]
    bubble = {**panel["bubbles"][0], "text": "Who ate it?!", "type": "shout"}
    faces = [{**c, "expression": "angry"} for c in panel["characters"]]

    res = client.patch(
        f"/api/panels/{panel['id']}", json={"bubbles": [bubble], "characters": faces}
    )

    assert res.status_code == 200
    again = client.get(f"/api/comics/{IDS['mango']}").json()["panels"][1]
    assert again["bubbles"][0]["text"] == "Who ate it?!"
    assert again["bubbles"][0]["type"] == "shout"
    assert {c["expression"] for c in again["characters"]} == {"angry"}


def test_patch_panel_rejects_unknown_expression(client: TestClient) -> None:
    panel = client.get(f"/api/comics/{IDS['mango']}").json()["panels"][0]
    faces = [{**panel["characters"][0], "expression": "grumpy"}]

    res = client.patch(f"/api/panels/{panel['id']}", json={"characters": faces})

    assert res.status_code == 422
    assert res.json()["message"] == "Please pick one of the choices for the expression."
