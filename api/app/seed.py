"""Demo data: one kid, 3 characters, 3 places and 3 comics.

`seed()` is idempotent: it does nothing if the seeded profile already exists.
`uv run python -m app.seed` resets the database and media files back to this data.
"""

import uuid
from datetime import timedelta
from typing import Any

from sqlalchemy import delete
from sqlmodel import Session

from app.avatar import spec as avatar_spec
from app.config import get_settings
from app.db import init_db, make_engine
from app.models import (
    Background,
    Character,
    CharacterVersion,
    Comic,
    Job,
    ModerationLog,
    Panel,
    Scene,
    User,
)
from app.models.base import utcnow
from app.providers.image import ImageProvider
from app.providers.mock import MockImageProvider
from app.services import looks
from app.services.builder_sheet import BuilderSheets
from app.services.character_sheet import ImageSheets, SheetProvider, SheetSpec
from app.services.image_gen import PlaceSpec, build_place
from app.services.storage import LocalStorage, Storage

# Fixed namespace so seeded ids (and URLs) stay the same after every reset.
_NS = uuid.UUID("6f1d2c4e-8b7a-4c1e-9d3f-2a5b6c7d8e9f")


def sid(name: str) -> str:
    return str(uuid.uuid5(_NS, name))


USER_ID = sid("user:aarav")
MIRA, RAJU, ROBO = sid("character:mira"), sid("character:raju"), sid("character:robotik")
KITCHEN, GARDEN, SPACE = (
    sid("background:kitchen"),
    sid("background:garden"),
    sid("background:space"),
)
MANGO, ROBO_DAY, SPACE_PICNIC = (
    sid("comic:mango"),
    sid("comic:robotik-day"),
    sid("comic:space-picnic"),
)

MEDIA_PREFIXES = ("characters", "backgrounds", "comics")

# Avatar specs (schemas/avatar.py), checked against the parts catalog when seeding. Anything left
# out gets the body type's default.
CHARACTERS: list[dict[str, Any]] = [
    {
        "id": MIRA,
        "name": "Mira",
        "status": "locked",
        "seed": 1101,
        "spec": {
            "body_type": "kid",
            "parts": {"hair": "bob", "top": "raincoat", "bottom": "jeans", "shoes": "rain_boots"},
            "colors": {
                "skin": "#EFC29B",
                "hair": "#3B2314",
                "top": "#FFD23F",
                "bottom": "#1F5BD1",
                "shoes": "#FFD23F",
                "card": "#FFE9A8",
            },
            "extras": ["backpack"],
            "personality": {
                "traits": ["brave", "curious"],
                "catchphrase": "Adventure is my middle name!",
            },
            "role": "hero",
        },
    },
    {
        "id": RAJU,
        "name": "Raju",
        "status": "locked",
        "seed": 1102,
        "spec": {
            "body_type": "kid",
            "parts": {"hair": "spiky", "top": "jersey", "bottom": "shorts", "shoes": "sneakers"},
            "colors": {
                "skin": "#CF8D5B",
                "hair": "#2B2B2B",
                "top": "#3FA34D",
                "bottom": "#23305E",
                "shoes": "#E53935",
                "card": "#FFD0C2",
            },
            "personality": {
                "traits": ["funny", "energetic"],
                "catchphrase": "Snack break? Snack break!",
            },
            "role": "sidekick",
        },
    },
    {
        "id": ROBO,
        "name": "Robo-Tik",
        "status": "draft",
        "seed": 1103,
        "spec": {
            "body_type": "robot",
            "parts": {"face_shape": "dome", "eyes": "sparkle"},
            "colors": {"skin": "#9AD0F5", "card": "#DDF0FC"},
            "extras": ["headphones"],
            "personality": {"traits": ["clever"], "catchphrase": "Beep boop, I can explain!"},
            "role": "friend",
        },
    },
]

BACKGROUNDS: list[dict[str, Any]] = [
    {
        "id": KITCHEN,
        "name": "Grandma's kitchen",
        "tint": "#FFD0C2",
        "seed": 2101,
        "description": "A warm kitchen with a fruit bowl, pots on hooks and a checked floor.",
    },
    {
        "id": GARDEN,
        "name": "School garden",
        "tint": "#B7E4A7",
        "seed": 2102,
        "description": "A sunny school garden with a big mango tree and a wooden bench.",
    },
    {
        "id": SPACE,
        "name": "Outer space",
        "tint": "#2E2A6B",
        "seed": 2103,
        "description": "Deep purple space with twinkling stars and a cheesy yellow moon.",
    },
]

