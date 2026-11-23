"""Phase 7 part C: longer comics. Panel counts 4 to 30, about a scene per 4 panels, the panel plan
made a part at a time as a job (a few parts at once, each saved as it's ready), the comic-wide
dialogue pass, classifier batches, and 25- and 30-panel comics made and printed."""

import re
import threading
import time
from dataclasses import replace
from typing import Any, get_args

import pytest
from fastapi.testclient import TestClient

from app.providers.meta import MetaLLMProvider
from app.schemas.common import PanelCount
from app.schemas.studio import PanelPlan, PlannedBubble, PlannedCharacter, PlannedPanel
from app.services import safety
from app.services.ai_limits import CLASSIFIER_BATCH, PANELS_PER_CALL, PLAN_PARTS_AT_ONCE
from app.services.plan_job import PLAN_BROKE
from app.services.story_planner import (
    LINKS,
    SAME_PLACE,
    SCENES_FOR,
    CastMember,
    Place,
    SceneInfo,
    StoryContext,
    check_panels,
    dialogue_clashes,
    mood_for,
    offline_panels,
    opening,
    part_brief,
    plan_parts,
    repair_dialogue,
    scene_shares,
    split_into,
)
from tests.conftest import IDS, plan_panels, sse_events, wait_for_job
from tests.fakes import TEXT_MODEL, VISION_MODEL, FakeMeta, panel_parts, server_error, use_meta
from tests.fakes import user_text as text_of
from tests.test_make_comic import page_count

COUNTS: list[int] = list(get_args(PanelCount))
STORY = (
    "Mira and Raju find a map in Grandma's kitchen. They follow it to the school garden and dig "
    "under the mango tree. A cheeky squirrel steals the map! They chase it, find the treasure and "
    "share it with everyone at a big party."
)


# ---- counts, scenes and shares ----------------------------------------------------------------


def test_the_panel_counts_and_scene_counts() -> None:
    assert COUNTS == [4, 6, 8, 10, 16, 20, 25, 30]
    assert SCENES_FOR == {4: 2, 6: 3, 8: 4, 10: 3, 16: 4, 20: 5, 25: 7, 30: 8}
    assert all(count / SCENES_FOR[count] <= 4 for count in COUNTS)  # about a scene per 4 panels


@pytest.mark.parametrize("count", COUNTS)
def test_scene_shares_add_up_and_parts_cover_every_panel(count: int) -> None:
    shares = scene_shares(count, SCENES_FOR[count])
    assert sum(shares) == count and min(shares) >= 1 and max(shares) - min(shares) <= 1

    parts = plan_parts(ctx(count))
    assert [i for p in parts for i in p.indexes] == list(range(count))  # in order, no gaps
    assert all(p.count <= PANELS_PER_CALL for p in parts)


def test_a_big_scene_is_planned_in_runs() -> None:
    one = ctx(30, scene_count=1)

    parts = plan_parts(one)

    assert [(p.count, p.piece, p.pieces) for p in parts] == [
        (8, 1, 4),
        (8, 2, 4),
        (7, 3, 4),
        (7, 4, 4),
    ]
    assert all((p.scene_first, p.scene_count) == (0, 30) for p in parts)


def test_each_catchphrase_belongs_to_one_part_its_character_is_in() -> None:
    story = ctx(30)

    parts = plan_parts(story)

    for member in story.cast:
        owners = [p for p in parts if member.id in p.catchphrases]
        assert len(owners) == 1 and member.id in owners[0].scene.character_ids


def test_the_scene_prompt_asks_for_a_beginning_middle_and_end() -> None:
    from app.prompts import render

    text = render("planner_scenes", scene_count=8)

    assert "exactly 8 scenes" in text and "clear beginning" in text and "middle and end" in text


# ---- the offline planner at every length ------------------------------------------------------

MIRA = CastMember("mira", "Mira", 1, "Adventure is my middle name!", ("brave",))
RAJU = CastMember("raju", "Raju", 1, "Snack break? Snack break!", ("funny",))
ZARA = CastMember("zara", "Zara", 1, "Let's go, go, go!", ("brave",))
PLACES = [Place("kitchen", "Grandma's kitchen"), Place("garden", "School garden")]


