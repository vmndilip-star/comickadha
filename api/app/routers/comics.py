"""Comics, scenes and panels; Make my comic! (generate), re-drawing a panel, final.png and PDF."""

import re
from collections import defaultdict
from functools import partial
from typing import Any, Literal

from fastapi import APIRouter, Query, Request, Response
from sqlalchemy import Engine
from sqlmodel import Session, col, select

from app.deps import EngineDep, JobsDep, LLMDep, SessionDep, StorageDep, UserDep
from app.errors import ERROR_RESPONSES, ApiError, invalid, not_found
from app.models import Background, Character, Comic, Job, Panel, Scene, User
from app.models.base import new_id, utcnow
from app.routers import backgrounds as background_routes
from app.routers import characters as character_routes
from app.schemas.comic import (
    ComicCreate,
    ComicRead,
    ComicUpdate,
    PanelRead,
    PanelUpdate,
    SceneRead,
    SceneWrite,
)
from app.schemas.common import ComicStatus, FieldNote
from app.schemas.job import JobStarted
from app.services import comic_maker, looks, pdf_export, recheck, safety
from app.services.bubbles import layout
from app.services.jobs import FAILED_MESSAGE, fail_rendering_panels
from app.services.recheck import STORY_LABELS
from app.services.storage import Storage

router = APIRouter(prefix="/api", tags=["comics"], responses=ERROR_RESPONSES)

MAX_SCENES = 8


def get_comic(session: Session, user: User, comic_id: str) -> Comic:
    comic = session.get(Comic, comic_id)
    if comic is None or comic.user_id != user.id or comic.deleted_at is not None:
        raise not_found("comic")
    return comic


def scene_read(scene: Scene) -> SceneRead:
    return SceneRead.model_validate(scene.model_dump())


def panel_read(panel: Panel, storage: Storage) -> PanelRead:
    version = f"?v={panel.art_version}" if panel.art_version else ""
    return PanelRead.model_validate(
        {
            **panel.model_dump(),
            "art_url": storage.url(panel.art_key) + version if panel.art_key else None,
            "thumb_url": storage.url(panel.thumb_key) + version if panel.thumb_key else None,
            "final_url": f"/api/panels/{panel.id}/final.png" if panel.art_key else None,
            "image_url": storage.url(panel.image_key) if panel.image_key else None,
            "text_check": panel.text_check or "checked",
        }
    )


def safety_notes(comic: Comic) -> list[FieldNote]:
    """The instant local checks (personal info, word list) on the title and synopsis."""
    notes: list[FieldNote] = []
    for name in ("title", "synopsis"):
        verdict = safety.check_local({name: getattr(comic, name)})
        if not verdict.allowed:
            notes.append(FieldNote(field=name, message=verdict.message(STORY_LABELS)))
    note = comic.check_note
    if note and not any(n.field == note.get("field") for n in notes):
        notes.append(FieldNote(field=str(note["field"]), message=str(note["message"])))
    return notes


