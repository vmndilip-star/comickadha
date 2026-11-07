"""Story Studio: plan scenes (step 1->2), plan panels (step 2->3), the Story Buddy and sparks.

The planner reads the comic as saved (the web app flushes its autosave first). Story text is
fully safety-checked (classifier included) before anything reaches Meta, and a block names the
exact field. If the classifier can't answer, text that passed the local checks is planned by the
offline planner only and marked "not yet AI-checked" (decision 55). Only locked characters and
places go into a plan.
"""

from fastapi import APIRouter, Query
from sqlmodel import Session, col, select

from app.deps import LLMDep, SessionDep, StorageDep, UserDep
from app.errors import ERROR_RESPONSES, ApiError, invalid
from app.models import Background, Character, Comic, Panel, Scene, User
from app.models.base import new_id, utcnow
from app.routers.comics import get_comic, panel_read, scene_read
from app.schemas.comic import SceneRead
from app.schemas.common import ErrorBody
from app.schemas.studio import (
    BuddyReply,
    BuddyRequest,
    PanelPlan,
    PanelsPlanned,
    PlanRequest,
    ScenePlan,
    ScenesPlanned,
    Spark,
)
from app.services import looks, safety, story_buddy, story_planner
from app.services.ai_guard import Guard, label
from app.services.bubbles import layout
from app.services.story_planner import CastMember, Place, PlanFailed, SceneInfo, StoryContext

router = APIRouter(
    prefix="/api/studio",
    tags=["studio"],
    responses={**ERROR_RESPONSES, 409: {"model": ErrorBody}},
)

STORY_LABELS = {"title": "title", "synopsis": "story"}
PLAN_FAILED = (
    "Our story helper got muddled making that plan. Your story is safe: tap Try again, "
    "or change a scene a little."
)


def _cast(session: Session, comic: Comic) -> tuple[list[CastMember], list[str]]:
    """(locked cast members, names of cast members left out because they aren't locked)."""
    if not comic.cast_ids:
        return [], []
    rows = {
        c.id: c
        for c in session.exec(
            select(Character).where(
                col(Character.id).in_(comic.cast_ids), col(Character.deleted_at).is_(None)
            )
        )
    }
    locked: list[CastMember] = []
    skipped: list[str] = []
    for cid in comic.cast_ids:
        c = rows.get(cid)
        if c is None:
            continue
        if c.status != "locked":
            skipped.append(c.name)
            continue
        personality = c.spec.get("personality", {})
        locked.append(
            CastMember(
                id=c.id,
                name=c.name,
                sheet_version=c.sheet_version,
                catchphrase=str(personality.get("catchphrase", "")),
                traits=tuple(personality.get("traits", [])),
            )
        )
    return locked, skipped


def _places(session: Session, user: User) -> list[Place]:
    stmt = select(Background).where(
        Background.user_id == user.id,
        Background.status == "locked",
        col(Background.deleted_at).is_(None),
    )
    return [
        Place(b.id, b.name, b.description)
        for b in session.exec(stmt.order_by(col(Background.created_at)))
    ]


def _scenes(session: Session, comic: Comic) -> list[Scene]:
    stmt = select(Scene).where(Scene.comic_id == comic.id).order_by(col(Scene.idx))
    return list(session.exec(stmt))


def _panels(session: Session, comic: Comic) -> list[Panel]:
    stmt = select(Panel).where(Panel.comic_id == comic.id).order_by(col(Panel.idx))
    return list(session.exec(stmt))


def _check_story(
    session: Session, user: User, comic: Comic, fields: dict[str, str], llm: LLMDep
) -> bool:
    """The full check (local + classifier). Blocks name the field. Returns True when the words are
    only locally checked (classifier down): then only the offline planner may use them."""
    verdict = safety.check_story(session, user.id, f"comic:{comic.id}", fields, llm)
    if not verdict.allowed:
        raise ApiError(422, "unsafe", verdict.message(STORY_LABELS), verdict.field_name)
    comic.text_check = "pending" if verdict.pending else "checked"
    if not verdict.pending:
        comic.check_note = None
    session.add(comic)
    return verdict.pending


