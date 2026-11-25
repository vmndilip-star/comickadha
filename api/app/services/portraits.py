"""Painted portraits (decision 132): Muse Image paints each locked character version once, from
the builder drawing, as an inked-and-painted illustration. The builder spec stays the blueprint
(it is the pinned look panels draw from); the portrait is extra and optional.

- The reference is the version's own front drawing (the frozen look), flat on cream, with no name
  or text on it; the prompt describes the look in catalog words and colour values only, so no
  kid-written word reaches Meta and no classifier call is needed.
- A real model's portrait passes the image check, then the look check; nothing is saved
  otherwise, and a failed portrait never changes the character (it stays locked).
- Files: characters/<id>/v<N>/portrait-<provider>.png (+ _thumb). The provider is in the key so
  mock and Muse portraits never mix; the URLs carry ?v=<hash> so a new painting shows at once.
- It runs as its own job after the lock commits, so locking never waits or fails for it.
"""

import hashlib
import json
from dataclasses import dataclass
from functools import partial
from typing import Any

from PIL import Image
from sqlalchemy import Engine
from sqlmodel import Session, col, select

from app.avatar.catalog import load_catalog
from app.avatar.render import render_pose
from app.avatar.spec import KIND_OF_BODY, describe, nearest, normalize, palette
from app.models import Character, Job
from app.prompts import render
from app.providers.image import ImageProvider
from app.providers.llm import LLMProvider
from app.services import imaging, looks
from app.services.character_safety import tagged
from app.services.character_sheet import sheet_prefix
from app.services.jobs import JobContext, JobFailed, JobRunner
from app.services.look_check import Expected, check_look
from app.services.painting import (
    Check,
    CheckerResting,
    Look,
    Painted,
    image_check,
    log_paint,
    paint_checked,
)
from app.services.storage import Storage

PORTRAIT_SIZE = (1024, 1024)  # 1:1, a shape Muse is measured to honour (decision 82)
THUMB_SIDE = 320
CREAM = (255, 248, 236)
RUNNING = ("queued", "running")

CANT_PAINT_PORTRAIT = (
    "We couldn't paint {name}'s portrait this time. Tap Paint portrait to try again!"
)
CHECKER_RESTING = (
    "Our picture checker is taking a break, so {name}'s portrait isn't painted yet. "
    "Tap Paint portrait in a minute!"
)
DAILY_LIMIT = "The paint brushes need a rest. Try again tomorrow!"

# Colour slots named in the prompts, with the part that must be there for the slot to show.
COLOUR_SLOTS = (
    ("skin", None),
    ("hair", "hair"),
    ("hat", "headwear"),
    ("top", "top"),
    ("bottom", "bottom"),
    ("shoes", "shoes"),
)


@dataclass(frozen=True)
class PortraitSpec:
    id: str
    name: str  # for the kid's messages only, never for a prompt
    version: int
    seed: int
    spec: dict[str, Any]  # the version's frozen look

    @classmethod
    def of(
        cls, session: Session, character: Character, version: int | None = None
    ) -> "PortraitSpec":
        v = version or character.sheet_version
        frozen = looks.looks_for(session, [(character.id, v)]).get(character.id, {}).get(str(v))
        manifest = character.manifest or {}
        spec = frozen or (manifest.get("spec") if manifest.get("renderer") == "builder" else None)
        return cls(character.id, character.name, v, character.seed, dict(spec or character.spec))


def portrait_key(character_id: str, version: int, provider: str, thumb: bool = False) -> str:
    suffix = "_thumb" if thumb else ""
    return f"{sheet_prefix(character_id, version)}/portrait-{provider}{suffix}.png"


def portrait_target(spec: PortraitSpec) -> str:
    """The moderation and paint log target."""
    return f"character:{spec.id}:v{spec.version}:portrait"


# ---- the look in words (catalog words and spec values only) ----------------------------------


def colour_words(spec: dict[str, Any]) -> str:
    """'skin sand #E0AC69; hair dark brown #3B2A20; ...': each colour's catalog name and its exact
    value, for the slots the character shows."""
    cat = load_catalog()
    s = normalize(spec, cat)
    body = s["body_type"]
    kind = KIND_OF_BODY[body]
    names = {"skin": "fur" if kind == "animal" else "body" if body == "robot" else "skin"}
    bits = []
    for slot, category in COLOUR_SLOTS:
        if category and s["parts"].get(category, "none") == "none":
            continue
        word = names.get(slot, slot)
        if slot == "hat" and has_head_covering(s):
            word = "head covering"
        bits.append(_colour(s, slot, word))
    for extra_id in s["extras"]:
        slot = cat["extras"][extra_id].get("slot")
        if slot and slot in s["colors"]:
            bits.append(_colour(s, slot, slot))
    return "; ".join(dict.fromkeys(bits))


def _colour(s: dict[str, Any], slot: str, word: str) -> str:
    value = str(s["colors"][slot]).upper()
    label = nearest(value, palette(slot, s["body_type"]))["label"].lower()
    return f"{word} {label} {value}"


def look_words(spec: dict[str, Any]) -> str:
    return f"{describe(spec)} (colours: {colour_words(spec)})"


def has_head_covering(spec: dict[str, Any]) -> bool:
    """A hijab or a turban: the catalog's "cultural" headwear (decision 68)."""
    return tagged("headwear", str(normalize(spec)["parts"].get("headwear", "none")), "cultural")


# ---- painting -------------------------------------------------------------------------------


def portrait_reference(spec: dict[str, Any]) -> bytes:
    """The version's front drawing, smiling, flat on cream (an edits API may read transparent
    areas as "paint here"). Never the kid's own uploaded drawing."""
    drawing = imaging.load(render_pose(normalize(spec), "front", PORTRAIT_SIZE[0], "happy"))
    flat = Image.new("RGB", drawing.size, CREAM)
    rgba = drawing.convert("RGBA")
    flat.paste(rgba, mask=rgba.getchannel("A"))
    return imaging.to_png(flat)


