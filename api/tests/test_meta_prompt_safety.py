"""Every kid-written word a Meta prompt carries is classified before the prompt is sent (Phase 6a,
services/kid_fields.py): cast names and catchphrases, place names and descriptions, the story,
scene summaries, the Lab's catchphrase and the Create flow's name."""

from typing import Any

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.avatar import spec as avatar_spec
from app.models import Background, Character, ModerationLog, Scene
from app.services import story_planner
from app.services.story_buddy import BuddyContext, _prompt, buddy_fields
from tests.conftest import IDS, app_state
from tests.fakes import FakeMeta, flag, server_error, use_meta, user_text

GOOD = "Mira and Raju follow sticky footprints to the school garden and find the mango."


def new_comic(client: TestClient, title: str = "Mango", synopsis: str = GOOD) -> str:
    comic_id: str = client.post("/api/comics", json={"title": title, "synopsis": synopsis}).json()[
        "id"
    ]
    client.patch(f"/api/comics/{comic_id}", json={"cast_ids": [IDS["mira"], IDS["raju"]]})
    return comic_id


def plan(client: TestClient, comic_id: str, what: str = "scenes") -> Any:
    return client.post(f"/api/studio/{comic_id}/plan-{what}", json={})


def buddy(client: TestClient, comic_id: str, action: str = "idea", text: str = "") -> Any:
    body = {"action": action, "text": text, "comic_id": comic_id}
    return client.post("/api/studio/buddy", json=body)


def checked_texts(fake: FakeMeta) -> str:
    return "\n".join(user_text(c) for c in fake.calls_for("safety_verdicts"))


def edit_row(client: TestClient, model: type[Any], row_id: str, **changes: Any) -> None:
    """Changes a saved row directly, as if it was saved or locked while Meta was off."""
    with Session(app_state(client).engine) as session:
        row = session.get(model, row_id)
        for key, value in changes.items():
            setattr(row, key, value)
        session.add(row)
        session.commit()


def set_catchphrase(client: TestClient, character_id: str, catchphrase: str) -> None:
    with Session(app_state(client).engine) as session:
        character = session.get(Character, character_id)
        assert character is not None
        spec = dict(character.spec)
        spec["personality"] = {**spec["personality"], "catchphrase": catchphrase}
        character.spec = spec
        session.add(character)
        session.commit()


# ---- the planner -------------------------------------------------------------------------------


def test_the_planner_checks_cast_and_places_before_meta(client: TestClient) -> None:
    fake = use_meta(client)
    fake.replies["scene_plan"] = server_error()  # the plan itself doesn't matter here
    comic_id = new_comic(client)

    assert plan(client, comic_id).status_code == 200

    texts = checked_texts(fake)
    for word in [
        "Mango",
        GOOD,
        "Mira",
        "Raju",
        "Adventure is my middle name!",
        "Grandma's kitchen",
    ]:
        assert word in texts, word
    # One classifier call for the whole prompt, before the planner call.
    assert [c["response_format"]["json_schema"]["name"] for c in fake.calls][:2] == [
        "safety_verdicts",
        "scene_plan",
    ]


KITCHEN_WORDS = "A kitchen where monsters lurk."


def block_kitchen(client: TestClient) -> tuple[FakeMeta, str]:
    """Grandma's kitchen was locked while Meta was off; now the classifier doesn't like it."""
    edit_row(client, Background, IDS["kitchen"], description=KITCHEN_WORDS)
    fake = use_meta(client)
    fake.replies["safety_verdicts"] = flag("monsters lurk", "scary")
    name: str = client.get(f"/api/backgrounds/{IDS['kitchen']}").json()["name"]
    return fake, name


def place_blocks(client: TestClient) -> list[str]:
    with Session(app_state(client).engine) as session:
        stmt = select(ModerationLog).where(ModerationLog.verdict == "block")
        return [row.target for row in session.exec(stmt)]


