"""LLM and image providers, selected by env var. Only the mock providers exist until Phase 6."""

from app.config import Settings
from app.providers.image import ImageProvider
from app.providers.mock import MockImageProvider


def get_image_provider(settings: Settings) -> ImageProvider:
    match settings.image_provider:
        case "mock":
            return MockImageProvider()