def ctx(
    count: int, scene_count: int | None = None, cast: list[CastMember] | None = None
) -> StoryContext:
    cast = cast or [MIRA, RAJU, ZARA]
    n = scene_count or SCENES_FOR[count]
    sentences = re.split(r"(?<=[.!?])\s+", STORY)
    scenes = [
        SceneInfo(
            f"s{i}",
            PLACES[i % 2].id,
            tuple(m.id for m in cast[: 2 + i % 2]),
            " ".join(group) or "They keep looking.",
        )
        for i, group in enumerate(split_into(sentences, n))
    ]
    return StoryContext("Map", STORY, "adventure", count, cast, PLACES, scenes)


@pytest.mark.parametrize("count", COUNTS)
def test_offline_plans_follow_every_rule_and_never_repeat_themselves(count: int) -> None:
    story = ctx(count)

    plan = offline_panels(story)

    assert len(plan.panels) == count
    assert check_panels(plan, story) == []  # incl. the dialogue rules, comic-wide
    beats = [p.beat for p in plan.panels]
    assert len(set(beats)) == len(beats)  # no beat twice
    for a, b in zip(plan.panels, plan.panels[1:], strict=False):
        assert (a.beat, a.bubbles) != (b.beat, b.bubbles)
    # Others react with their own pose and face, and characters swap sides.
    reacting = [
        c for p in plan.panels if len(p.characters) > 1 for c in p.characters[1:]
    ]  # fmt: skip
    if count >= 8:
        assert len({c.pose for c in reacting}) >= 3
        assert len({c.expression for c in reacting}) >= 3
        sides = {(p.characters[0].id, p.characters[0].position) for p in plan.panels}
        assert len(sides) >= 3


@pytest.mark.parametrize("count", [10, 16, 20, 25, 30])
def test_offline_plans_link_their_scenes_with_the_narrator(count: int) -> None:
    story = ctx(count)

    plan = offline_panels(story)

    links = [template.split("{")[0] for template in LINKS] + ["Back at", *SAME_PLACE]
    for part in plan_parts(story):
        if part.piece != 1 or part.first in (0, count - 1):
            continue
        first = plan.panels[part.first]
        captions = [b.text for b in first.bubbles if b.speaker == "narrator"]
        assert captions and any(c.startswith(tuple(links)) for c in captions), captions


def test_a_scene_at_the_same_place_links_without_naming_it_again() -> None:
    story = ctx(16)
    story.scenes = [replace(s, background_id="kitchen") for s in story.scenes]

    plan = offline_panels(story)

    for part in plan_parts(story)[1:]:
        captions = [b.text for b in plan.panels[part.first].bubbles if b.speaker == "narrator"]
        assert captions[0] in SAME_PLACE  # "A little later...", never "Back at" the same kitchen


def test_catchphrases_are_offered_only_where_they_fit() -> None:
    """Live test 2: "Mystery solved!" came right after the cake vanished. A catchphrase is an
    option the planner may skip, and the offline planner never puts one on a sad moment."""
    story = ctx(16)
    part = next(p for p in plan_parts(story) if p.catchphrases)

    brief = " ".join(part_brief(story, part))

    assert "only where one truly fits the moment (otherwise leave it out)" in brief
    assert mood_for("The moon cake vanishes from the table")[1] == "sad"
    assert mood_for("A squirrel stole the map")[1] == "sad"


# ---- the comic-wide pass ----------------------------------------------------------------------


def panel(scene: str, speaker: str, text: str, beat: str = "Something happens") -> PlannedPanel:
    return PlannedPanel(
        scene_id=scene,
        beat=beat,
        characters=[
            PlannedCharacter(id=speaker, pose="front", expression="happy", position="center")
        ],
        bubbles=[PlannedBubble(speaker=speaker, type="talk", text=text)],
    )


