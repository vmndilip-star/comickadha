"""IMAGE_PROVIDER=muse: the Muse Image provider, its startup rules, and place lock with the words
classified first and every picture checked before it is saved (Phase 6a)."""

import io
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlmodel import Session, col, select

from app.main import create_app
from app.models import ModerationLog
from app.prompts import render
from app.providers.image import ImageError
from app.providers.muse_image import MuseImageProvider
from app.services import imaging
from app.services.image_gen import CANT_PAINT, CHECKER_RESTING
from tests.conftest import app_state, make_settings, wait_for_job
from tests.fakes import (
    FakeImages,
    flag,
    muse,
    picture,
    scene_png,
    server_error,
    timeout_error,
    use_meta,
    use_muse,
    user_text,
)

# ---- the provider ------------------------------------------------------------------------------


def test_without_references_it_generates() -> None:
    fake = FakeImages(scene_png((1024, 768)))

    png = muse(fake).generate("A sunny park", (1024, 768), seed=7)

    assert [c["kind"] for c in fake.calls] == ["generate"]
    assert (fake.calls[0]["prompt"], fake.calls[0]["size"]) == ("A sunny park", "1024x768")
    assert fake.calls[0]["model"] == "muse-image-test"
    assert imaging.load(png).size == (1024, 768)


def test_with_references_it_edits_with_every_reference_each_time() -> None:
    fake = FakeImages(scene_png((1024, 1024)))
    refs = [scene_png((64, 64), (255, 0, 0)), scene_png((64, 64), (0, 255, 0))]
    provider = muse(fake)

    provider.generate("Both friends together", (1024, 1024), seed=1, reference_images=refs)
    provider.generate("Again", (1024, 1024), seed=1, reference_images=refs)

    assert [c["kind"] for c in fake.calls] == ["edit", "edit"]
    # Fresh file objects per call: the second call still sends every byte, in order.
    assert [c["references"] for c in fake.calls] == [refs, refs]
    # Meta wants image[0], image[1]... (it refuses the SDK's image[]).
    assert fake.calls[1]["fields"] == ["image[0]", "image[1]"]
    assert fake.calls[1]["filenames"] == ["reference-1.png", "reference-2.png"]
    assert (fake.calls[1]["model"], fake.calls[1]["size"]) == ("muse-image-test", "1024x1024")
    assert fake.calls[1]["options"]["headers"]["Content-Type"] == "multipart/form-data"


@pytest.mark.parametrize(
    ("returned", "asked", "expected"),
    [((1536, 1024), (1024, 768), (1365, 1024)), ((1024, 1024), (1024, 768), (1024, 768))],
)
def test_a_wrong_aspect_is_cover_cropped(
    returned: tuple[int, int], asked: tuple[int, int], expected: tuple[int, int]
) -> None:
    png = muse(FakeImages(scene_png(returned))).generate("A park", asked, seed=0)

    assert imaging.load(png).size == expected


def test_the_picture_comes_back_as_a_clean_png() -> None:
    image = Image.new("RGB", (400, 300), (10, 20, 30))
    buf = io.BytesIO()
    image.save(buf, format="JPEG", comment=b"secret camera notes")
    png = muse(FakeImages(buf.getvalue())).generate("A park", (400, 300), seed=0)

    assert png.startswith(bytes.fromhex("89504e470d0a1a0a"))
    assert imaging.load(png).info == {}


@pytest.mark.parametrize("error", [server_error(), timeout_error()])
def test_api_errors_become_one_error_type(error: Exception) -> None:
    with pytest.raises(ImageError):
        muse(FakeImages(error)).generate("A park", (1024, 768), seed=0)


def test_an_unreadable_picture_is_an_image_error() -> None:
    with pytest.raises(ImageError):
        muse(FakeImages(b"not a picture")).generate("A park", (1024, 768), seed=0)


def test_contributor_models_and_missing_settings_are_refused() -> None:
    with pytest.raises(ValueError, match="contributor"):
        MuseImageProvider(api_key="k", model="muse-image-1.0-contributor", base_url="http://x")
    with pytest.raises(ValueError, match="META_IMAGE_MODEL"):
        MuseImageProvider(api_key="k", model="", base_url="http://x")
    with pytest.raises(ValueError, match="META_API_KEY"):
        MuseImageProvider(api_key="", model="muse-image-1.0", base_url="http://x")


def test_muse_without_meta_stops_startup(tmp_path: Path) -> None:
    settings = make_settings(
        tmp_path / "storage",
        image_provider="muse",
        meta_api_key="k",
        meta_image_model="muse-image-1.0",
    )
    with pytest.raises(ValueError, match="LLM_PROVIDER=meta"), TestClient(create_app(settings)):
        pass
    assert not (tmp_path / "storage").exists()  # refused before anything was touched


def test_muse_with_meta_starts(tmp_path: Path) -> None:
    settings = make_settings(
        tmp_path / "storage",
        llm_provider="meta",
        image_provider="muse",
        meta_api_key="k",
        meta_model="muse-spark-1.3",
        meta_image_model="muse-image-1.0",
        seed_on_startup=False,
    )
    with TestClient(create_app(settings)) as client:
        assert isinstance(app_state(client).image_provider, MuseImageProvider)
        assert client.get("/api/health").json()["image_provider"] == "muse"


# ---- place lock with Muse ----------------------------------------------------------------------


def new_place(client: TestClient, name: str = "Treehouse") -> str:
    body = {"name": name, "description": "A wooden treehouse with a rope ladder."}
    place_id: str = client.post("/api/backgrounds", json=body).json()["id"]
    return place_id


