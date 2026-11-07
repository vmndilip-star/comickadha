"""Story Studio: the planner (offline and Meta), its checks, retries, fallback and re-planning."""

from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, col, select

from app.avatar.catalog import load_catalog
from app.models import Comic, Panel, Scene
from app.schemas.studio import (
    PanelPlan,
    PlannedBubble,
    PlannedCharacter,
    PlannedPanel,
    PlannedScene,
    ScenePlan,
)
from app.services.ai_guard import META_LABEL, OFFLINE_LABEL
from app.services.bubbles import layout
from app.services.story_planner import (
    CastMember,
    Place,
    SceneInfo,
    StoryContext,
    check_panels,
    check_scenes,
    offline_panels,
    offline_scenes,
)
from tests.conftest import IDS, app_state
from tests.fakes import FakeMeta, schema_of, server_error, use_meta, user_text

CAT = load_catalog()
SYNOPSIS = (
    "The last mango in Grandma's kitchen disappears before the festival. Mira and Raju follow "
    "sticky footprints to the school garden. They laughed when they found the monkeys."
)
CAST = [
    CastMember("m", "Mira", 1, "Adventure is my middle name!", ("brave",)),
    CastMember("r", "Raju", 1, "Snack break? Snack break!"),
    CastMember("t", "Robo-Tik", 2, "Beep boop, I can explain!"),
]
PLACES = [Place("k", "Grandma's kitchen"), Place("g", "School garden"), Place("s", "Outer space")]


def context(panels: int = 6, cast: int = 3, synopsis: str = SYNOPSIS) -> StoryContext:
    return StoryContext("The Missing Mango", synopsis, "mystery", panels, CAST[:cast], PLACES)


def with_scenes(ctx: StoryContext) -> StoryContext:
    plan = offline_scenes(ctx)
    ctx.scenes = [
        SceneInfo(f"scene-{i}", s.background_id, tuple(s.character_ids), s.summary)
        for i, s in enumerate(plan.scenes)
    ]
    return ctx


# ---- the offline planner ---------------------------------------------------------------------


@pytest.mark.parametrize("panels", [4, 6, 8])
@pytest.mark.parametrize("cast", [1, 2, 3])
@pytest.mark.parametrize("synopsis", [SYNOPSIS, "A robot bakes a cake.", "Mira finds a dragon"])
def test_offline_plans_always_pass_schema_and_semantic_checks(
    panels: int, cast: int, synopsis: str
) -> None:
    ctx = context(panels, cast, synopsis)
    scenes = offline_scenes(ctx)
    assert ScenePlan.model_validate(scenes.model_dump()) == scenes
    assert check_scenes(scenes, ctx) == []
    plan = offline_panels(with_scenes(ctx))
    assert PanelPlan.model_validate(plan.model_dump()) == plan
    assert check_panels(plan, ctx) == []
    assert len(plan.panels) == panels
    assert plan.panels[0].bubbles[0].type == "narrator"  # the first panel sets the scene
    assert plan.panels[-1].bubbles[0].type == "narrator"  # the last one resolves it


def test_offline_planner_picks_poses_and_faces_that_suit_the_beat() -> None:
    plan = offline_panels(with_scenes(context()))
    by_beat = {p.beat: p for p in plan.panels}
    sad = next(p for b, p in by_beat.items() if "disappears" in b)
    found = next(p for b, p in by_beat.items() if "found" in b or "footprints" in b)
    assert sad.characters[0].expression == "sad"
    assert {c.expression for c in found.characters} & {"surprised", "happy", "laughing"}


def test_offline_planner_is_deterministic() -> None:
    a = offline_panels(with_scenes(context()))
    b = offline_panels(with_scenes(context()))
    assert a == b


# ---- semantic checks ------------------------------------------------------------------------


def valid_panel_plan() -> tuple[PanelPlan, StoryContext]:
    ctx = with_scenes(context())
    return offline_panels(ctx), ctx


def bad(panel: PlannedPanel, **changes: Any) -> PlannedPanel:
    return panel.model_copy(update=changes)


