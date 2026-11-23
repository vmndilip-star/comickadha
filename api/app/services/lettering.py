"""Bubble lettering: the bundled fonts, and fitting text into a bubble.

Fonts live in api/assets/fonts (Bangers and Nunito, SIL Open Font License), so the server can
letter final.png and the PDF offline. Fitting steps the font size down to a minimum; if the text
still doesn't fit, the bubble grows taller. The web app follows the same rule with its own fonts.
"""

import math
from dataclasses import dataclass
from functools import lru_cache

from PIL import ImageFont

from app.config import API_DIR

FONTS = API_DIR / "assets" / "fonts"
SIZES = (26, 23, 20, 18)  # px for an 800-px-wide panel, largest first; 18 is the smallest
PAD = 12
LINE = 1.18

# The shout starburst, the same shape as the Reader's (web/src/lib/bubbles.ts): its spike tips and
# valleys as multiples of the bubble's half-width and half-height (valleys are 41/50 of the tips).
BURST_TIPS = (1.16, 1.44)
BURST_VALLEYS = (round(1.16 * 0.82, 4), round(1.44 * 0.82, 4))
# Shout words fit in the largest rectangle inside the valleys (an ellipse: 1/sqrt 2 of its axes),
# with a 5% margin, as a share of the bubble box. If they don't fit at the smallest size, the burst
# grows taller instead of the words spilling over the spikes.
SHOUT_TEXT_W = round(BURST_VALLEYS[0] / math.sqrt(2) * 0.95, 4)
SHOUT_TEXT_H = round(BURST_VALLEYS[1] / math.sqrt(2) * 0.95, 4)


@lru_cache(maxsize=64)
def font(kind: str, px: int) -> ImageFont.FreeTypeFont:
    """Bangers for shouts and titles; Nunito (heavy) for everything else."""
    if kind in ("shout", "title"):
        return ImageFont.truetype(str(FONTS / "Bangers-Regular.ttf"), px)
    f = ImageFont.truetype(str(FONTS / "Nunito-Variable.ttf"), px)
    f.set_variation_by_axes([700 if kind == "narrator" else 800])
    return f


def text_width(text: str, f: ImageFont.FreeTypeFont) -> float:
    return f.getlength(text)


def wrap(text: str, f: ImageFont.FreeTypeFont, width: float) -> list[str]:
    """Greedy word wrap; a word too long for a line gets a line of its own."""
    lines: list[str] = []
    line = ""
    for word in text.split():
        candidate = f"{line} {word}".strip()
        if line and text_width(candidate, f) > width:
            lines.append(line)
            line = word
        else:
            line = candidate
    if line:
        lines.append(line)
    return lines or [""]


@dataclass(frozen=True)
class Fit:
    size: int  # font size in px
    lines: list[str]
    height: float  # the bubble height needed, in px (at least the height asked for)


def fit(text: str, kind: str, width: float, height: float, scale: float = 1.0) -> Fit:
    """The biggest size whose wrapped text fits width x height; at the smallest size the
    bubble grows taller instead. Sizes and padding are multiplied by `scale` (2 for 2x art)."""
    shown = text.upper() if kind == "shout" else text
    if kind == "shout":
        return _fit_shout(shown, width, height, scale)
    pad = PAD * scale
    for step, size in enumerate(SIZES):
        px = round(size * scale)
        lines = wrap(shown, font(kind, px), width - 2 * pad)
        needed = len(lines) * px * LINE + 2 * pad
        if needed <= height or step == len(SIZES) - 1:
            return Fit(px, lines, max(height, needed))
    raise AssertionError("unreachable")


def _fit_shout(shown: str, width: float, height: float, scale: float) -> Fit:
    """Shouts: the words go in the box inside the burst's valleys (SHOUT_TEXT_W x SHOUT_TEXT_H of
    the bubble). At the smallest size the burst grows taller until they fit."""
    room_w, room_h = width * SHOUT_TEXT_W, height * SHOUT_TEXT_H
    for step, size in enumerate(SIZES):
        px = round(size * scale)
        lines = wrap(shown, font("shout", px), room_w)
        text_h = len(lines) * px * LINE
        if text_h <= room_h or step == len(SIZES) - 1:
            return Fit(px, lines, max(height, text_h / SHOUT_TEXT_H))
    raise AssertionError("unreachable")
