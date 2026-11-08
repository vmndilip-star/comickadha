"""Builds shared/avatar/catalog.json: the layered SVG parts library, the rig and the 16 poses.

The art is written as code: every part is generated from a few shape helpers for all four views
(front, three_quarter, side, back) and, where shapes depend on the body, for every body type. Both
renderers (web TypeScript and API Python) only read the JSON, so they draw identical SVG.

Conventions
- A cell is 200 x 200 units (rendered at 256 px), outlines are 2.4 units (about 3 px).
- Head space: the head's centre is (0, 0) and a round head has radius 24.
- Bones point down (+y) at angle 0. A positive angle turns clockwise, so a hanging limb swings to
  the screen-left. Three-quarter and side views face screen-right; *_left poses are mirrored.
- Colours are placeholders ({{skin}}, {{top_shade}}, ...) filled from palette entries at render time.

Run from api/:  uv run python ../shared/avatar/build_catalog.py
"""

from __future__ import annotations

import json
import math
from collections.abc import Callable, Sequence
from functools import partial
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "catalog.json"

INK = "#1A1A1A"
SW = 2.4
WHITE = "#FFFFFF"
METAL = "#6B6F78"
VIEWS = ("front", "three_quarter", "side", "back")
Point = tuple[float, float]


# ---- numbers and SVG helpers ----------------------------------------------------------------------


def num(x: float) -> int | float:
    """Rounded to 2 decimals; whole numbers become ints so both renderers print them the same."""
    r = round(float(x), 2)
    if r == 0:
        return 0
    return int(r) if r == int(r) else r


def n(x: float) -> str:
    return str(num(x))


def stroke(color: str = INK, width: float = SW) -> str:
    return f' stroke="{color}" stroke-width="{n(width)}" stroke-linejoin="round" stroke-linecap="round"'


def path(d: str, fill: str, line: str | None = INK, width: float = SW, extra: str = "") -> str:
    return f'<path d="{d}" fill="{fill}"{stroke(line, width) if line else ""}{extra}/>'


def circle(
    cx: float, cy: float, r: float, fill: str, line: str | None = INK, width: float = SW, extra: str = ""
) -> str:
    return f'<circle cx="{n(cx)}" cy="{n(cy)}" r="{n(r)}" fill="{fill}"{stroke(line, width) if line else ""}{extra}/>'


def ellipse(
    cx: float, cy: float, rx: float, ry: float, fill: str, line: str | None = INK, width: float = SW, extra: str = ""
) -> str:
    outline = stroke(line, width) if line else ""
    return f'<ellipse cx="{n(cx)}" cy="{n(cy)}" rx="{n(rx)}" ry="{n(ry)}" fill="{fill}"{outline}{extra}/>'


def rect(
    x: float,
    y: float,
    w: float,
    h: float,
    rx: float,
    fill: str,
    line: str | None = INK,
    width: float = SW,
    extra: str = "",
) -> str:
    return (
        f'<rect x="{n(x)}" y="{n(y)}" width="{n(w)}" height="{n(h)}" rx="{n(rx)}" fill="{fill}"'
        f"{stroke(line, width) if line else ''}{extra}/>"
    )


def polyline(points: Sequence[Point], color: str, width: float) -> str:
    d = "M" + " L".join(f"{n(x)} {n(y)}" for x, y in points)
    return f'<path d="{d}" fill="none"{stroke(color, width)}/>'


def group(inner: str, transform: str) -> str:
    return f'<g transform="{transform}">{inner}</g>' if inner else ""


def poly_d(points: Sequence[Point]) -> str:
    return "M" + " L".join(f"{n(x)} {n(y)}" for x, y in points) + " Z"


def smooth_d(points: Sequence[Point], closed: bool = True) -> str:
    """A Catmull-Rom curve through the points, as cubic Beziers: soft, hand-drawn shapes."""
    pts = list(points)
    count = len(pts)
    d = f"M{n(pts[0][0])} {n(pts[0][1])}"
    segments = count if closed else count - 1
    for i in range(segments):
        p0 = pts[(i - 1) % count] if closed or i > 0 else pts[0]
        p1 = pts[i]
        p2 = pts[(i + 1) % count]
        p3 = pts[(i + 2) % count] if closed or i + 2 < count else p2
        c1 = (p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6)
        d += f" C{n(c1[0])} {n(c1[1])} {n(c2[0])} {n(c2[1])} {n(p2[0])} {n(p2[1])}"
    return d + (" Z" if closed else "")


def rounded_d(points: Sequence[Point], radius: float) -> str:
    """A polygon with rounded corners."""
    pts = list(points)
    count = len(pts)
    d = ""
    for i in range(count):
        prev, cur, nxt = pts[i - 1], pts[i], pts[(i + 1) % count]
        a = _toward(cur, prev, radius)
        b = _toward(cur, nxt, radius)
        d += (
            f"M{n(a[0])} {n(a[1])}" if i == 0 else f" L{n(a[0])} {n(a[1])}"
        ) + f" Q{n(cur[0])} {n(cur[1])} {n(b[0])} {n(b[1])}"
    return d + " Z"


def _toward(a: Point, b: Point, dist: float) -> Point:
    dx, dy = b[0] - a[0], b[1] - a[1]
    length = math.hypot(dx, dy) or 1
    t = min(dist, length / 2) / length
    return (a[0] + dx * t, a[1] + dy * t)


def ellipse_d(cx: float, cy: float, rx: float, ry: float) -> str:
    return (
        f"M{n(cx - rx)} {n(cy)} A{n(rx)} {n(ry)} 0 1 0 {n(cx + rx)} {n(cy)} "
        f"A{n(rx)} {n(ry)} 0 1 0 {n(cx - rx)} {n(cy)} Z"
    )


def star_points(cx: float, cy: float, outer: float, inner: float, points: int = 5) -> list[Point]:
    out = []
    for i in range(points * 2):
        r = outer if i % 2 == 0 else inner
        a = math.pi * i / points - math.pi / 2
        out.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return out


def mapped(points: Sequence[Point], fx: float = 1.0, dx: float = 0.0, fy: float = 1.0, dy: float = 0.0) -> list[Point]:
    return [(x * fx + dx, y * fy + dy) for x, y in points]


def mirror_x(points: Sequence[Point]) -> list[Point]:
    return [(-x, y) for x, y in points]


# How head-space shapes (head, hair, hats) turn in each view: horizontal squash and shift.
HEAD_VIEW: dict[str, tuple[float, float]] = {
    "front": (1.0, 0.0),
    "three_quarter": (0.93, -2.0),
    "side": (0.92, 0.0),
    "back": (1.0, 0.0),
}
# How body-space shapes (torso, clothes) turn.
BODY_VIEW: dict[str, tuple[float, float]] = {
    "front": (1.0, 0.0),
    "three_quarter": (0.86, 1.0),
    "side": (0.6, 1.5),
    "back": (1.0, 0.0),
}

# ---- palettes ---------------------------------------------------------------------------------------


def _mix(hex_color: str, target: tuple[int, int, int], t: float) -> str:
    v = int(hex_color[1:], 16)
    rgb = ((v >> 16) & 255, (v >> 8) & 255, v & 255)
    mixed = tuple(round(c + (tc - c) * t) for c, tc in zip(rgb, target, strict=True))
    return "#{:02X}{:02X}{:02X}".format(*mixed)


def entry(id_: str, label: str, hex_color: str) -> dict[str, str]:
    return {
        "id": id_,
        "label": label,
        "hex": hex_color,
        "shade": _mix(hex_color, (26, 26, 26), 0.22),
        "light": _mix(hex_color, (255, 255, 255), 0.45),
    }


PALETTES = {
    "skin_human": [
        entry("porcelain", "Porcelain", "#FCE4D2"),
        entry("ivory", "Ivory", "#F7D5BA"),
        entry("sand", "Sand", "#EFC29B"),
        entry("honey", "Honey", "#E2A977"),
        entry("caramel", "Caramel", "#CF8D5B"),
        entry("amber", "Amber", "#B9773F"),
        entry("bronze", "Bronze", "#9C6236"),
        entry("chestnut", "Chestnut", "#7E4B2A"),
        entry("espresso", "Espresso", "#5E3720"),
        entry("ebony", "Ebony", "#43271A"),
    ],
    "skin_robot": [
        entry("silver", "Silver", "#C9CED6"),
        entry("sky", "Sky blue", "#9AD0F5"),
        entry("mint", "Mint", "#B7E4A7"),
        entry("sun", "Sunshine", "#FFD23F"),
        entry("coral", "Coral", "#FF8A6B"),
    ],
    "fur": [
        entry("ginger", "Ginger", "#E8954F"),
        entry("cream", "Cream", "#F3E2C3"),
        entry("grey", "Grey", "#A9A9AE"),
        entry("brown", "Brown", "#8A5A3B"),
        entry("black", "Black", "#3B3B3F"),
        entry("snow", "Snow", "#F7F5F0"),
    ],
    "hair": [
        entry("black", "Black", "#2B2B2B"),
        entry("dark_brown", "Dark brown", "#3B2314"),
        entry("brown", "Brown", "#6B4423"),
        entry("auburn", "Auburn", "#8E3B22"),
        entry("ginger", "Ginger", "#C8552B"),
        entry("blonde", "Blonde", "#E8C15A"),
        entry("platinum", "Platinum", "#EDE3C8"),
        entry("grey", "Grey", "#9A9A9A"),
        entry("white", "White", "#F2F2EE"),
        entry("blue", "Blue", "#3F6FD8"),
        entry("pink", "Pink", "#FF7FB0"),
        entry("purple", "Purple", "#7A4FC9"),
    ],
    "cloth": [
        entry("sun", "Sunshine", "#FFD23F"),
        entry("coral", "Coral", "#FF6B4A"),
        entry("red", "Red", "#E53935"),
        entry("pink", "Pink", "#FF7FB0"),
        entry("purple", "Purple", "#7A4FC9"),
        entry("pow_blue", "Pow blue", "#1F5BD1"),
        entry("sky", "Sky", "#9AD0F5"),
        entry("mint", "Mint", "#B7E4A7"),
        entry("green", "Green", "#3FA34D"),
        entry("brown", "Brown", "#8A5A3B"),
        entry("navy", "Navy", "#23305E"),
        entry("grey", "Grey", "#8C8C8C"),
        entry("white", "White", "#FFFFFF"),
        entry("black", "Black", "#2B2B2B"),
    ],
    "card": [
        entry("sun_tint", "Sunny", "#FFE9A8"),
        entry("coral_tint", "Peach", "#FFD0C2"),
        entry("sky_tint", "Sky", "#DDF0FC"),
        entry("mint_tint", "Mint", "#E6F6DF"),
    ],
}

# Which palette each colour slot uses (skin depends on the body type).
COLOR_SLOTS = {
    "skin": {
        "palette_by_body": {
            "kid": "skin_human",
            "grown_up": "skin_human",
            "robot": "skin_robot",
            "cat": "fur",
            "dog": "fur",
            "bear": "fur",
        }
    },
    "hair": {"palette": "hair"},
    "top": {"palette": "cloth"},
    "bottom": {"palette": "cloth"},
    "shoes": {"palette": "cloth"},
    "hat": {"palette": "cloth"},
    "cape": {"palette": "cloth"},
    "backpack": {"palette": "cloth"},
    "card": {"palette": "card"},
}

