"""Character sheets: 16 body poses (4x4) and 6 faces (2x3), described by a manifest.

Two sheet providers fill the same manifest (chosen by SHEET_PROVIDER):
- "builder" (default, services/builder_sheet.py) renders every cell from the avatar's parts.
- "image" (this module) asks an image model: the front view first; then the other 15 poses in
  batches of 4, each with the front view as the reference image; then the 6 faces. Every batch is
  validated (right size, every cell drawn on a magenta background) and retried once before the job
  fails. Cells are keyed to transparency and sliced.
Either way each cell is saved and announced as it arrives, so the Lab can show the sheet filling in.
"""

import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

from PIL import Image
from sqlalchemy import Engine
from sqlmodel import Session

from app.avatar import spec as avatar_spec
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
# Hair styles the mock image provider knows how to draw.
MOCK_HAIR = ("bob", "spiky", "braids", "curly")

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


class SheetProvider(Protocol):
    name: str

    def build(self, spec: SheetSpec, storage: Storage, emit: Emit) -> dict[str, Any]:
        """Draws all 22 cells (blocking), saves them, and returns the manifest as JSON data."""
        ...


def sheet_prefix(character_id: str, version: int) -> str:
    return f"characters/{character_id}/v{version}"


@dataclass
class SheetCells:
    """Saves cells as they arrive and announces each one as a cell_ready event."""

    spec: SheetSpec
    storage: Storage
    emit: Emit
    pause_seconds: float = 0.0
    body: dict[str, Image.Image] = field(default_factory=dict)
    faces: dict[str, Image.Image] = field(default_factory=dict)
    body_urls: dict[str, str] = field(default_factory=dict)
    face_urls: dict[str, str] = field(default_factory=dict)

    @property
    def prefix(self) -> str:
        return sheet_prefix(self.spec.id, self.spec.version)

    def progress(self) -> float:
        total = len(POSES) + len(EXPRESSIONS)
        return round(0.05 + 0.9 * (len(self.body) + len(self.faces)) / total, 3)

    def keep(self, sheet: Literal["body", "face"], name: str, image: Image.Image) -> None:
        key = f"{self.prefix}/cells/{sheet}/{name}.png"
        url = self.storage.url(self.storage.save(key, imaging.to_png(image)))
        target, urls, cells = (
            (self.body, self.body_urls, BODY_CELLS)
            if sheet == "body"
            else (self.faces, self.face_urls, FACE_CELLS)
        )
        target[name] = image
        urls[name] = url
        row, col = cells[name]
        self.emit(
            "cell_ready",
            {"sheet": sheet, "cell": name, "row": row, "col": col, "url": url},
            self.progress(),
        )
        if self.pause_seconds:
            time.sleep(self.pause_seconds)

    def finish(
        self,
        heads: dict[str, HeadBox],
        face_box: Box | None,
        *,
        renderer: Literal["builder", "image"],
        style: str,
        manifest_spec: dict[str, Any],
    ) -> dict[str, Any]:
        """Sheets, thumbnail and the manifest (stored on disk too, for old versions)."""
        self.emit("progress", {"stage": "finishing"}, 0.97)
        body_key = self.storage.save(
            f"{self.prefix}/body_sheet.png",
            imaging.to_png(imaging.assemble(self.body, BODY_GRID, list(POSES))),
        )
        face_key = self.storage.save(
            f"{self.prefix}/face_sheet.png",
            imaging.to_png(imaging.assemble(self.faces, FACE_GRID, list(EXPRESSIONS))),
        )
        thumb_key = self.storage.save(
            f"{self.prefix}/thumb.png", imaging.to_png(imaging.thumbnail(self.body[FRONT], 160))
        )
        manifest = CharacterManifest(
            id=self.spec.id,
            name=self.spec.name,
            locked=True,
            version=self.spec.version,
            seed=self.spec.seed,
            style=style,
            renderer=renderer,
            spec=manifest_spec,
            body_sheet=BodySheet(
                url=self.storage.url(body_key),
                grid=BODY_GRID,
                cell=CELL,
                cells=BODY_CELLS,
                cell_urls=self.body_urls,
                heads=heads,
                face_visible=FACE_VISIBLE,
            ),
            face_sheet=FaceSheet(
                url=self.storage.url(face_key),
                grid=FACE_GRID,
                cell=CELL,
                cells=FACE_CELLS,
                cell_urls=self.face_urls,
                head_box=face_box,
            ),
            thumb_url=self.storage.url(thumb_key),
        )
        self.storage.save(
            f"{self.prefix}/manifest.json", manifest.model_dump_json(indent=2).encode()
        )
        return manifest.model_dump(mode="json")


