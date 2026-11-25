"""Painted portraits (decisions 131, 132, 134): painted after a lock, checked, never blocking the
lock, no kid words in any prompt, the look check, the caps and the switch."""

from datetime import timedelta
from typing import Any

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.config import Settings
from app.models import Job, PaintLog
from app.models.base import utcnow
from app.prompts import render
from app.providers.mock import MockImageProvider
from app.seed import paint_portraits
from app.services import portraits
from app.services.backup import backups_dir
from app.services.jobs import PORTRAIT_INTERRUPTED, fail_interrupted_jobs
from app.services.painting import KEEP_LOOK
from app.services.safety import PNG_SIGNATURE
from tests.conftest import IDS, app_state, sse_events, wait_for_job
from tests.fakes import FakeImages, picture, same_look, scene_png, server_error, use_meta, use_muse

SQUARE = scene_png((1024, 1024))


def last_event(client: TestClient, job_id: str) -> tuple[str, dict[str, Any]]:
    wait_for_job(client, job_id)
    _id, kind, data = sse_events(client, job_id)[-1]
    return kind, data


def lock(client: TestClient, character_id: str) -> str | None:
    """Locks the character; returns the portrait job the lock started (None if none)."""
    res = client.post(f"/api/characters/{character_id}/lock")
    assert res.status_code == 202, res.json()
    kind, data = last_event(client, res.json()["job_id"])
    assert kind == "done", data
    job_id: str | None = data["portrait_job_id"]
    return job_id


def character(client: TestClient, character_id: str) -> dict[str, Any]:
    data: dict[str, Any] = client.get(f"/api/characters/{character_id}").json()
    return data


def paint_logs(client: TestClient) -> list[PaintLog]:
    with Session(app_state(client).engine) as session:
        return list(session.exec(select(PaintLog)))


def real_models(client: TestClient, *replies: bytes | Exception) -> tuple[Any, FakeImages]:
    """Meta for the checks, Muse for the pictures (both fakes)."""
    meta = use_meta(client)
    images = use_muse(client, FakeImages(*(replies or (SQUARE,))))
    return meta, images


# ---- painted after a lock --------------------------------------------------------------------


def test_locking_paints_a_portrait_as_its_own_job(client: TestClient) -> None:
    job_id = lock(client, IDS["robo"])
    assert job_id is not None
    kind, data = last_event(client, job_id)
    assert kind == "done" and data["portrait_url"].startswith(
        f"/media/characters/{IDS['robo']}/v1/portrait-mock.png?v="
    )
    robo = character(client, IDS["robo"])
    assert robo["status"] == "locked" and robo["show_portrait"] is True
    assert robo["manifest"]["portrait_url"] == data["portrait_url"]
    assert robo["manifest"]["portrait_thumb_url"].startswith(
        f"/media/characters/{IDS['robo']}/v1/portrait-mock_thumb.png?v="
    )
    assert robo["portrait_job_id"] is None  # finished
    storage = app_state(client).storage
    assert storage.read(f"characters/{IDS['robo']}/v1/portrait-mock.png").startswith(PNG_SIGNATURE)
    assert '"portrait_url"' in storage.read(f"characters/{IDS['robo']}/v1/manifest.json").decode()
    [row] = paint_logs(client)
    assert (row.kind, row.provider, row.outcome, row.attempts) == ("portrait", "mock", "saved", 1)


def test_a_blocked_portrait_leaves_the_character_locked_and_saves_nothing(
    client: TestClient,
) -> None:
    meta, images = real_models(client)
    meta.replies["image_safety"] = picture(safe_for_kids=False)
    job_id = lock(client, IDS["robo"])
    assert job_id is not None

    kind, data = last_event(client, job_id)

    assert kind == "error" and "couldn't paint Robo-Tik's portrait" in data["message"]
    robo = character(client, IDS["robo"])
    assert robo["status"] == "locked" and robo["manifest"].get("portrait_url") is None
    assert not app_state(client).storage.exists(f"characters/{IDS['robo']}/v1/portrait-muse.png")
    assert len(images.calls) == 2  # one more try, then stop
    [row] = paint_logs(client)
    assert (row.provider, row.outcome, row.attempts) == ("muse", "blocked", 2)