# Used when a spec leaves a slot out (body-type defaults come first).
COLOR_DEFAULTS = {
    "skin": "#EFC29B",
    "hair": "#3B2314",
    "top": "#FFD23F",
    "bottom": "#1F5BD1",
    "shoes": "#FF6B4A",
    "hat": "#FF6B4A",
    "cape": "#E53935",
    "backpack": "#3FA34D",
    "card": "#FFE9A8",
}

# ---- body types and rig -----------------------------------------------------------------------------

BONES = {  # bone -> parent ("root" is the hips, placed by the body type)
    "torso": "root",
    "neck": "torso",
    "head": "neck",
    "shoulder_l": "torso",
    "elbow_l": "shoulder_l",
    "wrist_l": "elbow_l",
    "shoulder_r": "torso",
    "elbow_r": "shoulder_r",
    "wrist_r": "elbow_r",
    "hip_l": "root",
    "knee_l": "hip_l",
    "ankle_l": "knee_l",
    "hip_r": "root",
    "knee_r": "hip_r",
    "ankle_r": "knee_r",
    "tail": "root",
}

BODIES: dict[str, dict] = {
    "kid": dict(
        label="Kid",
        kind="kid",
        rig="human",
        root=(100, 128),
        T=34,
        S=14,
        H=7,
        head=(0, -27),
        hs=1.0,
        U=19,
        L=17,
        Th=21,
        Sh=20,
        aw=7.5,
        lw=8.5,
        hand=4.6,
        foot=6.2,
        torso="human",
    ),
    "grown_up": dict(
        label="Grown-up",
        kind="grown_up",
        rig="human",
        root=(100, 120),
        T=45,
        S=18,
        H=8.5,
        head=(0, -22),
        hs=0.82,
        U=26,
        L=24,
        Th=28,
        Sh=28,
        aw=8.5,
        lw=10,
        hand=5,
        foot=7,
        torso="grown",
    ),
    "robot": dict(
        label="Robot",
        kind="robot",
        rig="robot",
        root=(100, 128),
        T=36,
        S=16,
        H=8,
        head=(0, -27),
        hs=1.0,
        U=18,
        L=17,
        Th=19,
        Sh=19,
        aw=8,
        lw=9,
        hand=5,
        foot=6.8,
        torso="robot",
    ),
    "cat": dict(
        label="Cat",
        kind="animal",
        rig="animal",
        root=(100, 132),
        T=30,
        S=12.5,
        H=7,
        head=(0, -27),
        hs=1.05,
        U=16,
        L=14,
        Th=16,
        Sh=15,
        aw=8,
        lw=9,
        hand=5,
        foot=6,
        torso="animal",
        tail="cat",
    ),
    "dog": dict(
        label="Dog",
        kind="animal",
        rig="animal",
        root=(100, 132),
        T=30,
        S=12.5,
        H=7,
        head=(0, -27),
        hs=1.05,
        U=16,
        L=14,
        Th=16,
        Sh=15,
        aw=8,
        lw=9,
        hand=5,
        foot=6,
        torso="animal",
        tail="dog",
    ),
    "bear": dict(
        label="Bear",
        kind="animal",
        rig="animal",
        root=(100, 131),
        T=31,
        S=13.5,
        H=7.5,
        head=(0, -27),
        hs=1.08,
        U=16,
        L=14,
        Th=16,
        Sh=15,
        aw=9,
        lw=10,
        hand=5.5,
        foot=6.5,
        torso="animal",
        tail="bear",
    ),
}
HUMANS = ["kid", "grown_up"]
ANIMALS = ["cat", "dog", "bear"]
ALL = list(BODIES)
CRITTERS = ["robot", *ANIMALS]  # body types that may go without clothes


def bone_offsets(b: dict, view: str) -> dict[str, list[int | float]]:
    T, S, H = b["T"], b["S"], b["H"]
    hx, hy = b["head"]
    if view == "three_quarter":
        sl, sr, hl, hr, neck, head, tail = (-S * 0.55, S * 0.8, -H * 0.55, H * 0.8, (2, -T), (hx + 3, hy), (-8, -4))
    elif view == "side":
        sl, sr, hl, hr, neck, head, tail = (-1, 5, -1.5, 1.5, (3, -T), (hx + 4, hy), (-12, -4))
    else:
        sl, sr, hl, hr, neck, head, tail = (-S, S, -H, H, (0, -T), (hx, hy), (0, -3))
    offsets: dict[str, Point] = {
        "torso": (0, 0),
        "neck": neck,
        "head": head,
        "shoulder_l": (sl, -T + 4),
        "elbow_l": (0, b["U"]),
        "wrist_l": (0, b["L"]),
        "shoulder_r": (sr, -T + 4),
        "elbow_r": (0, b["U"]),
        "wrist_r": (0, b["L"]),
        "hip_l": (hl, 0),
        "knee_l": (0, b["Th"]),
        "ankle_l": (0, b["Sh"]),
        "hip_r": (hr, 0),
        "knee_r": (0, b["Th"]),
        "ankle_r": (0, b["Sh"]),
        "tail": tail,
    }
    return {k: [num(x), num(y)] for k, (x, y) in offsets.items()}


# ---- torso shapes -----------------------------------------------------------------------------------


def torso_points(b: dict, bottom: float = 4.0, flare: float = 0.0) -> list[Point]:
    T = b["T"]
    match b["torso"]:
        case "grown":
            return [(-13 - flare, bottom), (-18, -T + 8), (-15, -T), (15, -T), (18, -T + 8), (13 + flare, bottom)]
        case "robot":
            return [(-16 - flare, bottom + 1), (-16, -T), (16, -T), (16 + flare, bottom + 1)]
        case "animal":
            return [
                (-14 - flare, bottom),
                (-15.5, -10),
                (-12, -T + 2),
                (-8, -T),
                (8, -T),
                (12, -T + 2),
                (15.5, -10),
                (14 + flare, bottom),
            ]
        case _:
            return [(-13 - flare, bottom), (-14.5, -T + 7), (-12, -T), (12, -T), (14.5, -T + 7), (13 + flare, bottom)]


def torso_d(b: dict, view: str, bottom: float = 4.0, flare: float = 0.0) -> str:
    fx, dx = BODY_VIEW[view]
    pts = mapped(torso_points(b, bottom, flare), fx, dx)
    if b["torso"] == "animal":
        return smooth_d(pts)
    return rounded_d(pts, 4 if b["torso"] != "robot" else 5)


def bview(view: str, x: float) -> float:
    fx, dx = BODY_VIEW[view]
    return x * fx + dx


def head_x(view: str, x: float) -> float:
    fx, dx = HEAD_VIEW[view]
    return x * fx + dx


# ---- body fragments (limbs, hands, neck, tail) ------------------------------------------------------


def limb(length: float, width: float, color: str | None) -> str:
    """One limb segment: the ink pass (color=None) or the colour pass, so joints join cleanly."""
    if color is None:
        return polyline([(0, 0), (0, length)], INK, width + 2 * SW)
    return polyline([(0, 0), (0, length)], color, width)


def body_fragments(bt: str, b: dict) -> dict[str, dict[str, str]]:
    robot = bt == "robot"
    animal = bt in ANIMALS
    joint = circle(0, 0, b["aw"] * 0.45, METAL, INK, 1.4) if robot else ""
    knee_joint = circle(0, 0, b["lw"] * 0.45, METAL, INK, 1.4) if robot else ""
    if robot:
        hand = (
            circle(0, 2, b["hand"] * 0.8, METAL)
            + polyline([(-2.5, 4), (-3.5, 8)], INK, 2.2)
            + polyline([(2.5, 4), (3.5, 8)], INK, 2.2)
        )
        neck = rect(-4.5, -9, 9, 11, 2, METAL)
    elif animal:
        hand = (
            circle(0, 2, b["hand"], "{{skin}}")
            + polyline([(-1.8, 5.5), (-1.8, 6.6)], INK, 1.2)
            + polyline([(1.8, 5.5), (1.8, 6.6)], INK, 1.2)
        )
        neck = rect(-4.5, -10, 9, 13, 3, "{{skin}}")
    else:
        hand = circle(0, 2, b["hand"], "{{skin}}")
        neck = rect(-3.5, -9, 7, 12, 2.5, "{{skin}}")

    frags = {
        "neck": {v: neck for v in VIEWS},
        "arm_upper_ink": {v: limb(b["U"], b["aw"], None) for v in VIEWS},
        "arm_upper_fill": {v: limb(b["U"], b["aw"], "{{arm_upper}}") for v in VIEWS},
        "arm_lower_ink": {v: limb(b["L"], b["aw"], None) for v in VIEWS},
        "arm_lower_fill": {v: limb(b["L"], b["aw"], "{{arm_lower}}") + joint for v in VIEWS},
        "hand": {v: hand for v in VIEWS},
        "leg_upper_ink": {v: limb(b["Th"], b["lw"], None) for v in VIEWS},
        "leg_upper_fill": {v: limb(b["Th"], b["lw"], "{{leg_upper}}") for v in VIEWS},
        "leg_lower_ink": {v: limb(b["Sh"], b["lw"], None) for v in VIEWS},
        "leg_lower_fill": {v: limb(b["Sh"], b["lw"], "{{leg_lower}}") + knee_joint for v in VIEWS},
        "tail": tail_fragments(b.get("tail")),
    }
    return frags


def tail_fragments(kind: str | None) -> dict[str, str]:
    if kind is None:
        return {v: "" for v in VIEWS}

    def curvy(points: list[Point], width: float) -> str:
        d = smooth_d(points, closed=False)
        ink = f'<path d="{d}" fill="none"{stroke(INK, width + 2 * SW)}/>'
        return ink + f'<path d="{d}" fill="none"{stroke("{{skin}}", width)}/>'

    if kind == "cat":
        side = [(-2, -2), (-14, -4), (-22, -17), (-18, -30)]
        return {
            "front": curvy([(4, -2), (16, -6), (22, -20), (17, -31)], 4),
            "three_quarter": curvy(side, 4),
            "side": curvy(side, 4),
            "back": curvy([(0, 0), (6, -10), (4, -24), (10, -30)], 4),
        }
    if kind == "dog":
        side = [(-2, -3), (-12, -8), (-16, -18)]
        return {
            "front": curvy([(4, -3), (13, -10), (16, -19)], 5),
            "three_quarter": curvy(side, 5),
            "side": curvy(side, 5),
            "back": curvy([(0, -2), (4, -12), (2, -20)], 5),
        }
    stub = circle(-11, -4, 5, "{{skin}}")
    return {"front": "", "three_quarter": stub, "side": stub, "back": circle(0, -3, 5.5, "{{skin}}")}


# ---- heads ------------------------------------------------------------------------------------------

HEAD_BOX = [-30, -36, 60, 66]  # head space; the face paste maps this box between body and face cells


