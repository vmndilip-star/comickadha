"""FastAPI entry point: create_app() wires settings, database, storage, jobs, routers and errors."""

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlmodel import Session

from app import __version__
from app.config import Settings, get_settings
from app.db import init_db, make_engine, missing_columns
from app.errors import install_error_handlers
from app.prompts import load_all as load_prompts
from app.props.images import ensure_images
from app.providers import get_image_provider, get_llm_provider
from app.providers.mock import MockImageProvider
from app.routers import (
    backgrounds,
    builder,
    characters,
    comics,
    jobs,
    media,
    profile,
    props,
    studio,
)
from app.seed import seed
from app.services import recheck
from app.services.backup import backup_storage
from app.services.builder_sheet import BuilderSheets
from app.services.character_sheet import SheetProvider
from app.services.jobs import JobRunner, fail_interrupted_jobs
from app.services.storage import LocalStorage
from app.starters import ensure_starters

log = logging.getLogger(__name__)


class Health(BaseModel):
    status: Literal["ok"]
    version: str
    llm_provider: str
    image_provider: str


def make_sheet_provider(settings: Settings, *, reveal: bool = True) -> SheetProvider:
    """Character sheets are drawn from the avatar's parts. reveal=False skips the per-cell pause
    (seeding has nobody watching)."""
    return BuilderSheets(reveal_seconds=settings.builder_reveal_seconds if reveal else 0)


def _log_to_console() -> None:
    """Shows the app's INFO lines (such as Meta token counts) next to uvicorn's."""
    app_log = logging.getLogger("app")
    if not app_log.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(levelname)s:     %(name)s: %(message)s"))
        app_log.addHandler(handler)
        app_log.setLevel(logging.INFO)


async def recheck_loop(app: FastAPI, every: float) -> None:
    """Decision 55: story text saved during a Meta outage is re-checked every so often."""
    while True:
        await asyncio.sleep(every)
        try:
            settled = await asyncio.to_thread(recheck.recheck_all, app.state.engine, app.state.llm)
        except Exception:
            log.exception("background re-check failed")
            continue
        if settled:
            log.info("re-checked %d story item(s) that were waiting for the safety helper", settled)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    _log_to_console()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        # First, so a bad Meta setting (missing key or model, a -contributor model, Muse Image
        # without LLM_PROVIDER=meta) stops startup before anything is touched.
        app.state.llm = get_llm_provider(settings)
        app.state.image_provider = get_image_provider(settings)
        # Every prompt is read and checked now, so a missing or broken one stops startup.
        load_prompts()
        settings.storage_dir.mkdir(parents=True, exist_ok=True)
        engine = make_engine(settings.resolved_database_url)
        # Back up the storage folder before adding columns to an existing database (the newest 5
        # are kept).
        if missing_columns(engine) and not settings.database_url:
            backup_storage(settings.storage_dir, reason="before-migration")
        init_db(engine)
        if interrupted := fail_interrupted_jobs(engine):
            log.warning("marked %d interrupted job(s) as failed", interrupted)
        app.state.engine = engine
        app.state.storage = LocalStorage(settings.media_dir)
        app.state.sheet_provider = make_sheet_provider(settings)
        app.state.jobs = JobRunner(engine, asyncio.get_running_loop())
        with Session(engine) as session:
            sheets = make_sheet_provider(settings, reveal=False)
            if settings.seed_on_startup:
                seed(session, app.state.storage, MockImageProvider(), sheets=sheets)
            # The 12 starter characters are for every kid, seeded demo data or not (part B).
            if added := ensure_starters(session, app.state.storage, sheets):
                log.info("added %d starter character(s)", added)
        ensure_images(app.state.storage)  # each prop state's picture, drawn once (Phase 8)
        rechecks = (
            asyncio.create_task(recheck_loop(app, settings.recheck_seconds))
            if settings.recheck_seconds > 0
            else None
        )
        yield
        if rechecks is not None:
            rechecks.cancel()
        app.state.jobs.cancel_all()
        engine.dispose()

    # One schema per model (no -Input/-Output split) keeps the generated TypeScript names simple.
    app = FastAPI(
        title="Comickadha API",
        version=__version__,
        lifespan=lifespan,
        separate_input_output_schemas=False,
    )
    app.state.settings = settings
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    install_error_handlers(app)

    @app.get("/api/health", tags=["health"])
    def health() -> Health:
        return Health(
            status="ok",
            version=__version__,
            llm_provider=settings.llm_provider,
            image_provider=settings.image_provider,
        )

    for router in (
        profile.router,
        characters.router,
        builder.router,
        backgrounds.router,
        comics.router,
        studio.router,
        props.router,
        jobs.router,
        media.router,
    ):
        app.include_router(router)
    return app


app = create_app()
