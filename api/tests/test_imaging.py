from PIL import Image, ImageDraw

from app.providers.mock import MockImageProvider
from app.schemas.common import EXPRESSIONS, POSES
from app.services import imaging

MAGENTA = (255, 0, 255)


def test_magenta_keys_to_the_expected_alpha() -> None:
    image = Image.new("RGB", (40, 40), MAGENTA)
    ImageDraw.Draw(image).rectangle((10, 10, 29, 29), fill=(200, 30, 30))  # a 20x20 red square
    image.putpixel((2, 2), (250, 10, 245))  # near-magenta noise, inside the tolerance

    alpha = imaging.key_magenta(image).getchannel("A")

    assert alpha.getpixel((0, 0)) == 0
    assert alpha.getpixel((2, 2)) == 0
    assert alpha.getpixel((20, 20)) == 255
    assert alpha.getpixel((10, 10)) == 0  # the 1px edge cleanup trims the outline
    assert alpha.getpixel((11, 11)) == 255
    assert alpha.histogram()[255] == 18 * 18
    assert alpha.histogram()[0] == 40 * 40 - 18 * 18


def _numbered_grid(rows: int, cols: int, cell: int) -> Image.Image:
    """Each cell filled with a colour that encodes its index."""
    image = Image.new("RGB", (cols * cell, rows * cell))
    draw = ImageDraw.Draw(image)
    for i in range(rows * cols):
        r, c = divmod(i, cols)
        draw.rectangle(
            (c * cell, r * cell, (c + 1) * cell - 1, (r + 1) * cell - 1), fill=(i * 10, 0, 0)
        )
    return image


def test_slicing_a_4x4_body_sheet() -> None:
    cells = imaging.slice_grid(_numbered_grid(4, 4, 256), (4, 4), list(POSES))

    assert list(cells) == list(POSES)
    assert all(cell.size == (256, 256) for cell in cells.values())
    for i, pose in enumerate(POSES):
        assert cells[pose].getpixel((128, 128)) == (i * 10, 0, 0)


def test_slicing_a_2x3_face_sheet() -> None:
    cells = imaging.slice_grid(_numbered_grid(2, 3, 256), (2, 3), list(EXPRESSIONS))

    assert list(cells) == list(EXPRESSIONS)
    assert all(cell.size == (256, 256) for cell in cells.values())
    assert cells["laughing"].getpixel((5, 5)) == (50, 0, 0)  # row 1, col 2


def test_head_estimate_finds_the_head_even_with_raised_arms() -> None:
    cell = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
    draw = ImageDraw.Draw(cell)
    draw.ellipse((98, 30, 158, 90), fill=(240, 190, 150, 255))  # head centred at x=128
    draw.rectangle((100, 92, 156, 230), fill=(255, 230, 160, 255))
    draw.line((100, 100, 40, 20), fill=(240, 190, 150, 255), width=12)
    draw.line((156, 100, 216, 20), fill=(240, 190, 150, 255), width=12)

    x, y, w, h = imaging.estimate_head_box(cell)

    assert abs((x + w / 2) * 256 - 128) < 12
    assert w * 256 < 90
    assert 0 < h < 0.4


def test_mock_is_deterministic_and_knows_its_heads() -> None:
    mock = MockImageProvider()
    prompt = (
        "Sheet: body\nLayout: 1 row(s) x 4 column(s) of equal square cells.\n"
        "Cells (left to right, top to bottom): walk | run | point | sit\n"
        "Palette: kind=kid; skin=#C98B5E; hair=#1A1A1A; hair_style=spiky; outfit=#FFD0C2"
    )

    first = mock.generate(prompt, (1024, 256), seed=7)

    assert first == mock.generate(prompt, (1024, 256), seed=7)
    assert imaging.load(first).size == (1024, 256)
    box = mock.head_box("body/walk")
    assert box is not None
    assert all(0 <= v <= 1 for v in box)
