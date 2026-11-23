"""The API side of the guided Create character flow: follow-up answers refine the same character
(the look field and the drift guard), role suggestions, and saving the result."""

from typing import Any

from fastapi.testclient import TestClient

from app.avatar import spec as avatar_spec
from app.services.safety import REAL_PERSON
from tests.conftest import own_cast
from tests.fakes import server_error, suggestion, use_meta

GINGER = {"target": "colors.hair", "value": "ginger"}


def create(client: TestClient, **body: Any) -> Any:
    return client.post("/api/builder/create", json={"kind": "person", **body})


def hex_of(slot: str, colour_id: str, body: str = "kid") -> str:
    return next(e["hex"] for e in avatar_spec.palette(slot, body) if e["id"] == colour_id)


def meta_reply(**changes: Any) -> dict[str, Any]:
    reply = suggestion(avatar_spec.validate({"body_type": "kid"}))
    reply.pop("body_type")
    reply |= {
        "traits": ["brave", "kind"],
        "intro_line": "Meet Nova, a brave kid!",
        "role_suggestion": "hero",
        "follow_up": {"question": "", "options": []},
    }
    return reply | changes


# ---- the look field ---------------------------------------------------------------------------


def test_a_look_only_comes_with_an_answer(client: TestClient) -> None:
    look = avatar_spec.validate({"body_type": "kid"})
    res = create(client, look=look)
    assert (res.status_code, res.json()["field"]) == (422, "look")


def test_a_look_is_checked_like_a_saved_one(client: TestClient) -> None:
    look = avatar_spec.validate({"body_type": "kid"})
    look["parts"]["top"] = "toga"
    res = create(client, look=look, follow_up_answer=GINGER)
    assert (res.status_code, res.json()["code"], res.json()["field"]) == (
        422,
        "unknown_part",
        "look",
    )
    robot = avatar_spec.validate({"body_type": "robot"})
    res = create(client, look=robot, follow_up_answer=GINGER)
    assert (res.status_code, res.json()["field"]) == (422, "look")


def test_answering_offline_keeps_the_same_character(client: TestClient) -> None:
    first = create(client, age="big_kid").json()

    second = create(client, age="big_kid", look=first["spec"], follow_up_answer=GINGER).json()

    expected = {
        **first["spec"],
        "colors": {**first["spec"]["colors"], "hair": hex_of("hair", "ginger")},
    }
    assert second["spec"] == expected
    assert second["follow_up"] is None


def test_a_follow_up_answer_never_asks_meta_again(client: TestClient) -> None:
    """Live test 2: a second Meta design took about 40 s to change only the eyes. The answer is
    applied with apply_choice: nothing else changes and nothing is sent to Meta."""
    look = avatar_spec.validate({"body_type": "kid"})
    look["personality"] = {"traits": ["calm", "honest"], "catchphrase": "Pickled onions forever"}
    look["extras"] = ["backpack"]
    fake = use_meta(client)

    made = create(client, look=look, follow_up_answer=GINGER).json()

    spec = made["spec"]
    assert spec["parts"] == look["parts"] and spec["extras"] == ["backpack"]
    assert {k: v for k, v in spec["colors"].items() if k != "hair"} == {
        k: v for k, v in look["colors"].items() if k != "hair"
    }
    assert spec["colors"]["hair"] == hex_of("hair", "ginger")
    assert spec["personality"] == look["personality"]  # the first answer's words stay
    assert fake.calls == []  # no design call, and no classifier call either: nothing sent
    assert made["follow_up"] is None


# ---- the intro line and name ideas (live test 2) ----------------------------------------------


def test_the_intro_line_introduces_the_kids_name(client: TestClient) -> None:
    fake = use_meta(client)
    fake.replies["character_create"] = meta_reply(intro_line="Meet Nova, a brave kid!")

    made = create(client, name="Sniffy").json()

    assert made["intro_line"] == "Meet Sniffy, a brave kid!"


def test_name_ideas_never_repeat_a_name_in_use(client: TestClient) -> None:
    """Live test 2: "Biscuit" (a starter) was suggested. Names in use: the kid's cast and the
    starters, Meta's ideas and the offline helper's alike; the intro follows the first idea."""
    fake = use_meta(client)
    fake.replies["character_create"] = meta_reply(
        name_ideas=["Biscuit", "Mira", "Juno"], intro_line="Meet Biscuit, the best sniffer!"
    )

    made = create(client).json()

    in_use = {c["name"].lower() for c in client.get("/api/characters").json()}
    assert made["name_ideas"][0] == "Juno" and len(made["name_ideas"]) == 3
    assert not {n.lower() for n in made["name_ideas"]} & in_use
    assert made["intro_line"] == "Meet Juno, the best sniffer!"