def _needs_locked(cast: list[CastMember], places: list[Place]) -> None:
    if not cast:
        raise ApiError(
            409,
            "needs_locked",
            "Your story needs at least one locked character. Pick one for your cast, "
            "or lock one in the Character Lab!",
            "cast",
        )
    if not places:
        raise ApiError(
            409,
            "needs_locked",
            "Your story needs at least one locked place. Describe one and lock it first!",
            "places",
        )


@router.post("/{comic_id}/plan-scenes")
def plan_scenes(
    comic_id: str, body: PlanRequest, session: SessionDep, user: UserDep, llm: LLMDep
) -> ScenesPlanned:
    """Step 1 -> 2: splits the story into 2-4 scenes with the kid's locked cast and places."""
    comic = get_comic(session, user, comic_id)
    cast, skipped = _cast(session, comic)
    places = _places(session, user)
    _needs_locked(cast, places)
    if len(comic.synopsis.split()) < 3:
        raise invalid("Write a sentence or two about your story first!", "synopsis")
    pending = _check_story(
        session, user, comic, {"title": comic.title, "synopsis": comic.synopsis}, llm
    )

    existing = _scenes(session, comic)
    if any(s.edited_at for s in existing) and not body.start_over:
        raise ApiError(
            409,
            "confirm_start_over",
            "You changed your scenes. Start scenes over with new ones?",
            "scenes",
        )

    ctx = StoryContext(comic.title, comic.synopsis, comic.mood, comic.panel_count, cast, places)
    guard = Guard(llm, session, user.id)
    guard.offline_only = pending  # unchecked words never reach Meta
    try:
        outcome = story_planner.plan_scenes(guard, ctx)
    except PlanFailed as failed:
        raise ApiError(422, "plan_failed", PLAN_FAILED) from failed

    scenes = _save_scenes(session, comic, existing, outcome.plan)
    return ScenesPlanned(
        scenes=scenes,
        skipped=skipped,
        source="meta" if outcome.source == "meta" else "mock",
        fallback=outcome.fallback,
        label=label(outcome.source),
    )


def _save_scenes(
    session: Session, comic: Comic, existing: list[Scene], plan: ScenePlan
) -> list[SceneRead]:
    # Panels keep their place and characters; they just stop pointing at the replaced scenes.
    old_ids = [s.id for s in existing]
    if old_ids:
        for panel in session.exec(select(Panel).where(col(Panel.scene_id).in_(old_ids))):
            panel.scene_id = None
            session.add(panel)
        session.flush()
        for scene in existing:
            session.delete(scene)
        session.flush()
    created = [
        Scene(
            id=new_id(),
            comic_id=comic.id,
            idx=i,
            background_id=s.background_id,
            character_ids=list(s.character_ids),
            summary=s.summary,
        )
        for i, s in enumerate(plan.scenes)
    ]
    for scene in created:
        session.add(scene)
    comic.studio_step = max(comic.studio_step, 2)
    comic.updated_at = utcnow()
    session.add(comic)
    session.flush()
    result = [scene_read(s) for s in created]
    session.commit()
    return result


