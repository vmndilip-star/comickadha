"""Database engine and table creation. SQLite for the hackathon; Postgres-ready via the URL."""

from typing import Any

from sqlalchemy import Engine, event, inspect, text
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
    add_missing_columns(engine)


def missing_columns(engine: Engine) -> list[str]:
    """ "table.column" for every nullable column the models have but the database lacks."""
    inspector = inspect(engine)
    missing: list[str] = []
    for table in SQLModel.metadata.sorted_tables:
        if not inspector.has_table(table.name):
            continue
        existing = {c["name"] for c in inspector.get_columns(table.name)}
        missing += [f"{table.name}.{c.name}" for c in table.columns if c.name not in existing]
    return missing


def add_missing_columns(engine: Engine) -> None:
    """Adds nullable columns that newer models have but an older database lacks.

    A tiny stand-in for migrations while the schema only grows (no Alembic in the hackathon build).
    """
    inspector = inspect(engine)
    with engine.begin() as conn:
        for table in SQLModel.metadata.sorted_tables:
            if not inspector.has_table(table.name):
                continue
            existing = {c["name"] for c in inspector.get_columns(table.name)}
            for column in table.columns:
                if column.name not in existing and column.nullable:
                    ddl = column.type.compile(engine.dialect)
                    conn.execute(
                        text(f'ALTER TABLE "{table.name}" ADD COLUMN "{column.name}" {ddl}')
                    )
