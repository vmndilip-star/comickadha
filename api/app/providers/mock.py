"""Offline image provider: simple, recognisable placeholder art so the app runs with no API keys.

It reads the same prompt a real model gets (Layout / Cells / Palette / Place lines), draws the
character in its colours on flat magenta, and is deterministic for a given prompt, size and seed.
"""

import io
import random
import re
import time
from dataclasses import dataclass, field

from PIL import Image, ImageDraw, ImageFont

KEY = (255, 0, 255)
INK = (26, 26, 26)
WHITE = (255, 255, 255)
CORAL = (255, 107, 74)
SKY = (154, 208, 245)
CONFETTI = [(255, 210, 63), (31, 91, 209), (255, 107, 74), (183, 228, 167)]

RGB = tuple[int, int, int]
Point = tuple[float, float]


def hex_rgb(value: str | None, fallback: RGB) -> RGB:
    m = re.fullmatch(r"#?([0-9a-fA-F]{6})", (value or "").strip())
    if not m:
        return fallback
    n = int(m.group(1), 16)
    return (n >> 16) & 255, (n >> 8) & 255, n & 255


def shade(color: RGB, factor: float) -> RGB:
    """factor < 1 darkens, > 1 lightens towards white."""
    if factor <= 1:
        return (int(color[0] * factor), int(color[1] * factor), int(color[2] * factor))
    t = factor - 1
    return tuple(int(c + (255 - c) * t) for c in color)  # type: ignore[return-value]


# ---- poses --------------------------------------------------------------------------------------
# Coordinates are in units of 1/100 of the cell; y grows downwards.

HEAD_R = 12.0


@dataclass(frozen=True)
class Figure:
    head: Point
    face: str  # front | left3q | right3q | left | right | back
    arms: tuple[tuple[Point, ...], ...]
    legs: tuple[tuple[Point, ...], ...]
    body_dy: float = 0.0
    expression: str = "happy"
    extra: str = ""  # think | shake | confetti


ARMS_DOWN = (((41, 44), (34, 58), (33, 66)), ((59, 44), (66, 58), (67, 66)))
LEGS = (((45, 66), (44, 86)), ((55, 66), (56, 86)))


def _mirror(fig: Figure, face: str) -> Figure:
    def flip(points: tuple[Point, ...]) -> tuple[Point, ...]:
        return tuple((100 - x, y) for x, y in points)

    return Figure(
        head=(100 - fig.head[0], fig.head[1]),
        face=face,
        arms=tuple(flip(a) for a in fig.arms),
        legs=tuple(flip(leg) for leg in fig.legs),
        body_dy=fig.body_dy,
        expression=fig.expression,
        extra=fig.extra,
    )


_3Q_LEFT = Figure(
    head=(48, 26),
    face="left3q",
    arms=(((42, 44), (36, 58), (36, 66)), ((58, 44), (62, 58), (62, 66))),
    legs=(((46, 66), (45, 86)), ((54, 66), (54, 86))),
)
_SIDE_LEFT = Figure(
    head=(49, 26),
    face="left",
    arms=(((50, 44), (47, 58), (46, 66)),),
    legs=(((49, 66), (47, 86)), ((51, 66), (53, 86))),
)

