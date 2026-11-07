"""Make my comic!: pinned looks, the generate job, re-drawing panels, final.png, cover and PDF."""

import re
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.models import Comic, Job, Panel
from app.services.jobs import PANEL_INTERRUPTED, fail_interrupted_jobs
from tests.conftest import IDS, app_state, sse_events, wait_for_job
from tests.fakes import server_error, use_meta

STORY = "Mira and Raju follow sticky footprints to the school garden and find the mango."


def planned_comic(
    client: TestClient, panels: int = 6, cast: tuple[str, ...] = ("mira", "raju")
) -> dict[str, Any]:
    comic_id = client.post("/api/comics", json={"title": "Mango Hunt", "synopsis": STORY}).json()[
        "id"
    ]
    client.patch(
        f"/api/comics/{comic_id}",
        json={"cast_ids": [IDS[c] for c in cast], "panel_count": panels},
    )
    assert client.post(f"/api/studio/{comic_id}/plan-scenes", json={}).status_code == 200
    assert client.post(f"/api/studio/{comic_id}/plan-panels", json={}).status_code == 200
    return comic(client, comic_id)


def comic(client: TestClient, comic_id: str) -> dict[str, Any]:
    data: dict[str, Any] = client.get(f"/api/comics/{comic_id}").json()
    return data


def generate(client: TestClient, comic_id: str) -> str:
    res = client.post(f"/api/comics/{comic_id}/generate")
    assert res.status_code == 202, res.json()
    assert res.json()["kind"] == "comic"
    job_id: str = res.json()["job_id"]
    assert wait_for_job(client, job_id)["status"] == "done"
    return job_id


def made_comic(client: TestClient, panels: int = 6) -> dict[str, Any]:
    c = planned_comic(client, panels)
    generate(client, c["id"])
    return comic(client, c["id"])


def art(client: TestClient, panel: dict[str, Any]) -> bytes:
    res = client.get(panel["art_url"])
    assert res.status_code == 200
    return res.content


def set_panel(client: TestClient, panel_id: str, **fields: Any) -> None:
    with Session(app_state(client).engine) as session:
        panel = session.get(Panel, panel_id)
        assert panel is not None
        for key, value in fields.items():
            setattr(panel, key, value)
        session.add(panel)
        session.commit()


# ---- pinned looks -------------------------------------------------------------------------


def test_relocking_with_a_new_hat_never_changes_an_old_comic(client: TestClient) -> None:
    old = made_comic(client)
    with_mira = next(
        p for p in old["panels"] if any(c["id"] == IDS["mira"] for c in p["characters"])
    )
    before = art(client, with_mira)
    assert old["looks"][IDS["mira"]]["1"]["parts"]["headwear"] == "none"

    client.post(f"/api/characters/{IDS['mira']}/unlock")
    spec = client.get(f"/api/characters/{IDS['mira']}").json()["spec"]
    spec["parts"]["headwear"] = "cap"
    assert client.patch(f"/api/characters/{IDS['mira']}", json={"spec": spec}).status_code == 200
    job = client.post(f"/api/characters/{IDS['mira']}/lock").json()["job_id"]
    assert wait_for_job(client, job)["status"] == "done"

    again = comic(client, old["id"])
    assert again["looks"] == old["looks"]  # still the version-1 look, no cap
    redrawn = client.post(f"/api/panels/{with_mira['id']}/render").json()
    assert art(client, redrawn) == before  # drawn again from the pinned look: identical
    # A new comic uses the new look.
    fresh = planned_comic(client)
    assert fresh["looks"][IDS["mira"]]["2"]["parts"]["headwear"] == "cap"


# ---- the generate job ---------------------------------------------------------------------


def test_make_my_comic_draws_every_panel_live_then_the_cover(client: TestClient) -> None:
    c = planned_comic(client)
    job_id = generate(client, c["id"])

    events = sse_events(client, job_id)
    ready = [e for e in events if e[1] == "panel_ready"]
    assert [e[2]["panel"]["idx"] for e in ready] == list(range(6))
    assert events[-1][1] == "done" and events[-1][2]["cover_url"]
    done = comic(client, c["id"])
    assert {p["status"] for p in done["panels"]} == {"ready"}
    assert done["last_job_id"] == job_id and done["cover_url"]
    assert client.get(done["cover_url"]).status_code == 200
    assert all(p["art_url"].endswith("?v=1") and p["thumb_url"] for p in done["panels"])


def test_events_replay_on_reconnect(client: TestClient) -> None:
    c = planned_comic(client, panels=4)
    job_id = generate(client, c["id"])
    every = sse_events(client, job_id)

    assert sse_events(client, job_id, after=3) == every[3:]
    assert sse_events(client, job_id, last_event_id=5) == every[5:]


