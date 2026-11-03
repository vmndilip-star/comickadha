"""Composes avatar SVG from an avatar spec and the shared catalog.

A spec picks a body type, one option per part category, some extras and palette colours:

    {"body_type": "kid", "parts": {"hair": "bob", ...}, "extras": ["glasses_round"],
     "colors": {"skin": "#EFC29B", "hair": "#3B2314", ...}}

Missing parts and colours fall back to the body type's defaults. web/src/avatar/compose.ts is the
twin of this file and must produce the same SVG text (golden-file tests check it).
"""

import re
from dataclasses import dataclass
from typing import Any

from app.avatar.catalog import Catalog, load_catalog
from app.avatar.rig import fmt, ops_to_svg, transform_ops

Spec = dict[str, Any]
PLACEHOLDER = re.compile(r"\{\{(\w+)\}\}")
LIMB_SLOTS = {"arm_upper": "top", "arm_lower": "top", "leg_upper": "bottom", "leg_lower": "bottom"}


@dataclass(frozen=True)
class Resolved:
    body_type: str
    parts: dict[str, str]
    extras: list[str]
    colors: dict[str, str]  # placeholder name -> hex


def resolve(spec: Spec, catalog: Catalog | None = None) -> Resolved:
    cat = catalog or load_catalog()
    requested = spec.get("body_type")
    body_type = str(requested) if requested in cat["body_types"] else "kid"
    body = cat["body_types"][body_type]

    parts: dict[str, str] = {}
    for category, info in cat["categories"].items():
        for choice in (
            spec.get("parts", {}).get(category),
            body["defaults"]["parts"].get(category),
        ):
            option = info["options"].get(choice) if choice else None
            if option and body_type in option["body_types"]:
                parts[category] = choice
                break

    extras: list[str] = []
    groups: set[str] = set()
    for extra_id in spec.get("extras", []):
        extra = cat["extras"].get(extra_id)
        if not extra or body_type not in extra["body_types"] or extra_id in extras:
            continue
        group = extra.get("group")
        if group:
            if group in groups:
                continue
            groups.add(group)
        extras.append(extra_id)

    colors: dict[str, str] = {}
    for slot, info in cat["color_slots"].items():
        palette_id = info.get("palette") or info["palette_by_body"][body_type]
        wanted = (
            spec.get("colors", {}).get(slot)
            or body["defaults"]["colors"].get(slot)
            or cat["color_defaults"][slot]
        ).upper()
        found = next((e for e in cat["palettes"][palette_id] if e["hex"] == wanted), None)
        colors[slot] = wanted
        colors[f"{slot}_shade"] = found["shade"] if found else wanted
        colors[f"{slot}_light"] = found["light"] if found else wanted

    face = cat["categories"]["face_shape"]["options"][parts["face_shape"]]
    colors["face_ink"] = face.get("face_ink", cat["ink"])
    for limb, garment in LIMB_SLOTS.items():
        option = cat["categories"][garment]["options"].get(parts.get(garment, ""))
        colors[limb] = colors[garment] if option and limb in option["coverage"] else colors["skin"]
    return Resolved(body_type, parts, extras, colors)


def compose_pose(
    spec: Spec, pose_name: str, expression: str | None = None, catalog: Catalog | None = None
) -> str:
    """The SVG (a <g> in the 200 x 200 canvas) for one pose cell."""
    cat = catalog or load_catalog()
    r = resolve(spec, cat)
    pose = cat["poses"][pose_name]
    view = pose["view"]
    expr = expression or pose.get("expression") or "happy"

    out: list[str] = []
    for layer in cat["layers"][view]:
        if layer["kind"] == "pose":
            for extra in pose.get("extras", []):
                if extra["layer"] == layer["layer"]:
                    out.append(
                        _group(extra["svg"], transform_ops(cat, r.body_type, pose, extra["bone"]))
                    )
            continue
        art = _layer_art(cat, r, layer, view, expr)
        if art:
            out.append(_group(art, transform_ops(cat, r.body_type, pose, layer["bone"])))
    inner = "".join(out)
    if pose["mirror"]:
        inner = f'<g transform="translate(200 0) scale(-1 1)">{inner}</g>'
    return _fill(inner, r.colors)


