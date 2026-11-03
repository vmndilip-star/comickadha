"""FastAPI entry point: create_app() wires settings, database, storage, routers and errors."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlmodel import Session

from app import __version__
from app.config import Settings, get_settings
from app.db import init_db, make_engine
from app.errors import install_error_handlers
from app.providers.mock import MockImageProvider
from app.routers import backgrounds, characters, comics, media, profile
from app.seed import seed
from app.services.storage import LocalStorage


class Health(BaseModel):
    status: Literal["ok"]
    version: str
    llm_provider: str
    image_provider: str


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        settings.storage_dir.mkdir(parents=True, exist_ok=True)
        engine = make_engine(settings.resolved_database_url)
        init_db(engine)
        app.state.engine = engine
        app.state.storage = LocalStorage(settings.media_dir)
        if settings.seed_on_startup:
            with Session(engine) as session:
                seed(session, app.state.storage, MockImageProvider())
        yield
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
        )

    for router in (
        profile.router,
        characters.router,
        backgrounds.router,
        comics.router,
        media.router,
    ):
        app.include_router(router)
    return app


app = create_app()
