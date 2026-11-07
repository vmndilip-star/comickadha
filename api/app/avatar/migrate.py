"""Startup migration: Phase 2/3 character specs become builder (avatar) specs.

Old specs were {skin, hair_style, hair_color, outfit, traits, catchphrase, tint}. Colours snap to
the nearest palette entry, the outfit text is read for garments and colour words, and the tint
becomes the card colour. Idempotent: specs that already have a body_type are left alone. Old sheet
versions keep their own manifest (and its old spec), so comics drawn with them don't change.
"""

import re
from typing import Any

from sqlalchemy import Engine
from sqlmodel import Session, select

from app.avatar.spec import KIND_OF_BODY, nearest, normalize, palette
from app.avatar.words import COLOR_WORDS, EXTRA_WORDS, PART_WORDS
from app.models import Character

OLD_KINDS = {"kid": "kid", "grown_up": "grown_up", "robot": "robot", "animal": "cat"}
_WORD = re.compile(r"[a-z\-]+")


def is_old(spec: dict[str, Any]) -> bool:
    return "body_type" not in spec


def migrate_spec(old: dict[str, Any], kind: str, role: str) -> dict[str, Any]:
    body_type = OLD_KINDS.get(kind, "kid")
    parts: dict[str, str] = {}
    colors: dict[str, str] = {}
    extras: list[str] = []

    if skin := old.get("skin"):
        colors["skin"] = nearest(skin, palette("skin", body_type))["hex"]
    if hair := old.get("hair_color"):
        colors["hair"] = nearest(hair, palette("hair", body_type))["hex"]
    if style := old.get("hair_style"):
        parts["hair"] = style  # bob, spiky, braids and curly are all builder styles
    if tint := old.get("tint"):
        colors["card"] = nearest(tint, palette("card", body_type))["hex"]
        # Without colour words, the outfit takes the card's colour (as the old placeholder did).
        colors["top"] = nearest(tint, palette("top", body_type))["hex"]

    words = _WORD.findall(str(old.get("outfit", "")).lower())
    for i, word in enumerate(words):
        if word in PART_WORDS:
            category, option = PART_WORDS[word]
            parts[category] = option
            if i > 0 and words[i - 1] in COLOR_WORDS:
                slot = {"headwear": "hat"}.get(category, category)
                if slot in ("top", "bottom", "shoes", "hat"):
                    colors[slot] = nearest(COLOR_WORDS[words[i - 1]], palette(slot, body_type))[
                        "hex"
                    ]
        elif word in EXTRA_WORDS:
            extras.append(EXTRA_WORDS[word])
            if word == "cape" and i > 0 and words[i - 1] in COLOR_WORDS:
                colors["cape"] = nearest(COLOR_WORDS[words[i - 1]], palette("cape", body_type))[
                    "hex"
                ]

    return normalize(
        {
            "body_type": body_type,
            "parts": parts,
            "colors": colors,
            "extras": extras,
            "personality": {
                "traits": list(old.get("traits", []))[:3],
                "catchphrase": str(old.get("catchphrase", ""))[:60],
            },
            "role": role if role in ("hero", "sidekick", "friend") else "friend",
        }
    )


def migrate_characters(engine: Engine) -> int:
    """Converts every old-format character spec. Returns how many changed."""
    changed = 0
    with Session(engine) as session:
        for character in session.exec(select(Character)):
            if not is_old(character.spec):
                continue
            spec = migrate_spec(character.spec, character.kind, character.role)
            character.spec = spec
            character.kind = KIND_OF_BODY[spec["body_type"]]
            session.add(character)
            changed += 1
        session.commit()
    return changed
