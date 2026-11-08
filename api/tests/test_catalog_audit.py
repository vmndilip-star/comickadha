"""The parts library safety audit (docs/character-safety.md, section 3). Runs every time."""

import json
import re
from itertools import product
from typing import Any, get_args

import pytest

from app.avatar.catalog import load_catalog
from app.avatar.spec import options_for
from app.avatar.words import PART_WORDS
from app.schemas.builder import FaceShape
from app.services import helper_offline
from app.services.safety import BLOCKLIST

CAT = load_catalog()
PEOPLE = [b for b, info in CAT["body_types"].items() if info["kind"] in ("kid", "grown_up")]
NOT_PEOPLE = [b for b in CAT["body_types"] if b not in PEOPLE]
CLOTHES = ("top", "bottom", "shoes")
WEAPONS = BLOCKLIST["weapons"] | {"sword", "bow", "arrow", "axe", "spear", "dagger", "blaster"}
BRANDS = {"nike", "adidas", "puma", "reebok", "gucci", "disney", "marvel", "pokemon", "logo"}
JOKES = {"funny", "silly", "joke", "weird", "lol", "costume", "crazy", "clown", "wacky"}


def every_option() -> list[tuple[str, str, dict[str, Any]]]:
    out = [
        (c, oid, o) for c, info in CAT["categories"].items() for oid, o in info["options"].items()
    ]
    return out + [("extras", eid, e) for eid, e in CAT["extras"].items()]


def test_people_are_always_dressed() -> None:
    """Kids and grown-ups must wear a top, a bottom and shoes: no "none" for them."""
    assert PEOPLE == ["kid", "grown_up"]
    for body in PEOPLE:
        tops, bottoms = options_for("top", body), options_for("bottom", body)
        for garment in CLOTHES:
            assert "none" not in options_for(garment, body), (body, garment)
        # Every top-and-bottom combination covers the body.
        for top, bottom in product(tops, bottoms):
            assert top != "none" and bottom != "none"
        defaults = CAT["body_types"][body]["defaults"]["parts"]
        assert all(defaults[g] != "none" for g in CLOTHES)


def test_only_robots_and_animals_may_go_without_clothes() -> None:
    for garment in CLOTHES:
        none = CAT["categories"][garment]["options"].get("none")
        assert none is not None
        assert set(none["body_types"]) <= set(NOT_PEOPLE), garment


def test_no_weapons_except_the_magic_wand() -> None:
    for group, option_id, option in every_option():
        words = set(re.findall(r"[a-z]+", f"{option_id} {option['label']}".lower()))
        assert not words & WEAPONS, (group, option_id)
    assert CAT["extras"]["wand"]["label"] == "Magic wand"


def test_no_text_brands_or_logos_on_anything() -> None:
    art = json.dumps(CAT)
    for tag in ("<text", "<tspan", "<image", "font-family", "href="):
        assert tag not in art, tag
    for group, option_id, option in every_option():
        words = set(re.findall(r"[a-z]+", f"{option_id} {option['label']}".lower()))
        assert not words & BRANDS, (group, option_id)


def test_cultural_items_are_for_every_human_body_and_labelled_respectfully() -> None:
    cultural = [(g, oid, o) for g, oid, o in every_option() if "cultural" in o.get("tags", [])]
    assert {(g, oid) for g, oid, _ in cultural} == {("headwear", "hijab"), ("headwear", "turban")}
    for _, option_id, option in cultural:
        assert set(PEOPLE) <= set(option["body_types"]), option_id
        assert option["label"] == option_id.title()
        assert not set(option["label"].lower().split()) & JOKES
        assert "silly" not in option["tags"]
        # The offline helper understands the word and gives exactly that item (no stand-in).
        assert PART_WORDS.get(option_id) == ("headwear", option_id)


@pytest.mark.parametrize("body", ["kid", "grown_up"])
def test_surprise_never_pairs_cultural_items_with_silly_ones(body: str) -> None:
    silly = {e for e, extra in CAT["extras"].items() if "silly" in extra.get("tags", [])}
    assert silly == {"glasses_star"}
    picked = 0
    for seed in range(3000):
        raw = helper_offline.surprise(body, seed)
        headwear = raw["parts"]["headwear"]
        if "cultural" in CAT["categories"]["headwear"]["options"][headwear]["tags"]:
            picked += 1
            assert not set(raw["extras"]) & silly, (seed, headwear, raw["extras"])
    assert picked > 50  # they still come up at random, with ordinary clothes and capes


def test_every_option_has_been_reviewed() -> None:
    unreviewed = [(g, oid) for g, oid, o in every_option() if o.get("reviewed") is not True]
    assert unreviewed == [], "Review these options and add them to REVIEWED in build_catalog.py"


def test_the_face_shape_list_matches_the_catalog() -> None:
    assert set(get_args(FaceShape)) == set(CAT["categories"]["face_shape"]["options"])
