"""Pillow helpers for character sheets: key out magenta, validate, slice, find heads, encode."""

import io
from collections.abc import Sequence

from PIL import Image, ImageChops, ImageFilter, ImageOps

Box = tuple[float, float, float, float]

# Pixels this close to magenta (per channel) become transparent.
KEY_TOLERANCE = 80


def load(png: bytes) -> Image.Image:
    image = Image.open(io.BytesIO(png))
    image.load()
    return image


def to_png(image: Image.Image) -> bytes:
    buf = io.BytesIO()
    image.save(buf, format="PNG", compress_level=3)
    return buf.getvalue()


def fit_size(
    image: Image.Image, size: tuple[int, int], tolerance: float = 0.03
) -> Image.Image | None:
    """The image at exactly `size`, resized if the aspect is close; None if the wrong shape."""
    if image.size == size:
        return image
    want, got = size[0] / size[1], image.width / image.height
    if abs(got - want) / want > tolerance:
        return None
    return image.resize(size, Image.Resampling.LANCZOS)


def cover_crop(image: Image.Image, aspect: tuple[int, int], tolerance: float = 0.01) -> Image.Image:
    """The centre of the image cut to the aspect of `aspect` (width, height), keeping as many
    pixels as possible; unchanged if it is already within `tolerance` of that aspect."""
    want = aspect[0] / aspect[1]
    got = image.width / image.height
    if abs(got - want) / want <= tolerance:
        return image
    if got > want:  # too wide: trim the sides
        width = max(1, round(image.height * want))
        left = (image.width - width) // 2
        return image.crop((left, 0, left + width, image.height))
    height = max(1, round(image.width / want))
    top = (image.height - height) // 2
    return image.crop((0, top, image.width, top + height))


def key_magenta(image: Image.Image, tolerance: int = KEY_TOLERANCE) -> Image.Image:
    """Makes the magenta background transparent, then trims a 1px edge to drop the pink fringe."""
    rgb = image.convert("RGB")
    r, g, b = rgb.split()

    def near(channel: Image.Image, target: int) -> Image.Image:
        return channel.point(lambda v: 255 if abs(v - target) <= tolerance else 0)

    background = ImageChops.multiply(ImageChops.multiply(near(r, 255), near(g, 0)), near(b, 255))
    alpha = ImageOps.invert(background).filter(ImageFilter.MinFilter(3))
    keyed = rgb.convert("RGBA")
    keyed.putalpha(alpha)
    return keyed


def coverage(cell: Image.Image) -> float:
    """Share of the cell that is opaque after keying (0 to 1)."""
    histogram = cell.getchannel("A").histogram()
    return sum(histogram[128:]) / (cell.width * cell.height)


def slice_grid(
    image: Image.Image, grid: tuple[int, int], names: Sequence[str]
) -> dict[str, Image.Image]:
    """Cuts a rows x cols grid into cells, named in row-major order."""
    rows, cols = grid
    if len(names) > rows * cols:
        raise ValueError(f"{len(names)} names for a {rows}x{cols} grid")
    cw, ch = image.width // cols, image.height // rows
    cells = {}
    for i, name in enumerate(names):
        r, c = divmod(i, cols)
        cells[name] = image.crop((c * cw, r * ch, (c + 1) * cw, (r + 1) * ch))
    return cells


def assemble(
    cells: dict[str, Image.Image], grid: tuple[int, int], names: Sequence[str]
) -> Image.Image:
    """Puts named cells back into one transparent sheet."""
    rows, cols = grid
    first = cells[names[0]]
    sheet = Image.new("RGBA", (first.width * cols, first.height * rows), (0, 0, 0, 0))
    for i, name in enumerate(names):
        r, c = divmod(i, cols)
        sheet.paste(cells[name], (c * first.width, r * first.height))
    return sheet


def thumbnail(image: Image.Image, max_side: int) -> Image.Image:
    thumb = image.copy()
    thumb.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
    return thumb


def alpha_box(cell: Image.Image) -> Box | None:
    """Bounding box of the opaque pixels, as fractions of the cell."""
    bbox = cell.getchannel("A").point(lambda v: 255 if v >= 128 else 0).getbbox()
    if bbox is None:
        return None
    x0, y0, x1, y1 = bbox
    return (x0 / cell.width, y0 / cell.height, (x1 - x0) / cell.width, (y1 - y0) / cell.height)


def estimate_head_box(cell: Image.Image) -> Box:
    """Top-of-silhouette guess for real image models: the head is the top ~28% of the figure.

    Raised arms make that band wide, so the box is narrowed to a squarish head around the band's
    centre of mass. Kids can fix bad guesses with the head-position nudges in the Lab.
    """
    alpha = cell.getchannel("A").point(lambda v: 255 if v >= 128 else 0)
    bbox = alpha.getbbox()
    if bbox is None:
        return (0.35, 0.1, 0.3, 0.3)
    x0, y0, x1, y1 = bbox
    head_h = max(1, round((y1 - y0) * 0.28))
    band = alpha.crop((x0, y0, x1, y0 + head_h))
    # Average each column down to one byte: how much of the band is filled in that column.
    weights = [float(v) for v in band.resize((band.width, 1), Image.Resampling.BOX).tobytes()]
    total = sum(weights) or 1.0
    cx = x0 + sum(i * w for i, w in enumerate(weights)) / total
    band_box = band.getbbox() or (0, 0, band.width, head_h)
    width = min(band_box[2] - band_box[0], head_h * 1.1)
    left = max(0.0, cx - width / 2)
    return (left / cell.width, y0 / cell.height, width / cell.width, head_h / cell.height)
