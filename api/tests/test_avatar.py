"""The avatar parts library: catalog shape, every pose for every body type, faces, rig maths."""

import importlib.util
import io
import json
import re
from collections.abc import Iterator
from typing import Any

import pytest
from PIL import Image

from app.avatar.catalog import catalog_path, load_catalog
from app.avatar.compose import compose_pose, resolve
from app.avatar.preview import SAMPLES
from app.avatar.render import render_face, render_pose
from app.avatar.rig import apply, face_cell_head_box, head_box, ops_to_matrix, transform_ops
from app.schemas.common import EXPRESSIONS, POSES

CAT = load_catalog()
BODY_TYPES = list(CAT["body_types"])
VIEWS = set(CAT["views"])
VIEW_POSES = ("front", "three_quarter_right", "side_right", "back")


def alpha(png: bytes) -> Image.Image:
    return Image.open(io.BytesIO(png)).convert("RGBA").getchannel("A")


def coverage(mask: Image.Image) -> float:
    data = mask.tobytes()
    return sum(1 for a in data if a) / len(data)


def numbers(value: Any) -> Iterator[int | float]:
    if isinstance(value, dict):
        for v in value.values():
            yield from numbers(v)
    elif isinstance(value, list):
        for v in value:
            yield from numbers(v)
    elif isinstance(value, int | float) and not isinstance(value, bool):
        yield value


def strings(value: Any) -> Iterator[str]:
    if isinstance(value, dict):
        for v in value.values():
            yield from strings(v)
    elif isinstance(value, list):
        for v in value:
            yield from strings(v)
    elif isinstance(value, str):
        yield value


