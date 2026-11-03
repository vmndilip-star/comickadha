"""Character sheets: 16 body poses (4x4) and 6 faces (2x3), described by a manifest.

Pipeline: the front view first; then the other 15 poses in batches of 4, each with the front view as
the reference image; then the 6 faces. Every batch is validated (right size, every cell drawn on a
magenta background) and retried once before the job fails. Cells are keyed to transparency, sliced,
saved, and announced as they arrive, so the Lab can show the sheet filling in live.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from PIL import Image
from sqlalchemy import Engine
from sqlmodel import Session

from app.models import Character
from app.models.base import utcnow
from app.prompts import render
from app.providers.image import ImageProvider, KnowsHeadBoxes
from app.schemas.common import EXPRESSIONS, POSES
from app.schemas.manifest import BodySheet, Box, CharacterManifest, FaceSheet, HeadBox
from app.services import imaging
from app.services.jobs import JobContext, JobFailed
from app.services.storage import Storage

BODY_GRID = (4, 4)
FACE_GRID = (2, 3)
CELL = (256, 256)
FRONT = "front"
BATCH_SIZE = 4
BATCHES = [list(POSES[i : i + BATCH_SIZE]) for i in range(1, len(POSES), BATCH_SIZE)]
FACE_VISIBLE = [p for p in POSES if p not in ("back", "side_left", "side_right")]

# A cell is valid if the character covers between 3% and 92% of it after keying.
MIN_COVERAGE, MAX_COVERAGE = 0.03, 0.92
ATTEMPTS = 2

BODY_CELLS: dict[str, tuple[int, int]] = {p: divmod(i, BODY_GRID[1]) for i, p in enumerate(POSES)}
FACE_CELLS: dict[str, tuple[int, int]] = {
    e: divmod(i, FACE_GRID[1]) for i, e in enumerate(EXPRESSIONS)
}
KIND_LABELS = {
    "kid": "kid",
    "grown_up": "grown-up",
    "animal": "friendly animal",
    "robot": "friendly robot",
}

Emit = Callable[[str, dict[str, Any], float | None], None]


@dataclass(frozen=True)
class SheetSpec:
    """A snapshot of the character, so the pipeline never touches the database from its thread."""

    id: str
    name: str
    kind: str
    role: str
    seed: int
    style: str
    spec: dict[str, Any]
    version: int

    @classmethod
    def of(cls, character: Character, version: int) -> "SheetSpec":
        return cls(
            id=character.id,
            name=character.name,
            kind=character.kind,
            role=character.role,
            seed=character.seed,
            style=character.style,
            spec=dict(character.spec),
            version=version,
        )


def sheet_prefix(character_id: str, version: int) -> str:
    return f"characters/{character_id}/v{version}"


def _prompt(
    spec: SheetSpec,
    sheet: str,
    task: str,
    grid: tuple[int, int],
    cells: Sequence[str],
    with_reference: bool,
) -> str:
    s = spec.spec
    hair = (
        ""
        if spec.kind in ("robot", "animal")
        else f" {s['hair_style'].title()} hair, colour {s['hair_color']}."
    )
    return render(
        "character_sheet",
        name=spec.name,
        kind_label=KIND_LABELS.get(spec.kind, spec.kind),
        role=spec.role,
        look=f"Skin or body colour {s['skin']}.{hair}",
        outfit=s.get("outfit") or "simple everyday clothes",
        reference_line=(
            "Keep the character identical to the reference image: "
            "same colours, outfit and proportions."
            if with_reference
            else ""
        ),
        sheet=sheet,
        task=task,
        rows=grid[0],
        cols=grid[1],
        cells=" | ".join(cells),
        kind=spec.kind,
        skin=s["skin"],
        hair_color=s["hair_color"],
        hair_style=s["hair_style"],
        tint=s["tint"],
    )


def validated_cells(
    png: bytes, size: tuple[int, int], grid: tuple[int, int], names: Sequence[str]
) -> dict[str, Image.Image] | None:
    """Keyed cells if the image is the right shape and every cell has a drawing; else None."""
    try:
        image = imaging.fit_size(imaging.load(png), size)
    except OSError:
        return None
    if image is None:
        return None
    cells = imaging.slice_grid(imaging.key_magenta(image), grid, names)
    if all(MIN_COVERAGE <= imaging.coverage(c) <= MAX_COVERAGE for c in cells.values()):
        return cells
    return None


def draw_cells(
    provider: ImageProvider,
    prompt: str,
    grid: tuple[int, int],
    names: Sequence[str],
    seed: int,
    references: list[bytes] | None,
    what: str,
) -> tuple[dict[str, Image.Image], bytes]:
    """One batch: generate, validate, and retry once with a new seed before giving up."""
    size = (grid[1] * CELL[0], grid[0] * CELL[1])
    for attempt in range(ATTEMPTS):
        png = provider.generate(prompt, size, seed + attempt * 7919, references)
        cells = validated_cells(png, size, grid, names)
        if cells is not None:
            return cells, png
    raise JobFailed(f"We couldn't draw {what}. Tap Lock to try again!")


def build_sheet(
    spec: SheetSpec, provider: ImageProvider, storage: Storage, emit: Emit
) -> dict[str, Any]:
    """Runs the whole pipeline (blocking) and returns the manifest as JSON data."""
    prefix = sheet_prefix(spec.id, spec.version)
    total = len(POSES) + len(EXPRESSIONS)
    body: dict[str, Image.Image] = {}
    faces: dict[str, Image.Image] = {}
    body_urls: dict[str, str] = {}
    face_urls: dict[str, str] = {}

    def progress() -> float:
        return round(0.05 + 0.9 * (len(body) + len(faces)) / total, 3)

    def keep(sheet: str, name: str, image: Image.Image) -> None:
        url = storage.url(storage.save(f"{prefix}/cells/{sheet}/{name}.png", imaging.to_png(image)))
        target, urls, cells = (
            (body, body_urls, BODY_CELLS) if sheet == "body" else (faces, face_urls, FACE_CELLS)
        )
        target[name] = image
        urls[name] = url
        row, col = cells[name]
        emit(
            "cell_ready",
            {"sheet": sheet, "cell": name, "row": row, "col": col, "url": url},
            progress(),
        )

    # 1. The front view: every other drawing must match it.
    emit("progress", {"stage": "front"}, 0.02)
    task = "the character standing, facing the viewer"
    cells, front_png = draw_cells(
        provider,
        _prompt(spec, "body", task, (1, 1), [FRONT], False),
        (1, 1),
        [FRONT],
        spec.seed,
        None,
        f"{spec.name}'s front view",
    )
    storage.save(f"{prefix}/raw/front.png", front_png)
    keep("body", FRONT, cells[FRONT])

    # 2. The other 15 poses, 4 at a time, with the front view as the reference.
    emit("progress", {"stage": "poses"}, progress())
    for i, batch in enumerate(BATCHES, start=1):
        grid = (1, len(batch))
        prompt = _prompt(spec, "body", "the same character in these poses", grid, batch, True)
        cells, raw = draw_cells(
            provider, prompt, grid, batch, spec.seed + i, [front_png], f"all of {spec.name}'s poses"
        )
        storage.save(f"{prefix}/raw/poses-{i}.png", raw)
        for pose in batch:
            keep("body", pose, cells[pose])

    # 3. The 6 expression faces.
    emit("progress", {"stage": "faces"}, progress())
    names = list(EXPRESSIONS)
    task = "close-up heads of the same character showing these expressions"
    cells, raw = draw_cells(
        provider,
        _prompt(spec, "faces", task, FACE_GRID, names, True),
        FACE_GRID,
        names,
        spec.seed + 99,
        [front_png],
        f"{spec.name}'s faces",
    )
    storage.save(f"{prefix}/raw/faces.png", raw)
    for expression in names:
        keep("face", expression, cells[expression])

    # 4. Sheets, thumbnail, head boxes and the manifest.
    emit("progress", {"stage": "finishing"}, 0.97)
    body_key = storage.save(
        f"{prefix}/body_sheet.png", imaging.to_png(imaging.assemble(body, BODY_GRID, list(POSES)))
    )
    face_key = storage.save(
        f"{prefix}/face_sheet.png", imaging.to_png(imaging.assemble(faces, FACE_GRID, names))
    )
    thumb_key = storage.save(
        f"{prefix}/thumb.png", imaging.to_png(imaging.thumbnail(body[FRONT], 160))
    )

    exact = provider if isinstance(provider, KnowsHeadBoxes) else None
    heads: dict[str, HeadBox] = {}
    for pose in POSES:
        box = exact.head_box(f"body/{pose}") if exact else None
        heads[pose] = HeadBox(
            box=box or imaging.estimate_head_box(body[pose]), source="exact" if box else "estimated"
        )
    face_box: Box | None = (exact.head_box("face/happy") if exact else None) or imaging.alpha_box(
        faces["happy"]
    )

    manifest = CharacterManifest(
        id=spec.id,
        name=spec.name,
        locked=True,
        version=spec.version,
        seed=spec.seed,
        style=spec.style,
        spec={"kind": spec.kind, "role": spec.role, **spec.spec},
        body_sheet=BodySheet(
            url=storage.url(body_key),
            grid=BODY_GRID,
            cell=CELL,
            cells=BODY_CELLS,
            cell_urls=body_urls,
            heads=heads,
            face_visible=FACE_VISIBLE,
        ),
        face_sheet=FaceSheet(
            url=storage.url(face_key),
            grid=FACE_GRID,
            cell=CELL,
            cells=FACE_CELLS,
            cell_urls=face_urls,
            head_box=face_box,
        ),
        thumb_url=storage.url(thumb_key),
    )
    storage.save(f"{prefix}/manifest.json", manifest.model_dump_json(indent=2).encode())
    return manifest.model_dump(mode="json")


async def run_sheet_job(
    ctx: JobContext, *, spec: SheetSpec, engine: Engine, provider: ImageProvider, storage: Storage
) -> dict[str, Any]:
    """Job work for POST /characters/{id}/lock."""
    manifest = await ctx.run(build_sheet, spec, provider, storage, ctx.emit_threadsafe)
    with Session(engine) as session:
        character = session.get(Character, spec.id)
        if character is None:
            raise JobFailed("We couldn't find that character any more.")
        character.manifest = manifest
        character.sheet_version = spec.version
        character.status = "locked"
        character.updated_at = utcnow()
        session.add(character)
        session.commit()
    return {"target_id": spec.id, "version": spec.version}


def mark_failed(engine: Engine, character_id: str) -> None:
    """The job failed: the kid can tap Lock again (old sheet versions are untouched)."""
    with Session(engine) as session:
        character = session.get(Character, character_id)
        if character is not None and character.status == "generating":
            character.status = "failed"
            character.updated_at = utcnow()
            session.add(character)
            session.commit()
