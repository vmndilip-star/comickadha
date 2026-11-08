"""The offline builder helper (LLM_PROVIDER=mock, and the fallback when Meta's API is down).

Nothing leaves the machine: "describe" matches words against the parts catalog, "surprise" makes a
seeded random character, and "from my drawing" reads the drawing's main colours. It returns the same
raw suggestion shape as the Meta helper, so both go through the same checks.
"""

import random
import re
import zlib
from collections.abc import Sequence
from typing import Any, get_args

from PIL import Image

from app.avatar.catalog import load_catalog
from app.avatar.spec import categories_for, nearest, options_for, palette
from app.avatar.words import (
    BODY_WORDS,
    COLOR_WORDS,
    EXTRA_WORDS,
    PART_WORDS,
    SKIN_WORDS,
    STAND_INS,
    TRAIT_WORDS,
)
from app.schemas.common import Trait
from app.services.character_safety import respectful_extras

Raw = dict[str, Any]

TRAITS: list[Trait] = list(get_args(Trait))
NAMES = {
    "kid": ["Zara", "Kiran", "Milo", "Asha", "Leo", "Noor", "Ravi", "Ivy", "Tomi", "Sana"],
    "grown_up": ["Auntie Meera", "Mr Okafor", "Coach Lin", "Grandpa Joe", "Ms Rosa", "Uncle Dev"],
    "robot": ["Bolt", "Gizmo", "Sprocket", "Pixel", "Widget", "Zap-9", "Beep-Bop"],
    "cat": ["Whiskers", "Mittens", "Ziggy", "Pumpkin", "Luna", "Tiger"],
    "dog": ["Biscuit", "Rocket", "Pepper", "Scout", "Noodle", "Bingo"],
    "bear": ["Honey", "Bruno", "Maple", "Bramble", "Teddy", "Pudding"],
}
CATCHPHRASES: dict[str, str] = {
    "brave": "Let's do this!",
    "curious": "Ooh, what's that?",
    "funny": "Knock knock!",
    "kind": "Need a hand?",
    "clever": "I have a plan!",
    "creative": "Let's make something amazing!",
    "calm": "No worries, we've got this.",
    "cheerful": "What a great day!",
    "helpful": "I can help with that!",
    "honest": "Here's the truth!",
    "adventurous": "Adventure time!",
    "caring": "Is everyone okay?",
    "energetic": "Let's goooo!",
    "gentle": "Slowly does it.",
    "patient": "Good things take time.",
    "playful": "Tag, you're it!",
    "shy": "Um... hi there!",
    "silly": "Wiggle wiggle!",
    "sporty": "Race you there!",
    "thoughtful": "Hmm, let me think...",
}
STOPWORDS = {
    *("a", "an", "the", "with", "and", "has", "have", "who", "is", "are", "very", "really"),
    *("my", "her", "his", "their", "its", "likes", "loves", "like", "love", "wearing", "wears"),
    *("wear", "in", "on", "of", "some", "lots", "lot", "tiny", "big", "little", "small", "cute"),
    *("who's", "that", "this", "to", "for", "always", "never", "also", "plus", "i", "want"),
    *("make", "me", "please", "one", "two"),
}
_WORD = re.compile(r"[a-z][a-z\-']*")


def _positions(text: str, phrase: str) -> list[int]:
    return [m.start() for m in re.finditer(rf"\b{re.escape(phrase)}\b", text)]


def _colour_before(text: str, at: int) -> str | None:
    """A colour word in the two words just before position `at` ("curly red hair")."""
    before = _WORD.findall(text[:at])[-2:]
    for i in range(len(before), 0, -1):
        two = " ".join(before[i - 2 : i]) if i >= 2 else ""
        if two in COLOR_WORDS:
            return COLOR_WORDS[two]
        if before[i - 1] in COLOR_WORDS:
            return COLOR_WORDS[before[i - 1]]
    return None


