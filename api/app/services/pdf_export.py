"""The comic as a PDF, built with Pillow from the panels' final.png files.

One page size for everyone: 8.27 x 11 in (A4's width, Letter's height) at 150 dpi, so it prints on
A4 or Letter with "Fit to page". Page 1 is the cover: the title, panel 1, the cast drawn from their
pinned looks, and "Made with Comickadha". Then the pages by slots (services/pages.py): 3 rows of
2 normal panels, a wide panel filling a row, a splash panel filling a page, and a "The End" tile
where a last page would be short. Page numbers at the bottom. All lettering uses the bundled
fonts (api/assets/fonts), drawn into the pages.
"""

import io
from dataclasses import dataclass
from typing import Any

from PIL import Image, ImageDraw, ImageOps

from app.avatar.render import render_pose
from app.services import lettering
from app.services.pages import Page, pages_of

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


def _centered(draw: ImageDraw.ImageDraw, y: float, text: str, kind: str, px: int) -> int:
    """Draws one line centred across the page; returns the font size used (shrunk to fit)."""
    f = lettering.font(kind, px)
    while f.getlength(text) > PAGE_W - 2 * MARGIN and px > 20:
        px -= 4
        f = lettering.font(kind, px)
    draw.text(((PAGE_W - f.getlength(text)) / 2, y), text, font=f, fill=INK)
    return px


def cover_page(title: str, cast: list[CastMember], hero: bytes | None = None) -> Image.Image:
    """The title on a sun band, panel 1 as the cover picture, the cast, "Made with Comickadha"."""
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
    _centered(draw, PAGE_H - 150, "Made with Comickadha", "title", 64)
    return page


CELL_W = (PAGE_W - 2 * MARGIN - GUTTER * (COLS - 1)) // COLS  # a normal panel: 530 x 397
CELL_H = CELL_W * 3 // 4
FULL_W = PAGE_W - 2 * MARGIN  # a wide panel fills the row: 1090 x 397
BLOCK_H = CELL_H * ROWS + GUTTER * (ROWS - 1)  # a splash panel fills the page: 1090 x 1251
TOP = (PAGE_H - BLOCK_H) // 2 - 20


def _paste(
    page: Image.Image, draw: ImageDraw.ImageDraw, png: bytes, box: tuple[int, int, int, int]
) -> None:
    x, y, w, h = box
    with Image.open(io.BytesIO(png)) as source:
        picture = ImageOps.fit(source.convert("RGB"), (w, h), method=Image.Resampling.LANCZOS)
    page.paste(picture, (x, y))
    draw.rectangle((x, y, x + w - 1, y + h - 1), outline=INK, width=BORDER)


def _the_end(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int]) -> None:
    """The tile that finishes a short last page."""
    x, y, w, h = box
    draw.rectangle((x, y, x + w - 1, y + h - 1), fill=SUN, outline=INK, width=BORDER)
    px = min(150, h * 2 // 3)
    f = lettering.font("title", px)
    text = "The End!"
    draw.text(
        (x + (w - f.getlength(text)) / 2, y + (h - px) / 2 - px * 0.08), text, font=f, fill=INK
    )


def panel_page(
    finals: list[bytes], number: int, layout: Page | None = None, shown: list[str] | None = None
) -> Image.Image:
    """One page of panels. `layout` (services/pages.py) says which panel goes where (indexes into
    `finals`), `shown` how big each panel is shown; without them, the panels fill 2 a row."""
    if layout is None:
        layout = Page(
            rows=[list(range(i, min(i + COLS, len(finals)))) for i in range(0, len(finals), COLS)]
        )
    sizes = shown or ["normal"] * len(finals)
    page = Image.new("RGB", (PAGE_W, PAGE_H), PAPER)
    draw = ImageDraw.Draw(page)
    if layout.splash is not None:
        _paste(page, draw, finals[layout.splash], (MARGIN, TOP, FULL_W, BLOCK_H))
    else:
        rows = ROWS if layout.the_end else len(layout.rows)
        top = (PAGE_H - (CELL_H * rows + GUTTER * (rows - 1))) // 2 - 20
        for r, row in enumerate(layout.rows):
            y = top + r * (CELL_H + GUTTER)
            if len(row) == 1 and sizes[row[0]] != "normal":  # a wide panel fills its row
                _paste(page, draw, finals[row[0]], (MARGIN, y, FULL_W, CELL_H))
                continue
            for c, index in enumerate(row):
                _paste(
                    page, draw, finals[index], (MARGIN + c * (CELL_W + GUTTER), y, CELL_W, CELL_H)
                )
        if layout.the_end:
            y = top + len(layout.rows) * (CELL_H + GUTTER)
            spare = rows - len(layout.rows)
            _the_end(draw, (MARGIN, y, FULL_W, CELL_H * spare + GUTTER * (spare - 1)))
    f = lettering.font("talk", 30)
    label = str(number)
    draw.text(((PAGE_W - f.getlength(label)) / 2, PAGE_H - 80), label, font=f, fill=INK)
    return page


def build_pdf(
    title: str, cast: list[CastMember], finals: list[bytes], shown: list[str | None] | None = None
) -> bytes:
    """The PDF: the cover, then the panels' pages. `shown`: each panel's shown size (None for a
    comic from before panel sizes: pairs of panels, as it always was)."""
    stored = shown if shown is not None else [None] * len(finals)
    sized = any(s is not None for s in stored)
    sizes = [s or "normal" for s in stored]
    layouts = pages_of(sizes, the_end=sized, balanced=sized)
    pages = [cover_page(title, cast, finals[0] if finals else None)]
    for n, layout in enumerate(layouts, start=2):
        pages.append(panel_page(finals, n, layout, sizes))
    out = io.BytesIO()
    pages[0].save(
        out,
        "PDF",
        save_all=True,
        append_images=pages[1:],
        resolution=DPI,
        title=title.strip() or "My Comic",
        author="Made with Comickadha",
    )
    return out.getvalue()