FIGURES: dict[str, Figure] = {
    "front": Figure((50, 26), "front", ARMS_DOWN, LEGS),
    "three_quarter_left": _3Q_LEFT,
    "side_left": _SIDE_LEFT,
    "back": Figure((50, 26), "back", ARMS_DOWN, LEGS),
    "three_quarter_right": _mirror(_3Q_LEFT, "right3q"),
    "side_right": _mirror(_SIDE_LEFT, "right"),
    "walk": Figure(
        (50, 26),
        "front",
        (((41, 44), (36, 56), (38, 64)), ((59, 44), (66, 54), (70, 60))),
        (((45, 66), (38, 85)), ((55, 66), (60, 86))),
    ),
    "run": Figure(
        (53, 27),
        "right3q",
        (((42, 45), (34, 52), (30, 46)), ((60, 45), (68, 56), (72, 62))),
        (((46, 66), (36, 80), (32, 86)), ((55, 66), (64, 74), (70, 80))),
    ),
    "point": Figure(
        (50, 26), "front", (((41, 44), (34, 58), (33, 66)), ((59, 44), (72, 40), (86, 38))), LEGS
    ),
    "sit": Figure(
        (50, 34),
        "front",
        (((41, 52), (36, 64), (40, 70)), ((59, 52), (64, 64), (60, 70))),
        (((45, 74), (36, 76), (34, 86)), ((55, 74), (64, 76), (66, 86))),
        body_dy=8,
    ),
    "jump": Figure(
        (50, 20),
        "front",
        (((41, 38), (34, 26), (30, 16)), ((59, 38), (66, 26), (70, 16))),
        (((45, 60), (40, 72), (44, 80)), ((55, 60), (60, 72), (56, 80))),
        body_dy=-6,
        expression="laughing",
    ),
    "wave": Figure(
        (50, 26), "front", (((41, 44), (34, 58), (33, 66)), ((59, 44), (68, 32), (70, 20))), LEGS
    ),
    "hands_on_hips": Figure(
        (50, 26), "front", (((41, 44), (30, 54), (41, 62)), ((59, 44), (70, 54), (59, 62))), LEGS
    ),
    "thinking": Figure(
        (50, 26),
        "front",
        (((41, 44), (34, 58), (33, 66)), ((59, 44), (64, 52), (56, 38))),
        LEGS,
        extra="think",
    ),
    "scared_pose": Figure(
        (50, 26),
        "front",
        (((41, 44), (32, 40), (38, 30)), ((59, 44), (68, 40), (62, 30))),
        LEGS,
        expression="scared",
        extra="shake",
    ),
    "celebrate": Figure(
        (50, 26),
        "front",
        (((41, 44), (34, 30), (30, 14)), ((59, 44), (66, 30), (70, 14))),
        LEGS,
        expression="laughing",
        extra="confetti",
    ),
}

# The face sheet draws one big front-facing head per cell.
FACE_HEAD = (50.0, 58.0)  # low enough that a robot's antenna fits in the cell
FACE_R = 27.0


def head_extent(hx: float, hy: float, r: float) -> tuple[float, float, float, float]:
    """Head box (incl. hair) in cell units. Same shape for body and face cells."""
    return (hx - 1.15 * r, hy - 1.6 * r, 2.3 * r, 2.65 * r)


# ---- prompt parsing -----------------------------------------------------------------------------


@dataclass
class Request:
    sheet: str | None
    grid: tuple[int, int]
    cells: list[str]
    palette: dict[str, str] = field(default_factory=dict)
    place: str | None = None


def _line(prompt: str, label: str) -> str | None:
    m = re.search(rf"^{label}:\s*(.+)$", prompt, re.MULTILINE)
    return m.group(1).strip() if m else None


def parse(prompt: str) -> Request:
    layout = re.search(r"^Layout:\s*(\d+) row\(s\) x (\d+) column", prompt, re.MULTILINE)
    cells_line = _line(prompt, r"Cells \(left to right, top to bottom\)") or ""
    palette_line = _line(prompt, "Palette") or ""
    palette = dict(
        kv.split("=", 1) for kv in (p.strip() for p in palette_line.split(";")) if "=" in kv
    )
    return Request(
        sheet=_line(prompt, "Sheet"),
        grid=(int(layout.group(1)), int(layout.group(2))) if layout else (1, 1),
        cells=[c.strip() for c in cells_line.split("|") if c.strip()],
        palette=palette,
        place=_line(prompt, "Place"),
    )


# ---- drawing ------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Palette:
    kind: str
    skin: RGB
    hair: RGB
    hair_style: str
    outfit: RGB


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    return ImageFont.load_default(size=size)


