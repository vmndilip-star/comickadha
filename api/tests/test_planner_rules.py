"""The planner keeps the kid's scenes and the story's rules (Phase 8, step 2): story positions,
key moments, sleepers who never talk, every scene character on stage, and failing panels asked
for again one at a time (at most twice) before they are repaired by hand."""

from dataclasses import replace
from typing import Any

from fastapi.testclient import TestClient

from app.schemas.studio import PanelPlan, PlannedPanel
from app.services import stage, story_planner
from app.services.story_planner import (
    CastMember,
    SceneInfo,
    check_part,
    ensure_scene_casts,
    key_panel,
    offline_part,
    plan_parts,
    scene_position,
)
from tests.conftest import IDS, plan_panels
from tests.fakes import panel_parts, schema_of, use_meta, user_text
from tests.test_long_comics import ctx
from tests.test_studio import new_comic

STORY = (
    "Mira and Raju guard the field at night. Raju snores. A rustle! Mira's torch shows a bear "
    "hugging the scarecrow. They share sweets with the bear."
)


# A story with no key moment (nothing found or revealed), so only the panel under test can fail.
CALM = "Mira and Raju bake a cake in the kitchen. Then they share the cake in the garden."


# ---- story positions ----------------------------------------------------------------------------


def test_each_scene_knows_where_it_sits_in_the_story() -> None:
    assert [scene_position(i, 8) for i in range(8)] == [
        "beginning",
        "beginning",
        "middle",
        "middle",
        "end",
        "end",
        "end",
        "end",
    ]
    assert [scene_position(i, 5) for i in range(5)] == [
        "beginning",
        "beginning",
        "middle",
        "end",
        "end",
    ]
    assert [scene_position(i, 2) for i in range(2)] == ["beginning", "end"]


def test_the_prompt_tells_each_part_its_position_time_and_key_moment() -> None:
    story = ctx(8)
    story.scenes[1] = replace(
        story.scenes[1], time_of_day="night", key_moment="The torch finds the bear"
    )
    lines = "\n".join(story_planner.scene_lines(story))
    assert "story position: beginning; time of day: day" in lines
    assert "time of day: night; key moment: The torch finds the bear" in lines
    part = next(p for p in plan_parts(story) if p.scene.id == story.scenes[1].id)
    brief = " ".join(story_planner.part_brief(story, part))
    assert "end of the story" in brief or "middle of the story" in brief or "beginning" in brief
    assert "It happens at night" in brief
    assert "key moment must be one of these panels" in brief and "The torch finds the bear" in brief
    first = plan_parts(story)[0]
    assert "Nothing gets solved yet" in " ".join(story_planner.part_brief(story, first))


def test_the_panel_prompt_keeps_scenes_and_saves_the_reveal_for_the_end() -> None:
    from app.prompts import template

    text = template("planner_panels")
    assert "Keep every scene exactly as the child set it" in text
    assert "Never move a scene to another place or leave one of its characters out" in text
    assert "Only end scenes reveal what happened" in text
    assert "never has a bubble of any kind" in text  # sleepers
    scenes = template("planner_scenes")
    assert '"time_of_day"' in scenes and '"key_moment"' in scenes
    assert "keep the answer for the final scenes" in scenes


# ---- key moments ---------------------------------------------------------------------------------


def test_the_key_moment_goes_to_its_scenes_last_run_and_must_be_shown() -> None:
    story = ctx(20, scene_count=2)  # 10 panels a scene: two runs each
    story.scenes[0] = replace(story.scenes[0], key_moment="The bear is found")
    parts = [p for p in plan_parts(story) if p.scene.id == story.scenes[0].id]
    assert [p.key_moment for p in parts] == ["", "The bear is found"]
    offline = offline_part(story, parts[1], story_planner.Voices())
    marked = [p for p in offline.panels if p.key_moment]
    assert len(marked) == 1 and marked[0].beat == "The bear is found"
    assert check_part(offline, story, parts[1]) == []
    unmarked = PanelPlan(
        panels=[p.model_copy(update={"key_moment": False}) for p in offline.panels]
    )
    problems = check_part(unmarked, story, parts[1])
    assert any(
        f"panel {key_panel(parts[1].count)}: show the scene's key moment" in p for p in problems
    )


