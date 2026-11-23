"""The compositor: panel art (background + characters), final.png (art + bubbles) and covers.

- art.png: the scene's locked place image cover-cropped to 4:3 (or its tint), then each character
  rendered straight from its pinned spec with resvg, in the planned pose and expression, placed
  by services/stage.py. No bubbles: the Reader draws those as HTML so text edits are instant.
- final.png: art.png with the bubbles lettered in (talk, think, shout, narrator), for thumbnails,
  covers and the PDF. Made lazily, when the bubbles or the art changed (`final_hash`).
- Everything is drawn at 2x (1600 x 1200) and saved without timestamps, so the same inputs give a
  byte-identical PNG.
"""

import hashlib
import io
import json
import math
from typing import Any

from PIL import Image, ImageDraw, ImageOps

from app.avatar.render import render_pose
from app.services import imaging, lettering, stage

SCALE = 2
W, H = stage.PANEL_W * SCALE, stage.PANEL_H * SCALE
THUMB = (400, 300)
INK = (26, 26, 26, 255)
WHITE = (255, 255, 255, 255)
NARRATOR_FILL = (255, 233, 168, 255)  # sun-tint
STROKE = 3 * SCALE


def _hex(color: str) -> tuple[int, int, int, int]:
    value = color.lstrip("#")
    return (int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16), 255)


def background(image_png: bytes | None, tint: str) -> Image.Image:
    """The place image cover-cropped to the panel's 4:3, or a flat tint."""
    if image_png:
        with Image.open(io.BytesIO(image_png)) as source:
            return ImageOps.fit(source.convert("RGBA"), (W, H), method=Image.Resampling.LANCZOS)
    return Image.new("RGBA", (W, H), _hex(tint))


def render_art(
    characters: list[dict[str, Any]],
    specs: dict[str, dict[str, Any]],
    place_png: bytes | None,
    tint: str,
    bubbles: list[dict[str, Any]],
) -> tuple[bytes, bytes]:
    """(art.png, thumb.png) for one panel. Deterministic for the same inputs."""
    canvas = background(place_png, tint)
    placements = stage.place(characters, specs)
    for p in stage.z_order(placements, stage.first_speaker(bubbles)):
        x, y, w, h = p.cell
        size = round(h * H)
        cell = Image.open(io.BytesIO(render_pose(p.spec, p.pose, size, p.expression))).convert(
            "RGBA"
        )
        if p.mirror:
            cell = ImageOps.mirror(cell)
        canvas.alpha_composite(cell, (round(x * W), round(y * H)))
    art = canvas.convert("RGB")
    thumb = art.resize(THUMB, Image.Resampling.LANCZOS)
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


def bake_final(art_png: bytes, bubbles: list[dict[str, Any]]) -> bytes:
    """art.png with every bubble drawn and lettered (Pillow), for thumbnails, covers and PDF."""
    with Image.open(io.BytesIO(art_png)) as source:
        canvas = source.convert("RGBA")
    draw = ImageDraw.Draw(canvas)
    for bubble in bubbles:
        box = bubble.get("box")
        if not box:
            continue
        _draw_bubble(draw, bubble, box, bubble.get("tail"))
    return imaging.to_png(canvas.convert("RGB"))


def _px(box: list[float] | tuple[float, ...]) -> tuple[float, float, float, float]:
    x, y, w, h = box
    return (x * W, y * H, w * W, h * H)


def _tail(
    draw: ImageDraw.ImageDraw, rect: tuple[float, float, float, float], tip: tuple[float, float]
) -> None:
    """A wedge from the bubble's nearest edge (bottom or top) to the tip. Drawn after the bubble:
    the white fill hides the bubble's outline where they join, then the two sides are inked."""
    x, y, w, h = rect
    tx, ty = tip[0] * W, tip[1] * H
    below = ty > y + h / 2
    base_y = (y + h - STROKE * 1.5) if below else (y + STROKE * 1.5)
    base_x = min(max(tx, x + w * 0.2), x + w * 0.8)
    half = min(w * 0.08, 22 * SCALE)
    left, right = (base_x - half, base_y), (base_x + half, base_y)
    draw.polygon([left, (tx, ty), right], fill=WHITE)
    draw.line([left, (tx, ty), right], fill=INK, width=STROKE, joint="curve")


def _draw_bubble(draw: ImageDraw.ImageDraw, bubble: dict[str, Any], box: Any, tail: Any) -> None:
    kind = str(bubble.get("type", "talk"))
    x, y, w, h = _px(box)
    text = str(bubble.get("text", ""))
    fitted = lettering.fit(text, kind, w, h, SCALE)
    h = max(h, fitted.height)
    rect = (x, y, w, h)
    if kind == "narrator":
        draw.rectangle((x, y, x + w, y + h), fill=NARRATOR_FILL, outline=INK, width=STROKE)
    elif kind == "think":
        _cloud(draw, rect)
        if tail:
            _think_trail(draw, rect, tail)
    elif kind == "shout":
        draw.polygon(_spikes(rect), fill=WHITE, outline=INK, width=STROKE)
        if tail:
            _tail(draw, rect, tail)
    else:
        draw.rounded_rectangle(
            (x, y, x + w, y + h),
            radius=min(h / 2, 28 * SCALE),
            fill=WHITE,
            outline=INK,
            width=STROKE,
        )
        if tail:
            _tail(draw, rect, tail)
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


def _cloud(draw: ImageDraw.ImageDraw, rect: tuple[float, float, float, float]) -> None:
    """A think bubble: a soft cloud of circles around an ellipse."""
    x, y, w, h = rect
    cx, cy = x + w / 2, y + h / 2
    bumps = 12
    r = min(w, h) * 0.22
    for i in range(bumps):
        a = 2 * math.pi * i / bumps
        bx, by = cx + (w / 2 - r * 0.6) * math.cos(a), cy + (h / 2 - r * 0.6) * math.sin(a)
        draw.ellipse((bx - r, by - r, bx + r, by + r), fill=WHITE, outline=INK, width=STROKE)
    draw.ellipse((x + r * 0.4, y + r * 0.4, x + w - r * 0.4, y + h - r * 0.4), fill=WHITE)


def _think_trail(
    draw: ImageDraw.ImageDraw, rect: tuple[float, float, float, float], tip: tuple[float, float]
) -> None:
    """Small trailing circles from the cloud toward the thinker's head."""
    x, y, w, h = rect
    sx, sy = x + w / 2, y + h
    tx, ty = tip[0] * W, tip[1] * H
    for i, t in enumerate((0.35, 0.6, 0.82)):
        r = (11 - i * 3) * SCALE
        px, py = sx + (tx - sx) * t, sy + (ty - sy) * t
        draw.ellipse((px - r, py - r, px + r, py + r), fill=WHITE, outline=INK, width=STROKE)


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
    """Panel 1's final.png with the title across the bottom in Bangers."""
    with Image.open(io.BytesIO(final_png)) as source:
        canvas = source.convert("RGBA")
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
