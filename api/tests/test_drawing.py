"""Make a character from a drawing (/api/builder/from-drawing), and the grown-up consent."""

import base64
import io
import os
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from PIL import Image, PngImagePlugin

from app.avatar import spec as avatar_spec
from app.config import Settings
from app.services.builder_helper import META_LABEL, OFFLINE_LABEL, RESTING
from app.services.drawing import MAX_BYTES, MAX_SIDE
from tests.fakes import (
    VISION_MODEL,
    data_url,
    drawing,
    photo,
    server_error,
    suggestion,
    use_meta,
)

KID = avatar_spec.validate({"body_type": "kid"})
MARKER = "secret-marker-7f3a9c"  # hidden in the upload's PNG metadata


def from_drawing(client: TestClient, image: str, spec: dict[str, Any] = KID) -> Any:
    return client.post("/api/builder/from-drawing", json={"image": image, "spec": spec})


def give_consent(client: TestClient) -> Any:
    return client.put("/api/me/drawing-consent", json={"a": 7, "b": 8, "answer": 56})


def marked_drawing() -> str:
    info = PngImagePlugin.PngInfo()
    info.add_text("Comment", MARKER)
    return data_url(drawing(900), pnginfo=info)


def snapshot(root: Path) -> dict[str, bytes]:
    return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()}


def sent_image(call: dict[str, Any]) -> Image.Image:
    part = next(p for p in call["messages"][1]["content"] if p["type"] == "image_url")
    url: str = part["image_url"]["url"]
    assert url.startswith("data:image/png;base64,")
    return Image.open(io.BytesIO(base64.b64decode(url.split(",", 1)[1])))


# ---- offline -------------------------------------------------------------------------------


def test_offline_reads_the_drawings_colours_without_consent(client: TestClient) -> None:
    res = from_drawing(client, data_url(drawing()))

    assert res.status_code == 200, res.json()
    out = res.json()
    assert avatar_spec.validate(out["spec"]) == out["spec"]
    assert out["spec"]["colors"]["top"] == "#E53935"  # the red jumper in the drawing
    assert "colors.top" in out["changed"]
    assert (out["source"], out["fallback"], out["label"]) == ("mock", False, OFFLINE_LABEL)


def test_a_photo_is_refused_as_not_a_drawing(client: TestClient) -> None:
    res = from_drawing(client, data_url(photo(), "JPEG"))

    assert res.status_code == 422
    assert res.json()["code"] == "not_a_drawing"


def test_over_5_mb_is_413(client: TestClient) -> None:
    payload = base64.b64encode(os.urandom(MAX_BYTES + 1)).decode()

    res = from_drawing(client, "data:image/png;base64," + payload)

    assert res.status_code == 413
    assert res.json()["code"] == "too_big"


def test_well_over_5_mb_is_still_413_not_a_validation_error(client: TestClient) -> None:
    payload = base64.b64encode(os.urandom(MAX_BYTES * 2)).decode()

    assert from_drawing(client, "data:image/png;base64," + payload).status_code == 413


def test_just_under_5_mb_is_not_refused_for_size(client: TestClient) -> None:
    payload = base64.b64encode(os.urandom(MAX_BYTES - 16)).decode()

    res = from_drawing(client, "data:image/png;base64," + payload)

    assert (res.status_code, res.json()["code"]) == (422, "invalid")  # random bytes, not a PNG


def test_something_that_is_not_a_picture_is_422(client: TestClient) -> None:
    for bad in ("hello", "data:text/plain;base64,aGk=", "data:image/png;base64,!!!"):
        res = from_drawing(client, bad)
        assert (res.status_code, res.json()["code"]) == (422, "invalid"), bad


def test_the_upload_is_never_written_to_disk_or_the_database(
    client: TestClient, settings: Settings
) -> None:
    upload = marked_drawing()
    encoded = upload.split(",", 1)[1]
    before = snapshot(settings.storage_dir)

    assert from_drawing(client, upload).status_code == 200

    after = snapshot(settings.storage_dir)
    new_files = set(after) - set(before)
    assert all(name.startswith("comickatha.db") for name in new_files), new_files
    media = {k for k in after if k.startswith("media")}
    assert media == {k for k in before if k.startswith("media")}
    for name, data in after.items():
        if data == before.get(name):
            continue
        assert MARKER.encode() not in data, name
        assert encoded[1000:1100].encode() not in data, name