def comic_reads(session: Session, comics: list[Comic], storage: Storage) -> list[ComicRead]:
    """Builds full comics (with scenes and panels) using two queries for the whole list."""
    ids = [c.id for c in comics]
    scenes: defaultdict[str, list[Scene]] = defaultdict(list)
    panels: defaultdict[str, list[Panel]] = defaultdict(list)
    if ids:
        for scene in session.exec(
            select(Scene).where(col(Scene.comic_id).in_(ids)).order_by(col(Scene.idx))
        ):
            scenes[scene.comic_id].append(scene)
        for panel in session.exec(
            select(Panel).where(col(Panel.comic_id).in_(ids)).order_by(col(Panel.idx))
        ):
            panels[panel.comic_id].append(panel)

    # Characters and places each comic uses, deleted or not, in first-use order.
    used_chars: dict[str, list[str]] = {}
    used_bgs: dict[str, list[str]] = {}
    for c in comics:
        char_ids = [*c.cast_ids]
        bg_ids: list[str] = []
        for s in scenes[c.id]:
            char_ids += s.character_ids
            bg_ids.append(s.background_id)
        for p in panels[c.id]:
            char_ids += [pc["id"] for pc in p.characters]
            bg_ids.append(p.background_id)
        used_chars[c.id] = list(dict.fromkeys(char_ids))
        used_bgs[c.id] = list(dict.fromkeys(bg_ids))
    all_chars = {cid for ids in used_chars.values() for cid in ids}
    pinned = looks.looks_for(
        session,
        {
            (pc["id"], int(pc.get("sheet_version", 0)))
            for ps in panels.values()
            for p in ps
            for pc in p.characters
        },  # fmt: skip
    )
    all_bgs = {bid for ids in used_bgs.values() for bid in ids}
    chars = {
        ch.id: character_routes.to_read(ch)
        for ch in session.exec(select(Character).where(col(Character.id).in_(all_chars)))
    }
    bgs = {
        bg.id: background_routes.to_read(bg, storage)
        for bg in session.exec(select(Background).where(col(Background.id).in_(all_bgs)))
    }

    return [
        ComicRead.model_validate(
            {
                **c.model_dump(),
                "cover_url": (
                    f"{storage.url(c.cover_key)}?v={int(c.updated_at.timestamp())}"
                    if c.cover_key
                    else None
                ),
                "scenes": [scene_read(s) for s in scenes[c.id]],
                "panels": [panel_read(p, storage) for p in panels[c.id]],
                "characters": [chars[i] for i in used_chars[c.id] if i in chars],
                "backgrounds": [bgs[i] for i in used_bgs[c.id] if i in bgs],
                "safety_notes": safety_notes(c),
                "looks": {
                    cid: pinned[cid]
                    for cid in {pc["id"] for p in panels[c.id] for pc in p.characters}
                    if cid in pinned
                },
                "text_check": c.text_check or "checked",
            }
        )
        for c in comics
    ]


def comic_read(session: Session, comic: Comic, storage: Storage) -> ComicRead:
    return comic_reads(session, [comic], storage)[0]


def _owned_place_ids(session: Session, user: User, ids: list[str]) -> set[str]:
    if not ids:
        return set()
    stmt = select(Background.id).where(Background.user_id == user.id, col(Background.id).in_(ids))
    return set(session.exec(stmt))


# Comics may use the kid's own characters and the starter characters (part B).
_usable_character_ids = character_routes.usable_character_ids


# ---- comics -------------------------------------------------------------------------------------


@router.get("/comics")
def list_comics(
    session: SessionDep,
    user: UserDep,
    storage: StorageDep,
    status: ComicStatus | None = None,
    q: str | None = Query(default=None, max_length=60, description="Search in titles"),
    sort: Literal["updated", "created"] = "updated",
) -> list[ComicRead]:
    stmt = select(Comic).where(Comic.user_id == user.id, col(Comic.deleted_at).is_(None))
    if status:
        stmt = stmt.where(Comic.status == status)
    if q and q.strip():
        term = q.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        stmt = stmt.where(col(Comic.title).ilike(f"%{term}%", escape="\\"))
    order = col(Comic.updated_at) if sort == "updated" else col(Comic.created_at)
    comics = list(session.exec(stmt.order_by(order.desc())))
    return comic_reads(session, comics, storage)


@router.post("/comics", status_code=201)
def create_comic(
    body: ComicCreate, session: SessionDep, user: UserDep, storage: StorageDep
) -> ComicRead:
    comic = Comic(user_id=user.id, title=body.title, synopsis=body.synopsis)
    session.add(comic)
    session.commit()
    session.refresh(comic)
    return comic_read(session, comic, storage)


@router.get("/comics/{comic_id}")
def read_comic(comic_id: str, session: SessionDep, user: UserDep, storage: StorageDep) -> ComicRead:
    return comic_read(session, get_comic(session, user, comic_id), storage)


