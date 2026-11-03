"""FastAPI entry point. Phase 1 has the health check only; domain routers arrive in Phase 2."""

from typing import Literal

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app import __version__
from app.config import get_settings


class Health(BaseModel):
    status: Literal["ok"]
    version: str
    llm_provider: str
    image_provider: str


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Comickatha API", version=__version__)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    def health() -> Health:
        return Health(
            status="ok",
            version=__version__,
            llm_provider=settings.llm_provider,
            image_provider=settings.image_provider,
        )

    return app


app = create_app()
