"""FastAPI dependencies: DB session, storage, image provider, job runner and the current kid."""

from collections.abc import Iterator
from typing import Annotated, cast

from fastapi import Depends, Request
from sqlalchemy import Engine
from sqlmodel import Session, col, select

from app.errors import ApiError
from app.models import User
from app.providers.image import ImageProvider
from app.services.jobs import JobRunner
from app.services.storage import Storage


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


def get_jobs(request: Request) -> JobRunner:
    return cast(JobRunner, request.app.state.jobs)


EngineDep = Annotated[Engine, Depends(get_engine)]
SessionDep = Annotated[Session, Depends(get_session)]
StorageDep = Annotated[Storage, Depends(get_storage)]
ProviderDep = Annotated[ImageProvider, Depends(get_provider)]
JobsDep = Annotated[JobRunner, Depends(get_jobs)]


def get_current_user(session: SessionDep) -> User:
    """No auth in the hackathon build: the one seeded profile is the current kid."""
    user = session.exec(select(User).order_by(col(User.created_at))).first()
    if user is None:
        raise ApiError(
            503, "no_profile", "Comickatha isn't set up yet. Ask a grown-up to run the seed script."
        )
    return user


UserDep = Annotated[User, Depends(get_current_user)]