def test_validator_catches_an_unknown_pose_or_expression() -> None:
    plan, ctx = valid_panel_plan()
    # Built without validation, as a model might answer.
    values = {"id": "m", "pose": "moonwalk", "expression": "smug", "position": "left"}
    odd = PlannedCharacter.model_construct(**values)  # type: ignore[arg-type]
    plan.panels[1] = bad(plan.panels[1], characters=[odd])
    problems = check_panels(plan, ctx)
    assert any("moonwalk" in p for p in problems) and any("smug" in p for p in problems)


def test_validator_catches_an_unlocked_character_and_place() -> None:
    plan, ctx = valid_panel_plan()
    stranger = PlannedCharacter(id="ghost", pose="front", expression="happy", position="left")
    plan.panels[2] = bad(plan.panels[2], characters=[stranger], bubbles=[])
    assert any("ghost is not a locked character" in p for p in check_panels(plan, ctx))

    scenes = ScenePlan(
        scenes=[
            PlannedScene(background_id="moon", character_ids=["m", "r", "t"], summary="Hi."),
            PlannedScene(background_id="k", character_ids=["m"], summary="Bye."),
        ]
    )
    assert any("locked places" in p for p in check_scenes(scenes, context()))


def test_validator_catches_the_wrong_panel_count() -> None:
    plan, ctx = valid_panel_plan()
    plan.panels.pop()
    assert any("exactly 6 panels" in p for p in check_panels(plan, ctx))


def test_validator_catches_position_collisions() -> None:
    plan, ctx = valid_panel_plan()
    twins = [
        PlannedCharacter(id="m", pose="front", expression="happy", position="left"),
        PlannedCharacter(id="r", pose="front", expression="happy", position="left"),
    ]
    plan.panels[1] = bad(plan.panels[1], characters=twins, bubbles=[])
    assert any("same position" in p for p in check_panels(plan, ctx))


def test_validator_catches_long_bubbles_and_speakers_not_in_the_panel() -> None:
    plan, ctx = valid_panel_plan()
    lonely = [PlannedCharacter(id="m", pose="front", expression="happy", position="center")]
    long_text = "one two three four five six seven eight nine ten eleven twelve thirteen"
    plan.panels[1] = bad(
        plan.panels[1],
        characters=lonely,
        bubbles=[
            PlannedBubble(speaker="m", type="talk", text=long_text),
            PlannedBubble(speaker="r", type="talk", text="Hi!"),
        ],
    )
    problems = check_panels(plan, ctx)
    assert any("12 words" in p for p in problems)
    assert any("speaker r is not in this panel" in p for p in problems)


def test_scenes_must_include_every_cast_member() -> None:
    scenes = ScenePlan(
        scenes=[
            PlannedScene(background_id="k", character_ids=["m"], summary="Hi."),
            PlannedScene(background_id="g", character_ids=["m", "r"], summary="Bye."),
        ]
    )
    assert any("Robo-Tik" in p for p in check_scenes(scenes, context()))


# ---- bubble layout -------------------------------------------------------------------------


def test_bubbles_are_laid_out_over_their_speakers() -> None:
    characters = [{"id": "m", "position": "left"}, {"id": "r", "position": "right"}]
    bubbles = [
        {"id": "1", "speaker": "narrator", "type": "narrator", "text": "Meanwhile..."},
        {"id": "2", "speaker": "r", "type": "talk", "text": "Look what I found!"},
    ]
    narrator, speech = layout(bubbles, characters)
    assert narrator["tail"] is None and narrator["box"][1] < speech["box"][1]
    x, y, w, h = speech["box"]
    assert x >= 0 and x + w <= 1 and y >= 0 and y + h <= 1
    assert speech["tail"][0] == 0.78  # points at the speaker on the right
    assert x + w / 2 > 0.5
    assert bubbles[1].get("box") is None  # the input is not changed


# ---- the endpoints, offline -------------------------------------------------------------------


def new_comic(
    client: TestClient,
    synopsis: str = SYNOPSIS,
    cast: tuple[str, ...] = ("mira", "raju"),
    panel_count: int = 6,
) -> str:
    comic_id: str = client.post(
        "/api/comics", json={"title": "Mango", "synopsis": synopsis}
    ).json()["id"]
    body = {"cast_ids": [IDS[c] for c in cast], "panel_count": panel_count, "mood": "mystery"}
    assert client.patch(f"/api/comics/{comic_id}", json=body).status_code == 200
    return comic_id


