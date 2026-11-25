"""The compositor: panel art (background, props, characters), final.png (art + bubbles), covers.

- art.png: the scene's locked place image cover-cropped to the panel's shape (or its tint), then
  everything services/stage.py placed, back to front: props on the ground, each character
  rendered straight from its pinned spec with resvg in the planned pose and expression, with what
  they hold (a hugged scarecrow goes just behind them), and a sleeping character's "Zzz". No
  bubbles: the Reader draws those as HTML so text edits are instant.
- final.png: art.png with the bubbles lettered in (talk, think, shout, narrator), for thumbnails,
  covers and the PDF. Made lazily, when the bubbles or the art changed (`final_hash`).
- A normal panel is drawn at 2x (1600 x 1200); wide and splash panels at 1.25x (2050 x 750 and
  2050 x 2350). Saved without timestamps, so the same inputs give a byte-identical PNG.
"""

import hashlib
import io
import json
import math
from dataclasses import dataclass
from typing import Any

from PIL import Image, ImageDraw, ImageOps

from app.avatar.render import render_pose
from app.props import images as prop_images
from app.services import imaging, lettering, stage

SCALE = 2  # a normal panel's pixels per unit
SCALES = {"normal": 2.0, "wide": 1.25, "splash": 1.25}
W, H = stage.PANEL_W * SCALE, stage.PANEL_H * SCALE
THUMB = (400, 300)
THUMB_H = {"normal": 300, "wide": 300, "splash": 460}
INK = (26, 26, 26, 255)
WHITE = (255, 255, 255, 255)
NARRATOR_FILL = (255, 233, 168, 255)  # sun-tint
STROKE = 3 * SCALE
# Where a cover-crop keeps the place picture: wide panels keep its lower part, where the ground is.
CENTERING = {"normal": (0.5, 0.5), "wide": (0.5, 0.78), "splash": (0.5, 0.5)}


def _hex(color: str) -> tuple[int, int, int, int]:
    value = color.lstrip("#")
    return (int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16), 255)


def canvas_size(size: str | None) -> tuple[int, int]:
    frame = stage.frame_for(size)
    scale = SCALES.get(frame.size, SCALE)
    return round(frame.w * scale), round(frame.h * scale)


def background(image_png: bytes | None, tint: str, size: str | None = None) -> Image.Image:
    """The place image cover-cropped to the panel's shape, or a flat tint."""
    dims = canvas_size(size)
    if image_png:
        with Image.open(io.BytesIO(image_png)) as source:
            return ImageOps.fit(
                source.convert("RGBA"),
                dims,
                method=Image.Resampling.LANCZOS,
                centering=CENTERING.get(stage.frame_for(size).size, (0.5, 0.5)),
            )
    return Image.new("RGBA", dims, _hex(tint))


def _prop_image(pp: stage.PropPlacement, width: float, height: float) -> Image.Image:
    _x, _y, w, h = pp.box
    png = prop_images.render_state(pp.id, pp.state, round(w * width), round(h * height))
    image = Image.open(io.BytesIO(png)).convert("RGBA")
    return ImageOps.mirror(image) if pp.flip else image


def _paste_prop(canvas: Image.Image, pp: stage.PropPlacement) -> None:
    width, height = canvas.size
    image = _prop_image(pp, width, height)
    x, y, _w, _h = pp.box
    if not pp.rotate:
        canvas.alpha_composite(image, (round(x * width), round(y * height)))
        return
    # Turned about its anchor: put the anchor in the middle of a big enough square, turn, paste.
    ax, ay = pp.origin[0] * image.width, pp.origin[1] * image.height
    side = 2 * math.ceil(math.hypot(max(ax, image.width - ax), max(ay, image.height - ay))) + 2
    square = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    square.alpha_composite(image, (round(side / 2 - ax), round(side / 2 - ay)))
    turned = square.rotate(-pp.rotate, resample=Image.Resampling.BICUBIC)
    anchor = (x * width + ax, y * height + ay)
    canvas.alpha_composite(turned, (round(anchor[0] - side / 2), round(anchor[1] - side / 2)))


