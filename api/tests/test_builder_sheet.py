"""SHEET_PROVIDER=builder (the default): Lock draws every cell straight from the avatar's parts."""

from typing import Any

from fastapi.testclient import TestClient
from PIL import Image, ImageChops

from app.avatar import rig
from app.avatar.render import render_face, render_pose
from app.schemas.common import EXPRESSIONS, POSES
from app.schemas.manifest import CharacterManifest
from app.services import imaging
from app.services.builder_sheet import STYLE, as_fractions
from app.services.character_sheet import CELL
from tests.conftest import IDS, sse_events, wait_for_job


def lock_robo(client: TestClient) -> tuple[str, dict[str, Any]]:
    res = client.post(f"/api/characters/{IDS['robo']}/lock")
    assert res.status_code == 202, res.json()
    job_id: str = res.json()["job_id"]
    assert wait_for_job(client, job_id)["status"] == "done"
    robo: dict[str, Any] = client.get(f"/api/characters/{IDS['robo']}").json()
    return job_id, robo


def cell(client: TestClient, url: str) -> Image.Image:
    res = client.get(url)
    assert res.status_code == 200
    return imaging.load(res.content)


def same(a: Image.Image, b: Image.Image) -> bool:
    return (a.mode, a.size, a.tobytes()) == (b.mode, b.size, b.tobytes())


def changed_box(a: Image.Image, b: Image.Image) -> tuple[int, int, int, int] | None:
    """Where two images differ in any channel (plain getbbox() on RGBA only looks at alpha)."""
    return ImageChops.difference(a, b).getbbox(alpha_only=False)


def test_lock_draws_16_poses_and_6_faces_with_a_valid_manifest(client: TestClient) -> None:
    job_id, robo = lock_robo(client)

    assert robo["status"] == "locked" and robo["sheet_version"] == 1
    assert robo["style"] == STYLE
    manifest = CharacterManifest.model_validate(robo["manifest"])
    assert manifest.renderer == "builder"
    assert manifest.spec == robo["spec"]  # the sheet remembers exactly what it drew
    body, face = manifest.body_sheet, manifest.face_sheet
    assert set(body.cells) == set(body.cell_urls) == set(body.heads) == set(POSES)
    assert set(face.cells) == set(face.cell_urls) == set(EXPRESSIONS)
    assert (body.grid, face.grid, body.cell) == ((4, 4), (2, 3), CELL)
    assert cell(client, body.url).size == (4 * CELL[0], 4 * CELL[1])
    assert manifest.thumb_url is not None
    assert cell(client, manifest.thumb_url).size[0] <= 160

    events = sse_events(client, job_id)
    ready = [data for _, kind, data in events if kind == "cell_ready"]
    assert [d["cell"] for d in ready if d["sheet"] == "body"][0] == "front"
    assert sorted(d["cell"] for d in ready if d["sheet"] == "body") == sorted(POSES)
    assert sorted(d["cell"] for d in ready if d["sheet"] == "face") == sorted(EXPRESSIONS)
    assert events[-1][1] == "done"


def test_head_boxes_are_exact_and_come_from_the_rig(client: TestClient) -> None:
    _, robo = lock_robo(client)
    manifest = CharacterManifest.model_validate(robo["manifest"])

    for pose in POSES:
        head = manifest.body_sheet.heads[pose]
        assert head.source == "exact"
        assert head.box == as_fractions(rig.head_box("robot", pose))
        assert all(0 <= v <= 1 for v in head.box)
    assert manifest.face_sheet.head_box == as_fractions(rig.face_cell_head_box())


def test_every_cell_is_drawn_directly_with_its_own_expression(client: TestClient) -> None:
    """No face is pasted on: each pose cell is exactly the avatar rendered in that pose, with the
    pose's own expression (a scared pose looks scared, a jump laughs)."""
    _, robo = lock_robo(client)
    manifest = CharacterManifest.model_validate(robo["manifest"])
    spec = robo["spec"]

    for pose in POSES:
        drawn = cell(client, manifest.body_sheet.cell_urls[pose])
        assert same(drawn, imaging.load(render_pose(spec, pose, CELL[0]))), pose
    for expression in EXPRESSIONS:
        drawn = cell(client, manifest.face_sheet.cell_urls[expression])
        assert same(drawn, imaging.load(render_face(spec, expression, CELL[0]))), expression

    # The poses with their own expression differ from the same pose drawn smiling, and only
    # inside the head: the expression is part of the drawing, not a sticker on top.
    for pose in ("jump", "scared_pose", "celebrate"):
        drawn = cell(client, manifest.body_sheet.cell_urls[pose])
        happy = imaging.load(render_pose(spec, pose, CELL[0], expression="happy"))
        changed = changed_box(drawn, happy)
        assert changed is not None, pose
        x, y, w, h = (v * CELL[0] for v in manifest.body_sheet.heads[pose].box)
        assert x - 2 <= changed[0] and changed[2] <= x + w + 2, pose
        assert y - 2 <= changed[1] and changed[3] <= y + h + 2, pose


def test_cells_are_transparent_outside_the_character(client: TestClient) -> None:
    _, robo = lock_robo(client)
    manifest = CharacterManifest.model_validate(robo["manifest"])

    wave = cell(client, manifest.body_sheet.cell_urls["wave"])

    assert wave.mode == "RGBA"
    assert wave.getchannel("A").getpixel((0, 0)) == 0


def test_seeded_characters_have_builder_sheets(client: TestClient) -> None:
    mira = client.get(f"/api/characters/{IDS['mira']}/manifest").json()

    assert mira["renderer"] == "builder"
    assert mira["spec"]["parts"]["top"] == "raincoat"
