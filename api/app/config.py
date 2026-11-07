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

    # "meta" uses Meta's model API for the builder helper and safety; "mock" works offline.
    llm_provider: Literal["mock", "meta"] = "mock"
    # Real image providers are added in Phase 6.
    image_provider: Literal["mock"] = "mock"
    # "builder" draws character sheets from the avatar parts; "image" asks the image provider.
    sheet_provider: Literal["builder", "image"] = "builder"
    # Pause per builder cell, so the sheet visibly fills in (22 cells, about 2 seconds).
    builder_reveal_seconds: float = 0.08

    # Meta's model API (OpenAI-compatible). The model names come from .env, never from code.
    meta_api_key: str = ""
    meta_model: str = ""
    # Empty: the same model as META_MODEL.
    meta_vision_model: str = ""
    meta_base_url: str = "https://api.meta.ai/v1"
    meta_timeout_seconds: float = 20.0

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
