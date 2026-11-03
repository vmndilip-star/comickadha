"""LLM and image providers, chosen by IMAGE_PROVIDER / LLM_PROVIDER. Mock until Phase 6."""

from app.config import Settings
from app.providers.image import ImageProvider
from app.providers.mock import MockImageProvider


def get_image_provider(settings: Settings) -> ImageProvider:
    match settings.image_provider:
        case "mock":
            return MockImageProvider(delay_seconds=settings.mock_delay_seconds)
