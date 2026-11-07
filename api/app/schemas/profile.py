from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import UtcDatetime


class ProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    display_name: str
    avatar_color: str
    max_cast: int
    # When a grown-up OK'd sending drawings to Meta AI; null if not given (or taken back).
    drawing_consent_at: UtcDatetime | None


class DrawingConsent(BaseModel):
    """The grown-up check: a times-table question kids under 10 can't easily answer."""

    a: int = Field(ge=6, le=12)
    b: int = Field(ge=6, le=12)
    answer: int