def describe(text: str, spec: dict[str, Any]) -> Raw:
    t = " " + text.lower() + " "
    body_type = spec["body_type"]
    for word, body in BODY_WORDS.items():
        if _positions(t, word):
            body_type = body
            break

    parts: dict[str, str] = {}
    colors: dict[str, str] = {}
    extras: list[str] = list(spec["extras"])  # new extras are added to the ones already on
    traits: list[str] = []
    known: set[str] = set()  # words that matched something

    for phrase in sorted(PART_WORDS, key=len, reverse=True):
        for at in _positions(t, phrase):
            category, option = PART_WORDS[phrase]
            parts.setdefault(category, option)
            known.update(phrase.split())
            colour = _colour_before(t, at)
            slot = {"headwear": "hat", "hair": "hair"}.get(category, category)
            if colour and slot in ("hair", "hat", "top", "bottom", "shoes"):
                colors.setdefault(slot, colour)
    for at in _positions(t, "hair"):  # "red hair" without a style
        known.add("hair")
        if colour := _colour_before(t, at):
            colors.setdefault("hair", colour)
    for phrase in sorted(EXTRA_WORDS, key=len, reverse=True):
        for at in _positions(t, phrase):
            extra = EXTRA_WORDS[phrase]
            if extra not in extras:
                extras.append(extra)
            known.update(phrase.split())
            colour = _colour_before(t, at)
            if colour and extra in ("cape", "backpack"):
                colors.setdefault(extra, colour)
    for phrase, hex_color in SKIN_WORDS.items():
        if _positions(t, phrase):
            colors["skin"] = hex_color
            known.update(phrase.split())
    for word, trait in TRAIT_WORDS.items():
        if _positions(t, word) and trait not in traits:
            traits.append(trait)
            known.add(word)
    known.update(w for w in BODY_WORDS if _positions(t, w))
    known.update(w for w in COLOR_WORDS if _positions(t, w))

    # Wishes we can't draw: stand-ins first, then any chunk with no word we know.
    unmatched: list[str] = []
    notes: list[str] = []
    chunks = [c.strip() for c in re.split(r",|\.|;|!|\band\b|\bwith\b|\bwho\b", text.lower())]
    for chunk in chunks:
        words = [w for w in _WORD.findall(chunk) if w not in STOPWORDS]
        if not words or any(w in known for w in words):
            continue
        unmatched.append(chunk)
        stand_in = next((STAND_INS[w] for w in words if w in STAND_INS), None)
        if stand_in:
            kind, option = stand_in
            if kind == "extra":
                if option not in extras:
                    extras.append(option)
                label = load_catalog()["extras"][option]["label"].lower()
            else:
                parts.setdefault(kind, option)
                label = load_catalog()["categories"][kind]["options"][option]["label"].lower()
            notes.append(f"We don't have {chunk} yet, so I gave you a {label}!")
        else:
            notes.append(f"We can't draw {chunk} yet. Maybe soon!")

    changed = bool(parts or colors or extras != spec["extras"] or body_type != spec["body_type"])
    if changed:
        reply = "Ta-da! Here's your character."
    else:
        reply = (
            "Hmm, I couldn't spot any parts in that. Try words like curly hair, red hoodie or cape!"
        )
    if notes:
        reply = (reply + " " + " ".join(notes[:2])).strip()
    traits = traits[:3] or list(spec["personality"]["traits"])
    seed = zlib.crc32(text.encode())
    return {
        "body_type": body_type,
        "parts": parts,
        "colors": colors,
        "extras": extras,
        "name_ideas": _names(body_type, seed),
        "traits": traits,
        "catchphrase": _catchphrase(traits, body_type) or spec["personality"]["catchphrase"],
        "reply": reply,
        "unmatched": unmatched,
    }


