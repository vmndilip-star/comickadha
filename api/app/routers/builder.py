"""The builder helper: create a character, describe it, surprise me, name ideas, from a drawing.

Answers come from Meta's model API (LLM_PROVIDER=meta) or the offline helper, and are always a full
spec the parts library can draw. The browser applies them, so the kid can still tweak or undo.
"""

from typing import Any

from fastapi import APIRouter

from app.deps import LLMDep, SessionDep, UserDep
from app.errors import ERROR_RESPONSES
from app.schemas.builder import (
    Created,
    CreateRequest,
    DescribeRequest,
    DrawingRequest,
    HelperInfo,
    Ideas,
    IdeasRequest,
    Suggestion,
    SurpriseRequest,
)
from app.schemas.common import ErrorBody
from app.services import drawing
from app.services.builder_create import Creator
from app.services.builder_helper import Helper, label

RESPONSES: dict[int | str, dict[str, Any]] = {
    **ERROR_RESPONSES,
    403: {"model": ErrorBody},
    413: {"model": ErrorBody},
}
router = APIRouter(prefix="/api/builder", tags=["builder"], responses=RESPONSES)


@router.get("/info")
def helper_info(llm: LLMDep, user: UserDep) -> HelperInfo:
    source = "meta" if llm is not None else "mock"
    return HelperInfo(
        source=source,
        label=label(source),
        drawing_needs_consent=llm is not None,
        drawing_consent=user.drawing_consent_at is not None,
    )


@router.post("/create")
def create(body: CreateRequest, llm: LLMDep, session: SessionDep, user: UserDep) -> Created:
    """A brand-new character from a few choices and an optional description. The rules are in
    docs/character-safety.md: everything is checked before Meta sees it, every answer is checked
    field by field, and anything unusable is replaced with a safe default."""
    return Creator(llm, session, user.id).create(body)


@router.post("/describe")
def describe(body: DescribeRequest, llm: LLMDep, session: SessionDep, user: UserDep) -> Suggestion:
    """ "A brave girl with curly red hair and a cape" -> a spec with those parts."""
    return Helper(llm, session, user.id).describe(body.text, body.spec.model_dump())


@router.post("/surprise")
def surprise(body: SurpriseRequest, llm: LLMDep, session: SessionDep, user: UserDep) -> Suggestion:
    spec = body.spec.model_dump() if body.spec else {"body_type": body.body_type or "kid"}
    return Helper(llm, session, user.id).surprise(body.body_type, spec)


@router.post("/ideas")
def ideas(body: IdeasRequest, llm: LLMDep, session: SessionDep, user: UserDep) -> Ideas:
    """Names, personality traits and a catchphrase that suit the character."""
    return Helper(llm, session, user.id).ideas(body.spec.model_dump(), body.name)


@router.post("/from-drawing")
def from_drawing(
    body: DrawingRequest, llm: LLMDep, session: SessionDep, user: UserDep
) -> Suggestion:
    """Picks parts and colours from a kid's drawing. The upload is never stored."""
    png, image = drawing.decode(body.image)
    return Helper(llm, session, user.id).from_drawing(
        png, image, body.spec.model_dump(), consent=user.drawing_consent_at is not None
    )
