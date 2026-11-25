"""Where characters and props stand in a panel, how they face, and where heads and hands are.

One piece of geometry, shared by the compositor (to draw), the bubble layout (to aim tails) and the
web app's previews (PanelRead.stage), so a tail always points at the head as drawn and a held torch
sits in the hand as drawn. Coordinates are fractions of the panel (0-1).

- Panel sizes (frames): normal 4:3 (800 x 600 units), wide (a full row: 1640 x 600) and splash (a
  full page: 1640 x 1880). Characters are the same size in normal and wide panels; bigger in a
  splash.
- Up to 3 characters at left, center and right stand where they always have (x 0.22, 0.5, 0.78),
  so old comics draw exactly as before. Any other line-up (4 or more, or the far_left/far_right
  spots) is spread evenly across the panel in position order; with 4 or more everyone shrinks a
  little and stands in two rows (back row higher and smaller, between the front row), so every
  face shows. Nobody is cut off at the edge: a figure is nudged in until its drawing fits.
- Facing: with two or more characters, a plain standing "front" pose turns three-quarter toward
  the middle, and "point" is mirrored so the arm aims at the middle. A lone character stays as
  planned.
- Props (app/props): on the ground at a spot, in a character's hand (the hand toward the middle),
  or worn on a head (turbans; the scarecrow can wear one too).
- Draw order: ground props, then characters back to front (left, centre, right; the first bubble's
  speaker in front of their row), each with what they hold; a sleeping character's "Zzz" on top.
"""

import io
import json
import math
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Literal

from PIL import Image

from app.avatar import rig
from app.avatar.catalog import load_catalog
from app.avatar.render import render_pose
from app.avatar.spec import normalize
from app.props import PROPS, PropState

PANEL_W, PANEL_H = 800, 600  # a normal panel, in units (1x); art is drawn at 2x
GROUND = 0.88
FIGURE = 0.64  # a character cell is this tall, as a share of the panel height (at scale 1)
POSITION_X = {"left": 0.22, "center": 0.5, "right": 0.78}  # up to 3, as they always stood
SLOT_X = {"far_left": 0.12, "left": 0.31, "center": 0.5, "right": 0.69, "far_right": 0.88}
POSITIONS = ("far_left", "left", "center", "right", "far_right")
ORDER = {name: i for i, name in enumerate(POSITIONS)}
LEGACY = {"left", "center", "right"}
EDGE = 0.012  # how close a drawing may come to the panel's side
TURBAN_FIT = 0.9  # a worn turban is a little wider than the head
TURBAN_BAND = 0.4  # its band sits this far down the head (its rim clears the eyes)
ASLEEP = "asleep"  # the sleeping pose: closed eyes and a "Zzz", never a bubble (Phase 8)
SLEEPY = "sleepy"

Box = tuple[float, float, float, float]
Size = Literal["normal", "wide", "splash"]


@dataclass(frozen=True)
class Frame:
    """A panel size: its shape in units, how tall a character cell is and where the ground is."""

    size: str
    w: float
    h: float
    figure: float  # cell height as a share of the panel height, at scale 1
    ground: float

    @property
    def aspect(self) -> float:
        return self.w / self.h


FRAMES: dict[str, Frame] = {
    "normal": Frame("normal", PANEL_W, PANEL_H, FIGURE, GROUND),
    "wide": Frame("wide", 1640, PANEL_H, FIGURE, GROUND),
    "splash": Frame("splash", 1640, 1880, 0.4, 0.9),
}
NORMAL = FRAMES["normal"]


def frame_for(size: str | None) -> Frame:
    return FRAMES.get(size or "normal", NORMAL)


