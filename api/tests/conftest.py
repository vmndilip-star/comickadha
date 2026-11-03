from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.seed import GARDEN, KITCHEN, MANGO, MIRA, RAJU, ROBO, ROBO_DAY, SPACE, SPACE_PICNIC

# Re-exported so tests read naturally.
IDS = {
    "mira": MIRA,
    "raju": RAJU,
    "robo": ROBO,
    "kitchen": KITCHEN,
    "garden": GARDEN,
    "space": SPACE,
    "mango": MANGO,
    "robo_day": ROBO_DAY,
    "space_picnic": SPACE_PICNIC,
}


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    """A fresh SQLite file and media folder per test, seeded on startup."""
    return Settings(storage_dir=tmp_path / "storage", database_url="", seed_on_startup=True)


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    with TestClient(create_app(settings)) as c:
        yield c
