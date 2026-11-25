"""Phase 8, step 5: the 12-word stop, and places at day, sunset and night."""

import io
from typing import Any

from fastapi.testclient import TestClient
from PIL import Image, ImageStat
from sqlmodel import Session

from app.models import Background, Panel
from app.services import image_gen, imaging
from tests.conftest import IDS, app_state, wait_for_job
from tests.test_make_comic import comic, generate, planned_comic


def brightness(png: bytes) -> float:
    with Image.open(io.BytesIO(png)) as image:
        return float(sum(ImageStat.Stat(image.convert("L")).mean))


# ---- 12 words is the most ------------------------------------------------------------------------


def test_a_bubble_over_12_words_is_refused_under_that_bubble(client: TestClient) -> None:
    panel = planned_comic(client, 4)["panels"][1]
    speaker = panel["characters"][0]["id"]
    long = {"id": "b1", "speaker": speaker, "type": "talk", "text": " ".join(["word"] * 13)}
    res = client.patch(f"/api/panels/{panel['id']}", json={"bubbles": [long]})
    assert res.status_code == 422
    assert res.json()["field"] == "bubbles.b1.text" and "13 words" in res.json()["message"]
    twelve = {**long, "text": " ".join(["word"] * 12)}
    assert client.patch(f"/api/panels/{panel['id']}", json={"bubbles": [twelve]}).status_code == 200


# ---- places at day, sunset and night -------------------------------------------------------------


def new_place(client: TestClient, name: str = "Mango grove") -> dict[str, Any]:
    made = client.post(
        "/api/backgrounds", json={"name": name, "description": "Trees full of mangoes."}
    ).json()
    job = client.post(f"/api/backgrounds/{made['id']}/lock").json()["job_id"]
    assert wait_for_job(client, job)["status"] == "done"
    place: dict[str, Any] = client.get(f"/api/backgrounds/{made['id']}").json()
    return place


def test_a_new_place_is_painted_at_day_sunset_and_night(client: TestClient) -> None:
    place = new_place(client)
    assert place["times"] == ["day", "sunset", "night"]
    storage = app_state(client).storage
    v = int(place["version"])
    day = storage.read(f"backgrounds/{place['id']}/v{v}/reference.png")
    night = storage.read(image_gen.time_key(place["id"], v, "night"))
    sunset = storage.read(image_gen.time_key(place["id"], v, "sunset"))
    assert brightness(night) < brightness(sunset) < brightness(day)  # the same place, other light
    assert storage.exists(image_gen.time_key(place["id"], v, "night", thumb=True))


def test_a_panel_draws_its_scenes_time_of_day(client: TestClient) -> None:
    made = planned_comic(client, 4)
    scenes = made["scenes"]
    body = [
        {k: s[k] for k in ("id", "background_id", "character_ids", "summary")}
        | {"time_of_day": "night"}
        for s in scenes
    ]
    assert client.put(f"/api/comics/{made['id']}/scenes", json=body).status_code == 200
    with Session(app_state(client).engine) as session:  # the panels were planned before: night now
        for p in made["panels"]:
            row = session.get(Panel, p["id"])
            assert row is not None
            row.time_of_day = "night"
            session.add(row)
        session.commit()
    generate(client, made["id"])
    night = comic(client, made["id"])["panels"][0]
    assert night["time_of_day"] == "night"
    art = client.get(night["art_url"]).content
    with Session(app_state(client).engine) as session:
        row = session.get(Panel, night["id"])
        assert row is not None and row.place_version
        bg = session.get(Background, row.background_id)
        assert bg is not None
        day = image_gen.place_picture(app_state(client).storage, bg, row.place_version, "day")
    assert day is not None and brightness(art) < brightness(day)  # drawn darker than the day place


def test_old_places_are_tinted_until_their_times_are_painted(client: TestClient) -> None:
    storage = app_state(client).storage
    with Session(app_state(client).engine) as session:
        garden = session.get(Background, IDS["garden"])
        assert garden is not None
        for t in image_gen.TIMES:  # a place painted before Phase 8: a day picture only
            for thumb in (False, True):
                key = image_gen.time_key(garden.id, garden.version, t, thumb)
                path = storage.local_path(key)
                if path is not None and path.exists():
                    path.unlink()
        assert image_gen.painted_times(storage, garden) == ["day"]
        tinted = image_gen.place_picture(storage, garden, garden.version, "night")
        day = image_gen.place_picture(storage, garden, garden.version, "day")
        assert tinted is not None and day is not None and brightness(tinted) < brightness(day)
        assert tinted == imaging.to_png(imaging.time_tint(imaging.load(day), "night"))
    assert client.get(f"/api/backgrounds/{IDS['garden']}").json()["times"] == ["day"]

    job = client.post(f"/api/backgrounds/{IDS['garden']}/times").json()["job_id"]

    assert wait_for_job(client, job)["status"] == "done"
    after = client.get(f"/api/backgrounds/{IDS['garden']}").json()
    assert after["times"] == ["day", "sunset", "night"] and after["status"] == "locked"
    assert after["version"] == garden.version  # the same version: comics keep their pictures


def test_previews_show_the_place_at_the_panels_time(client: TestClient) -> None:
    made = planned_comic(client, 4)
    panel = made["panels"][0]
    with Session(app_state(client).engine) as session:
        row = session.get(Panel, panel["id"])
        assert row is not None
        row.time_of_day = "sunset"
        session.add(row)
        session.commit()
        version, place = row.place_version, row.background_id
    shown = comic(client, made["id"])["panels"][0]
    storage = app_state(client).storage
    if storage.exists(image_gen.time_key(place, version or 0, "sunset")):
        assert shown["place_url"].endswith("sunset_thumb.png") and shown["place_tone"] is None
    else:
        assert shown["place_url"].endswith("/thumb.png") and shown["place_tone"] == "sunset"
