"""Place (background) images: one locked reference image per place, at the panel aspect ratio.

A picture from a real image model (anything but the mock) goes through the image check before it
is saved or announced (Phase 6a). A blocked picture gets one more try (told "no signs, letters or
logos" when the block was for writing); a checker outage fails the job at once. Nothing is saved
unless a picture passes.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from PIL import Image
from sqlalchemy import Engine
from sqlmodel import Session

from app.models import Background
from app.models.base import utcnow
from app.prompts import render
from app.providers.image import ImageProvider
from app.providers.llm import LLMProvider
from app.services import imaging
from app.services.jobs import JobContext, JobFailed
from app.services.painting import (
    Check,
    CheckerResting,
    image_check,
    paint_checked,
)
from app.services.prop_rules import without_props
from app.services.storage import Storage

PLACE_SIZE = (1024, 768)  # 4:3, the same shape as a comic panel
THUMB_SIDE = 320
# Phase 8: every place is painted at these times of day too, from the same description and the day
# picture, so a scene at sunset or at night shows the same place in that light.
TIMES = ("sunset", "night")
TIME_LIGHT = {
    "sunset": "golden evening light, an orange and pink sky, long soft shadows",
    "night": "night time, a dark blue sky with a moon and stars, cool moonlight, a few warm lights",
}

Emit = Callable[[str, dict[str, Any], float | None], None]

# Places have a "Paint it again" button (and Delete) on their tile.
CANT_PAINT = "We couldn't paint {name}. Tap Paint it again!"
CHECKER_RESTING = (
    "Our picture checker is taking a break, so {name} isn't painted yet. "
    "Tap Paint it again in a minute!"
)


@dataclass(frozen=True)
class PlaceSpec:
    id: str
    name: str
    description: str
    tint: str
    seed: int
    version: int

    @classmethod
    def of(cls, bg: Background, version: int) -> "PlaceSpec":
        return cls(bg.id, bg.name, bg.description, bg.tint, bg.seed, version)


def place_prefix(background_id: str, version: int) -> str:
    return f"backgrounds/{background_id}/v{version}"


def time_key(background_id: str, version: int, time_of_day: str, thumb: bool = False) -> str:
    """Where a version's sunset or night picture is kept."""
    return f"{place_prefix(background_id, version)}/{time_of_day}{'_thumb' if thumb else ''}.png"


def painted_times(storage: Storage, bg: Background, version: int | None = None) -> list[str]:
    """The times of day a version of the place has real pictures for ("day" always)."""
    v = version or bg.version
    return ["day", *(t for t in TIMES if v and storage.exists(time_key(bg.id, v, t)))]


def place_picture(
    storage: Storage, bg: Background, version: int | None, time_of_day: str | None = None
) -> bytes | None:
    """The picture a panel draws: its pinned version of the place (Phase 8: repainting a place
    makes a new version and old panels keep theirs), at the panel's time of day: the painted
    sunset or night picture, or until there is one, the day picture tinted on this machine. None
    when the place has no picture."""
    keys = []
    if version:
        keys.append(f"{place_prefix(bg.id, version)}/reference.png")
    if bg.image_key:
        keys.append(bg.image_key)
    day = next((storage.read(k) for k in keys if storage.exists(k)), None)
    if day is None or time_of_day not in TIMES:
        return day
    if version and storage.exists(time_key(bg.id, version, time_of_day)):
        return storage.read(time_key(bg.id, version, time_of_day))
    return imaging.to_png(imaging.time_tint(imaging.load(day), time_of_day))


def _valid_place(png: bytes) -> Image.Image | None:
    try:
        image = imaging.fit_size(imaging.load(png), PLACE_SIZE)
    except OSError:
        return None
    # A background is a full scene: mostly magenta means the model drew a sheet instead.
    if image is None or imaging.coverage(imaging.key_magenta(image)) < 0.5:
        return None
    return image.convert("RGB")


def build_place(
    spec: PlaceSpec,
    provider: ImageProvider,
    storage: Storage,
    emit: Emit,
    check: Check | None = None,
) -> dict[str, str]:
    """Paints, validates and (with `check`) checks the picture, then saves it. Blocking."""
    prompt = place_prompt(spec)
    emit("progress", {"stage": "painting"}, 0.1)
    png = _paint(spec, prompt, provider, emit, check, spec.seed, None, 0.3)
    if png is None:
        raise JobFailed(CANT_PAINT.format(name=spec.name))

    prefix = place_prefix(spec.id, spec.version)
    image_key = storage.save(f"{prefix}/reference.png", png)
    thumb = imaging.thumbnail(imaging.load(png), THUMB_SIDE)
    thumb_key = storage.save(f"{prefix}/thumb.png", imaging.to_png(thumb))
    emit(
        "cell_ready",
        {"sheet": "place", "cell": "reference", "row": 0, "col": 0, "url": storage.url(thumb_key)},
        0.4,
    )
    paint_times(spec, provider, storage, emit, check, png)
    return {"image_key": image_key, "thumb_key": thumb_key}


def place_prompt(spec: PlaceSpec, time_of_day: str | None = None) -> str:
    prompt = render(
        "background",
        name=spec.name,
        # Props are drawn per panel, on top of the place: never painted into it (Phase 8).
        description=without_props(spec.description) or f"A fun place called {spec.name}.",
        aspect="4:3",
        tint=spec.tint,
    )
    if time_of_day in TIMES:
        prompt += "\n\n" + render(
            "background_time", time=time_of_day, light=TIME_LIGHT[time_of_day]
        )
    return prompt


