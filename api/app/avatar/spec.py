"""Avatar specs checked against the parts catalog.

A full spec names one option for every category its body type uses, a palette colour for every
colour slot, its extras, personality and role. `validate` is strict: an unknown or ill-fitting
choice is a SpecError with a message for kids, and anything left out gets the body type's default.
`normalize` is forgiving (it swaps bad choices for defaults and snaps colours to the palette), for
migrated data and AI suggestions.
"""

from collections.abc import Mapping
from typing import Any

from app.avatar.catalog import Catalog, load_catalog
from app.schemas.avatar import AvatarSpec

KIND_OF_BODY = {
    "kid": "kid",
    "grown_up": "grown_up",
    "robot": "robot",
    "cat": "animal",
    "dog": "animal",
    "bear": "animal",
}
# Card colours for new characters, one per cast slot (sun, coral and sky tints from the boards).
SLOT_CARDS = ("#FFE9A8", "#FFD0C2", "#DDF0FC")

Spec = dict[str, Any]


class SpecError(ValueError):
    """A choice the catalog doesn't have, or that doesn't fit the body type. Kid-friendly text."""


def categories_for(body_type: str, catalog: Catalog | None = None) -> list[str]:
    """The part categories this body type uses (robots and animals have no hair or nose)."""
    cat = catalog or load_catalog()
    return [
        category
        for category, info in cat["categories"].items()
        if any(body_type in option["body_types"] for option in info["options"].values())
    ]


def options_for(category: str, body_type: str, catalog: Catalog | None = None) -> list[str]:
    cat = catalog or load_catalog()
    options = cat["categories"][category]["options"]
    return [option_id for option_id, option in options.items() if body_type in option["body_types"]]


def palette(slot: str, body_type: str, catalog: Catalog | None = None) -> list[dict[str, str]]:
    cat = catalog or load_catalog()
    info = cat["color_slots"][slot]
    palette_id = info.get("palette") or info["palette_by_body"][body_type]
    entries: list[dict[str, str]] = cat["palettes"][palette_id]
    return entries


def nearest(hex_color: str, entries: list[dict[str, str]]) -> dict[str, str]:
    """The palette entry closest to a colour (plain RGB distance)."""
    r, g, b = _rgb(hex_color)

    def distance(entry: dict[str, str]) -> int:
        er, eg, eb = _rgb(entry["hex"])
        return (r - er) ** 2 + (g - eg) ** 2 + (b - eb) ** 2

    return min(entries, key=distance)


def _rgb(hex_color: str) -> tuple[int, int, int]:
    v = int(hex_color.lstrip("#")[:6], 16)
    return (v >> 16) & 255, (v >> 8) & 255, v & 255


def default_spec(body_type: str = "kid", *, card: str | None = None) -> Spec:
    spec = validate({"body_type": body_type})
    if card:
        spec["colors"]["card"] = nearest(card, palette("card", body_type))["hex"]
    return spec


def validate(spec: Mapping[str, Any], catalog: Catalog | None = None) -> Spec:
    """A full, checked copy of the spec. Raises SpecError for anything the catalog can't draw."""
    return _resolve(spec, catalog or load_catalog(), strict=True)


def normalize(spec: Mapping[str, Any], catalog: Catalog | None = None) -> Spec:
    """Like validate, but swaps anything that doesn't fit for the body type's default."""
    return _resolve(spec, catalog or load_catalog(), strict=False)


