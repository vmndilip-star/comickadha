"""Contact sheets for reviewing the avatar art: every pose for every body type, faces and parts.

Run from api/:  uv run python -m app.avatar.preview
Writes PNGs to shared/avatar/preview/ (gitignored).
"""

import io
import sys
import time
from collections.abc import Callable

from PIL import Image, ImageDraw, ImageFont

from app.avatar.catalog import Catalog, catalog_path, load_catalog
from app.avatar.compose import Spec
from app.avatar.render import render_face, render_pose

PAPER = (255, 248, 236)
INK = (26, 26, 26)
RULE = (239, 230, 211)
CARD = (255, 233, 168)

SAMPLES: dict[str, Spec] = {
    "kid": {
        "body_type": "kid",
        "parts": {
            "face_shape": "round",
            "eyes": "sparkle",
            "brows": "arched",
            "nose": "button",
            "hair": "two_puffs",
            "top": "hoodie",
            "bottom": "jeans",
            "shoes": "sneakers",
        },
        "extras": ["backpack", "freckles"],
        "colors": {
            "skin": "#CF8D5B",
            "hair": "#3B2314",
            "top": "#FF6B4A",
            "bottom": "#1F5BD1",
            "shoes": "#FFD23F",
            "backpack": "#3FA34D",
        },
    },
    "grown_up": {
        "body_type": "grown_up",
        "parts": {
            "face_shape": "oval",
            "eyes": "almond",
            "brows": "straight",
            "nose": "round",
            "hair": "bun",
            "top": "sweater",
            "bottom": "trousers",
            "shoes": "boots",
        },
        "extras": ["glasses_round"],
        "colors": {
            "skin": "#F7D5BA",
            "hair": "#EDE3C8",
            "top": "#7A4FC9",
            "bottom": "#23305E",
            "shoes": "#8A5A3B",
        },
    },
    "robot": {
        "body_type": "robot",
        "parts": {"face_shape": "screen", "eyes": "round", "brows": "straight"},
        "extras": ["cape"],
        "colors": {"skin": "#C9CED6", "cape": "#E53935"},
    },
    "cat": {
        "body_type": "cat",
        "parts": {
            "face_shape": "cat",
            "eyes": "almond",
            "brows": "thin",
            "top": "tshirt",
            "bottom": "skirt",
        },
        "extras": ["blush"],
        "colors": {"skin": "#E8954F", "top": "#9AD0F5", "bottom": "#FF7FB0"},
    },
    "dog": {
        "body_type": "dog",
        "parts": {
            "face_shape": "dog",
            "eyes": "button",
            "brows": "arched",
            "top": "jersey",
            "bottom": "shorts",
            "shoes": "sneakers",
            "headwear": "cap",
        },
        "colors": {
            "skin": "#F3E2C3",
            "top": "#1F5BD1",
            "bottom": "#FFFFFF",
            "shoes": "#FF6B4A",
            "hat": "#E53935",
        },
    },
    "bear": {
        "body_type": "bear",
        "parts": {"face_shape": "bear", "eyes": "round", "brows": "bushy", "top": "superhero"},
        "extras": ["cape", "wand"],
        "colors": {"skin": "#8A5A3B", "top": "#3FA34D", "cape": "#FFD23F"},
    },
}