def head_shape_points(shape: str) -> list[Point]:
    match shape:
        case "oval":
            return [(21 * math.cos(a), 25.5 * math.sin(a)) for a in _angles(16)]
        case "square":
            return [(-22.5, -23.5), (22.5, -23.5), (22.5, 15), (12, 24), (-12, 24), (-22.5, 15)]
        case "heart":
            return [
                (0, -24),
                (17, -21.5),
                (24.5, -7),
                (21, 9),
                (11, 21),
                (0, 25),
                (-11, 21),
                (-21, 9),
                (-24.5, -7),
                (-17, -21.5),
            ]
        case _:
            return [(24 * math.cos(a), 24 * math.sin(a)) for a in _angles(16)]


def _angles(count: int) -> list[float]:
    return [2 * math.pi * i / count for i in range(count)]


def human_head(shape: str) -> dict[str, dict[str, str]]:
    layers: dict[str, dict[str, str]] = {"ears_back": {}, "base": {}, "ears_front": {}}
    for view in VIEWS:
        fx, dx = HEAD_VIEW[view]
        pts = mapped(head_shape_points(shape), fx, dx)
        base = path(rounded_d(pts, 9) if shape == "square" else smooth_d(pts), "{{skin}}")

        def ear(x: float, y: float) -> str:
            inner = f"M{n(x - 1)} {n(y - 3)} Q{n(x + 1.6)} {n(y)} {n(x - 1)} {n(y + 3)}"
            return ellipse(x, y, 4.2, 6, "{{skin}}") + path(inner, "none", "{{skin_shade}}", 1.4)

        def side_ear(x: float, y: float) -> str:
            # Small, set well back, with an ink "C" so it never reads as a second eye.
            inner = f"M{n(x + 1.2)} {n(y - 2.3)} Q{n(x - 2.1)} {n(y)} {n(x + 1.2)} {n(y + 2.3)}"
            return ellipse(x, y, 3.3, 4.6, "{{skin}}", INK, 2) + path(inner, "none", INK, 1.2)

        if view in ("front", "back"):
            layers["ears_back"][view] = ear(-23.5, 3) + ear(23.5, 3)
            layers["ears_front"][view] = ""
        elif view == "three_quarter":
            layers["ears_back"][view] = ""
            layers["ears_front"][view] = ear(-17, 3)
        else:
            layers["ears_back"][view] = ""
            layers["ears_front"][view] = side_ear(-9, 3)
        layers["base"][view] = base
    return layers


# Where a screen head's screen starts at the back: turned heads show more metal behind the face.
SCREEN_BACK = {"front": -19, "three_quarter": -15, "side": -9, "back": -19}


def robot_head(shape: str) -> dict[str, dict[str, str]]:
    layers: dict[str, dict[str, str]] = {"ears_back": {}, "base": {}, "ears_front": {}}
    for view in VIEWS:
        fx, dx = HEAD_VIEW[view]
        sx = partial(head_x, view)
        antenna = polyline([(sx(0), -22), (sx(0), -32)], INK, 2.4) + circle(sx(0), -34, 3.2, "#FF6B4A", INK, 2)
        if shape == "dome":
            d = smooth_d(mapped([(-24, 22), (-25, -2), (-18, -18), (0, -25), (18, -18), (25, -2), (24, 22)], fx, dx))
            base = path(d, "{{skin}}") + polyline([(sx(-18), -6), (sx(18), -6)], "{{skin_shade}}", 1.6)
            antenna = (
                polyline([(sx(-8), -22), (sx(-12), -31)], INK, 2.2)
                + circle(sx(-12), -32.5, 2.6, "#FF6B4A", INK, 1.8)
                + polyline([(sx(8), -22), (sx(12), -31)], INK, 2.2)
                + circle(sx(12), -32.5, 2.6, "#FFD23F", INK, 1.8)
            )
        elif shape == "screen":
            base = path(rounded_d(mapped([(-25, -22), (25, -22), (25, 24), (-25, 24)], fx, dx), 7), "{{skin}}")
            screen = (
                ""
                if view == "back"
                else path(
                    rounded_d(
                        mapped(
                            [(SCREEN_BACK[view], -15), (19, -15), (19, 18), (SCREEN_BACK[view], 18)],
                            fx,
                            dx + (3 if view != "front" else 0),
                        ),
                        5,
                    ),
                    "#1F2A44",
                    INK,
                    2,
                )
            )
            base += screen
        else:  # box
            base = path(rounded_d(mapped([(-24, -22), (24, -22), (24, 24), (-24, 24)], fx, dx), 6), "{{skin}}")
            if view != "back":
                base += rect(sx(-14) - 1, 16, 28 * fx + 2, 3, 1.5, "{{skin_shade}}", None)
        bolts = rect(-28, -4, 5, 10, 2, METAL, INK, 1.8) + rect(23, -4, 5, 10, 2, METAL, INK, 1.8)
        layers["ears_back"][view] = bolts if view in ("front", "back") else ""
        # Turned away, the bolt sits on the back edge of the head, clear of the face.
        layers["ears_front"][view] = (
            rect(sx(-24) - 3, -4, 5, 10, 2, METAL, INK, 1.8) if view in ("side", "three_quarter") else ""
        )
        layers["base"][view] = antenna + base
    return layers


def animal_head(species: str) -> dict[str, dict[str, str]]:
    layers: dict[str, dict[str, str]] = {"ears_back": {}, "base": {}, "ears_front": {}}
    for view in VIEWS:
        fx, dx = HEAD_VIEW[view]
        sx = partial(head_x, view)
        face_dx = {"front": 0, "three_quarter": 7, "side": 12, "back": 0}[view]
        show_face = view != "back"
        if species == "cat":
            ear_pts = [(-22, -8), (-20, -36), (-6, -21)]
            ears = ""
            for side in (-1, 1):
                if view == "side" and side == 1:
                    continue
                pts = mapped([(x * side, y) for x, y in ear_pts], fx, dx)
                inner = mapped(
                    [(x * side * 0.75 + (-3 if side < 0 else 3) * 0.2, y * 0.85 - 2) for x, y in ear_pts[:3]], fx, dx
                )
                ears += path(poly_d(pts), "{{skin}}") + path(poly_d(inner), "#FF9AA2", None)
            head = path(
                smooth_d(mapped([(25 * math.cos(a), 22 * math.sin(a) + 1) for a in _angles(16)], fx, dx)), "{{skin}}"
            )
            muzzle = ellipse(face_dx, 11, 8.5, 6.5, "{{skin_light}}", None) if show_face else ""
            nose = (
                path(poly_d([(face_dx - 2.4, 6.5), (face_dx + 2.4, 6.5), (face_dx, 9)]), "#FF8FA3", INK, 1.4)
                if show_face
                else ""
            )
            whiskers = ""
            if show_face:
                for sgn in (-1, 1):
                    if view == "side" and sgn == -1:
                        continue
                    for dy in (-1.5, 2):
                        whiskers += polyline(
                            [(face_dx + sgn * 8, 10 + dy * 0.4), (face_dx + sgn * 20, 8 + dy * 1.6)], INK, 1.1
                        )
            layers["ears_back"][view] = ears
            layers["base"][view] = head + muzzle + nose
            layers["ears_front"][view] = whiskers
        elif species == "dog":
            head = path(
                smooth_d(mapped([(24 * math.cos(a), 23 * math.sin(a)) for a in _angles(16)], fx, dx)), "{{skin}}"
            )
            muzzle = ellipse(face_dx, 11, 10, 7.5, "{{skin_light}}", None) if show_face else ""
            nose = ellipse(face_dx, 6, 4.2, 3.2, INK, None) if show_face else ""

            def ear(x: float, flip: int) -> str:
                points = [(x, -14), (x + 9 * flip, -12), (x + 10 * flip, 6), (x + 4 * flip, 14), (x - 2 * flip, 4)]
                return path(smooth_d(points), "{{skin_shade}}")

            if view in ("front", "back"):
                ears = ear(-18, -1) + ear(18, 1)
            elif view == "three_quarter":
                ears = ear(sx(-18), -1)
            else:
                ears = ear(sx(-6), -1)
            layers["ears_back"][view] = ""
            layers["base"][view] = head + muzzle + nose
            layers["ears_front"][view] = ears
        else:  # bear
            ears = ""
            for x in (-18, 18):
                if view == "side" and x > 0:
                    continue
                ears += circle(sx(x), -18, 8, "{{skin}}") + circle(sx(x), -18, 4, "{{skin_light}}", None)
            head = path(
                smooth_d(mapped([(25 * math.cos(a), 23.5 * math.sin(a)) for a in _angles(16)], fx, dx)), "{{skin}}"
            )
            muzzle = ellipse(face_dx, 11, 10.5, 8, "{{skin_light}}", INK, 1.6) if show_face else ""
            nose = ellipse(face_dx, 6.5, 4.4, 3.2, INK, None) if show_face else ""
            layers["ears_back"][view] = ears
            layers["base"][view] = head + muzzle + nose
            layers["ears_front"][view] = ""
    return layers


# ---- face features ----------------------------------------------------------------------------------


def eye_states(shape: str) -> dict[str, str]:
    ink = "{{face_ink}}"
    closed = path("M-4.2 1.4 Q0 -3.4 4.2 1.4", "none", ink, 2.2)
    hl = circle(1.2, -1.3, 1.1, WHITE, None)
    match shape:
        case "oval":
            return {
                "open": ellipse(0, 0, 2.7, 4, ink, None) + hl,
                "small": ellipse(0, 0, 1.6, 2.4, ink, None),
                "wide": ellipse(0, 0, 4.2, 5.6, WHITE, ink, 1.5) + ellipse(0, 0.4, 2, 2.8, ink, None),
                "closed": closed,
            }
        case "almond":
            almond = "M-5.2 0 Q0 -4.6 5.2 0 Q0 4.6 -5.2 0 Z"
            return {
                "open": path(almond, WHITE, ink, 1.5)
                + circle(0.4, 0, 2.3, ink, None)
                + circle(1.3, -0.9, 0.8, WHITE, None),
                "small": path("M-4.2 0 Q0 -2.8 4.2 0 Q0 2.8 -4.2 0 Z", WHITE, ink, 1.4) + circle(0, 0, 1.2, ink, None),
                "wide": path("M-6 0 Q0 -6.5 6 0 Q0 6.5 -6 0 Z", WHITE, ink, 1.5) + circle(0, 0, 2.4, ink, None),
                "closed": closed,
            }
        case "sleepy":
            return {
                "open": path("M-4 -0.2 A4 4 0 0 0 4 -0.2 Z", ink, None)
                + polyline([(-4.6, -0.6), (4.6, -0.6)], ink, 1.8),
                "small": path("M-3 0 A3 3 0 0 0 3 0 Z", ink, None) + polyline([(-3.6, -0.4), (3.6, -0.4)], ink, 1.6),
                "wide": circle(0, 0, 4.8, WHITE, ink, 1.5) + circle(0, 0.5, 2.2, ink, None),
                "closed": closed,
            }
        case "sparkle":
            sparkle = circle(1.5, -1.5, 1.6, WHITE, None) + circle(-1.4, 1.5, 0.7, WHITE, None)
            return {
                "open": circle(0, 0, 4.3, ink, None) + sparkle,
                "small": circle(0, 0, 2.6, ink, None) + circle(0.8, -0.8, 0.8, WHITE, None),
                "wide": circle(0, 0, 5.4, ink, None)
                + circle(2, -2, 2, WHITE, None)
                + circle(-1.8, 1.8, 0.9, WHITE, None),
                "closed": closed,
            }
        case "button":
            return {
                "open": circle(0, 0, 2.5, ink, None),
                "small": circle(0, 0, 1.6, ink, None),
                "wide": circle(0, 0, 4.4, WHITE, ink, 1.5) + circle(0, 0, 1.8, ink, None),
                "closed": closed,
            }
        case _:  # round
            return {
                "open": circle(0, 0, 3.5, ink, None) + hl,
                "small": circle(0, 0, 2, ink, None),
                "wide": circle(0, 0, 5, WHITE, ink, 1.5) + circle(0, 0.3, 2.3, ink, None),
                "closed": closed,
            }


