from collections import defaultdict
from typing import Literal

from fastapi import APIRouter, Query
from sqlmodel import Session, col, select

from app.deps import LLMDep, SessionDep, StorageDep, UserDep
from app.errors import ERROR_RESPONSES, ApiError, invalid, not_found
from app.models import Background, Character, Comic, Panel, Scene, User
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
from app.services import safety
from app.services.bubbles import layout
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
    return PanelRead.model_validate(
        {
            **panel.model_dump(),
            "art_url": storage.url(panel.art_key) if panel.art_key else None,
            "image_url": storage.url(panel.image_key) if panel.image_key else None,
        }
    )


STORY_LABELS = {"title": "title", "synopsis": "story"}


def safety_notes(comic: Comic) -> list[FieldNote]:
    """The instant local checks (personal info, word list) on the title and synopsis."""
    notes: list[FieldNote] = []
    for name in ("title", "synopsis"):
        verdict = safety.check_local({name: getattr(comic, name)})
        if not verdict.allowed:
            notes.append(FieldNote(field=name, message=verdict.message(STORY_LABELS)))
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
                "cover_url": storage.url(c.cover_key) if c.cover_key else None,
                "scenes": [scene_read(s) for s in scenes[c.id]],
                "panels": [panel_read(p, storage) for p in panels[c.id]],
                "characters": [chars[i] for i in used_chars[c.id] if i in chars],
                "backgrounds": [bgs[i] for i in used_bgs[c.id] if i in bgs],
                "safety_notes": safety_notes(c),
            }
        )
        for c in comics
    ]


def comic_read(session: Session, comic: Comic, storage: Storage) -> ComicRead:
    return comic_reads(session, [comic], storage)[0]


def _owned_ids(
    session: Session, user: User, model: type[Character] | type[Background], ids: list[str]
) -> set[str]:
    if not ids:
        return set()
    stmt = select(model.id).where(model.user_id == user.id, col(model.id).in_(ids))
    return set(session.exec(stmt))


def _active_character_ids(session: Session, user: User, ids: list[str]) -> set[str]:
    if not ids:
        return set()
    stmt = select(Character.id).where(
        Character.user_id == user.id,
        col(Character.id).in_(ids),
        col(Character.deleted_at).is_(None),
    )
    return set(session.exec(stmt))


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
    comic_id: str, body: ComicUpdate, session: SessionDep, user: UserDep, storage: StorageDep
) -> ComicRead:
    comic = get_comic(session, user, comic_id)
    changes = body.model_dump(exclude_unset=True, exclude_none=True)
    if "cast_ids" in changes:
        cast_ids: list[str] = list(
            dict.fromkeys(changes["cast_ids"])
        )  # drop duplicates, keep order
        # Characters already in the comic may stay even if deleted; new ones must be active.
        added = [i for i in cast_ids if i not in comic.cast_ids]
        if _owned_ids(session, user, Character, cast_ids) != set(cast_ids) or (
            _active_character_ids(session, user, added) != set(added)
        ):
            raise invalid("Pick characters from your cast.")
        changes["cast_ids"] = cast_ids
    for field, value in changes.items():
        setattr(comic, field, value)
    comic.updated_at = utcnow()
    session.add(comic)
    session.commit()
    # Autosave runs only the instant local checks. A blocked draft is still saved (it never
    # leaves the machine) and logged; ComicRead.safety_notes shows the message under the field.
    for name in ("title", "synopsis"):
        if name in changes:
            verdict = safety.check_local({name: changes[name]})
            if not verdict.allowed:
                target = f"comic:{comic.id}:{name}"
                safety.log_verdict(session, user.id, target, verdict, "text")
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
    if _owned_ids(session, user, Background, list(bg_ids)) != bg_ids:
        raise invalid("Pick a place from your places for every scene.")
    char_ids = {cid for w in body for cid in w.character_ids}
    if _owned_ids(session, user, Character, list(char_ids)) != char_ids:
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
    """Kid edits to a planned panel. New bubble words are safety-checked (with the classifier
    when Meta is on); a block names the bubble, so the message shows under it."""
    panel = session.get(Panel, panel_id)
    if panel is None:
        raise not_found("panel")
    comic = get_comic(session, user, panel.comic_id)
    before = (panel.beat, panel.characters, panel.bubbles)

    if body.characters is not None:
        ids = {c.id for c in body.characters}
        if _owned_ids(session, user, Character, list(ids)) != ids:
            raise invalid("Pick characters from your cast for this panel.")
        positions = [c.position for c in body.characters]
        if len(set(positions)) != len(positions):
            raise invalid("Two characters can't stand in the same spot.", "characters")
        panel.characters = [c.model_dump(mode="json") for c in body.characters]
    if body.bubbles is not None:
        speakers = {"narrator", *comic.cast_ids, *(c["id"] for c in panel.characters)}
        if any(b.speaker not in speakers for b in body.bubbles):
            raise invalid("Every bubble needs a speaker from this comic, or the narrator.")
        old_text = {b.get("id"): b.get("text") for b in panel.bubbles}
        changed = {
            f"bubbles.{b.id}.text": b.text for b in body.bubbles if old_text.get(b.id) != b.text
        }
        if changed:
            verdict = safety.check_story(session, user.id, f"panel:{panel.id}", changed, llm)
            if not verdict.allowed:
                raise ApiError(422, "unsafe", verdict.message({}), verdict.field_name)
        panel.bubbles = [b.model_dump(mode="json") for b in body.bubbles]
    if body.beat is not None:
        panel.beat = body.beat
    # Bubbles sit over their speakers (kids can't move bubbles by hand until Phase 5).
    panel.bubbles = layout(panel.bubbles, panel.characters)

    if (panel.beat, panel.characters, panel.bubbles) != before:
        panel.edited_at = utcnow()
    panel.updated_at = comic.updated_at = utcnow()
    session.add(panel)
    session.add(comic)
    session.commit()
    session.refresh(panel)
    return panel_read(panel, storage)
