"""Make my comic: draw every panel as a job, re-draw one panel, final.png and the cover.

- `run_comic_job` draws the panels in order on the job runner: each panel's words get the local
  checks (plus the classifier when they aren't AI-checked yet), its place image gets check_image,
  then the compositor draws art.png and a thumbnail. Every panel ends in `panel_ready` or
  `panel_failed` (blocked words or picture, or a drawing error), so one bad panel never stops the
  rest. The cover (panel 1's final.png with the title) comes last.
- `draw_panel` is the same drawing, run straight away: Try again, and a face, pose or position
  change in the Reader. Text edits never re-draw art: bubbles are HTML in the Reader, and
  final.png is baked lazily (`ensure_final`) when its inputs change.
"""

import asyncio
import logging
from collections.abc import Callable
from typing import Any

from sqlalchemy import Engine
from sqlmodel import Session, col, select

from app.models import Background, Comic, Panel
from app.models.base import utcnow
from app.providers.llm import LLMProvider
from app.services import bubbles, compositor, image_gen, looks, pages, recheck, safety
from app.services.jobs import JobContext
from app.services.storage import Storage

log = logging.getLogger(__name__)

DEFAULT_TINT = "#FFE9A8"
DRAW_FAILED = "Oops, this panel didn't draw. Tap Try again!"

PanelJson = Callable[[Panel], dict[str, Any]]


def panel_prefix(panel: Panel) -> str:
    return f"comics/{panel.comic_id}/panels/{panel.id}"


def check_words(
    session: Session, user_id: str, panel: Panel, llm: LLMProvider | None
) -> safety.Verdict:
    """The panel's bubble words: the instant local checks always, and the full check (classifier)
    when they aren't AI-checked yet. Updates panel.text_check."""
    fields = recheck.bubble_fields(panel)
    if not fields:
        panel.text_check = "checked"
        return safety.Verdict(True)
    if panel.text_check in recheck.WAITING:
        verdict = safety.check_story(session, user_id, f"panel:{panel.id}", fields, llm)
        if verdict.allowed:
            panel.text_check = "pending" if verdict.pending else "checked"
        return verdict
    verdict = safety.check_local(fields)
    if not verdict.allowed:
        safety.log_verdict(session, user_id, f"panel:{panel.id}", verdict, "text")
    return verdict


def draw_panel(
    session: Session, storage: Storage, panel: Panel, user_id: str, llm: LLMProvider | None
) -> None:
    """Checks and draws one panel now, leaving it ready, blocked or failed (not committed)."""
    words = check_words(session, user_id, panel, llm)
    if not words.allowed:
        panel.status, panel.error = "blocked", words.message({})
        return
    background = session.get(Background, panel.background_id)
    place_png = None
    if background is not None:
        if panel.place_version is None:  # pinned the first time it is drawn
            panel.place_version = background.version
        place_png = image_gen.place_picture(
            storage, background, panel.place_version, panel.time_of_day
        )
    picture = safety.check_image(session, user_id, f"panel:{panel.id}:place", place_png)
    if not picture.allowed:
        panel.status, panel.error = "blocked", picture.message({})
        return
    try:
        specs = looks.specs_for(session, panel.characters)
        panel.bubbles = bubbles.layout(panel.bubbles, panel.characters, specs, panel.shown_size)
        art, thumb = compositor.render_art(
            panel.characters,
            specs,
            place_png,
            background.tint if background else DEFAULT_TINT,
            panel.bubbles,
            panel.props or [],
            panel.shown_size,
        )
        prefix = panel_prefix(panel)
        panel.art_key = storage.save(f"{prefix}/art.png", art)
        panel.thumb_key = storage.save(f"{prefix}/thumb.png", thumb)
    except Exception:
        log.exception("panel %s failed to draw", panel.id)
        panel.status, panel.error = "failed", DRAW_FAILED
        return
    panel.art_version = (panel.art_version or 0) + 1
    panel.status, panel.error = "ready", None
    panel.updated_at = utcnow()


