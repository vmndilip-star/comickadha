"""Safety on story text: blocks name the exact field, personal info stays secret, fails closed."""

from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, col, select

from app.models import ModerationLog
from app.services import safety
from tests.conftest import IDS, app_state
from tests.fakes import server_error, use_meta

GOOD = "Mira and Raju follow sticky footprints to the school garden and find the mango."


def new_comic(client: TestClient, synopsis: str = GOOD, title: str = "Mango") -> str:
    comic_id: str = client.post("/api/comics", json={"title": title, "synopsis": synopsis}).json()[
        "id"
    ]
    client.patch(f"/api/comics/{comic_id}", json={"cast_ids": [IDS["mira"], IDS["raju"]]})
    return comic_id


def plan(client: TestClient, comic_id: str, what: str) -> Any:
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
    fake.replies["safety_verdicts"] = {
        "verdicts": [{"safe": True, "categories": []}, {"safe": False, "categories": ["bullying"]}]
    }
    comic_id = new_comic(client, synopsis="Mira is mean to Raju all day long.")

    res = plan(client, comic_id, "scenes")

    assert (res.status_code, res.json()["field"]) == (422, "synopsis")
    assert fake.calls_for("scene_plan") == []
    assert (f"comic:{comic_id}", ["bullying"]) in blocks(client)


def test_a_classifier_error_blocks_too(client: TestClient) -> None:
    """Fails closed: if the story can't be checked, it isn't planned (and never reaches Meta)."""
    fake = use_meta(client)
    fake.replies["safety_verdicts"] = server_error()
    comic_id = new_comic(client)

    res = plan(client, comic_id, "scenes")

    assert (res.status_code, res.json()["code"], res.json()["field"]) == (422, "unsafe", "title")
    assert res.json()["message"] == safety.CHECKER_RESTING
    assert fake.calls_for("scene_plan") == []
    assert (f"comic:{comic_id}", ["unavailable"]) in blocks(client)


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


def test_bubble_classifier_errors_fail_closed(client: TestClient) -> None:
    comic_id = new_comic(client)
    plan(client, comic_id, "scenes")
    panel = plan(client, comic_id, "panels").json()["panels"][1]
    bubble = panel["bubbles"][0]
    fake = use_meta(client)
    fake.replies["safety_verdicts"] = server_error()

    res = client.patch(
        f"/api/panels/{panel['id']}", json={"bubbles": [{**bubble, "text": "Hello!"}]}
    )

    assert res.status_code == 422 and res.json()["message"] == safety.CHECKER_RESTING
    # Unchanged words aren't re-checked: moving a character still works while the checker rests.
    moved = [{**panel["characters"][0], "position": "center"}]
    assert client.patch(f"/api/panels/{panel['id']}", json={"characters": moved}).status_code == 200