def test_make_my_comic_needs_a_full_plan(client: TestClient) -> None:
    comic_id = client.post("/api/comics", json={"title": "Empty", "synopsis": STORY}).json()["id"]
    res = client.post(f"/api/comics/{comic_id}/generate")
    assert (res.status_code, res.json()["code"]) == (409, "needs_plan")


def test_make_my_comic_needs_everyone_locked(client: TestClient) -> None:
    c = planned_comic(client)
    panel = c["panels"][0]
    robo = {"id": IDS["robo"], "sheet_version": 0, "pose": "front", "expression": "happy",
            "position": "center", "scale": 1.0}  # fmt: skip
    others = [ch for ch in panel["characters"] if ch["position"] != "center"]
    client.patch(f"/api/panels/{panel['id']}", json={"characters": [*others, robo]})

    res = client.post(f"/api/comics/{c['id']}/generate")

    assert (res.status_code, res.json()["code"]) == (409, "needs_locked")
    assert "Robo-Tik" in res.json()["message"]


def test_a_blocked_bubble_fails_only_its_panel(client: TestClient) -> None:
    c = planned_comic(client)
    bad = c["panels"][2]
    words = [{**bad["bubbles"][0], "text": "Grab the gun!"}]
    set_panel(client, bad["id"], bubbles=words)

    events = sse_events(client, generate(client, c["id"]))

    failed = [e[2]["panel"] for e in events if e[1] == "panel_failed"]
    assert [(p["id"], p["status"]) for p in failed] == [(bad["id"], "blocked")]
    assert "friendly" in failed[0]["error"]
    assert len([e for e in events if e[1] == "panel_ready"]) == 5


def test_fixing_a_blocked_bubble_draws_its_panel(client: TestClient) -> None:
    c = planned_comic(client)
    bad = c["panels"][2]
    set_panel(client, bad["id"], bubbles=[{**bad["bubbles"][0], "text": "Grab the gun!"}])
    generate(client, c["id"])
    blocked = comic(client, c["id"])["panels"][2]
    assert blocked["status"] == "blocked" and blocked["art_url"] is None

    fixed = [{**blocked["bubbles"][0], "text": "Grab the mango!"}]
    res = client.patch(f"/api/panels/{bad['id']}", json={"bubbles": fixed})

    assert res.status_code == 200
    assert res.json()["status"] == "ready" and res.json()["art_url"]


def test_a_blocked_title_stops_before_drawing(client: TestClient) -> None:
    c = planned_comic(client)
    client.patch(f"/api/comics/{c['id']}", json={"title": "Call 07700 900 123"})
    res = client.post(f"/api/comics/{c['id']}/generate")
    assert (res.status_code, res.json()["field"]) == (422, "title")


def test_pressing_make_again_while_drawing_reconnects(client: TestClient) -> None:
    c = planned_comic(client)
    state = app_state(client)
    with Session(state.engine) as session:
        job = Job(kind="comic", target_id=c["id"], status="running")
        session.add(job)
        session.commit()
        job_id = job.id
    with Session(state.engine) as session:
        row = session.get(Comic, c["id"])
        assert row is not None
        row.last_job_id = job_id
        session.add(row)
        session.commit()
    assert client.post(f"/api/comics/{c['id']}/generate").json()["job_id"] == job_id


def test_panels_left_mid_drawing_by_a_restart_can_be_tried_again(client: TestClient) -> None:
    c = planned_comic(client)
    state = app_state(client)
    set_panel(client, c["panels"][1]["id"], status="rendering")
    with Session(state.engine) as session:
        session.add(Job(kind="comic", target_id=c["id"], status="running"))
        session.commit()

    fail_interrupted_jobs(state.engine)

    panel = comic(client, c["id"])["panels"][1]
    assert (panel["status"], panel["error"]) == ("failed", PANEL_INTERRUPTED)
    retried = client.post(f"/api/panels/{panel['id']}/render").json()
    assert retried["status"] == "ready" and retried["error"] is None


# ---- re-drawing ---------------------------------------------------------------------------


def test_a_face_change_redraws_only_that_panel(client: TestClient) -> None:
    c = made_comic(client)
    target = c["panels"][1]
    first = target["characters"][0]
    face = "sad" if first["expression"] != "sad" else "angry"
    before = art(client, target)

    res = client.patch(
        f"/api/panels/{target['id']}",
        json={"characters": [{**first, "expression": face}, *target["characters"][1:]]},
    )

    assert res.status_code == 200 and res.json()["art_url"].endswith("?v=2")
    assert art(client, res.json()) != before
    versions = [p["art_url"].rsplit("=", 1)[1] for p in comic(client, c["id"])["panels"]]
    assert versions == ["1", "2", "1", "1", "1", "1"]


