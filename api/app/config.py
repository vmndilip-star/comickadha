"""App settings, read from environment variables and the repo-root .env (see .env.example)."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

API_DIR = Path(__file__).resolve().parent.parent
REPO_DIR = API_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(REPO_DIR / ".env", API_DIR / ".env"),
        extra="ignore",
    )

    # "meta": Meta's model API for every AI helper, the safety classifier and the image check.
    # "mock": no LLM at all; the offline helpers answer and safety is the local checks only.
    llm_provider: Literal["mock", "meta"] = "mock"
    # "muse": places are painted by Meta's Muse Image (needs LLM_PROVIDER=meta, so the words and the
    # pictures can be checked; startup refuses it otherwise). "mock": offline placeholder places.
    image_provider: Literal["mock", "muse"] = "mock"
    # Pause per builder cell, so the sheet visibly fills in (22 cells, about 2 seconds).
    builder_reveal_seconds: float = 0.08
    # Pause after each panel of "Make my comic!", so the Reader visibly fills in. Tests use 0.
    panel_reveal_seconds: float = 0.4
    # Pause after each part of an offline panel plan, so the Studio visibly fills in scene by
    # scene (Meta's plans take their own time). Tests use 0.
    plan_reveal_seconds: float = 0.3
    # How often story text that is "not yet AI-checked" is re-checked (decision 55). 0: never.
    recheck_seconds: float = 60.0

    # Meta's model API (OpenAI-compatible). The model names come from .env, never from code.
    meta_api_key: str = ""
    meta_model: str = ""
    # Empty: the same model as META_MODEL.
    meta_vision_model: str = ""
    meta_base_url: str = "https://api.meta.ai/v1"
    meta_timeout_seconds: float = 20.0
    # IMAGE_PROVIDER=muse: the image model (from .env, e.g. muse-image-1.0) and its own timeout
    # (a picture took 10-19 s in Phase 6a; decision 82).
    meta_image_model: str = ""
    meta_image_timeout_seconds: float = 60.0

    # Holds the SQLite file and the media/ folder.
    storage_dir: Path = API_DIR / "storage"
    # Empty means a SQLite file inside storage_dir.
    database_url: str = ""
    cors_origins: list[str] = ["http://localhost:5173"]
    # Insert the demo data on startup when the database is empty.
    seed_on_startup: bool = True
    # Pause per mock image, so kids (and demos) can watch a sheet build live. Tests use 0.
    mock_delay_seconds: float = 1.2

    @property
    def resolved_database_url(self) -> str:
        return self.database_url or f"sqlite:///{(self.storage_dir / 'comickatha.db').as_posix()}"

    @property
    def resolved_vision_model(self) -> str:
        return self.meta_vision_model or self.meta_model

    @property
    def media_dir(self) -> Path:
        # A subfolder, so /media can never serve the database file.
        return self.storage_dir / "media"


@lru_cache
def get_settings() -> Settings:
    return Settings()