def test_a_blocked_place_is_left_out_of_both_plans_with_a_note(client: TestClient) -> None:
    fake, kitchen = block_kitchen(client)
    # Meta's plans fail, so the offline planner plans: the place must be out of both.
    fake.replies["scene_plan"] = server_error()
    fake.replies["panel_plan"] = server_error()
    comic_id = new_comic(client)

    scenes = plan(client, comic_id)

    assert scenes.status_code == 200, scenes.json()
    assert scenes.json()["left_out_places"] == [kitchen]
    assert all(s["background_id"] != IDS["kitchen"] for s in scenes.json()["scenes"])
    scene_prompt = user_text(fake.calls_for("scene_plan")[0])
    assert kitchen not in scene_prompt and "monsters" not in scene_prompt
    assert f"background:{IDS['kitchen']}" in place_blocks(client)

    panels = plan(client, comic_id, "panels")

    assert panels.status_code == 200, panels.json()
    assert panels.json()["left_out_places"] == [kitchen]
    assert all(p["background_id"] != IDS["kitchen"] for p in panels.json()["panels"])
    panel_prompt = user_text(fake.calls_for("panel_plan")[0])
    assert kitchen not in panel_prompt and "monsters" not in panel_prompt


def test_a_classifier_outage_leaves_no_place_out(client: TestClient) -> None:
    """An outage isn't a block (decision 55): places that passed the local checks stay in the
    offline plan, with no "didn't like its words" note, even words the classifier would block."""
    edit_row(client, Background, IDS["kitchen"], description=KITCHEN_WORDS)
    fake = use_meta(client)
    fake.replies["safety_verdicts"] = server_error()
    synopsis = (
        "Mira and Raju bake cookies in Grandma's kitchen, then share them in the school garden."
    )
    comic_id = new_comic(client, synopsis=synopsis)

    scenes = plan(client, comic_id)

    assert scenes.status_code == 200, scenes.json()
    assert scenes.json()["left_out_places"] == []
    assert (scenes.json()["source"], scenes.json()["fallback"]) == ("mock", True)
    used = {s["background_id"] for s in scenes.json()["scenes"]}
    assert {IDS["kitchen"], IDS["garden"]} <= used  # the offline plan uses them
    assert fake.calls_for("scene_plan") == []
    assert f"background:{IDS['kitchen']}" not in place_blocks(client)

    panels = plan(client, comic_id, "panels")

    assert panels.status_code == 200, panels.json()
    assert panels.json()["left_out_places"] == []
    assert IDS["kitchen"] in {p["background_id"] for p in panels.json()["panels"]}


def test_a_place_failing_the_word_list_is_left_out_offline_too(client: TestClient) -> None:
    edit_row(client, Background, IDS["kitchen"], description="A kitchen full of beer bottles.")
    comic_id = new_comic(client)

    res = plan(client, comic_id)

    assert res.status_code == 200
    kitchen = client.get(f"/api/backgrounds/{IDS['kitchen']}").json()["name"]
    assert res.json()["left_out_places"] == [kitchen]
    assert all(s["background_id"] != IDS["kitchen"] for s in res.json()["scenes"])


def test_a_scene_at_a_blocked_place_has_to_change_place(client: TestClient) -> None:
    comic_id = new_comic(client)
    scenes = plan(client, comic_id).json()["scenes"]  # offline, before the place is blocked
    edit_row(client, Scene, scenes[0]["id"], background_id=IDS["kitchen"])
    fake, kitchen = block_kitchen(client)

    res = plan(client, comic_id, "panels")

    assert (res.status_code, res.json()["field"]) == (422, f"scenes.{scenes[0]['id']}")
    assert kitchen in res.json()["message"] and "Pick another place" in res.json()["message"]
    assert fake.calls_for("panel_plan") == []


def test_with_every_place_blocked_there_is_nothing_to_plan(client: TestClient) -> None:
    for place in ("kitchen", "garden", "space"):
        edit_row(client, Background, IDS[place], description="Somewhere zzbad.")
    fake = use_meta(client)
    fake.replies["safety_verdicts"] = flag("zzbad")
    comic_id = new_comic(client)

    res = plan(client, comic_id)

    assert (res.status_code, res.json()["code"], res.json()["field"]) == (
        409,
        "needs_locked",
        "places",
    )
    assert "Delete it and describe a new place" in res.json()["message"]
    assert fake.calls_for("scene_plan") == []


