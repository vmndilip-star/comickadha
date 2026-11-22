"""The 2D puppet rig: bone transforms for a pose, as SVG text and as matrices (for head boxes).

Each bone hangs off its parent (see catalog["bones"]); "root" is the hips. A bone's transform is
the chain root -> ... -> bone of translate(offset) rotate(angle), plus the body's head scale on
the head bone. web/src/avatar/rig.ts emits the same SVG text.
"""

import math
from typing import Any

from app.avatar.catalog import Catalog, load_catalog

Op = tuple[str, float, float]  # ("translate", x, y) | ("rotate", deg, 0) | ("scale", s, 0)
Matrix = tuple[float, float, float, float, float, float]  # SVG matrix(a b c d e f)
Box = tuple[float, float, float, float]  # x, y, w, h

CANVAS = 200


def fmt(x: float) -> str:
    """Numbers as JavaScript's String() prints them (the catalog keeps them short)."""
    return str(int(x)) if float(x).is_integer() else repr(float(x))


def transform_ops(catalog: Catalog, body_type: str, pose: dict[str, Any], bone: str) -> list[Op]:
    body = catalog["body_types"][body_type]
    offsets = body["bones"][pose["view"]]
    angles: dict[str, float] = pose["angles"]
    ops: list[Op] = [("translate", body["root"][0], body["root"][1])]
    px, py = pose["root"]
    if px or py:
        ops.append(("translate", px, py))
    if angles.get("root"):
        ops.append(("rotate", angles["root"], 0))

    chain: list[str] = []
    while bone != "root":
        chain.append(bone)
        bone = catalog["bones"][bone]
    for name in reversed(chain):
        ox, oy = offsets[name]
        if ox or oy:
            ops.append(("translate", ox, oy))
        if angles.get(name):
            ops.append(("rotate", angles[name], 0))
        if name == "head" and body["head_scale"] != 1:
            ops.append(("scale", body["head_scale"], 0))
    return ops


def ops_to_svg(ops: list[Op]) -> str:
    out = []
    for kind, a, b in ops:
        if kind == "translate":
            out.append(f"translate({fmt(a)} {fmt(b)})")
        elif kind == "rotate":
            out.append(f"rotate({fmt(a)})")
        else:
            out.append(f"scale({fmt(a)})")
    return " ".join(out)


def ops_to_matrix(ops: list[Op]) -> Matrix:
    m: Matrix = (1, 0, 0, 1, 0, 0)
    for kind, a, b in ops:
        if kind == "translate":
            step: Matrix = (1, 0, 0, 1, a, b)
        elif kind == "rotate":
            c, s = math.cos(math.radians(a)), math.sin(math.radians(a))
            step = (c, s, -s, c, 0, 0)
        else:
            step = (a, 0, 0, a, 0, 0)
        m = _multiply(m, step)
    return m


def _multiply(m: Matrix, n: Matrix) -> Matrix:
    a, b, c, d, e, f = m
    a2, b2, c2, d2, e2, f2 = n
    return (
        a * a2 + c * b2,
        b * a2 + d * b2,
        a * c2 + c * d2,
        b * c2 + d * d2,
        a * e2 + c * f2 + e,
        b * e2 + d * f2 + f,
    )


def apply(m: Matrix, x: float, y: float) -> tuple[float, float]:
    a, b, c, d, e, f = m
    return a * x + c * y + e, b * x + d * y + f


def head_box(body_type: str, pose_name: str, catalog: Catalog | None = None) -> Box:
    """Where the head box (catalog["head_box"], head space) lands in a pose cell, in canvas units.

    Builder manifests store it as each pose's head box; panels and bubbles use it via stage.py.
    """
    cat = catalog or load_catalog()
    pose = cat["poses"][pose_name]
    m = ops_to_matrix(transform_ops(cat, body_type, pose, "head"))
    hx, hy, hw, hh = cat["head_box"]
    corners = [
        apply(m, x, y) for x, y in ((hx, hy), (hx + hw, hy), (hx, hy + hh), (hx + hw, hy + hh))
    ]
    xs = [p[0] for p in corners]
    ys = [p[1] for p in corners]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    if pose["mirror"]:
        x0, x1 = CANVAS - x1, CANVAS - x0
    return (x0, y0, x1 - x0, y1 - y0)


def face_cell_head_box(catalog: Catalog | None = None) -> Box:
    """The head box inside a face cell (front view, drawn at catalog["face_cell"])."""
    cat = catalog or load_catalog()
    tx, ty = cat["face_cell"]["translate"]
    s = cat["face_cell"]["scale"]
    hx, hy, hw, hh = cat["head_box"]
    return (tx + hx * s, ty + hy * s, hw * s, hh * s)
