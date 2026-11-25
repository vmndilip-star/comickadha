"""Character sheets: 16 body poses (4x4) and 6 faces (2x3), described by a manifest.

The sheet provider (services/builder_sheet.py, the only one since Cleanup 1) renders every cell
from the avatar's parts. Each cell is saved and announced as it arrives, so the Lab can show the
sheet filling in. Comics never use sheet images: panels draw every character from its pinned spec.
"""

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

from PIL import Image
from sqlalchemy import Engine
from sqlmodel import Session

from app.models import Character
from app.models.base import utcnow
from app.schemas.common import SHEET_EXPRESSIONS as EXPRESSIONS
from app.schemas.common import SHEET_POSES as POSES
from app.schemas.manifest import BodySheet, Box, CharacterManifest, FaceSheet, HeadBox
from app.services import imaging, looks
from app.services.jobs import JobContext, JobFailed
from app.services.storage import Storage

log = logging.getLogger(__name__)

BODY_GRID = (4, 4)
FACE_GRID = (2, 3)
CELL = (256, 256)
FRONT = "front"
FACE_VISIBLE = [p for p in POSES if p not in ("back", "side_left", "side_right")]

BODY_CELLS: dict[str, tuple[int, int]] = {p: divmod(i, BODY_GRID[1]) for i, p in enumerate(POSES)}
FACE_CELLS: dict[str, tuple[int, int]] = {
    e: divmod(i, FACE_GRID[1]) for i, e in enumerate(EXPRESSIONS)
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
            renderer="builder",
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


# ---- the job --------------------------------------------------------------------------------


async def run_sheet_job(
    ctx: JobContext,
    *,
    spec: SheetSpec,
    engine: Engine,
    sheets: SheetProvider,
    storage: Storage,
    after: Callable[[], str | None] | None = None,
) -> dict[str, Any]:
    """Job work for POST /characters/{id}/lock. `after` runs once the lock is saved (it starts the
    portrait job, decision 132, and returns its id); nothing it does can undo the lock."""
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
        # Freeze the look this version was locked with: comics drawn with it never change.
        looks.freeze(session, spec.id, spec.version, spec.spec)
        session.commit()
    portrait_job_id = None
    if after is not None:
        try:
            portrait_job_id = after()
        except Exception:
            log.exception("couldn't start the portrait for %s", spec.id)
    return {"target_id": spec.id, "version": spec.version, "portrait_job_id": portrait_job_id}


def mark_failed(engine: Engine, character_id: str) -> None:
    """The job failed: the kid can tap Lock again (old sheet versions are untouched)."""
    with Session(engine) as session:
        character = session.get(Character, character_id)
        if character is not None and character.status == "generating":
            character.status = "failed"
            character.updated_at = utcnow()
            session.add(character)
            session.commit()
