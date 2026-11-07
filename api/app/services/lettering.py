"""Bubble lettering: the bundled fonts, and fitting text into a bubble.

Fonts live in api/assets/fonts (Bangers and Nunito, SIL Open Font License), so the server can
letter final.png and the PDF offline. Fitting steps the font size down to a minimum; if the text
still doesn't fit, the bubble grows taller. The web app follows the same rule with its own fonts.
"""

from dataclasses import dataclass
from functools import lru_cache

from PIL import ImageFont

from app.config import API_DIR

FONTS = API_DIR / "assets" / "fonts"
SIZES = (26, 23, 20, 18)  # px for an 800-px-wide panel, largest first; 18 is the smallest
PAD = 12
LINE = 1.18


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
    pad = PAD * scale
    for step, size in enumerate(SIZES):
        px = round(size * scale)
        lines = wrap(shown, font(kind, px), width - 2 * pad)
        needed = len(lines) * px * LINE + 2 * pad
        if needed <= height or step == len(SIZES) - 1:
            return Fit(px, lines, max(height, needed))
    raise AssertionError("unreachable")