@dataclass(frozen=True)
class Placement:
    id: str
    spec: dict[str, Any]
    pose: str  # the pose as drawn (a front pose may turn three-quarter)
    expression: str
    mirror: bool  # flip the drawn cell left-right
    cell: Box  # where the square cell goes (0-1 of the panel)
    head: Box  # the head as drawn (0-1 of the panel)
    row: int = 0  # 0 front, 1 back (only with 4 or more characters)

    @property
    def head_target(self) -> tuple[float, float]:
        """Where a bubble tail points: inside the head, a little above its middle."""
        x, y, w, h = self.head
        return (round(x + w / 2, 4), round(y + h * 0.4, 4))

    @property
    def center_x(self) -> float:
        return self.cell[0] + self.cell[2] / 2


@dataclass(frozen=True)
class PropPlacement:
    id: str
    state: str
    box: Box  # the drawing's box, as placed (0-1 of the panel)
    flip: bool = False  # mirrored left-right (a torch pointing left)
    rotate: float = 0.0  # degrees, about `origin` (a turban on a scarecrow lying down)
    origin: tuple[float, float] = (0.5, 1.0)  # the anchor, as a share of the box
    held_by: str | None = None
    behind: bool = False  # drawn just behind its holder (a hugged scarecrow)


@dataclass(frozen=True)
class Effect:
    kind: Literal["zzz"]
    box: Box
    owner: str


@dataclass
class StageLayout:
    frame: Frame
    characters: list[Placement]
    props: list[PropPlacement]
    effects: list[Effect] = field(default_factory=list)
    order: list[tuple[str, int]] = field(default_factory=list)  # ("character" | "prop", index)


def drawn_pose(pose: str, position: str, count: int) -> tuple[str, bool]:
    """(pose to draw, mirror) so characters face each other. `position` is the side the
    character stands on: left, right (or anything else for the middle)."""
    side = (
        "left"
        if position in ("left", "far_left")
        else "right"
        if position in ("right", "far_right")
        else "center"
    )
    if count >= 2 and side in ("left", "right"):
        if pose == "front":
            return ("three_quarter_right" if side == "left" else "three_quarter_left", False)
        if pose == "point":
            # "point" aims at the viewer's right: mirror it for the character on the right.
            return ("point", side == "right")
    return (pose, False)


@lru_cache(maxsize=16)
def foot_line(body_type: str) -> float:
    """How far down the 200-unit cell the feet are (from the front pose's drawing)."""
    png = render_pose(normalize({"body_type": body_type}), "front", 200)
    box = Image.open(io.BytesIO(png)).getchannel("A").getbbox()
    return float(box[3]) if box else 180.0


@lru_cache(maxsize=512)
def _drawn_span(spec_json: str, pose: str, expression: str) -> tuple[float, float]:
    """The left and right edges of a pose's drawing in its 200-unit cell (unmirrored)."""
    png = render_pose(json.loads(spec_json), pose, 200, expression)
    box = Image.open(io.BytesIO(png)).getchannel("A").getbbox()
    return (float(box[0]), float(box[2])) if box else (40.0, 160.0)


def drawn_span(
    spec: dict[str, Any], pose: str, expression: str, mirror: bool
) -> tuple[float, float]:
    left, right = _drawn_span(json.dumps(spec, sort_keys=True), pose, expression)
    return (rig.CANVAS - right, rig.CANVAS - left) if mirror else (left, right)


def drawn_expression(pose: str, expression: str) -> str:
    """A sleeping character always has the sleepy face (closed eyes)."""
    return SLEEPY if pose == ASLEEP and SLEEPY in load_catalog()["expressions"] else expression


def _crowd(count: int) -> tuple[float, float]:
    """(front scale, back scale) for a big group: everyone a bit smaller, the back row more so."""
    front = {4: 0.84, 5: 0.76}.get(count, 0.7)
    return front, round(front * 0.88, 4)


def _rows(count: int) -> list[int]:
    """Which row each character (in position order) stands in: 4 -> front, back, back, front;
    5 or more alternate, starting in front."""
    if count == 4:
        return [0, 1, 1, 0]
    return [i % 2 for i in range(count)]


