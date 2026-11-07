"""Default speech-bubble boxes and tails, from where the characters stand.

Coordinates are fractions of the panel (0-1): box = (x, y, w, h), tail = the tip (x, y). The
model never outputs coordinates; this lays every bubble out. Narrator captions run across the
top with no tail; speech bubbles stack below, each above its speaker, with the tail pointing
down towards the speaker's head.
"""

import math
from typing import Any

POSITION_X = {"left": 0.22, "center": 0.5, "right": 0.78}
HEAD_Y = 0.58  # where a standing character's head is, as a fraction of the panel height
MARGIN = 0.03
GAP = 0.025
CHARS_PER_LINE = 22


def _height(text: str, width: float) -> float:
    per_line = max(10, int(CHARS_PER_LINE * width / 0.42))
    lines = max(1, math.ceil(len(text) / per_line))
    return round(min(0.32, 0.07 + 0.055 * lines), 3)


def layout(bubbles: list[dict[str, Any]], characters: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The bubbles with `box` and `tail` filled in (new dicts; the input is not changed)."""
    where = {c["id"]: POSITION_X.get(str(c.get("position")), 0.5) for c in characters}
    out: list[dict[str, Any]] = []
    y = MARGIN
    for bubble in bubbles:
        if bubble.get("type") == "narrator" or bubble.get("speaker") == "narrator":
            h = _height(str(bubble.get("text", "")), 0.94)
            out.append({**bubble, "box": (MARGIN, round(y, 3), 0.94, h), "tail": None})
            y += h + GAP
            continue
        x_speaker = where.get(bubble.get("speaker", ""), 0.5)
        w = 0.42
        h = _height(str(bubble.get("text", "")), w)
        x = min(max(x_speaker - w / 2, MARGIN), 1 - MARGIN - w)
        tail = (round(x_speaker, 3), HEAD_Y)
        out.append({**bubble, "box": (round(x, 3), round(y, 3), w, h), "tail": tail})
        y += h + GAP
    return out