def test_clashing_openings_across_parts_are_found_and_settled() -> None:
    story = ctx(8)  # 4 scenes of 2 panels
    parts = plan_parts(story)
    lines = ["Look at this!", "Wow, cool!", "Look at that!", "Look at me!", "Nice!", "Hey you!",
             "Yay!", "The end!"]  # fmt: skip
    plans: list[PanelPlan | None] = [
        PanelPlan(panels=[panel(p.scene.id, "mira", lines[i]) for i in p.indexes]) for p in parts
    ]

    clashes = dialogue_clashes(plans, parts)

    assert list(clashes) == [1]  # Mira's third "look at" is in scene 2's part (panels 3, 4)
    assert {"look at", "wow cool"} <= clashes[1]["mira"]  # what Mira says in the other parts
    fixed = repair_dialogue(plans, parts, story)
    assert list(fixed) == [1]
    third = fixed[1].panels[1]
    assert [(b.speaker, b.text) for b in third.bubbles] == [("narrator", "Something happens.")]
    assert dialogue_clashes([fixed.get(i, p) for i, p in enumerate(plans)], parts) == {}


# ---- the planning job -------------------------------------------------------------------------


def long_comic(client: TestClient, count: int, cast: tuple[str, ...] = ("mira", "raju")) -> str:
    comic_id: str = client.post("/api/comics", json={"title": "Map", "synopsis": STORY}).json()[
        "id"
    ]
    body = {"cast_ids": [IDS[c] for c in cast], "panel_count": count, "mood": "adventure"}
    assert client.patch(f"/api/comics/{comic_id}", json=body).status_code == 200
    scenes = client.post(f"/api/studio/{comic_id}/plan-scenes", json={})
    assert scenes.status_code == 200 and len(scenes.json()["scenes"]) == SCENES_FOR[count]
    return comic_id


@pytest.mark.parametrize("count", COUNTS)
def test_every_panel_count_plans_exactly_that_many_panels_offline(
    client: TestClient, count: int
) -> None:
    comic_id = long_comic(client, count)

    res = plan_panels(client, comic_id)

    assert res.status_code == 200, res.json()
    panels = res.json()["panels"]
    assert [p["idx"] for p in panels] == list(range(count))
    assert all(1 <= len(p["characters"]) <= 3 for p in panels)
    kinds = [kind for _id, kind, _data in res.events]
    assert kinds[0] == "progress" and kinds[-1] == "done"
    planned = [data for _id, kind, data in res.events if kind == "scene_planned"]
    assert sum(d["count"] for d in planned) == count  # every part, each saved as it was ready


@pytest.mark.parametrize("count", [4, 10, 16, 25, 30])
def test_every_panel_count_plans_exactly_that_many_panels_with_meta(
    client: TestClient, count: int
) -> None:
    comic_id = long_comic(client, count)
    fake = use_meta(client)
    fake.replies["panel_plan"] = panel_parts()

    res = plan_panels(client, comic_id)

    assert res.status_code == 200, res.json()
    assert (res.json()["source"], res.json()["fallback"]) == ("meta", False)
    assert len(res.json()["panels"]) == count
    assert len(fake.calls_for("panel_plan")) == SCENES_FOR[count]  # one call a scene
    assert all(p["beat"].startswith("Beat ") for p in res.json()["panels"])
    parts = [d for _i, kind, d in res.events if kind == "scene_planned"]
    assert {d["source"] for d in parts} == {"meta"}  # each part says who made it


def test_parts_are_planned_a_few_at_once(client: TestClient) -> None:
    comic_id = long_comic(client, 30)  # 8 scenes
    fake = use_meta(client)
    busy, most = [0], [0]
    lock = threading.Lock()

    def in_flight(_call: dict[str, Any]) -> None:
        with lock:
            busy[0] += 1
            most[0] = max(most[0], busy[0])
        time.sleep(0.15)
        with lock:
            busy[0] -= 1

    fake.replies["panel_plan"] = panel_parts(on_call=in_flight)

    assert plan_panels(client, comic_id).status_code == 200
    assert 1 < most[0] <= PLAN_PARTS_AT_ONCE


