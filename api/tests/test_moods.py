"""Story moods and comics up to 200 panels (decision 128)."""

from dataclasses import replace
from typing import get_args

from fastapi.testclient import TestClient

from app.moods import MOODS, mood_info, mood_line
from app.schemas.common import Mood
from app.services.story_planner import offline_panels, story_lines
from tests.conftest import plan_panels
from tests.fakes import use_meta
from tests.test_long_comics import ctx
from tests.test_studio import new_comic


def test_every_mood_has_its_entry_and_fits_the_database() -> None:
    assert set(MOODS) == set(get_args(Mood))
    for mood, info in MOODS.items():
        assert len(mood) <= 16, mood  # the comic table's mood column
        assert "{place}" in info.opener and len(info.closer.split()) <= 12, mood
        assert len(info.title_words) == 3 and all(q.endswith("?") for q in info.questions), mood


def test_prompts_get_what_the_mood_means() -> None:
    assert mood_line("pirate").startswith("pirate (treasure maps")
    assert "no weapons" in mood_line("pirate") and "nobody gets eaten" in mood_line("dinosaur")
    assert mood_line("robots_future").startswith("robots future (gadgets")
    lines = story_lines(replace(ctx(6), mood="space"))
    assert f"Mood: {mood_line('space')}" in lines


def test_the_story_buddy_tells_meta_the_mood(client: TestClient) -> None:
    fake = use_meta(client)
    comic_id = new_comic(client)
    assert client.patch(f"/api/comics/{comic_id}", json={"mood": "folk_tale"}).status_code == 200
    fake.replies["buddy_idea"] = {"questions": ["What lesson could Mira learn?"], "reply": "Hmm!"}
    body = {"action": "idea", "text": "Mira meets a clever crow.", "comic_id": comic_id}
    assert client.post("/api/studio/buddy", json=body).status_code == 200
    prompt = fake.calls_for("buddy_idea")[0]["messages"][1]["content"]
    assert "Panchatantra" in prompt


def test_the_offline_planner_opens_and_closes_in_the_mood() -> None:
    plan = offline_panels(replace(ctx(6), mood="space"))
    first, last = plan.panels[0].bubbles[0].text, plan.panels[-1].bubbles[0].text
    assert first.startswith("3, 2, 1") and last == mood_info("space").closer


def test_a_mood_the_table_doesnt_know_reads_as_adventure() -> None:
    assert mood_info("unknown") == MOODS["adventure"]


def test_a_comic_longer_than_thirty_panels_plans_exactly_that_many(client: TestClient) -> None:
    comic_id = new_comic(client, panel_count=45)
    assert client.patch(f"/api/comics/{comic_id}", json={"mood": "underwater"}).status_code == 200
    assert client.post(f"/api/studio/{comic_id}/plan-scenes", json={}).status_code == 200
    assert plan_panels(client, comic_id).status_code == 200
    panels = client.get(f"/api/comics/{comic_id}").json()["panels"]
    assert len(panels) == 45 and panels[0]["bubbles"][0]["text"].startswith("Deep down")