@router.post("/{comic_id}/plan-panels")
def plan_panels(
    comic_id: str,
    body: PlanRequest,
    session: SessionDep,
    user: UserDep,
    storage: StorageDep,
    llm: LLMDep,
) -> PanelsPlanned:
    """Step 2 -> 3: exactly panel_count panels from the kid's scenes. Panels the kid edited (or
    that are drawn) are kept unless they confirm "Start panels over"."""
    comic = get_comic(session, user, comic_id)
    cast, _skipped = _cast(session, comic)
    places = _places(session, user)
    _needs_locked(cast, places)
    scenes = _scenes(session, comic)
    if not scenes:
        raise ApiError(409, "needs_scenes", "Add at least one scene first!", "scenes")
    cast_ids = {c.id for c in cast}
    place_ids = {p.id for p in places}
    for i, s in enumerate(scenes, start=1):
        if s.background_id not in place_ids:
            raise ApiError(
                409,
                "needs_locked",
                f"Scene {i}'s place isn't locked yet. Lock it, or pick a locked place.",
                f"scenes.{s.id}",
            )
        if not s.character_ids:
            raise invalid(f"Pick at least one character for scene {i}.", f"scenes.{s.id}")
        if not set(s.character_ids) <= cast_ids:
            raise ApiError(
                409,
                "needs_locked",
                f"Scene {i} has someone who isn't locked yet. Lock them in the Lab, "
                "or take them out of the scene.",
                f"scenes.{s.id}",
            )
    fields = {"title": comic.title, "synopsis": comic.synopsis}
    fields |= {f"scenes.{s.id}.summary": s.summary for s in scenes}
    pending = _check_story(session, user, comic, fields, llm)

    existing = _panels(session, comic)
    keep = (
        {}
        if body.start_over
        else {p.idx: p for p in existing if p.edited_at is not None or p.status != "planned"}
    )
    if any(idx >= comic.panel_count for idx in keep):
        raise ApiError(
            409,
            "confirm_start_over",
            "Some panels you changed don't fit any more. Start panels over?",
            "panels",
        )

    ctx = StoryContext(
        comic.title,
        comic.synopsis,
        comic.mood,
        comic.panel_count,
        cast,
        places,
        [SceneInfo(s.id, s.background_id, tuple(s.character_ids), s.summary) for s in scenes],
    )
    guard = Guard(llm, session, user.id)
    guard.offline_only = pending  # unchecked words never reach Meta
    try:
        outcome = story_planner.plan_panels(guard, ctx)
    except PlanFailed as failed:
        raise ApiError(422, "plan_failed", PLAN_FAILED) from failed

    check = "pending" if pending else "checked"
    panels = _save_panels(session, comic, existing, keep, outcome.plan, ctx, scenes, check)
    return PanelsPlanned(
        panels=[panel_read(p, storage) for p in panels],
        kept=len(keep),
        source="meta" if outcome.source == "meta" else "mock",
        fallback=outcome.fallback,
        label=label(outcome.source),
    )


def _save_panels(
    session: Session,
    comic: Comic,
    existing: list[Panel],
    keep: dict[int, Panel],
    plan: PanelPlan,
    ctx: StoryContext,
    scenes: list[Scene],
    text_check: str,
) -> list[Panel]:
    background = {s.id: s.background_id for s in scenes}
    for panel in existing:
        if panel.idx not in keep or keep[panel.idx] is not panel:
            session.delete(panel)
    session.flush()
    out: list[Panel] = []
    for idx, planned in enumerate(plan.panels):
        if idx in keep:
            out.append(keep[idx])
            continue
        characters = [
            {
                "id": c.id,
                "sheet_version": member.sheet_version if (member := ctx.member(c.id)) else 0,
                "pose": c.pose,
                "expression": c.expression,
                "position": c.position,
                "scale": 1.0,
            }
            for c in planned.characters
        ]
        bubbles = [
            {"id": new_id(), "speaker": b.speaker, "type": b.type, "text": b.text}
            for b in planned.bubbles
        ]
        panel = Panel(
            id=new_id(),
            comic_id=comic.id,
            scene_id=planned.scene_id,
            idx=idx,
            # Every panel's place is its scene's place: the model never chooses it.
            background_id=background[planned.scene_id],
            beat=planned.beat,
            characters=characters,
            bubbles=layout(bubbles, characters, looks.specs_for(session, characters)),
            status="planned",
            text_check=text_check,
        )
        session.add(panel)
        out.append(panel)
    comic.studio_step = 3
    comic.updated_at = utcnow()
    session.add(comic)
    session.commit()
    for panel in out:
        session.refresh(panel)
    return out


@router.post("/buddy")
def buddy(body: BuddyRequest, session: SessionDep, user: UserDep, llm: LLMDep) -> BuddyReply:
    """Questions that help the kid think, a spelling check, or scene title ideas."""
    comic = get_comic(session, user, body.comic_id)
    cast, _ = _cast(session, comic)
    names = [c.name for c in cast] or [
        c.name for c in session.exec(select(Character).where(col(Character.id).in_(comic.cast_ids)))
    ]
    ctx = story_buddy.BuddyContext(
        title=comic.title,
        synopsis=comic.synopsis,
        mood=comic.mood,
        cast_names=names,
        place_names=[p.name for p in _places(session, user)],
    )
    return story_buddy.Buddy(llm, session, user.id).answer(body.action, body.text, ctx)


@router.get("/spark")
def spark(after: int | None = Query(default=None, ge=0, description="Not this one again")) -> Spark:
    """A random story spark for the Home page."""
    return story_buddy.spark(after)