def test_a_checker_outage_fails_closed_and_the_character_stays_locked(client: TestClient) -> None:
    meta, _images = real_models(client)
    meta.replies["image_safety"] = server_error()
    job_id = lock(client, IDS["robo"])
    assert job_id is not None
    kind, data = last_event(client, job_id)
    assert kind == "error" and "picture checker is taking a break" in data["message"]
    assert character(client, IDS["robo"])["status"] == "locked"


def test_no_kid_words_reach_muse_or_the_look_check(client: TestClient) -> None:
    spec = character(client, IDS["robo"])["spec"]
    spec["personality"]["catchphrase"] = "Wibble wobble"
    body = {"name": "Zorblax", "spec": spec}
    assert client.patch(f"/api/characters/{IDS['robo']}", json=body).status_code == 200
    meta, images = real_models(client)
    job_id = lock(client, IDS["robo"])
    assert job_id is not None and last_event(client, job_id)[0] == "done"

    [paint] = images.calls
    assert paint["kind"] == "edit" and len(paint["references"]) == 1
    assert paint["references"][0].startswith(PNG_SIGNATURE)
    assert "#" in paint["prompt"] and "colours:" in paint["prompt"]  # the spec's colour values
    [look] = meta.calls_for("look_check")
    parts = look["messages"][1]["content"]
    assert sum(1 for p in parts if p["type"] == "image_url") == 1  # one side-by-side picture
    sent = paint["prompt"] + " ".join(p.get("text", "") for p in parts)
    for word in ("Zorblax", "Wibble", "wobble"):
        assert word not in sent
    assert meta.calls_for("safety_verdicts") == []  # nothing kid-written to classify


def test_a_look_check_fail_tries_again_then_keeps_the_builder_look(client: TestClient) -> None:
    meta, images = real_models(client)
    meta.replies["look_check"] = lambda call: same_look(call, skin_tone="lighter")
    job_id = lock(client, IDS["robo"])
    assert job_id is not None

    kind, _data = last_event(client, job_id)

    assert kind == "error"
    assert render(KEEP_LOOK) not in images.calls[0]["prompt"]
    assert render(KEEP_LOOK) in images.calls[1]["prompt"]  # the stronger line, once
    [row] = paint_logs(client)
    assert row.outcome == "look_failed" and "character 1: skin lighter (hard)" in row.findings
    assert character(client, IDS["robo"])["manifest"].get("portrait_url") is None


def test_a_missing_head_covering_fails_but_changed_hair_is_only_logged(
    client: TestClient,
) -> None:
    meta, _images = real_models(client)
    meta.replies["look_check"] = lambda call: same_look(call, hair_kept=False)
    job_id = lock(client, IDS["robo"])
    assert job_id is not None and last_event(client, job_id)[0] == "done"
    [row] = paint_logs(client)
    assert row.outcome == "saved" and row.findings == ["character 1: hair changed"]


def test_a_head_covering_is_expected_and_checked(client: TestClient) -> None:
    made = client.post("/api/characters", json={"name": "Aisha"}).json()  # a default kid
    spec = made["spec"]
    spec["parts"]["headwear"] = "hijab"
    assert portraits.has_head_covering(spec)
    assert "head covering" in portraits.colour_words(spec)
    assert client.patch(f"/api/characters/{made['id']}", json={"spec": spec}).status_code == 200
    meta, _images = real_models(client)
    meta.replies["look_check"] = lambda call: same_look(call, head_covering_kept=False)
    job_id = lock(client, made["id"])
    assert job_id is not None and last_event(client, job_id)[0] == "error"
    [look, _again] = meta.calls_for("look_check")
    assert "They wear a head covering." in look["messages"][1]["content"][0]["text"]
    assert "character 1: head covering missing (hard)" in paint_logs(client)[0].findings