def reshape(
    session: Session,
    storage: Storage,
    comic_id: str,
    user_id: str,
    llm: LLMProvider | None,
    *,
    hold: str | None = None,
    draw: bool = True,
) -> list[Panel]:
    """Every panel's shown size from the sizes chosen for the comic's panels (services/pages.py:
    a normal panel alone in its row is shown wide...). A panel whose shown size changes gets its
    bubbles laid out again and, if it was drawn, is drawn again at its new size (unless not
    `draw`: Make my comic! draws every panel next anyway). `hold`: a panel the caller lays out and
    draws itself (it only gets its new shown size). Not committed. Returns the panels that
    changed."""
    stmt = select(Panel).where(Panel.comic_id == comic_id).order_by(col(Panel.idx))
    rows = list(session.exec(stmt))
    changed: list[Panel] = []
    for panel, shown in zip(
        rows, pages.shown_sizes([p.size or "normal" for p in rows]), strict=True
    ):
        before = panel.shown_size
        if before == shown:
            continue
        panel.shown_size = shown
        session.add(panel)
        if panel.id == hold or (before or "normal") == shown:
            continue  # only stored for the first time: drawn at this size already
        specs = looks.specs_for(session, panel.characters)
        panel.bubbles = bubbles.layout(panel.bubbles, panel.characters, specs, shown)
        if panel.art_key and draw:
            draw_panel(session, storage, panel, user_id, llm)
        changed.append(panel)
    return changed


def ensure_final(session: Session, storage: Storage, panel: Panel) -> bytes:
    """final.png (art + bubbles), baked again only when the art or the bubbles changed."""
    if not panel.art_key:
        raise LookupError(panel.id)
    wanted = compositor.final_hash(panel.art_key, panel.art_version, panel.bubbles)
    if panel.final_key and panel.final_hash == wanted and storage.exists(panel.final_key):
        return storage.read(panel.final_key)
    png = compositor.bake_final(storage.read(panel.art_key), panel.bubbles, panel.shown_size)
    panel.final_key = storage.save(f"{panel_prefix(panel)}/final.png", png)
    panel.final_hash = wanted
    session.add(panel)
    session.commit()
    return png


def make_cover(session: Session, storage: Storage, comic: Comic) -> None:
    """Panel 1's final.png with the title in Bangers, for My Comics and Home."""
    first = session.exec(
        select(Panel).where(Panel.comic_id == comic.id).order_by(col(Panel.idx))
    ).first()
    if first is None or first.status != "ready" or not first.art_key:
        return
    png = compositor.cover(ensure_final(session, storage, first), comic.title)
    comic.cover_key = storage.save(f"comics/{comic.id}/cover.png", png)
    session.add(comic)
    session.commit()


def _draw_one(
    engine: Engine,
    storage: Storage,
    llm: LLMProvider | None,
    panel_id: str,
    read: PanelJson,
) -> dict[str, Any]:
    with Session(engine) as session:
        panel = session.get(Panel, panel_id)
        comic = session.get(Comic, panel.comic_id) if panel else None
        if panel is None or comic is None:
            return {}
        draw_panel(session, storage, panel, comic.user_id, llm)
        session.add(panel)
        session.commit()
        session.refresh(panel)
        return read(panel)


def _set_status(engine: Engine, panel_id: str, status: str) -> None:
    with Session(engine) as session:
        panel = session.get(Panel, panel_id)
        if panel is not None:
            panel.status, panel.error = status, None
            session.add(panel)
            session.commit()


def _finish(engine: Engine, storage: Storage, comic_id: str) -> str | None:
    with Session(engine) as session:
        comic = session.get(Comic, comic_id)
        if comic is None:
            return None
        make_cover(session, storage, comic)
        return storage.url(comic.cover_key) if comic.cover_key else None


async def run_comic_job(
    ctx: JobContext,
    *,
    comic_id: str,
    engine: Engine,
    storage: Storage,
    llm: LLMProvider | None,
    read: PanelJson,
    reveal_seconds: float,
) -> dict[str, Any]:
    """Draws every panel in order, then the cover. Events: progress (which panel is being
    inked), panel_ready / panel_failed (with the panel), then done (with the cover)."""
    with Session(engine) as session:
        ids = list(
            session.exec(
                select(Panel.id).where(Panel.comic_id == comic_id).order_by(col(Panel.idx))
            )
        )
    total = len(ids)
    ready = 0
    for i, panel_id in enumerate(ids):
        await ctx.run(_set_status, engine, panel_id, "rendering")
        ctx.emit("progress", {"stage": "inking", "panel_id": panel_id, "idx": i}, i / (total + 1))
        panel = await ctx.run(_draw_one, engine, storage, llm, panel_id, read)
        ok = panel.get("status") == "ready"
        ready += ok
        ctx.emit("panel_ready" if ok else "panel_failed", {"panel": panel}, (i + 1) / (total + 1))
        if reveal_seconds:
            await asyncio.sleep(reveal_seconds)
    cover_url = await ctx.run(_finish, engine, storage, comic_id)
    return {"ready": ready, "failed": total - ready, "cover_url": cover_url}
