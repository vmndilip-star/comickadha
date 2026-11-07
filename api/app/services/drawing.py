"""Uploaded drawings: decoded, checked and shrunk in memory, then thrown away.

Nothing here touches disk or the database. The image is re-encoded as a fresh PNG, which drops
EXIF and every other bit of metadata, and downscaled so the longest side is at most 768 px.
"""

import base64
import binascii
import io
import re

from PIL import Image, ImageOps

from app.errors import ApiError

MAX_BYTES = 5 * 1024 * 1024
MAX_SIDE = 768
_DATA_URL = re.compile(r"data:image/(png|jpeg|jpg|webp|gif);base64,(.+)", re.S)

NOT_A_PICTURE = "That file doesn't look like a picture. Please upload a PNG or JPG drawing."
TOO_BIG = "That picture is too big. Please pick one under 5 MB."


def decode(data_url: str) -> tuple[bytes, Image.Image]:
    """-> (clean PNG bytes, the image). 422 if it isn't a picture, 413 if it is too big."""
    match = _DATA_URL.fullmatch(data_url.strip())
    if match is None:
        raise ApiError(422, "invalid", NOT_A_PICTURE)
    encoded = match.group(2)
    # Checked on the base64 length first, so a huge upload is refused before it is decoded.
    if len(encoded) * 3 // 4 - encoded.count("=", -2) > MAX_BYTES:
        raise ApiError(413, "too_big", TOO_BIG)
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as error:
        raise ApiError(422, "invalid", NOT_A_PICTURE) from error
    try:
        with Image.open(io.BytesIO(raw)) as source:
            source.load()
            image = ImageOps.exif_transpose(source).convert("RGB")
    except (OSError, ValueError, Image.DecompressionBombError) as error:
        raise ApiError(422, "invalid", NOT_A_PICTURE) from error
    image.thumbnail((MAX_SIDE, MAX_SIDE))
    out = io.BytesIO()
    image.save(out, "PNG")
    return out.getvalue(), image