@router.patch("/comics/{comic_id}")
def update_comic(
    comic_id: str,
    body: ComicUpdate,
    session: SessionDep,
    user: UserDep,
    storage: StorageDep,
    llm: LLMDep,
) -> ComicRead:
    comic = get_comic(session, user, comic_id)
    changes = body.model_dump(exclude_unset=True, exclude_none=True)
    if "cast_ids" in changes:
        cast_ids: list[str] = list(
            dict.fromkeys(changes["cast_ids"])
        )  # drop duplicates, keep order
        # Characters already in the comic may stay even if deleted; new ones must be active.
        added = [i for i in cast_ids if i not in comic.cast_ids]
        if _usable_character_ids(session, user, cast_ids) != set(cast_ids) or (
            _usable_character_ids(session, user, added, active=True) != set(added)
        ):
            raise invalid("Pick characters from your cast or the starter characters.")
        changes["cast_ids"] = cast_ids
    if changes.get("status") == "finished":
        _require_drawn(session, comic, "finish")
    for field, value in changes.items():
        setattr(comic, field, value)
    if changes.keys() - {"status", "studio_step"}:
        comic.status = "draft"  # editing a finished comic makes it a draft again
    words = {name: changes[name] for name in ("title", "synopsis") if name in changes}
    if words:
        # Autosave runs only the instant local checks; the full check runs when the story is
        # planned or made, or in the background (decision 55). With no classifier (mock), the
        # local checks are the full check.
        local = safety.check_local({"title": comic.title, "synopsis": comic.synopsis})
        comic.text_check = (
            "blocked" if not local.allowed else ("checked" if llm is None else "pending")
        )
        comic.check_note = None
    comic.updated_at = utcnow()
    session.add(comic)
    session.commit()
    # A blocked draft is still saved (it never leaves the machine) and logged;
    # ComicRead.safety_notes shows the message under the field.
    for name, text in words.items():
        verdict = safety.check_local({name: text})
        if not verdict.allowed:
            safety.log_verdict(session, user.id, f"comic:{comic.id}:{name}", verdict, "text")
    if changes.get("status") == "finished" or ("title" in changes and comic.cover_key):
        comic_maker.make_cover(session, storage, comic)
    session.refresh(comic)
    return comic_read(session, comic, storage)


@router.delete("/comics/{comic_id}", status_code=204)
def delete_comic(comic_id: str, session: SessionDep, user: UserDep) -> None:
    comic = get_comic(session, user, comic_id)
    comic.deleted_at = comic.updated_at = utcnow()
    session.add(comic)
    session.commit()


# ---- scenes -------------------------------------------------------------------------------------


@router.put("/comics/{comic_id}/scenes")
def replace_scenes(
    comic_id: str, body: list[SceneWrite], session: SessionDep, user: UserDep
) -> list[SceneRead]:
    """Replaces the comic's scenes with this ordered list. Scenes keep their ids when sent back."""
    comic = get_comic(session, user, comic_id)
    if len(body) > MAX_SCENES:
        raise invalid(f"That's a lot of scenes! The most you can have is {MAX_SCENES}.")

    sent_ids = [w.id for w in body if w.id]
    if len(sent_ids) != len(set(sent_ids)):
        raise invalid("Two scenes have the same id. Please refresh and try again.")
    bg_ids = {w.background_id for w in body}
    if _owned_place_ids(session, user, list(bg_ids)) != bg_ids:
        raise invalid("Pick a place from your places for every scene.")
    char_ids = {cid for w in body for cid in w.character_ids}
    if _usable_character_ids(session, user, list(char_ids)) != char_ids:
        raise invalid("Pick characters from your cast for every scene.")

    existing = {s.id: s for s in session.exec(select(Scene).where(Scene.comic_id == comic.id))}
    for scene_id in sent_ids:
        if scene_id not in existing and session.get(Scene, scene_id) is not None:
            raise invalid("That scene belongs to another comic. Please refresh and try again.")

    kept: list[Scene] = []
    now = utcnow()
    for idx, w in enumerate(body):
        before = existing.get(w.id or "")
        scene = before or Scene(
            id=w.id or new_id(), comic_id=comic.id, idx=idx, background_id=w.background_id
        )
        # Any change by the kid (new, moved, re-placed, re-cast or re-written) marks the scene
        # as edited, so re-planning asks before replacing it.
        new_state = (idx, w.background_id, list(w.character_ids), w.summary)
        if (
            before is None
            or (before.idx, before.background_id, before.character_ids, before.summary) != new_state
        ):
            scene.edited_at = now
        scene.idx = idx
        scene.background_id = w.background_id
        scene.character_ids = list(w.character_ids)
        scene.summary = w.summary
        session.add(scene)
        kept.append(scene)

    removed = set(existing) - {s.id for s in kept}
    if removed:
        # Panels keep their place and characters; they just stop pointing at the deleted scene.
        for panel in session.exec(select(Panel).where(col(Panel.scene_id).in_(removed))):
            panel.scene_id = None
            session.add(panel)
        session.flush()
        for scene_id in removed:
            session.delete(existing[scene_id])

    result = [scene_read(s) for s in kept]  # read before commit expires the objects
    comic.status = "draft"
    comic.updated_at = utcnow()
    session.add(comic)
    session.commit()
    return result


