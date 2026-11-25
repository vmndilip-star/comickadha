"""The Story Buddy, story sparks, prompts loaded at startup, and storage backups."""

import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import prompts
from app.config import Settings
from app.main import create_app
from app.services.ai_guard import META_LABEL, OFFLINE_LABEL, RESTING
from app.services.backup import backup_storage, backups_dir
from app.services.story_buddy import SPARKS
from tests.conftest import IDS
from tests.fakes import server_error, use_meta


def buddy(client: TestClient, action: str, text: str = "") -> dict:  # type: ignore[type-arg]
    res = client.post(
        "/api/studio/buddy", json={"action": action, "text": text, "comic_id": IDS["mango"]}
    )
    assert res.status_code == 200, res.json()
    data: dict = res.json()  # type: ignore[type-arg]
    return data


# ---- Story Buddy ---------------------------------------------------------------------------


def test_idea_asks_questions_and_never_writes_the_story(client: TestClient) -> None:
    out = buddy(client, "idea", "Mira looks for the mango.")

    assert 1 <= len(out["questions"]) <= 2
    assert all(q.endswith("?") and len(q.split()) <= 20 for q in out["questions"])
    assert out["corrected"] is None and out["titles"] == []
    assert (out["source"], out["label"]) == ("mock", OFFLINE_LABEL)


def test_spelling_returns_corrected_text_and_the_changes(client: TestClient) -> None:
    out = buddy(client, "spelling", "mira and her freind went to teh garden")

    assert out["corrected"] == "Mira and her friend went to the garden."
    assert {"before": "freind", "after": "friend"} in out["changes"]
    assert buddy(client, "spelling", "All good here.")["changes"] == []


def test_name_scene_gives_three_titles(client: TestClient) -> None:
    out = buddy(client, "name_scene", "Mira finds sticky footprints in the School garden")

    assert len(out["titles"]) == 3 and all(1 <= len(t.split()) <= 6 for t in out["titles"])


def test_buddy_input_goes_through_safety(client: TestClient) -> None:
    res = client.post(
        "/api/studio/buddy",
        json={"action": "idea", "text": "Mira's phone is 07700 900123", "comic_id": IDS["mango"]},
    )
    assert (res.status_code, res.json()["code"], res.json()["field"]) == (422, "unsafe", "buddy")
    assert "phone numbers secret" in res.json()["message"]


def test_buddy_with_meta_and_its_fallback(client: TestClient) -> None:
    fake = use_meta(client)
    fake.replies["buddy_idea"] = {
        "questions": ["What clue could Mira spot first?"],
        "reply": "Ooh, a mystery!",
    }
    out = buddy(client, "idea", "Mira looks for the mango.")
    assert (out["source"], out["label"], out["questions"]) == (
        "meta",
        META_LABEL,
        ["What clue could Mira spot first?"],
    )

    fake.replies["buddy_name_scene"] = server_error()
    down = buddy(client, "name_scene", "They find the monkeys")
    assert (down["source"], down["fallback"], down["label"]) == ("mock", True, OFFLINE_LABEL)
    assert down["reply"].startswith(RESTING) and len(down["titles"]) == 3


def test_meta_story_text_instead_of_questions_is_not_used(client: TestClient) -> None:
    fake = use_meta(client)
    fake.replies["buddy_idea"] = {
        "questions": ["Then Mira found the mango under the bed and everyone cheered."],
        "reply": "Here's your story!",
    }
    out = buddy(client, "idea", "Mira looks for the mango.")
    assert out["source"] == "mock" and all(q.endswith("?") for q in out["questions"])


def test_unsafe_buddy_output_is_never_shown(client: TestClient) -> None:
    fake = use_meta(client)
    fake.replies["buddy_name_scene"] = {
        "titles": ["The Beer Garden", "Mango Time", "Monkey Business"],
        "reply": "Fun!",
    }
    out = buddy(client, "name_scene", "They find the monkeys")
    assert out["fallback"] is True and all("Beer" not in t for t in out["titles"])


def test_sparks(client: TestClient) -> None:
    assert len(SPARKS) == 30 and len(set(SPARKS)) == 30
    first = client.get("/api/studio/spark").json()
    for _ in range(5):
        nxt = client.get(f"/api/studio/spark?after={first['index']}").json()
        assert nxt["index"] != first["index"] and nxt["text"] == SPARKS[nxt["index"]]


# ---- prompts ----------------------------------------------------------------------------------


def test_every_prompt_loads_including_the_moved_ones() -> None:
    loaded = prompts.load_all()
    assert set(prompts.REQUIRED) <= set(loaded)
    helper = prompts.render("builder_helper", catalog="CATALOG HERE")
    assert helper.startswith("You are the friendly helper in Comickadha")
    assert "CATALOG HERE" in helper and "{" not in helper
    classifier = prompts.render("safety_classifier")
    assert classifier.startswith("You check text for Comickadha")
    assert classifier.endswith("Reply with one verdict for each numbered text, in order.")


def test_a_missing_or_broken_prompt_stops_startup(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setitem(prompts.REQUIRED, "no_such_prompt", set())
    with pytest.raises(RuntimeError, match="no_such_prompt"):
        prompts.load_all()
    monkeypatch.delitem(prompts.REQUIRED, "no_such_prompt")
    monkeypatch.setitem(prompts.REQUIRED, "planner_scenes", {"something_else"})
    with pytest.raises(RuntimeError, match="unknown placeholders"):
        prompts.load_all()


# ---- backups ----------------------------------------------------------------------------------


def test_backup_copies_the_database_and_media_and_keeps_five(
    settings: Settings, capsys: pytest.CaptureFixture[str]
) -> None:
    storage = settings.storage_dir
    made = [backup_storage(storage) for _ in range(7)]

    assert all(m is not None for m in made)
    kept = sorted(p.name for p in backups_dir(storage).iterdir())
    assert len(kept) == 5 and kept[-1] == made[-1].name  # type: ignore[union-attr]
    newest = made[-1]
    assert newest is not None and (newest / "comickadha.db").exists()
    assert sorted(p.name for p in (newest / "media").rglob("*.png")) == sorted(
        p.name for p in (storage / "media").rglob("*.png")
    )
    with sqlite3.connect(newest / "comickadha.db") as copy:
        assert copy.execute("pragma integrity_check").fetchone()[0] == "ok"
    assert f"Backed up {storage} to {newest}" in capsys.readouterr().out


def test_startup_backs_up_before_migrating_an_older_database(settings: Settings) -> None:
    db = settings.storage_dir / "comickadha.db"
    with sqlite3.connect(db) as conn:
        conn.execute("ALTER TABLE panel DROP COLUMN edited_at")  # as before Phase 4

    with TestClient(create_app(settings)):
        pass

    backups = list(backups_dir(settings.storage_dir).iterdir())
    assert len(backups) == 1 and backups[0].name.endswith("before-migration")
    with sqlite3.connect(backups[0] / "comickadha.db") as copy:  # the copy is the old database
        columns = [row[1] for row in copy.execute("pragma table_info(panel)")]
    assert "edited_at" not in columns
    with sqlite3.connect(db) as conn:  # and the live one was migrated
        assert "edited_at" in [row[1] for row in conn.execute("pragma table_info(panel)")]

    with TestClient(create_app(settings)):  # nothing to migrate: no new backup
        pass
    assert len(list(backups_dir(settings.storage_dir).iterdir())) == 1