# ---- sleepers ------------------------------------------------------------------------------------


def members() -> list[CastMember]:
    return [CastMember("h", "Mr. Hari", 1), CastMember("l", "Leo", 1), CastMember("s", "Sniffy", 1)]


def test_sleepers_are_drawn_asleep_and_never_speak() -> None:
    story = ctx(4, cast=members())
    scene = SceneInfo(
        "night",
        story.places[0].id,
        ("h", "l", "s"),
        "Mr Hari snores, Leo naps, Sniffy keeps watch.",
    )
    story = replace(story, panel_count=2, scenes=[scene])
    plan = story_planner.offline_panels(story)
    sleepy = [p for p in plan.panels if any(c.pose == "asleep" for c in p.characters)]
    assert sleepy, [p.beat for p in plan.panels]
    for panel in plan.panels:
        asleep = {c.id for c in panel.characters if c.pose == "asleep"}
        assert all(c.expression == "sleepy" for c in panel.characters if c.id in asleep)
        assert not any(b.speaker in asleep for b in panel.bubbles)
    assert story_planner.check_panels(plan, story) == []


def test_whoever_falls_asleep_in_a_scene_sleeps_through_its_later_panels() -> None:
    story = ctx(4, cast=members())
    scene = SceneInfo(
        "night",
        story.places[0].id,
        ("h", "l", "s"),
        "At night the friends climb the machan. Mr Hari snores, Leo sleeps, only Sniffy stays "
        "awake. A rustle in the cane! Sniffy's torch finds a bear.",
    )
    story = replace(story, panel_count=4, scenes=[scene])
    plan = story_planner.offline_panels(story)
    for panel in plan.panels[1:]:
        asleep = {c.id for c in panel.characters if c.pose == "asleep"}
        assert asleep == {"h", "l"}, panel.beat
        assert not any(b.speaker in asleep for b in panel.bubbles)
    torch = [p for panel in plan.panels for p in panel.props if p.id == "torch"]
    assert torch and all(p.held_by == "s" for p in torch)  # "Sniffy's torch"
    assert story_planner.check_panels(plan, story) == []


def test_a_sleepers_bubble_is_a_problem() -> None:
    story = replace(ctx(4, cast=members()), panel_count=1)
    story.scenes[:] = [SceneInfo("night", story.places[0].id, ("h", "s"), "Night watch.")]
    panel = PlannedPanel.model_validate(
        {
            "scene_id": "night",
            "beat": "Snoring",
            "characters": [
                {"id": "h", "pose": "asleep", "expression": "sleepy", "position": "left"},
                {"id": "s", "pose": "front", "expression": "happy", "position": "right"},
            ],
            "bubbles": [{"speaker": "h", "type": "think", "text": "Zzz, cake..."}],
        }
    )
    problems = story_planner.check_panels(PanelPlan(panels=[panel]), story)
    assert any("Mr. Hari is asleep, so they can't have a bubble" in p for p in problems)


def test_a_sleeper_gets_a_zzz_and_the_sleepy_face() -> None:
    from app.avatar.spec import normalize

    laid = stage.layout(
        [{"id": "h", "pose": "asleep", "expression": "happy", "position": "center"}],
        {"h": normalize({"body_type": "grown_up"})},
    )
    assert laid.characters[0].expression == "sleepy"
    assert [e.kind for e in laid.effects] == ["zzz"]
    zzz, head = laid.effects[0].box, laid.characters[0].head
    assert zzz[1] < head[1]  # above the head