# ---- Meta: needs a grown-up's OK, and sends a clean, small copy -----------------------------


def test_meta_needs_a_grown_ups_consent_first(client: TestClient) -> None:
    fake = use_meta(client)

    res = from_drawing(client, data_url(drawing()))

    assert res.status_code == 403
    assert res.json()["code"] == "consent_needed"
    assert fake.calls == []  # nothing was sent


def test_the_consent_check_needs_the_right_answer(client: TestClient) -> None:
    wrong = client.put("/api/me/drawing-consent", json={"a": 7, "b": 8, "answer": 54})
    easy = client.put("/api/me/drawing-consent", json={"a": 2, "b": 3, "answer": 6})

    assert (wrong.status_code, wrong.json()["code"]) == (422, "wrong_answer")
    assert easy.status_code == 422  # questions are 6-12 times tables
    assert client.get("/api/me").json()["drawing_consent_at"] is None


def test_with_consent_meta_gets_a_clean_downscaled_png(client: TestClient) -> None:
    fake = use_meta(client)
    fake.replies["drawing_suggestion"] = suggestion(
        KID,
        is_drawing=True,
        shows_real_person=False,
        safe_for_kids=True,
        parts={"hair": "two_puffs"},
        colors={"top": "red"},
        reply="Love the red jumper!",
    )
    consent = give_consent(client)
    assert consent.status_code == 200 and consent.json()["drawing_consent_at"]
    assert client.get("/api/builder/info").json()["drawing_consent"] is True

    res = from_drawing(client, marked_drawing())

    assert res.status_code == 200, res.json()
    out = res.json()
    assert out["spec"]["parts"]["hair"] == "two_puffs"
    assert out["spec"]["colors"]["top"] == "#E53935"
    assert (out["source"], out["label"]) == ("meta", META_LABEL)
    [call] = fake.calls_for("drawing_suggestion")
    assert call["model"] == VISION_MODEL
    image = sent_image(call)
    assert max(image.size) <= MAX_SIDE
    assert MARKER not in str(image.info)  # metadata stripped


def test_consent_can_be_taken_back(client: TestClient) -> None:
    use_meta(client)
    give_consent(client)

    assert client.delete("/api/me/drawing-consent").json()["drawing_consent_at"] is None
    assert from_drawing(client, data_url(drawing())).status_code == 403


def test_meta_can_say_it_is_not_a_drawing(client: TestClient) -> None:
    fake = use_meta(client)
    give_consent(client)
    fake.replies["drawing_suggestion"] = suggestion(
        KID, is_drawing=False, shows_real_person=True, safe_for_kids=True
    )

    res = from_drawing(client, data_url(drawing()))

    assert (res.status_code, res.json()["code"]) == (422, "not_a_drawing")


def test_meta_can_say_a_drawing_is_unsafe(client: TestClient) -> None:
    fake = use_meta(client)
    give_consent(client)
    fake.replies["drawing_suggestion"] = suggestion(
        KID, is_drawing=True, shows_real_person=False, safe_for_kids=False
    )

    res = from_drawing(client, data_url(drawing()))

    assert (res.status_code, res.json()["code"]) == (422, "unsafe")


def test_meta_down_falls_back_to_reading_colours_offline(client: TestClient) -> None:
    fake = use_meta(client)
    give_consent(client)
    fake.replies["drawing_suggestion"] = server_error()

    out = from_drawing(client, data_url(drawing())).json()

    assert (out["source"], out["fallback"], out["label"]) == ("mock", True, OFFLINE_LABEL)
    assert out["reply"].startswith(RESTING)
    assert out["spec"]["colors"]["top"] == "#E53935"


def test_meta_down_still_refuses_a_photo(client: TestClient) -> None:
    fake = use_meta(client)
    give_consent(client)
    fake.replies["drawing_suggestion"] = server_error()

    res = from_drawing(client, data_url(photo(), "JPEG"))

    assert (res.status_code, res.json()["code"]) == (422, "not_a_drawing")