def _label(draw: ImageDraw.ImageDraw, center: Point, text: str, size: int) -> None:
    font = _font(size)
    left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
    w, h = right - left, bottom - top
    x, y = center[0] - w / 2, center[1] - h / 2
    pad = max(3, size // 3)
    draw.rounded_rectangle(
        (x - pad, y - pad, x + w + pad, y + h + pad), radius=pad, fill=WHITE, outline=INK, width=2
    )
    draw.text((x - left, y - top), text, fill=INK, font=font)


class _Pen:
    """Draws in cell units: (0, 0) is the cell's top-left and 100 is its width."""

    def __init__(self, draw: ImageDraw.ImageDraw, x0: int, y0: int, size: int) -> None:
        self.d, self.x0, self.y0, self.u = draw, x0, y0, size / 100

    def p(self, x: float, y: float) -> Point:
        return (self.x0 + x * self.u, self.y0 + y * self.u)

    def box(self, x0: float, y0: float, x1: float, y1: float) -> tuple[float, float, float, float]:
        return (*self.p(x0, y0), *self.p(x1, y1))

    def w(self, units: float) -> int:
        return max(1, round(units * self.u))

    def limb(self, points: tuple[Point, ...], color: RGB, thick: float) -> None:
        pts = [self.p(*pt) for pt in points]
        self.d.line(pts, fill=INK, width=self.w(thick + 2.2), joint="curve")
        self.d.line(pts, fill=color, width=self.w(thick), joint="curve")

    def circle(self, x: float, y: float, r: float, fill: RGB | None, width: float = 1.0) -> None:
        self.d.ellipse(
            self.box(x - r, y - r, x + r, y + r), fill=fill, outline=INK, width=self.w(width)
        )


def _hair(pen: _Pen, hx: float, hy: float, r: float, pal: Palette, back: bool) -> None:
    k = r / HEAD_R
    color, line = pal.hair, 1.0 * k
    if back:
        pen.circle(hx, hy - 0.5 * k, r * 1.02, color, line)
        return
    match pal.hair_style:
        case "spiky":
            pts = [
                (-13, -2),
                (-11, -16),
                (-6, -9),
                (-1, -19),
                (4, -9),
                (9, -17),
                (13, -2),
                (6, -8),
                (-6, -8),
            ]
            pen.d.polygon(
                [pen.p(hx + x * k, hy + y * k) for x, y in pts],
                fill=color,
                outline=INK,
                width=pen.w(line),
            )
        case "curly":
            for angle_x, angle_y in [(-10, -6), (-7, -11), (-1, -13), (5, -12), (10, -7)]:
                pen.circle(hx + angle_x * k, hy + angle_y * k, 5 * k, color, line)
        case "braids":
            for side in (-1, 1):
                for i in range(3):
                    pen.circle(hx + side * 14 * k, hy + (3 + i * 5) * k, 3 * k, color, line)
            pen.d.chord(
                pen.box(hx - 13 * k, hy - 14 * k, hx + 13 * k, hy + 6 * k),
                180,
                360,
                fill=color,
                outline=INK,
                width=pen.w(line),
            )
        case _:  # bob
            pen.d.chord(
                pen.box(hx - 13 * k, hy - 14 * k, hx + 13 * k, hy + 8 * k),
                180,
                360,
                fill=color,
                outline=INK,
                width=pen.w(line),
            )
            for side in (-1, 1):
                x0 = hx + side * 13 * k
                pen.d.rectangle(
                    pen.box(
                        min(x0, x0 - side * 3.5 * k),
                        hy - 3 * k,
                        max(x0, x0 - side * 3.5 * k),
                        hy + 5 * k,
                    ),
                    fill=color,
                    outline=INK,
                    width=pen.w(line),
                )


def _features(pen: _Pen, hx: float, hy: float, r: float, face: str, expression: str) -> None:
    k = r / HEAD_R
    eyes = {
        "front": [(-5, 1), (5, 1)],
        "left3q": [(-7, 1), (1, 1)],
        "right3q": [(-1, 1), (7, 1)],
        "left": [(-7, 1)],
        "right": [(7, 1)],
    }[face]
    mouth_x = {"front": 0, "left3q": -3, "right3q": 3, "left": -6, "right": 6}[face]
    if face in ("left", "right"):
        side = -1 if face == "left" else 1
        pen.circle(hx + side * 12.3 * k, hy + 3 * k, 1.8 * k, None, 0.8 * k)

    for ex, ey in eyes:
        x, y = hx + ex * k, hy + ey * k
        match expression:
            case "surprised":
                pen.circle(x, y, 2.6 * k, WHITE, 0.7 * k)
                pen.circle(x, y, 1.1 * k, INK, 0.1)
            case "laughing":
                pen.d.arc(
                    pen.box(x - 2.2 * k, y - 1.5 * k, x + 2.2 * k, y + 2 * k),
                    200,
                    340,
                    fill=INK,
                    width=pen.w(0.8 * k),
                )
            case "scared":
                pen.circle(x, y, 1.1 * k, INK, 0.1)
            case _:
                pen.circle(x, y, 1.5 * k, INK, 0.1)
        # Brows: angry ones dip towards the middle of the face, sad ones rise there.
        tilt = {"angry": 1.6, "sad": -1.6}.get(expression, 0.0)
        y0 = y - (6.1 if expression == "surprised" else 3.6) * k
        left_y, right_y = (y0, y0 + tilt * k) if ex < mouth_x else (y0 + tilt * k, y0)
        pen.d.line(
            [pen.p(x - 2.2 * k, left_y), pen.p(x + 2.2 * k, right_y)],
            fill=INK,
            width=pen.w(0.7 * k),
        )

    mx, my = hx + mouth_x * k, hy + 6.5 * k
    match expression:
        case "sad":
            pen.d.arc(
                pen.box(mx - 4 * k, my, mx + 4 * k, my + 5 * k),
                200,
                340,
                fill=INK,
                width=pen.w(0.8 * k),
            )
        case "angry":
            pen.d.line(
                [pen.p(mx - 3.5 * k, my + 1.5 * k), pen.p(mx + 3.5 * k, my + 1.5 * k)],
                fill=INK,
                width=pen.w(0.8 * k),
            )
        case "surprised":
            pen.d.ellipse(pen.box(mx - 1.8 * k, my - 0.5 * k, mx + 1.8 * k, my + 3.5 * k), fill=INK)
        case "scared":
            pts = [
                pen.p(mx + (i - 3) * 1.4 * k, my + (1.6 if i % 2 else 0.2) * k) for i in range(7)
            ]
            pen.d.line(pts, fill=INK, width=pen.w(0.7 * k))
            pen.circle(hx + 10 * k, hy - 5 * k, 1.4 * k, SKY, 0.5 * k)
        case "laughing":
            pen.d.chord(
                pen.box(mx - 4.5 * k, my - 3 * k, mx + 4.5 * k, my + 5 * k),
                0,
                180,
                fill=WHITE,
                outline=INK,
                width=pen.w(0.8 * k),
            )
        case _:  # happy
            pen.d.arc(
                pen.box(mx - 4.5 * k, my - 3.5 * k, mx + 4.5 * k, my + 2.5 * k),
                20,
                160,
                fill=INK,
                width=pen.w(0.8 * k),
            )


def _head(
    pen: _Pen, hx: float, hy: float, r: float, face: str, expression: str, pal: Palette
) -> None:
    k = r / HEAD_R
    line = 1.0 * k
    if pal.kind == "robot":
        pen.d.line([pen.p(hx, hy - r), pen.p(hx, hy - r - 7 * k)], fill=INK, width=pen.w(line))
        pen.circle(hx, hy - r - 8.5 * k, 2.4 * k, CORAL, line)
        pen.d.rounded_rectangle(
            pen.box(hx - r, hy - r, hx + r, hy + r),
            radius=pen.w(4 * k),
            fill=pal.skin,
            outline=INK,
            width=pen.w(line),
        )
        if face != "back":
            _features(pen, hx, hy, r, face, expression)
        return
    if pal.kind == "animal":
        for side in (-1, 1):
            pen.circle(hx + side * 9 * k, hy - 10 * k, 5.5 * k, pal.skin, line)
    pen.circle(hx, hy, r, pal.skin, line)
    if pal.kind != "animal":
        _hair(pen, hx, hy, r, pal, back=face == "back")
    if face != "back":
        _features(pen, hx, hy, r, face, expression)


def _figure(pen: _Pen, fig: Figure, pal: Palette, rng: random.Random) -> None:
    dy = fig.body_dy
    pants = shade(pal.outfit, 0.55)
    for leg in fig.legs:
        pen.limb(leg, pants, 5.5)
        fx, fy = leg[-1]
        pen.d.ellipse(pen.box(fx - 3.5, fy - 1.5, fx + 3.5, fy + 2.5), fill=INK)
    narrow = fig.face in ("left", "right")
    half = 7 if narrow else 11
    pen.d.rounded_rectangle(
        pen.box(50 - half, 40 + dy, 50 + half, 68 + dy),
        radius=pen.w(6),
        fill=pal.outfit,
        outline=INK,
        width=pen.w(1.2),
    )
    for arm in fig.arms:
        pen.limb(arm, pal.skin, 4.5)
        ax, ay = arm[-1]
        pen.circle(ax, ay, 2.6, pal.skin, 0.9)
    hx, hy = fig.head
    _head(pen, hx, hy, HEAD_R, fig.face, fig.expression, pal)

    match fig.extra:
        case "think":
            for i, (tx, ty) in enumerate([(68, 14), (75, 8), (83, 4)]):
                pen.circle(tx, ty, 1.5 + i, WHITE, 0.8)
        case "shake":
            for side in (-1, 1):
                sx = 50.0 + side * 22
                for j in range(3):
                    pen.d.line(
                        [pen.p(sx, 18 + j * 6), pen.p(sx + side * 4, 16 + j * 6)],
                        fill=INK,
                        width=pen.w(0.9),
                    )
        case "confetti":
            for _ in range(10):
                x, y = rng.uniform(15, 85), rng.uniform(4, 40)
                pen.d.rectangle(pen.box(x, y, x + 2.5, y + 1.5), fill=rng.choice(CONFETTI))


def _palette(req: Request) -> Palette:
    p = req.palette
    return Palette(
        kind=p.get("kind", "kid"),
        skin=hex_rgb(p.get("skin"), (242, 194, 155)),
        hair=hex_rgb(p.get("hair"), INK),
        hair_style=p.get("hair_style", "bob"),
        outfit=hex_rgb(p.get("outfit"), (255, 233, 168)),
    )


def _png(image: Image.Image) -> bytes:
    buf = io.BytesIO()
    image.save(buf, format="PNG", compress_level=3)
    return buf.getvalue()


class MockImageProvider:
    """Placeholder art for character sheets, expression faces and places."""

    name = "mock"

    def __init__(self, delay_seconds: float = 0.0) -> None:
        self.delay_seconds = delay_seconds

    def generate(
        self,
        prompt: str,
        size: tuple[int, int],
        seed: int,
        reference_images: list[bytes] | None = None,
    ) -> bytes:
        if self.delay_seconds:
            time.sleep(self.delay_seconds)  # pretend to be a slow image API, so progress is visible
        req = parse(prompt)
        rng = random.Random(seed)
        if req.sheet:
            return _png(self._sheet(req, size, rng))
        if req.place:
            return _png(self._place(req, size, rng))
        return _png(self._card(prompt, size))

    def head_box(self, cell: str) -> tuple[float, float, float, float] | None:
        sheet, _, name = cell.partition("/")
        if sheet == "face":
            box = head_extent(*FACE_HEAD, FACE_R)
        elif sheet == "body" and name in FIGURES:
            fig = FIGURES[name]
            box = head_extent(fig.head[0], fig.head[1], HEAD_R)
        else:
            return None
        return (box[0] / 100, box[1] / 100, box[2] / 100, box[3] / 100)

    def _sheet(self, req: Request, size: tuple[int, int], rng: random.Random) -> Image.Image:
        rows, cols = req.grid
        width, height = size
        cw, ch = width // cols, height // rows
        image = Image.new("RGB", (width, height), KEY)
        draw = ImageDraw.Draw(image)
        pal = _palette(req)
        faces = req.sheet == "faces"
        for i, name in enumerate(req.cells[: rows * cols]):
            r, c = divmod(i, cols)
            pen = _Pen(draw, c * cw, r * ch, min(cw, ch))
            if faces:
                _head(pen, FACE_HEAD[0], FACE_HEAD[1], FACE_R, "front", name, pal)
            else:
                _figure(pen, FIGURES.get(name, FIGURES["front"]), pal, rng)
                _label(draw, pen.p(50, 94), name.replace("_", " "), max(10, round(4.6 * pen.u)))
        return image

    def _place(self, req: Request, size: tuple[int, int], rng: random.Random) -> Image.Image:
        width, height = size
        tint = hex_rgb(req.palette.get("tint"), (183, 228, 167))
        dark = sum(tint) / 3 < 90
        horizon = int(height * 0.62)
        image = Image.new("RGB", size, shade(tint, 1.35) if not dark else tint)
        draw = ImageDraw.Draw(image)
        draw.rectangle((0, horizon, width, height), fill=shade(tint, 0.8))
        draw.line((0, horizon, width, horizon), fill=INK, width=5)
        for _ in range(4 if not dark else 18):
            x, y = rng.uniform(0.05, 0.95) * width, rng.uniform(0.05, 0.5) * height
            if dark:
                r = rng.uniform(3, 7)
                draw.ellipse((x - r, y - r, x + r, y + r), fill=(255, 210, 63))
            else:
                w = rng.uniform(70, 150)
                draw.ellipse(
                    (x - w / 2, y - w / 5, x + w / 2, y + w / 5), fill=WHITE, outline=INK, width=3
                )
        for _ in range(3):
            x = rng.uniform(0.05, 0.85) * width
            w, h = rng.uniform(80, 180), rng.uniform(40, 110)
            draw.rounded_rectangle(
                (x, horizon - h, x + w, horizon + 8),
                radius=18,
                fill=shade(tint, 0.65),
                outline=INK,
                width=4,
            )
        draw.rectangle((0, 0, width - 1, height - 1), outline=INK, width=6)
        _label(draw, (width * 0.2, 40), (req.place or "Place")[:32], 26)
        _label(draw, (width - 60, 36), "MOCK", 18)
        return image

    def _card(self, prompt: str, size: tuple[int, int]) -> Image.Image:
        image = Image.new("RGB", size, (255, 248, 236))
        draw = ImageDraw.Draw(image)
        draw.rectangle((0, 0, size[0] - 1, size[1] - 1), outline=INK, width=6)
        _label(
            draw, (size[0] / 2, size[1] / 2), prompt.splitlines()[0][:40] if prompt else "MOCK", 24
        )
        return image
