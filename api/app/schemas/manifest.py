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
    # Where each pose's head is, so the compositor can paste an expression onto it.
    heads: dict[str, HeadBox] = {}
    # Poses that face the viewer enough to get an expression pasted on.
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
    # "builder": drawn from the avatar spec below, so any pose can be redrawn with any expression.
    # "image": drawn by an image model; expressions are pasted onto the head boxes.
    renderer: Literal["builder", "image"] = "image"
    spec: dict[str, Any]
    body_sheet: BodySheet
    face_sheet: FaceSheet
    thumb_url: str | None = None
