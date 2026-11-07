"""Avatar specs: strict checks against the parts catalog, and the old-spec migration."""

from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.avatar import spec as avatar_spec
from app.avatar.catalog import load_catalog
from app.avatar.migrate import migrate_characters, migrate_spec
from app.config import Settings
from app.main import create_app
from app.models import Character
from app.seed import USER_ID
from tests.conftest import IDS, app_state

CAT = load_catalog()


def robo_path() -> str:
    return f"/api/characters/{IDS['robo']}"


def robo_spec(client: TestClient) -> dict[str, Any]:
    spec: dict[str, Any] = client.get(robo_path()).json()["spec"]
    return spec


# ---- strict validation through the API ------------------------------------------------------


@pytest.mark.parametrize(
    ("change", "says"),
    [
        ({"body_type": "kid", "parts": {"hair": "mohawk"}}, "We don't have that hair"),
        ({"body_type": "kid", "parts": {"tail": "fluffy"}}, "that kind of part"),
        ({"parts": {"hair": "bob"}}, "doesn't fit a robot"),
        ({"parts": {"nose": "button"}}, "doesn't fit a robot"),
        ({"parts": {"face_shape": "round"}}, "doesn't fit a robot"),
        ({"body_type": "cat", "parts": {"headwear": "hijab"}}, "doesn't fit a cat"),
        ({"colors": {"skin": "#9AD0F5", "top": "#123456"}}, "isn't in our paint box"),
        ({"colors": {"skin": "#EFC29B"}}, "isn't in our paint box"),  # human skin on a robot
        ({"colors": {"glitter": "#FFD23F"}}, "paint pot"),
        ({"extras": ["jetpack"]}, "We don't have that extra"),
        ({"extras": ["freckles"]}, "doesn't fit a robot"),
        ({"extras": ["glasses_round", "glasses_star"]}, "one pair of glasses"),
    ],
)
def test_a_spec_the_catalog_cannot_draw_is_422_unknown_part(
    client: TestClient, change: dict[str, Any], says: str
) -> None:
    before = robo_spec(client)

    res = client.patch(robo_path(), json={"spec": before | change})

    assert res.status_code == 422, res.json()
    assert res.json()["code"] == "unknown_part"
    assert says in res.json()["message"]
    assert robo_spec(client) == before  # nothing was saved


def test_a_new_character_with_a_bad_spec_is_refused(client: TestClient) -> None:
    client.delete(robo_path())  # make room in the cast

    res = client.post("/api/characters", json={"spec": {"parts": {"hair": "mohawk"}}})

    assert res.status_code == 422
    assert res.json()["code"] == "unknown_part"


def test_a_new_character_gets_a_full_default_spec_and_a_slot_colour(client: TestClient) -> None:
    client.delete(robo_path())

    zara = client.post("/api/characters", json={"name": "Zara"}).json()

    assert zara["spec"] == avatar_spec.validate(zara["spec"])  # already complete
    assert set(zara["spec"]["parts"]) == set(avatar_spec.categories_for("kid"))
    assert zara["spec"]["colors"]["card"] == avatar_spec.SLOT_CARDS[2]  # the third cast slot
    assert (zara["kind"], zara["role"]) == ("kid", "friend")


# ---- validate and normalize ----------------------------------------------------------------


def test_validate_fills_in_every_category_and_colour_for_the_body_type() -> None:
    for body_type, body in CAT["body_types"].items():
        spec = avatar_spec.validate({"body_type": body_type})

        assert spec["parts"] == {
            c: body["defaults"]["parts"].get(c) or avatar_spec.options_for(c, body_type)[0]
            for c in avatar_spec.categories_for(body_type)
        }
        assert set(spec["colors"]) == set(CAT["color_slots"])
        assert avatar_spec.validate(spec) == spec  # a full spec passes unchanged


def test_robots_and_animals_have_no_hair_or_nose() -> None:
    for body_type in ("robot", "cat", "dog", "bear"):
        assert {"hair", "nose"}.isdisjoint(avatar_spec.categories_for(body_type))


def test_normalize_swaps_what_does_not_fit_and_snaps_colours() -> None:
    spec = avatar_spec.normalize(
        {
            "body_type": "robot",
            "parts": {"hair": "bob", "face_shape": "nope", "top": "hoodie"},
            "colors": {"skin": "#0000FF", "top": "#FF0001", "bad": "#FFFFFF", "hair": "red"},
            "extras": ["freckles", "cape", "cape", "jetpack"],
            "mystery": True,
        }
    )

    assert spec == avatar_spec.validate(spec)
    assert "hair" not in spec["parts"]
    assert spec["parts"]["face_shape"] == "box"  # the robot default
    assert spec["parts"]["top"] == "hoodie"
    assert spec["colors"]["top"] == "#E53935"  # nearest cloth colour to #FF0001
    assert spec["colors"]["skin"] in {e["hex"] for e in avatar_spec.palette("skin", "robot")}
    assert spec["extras"] == ["cape"]