BROWS = {
    "straight": path("M-4.5 0 L4.5 0", "none", "{{face_ink}}", 2.2),
    "arched": path("M-4.6 1.3 Q0 -2.6 4.6 1.3", "none", "{{face_ink}}", 2.2),
    "bushy": rect(-5.2, -1.9, 10.4, 3.8, 1.9, "{{face_ink}}", None),
    "thin": path("M-4.2 0.4 Q0 -1.3 4.2 0.4", "none", "{{face_ink}}", 1.3),
}

NOSES = {
    "button": {
        "front": path("M-2.3 0 Q0 2.6 2.3 0", "none", INK, 1.6),
        "side": path("M-1 -5 Q5.5 1 -0.5 2.6", "{{skin}}", INK, 1.8),
    },
    "round": {
        "front": circle(0, 0, 2.9, "{{skin_shade}}", INK, 1.4),
        "side": path("M-1 -4.5 Q6.5 -1 5 2 Q2.5 4.5 -0.5 3", "{{skin}}", INK, 1.8),
    },
    "pointy": {
        "front": path("M0 -4.5 L2.6 2 L-0.8 2", "none", INK, 1.6),
        "side": path("M-1 -5.5 L6.5 2.5 L-0.5 2.5", "{{skin}}", INK, 1.8),
    },
    "dot": {
        "front": circle(-1.6, 0.6, 0.95, INK, None) + circle(1.6, 0.6, 0.95, INK, None),
        "side": path("M-0.5 -3 Q3 0.5 -0.5 2", "none", INK, 1.6),
    },
}

MOUTHS_FRONT = {
    "smile": path("M-6 -1 Q0 5.5 6 -1", "none", "{{face_ink}}", 2.2),
    "frown": path("M-5 2.6 Q0 -2.6 5 2.6", "none", "{{face_ink}}", 2.2),
    "grit": rect(-5.5, -2.2, 11, 4.4, 1.6, WHITE, "{{face_ink}}", 1.6)
    + polyline([(-5.5, 0), (5.5, 0)], "{{face_ink}}", 1.1),
    "o": ellipse(0, 0.5, 2.8, 3.6, "{{face_ink}}", None),
    "wavy": path(
        "M-6 0.6 Q-4.5 -1.6 -3 0.6 Q-1.5 2.8 0 0.6 Q1.5 -1.6 3 0.6 Q4.5 2.8 6 0.6", "none", "{{face_ink}}", 1.8
    ),
    "open": path("M-6.5 -1.6 Q0 9.5 6.5 -1.6 Z", WHITE, "{{face_ink}}", 1.8)
    + path("M-3 4 Q0 2 3 4 Q0 6.4 -3 4 Z", "#FF8A80", None),
}

EXPRESSIONS = {
    "happy": {"eyes": "open", "mouth": "smile", "brows": {"l": {"angle": 0, "dy": 0}, "r": {"angle": 0, "dy": 0}}},
    "sad": {"eyes": "open", "mouth": "frown", "brows": {"l": {"angle": -14, "dy": -1}, "r": {"angle": 14, "dy": -1}}},
    "angry": {"eyes": "open", "mouth": "grit", "brows": {"l": {"angle": 18, "dy": 1}, "r": {"angle": -18, "dy": 1}}},
    "surprised": {"eyes": "wide", "mouth": "o", "brows": {"l": {"angle": -4, "dy": -4}, "r": {"angle": 4, "dy": -4}}},
    "scared": {
        "eyes": "small",
        "mouth": "wavy",
        "brows": {"l": {"angle": -16, "dy": -3}, "r": {"angle": 16, "dy": -3}},
    },
    "laughing": {
        "eyes": "closed",
        "mouth": "open",
        "brows": {"l": {"angle": -6, "dy": -2}, "r": {"angle": 6, "dy": -2}},
    },
}


def face_rig(with_nose: bool, mouth_y: float = 15) -> dict[str, list[dict]]:
    def f(feature: str, side: str | None, at: Point, scale: Point = (1, 1)) -> dict:
        item: dict = {"feature": feature, "at": [num(at[0]), num(at[1])]}
        if side:
            item["side"] = side
        if scale != (1, 1):
            item["scale"] = [num(scale[0]), num(scale[1])]
        return item

    rig = {
        "front": [
            f("eye", "l", (-9, 1)),
            f("eye", "r", (9, 1)),
            f("brow", "l", (-9, -8)),
            f("brow", "r", (9, -8)),
            f("nose", None, (0, 8)),
            f("mouth", None, (0, mouth_y)),
        ],
        "three_quarter": [
            f("eye", "l", (-2.5, 1), (0.78, 1)),
            f("eye", "r", (12, 1)),
            f("brow", "l", (-2.5, -8), (0.78, 1)),
            f("brow", "r", (12, -8)),
            f("nose", None, (16, 8)),
            f("mouth", None, (9, mouth_y), (0.85, 1)),
        ],
        "side": [
            f("eye", "r", (12, 1), (0.8, 1)),
            f("brow", "r", (12, -8), (0.8, 1)),
            f("nose", None, (20.5, 7)),
            f("mouth", None, (13.5, mouth_y), (0.6, 1)),
        ],
        "back": [],
    }
    if not with_nose:
        rig = {v: [x for x in items if x["feature"] != "nose"] for v, items in rig.items()}
    return rig


# ---- hair -------------------------------------------------------------------------------------------


def cap_points(top: float = -30, fringe: float = -11, side_y: float = 2, width: float = 25.5) -> list[Point]:
    return [
        (-width, side_y),
        (-width - 0.6, -12),
        (-18, -26),
        (0, top),
        (18, -26),
        (width + 0.6, -12),
        (width, side_y),
        (17, fringe + 2.5),
        (0, fringe),
        (-17, fringe + 2.5),
    ]


def back_cover_points(bottom: float = 12, top: float = -31) -> list[Point]:
    return [
        (-26, bottom - 4),
        (-27, -12),
        (-18, -27),
        (0, top),
        (18, -27),
        (27, -12),
        (26, bottom - 4),
        (14, bottom + 1),
        (0, bottom + 2),
        (-14, bottom + 1),
    ]


HairShape = Callable[[str], str]


def hair_style(
    front: Callable[[float, float], str],
    back: Callable[[str], str],
    back_cover_bottom: float = 12,
    back_cover_top: float = -31,
    back_cover: str | None = None,
) -> dict[str, dict[str, str]]:
    """front(fx, dx) draws the hair over the face for a view; back(view) draws what sits behind the head."""
    layers: dict[str, dict[str, str]] = {"front": {}, "back": {}}
    for view in VIEWS:
        fx, dx = HEAD_VIEW[view]
        if view == "back":
            layers["front"][view] = back_cover or path(
                smooth_d(back_cover_points(back_cover_bottom, back_cover_top)), "{{hair}}"
            )
        else:
            layers["front"][view] = front(fx, dx)
        layers["back"][view] = back(view)
    return layers


def hp(points: list[Point], fx: float, dx: float, smooth: bool = True) -> str:
    pts = mapped(points, fx, dx)
    return path(smooth_d(pts) if smooth else poly_d(pts), "{{hair}}")


def nothing(_view: str) -> str:
    return ""


def curls(fx: float, dx: float, angles: Sequence[float], radius: float = 25.5, r: float = 7) -> str:
    out = ""
    for a in angles:
        rad = math.radians(a)
        out += circle(radius * math.cos(rad) * fx + dx, radius * math.sin(rad), r, "{{hair}}")
    return out


