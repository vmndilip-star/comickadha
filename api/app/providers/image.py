"""Image generation interface. Phase 3 adds reference-guided sheet generation on top of it."""

from typing import Protocol

from pydantic import BaseModel, Field


class ImageRequest(BaseModel):
    prompt: str
    width: int
    height: int
    seed: int = 0
    # Reference images (PNG bytes) the result must stay consistent with.
    references: list[bytes] = Field(default_factory=list)
    # For sheets: rows x cols, and one label per cell in row-major order.
    grid: tuple[int, int] | None = None
    labels: list[str] = Field(default_factory=list)
    # Rendering hints only the mock uses (colours), so placeholders look like the character.
    hints: dict[str, str] = Field(default_factory=dict)


class ImageProvider(Protocol):
    name: str

    def generate(self, request: ImageRequest) -> bytes:
        """Returns PNG bytes."""
        ...
