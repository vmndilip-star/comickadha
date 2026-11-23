"""The 12 starter characters: ready-made, locked and the same for every kid (Phase 7 part B).

A kid can make a story straight away, without designing anyone first. Starters are rows in the
character table with `starter=True`, owned by a fixed "starter cast" profile (the table needs an
owner; `get_current_user` never picks that profile). Each has a fixed uuid5 id, a sheet drawn by
the builder (free, offline) and a frozen look (CharacterVersion 1), so comics using them never
change. They don't count toward a kid's 3 own characters and can't be changed (a 409 "starter");
"Make it mine" copies one into the kid's own cast as an editable draft.

`ensure_starters()` runs at every startup and after a reset. It is idempotent: it only adds what's
missing (and redraws a sheet whose files are gone).
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlmodel import Session

from app.avatar import spec as avatar_spec
from app.models import Character, User
from app.services import looks
from app.services.builder_sheet import BuilderSheets
from app.services.character_sheet import SheetProvider, SheetSpec, sheet_prefix
from app.services.storage import Storage

# Fixed namespace, so the starters' ids (and their media URLs) are the same everywhere, forever.
_NS = uuid.UUID("3c9a7f52-1d4e-4b8a-9e6f-5a2b7c8d9e01")


def starter_id(key: str) -> str:
    return str(uuid.uuid5(_NS, key))


STARTER_USER_ID = starter_id("user:starter-cast")
VERSION = 1  # the frozen look; a new look for a starter would be a new version
_CREATED = datetime(2026, 11, 1, tzinfo=UTC)

# Palette hexes (shared/avatar/catalog.json): skin, hair, cloth and card colours by name.
SKIN = {
    "porcelain": "#FCE4D2", "sand": "#EFC29B", "caramel": "#CF8D5B", "amber": "#B9773F",
    "bronze": "#9C6236", "chestnut": "#7E4B2A", "espresso": "#5E3720", "ebony": "#43271A",
}  # fmt: skip
HAIR = {"black": "#2B2B2B", "dark_brown": "#3B2314", "auburn": "#8E3B22", "white": "#F2F2EE"}
FUR = {"ginger": "#E8954F", "cream": "#F3E2C3", "brown": "#8A5A3B"}
CLOTH = {
    "sun": "#FFD23F", "coral": "#FF6B4A", "red": "#E53935", "pink": "#FF7FB0",
    "purple": "#7A4FC9", "pow_blue": "#1F5BD1", "sky": "#9AD0F5", "mint": "#B7E4A7",
    "green": "#3FA34D", "brown": "#8A5A3B", "navy": "#23305E", "grey": "#8C8C8C",
    "white": "#FFFFFF",
}  # fmt: skip
CARD = {"sun": "#FFE9A8", "coral": "#FFD0C2", "sky": "#DDF0FC", "mint": "#E6F6DF"}


def _person(
    body_type: str,
    face: tuple[str, str, str, str],
    hair: tuple[str, str],
    clothes: tuple[str, str, str],
    colours: tuple[str, str, str],
    skin: str,
    card: str,
    *,
    headwear: tuple[str, str] | None = None,
    extras: tuple[str, ...] = (),
    backpack: str | None = None,
    cape: str | None = None,
) -> dict[str, Any]:
    face_shape, eyes, brows, nose = face
    parts = {
        "face_shape": face_shape, "eyes": eyes, "brows": brows, "nose": nose, "hair": hair[0],
        "headwear": headwear[0] if headwear else "none",
        "top": clothes[0], "bottom": clothes[1], "shoes": clothes[2],
    }  # fmt: skip
    colors = {
        "skin": SKIN[skin], "hair": HAIR[hair[1]], "top": CLOTH[colours[0]],
        "bottom": CLOTH[colours[1]], "shoes": CLOTH[colours[2]], "card": CARD[card],
    }  # fmt: skip
    if headwear:
        colors["hat"] = CLOTH[headwear[1]]
    if backpack:
        colors["backpack"] = CLOTH[backpack]
    if cape:
        colors["cape"] = CLOTH[cape]
    return {"body_type": body_type, "parts": parts, "colors": colors, "extras": list(extras)}


def _creature(
    body_type: str,
    eyes: str,
    brows: str,
    skin: str,
    card: str,
    *,
    face_shape: str | None = None,
    headwear: tuple[str, str] | None = None,
    top: tuple[str, str] | None = None,
    extras: tuple[str, ...] = (),
    backpack: str | None = None,
) -> dict[str, Any]:
    parts = {"face_shape": face_shape or body_type, "eyes": eyes, "brows": brows}
    colors = {"skin": skin, "card": CARD[card]}
    if headwear:
        parts["headwear"], colors["hat"] = headwear[0], CLOTH[headwear[1]]
    if top:
        parts["top"], colors["top"] = top[0], CLOTH[top[1]]
    if backpack:
        colors["backpack"] = CLOTH[backpack]
    return {"body_type": body_type, "parts": parts, "colors": colors, "extras": list(extras)}


def _starter(
    key: str, name: str, role: str, traits: list[str], catchphrase: str, look: dict[str, Any]
) -> dict[str, Any]:
    spec = {**look, "personality": {"traits": traits, "catchphrase": catchphrase}, "role": role}
    return {"id": starter_id(f"character:{key}"), "name": name, "spec": spec}


# A spread of skin tones, hair and outfits; Aisha's hijab and Arjun's turban go with ordinary
# clothes, never with silly items (decision 68). Order is the order kids see them in.
STARTERS: list[dict[str, Any]] = [
    _starter("zara", "Zara", "hero", ["brave", "adventurous"], "Let's go, go, go!", _person(
        "kid", ("round", "sparkle", "arched", "button"), ("two_puffs", "black"),
        ("superhero", "leggings", "boots"), ("purple", "navy", "red"), "espresso", "coral",
        extras=("cape",), cape="red")),
    _starter("leo", "Leo", "sidekick", ["funny", "silly"], "Did somebody say snacks?", _person(
        "kid", ("square", "round", "bushy", "round"), ("spiky", "dark_brown"),
        ("tshirt", "shorts", "sneakers"), ("sun", "pow_blue", "coral"), "amber", "sun",
        extras=("glasses_star",))),
    _starter("aisha", "Aisha", "friend", ["clever", "kind"], "Don't worry, I have a plan!",
             _person(
        "kid", ("oval", "almond", "arched", "dot"), ("bob", "dark_brown"),
        ("sweater", "jeans", "sneakers"), ("purple", "pow_blue", "white"), "caramel", "mint",
        headwear=("hijab", "mint"), extras=("glasses_round", "backpack"), backpack="sun")),
    _starter("arjun", "Arjun", "hero", ["curious", "creative"], "Ooh, what does this button do?",
             _person(
        "kid", ("round", "oval", "straight", "button"), ("crop", "black"),
        ("hoodie", "cargo", "sneakers"), ("green", "brown", "red"), "bronze", "sky",
        headwear=("turban", "coral"), extras=("backpack",), backpack="navy")),
    _starter("kofi", "Kofi", "sidekick", ["creative", "calm"], "Let me draw you a map.", _person(
        "kid", ("oval", "sleepy", "thin", "round"), ("buzz", "black"),
        ("dungarees", "jeans", "sandals"), ("sky", "navy", "brown"), "ebony", "sun",
        extras=("backpack",), backpack="coral")),
    _starter("mei", "Mei", "friend", ["sporty", "cheerful"], "Race you there!", _person(
        "kid", ("heart", "sparkle", "straight", "dot"), ("braids", "auburn"),
        ("jersey", "shorts", "sneakers"), ("red", "navy", "white"), "sand", "coral",
        extras=("headphones",))),
    _starter("nana-rose", "Nana Rose", "friend", ["caring", "patient"], "Cocoa fixes everything.",
             _person(
        "grown_up", ("round", "oval", "thin", "round"), ("bun", "white"),
        ("sweater", "skirt", "boots"), ("pink", "purple", "brown"), "porcelain", "mint",
        extras=("glasses_round",))),
    _starter("mr-hari", "Mr. Hari", "friend", ["thoughtful", "honest"], "Every mistake is a clue.",
             _person(
        "grown_up", ("square", "almond", "bushy", "pointy"), ("side_part", "black"),
        ("sweater", "trousers", "boots"), ("green", "navy", "brown"), "chestnut", "sky",
        extras=("glasses_square",))),
    _starter("pixel", "Pixel", "sidekick", ["clever", "playful"],
             "Calculating... fun level: maximum!", _creature(
        "robot", "round", "straight", "#9AD0F5", "sun", face_shape="screen",
        extras=("backpack",), backpack="sun")),
    _starter("whiskers", "Whiskers", "friend", ["curious", "playful"], "Purr-fect!", _creature(
        "cat", "almond", "thin", FUR["ginger"], "sky", headwear=("beanie", "purple"),
        extras=("blush",))),
    _starter("biscuit", "Biscuit", "sidekick", ["cheerful", "helpful"], "Woof! Follow me!",
             _creature(
        "dog", "button", "arched", FUR["cream"], "coral", headwear=("cap", "red"),
        extras=("backpack",), backpack="pow_blue")),
    _starter("barnaby", "Barnaby", "friend", ["gentle", "shy"], "Um... can I come too?", _creature(
        "bear", "round", "bushy", FUR["brown"], "mint", top=("hoodie", "sky"))),
]  # fmt: skip

STARTER_IDS: tuple[str, ...] = tuple(s["id"] for s in STARTERS)


def _quiet(_type: str, _data: dict[str, Any], _progress: float | None) -> None:
    """Drawn without a job, so there is nobody to send cell events to."""


def ensure_starters(session: Session, storage: Storage, sheets: SheetProvider | None = None) -> int:
    """Adds the starter cast profile and any starter that's missing; returns how many it added.

    A starter whose sheet files are gone (say, the media folder was cleared) is drawn again: the
    builder draws the same look the same way, and the frozen look never changes."""
    sheets = sheets or BuilderSheets()
    if session.get(User, STARTER_USER_ID) is None:
        session.add(
            User(
                id=STARTER_USER_ID,
                display_name="Starter cast",
                avatar_color="#FFD23F",
                created_at=_CREATED,
            )
        )
        session.flush()
    added = 0
    for i, data in enumerate(STARTERS):
        character = session.get(Character, data["id"])
        drawn = storage.exists(f"{sheet_prefix(data['id'], VERSION)}/manifest.json")
        if character is not None and drawn:
            continue
        spec = avatar_spec.validate(data["spec"])
        if character is None:
            character = Character(
                id=data["id"],
                user_id=STARTER_USER_ID,
                name=data["name"],
                role=spec["role"],
                kind=avatar_spec.KIND_OF_BODY[spec["body_type"]],
                spec=spec,
                status="locked",
                seed=7101 + i,
                sheet_version=VERSION,
                starter=True,
                created_at=_CREATED + timedelta(seconds=i),
                updated_at=_CREATED,
            )
            added += 1
        character.manifest = sheets.build(SheetSpec.of(character, VERSION), storage, _quiet)
        character.style = character.manifest["style"]
        session.add(character)
        session.flush()
        looks.freeze(session, character.id, VERSION, character.spec)
    session.commit()
    return added