def test_catalog_matches_its_generator() -> None:
    spec = importlib.util.spec_from_file_location(
        "build_catalog", catalog_path().parent / "build_catalog.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    built = json.loads(json.dumps(module.build()))
    assert built == CAT, "catalog.json is stale: run shared/avatar/build_catalog.py"


def test_web_golden_file_is_current() -> None:
    """web/src/avatar tests compare the TypeScript twin against this file."""
    from app.avatar import golden

    assert golden.GOLDEN_PATH.read_text(encoding="utf-8") == golden.render(golden.build()), (
        "shared/avatar/golden.json is stale: run uv run python -m app.avatar.golden"
    )


def test_poses_and_expressions_match_the_sheet_contract() -> None:
    assert list(CAT["poses"]) == list(POSES)
    assert list(CAT["expressions"]) == list(EXPRESSIONS)
    assert CAT["face_visible"] == [p for p in POSES if p not in ("back", "side_left", "side_right")]


def test_numbers_print_the_same_in_python_and_javascript() -> None:
    # Whole numbers are ints and floats have at most 2 decimals, so str() in Python and
    # String() in JavaScript give the same text: both composers emit identical SVG.
    for x in numbers(CAT):
        if isinstance(x, float):
            assert not x.is_integer() and round(x, 2) == x, x
    for svg in strings(CAT):
        assert not re.search(r"\d\.\d{3}|\d\.0(?!\d)|e-\d", svg), svg[:80]


def test_every_part_is_drawn_in_all_four_views() -> None:
    def check(layers: dict[str, dict[str, str]], where: str) -> None:
        for layer, by_view in layers.items():
            assert set(by_view) == VIEWS, f"{where}.{layer}"

    assert set(CAT["layers"]) == VIEWS
    for body_type, body in CAT["body_types"].items():
        assert set(body["bones"]) == VIEWS
        assert set(body["bones"]["front"]) == set(CAT["bones"])
        check(body["fragments"], body_type)
    for rig in CAT["face_rigs"].values():
        assert set(rig) == VIEWS
    groups = [*(c["options"].items() for c in CAT["categories"].values()), CAT["extras"].items()]
    for options in groups:
        for option_id, option in options:
            if "layers" in option:
                check(option["layers"], option_id)
            if "by_body" in option:
                assert set(option["by_body"]) == set(BODY_TYPES), option_id
                for body_type, layers in option["by_body"].items():
                    check(layers, f"{option_id}.{body_type}")


def test_body_type_defaults_are_allowed_options() -> None:
    for body_type, body in CAT["body_types"].items():
        for category, choice in body["defaults"]["parts"].items():
            assert body_type in CAT["categories"][category]["options"][choice]["body_types"], (
                body_type,
                category,
            )
        assert resolve({"body_type": body_type}).parts == body["defaults"]["parts"]


def test_unknown_or_disallowed_parts_fall_back_to_defaults() -> None:
    r = resolve(
        {
            "body_type": "robot",
            "parts": {"hair": "afro", "top": "no_such_top"},
            "extras": ["glasses_round", "glasses_star"],
        }
    )
    assert "hair" not in r.parts
    assert r.parts["top"] == CAT["body_types"]["robot"]["defaults"]["parts"]["top"]
    assert r.extras == ["glasses_round"]  # one pair of glasses at a time


def test_every_option_composes_on_every_body_type_it_allows() -> None:
    for category_id, category in CAT["categories"].items():
        for option_id, option in category["options"].items():
            for body_type in option["body_types"]:
                spec = {"body_type": body_type, "parts": {category_id: option_id}}
                assert resolve(spec).parts[category_id] == option_id
                for pose in VIEW_POSES:
                    assert "{{" not in compose_pose(spec, pose), (
                        category_id,
                        option_id,
                        body_type,
                        pose,
                    )
    for extra_id, extra in CAT["extras"].items():
        for body_type in extra["body_types"]:
            spec = {"body_type": body_type, "extras": [extra_id]}
            for pose in VIEW_POSES:
                assert "{{" not in compose_pose(spec, pose), (extra_id, body_type, pose)


@pytest.mark.parametrize("body_type", BODY_TYPES)
def test_every_pose_renders_inside_the_cell(body_type: str) -> None:
    for spec in (SAMPLES[body_type], {"body_type": body_type}):
        for pose in POSES:
            mask = alpha(render_pose(spec, pose, 128))
            assert 0.04 < coverage(mask) < 0.6, pose
            box = mask.getbbox()
            assert box and box[0] > 0 and box[1] > 0 and box[2] < 128 and box[3] < 128, (pose, box)


@pytest.mark.parametrize("body_type", BODY_TYPES)
def test_every_expression_renders_as_a_face(body_type: str) -> None:
    images = [render_face(SAMPLES[body_type], expression, 96) for expression in EXPRESSIONS]
    assert len(set(images)) == len(EXPRESSIONS)  # each one looks different
    for png in images:
        assert coverage(alpha(png)) > 0.3


def test_head_boxes_follow_the_rig() -> None:
    # The head box maths must agree with what the renderer draws: render at 200 px (1 px = 1 unit)
    # and check that a point on the cheek is skin-coloured (hair from behind) in every pose.
    kid = {
        "body_type": "kid",
        "parts": {"hair": "buzz"},
        "colors": {"skin": "#EFC29B", "hair": "#3B2314"},
    }
    skin, hair = (0xEF, 0xC2, 0x9B), (0x3B, 0x23, 0x14)
    for pose in POSES:
        x, y, w, h = head_box("kid", pose)
        assert x >= 0 and x + w <= 200 and y >= 0 and y + h <= 200, pose
        data = CAT["poses"][pose]
        # Points clear of eyes, brows, ears and the hair's edge.
        probe = {"front": (0, 4), "back": (0, -10)}.get(data["view"], (4, 4))
        px, py = apply(ops_to_matrix(transform_ops(CAT, "kid", data, "head")), *probe)
        if data["mirror"]:
            px = 200 - px
        image = Image.open(io.BytesIO(render_pose(kid, pose, 200))).convert("RGB")
        assert image.getpixel((round(px), round(py))) == (hair if pose == "back" else skin), pose
        assert x < px < x + w and y < py < y + h, pose
    fx, fy, fw, fh = face_cell_head_box()
    assert fx >= 0 and fx + fw <= 200 and fy >= 0 and fy + fh <= 200