def plan(client: TestClient, comic_id: str, what: str, start_over: bool = False) -> Any:
    return client.post(f"/api/studio/{comic_id}/plan-{what}", json={"start_over": start_over})


def rows(client: TestClient, comic_id: str) -> tuple[list[dict[str, Any]], ...]:
    with Session(app_state(client).engine) as session:
        scenes = session.exec(
            select(Scene).where(Scene.comic_id == comic_id).order_by(col(Scene.idx))
        )
        panels = session.exec(
            select(Panel).where(Panel.comic_id == comic_id).order_by(col(Panel.idx))
        )
        comic = session.get(Comic, comic_id)
        assert comic is not None
        return (
            [s.model_dump() for s in scenes],
            [p.model_dump() for p in panels],
            [{"step": comic.studio_step}],
        )


def test_plan_scenes_then_panels_offline(client: TestClient) -> None:
    comic_id = new_comic(client, cast=("mira", "raju", "robo"))

    res = plan(client, comic_id, "scenes")

    assert res.status_code == 200, res.json()
    scenes = res.json()
    assert (scenes["source"], scenes["fallback"], scenes["label"]) == ("mock", False, OFFLINE_LABEL)
    assert scenes["skipped"] == ["Robo-Tik"]  # not locked, so left out with a note
    assert len(scenes["scenes"]) == 3
    cast_in_scenes = {cid for s in scenes["scenes"] for cid in s["character_ids"]}
    assert cast_in_scenes == {IDS["mira"], IDS["raju"]}
    locked_places = {IDS["kitchen"], IDS["garden"], IDS["space"]}
    assert {s["background_id"] for s in scenes["scenes"]} <= locked_places

    res = plan(client, comic_id, "panels")

    assert res.status_code == 200, res.json()
    panels = res.json()["panels"]
    assert len(panels) == 6 and res.json()["kept"] == 0
    scene_bg = {s["id"]: s["background_id"] for s in scenes["scenes"]}
    for p in panels:
        assert p["status"] == "planned" and p["beat"]
        assert p["background_id"] == scene_bg[p["scene_id"]]
        assert all(c["sheet_version"] == 1 and c["pose"] in CAT["poses"] for c in p["characters"])
        assert all(b["box"] and len(b["text"].split()) <= 12 for b in p["bubbles"])
    comic = client.get(f"/api/comics/{comic_id}").json()
    assert comic["studio_step"] == 3 and len(comic["panels"]) == 6


def test_planning_needs_a_locked_character_and_a_story(client: TestClient) -> None:
    only_robo = new_comic(client, cast=("robo",))
    res = plan(client, only_robo, "scenes")
    assert (res.status_code, res.json()["code"], res.json()["field"]) == (
        409,
        "needs_locked",
        "cast",
    )

    empty = new_comic(client, synopsis="Hi")
    res = plan(client, empty, "scenes")
    assert (res.status_code, res.json()["field"]) == (422, "synopsis")

    assert plan(client, empty, "panels").json()["code"] == "needs_scenes"


def test_replanning_scenes_asks_first_if_the_kid_edited_them(client: TestClient) -> None:
    comic_id = new_comic(client)
    first = plan(client, comic_id, "scenes").json()["scenes"]
    assert plan(client, comic_id, "scenes").status_code == 200  # untouched: replaced silently

    current = client.get(f"/api/comics/{comic_id}").json()["scenes"]
    edited = [
        {**s, "summary": "Mira finds a clue."} if i == 0 else s for i, s in enumerate(current)
    ]
    body = [{k: s[k] for k in ("id", "background_id", "character_ids", "summary")} for s in edited]
    assert client.put(f"/api/comics/{comic_id}/scenes", json=body).status_code == 200

    res = plan(client, comic_id, "scenes")
    assert (res.status_code, res.json()["code"]) == (409, "confirm_start_over")
    assert (
        client.get(f"/api/comics/{comic_id}").json()["scenes"][0]["summary"] == "Mira finds a clue."
    )
    again = plan(client, comic_id, "scenes", start_over=True)
    assert again.status_code == 200 and again.json()["scenes"][0]["summary"] == first[0]["summary"]