def _paint(
    spec: PlaceSpec,
    prompt: str,
    provider: ImageProvider,
    emit: Emit,
    check: Check | None,
    seed: int,
    references: list[bytes] | None,
    progress: float,
) -> bytes | None:
    """One picture, painted and (with `check`) checked, with one more try; None if none passed."""
    try:
        painted = paint_checked(
            prompt,
            PLACE_SIZE,
            provider,
            seed,
            references,
            fit=_valid_place,
            check=check,
            on_checking=lambda: emit("progress", {"stage": "checking"}, progress),
        )
    except CheckerResting as resting:
        raise JobFailed(CHECKER_RESTING.format(name=spec.name)) from resting
    return painted.png


def paint_times(
    spec: PlaceSpec,
    provider: ImageProvider,
    storage: Storage,
    emit: Emit,
    check: Check | None,
    day: bytes,
    only_missing: bool = False,
) -> list[str]:
    """The sunset and night pictures of this version, painted from the same description with the
    day picture to copy (the same place, other light). A time that doesn't paint is skipped:
    panels tint the day picture instead. Returns the times painted."""
    painted: list[str] = []
    for n, time_of_day in enumerate(TIMES):
        key = time_key(spec.id, spec.version, time_of_day)
        if only_missing and storage.exists(key):
            continue
        emit("progress", {"stage": f"painting {time_of_day}"}, 0.45 + n * 0.25)
        seed = spec.seed + 101 * (n + 1)
        png = _paint(
            spec, place_prompt(spec, time_of_day), provider, emit, check, seed, [day], 0.6 + n * 0.2
        )
        if png is None:
            continue
        storage.save(key, png)
        thumb = imaging.thumbnail(imaging.load(png), THUMB_SIDE)
        storage.save(
            time_key(spec.id, spec.version, time_of_day, thumb=True), imaging.to_png(thumb)
        )
        painted.append(time_of_day)
    return painted


async def run_times_job(
    ctx: JobContext,
    *,
    spec: PlaceSpec,
    engine: Engine,
    provider: ImageProvider,
    storage: Storage,
    llm: LLMProvider | None = None,
    user_id: str = "",
) -> dict[str, Any]:
    """Job work for POST /backgrounds/{id}/times: the sunset and night pictures a locked place's
    version is missing (painted before Phase 8). The place stays locked throughout."""
    check = place_check(engine, spec, provider, llm, user_id)
    day = storage.read(f"{place_prefix(spec.id, spec.version)}/reference.png")
    painted = await ctx.run(
        paint_times, spec, provider, storage, ctx.emit_threadsafe, check, day, True
    )
    _settle(engine, spec.id)
    return {"target_id": spec.id, "version": spec.version, "times": painted}


def _settle(engine: Engine, background_id: str) -> None:
    with Session(engine) as session:
        bg = session.get(Background, background_id)
        if bg is not None and bg.status == "generating":
            bg.status = "locked"
            bg.updated_at = utcnow()
            session.add(bg)
            session.commit()


async def run_place_job(
    ctx: JobContext,
    *,
    spec: PlaceSpec,
    engine: Engine,
    provider: ImageProvider,
    storage: Storage,
    llm: LLMProvider | None = None,
    user_id: str = "",
) -> dict[str, Any]:
    """Job work for POST /backgrounds/{id}/lock."""
    check = place_check(engine, spec, provider, llm, user_id)
    keys = await ctx.run(build_place, spec, provider, storage, ctx.emit_threadsafe, check)
    save_place(engine, spec, keys)
    return {"target_id": spec.id, "version": spec.version}


def place_check(
    engine: Engine, spec: PlaceSpec, provider: ImageProvider, llm: LLMProvider | None, user_id: str
) -> Check | None:
    """The image check for a real model's pictures (None for the mock's). Fails closed without an
    LLM (startup refuses that set-up anyway)."""
    target = f"background:{spec.id}:v{spec.version}"
    try:
        return image_check(engine, provider, llm, user_id, target)
    except CheckerResting as resting:
        raise JobFailed(CHECKER_RESTING.format(name=spec.name)) from resting


def save_place(engine: Engine, spec: PlaceSpec, keys: dict[str, str]) -> None:
    """The painted picture becomes the place's reference: locked at the new version."""
    with Session(engine) as session:
        bg = session.get(Background, spec.id)
        if bg is None:
            raise JobFailed("We couldn't find that place any more.")
        bg.image_key = keys["image_key"]
        bg.thumb_key = keys["thumb_key"]
        bg.version = spec.version
        bg.status = "locked"
        bg.updated_at = utcnow()
        session.add(bg)
        session.commit()


def mark_failed(engine: Engine, background_id: str, *, was_locked: bool = False) -> None:
    """A painting that didn't work: a new place is "failed" (Paint it again); a locked place
    that was getting a new version stays locked with the version it had."""
    with Session(engine) as session:
        bg = session.get(Background, background_id)
        if bg is not None and bg.status == "generating":
            bg.status = "locked" if was_locked else "failed"
            bg.updated_at = utcnow()
            session.add(bg)
            session.commit()