def test_describe_reads_like_a_prompt() -> None:
    spec = avatar_spec.validate(
        {"body_type": "kid", "parts": {"hair": "curly"}, "extras": ["cape"]}
    )

    text = avatar_spec.describe(spec)

    assert text.startswith("a kid with sand skin, curly dark brown hair")
    assert text.endswith("with a red cape")


# ---- migration from Phase 2/3 specs ----------------------------------------------------------

OLD_MIRA = {
    "skin": "#F2C29B",
    "hair_style": "bob",
    "hair_color": "#3B2314",
    "outfit": "Yellow raincoat with big pockets",
    "traits": ["brave", "curious"],
    "catchphrase": "Adventure is my middle name!",
    "tint": "#FFE9A8",
}
OLD_RAJU = {
    "skin": "#C98B5E",
    "hair_style": "spiky",
    "hair_color": "#1A1A1A",
    "outfit": "Green football jersey and red sneakers",
    "traits": ["funny", "loud"],
    "catchphrase": "Snack break? Snack break!",
    "tint": "#FFD0C2",
}


def test_an_old_spec_becomes_a_valid_builder_spec() -> None:
    spec = migrate_spec(OLD_MIRA, "kid", "hero")

    assert spec == avatar_spec.validate(spec)
    assert spec["body_type"] == "kid"
    assert spec["parts"]["hair"] == "bob"
    assert spec["parts"]["top"] == "raincoat"
    assert spec["colors"]["top"] == "#FFD23F"  # "yellow"
    assert spec["colors"]["skin"] == "#EFC29B"  # nearest skin swatch
    assert spec["colors"]["hair"] == "#3B2314"
    assert spec["colors"]["card"] == "#FFE9A8"  # the old tint
    assert spec["personality"] == {
        "traits": ["brave", "curious"],
        "catchphrase": "Adventure is my middle name!",
    }
    assert spec["role"] == "hero"


def test_colour_words_in_the_outfit_go_to_the_right_garment() -> None:
    spec = migrate_spec(OLD_RAJU, "kid", "sidekick")

    assert (spec["parts"]["top"], spec["colors"]["top"]) == ("jersey", "#3FA34D")
    assert (spec["parts"]["shoes"], spec["colors"]["shoes"]) == ("sneakers", "#E53935")
    assert spec["colors"]["hair"] == "#2B2B2B"


def test_old_robots_and_animals_lose_hair_and_animals_become_cats() -> None:
    robot = migrate_spec({**OLD_MIRA, "skin": "#9AD0F5"}, "robot", "friend")
    animal = migrate_spec(OLD_MIRA, "animal", "villain")

    assert robot["body_type"] == "robot" and "hair" not in robot["parts"]
    assert robot["colors"]["skin"] == "#9AD0F5"
    assert animal["body_type"] == "cat" and "hair" not in animal["parts"]
    assert animal["role"] == "friend"  # unknown roles fall back
    assert animal == avatar_spec.validate(animal)


def test_migration_converts_old_rows_once_and_running_it_again_changes_nothing(
    client: TestClient,
) -> None:
    engine = app_state(client).engine
    with Session(engine) as session:
        session.add(
            Character(
                id="old-raju",
                user_id=USER_ID,
                name="Old Raju",
                role="sidekick",
                kind="kid",
                spec=dict(OLD_RAJU),
            )
        )
        session.add(
            Character(
                id="old-cat",
                user_id=USER_ID,
                name="Old Cat",
                role="friend",
                kind="animal",
                spec={"skin": "#E8954F", "tint": "#FFD0C2", "outfit": "a cape"},
            )
        )
        session.commit()

    ids = ("old-raju", "old-cat", IDS["mira"])
    before = specs(engine, ids)

    assert migrate_characters(engine) == 2

    first = specs(engine, ids)
    assert first["old-raju"] == migrate_spec(OLD_RAJU, "kid", "sidekick")
    assert first["old-cat"]["body_type"] == "cat" and first["old-cat"]["extras"] == ["cape"]
    assert first[IDS["mira"]] == before[IDS["mira"]]  # already a builder spec: left alone
    with Session(engine) as session:
        cat = session.get(Character, "old-cat")
        assert cat is not None and cat.kind == "animal"

    assert migrate_characters(engine) == 0  # idempotent
    assert specs(engine, ids) == first


def specs(engine: Any, ids: tuple[str, ...]) -> dict[str, dict[str, Any]]:
    with Session(engine) as session:
        rows = {cid: session.get(Character, cid) for cid in ids}
        return {cid: dict(row.spec) for cid, row in rows.items() if row is not None}


def test_migration_runs_at_startup(client: TestClient, settings: Settings) -> None:
    with Session(app_state(client).engine) as session:
        session.add(
            Character(
                id="old-mira", user_id=USER_ID, name="Old", role="hero", kind="kid", spec=OLD_MIRA
            )
        )
        session.commit()

    with TestClient(create_app(settings)) as restarted:  # same storage, so a restart
        old = restarted.get("/api/characters/old-mira").json()

    assert old["spec"]["body_type"] == "kid" and old["spec"]["parts"]["top"] == "raincoat"
