"""File storage behind a small interface, so S3 can replace local disk later."""

import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import Protocol

# Keys look like "characters/<id>/v1/body_sheet.png". Every segment starts with a letter or digit,
# so "..", hidden files and absolute paths are impossible.
_KEY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*(/[A-Za-z0-9][A-Za-z0-9._-]*)*$")


class InvalidKeyError(ValueError):
    pass


class Storage(Protocol):
    def save(self, key: str, data: bytes) -> str: ...
    def read(self, key: str) -> bytes: ...
    def exists(self, key: str) -> bool: ...
    def delete_prefix(self, prefix: str) -> None: ...
    def url(self, key: str) -> str: ...
    def local_path(self, key: str) -> Path | None:
        """Path on disk for local storage; None for remote storage."""
        ...


class LocalStorage:
    def __init__(self, root: Path, base_url: str = "/media") -> None:
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.base_url = base_url.rstrip("/")

    def _path(self, key: str) -> Path:
        if not _KEY_RE.match(key):
            raise InvalidKeyError(key)
        path = (self.root / key).resolve()
        if not path.is_relative_to(self.root):
            raise InvalidKeyError(key)
        return path

    def save(self, key: str, data: bytes) -> str:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        # Write then rename, so readers never see a half-written file.
        fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".tmp-")
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        os.replace(tmp, path)
        return key

    def read(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def exists(self, key: str) -> bool:
        return self._path(key).is_file()

    def delete_prefix(self, prefix: str) -> None:
        path = self._path(prefix)
        if path.is_dir():
            shutil.rmtree(path)
        elif path.is_file():
            path.unlink()

    def url(self, key: str) -> str:
        return f"{self.base_url}/{key}"

    def local_path(self, key: str) -> Path | None:
        return self._path(key)
