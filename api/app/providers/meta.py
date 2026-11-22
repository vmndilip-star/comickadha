"""Meta's model API (OpenAI-compatible chat completions), with LLM_PROVIDER=meta.

Settings: META_API_KEY, META_MODEL, META_VISION_MODEL (defaults to META_MODEL) and META_BASE_URL.
Model names come from .env, never from code. "-contributor" models are refused at startup because
requests to them may be used for training. Each call site passes its own max_tokens and timeout
(services/ai_limits.py; META_TIMEOUT_SECONDS is the fallback), and the openai client retries once
with backoff on 429 and 5xx. Each request logs its call name, token counts and seconds so the
quota can be watched; prompts, images and replies never are.
"""

import base64
import json
import logging
import time
from datetime import UTC, datetime
from typing import Any

import openai
from openai import OpenAI

from app.providers.llm import LLMError

log = logging.getLogger(__name__)


def check_model_name(
    model: str,
    setting: str,
    *,
    needed_by: str = "LLM_PROVIDER=meta",
    example: str = "muse-spark-1.3",
) -> None:
    if not model:
        raise ValueError(f"{needed_by} needs {setting} in .env (for example {example}).")
    if model.endswith("-contributor"):
        raise ValueError(
            f"{setting}={model} is a contributor model: requests to it may be used for training. "
            "Kids' content must not be, so pick the standard model instead."
        )


class MetaLLMProvider:
    name = "meta"

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        vision_model: str,
        base_url: str,
        timeout: float = 20.0,
        client: Any = None,
    ) -> None:
        if not api_key:
            raise ValueError("LLM_PROVIDER=meta needs META_API_KEY in .env.")
        check_model_name(model, "META_MODEL")
        check_model_name(vision_model, "META_VISION_MODEL")
        self.model = model
        self.vision_model = vision_model
        self.client = client or OpenAI(
            api_key=api_key, base_url=base_url, timeout=timeout, max_retries=1
        )
        self.last_call: dict[str, object] | None = None

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
        content: Any = prompt
        extra: dict[str, Any] = {"timeout": timeout} if timeout else {}
        if image_png is not None:
            url = "data:image/png;base64," + base64.b64encode(image_png).decode("ascii")
            content = [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": url}},
            ]
        text = self._chat(
            self.vision_model if image_png is not None else self.model,
            system,
            content,
            max_tokens,
            schema_name,
            response_format={
                "type": "json_schema",
                "json_schema": {"name": schema_name, "schema": schema, "strict": True},
            },
            **extra,
        )
        try:
            data = json.loads(text)
        except json.JSONDecodeError as error:
            raise LLMError("The model's reply wasn't JSON.") from error
        if not isinstance(data, dict):
            raise LLMError("The model's reply wasn't a JSON object.")
        return data

    def _chat(
        self,
        model: str,
        system: str,
        content: Any,
        max_tokens: int,
        call: str = "chat",
        **extra: Any,
    ) -> str:
        started = time.monotonic()
        try:
            response = self.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": content},
                ],
                max_tokens=max_tokens,
                temperature=0.7,
                **extra,
            )
        except openai.OpenAIError as error:
            log.warning("meta request failed: %s", type(error).__name__)
            self._record(False, type(error).__name__)
            raise LLMError("Meta's API didn't answer.") from error
        usage = getattr(response, "usage", None)
        log.info(
            "meta usage call=%s model=%s prompt_tokens=%s completion_tokens=%s total_tokens=%s "
            "max_tokens=%s seconds=%.1f",
            call,
            model,
            getattr(usage, "prompt_tokens", "?"),
            getattr(usage, "completion_tokens", "?"),
            getattr(usage, "total_tokens", "?"),
            max_tokens,
            time.monotonic() - started,
        )
        choice = response.choices[0] if response.choices else None
        text = choice.message.content if choice and choice.message else None
        # A model that thinks before it answers can spend the whole budget: nothing, or half a
        # reply (unusable JSON), comes back.
        if getattr(choice, "finish_reason", None) == "length":
            log.warning("meta reply cut off call=%s max_tokens=%s", call, max_tokens)
            self._record(False, "OutOfTokens")
            raise LLMError("Meta's reply was cut off.")
        if not text:
            self._record(False, "EmptyReply")
            raise LLMError("Meta's API sent an empty reply.")
        self._record(True, None)
        return str(text)

    def _record(self, ok: bool, error: str | None) -> None:
        """The last call's outcome, for the dev-only helper indicator (never prompts or keys)."""
        self.last_call = {"ok": ok, "at": datetime.now(UTC), "error": error}
