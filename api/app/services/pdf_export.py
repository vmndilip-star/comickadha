"""The comic as a PDF, built with Pillow from the panels' final.png files.

One page size for everyone: 8.27 x 11 in (A4's width, Letter's height) at 150 dpi, so it prints on
A4 or Letter with "Fit to page". Page 1 is the cover: the title, panel 1, the cast drawn from their
pinned looks, and "Made with Comickatha". Then 6 panels per page, 2 per row, with page numbers. All
lettering uses the bundled fonts (api/assets/fonts), drawn into the pages.
"""

import io
from dataclasses import dataclass
from typing import Any

from PIL import Image, ImageDraw

from app.avatar.render import render_pose
from app.services import lettering

DPI = 150
PAGE_W, PAGE_H = round(8.27 * DPI), round(11 * DPI)  # 1240 x 1650
MARGIN = 75
GUTTER = 30
COLS, ROWS = 2, 3
PER_PAGE = COLS * ROWS
PAPER = (255, 251, 240)  # the app's cream
INK = (26, 26, 26)
SUN = (255, 210, 63)
BORDER = 4


@dataclass(frozen=True)
class CastMember:
    name: str
    spec: dict[str, Any]


def page_count(panels: int) -> int:
    return 1 + -(-panels // PER_PAGE)


def _centered(draw: ImageDraw.ImageDraw, y: float, text: str, kind: str, px: int) -> int:
    """Draws one line centred across the page; returns the font size used (shrunk to fit)."""
    f = lettering.font(kind, px)
    while f.getlength(text) > PAGE_W - 2 * MARGIN and px > 20:
        px -= 4
        f = lettering.font(kind, px)
    draw.text(((PAGE_W - f.getlength(text)) / 2, y), text, font=f, fill=INK)
    return px


def cover_page(title: str, cast: list[CastMember], hero: bytes | None = None) -> Image.Image:
    """The title on a sun band, panel 1 as the cover picture, the cast, "Made with Comickatha"."""
    page = Image.new("RGB", (PAGE_W, PAGE_H), PAPER)
    draw = ImageDraw.Draw(page)
    band = 340
    draw.rectangle((0, 0, PAGE_W, band), fill=SUN)
    draw.line((0, band, PAGE_W, band), fill=INK, width=BORDER * 2)
    shown = title.strip() or "My Comic"
    lines = lettering.wrap(shown, lettering.font("title", 110), PAGE_W - 2 * MARGIN)[:3]
    size = 110 if len(lines) == 1 else 88
    top = band / 2 - len(lines) * size * 0.55
    for i, line in enumerate(lines):
        _centered(draw, top + i * size * 1.05, line, "title", size)

    y = band + 50
    if hero:
        w = 860
        h = w * 3 // 4
        x = (PAGE_W - w) // 2
        with Image.open(io.BytesIO(hero)) as source:
            picture = source.convert("RGB").resize((w, h), Image.Resampling.LANCZOS)
        page.paste(picture, (x, y))
        draw.rectangle((x, y, x + w - 1, y + h - 1), outline=INK, width=BORDER)
        y += h + 40
    if cast:
        side = min(280 if hero else 420, (PAGE_W - 2 * MARGIN) // len(cast))
        left = (PAGE_W - side * len(cast)) / 2
        f = lettering.font("talk", 30)
        for i, member in enumerate(cast):
            png = render_pose(member.spec, "front", side, "happy")
            with Image.open(io.BytesIO(png)) as cell:
                figure = cell.convert("RGBA")
            x = round(left + i * side)
            page.paste(figure, (x, y), figure)
            name = member.name
            draw.text((x + (side - f.getlength(name)) / 2, y + side), name, font=f, fill=INK)
    _centered(draw, PAGE_H - 150, "Made with Comickatha", "title", 64)
    return page


def panel_page(finals: list[bytes], number: int) -> Image.Image:
    page = Image.new("RGB", (PAGE_W, PAGE_H), PAPER)
    draw = ImageDraw.Draw(page)
    w = (PAGE_W - 2 * MARGIN - GUTTER * (COLS - 1)) // COLS
    h = w * 3 // 4
    top = (PAGE_H - (h * ROWS + GUTTER * (ROWS - 1))) // 2 - 20
    for i, png in enumerate(finals):
        col, row = i % COLS, i // COLS
        x, y = MARGIN + col * (w + GUTTER), top + row * (h + GUTTER)
        with Image.open(io.BytesIO(png)) as source:
            panel = source.convert("RGB").resize((w, h), Image.Resampling.LANCZOS)
        page.paste(panel, (x, y))
        draw.rectangle((x, y, x + w - 1, y + h - 1), outline=INK, width=BORDER)
    f = lettering.font("talk", 30)
    label = str(number)
    draw.text(((PAGE_W - f.getlength(label)) / 2, PAGE_H - 80), label, font=f, fill=INK)
    return page


def build_pdf(title: str, cast: list[CastMember], finals: list[bytes]) -> bytes:
    pages = [cover_page(title, cast, finals[0] if finals else None)]
    for n, start in enumerate(range(0, len(finals), PER_PAGE), start=2):
        pages.append(panel_page(finals[start : start + PER_PAGE], n))
    out = io.BytesIO()
    pages[0].save(
        out,
        "PDF",
        save_all=True,
        append_images=pages[1:],
        resolution=DPI,
        title=title.strip() or "My Comic",
        author="Made with Comickatha",
    )
    return out.getvalue()
