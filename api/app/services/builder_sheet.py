"""SHEET_PROVIDER=builder: draws all 16 poses and 6 faces from the avatar's parts.

Every cell is the character's avatar spec rendered with resvg, the same SVG the Lab previews, so the
sheet matches the preview exactly. Head boxes come straight from the rig. Builder characters are
drawn directly in any pose with any expression, so nothing is pasted; the head boxes stay in the
manifest so the compositor contract doesn't change. A short pause per cell keeps the reveal visible.
"""

from typing import Any

from app.avatar import rig
from app.avatar import spec as avatar_spec
from app.avatar.render import render_face, render_pose
from app.schemas.common import EXPRESSIONS, POSES
from app.schemas.manifest import Box, HeadBox
from app.services import imaging
from app.services.character_sheet import CELL, FRONT, Emit, SheetCells, SheetSpec
from app.services.storage import Storage

STYLE = "builder-v1"


def as_fractions(box: rig.Box) -> Box:
    size = rig.CANVAS
    x, y, w, h = box
    return (round(x / size, 4), round(y / size, 4), round(w / size, 4), round(h / size, 4))


class BuilderSheets:
    name = "builder"

    def __init__(self, reveal_seconds: float = 0.0) -> None:
        self.reveal_seconds = reveal_seconds

    def build(self, spec: SheetSpec, storage: Storage, emit: Emit) -> dict[str, Any]:
        avatar = avatar_spec.normalize(spec.spec)
        out = SheetCells(spec, storage, emit, pause_seconds=self.reveal_seconds)

        emit("progress", {"stage": "front"}, 0.02)
        out.keep("body", FRONT, imaging.load(render_pose(avatar, FRONT, CELL[0])))
        emit("progress", {"stage": "poses"}, out.progress())
        for pose in POSES:
            if pose != FRONT:
                out.keep("body", pose, imaging.load(render_pose(avatar, pose, CELL[0])))

        emit("progress", {"stage": "faces"}, out.progress())
        for expression in EXPRESSIONS:
            out.keep("face", expression, imaging.load(render_face(avatar, expression, CELL[0])))

        body_type = avatar["body_type"]
        heads: dict[str, HeadBox] = {
            pose: HeadBox(box=as_fractions(rig.head_box(body_type, pose)), source="exact")
            for pose in POSES
        }
        return out.finish(
            heads,
            as_fractions(rig.face_cell_head_box()),
            renderer="builder",
            style=STYLE,
            manifest_spec=avatar,
        )
