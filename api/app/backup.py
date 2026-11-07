"""`uv run python -m app.backup`: backs up the storage folder (keeps the newest 5)."""

from app.config import get_settings
from app.services.backup import backup_storage


def main() -> None:
    if backup_storage(get_settings().storage_dir) is None:
        print("Nothing to back up yet.")


if __name__ == "__main__":
    main()