def test_the_buddy_leaves_a_place_with_a_blocked_name_out_of_its_prompt(
    client: TestClient,
) -> None:
    # The Buddy's prompt has place names only, so only a blocked name keeps a place out of it.
    edit_row(client, Background, IDS["kitchen"], name="Zzbad Kitchen")
    fake = use_meta(client)
    fake.replies["safety_verdicts"] = flag("Zzbad")
    fake.replies["buddy_idea"] = {"questions": ["Where do they go first?"], "reply": "Ooh!"}
    comic_id = new_comic(client)

    res = buddy(client, comic_id, text="They look for clues.")

    assert res.status_code == 200 and res.json()["source"] == "meta"
    prompt = user_text(fake.calls_for("buddy_idea")[0])
    assert "Zzbad" not in prompt and "School garden" in prompt


def test_a_blocked_catchphrase_blocks_planning_and_names_the_character(
    client: TestClient,
) -> None:
    set_catchphrase(client, IDS["raju"], "Snack break or I bite!")
    fake = use_meta(client)
    fake.replies["safety_verdicts"] = flag("I bite", "violence")
    comic_id = new_comic(client)

    res = plan(client, comic_id)

    assert (res.status_code, res.json()["field"]) == (422, f"cast.{IDS['raju']}.catchphrase")
    assert "Raju's catchphrase" in res.json()["message"]
    assert fake.calls_for("scene_plan") == []


def test_a_blocked_cast_name_is_not_repeated_back(client: TestClient) -> None:
    edit_row(client, Character, IDS["raju"], name="Raju the Terrible")
    fake = use_meta(client)
    fake.replies["safety_verdicts"] = flag("Terrible")
    comic_id = new_comic(client)

    res = plan(client, comic_id)

    assert res.json()["field"] == f"cast.{IDS['raju']}.name"
    assert "Terrible" not in res.json()["message"]
    assert "second character in your cast" in res.json()["message"]


def test_panel_planning_checks_everything_again(client: TestClient) -> None:
    fake = use_meta(client)
    comic_id = new_comic(client)
    fake.replies["scene_plan"] = server_error()
    assert plan(client, comic_id).status_code == 200
    set_catchphrase(client, IDS["mira"], "Hand over your lunch money!")
    fake.replies["safety_verdicts"] = flag("lunch money", "bullying")

    res = plan(client, comic_id, "panels")

    assert (res.status_code, res.json()["field"]) == (422, f"cast.{IDS['mira']}.catchphrase")
    assert fake.calls_for("panel_plan") == []


def test_a_classifier_outage_plans_offline_with_nothing_sent(client: TestClient) -> None:
    set_catchphrase(client, IDS["raju"], "Never checked by the classifier")
    fake = use_meta(client)
    fake.replies["safety_verdicts"] = server_error()
    comic_id = new_comic(client)

    res = plan(client, comic_id)

    assert res.status_code == 200
    assert (res.json()["source"], res.json()["fallback"]) == ("mock", True)
    assert fake.calls_for("scene_plan") == []


def test_planner_fields_cover_every_kid_word_in_the_prompt() -> None:
    ctx = story_planner.StoryContext(
        "The Title",
        "The synopsis words.",
        "funny",
        4,
        [story_planner.CastMember("c1", "Zed", 1, "Zoom zoom!", ("brave",))],
        [story_planner.Place("p1", "Moon Base", "Craters everywhere.")],
        [story_planner.SceneInfo("s1", "p1", ("c1",), "Zed lands on the moon.")],
    )
    fields = story_planner.planner_fields(ctx).texts
    prompt = "\n".join(story_planner.story_lines(ctx))

    kid_words = ["The Title", "The synopsis words.", "Zed", "Zoom zoom!", "Moon Base"]
    kid_words.append("Craters everywhere.")
    assert all(w in prompt for w in kid_words)
    assert set(kid_words) | {"Zed lands on the moon."} == set(fields.values())


# ---- Story Buddy -------------------------------------------------------------------------------


