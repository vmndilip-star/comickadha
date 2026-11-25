"""The prop library: story objects drawn the way characters are, as their own transparent layer.

A place picture never paints these (a scarecrow that moves, a torch, a notebook...): they are drawn
on top of it, per panel, so a panel can show the scarecrow on its pole, lying in the field, or not
there at all. The art uses the characters' units (a character cell is 200 units tall), ink and
stroke width, so a prop is the right size next to a character and looks drawn by the same hand.

Each prop has states; each state is a drawing with an `anchor`, the point that is placed:
- on the ground (standing, on_pole, lying_down, on_ground): the bottom centre, on the ground line;
- held: the grip, placed at the holder's hand;
- worn: the bottom of the band, placed on the wearer's head (turbans; the scarecrow can wear one).
"""

from dataclasses import dataclass, field
from typing import Literal

INK = "#1A1A1A"
SW = 2.4  # the characters' stroke width (shared/avatar/build_catalog.py)
WOOD = "#B07A45"
WOOD_DARK = "#8A5A2E"
STRAW = "#F2C94C"
STRAW_DARK = "#D9A62B"
BURLAP = "#DDBB80"
BURLAP_DARK = "#C49A5C"
STEEL = "#CDD3DA"
STEEL_DARK = "#9AA3AE"
BEAM = "#FFF3A0"

Placement = Literal["ground", "held", "worn"]
Box = tuple[float, float, float, float]  # x, y, w, h in prop units
Point = tuple[float, float]


@dataclass(frozen=True)
class PropState:
    label: str
    placement: Placement
    svg: str  # drawn in prop units around the anchor at (0, 0)
    box: Box  # what to render, in prop units (with room for the strokes)
    # The scarecrow's head: where a worn turban goes (centre of the band), its width, its turn.
    head: tuple[float, float, float, float] | None = None  # x, y, width, rotate (degrees)
    # Held things that point a way (the torch's beam) are flipped to face the panel's middle.
    directional: bool = False
    # Held things too big to hold in front of the face (the scarecrow) go behind the holder.
    behind_holder: bool = False
    # A beam's outline (prop units), so the stage can tilt it down off everyone's face.
    beam: tuple[tuple[float, float], ...] | None = None


@dataclass(frozen=True)
class Prop:
    id: str
    name: str
    states: dict[str, PropState]
    # Words that name it in a bubble or caption (whole words, lower case).
    words: tuple[str, ...]
    default_state: str
    notes: str = ""  # one line for the planner prompt
    worn_by_props: tuple[str, ...] = field(default=())  # props it can sit on (turban -> scarecrow)


def n(x: float) -> str:
    r = round(float(x), 2)
    return str(int(r)) if r == int(r) else str(r)


def stroke(color: str = INK, width: float = SW) -> str:
    return (
        f' stroke="{color}" stroke-width="{n(width)}" stroke-linejoin="round" '
        'stroke-linecap="round"'
    )


def path(d: str, fill: str, line: str | None = INK, width: float = SW, extra: str = "") -> str:
    return f'<path d="{d}" fill="{fill}"{stroke(line, width) if line else ""}{extra}/>'


def circle(
    cx: float, cy: float, r: float, fill: str, line: str | None = INK, width: float = SW
) -> str:
    outline = stroke(line, width) if line else ""
    return f'<circle cx="{n(cx)}" cy="{n(cy)}" r="{n(r)}" fill="{fill}"{outline}/>'


def ellipse(
    cx: float, cy: float, rx: float, ry: float, fill: str, line: str | None = INK, width: float = SW
) -> str:
    outline = stroke(line, width) if line else ""
    return f'<ellipse cx="{n(cx)}" cy="{n(cy)}" rx="{n(rx)}" ry="{n(ry)}" fill="{fill}"{outline}/>'


def rect(
    x: float, y: float, w: float, h: float, rx: float, fill: str, line: str | None = INK,
    width: float = SW,
) -> str:  # fmt: skip
    outline = stroke(line, width) if line else ""
    return (
        f'<rect x="{n(x)}" y="{n(y)}" width="{n(w)}" height="{n(h)}" rx="{n(rx)}" '
        f'fill="{fill}"{outline}/>'
    )


def line(points: list[Point], color: str = INK, width: float = SW) -> str:
    d = "M" + " L".join(f"{n(x)} {n(y)}" for x, y in points)
    return f'<path d="{d}" fill="none"{stroke(color, width)}/>'


def group(inner: str, transform: str) -> str:
    return f'<g transform="{transform}">{inner}</g>'


# ---- the scarecrow ---------------------------------------------------------------------------


