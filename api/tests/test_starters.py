"""Phase 7 part B: the 12 starter characters. Ready-made, locked and the same for every kid;
read-only (a 409 "starter"); not counted toward the kid's 3; "Make it mine" copies one; comics can
have up to 5 characters, own and starters mixed, with at most 3 in a panel."""

import shutil
import sqlite3
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, col, select

from app.avatar import spec as avatar_spec
from app.avatar.catalog import load_catalog
from app.config import Settings
from app.main import create_app
from app.models import CharacterVersion
from app.schemas.common import SHEET_EXPRESSIONS as EXPRESSIONS
from app.schemas.common import SHEET_POSES as POSES
from app.schemas.common import TRAITS
from app.schemas.studio import PanelPlan, PlannedCharacter, PlannedPanel
from app.services import safety
from app.services.backup import backups_dir
from app.services.character_safety import name_problem, respectful_extras, tagged
from app.services.character_sheet import sheet_prefix
from app.services.story_planner import (
    CastMember,
    Place,
    SceneInfo,
    StoryContext,
    check_panels,
    offline_panels,
)
from app.starters import STARTER_IDS, STARTERS, VERSION, ensure_starters
from tests.conftest import (
    IDS,
    app_state,
    fill_cast,
    make_settings,
    own_cast,
    plan_panels,
    wait_for_job,
)

MESSAGE = "Starter characters can't be changed. Tap Make it mine to get your own copy!"
STARTER = {s["name"]: s["id"] for s in STARTERS}
CAT = load_catalog()


def starters(client: TestClient) -> list[dict[str, Any]]:
    return [c for c in client.get("/api/characters").json() if c["starter"]]


# ---- seeded, locked, frozen -------------------------------------------------------------------


def test_the_12_starters_are_seeded_locked_and_frozen(client: TestClient) -> None:
    listed = client.get("/api/characters").json()

    assert [c["name"] for c in listed[:3]] == ["Mira", "Raju", "Robo-Tik"]  # own cast first
    found = starters(client)
    assert [c["name"] for c in found] == [
        "Zara", "Leo", "Aisha", "Arjun", "Kofi", "Mei",
        "Nana Rose", "Mr. Hari", "Pixel", "Whiskers", "Biscuit", "Barnaby",
    ]  # fmt: skip
    assert tuple(c["id"] for c in found) == STARTER_IDS  # fixed uuid5 ids
    storage = app_state(client).storage
    with Session(app_state(client).engine) as session:
        for c in found:
            assert (c["status"], c["sheet_version"], c["deleted"]) == ("locked", VERSION, False)
            assert c["manifest"] is not None and c["designed_by"] is None
            assert storage.exists(f"{sheet_prefix(c['id'], VERSION)}/manifest.json")
            look = session.exec(
                select(CharacterVersion).where(CharacterVersion.character_id == c["id"])
            ).all()
            assert [(v.version, v.spec) for v in look] == [(VERSION, c["spec"])]


def test_ensure_starters_is_idempotent_and_redraws_a_lost_sheet(client: TestClient) -> None:
    state = app_state(client)
    zara = STARTER["Zara"]
    shutil.rmtree(state.storage.local_path(f"characters/{zara}"))

    with Session(state.engine) as session:
        assert ensure_starters(session, state.storage) == 0  # nothing new to add
        assert ensure_starters(session, state.storage) == 0
        versions = session.exec(
            select(CharacterVersion).where(col(CharacterVersion.character_id).in_(STARTER_IDS))
        ).all()

    assert state.storage.exists(f"{sheet_prefix(zara, VERSION)}/manifest.json")  # drawn again
    assert len(starters(client)) == 12 and len(versions) == 12


def test_a_fresh_install_draws_every_starter_and_has_no_kid_yet(
    client: TestClient, tmp_path: Path
) -> None:
    assert client.get("/api/me").json()["display_name"] == "Aarav"  # never the starter profile
    # A fresh install without demo data: the 12 starters, every cell drawn, but no kid profile.
    fresh = make_settings(tmp_path / "fresh", seed_on_startup=False)
    with TestClient(create_app(fresh)) as empty:
        res = empty.get("/api/me")
        assert (res.status_code, res.json()["code"]) == (503, "no_profile")
        storage = app_state(empty).storage
        for starter_id in STARTER_IDS:
            cells = storage.local_path(f"{sheet_prefix(starter_id, VERSION)}/cells")
            assert len(list(cells.rglob("*.png"))) == len(POSES) + len(EXPRESSIONS)  # 16 + 6


def test_an_older_database_gets_the_column_and_the_starters_after_a_backup(
    settings: Settings,
) -> None:
    db = settings.storage_dir / "comickadha.db"
    starters_sql = "SELECT id FROM character WHERE starter = 1"
    with sqlite3.connect(db) as conn:  # as before part B: no starter column, no starters
        conn.execute(f"DELETE FROM character_version WHERE character_id IN ({starters_sql})")
        conn.execute("DELETE FROM character WHERE starter = 1")
        conn.execute("ALTER TABLE character DROP COLUMN starter")

    with TestClient(create_app(settings)) as client:
        assert len(starters(client)) == 12
        assert [c["name"] for c in own_cast(client)] == ["Mira", "Raju", "Robo-Tik"]

    backups = list(backups_dir(settings.storage_dir).iterdir())
    assert len(backups) == 1 and backups[0].name.endswith("before-migration")