def _figure(
    c: dict[str, Any],
    spec: dict[str, Any],
    frame: Frame,
    cx: float,
    ground: float,
    scale: float,
    count: int,
    side: str,
    clamp: bool,
    row: int = 0,
) -> Placement:
    pose, mirror = drawn_pose(str(c.get("pose", "front")), side, count)
    expression = drawn_expression(pose, str(c.get("expression", "happy")))
    size = frame.figure * scale  # cell side, as a share of the panel height
    size_w = size / frame.aspect  # the same side, as a share of the width
    if clamp:  # keep the drawing (arms and all) inside the panel
        left_u, right_u = drawn_span(spec, pose, expression, mirror)
        lo = cx - size_w / 2 + left_u / rig.CANVAS * size_w
        hi = cx - size_w / 2 + right_u / rig.CANVAS * size_w
        if lo < EDGE:
            cx += EDGE - lo
        elif hi > 1 - EDGE:
            cx -= hi - (1 - EDGE)
    top = ground - foot_line(spec["body_type"]) / rig.CANVAS * size
    left = cx - size_w / 2
    hx, hy, hw, hh = rig.head_box(spec["body_type"], pose)
    if mirror:
        hx = rig.CANVAS - hx - hw
    unit_w, unit_h = size_w / rig.CANVAS, size / rig.CANVAS
    return Placement(
        id=c["id"],
        spec=spec,
        pose=pose,
        expression=expression,
        mirror=mirror,
        cell=(left, top, size_w, size),
        head=(left + hx * unit_w, top + hy * unit_h, hw * unit_w, hh * unit_h),
        row=row,
    )


def place(
    characters: list[dict[str, Any]], specs: dict[str, dict[str, Any]], size: str | None = None
) -> list[Placement]:
    """The characters of a panel, placed (in the order given). `specs` are their pinned looks."""
    frame = frame_for(size)
    count = len(characters)
    positions = [str(c.get("position", "center")) for c in characters]
    looks = [normalize(specs.get(c["id"]) or {}) for c in characters]
    if frame is NORMAL and count <= 3 and set(positions) <= LEGACY:
        return [
            _figure(
                c,
                spec,
                frame,
                POSITION_X.get(pos, 0.5),
                frame.ground,
                float(c.get("scale", 1.0)),
                count,
                pos,
                clamp=False,
            )
            for c, spec, pos in zip(characters, looks, positions, strict=True)
        ]
    order = sorted(range(count), key=lambda i: (ORDER.get(positions[i], 2), i))
    out: dict[int, Placement] = {}
    if count <= 3:
        for i in order:
            cx = SLOT_X.get(positions[i], 0.5)
            side = _side(cx)
            out[i] = _figure(
                characters[i],
                looks[i],
                frame,
                cx,
                frame.ground,
                float(characters[i].get("scale", 1.0)),
                count,
                side,
                clamp=True,
            )
        return [out[i] for i in range(count)]
    front, back = _crowd(count)
    margin = 0.05
    step = (1 - 2 * margin) / count
    for slot, (i, row) in enumerate(zip(order, _rows(count), strict=True)):
        cx = margin + step * (slot + 0.5)
        ground = frame.ground + 0.02 if row == 0 else frame.ground - 0.09
        out[i] = _figure(
            characters[i],
            looks[i],
            frame,
            cx,
            ground,
            front if row == 0 else back,
            count,
            _side(cx),
            clamp=True,
            row=row,
        )
    return [out[i] for i in range(count)]


def _side(cx: float) -> str:
    return "left" if cx < 0.42 else "right" if cx > 0.58 else "center"


def z_order(placements: list[Placement], front_id: str | None = None) -> list[Placement]:
    """Back to front: the back row first, then left to right; the first bubble's speaker comes to
    the front of their row."""
    ordered = sorted(placements, key=lambda p: (-p.row, p.center_x))
    if front_id:
        ordered.sort(key=lambda p: (-p.row, p.id == front_id))
    return ordered