# ---- panels -------------------------------------------------------------------------------------


@router.patch("/panels/{panel_id}")
def update_panel(
    panel_id: str,
    body: PanelUpdate,
    session: SessionDep,
    user: UserDep,
    storage: StorageDep,
    llm: LLMDep,
) -> PanelRead:
    """Kid edits to a panel. New bubble words are safety-checked first (with the classifier when
    Meta is on); a block names the bubble, so the message shows under it, and nothing is saved.
    Bubbles sit over their speakers unless the kid moved them (`fixed`). A drawn panel whose
    characters changed (face, pose, position) is re-drawn now; text edits never re-draw art."""
    panel = session.get(Panel, panel_id)
    if panel is None:
        raise not_found("panel")
    comic = get_comic(session, user, panel.comic_id)
    before = (panel.beat, panel.characters, panel.bubbles)
    was_check, was_status = panel.text_check, panel.status

    characters = panel.characters
    if body.characters is not None:
        ids = {c.id for c in body.characters}
        if _usable_character_ids(session, user, list(ids)) != ids:
            raise invalid("Pick characters from your cast for this panel.")
        positions = [c.position for c in body.characters]
        if len(set(positions)) != len(positions):
            raise invalid("Two characters can't stand in the same spot.", "characters")
        characters = [c.model_dump(mode="json") for c in body.characters]
    new_bubbles = panel.bubbles
    text_check = was_check
    if body.bubbles is not None:
        speakers = {"narrator", *comic.cast_ids, *(c["id"] for c in characters)}
        if any(b.speaker not in speakers for b in body.bubbles):
            raise invalid("Every bubble needs a speaker from this comic, or the narrator.")
        old_text = {b.get("id"): b.get("text") for b in panel.bubbles}
        fields = {
            f"bubbles.{b.id}.text": b.text for b in body.bubbles if old_text.get(b.id) != b.text
        }
        if was_check in recheck.WAITING and fields:  # not yet AI-checked: check every bubble
            fields = {f"bubbles.{b.id}.text": b.text for b in body.bubbles if b.text.strip()}
        if fields:
            verdict = safety.check_story(session, user.id, f"panel:{panel.id}", fields, llm)
            if not verdict.allowed:
                raise ApiError(422, "unsafe", verdict.message({}), verdict.field_name)
            text_check = "pending" if verdict.pending else "checked"
        new_bubbles = [b.model_dump(mode="json") for b in body.bubbles]

    redraw = panel.art_key is not None and characters != before[1]
    redraw = redraw or (was_status == "blocked" and new_bubbles != before[2])
    panel.characters = characters
    panel.text_check = text_check
    if was_check == "blocked" and text_check == "checked" and was_status == "ready":
        panel.error = None
    if body.beat is not None:
        panel.beat = body.beat
    panel.bubbles = layout(new_bubbles, characters, looks.specs_for(session, characters))
    if redraw:
        comic_maker.draw_panel(session, storage, panel, user.id, llm)

    if (panel.beat, panel.characters, panel.bubbles) != before:
        panel.edited_at = utcnow()
        comic.status = "draft"
    panel.updated_at = comic.updated_at = utcnow()
    session.add(panel)
    session.add(comic)
    session.commit()
    if redraw and panel.idx == 0:
        comic_maker.make_cover(session, storage, comic)
    session.refresh(panel)
    return panel_read(panel, storage)


