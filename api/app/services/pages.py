"""Comic pages by slots (Phase 8): how panels of different sizes fill pages, for the Reader and PDF.

A page holds 6 slots: 3 rows of 2. A normal panel takes 1 slot (half a row), a wide panel a whole
row (2 slots), a splash panel the whole page. `shown_sizes` turns the sizes the planner or the kid
chose into the sizes the panels are shown (and drawn) at; `pages_of` lays those out:

1. Rows: normal panels pair up in order. A normal panel left alone in its row (the next panel is
   wide or a splash, or the comic ends) is shown wide, so no row is half empty.
2. Pages: rows between splash pages fill pages of 3 rows. A run that would leave a page with a
   single row is split 2 + 2 instead, so no page is mostly empty. A single row on its own between
   splashes becomes two wide panels (or, one wide panel, a splash).
3. The last page: if it has one row of two normal panels, both are shown wide; a "The End" tile
   fills whatever is left (a last page with one wide panel keeps a row empty: never mostly empty).

Comics drawn before panel sizes (every panel without a shown size) keep the layout they always had:
pairs of panels, no "The End".
"""

from dataclasses import dataclass, field

ROWS = 3
SIZES = ("normal", "wide", "splash")


@dataclass
class Page:
    """One page: rows of panel indexes ([i, j] two normal panels, [i] a wide one), or a splash."""

    rows: list[list[int]] = field(default_factory=list)
    splash: int | None = None
    the_end: bool = False  # a "The End" tile fills the last row(s)


def _units(shown: list[str]) -> list[list[int] | int]:
    """Rows (lists of indexes) and splash pages (an index), in order."""
    units: list[list[int] | int] = []
    waiting: list[int] = []
    for i, size in enumerate(shown):
        if size == "normal":
            waiting.append(i)
            if len(waiting) == 2:
                units.append(waiting)
                waiting = []
            continue
        if waiting:
            units.append(waiting)
            waiting = []
        units.append(i if size == "splash" else [i])
    if waiting:
        units.append(waiting)
    return units


def _split(rows: list[list[int]], balanced: bool = True) -> list[list[list[int]]]:
    """Rows into pages of 3, never leaving a page with 1 row when there are 2 or more rows (unless
    not `balanced`: the old layout, plain pages of 3 rows)."""
    sizes = [ROWS] * (len(rows) // ROWS)
    left = len(rows) % ROWS
    if left == 1 and sizes and balanced:
        sizes[-1] = 2
        sizes.append(2)
    elif left:
        sizes.append(left)
    out: list[list[list[int]]] = []
    start = 0
    for size in sizes:
        out.append(rows[start : start + size])
        start += size
    return out


def pages_of(shown: list[str], the_end: bool = True, balanced: bool = True) -> list[Page]:
    """The pages for panels shown at these sizes. `the_end`: a short last page gets "The End";
    `balanced`: no page is left with a single row (the old layout had neither)."""
    pages: list[Page] = []
    run: list[list[int]] = []
    for unit in _units(shown):
        if isinstance(unit, int):
            pages.extend(Page(rows=chunk) for chunk in _split(run, balanced))
            run = []
            pages.append(Page(splash=unit))
        else:
            run.append(unit)
    pages.extend(Page(rows=chunk) for chunk in _split(run, balanced))
    if the_end and pages and pages[-1].splash is None and len(pages[-1].rows) < ROWS:
        pages[-1].the_end = True
    return pages


def shown_sizes(chosen: list[str]) -> list[str]:
    """The size each panel is shown (and drawn) at, from the sizes chosen for them."""
    shown = [s if s in SIZES else "normal" for s in chosen]
    for unit in _units(shown):  # 1. nobody alone in a row
        if isinstance(unit, list) and len(unit) == 1 and shown[unit[0]] == "normal":
            shown[unit[0]] = "wide"
    units = _units(shown)
    for k, unit in enumerate(units):  # 2. a lone row between splashes
        if not isinstance(unit, list):
            continue
        before = k == 0 or isinstance(units[k - 1], int)
        after = k + 1 < len(units) and isinstance(units[k + 1], int)
        if before and after:
            if len(unit) == 2:
                shown[unit[0]] = shown[unit[1]] = "wide"
            else:
                shown[unit[0]] = "splash"
    pages = pages_of(shown)  # 3. the last page
    last = pages[-1] if pages else None
    if last and last.splash is None and len(last.rows) == 1 and len(last.rows[0]) == 2:
        shown[last.rows[0][0]] = shown[last.rows[0][1]] = "wide"
    return shown


def comic_pages(sizes: list[str | None]) -> list[Page]:
    """The pages a comic shows, from its panels' stored shown sizes. A comic from before panel
    sizes (none stored) keeps its old layout: pairs of panels, no "The End"."""
    sized = any(s is not None for s in sizes)
    return pages_of([s or "normal" for s in sizes], the_end=sized, balanced=sized)