def compose_face(spec: Spec, expression: str, catalog: Catalog | None = None) -> str:
    """The SVG for one face cell: the front-view head, large and centred, with an expression."""
    cat = catalog or load_catalog()
    r = resolve(spec, cat)
    cell = cat["face_cell"]
    out = [
        _layer_art(cat, r, layer, "front", expression)
        for layer in cat["layers"]["front"]
        if layer["bone"] == "head"
    ]
    inner = "".join(out)
    tx, ty = cell["translate"]
    transform = f"translate({fmt(tx)} {fmt(ty)}) scale({fmt(cell['scale'])})"
    return _fill(f'<g transform="{transform}">{inner}</g>', r.colors)


def svg_document(inner: str, size: int = 256) -> str:
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200" '
        f'width="{size}" height="{size}">{inner}</svg>'
    )


def _group(art: str, ops: list[tuple[str, float, float]]) -> str:
    return f'<g transform="{ops_to_svg(ops)}">{art}</g>'


def _fill(svg: str, colors: dict[str, str]) -> str:
    return PLACEHOLDER.sub(lambda m: colors[m.group(1)], svg)


def _layer_art(cat: Catalog, r: Resolved, layer: dict[str, str], view: str, expression: str) -> str:
    kind = layer["kind"]
    if kind == "body":
        return str(cat["body_types"][r.body_type]["fragments"][layer["part"]][view])
    if kind == "face":
        return _face(cat, r, view, expression)
    if kind == "part":
        category = layer["category"]
        choice = r.parts.get(category)
        if choice is None or f"{category}.{layer['layer']}" in _hidden(cat, r):
            return ""
        option = cat["categories"][category]["options"][choice]
        layers = option["by_body"][r.body_type] if "by_body" in option else option["layers"]
        return str(layers.get(layer["layer"], {}).get(view, ""))
    if kind == "extra":
        extra_id = layer.get("extra")
        if extra_id is None:  # a group such as glasses: whichever one the spec picked
            extra_id = next(
                (e for e in r.extras if cat["extras"][e].get("group") == layer["group"]), None
            )
        if extra_id is None or extra_id not in r.extras:
            return ""
        extra = cat["extras"][extra_id]
        layers = extra["by_body"][r.body_type] if "by_body" in extra else extra["layers"]
        return str(layers.get(layer["layer"], {}).get(view, ""))
    return ""


def _hidden(cat: Catalog, r: Resolved) -> list[str]:
    headwear = r.parts.get("headwear")
    if not headwear:
        return []
    hides: list[str] = cat["categories"]["headwear"]["options"][headwear].get("hides", [])
    return hides


def _face(cat: Catalog, r: Resolved, view: str, expression: str) -> str:
    body = cat["body_types"][r.body_type]
    expr = cat["expressions"][expression]
    categories = cat["categories"]
    eye = categories["eyes"]["options"][r.parts["eyes"]]["states"][expr["eyes"]]
    brow = categories["brows"]["options"][r.parts["brows"]]["art"]
    nose_choice = r.parts.get("nose")
    nose = categories["nose"]["options"][nose_choice]["views"] if nose_choice else None
    mouth = cat["mouths"][expr["mouth"]]["front"]

    out = []
    for item in cat["face_rigs"][body["face_rig"]][view]:
        feature = item["feature"]
        transform = f"translate({fmt(item['at'][0])} {fmt(item['at'][1])})"
        if "scale" in item:
            transform += f" scale({fmt(item['scale'][0])} {fmt(item['scale'][1])})"
        if feature == "eye":
            art = eye
        elif feature == "brow":
            tilt = expr["brows"][item["side"]]
            if tilt["dy"]:
                transform += f" translate(0 {fmt(tilt['dy'])})"
            if tilt["angle"]:
                transform += f" rotate({fmt(tilt['angle'])})"
            art = brow
        elif feature == "nose":
            if nose is None:
                continue
            art = nose["front" if view == "front" else "side"]
        else:
            art = mouth
        out.append(f'<g transform="{transform}">{art}</g>')
    return "".join(out)
