"""Providers, chosen by settings: IMAGE_PROVIDER and LLM_PROVIDER."""

from app.config import Settings
from app.providers.image import ImageProvider
from app.providers.llm import LLMProvider
from app.providers.meta import MetaLLMProvider
from app.providers.mock import MockImageProvider
from app.providers.muse_image import MuseImageProvider

NEEDS_CHECKS = (
    "IMAGE_PROVIDER=muse needs LLM_PROVIDER=meta: real pictures are only made when the place words "
    "can go through the safety classifier and every picture through the image check. "
    "Set LLM_PROVIDER=meta (with META_MODEL), or use IMAGE_PROVIDER=mock."
)


def get_image_provider(settings: Settings) -> ImageProvider:
    """IMAGE_PROVIDER=muse checks its settings here, so a bad setting stops the server at startup.
    It fails closed by configuration: no real images without the classifier and the image check."""
    match settings.image_provider:
        case "mock":
            return MockImageProvider(delay_seconds=settings.mock_delay_seconds)
        case "muse":
            if settings.llm_provider != "meta":
                raise ValueError(NEEDS_CHECKS)
            return MuseImageProvider(
                api_key=settings.meta_api_key,
                model=settings.meta_image_model,
                base_url=settings.meta_base_url,
                timeout=settings.meta_image_timeout_seconds,
            )


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