def _fit(png: bytes) -> Image.Image | None:
    try:
        image = imaging.fit_size(imaging.load(png), PORTRAIT_SIZE)
    except OSError:
        return None
    return image.convert("RGB") if image is not None else None


def paint_portrait(
    spec: PortraitSpec,
    provider: ImageProvider,
    check: Check | None,
    llm: LLMProvider | None,
    on_checking: Any = None,
) -> Painted:
    """Blocking: paints, checks and look-checks one portrait (None in .png if none passed)."""
    reference = portrait_reference(spec.spec)
    look: Look | None = None
    if check is not None and llm is not None:
        expected = Expected([look_words(spec.spec)], [has_head_covering(spec.spec)])
        checker = llm

        def look_at(png: bytes) -> Any:
            return check_look(checker, reference, png, expected)

        look = look_at
    return paint_checked(
        render("portrait", look=look_words(spec.spec)),
        PORTRAIT_SIZE,
        provider,
        spec.seed,
        [reference],
        fit=_fit,
        check=check,
        look=look,
        on_checking=on_checking,
    )


def save_portrait(
    engine: Engine, storage: Storage, spec: PortraitSpec, provider: str, png: bytes
) -> dict[str, str]:
    """Saves the portrait and its thumbnail; the character's manifest gets the URLs if it is still
    on that version, and the version's manifest.json always does."""
    key = storage.save(portrait_key(spec.id, spec.version, provider), png)
    thumb = imaging.thumbnail(imaging.load(png), THUMB_SIDE)
    thumb_key = storage.save(
        portrait_key(spec.id, spec.version, provider, thumb=True), imaging.to_png(thumb)
    )
    tag = hashlib.sha256(png).hexdigest()[:8]
    urls = {
        "portrait_url": f"{storage.url(key)}?v={tag}",
        "portrait_thumb_url": f"{storage.url(thumb_key)}?v={tag}",
    }
    with Session(engine) as session:
        character = session.get(Character, spec.id)
        if character is not None and character.sheet_version == spec.version and character.manifest:
            character.manifest = {**character.manifest, **urls}
            session.add(character)
            session.commit()
    manifest_key = f"{sheet_prefix(spec.id, spec.version)}/manifest.json"
    if storage.exists(manifest_key):
        data = json.loads(storage.read(manifest_key))
        data.update(urls)
        storage.save(manifest_key, json.dumps(data, indent=2).encode())
    return urls


# ---- the job --------------------------------------------------------------------------------


async def run_portrait_job(
    ctx: JobContext,
    *,
    spec: PortraitSpec,
    engine: Engine,
    provider: ImageProvider,
    storage: Storage,
    llm: LLMProvider | None,
    user_id: str,
) -> dict[str, Any]:
    """Job work for a portrait (after a lock, or Paint portrait). Never touches the character's
    status: a failed portrait leaves it locked with the builder look."""
    target = portrait_target(spec)
    try:
        check = image_check(engine, provider, llm, user_id, target)
    except CheckerResting as resting:
        raise JobFailed(CHECKER_RESTING.format(name=spec.name)) from resting
    ctx.emit("progress", {"stage": "painting"}, 0.1)

    def checking() -> None:
        ctx.emit_threadsafe("progress", {"stage": "checking"}, 0.7)

    try:
        painted = await ctx.run(paint_portrait, spec, provider, check, llm, checking)
    except CheckerResting as resting:
        raise JobFailed(CHECKER_RESTING.format(name=spec.name)) from resting
    log_paint(
        engine,
        user_id=user_id,
        kind="portrait",
        target=target,
        provider=provider.name,
        painted=painted,
    )
    if painted.png is None:
        raise JobFailed(CANT_PAINT_PORTRAIT.format(name=spec.name))
    urls = await ctx.run(save_portrait, engine, storage, spec, provider.name, painted.png)
    return {"target_id": spec.id, "version": spec.version, **urls}


def running_portrait_jobs(session: Session, character_ids: list[str]) -> dict[str, str]:
    """{character_id: job_id} for portraits being painted now."""
    if not character_ids:
        return {}
    stmt = select(Job).where(
        Job.kind == "portrait",
        col(Job.status).in_(RUNNING),
        col(Job.target_id).in_(character_ids),
    )
    return {job.target_id: job.id for job in session.exec(stmt)}


def start_portrait_job(
    jobs: JobRunner,
    *,
    character_id: str,
    engine: Engine,
    provider: ImageProvider,
    storage: Storage,
    llm: LLMProvider | None,
    user_id: str,
) -> str | None:
    """Starts painting the character's current locked version (or returns the portrait job already
    running). None if the character isn't locked. The caller checks the switch and the caps."""
    with Session(engine) as session:
        character = session.get(Character, character_id)
        if character is None or character.status != "locked" or character.sheet_version < 1:
            return None
        running = running_portrait_jobs(session, [character_id]).get(character_id)
        if running:
            return running
        spec = PortraitSpec.of(session, character)
    job = jobs.create("portrait", character_id)
    jobs.start(
        job.id,
        partial(
            run_portrait_job,
            spec=spec,
            engine=engine,
            provider=provider,
            storage=storage,
            llm=llm,
            user_id=user_id,
        ),
    )
    return job.id


def portrait_png(storage: Storage, character_id: str, version: int, provider: str) -> bytes | None:
    """A saved portrait (Phase B uses it as a reference), or None."""
    key = portrait_key(character_id, version, provider)
    return storage.read(key) if storage.exists(key) else None