# ---- Paint portrait (and Paint again) ---------------------------------------------------------


def test_paint_portrait_paints_a_character_locked_before_portraits(client: TestClient) -> None:
    assert character(client, IDS["mira"])["manifest"].get("portrait_url") is None  # seeded, locked
    res = client.post(f"/api/characters/{IDS['mira']}/portrait")
    assert res.status_code == 202 and res.json()["kind"] == "portrait"
    assert last_event(client, res.json()["job_id"])[0] == "done"
    first = character(client, IDS["mira"])["manifest"]["portrait_url"]
    again = client.post(f"/api/characters/{IDS['mira']}/portrait")  # Paint again
    assert last_event(client, again.json()["job_id"])[0] == "done"
    assert character(client, IDS["mira"])["manifest"]["portrait_url"] == first  # same bytes


def test_paint_portrait_refusals(client: TestClient) -> None:
    draft = client.post(f"/api/characters/{IDS['robo']}/portrait")
    assert (draft.status_code, draft.json()["code"]) == (409, "needs_locked")
    starter = next(c for c in client.get("/api/characters").json() if c["starter"])
    res = client.post(f"/api/characters/{starter['id']}/portrait")
    assert (res.status_code, res.json()["code"]) == (409, "starter")
    app_state(client).settings.painting_enabled = False
    off = client.post(f"/api/characters/{IDS['mira']}/portrait")
    assert (off.status_code, off.json()["code"]) == (409, "painting_off")


def test_a_second_press_returns_the_portrait_already_being_painted(client: TestClient) -> None:
    with Session(app_state(client).engine) as session:
        job = Job(kind="portrait", target_id=IDS["mira"], status="running")
        session.add(job)
        session.commit()
        job_id = job.id
    res = client.post(f"/api/characters/{IDS['mira']}/portrait")
    assert res.status_code == 202 and res.json()["job_id"] == job_id
    assert character(client, IDS["mira"])["portrait_job_id"] == job_id


def add_paints(client: TestClient, attempts: int, user_id: str, *, days_ago: int = 0) -> None:
    with Session(app_state(client).engine) as session:
        session.add(
            PaintLog(
                user_id=user_id,
                kind="portrait",
                target="character:x:v1:portrait",
                provider="muse",
                attempts=attempts,
                outcome="saved",
                created_at=utcnow() - timedelta(days=days_ago),
            )
        )
        session.commit()


def test_the_daily_caps_stop_paid_portraits(client: TestClient) -> None:
    kid = client.get("/api/me").json()["id"]
    real_models(client)
    add_paints(client, 30, kid, days_ago=1)  # yesterday's don't count
    add_paints(client, 9, kid)
    assert client.post(f"/api/characters/{IDS['mira']}/portrait").status_code == 202
    wait_for_job(client, character(client, IDS["mira"])["portrait_job_id"] or "")


def test_at_the_kid_cap_or_everyones_cap_it_is_a_429(client: TestClient) -> None:
    kid = client.get("/api/me").json()["id"]
    real_models(client)
    add_paints(client, 10, kid)
    res = client.post(f"/api/characters/{IDS['mira']}/portrait")
    assert (res.status_code, res.json()["code"]) == (429, "daily_limit")
    assert "paint brushes need a rest" in res.json()["message"]
    settings: Settings = app_state(client).settings
    settings.portrait_paints_per_kid = 100
    settings.paints_per_day = 12
    add_paints(client, 3, "someone-else")
    res = client.post(f"/api/characters/{IDS['raju']}/portrait")
    assert (res.status_code, res.json()["code"]) == (429, "daily_limit")


def test_the_mock_is_free_so_it_never_reaches_a_cap(client: TestClient) -> None:
    kid = client.get("/api/me").json()["id"]
    add_paints(client, 500, kid)
    assert client.post(f"/api/characters/{IDS['mira']}/portrait").status_code == 202


