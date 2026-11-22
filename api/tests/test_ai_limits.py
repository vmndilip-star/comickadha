"""Every Meta call site sends its max_tokens and timeout from services/ai_limits.py."""

from typing import Any

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.avatar import spec as avatar_spec
from app.seed import USER_ID
from app.services import safety
from app.services.ai_limits import LIMITS
from tests.conftest import IDS, app_state
from tests.fakes import FakeMeta, data_url, drawing, scene_png, server_error, use_meta

KID = avatar_spec.validate({"body_type": "kid"})
SCHEMAS = [
    "avatar_suggestion",
    "character_ideas",
    "drawing_suggestion",
    "character_create",
    "buddy_idea",
    "buddy_spelling",
    "buddy_name_scene",
    "scene_plan",
    "panel_plan",
]


def sent(fake: FakeMeta, schema_name: str) -> list[tuple[int, float]]:
    return [(c["max_tokens"], c["timeout"]) for c in fake.calls_for(schema_name)]


def expected(call: str) -> tuple[int, float]:
    return (LIMITS[call].max_tokens, LIMITS[call].timeout)


def run(fake: FakeMeta, schema_name: str, request: Any) -> list[tuple[int, float]]:
    """The limits of the calls one request made with this schema."""
    before = len(fake.calls_for(schema_name))
    request()
    return sent(fake, schema_name)[before:]


def test_every_call_site_sends_its_limits(client: TestClient) -> None:
    fake = use_meta(client)
    for name in SCHEMAS:
        fake.replies[name] = server_error()  # the reply doesn't matter, only what was sent
    post = client.post
    comic = IDS["mango"]

    describe = run(
        fake,
        "avatar_suggestion",
        lambda: post("/api/builder/describe", json={"text": "a kid in a red cap", "spec": KID}),
    )
    surprise = run(
        fake, "avatar_suggestion", lambda: post("/api/builder/surprise", json={"spec": KID})
    )
    ideas = run(
        fake,
        "character_ideas",
        lambda: post("/api/builder/ideas", json={"spec": KID, "name": "Zara"}),
    )
    client.put("/api/me/drawing-consent", json={"a": 7, "b": 8, "answer": 56})
    from_drawing = run(
        fake,
        "drawing_suggestion",
        lambda: post("/api/builder/from-drawing", json={"image": data_url(drawing()), "spec": KID}),
    )
    create = run(
        fake,
        "character_create",
        lambda: post(
            "/api/builder/create", json={"kind": "person", "description": "a kid with a big smile"}
        ),
    )
    buddy = {
        action: run(
            fake,
            f"buddy_{action}",
            lambda a=action: post(
                "/api/studio/buddy",
                json={"action": a, "text": "Mira looks for the mango.", "comic_id": comic},
            ),
        )
        for action in ("idea", "spelling", "name_scene")
    }
    comic_id = post(
        "/api/comics",
        json={"title": "Mango", "synopsis": "Mira and Raju look for the lost mango in the garden."},
    ).json()["id"]
    client.patch(f"/api/comics/{comic_id}", json={"cast_ids": [IDS["mira"], IDS["raju"]]})
    scenes = run(fake, "scene_plan", lambda: post(f"/api/studio/{comic_id}/plan-scenes", json={}))
    panels = run(fake, "panel_plan", lambda: post(f"/api/studio/{comic_id}/plan-panels", json={}))
    with Session(app_state(client).engine) as session:
        safety.check_image(session, USER_ID, "test", scene_png(), app_state(client).llm)

    assert describe == [expected("describe")]
    assert surprise == [expected("surprise")]
    assert ideas == [expected("ideas")]
    assert from_drawing == [expected("from_drawing")]
    assert create == [expected("create")]
    assert {a: calls for a, calls in buddy.items()} == {
        a: [expected(f"buddy_{a}")] for a in ("idea", "spelling", "name_scene")
    }
    assert scenes == [expected("plan_scenes")]
    assert panels == [expected("plan_panels")]
    classifier = sent(fake, "safety_verdicts")
    assert classifier and set(classifier) == {expected("classifier")}
    assert sent(fake, "image_safety") == [expected("image_check")]
    image_call = fake.calls_for("image_safety")[0]
    assert image_call["model"] == "muse-vision-test"  # the vision model