def test_a_text_change_redraws_nothing(client: TestClient) -> None:
    c = made_comic(client)
    target = next(p for p in c["panels"] if p["bubbles"])
    before = art(client, target)
    final_before = client.get(target["final_url"]).content

    words = [{**target["bubbles"][0], "text": "A brand new line!"}, *target["bubbles"][1:]]
    res = client.patch(f"/api/panels/{target['id']}", json={"bubbles": words})

    assert res.json()["art_url"] == target["art_url"]
    assert art(client, res.json()) == before
    assert client.get(target["final_url"]).content != final_before  # final.png re-lettered


def test_final_png_is_only_baked_again_when_stale(client: TestClient) -> None:
    c = made_comic(client, panels=4)
    panel = c["panels"][0]
    first = client.get(panel["final_url"])
    assert first.headers["content-type"] == "image/png"
    with Session(app_state(client).engine) as session:
        row = session.get(Panel, panel["id"])
        assert row is not None
        key, digest = row.final_key, row.final_hash
    assert client.get(panel["final_url"]).content == first.content
    with Session(app_state(client).engine) as session:
        row = session.get(Panel, panel["id"])
        assert row is not None and (row.final_key, row.final_hash) == (key, digest)


def test_a_drag_keeps_the_bubble_where_the_kid_put_it(client: TestClient) -> None:
    c = made_comic(client, panels=4)
    target = next(
        p for p in c["panels"] if p["bubbles"] and p["bubbles"][0]["speaker"] != "narrator"
    )
    moved = {**target["bubbles"][0], "box": [0.55, 0.6, 0.3, 0.14], "fixed": True}

    res = client.patch(
        f"/api/panels/{target['id']}", json={"bubbles": [moved, *target["bubbles"][1:]]}
    )

    bubble = res.json()["bubbles"][0]
    assert bubble["box"] == [0.55, 0.6, 0.3, 0.14] and bubble["fixed"] is True
    assert bubble["tail"] == target["bubbles"][0]["tail"]  # still aimed at the same head
    assert res.json()["art_url"] == target["art_url"]


# ---- finishing ----------------------------------------------------------------------------


def test_finishing_needs_drawn_panels_and_editing_makes_it_a_draft(client: TestClient) -> None:
    c = planned_comic(client)
    res = client.patch(f"/api/comics/{c['id']}", json={"status": "finished"})
    assert (res.status_code, res.json()["code"]) == (409, "not_ready")

    generate(client, c["id"])
    assert (
        client.patch(f"/api/comics/{c['id']}", json={"status": "finished"}).json()["status"]
        == "finished"
    )
    assert (
        client.patch(f"/api/comics/{c['id']}", json={"title": "Mango Hunt 2"}).json()["status"]
        == "draft"
    )


# ---- PDF ----------------------------------------------------------------------------------


def page_count(pdf: bytes) -> int:
    return len(re.findall(rb"/Type\s*/Page(?![s\w])", pdf))


@pytest.mark.parametrize(("panels", "pages"), [(4, 2), (6, 2), (8, 3)])
def test_the_pdf_has_a_cover_then_six_panels_a_page(
    client: TestClient, panels: int, pages: int
) -> None:
    c = made_comic(client, panels)
    res = client.get(f"/api/comics/{c['id']}/pdf")
    assert res.status_code == 200 and res.headers["content-type"] == "application/pdf"
    assert res.content.startswith(b"%PDF")
    assert 'filename="mango-hunt.pdf"' in res.headers["content-disposition"]
    assert page_count(res.content) == pages


def test_the_pdf_waits_for_every_panel(client: TestClient) -> None:
    c = planned_comic(client)
    res = client.get(f"/api/comics/{c['id']}/pdf")
    assert (res.status_code, res.json()["code"]) == (409, "not_ready")
    assert "Panel 1" in res.json()["message"]


def test_the_pdf_waits_for_the_ai_check(client: TestClient) -> None:
    """Decision 55: words saved during an outage block the PDF until Meta checks them."""
    c = made_comic(client)
    fake = use_meta(client)
    fake.replies["safety_verdicts"] = server_error()
    target = next(p for p in c["panels"] if p["bubbles"])
    words = [{**target["bubbles"][0], "text": "Saved while Meta rests"}, *target["bubbles"][1:]]
    assert (
        client.patch(f"/api/panels/{target['id']}", json={"bubbles": words}).json()["text_check"]
        == "pending"
    )

    res = client.get(f"/api/comics/{c['id']}/pdf")
    assert (res.status_code, res.json()["code"]) == (409, "not_checked")

    del fake.replies["safety_verdicts"]  # Meta is back: the PDF re-checks first
    assert client.get(f"/api/comics/{c['id']}/pdf").status_code == 200
    assert comic(client, c["id"])["panels"][target["idx"]]["text_check"] == "checked"
