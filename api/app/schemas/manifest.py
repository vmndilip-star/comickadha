from typing import Any, Literal

from pydantic import BaseModel

Box = tuple[float, float, float, float]  # x, y, w, h as fractions of a cell


class HeadBox(BaseModel):
    box: Box
    # "exact" for builder sheets (from the rig); "estimated" only in old image-model manifests.
    # Old manifests may also carry an `offset` (the removed head nudges): it is ignored.
    source: Literal["exact", "estimated"]


class SheetInfo(BaseModel):
    url: str
    grid: tuple[int, int]  # rows, cols
    cell: tuple[int, int]  # width, height in pixels
    cells: dict[str, tuple[int, int]]  # cell name -> (row, col)
    # One transparent PNG per cell.
    cell_urls: dict[str, str] = {}


class BodySheet(SheetInfo):
    # Where each pose's head is (exact, from the rig, for builder sheets). A record only:
    # panels and bubbles work their head positions out from the pinned spec (stage.py).
    heads: dict[str, HeadBox] = {}
    # Poses whose face shows (the face-sheet expressions apply to them).
    face_visible: list[str] = []


class FaceSheet(SheetInfo):
    # Where the head sits inside every face cell.
    head_box: Box | None = None


class CharacterManifest(BaseModel):
    """One version of a locked character's sheets. Stored on the character and as manifest.json."""

    id: str
    name: str
    locked: bool
    version: int
    seed: int
    style: str
    # "builder": drawn from the avatar spec below (every sheet since Phase 3.5).
    # "image": an old image-model sheet from Phase 3; still read so those characters display.
    renderer: Literal["builder", "image"] = "image"
    spec: dict[str, Any]
    body_sheet: BodySheet
    face_sheet: FaceSheet
    thumb_url: str | None = None
    # The painted portrait of this version (decision 132), once Muse (or the mock) painted one.
    portrait_url: str | None = None
    portrait_thumb_url: str | None = None