def test_with_painting_off_a_lock_paints_no_portrait(client: TestClient) -> None:
    _meta, images = real_models(client)
    app_state(client).settings.painting_enabled = False
    assert lock(client, IDS["robo"]) is None
    assert images.calls == [] and character(client, IDS["robo"])["status"] == "locked"
    assert client.get("/api/me").json()["painting_enabled"] is False


# ---- versions, the kid's choice, restarts ------------------------------------------------------


def test_locking_again_paints_a_new_version_and_keeps_the_old_portrait(client: TestClient) -> None:
    storage = app_state(client).storage
    first_job = lock(client, IDS["robo"])
    assert first_job is not None and last_event(client, first_job)[0] == "done"
    v1 = storage.read(f"characters/{IDS['robo']}/v1/portrait-mock.png")
    assert client.post(f"/api/characters/{IDS['robo']}/unlock").status_code == 200
    spec = character(client, IDS["robo"])["spec"]
    spec["colors"]["top"] = "#1F5BD1"
    assert client.patch(f"/api/characters/{IDS['robo']}", json={"spec": spec}).status_code == 200
    second_job = lock(client, IDS["robo"])
    assert second_job is not None and last_event(client, second_job)[0] == "done"
    assert storage.read(f"characters/{IDS['robo']}/v1/portrait-mock.png") == v1
    assert storage.exists(f"characters/{IDS['robo']}/v2/portrait-mock.png")
    assert "/v2/portrait-mock.png" in character(client, IDS["robo"])["manifest"]["portrait_url"]


def test_the_kid_can_choose_the_drawing_or_the_painting_while_locked(client: TestClient) -> None:
    off = client.patch(f"/api/characters/{IDS['mira']}", json={"show_portrait": False})
    assert off.status_code == 200 and off.json()["show_portrait"] is False
    on = client.patch(f"/api/characters/{IDS['mira']}", json={"show_portrait": True})
    assert on.json()["show_portrait"] is True
    rename = client.patch(f"/api/characters/{IDS['mira']}", json={"name": "Mirabel"})
    assert (rename.status_code, rename.json()["code"]) == (409, "locked")  # the look stays locked


def test_an_interrupted_portrait_fails_kindly_and_the_character_stays_locked(
    client: TestClient,
) -> None:
    engine = app_state(client).engine
    with Session(engine) as session:
        job = Job(kind="portrait", target_id=IDS["mira"], status="running")
        session.add(job)
        session.commit()
        job_id = job.id
    assert fail_interrupted_jobs(engine) == 1
    with Session(engine) as session:
        done = session.get(Job, job_id)
        assert done is not None and (done.status, done.error) == ("failed", PORTRAIT_INTERRUPTED)
    assert character(client, IDS["mira"])["status"] == "locked"


# ---- the mock restyle and seed --portraits -----------------------------------------------------


def test_the_mock_restyle_is_deterministic_and_changes_the_picture() -> None:
    reference = portraits.portrait_reference({"body_type": "kid"})
    mock = MockImageProvider()
    prompt = render("portrait", look="a kid")
    one = mock.generate(prompt, (512, 512), 7, [reference])
    assert one == mock.generate(prompt, (512, 512), 7, [reference]) and one != reference
    assert one.startswith(PNG_SIGNATURE)


def test_seed_portraits_paints_the_starters_after_a_backup(
    client: TestClient, settings: Settings
) -> None:
    report = paint_portraits(settings)
    assert len(report) == 12 and all("painted" in line for line in report)
    assert any(
        p.name.endswith("before-portraits") for p in backups_dir(settings.storage_dir).iterdir()
    )
    starter = next(c for c in client.get("/api/characters").json() if c["starter"])
    assert "/portrait-mock.png?v=" in starter["manifest"]["portrait_url"]
    assert all(row.seed_run for row in paint_logs(client))
