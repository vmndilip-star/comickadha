"""Safety on story text: blocks name the exact field, personal info stays secret, and a
classifier outage leaves locally checked words "not yet AI-checked" (decision 55)."""

from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, col, select

from app.models import ModerationLog
from app.services import recheck, safety
from tests.conftest import IDS, app_state, plan_panels
from tests.fakes import flag, server_error, use_meta

GOOD = "Mira and Raju follow sticky footprints to the school garden and find the mango."


def new_comic(client: TestClient, synopsis: str = GOOD, title: str = "Mango") -> str:
    comic_id: str = client.post("/api/comics", json={"title": title, "synopsis": synopsis}).json()[
        "id"
    ]
    client.patch(f"/api/comics/{comic_id}", json={"cast_ids": [IDS["mira"], IDS["raju"]]})
    return comic_id


def plan(client: TestClient, comic_id: str, what: str) -> Any:
    if what == "panels":  # a job since Phase 7 part C: run it and wait
        return plan_panels(client, comic_id)
    return client.post(f"/api/studio/{comic_id}/plan-{what}", json={})


def blocks(client: TestClient) -> list[tuple[str, list[str]]]:
    with Session(app_state(client).engine) as session:
        stmt = select(ModerationLog).where(ModerationLog.verdict == "block")
        return [
            (log.target, log.categories)
            for log in session.exec(stmt.order_by(col(ModerationLog.created_at)))
        ]


# ---- the local checks ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "says"),
    [
        ("Call Mira on 07700 900 123 tonight.", "phone numbers secret"),
        ("Her number is +44 (0)20 7946 0018.", "phone numbers secret"),
        ("Email me at mira.rao@example.com", "email addresses secret"),
        ("They live at 42 Oak Lane.", "real addresses secret"),
        ("We live at 7, Gandhi Nagar", "real addresses secret"),
        ("I go to Sunnyhill Primary.", "school names secret"),
        ("My name is Priya Sharma.", "full names secret"),
    ],
)
def test_personal_info_is_blocked_with_a_gentle_message(text: str, says: str) -> None:
    verdict = safety.check_local({"synopsis": text})
    assert not verdict.allowed and verdict.field_name == "synopsis"
    assert verdict.categories == ["personal_info"]
    assert says in verdict.message({})


@pytest.mark.parametrize(
    "text",
    [
        "Robo-Tik starts school and gets everything a little bit wrong.",
        "They follow footprints to the school garden.",
        "Class 3B counted 1000 stars in 2026.",
        "Robo Tik and Grandpa Joe fly to the moon.",
        "Mira is 10 and Raju is 11.",
    ],
)
def test_ordinary_story_words_are_fine(text: str) -> None:
    assert safety.check_local({"synopsis": text}).allowed


def test_seeded_demo_stories_pass_the_local_checks(client: TestClient) -> None:
    for comic in client.get("/api/comics").json():
        assert comic["safety_notes"] == [], comic["title"]


# ---- autosave: local checks, still saved, message right away ----------------------------------


def test_autosave_keeps_a_blocked_draft_and_notes_the_field(client: TestClient) -> None:
    comic_id = new_comic(client)

    res = client.patch(f"/api/comics/{comic_id}", json={"synopsis": "Text Mira on 07700 900123!"})

    assert res.status_code == 200
    assert res.json()["synopsis"] == "Text Mira on 07700 900123!"  # the draft is kept
    assert res.json()["safety_notes"] == [{"field": "synopsis", "message": safety.SECRET_PHONE}]
    assert (f"comic:{comic_id}:synopsis", ["personal_info"]) in blocks(client)
    # Still there after a refresh, until the kid changes it.
    assert client.get(f"/api/comics/{comic_id}").json()["safety_notes"][0]["field"] == "synopsis"
    fixed = client.patch(f"/api/comics/{comic_id}", json={"synopsis": GOOD}).json()
    assert fixed["safety_notes"] == []


def test_autosave_never_calls_meta(client: TestClient) -> None:
    fake = use_meta(client)
    comic_id = new_comic(client)

    client.patch(f"/api/comics/{comic_id}", json={"title": "A beer party", "synopsis": GOOD})

    assert fake.calls == []  # only the instant local checks


# ---- Next (plan-scenes): the full check -----------------------------------------------------


def test_a_word_list_hit_blocks_planning_under_the_field(client: TestClient) -> None:
    comic_id = new_comic(client, title="The beer festival")

    res = plan(client, comic_id, "scenes")

    assert (res.status_code, res.json()["code"], res.json()["field"]) == (422, "unsafe", "title")
    assert "title" in res.json()["message"]
    assert client.get(f"/api/comics/{comic_id}").json()["scenes"] == []


def test_personal_info_blocks_planning_with_its_message(client: TestClient) -> None:
    comic_id = new_comic(client, synopsis="Mira lives at 12 Baker Street and finds a mango.")

    res = plan(client, comic_id, "scenes")

    assert (res.status_code, res.json()["field"]) == (422, "synopsis")
    assert res.json()["message"] == safety.SECRET_ADDRESS


def test_the_classifier_blocks_unsafe_story_text(client: TestClient) -> None:
    fake = use_meta(client)
    fake.replies["safety_verdicts"] = flag("mean to", "bullying")
    comic_id = new_comic(client, synopsis="Mira is mean to Raju all day long.")

    res = plan(client, comic_id, "scenes")

    assert (res.status_code, res.json()["field"]) == (422, "synopsis")
    assert fake.calls_for("scene_plan") == []
    assert (f"comic:{comic_id}", ["bullying"]) in blocks(client)