# ---- the image-model provider ---------------------------------------------------------------


class ImageSheets:
    """SHEET_PROVIDER=image: an image model draws the sheet; faces are pasted onto head boxes."""

    name = "image"

    def __init__(self, provider: ImageProvider) -> None:
        self.provider = provider

    def build(self, spec: SheetSpec, storage: Storage, emit: Emit) -> dict[str, Any]:
        return build_sheet(spec, self.provider, storage, emit)


def _prompt(
    spec: SheetSpec,
    sheet: str,
    task: str,
    grid: tuple[int, int],
    cells: Sequence[str],
    with_reference: bool,
) -> str:
    s = avatar_spec.normalize(spec.spec)
    look = avatar_spec.describe(s)
    hair = s["parts"].get("hair", "")
    return render(
        "character_sheet",
        name=spec.name,
        kind_label=KIND_LABELS.get(spec.kind, spec.kind),
        role=spec.role,
        look=look[0].upper() + look[1:] + ".",
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
        skin=s["colors"]["skin"],
        hair_color=s["colors"]["hair"],
        hair_style=hair if hair in MOCK_HAIR else "curly",
        tint=s["colors"]["top"],
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
    """Runs the whole image pipeline (blocking) and returns the manifest as JSON data."""
    out = SheetCells(spec, storage, emit)
    prefix = out.prefix

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
    out.keep("body", FRONT, cells[FRONT])

    # 2. The other 15 poses, 4 at a time, with the front view as the reference.
    emit("progress", {"stage": "poses"}, out.progress())
    for i, batch in enumerate(BATCHES, start=1):
        grid = (1, len(batch))
        prompt = _prompt(spec, "body", "the same character in these poses", grid, batch, True)
        cells, raw = draw_cells(
            provider, prompt, grid, batch, spec.seed + i, [front_png], f"all of {spec.name}'s poses"
        )
        storage.save(f"{prefix}/raw/poses-{i}.png", raw)
        for pose in batch:
            out.keep("body", pose, cells[pose])

    # 3. The 6 expression faces.
    emit("progress", {"stage": "faces"}, out.progress())
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
        out.keep("face", expression, cells[expression])

    # 4. Head boxes (exact if the provider knows them, else estimated) and the manifest.
    exact = provider if isinstance(provider, KnowsHeadBoxes) else None
    heads: dict[str, HeadBox] = {}
    for pose in POSES:
        box = exact.head_box(f"body/{pose}") if exact else None
        heads[pose] = HeadBox(
            box=box or imaging.estimate_head_box(out.body[pose]),
            source="exact" if box else "estimated",
        )
    face_box: Box | None = (exact.head_box("face/happy") if exact else None) or imaging.alpha_box(
        out.faces["happy"]
    )
    return out.finish(
        heads,
        face_box,
        renderer="image",
        style=spec.style,
        manifest_spec={"kind": spec.kind, "role": spec.role, **spec.spec},
    )


# ---- the job --------------------------------------------------------------------------------


async def run_sheet_job(
    ctx: JobContext, *, spec: SheetSpec, engine: Engine, sheets: SheetProvider, storage: Storage
) -> dict[str, Any]:
    """Job work for POST /characters/{id}/lock."""
    manifest = await ctx.run(sheets.build, spec, storage, ctx.emit_threadsafe)
    with Session(engine) as session:
        character = session.get(Character, spec.id)
        if character is None:
            raise JobFailed("We couldn't find that character any more.")
        character.manifest = manifest
        character.sheet_version = spec.version
        character.style = manifest["style"]
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
