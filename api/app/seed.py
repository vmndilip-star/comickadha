"""Demo data: one kid, 3 characters, 3 places and 3 comics.

`seed()` is idempotent: it does nothing if the seeded profile already exists.
`uv run python -m app.seed` resets the database and media files back to this data.
"""

import io
import uuid
from datetime import timedelta
from typing import Any

from PIL import Image
from sqlalchemy import delete
from sqlmodel import Session

from app.config import get_settings
from app.db import init_db, make_engine
from app.models import Background, Character, Comic, Job, ModerationLog, Panel, Scene, User
from app.models.base import utcnow
from app.providers.image import ImageProvider, ImageRequest
from app.providers.mock import MockImageProvider
from app.services.character_sheet import build_placeholder_manifest
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

CHARACTERS: list[dict[str, Any]] = [
    {
        "id": MIRA,
        "name": "Mira",
        "role": "hero",
        "kind": "kid",
        "status": "locked",
        "seed": 1101,
        "spec": {
            "skin": "#F2C29B",
            "hair_style": "bob",
            "hair_color": "#3B2314",
            "outfit": "Yellow raincoat with big pockets",
            "traits": ["brave", "curious"],
            "catchphrase": "Adventure is my middle name!",
            "tint": "#FFE9A8",
        },
    },
    {
        "id": RAJU,
        "name": "Raju",
        "role": "sidekick",
        "kind": "kid",
        "status": "locked",
        "seed": 1102,
        "spec": {
            "skin": "#C98B5E",
            "hair_style": "spiky",
            "hair_color": "#1A1A1A",
            "outfit": "Green football jersey and red sneakers",
            "traits": ["funny", "loud"],
            "catchphrase": "Snack break? Snack break!",
            "tint": "#FFD0C2",
        },
    },
    {
        "id": ROBO,
        "name": "Robo-Tik",
        "role": "friend",
        "kind": "robot",
        "status": "draft",
        "seed": 1103,
        "spec": {
            "skin": "#9AD0F5",
            "hair_style": "bob",
            "hair_color": "#1A1A1A",
            "outfit": "Shiny blue panels with an orange antenna",
            "traits": ["clever"],
            "catchphrase": "Beep boop, I can explain!",
            "tint": "#DDF0FC",
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
    for model in (Panel, Scene, Comic, Job, ModerationLog, Character, Background, User):
        session.execute(delete(model))
    session.commit()
    for prefix in MEDIA_PREFIXES:
        storage.delete_prefix(prefix)


def _place_images(bg: Background, storage: Storage, provider: ImageProvider) -> None:
    png = provider.generate(
        ImageRequest(
            prompt=bg.description,
            width=1024,
            height=768,
            seed=bg.seed,
            hints={"tint": bg.tint, "label": bg.name},
        )
    )
    prefix = f"backgrounds/{bg.id}/v{bg.version}"
    bg.image_key = storage.save(f"{prefix}/reference.png", png)
    thumb = Image.open(io.BytesIO(png))
    thumb.thumbnail((320, 240))
    buf = io.BytesIO()
    thumb.save(buf, format="PNG")
    bg.thumb_key = storage.save(f"{prefix}/thumb.png", buf.getvalue())


def seed(
    session: Session,
    storage: Storage,
    provider: ImageProvider | None = None,
    *,
    reset: bool = False,
) -> bool:
    """Inserts the demo data. Returns False (and changes nothing) if it is already there."""
    if reset:
        wipe(session, storage)
    if session.get(User, USER_ID) is not None:
        return False
    provider = provider or MockImageProvider()
    now = utcnow()

    # No ORM relationships are declared, so flush parents before children (SQLite enforces FKs).
    session.add(User(id=USER_ID, display_name="Aarav", avatar_color="#FF8A6B", created_at=now))
    session.flush()

    sheet_versions: dict[str, int] = {}
    for i, data in enumerate(CHARACTERS):
        character = Character(
            user_id=USER_ID, created_at=now + timedelta(seconds=i), updated_at=now, **data
        )
        if character.status == "locked":
            character.sheet_version = 1
            character.manifest = build_placeholder_manifest(character, storage, provider)
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
        _place_images(bg, storage, provider)
        session.add(bg)
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
    with Session(engine) as session:
        seed(session, storage, MockImageProvider(), reset=True)
    print("Reset Comickatha: 1 kid, 3 characters, 3 places, 3 comics.")


if __name__ == "__main__":
    main()
