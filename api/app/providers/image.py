"""Image generation interface: every provider turns a prompt into PNG bytes."""

from typing import Protocol, runtime_checkable


class ImageError(Exception):
    """The image model couldn't paint: network down, quota used up, a refusal, or a picture we
    can't read. Jobs treat it like a picture that came out wrong (a failed attempt)."""


class ImageProvider(Protocol):
    name: str

    def generate(
        self,
        prompt: str,
        size: tuple[int, int],
        seed: int,
        reference_images: list[bytes] | None = None,
    ) -> bytes:
        """Returns a PNG of `size` (width, height), or at least its aspect ratio.

        `reference_images` (PNG bytes) are what the result must stay consistent with,
        e.g. the character's front view when drawing the other poses.
        """
        ...


@runtime_checkable
class KnowsHeadBoxes(Protocol):
    """Optional: providers that know exactly where they drew each head (the mock does).

    Others get head boxes estimated from the cell's alpha mask.
    """

    def head_box(self, cell: str) -> tuple[float, float, float, float] | None:
        """(x, y, w, h) as fractions of the cell, for "body/<pose>" or "face/<expression>"."""
        ...