def verdicts(client: TestClient, verdict: str) -> list[str]:
    with Session(app_state(client).engine) as session:
        stmt = select(ModerationLog).where(ModerationLog.verdict == verdict)
        return [log.target for log in session.exec(stmt)]


def test_a_classifier_outage_plans_offline_and_marks_the_story_pending(
    client: TestClient,
) -> None:
    """Decision 55: the local checks still pass it, the offline planner takes over, nothing
    unchecked reaches Meta, and the story is "not yet AI-checked"."""
    fake = use_meta(client)
    fake.replies["safety_verdicts"] = server_error()
    comic_id = new_comic(client)

    res = plan(client, comic_id, "scenes")

    assert res.status_code == 200 and res.json()["fallback"] is True
    assert fake.calls_for("scene_plan") == []
    assert f"comic:{comic_id}" in verdicts(client, "pending")
    assert client.get(f"/api/comics/{comic_id}").json()["text_check"] == "pending"
    panels = plan(client, comic_id, "panels").json()["panels"]
    assert fake.calls_for("panel_plan") == []
    assert {p["text_check"] for p in panels} == {"pending"}


def test_the_local_checks_still_block_during_an_outage(client: TestClient) -> None:
    fake = use_meta(client)
    fake.replies["safety_verdicts"] = server_error()
    comic_id = new_comic(client, synopsis="Mira calls 07700 900 123 to find the mango.")

    res = plan(client, comic_id, "scenes")

    assert (res.status_code, res.json()["field"]) == (422, "synopsis")


def test_pending_story_text_is_rechecked_when_meta_is_back(client: TestClient) -> None:
    fake = use_meta(client)
    fake.replies["safety_verdicts"] = server_error()
    comic_id = new_comic(client)
    plan(client, comic_id, "scenes")
    plan(client, comic_id, "panels")
    state = app_state(client)

    assert recheck.recheck_all(state.engine, state.llm) == 0  # still resting: nothing settles

    del fake.replies["safety_verdicts"]  # Meta is back: everything is safe
    assert recheck.recheck_all(state.engine, state.llm) == 7  # the comic and its 6 panels
    comic = client.get(f"/api/comics/{comic_id}").json()
    assert comic["text_check"] == "checked"
    assert {p["text_check"] for p in comic["panels"]} == {"checked"}


def test_a_later_block_shows_under_the_field(client: TestClient) -> None:
    fake = use_meta(client)
    fake.replies["safety_verdicts"] = server_error()
    comic_id = new_comic(client)
    plan(client, comic_id, "scenes")
    fake.replies["safety_verdicts"] = {
        "verdicts": [{"safe": True, "categories": []}, {"safe": False, "categories": ["bullying"]}]
    }

    state = app_state(client)
    recheck.recheck_all(state.engine, state.llm)

    comic = client.get(f"/api/comics/{comic_id}").json()
    assert comic["text_check"] == "blocked"
    assert [n["field"] for n in comic["safety_notes"]] == ["synopsis"]


def test_scene_summaries_are_checked_before_planning_panels(client: TestClient) -> None:
    comic_id = new_comic(client)
    scenes = plan(client, comic_id, "scenes").json()["scenes"]
    scenes[1]["summary"] = "Raju's email is raju@example.com"
    body = [{k: s[k] for k in ("id", "background_id", "character_ids", "summary")} for s in scenes]
    client.put(f"/api/comics/{comic_id}/scenes", json=body)

    res = plan(client, comic_id, "panels")

    assert res.status_code == 422
    assert res.json()["field"] == f"scenes.{scenes[1]['id']}.summary"
    assert res.json()["message"] == safety.SECRET_EMAIL


def test_bubble_text_is_checked_on_save_and_names_the_bubble(client: TestClient) -> None:
    comic_id = new_comic(client)
    plan(client, comic_id, "scenes")
    panel = plan(client, comic_id, "panels").json()["panels"][1]
    bubble = panel["bubbles"][0]

    res = client.patch(
        f"/api/panels/{panel['id']}", json={"bubbles": [{**bubble, "text": "Grab the gun!"}]}
    )

    assert res.status_code == 422 and res.json()["code"] == "unsafe"
    assert res.json()["field"] == f"bubbles.{bubble['id']}.text"
    saved = client.get(f"/api/comics/{comic_id}").json()["panels"][1]["bubbles"][0]["text"]
    assert saved == bubble["text"]  # nothing unsafe was saved


def test_bubble_words_saved_during_an_outage_are_pending(client: TestClient) -> None:
    comic_id = new_comic(client)
    plan(client, comic_id, "scenes")
    panel = plan(client, comic_id, "panels").json()["panels"][1]
    bubble = panel["bubbles"][0]
    fake = use_meta(client)
    fake.replies["safety_verdicts"] = server_error()

    res = client.patch(
        f"/api/panels/{panel['id']}", json={"bubbles": [{**bubble, "text": "Hello!"}]}
    )

    assert res.status_code == 200 and res.json()["text_check"] == "pending"
    assert res.json()["bubbles"][0]["text"] == "Hello!"
    # Unsafe words are still caught by the local checks while the classifier rests.
    bad = client.patch(
        f"/api/panels/{panel['id']}", json={"bubbles": [{**bubble, "text": "Grab the gun!"}]}
    )
    assert bad.status_code == 422
    # Once Meta answers, the next save checks every bubble of a pending panel.
    del fake.replies["safety_verdicts"]
    res = client.patch(
        f"/api/panels/{panel['id']}", json={"bubbles": [{**bubble, "text": "Hello again!"}]}
    )
    assert res.json()["text_check"] == "checked"
