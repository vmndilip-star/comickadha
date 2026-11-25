from fastapi import APIRouter

from app.config import Settings
from app.deps import SessionDep, SettingsDep, UserDep
from app.errors import ERROR_RESPONSES, ApiError
from app.models import User
from app.models.base import utcnow
from app.schemas.common import MAX_CAST
from app.schemas.profile import DrawingConsent, ProfileRead

router = APIRouter(prefix="/api", tags=["profile"], responses=ERROR_RESPONSES)


def to_read(user: User, settings: Settings) -> ProfileRead:
    return ProfileRead(
        id=user.id,
        display_name=user.display_name,
        avatar_color=user.avatar_color,
        max_cast=MAX_CAST,
        painting_enabled=settings.painting_enabled,
        drawing_consent_at=user.drawing_consent_at,
    )


@router.get("/me")
def get_me(user: UserDep, settings: SettingsDep) -> ProfileRead:
    return to_read(user, settings)


@router.put("/me/drawing-consent")
def give_drawing_consent(
    body: DrawingConsent, session: SessionDep, user: UserDep, settings: SettingsDep
) -> ProfileRead:
    """A grown-up OKs sending drawings to Meta AI (once per profile, with a timestamp)."""
    if body.a * body.b != body.answer:
        raise ApiError(422, "wrong_answer", "That's not quite right. Ask a grown-up to help!")
    user.drawing_consent_at = utcnow()
    session.add(user)
    session.commit()
    session.refresh(user)
    return to_read(user, settings)


@router.delete("/me/drawing-consent")
def revoke_drawing_consent(
    session: SessionDep, user: UserDep, settings: SettingsDep
) -> ProfileRead:
    """Takes the OK back: drawings won't be sent until a grown-up says yes again."""
    user.drawing_consent_at = None
    session.add(user)
    session.commit()
    session.refresh(user)
    return to_read(user, settings)