FOLLOW_UP = {
    "hair": "What colour should their hair be?",
    "robot": "What colour should this robot be?",
    "animal": "What colour should their fur be?",
}
AGE_LABEL = {"little_kid": "little kid", "big_kid": "kid", "grandparent": "grandparent"}
GRANDPARENT_HAIR = ("grey", "white")


def create(
    body: str,
    age: str | None,
    description: str,
    base: dict[str, Any],
    *,
    name: str,
    answered: bool,
    seed: int,
) -> Raw:
    """A new character: matched to the description's words, or a seeded surprise without one.
    Adds an intro line and (until it's answered) a follow-up question about colours."""
    rng = random.Random(seed)
    cat = load_catalog()
    if description:
        raw = describe(description, base)
    else:
        raw = surprise(body, seed)
        if age == "grandparent":
            hair = rng.choice(GRANDPARENT_HAIR)
            raw["colors"]["hair"] = next(e["hex"] for e in palette("hair", body) if e["id"] == hair)
    raw["body_type"] = body
    traits = list(raw.get("traits") or []) or rng.sample(TRAITS, k=2)
    raw["traits"] = traits[:3]
    names = list(raw.get("name_ideas") or []) or _names(body, seed)
    raw["name_ideas"] = names
    who = name or names[0]
    label = AGE_LABEL.get(age or "", cat["body_types"][body]["label"].lower())
    raw["intro_line"] = f"Meet {who}, a {traits[0]} {label} ready for adventure!"
    raw["catchphrase"] = raw.get("catchphrase") or _catchphrase(traits, body)
    raw["follow_up"] = None if answered else _follow_up(body, rng)
    if not description:
        raw["reply"] = f"Here's {who}! Change anything you like."
    return raw


def _follow_up(body: str, rng: random.Random) -> Raw:
    kind = load_catalog()["body_types"][body]["kind"]
    slot = "hair" if kind in ("kid", "grown_up") else "skin"
    question = FOLLOW_UP["hair" if slot == "hair" else ("robot" if kind == "robot" else "animal")]
    entries = rng.sample(palette(slot, body), k=3)
    return {
        "question": question,
        "options": [
            {"label": e["label"], "target": f"colors.{slot}", "value": e["id"]} for e in entries
        ],
    }


def surprise(body_type: str | None, seed: int) -> Raw:
    rng = random.Random(seed)
    cat = load_catalog()
    body = body_type or rng.choice(list(cat["body_types"]))
    parts = {c: rng.choice(options_for(c, body)) for c in categories_for(body)}
    if parts.get("headwear") != "none" and rng.random() < 0.6:
        parts["headwear"] = "none"  # most surprises show off their hair
    colors = {slot: rng.choice(palette(slot, body))["hex"] for slot in cat["color_slots"]}
    allowed = [e for e, extra in cat["extras"].items() if body in extra["body_types"]]
    extras: list[str] = []
    for extra_id in rng.sample(allowed, k=rng.randint(0, 2)):
        group = cat["extras"][extra_id].get("group")
        if group and any(cat["extras"][e].get("group") == group for e in extras):
            continue
        extras.append(extra_id)
    # Cultural or religious headwear is never paired with silly items (docs/character-safety.md).
    extras = respectful_extras(parts, extras)
    traits = rng.sample(TRAITS, k=2)
    label = cat["body_types"][body]["label"].lower()
    return {
        "body_type": body,
        "parts": parts,
        "colors": colors,
        "extras": extras,
        "name_ideas": _names(body, seed),
        "traits": traits,
        "catchphrase": _catchphrase(traits, body),
        "reply": f"Surprise! Meet a {traits[0]}, {traits[1]} {label}.",
        "unmatched": [],
    }


def ideas(spec: dict[str, Any], name: str, seed: int) -> Raw:
    rng = random.Random(seed)
    traits = list(spec["personality"]["traits"]) or rng.sample(TRAITS, k=2)
    names = [n for n in _names(spec["body_type"], seed, count=4) if n != name][:3]
    return {
        "name_ideas": names,
        "traits": traits[:3],
        "catchphrase": _catchphrase(traits, spec["body_type"], rng),
        "reply": f"How about {names[0]}? Tap a name to use it.",
    }