def test_the_api_never_lets_a_sleeper_talk(client: TestClient) -> None:
    comic_id = new_comic(client)
    assert client.post(f"/api/studio/{comic_id}/plan-scenes", json={}).status_code == 200
    assert plan_panels(client, comic_id).status_code == 200
    panel = client.get(f"/api/comics/{comic_id}").json()["panels"][1]
    sleeper = panel["characters"][0]
    characters = [
        {**c, "pose": "asleep"} if c["id"] == sleeper["id"] else c for c in panel["characters"]
    ]
    bubble = {"id": "b1", "speaker": sleeper["id"], "type": "talk", "text": "I am awake!"}
    res = client.patch(
        f"/api/panels/{panel['id']}", json={"characters": characters, "bubbles": [bubble]}
    )
    assert res.status_code == 422 and res.json()["field"] == "bubbles.b1.text"
    assert "asleep" in res.json()["message"]
    quiet = client.patch(
        f"/api/panels/{panel['id']}", json={"characters": characters, "bubbles": []}
    )
    assert quiet.status_code == 200
    assert any(layer["kind"] == "effect" for layer in quiet.json()["stage"]["layers"])


# ---- every scene character on stage -------------------------------------------------------------


def test_nobody_in_a_scene_is_left_out_of_its_panels() -> None:
    story = ctx(4)
    parts = plan_parts(story)
    plans = [story_planner.offline_part(story, p, story_planner.Voices()) for p in parts]
    first = parts[0]
    lead = first.scene.character_ids[0]
    lonely = PanelPlan(
        panels=[
            p.model_copy(update={"characters": [c for c in p.characters if c.id == lead]})
            for p in plans[0].panels
        ]
    )
    missing = set(first.scene.character_ids) - {c.id for p in lonely.panels for c in p.characters}
    assert missing
    fixed = ensure_scene_casts([lonely, *plans[1:]], parts, story)
    assert 0 in fixed
    shown = {c.id for p in fixed[0].panels for c in p.characters}
    assert set(first.scene.character_ids) <= shown


# ---- failing panels are asked for again, one at a time ---------------------------------------


def test_a_failing_panel_is_asked_for_again_on_its_own(client: TestClient) -> None:
    """The first answer gives a bubble to someone who isn't in the panel: only that panel is asked
    for again (panel_fix), its fixed version is kept, and the part isn't planned again."""
    comic_id = new_comic(client, synopsis=CALM, panel_count=4)
    assert client.post(f"/api/studio/{comic_id}/plan-scenes", json={}).status_code == 200
    fake = use_meta(client)
    base = panel_parts()

    def wrong_once(call: dict[str, Any]) -> dict[str, Any]:
        out = base(call)
        out["panels"][0]["bubbles"] = [
            {"speaker": "narrator", "type": "talk", "text": "Oops, a mix-up!"}
        ]
        return out

    fixed_words = "Mira looks around the kitchen."

    def fix(call: dict[str, Any]) -> dict[str, Any]:
        item = schema_of(call)["schema"]["properties"]["panels"]["items"]["properties"]
        number = item["panel"]["enum"][0]
        speaker = item["characters"]["items"]["properties"]["id"]["enum"][0]
        return {
            "panels": [
                {
                    "panel": number,
                    "scene_id": item["scene_id"]["enum"][0],
                    "beat": "Fixed beat",
                    "characters": [
                        {"id": speaker, "pose": "front", "expression": "happy", "position": "left"}
                    ],
                    "bubbles": [{"speaker": "narrator", "type": "narrator", "text": fixed_words}],
                    "props": [],
                    "key_moment": False,
                }
            ]
        }

    fake.replies["panel_plan"] = wrong_once
    fake.replies["panel_fix"] = fix

    assert plan_panels(client, comic_id).status_code == 200

    fixes = fake.calls_for("panel_fix")
    assert fixes and all(
        len(schema_of(c)["schema"]["properties"]["panels"]["items"]["properties"]["panel"]["enum"])
        == 1
        for c in fixes
    )
    assert "only those" in user_text(
        fixes[0]
    ) and "only the narrator uses narrator bubbles" in user_text(fixes[0])
    panels = client.get(f"/api/comics/{comic_id}").json()["panels"]
    assert any(p["beat"] == "Fixed beat" for p in panels)
    scenes = {
        c_scene
        for c_scene in (
            schema_of(c)["schema"]["properties"]["panels"]["items"]["properties"]["scene_id"][
                "enum"
            ][0]
            for c in fake.calls_for("panel_plan")
        )
    }
    assert len(fake.calls_for("panel_plan")) == len(scenes)  # no part was planned twice


