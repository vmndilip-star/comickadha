"""Pictures from an image model, painted and checked the same way everywhere: places, portraits
(decision 132) and, in Phase B, panels.

Each picture gets PAINT_ATTEMPTS tries. A picture from a real image model passes the image check
before anything else happens to it; a character picture then passes the look check too (it
compares the builder drawing with the painting). A blocked or look-failed picture gets one more
try with a stronger instruction; a checker outage raises CheckerResting at once (fails closed).
Nothing comes back unless a picture passes. The daily caps (decision 134) count every image model
call in the paint log.
"""

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from datetime import time as day_time

from PIL import Image
from sqlalchemy import Engine, func
from sqlmodel import Session, col, select

from app.config import Settings
from app.models import PaintLog
from app.prompts import render
from app.providers.image import ImageError, ImageProvider
from app.providers.llm import LLMProvider
from app.services import imaging, safety
from app.services.ai_limits import PAINT_ATTEMPTS
from app.services.safety import Verdict

Check = Callable[[bytes], Verdict]
Fit = Callable[[bytes], Image.Image | None]

KEEP_LOOK = "paint_keep_look"  # the prompt added after a look check fails


class CheckerResting(Exception):
    """The image check or the look check didn't answer: nothing is saved."""


@dataclass(frozen=True)
class LookVerdict:
    """What the look check saw. `hard_fail` rejects the picture; `findings` list every difference
    it saw (hard ones and the ones that are only logged), in plain words for the paint log."""

    hard_fail: bool
    findings: list[str] = field(default_factory=list)
    # Head centres in the painting, left to right, as fractions of its width and height.
    heads: list[tuple[float, float]] = field(default_factory=list)


Look = Callable[[bytes], LookVerdict]


@dataclass(frozen=True)
class Painted:
    png: bytes | None
    attempts: int
    outcome: str  # "saved", "blocked", "look_failed" or "error"
    findings: list[str] = field(default_factory=list)
    ms: int = 0
    heads: list[tuple[float, float]] = field(default_factory=list)


def needs_image_check(provider: ImageProvider) -> bool:
    """Pictures from any real image model are checked; the mock's are drawn on this machine."""
    return provider.name != "mock"


def paint_checked(
    prompt: str,
    size: tuple[int, int],
    provider: ImageProvider,
    seed: int,
    references: list[bytes] | None,
    *,
    fit: Fit,
    check: Check | None = None,
    look: Look | None = None,
    on_checking: Callable[[], None] | None = None,
) -> Painted:
    """One picture, painted and checked, with one more try. Blocking (call it off the event loop).
    `fit` turns the model's bytes into the picture to keep (None: unusable). With `check` (a real
    model), the image check runs on every picture, then `look` if given."""
    start = time.monotonic()
    outcome, attempts = "error", 0
    findings: list[str] = []

    def result(png: bytes | None, heads: list[tuple[float, float]] | None = None) -> Painted:
        ms = round((time.monotonic() - start) * 1000)
        return Painted(png, attempts, outcome, findings, ms, heads or [])

    for attempt in range(PAINT_ATTEMPTS):
        attempts += 1
        try:
            image = fit(provider.generate(prompt, size, seed + attempt * 7919, references))
        except ImageError:
            image = None
        if image is None:
            outcome = "error"
            continue
        candidate = imaging.to_png(image)
        if check is None:
            outcome = "saved"
            return result(candidate)
        if on_checking:
            on_checking()
        verdict = check(candidate)
        if "unavailable" in verdict.categories:
            raise CheckerResting()
        if not verdict.allowed:
            outcome = "blocked"
            if "text" in verdict.categories:
                prompt = prompt + "\n\n" + render("background_no_text")
            continue
        if look is not None:
            seen = look(candidate)
            findings = seen.findings
            if seen.hard_fail:
                outcome = "look_failed"
                if render(KEEP_LOOK) not in prompt:
                    prompt = prompt + "\n\n" + render(KEEP_LOOK)
                continue
            outcome = "saved"
            return result(candidate, seen.heads)
        outcome = "saved"
        return result(candidate)
    return result(None)


def image_check(
    engine: Engine, provider: ImageProvider, llm: LLMProvider | None, user_id: str, target: str
) -> Check | None:
    """The image check for a real model's pictures (None for the mock's), logged under `target`.
    Raises CheckerResting without an LLM (startup refuses that set-up anyway)."""
    if not needs_image_check(provider):
        return None
    if llm is None:
        raise CheckerResting()
    checker = llm

    def check(png: bytes) -> Verdict:
        with Session(engine) as session:
            return safety.check_image(session, user_id, target, png, checker)

    return check


# ---- the paint log and the daily caps (decision 134) ----------------------------------------


def log_paint(
    engine: Engine,
    *,
    user_id: str,
    kind: str,
    target: str,
    provider: str,
    painted: Painted,
    seed_run: bool = False,
) -> None:
    with Session(engine) as session:
        session.add(
            PaintLog(
                user_id=user_id,
                kind=kind,
                target=target,
                provider=provider,
                attempts=painted.attempts,
                ms=painted.ms,
                outcome=painted.outcome,
                findings=painted.findings,
                seed_run=seed_run,
            )
        )
        session.commit()


def _calls_today(session: Session, *, user_id: str | None = None, kind: str | None = None) -> int:
    """Image model calls since midnight (UTC), retries included; the mock and seed runs don't
    count."""
    midnight = datetime.combine(datetime.now(UTC).date(), day_time(0), tzinfo=UTC)
    stmt = select(func.coalesce(func.sum(PaintLog.attempts), 0)).where(
        col(PaintLog.created_at) >= midnight,
        PaintLog.provider != "mock",
        col(PaintLog.seed_run).is_(False),
    )
    if user_id is not None:
        stmt = stmt.where(PaintLog.user_id == user_id)
    if kind is not None:
        stmt = stmt.where(PaintLog.kind == kind)
    return int(session.exec(stmt).one())


def daily_cap_reached(
    session: Session, settings: Settings, provider: ImageProvider, user_id: str, kind: str
) -> bool:
    """Whether another `kind` picture today would go over this kid's cap or everyone's. Pictures
    from the mock are free, so it never reaches a cap."""
    if not needs_image_check(provider):
        return False
    per_kid = {"portrait": settings.portrait_paints_per_kid, "panel": settings.panel_paints_per_kid}
    if _calls_today(session, user_id=user_id, kind=kind) >= per_kid.get(kind, 0):
        return True
    return _calls_today(session) >= settings.paints_per_day