def build_hair() -> dict[str, dict]:
    spiky_pts = [
        (-25, 1),
        (-24.5, -14),
        (-28, -28),
        (-16, -24),
        (-15, -38),
        (-6, -27),
        (0, -41),
        (5, -27),
        (14, -38),
        (16, -24),
        (27, -29),
        (24.5, -14),
        (25, 1),
        (16, -9),
        (8, -13),
        (0, -11),
        (-8, -13),
        (-16, -9),
    ]
    part_pts = [
        (-25, 4),
        (-26, -14),
        (-17, -27),
        (-2, -31),
        (14, -29),
        (24, -20),
        (25.5, -6),
        (25, 2),
        (20, -8),
        (12, -15),
        (2, -18),
        (-6, -10),
        (-16, -4),
    ]
    bob_front = [
        (-27, 14),
        (-28.5, -4),
        (-24, -22),
        (-12, -30),
        (0, -31),
        (12, -30),
        (24, -22),
        (28.5, -4),
        (27, 14),
        (20, 14),
        (20.5, 0),
        (17, -10),
        (8, -13),
        (0, -12),
        (-8, -13),
        (-17, -10),
        (-20.5, 0),
        (-20, 14),
    ]

    def ponytail(view: str) -> str:
        if view == "front":
            return ellipse(26, -18, 6, 10, "{{hair}}")
        if view == "back":
            return circle(0, -20, 3.2, "#FF6B4A", INK, 1.6) + ellipse(0, 0, 7, 17, "{{hair}}")
        x = -24 if view == "side" else -22
        return path(
            smooth_d([(x + 4, -24), (x - 8, -16), (x - 12, 2), (x - 6, 16), (x + 2, 4), (x + 4, -12)]), "{{hair}}"
        )

    def braids(view: str) -> str:
        out = ""
        sides = {"front": (-26, 26), "back": (-20, 20), "three_quarter": (-24,), "side": (-20,)}[view]
        for x in sides:
            for i, y in enumerate((4, 12, 20, 28)):
                out += ellipse(x + (i % 2) * (1 if x > 0 else -1), y, 4.6, 4.4, "{{hair}}", INK, 2)
            out += circle(x, 34, 2.4, "#FF6B4A", INK, 1.4)
        return out

    def long_back(view: str) -> str:
        pts = [(-29, -8), (-27, -26), (0, -32), (27, -26), (29, -8), (30, 34), (-30, 34)]
        if view in ("side", "three_quarter"):
            pts = [(-30, -8), (-26, -26), (0, -32), (14, -26), (12, 10), (6, 34), (-32, 34)]
        return path(smooth_d(pts) if view != "back" else rounded_d(pts, 8), "{{hair}}")

    def bob_back(view: str) -> str:
        if view == "back":
            return ""
        pts = [(-28, 16), (-30, -6), (-22, -26), (0, -32), (22, -26), (30, -6), (28, 16), (0, 19)]
        if view in ("side", "three_quarter"):
            pts = [(-30, 16), (-31, -6), (-22, -26), (0, -32), (12, -26), (14, -4), (10, 16), (-10, 19)]
        return path(smooth_d(pts), "{{hair}}")

    def puffs(view: str) -> str:
        if view == "side":
            return circle(-14, -27, 10, "{{hair}}")
        if view == "three_quarter":
            return circle(-22, -24, 10, "{{hair}}") + circle(17, -27, 9, "{{hair}}")
        return circle(-21, -25, 10, "{{hair}}") + circle(21, -25, 10, "{{hair}}")

    def afro(view: str) -> str:
        cx = {"front": 0, "back": 0, "three_quarter": -3, "side": -6}[view]
        return circle(cx, -8, 37, "{{hair}}")

    def bun_back(view: str) -> str:
        return circle(0, -32, 9, "{{hair}}") if view == "back" else ""

    def bun_front(fx: float, dx: float) -> str:
        return circle(dx - 3 * (1 - fx) * 10, -33, 9, "{{hair}}") + hp(cap_points(-28, -13), fx, dx)

    def long_front(fx: float, dx: float) -> str:
        strands = ""
        if fx > 0.9:  # front and three-quarter: strands framing the face
            for side in (-1, 1):
                pts = [(-26 * side, -6), (-28 * side, 30), (-21 * side, 30), (-20 * side, -2)]
                strands += hp(pts, fx, dx)
        return hp(cap_points(-30, -14), fx, dx) + strands

    def curly_front(fx: float, dx: float) -> str:
        return hp(cap_points(-27, -12), fx, dx) + curls(fx, dx, range(-170, -9, 20))

    def curly_back(view: str) -> str:
        if view == "back":
            return curls(1, 0, range(-180, 1, 20), 25, 7.5)
        fx, dx = HEAD_VIEW[view]
        return curls(fx, dx, (170, 190, 160, -10, 10, 20), 25, 7)

    styles = {
        "none": ({"front": {v: "" for v in VIEWS}, "back": {v: "" for v in VIEWS}}, "Bald"),
        "crop": (hair_style(lambda fx, dx: hp(cap_points(-29.5, -13, -1), fx, dx), nothing), "Crop"),
        "buzz": (hair_style(lambda fx, dx: hp(cap_points(-26.5, -17, -4, 24.3), fx, dx), nothing, 4, -27), "Buzz"),
        "spiky": (
            hair_style(
                lambda fx, dx: hp(spiky_pts, fx, dx, smooth=False),
                nothing,
                back_cover=hp([*spiky_pts[:13], (26, 8), (14, 13), (0, 14), (-14, 13), (-26, 8)], 1, 0, smooth=False),
            ),
            "Spiky",
        ),
        "side_part": (hair_style(lambda fx, dx: hp(part_pts, fx, dx), nothing), "Side part"),
        "bob": (hair_style(lambda fx, dx: hp(bob_front, fx, dx), bob_back, 18), "Bob"),
        "curly": (hair_style(curly_front, curly_back, 10), "Curly"),
        "afro": (hair_style(lambda fx, dx: hp(cap_points(-29, -13), fx, dx), afro, 10), "Afro"),
        "ponytail": (hair_style(lambda fx, dx: hp(cap_points(-30, -12), fx, dx), ponytail), "Ponytail"),
        "two_puffs": (hair_style(lambda fx, dx: hp(cap_points(-28, -13), fx, dx), puffs), "Two puffs"),
        "braids": (hair_style(lambda fx, dx: hp(cap_points(-29, -12), fx, dx), braids), "Braids"),
        "long_straight": (hair_style(long_front, long_back, 16), "Long"),
        "bun": (hair_style(bun_front, bun_back), "Bun"),
    }
    options = {}
    for id_, (layers, label) in styles.items():
        options[id_] = {"label": label, "body_types": HUMANS, "layers": layers}
    return options


# ---- headwear ---------------------------------------------------------------------------------------


def build_headwear() -> dict[str, dict]:
    def per_view(fn: Callable[[str, float, float], str]) -> dict[str, str]:
        return {v: fn(v, *HEAD_VIEW[v]) for v in VIEWS}

    dome = [(-25.5, -11), (-25, -22), (-14, -32), (0, -34), (14, -32), (25, -22), (25.5, -11), (0, -13)]

    def cap(view: str, fx: float, dx: float) -> str:
        crown = path(smooth_d(mapped(dome, fx, dx)), "{{hat}}") + circle(dx, -33.5, 2.2, "{{hat_shade}}", INK, 1.6)
        if view == "front":
            brim = path(smooth_d([(-27, -12), (0, -17), (27, -12), (24, -7), (0, -10), (-24, -7)]), "{{hat_shade}}")
        elif view == "back":
            brim = rect(-7, -15, 14, 5, 2, "{{hat_shade}}", INK, 1.8)
        else:
            reach = 38 if view == "side" else 32
            brim = path(smooth_d([(dx + 8, -14), (reach, -11), (reach, -7), (dx + 8, -9)]), "{{hat_shade}}")
        return crown + brim

    def beanie(view: str, fx: float, dx: float) -> str:
        return (
            path(
                smooth_d(
                    mapped([(-26, -10), (-26, -22), (-14, -33), (0, -35), (14, -33), (26, -22), (26, -10)], fx, dx)
                ),
                "{{hat}}",
            )
            + rect(-27 * fx + dx, -17, 54 * fx, 8, 4, "{{hat_shade}}")
            + circle(dx, -37, 5, WHITE)
        )

    def hijab_back(view: str, fx: float, dx: float) -> str:
        pts = [(-31, -8), (-29, -27), (0, -35), (29, -27), (31, -8), (33, 22), (23, 38), (-23, 38), (-33, 22)]
        return path(smooth_d(mapped(pts, fx, dx)), "{{hat}}")

    def hijab_front(view: str, fx: float, dx: float) -> str:
        outer = ellipse_d(dx, -2, 30 * fx, 34)
        if view == "back":
            return path(outer, "{{hat}}")
        face_dx = {"front": 0, "three_quarter": 6, "side": 10}[view]
        inner = ellipse_d(face_dx, 4, (19.5 if view == "front" else 16) * fx, 23.5)
        return path(f"{outer} {inner}", "{{hat}}", extra=' fill-rule="evenodd"')

    def turban(view: str, fx: float, dx: float) -> str:
        shape = path(
            smooth_d(
                mapped([(-27, -2), (-28, -18), (-19, -33), (0, -40), (19, -33), (28, -18), (27, -2), (0, -8)], fx, dx)
            ),
            "{{hat}}",
        )
        folds = path(f"M{n(-24 * fx + dx)} -8 Q{n(dx)} -26 {n(22 * fx + dx)} -30", "none", "{{hat_shade}}", 2) + path(
            f"M{n(-20 * fx + dx)} -24 Q{n(dx)} -12 {n(25 * fx + dx)} -14", "none", "{{hat_shade}}", 2
        )
        return shape + folds

    def helmet(view: str, fx: float, dx: float) -> str:
        glass = circle(0, -3, 35, WHITE, INK, SW, ' fill-opacity="0.22"')
        shine = path("M-22 -22 Q-14 -32 -2 -34", "none", WHITE, 3)
        collar = rect(-23, 25, 46, 9, 4, "#C9CED6")
        return collar + glass + shine

    empty = {v: "" for v in VIEWS}
    return {
        "none": {"label": "No hat", "body_types": ALL, "layers": {"back": empty, "front": empty}, "hides": []},
        "cap": {"label": "Cap", "body_types": ALL, "layers": {"back": empty, "front": per_view(cap)}, "hides": []},
        "beanie": {
            "label": "Beanie",
            "body_types": ALL,
            "layers": {"back": empty, "front": per_view(beanie)},
            "hides": [],
        },
        "hijab": {
            "label": "Hijab",
            "body_types": HUMANS,
            "layers": {"back": per_view(hijab_back), "front": per_view(hijab_front)},
            "hides": ["hair.front", "hair.back"],
        },
        "turban": {
            "label": "Turban",
            "body_types": HUMANS,
            "layers": {"back": empty, "front": per_view(turban)},
            "hides": ["hair.front"],
        },
        "space_helmet": {
            "label": "Space helmet",
            "body_types": ALL,
            "layers": {"back": empty, "front": per_view(helmet)},
            "hides": [],
        },
    }


# ---- tops, bottoms, shoes -----------------------------------------------------------------------------


def build_tops() -> dict[str, dict]:
    def make(style: str) -> dict[str, dict[str, dict[str, str]]]:
        by_body: dict[str, dict[str, dict[str, str]]] = {}
        for bt, b in BODIES.items():
            torso_layer: dict[str, str] = {}
            behind_layer: dict[str, str] = {}
            T = b["T"]
            for view in VIEWS:
                x = partial(bview, view)
                front = view != "back"
                behind = ""
                if style == "none":
                    if bt == "robot":
                        art = path(torso_d(b, view), "{{skin}}")
                        if front:
                            art += rect(x(-9), -T + 9, 18 * BODY_VIEW[view][0], 12, 3, "#1F2A44", INK, 1.8)
                            art += (
                                circle(x(-4), -T + 15, 1.8, "#FF6B4A", None)
                                + circle(x(1), -T + 15, 1.8, "#FFD23F", None)
                                + circle(x(6), -T + 15, 1.8, "#B7E4A7", None)
                            )
                    else:
                        art = path(torso_d(b, view), "{{skin}}")
                        if front:
                            art += ellipse(x(0), -11, 9 * BODY_VIEW[view][0], 11, "{{skin_light}}", None)
                elif style == "dress":
                    skirt = mapped([(-12, -9), (12, -9), (20, 17), (0, 19), (-20, 17)], *BODY_VIEW[view])
                    art = path(smooth_d(skirt), "{{top}}") + path(torso_d(b, view, -6), "{{top}}")
                    art += polyline([(x(-12), -9), (x(12), -9)], "{{top_shade}}", 2)
                elif style == "raincoat":
                    art = path(torso_d(b, view, 12, 3), "{{top}}")
                    if front:
                        art += "".join(circle(x(0), y, 1.5, INK, None) for y in (-T + 10, -T + 18, -T + 26))
                        art += rect(x(-11), -4, 7 * BODY_VIEW[view][0], 6, 1.5, "{{top_shade}}", INK, 1.4)
                        art += path(f"M{n(x(-8))} {n(-T)} L{n(x(0))} {n(-T + 6)} L{n(x(8))} {n(-T)}", "none", INK, 1.6)
                else:
                    art = path(torso_d(b, view), "{{top}}")
                    if style == "tshirt" and front:
                        art += path(f"M{n(x(-6))} {n(-T)} Q{n(x(0))} {n(-T + 6)} {n(x(6))} {n(-T)}", "none", INK, 1.6)
                    elif style == "hoodie":
                        behind = ellipse(x(0), -T - 1, 12 * BODY_VIEW[view][0], 6, "{{top_shade}}")
                        if front:
                            art += rect(x(-9), -14, 18 * BODY_VIEW[view][0], 8, 3, "{{top_shade}}", INK, 1.6)
                            art += polyline([(x(-3), -T + 1), (x(-3), -T + 9)], INK, 1.4) + polyline(
                                [(x(3), -T + 1), (x(3), -T + 9)], INK, 1.4
                            )
                    elif style == "sweater":
                        art += rect(
                            x(-14) if view != "side" else x(-14),
                            -T + 9,
                            28 * BODY_VIEW[view][0],
                            6,
                            1,
                            "{{top_shade}}",
                            None,
                        )
                        art += path(torso_d(b, view), "none")
                    elif style == "jersey" and front:
                        art += path(f"M{n(x(-6))} {n(-T)} L{n(x(0))} {n(-T + 7)} L{n(x(6))} {n(-T)}", "none", INK, 1.6)
                        art += path(poly_d(star_points(x(0), -14, 6.5, 2.8)), WHITE, INK, 1.4)
                    elif style == "dungarees":
                        bib_w = 18 * BODY_VIEW[view][0]
                        art += rect(x(0) - bib_w / 2, -T + 12, bib_w, T - 8, 3, "{{bottom}}", INK, 1.8)
                        if front:
                            art += polyline([(x(-7), -T + 12), (x(-9), -T)], "{{bottom}}", 3) + polyline(
                                [(x(7), -T + 12), (x(9), -T)], "{{bottom}}", 3
                            )
                            art += circle(x(-5.5), -T + 15, 1.4, "#FFD23F", INK, 1) + circle(
                                x(5.5), -T + 15, 1.4, "#FFD23F", INK, 1
                            )
                    elif style == "superhero":
                        art += rect(x(-14), -6, 28 * BODY_VIEW[view][0], 5, 1, "{{top_shade}}", INK, 1.6)
                        if front:
                            art += path(poly_d(star_points(x(0), -T + 14, 7.5, 3.2)), "#FFD23F", INK, 1.6)
                torso_layer[view] = art
                behind_layer[view] = behind
            by_body[bt] = {"torso": torso_layer, "behind": behind_layer}
        return by_body

    spec = {
        "tshirt": ("T-shirt", ["arm_upper"], ALL),
        "hoodie": ("Hoodie", ["arm_upper", "arm_lower"], ALL),
        "raincoat": ("Raincoat", ["arm_upper", "arm_lower"], ALL),
        "sweater": ("Sweater", ["arm_upper", "arm_lower"], ALL),
        "jersey": ("Sports jersey", ["arm_upper"], ALL),
        "dress": ("Dress", [], ALL),
        "dungarees": ("Dungarees", ["arm_upper"], ALL),
        "superhero": ("Superhero suit", ["arm_upper", "arm_lower"], ALL),
        "none": ("No top", [], CRITTERS),
    }
    return {
        id_: {"label": label, "body_types": bts, "coverage": cov, "by_body": make(id_)}
        for id_, (label, cov, bts) in spec.items()
    }


