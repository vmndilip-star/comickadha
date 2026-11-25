"""Big groups in one panel (Phase 8, step 4): with 4 or more characters everyone shrinks a little
and stands in two rows, so every face shows, nobody is cut off at the edge, no bubble covers a
face, and every tail points at its speaker. Checked on the real drawings (alpha masks) with the
Sniffy comic's five characters, in every panel size and a mix of poses."""

import io
from typing import Any

import pytest
from PIL import Image, ImageChops, ImageOps

from app.avatar import rig
from app.avatar.render import render_pose
from app.avatar.spec import normalize
from app.services import bubbles, compositor, stage
from app.starters import STARTERS

STARTER = {s["name"]: s["spec"] for s in STARTERS}
SNIFFY = normalize({"body_type": "dog", "extras": ["cape"], "parts": {"headwear": "cap"}})
CAST = {
    "sniffy": SNIFFY,
    "leo": STARTER["Leo"],
    "hari": STARTER["Mr. Hari"],
    "barnaby": STARTER["Barnaby"],
    "nana": STARTER["Nana Rose"],
}
POSITIONS = ["far_left", "left", "center", "right", "far_right"]
POSE_SETS = {
    "standing": ["front"] * 5,
    "busy": ["point", "wave", "front", "celebrate", "hands_on_hips"],
    "night": ["point", "asleep", "scared_pose", "front", "thinking"],
}
SCALE = 1.0  # pixels per unit for the masks (800 x 600 for a normal panel)


def chars(poses: list[str], count: int = 5) -> list[dict[str, Any]]:
    ids = list(CAST)[:count]
    return [
        {
            "id": cid,
            "sheet_version": 1,
            "pose": pose,
            "expression": "happy",
            "position": pos,
            "scale": 1.0,
        }
        for cid, pose, pos in zip(
            ids,
            poses,
            POSITIONS[:count] if count > 3 else ["left", "center", "right"],
            strict=False,
        )
    ]


def masks(laid: stage.StageLayout) -> tuple[tuple[int, int], dict[str, Image.Image]]:
    """Each character's drawn alpha on a panel-sized canvas (mirrored where it is drawn so)."""
    w, h = round(laid.frame.w * SCALE), round(laid.frame.h * SCALE)
    out: dict[str, Image.Image] = {}
    for p in laid.characters:
        x, y, cw, ch = p.cell
        side = round(ch * h)
        cell = Image.open(io.BytesIO(render_pose(p.spec, p.pose, side, p.expression))).getchannel(
            "A"
        )
        if p.mirror:
            cell = ImageOps.mirror(cell)
        canvas = Image.new("L", (w, h), 0)
        canvas.paste(cell, (round(x * w), round(y * h)))
        out[p.id] = canvas
    return (w, h), out


def head_pixels(p: stage.Placement, size: tuple[int, int]) -> tuple[int, int, int, int]:
    x, y, hw, hh = p.head
    w, h = size
    return (round(x * w), round(y * h), round((x + hw) * w), round((y + hh) * h))


def count(image: Image.Image) -> int:
    return sum(image.histogram()[1:])


@pytest.mark.parametrize("size", ["normal", "wide", "splash"])
@pytest.mark.parametrize("poses", list(POSE_SETS))
@pytest.mark.parametrize("people", [4, 5])
def test_every_face_shows_and_nobody_is_cut_off(size: str, poses: str, people: int) -> None:
    laid = stage.layout(chars(POSE_SETS[poses], people), CAST, size=size)
    dims, drawn = masks(laid)
    order = [laid.characters[i].id for kind, i in laid.order if kind == "character"]
    for p in laid.characters:
        box = head_pixels(p, dims)
        own = drawn[p.id].crop(box).point(lambda v: 255 if v > 128 else 0)
        in_front = [drawn[o] for o in order[order.index(p.id) + 1 :]]
        covered = Image.new("L", own.size, 0)
        for other in in_front:
            covered = ImageChops.lighter(
                covered, other.crop(box).point(lambda v: 255 if v > 128 else 0)
            )
        hidden = count(ImageChops.multiply(own, covered)) / max(1, count(own))
        assert hidden < 0.12, f"{p.id}'s face is {hidden:.0%} hidden ({size}, {poses})"
        left, right = stage.drawn_span(p.spec, p.pose, p.expression, p.mirror)
        x0 = p.cell[0] + left / rig.CANVAS * p.cell[2]
        x1 = p.cell[0] + right / rig.CANVAS * p.cell[2]
        assert x0 >= 0 and x1 <= 1, f"{p.id} is cut off ({x0:.3f}-{x1:.3f}, {size}, {poses})"
    assert {p.row for p in laid.characters} == {0, 1}  # two rows
    fronts = [p.cell[3] for p in laid.characters if p.row == 0]
    assert max(fronts) < stage.frame_for(size).figure  # everyone a bit smaller


@pytest.mark.parametrize("size", ["normal", "wide", "splash"])
def test_bubbles_never_cover_a_face_and_tails_find_their_speaker(size: str) -> None:
    group = chars(POSE_SETS["busy"])
    said = [
        {
            "id": "n",
            "speaker": "narrator",
            "type": "narrator",
            "text": "Later that night, in the field...",
        },
        {"id": "a", "speaker": "barnaby", "type": "talk", "text": "Um... I only wanted a hug."},
        {"id": "b", "speaker": "sniffy", "type": "shout", "text": "Case closed, everyone!"},
    ]
    laid = bubbles.layout(said, group, CAST, size)
    placed = {p.id: p for p in stage.place(group, CAST, size)}
    for bubble in laid:
        bx, by, bw, bh = bubble["box"]
        for p in placed.values():
            hx, hy, hw, hh = p.head
            overlap_w = min(bx + bw, hx + hw) - max(bx, hx)
            overlap_h = min(by + bh, hy + hh) - max(by, hy)
            assert overlap_w <= 0 or overlap_h <= 0, f"{bubble['id']} covers {p.id}'s face ({size})"
        if bubble["speaker"] != "narrator":
            assert tuple(bubble["tail"]) == placed[bubble["speaker"]].head_target


def test_three_or_fewer_stand_where_they_always_did() -> None:
    """Old comics never change: up to 3 at left, center and right keep the old spots and sizes."""
    old = stage.place(chars(["front"] * 3, 3), CAST)
    assert [round(p.center_x, 4) for p in old] == [0.22, 0.5, 0.78]
    assert all(p.cell[3] == stage.FIGURE and p.row == 0 for p in old)


def test_five_characters_draw_into_one_panel() -> None:
    art, _ = compositor.render_art(chars(POSE_SETS["standing"]), CAST, None, "#DDF0FC", [])
    with Image.open(io.BytesIO(art)) as image:
        assert image.size == (1600, 1200)
