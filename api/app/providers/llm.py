"""Text generation interface: the builder helper and safety classifier; the planner in Phase 4."""

from typing import Any, Protocol


class LLMError(Exception):
    """The model couldn't answer: network down, quota used up, or a reply we can't use."""


class LLMProvider(Protocol):
    name: str

    def complete(
        self,
        system: str,
        prompt: str,
        *,
        max_tokens: int = 1024,
        json_mode: bool = False,
    ) -> str:
        """Returns the model's reply. With json_mode, the reply must be a single JSON document."""
        ...

    def complete_json(
        self,
        system: str,
        prompt: str,
        schema: dict[str, Any],
        *,
        schema_name: str,
        image_png: bytes | None = None,
        max_tokens: int = 1024,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        """A reply that matches the JSON schema (structured output). image_png uses the vision
        model; timeout (seconds) overrides the provider's default for one long call. Raises
        LLMError if there is no usable reply."""
        ...
