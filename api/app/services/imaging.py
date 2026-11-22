"""Pillow helpers: load and encode PNGs, check shapes, key out magenta, assemble sheets."""

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