def test_a_refresh_during_planning_reconnects_and_keeps_planned_scenes(client: TestClient) -> None:
    comic_id = long_comic(client, 16)  # 4 scenes of 4 panels
    scenes = client.get(f"/api/comics/{comic_id}").json()["scenes"]
    fake = use_meta(client)
    release = threading.Event()

    def hold_the_last_scene(call: dict[str, Any]) -> None:
        if f"scene_id {scenes[-1]['id']}" in text_of(call):
            release.wait(10)

    fake.replies["panel_plan"] = panel_parts(on_call=hold_the_last_scene)
    started = client.post(f"/api/studio/{comic_id}/plan-panels", json={})
    assert started.status_code == 202 and started.json()["kind"] == "panel_plan"
    job_id = started.json()["job_id"]

    # "Refresh": the comic shows the parts planned so far and the job to follow.
    deadline = time.monotonic() + 10
    while len(client.get(f"/api/comics/{comic_id}").json()["panels"]) < 12:
        assert time.monotonic() < deadline
        time.sleep(0.05)
    comic = client.get(f"/api/comics/{comic_id}").json()
    assert comic["plan_job_id"] == job_id
    assert {p["scene_id"] for p in comic["panels"]} == {s["id"] for s in scenes[:-1]}
    again = client.post(f"/api/studio/{comic_id}/plan-panels", json={})
    assert again.json()["job_id"] == job_id  # pressing it again follows the same job

    release.set()
    assert wait_for_job(client, job_id)["status"] == "done"
    events = sse_events(client, job_id)  # a reconnect replays everything
    planned = [d["scene_id"] for _i, kind, d in events if kind == "scene_planned"]
    assert sorted(planned) == sorted(s["id"] for s in scenes) and events[-1][1] == "done"
    later = sse_events(client, job_id, last_event_id=events[-3][0])
    assert [kind for _i, kind, _d in later] == [kind for _i, kind, _d in events[-2:]]
    final = client.get(f"/api/comics/{comic_id}").json()
    assert len(final["panels"]) == 16 and final["plan_job_id"] is None


def test_clashing_parts_are_asked_again_with_the_openings_to_avoid(client: TestClient) -> None:
    comic_id = long_comic(client, 16)
    fake = use_meta(client)

    # Every first answer starts two lines "Look at ..." (fine in one scene, too many in the comic):
    # the comic-wide pass asks those parts again, with the openings to avoid.
    def line(n: int, i: int, text: str) -> str:
        fresh = "start theirs differently" in text or i % 2
        return f"Line {n} is fresh!" if fresh else f"Look at {n}!"

    fake.replies["panel_plan"] = panel_parts(line=line)

    res = plan_panels(client, comic_id)

    assert res.status_code == 200 and res.json()["source"] == "meta"
    asked_again = [
        c for c in fake.calls_for("panel_plan") if "start theirs differently" in text_of(c)
    ]
    assert asked_again and len(fake.calls_for("panel_plan")) == 4 + len(asked_again)
    starts = [
        (b["speaker"], opening(b["text"]))
        for p in res.json()["panels"]
        for b in p["bubbles"]
        if b["speaker"] != "narrator"
    ]
    assert max(starts.count(s) for s in set(starts)) <= 2  # per character, comic-wide
    assert any(kind == "progress" and d["stage"] == "polishing" for _i, kind, d in res.events)


def test_a_long_story_has_room_for_1000_letters(client: TestClient) -> None:
    comic_id = client.post("/api/comics", json={"title": "Long"}).json()["id"]
    story = ("Mira and Raju look for the map. " * 40)[:1000]

    ok = client.patch(f"/api/comics/{comic_id}", json={"synopsis": story})
    assert ok.status_code == 200 and len(ok.json()["synopsis"]) == 1000
    too_long = client.patch(f"/api/comics/{comic_id}", json={"synopsis": story + "!"})
    assert too_long.status_code == 422
    buddy = {"action": "spelling", "text": story, "comic_id": comic_id}
    assert client.post("/api/studio/buddy", json=buddy).status_code == 200


