"""Database engine and table creation. SQLite for the hackathon; Postgres-ready via the URL."""

from typing import Any

from sqlalchemy import Engine, event, inspect, text
from sqlmodel import SQLModel, create_engine

import app.models  # noqa: F401  (registers tables)


def make_engine(url: str) -> Engine:
    is_sqlite = url.startswith("sqlite")
    # SQLite: wait up to 30 s for another request's write (drawing a panel can take a moment)
    # instead of failing with "database is locked" after 5.
    args = {"check_same_thread": False, "timeout": 30} if is_sqlite else {}
    engine = create_engine(url, connect_args=args)
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
    pin_place_versions(engine)


def pin_place_versions(engine: Engine) -> None:
    """Panels from before place versions (Phase 8) pin the version their place has now: locked
    places couldn't be repainted until then, so it is the picture they were drawn with."""
    with engine.begin() as conn:
        conn.execute(
            text(
                "UPDATE panel SET place_version = (SELECT version FROM background "
                "WHERE background.id = panel.background_id) WHERE place_version IS NULL"
            )
        )


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