# ---- read-only --------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("method", "suffix", "body"),
    [
        ("PATCH", "", {"name": "Zed"}),
        ("DELETE", "", None),
        ("POST", "/lock", None),
        ("POST", "/unlock", None),
    ],
)
def test_starters_are_read_only(
    client: TestClient, method: str, suffix: str, body: dict[str, Any] | None
) -> None:
    zara = STARTER["Zara"]

    res = client.request(method, f"/api/characters/{zara}{suffix}", json=body)

    assert res.status_code == 409
    assert res.json() == {"code": "starter", "message": MESSAGE}
    again = client.get(f"/api/characters/{zara}").json()
    assert (again["name"], again["status"], again["deleted"]) == ("Zara", "locked", False)


def test_a_starter_can_be_read_with_its_manifest(client: TestClient) -> None:
    pixel = STARTER["Pixel"]

    assert client.get(f"/api/characters/{pixel}").json()["kind"] == "robot"
    assert client.get(f"/api/characters/{pixel}/manifest").status_code == 200


# ---- the kid's own cast, and Make it mine -----------------------------------------------------


def test_starters_dont_count_toward_the_kids_cast(client: TestClient) -> None:
    assert len(own_cast(client)) == 3 and len(starters(client)) == 12
    fill_cast(client)  # all of their own: the 12 starters still don't count

    full = client.post("/api/characters", json={"name": "Zed"})
    assert (full.status_code, full.json()["code"]) == (409, "cast_full")

    client.delete(f"/api/characters/{IDS['robo']}")
    assert client.post("/api/characters", json={"name": "Zed"}).status_code == 201


def test_make_it_mine_copies_a_starter_as_an_editable_draft_that_counts(
    client: TestClient,
) -> None:
    zara = client.get(f"/api/characters/{STARTER['Zara']}").json()
    res = client.post(f"/api/characters/{zara['id']}/copy")

    assert res.status_code == 201
    mine = res.json()
    assert mine["id"] != zara["id"] and mine["starter"] is False
    assert (mine["name"], mine["status"], mine["spec"]) == ("Zara", "draft", zara["spec"])
    assert [c["name"] for c in own_cast(client)] == ["Mira", "Raju", "Robo-Tik", "Zara"]  # counts
    edited = client.patch(f"/api/characters/{mine['id']}", json={"name": "Zara Two"})
    assert edited.status_code == 200 and edited.json()["name"] == "Zara Two"
    assert client.get(f"/api/characters/{zara['id']}").json()["name"] == "Zara"  # untouched
    fill_cast(client)
    again = client.post(f"/api/characters/{STARTER['Leo']}/copy")
    assert (again.status_code, again.json()["code"]) == (409, "cast_full")


def test_make_it_mine_only_copies_starters(client: TestClient) -> None:
    res = client.post(f"/api/characters/{IDS['mira']}/copy")

    assert (res.status_code, res.json()["code"]) == (422, "invalid")


# ---- comics with up to 5 characters -----------------------------------------------------------

FIVE = [IDS["mira"], IDS["raju"], STARTER["Zara"], STARTER["Leo"], STARTER["Pixel"]]
STORY = (
    "Mira, Raju, Zara, Leo and Pixel hunt for the missing mango. They search the kitchen, "
    "follow footprints to the school garden and find it under the bench. Everyone cheers."
)


def test_a_comic_can_have_up_to_5_characters_own_and_starters_mixed(client: TestClient) -> None:
    comic_id = client.post("/api/comics", json={"title": "Five"}).json()["id"]

    ok = client.patch(f"/api/comics/{comic_id}", json={"cast_ids": FIVE})
    assert ok.status_code == 200 and ok.json()["cast_ids"] == FIVE
    assert {c["id"] for c in ok.json()["characters"]} == set(FIVE)  # the Reader can show them

    six = client.patch(f"/api/comics/{comic_id}", json={"cast_ids": [*FIVE, STARTER["Mei"]]})
    assert six.status_code == 422


def test_a_5_character_comic_plans_and_draws(client: TestClient) -> None:
    """Phase 8: no 3-character limit; a panel shows whoever it needs, up to the whole scene."""
    comic_id = client.post("/api/comics", json={"title": "Mango", "synopsis": STORY}).json()["id"]
    client.patch(f"/api/comics/{comic_id}", json={"cast_ids": FIVE, "panel_count": 8})

    scenes = client.post(f"/api/studio/{comic_id}/plan-scenes", json={}).json()["scenes"]
    res = plan_panels(client, comic_id)

    assert res.status_code == 200, res.json()
    panels = res.json()["panels"]
    assert len(panels) == 8
    in_scene = {s["id"]: set(s["character_ids"]) for s in scenes}
    for p in panels:
        ids = [c["id"] for c in p["characters"]]
        assert 1 <= len(ids) <= len(in_scene[p["scene_id"]])
        assert len({c["position"] for c in p["characters"]}) == len(ids)
        assert set(ids) <= in_scene[p["scene_id"]]
    assert {c["id"] for p in panels for c in p["characters"]} == set(FIVE)  # everyone appears

    job = client.post(f"/api/comics/{comic_id}/generate").json()["job_id"]
    assert wait_for_job(client, job)["status"] == "done"
    pdf = client.get(f"/api/comics/{comic_id}/pdf")
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")


