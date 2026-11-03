from typing import Any

from pydantic import BaseModel


class SheetInfo(BaseModel):
    url: str
    grid: tuple[int, int]  # rows, cols
    cell: tuple[int, int]  # width, height in pixels
    cells: dict[str, tuple[int, int]]  # cell name -> (row, col)


class CharacterManifest(BaseModel):
    """Describes a locked character's sheets. Stored on the character and beside the sheets."""

    id: str
    name: str
    locked: bool
    version: int
    seed: int
    style: str
    spec: dict[str, Any]
    body_sheet: SheetInfo
    face_sheet: SheetInfo