def build_bottoms() -> dict[str, dict]:
    def make(style: str) -> dict[str, dict[str, dict[str, str]]]:
        by_body = {}
        for bt, b in BODIES.items():
            hips: dict[str, str] = {}
            H = b["H"]
            for view in VIEWS:
                fx, dx = BODY_VIEW[view]
                w = H + 5
                if style == "none":
                    art = rect(-w * fx + dx, -5, 2 * w * fx, 10, 3, "{{skin}}") if bt == "robot" else ""
                elif style == "skirt":
                    art = path(
                        smooth_d(mapped([(-w, -6), (w, -6), (w + 7, 13), (0, 15), (-w - 7, 13)], fx, dx)), "{{bottom}}"
                    )
                    art += polyline([(dx - w * fx, -6), (dx + w * fx, -6)], "{{bottom_shade}}", 2)
                else:
                    width = w - (1.5 if style == "leggings" else 0)
                    art = rect(-width * fx + dx, -5, 2 * width * fx, 11, 3, "{{bottom}}")
                    if style == "jeans":
                        art += polyline([(dx, -5), (dx, 4)], "{{bottom_shade}}", 1.4)
                    if style == "cargo" and view != "back":
                        art += rect(dx - width * fx - 1, 1, 5, 6, 1.5, "{{bottom_shade}}", INK, 1.4)
                hips[view] = art
            by_body[bt] = {"hips": hips}
        return by_body

    spec = {
        "shorts": ("Shorts", ["leg_upper"], ALL),
        "trousers": ("Trousers", ["leg_upper", "leg_lower"], ALL),
        "jeans": ("Jeans", ["leg_upper", "leg_lower"], ALL),
        "skirt": ("Skirt", [], ALL),
        "leggings": ("Leggings", ["leg_upper", "leg_lower"], ALL),
        "cargo": ("Cargo pants", ["leg_upper", "leg_lower"], ALL),
        "none": ("Nothing", [], CRITTERS),
    }
    return {
        id_: {"label": label, "body_types": bts, "coverage": cov, "by_body": make(id_)}
        for id_, (label, cov, bts) in spec.items()
    }


def build_shoes() -> dict[str, dict]:
    def make(style: str) -> dict[str, dict[str, dict[str, str]]]:
        by_body = {}
        for bt, b in BODIES.items():
            foot: dict[str, str] = {}
            fw, lw = b["foot"], b["lw"]
            for view in VIEWS:
                cx = {"front": 0, "back": 0, "three_quarter": 2.5, "side": 4.5}[view]
                rx = fw * {"front": 1, "back": 1, "three_quarter": 1.15, "side": 1.35}[view]
                ry = fw * 0.62
                cy = 2.5
                if style == "none":
                    if bt == "robot":
                        art = rect(cx - rx, cy - 3.5, 2 * rx, 7, 2.5, "{{skin}}") + rect(
                            cx - rx, cy + 2, 2 * rx, 2.5, 1, METAL, None
                        )
                    else:
                        art = (
                            ellipse(cx, cy, rx, ry, "{{skin}}")
                            + polyline([(cx - 1.8, cy + 1.5), (cx - 1.8, cy + 3.2)], INK, 1.1)
                            + polyline([(cx + 1.8, cy + 1.5), (cx + 1.8, cy + 3.2)], INK, 1.1)
                        )
                elif style == "sandals":
                    art = ellipse(cx, cy, rx, ry, "{{skin}}") + polyline(
                        [(cx - rx * 0.6, cy - 1), (cx + rx * 0.6, cy - 1)], "{{shoes}}", 2.2
                    )
                    art += polyline([(cx - rx * 0.9, cy + 2.4), (cx + rx * 0.9, cy + 2.4)], "{{shoes_shade}}", 2)
                else:
                    shaft = ""
                    if style in ("boots", "rain_boots"):
                        top = -9 if style == "boots" else -14
                        shaft = rect(-lw / 2 - 1.6, top, lw + 3.2, -top + 3, 2, "{{shoes}}")
                        if style == "rain_boots":
                            shaft += polyline([(-lw / 2 + 1, top + 3), (-lw / 2 + 1, top + 8)], WHITE, 1.6)
                    art = shaft + ellipse(cx, cy, rx, ry, "{{shoes}}")
                    if style == "sneakers":
                        art += path(
                            f"M{n(cx - rx * 0.92)} {n(cy + 1.4)} Q{n(cx)} {n(cy + ry * 1.25)} "
                            f"{n(cx + rx * 0.92)} {n(cy + 1.4)}",
                            "none",
                            WHITE,
                            2.2,
                        )
                foot[view] = art
            by_body[bt] = {"foot": foot}
        return by_body

    spec = {
        "sneakers": ("Sneakers", ALL),
        "boots": ("Boots", ALL),
        "sandals": ("Sandals", ALL),
        "rain_boots": ("Rain boots", ALL),
        "none": ("Bare feet", CRITTERS),
    }
    return {id_: {"label": label, "body_types": bts, "by_body": make(id_)} for id_, (label, bts) in spec.items()}


# ---- extras -------------------------------------------------------------------------------------------


def build_extras() -> dict[str, dict]:
    empty = {v: "" for v in VIEWS}

    def glasses(kind: str) -> dict[str, str]:
        def lens(cx: float, sx: float) -> str:
            if kind == "square":
                return rect(cx - 5.6 * sx, -3.6, 11.2 * sx, 8.4, 2, WHITE, INK, 1.8, ' fill-opacity="0.18"')
            if kind == "star":
                return path(
                    poly_d(mapped(star_points(0, 1, 7, 3.2), sx, cx)), "#FFD23F", INK, 1.6, ' fill-opacity="0.55"'
                )
            return ellipse(cx, 1, 5.6 * sx, 5.6, WHITE, INK, 1.8, ' fill-opacity="0.18"')

        return {
            "front": lens(-9, 1) + lens(9, 1) + polyline([(-3.4, 0), (3.4, 0)], INK, 1.6),
            "three_quarter": lens(-2.5, 0.78) + lens(12, 1) + polyline([(2, 0), (6.4, 0)], INK, 1.6),
            "side": lens(12, 0.8) + polyline([(7.5, 0), (-3, -1)], INK, 1.6),
            "back": "",
        }

    def cheeks(art: Callable[[float, float, float], str]) -> dict[str, str]:
        return {
            "front": art(-14, 9, 1) + art(14, 9, 1),
            "three_quarter": art(-5, 9, 0.75) + art(18, 9, 1),
            "side": art(9, 9, 0.8),
            "back": "",
        }

    blush = cheeks(lambda x, y, s: ellipse(x, y, 4 * s, 2.4, "#FF8FA3", None, extra=' fill-opacity="0.6"'))
    freckles = cheeks(
        lambda x, y, s: "".join(
            circle(x + dx * s, y + dy, 0.75, "#8A4B2A", None, extra=' fill-opacity="0.75"')
            for dx, dy in ((-2.5, -0.5), (0, 1), (2.5, -0.5), (0.5, -2))
        )
    )

    def headphones() -> dict[str, str]:
        band = lambda fx, dx: path(f"M{n(-25 * fx + dx)} -2 Q{n(dx)} -48 {n(25 * fx + dx)} -2", "none", "#2B2B2B", 3.6)  # noqa: E731
        cup = lambda x: rect(x - 4, -8, 8, 15, 3, "#FF6B4A")  # noqa: E731
        return {
            "front": band(1, 0) + cup(-26) + cup(26),
            "three_quarter": band(0.93, -2) + cup(-19),
            "side": band(0.6, -5) + cup(-6),
            "back": band(1, 0) + cup(-26) + cup(26),
        }

    def cape() -> dict[str, dict[str, dict[str, str]]]:
        by_body = {}
        for bt, b in BODIES.items():
            T = b["T"]
            drop = b["Th"] + 6
            back_view = path(
                smooth_d([(-14, -T + 1), (14, -T + 1), (20, drop), (0, drop + 3), (-20, drop)]), "{{cape}}"
            )
            behind = {
                "front": path(
                    smooth_d([(-15, -T + 2), (15, -T + 2), (22, drop), (0, drop + 4), (-22, drop)]), "{{cape_shade}}"
                ),
                "three_quarter": path(
                    smooth_d([(-10, -T + 2), (8, -T + 2), (6, drop), (-12, drop + 3), (-24, drop - 2)]), "{{cape}}"
                ),
                "side": path(
                    smooth_d([(-4, -T + 2), (2, -T + 2), (-4, drop), (-16, drop + 2), (-26, drop - 4)]), "{{cape}}"
                ),
                "back": "",
            }
            over = {"front": "", "three_quarter": "", "side": "", "back": back_view}
            clasp = {
                "front": path(poly_d([(-9, -T - 1), (0, -T + 5), (9, -T - 1)]), "{{cape}}")
                + circle(0, -T + 3, 2.2, "#FFD23F", INK, 1.4),
                "three_quarter": path(poly_d([(-5, -T - 1), (3, -T + 5), (9, -T - 1)]), "{{cape}}")
                + circle(3, -T + 3, 2, "#FFD23F", INK, 1.4),
                "side": "",
                "back": "",
            }
            by_body[bt] = {"behind": behind, "over": over, "collar": clasp}
        return by_body

    def backpack() -> dict[str, dict[str, dict[str, str]]]:
        by_body = {}
        for bt, b in BODIES.items():
            T = b["T"]
            pack_back = rect(-12, -T + 5, 24, T - 8, 5, "{{backpack}}") + rect(
                -8, -14, 16, 8, 3, "{{backpack_shade}}", INK, 1.6
            )
            behind = {
                "front": rect(-17, -T + 7, 34, T - 10, 6, "{{backpack_shade}}"),
                "three_quarter": rect(-21, -T + 5, 14, T - 9, 5, "{{backpack}}"),
                "side": rect(-21, -T + 5, 13, T - 9, 5, "{{backpack}}"),
                "back": "",
            }
            straps = {
                "front": polyline([(-8, -T), (-9, -12)], "{{backpack_shade}}", 3)
                + polyline([(8, -T), (9, -12)], "{{backpack_shade}}", 3),
                "three_quarter": polyline([(4, -T), (5, -12)], "{{backpack_shade}}", 3),
                "side": polyline([(1, -T), (2, -12)], "{{backpack_shade}}", 3),
                "back": "",
            }
            over = {"front": "", "three_quarter": "", "side": "", "back": pack_back}
            by_body[bt] = {"behind": behind, "straps": straps, "over": over}
        return by_body

    wand = polyline([(0, 2), (0, 20)], "#8A5A3B", 2.6) + path(poly_d(star_points(0, 23, 5.5, 2.4)), "#FFD23F", INK, 1.6)

    return {
        "glasses_round": {
            "label": "Round glasses",
            "group": "glasses",
            "body_types": ALL,
            "layers": {"glasses": glasses("round")},
        },
        "glasses_square": {
            "label": "Square glasses",
            "group": "glasses",
            "body_types": ALL,
            "layers": {"glasses": glasses("square")},
        },
        "glasses_star": {
            "label": "Star glasses",
            "group": "glasses",
            "body_types": ALL,
            "layers": {"glasses": glasses("star")},
        },
        "cape": {"label": "Cape", "body_types": ALL, "slot": "cape", "by_body": cape()},
        "backpack": {"label": "Backpack", "body_types": ALL, "slot": "backpack", "by_body": backpack()},
        "wand": {"label": "Magic wand", "body_types": ALL, "layers": {"hand": {v: wand for v in VIEWS}}},
        "headphones": {"label": "Headphones", "body_types": ALL, "layers": {"headphones": headphones()}},
        "freckles": {"label": "Freckles", "body_types": [*HUMANS, *ANIMALS], "layers": {"cheeks": freckles}},
        "blush": {"label": "Rosy cheeks", "body_types": ALL, "layers": {"cheeks": blush}},
        "_none": {"label": "", "body_types": [], "layers": {"glasses": empty}},
    }


