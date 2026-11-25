"""Prop pictures: each prop state drawn as a transparent PNG (app/props/library.py has the art).

`render_state` turns a prop state into a transparent PNG at any size with resvg (the same renderer
as the characters, so the outlines match). Each state's picture is made once and cached: in memory
for the compositor, and as a file in storage (`props/<style>/<id>/<state>.png`) that the web app
shows in the Studio and the Reader's sketches (`ensure_images`, called at startup).
"""

from functools import lru_cache

import resvg_py

from app.props.library import PROPS, PropState
from app.services.storage import Storage

# Bumped when any prop drawing changes, so cached files are made again.
STYLE = "props-v2"  # v2: a smaller, fainter torch beam
FILE_HEIGHT = 480  # px, the cached file's height (enough for a splash panel)

__all__ = ["ensure_images", "image_key", "render_state"]


def svg(state: PropState) -> str:
    x, y, w, h = state.box
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{x} {y} {w} {h}">{state.svg}</svg>'


@lru_cache(maxsize=256)
def render_state(prop_id: str, state_id: str, width: int, height: int) -> bytes:
    """The state's drawing as a transparent PNG of exactly width x height (its box, stretched to
    fit: callers keep the box's shape)."""
    state = PROPS[prop_id].states[state_id]
    png: bytes = resvg_py.svg_to_bytes(
        svg_string=svg(state), width=max(1, width), height=max(1, height), skip_system_fonts=True
    )
    return png


def file_size(state: PropState) -> tuple[int, int]:
    _x, _y, w, h = state.box
    return max(1, round(FILE_HEIGHT * w / h)), FILE_HEIGHT


def image_key(prop_id: str, state_id: str) -> str:
    return f"props/{STYLE}/{prop_id}/{state_id}.png"


def ensure_images(storage: Storage) -> None:
    """Draws every prop state's file once (the next start finds them and does nothing)."""
    for prop in PROPS.values():
        for state_id, state in prop.states.items():
            key = image_key(prop.id, state_id)
            if not storage.exists(key):
                storage.save(key, render_state(prop.id, state_id, *file_size(state)))
