"""Backups of the storage folder (SQLite database + media), made before any migration.

Backups go to `<storage_dir>/../storage-backups/<timestamp>/` (api/storage-backups by default,
gitignored). The database is copied with SQLite's backup API, so a copy taken while the server is
running is consistent. Only the newest `KEEP` backups are kept. `uv run python -m app.backup`
makes one by hand.
"""

import logging
import shutil
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

log = logging.getLogger(__name__)

KEEP = 5
DB_NAME = "comickatha.db"


def backups_dir(storage_dir: Path) -> Path:
    return storage_dir.parent / "storage-backups"


def backup_storage(storage_dir: Path, *, reason: str = "manual", keep: int = KEEP) -> Path | None:
    """Copies the database and media; returns the backup folder (None if there is nothing yet)."""
    db = storage_dir / DB_NAME
    media = storage_dir / "media"
    if not db.exists() and not media.exists():
        return None
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S-%f")
    target = backups_dir(storage_dir) / f"{stamp}-{reason}"
    target.mkdir(parents=True)
    if db.exists():
        source = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
        copy = sqlite3.connect(target / DB_NAME)
        try:
            source.backup(copy)
        finally:
            copy.close()
            source.close()
    if media.exists():
        shutil.copytree(media, target / "media")
    prune(storage_dir, keep)
    message = f"Backed up {storage_dir} to {target}"
    print(message, flush=True)
    log.info(message)
    return target


def prune(storage_dir: Path, keep: int = KEEP) -> None:
    """Deletes all but the newest `keep` backups (folder names start with a sortable timestamp)."""
    root = backups_dir(storage_dir)
    if not root.exists():
        return
    folders = sorted((p for p in root.iterdir() if p.is_dir()), key=lambda p: p.name)
    for old in folders[: max(0, len(folders) - keep)]:
        shutil.rmtree(old, ignore_errors=True)