def test_a_panel_still_wrong_after_two_tries_is_repaired_by_hand(client: TestClient) -> None:
    comic_id = new_comic(client, synopsis=CALM, panel_count=4)
    assert client.post(f"/api/studio/{comic_id}/plan-scenes", json={}).status_code == 200
    fake = use_meta(client)
    base = panel_parts()

    def too_wordy(call: dict[str, Any]) -> dict[str, Any]:
        out = base(call)
        out["panels"][0]["bubbles"][0]["text"] = " ".join(["word"] * 20)
        return out

    def same_again(call: dict[str, Any]) -> dict[str, Any]:  # never gets it right
        item = schema_of(call)["schema"]["properties"]["panels"]["items"]["properties"]
        out = too_wordy(call)
        return {"panels": [{**out["panels"][0], "panel": item["panel"]["enum"][0]}]}

    fake.replies["panel_plan"] = too_wordy
    fake.replies["panel_fix"] = same_again

    res = plan_panels(client, comic_id)

    assert res.status_code == 200 and res.json()["source"] == "meta"
    per_scene: dict[str, int] = {}
    for call in fake.calls_for("panel_fix"):
        scene = schema_of(call)["schema"]["properties"]["panels"]["items"]["properties"][
            "scene_id"
        ]["enum"][0]
        per_scene[scene] = per_scene.get(scene, 0) + 1
    assert per_scene and max(per_scene.values()) == story_planner.FIX_TRIES  # twice, no more
    for panel in client.get(f"/api/comics/{comic_id}").json()["panels"]:
        assert all(len(b["text"].split()) <= 12 for b in panel["bubbles"])  # clipped by hand


# ---- the kid's scenes keep their time of day, key moment and panel count -------------------------


def test_scenes_keep_their_time_of_day_key_moment_and_panel_count(client: TestClient) -> None:
    comic_id = new_comic(client)
    scene = {
        "background_id": IDS["garden"],
        "character_ids": [IDS["mira"]],
        "summary": "x" * 300,
        "time_of_day": "night",
        "key_moment": "The torch finds the bear",
        "panel_count": 5,
    }
    res = client.put(f"/api/comics/{comic_id}/scenes", json=[scene])
    assert res.status_code == 200, res.json()
    saved = res.json()[0]
    assert (saved["time_of_day"], saved["key_moment"], saved["panel_count"]) == (
        "night",
        "The torch finds the bear",
        5,
    )
    assert len(saved["summary"]) == 300
    again = client.get(f"/api/comics/{comic_id}").json()["scenes"][0]
    assert again["time_of_day"] == "night" and again["key_moment"] == "The torch finds the bear"


def test_planned_panels_happen_at_their_scenes_time_of_day(client: TestClient) -> None:
    comic_id = new_comic(client, panel_count=4)
    scenes = client.post(f"/api/studio/{comic_id}/plan-scenes", json={}).json()["scenes"]
    body = [{**s, "time_of_day": "night" if i == 0 else "sunset"} for i, s in enumerate(scenes)]
    for s in body:
        s.pop("idx", None)
    assert client.put(f"/api/comics/{comic_id}/scenes", json=body).status_code == 200
    assert plan_panels(client, comic_id, start_over=True).status_code == 200
    comic = client.get(f"/api/comics/{comic_id}").json()
    times = {s["id"]: s["time_of_day"] for s in comic["scenes"]}
    assert comic["panels"] and all(
        p["time_of_day"] == times[p["scene_id"]] for p in comic["panels"]
    )


def test_offline_scenes_take_their_time_of_day_from_the_story() -> None:
    story = replace(ctx(6), synopsis=STORY, scenes=[])
    plan = story_planner.offline_scenes(story)
    assert any(s.time_of_day == "night" for s in plan.scenes)
    assert any("torch shows a bear" in s.key_moment for s in plan.scenes)
    schema = story_planner.scenes_schema(story)["properties"]["scenes"]["items"]["properties"]
    assert schema["time_of_day"]["enum"] == ["day", "sunset", "night"] and "key_moment" in schema
