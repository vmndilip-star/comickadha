"""Pinned looks: the frozen spec of every character sheet version.

Locking a character freezes its spec as that sheet version (CharacterVersion). Panels pin a
sheet_version and are drawn from that spec, never the character's current one, so old comics
never change.
"""

from collections.abc import Iterable
from typing import Any

from sqlmodel import Session, col, select

from app.avatar.spec import normalize
from app.models import Character, CharacterVersion

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