# ---- layers, poses ---------------------------------------------------------------------------------


def L(kind: str, bone: str, **kw: str) -> dict[str, str]:  # noqa: N802
    return {"kind": kind, "bone": bone, **kw}


def limb_chain(side: str, which: str) -> list[dict[str, str]]:
    if which == "arm":
        return [
            L("body", f"shoulder_{side}", part="arm_upper_ink"),
            L("body", f"elbow_{side}", part="arm_lower_ink"),
            L("body", f"shoulder_{side}", part="arm_upper_fill"),
            L("body", f"elbow_{side}", part="arm_lower_fill"),
        ]
    return [
        L("body", f"hip_{side}", part="leg_upper_ink"),
        L("body", f"knee_{side}", part="leg_lower_ink"),
        L("body", f"hip_{side}", part="leg_upper_fill"),
        L("body", f"knee_{side}", part="leg_lower_fill"),
    ]


def arm(side: str) -> list[dict[str, str]]:
    out = limb_chain(side, "arm")
    if side == "r":
        out.append(L("extra", "wrist_r", extra="wand", layer="hand"))
    out.append(L("body", f"wrist_{side}", part="hand"))
    return out


def leg(side: str) -> list[dict[str, str]]:
    return [*limb_chain(side, "leg"), L("part", f"ankle_{side}", category="shoes", layer="foot")]


HEAD_LAYERS = [
    L("part", "head", category="face_shape", layer="ears_back"),
    L("part", "head", category="face_shape", layer="base"),
    L("face", "head"),
    L("extra", "head", extra="freckles", layer="cheeks"),
    L("extra", "head", extra="blush", layer="cheeks"),
    L("part", "head", category="face_shape", layer="ears_front"),
    L("part", "head", category="hair", layer="front"),
    L("part", "head", category="headwear", layer="front"),
    L("extra", "head", group="glasses", layer="glasses"),
    L("extra", "head", extra="headphones", layer="headphones"),
]
BEHIND_HEAD = [L("part", "head", category="hair", layer="back"), L("part", "head", category="headwear", layer="back")]
LEGS_BOTH = [
    *limb_chain("l", "leg")[:2],
    *limb_chain("r", "leg")[:2],
    *limb_chain("l", "leg")[2:],
    *limb_chain("r", "leg")[2:],
    L("part", "ankle_l", category="shoes", layer="foot"),
    L("part", "ankle_r", category="shoes", layer="foot"),
]
TORSO = [
    L("part", "torso", category="bottom", layer="hips"),
    L("body", "neck", part="neck"),
    L("part", "torso", category="top", layer="torso"),
]

LAYERS = {
    "front": [
        L("pose", "root", layer="back"),
        L("extra", "torso", extra="cape", layer="behind"),
        *BEHIND_HEAD,
        L("part", "torso", category="top", layer="behind"),
        L("extra", "torso", extra="backpack", layer="behind"),
        L("body", "tail", part="tail"),
        *LEGS_BOTH,
        *TORSO,
        L("extra", "torso", extra="backpack", layer="straps"),
        L("extra", "torso", extra="cape", layer="collar"),
        *arm("l"),
        *arm("r"),
        *HEAD_LAYERS,
        L("pose", "root", layer="front"),
    ],
    "three_quarter": [
        L("pose", "root", layer="back"),
        L("extra", "torso", extra="cape", layer="behind"),
        *BEHIND_HEAD,
        L("part", "torso", category="top", layer="behind"),
        L("extra", "torso", extra="backpack", layer="behind"),
        L("body", "tail", part="tail"),
        *arm("l"),
        *leg("l"),
        *leg("r"),
        *TORSO,
        L("extra", "torso", extra="backpack", layer="straps"),
        L("extra", "torso", extra="cape", layer="collar"),
        *arm("r"),
        *HEAD_LAYERS,
        L("pose", "root", layer="front"),
    ],
    "side": [
        L("pose", "root", layer="back"),
        L("extra", "torso", extra="cape", layer="behind"),
        *BEHIND_HEAD,
        L("part", "torso", category="top", layer="behind"),
        L("extra", "torso", extra="backpack", layer="behind"),
        L("body", "tail", part="tail"),
        *arm("l"),
        *leg("l"),
        *leg("r"),
        *TORSO,
        L("extra", "torso", extra="backpack", layer="straps"),
        *arm("r"),
        *HEAD_LAYERS,
        L("pose", "root", layer="front"),
    ],
    "back": [
        L("pose", "root", layer="back"),
        *LEGS_BOTH,
        L("part", "torso", category="bottom", layer="hips"),
        *arm("l"),
        *arm("r"),
        L("body", "neck", part="neck"),
        L("part", "torso", category="top", layer="torso"),
        L("extra", "torso", extra="backpack", layer="over"),
        L("extra", "torso", extra="cape", layer="over"),
        L("body", "tail", part="tail"),
        L("part", "head", category="face_shape", layer="ears_back"),
        L("part", "head", category="face_shape", layer="base"),
        L("part", "head", category="face_shape", layer="ears_front"),
        L("part", "head", category="hair", layer="front"),
        L("part", "head", category="headwear", layer="back"),
        L("part", "head", category="hair", layer="back"),
        L("part", "head", category="headwear", layer="front"),
        L("extra", "head", extra="headphones", layer="headphones"),
        L("pose", "root", layer="front"),
    ],
}


def pose(
    view: str,
    angles: dict[str, float],
    root: Point = (0, 0),
    mirror: bool = False,
    expression: str | None = None,
    extras: Sequence[tuple[str, str, str]] = (),
) -> dict:
    """Angles in degrees; feet are turned to stay flat on the ground. Extras: (bone, svg, "back" | "front")."""
    full = dict(angles)
    for side in ("l", "r"):
        full[f"ankle_{side}"] = -(full.get(f"hip_{side}", 0) + full.get(f"knee_{side}", 0))
    out: dict = {
        "view": view,
        "mirror": mirror,
        "root": [num(root[0]), num(root[1])],
        "angles": {k: num(v) for k, v in full.items() if num(v) != 0},
    }
    if expression:
        out["expression"] = expression
    if extras:
        out["extras"] = [{"bone": bone, "svg": svg, "layer": layer} for bone, svg, layer in extras]
    return out


THINK = "".join(circle(x, y, r, WHITE, INK, 1.6) for x, y, r in ((27, -26, 2), (33, -33, 3), (41, -40, 4.2)))
SHAKE = "".join(
    polyline([(sx * 30, -10 + i * 7), (sx * 35, -12 + i * 7)], INK, 1.8) for sx in (-1, 1) for i in range(3)
)
CONFETTI = "".join(
    rect(x, y, 4, 2.4, 0.6, c, None)
    for x, y, c in (
        (-40, -30, "#FFD23F"),
        (36, -38, "#FF6B4A"),
        (-30, -48, "#1F5BD1"),
        (28, -52, "#B7E4A7"),
        (-46, -12, "#FF7FB0"),
        (44, -16, "#1F5BD1"),
        (6, -58, "#FF6B4A"),
        (-14, -60, "#B7E4A7"),
    )
)
SPEED = "".join(polyline([(-34 - i * 3, -20 + i * 9), (-46 - i * 3, -20 + i * 9)], INK, 1.8) for i in range(3))
JUMP_LINES = "".join(polyline([(x, 10), (x, 16)], INK, 1.6) for x in (-4, 4))
STOOL = rect(-16, 10, 32, 7, 2, "#C9A27A") + rect(-13, 17, 4, 18, 1, "#A07A52") + rect(9, 17, 4, 18, 1, "#A07A52")

BASE = {"shoulder_l": 14, "elbow_l": 4, "shoulder_r": -14, "elbow_r": -4, "hip_l": 3, "hip_r": -3}
TQ = {"shoulder_l": 6, "elbow_l": 6, "shoulder_r": -8, "elbow_r": -6, "hip_l": 2, "hip_r": -3}
SIDE = {"shoulder_l": 8, "elbow_l": -8, "shoulder_r": -6, "elbow_r": -10, "hip_l": 4, "hip_r": -4}

