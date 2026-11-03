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

    # Real providers are added to these literals in Phase 6.
    llm_provider: Literal["mock"] = "mock"
    image_provider: Literal["mock"] = "mock"

    storage_dir: Path = API_DIR / "storage"
    # Empty means a SQLite file inside storage_dir.
    database_url: str = ""
    cors_origins: list[str] = ["http://localhost:5173"]

    @property
    def resolved_database_url(self) -> str:
        return self.database_url or f"sqlite:///{(self.storage_dir / 'comickatha.db').as_posix()}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