def test_replanning_panels_keeps_edited_ones_unless_starting_over(client: TestClient) -> None:
    comic_id = new_comic(client)
    plan(client, comic_id, "scenes")
    panels = plan(client, comic_id, "panels").json()["panels"]
    edited = panels[1]
    bubble = {**edited["bubbles"][0], "text": "My own words!"}
    res = client.patch(f"/api/panels/{edited['id']}", json={"bubbles": [bubble]})
    assert res.status_code == 200

    again = plan(client, comic_id, "panels").json()

    assert again["kept"] == 1
    ids = [p["id"] for p in again["panels"]]
    assert ids[1] == edited["id"] and again["panels"][1]["bubbles"][0]["text"] == "My own words!"
    assert not set(ids) - {edited["id"]} & {p["id"] for p in panels}  # the rest are new

    fresh = plan(client, comic_id, "panels", start_over=True).json()
    assert fresh["kept"] == 0 and edited["id"] not in [p["id"] for p in fresh["panels"]]


def test_drawn_panels_are_kept_too(client: TestClient) -> None:
    mango = IDS["mango"]  # seeded: 4 of its 6 panels are drawn
    comic = client.get(f"/api/comics/{mango}").json()
    drawn = [p["id"] for p in comic["panels"] if p["status"] == "ready"]

    # Scene 2 has Robo-Tik, who isn't locked: planning says which scene to fix.
    res = plan(client, mango, "panels")
    scene2 = comic["scenes"][1]
    assert (res.status_code, res.json()["code"]) == (409, "needs_locked")
    assert res.json()["field"] == f"scenes.{scene2['id']}"
    body = [
        {
            "id": s["id"],
            "background_id": s["background_id"],
            "character_ids": [c for c in s["character_ids"] if c != IDS["robo"]],
            "summary": s["summary"],
        }
        for s in comic["scenes"]
    ]
    assert client.put(f"/api/comics/{mango}/scenes", json=body).status_code == 200

    after = plan(client, mango, "panels").json()

    assert after["kept"] == 4
    assert [p["id"] for p in after["panels"] if p["status"] == "ready"] == drawn


def test_panel_edits_cant_stack_two_characters_in_one_spot(client: TestClient) -> None:
    comic_id = new_comic(client)
    plan(client, comic_id, "scenes")
    panel = plan(client, comic_id, "panels").json()["panels"][1]
    twins = [
        {**panel["characters"][0], "id": IDS["mira"], "position": "left"},
        {**panel["characters"][0], "id": IDS["raju"], "position": "left"},
    ]
    res = client.patch(f"/api/panels/{panel['id']}", json={"characters": twins})
    assert (res.status_code, res.json()["field"]) == (422, "characters")


def test_moving_a_character_moves_their_bubble(client: TestClient) -> None:
    comic_id = new_comic(client, cast=("mira",))
    plan(client, comic_id, "scenes")
    panel = next(
        p
        for p in plan(client, comic_id, "panels").json()["panels"]
        if p["bubbles"][0]["speaker"] != "narrator"
    )
    moved = [{**panel["characters"][0], "position": "right"}]

    res = client.patch(f"/api/panels/{panel['id']}", json={"characters": moved})

    assert abs(res.json()["bubbles"][0]["tail"][0] - 0.78) < 0.04  # at their head, on the right


# ---- Meta's planner, with a fake client --------------------------------------------------------


def scene_reply(*members: str) -> dict[str, Any]:
    return {
        "scenes": [
            {
                "background_id": IDS["kitchen"],
                "character_ids": [IDS["mira"]],
                "summary": "The mango is gone.",
            },
            {
                "background_id": IDS["garden"],
                "character_ids": [IDS[m] for m in members],
                "summary": "They follow footprints.",
            },
        ]
    }


def panel_reply(scenes: list[dict[str, Any]], count: int = 6) -> dict[str, Any]:
    return {
        "panels": [
            {
                "scene_id": scenes[i % len(scenes)]["id"],
                "beat": f"Beat {i + 1}",
                "characters": [
                    {
                        "id": IDS["mira"],
                        "pose": "point",
                        "expression": "surprised",
                        "position": "left",
                    }
                ],
                "bubbles": [{"speaker": IDS["mira"], "type": "talk", "text": "Look at this!"}],
            }
            for i in range(count)
        ]
    }


