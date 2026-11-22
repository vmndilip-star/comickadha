"""Avatar specs: strict checks against the parts catalog, and the old-spec migration."""

from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.avatar import spec as avatar_spec
from app.avatar.catalog import load_catalog
from tests.conftest import IDS

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