POSES = {
    "front": pose("front", BASE),
    "three_quarter_left": pose("three_quarter", TQ, mirror=True),
    "side_left": pose("side", SIDE, mirror=True),
    "back": pose("back", BASE),
    "three_quarter_right": pose("three_quarter", TQ),
    "side_right": pose("side", SIDE),
    "walk": pose(
        "three_quarter",
        {
            "shoulder_l": -28,
            "elbow_l": -12,
            "shoulder_r": 26,
            "elbow_r": -14,
            "hip_l": 18,
            "knee_l": 14,
            "hip_r": -22,
            "knee_r": 6,
        },
        root=(0, -1),
    ),
    "run": pose(
        "three_quarter",
        {
            "torso": 10,
            "head": -6,
            "shoulder_l": 40,
            "elbow_l": -70,
            "shoulder_r": -55,
            "elbow_r": -75,
            "hip_l": 45,
            "knee_l": 70,
            "hip_r": -60,
            "knee_r": 70,
        },
        root=(0, -6),
        extras=[("root", SPEED, "back")],
    ),
    "point": pose("front", {**BASE, "head": -4, "shoulder_r": -95, "elbow_r": 0}),
    "sit": pose(
        "three_quarter",
        {
            "torso": -4,
            "shoulder_l": -10,
            "elbow_l": -40,
            "shoulder_r": -18,
            "elbow_r": -45,
            "hip_l": -80,
            "knee_l": 75,
            "hip_r": -86,
            "knee_r": 82,
        },
        root=(0, 16),
        extras=[("root", STOOL, "back")],
    ),
    "jump": pose(
        "front",
        {"shoulder_l": 130, "elbow_l": 25, "shoulder_r": -130, "elbow_r": -25, "hip_l": 22, "hip_r": -22},
        root=(0, -10),
        expression="laughing",
        extras=[("ankle_l", JUMP_LINES, "back"), ("ankle_r", JUMP_LINES, "back")],
    ),
    "wave": pose("front", {**BASE, "shoulder_r": -110, "elbow_r": -60}),
    "hands_on_hips": pose("front", {**BASE, "shoulder_l": 48, "elbow_l": -105, "shoulder_r": -48, "elbow_r": 105}),
    "thinking": pose(
        "front", {**BASE, "head": 6, "shoulder_r": -60, "elbow_r": 200}, extras=[("head", THINK, "front")]
    ),
    "scared_pose": pose(
        "front",
        {**BASE, "shoulder_l": 120, "elbow_l": 50, "shoulder_r": -120, "elbow_r": -50},
        expression="scared",
        extras=[("head", SHAKE, "front")],
    ),
    "celebrate": pose(
        "front",
        {**BASE, "shoulder_l": 135, "elbow_l": 15, "shoulder_r": -135, "elbow_r": -15},
        root=(0, -4),
        expression="laughing",
        extras=[("root", CONFETTI, "back")],
    ),
}
FACE_VISIBLE = [p for p, data in POSES.items() if data["view"] in ("front", "three_quarter")]

DEFAULTS = {
    "kid": {
        "parts": {
            "face_shape": "round",
            "eyes": "round",
            "brows": "arched",
            "nose": "button",
            "hair": "crop",
            "headwear": "none",
            "top": "tshirt",
            "bottom": "shorts",
            "shoes": "sneakers",
        },
        "colors": {
            "skin": "#EFC29B",
            "hair": "#3B2314",
            "top": "#FFD23F",
            "bottom": "#1F5BD1",
            "shoes": "#FF6B4A",
            "card": "#FFE9A8",
        },
    },
    "grown_up": {
        "parts": {
            "face_shape": "oval",
            "eyes": "almond",
            "brows": "straight",
            "nose": "round",
            "hair": "side_part",
            "headwear": "none",
            "top": "sweater",
            "bottom": "trousers",
            "shoes": "boots",
        },
        "colors": {
            "skin": "#B9773F",
            "hair": "#2B2B2B",
            "top": "#3FA34D",
            "bottom": "#23305E",
            "shoes": "#8A5A3B",
            "card": "#E6F6DF",
        },
    },
    "robot": {
        "parts": {
            "face_shape": "box",
            "eyes": "round",
            "brows": "straight",
            "headwear": "none",
            "top": "none",
            "bottom": "none",
            "shoes": "none",
        },
        "colors": {"skin": "#9AD0F5", "card": "#DDF0FC"},
    },
    "cat": {
        "parts": {
            "face_shape": "cat",
            "eyes": "almond",
            "brows": "thin",
            "headwear": "none",
            "top": "none",
            "bottom": "none",
            "shoes": "none",
        },
        "colors": {"skin": "#E8954F", "card": "#FFD0C2"},
    },
    "dog": {
        "parts": {
            "face_shape": "dog",
            "eyes": "button",
            "brows": "arched",
            "headwear": "none",
            "top": "none",
            "bottom": "none",
            "shoes": "none",
        },
        "colors": {"skin": "#F3E2C3", "card": "#FFE9A8"},
    },
    "bear": {
        "parts": {
            "face_shape": "bear",
            "eyes": "round",
            "brows": "bushy",
            "headwear": "none",
            "top": "none",
            "bottom": "none",
            "shoes": "none",
        },
        "colors": {"skin": "#8A5A3B", "card": "#E6F6DF"},
    },
}


# ---- assemble ---------------------------------------------------------------------------------------


def build() -> dict:
    face_shapes: dict[str, dict] = {}
    for shape, label in (("round", "Round"), ("oval", "Oval"), ("square", "Square"), ("heart", "Heart")):
        face_shapes[shape] = {"label": label, "body_types": HUMANS, "layers": human_head(shape)}
    for shape, label in (("box", "Box head"), ("dome", "Dome head"), ("screen", "Screen head")):
        option = {"label": label, "body_types": ["robot"], "layers": robot_head(shape)}
        if shape == "screen":
            option["face_ink"] = "#7CF3E0"
        face_shapes[shape] = option
    for species in ANIMALS:
        face_shapes[species] = {
            "label": f"{species.title()} head",
            "body_types": [species],
            "layers": animal_head(species),
        }

    eye_labels = {
        "round": "Round",
        "oval": "Oval",
        "almond": "Almond",
        "sleepy": "Sleepy",
        "sparkle": "Sparkly",
        "button": "Button",
    }
    categories = {
        "face_shape": {"label": "Face", "options": face_shapes},
        "eyes": {
            "label": "Eyes",
            "options": {k: {"label": v, "body_types": ALL, "states": eye_states(k)} for k, v in eye_labels.items()},
        },
        "brows": {
            "label": "Eyebrows",
            "options": {k: {"label": k.title(), "body_types": ALL, "art": v} for k, v in BROWS.items()},
        },
        "nose": {
            "label": "Nose",
            "options": {k: {"label": k.title(), "body_types": HUMANS, "views": v} for k, v in NOSES.items()},
        },
        "hair": {"label": "Hair", "slot": "hair", "options": build_hair()},
        "headwear": {"label": "Hats", "slot": "hat", "options": build_headwear()},
        "top": {"label": "Tops", "slot": "top", "options": build_tops()},
        "bottom": {"label": "Bottoms", "slot": "bottom", "options": build_bottoms()},
        "shoes": {"label": "Shoes", "slot": "shoes", "options": build_shoes()},
    }
    extras = build_extras()
    extras.pop("_none")
    review(categories, extras)

    body_types = {}
    for bt, b in BODIES.items():
        body_types[bt] = {
            "label": b["label"],
            "kind": b["kind"],
            "face_rig": b["rig"],
            "root": [num(b["root"][0]), num(b["root"][1])],
            "head_scale": num(b["hs"]),
            "bones": {view: bone_offsets(b, view) for view in VIEWS},
            "fragments": body_fragments(bt, b),
            "defaults": DEFAULTS[bt],
        }

    return {
        "version": 1,
        "canvas": 200,
        "ink": INK,
        "views": list(VIEWS),
        "palettes": PALETTES,
        "color_slots": COLOR_SLOTS,
        "color_defaults": COLOR_DEFAULTS,
        "bones": BONES,
        "body_types": body_types,
        "categories": categories,
        "extras": extras,
        "expressions": EXPRESSIONS,
        "mouths": {k: {"front": v, "side": v} for k, v in MOUTHS_FRONT.items()},
        "face_rigs": {"human": face_rig(True), "robot": face_rig(False), "animal": face_rig(False, 15.5)},
        "layers": LAYERS,
        "poses": POSES,
        "face_visible": FACE_VISIBLE,
        "head_box": HEAD_BOX,
        "face_cell": {"translate": [100, 112], "scale": 2.55},
    }


# ---- safety review (docs/character-safety.md) ------------------------------------------------
#
# Every option a kid can pick is listed here once a person has checked its art: people stay
# covered, no text, brand names or logos, no weapons (the magic wand is the only hand-held power
# item), and cultural or religious items are drawn and labelled respectfully. A new option is
# written with "reviewed": false until it is added here, and the catalog audit test fails.

REVIEWED: dict[str, set[str]] = {
    "face_shape": {"round", "oval", "square", "heart", "box", "dome", "screen", "cat", "dog", "bear"},
    "eyes": {"round", "oval", "almond", "sleepy", "sparkle", "button"},
    "brows": {"straight", "arched", "bushy", "thin"},
    "nose": {"button", "round", "pointy", "dot"},
    "hair": {
        "none", "crop", "buzz", "spiky", "side_part", "bob", "curly", "afro", "ponytail",
        "two_puffs", "braids", "long_straight", "bun",
    },
    "headwear": {"none", "cap", "beanie", "hijab", "turban", "space_helmet"},
    "top": {"tshirt", "hoodie", "raincoat", "sweater", "jersey", "dress", "dungarees", "superhero", "none"},
    "bottom": {"shorts", "trousers", "jeans", "skirt", "leggings", "cargo", "none"},
    "shoes": {"sneakers", "boots", "sandals", "rain_boots", "none"},
    "extras": {
        "glasses_round", "glasses_square", "glasses_star", "cape", "backpack", "wand",
        "headphones", "freckles", "blush",
    },
}  # fmt: skip
# Cultural and religious items: for every human body, never mixed with silly items at random.
CULTURAL = {("headwear", "hijab"), ("headwear", "turban")}
# Joke items "Surprise me" never pairs with a cultural item.
SILLY = {("extras", "glasses_star")}


def review(categories: dict[str, dict], extras: dict[str, dict]) -> None:
    """Writes "reviewed" and "tags" on every option from the tables above."""
    groups = [(name, info["options"]) for name, info in categories.items()] + [("extras", extras)]
    for group_name, options in groups:
        for option_id, option in options.items():
            option["reviewed"] = option_id in REVIEWED.get(group_name, set())
            option["tags"] = [
                tag for tag, members in (("cultural", CULTURAL), ("silly", SILLY)) if (group_name, option_id) in members
            ]


if __name__ == "__main__":
    catalog = build()
    OUT.write_text(json.dumps(catalog, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {OUT} ({OUT.stat().st_size // 1024} KB)")