def _names(body_type: str, seed: int, count: int = 3) -> list[str]:
    pool = NAMES.get(body_type, NAMES["kid"])
    return random.Random(seed).sample(pool, k=min(count, len(pool)))


def _catchphrase(traits: Sequence[str], body_type: str, rng: random.Random | None = None) -> str:
    if not traits:
        return ""
    trait = rng.choice(traits) if rng else traits[0]
    line = CATCHPHRASES.get(trait, "")
    return f"Beep boop! {line}" if body_type == "robot" and line else line


# ---- drawings -------------------------------------------------------------------------------

# A drawing is mostly a few flat colours; a photo spreads over many. Counted on a coarse grid of
# colours, as the share of pixels the most common bins cover.
PHOTO_BINS = 40


def looks_like_photo(image: Image.Image) -> bool:
    small = image.convert("RGB").resize((96, 96))
    counts: dict[tuple[int, int, int], int] = {}
    data = small.tobytes()
    for i in range(0, len(data), 3):
        key = (data[i] // 32, data[i + 1] // 32, data[i + 2] // 32)
        counts[key] = counts.get(key, 0) + 1
    total, covered = 96 * 96, 0
    for bins, count in enumerate(sorted(counts.values(), reverse=True), start=1):
        covered += count
        if covered >= total * 0.9:
            return bins > PHOTO_BINS
    return True


def main_colours(image: Image.Image, count: int = 3) -> list[str]:
    """The drawing's main colours as hex, skipping paper (near white) and ink (near black)."""
    small = image.convert("RGB").resize((64, 64))
    counts: dict[tuple[int, int, int], int] = {}
    data = small.tobytes()
    for i in range(0, len(data), 3):
        r, g, b = data[i], data[i + 1], data[i + 2]
        if min(r, g, b) > 215 or max(r, g, b) < 60:
            continue
        key = (r // 24 * 24 + 12, g // 24 * 24 + 12, b // 24 * 24 + 12)
        counts[key] = counts.get(key, 0) + 1
    ranked = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)
    return ["#{:02X}{:02X}{:02X}".format(*key) for key, n in ranked[:count] if n >= 20]


def from_drawing(image: Image.Image, spec: dict[str, Any]) -> Raw:
    body_type = spec["body_type"]
    colours = main_colours(image)
    colors: dict[str, str] = {}
    for slot, hex_color in zip(("top", "bottom", "hair"), colours, strict=False):
        if slot == "hair" and "hair" not in spec["parts"]:
            continue
        colors[slot] = hex_color
    names = [nearest(c, palette("top", body_type))["label"].lower() for c in colours]
    reply = (
        f"I spotted {', '.join(names[:-1]) + ' and ' + names[-1] if len(names) > 1 else names[0]} "
        "in your drawing, so I used those colours!"
        if names
        else "What a lovely drawing! I couldn't spot many colours, so try colouring it in."
    )
    seed = zlib.crc32(image.tobytes()[:4096])
    return {
        "body_type": body_type,
        "parts": {},
        "colors": colors,
        "extras": list(spec["extras"]),
        "name_ideas": _names(body_type, seed),
        "traits": list(spec["personality"]["traits"]),
        "catchphrase": spec["personality"]["catchphrase"],
        "reply": reply,
        "unmatched": [],
    }


def offline_names(body_type: str, seed: int, count: int = 3) -> list[str]:
    """Made-up names from the offline list (the safe default for unusable name ideas)."""
    return _names(body_type, seed, count)


def catchphrase_for(traits: Sequence[str], body_type: str) -> str:
    """A friendly catchphrase for the first trait (the safe default for an unusable one)."""
    return _catchphrase(traits, body_type)
