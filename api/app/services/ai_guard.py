"""The one safe way to ask Meta's API something for a kid, shared by every AI helper.

    kid's words -> local checks -> classifier -> Meta -> model's words checked -> answer
                                       \\ any problem: the offline helper answers instead

- The kid's words never reach the model unless they pass the word list, the personal-info check
  and (with Meta) the classifier. Unsafe words are a 422 "unsafe" with a message for that field.
- If the classifier can't check the kid's words, the offline helper answers (nothing unchecked is
  ever sent to Meta).
- A reply that is valid JSON but fails the caller's check (or raises KeyError, TypeError or
  ValueError while being read) is asked for once more. Everything else falls back to the offline
  helper, labelled as such, with no retry: an outage, and also a reply that isn't JSON or was cut
  off at max_tokens (the provider raises LLMError for both, which counts as an outage), an unsafe
  reply, or one the classifier can't check. So a max_tokens that is too low silently turns a Meta
  feature offline: services/ai_limits.py holds the measured limits.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from sqlmodel import Session

from app.errors import ApiError
from app.providers.llm import LLMError, LLMProvider
from app.services import safety
from app.services.safety import SafetyUnavailable, Verdict

Raw = dict[str, Any]

META_LABEL = "Made with Meta AI"
OFFLINE_LABEL = "Made by the offline helper"
RESTING = "Our helper is resting. Here's an offline idea!"
UNSAFE = "Let's keep Comickadha friendly for everyone! Please try different words."


class InvalidReply(ValueError):
    """The model's reply doesn't have the shape we asked for."""


def label(source: str) -> str:
    return META_LABEL if source == "meta" else OFFLINE_LABEL


@dataclass
class Guard:
    llm: LLMProvider | None
    session: Session
    user_id: str
    # Set when the classifier couldn't check the kid's words: only the offline helper may answer.
    offline_only: bool = field(default=False, init=False)

    @property
    def source(self) -> str:
        return "meta" if self.llm is not None else "mock"

    def log(self, target: str, verdict: Verdict, kind: str = "text") -> None:
        safety.log_verdict(self.session, self.user_id, target, verdict, kind)

    def check_input(
        self,
        target: str,
        fields: dict[str, str],
        *,
        field_name: str | None = None,
        labels: dict[str, str] | None = None,
    ) -> None:
        """Raises 422 "unsafe" for unsafe words. A classifier outage means "offline only".

        With `labels` (field -> "your catchphrase"), the message says which words to change and
        the error names the blocked field; otherwise it names `field_name`."""
        verdict = safety.check_local(fields)
        if verdict.allowed and self.llm is not None:
            try:
                verdict = safety.classify(self.llm, fields)
            except SafetyUnavailable:
                self.offline_only = True
                self.log(target, Verdict(False, None, ["unavailable"]))
                return
        self.log(target, verdict)
        if not verdict.allowed:
            where = labels.get(verdict.field_name or "") if labels else None
            message = verdict.kid_message or (
                f"Let's keep Comickadha friendly for everyone! Please change {where} and try again."
                if where
                else UNSAFE
            )
            raise ApiError(422, "unsafe", message, verdict.field_name if labels else field_name)

    def output_ok(self, target: str, fields: dict[str, str]) -> bool:
        """The model's words pass the local checks and the classifier (fails closed)."""
        try:
            verdict = safety.check_text(fields, self.llm)
        except SafetyUnavailable:
            verdict = Verdict(False, None, ["unavailable"])
        self.log(target, verdict)
        return verdict.allowed

    @property
    def may_ask_meta(self) -> bool:
        return self.llm is not None and not self.offline_only

    def ask(
        self,
        meta: Callable[[LLMProvider], Raw],
        offline: Callable[[], Raw],
        *,
        check: Callable[[Raw], object],
        texts: Callable[[Raw], dict[str, str]],
        target: str,
    ) -> tuple[Raw, str, bool]:
        """Meta's reply if it's usable and safe, else the offline helper's.

        Returns (raw, source, fallback); fallback is True when Meta was set up but didn't answer.
        """
        if self.llm is not None and not self.offline_only:
            for _attempt in range(2):  # one more try for JSON that fails `check` (not for LLMError)
                try:
                    raw = meta(self.llm)
                    if not check(raw):
                        raise InvalidReply("missing fields")
                except (InvalidReply, KeyError, TypeError, ValueError):
                    continue
                except LLMError:
                    break
                fields = texts(raw)  # empty: the caller checks each text itself
                if not fields or self.output_ok(target, fields):
                    return raw, "meta", False
                break
        return offline(), "mock", self.llm is not None
