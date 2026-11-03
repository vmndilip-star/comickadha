"""Character sheets: a 4x4 body sheet and a 2x3 face sheet, described by a manifest.

Phase 2 renders the sheets in one call each (placeholders for seeded characters).
Phase 3 adds the real pipeline: front view first, reference-guided batches,
validate, slice, key out.
"""

from app.models import Character
from app.providers.image import ImageProvider, ImageRequest
from app.schemas.common import EXPRESSIONS, POSES
from app.schemas.manifest import CharacterManifest, SheetInfo
from app.services.storage import Storage

BODY_GRID = (4, 4)
FACE_GRID = (2, 3)
CELL = (256, 256)

BODY_CELLS: dict[str, tuple[int, int]] = {
    pose: divmod(i, BODY_GRID[1]) for i, pose in enumerate(POSES)
}
FACE_CELLS: dict[str, tuple[int, int]] = {
    expr: divmod(i, FACE_GRID[1]) for i, expr in enumerate(EXPRESSIONS)
}


def sheet_prefix(character_id: str, version: int) -> str:
    return f"characters/{character_id}/v{version}"


def build_placeholder_manifest(
    character: Character, storage: Storage, provider: ImageProvider
) -> dict[str, object]:
    """Renders both sheets for the current sheet_version; returns the manifest as JSON data."""
    version = max(character.sheet_version, 1)
    prefix = sheet_prefix(character.id, version)
    hints = {
        "skin": character.spec.get("skin", "#F2C29B"),
        "tint": character.spec.get("tint", "#9AD0F5"),
        "hair": character.spec.get("hair_color", "#1A1A1A"),
    }

    sheets: dict[str, SheetInfo] = {}
    for name, grid, cells in (("body", BODY_GRID, BODY_CELLS), ("face", FACE_GRID, FACE_CELLS)):
        png = provider.generate(
            ImageRequest(
                prompt=f"{character.name} {name} sheet",
                width=CELL[0] * grid[1],
                height=CELL[1] * grid[0],
                seed=character.seed,
                grid=grid,
                labels=list(cells),
                hints={**hints, "sheet": name},
            )
        )
        key = storage.save(f"{prefix}/{name}_sheet.png", png)
        sheets[name] = SheetInfo(url=storage.url(key), grid=grid, cell=CELL, cells=cells)

    manifest = CharacterManifest(
        id=character.id,
        name=character.name,
        locked=True,
        version=version,
        seed=character.seed,
        style=character.style,
        spec={"kind": character.kind, "role": character.role, **character.spec},
        body_sheet=sheets["body"],
        face_sheet=sheets["face"],
    )
    storage.save(f"{prefix}/manifest.json", manifest.model_dump_json(indent=2).encode())
    return manifest.model_dump(mode="json")