def test_a_planner_bug_fails_the_job_with_a_planning_message(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    comic_id = long_comic(client, 10)

    def broken(*_args: object) -> None:
        raise RuntimeError("a bug")

    monkeypatch.setattr("app.services.story_planner.offline_panels", broken)
    res = plan_panels(client, comic_id)

    assert res.status_code == 500  # the job failed (the helper turns its error event into this)
    assert res.json()["message"] == PLAN_BROKE


def test_more_scenes_than_panels_is_refused(client: TestClient) -> None:
    comic_id = long_comic(client, 8)  # 4 scenes
    client.patch(f"/api/comics/{comic_id}", json={"panel_count": 4})
    scenes = client.get(f"/api/comics/{comic_id}").json()["scenes"]
    keep = ("id", "background_id", "character_ids", "summary")
    body = [{k: s[k] for k in keep} for s in scenes]
    body.append({"background_id": scenes[0]["background_id"], "character_ids": [IDS["mira"]]})
    assert client.put(f"/api/comics/{comic_id}/scenes", json=body).status_code == 200

    res = plan_panels(client, comic_id)

    assert (res.status_code, res.json()["field"]) == (422, "scenes")
    assert "5 scenes but only 4 panels" in res.json()["message"]


@pytest.mark.parametrize(("count", "pages"), [(25, 6), (30, 6)])
def test_a_long_comic_is_made_and_printed(client: TestClient, count: int, pages: int) -> None:
    comic_id = long_comic(client, count, cast=("mira", "raju"))
    assert plan_panels(client, comic_id).status_code == 200

    made = client.post(f"/api/comics/{comic_id}/generate")
    assert made.status_code == 202
    assert wait_for_job(client, made.json()["job_id"], timeout=120)["status"] == "done"
    comic = client.get(f"/api/comics/{comic_id}").json()
    assert len(comic["panels"]) == count and all(p["status"] == "ready" for p in comic["panels"])

    pdf = client.get(f"/api/comics/{comic_id}/pdf")
    assert pdf.status_code == 200 and page_count(pdf.content) == pages  # the cover + 6 a page


# ---- classifier batches -----------------------------------------------------------------------


def meta(fake: FakeMeta) -> MetaLLMProvider:
    return MetaLLMProvider(
        api_key="k",
        model=TEXT_MODEL,
        vision_model=VISION_MODEL,
        base_url="http://x.invalid/v1",
        client=fake,
    )


def test_the_classifier_checks_in_batches() -> None:
    fake = FakeMeta()
    fields = {f"field {i}": f"A kind sentence number {i}." for i in range(45)}

    verdicts = safety.classify_each(meta(fake), fields)

    assert list(verdicts) == list(fields) and all(v.allowed for v in verdicts.values())
    sizes = [
        len(re.findall(r"^\d+\. ", text_of(c), re.MULTILINE))
        for c in fake.calls_for("safety_verdicts")
    ]
    assert sizes == [CLASSIFIER_BATCH, CLASSIFIER_BATCH, 5]


def test_an_outage_in_any_batch_fails_the_whole_check_closed() -> None:
    fake = FakeMeta()
    safe = {"verdicts": [{"safe": True, "categories": []}] * CLASSIFIER_BATCH}
    fake.replies["safety_verdicts"] = [safe, server_error()]
    fields = {f"field {i}": f"A kind sentence number {i}." for i in range(30)}

    with pytest.raises(safety.SafetyUnavailable):
        safety.classify_each(meta(fake), fields)


def test_a_30_panel_plan_is_checked_in_batches(client: TestClient) -> None:
    comic_id = long_comic(client, 30)
    fake = use_meta(client)
    fake.replies["panel_plan"] = panel_parts()

    assert plan_panels(client, comic_id).status_code == 200

    for call in fake.calls_for("safety_verdicts"):
        assert len(re.findall(r"^\d+\. ", text_of(call), re.MULTILINE)) <= CLASSIFIER_BATCH
