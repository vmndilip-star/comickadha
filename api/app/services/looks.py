"""Pinned looks: the frozen spec of every character sheet version.

Locking a character freezes its spec as that sheet version (CharacterVersion). Panels pin a
sheet_version and are drawn from that spec, never the character's current one, so old comics
never change. `backfill_versions` fills in versions locked before this table existed: from the
version's manifest.json when it holds a builder spec, otherwise from the current spec.
"""

import json
from collections.abc import Iterable
from typing import Any

from sqlalchemy import Engine, inspect, text
from sqlmodel import Session, col, select

from app.avatar.spec import normalize
from app.models import Character, CharacterVersion
from app.services.storage import Storage

Spec = dict[str, Any]


def freeze(session: Session, character_id: str, version: int, spec: Spec) -> None:
    """Stores the look for a sheet version (once: a version never changes)."""
    stmt = select(CharacterVersion).where(
        CharacterVersion.character_id == character_id, CharacterVersion.version == version
    )
    if session.exec(stmt).first() is None:
        session.add(
            CharacterVersion(character_id=character_id, version=version, spec=normalize(spec))
        )


def needs_backfill(engine: Engine) -> bool:
    """Locked versions with no frozen look yet (checked before tables are created or changed)."""
    inspector = inspect(engine)
    if not inspector.has_table("character"):
        return False
    with engine.connect() as conn:
        wanted = conn.execute(
            text("SELECT COALESCE(SUM(sheet_version), 0) FROM character")
        ).scalar()
        if not wanted:
            return False
        if not inspector.has_table("character_version"):
            return True
        have = conn.execute(text("SELECT COUNT(*) FROM character_version")).scalar()
        return bool(have is not None and have < wanted)


def _manifest_spec(storage: Storage, character_id: str, version: int) -> Spec | None:
    key = f"characters/{character_id}/v{version}/manifest.json"
    if not storage.exists(key):
        return None
    spec = json.loads(storage.read(key)).get("spec") or {}
    return spec if "body_type" in spec else None


def backfill_versions(engine: Engine, storage: Storage) -> int:
    """Freezes a look for every locked version that lacks one. Returns how many were added."""
    added = 0
    with Session(engine) as session:
        have = {(v.character_id, v.version) for v in session.exec(select(CharacterVersion))}
        for character in session.exec(select(Character).where(col(Character.sheet_version) > 0)):
            for version in range(1, character.sheet_version + 1):
                if (character.id, version) in have:
                    continue
                spec = _manifest_spec(storage, character.id, version) or character.spec
                freeze(session, character.id, version, spec)
                added += 1
        session.commit()
    return added


def looks_for(session: Session, pairs: Iterable[tuple[str, int]]) -> dict[str, dict[str, Spec]]:
    """{character_id: {"version": spec}} for the (character, sheet_version) pairs asked for."""
    wanted = set(pairs)
    if not wanted:
        return {}
    ids = {cid for cid, _ in wanted}
    out: dict[str, dict[str, Spec]] = {}
    stmt = select(CharacterVersion).where(col(CharacterVersion.character_id).in_(ids))
    for row in session.exec(stmt):
        if (row.character_id, row.version) in wanted:
            out.setdefault(row.character_id, {})[str(row.version)] = row.spec
    return out


def pinned_spec(session: Session, character_id: str, version: int) -> Spec | None:
    stmt = select(CharacterVersion).where(
        CharacterVersion.character_id == character_id, CharacterVersion.version == version
    )
    row = session.exec(stmt).first()
    return row.spec if row else None


def specs_for(session: Session, characters: list[dict[str, Any]]) -> dict[str, Spec]:
    """The look to draw for each character in a panel: its pinned version's spec, or (for a
    version with no frozen look, such as an unlocked character) its current spec."""
    pairs = {(c["id"], int(c.get("sheet_version", 0))) for c in characters}
    found = looks_for(session, pairs)
    out: dict[str, Spec] = {}
    for c in characters:
        spec = found.get(c["id"], {}).get(str(int(c.get("sheet_version", 0))))
        if spec is None:
            row = session.get(Character, c["id"])
            spec = row.spec if row else {}
        out[c["id"]] = spec
    return out
