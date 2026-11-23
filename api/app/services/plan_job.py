"""Planning a comic's panels as a job (Phase 7 part C), followed over SSE like Make my comic!.

One Meta call can't write 30 panels, so the plan is made a part at a time (a scene, or a run of a
big scene's panels: `story_planner.plan_parts`), PLAN_PARTS_AT_ONCE parts at once. Each part gets
its own checks, one retry and its own offline fallback, and is saved the moment it's ready, so a
refresh during planning keeps every part planned so far. Events:

- progress: {stage: "planning" | "polishing", done, of} ("Planning scene 3 of 7...");
- scene_planned: {scene_id, part, first, count, panels} (the part's panels as saved; sent again
  if the comic-wide pass changes them);
- done: {kept, left_out_places, source, fallback, label}.

Then the comic-wide pass: parts whose line openings clash with another part's are asked once more
(with the openings to avoid), and `story_planner.repair_dialogue` settles anything left. Offline
(no Meta, or words not yet AI-checked), the whole plan comes from the offline planner in one go.
"""

import asyncio
from collections.abc import Callable, Collection, Mapping
from dataclasses import dataclass
from typing import Any

from sqlalchemy import Engine
from sqlmodel import Session, col, select

from app.models import Comic, Panel, Scene
from app.models.base import new_id, utcnow
from app.providers.llm import LLMProvider
from app.schemas.studio import PanelPlan
from app.services import looks, story_planner
from app.services.ai_guard import Guard, label
from app.services.ai_limits import PLAN_PARTS_AT_ONCE
from app.services.bubbles import layout
from app.services.jobs import JobContext, JobFailed
from app.services.story_planner import Outcome, ScenePart, StoryContext

PanelJson = Callable[[Panel], dict[str, Any]]
# When planning breaks unexpectedly (a bug, never the kid's fault): the parts saved so far stay.
PLAN_BROKE = "Our story helper got muddled. Your story is safe: tap Plan my panels to try again."


@dataclass(frozen=True)
class PlanJob:
    """Everything the job needs, read and checked by the request before it starts."""

    comic_id: str
    user_id: str
    story: StoryContext
    keep: frozenset[int]  # panel slots the kid edited (or that are drawn): left as they are
    text_check: str  # "checked", or "pending" while the classifier was resting (decision 55)
    offline_only: bool  # the kid's words aren't AI-checked yet: Meta may not see them
    left_out: tuple[str, ...]  # places left out because their words didn't pass


async def run_plan_job(
    ctx: JobContext,
    *,
    job: PlanJob,
    engine: Engine,
    llm: LLMProvider | None,
    read: PanelJson,
    reveal_seconds: float = 0.0,
) -> dict[str, Any]:
    try:
        return await _run(ctx, job, engine, llm, read, reveal_seconds)
    except Exception as error:  # the job's error event says what to do, in kid words
        raise JobFailed(PLAN_BROKE) from error


