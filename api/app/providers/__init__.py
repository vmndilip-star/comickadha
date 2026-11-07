"""Providers, chosen by settings: IMAGE_PROVIDER, LLM_PROVIDER and SHEET_PROVIDER."""

from app.config import Settings
from app.providers.image import ImageProvider
from app.providers.llm import LLMProvider
from app.providers.meta import MetaLLMProvider
from app.providers.mock import MockImageProvider


def get_image_provider(settings: Settings) -> ImageProvider:
    match settings.image_provider:
        case "mock":
            return MockImageProvider(delay_seconds=settings.mock_delay_seconds)


def get_llm_provider(settings: Settings) -> LLMProvider | None:
    """None means offline: the builder uses its offline helper and safety its word list.

    LLM_PROVIDER=meta checks its settings here, so a bad model name stops the server at startup.
    """
    match settings.llm_provider:
        case "mock":
            return None
        case "meta":
            return MetaLLMProvider(
                api_key=settings.meta_api_key,
                model=settings.meta_model,
                vision_model=settings.resolved_vision_model,
                base_url=settings.meta_base_url,
                timeout=settings.meta_timeout_seconds,
            )
