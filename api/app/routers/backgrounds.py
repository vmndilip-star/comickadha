from functools import partial

from fastapi import APIRouter
from sqlmodel import Session, col, select

from app.deps import EngineDep, JobsDep, ProviderDep, SessionDep, StorageDep, UserDep
from app.errors import ERROR_RESPONSES, ApiError, not_found
from app.models import Background, User
from app.models.base import utcnow
from app.schemas.background import BackgroundCreate, BackgroundRead, BackgroundUpdate
from app.schemas.job import JobStarted
from app.services import image_gen, safety
from app.services.storage import Storage

router = APIRouter(prefix="/api/backgrounds", tags=["backgrounds"], responses=ERROR_RESPONSES)

PLACE_TINTS = ("#B7E4A7", "#FFD0C2", "#9AD0F5", "#FFE9A8", "#2E2A6B", "#FF8A6B")
SAFETY_LABELS = {"name": "place name", "description": "description"}


def active_backgrounds(session: Session, user: User) -> list[Background]:
    stmt = (
        select(Background)
        .where(Background.user_id == user.id, col(Background.deleted_at).is_(None))
        .order_by(col(Background.created_at))
    )
    return list(session.exec(stmt))


def get_background(
    session: Session, user: User, background_id: str, *, include_deleted: bool = False
) -> Background:
    bg = session.get(Background, background_id)
    if bg is None or bg.user_id != user.id:
        raise not_found("place")
    if bg.deleted_at is not None and not include_deleted:
        raise not_found("place")
    return bg


def to_read(bg: Background, storage: Storage) -> BackgroundRead:
    return BackgroundRead.model_validate(
        {
            **bg.model_dump(),
            "image_url": storage.url(bg.image_key) if bg.image_key else None,
            "thumb_url": storage.url(bg.thumb_key) if bg.thumb_key else None,
            "deleted": bg.deleted_at is not None,
        }
    )


def _save(session: Session, bg: Background, storage: Storage) -> BackgroundRead:
    bg.updated_at = utcnow()
    session.add(bg)
    session.commit()
    session.refresh(bg)
    return to_read(bg, storage)


@router.get("")
def list_backgrounds(
    session: SessionDep, user: UserDep, storage: StorageDep
) -> list[BackgroundRead]:
    return [to_read(bg, storage) for bg in active_backgrounds(session, user)]


@router.post("", status_code=201)
def create_background(
    body: BackgroundCreate, session: SessionDep, user: UserDep, storage: StorageDep
) -> BackgroundRead:
    count = len(active_backgrounds(session, user))
    bg = Background(
        user_id=user.id,
        name=body.name,
        description=body.description,
        tint=body.tint or PLACE_TINTS[count % len(PLACE_TINTS)],
    )
    return _save(session, bg, storage)


@router.get("/{background_id}")
def read_background(
    background_id: str, session: SessionDep, user: UserDep, storage: StorageDep
) -> BackgroundRead:
    return to_read(get_background(session, user, background_id, include_deleted=True), storage)


@router.patch("/{background_id}")
def update_background(
    background_id: str,
    body: BackgroundUpdate,
    session: SessionDep,
    user: UserDep,
    storage: StorageDep,
) -> BackgroundRead:
    bg = get_background(session, user, background_id)
    if bg.status == "generating":
        raise _busy(bg)
    if bg.status == "locked":
        raise ApiError(
            409,
            "locked",
            f"{bg.name} is locked so it looks the same in every panel. Unlock it to make changes.",
        )
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(bg, field, value)
    return _save(session, bg, storage)


@router.delete("/{background_id}", status_code=204)
def delete_background(
    background_id: str, session: SessionDep, user: UserDep, storage: StorageDep
) -> None:
    bg = get_background(session, user, background_id)
    if bg.status == "generating":
        raise _busy(bg)
    bg.deleted_at = utcnow()
    _save(session, bg, storage)


def _busy(bg: Background) -> ApiError:
    return ApiError(
        409, "busy", f"{bg.name} is being painted right now. Wait a moment and try again!"
    )


@router.post("/{background_id}/lock", status_code=202)
def lock_background(
    background_id: str,
    session: SessionDep,
    user: UserDep,
    engine: EngineDep,
    jobs: JobsDep,
    provider: ProviderDep,
    storage: StorageDep,
) -> JobStarted:
    """Checks the description is kid-safe, then paints the reference image as an SSE-tracked job."""
    bg = get_background(session, user, background_id)
    if bg.status == "generating" and bg.last_job_id:
        return JobStarted(job_id=bg.last_job_id, kind="background_image", target_id=bg.id)
    if bg.status == "locked":
        raise ApiError(409, "already_locked", f"{bg.name} is already locked!")

    verdict = safety.check_and_log(
        session, user.id, f"background:{bg.id}", {"name": bg.name, "description": bg.description}
    )
    if not verdict.allowed:
        raise ApiError(422, "unsafe", verdict.message(SAFETY_LABELS))

    job = jobs.create("background_image", bg.id)
    spec = image_gen.PlaceSpec.of(bg, version=bg.version + 1)
    bg.status = "generating"
    bg.last_job_id = job.id
    _save(session, bg, storage)
    jobs.start(
        job.id,
        partial(
            image_gen.run_place_job, spec=spec, engine=engine, provider=provider, storage=storage
        ),
        on_error=lambda _message: image_gen.mark_failed(engine, spec.id),
    )
    return JobStarted(job_id=job.id, kind="background_image", target_id=bg.id)


@router.post("/{background_id}/unlock")
def unlock_background(
    background_id: str, session: SessionDep, user: UserDep, storage: StorageDep
) -> BackgroundRead:
    bg = get_background(session, user, background_id)
    if bg.status == "generating":
        raise _busy(bg)
    bg.status = "draft"
    return _save(session, bg, storage)
