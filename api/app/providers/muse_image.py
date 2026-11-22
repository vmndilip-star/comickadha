"""Meta's Muse Image model, with IMAGE_PROVIDER=muse (Meta's Model API, OpenAI-style Images API).

- No references: POST /images/generations (text to image), through client.images.generate.
- References: POST /images/edits with every reference, in order, as image[0], image[1]... Meta
  refuses the SDK's own field name (image[], a 400), so this posts the multipart form itself.
  Prompts name the references by position ("the first reference"), so the order matters.

Settings: META_API_KEY, META_IMAGE_MODEL (from .env, never from code; "-contributor" models are
refused), META_BASE_URL and META_IMAGE_TIMEOUT_SECONDS. `size` only sets the aspect ratio: the
server picks the pixels, so the picture is cover-cropped to the asked aspect before it is
returned (ImageProvider promises the aspect, callers resize). Pictures are decoded and re-encoded
as PNG with no metadata. Prompts and pictures are never logged.

Startup refuses IMAGE_PROVIDER=muse unless LLM_PROVIDER=meta (providers/__init__.py): the place
words go through the classifier and every picture through the image check before a kid sees it.
"""

import base64
import io
import logging
import urllib.request
from typing import Any

import openai
from openai import OpenAI
from openai.types import ImagesResponse
from PIL import Image

from app.providers.image import ImageError
from app.providers.meta import check_model_name
from app.services import imaging

log = logging.getLogger(__name__)

DOWNLOAD_LIMIT = 30 * 1024 * 1024

__all__ = ["ImageError", "MuseImageProvider"]


class MuseImageProvider:
    name = "muse"

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str,
        timeout: float = 60.0,
        client: Any = None,
    ) -> None:
        if not api_key:
            raise ValueError("IMAGE_PROVIDER=muse needs META_API_KEY in .env.")
        check_model_name(
            model, "META_IMAGE_MODEL", needed_by="IMAGE_PROVIDER=muse", example="muse-image-1.0"
        )
        self.model = model
        self.timeout = timeout
        self.client = client or OpenAI(
            api_key=api_key, base_url=base_url, timeout=timeout, max_retries=1
        )

    def generate(
        self,
        prompt: str,
        size: tuple[int, int],
        seed: int,
        reference_images: list[bytes] | None = None,
    ) -> bytes:
        # `seed` is not sent: Muse Image refuses it ("400 unknown parameter `seed`", Phase 6a), so
        # a retry simply draws again.
        del seed
        width, height = size
        try:
            if reference_images:
                # A fresh file object per reference per call: a used-up one silently sends nothing.
                files = [
                    (f"image[{i}]", (f"reference-{i + 1}.png", io.BytesIO(png), "image/png"))
                    for i, png in enumerate(reference_images)
                ]
                response = self.client.post(
                    "/images/edits",
                    cast_to=ImagesResponse,
                    body={
                        "model": self.model,
                        "prompt": prompt,
                        "size": f"{width}x{height}",
                        "n": 1,
                    },
                    files=files,
                    options={
                        "headers": {"Content-Type": "multipart/form-data"},
                        "security": {"bearer_auth": True},
                    },
                )
            else:
                response = self.client.images.generate(
                    model=self.model, prompt=prompt, size=f"{width}x{height}", n=1
                )
        except openai.OpenAIError as error:
            log.warning("muse image request failed: %s", type(error).__name__)
            raise ImageError("Muse Image didn't answer.") from error
        try:
            image = imaging.load(self._picture(response))
        except (OSError, ValueError) as error:
            raise ImageError("Muse Image sent a picture we can't read.") from error
        log.info("muse image size=%sx%s asked=%sx%s", image.width, image.height, width, height)
        return imaging.to_png(imaging.cover_crop(_clean(image), size))

    def _picture(self, response: Any) -> bytes:
        data = getattr(response, "data", None) or []
        if not data:
            raise ImageError("Muse Image sent no picture.")
        first = data[0]
        if b64 := getattr(first, "b64_json", None):
            return base64.b64decode(b64, validate=False)
        url = getattr(first, "url", None)
        if url and str(url).startswith("https://"):
            try:
                with urllib.request.urlopen(str(url), timeout=self.timeout) as reply:  # noqa: S310
                    picture: bytes = reply.read(DOWNLOAD_LIMIT + 1)
            except OSError as error:
                raise ImageError("Muse Image's picture couldn't be downloaded.") from error
            if len(picture) > DOWNLOAD_LIMIT:
                raise ImageError("Muse Image's picture is too big.")
            return picture
        raise ImageError("Muse Image sent no picture.")


def _clean(image: Image.Image) -> Image.Image:
    """The pixels only, as RGB (or RGBA if it has transparency): no ICC profile, text or EXIF."""
    has_alpha = image.mode in ("RGBA", "LA") or (image.mode == "P" and "transparency" in image.info)
    mode = "RGBA" if has_alpha else "RGB"
    converted = image.convert(mode)
    return Image.frombytes(mode, converted.size, converted.tobytes())
