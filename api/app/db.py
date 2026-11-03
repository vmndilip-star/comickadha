"""Database engine and table creation. SQLite for the hackathon; Postgres-ready via the URL."""

from typing import Any

from sqlalchemy import Engine, event
from sqlmodel import SQLModel, create_engine

import app.models  # noqa: F401  (registers tables)


def make_engine(url: str) -> Engine:
    is_sqlite = url.startswith("sqlite")
    engine = create_engine(url, connect_args={"check_same_thread": False} if is_sqlite else {})
    if is_sqlite:

        @event.listens_for(engine, "connect")
        def _enable_foreign_keys(dbapi_connection: Any, _record: Any) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


def init_db(engine: Engine) -> None:
    SQLModel.metadata.create_all(engine)