def _resolve(spec: Mapping[str, Any], cat: Catalog, *, strict: bool) -> Spec:
    model = AvatarSpec.model_validate(
        {**spec, "body_type": spec.get("body_type") or "kid"} if strict else _loose_fields(spec)
    )
    body_type = model.body_type
    body = cat["body_types"][body_type]
    body_label = body["label"].lower()
    defaults = body["defaults"]

    def problem(message: str) -> None:
        if strict:
            raise SpecError(message)

    parts: dict[str, str] = {}
    wanted = categories_for(body_type, cat)
    for category, choice in model.parts.items():
        info = cat["categories"].get(category)
        if info is None:
            problem("We don't have that kind of part. Pick one from the list!")
            continue
        option = info["options"].get(choice)
        label = info["label"].lower()
        if option is None:
            problem(f"We don't have that {_singular(label)}. Pick one from the list!")
        elif body_type not in option["body_types"]:
            problem(f"{option['label']} doesn't fit a {body_label}. Pick another one!")
        elif category in wanted:
            parts[category] = choice
    for category in wanted:
        if category not in parts:
            parts[category] = (
                defaults["parts"].get(category) or options_for(category, body_type, cat)[0]
            )

    colors: dict[str, str] = {}
    for slot, value in model.colors.items():
        if slot not in cat["color_slots"]:
            problem("We don't have that paint pot. Pick a colour from the list!")
            continue
        entries = palette(slot, body_type, cat)
        match = next((e for e in entries if e["hex"] == value.upper()), None)
        if match is None:
            problem("That colour isn't in our paint box. Pick one of the swatches!")
            match = nearest(value, entries)
        colors[slot] = match["hex"]
    for slot in cat["color_slots"]:
        if slot not in colors:
            colors[slot] = (defaults["colors"].get(slot) or cat["color_defaults"][slot]).upper()

    extras: list[str] = []
    groups: set[str] = set()
    for extra_id in model.extras:
        extra = cat["extras"].get(extra_id)
        if extra is None:
            problem("We don't have that extra. Pick one from the list!")
            continue
        if body_type not in extra["body_types"]:
            problem(f"{extra['label']} doesn't fit a {body_label}. Pick another extra!")
            continue
        group = extra.get("group")
        if group and group in groups:
            problem("Only one pair of glasses at a time!")
            continue
        if extra_id not in extras:
            extras.append(extra_id)
            if group:
                groups.add(group)

    return {
        "body_type": body_type,
        "parts": parts,
        "colors": colors,
        "extras": extras,
        "personality": model.personality.model_dump(),
        "role": model.role,
    }


def _loose_fields(spec: Mapping[str, Any]) -> dict[str, Any]:
    """Drops fields that would fail the schema, so normalize() never raises."""
    out: dict[str, Any] = {}
    for key, value in spec.items():
        try:
            AvatarSpec.model_validate({key: value})
        except ValueError:
            continue
        out[key] = value
    colors = spec.get("colors")
    if isinstance(colors, Mapping):  # keep good colours even if one is malformed
        out["colors"] = {k: v for k, v in colors.items() if isinstance(v, str) and _is_hex(v)}
    return out


def _is_hex(value: str) -> bool:
    return (
        len(value) == 7
        and value[0] == "#"
        and all(c in "0123456789abcdefABCDEF" for c in value[1:])
    )


def _singular(label: str) -> str:
    return {"eyebrows": "eyebrow", "hats": "hat", "tops": "top", "bottoms": "bottom"}.get(
        label, label
    )


def describe(spec: Mapping[str, Any], catalog: Catalog | None = None) -> str:
    """The look in plain words, for prompts: 'a kid with sand skin, curly dark brown hair, ...'."""
    cat = catalog or load_catalog()
    s = normalize(spec, cat)
    body_type = s["body_type"]

    def option(category: str) -> str:
        choice = s["parts"].get(category)
        if not choice or choice == "none":
            return ""
        return str(cat["categories"][category]["options"][choice]["label"]).lower()

    def colour(slot: str) -> str:
        entry = nearest(s["colors"][slot], palette(slot, body_type, cat))
        return entry["label"].lower()

    body = cat["body_types"][body_type]["label"].lower()
    skin_word = (
        "fur" if KIND_OF_BODY[body_type] == "animal" else "body" if body_type == "robot" else "skin"
    )
    bits = [f"{colour('skin')} {skin_word}"]
    if option("hair"):
        bits.append(f"{option('hair')} {colour('hair')} hair")
    bits.append(f"{option('eyes')} eyes")
    wearing = [
        f"a {colour(slot)} {option(category)}"
        for category, slot in (
            ("headwear", "hat"),
            ("top", "top"),
            ("bottom", "bottom"),
            ("shoes", "shoes"),
        )
        if option(category) and s["parts"].get(category) not in ("none",)
    ]
    extras = []
    for extra_id in s["extras"]:
        label = str(cat["extras"][extra_id]["label"]).lower()
        slot = cat["extras"][extra_id].get("slot")
        extras.append(f"a {colour(slot)} {label}" if slot else label)
    text = f"a {body} with " + ", ".join(bits)
    if wearing:
        text += ", wearing " + _join(wearing)
    if extras:
        text += ", with " + _join(extras)
    return text


def _join(items: list[str]) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]
