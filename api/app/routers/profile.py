from fastapi import APIRouter

from app.deps import UserDep
from app.errors import ERROR_RESPONSES
from app.schemas.common import MAX_CAST
from app.schemas.profile import ProfileRead

router = APIRouter(prefix="/api", tags=["profile"], responses=ERROR_RESPONSES)


@router.get("/me")
def get_me(user: UserDep) -> ProfileRead:
    return ProfileRead(
        id=user.id,
        display_name=user.display_name,
        avatar_color=user.avatar_color,
        max_cast=MAX_CAST,
    )
