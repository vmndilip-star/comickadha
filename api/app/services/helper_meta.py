"""The builder helper on Meta's model API: prompts, and JSON schemas built from the parts catalog.

Every part, colour, extra and trait is an enum of real catalog ids, so the model can only pick
things the builder can draw. Colours are offered by name (palette ids such as "pow_blue") and turned
into hex afterwards. The orchestrator (builder_helper.py) checks every result again.
"""

from typing import Any

from app.avatar.catalog import Catalog, load_catalog
from app.avatar.spec import palette
from app.prompts import render
from app.providers.llm import LLMProvider
from app.services.helper_offline import TRAITS

Raw = dict[str, Any]


def catalog_brief(cat: Catalog | None = None) -> str:
    """The parts library as compact text for the system prompt."""
    cat = cat or load_catalog()
    lines = [
        "Body types: " + ", ".join(f"{k} ({v['label']})" for k, v in cat["body_types"].items())
    ]
    lines.append("Parts (id = label [body types that can use it]):")
    for category, info in cat["categories"].items():
        options = "; ".join(
            f"{oid} = {o['label']}"
            + (
                ""
                if len(o["body_types"]) == len(cat["body_types"])
                else f" [{', '.join(o['body_types'])}]"
            )
            for oid, o in info["options"].items()
        )
        lines.append(f"- {category}: {options}")
    lines.append("Colours (id = name):")
    for slot, info in cat["color_slots"].items():
        if "palette_by_body" in info:
            by_palette: dict[str, list[str]] = {}
            for body, palette_id in info["palette_by_body"].items():
                by_palette.setdefault(palette_id, []).append(body)
            for palette_id, bodies in by_palette.items():
                entries = ", ".join(
                    f"{e['id']} = {e['label']}" for e in cat["palettes"][palette_id]
                )
                lines.append(f"- {slot} for {'/'.join(bodies)}: {entries}")
        else:
            entries = ", ".join(
                f"{e['id']} = {e['label']}" for e in cat["palettes"][info["palette"]]
            )
            lines.append(f"- {slot}: {entries}")
    extras = "; ".join(
        f"{eid} = {e['label']}" + (" (only one pair of glasses)" if e.get("group") else "")
        for eid, e in cat["extras"].items()
    )
    lines.append(f"Extras: {extras}")
    lines.append("Personality traits (pick up to 3): " + ", ".join(TRAITS))
    return "\n".join(lines)


def colour_ids(slot: str, cat: Catalog) -> list[str]:
    info = cat["color_slots"][slot]
    palette_ids = (
        list(dict.fromkeys(info["palette_by_body"].values()))
        if "palette_by_body" in info
        else [info["palette"]]
    )
    ids: list[str] = []
    for palette_id in palette_ids:
        ids += [e["id"] for e in cat["palettes"][palette_id] if e["id"] not in ids]
    return ids


def _object(properties: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


def suggestion_schema(cat: Catalog | None = None, *, drawing: bool = False) -> dict[str, Any]:
    cat = cat or load_catalog()
    strings = {"type": "array", "items": {"type": "string"}}
    properties: dict[str, Any] = {}
    if drawing:
        properties |= {
            "is_drawing": {"type": "boolean"},
            "shows_real_person": {"type": "boolean"},
            "safe_for_kids": {"type": "boolean"},
        }
    properties |= {
        "body_type": {"type": "string", "enum": list(cat["body_types"])},
        "parts": _object(
            {
                c: {"type": "string", "enum": list(info["options"])}
                for c, info in cat["categories"].items()
            }
        ),
        "colors": _object(
            {slot: {"type": "string", "enum": colour_ids(slot, cat)} for slot in cat["color_slots"]}
        ),
        "extras": {"type": "array", "items": {"type": "string", "enum": list(cat["extras"])}},
        "name_ideas": strings,
        "traits": {"type": "array", "items": {"type": "string", "enum": TRAITS}},
        "catchphrase": {"type": "string"},
        "reply": {"type": "string"},
        "unmatched": strings,
    }
    return _object(properties)


def ideas_schema() -> dict[str, Any]:
    return _object(
        {
            "name_ideas": {"type": "array", "items": {"type": "string"}},
            "traits": {"type": "array", "items": {"type": "string", "enum": TRAITS}},
            "catchphrase": {"type": "string"},
            "reply": {"type": "string"},
        }
    )


def current(spec: dict[str, Any], cat: Catalog | None = None) -> str:
    """The current character as ids (colours as palette ids), for the prompt."""
    cat = cat or load_catalog()
    body_type = spec["body_type"]
    colours = {}
    for slot, hex_color in spec["colors"].items():
        entry = next((e for e in palette(slot, body_type, cat) if e["hex"] == hex_color), None)
        colours[slot] = entry["id"] if entry else hex_color
    personality = spec["personality"]
    return (
        f"body_type={body_type}; parts={spec['parts']}; colors={colours}; "
        f"extras={spec['extras']}; traits={personality['traits']}; "
        f"catchphrase={personality['catchphrase']!r}"
    )


def _system() -> str:
    return render("builder_helper", catalog=catalog_brief())


def describe(llm: LLMProvider, text: str, spec: dict[str, Any]) -> Raw:
    prompt = (
        f"Current character: {current(spec)}\n"
        f"The child describes the character they want: {text!r}\n"
        "Update the character to match the description."
    )
    return llm.complete_json(
        _system(), prompt, suggestion_schema(), schema_name="avatar_suggestion"
    )


def surprise(llm: LLMProvider, body_type: str | None, spec: dict[str, Any]) -> Raw:
    keep = f"Keep body_type={body_type}." if body_type else "Pick any body type."
    prompt = (
        f"Current character: {current(spec)}\n"
        "Invent a brand-new, fun and coherent character with a matching personality, "
        f"ignoring the current look. {keep} Make the colours and outfit go well together."
    )
    return llm.complete_json(
        _system(), prompt, suggestion_schema(), schema_name="avatar_suggestion"
    )


def ideas(llm: LLMProvider, spec: dict[str, Any], name: str) -> Raw:
    prompt = (
        f"Character: {current(spec)}; current name: {name!r}\n"
        "Suggest three new names, up to three personality traits and a catchphrase that suit "
        "this character's look. Reply with one short sentence."
    )
    return llm.complete_json(_system(), prompt, ideas_schema(), schema_name="character_ideas")


def from_drawing(llm: LLMProvider, png: bytes, spec: dict[str, Any]) -> Raw:
    prompt = (
        f"Current character: {current(spec)}\n"
        "The image should be a child's drawing of a character. First decide: is_drawing (a "
        "drawing, not a photo), shows_real_person (a photo of a real person), safe_for_kids. "
        "If it's a safe drawing, pick the parts and colours that best match it; otherwise copy "
        "the current character unchanged and reply kindly."
    )
    return llm.complete_json(
        _system(),
        prompt,
        suggestion_schema(drawing=True),
        schema_name="drawing_suggestion",
        image_png=png,
    )
