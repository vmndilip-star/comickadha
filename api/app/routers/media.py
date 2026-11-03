from fastapi import APIRouter
from fastapi.responses import FileResponse

from app.deps import StorageDep
from app.errors import not_found
from app.services.storage import InvalidKeyError

router = APIRouter(tags=["media"])


@router.get("/media/{key:path}", include_in_schema=False)
def get_media(key: str, storage: StorageDep) -> FileResponse:
    """Serves stored files (sheets, place images, panels) from local storage."""
    try:
        path = storage.local_path(key)
    except InvalidKeyError:
        raise not_found("picture") from None
    if path is None or not path.is_file():
        raise not_found("picture")
    return FileResponse(path)