def _tuft(x: float, y: float, direction: float) -> str:
    """A fan of straw sticking out of a sleeve or hem (direction: -1 left, 1 right, 0 down)."""
    out = ""
    if direction == 0:
        for dx in (-9, -3, 3, 9):
            out += line([(x + dx, y), (x + dx * 1.35, y + 11)], STRAW_DARK, 2.6)
        return out
    for dy in (-6, -2, 2, 6):
        out += line([(x, y + dy), (x + direction * 11, y + dy * 1.5)], STRAW_DARK, 2.6)
    return out


def _scarecrow_body(arms_out: bool) -> str:
    """The stuffed shirt, head and face, standing upright with the head top near y=-166.
    Arms out (on its pole's crossbar) or down by its sides (held or lying down)."""
    shirt = "#4C7EDB"
    shirt_dark = "#3A63B0"
    patch = "#F2C14E"
    out = ""
    if arms_out:
        for side in (-1, 1):
            out += _tuft(side * 54, -114, side)
            sleeve = (
                f"M{n(side * 18)} -124 L{n(side * 54)} -121 L{n(side * 54)} -107 "
                f"L{n(side * 18)} -104 Z"
            )
            out += path(sleeve, shirt)
            out += line([(side * 36, -122.5), (side * 36, -105.5)], shirt_dark, 1.6)
    else:
        for side in (-1, 1):
            out += _tuft(side * 25, -64, side)
            sleeve = (
                f"M{n(side * 16)} -122 L{n(side * 27)} -116 L{n(side * 29)} -68 "
                f"L{n(side * 20)} -66 Z"
            )
            out += path(sleeve, shirt)
    out += _tuft(0, -62, 0)
    out += path("M-22 -124 L22 -124 L25 -64 L-25 -64 Z", shirt)
    out += line([(-24, -80), (24, -80)], WOOD_DARK, 3.4)  # rope belt
    out += rect(-15, -112, 13, 13, 2, patch, INK, 1.8)
    out += line([(-13, -108), (-4, -108)], INK, 1.2) + line([(-13, -103), (-4, -103)], INK, 1.2)
    out += line([(8, -118), (8, -86)], shirt_dark, 1.6)
    out += line([(-8, -96), (-8, -84)], shirt_dark, 1.6)
    # Head: a stuffed sack tied at the neck, with a stitched, friendly face.
    out += path("M-10 -122 L10 -122 L13 -128 L-13 -128 Z", BURLAP_DARK)
    out += path(
        "M0 -166 C13 -166 22 -157 22 -145 C22 -134 13 -127 0 -127 C-13 -127 -22 -134 -22 -145 "
        "C-22 -157 -13 -166 0 -166 Z",
        BURLAP,
    )
    out += circle(-7.5, -148, 2.6, INK, None) + circle(7.5, -148, 2.6, INK, None)
    out += path("M-8 -138 Q0 -132 8 -138", "none", INK, 2)
    for x in (-5, 0, 5):
        out += line([(x, -137.2 + abs(x) * 0.12), (x, -133.5 + abs(x) * 0.12)], INK, 1.2)
    out += circle(-13, -140, 2.4, "#F08A8A", None) + circle(13, -140, 2.4, "#F08A8A", None)
    return out


def _pole(top: float = -150, crossbar: bool = True) -> str:
    out = ""
    if crossbar:
        out += rect(-58, -119, 116, 7, 2, WOOD)
    out += rect(-4.5, top, 9, -top, 2, WOOD)
    out += line([(-1, top + 10), (-1, -6)], WOOD_DARK, 1.4)
    return out


def _straw_bits() -> str:
    return (
        line([(-16, -1), (-7, -4)], STRAW_DARK, 2.4)
        + line([(8, -1), (17, -3)], STRAW_DARK, 2.4)
        + line([(-3, 0), (4, -2)], STRAW_DARK, 2.4)
    )


SCARECROW_HEAD = (0.0, -151.0, 44.0)  # the band's centre and width, in standing units

# Lying down: the arms-down figure turned on its side, head to the left, resting on the ground.
_LYING = "translate(80 -36) rotate(-90)"


def _lying_point(x: float, y: float) -> Point:
    """Where a standing-figure point lands once lying down (_LYING)."""
    return (y + 80, -x - 36)