def image_verdicts(client: TestClient, place_id: str) -> list[tuple[str, list[str]]]:
    with Session(app_state(client).engine) as session:
        stmt = select(ModerationLog).where(
            ModerationLog.kind == "image",
            col(ModerationLog.target).startswith(f"background:{place_id}"),
        )
        return [
            (r.verdict, r.categories)
            for r in session.exec(stmt.order_by(col(ModerationLog.created_at)))
        ]


def saved_files(client: TestClient, place_id: str) -> list[Path]:
    folder: Path = app_state(client).storage.root / "backgrounds" / place_id
    return [p for p in folder.rglob("*") if p.is_file()] if folder.exists() else []


def lock(client: TestClient, place_id: str) -> Any:
    return client.post(f"/api/backgrounds/{place_id}/lock")


def test_the_words_are_classified_before_anything_goes_to_muse(client: TestClient) -> None:
    meta = use_meta(client)
    images = use_muse(client)
    place_id = new_place(client)

    res = lock(client, place_id)

    assert res.status_code == 202
    checked = [user_text(c) for c in meta.calls_for("safety_verdicts")]
    assert checked and "Treehouse" in checked[0] and "rope ladder" in checked[0]
    assert wait_for_job(client, res.json()["job_id"])["status"] == "done"
    assert len(images.calls) == 1
    assert image_verdicts(client, place_id) == [("allow", [])]
    place = client.get(f"/api/backgrounds/{place_id}").json()
    assert place["status"] == "locked"
    assert imaging.load(client.get(place["image_url"]).content).size == (1024, 768)


def test_unsafe_words_never_reach_muse(client: TestClient) -> None:
    meta = use_meta(client)
    meta.replies["safety_verdicts"] = flag("rope ladder", "scary")
    images = use_muse(client)
    place_id = new_place(client)

    res = lock(client, place_id)

    assert (res.status_code, res.json()["code"]) == (422, "unsafe")
    assert images.calls == []


def test_a_classifier_outage_sends_nothing_and_keeps_the_draft(client: TestClient) -> None:
    meta = use_meta(client)
    meta.replies["safety_verdicts"] = server_error()
    images = use_muse(client)
    place_id = new_place(client)

    res = lock(client, place_id)

    assert (res.status_code, res.json()["code"]) == (503, "not_checked")
    assert "Treehouse" in res.json()["message"]
    assert images.calls == []
    assert client.get(f"/api/backgrounds/{place_id}").json()["status"] == "draft"


def test_mock_places_keep_the_word_list_only(client: TestClient) -> None:
    meta = use_meta(client)
    meta.replies["safety_verdicts"] = server_error()  # an outage doesn't block a mock Lock
    place_id = new_place(client)

    res = lock(client, place_id)

    assert res.status_code == 202
    assert wait_for_job(client, res.json()["job_id"])["status"] == "done"
    assert meta.calls_for("image_safety") == []  # mock pictures aren't sent to the checker


def test_a_picture_with_writing_is_painted_again_without_any(client: TestClient) -> None:
    meta = use_meta(client)
    meta.replies["image_safety"] = [picture(has_text_or_logos=True), picture()]
    images = use_muse(client)
    place_id = new_place(client)

    job = wait_for_job(client, lock(client, place_id).json()["job_id"])

    assert job["status"] == "done"
    assert len(images.calls) == 2
    assert render("background_no_text") not in images.calls[0]["prompt"]
    assert images.calls[1]["prompt"].endswith(render("background_no_text"))
    assert image_verdicts(client, place_id) == [("block", ["text"]), ("allow", [])]
    # Only the picture that passed was saved.
    saved = {p.name for p in saved_files(client, place_id)}
    assert saved == {"reference.png", "thumb.png"}


def test_two_blocked_pictures_fail_the_job_and_save_nothing(client: TestClient) -> None:
    meta = use_meta(client)
    meta.replies["image_safety"] = picture(is_scary=True)
    images = use_muse(client)
    place_id = new_place(client)

    job = wait_for_job(client, lock(client, place_id).json()["job_id"])

    assert (job["status"], job["error"]) == ("failed", CANT_PAINT.format(name="Treehouse"))
    assert len(images.calls) == 2
    assert render("background_no_text") not in images.calls[1]["prompt"]  # not blocked for text
    assert image_verdicts(client, place_id) == [("block", ["scary"]), ("block", ["scary"])]
    assert saved_files(client, place_id) == []
    assert client.get(f"/api/backgrounds/{place_id}").json()["status"] == "failed"


def test_an_image_check_outage_fails_at_once_and_saves_nothing(client: TestClient) -> None:
    meta = use_meta(client)
    meta.replies["image_safety"] = server_error()
    images = use_muse(client)
    place_id = new_place(client)

    job = wait_for_job(client, lock(client, place_id).json()["job_id"])

    assert (job["status"], job["error"]) == ("failed", CHECKER_RESTING.format(name="Treehouse"))
    assert len(images.calls) == 1
    assert image_verdicts(client, place_id) == [("block", ["unavailable"])]
    assert saved_files(client, place_id) == []


def test_a_muse_error_is_the_kid_message_not_the_generic_one(client: TestClient) -> None:
    use_meta(client)
    images = use_muse(client, FakeImages(server_error()))
    place_id = new_place(client)

    job = wait_for_job(client, lock(client, place_id).json()["job_id"])

    assert (job["status"], job["error"]) == ("failed", CANT_PAINT.format(name="Treehouse"))
    assert len(images.calls) == 2  # one more try, like a picture that came out wrong
    assert saved_files(client, place_id) == []
