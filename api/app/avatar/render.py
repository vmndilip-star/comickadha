"""Renders avatar SVG to PNG with resvg (no browser, no system fonts needed)."""

import resvg_py

from app.avatar.catalog import Catalog
from app.avatar.compose import Spec, compose_face, compose_pose, svg_document


def render_svg(svg: str, size: int) -> bytes:
    png: bytes = resvg_py.svg_to_bytes(
        svg_string=svg, width=size, height=size, skip_system_fonts=True
    )
    return png


def render_pose(
    spec: Spec,
    pose: str,
    size: int = 256,
    expression: str | None = None,
    catalog: Catalog | None = None,
) -> bytes:
    return render_svg(svg_document(compose_pose(spec, pose, expression, catalog), size), size)


def render_face(
    spec: Spec, expression: str, size: int = 256, catalog: Catalog | None = None
) -> bytes:
    return render_svg(svg_document(compose_face(spec, expression, catalog), size), size)
