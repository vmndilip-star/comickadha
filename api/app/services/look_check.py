"""The look check (decision 132): after the image check, one vision call compares the builder's
drawing with the painting, to catch a painting that changed who a character is.

The vision call takes a single image, so both go in ONE side-by-side picture: the drawing on the
left, the painting on the right. Characters are described in catalog words and colour values and
named by position, never by name, so no kid-written word reaches Meta. An outage raises
CheckerResting (fails closed).

What fails a picture from day one: the wrong number of characters, an extra character, a missing
head covering, and (for portraits, painted in plain light) a different skin tone. Everything else
it sees (hair, clothes, accessories, and for panels the skin tone under the scene's light and the
props) is only logged until the Phase B measurements show the check judges it reliably.
"""

import io
import logging
from dataclasses import dataclass, field
from typing import Any

from PIL import Image

from app.prompts import render
from app.providers.llm import LLMError, LLMProvider
from app.services.ai_limits import LIMITS
from app.services.painting import CheckerResting, LookVerdict

log = logging.getLogger(__name__)

HALF_HEIGHT = 512
DIVIDER = 8
CREAM = (255, 248, 236)
INK = (26, 26, 26)

CHARACTER_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "skin_tone": {"type": "string", "enum": ["same", "lighter", "darker"]},
        "hair_kept": {"type": "boolean"},
        "head_covering_kept": {"type": "boolean"},
        "clothing_colours_kept": {"type": "boolean"},
        "accessories_kept": {"type": "boolean"},
        "head_x": {"type": "number"},
        "head_y": {"type": "number"},
    },
    "required": [
        "skin_tone",
        "hair_kept",
        "head_covering_kept",
        "clothing_colours_kept",
        "accessories_kept",
        "head_x",
        "head_y",
    ],
    "additionalProperties": False,
}
LOOK_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "characters_in_painting": {"type": "integer"},
        "extra_characters": {"type": "boolean"},
        "characters": {"type": "array", "items": CHARACTER_SCHEMA},
        "props_visible": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["characters_in_painting", "extra_characters", "characters", "props_visible"],
    "additionalProperties": False,
}


@dataclass(frozen=True)
class Expected:
    """Who should be in the painting, left to right: each one's look in catalog words and colour
    values, and whether they wear a head covering (hijab, turban)."""

    looks: list[str]
    head_coverings: list[bool]
    # Portraits are painted in plain light, so a different skin tone fails them; in a panel the
    # scene's light (sunset, night) changes it, so there it is only logged for now.
    skin_tone_fails: bool = True
    props: list[str] = field(default_factory=list)


def side_by_side(left_png: bytes, right_png: bytes, half_height: int = HALF_HEIGHT) -> bytes:
    """Both pictures at the same height on cream, the drawing left and the painting right, with an
    ink divider between them and no text."""
    halves = []
    for png in (left_png, right_png):
        image = Image.open(io.BytesIO(png)).convert("RGBA")
        width = max(1, round(image.width * half_height / image.height))
        flat = Image.new("RGB", image.size, CREAM)
        flat.paste(image, mask=image.getchannel("A"))
        halves.append(flat.resize((width, half_height), Image.Resampling.LANCZOS))
    left, right = halves
    sheet = Image.new("RGB", (left.width + DIVIDER + right.width, half_height), INK)
    sheet.paste(left, (0, 0))
    sheet.paste(right, (left.width + DIVIDER, 0))
    buf = io.BytesIO()
    sheet.save(buf, format="PNG")
    return buf.getvalue()


def prompt_for(expected: Expected) -> str:
    lines = ["Expected characters in the painting, left to right:"]
    for n, (look, covered) in enumerate(zip(expected.looks, expected.head_coverings, strict=True)):
        covering = " They wear a head covering." if covered else ""
        lines.append(f"{n + 1}. {look}.{covering}")
    if expected.props:
        lines.append("Props to look for (use these exact names in props_visible):")
        lines += [f"- {prop}" for prop in expected.props]
    else:
        lines.append("No props to look for: props_visible is an empty list.")
    return "\n".join(lines)


def check_look(
    llm: LLMProvider, reference_png: bytes, painting_png: bytes, expected: Expected
) -> LookVerdict:
    """One vision call on the side-by-side picture; raises CheckerResting if it doesn't answer."""
    limit = LIMITS["look_check"]
    try:
        reply = llm.complete_json(
            render("look_check"),
            prompt_for(expected),
            LOOK_SCHEMA,
            schema_name="look_check",
            image_png=side_by_side(reference_png, painting_png),
            max_tokens=limit.max_tokens,
            timeout=limit.timeout,
        )
        return judge(reply, expected)
    except (LLMError, KeyError, TypeError, ValueError) as error:
        log.warning("look check unavailable: %s", type(error).__name__)
        raise CheckerResting() from error


def judge(reply: dict[str, Any], expected: Expected) -> LookVerdict:
    """Turns the reply into a verdict. Raises KeyError/TypeError/ValueError on a reply that
    doesn't fit the schema (the caller treats that as an outage)."""
    count = int(reply["characters_in_painting"])
    characters = list(reply["characters"])
    hard: list[str] = []
    soft: list[str] = []
    if count != len(expected.looks) or len(characters) != len(expected.looks):
        hard.append(f"{count} characters painted, {len(expected.looks)} expected")
    if bool(reply["extra_characters"]):
        hard.append("an extra character")
    heads: list[tuple[float, float]] = []
    for n, (seen, covered) in enumerate(zip(characters, expected.head_coverings, strict=False)):
        who = f"character {n + 1}"
        if covered and not bool(seen["head_covering_kept"]):
            hard.append(f"{who}: head covering missing")
        tone = str(seen["skin_tone"])
        if tone not in ("same", "lighter", "darker"):
            raise ValueError(tone)
        if tone != "same":
            (hard if expected.skin_tone_fails else soft).append(f"{who}: skin {tone}")
        for key, words in (
            ("hair_kept", "hair changed"),
            ("clothing_colours_kept", "clothing colours changed"),
            ("accessories_kept", "accessories changed"),
        ):
            if not bool(seen[key]):
                soft.append(f"{who}: {words}")
        heads.append((_fraction(seen["head_x"]), _fraction(seen["head_y"])))
    visible = {str(p).strip().lower() for p in reply["props_visible"]}
    soft += [f"prop missing: {p}" for p in expected.props if p.lower() not in visible]
    findings = [f"{f} (hard)" for f in hard] + soft
    return LookVerdict(hard_fail=bool(hard), findings=findings, heads=heads)


def _fraction(value: object) -> float:
    number = float(value)  # type: ignore[arg-type]
    return min(1.0, max(0.0, number))
