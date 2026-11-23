"""Story Studio: plan scenes (step 1->2), plan panels (step 2->3), the Story Buddy and sparks.

Planning panels is a job (Phase 7 part C, services/plan_job.py): the request runs the quick checks
and the safety check on every word, clears the panels the plan replaces and returns 202; the job
plans the comic a part at a time and saves each part as it's ready.

The planner reads the comic as saved (the web app flushes its autosave first). Every kid-written
word a Meta prompt carries (the story, scene summaries, cast names and catchphrases, place names
and descriptions) is fully safety-checked (classifier included) before anything reaches Meta, and
a block names the exact field (services/kid_fields.py). If the classifier can't answer, text
that passed the local checks is planned by the offline planner only and marked "not yet
AI-checked" (decision 55). Only locked characters and places go into a plan.
"""

from functools import partial
from typing import Any

from fastapi import APIRouter, Query, Request
from sqlmodel import Session, col, select

from app.deps import EngineDep, JobsDep, LLMDep, SessionDep, StorageDep, UserDep
from app.errors import ERROR_RESPONSES, ApiError, invalid
from app.models import Background, Character, Comic, Job, Panel, Scene, User
from app.models.base import new_id, utcnow
from app.routers.comics import get_comic, panel_read, scene_read
from app.schemas.comic import SceneRead
from app.schemas.common import ErrorBody
from app.schemas.job import JobStarted
from app.schemas.studio import (
    BuddyReply,
    BuddyRequest,
    PlanRequest,
    ScenePlan,
    ScenesPlanned,
    Spark,
)
from app.services import story_buddy, story_planner
from app.services.ai_guard import Guard, label
from app.services.kid_fields import Checked, KidFields, check_before_meta
from app.services.plan_job import PlanJob, run_plan_job
from app.services.story_planner import CastMember, Place, PlanFailed, SceneInfo, StoryContext

router = APIRouter(
    prefix="/api/studio",
    tags=["studio"],
    responses={**ERROR_RESPONSES, 409: {"model": ErrorBody}},
)

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
    session: Session, user: User, comic: Comic, fields: KidFields, llm: LLMDep
) -> Checked:
    """The full check (local + classifier) of every kid-written word the planner prompt carries:
    the story, scene summaries, cast names and catchphrases, place names and descriptions. Blocks
    name the field; places whose words don't pass come back in `left_out` (decision 89). `pending`
    means the words are only locally checked (classifier down): only the offline planner may use
    them."""
    checked = check_before_meta(session, user.id, f"comic:{comic.id}", fields, llm)
    comic.text_check = "pending" if checked.pending else "checked"
    if not checked.pending:
        comic.check_note = None
    session.add(comic)
    return checked