def test_meta_scenes_and_panels_use_catalog_and_comic_ids_in_the_schema(client: TestClient) -> None:
    fake = use_meta(client)
    comic_id = new_comic(client, cast=("mira", "raju", "robo"))
    fake.replies["scene_plan"] = scene_reply("mira", "raju")

    res = plan(client, comic_id, "scenes")

    assert res.status_code == 200, res.json()
    assert (res.json()["source"], res.json()["label"]) == ("meta", META_LABEL)
    schema = schema_of(fake.calls_for("scene_plan")[0])["schema"]
    scene_item = schema["properties"]["scenes"]["items"]["properties"]
    assert set(scene_item["character_ids"]["items"]["enum"]) == {IDS["mira"], IDS["raju"]}
    assert IDS["kitchen"] in scene_item["background_id"]["enum"]

    scenes = res.json()["scenes"]
    fake.replies["panel_plan"] = panel_reply(scenes)
    res = plan(client, comic_id, "panels")

    assert res.status_code == 200, res.json()
    panel_schema = schema_of(fake.calls_for("panel_plan")[0])["schema"]
    item = panel_schema["properties"]["panels"]["items"]["properties"]
    character = item["characters"]["items"]["properties"]
    assert character["pose"]["enum"] == list(CAT["poses"])
    assert character["expression"]["enum"] == list(CAT["expressions"])
    assert set(item["scene_id"]["enum"]) == {s["id"] for s in scenes}
    assert "narrator" in item["bubbles"]["items"]["properties"]["speaker"]["enum"]
    assert res.json()["panels"][0]["characters"][0]["pose"] == "point"


def test_an_invalid_plan_is_retried_once_with_the_problems(client: TestClient) -> None:
    fake = use_meta(client)
    comic_id = new_comic(client)
    fake.replies["scene_plan"] = [
        scene_reply("mira"),
        scene_reply("mira", "raju"),
    ]  # Raju missing first

    res = plan(client, comic_id, "scenes")

    assert res.status_code == 200 and res.json()["source"] == "meta"
    first, second = fake.calls_for("scene_plan")
    assert "problems" not in user_text(first)
    assert "Raju" in user_text(second) and "Fix them" in user_text(second)


def test_invalid_twice_is_a_friendly_422_and_nothing_changes(client: TestClient) -> None:
    fake = use_meta(client)
    comic_id = new_comic(client)
    fake.replies["scene_plan"] = scene_reply("mira", "raju")
    scenes = plan(client, comic_id, "scenes").json()["scenes"]
    fake.replies["panel_plan"] = panel_reply(scenes)
    plan(client, comic_id, "panels")
    before = rows(client, comic_id)
    fake.replies["panel_plan"] = panel_reply(scenes, count=3)  # wrong count, twice

    res = plan(client, comic_id, "panels")

    assert (res.status_code, res.json()["code"]) == (422, "plan_failed")
    assert "Your story is safe" in res.json()["message"]
    assert rows(client, comic_id) == before


def test_meta_down_falls_back_to_the_offline_planner(client: TestClient) -> None:
    fake = use_meta(client)
    fake.replies["scene_plan"] = server_error()
    fake.replies["panel_plan"] = server_error()
    comic_id = new_comic(client)

    scenes = plan(client, comic_id, "scenes").json()
    panels = plan(client, comic_id, "panels").json()

    for out in (scenes, panels):
        assert (out["source"], out["fallback"], out["label"]) == ("mock", True, OFFLINE_LABEL)
    assert len(panels["panels"]) == 6


def test_unsafe_model_words_are_never_shown(client: TestClient) -> None:
    fake = use_meta(client)
    comic_id = new_comic(client)
    reply = scene_reply("mira", "raju")
    reply["scenes"][0]["summary"] = "They drink beer."
    fake.replies["scene_plan"] = reply

    out = plan(client, comic_id, "scenes").json()

    assert out["fallback"] is True and all("beer" not in s["summary"] for s in out["scenes"])


def test_fake_meta_counts_safety_calls(client: TestClient) -> None:
    """Nothing reaches the planner unless the story passed the classifier first."""
    fake: FakeMeta = use_meta(client)
    fake.replies["scene_plan"] = scene_reply("mira", "raju")
    comic_id = new_comic(client)

    plan(client, comic_id, "scenes")

    names = [schema_of(c)["name"] for c in fake.calls]
    assert names.index("safety_verdicts") < names.index("scene_plan")