def _zzz(canvas: Image.Image, effect: stage.Effect) -> None:
    """A sleeping character's "Zzz": Bangers, inked with a white edge, tilted."""
    width, height = canvas.size
    x, y, w, h = effect.box
    bw, bh = max(8, round(w * width)), max(8, round(h * height))
    layer = Image.new("RGBA", (bw * 2, bh * 2), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    size = max(10, round(bh * 0.95))
    edge = max(2, size // 9)
    left = bw // 2
    for i, (letter, grow) in enumerate((("Z", 0.62), ("z", 0.8), ("z", 1.0))):
        f = lettering.font("shout", max(8, round(size * grow)))
        top = bh // 2 + round(bh * (0.38 - i * 0.19))
        draw.text((left, top), letter, font=f, fill=INK, stroke_width=edge, stroke_fill=WHITE)
        left += round(f.getlength(letter) + edge)
    turned = layer.rotate(10, resample=Image.Resampling.BICUBIC)
    canvas.alpha_composite(turned, (round(x * width) - bw // 2, round(y * height) - bh // 2))


def render_art(
    characters: list[dict[str, Any]],
    specs: dict[str, dict[str, Any]],
    place_png: bytes | None,
    tint: str,
    bubbles: list[dict[str, Any]],
    props: list[dict[str, Any]] | None = None,
    size: str | None = None,
) -> tuple[bytes, bytes]:
    """(art.png, thumb.png) for one panel. Deterministic for the same inputs."""
    canvas = background(place_png, tint, size)
    width, height = canvas.size
    laid = stage.layout(characters, specs, props, size, bubbles)
    for kind, index in laid.order:
        if kind == "prop":
            _paste_prop(canvas, laid.props[index])
            continue
        p = laid.characters[index]
        x, y, _w, h = p.cell
        side = round(h * height)
        cell = Image.open(io.BytesIO(render_pose(p.spec, p.pose, side, p.expression))).convert(
            "RGBA"
        )
        if p.mirror:
            cell = ImageOps.mirror(cell)
        canvas.alpha_composite(cell, (round(x * width), round(y * height)))
    for effect in laid.effects:
        _zzz(canvas, effect)
    art = canvas.convert("RGB")
    thumb_h = THUMB_H.get(laid.frame.size, THUMB[1])
    thumb = art.resize((round(thumb_h * width / height), thumb_h), Image.Resampling.LANCZOS)
    return imaging.to_png(art), imaging.to_png(thumb)


# ---- final.png: bubbles lettered in --------------------------------------------------------


# Bumped when the lettering itself changes (2: shout words fit inside the burst, Phase 7), so every
# final.png baked before re-letters itself the next time it is asked for.
LETTERING_VERSION = 2


def final_hash(art_key: str | None, art_version: int | None, bubbles: list[dict[str, Any]]) -> str:
    """What final.png is made from; when this changes, final.png is stale."""
    keep = [
        {k: b.get(k) for k in ("id", "speaker", "type", "text", "box", "tail")} for b in bubbles
    ]
    blob = json.dumps([art_key, art_version, keep, LETTERING_VERSION], sort_keys=True)
    return hashlib.sha256(blob.encode()).hexdigest()


@dataclass(frozen=True)
class Sheet:
    """The picture bubbles are lettered onto: its size in pixels and pixels per unit."""

    w: float
    h: float
    scale: float

    @property
    def stroke(self) -> int:
        return round(3 * self.scale)


def bake_final(art_png: bytes, bubbles: list[dict[str, Any]], size: str | None = None) -> bytes:
    """art.png with every bubble drawn and lettered (Pillow), for thumbnails, covers and PDF."""
    with Image.open(io.BytesIO(art_png)) as source:
        canvas = source.convert("RGBA")
    sheet = Sheet(canvas.width, canvas.height, canvas.width / stage.frame_for(size).w)
    draw = ImageDraw.Draw(canvas)
    for bubble in bubbles:
        box = bubble.get("box")
        if not box:
            continue
        _draw_bubble(draw, sheet, bubble, box, bubble.get("tail"))
    return imaging.to_png(canvas.convert("RGB"))


def _px(sheet: Sheet, box: list[float] | tuple[float, ...]) -> tuple[float, float, float, float]:
    x, y, w, h = box
    return (x * sheet.w, y * sheet.h, w * sheet.w, h * sheet.h)


def _tail(
    draw: ImageDraw.ImageDraw,
    sheet: Sheet,
    rect: tuple[float, float, float, float],
    tip: tuple[float, float],
) -> None:
    """A wedge from the bubble's nearest edge (bottom or top) to the tip. Drawn after the bubble:
    the white fill hides the bubble's outline where they join, then the two sides are inked."""
    x, y, w, h = rect
    tx, ty = tip[0] * sheet.w, tip[1] * sheet.h
    below = ty > y + h / 2
    base_y = (y + h - sheet.stroke * 1.5) if below else (y + sheet.stroke * 1.5)
    base_x = min(max(tx, x + w * 0.2), x + w * 0.8)
    half = min(w * 0.08, 22 * sheet.scale)
    left, right = (base_x - half, base_y), (base_x + half, base_y)
    draw.polygon([left, (tx, ty), right], fill=WHITE)
    draw.line([left, (tx, ty), right], fill=INK, width=sheet.stroke, joint="curve")


def _draw_bubble(
    draw: ImageDraw.ImageDraw, sheet: Sheet, bubble: dict[str, Any], box: Any, tail: Any
) -> None:
    kind = str(bubble.get("type", "talk"))
    x, y, w, h = _px(sheet, box)
    text = str(bubble.get("text", ""))
    fitted = lettering.fit(text, kind, w, h, sheet.scale)
    h = max(h, fitted.height)
    rect = (x, y, w, h)
    if kind == "narrator":
        draw.rectangle((x, y, x + w, y + h), fill=NARRATOR_FILL, outline=INK, width=sheet.stroke)
    elif kind == "think":
        _cloud(draw, sheet, rect)
        if tail:
            _think_trail(draw, sheet, rect, tail)
    elif kind == "shout":
        draw.polygon(_spikes(rect), fill=WHITE, outline=INK, width=sheet.stroke)
        if tail:
            _tail(draw, sheet, rect, tail)
    else:
        draw.rounded_rectangle(
            (x, y, x + w, y + h),
            radius=min(h / 2, 28 * sheet.scale),
            fill=WHITE,
            outline=INK,
            width=sheet.stroke,
        )
        if tail:
            _tail(draw, sheet, rect, tail)
    _letter(draw, rect, fitted, kind)


def _letter(
    draw: ImageDraw.ImageDraw,
    rect: tuple[float, float, float, float],
    fitted: lettering.Fit,
    kind: str,
) -> None:
    x, y, w, h = rect
    f = lettering.font(kind, fitted.size)
    line_h = fitted.size * lettering.LINE
    top = y + (h - line_h * len(fitted.lines)) / 2
    for i, line in enumerate(fitted.lines):
        lw = f.getlength(line)
        draw.text((x + (w - lw) / 2, top + i * line_h), line, font=f, fill=INK)


def _cloud(
    draw: ImageDraw.ImageDraw, sheet: Sheet, rect: tuple[float, float, float, float]
) -> None:
    """A think bubble: a soft cloud of circles around an ellipse."""
    x, y, w, h = rect
    cx, cy = x + w / 2, y + h / 2
    bumps = 12
    r = min(w, h) * 0.22
    for i in range(bumps):
        a = 2 * math.pi * i / bumps
        bx, by = cx + (w / 2 - r * 0.6) * math.cos(a), cy + (h / 2 - r * 0.6) * math.sin(a)
        draw.ellipse((bx - r, by - r, bx + r, by + r), fill=WHITE, outline=INK, width=sheet.stroke)
    draw.ellipse((x + r * 0.4, y + r * 0.4, x + w - r * 0.4, y + h - r * 0.4), fill=WHITE)


def _think_trail(
    draw: ImageDraw.ImageDraw,
    sheet: Sheet,
    rect: tuple[float, float, float, float],
    tip: tuple[float, float],
) -> None:
    """Small trailing circles from the cloud toward the thinker's head."""
    x, y, w, h = rect
    sx, sy = x + w / 2, y + h
    tx, ty = tip[0] * sheet.w, tip[1] * sheet.h
    for i, t in enumerate((0.35, 0.6, 0.82)):
        r = (11 - i * 3) * sheet.scale
        px, py = sx + (tx - sx) * t, sy + (ty - sy) * t
        draw.ellipse((px - r, py - r, px + r, py + r), fill=WHITE, outline=INK, width=sheet.stroke)


def _spikes(rect: tuple[float, float, float, float]) -> list[tuple[float, float]]:
    """A shout bubble: a starburst around the box."""
    x, y, w, h = rect
    cx, cy = x + w / 2, y + h / 2
    points: list[tuple[float, float]] = []
    count = 18
    for i in range(count * 2):
        a = math.pi * i / count
        sx, sy = lettering.BURST_TIPS if i % 2 == 0 else lettering.BURST_VALLEYS
        points.append((cx + w / 2 * sx * math.cos(a), cy + h / 2 * sy * math.sin(a)))
    return points


# ---- the cover -----------------------------------------------------------------------------


def cover(final_png: bytes, title: str) -> bytes:
    """Panel 1's final.png with the title across the bottom in Bangers (a wide or splash first
    panel is cropped to a normal panel's shape first)."""
    with Image.open(io.BytesIO(final_png)) as source:
        canvas = source.convert("RGBA")
    if canvas.size != (W, H):
        canvas = ImageOps.fit(canvas, (W, H), method=Image.Resampling.LANCZOS)
    draw = ImageDraw.Draw(canvas)
    band_h = H // 5
    draw.rectangle((0, H - band_h, W, H), fill=(255, 210, 63, 255), outline=INK, width=STROKE * 2)
    size = 96 * SCALE // 2
    f = lettering.font("title", size)
    shown = title.strip() or "My Comic"
    while f.getlength(shown) > W * 0.9 and size > 28:
        size -= 6
        f = lettering.font("title", size)
    tw = f.getlength(shown)
    draw.text(((W - tw) / 2, H - band_h + (band_h - size) / 2), shown, font=f, fill=INK)
    return imaging.to_png(canvas.convert("RGB"))
