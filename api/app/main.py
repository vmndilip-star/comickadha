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
from app.avatar.migrate import migrate_characters
from app.config import Settings, get_settings
from app.db import init_db, make_engine
from app.errors import install_error_handlers
from app.providers import get_image_provider, get_llm_provider
from app.providers.image import ImageProvider
from app.providers.mock import MockImageProvider
from app.routers import backgrounds, builder, characters, comics, jobs, media, profile
from app.seed import seed
from app.services.builder_sheet import BuilderSheets
from app.services.character_sheet import ImageSheets, SheetProvider
from app.services.jobs import JobRunner, fail_interrupted_jobs
from app.services.storage import LocalStorage

log = logging.getLogger(__name__)


class Health(BaseModel):
    status: Literal["ok"]
    version: str
    llm_provider: str
    image_provider: str
    sheet_provider: str


def make_sheet_provider(
    settings: Settings, image_provider: ImageProvider, *, reveal: bool = True
) -> SheetProvider:
    """reveal=False skips the builder's per-cell pause (seeding has nobody watching)."""
    if settings.sheet_provider == "image":
        return ImageSheets(image_provider)
    return BuilderSheets(reveal_seconds=settings.builder_reveal_seconds if reveal else 0)


def _log_to_console() -> None:
    """Shows the app's INFO lines (such as Meta token counts) next to uvicorn's."""
    app_log = logging.getLogger("app")
    if not app_log.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(levelname)s:     %(name)s: %(message)s"))
        app_log.addHandler(handler)
        app_log.setLevel(logging.INFO)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    _log_to_console()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        # First, so a bad Meta setting (missing key or model, a -contributor model) stops startup.
        app.state.llm = get_llm_provider(settings)
        settings.storage_dir.mkdir(parents=True, exist_ok=True)
        engine = make_engine(settings.resolved_database_url)
        init_db(engine)
        if interrupted := fail_interrupted_jobs(engine):
            log.warning("marked %d interrupted job(s) as failed", interrupted)
        if migrated := migrate_characters(engine):
            log.info("moved %d character(s) to builder specs", migrated)
        app.state.engine = engine
        app.state.storage = LocalStorage(settings.media_dir)
        app.state.image_provider = get_image_provider(settings)
        app.state.sheet_provider = make_sheet_provider(settings, app.state.image_provider)
        app.state.jobs = JobRunner(engine, asyncio.get_running_loop())
        if settings.seed_on_startup:
            with Session(engine) as session:
                mock = MockImageProvider()
                sheets = make_sheet_provider(settings, mock, reveal=False)
                seed(session, app.state.storage, mock, sheets=sheets)
        yield
        app.state.jobs.cancel_all()
        engine.dispose()

    # One schema per model (no -Input/-Output split) keeps the generated TypeScript names simple.
    app = FastAPI(
        title="Comickatha API",
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
            sheet_provider=settings.sheet_provider,
        )

    for router in (
        profile.router,
        characters.router,
        builder.router,
        backgrounds.router,
        comics.router,
        jobs.router,
        media.router,
    ):
        app.include_router(router)
    return app


app = create_app()