def _usable_places(places: list[Place], checked: Checked) -> list[Place]:
    """The places a plan may use: every locked place whose words passed. None left is a 409."""
    usable = [p for p in places if p.id not in checked.left_out]
    if not usable:
        names = " and ".join(f"“{name}”" for name in checked.left_out.values())
        raise ApiError(
            409,
            "needs_locked",
            f"Our safety helper didn't like the words of {names}, so your story has no place to "
            "use. Delete it and describe a new place!",
            "places",
        )
    return usable


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
    ctx = StoryContext(comic.title, comic.synopsis, comic.mood, comic.panel_count, cast, places)
    checked = _check_story(session, user, comic, story_planner.planner_fields(ctx), llm)
    ctx.places = _usable_places(places, checked)  # out of the Meta and the offline plan alike

    existing = _scenes(session, comic)
    if any(s.edited_at for s in existing) and not body.start_over:
        raise ApiError(
            409,
            "confirm_start_over",
            "You changed your scenes. Start scenes over with new ones?",
            "scenes",
        )

    guard = Guard(llm, session, user.id)
    guard.offline_only = checked.pending  # unchecked words never reach Meta
    try:
        outcome = story_planner.plan_scenes(guard, ctx)
    except PlanFailed as failed:
        raise ApiError(422, "plan_failed", PLAN_FAILED) from failed

    scenes = _save_scenes(session, comic, existing, outcome.plan)
    return ScenesPlanned(
        scenes=scenes,
        skipped=skipped,
        left_out_places=list(checked.left_out.values()),
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


def running_plan_job(session: Session, comic_id: str) -> Job | None:
    """The panel plan being made for this comic right now, if any."""
    stmt = select(Job).where(
        Job.kind == "panel_plan",
        Job.target_id == comic_id,
        col(Job.status).in_(("queued", "running")),
    )
    return session.exec(stmt.order_by(col(Job.created_at).desc())).first()


@router.post("/{comic_id}/plan-panels", status_code=202)
def plan_panels(
    comic_id: str,
    body: PlanRequest,
    request: Request,
    session: SessionDep,
    user: UserDep,
    storage: StorageDep,
    llm: LLMDep,
    engine: EngineDep,
    jobs: JobsDep,
) -> JobStarted:
    """Step 2 -> 3: exactly panel_count panels from the kid's scenes, made by a job (follow it
    over SSE: progress, scene_planned per part as it's saved, done). Each scene gets an even share
    of the panels. Panels the kid edited (or that are drawn) are kept unless they confirm "Start
    panels over". Pressing it again while planning reconnects to the same job."""
    comic = get_comic(session, user, comic_id)
    if (running := running_plan_job(session, comic.id)) is not None:
        return JobStarted(job_id=running.id, kind="panel_plan", target_id=comic.id)
    cast, _skipped = _cast(session, comic)
    places = _places(session, user)
    _needs_locked(cast, places)
    scenes = _scenes(session, comic)
    if not scenes:
        raise ApiError(409, "needs_scenes", "Add at least one scene first!", "scenes")
    if len(scenes) > comic.panel_count:
        raise invalid(
            f"Your story has {len(scenes)} scenes but only {comic.panel_count} panels. Pick more "
            "panels, or take out a scene.",
            "scenes",
        )
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
    ctx = StoryContext(
        comic.title,
        comic.synopsis,
        comic.mood,
        comic.panel_count,
        cast,
        places,
        [SceneInfo(s.id, s.background_id, tuple(s.character_ids), s.summary) for s in scenes],
    )
    checked = _check_story(session, user, comic, story_planner.planner_fields(ctx), llm)
    ctx.places = _usable_places(places, checked)
    for i, s in enumerate(scenes, start=1):
        if s.background_id in checked.left_out:
            name = checked.left_out[s.background_id]
            raise ApiError(
                422,
                "unsafe",
                f"Our safety helper didn't like the words of “{name}”, so it can't go in your "
                f"story. Pick another place for scene {i}, or delete “{name}” and describe a new "
                "one.",
                f"scenes.{s.id}",
            )

    existing = _panels(session, comic)
    keep = (
        set()
        if body.start_over
        else {p.idx for p in existing if p.edited_at is not None or p.status != "planned"}
    )
    if any(idx >= comic.panel_count for idx in keep):
        raise ApiError(
            409,
            "confirm_start_over",
            "Some panels you changed don't fit any more. Start panels over?",
            "panels",
        )
    # The plan replaces every other panel: clear them now, so a refresh while it plans shows only
    # the kept panels and the parts planned so far.
    for panel in existing:
        if panel.idx not in keep:
            session.delete(panel)
    comic.updated_at = utcnow()
    session.add(comic)
    session.commit()

    plan = PlanJob(
        comic_id=comic.id,
        user_id=user.id,
        story=ctx,
        keep=frozenset(keep),
        text_check="pending" if checked.pending else "checked",
        offline_only=checked.pending,  # unchecked words never reach Meta
        left_out=tuple(checked.left_out.values()),
    )

    def read(panel: Panel) -> dict[str, Any]:
        return panel_read(panel, storage).model_dump(mode="json")

    job = jobs.create("panel_plan", comic.id)
    reveal = request.app.state.settings.plan_reveal_seconds
    work = partial(run_plan_job, job=plan, engine=engine, llm=llm, read=read, reveal_seconds=reveal)
    jobs.start(job.id, work)
    return JobStarted(job_id=job.id, kind="panel_plan", target_id=comic.id)


@router.post("/buddy")
def buddy(body: BuddyRequest, session: SessionDep, user: UserDep, llm: LLMDep) -> BuddyReply:
    """Questions that help the kid think, a spelling check, or scene title ideas."""
    comic = get_comic(session, user, body.comic_id)
    cast, _ = _cast(session, comic)
    people = [(c.id, c.name) for c in cast] or [
        (c.id, c.name)
        for c in session.exec(select(Character).where(col(Character.id).in_(comic.cast_ids)))
    ]
    places = _places(session, user)
    # Story Buddy checks every word of this (and the kid's text) before Meta sees it.
    ctx = story_buddy.BuddyContext(
        title=comic.title,
        synopsis=comic.synopsis,
        mood=comic.mood,
        cast_names=[name for _, name in people],
        place_names=[p.name for p in places],
        cast_ids=[cid for cid, _ in people],
        place_ids=[p.id for p in places],
    )
    return story_buddy.Buddy(llm, session, user.id).answer(body.action, body.text, ctx)


@router.get("/spark")
def spark(after: int | None = Query(default=None, ge=0, description="Not this one again")) -> Spark:
    """A random story spark for the Home page."""
    return story_buddy.spark(after)
