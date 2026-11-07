"""Speech-bubble boxes and tails, in fractions of the panel (0-1).

box = (x, y, w, h); tail = the tip (x, y). Narrator captions run across the top with no tail.
Speech, think and shout bubbles stack below them, each above its speaker, and the stack then
slides down to just above the highest head so tails stay short. The tail tip points inside the
speaker's head as drawn (services/stage.py), so it follows poses, positions and mirroring.
Text fits by stepping the font down, then growing the bubble (services/lettering.py).
A bubble the kid moved or resized (`fixed`) keeps its box; only its tail is re-aimed.
"""

from typing import Any

from app.services import lettering, stage

MARGIN = 0.03
GAP = 0.02
SPEECH_W = 0.42
NARRATOR_W = 0.94
MIN_H = 0.12
FALLBACK_HEAD_Y = 0.42
TAIL_MIN = 0.07  # the gap left between the bubble stack and the highest head


def heads(
    characters: list[dict[str, Any]], specs: dict[str, dict[str, Any]] | None
) -> tuple[dict[str, tuple[float, float]], float]:
    """Each character's tail target (0-1), and the top of the highest head."""
    if specs is not None:
        placements = stage.place(characters, specs)
        top = min((p.head[1] for p in placements), default=FALLBACK_HEAD_Y)
        return {p.id: p.head_target for p in placements}, top
    targets = {
        c["id"]: (stage.POSITION_X.get(str(c.get("position")), 0.5), FALLBACK_HEAD_Y)
        for c in characters
    }
    return targets, FALLBACK_HEAD_Y - 0.06


def fitted_height(text: str, kind: str, width: float) -> float:
    """The height (0-1 of the panel) a bubble of this width needs for its text."""
    w_px = width * stage.PANEL_W
    result = lettering.fit(text, kind, w_px, MIN_H * stage.PANEL_H)
    return round(result.height / stage.PANEL_H, 4)


def layout(
    bubbles: list[dict[str, Any]],
    characters: list[dict[str, Any]],
    specs: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """The bubbles with `box` and `tail` filled in (new dicts; the input is not changed).
    `specs` are the characters' pinned looks; without them, heads are estimated."""
    targets, head_top = heads(characters, specs)
    out: list[dict[str, Any]] = []
    narrators = [b for b in bubbles if _is_narrator(b)]
    y = MARGIN
    placed: dict[str, dict[str, Any]] = {}
    for bubble in narrators:  # captions go across the top first
        if bubble.get("fixed") and bubble.get("box"):
            placed[str(bubble["id"])] = {**bubble, "tail": None}
            continue
        h = fitted_height(str(bubble.get("text", "")), "narrator", NARRATOR_W)
        placed[str(bubble["id"])] = {
            **bubble,
            "box": (MARGIN, round(y, 4), NARRATOR_W, h),
            "tail": None,
        }
        y += h + GAP
    stack: list[str] = []
    for bubble in bubbles:
        if _is_narrator(bubble):
            continue
        tip = targets.get(str(bubble.get("speaker", "")), (0.5, FALLBACK_HEAD_Y))
        if bubble.get("fixed") and bubble.get("box"):
            placed[str(bubble["id"])] = {**bubble, "tail": tip}
            continue
        kind = str(bubble.get("type", "talk"))
        w = SPEECH_W
        h = fitted_height(str(bubble.get("text", "")), kind, w)
        x = min(max(tip[0] - w / 2, MARGIN), 1 - MARGIN - w)
        placed[str(bubble["id"])] = {
            **bubble,
            "box": (round(x, 4), round(y, 4), w, h),
            "tail": tip,
        }
        stack.append(str(bubble["id"]))
        y += h + GAP
    shift = head_top - TAIL_MIN - (y - GAP)  # slide the speech stack down toward the heads
    if stack and shift > 0:
        for key in stack:
            bx, by, bw, bh = placed[key]["box"]
            placed[key]["box"] = (bx, round(by + shift, 4), bw, bh)
    for bubble in bubbles:  # keep the kid's order
        out.append(placed[str(bubble["id"])])
    return out


def _is_narrator(bubble: dict[str, Any]) -> bool:
    return bubble.get("type") == "narrator" or bubble.get("speaker") == "narrator"