async def _run(
    ctx: JobContext,
    job: PlanJob,
    engine: Engine,
    llm: LLMProvider | None,
    read: PanelJson,
    reveal_seconds: float,
) -> dict[str, Any]:
    parts = story_planner.plan_parts(job.story)
    plans: list[PanelPlan | None] = [None] * len(parts)
    sources = ["mock"] * len(parts)
    fallbacks = [False] * len(parts)
    planned: set[int] = set()
    saving = asyncio.Lock()
    stage = ["planning"]  # then "polishing" for the comic-wide pass

    def progress() -> None:
        share = len(planned) / max(1, len(parts))
        data = {"stage": stage[0], "done": len(planned), "of": len(parts)}
        ctx.emit("progress", data, share * 0.9)

    async def save(i: int) -> None:
        plan = plans[i]
        assert plan is not None
        async with saving:  # one writer at a time; the planning itself runs side by side
            panels = await ctx.run(save_part, engine, job, parts[i], plan, read)
        planned.add(i)
        part = parts[i]
        ctx.emit(
            "scene_planned",
            {
                "scene_id": part.scene.id,
                "part": i,
                "first": part.first,
                "count": part.count,
                "source": sources[i],  # "meta", or "mock" when the offline planner made it
                "panels": panels,
            },
        )
        progress()

    progress()
    if llm is None or job.offline_only:
        whole = story_planner.offline_panels(job.story)
        for i, part in enumerate(parts):
            plans[i] = PanelPlan(panels=whole.panels[part.first : part.first + part.count])
            fallbacks[i] = llm is not None
            await save(i)
            if reveal_seconds:  # so the Studio fills in scene by scene (PLAN_REVEAL_SECONDS)
                await asyncio.sleep(reveal_seconds)
    else:
        gate = asyncio.Semaphore(PLAN_PARTS_AT_ONCE)

        async def one(i: int, avoid: Mapping[str, Collection[str]] | None = None) -> None:
            async with gate:
                outcome = await ctx.run(_plan_one, engine, llm, job, parts[i], avoid)
            plans[i], sources[i], fallbacks[i] = outcome.plan, outcome.source, outcome.fallback
            await save(i)

        await asyncio.gather(*(one(i) for i in range(len(parts))))
        clashes = story_planner.dialogue_clashes(plans, parts, job.keep)
        if clashes:
            stage[0] = "polishing"
            progress()
            await asyncio.gather(*(one(i, avoid) for i, avoid in clashes.items()))
        for i, plan in story_planner.repair_dialogue(plans, parts, job.story, job.keep).items():
            plans[i] = plan
            await save(i)
    await ctx.run(_finish, engine, job.comic_id)
    source = "meta" if "meta" in sources else "mock"
    return {
        "kept": len(job.keep),
        "left_out_places": list(job.left_out),
        "source": source,
        "fallback": any(fallbacks),
        "label": label(source),
    }


def _plan_one(
    engine: Engine,
    llm: LLMProvider,
    job: PlanJob,
    part: ScenePart,
    avoid: Mapping[str, Collection[str]] | None,
) -> Outcome[PanelPlan]:
    """One part from Meta (or the offline planner), in a worker thread with its own session."""
    with Session(engine) as session:
        guard = Guard(llm, session, job.user_id)
        return story_planner.plan_part(guard, job.story, part, avoid)


def save_part(
    engine: Engine, job: PlanJob, part: ScenePart, plan: PanelPlan, read: PanelJson
) -> list[dict[str, Any]]:
    """Saves a part's panels into its slots (replacing what was there, except the kid's kept
    panels) and returns them as the API shows them."""
    with Session(engine) as session:
        comic = session.get(Comic, job.comic_id)
        if comic is None or comic.deleted_at is not None:
            return []
        places = {
            s.id: s.background_id
            for s in session.exec(select(Scene).where(Scene.comic_id == job.comic_id))
        }
        stmt = select(Panel).where(
            Panel.comic_id == job.comic_id, col(Panel.idx).in_(list(part.indexes))
        )
        for old in session.exec(stmt):
            if old.idx not in job.keep:
                session.delete(old)
        session.flush()
        saved: list[Panel] = []
        for idx, planned in zip(part.indexes, plan.panels, strict=True):
            if idx in job.keep:
                continue
            characters = [
                {
                    "id": c.id,
                    "sheet_version": member.sheet_version
                    if (member := job.story.member(c.id))
                    else 0,
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
            # Every panel's place is its scene's place: the model never chooses it. (A scene the
            # kid deleted while this was planning leaves its panels without a scene.)
            scene_id = planned.scene_id if planned.scene_id in places else None
            panel = Panel(
                id=new_id(),
                comic_id=job.comic_id,
                scene_id=scene_id,
                idx=idx,
                background_id=places.get(planned.scene_id, part.scene.background_id),
                beat=planned.beat,
                characters=characters,
                bubbles=layout(bubbles, characters, looks.specs_for(session, characters)),
                status="planned",
                text_check=job.text_check,
            )
            session.add(panel)
            saved.append(panel)
        comic.updated_at = utcnow()
        session.add(comic)
        session.commit()
        for panel in saved:
            session.refresh(panel)
        return [read(p) for p in saved]


def _finish(engine: Engine, comic_id: str) -> None:
    with Session(engine) as session:
        comic = session.get(Comic, comic_id)
        if comic is None:
            return
        comic.studio_step = 3
        comic.updated_at = utcnow()
        session.add(comic)
        session.commit()
