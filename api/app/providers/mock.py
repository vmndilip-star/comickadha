"""Offline image provider: simple, recognisable placeholder art so the app runs with no API keys.

It reads the same place prompt a real model gets (its Place and Palette lines), paints a simple
scene in the place's tint, and is deterministic for a given prompt, size and seed. Any other prompt
gets a plain card with the prompt's first line.
"""

import io
import random
import re
import time
from dataclasses import dataclass, field

from PIL import Image, ImageDraw, ImageFont

from app.services import imaging

INK = (26, 26, 26)
WHITE = (255, 255, 255)

RGB = tuple[int, int, int]
Point = tuple[float, float]


def hex_rgb(value: str | None, fallback: RGB) -> RGB:
    m = re.fullmatch(r"#?([0-9a-fA-F]{6})", (value or "").strip())
    if not m:
        return fallback
    n = int(m.group(1), 16)
    return (n >> 16) & 255, (n >> 8) & 255, n & 255


def shade(color: RGB, factor: float) -> RGB:
    """factor < 1 darkens, > 1 lightens towards white."""
    if factor <= 1:
        return (int(color[0] * factor), int(color[1] * factor), int(color[2] * factor))
    t = factor - 1
    return tuple(int(c + (255 - c) * t) for c in color)  # type: ignore[return-value]


# ---- prompt parsing -----------------------------------------------------------------------------


@dataclass
class Request:
    palette: dict[str, str] = field(default_factory=dict)
    place: str | None = None
    time: str | None = None  # "sunset" or "night": the same place at that time of day


def _line(prompt: str, label: str) -> str | None:
    m = re.search(rf"^{label}:\s*(.+)$", prompt, re.MULTILINE)
    return m.group(1).strip() if m else None


def parse(prompt: str) -> Request:
    palette_line = _line(prompt, "Palette") or ""
    palette = dict(
        kv.split("=", 1) for kv in (p.strip() for p in palette_line.split(";")) if "=" in kv
    )
    time = (_line(prompt, "Time of day") or "").split(" ")[0].strip(".,:").lower() or None
    return Request(palette=palette, place=_line(prompt, "Place"), time=time)


# ---- drawing ------------------------------------------------------------------------------------


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    return ImageFont.load_default(size=size)


def _label(draw: ImageDraw.ImageDraw, center: Point, text: str, size: int) -> None:
    font = _font(size)
    left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
    w, h = right - left, bottom - top
    x, y = center[0] - w / 2, center[1] - h / 2
    pad = max(3, size // 3)
    draw.rounded_rectangle(
        (x - pad, y - pad, x + w + pad, y + h + pad), radius=pad, fill=WHITE, outline=INK, width=2
    )
    draw.text((x - left, y - top), text, fill=INK, font=font)


def _png(image: Image.Image) -> bytes:
    buf = io.BytesIO()
    image.save(buf, format="PNG", compress_level=3)
    return buf.getvalue()


class MockImageProvider:
    """Placeholder art for places (and a plain card for anything else)."""

    name = "mock"

    def __init__(self, delay_seconds: float = 0.0) -> None:
        self.delay_seconds = delay_seconds

    def generate(
        self,
        prompt: str,
        size: tuple[int, int],
        seed: int,
        reference_images: list[bytes] | None = None,
    ) -> bytes:
        if self.delay_seconds:
            time.sleep(self.delay_seconds)  # pretend to be a slow image API, so progress is visible
        req = parse(prompt)
        if req.place:
            image = self._place(req, size, random.Random(seed))
            return _png(imaging.time_tint(image, req.time) if req.time else image)
        return _png(self._card(prompt, size))

    def _place(self, req: Request, size: tuple[int, int], rng: random.Random) -> Image.Image:
        width, height = size
        tint = hex_rgb(req.palette.get("tint"), (183, 228, 167))
        dark = sum(tint) / 3 < 90
        horizon = int(height * 0.62)
        image = Image.new("RGB", size, shade(tint, 1.35) if not dark else tint)
        draw = ImageDraw.Draw(image)
        draw.rectangle((0, horizon, width, height), fill=shade(tint, 0.8))
        draw.line((0, horizon, width, horizon), fill=INK, width=5)
        for _ in range(4 if not dark else 18):
            x, y = rng.uniform(0.05, 0.95) * width, rng.uniform(0.05, 0.5) * height
            if dark:
                r = rng.uniform(3, 7)
                draw.ellipse((x - r, y - r, x + r, y + r), fill=(255, 210, 63))
            else:
                w = rng.uniform(70, 150)
                draw.ellipse(
                    (x - w / 2, y - w / 5, x + w / 2, y + w / 5), fill=WHITE, outline=INK, width=3
                )
        for _ in range(3):
            x = rng.uniform(0.05, 0.85) * width
            w, h = rng.uniform(80, 180), rng.uniform(40, 110)
            draw.rounded_rectangle(
                (x, horizon - h, x + w, horizon + 8),
                radius=18,
                fill=shade(tint, 0.65),
                outline=INK,
                width=4,
            )
        draw.rectangle((0, 0, width - 1, height - 1), outline=INK, width=6)
        _label(draw, (width * 0.2, 40), (req.place or "Place")[:32], 26)
        _label(draw, (width - 60, 36), "MOCK", 18)
        return image

    def _card(self, prompt: str, size: tuple[int, int]) -> Image.Image:
        image = Image.new("RGB", size, (255, 248, 236))
        draw = ImageDraw.Draw(image)
        draw.rectangle((0, 0, size[0] - 1, size[1] - 1), outline=INK, width=6)
        _label(
            draw, (size[0] / 2, size[1] / 2), prompt.splitlines()[0][:40] if prompt else "MOCK", 24
        )
        return image