@router.post("/panels/{panel_id}/render")
def render_panel(
    panel_id: str, session: SessionDep, user: UserDep, storage: StorageDep, llm: LLMDep
) -> PanelRead:
    """Draws one panel again now (Try again on a failed or blocked panel)."""
    panel = session.get(Panel, panel_id)
    if panel is None:
        raise not_found("panel")
    comic = get_comic(session, user, panel.comic_id)
    _require_looks(session, [panel])
    comic_maker.draw_panel(session, storage, panel, user.id, llm)
    session.add(panel)
    session.commit()
    if panel.idx == 0:
        comic_maker.make_cover(session, storage, comic)
    session.refresh(panel)
    return panel_read(panel, storage)


@router.get(
    "/panels/{panel_id}/final.png",
    response_class=Response,
    responses={200: {"content": {"image/png": {}}}},
)
def panel_final(panel_id: str, session: SessionDep, user: UserDep, storage: StorageDep) -> Response:
    """The panel with its bubbles lettered in (made again only when it's out of date)."""
    panel = session.get(Panel, panel_id)
    if panel is None:
        raise not_found("panel")
    get_comic(session, user, panel.comic_id)
    if not panel.art_key:
        raise not_found("panel picture")
    png = comic_maker.ensure_final(session, storage, panel)
    return Response(png, media_type="image/png", headers={"Cache-Control": "no-cache"})


# ---- Make my comic! -----------------------------------------------------------------------------


def _panels_of(session: Session, comic: Comic) -> list[Panel]:
    stmt = select(Panel).where(Panel.comic_id == comic.id).order_by(col(Panel.idx))
    return list(session.exec(stmt))


def _require_looks(session: Session, panels: list[Panel]) -> None:
    """Decision 14: everyone in a panel that gets drawn is locked (has a pinned look)."""
    pairs = {(c["id"], int(c.get("sheet_version", 0))) for p in panels for c in p.characters}
    pinned = looks.looks_for(session, pairs)
    missing = sorted({cid for cid, v in pairs if str(v) not in pinned.get(cid, {})})
    if missing:
        who = session.get(Character, missing[0])
        name = who.name if who else "Someone"
        raise ApiError(
            409,
            "needs_locked",
            f"{name} isn't locked yet. Lock them in the Character Lab, then make your comic!",
            "cast",
        )


def _require_drawn(session: Session, comic: Comic, what: Literal["finish", "download"]) -> None:
    panels = _panels_of(session, comic)
    waiting = next((p for p in panels if p.status != "ready" or not p.art_key), None)
    if not panels or waiting is not None:
        n = waiting.idx + 1 if waiting else 1
        verb = "finish it" if what == "finish" else "download it"
        raise ApiError(
            409,
            "not_ready",
            f"Panel {n} isn't drawn yet. Make your comic first, then {verb}!",
            "panels",
        )


def _check_title_words(session: Session, user: User, comic: Comic, llm: LLMDep) -> None:
    """The title and synopsis: the instant local checks always, and the full check when they
    aren't AI-checked yet (decision 55)."""
    fields = {"title": comic.title, "synopsis": comic.synopsis}
    local = safety.check_local(fields)
    if not local.allowed:
        safety.log_verdict(session, user.id, f"comic:{comic.id}", local, "text")
        raise ApiError(422, "unsafe", local.message(STORY_LABELS), local.field_name)
    if comic.text_check in recheck.WAITING:
        verdict = safety.check_story(session, user.id, f"comic:{comic.id}", fields, llm)
        if not verdict.allowed:
            raise ApiError(422, "unsafe", verdict.message(STORY_LABELS), verdict.field_name)
        comic.text_check = "pending" if verdict.pending else "checked"
        comic.check_note = None
        session.add(comic)