def font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for name in ("arialbd.ttf", "DejaVuSans-Bold.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def png(data: bytes) -> Image.Image:
    return Image.open(io.BytesIO(data)).convert("RGBA")


def grid(
    title: str,
    rows: list[str],
    cols: list[str],
    cell: Callable[[str, str], Image.Image],
    size: int = 150,
    label_w: int = 110,
) -> Image.Image:
    head_h, col_h = 46, 22
    sheet = Image.new(
        "RGB",
        (label_w + size * len(cols) + 10, head_h + col_h + (size + 8) * len(rows) + 10),
        PAPER,
    )
    draw = ImageDraw.Draw(sheet)
    draw.text((12, 10), title, fill=INK, font=font(22))
    small = font(12)
    for c, name in enumerate(cols):
        draw.text((label_w + c * size + 4, head_h + 2), name, fill=INK, font=small)
    for r, row in enumerate(rows):
        y = head_h + col_h + r * (size + 8)
        draw.text((10, y + size // 2 - 8), row, fill=INK, font=font(14))
        for c, col in enumerate(cols):
            x = label_w + c * size
            draw.rounded_rectangle(
                (x + 3, y + 3, x + size - 3, y + size - 3),
                radius=10,
                fill=CARD if (r + c) % 2 == 0 else RULE,
            )
            art = cell(row, col).resize((size - 6, size - 6), Image.Resampling.LANCZOS)
            sheet.paste(art, (x + 3, y + 3), art)
    return sheet


def with_part(base: Spec, category: str, option: str) -> Spec:
    return {**base, "parts": {**base.get("parts", {}), category: option}}


def main() -> None:
    out_dir = catalog_path().parent / "preview"
    out_dir.mkdir(exist_ok=True)
    cat: Catalog = load_catalog()
    started = time.perf_counter()
    poses = list(cat["poses"])
    bodies = list(cat["body_types"])
    expressions = list(cat["expressions"])
    only = set(sys.argv[1:])

    def save(name: str, image: Image.Image) -> None:
        if only and name not in only:
            return
        image.save(out_dir / f"{name}.png")
        print(f"  {name}.png  {image.width}x{image.height}")

    if not only or "poses" in only or "poses_a" in only or "poses_b" in only:
        sheets = {
            "poses_a": poses[:8],
            "poses_b": poses[8:],
        }
        for name, chunk in sheets.items():
            save(
                name,
                grid(
                    f"Poses {name[-1].upper()}",
                    bodies,
                    chunk,
                    lambda row, col: png(render_pose(SAMPLES[row], col, 256, catalog=cat)),
                    size=190,
                ),
            )
        save(
            "poses",
            grid(
                "All 16 poses x 6 body types",
                bodies,
                poses,
                lambda row, col: png(render_pose(SAMPLES[row], col, 256, catalog=cat)),
                size=150,
            ),
        )

    save(
        "faces",
        grid(
            "Faces: 6 expressions x 6 body types",
            bodies,
            expressions,
            lambda row, col: png(render_face(SAMPLES[row], col, 256, catalog=cat)),
            size=170,
        ),
    )

    hair = list(cat["categories"]["hair"]["options"])
    views = ["front", "three_quarter_right", "side_right", "back"]
    kid = SAMPLES["kid"] | {"extras": []}
    save(
        "hair",
        grid(
            "Hair x views (kid)",
            views,
            hair,
            lambda row, col: png(render_pose(with_part(kid, "hair", col), row, 256, catalog=cat)),
            size=150,
        ),
    )

    rows: dict[str, tuple[str, list[str]]] = {
        "tops": ("top", list(cat["categories"]["top"]["options"])),
        "bottoms": ("bottom", list(cat["categories"]["bottom"]["options"])),
        "shoes": ("shoes", list(cat["categories"]["shoes"]["options"])),
        "headwear": ("headwear", list(cat["categories"]["headwear"]["options"])),
    }
    plain = {
        "body_type": "kid",
        "parts": {"hair": "crop"},
        "colors": {"top": "#FFD23F", "bottom": "#1F5BD1", "shoes": "#FF6B4A"},
    }
    for name, (category, options) in rows.items():
        targets = ["kid", "robot"] if category in ("top", "bottom", "shoes") else ["kid", "dog"]
        bodies_for = {t: plain if t == "kid" else {**SAMPLES[t], "extras": []} for t in targets}

        def part_cell(
            row: str, col: str, c: str = category, b: dict[str, Spec] = bodies_for
        ) -> Image.Image:
            body, view = row.split()
            pose = "front" if view == "front" else "three_quarter_right"
            return png(render_pose(with_part(b[body], c, col), pose, 256, catalog=cat))

        rows_for = [f"{t} front" for t in targets] + [f"{t} 3/4" for t in targets]
        save(
            f"parts_{name}",
            grid(f"{name.title()} (front / three-quarter)", rows_for, options, part_cell, size=140),
        )

    face_bits = {
        "eyes": list(cat["categories"]["eyes"]["options"]),
        "brows": list(cat["categories"]["brows"]["options"]),
        "nose": list(cat["categories"]["nose"]["options"]),
        "face_shape": ["round", "oval", "square", "heart", "box", "dome", "screen"],
    }
    for category, options in face_bits.items():

        def cell(row: str, col: str, c: str = category) -> Image.Image:
            base = (
                SAMPLES["robot"]
                if col in ("box", "dome", "screen")
                else {**SAMPLES["kid"], "extras": []}
            )
            spec = with_part(base, c, col)
            if row == "face":
                return png(render_face(spec, "happy", 256, catalog=cat))
            return png(render_pose(spec, row, 256, catalog=cat))

        save(
            f"parts_{category}",
            grid(
                category.replace("_", " ").title(),
                ["face", "three_quarter_right", "side_right"],
                options,
                cell,
                size=140,
            ),
        )

    extras = list(cat["extras"])

    def extra_cell(row: str, col: str) -> Image.Image:
        spec = {**SAMPLES["kid"], "extras": [col]}
        return png(render_pose(spec, row, 256, catalog=cat))

    save(
        "parts_extras",
        grid("Extras", ["front", "three_quarter_right", "back"], extras, extra_cell, size=140),
    )
    print(f"Done in {time.perf_counter() - started:.1f}s -> {out_dir}")


if __name__ == "__main__":
    main()