def first_speaker(bubbles: list[dict[str, Any]]) -> str | None:
    return next(
        (b.get("speaker") for b in bubbles if b.get("speaker") not in (None, "narrator")), None
    )


# ---- hands, props and effects ----------------------------------------------------------------


def hands(p: Placement) -> dict[str, tuple[float, float]]:
    """Both hands as drawn ("l" and "r"), in panel fractions (the middle of the hand)."""
    cat = load_catalog()
    pose = cat["poses"][p.pose]
    out: dict[str, tuple[float, float]] = {}
    x0, y0, w, h = p.cell
    for side in ("l", "r"):
        m = rig.ops_to_matrix(rig.transform_ops(cat, p.spec["body_type"], pose, f"wrist_{side}"))
        hx, hy = rig.apply(m, 0, 3)
        if pose["mirror"]:
            hx = rig.CANVAS - hx
        if p.mirror:
            hx = rig.CANVAS - hx
        out[side] = (x0 + hx / rig.CANVAS * w, y0 + hy / rig.CANVAS * h)
    return out


def holding_hand(p: Placement, taken: int = 0) -> tuple[float, float]:
    """The hand a character holds things in: the one toward the middle of the panel (the other
    one for a second thing)."""
    both = sorted(hands(p).values(), key=lambda xy: xy[0])  # viewer's left hand first
    toward_middle = both[0] if p.center_x > 0.5 else both[1]
    other = both[1] if toward_middle is both[0] else both[0]
    return toward_middle if taken % 2 == 0 else other


FACE_COVER = 0.12  # the most of its holder's face a held thing may cover
BEAM_TILTS = (0.0, 7.0, 14.0, 21.0, 28.0)  # degrees down a beam turns to miss the heads in its way


def _face(p: Placement) -> Box:
    """Where a character's face is (the head below the hair line), in panel fractions."""
    x, y, w, h = p.head
    return (x + w * 0.12, y + h * 0.3, w * 0.76, h * 0.62)


def _covered(box: Box, face: Box) -> float:
    """How much of a face a box covers (0-1)."""
    w = min(box[0] + box[2], face[0] + face[2]) - max(box[0], face[0])
    h = min(box[1] + box[3], face[1] + face[3]) - max(box[1], face[1])
    return max(0.0, w) * max(0.0, h) / (face[2] * face[3]) if face[2] and face[3] else 0.0


def _in_hand(
    state: PropState, holder: Placement, frame: Frame, hand: tuple[float, float]
) -> tuple[Box, tuple[float, float], bool]:
    """A held thing's box, anchor and flip at one hand."""
    flip = state.directional and hand[0] < holder.center_x
    unit = holder.cell[3] / rig.CANVAS
    if state.behind_holder:  # hugged: mostly beside the holder, toward the middle
        toward = 1 if holder.center_x <= 0.5 else -1
        hand = (hand[0] + toward * state.box[2] * unit / frame.aspect * 0.32, hand[1])
    box, origin = _box_at(state.box, unit, frame, hand, flip)
    return box, origin, flip


def _held(
    prop_id: str,
    state_id: str,
    state: PropState,
    holder: Placement,
    frame: Frame,
    in_hand: dict[str, int],
    heads: list[Box],
) -> PropPlacement:
    """A held thing at its holder's hand: the one toward the middle (the other one for a second
    thing), unless it would cover the holder's face there (a hand raised to the chin): then the
    other hand, or the same hand with the thing just below the chin. A beam (the torch) turns
    down until it misses the other characters' heads."""
    taken = in_hand.get(holder.id, 0)
    in_hand[holder.id] = taken + 1
    face = _face(holder)
    tries = [_in_hand(state, holder, frame, holding_hand(holder, taken + k)) for k in (0, 1)]
    if state.behind_holder:
        box, origin, flip = tries[0]
    else:
        box, origin, flip = min(tries, key=lambda t: _covered(t[0], face) > FACE_COVER)
        if _covered(box, face) > FACE_COVER:  # both hands at the face: hold it under the chin
            box = (box[0], max(box[1], face[1] + face[3]), box[2], box[3])
    rotate = _beam_tilt(state, box, origin, flip, frame, heads) if state.beam else 0.0
    return PropPlacement(
        prop_id,
        state_id,
        box,
        flip=flip,
        rotate=rotate,
        origin=origin,
        held_by=holder.id,
        behind=state.behind_holder,
    )


