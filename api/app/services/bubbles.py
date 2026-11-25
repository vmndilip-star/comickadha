"""Speech-bubble boxes and tails, in fractions of the panel (0-1).

box = (x, y, w, h); tail = the tip (x, y). Narrator captions run across the top with no tail.
Speech, think and shout bubbles stack below them, each above its speaker, and the stack then
slides down to just above the highest head so tails stay short. The tail tip points inside the
speaker's head as drawn (services/stage.py), so it follows poses, positions and mirroring.
Text fits by stepping the font down, then growing the bubble (services/lettering.py).
A bubble the kid moved or resized (`fixed`) keeps its box; only its tail is re-aimed.

Sizes are in units (a normal panel is 800 x 600), so a bubble is the same size in a wide or splash
panel as in a normal one; for a normal panel the fractions are the ones it always had.
"""

from typing import Any

from app.services import lettering, stage

MARGIN_X, MARGIN_Y = 24.0, 18.0  # units (0.03 of a normal panel)
GAP = 12.0  # units between stacked bubbles
SPEECH_W = 336.0  # units (0.42 of a normal panel)
NARRATOR_W = 0.94  # captions run across the panel, whatever its size
MIN_H = 72.0  # units (0.12 of a normal panel)
FALLBACK_HEAD_Y = 0.42
TAIL_MIN = 42.0  # units: the gap left between the bubble stack and the highest head


def heads(
    characters: list[dict[str, Any]],
    specs: dict[str, dict[str, Any]] | None,
    size: str | None = None,
) -> tuple[dict[str, tuple[float, float]], float]:
    """Each character's tail target (0-1), and the top of the highest head."""
    if specs is not None:
        placements = stage.place(characters, specs, size)
        top = min((p.head[1] for p in placements), default=FALLBACK_HEAD_Y)
        return {p.id: p.head_target for p in placements}, top
    spots = {**stage.SLOT_X, **stage.POSITION_X}
    targets = {
        c["id"]: (spots.get(str(c.get("position")), 0.5), FALLBACK_HEAD_Y) for c in characters
    }
    return targets, FALLBACK_HEAD_Y - 0.06


def fitted_height(text: str, kind: str, width: float, frame: stage.Frame = stage.NORMAL) -> float:
    """The height (0-1 of the panel) a bubble of this width (0-1) needs for its text."""
    result = lettering.fit(text, kind, width * frame.w, MIN_H)
    return round(result.height / frame.h, 4)


def layout(
    bubbles: list[dict[str, Any]],
    characters: list[dict[str, Any]],
    specs: dict[str, dict[str, Any]] | None = None,
    size: str | None = None,
) -> list[dict[str, Any]]:
    """The bubbles with `box` and `tail` filled in (new dicts; the input is not changed).
    `specs` are the characters' pinned looks; without them, heads are estimated."""
    frame = stage.frame_for(size)
    margin_x, margin_y = MARGIN_X / frame.w, MARGIN_Y / frame.h
    gap, tail_min = GAP / frame.h, TAIL_MIN / frame.h
    targets, head_top = heads(characters, specs, size)
    out: list[dict[str, Any]] = []
    narrators = [b for b in bubbles if _is_narrator(b)]
    y = margin_y
    placed: dict[str, dict[str, Any]] = {}
    for bubble in narrators:  # captions go across the top first
        if bubble.get("fixed") and bubble.get("box"):
            placed[str(bubble["id"])] = {**bubble, "tail": None}
            continue
        h = fitted_height(str(bubble.get("text", "")), "narrator", NARRATOR_W, frame)
        placed[str(bubble["id"])] = {
            **bubble,
            "box": (margin_x, round(y, 4), NARRATOR_W, h),
            "tail": None,
        }
        y += h + gap
    stack: list[str] = []
    for bubble in bubbles:
        if _is_narrator(bubble):
            continue
        tip = targets.get(str(bubble.get("speaker", "")), (0.5, FALLBACK_HEAD_Y))
        if bubble.get("fixed") and bubble.get("box"):
            placed[str(bubble["id"])] = {**bubble, "tail": tip}
            continue
        kind = str(bubble.get("type", "talk"))
        w = round(SPEECH_W / frame.w, 4)
        h = fitted_height(str(bubble.get("text", "")), kind, w, frame)
        # A shout's spikes reach past its box (lettering.BURST_TIPS): keep them inside the panel.
        edge = margin_x + (w * (lettering.BURST_TIPS[0] - 1) / 2 if kind == "shout" else 0)
        x = min(max(tip[0] - w / 2, edge), 1 - edge - w)
        placed[str(bubble["id"])] = {
            **bubble,
            "box": (round(x, 4), round(y, 4), w, h),
            "tail": tip,
        }
        stack.append(str(bubble["id"]))
        y += h + gap
    shift = head_top - tail_min - (y - gap)  # slide the speech stack down toward the heads
    if stack and shift > 0:
        for key in stack:
            bx, by, bw, bh = placed[key]["box"]
            placed[key]["box"] = (bx, round(by + shift, 4), bw, bh)
    for bubble in bubbles:  # keep the kid's order
        out.append(placed[str(bubble["id"])])
    return out


def _is_narrator(bubble: dict[str, Any]) -> bool:
    return bubble.get("type") == "narrator" or bubble.get("speaker") == "narrator"