# Panel rows: (scene number, beat, [(character, expression, position, pose)], (speaker, type, text))
PanelSpec = tuple[int, str, list[tuple[str, str, str, str]], tuple[str, str, str]]

COMICS: list[dict[str, Any]] = [
    {
        "id": MANGO,
        "title": "The Missing Mango Mystery",
        "mood": "mystery",
        "status": "draft",
        "studio_step": 3,
        "panel_count": 6,
        "cast_ids": [MIRA, RAJU, ROBO],
        "created_h": 30,
        "updated_h": 2,
        "synopsis": "The last mango in Grandma's kitchen disappears before the festival. "
        "Mira and Raju "
        "follow sticky footprints to the school garden, where Robo-Tik confesses he was keeping it "
        "safe from the monkeys.",
        "scenes": [
            (KITCHEN, [MIRA, RAJU], "The mango is gone! Sticky footprints on the floor."),
            (GARDEN, [MIRA, RAJU, ROBO], "Robo-Tik is hiding something behind his back."),
        ],
        "ready": 4,
        "panels": [
            (
                1,
                "The mango bowl is empty!",
                [(MIRA, "surprised", "left", "point"), (RAJU, "surprised", "right", "front")],
                (MIRA, "talk", "The mango bowl is EMPTY!"),
            ),
            (
                1,
                "Spots sticky footprints.",
                [(MIRA, "scared", "left", "front"), (RAJU, "scared", "right", "front")],
                (RAJU, "talk", "Sticky footprints... gross!"),
            ),
            (
                2,
                "Footprints lead to the garden.",
                [(MIRA, "happy", "left", "walk"), (RAJU, "happy", "right", "walk")],
                ("narrator", "narrator", "The trail leads outside..."),
            ),
            (
                2,
                "Hiding something. Looks guilty.",
                [(ROBO, "scared", "center", "front")],
                (ROBO, "talk", "I can explain. Beep."),
            ),
            (
                2,
                "Monkeys in the tree!",
                [
                    (MIRA, "surprised", "left", "front"),
                    (ROBO, "surprised", "center", "front"),
                    (RAJU, "surprised", "right", "scared_pose"),
                ],
                (RAJU, "shout", "MONKEYS!!"),
            ),
            (
                1,
                "Mango saved. Festival time!",
                [
                    (MIRA, "happy", "left", "celebrate"),
                    (ROBO, "laughing", "center", "front"),
                    (RAJU, "laughing", "right", "front"),
                ],
                (MIRA, "talk", "Mango saved. Festival time!"),
            ),
        ],
    },
    {
        "id": ROBO_DAY,
        "title": "Robo-Tik's First Day",
        "mood": "funny",
        "status": "finished",
        "studio_step": 3,
        "panel_count": 6,
        "cast_ids": [ROBO, MIRA, RAJU],
        "created_h": 24 * 12,
        "updated_h": 24 * 8,
        "synopsis": "Robo-Tik starts school and gets everything a little bit wrong, "
        "in the best way.",
        "scenes": [
            (GARDEN, [ROBO, MIRA, RAJU], "Robo-Tik arrives at school for the first time."),
            (KITCHEN, [ROBO, MIRA], "Robo-Tik discovers the lunch room."),
        ],
        "ready": 6,
        "panels": [
            (
                1,
                "Robo-Tik rolls in.",
                [(ROBO, "happy", "center", "wave")],
                ("narrator", "narrator", "Robo-Tik's first day at school!"),
            ),
            (
                1,
                "Lost already.",
                [(ROBO, "surprised", "left", "front"), (MIRA, "happy", "right", "front")],
                (ROBO, "talk", "Beep! Where is class 3B?"),
            ),
            (
                2,
                "Wrong room.",
                [(MIRA, "laughing", "left", "front"), (ROBO, "surprised", "right", "front")],
                (MIRA, "talk", "That's the lunch room, silly!"),
            ),
            (
                2,
                "Robo-Tik wonders.",
                [(ROBO, "surprised", "center", "thinking")],
                (ROBO, "think", "Lunch... what is lunch?"),
            ),
            (
                1,
                "Dance party.",
                [
                    (MIRA, "laughing", "left", "jump"),
                    (ROBO, "laughing", "center", "celebrate"),
                    (RAJU, "laughing", "right", "jump"),
                ],
                (RAJU, "shout", "ROBOT DANCE PARTY!"),
            ),
            (
                1,
                "Best day.",
                [
                    (MIRA, "happy", "left", "front"),
                    (ROBO, "happy", "center", "front"),
                    (RAJU, "happy", "right", "front"),
                ],
                ("narrator", "narrator", "Best. First. Day. Ever."),
            ),
        ],
    },
    {
        "id": SPACE_PICNIC,
        "title": "Space Picnic",
        "mood": "adventure",
        "status": "finished",
        "studio_step": 3,
        "panel_count": 8,
        "cast_ids": [MIRA, RAJU, ROBO],
        "created_h": 24 * 9,
        "updated_h": 24 * 5,
        "synopsis": "Three friends fly to the moon for a picnic and forget the sandwiches.",
        "scenes": [(SPACE, [MIRA, RAJU, ROBO], "A picnic on the moon goes wrong, then right.")],
        "ready": 8,
        "panels": [
            (
                1,
                "Blast off.",
                [
                    (MIRA, "happy", "left", "front"),
                    (ROBO, "happy", "center", "front"),
                    (RAJU, "laughing", "right", "front"),
                ],
                ("narrator", "narrator", "Three friends. One rocket. Zero snacks."),
            ),
            (
                1,
                "No sandwiches.",
                [(RAJU, "angry", "center", "hands_on_hips")],
                (RAJU, "talk", "Who forgot the sandwiches?!"),
            ),
            (
                1,
                "Not Mira.",
                [(MIRA, "happy", "left", "point"), (RAJU, "sad", "right", "front")],
                (MIRA, "talk", "Not me! I packed the map."),
            ),
            (
                1,
                "Robo-Tik confesses.",
                [(ROBO, "sad", "center", "front")],
                (ROBO, "talk", "I packed... batteries."),
            ),
            (
                1,
                "A cheese moon.",
                [(MIRA, "surprised", "left", "front"), (RAJU, "surprised", "right", "front")],
                ("narrator", "narrator", "Then they spotted a cheese moon."),
            ),
            (
                1,
                "Lunch!",
                [(RAJU, "laughing", "center", "run")],
                (RAJU, "shout", "LUNCH IS SERVED!"),
            ),
            (
                1,
                "Mira is not sure.",
                [(MIRA, "scared", "center", "thinking")],
                (MIRA, "think", "Is moon cheese even safe?"),
            ),
            (
                1,
                "Robo-Tik checks.",
                [
                    (MIRA, "happy", "left", "front"),
                    (ROBO, "laughing", "center", "front"),
                    (RAJU, "happy", "right", "front"),
                ],
                (ROBO, "talk", "Scanning... 100% delicious!"),
            ),
        ],
    },
]