def _prop_points(
    points: tuple[tuple[float, float], ...],
    state: PropState,
    box: Box,
    origin: tuple[float, float],
    flip: bool,
    rotate: float,
    frame: Frame,
) -> list[tuple[float, float]]:
    """Points of a prop drawing (prop units) where they land in the panel, flipped and turned
    clockwise about the anchor like the drawing, in panel-height units (x times the aspect)."""
    sx, sy, sw, sh = state.box
    bx, by, bw, bh = box
    ax, ay = (bx + origin[0] * bw) * frame.aspect, by + origin[1] * bh
    turn = math.radians(rotate)
    cos, sin = math.cos(turn), math.sin(turn)
    out = []
    for u, v in points:
        fx = (u - sx) / sw
        x = (bx + (1 - fx if flip else fx) * bw) * frame.aspect - ax
        y = by + (v - sy) / sh * bh - ay
        out.append((ax + x * cos - y * sin, ay + x * sin + y * cos))
    return out


def _in_polygon(point: tuple[float, float], polygon: list[tuple[float, float]]) -> bool:
    x, y = point
    inside = False
    for (x1, y1), (x2, y2) in zip(polygon, polygon[1:] + polygon[:1], strict=True):
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            inside = not inside
    return inside


def _beam_hits(polygon: list[tuple[float, float]], head: Box, frame: Frame) -> int:
    """How many of 25 points spread over a head (hair and all) a beam covers."""
    x, y, w, h = head
    steps = range(5)
    points = [((x + w * i / 4) * frame.aspect, y + h * j / 4) for i in steps for j in steps]
    return sum(_in_polygon(p, polygon) for p in points)


def _beam_tilt(
    state: PropState,
    box: Box,
    origin: tuple[float, float],
    flip: bool,
    frame: Frame,
    heads: list[Box],
) -> float:
    """The turn (degrees, clockwise) that points a beam down just enough to miss every head; the
    one covering the least when none misses them all."""
    best: tuple[int, float] | None = None
    for tilt in BEAM_TILTS:
        rotate = -tilt if flip else tilt  # pointing left, down is anticlockwise
        polygon = _prop_points(state.beam or (), state, box, origin, flip, rotate, frame)
        hits = sum(_beam_hits(polygon, head, frame) for head in heads)
        if hits == 0:
            return rotate
        if best is None or hits < best[0]:
            best = (hits, rotate)
    return best[1] if best else 0.0


def _box_at(
    state_box: tuple[float, float, float, float],
    unit: float,
    frame: Frame,
    at: tuple[float, float],
    flip: bool = False,
) -> tuple[Box, tuple[float, float]]:
    """A prop drawing's box placed with its anchor (0, 0) at `at`. `unit` is the size of one prop
    unit in panel-height fractions. Returns (box, anchor as a share of the box)."""
    bx, by, bw, bh = state_box
    w, h = bw * unit / frame.aspect, bh * unit
    ox, oy = -bx / bw, -by / bh  # the anchor inside the box
    if flip:
        ox = 1 - ox
    return (at[0] - ox * w, at[1] - oy * h, w, h), (ox, oy)


def _inside(box: Box, origin: tuple[float, float]) -> tuple[Box, tuple[float, float]]:
    """A prop on the ground, nudged in so its drawing isn't cut off at the panel's side."""
    x, y, w, h = box
    x = min(max(x, EDGE), 1 - EDGE - w) if w < 1 - 2 * EDGE else (1 - w) / 2
    return (x, y, w, h), origin


