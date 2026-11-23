"""FastAPI dependencies: DB session, storage, image provider, job runner and the current kid."""

from collections.abc import Iterator
from typing import Annotated, cast

from fastapi import Depends, Request
from sqlalchemy import Engine
from sqlmodel import Session, col, select

from app.errors import ApiError
from app.models import User
from app.providers.image import ImageProvider
from app.providers.llm import LLMProvider
from app.services.character_sheet import SheetProvider
from app.services.jobs import JobRunner
from app.services.storage import Storage
from app.starters import STARTER_USER_ID


def get_engine(request: Request) -> Engine:
    return cast(Engine, request.app.state.engine)


def get_session(request: Request) -> Iterator[Session]:
    with Session(get_engine(request)) as session:
        yield session


def get_storage(request: Request) -> Storage:
    return cast(Storage, request.app.state.storage)


def get_provider(request: Request) -> ImageProvider:
    # Read per request, so tests can swap the provider on a running app.
    return cast(ImageProvider, request.app.state.image_provider)


def get_sheets(request: Request) -> SheetProvider:
    return cast(SheetProvider, request.app.state.sheet_provider)


def get_llm(request: Request) -> LLMProvider | None:
    """None when offline (LLM_PROVIDER=mock)."""
    return cast(LLMProvider | None, request.app.state.llm)


def get_jobs(request: Request) -> JobRunner:
    return cast(JobRunner, request.app.state.jobs)


EngineDep = Annotated[Engine, Depends(get_engine)]
SessionDep = Annotated[Session, Depends(get_session)]
StorageDep = Annotated[Storage, Depends(get_storage)]
ProviderDep = Annotated[ImageProvider, Depends(get_provider)]
SheetsDep = Annotated[SheetProvider, Depends(get_sheets)]
LLMDep = Annotated[LLMProvider | None, Depends(get_llm)]
JobsDep = Annotated[JobRunner, Depends(get_jobs)]


def get_current_user(session: SessionDep) -> User:
    """No auth in the hackathon build: the one seeded profile is the current kid (never the
    starter cast profile that owns the starter characters)."""
    stmt = select(User).where(User.id != STARTER_USER_ID).order_by(col(User.created_at))
    user = session.exec(stmt).first()
    if user is None:
        raise ApiError(
            503, "no_profile", "Comickatha isn't set up yet. Ask a grown-up to run the seed script."
        )
    return user


UserDep = Annotated[User, Depends(get_current_user)]