SCARECROW = Prop(
    id="scarecrow",
    name="Scarecrow",
    words=("scarecrow", "scarecrows"),
    default_state="on_pole",
    notes="on_pole (standing in the field), lying_down (fallen over), held (carried or hugged)",
    states={
        "on_pole": PropState(
            "On its pole",
            "ground",
            _pole() + _scarecrow_body(arms_out=True),
            (-70, -172, 140, 178),
            head=(*SCARECROW_HEAD, 0.0),
        ),
        "lying_down": PropState(
            "Lying down",
            "ground",
            group(rect(-4.5, -60, 9, 66, 2, WOOD) + _scarecrow_body(arms_out=False), _LYING),
            (-90, -76, 180, 80),
            head=(*_lying_point(0, -151), 44.0, -90.0),
        ),
        "held": PropState(
            "Held",
            "held",
            group(
                rect(-4.5, -70, 9, 34, 2, WOOD) + _scarecrow_body(arms_out=False), "translate(0 95)"
            ),
            (-38, -75, 76, 138),
            head=(SCARECROW_HEAD[0], SCARECROW_HEAD[1] + 95, SCARECROW_HEAD[2], 0.0),
            behind_holder=True,
        ),
    },
)

POLE = Prop(
    id="pole",
    name="Empty pole",
    words=("pole", "poles"),
    default_state="standing",
    notes="the scarecrow's pole with nobody on it",
    states={
        "standing": PropState("Standing", "ground", _pole() + _straw_bits(), (-62, -154, 124, 158)),
    },
)


# ---- turbans -----------------------------------------------------------------------------------


def _turban(color: str, shade: str) -> str:
    """A wrapped turban, band at the bottom (y=0), about as wide as a head (64 units)."""
    out = path(
        "M-31 0 C-35 -16 -28 -34 -10 -39 C2 -42 18 -40 27 -30 C33 -22 34 -10 31 0 Q0 7 -31 0 Z",
        color,
    )
    out += path("M-30 -9 Q-2 -20 31 -8", "none", shade, 3)
    out += path("M-27 -21 Q2 -33 29 -19", "none", shade, 3)
    out += path("M-17 -32 Q4 -40 21 -32", "none", shade, 2.6)
    out += path("M-31 0 Q0 7 31 0 L30 -6 Q0 1 -30 -6 Z", shade, INK, 1.8)
    out += path("M5 -38 C10 -48 20 -47 18 -38 Z", color, INK, 2)  # the tuck at the top
    return out


def _turban_prop(prop_id: str, name: str, color: str, shade: str, word: str) -> Prop:
    art = _turban(color, shade)
    box = (-37, -50, 74, 58)
    return Prop(
        id=prop_id,
        name=name,
        words=(f"{word} turban", f"{word} turbans"),
        default_state="worn",
        notes="worn (on a character's head, or on the scarecrow), held, on_ground",
        worn_by_props=("scarecrow",),
        states={
            "worn": PropState("Worn", "worn", art, box),
            "held": PropState("Held", "held", group(art, "translate(0 -2) scale(0.8)"), box),
            "on_ground": PropState("On the ground", "ground", group(art, "scale(0.8)"), box),
        },
    )


RED_TURBAN = _turban_prop("red_turban", "Red turban", "#E5483B", "#B83227", "red")
ORANGE_TURBAN = _turban_prop("orange_turban", "Orange turban", "#FF9A2E", "#D9741A", "orange")


# ---- small things --------------------------------------------------------------------------------


TORCH_BEAM = ((20.0, -6.0), (128.0, -32.0), (128.0, 32.0), (20.0, 6.0))


def _outline(points: tuple[tuple[float, float], ...]) -> str:
    first, *rest = points
    return f"M{first[0]:g} {first[1]:g} " + " ".join(f"L{x:g} {y:g}" for x, y in rest) + " Z"


def _torch_body() -> str:
    return (
        rect(-15, -5, 25, 10, 3, "#E5483B")
        + line([(-9, -5), (-9, 5)], "#B83227", 1.6)
        + path("M10 -5 L19 -8.5 L19 8.5 L10 5 Z", STEEL)
        + ellipse(19.5, 0, 2.2, 8, "#FFFBD6", INK, 1.8)
    )


TORCH = Prop(
    id="torch",
    name="Torch",
    words=("torch", "torches", "torchlight", "flashlight"),
    default_state="held",
    notes="held (switched on, its beam lights the way), on_ground",
    states={
        "held": PropState(
            "Held, shining",
            "held",
            path(_outline(TORCH_BEAM), BEAM, None, extra=' fill-opacity="0.45"')
            + path("M20 -4 L96 -15 L96 15 L20 4 Z", "#FFFBD6", None, extra=' fill-opacity="0.45"')
            + _torch_body(),
            (-18, -34, 148, 68),
            directional=True,
            beam=TORCH_BEAM,
        ),
        "on_ground": PropState(
            "On the ground", "ground", group(_torch_body(), "translate(0 -9)"), (-18, -20, 40, 22)
        ),
    },
)


def _notebook_closed() -> str:
    out = rect(-12, -32, 24, 32, 2.5, "#2F6FE0")
    out += rect(-7.5, -24, 15, 8, 1.5, "#FFFFFF", INK, 1.4)
    for x in (-7.5, -2.5, 2.5, 7.5):
        out += circle(x, -32, 2.2, STEEL, INK, 1.2)
    return out