def test_buddy_classifies_a_pending_title_before_meta_sees_it(client: TestClient) -> None:
    fake = use_meta(client)
    comic_id = new_comic(client, title="Raju's Secret Snack Stash")
    # Autosave never calls Meta (decision 55): the title is only locally checked so far.
    assert fake.calls == []
    fake.replies["buddy_idea"] = {"questions": ["Who hid the snacks?"], "reply": "Ooh!"}

    res = buddy(client, comic_id, text="Raju finds a map.")

    assert res.status_code == 200 and res.json()["source"] == "meta"
    names = [c["response_format"]["json_schema"]["name"] for c in fake.calls]
    assert names[0] == "safety_verdicts" and "buddy_idea" in names
    first_check = user_text(fake.calls[0])
    for word in ["Raju's Secret Snack Stash", "Raju finds a map.", "Mira", "School garden"]:
        assert word in first_check, word


def test_buddy_with_an_unchecked_title_and_an_outage_stays_offline(client: TestClient) -> None:
    fake = use_meta(client)
    comic_id = new_comic(client, title="Raju's Secret Snack Stash")
    fake.replies["safety_verdicts"] = server_error()

    res = buddy(client, comic_id, "name_scene", "They find the snacks")

    assert res.status_code == 200
    assert (res.json()["source"], res.json()["fallback"]) == ("mock", True)
    assert fake.calls_for("buddy_name_scene") == []


def test_a_blocked_title_stops_the_buddy_and_names_the_title(client: TestClient) -> None:
    fake = use_meta(client)
    comic_id = new_comic(client, title="Raju Gets Revenge")
    fake.replies["safety_verdicts"] = flag("Revenge", "violence")

    res = buddy(client, comic_id, text="What happens next?")

    assert (res.status_code, res.json()["field"]) == (422, "title")
    assert "the title" in res.json()["message"]
    assert fake.calls_for("buddy_idea") == []


def test_the_buddy_prompt_has_no_synopsis_and_its_fields_match() -> None:
    ctx = BuddyContext(
        "A Title", "SECRET SYNOPSIS", "funny", ["Zed"], ["Moon Base"], ["c1"], ["p1"]
    )
    prompt = _prompt("my words", ctx)

    assert "SECRET SYNOPSIS" not in prompt
    texts = buddy_fields("my words", ctx).texts
    assert set(texts.values()) == {"my words", "A Title", "Zed", "Moon Base"}
    assert all(t in prompt for t in texts.values())


# ---- the Lab helper and the Create flow --------------------------------------------------------

KID = avatar_spec.validate({"body_type": "kid"})


def with_catchphrase(catchphrase: str) -> dict[str, Any]:
    return {**KID, "personality": {"traits": [], "catchphrase": catchphrase}}


def test_the_lab_checks_the_catchphrase_it_sends_to_meta(client: TestClient) -> None:
    fake = use_meta(client)
    fake.replies["safety_verdicts"] = flag("punch", "violence")
    spec = with_catchphrase("I punch first!")

    for path, body in [
        ("describe", {"text": "a kid with a red cap", "spec": spec}),
        ("surprise", {"spec": spec}),
        ("ideas", {"spec": spec, "name": "Zara"}),
    ]:
        res = client.post(f"/api/builder/{path}", json=body)
        assert (res.status_code, res.json()["field"]) == (422, "catchphrase"), path
        assert "catchphrase" in res.json()["message"]
    assert fake.calls_for("avatar_suggestion") == fake.calls_for("character_ideas") == []


def test_surprise_with_no_kid_words_makes_no_classifier_call(client: TestClient) -> None:
    fake = use_meta(client)
    fake.replies["avatar_suggestion"] = server_error()

    client.post("/api/builder/surprise", json={"spec": KID})

    assert fake.calls_for("safety_verdicts") == []


def test_create_checks_the_name_it_sends_to_meta(client: TestClient) -> None:
    fake = use_meta(client)
    fake.replies["safety_verdicts"] = flag("Stinky", "bullying")

    res = client.post(
        "/api/builder/create",
        json={"kind": "person", "name": "Stinky Sam", "description": "a kid with a big smile"},
    )

    assert (res.status_code, res.json()["field"]) == (422, "name")
    assert fake.calls_for("character_create") == []
