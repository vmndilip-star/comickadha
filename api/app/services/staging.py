"""PanelRead.stage: what a panel draws and where (services/stage.py), for the web app's previews.

The Studio's panel cards and the Reader's sketches draw exactly what the art will: characters in
their drawn pose (a front pose may turn three-quarter), props from their cached pictures (in the
hand, on a head, on the ground), and a sleeping character's "Zzz".
"""

import json
from typing import Any

from app.models import Panel
from app.props import images
from app.schemas.comic import PanelStage, StageLayer
from app.services import stage
from app.services.storage import Storage


def _box(box: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
    x, y, w, h = box
    return (round(x, 4), round(y, 4), round(w, 4), round(h, 4))


def stage_key(
    characters: list[dict[str, Any]], props: list[dict[str, Any]], size: str | None
) -> str:
    """What the layout depends on besides faces and poses: who stands where, the props, the size.
    The web app builds the same string (web/src/lib/stage.ts stageKey) to tell a stale stage."""
    lineup = [[str(c["id"]), str(c.get("position", "center"))] for c in characters]
    things = [
        [
            str(p.get("id")),
            str(p.get("state")),
            str(p.get("position") or ""),
            str(p.get("held_by") or ""),
        ]
        for p in props
    ]
    return json.dumps([lineup, things, size or "normal"], separators=(",", ":"))


def panel_stage(panel: Panel, specs: dict[str, dict[str, Any]], storage: Storage) -> PanelStage:
    laid = stage.layout(panel.characters, specs, panel.props or [], panel.shown_size, panel.bubbles)
    layers: list[StageLayer] = []
    for kind, index in laid.order:
        if kind == "character":
            p = laid.characters[index]
            layers.append(
                StageLayer.model_validate(
                    {
                        "kind": "character",
                        "id": p.id,
                        "box": _box(p.cell),
                        "flip": p.mirror,
                        "pose": p.pose,
                        "expression": p.expression,
                    }  # fmt: skip
                )
            )
            continue
        pp = laid.props[index]
        layers.append(
            StageLayer.model_validate(
                {
                    "kind": "prop",
                    "id": pp.id,
                    "box": _box(pp.box),
                    "flip": pp.flip,
                    "rotate": pp.rotate,
                    "origin": (round(pp.origin[0], 4), round(pp.origin[1], 4)),
                    "state": pp.state,
                    "image_url": storage.url(images.image_key(pp.id, pp.state)),
                }
            )
        )
    for effect in laid.effects:
        layers.append(StageLayer(kind="effect", id=effect.kind, box=_box(effect.box)))
    source = stage_key(panel.characters, panel.props or [], panel.shown_size)
    return PanelStage(aspect=round(laid.frame.aspect, 4), layers=layers, source=source)
