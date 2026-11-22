"""Text generation interface for every Meta call: the Lab helper, Create character, Story Buddy,
the planner, the safety classifier and the image check (services/ai_limits.py lists them)."""

from typing import Any, Protocol


class LLMError(Exception):
    """The model couldn't answer: network down, quota used up, or a reply we can't use."""


class LLMProvider(Protocol):
    name: str

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
