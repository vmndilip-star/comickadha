"""Re-checking story text that is "not yet AI-checked" (decision 55).

During a Meta outage, story text that passes the local checks is saved as `pending`. This runs
the full check again (local + classifier) on pending comics (title, synopsis) and panels (bubble
words): from a background loop every `recheck_seconds`, and on demand before a PDF. It stops at
the first classifier outage, since Meta is still down. A later block is stored where the kid will
see it: `comic.check_note` (shown under the field) or the panel's error.
With LLM_PROVIDER=mock there is no classifier, so the local checks count as the full check.
"""

import logging

from sqlalchemy import Engine
from sqlmodel import Session, col, select

from app.models import Comic, Panel
from app.providers.llm import LLMProvider
from app.services import safety

log = logging.getLogger(__name__)

STORY_LABELS = {"title": "title", "synopsis": "story"}
WAITING = ("pending", "blocked")


def bubble_fields(panel: Panel) -> dict[str, str]:
    """The panel's bubble words, keyed by field name, so a block names the bubble."""
    return {
        f"bubbles.{b.get('id')}.text": str(b.get("text", ""))
        for b in panel.bubbles
        if str(b.get("text", "")).strip()
    }


def recheck(session: Session, llm: LLMProvider | None, comic_id: str | None = None) -> int:
    """Settles pending comics and panels (all, or one comic's). Returns how many were settled."""
    comics = select(Comic).where(Comic.text_check == "pending", col(Comic.deleted_at).is_(None))
    panels = select(Panel).where(Panel.text_check == "pending")
    if comic_id:
        comics = comics.where(Comic.id == comic_id)
        panels = panels.where(Panel.comic_id == comic_id)
    settled = 0
    try:
        for comic in session.exec(comics).all():
            verdict = safety.check_text({"title": comic.title, "synopsis": comic.synopsis}, llm)
            safety.log_verdict(session, comic.user_id, f"recheck:comic:{comic.id}", verdict, "text")
            comic.text_check = "checked" if verdict.allowed else "blocked"
            comic.check_note = (
                None
                if verdict.allowed
                else {
                    "field": verdict.field_name or "title",
                    "message": verdict.message(STORY_LABELS),
                }
            )
            session.add(comic)
            settled += 1
        for panel in session.exec(panels).all():
            owner = session.get(Comic, panel.comic_id)
            fields = bubble_fields(panel)
            verdict = safety.check_text(fields, llm) if fields else safety.Verdict(True)
            if owner is not None:
                target = f"recheck:panel:{panel.id}"
                safety.log_verdict(session, owner.user_id, target, verdict, "text")
            panel.text_check = "checked" if verdict.allowed else "blocked"
            if not verdict.allowed:
                panel.error = verdict.message({})
            session.add(panel)
            settled += 1
    except safety.SafetyUnavailable:
        log.info("safety helper still resting; %d item(s) re-checked so far", settled)
    session.commit()
    return settled


def recheck_all(engine: Engine, llm: LLMProvider | None) -> int:
    with Session(engine) as session:
        return recheck(session, llm)
