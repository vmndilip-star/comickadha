"""Place (background) images: one locked reference image per place, at the panel aspect ratio."""

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
from app.services import imaging
from app.services.jobs import JobContext, JobFailed
from app.services.storage import Storage

PLACE_SIZE = (1024, 768)  # 4:3, the same shape as a comic panel
THUMB_SIDE = 320
ATTEMPTS = 2

Emit = Callable[[str, dict[str, Any], float | None], None]


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
    spec: PlaceSpec, provider: ImageProvider, storage: Storage, emit: Emit
) -> dict[str, str]:
    prompt = render(
        "background",
        name=spec.name,
        description=spec.description or f"A fun place called {spec.name}.",
        aspect="4:3",
        tint=spec.tint,
    )
    emit("progress", {"stage": "painting"}, 0.1)
    for attempt in range(ATTEMPTS):
        image = _valid_place(
            provider.generate(prompt, PLACE_SIZE, spec.seed + attempt * 7919, None)
        )
        if image is not None:
            break
    else:
        raise JobFailed(f"We couldn't paint {spec.name}. Tap Lock to try again!")

    prefix = place_prefix(spec.id, spec.version)
    image_key = storage.save(f"{prefix}/reference.png", imaging.to_png(image))
    thumb_key = storage.save(
        f"{prefix}/thumb.png", imaging.to_png(imaging.thumbnail(image, THUMB_SIDE))
    )
    emit(
        "cell_ready",
        {"sheet": "place", "cell": "reference", "row": 0, "col": 0, "url": storage.url(thumb_key)},
        0.9,
    )
    return {"image_key": image_key, "thumb_key": thumb_key}


async def run_place_job(
    ctx: JobContext, *, spec: PlaceSpec, engine: Engine, provider: ImageProvider, storage: Storage
) -> dict[str, Any]:
    """Job work for POST /backgrounds/{id}/lock."""
    keys = await ctx.run(build_place, spec, provider, storage, ctx.emit_threadsafe)
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
    return {"target_id": spec.id, "version": spec.version}


def mark_failed(engine: Engine, background_id: str) -> None:
    with Session(engine) as session:
        bg = session.get(Background, background_id)
        if bg is not None and bg.status == "generating":
            bg.status = "failed"
            bg.updated_at = utcnow()
            session.add(bg)
            session.commit()
