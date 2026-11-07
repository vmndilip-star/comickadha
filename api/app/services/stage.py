"""Where characters stand in a panel, how they face, and where their heads are.

One piece of geometry, shared by the compositor (to draw) and the bubble layout (to aim tails),
so a tail always points at the head as drawn. Coordinates are fractions of the panel (0-1);
the panel is 4:3.

- Position sets x (left 0.22, centre 0.5, right 0.78); everyone stands on a ground line at 88%.
- Facing: with two or three characters, a plain standing "front" pose turns three-quarter toward
  the middle, and "point" is mirrored so the arm aims at the middle. Action poses keep their front
  view. A lone character stays as planned.
- Z-order: left, centre, right, then the first bubble's speaker in front.
"""

import io
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from PIL import Image

from app.avatar import rig
from app.avatar.render import render_pose
from app.avatar.spec import normalize

PANEL_W, PANEL_H = 800, 600  # 1x; art is drawn at 2x
GROUND = 0.88
FIGURE = 0.64  # a character cell is this tall, as a share of the panel height (at scale 1)
POSITION_X = {"left": 0.22, "center": 0.5, "right": 0.78}
ORDER = {"left": 0, "center": 1, "right": 2}

Box = tuple[float, float, float, float]


@dataclass(frozen=True)
class Placement:
    id: str
    spec: dict[str, Any]
    pose: str  # the pose as drawn (a front pose may turn three-quarter)
    expression: str
    mirror: bool  # flip the drawn cell left-right
    cell: Box  # where the square cell goes (0-1 of the panel)
    head: Box  # the head as drawn (0-1 of the panel)

    @property
    def head_target(self) -> tuple[float, float]:
        """Where a bubble tail points: inside the head, a little above its middle."""
        x, y, w, h = self.head
        return (round(x + w / 2, 4), round(y + h * 0.4, 4))


def drawn_pose(pose: str, position: str, count: int) -> tuple[str, bool]:
    """(pose to draw, mirror) so characters face each other."""
    if count >= 2 and position in ("left", "right"):
        if pose == "front":
            return ("three_quarter_right" if position == "left" else "three_quarter_left", False)
        if pose == "point":
            # "point" aims at the viewer's right: mirror it for the character on the right.
            return ("point", position == "right")
    return (pose, False)


@lru_cache(maxsize=16)
def foot_line(body_type: str) -> float:
    """How far down the 200-unit cell the feet are (from the front pose's drawing)."""
    png = render_pose(normalize({"body_type": body_type}), "front", 200)
    box = Image.open(io.BytesIO(png)).getchannel("A").getbbox()
    return float(box[3]) if box else 180.0


def place(characters: list[dict[str, Any]], specs: dict[str, dict[str, Any]]) -> list[Placement]:
    """The characters of a panel, placed. `specs` are their pinned looks by character id."""
    count = len(characters)
    out: list[Placement] = []
    for c in characters:
        spec = normalize(specs.get(c["id"]) or {})
        position = str(c.get("position", "center"))
        pose, mirror = drawn_pose(str(c.get("pose", "front")), position, count)
        size = FIGURE * float(c.get("scale", 1.0))  # cell side, as a share of the panel height
        size_w = size * PANEL_H / PANEL_W  # the same side, as a share of the width
        cx = POSITION_X.get(position, 0.5)
        top = GROUND - foot_line(spec["body_type"]) / rig.CANVAS * size
        left = cx - size_w / 2
        hx, hy, hw, hh = rig.head_box(spec["body_type"], pose)
        if mirror:
            hx = rig.CANVAS - hx - hw
        unit_w, unit_h = size_w / rig.CANVAS, size / rig.CANVAS
        out.append(
            Placement(
                id=c["id"],
                spec=spec,
                pose=pose,
                expression=str(c.get("expression", "happy")),
                mirror=mirror,
                cell=(left, top, size_w, size),
                head=(left + hx * unit_w, top + hy * unit_h, hw * unit_w, hh * unit_h),
            )
        )
    return out


def z_order(placements: list[Placement], front_id: str | None = None) -> list[Placement]:
    """Back to front: left, centre, right; the first bubble's speaker comes to the front."""
    ordered = sorted(placements, key=lambda p: ORDER.get(_position(p), 1))
    if front_id:
        ordered.sort(key=lambda p: p.id == front_id)
    return ordered


def _position(p: Placement) -> str:
    cx = p.cell[0] + p.cell[2] / 2
    return min(POSITION_X, key=lambda name: abs(POSITION_X[name] - cx))


def first_speaker(bubbles: list[dict[str, Any]]) -> str | None:
    return next(
        (b.get("speaker") for b in bubbles if b.get("speaker") not in (None, "narrator")), None
    )