def body_spans(placements: list[Placement]) -> list[tuple[float, float]]:
    """Where each character's drawing is, left to right (0-1 of the panel width)."""
    spans: list[tuple[float, float]] = []
    for p in placements:
        left_u, right_u = drawn_span(p.spec, p.pose, p.expression, p.mirror)
        x, _y, w, _h = p.cell
        spans.append((x + left_u / rig.CANVAS * w, x + right_u / rig.CANVAS * w))
    return sorted(spans)


def _overlap(a: float, b: float, spans: list[tuple[float, float]]) -> float:
    return sum(max(0.0, min(b, hi) - max(a, lo)) for lo, hi in spans)


def _in_view(box: Box, spans: list[tuple[float, float]]) -> Box:
    """A thing on the ground steps into a gap between the characters when it would stand mostly
    behind one of them (judged by the middle half of its drawing), so it can be seen. Its middle
    stays inside the panel; its ends (a crossbar, a fallen scarecrow's feet) may run off the side,
    as things do in comics. Characters are never cut off; props may be."""
    x, y, w, h = box
    core = w * 0.5

    def hidden(center: float) -> float:
        return _overlap(center - core / 2, center + core / 2, spans) / core

    center = x + w / 2
    if not spans or hidden(center) <= 0.35:
        return box
    lo, hi = EDGE + core / 2, 1 - EDGE - core / 2
    edges = [EDGE, *[v for span in spans for v in span], 1 - EDGE]
    gaps = [
        (edges[i], edges[i + 1]) for i in range(0, len(edges) - 1, 2) if edges[i + 1] > edges[i]
    ]
    options = [
        min(max(center, a + core / 2), b - core / 2) if b - a >= core else (a + b) / 2
        for a, b in gaps
    ]
    options = [min(max(c, lo), hi) for c in options]
    best = min(options, key=lambda c: (round(hidden(c), 2), abs(c - center)), default=center)
    if hidden(best) >= hidden(center):
        return box
    return (best - w / 2, y, w, h)


def place_props(
    props: list[dict[str, Any]], placements: list[Placement], frame: Frame
) -> list[PropPlacement]:
    """Where each prop goes. Unknown props, and held or worn ones whose holder isn't in the panel,
    are left out (the planner's checks and the editor stop that before it gets here)."""
    by_id = {p.id: p for p in placements}
    # Things on the ground stand with the back row (or with everyone): their size and ground line.
    rows = [p for p in placements if p.row == 1] or placements
    base, ground = frame.figure, frame.ground
    if rows:
        base = min(p.cell[3] for p in rows)
        ground = min(
            p.cell[1] + foot_line(p.spec["body_type"]) / rig.CANVAS * p.cell[3] for p in rows
        )
    ground_unit = base / rig.CANVAS
    out: list[PropPlacement] = []
    spans: list[tuple[float, float]] | None = None  # the characters' drawings, worked out once
    placed: dict[str, PropPlacement] = {}
    in_hand: dict[str, int] = {}
    worn: list[tuple[dict[str, Any], str]] = []
    for item in props:
        prop = PROPS.get(str(item.get("id")))
        state = prop.states.get(str(item.get("state"))) if prop else None
        if prop is None or state is None:
            continue
        holder_id = item.get("held_by")
        if state.placement == "ground":
            x = SLOT_X.get(str(item.get("position") or "center"), 0.5)
            y = min(frame.ground + 0.07, 0.985) if prop.id == "paw_prints" else ground
            box, origin = _inside(*_box_at(state.box, ground_unit, frame, (x, y)))
            if prop.id != "paw_prints":  # flat on the ground in front: nobody hides them
                spans = spans if spans is not None else body_spans(placements)
                box = _in_view(box, spans)
                middle = box[0] + box[2] / 2  # the next prop finds its own gap
                spans = sorted([*spans, (middle - box[2] / 4, middle + box[2] / 4)])
            pp = PropPlacement(prop.id, state=str(item["state"]), box=box, origin=origin)
        elif state.placement == "held" and holder_id in by_id:
            holder = by_id[str(holder_id)]
            heads = [p.head for p in placements if p.id != holder.id]
            pp = _held(prop.id, str(item["state"]), state, holder, frame, in_hand, heads)
        elif state.placement == "worn" and holder_id in by_id:
            head = by_id[str(holder_id)].head
            unit = head[2] * frame.aspect * TURBAN_FIT / 64  # a turban is 64 units wide
            at = (head[0] + head[2] / 2, head[1] + head[3] * TURBAN_BAND)
            box, origin = _box_at(state.box, unit, frame, at)
            pp = PropPlacement(
                prop.id, str(item["state"]), box, origin=origin, held_by=str(holder_id)
            )
        elif state.placement == "worn" and holder_id:
            worn.append((item, str(holder_id)))  # on a prop: placed once that prop is
            continue
        else:
            continue
        out.append(pp)
        placed.setdefault(prop.id, pp)
    for item, holder_id in worn:
        carrier = placed.get(holder_id)
        carrier_state = PROPS[holder_id].states.get(carrier.state) if carrier else None
        if carrier is None or carrier_state is None or carrier_state.head is None:
            continue
        hx, hy, width, turn = carrier_state.head
        bx, by, bw, bh = carrier_state.box
        unit = carrier.box[3] / bh  # the carrier's prop unit, in panel-height fractions
        anchor = (
            carrier.box[0] + (hx - bx) * unit / frame.aspect,
            carrier.box[1] + (hy - by) * unit,
        )
        state = PROPS[str(item["id"])].states[str(item["state"])]
        box, origin = _box_at(state.box, unit * width / 64, frame, anchor)
        out.append(
            PropPlacement(
                str(item["id"]),
                str(item["state"]),
                box,
                rotate=turn,
                origin=origin,
                held_by=holder_id,
            )
        )
    return out