def wipe(session: Session, storage: Storage) -> None:
    """Deletes every row (children first) and every generated file."""
    for model in (
        Panel,
        Scene,
        Comic,
        Job,
        ModerationLog,
        CharacterVersion,
        Character,
        Background,
        User,
    ):
        session.execute(delete(model))
    session.commit()
    for prefix in MEDIA_PREFIXES:
        storage.delete_prefix(prefix)


def _quiet(_type: str, _data: dict[str, Any], _progress: float | None) -> None:
    """Seeding runs the real pipelines without a job, so there is nobody to send events to."""


def seed(
    session: Session,
    storage: Storage,
    provider: ImageProvider | None = None,
    *,
    sheets: SheetProvider | None = None,
    reset: bool = False,
) -> bool:
    """Inserts the demo data. Returns False (and changes nothing) if it is already there.

    `provider` paints the places; `sheets` draws the locked characters (default: the builder).
    """
    if reset:
        wipe(session, storage)
    if session.get(User, USER_ID) is not None:
        return False
    provider = provider or MockImageProvider()
    sheets = sheets or BuilderSheets()
    now = utcnow()

    # No ORM relationships are declared, so flush parents before children (SQLite enforces FKs).
    session.add(User(id=USER_ID, display_name="Aarav", avatar_color="#FF8A6B", created_at=now))
    session.flush()

    sheet_versions: dict[str, int] = {}
    for i, data in enumerate(CHARACTERS):
        spec = avatar_spec.validate(data["spec"])
        character = Character(
            user_id=USER_ID,
            name=data["name"],
            role=spec["role"],
            kind=avatar_spec.KIND_OF_BODY[spec["body_type"]],
            spec=spec,
            status=data["status"],
            seed=data["seed"],
            id=data["id"],
            created_at=now + timedelta(seconds=i),
            updated_at=now,
        )
        if character.status == "locked":
            character.sheet_version = 1
            character.manifest = sheets.build(SheetSpec.of(character, 1), storage, _quiet)
            character.style = character.manifest["style"]
        sheet_versions[character.id] = character.sheet_version
        session.add(character)

    for i, data in enumerate(BACKGROUNDS):
        bg = Background(
            user_id=USER_ID,
            status="locked",
            version=1,
            created_at=now + timedelta(seconds=i),
            updated_at=now,
            **data,
        )
        keys = build_place(PlaceSpec.of(bg, 1), provider, storage, _quiet)
        bg.image_key, bg.thumb_key = keys["image_key"], keys["thumb_key"]
        session.add(bg)
    session.flush()
    # The looks the locked characters were locked with (panels are drawn from these).
    for data in CHARACTERS:
        if data["status"] == "locked":
            looks.freeze(session, data["id"], 1, data["spec"])
    session.flush()

    for data in COMICS:
        comic_id = data["id"]
        comic = Comic(
            id=comic_id,
            user_id=USER_ID,
            title=data["title"],
            synopsis=data["synopsis"],
            mood=data["mood"],
            panel_count=data["panel_count"],
            cast_ids=data["cast_ids"],
            studio_step=data["studio_step"],
            status=data["status"],
            created_at=now - timedelta(hours=data["created_h"]),
            updated_at=now - timedelta(hours=data["updated_h"]),
        )
        session.add(comic)
        session.flush()
        scene_ids: list[str] = []
        scene_bgs: list[str] = []
        for idx, (bg_id, char_ids, summary) in enumerate(data["scenes"]):
            scene = Scene(
                id=sid(f"scene:{comic_id}:{idx}"),
                comic_id=comic_id,
                idx=idx,
                background_id=bg_id,
                character_ids=char_ids,
                summary=summary,
            )
            session.add(scene)
            scene_ids.append(scene.id)
            scene_bgs.append(bg_id)
        session.flush()

        panels: list[PanelSpec] = data["panels"]
        for idx, (scene_no, beat, cast, (speaker, kind, text)) in enumerate(panels):
            panel_id = sid(f"panel:{comic_id}:{idx}")
            session.add(
                Panel(
                    id=panel_id,
                    comic_id=comic_id,
                    scene_id=scene_ids[scene_no - 1],
                    idx=idx,
                    background_id=scene_bgs[scene_no - 1],
                    beat=beat,
                    characters=[
                        {
                            "id": cid,
                            "sheet_version": sheet_versions[cid],
                            "pose": pose,
                            "expression": expr,
                            "position": pos,
                            "scale": 1.0,
                        }
                        for cid, expr, pos, pose in cast
                    ],
                    bubbles=[
                        {
                            "id": sid(f"bubble:{panel_id}:0"),
                            "speaker": speaker,
                            "type": kind,
                            "text": text,
                            "box": None,
                            "tail": None,
                        }
                    ],
                    status="ready" if idx < data["ready"] else "planned",
                    updated_at=comic.updated_at,
                )
            )

    session.commit()
    return True


def main() -> None:
    settings = get_settings()
    settings.storage_dir.mkdir(parents=True, exist_ok=True)
    engine = make_engine(settings.resolved_database_url)
    init_db(engine)
    storage = LocalStorage(settings.media_dir)
    mock = MockImageProvider()
    sheets = ImageSheets(mock) if settings.sheet_provider == "image" else BuilderSheets()
    with Session(engine) as session:
        seed(session, storage, mock, sheets=sheets, reset=True)
    print("Reset Comickatha: 1 kid, 3 characters, 3 places, 3 comics.")


if __name__ == "__main__":
    main()