def _notebook_open() -> str:
    out = path("M-24 0 L-21 -11 L0 -9 L0 1 Z", "#FFFFFF")
    out += path("M24 0 L21 -11 L0 -9 L0 1 Z", "#FFFFFF")
    for i in (0, 1, 2):
        y = -7.6 + i * 2.6
        out += line([(-18 + i * 0.6, y), (-4, y + 0.5)], "#9AB6E6", 1)
        out += line([(4, y + 0.5), (18 - i * 0.6, y)], "#9AB6E6", 1)
    return out


NOTEBOOK = Prop(
    id="notebook",
    name="Notebook",
    words=("notebook", "notebooks", "note book", "diary", "diaries"),
    default_state="held",
    notes="held, on_ground (open)",
    states={
        "held": PropState(
            "Held", "held", group(_notebook_closed(), "translate(0 4)"), (-15, -32, 30, 40)
        ),
        "on_ground": PropState("On the ground", "ground", _notebook_open(), (-26, -14, 52, 17)),
    },
)


def _tiffin() -> str:
    """A three-tier steel tiffin carrier with its carrying clip."""
    out = path("M-14 -6 L-14 -44 Q0 -51 14 -44 L14 -6", "none", STEEL_DARK, 3)
    out += path("M-14 -6 L-14 -44 Q0 -51 14 -44 L14 -6", "none", INK, 1.2)
    for top in (-36, -24, -12):
        out += rect(-11, top, 22, 12, 3, STEEL)
    out += path("M-11 -36 Q0 -43 11 -36 Z", STEEL, INK, 1.8)
    return out


TIFFIN = Prop(
    id="tiffin",
    name="Tiffin box",
    words=("tiffin", "tiffins", "tiffin box", "lunchbox", "lunch box"),
    default_state="held",
    notes="held (by its handle), on_ground",
    states={
        "held": PropState("Held", "held", group(_tiffin(), "translate(0 48)"), (-17, -3, 34, 52)),
        "on_ground": PropState("On the ground", "ground", _tiffin(), (-17, -51, 34, 53)),
    },
)


def _laddoos() -> str:
    out = ellipse(0, -4, 24, 5.5, "#E8E8E8")
    for x, y in ((-12, -11), (0, -11), (12, -11), (-6, -21), (6, -21), (0, -31)):
        out += circle(x, y, 6.4, "#F4A640", INK, 2)
        out += circle(x - 2, y - 1.5, 0.9, "#C9761F", None) + circle(
            x + 2, y + 1.4, 0.9, "#C9761F", None
        )
    return out


LADDOOS = Prop(
    id="laddoos",
    name="Laddoos",
    words=("laddoo", "laddoos", "ladoo", "ladoos", "laddu", "laddus"),
    default_state="held",
    notes="a plate of round sweets: held, on_ground",
    states={
        "held": PropState("Held", "held", group(_laddoos(), "translate(0 6)"), (-27, -32, 54, 42)),
        "on_ground": PropState("On the ground", "ground", _laddoos(), (-27, -40, 54, 43)),
    },
)


def _paw(x: float, y: float, size: float = 1.0) -> str:
    color = "#6B4A2E"
    out = ellipse(x, y, 6.6 * size, 5.4 * size, color, None)
    for dx, dy in ((-6.2, -6.6), (-2.2, -9.4), (2.2, -9.4), (6.2, -6.6)):
        out += circle(x + dx * size, y + dy * size, 2.3 * size, color, None)
    return out


PAW_PRINTS = Prop(
    id="paw_prints",
    name="Paw prints",
    words=(
        "paw print",
        "paw prints",
        "pawprint",
        "pawprints",
        "footprint",
        "footprints",
        "foot print",
        "foot prints",
        "paw marks",
        "tracks",
    ),  # fmt: skip
    default_state="on_ground",
    notes="a trail of big round paw prints on the ground",
    states={
        "on_ground": PropState(
            "On the ground",
            "ground",
            "".join(_paw(x, y) for x, y in ((-64, -6), (-32, -15), (0, -6), (32, -15), (64, -6))),
            (-74, -28, 148, 30),
        ),
    },
)

PROPS: dict[str, Prop] = {
    p.id: p
    for p in (
        SCARECROW,
        POLE,
        RED_TURBAN,
        ORANGE_TURBAN,
        TORCH,
        NOTEBOOK,
        TIFFIN,
        LADDOOS,
        PAW_PRINTS,
    )
}
PROP_IDS: tuple[str, ...] = tuple(PROPS)
STATES: tuple[str, ...] = tuple(dict.fromkeys(s for p in PROPS.values() for s in p.states))
