"""Text generation interface for the story planner, story buddy and safety classifier (Phase 4)."""

from typing import Protocol


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
