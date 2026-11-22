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
from app.providers.image import ImageError, ImageProvider
from app.providers.llm import LLMProvider
from app.services import imaging, safety
from app.services.jobs import JobContext, JobFailed
from app.services.safety import Verdict
from app.services.storage import Storage

PLACE_SIZE = (1024, 768)  # 4:3, the same shape as a comic panel
THUMB_SIDE = 320
ATTEMPTS = 2

Emit = Callable[[str, dict[str, Any], float | None], None]
Check = Callable[[bytes], Verdict]

# Places have a "Paint it again" button (and Delete) on their tile.
CANT_PAINT = "We couldn't paint {name}. Tap Paint it again!"
CHECKER_RESTING = (
    "Our picture checker is taking a break, so {name} isn't painted yet. "
    "Tap Paint it again in a minute!"
)


def needs_image_check(provider: ImageProvider) -> bool:
    """Pictures from any real image model are checked; the mock's are drawn on this machine."""
    return provider.name != "mock"


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
    spec: PlaceSpec,
    provider: ImageProvider,
    storage: Storage,
    emit: Emit,
    check: Check | None = None,
) -> dict[str, str]:
    """Paints, validates and (with `check`) checks the picture, then saves it. Blocking."""
    prompt = render(
        "background",
        name=spec.name,
        description=spec.description or f"A fun place called {spec.name}.",
        aspect="4:3",
        tint=spec.tint,
    )
    emit("progress", {"stage": "painting"}, 0.1)
    png: bytes | None = None
    for attempt in range(ATTEMPTS):
        try:
            image = _valid_place(
                provider.generate(prompt, PLACE_SIZE, spec.seed + attempt * 7919, None)
            )
        except ImageError:
            image = None
        if image is None:
            continue
        candidate = imaging.to_png(image)
        if check is None:
            png = candidate
            break
        emit("progress", {"stage": "checking"}, 0.6)
        verdict = check(candidate)
        if "unavailable" in verdict.categories:
            raise JobFailed(CHECKER_RESTING.format(name=spec.name))
        if verdict.allowed:
            png = candidate
            break
        if "text" in verdict.categories:
            prompt = prompt + "\n\n" + render("background_no_text")
    if png is None:
        raise JobFailed(CANT_PAINT.format(name=spec.name))

    prefix = place_prefix(spec.id, spec.version)
    image_key = storage.save(f"{prefix}/reference.png", png)
    thumb = imaging.thumbnail(imaging.load(png), THUMB_SIDE)
    thumb_key = storage.save(f"{prefix}/thumb.png", imaging.to_png(thumb))
    emit(
        "cell_ready",
        {"sheet": "place", "cell": "reference", "row": 0, "col": 0, "url": storage.url(thumb_key)},
        0.9,
    )
    return {"image_key": image_key, "thumb_key": thumb_key}


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
    check: Check | None = None
    if needs_image_check(provider):
        if llm is None:  # startup refuses this; fail closed anyway
            raise JobFailed(CHECKER_RESTING.format(name=spec.name))
        checker = llm

        def check(png: bytes) -> Verdict:
            with Session(engine) as session:
                target = f"background:{spec.id}:v{spec.version}"
                return safety.check_image(session, user_id, target, png, checker)

    keys = await ctx.run(build_place, spec, provider, storage, ctx.emit_threadsafe, check)
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
