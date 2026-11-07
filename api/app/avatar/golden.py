"""Golden files for the web twin: what the Python avatar code produces, for Vitest to match.

`uv run python -m app.avatar.golden` writes shared/avatar/golden.json. It holds the SHA-256 of the
SVG for every part option on every body type it fits, every pose, every expression and a few rich
characters; a couple of full SVGs (to diff by eye); the head box of every pose for every body type;
and normalize() results, so specs made in the browser pass the API's checks. A test fails when the
file is stale, so run this after changing the catalog or the avatar code.
"""

import hashlib
import json
from pathlib import Path
from typing import Any

from app.avatar import rig
from app.avatar import spec as avatar_spec
from app.avatar.catalog import Catalog, catalog_path, load_catalog
from app.avatar.compose import compose_face, compose_pose, svg_document

Spec = dict[str, Any]

RICH: list[Spec] = [
    {
        "body_type": "kid",
        "parts": {"hair": "two_puffs", "headwear": "cap", "top": "superhero", "shoes": "boots"},
        "colors": {"hair": "#FF7FB0", "hat": "#1F5BD1", "top": "#E53935", "cape": "#FFD23F"},
        "extras": ["glasses_star", "cape", "wand", "freckles"],
    },
    {
        "body_type": "grown_up",
        "parts": {"hair": "bun", "headwear": "hijab", "top": "dress", "bottom": "leggings"},
        "colors": {"skin": "#5E3720", "hat": "#7A4FC9", "top": "#3FA34D"},
        "extras": ["backpack", "headphones", "glasses_square", "blush"],
    },
    {
        "body_type": "robot",
        "parts": {"face_shape": "screen", "eyes": "sparkle", "top": "hoodie", "headwear": "beanie"},
        "colors": {"skin": "#FF8A6B", "top": "#23305E"},
        "extras": ["headphones", "cape"],
    },
    {
        "body_type": "dog",
        "parts": {"headwear": "space_helmet", "shoes": "rain_boots"},
        "colors": {"skin": "#3B3B3F", "shoes": "#FFD23F"},
        "extras": ["backpack", "wand"],
    },
]

# Messy input for normalize(): bad parts, off-palette colours, duplicate and ill-fitting extras.
NORMALIZE_INPUTS: list[Spec] = [
    {},
    {"body_type": "cat"},
    {
        "body_type": "robot",
        "parts": {"hair": "bob", "face_shape": "nope", "top": "hoodie"},
        "colors": {"skin": "#0000FF", "top": "#FF0001", "bad": "#FFFFFF", "hair": "red"},
        "extras": ["freckles", "cape", "cape", "jetpack"],
    },
    {
        "body_type": "kid",
        "parts": {"hair": "afro", "nose": "pointy", "shoes": "none"},
        "colors": {"skin": "#f2c29b", "card": "#DDF0FC"},
        "extras": ["glasses_round", "glasses_star", "wand"],
        "personality": {"traits": ["brave", "kind"], "catchphrase": "Hi!"},
        "role": "hero",
    },
    {"body_type": "bear", "parts": {"headwear": "turban", "top": "none"}, "extras": ["blush"]},
    {"body_type": "grown_up", "colors": {"hair": "#123456", "top": "#ffffff"}},
]

GOLDEN_PATH = catalog_path().parent / "golden.json"


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _cases(cat: Catalog) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []

    def pose(spec: Spec, name: str, expression: str | None = None) -> None:
        svg = compose_pose(spec, name, expression, cat)
        case = {"kind": "pose", "spec": spec, "pose": name, "expression": expression}
        cases.append(case | {"sha256": sha(svg), "length": len(svg)})

    def face(spec: Spec, expression: str) -> None:
        svg = compose_face(spec, expression, cat)
        case = {"kind": "face", "spec": spec, "expression": expression}
        cases.append(case | {"sha256": sha(svg), "length": len(svg)})

    for body_type in cat["body_types"]:
        base: Spec = {"body_type": body_type}
        for name in cat["poses"]:
            pose(base, name)
        for expression in cat["expressions"]:
            face(base, expression)
            pose(base, "three_quarter_right", expression)
        for category, info in cat["categories"].items():
            for option_id, option in info["options"].items():
                if body_type in option["body_types"]:
                    pose({"body_type": body_type, "parts": {category: option_id}}, "front")
        for extra_id, extra in cat["extras"].items():
            if body_type in extra["body_types"]:
                pose({"body_type": body_type, "extras": [extra_id]}, "three_quarter_right")
    for spec in RICH:
        for name in cat["poses"]:
            pose(spec, name)
        face(spec, "laughing")
    return cases


def build() -> dict[str, Any]:
    cat = load_catalog()
    return {
        "catalog_version": cat["version"],
        "cases": _cases(cat),
        "samples": [
            {"kind": "pose", "spec": RICH[0], "pose": "wave", "svg": compose_pose(RICH[0], "wave")},
            {
                "kind": "face",
                "spec": RICH[1],
                "expression": "surprised",
                "svg": compose_face(RICH[1], "surprised"),
            },
        ],
        "document": svg_document("<g/>", 64),
        "head_boxes": {
            body_type: {name: list(rig.head_box(body_type, name, cat)) for name in cat["poses"]}
            for body_type in cat["body_types"]
        },
        "face_cell_head_box": list(rig.face_cell_head_box(cat)),
        "normalize": [
            {"input": spec, "output": avatar_spec.normalize(spec, cat)} for spec in NORMALIZE_INPUTS
        ],
    }


def render(data: dict[str, Any]) -> str:
    return json.dumps(data, indent=1, ensure_ascii=False) + "\n"


def main(path: Path = GOLDEN_PATH) -> None:
    text = render(build())
    path.write_text(text, encoding="utf-8", newline="\n")
    print(f"Wrote {path} ({len(text) // 1024} KB).")


if __name__ == "__main__":
    main()
