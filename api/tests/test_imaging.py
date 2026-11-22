from PIL import Image, ImageDraw

from app.providers.mock import MockImageProvider
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


def test_the_mock_paints_places_deterministically() -> None:
    mock = MockImageProvider()
    prompt = "Place: Sunny park\nDescription: A park.\nPalette: tint=#B7E4A7"

    first = mock.generate(prompt, (1024, 768), seed=7)

    assert first == mock.generate(prompt, (1024, 768), seed=7)
    assert first != mock.generate(prompt, (1024, 768), seed=8)
    image = imaging.load(first)
    assert (image.size, image.mode) == ((1024, 768), "RGB")
    assert imaging.coverage(imaging.key_magenta(image)) > 0.99  # a scene, no magenta
