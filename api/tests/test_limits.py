"""No 3-character limit, more scenes, any panel count, panels per scene (Phase 8, step 4)."""

from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from app.services import story_planner
from app.services.story_planner import plan_parts, scene_shares, scenes_for
from tests.conftest import IDS, plan_panels
from tests.test_long_comics import ctx
from tests.test_studio import new_comic

CAST5 = ("mira", "robo")  # plus three starters, below


def starters(client: TestClient, *names: str) -> list[str]:
    chars = client.get("/api/characters").json()
    return [next(c["id"] for c in chars if c["name"] == n) for n in names]


def five_cast_comic(client: TestClient, panels: int = 6) -> tuple[str, list[str]]:
    comic_id = new_comic(client, cast=CAST5, panel_count=panels)
    cast = [IDS["mira"], IDS["robo"], *starters(client, "Leo", "Barnaby", "Nana Rose")]
    assert client.patch(f"/api/comics/{comic_id}", json={"cast_ids": cast}).status_code == 200
    return comic_id, cast


# ---- a panel holds the whole cast ---------------------------------------------------------------


def test_a_panel_can_hold_all_five_characters(client: TestClient) -> None:
    comic_id, cast = five_cast_comic(client)
    assert client.post(f"/api/studio/{comic_id}/plan-scenes", json={}).status_code == 200
    assert plan_panels(client, comic_id).status_code == 200
    panel = client.get(f"/api/comics/{comic_id}").json()["panels"][0]
    spots = ["far_left", "left", "center", "right", "far_right"]
    everyone = [
        {
            "id": cid,
            "sheet_version": 1,
            "pose": "front",
            "expression": "happy",
            "position": spot,
            "scale": 1.0,
        }
        for cid, spot in zip(cast, spots, strict=True)
    ]
    res = client.patch(f"/api/panels/{panel['id']}", json={"characters": everyone})
    assert res.status_code == 200, res.json()
    layers = [layer for layer in res.json()["stage"]["layers"] if layer["kind"] == "character"]
    assert len(layers) == 5
    tops = sorted({round(layer["box"][1], 3) for layer in layers})
    assert len(tops) >= 2  # two rows


def test_the_planner_may_put_everyone_in_a_panel() -> None:
    story = ctx(8)
    one = replace(
        story, scenes=[replace(story.scenes[0], character_ids=tuple(m.id for m in story.cast))]
    )
    one = replace(one, panel_count=4)
    plan = story_planner.offline_panels(one)
    assert max(len(p.characters) for p in plan.panels) == len(story.cast)  # the scene's big panels
    assert story_planner.check_panels(plan, one) == []
    schema = story_planner.panels_schema(one)["properties"]["panels"]["items"]["properties"]
    assert schema["characters"]["items"]["properties"]["position"]["enum"] == [
        "far_left",
        "left",
        "center",
        "right",
        "far_right",
    ]


def test_the_prompts_no_longer_cap_a_panel_at_three() -> None:
    from app.prompts import template

    panels, scenes = template("planner_panels"), template("planner_scenes")
    assert "1 to 3" not in panels and "at most 3" not in scenes
    assert "A panel can show all of the scene's characters" in panels


# ---- scenes and panel counts --------------------------------------------------------------------


def test_a_comic_can_have_twelve_scenes(client: TestClient) -> None:
    comic_id = new_comic(client, panel_count=20)
    scene = {"background_id": IDS["garden"], "character_ids": [IDS["mira"]], "summary": "Hi"}
    assert client.put(f"/api/comics/{comic_id}/scenes", json=[scene] * 12).status_code == 200
    too_many = client.put(f"/api/comics/{comic_id}/scenes", json=[scene] * 13)
    assert too_many.status_code == 422 and "12" in too_many.json()["message"]


@pytest.mark.parametrize(
    ("count", "ok"),
    [(3, False), (4, True), (13, True), (30, True), (31, True), (200, True), (201, False)],
)
def test_any_panel_count_from_4_to_200(client: TestClient, count: int, ok: bool) -> None:
    comic_id = new_comic(client)
    res = client.patch(f"/api/comics/{comic_id}", json={"panel_count": count})
    assert (res.status_code == 200) is ok
    if ok:
        assert res.json()["panel_count"] == count


def test_odd_panel_counts_plan_exactly_that_many(client: TestClient) -> None:
    comic_id = new_comic(client, panel_count=13)
    assert client.post(f"/api/studio/{comic_id}/plan-scenes", json={}).status_code == 200
    assert plan_panels(client, comic_id).status_code == 200
    assert len(client.get(f"/api/comics/{comic_id}").json()["panels"]) == 13
    assert scenes_for(13) == scenes_for(10) and scenes_for(29) == scenes_for(25)


# ---- panels per scene ---------------------------------------------------------------------------


def test_scene_shares_respect_the_kids_numbers() -> None:
    assert scene_shares(10, 3) == [4, 3, 3]
    assert scene_shares(10, 3, [6, None, None]) == [6, 2, 2]
    assert scene_shares(10, 3, [5, 3, 2]) == [5, 3, 2]
    story = ctx(10)
    story.scenes[0] = replace(story.scenes[0], panel_count=6)
    parts = plan_parts(story)
    assert sum(p.count for p in parts if p.scene.id == story.scenes[0].id) == 6
    assert sum(p.count for p in parts) == 10


def test_setting_every_scenes_panels_sets_the_comics_length(client: TestClient) -> None:
    comic_id = new_comic(client, panel_count=6)
    scenes = [
        {
            "background_id": IDS["garden"],
            "character_ids": [IDS["mira"]],
            "summary": "One",
            "panel_count": 5,
        },
        {
            "background_id": IDS["kitchen"],
            "character_ids": [IDS["raju"]],
            "summary": "Two",
            "panel_count": 4,
        },
    ]
    assert client.put(f"/api/comics/{comic_id}/scenes", json=scenes).status_code == 200
    assert client.get(f"/api/comics/{comic_id}").json()["panel_count"] == 9
    assert plan_panels(client, comic_id).status_code == 200
    panels = client.get(f"/api/comics/{comic_id}").json()
    by_scene = [
        sum(1 for p in panels["panels"] if p["scene_id"] == s["id"]) for s in panels["scenes"]
    ]
    assert by_scene == [5, 4]
    too_long = [{**s, "panel_count": 110} for s in scenes]  # 220: more than MAX_PANELS (200)
    res = client.put(f"/api/comics/{comic_id}/scenes", json=too_long)
    assert res.status_code == 422 and "220 panels" in res.json()["message"]


def test_some_scenes_with_numbers_must_leave_room_for_the_rest(client: TestClient) -> None:
    comic_id = new_comic(client, panel_count=6)
    scenes = [
        {
            "background_id": IDS["garden"],
            "character_ids": [IDS["mira"]],
            "summary": "One",
            "panel_count": 6,
        },
        {"background_id": IDS["kitchen"], "character_ids": [IDS["raju"]], "summary": "Two"},
    ]
    assert client.put(f"/api/comics/{comic_id}/scenes", json=scenes).status_code == 200
    res = plan_panels(client, comic_id)
    assert res.status_code == 422 and "ask for 6 panels" in res.body["message"]