def member(name: str) -> CastMember:
    return CastMember(name.lower(), name, 1)


def test_the_offline_planner_gives_everyone_in_a_big_scene_a_moment() -> None:
    cast = [member(n) for n in ("Ava", "Bo", "Cy", "Di", "Ed")]
    scene = SceneInfo("s1", "park", tuple(m.id for m in cast), "They all play in the park.")
    ctx = StoryContext("Park", "They play.", "funny", 4, cast, [Place("park", "Park")], [scene])

    plan = offline_panels(ctx)

    assert all(1 <= len(p.characters) <= len(cast) for p in plan.panels)
    assert len(plan.panels[0].characters) == len(cast)  # the scene's first panel shows everyone
    assert {c.id for p in plan.panels for c in p.characters} == {m.id for m in cast}
    assert check_panels(plan, ctx) == []


def test_check_panels_keeps_each_panel_to_its_scenes_characters() -> None:
    cast = [member("Ava"), member("Bo")]
    scenes = [
        SceneInfo("s1", "park", ("ava",), "Ava plays."),
        SceneInfo("s2", "park", ("ava", "bo"), "Bo comes."),
    ]
    ctx = StoryContext("Park", "Play.", "funny", 4, cast, [Place("park", "Park")], scenes)
    stray = PlannedPanel(
        scene_id="s1",
        beat="Bo pops up",
        characters=[PlannedCharacter(id="bo", pose="front", expression="happy", position="center")],
    )
    plan = PanelPlan(panels=[stray, *offline_panels(ctx).panels[1:]])

    assert any("Bo isn't in scene 1" in p for p in check_panels(plan, ctx))


# ---- every starter passes the checks ----------------------------------------------------------

PEOPLE = ("kid", "grown_up")


@pytest.mark.parametrize("data", STARTERS, ids=[s["name"] for s in STARTERS])
def test_every_starter_passes_the_checks(data: dict[str, Any]) -> None:
    spec = data["spec"]
    personality = spec["personality"]

    assert name_problem(data["name"]) is None
    assert safety.check_local({"catchphrase": personality["catchphrase"]}).allowed
    assert 1 <= len(personality["traits"]) <= 3 and set(personality["traits"]) <= set(TRAITS)
    # Strict against the catalog (an unknown or ill-fitting choice raises), and every choice kept.
    full = avatar_spec.validate(spec)
    assert all(full["parts"][category] == v for category, v in spec["parts"].items())
    assert all(full["colors"][slot] == v for slot, v in spec["colors"].items())
    assert full["extras"] == spec["extras"]
    # The catalog audit: reviewed parts, people dressed, no silly items with a hijab or turban.
    for category, choice in full["parts"].items():
        assert CAT["categories"][category]["options"][choice]["reviewed"] is True
    for extra in full["extras"]:
        assert CAT["extras"][extra]["reviewed"] is True
    if full["body_type"] in PEOPLE:
        assert all(full["parts"][g] != "none" for g in ("top", "bottom", "shoes"))
    assert respectful_extras(full["parts"], full["extras"]) == full["extras"]


def test_the_starters_are_a_varied_respectful_cast() -> None:
    specs = {s["name"]: avatar_spec.validate(s["spec"]) for s in STARTERS}
    kinds = [avatar_spec.KIND_OF_BODY[s["body_type"]] for s in specs.values()]
    assert kinds.count("kid") == 6 and kinds.count("grown_up") == 2
    assert [specs[n]["body_type"] for n in ("Pixel", "Whiskers", "Biscuit", "Barnaby")] == [
        "robot", "cat", "dog", "bear",
    ]  # fmt: skip
    humans = [s for s in specs.values() if s["body_type"] in PEOPLE]
    assert len({s["colors"]["skin"] for s in humans}) == len(humans)  # a spread of skin tones
    assert len({s["parts"]["hair"] for s in humans}) >= 7
    cultural = [
        n for n, s in specs.items() if tagged("headwear", s["parts"]["headwear"], "cultural")
    ]
    assert cultural == ["Aisha", "Arjun"]
    for name in cultural:  # with ordinary clothes, never silly items (decision 68)
        assert not any(tagged("extras", e, "silly") for e in specs[name]["extras"])
    grey_or_white = {"#9A9A9A", "#F2F2EE"}
    assert specs["Nana Rose"]["colors"]["hair"] in grey_or_white  # decision 70