def effects_for(placements: list[Placement]) -> list[Effect]:
    """A "Zzz" over every sleeping character's head, toward the middle of the panel."""
    out: list[Effect] = []
    for p in placements:
        if p.pose != ASLEEP:
            continue
        x, y, w, h = p.head
        ew, eh = w * 0.95, h * 0.62
        ex = x + w * 0.55 if p.center_x <= 0.5 else x - ew + w * 0.45
        out.append(Effect("zzz", (ex, max(0.01, y - eh * 0.9), ew, eh), p.id))
    return out


def layout(
    characters: list[dict[str, Any]],
    specs: dict[str, dict[str, Any]],
    props: list[dict[str, Any]] | None = None,
    size: str | None = None,
    bubbles: list[dict[str, Any]] | None = None,
) -> StageLayout:
    """Everything a panel draws, placed, with the draw order (back to front)."""
    frame = frame_for(size)
    placed = place(characters, specs, size)
    stage_props = place_props(props or [], placed, frame)
    order: list[tuple[str, int]] = [
        ("prop", i) for i, pp in enumerate(stage_props) if pp.held_by is None
    ]
    for p in z_order(placed, first_speaker(bubbles or [])):
        held = [i for i, pp in enumerate(stage_props) if pp.held_by == p.id]
        order += [("prop", i) for i in held if stage_props[i].behind]
        order.append(("character", placed.index(p)))
        order += [("prop", i) for i in held if not stage_props[i].behind]
    shown = {i for kind, i in order if kind == "prop"}
    # Worn by a prop (a turban on the scarecrow): right after the prop that wears it.
    for i, pp in enumerate(stage_props):
        if i in shown or pp.held_by is None:
            continue
        carrier = next((j for j, other in enumerate(stage_props) if other.id == pp.held_by), None)
        spot = next((k for k, entry in enumerate(order) if entry == ("prop", carrier)), len(order))
        order.insert(spot + 1, ("prop", i))
    return StageLayout(frame, placed, stage_props, effects_for(placed), order)