@router.post("/comics/{comic_id}/generate", status_code=202)
def generate_comic(
    comic_id: str,
    request: Request,
    session: SessionDep,
    user: UserDep,
    storage: StorageDep,
    engine: EngineDep,
    jobs: JobsDep,
    llm: LLMDep,
) -> JobStarted:
    """Make my comic!: draws every panel as a job (follow it over SSE: panel_ready or
    panel_failed per panel, then done with the cover). Needs a full panel plan with every
    character locked. Pressing it again while drawing reconnects to the same job."""
    comic = get_comic(session, user, comic_id)
    if comic.last_job_id:
        running = session.get(Job, comic.last_job_id)
        if running is not None and running.status in ("queued", "running"):
            return JobStarted(job_id=running.id, kind="comic", target_id=comic.id)
    panels = _panels_of(session, comic)
    if len(panels) != comic.panel_count:
        raise ApiError(409, "needs_plan", "Plan your panels in the Story Studio first!", "panels")
    _require_looks(session, panels)
    _check_title_words(session, user, comic, llm)

    job = jobs.create("comic", comic.id)
    comic.last_job_id = job.id
    comic.status = "draft"
    comic.updated_at = utcnow()
    session.add(comic)
    session.commit()
    settings = request.app.state.settings

    def read(panel: Panel) -> dict[str, Any]:
        return panel_read(panel, storage).model_dump(mode="json")

    jobs.start(
        job.id,
        partial(
            comic_maker.run_comic_job,
            comic_id=comic.id,
            engine=engine,
            storage=storage,
            llm=llm,
            read=read,
            reveal_seconds=settings.panel_reveal_seconds,
        ),
        on_error=partial(_job_failed, engine, comic.id),
    )
    return JobStarted(job_id=job.id, kind="comic", target_id=comic.id)


def _job_failed(engine: Engine, comic_id: str, _message: str) -> None:
    with Session(engine) as session:
        fail_rendering_panels(session, comic_id, FAILED_MESSAGE)
        session.commit()


# ---- PDF ----------------------------------------------------------------------------------------


def _filename(title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:40]
    return f"{slug or 'my-comic'}.pdf"


@router.get(
    "/comics/{comic_id}/pdf",
    response_class=Response,
    responses={200: {"content": {"application/pdf": {}}}},
)
def comic_pdf(
    comic_id: str, session: SessionDep, user: UserDep, storage: StorageDep, llm: LLMDep
) -> Response:
    """The comic as a PDF (cover, then 6 panels a page). Every panel must be drawn and every
    word AI-checked (decision 55); otherwise a 409 says what's missing."""
    comic = get_comic(session, user, comic_id)
    _require_drawn(session, comic, "download")
    recheck.recheck(session, llm, comic.id)  # words waiting for Meta get another try now
    session.refresh(comic)
    panels = _panels_of(session, comic)
    if comic.text_check == "blocked" or any(p.text_check == "blocked" for p in panels):
        raise ApiError(
            409,
            "unsafe",
            "Some words need changing before you can download. Look for the note!",
            "panels",
        )
    if comic.text_check == "pending" or any(p.text_check == "pending" for p in panels):
        raise ApiError(
            409,
            "not_checked",
            "Our safety helper hasn't double-checked your words yet. Try again in a minute!",
            "panels",
        )
    finals = [comic_maker.ensure_final(session, storage, p) for p in panels]
    specs: dict[str, dict[str, Any]] = {}
    for p in panels:
        for cid, spec in looks.specs_for(session, p.characters).items():
            specs.setdefault(cid, spec)
    names = {
        c.id: c.name
        for c in session.exec(select(Character).where(col(Character.id).in_(list(specs))))
    }
    order = dict.fromkeys(cid for cid in [*comic.cast_ids, *specs] if cid in specs)
    cast = [pdf_export.CastMember(names.get(cid, ""), specs[cid]) for cid in order]
    pdf = pdf_export.build_pdf(comic.title, cast, finals)
    return Response(
        pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{_filename(comic.title)}"'},
    )
