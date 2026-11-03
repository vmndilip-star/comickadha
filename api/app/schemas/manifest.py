from typing import Any, Literal

from pydantic import BaseModel, Field

Box = tuple[float, float, float, float]  # x, y, w, h as fractions of a cell


class HeadOffset(BaseModel):
    """Kid-editable nudge for a head box: fractions of the cell; scale grows from the centre."""

    dx: float = Field(default=0.0, ge=-0.5, le=0.5)
    dy: float = Field(default=0.0, ge=-0.5, le=0.5)
    scale: float = Field(default=1.0, ge=0.5, le=2.0)


class HeadBox(BaseModel):
    box: Box
    # "exact" when the image provider knows where it drew the head (the mock), else "estimated".
    source: Literal["exact", "estimated"]
    offset: HeadOffset = HeadOffset()


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
    spec: dict[str, Any]
    body_sheet: BodySheet
    face_sheet: FaceSheet
    thumb_url: str | None = None