def test_offline_name_ideas_skip_starters_and_the_kids_cast(client: TestClient) -> None:
    robo = next(c for c in own_cast(client) if c["name"] == "Robo-Tik")
    assert client.patch(f"/api/characters/{robo['id']}", json={"name": "Rocket"}).status_code == 200

    seen: set[str] = set()
    for i in range(12):
        made = client.post(
            "/api/builder/create", json={"kind": "dog", "description": f"a fluffy dog number {i}"}
        ).json()
        seen |= set(made["name_ideas"])
        assert len(made["name_ideas"]) == 3
    assert "Biscuit" not in seen and "Rocket" not in seen  # a starter and the kid's own


def test_lab_name_ideas_skip_names_in_use(client: TestClient) -> None:
    dog = avatar_spec.validate({"body_type": "dog"})
    for _ in range(12):
        offline = client.post("/api/builder/ideas", json={"spec": dog, "name": ""}).json()
        assert "Biscuit" not in offline["name_ideas"] and len(offline["name_ideas"]) == 3
    fake = use_meta(client)
    fake.replies["character_ideas"] = {
        "name_ideas": ["Biscuit", "Whiskers", "Nova"],
        "traits": ["kind"],
        "catchphrase": "Woof!",
        "reply": "How about these?",
    }

    meta = client.post("/api/builder/ideas", json={"spec": dog, "name": ""}).json()

    assert meta["name_ideas"][0] == "Nova" and len(meta["name_ideas"]) == 3
    assert not {"Biscuit", "Whiskers"} & set(meta["name_ideas"])


def test_a_dress_answer_brings_its_leggings(client: TestClient) -> None:
    first = create(client).json()
    dress = {"target": "top", "value": "dress"}
    made = create(client, look=first["spec"], follow_up_answer=dress).json()
    assert made["spec"]["parts"]["top"] == "dress" and made["spec"]["parts"]["bottom"] == "leggings"


# ---- role suggestions -------------------------------------------------------------------------


def test_offline_suggests_a_role_from_the_traits(client: TestClient) -> None:
    made = create(client, description="a brave kid in a red raincoat").json()
    assert "brave" in made["spec"]["personality"]["traits"]
    assert made["role_suggestion"] == "hero"


def test_metas_role_is_used_when_it_is_a_real_role(client: TestClient) -> None:
    fake = use_meta(client)
    fake.replies["character_create"] = meta_reply(role_suggestion="sidekick")
    assert create(client).json()["role_suggestion"] == "sidekick"
    fake.replies["character_create"] = meta_reply(role_suggestion="villain", traits=["caring"])
    assert create(client).json()["role_suggestion"] == "sidekick"  # from "caring"


# ---- saving the result ------------------------------------------------------------------------


def free_a_slot(client: TestClient) -> None:
    for c in own_cast(client)[1:]:
        client.delete(f"/api/characters/{c['id']}")


def test_creating_a_character_checks_the_name(client: TestClient) -> None:
    free_a_slot(client)
    res = client.post("/api/characters", json={"name": "Taylor Swift"})
    assert (res.status_code, res.json()["field"], res.json()["message"]) == (
        422,
        "name",
        REAL_PERSON,
    )


def test_designed_by_stays_until_the_look_is_edited(client: TestClient) -> None:
    free_a_slot(client)
    spec = create(client).json()["spec"]
    made = client.post(
        "/api/characters", json={"name": "Nova", "spec": spec, "designed_by": "meta"}
    )
    assert made.status_code == 201, made.json()
    cid = made.json()["id"]
    assert made.json()["designed_by"] == "meta"

    renamed = client.patch(f"/api/characters/{cid}", json={"name": "Nova Star"}).json()
    assert renamed["designed_by"] == "meta"  # a new name doesn't change who designed the look
    same = client.patch(f"/api/characters/{cid}", json={"spec": spec}).json()
    assert same["designed_by"] == "meta"  # saving the same look isn't an edit
    spec["parts"]["hair"] = "curly"
    edited = client.patch(f"/api/characters/{cid}", json={"spec": spec}).json()
    assert edited["designed_by"] is None


def test_helper_info_reports_the_last_meta_call(client: TestClient) -> None:
    fake = use_meta(client)
    assert client.get("/api/builder/info").json()["last_call"] is None

    fake.replies["character_create"] = meta_reply()
    create(client)
    last = client.get("/api/builder/info").json()["last_call"]
    assert last["ok"] is True and last["error"] is None and last["at"]

    fake.replies["character_create"] = server_error()
    create(client)
    last = client.get("/api/builder/info").json()["last_call"]
    assert last["ok"] is False and last["error"] == "InternalServerError"
