from functools import partial

from fastapi import APIRouter
from sqlmodel import Session, col, select

from app.deps import EngineDep, JobsDep, ProviderDep, SessionDep, StorageDep, UserDep
from app.errors import ERROR_RESPONSES, ApiError, not_found
from app.models import Character, User
from app.models.base import utcnow
from app.schemas.character import CharacterCreate, CharacterRead, CharacterSpec, CharacterUpdate
from app.schemas.common import MAX_CAST, Pose
from app.schemas.job import JobStarted
from app.schemas.manifest import CharacterManifest, HeadOffset
from app.services import character_sheet, safety
from app.services.storage import Storage

router = APIRouter(prefix="/api/characters", tags=["characters"], responses=ERROR_RESPONSES)

# One card colour per cast slot (sun, coral and sky tints from the boards).
SLOT_TINTS = ("#FFE9A8", "#FFD0C2", "#DDF0FC")
SAFETY_LABELS = {"name": "name", "outfit": "outfit", "catchphrase": "catchphrase"}


def active_characters(session: Session, user: User) -> list[Character]:
    stmt = (
        select(Character)
        .where(Character.user_id == user.id, col(Character.deleted_at).is_(None))
        .order_by(col(Character.created_at))
    )
    return list(session.exec(stmt))


def get_character(
    session: Session, user: User, character_id: str, *, include_deleted: bool = False
) -> Character:
    character = session.get(Character, character_id)
    if character is None or character.user_id != user.id:
        raise not_found("character")
    if character.deleted_at is not None and not include_deleted:
        raise not_found("character")
    return character


def to_read(character: Character) -> CharacterRead:
    return CharacterRead.model_validate(
        {**character.model_dump(), "deleted": character.deleted_at is not None}
    )


def _save(session: Session, character: Character) -> CharacterRead:
    character.updated_at = utcnow()
    session.add(character)
    session.commit()
    session.refresh(character)
    return to_read(character)


def _busy(character: Character) -> ApiError:
    return ApiError(
        409, "busy", f"{character.name} is being drawn right now. Wait a moment and try again!"
    )


def _no_manifest(character: Character) -> ApiError:
    return ApiError(
        404,
        "no_manifest",
        f"{character.name} doesn't have a character sheet yet. Lock {character.name} to make one.",
    )


@router.get("")
def list_characters(session: SessionDep, user: UserDep) -> list[CharacterRead]:
    return [to_read(c) for c in active_characters(session, user)]


@router.post("", status_code=201)
def create_character(body: CharacterCreate, session: SessionDep, user: UserDep) -> CharacterRead:
    cast = active_characters(session, user)
    if len(cast) >= MAX_CAST:
        raise ApiError(
            409,
            "cast_full",
            f"Your cast is full! You can have {MAX_CAST} characters. "
            "Delete one to make room for someone new.",
        )
    spec = body.spec or CharacterSpec(tint=SLOT_TINTS[len(cast) % len(SLOT_TINTS)])
    character = Character(
        user_id=user.id, name=body.name, role=body.role, kind=body.kind, spec=spec.model_dump()
    )
    return _save(session, character)


@router.get("/{character_id}")
def read_character(character_id: str, session: SessionDep, user: UserDep) -> CharacterRead:
    """Also returns deleted characters (deleted: true), so old comics can still show them."""
    return to_read(get_character(session, user, character_id, include_deleted=True))


@router.patch("/{character_id}")
def update_character(
    character_id: str, body: CharacterUpdate, session: SessionDep, user: UserDep
) -> CharacterRead:
    character = get_character(session, user, character_id)
    if character.status == "generating":
        raise _busy(character)
    if character.status == "locked":
        raise ApiError(
            409,
            "locked",
            f"{character.name} is locked so they look the same in every panel. "
            f"Unlock {character.name} to make changes.",
        )
    if body.name is not None:
        character.name = body.name
    if body.role is not None:
        character.role = body.role
    if body.kind is not None:
        character.kind = body.kind
    if body.spec is not None:
        # Assign a new dict so SQLAlchemy sees the JSON change.
        character.spec = {**character.spec, **body.spec.model_dump(exclude_unset=True)}
    return _save(session, character)


@router.delete("/{character_id}", status_code=204)
def delete_character(character_id: str, session: SessionDep, user: UserDep) -> None:
    """Soft delete: frees the cast slot; comics that already use the character keep it."""
    character = get_character(session, user, character_id)
    if character.status == "generating":
        raise _busy(character)
    character.deleted_at = utcnow()
    _save(session, character)


@router.post("/{character_id}/lock", status_code=202)
def lock_character(
    character_id: str,
    session: SessionDep,
    user: UserDep,
    engine: EngineDep,
    jobs: JobsDep,
    provider: ProviderDep,
    storage: StorageDep,
) -> JobStarted:
    """Checks the look is kid-safe, then draws the character sheet as a job (follow it over SSE)."""
    character = get_character(session, user, character_id)
    if character.status == "generating" and character.last_job_id:
        return JobStarted(
            job_id=character.last_job_id, kind="character_sheet", target_id=character.id
        )
    if character.status == "locked":
        raise ApiError(409, "already_locked", f"{character.name} is already locked!")

    verdict = safety.check_and_log(
        session,
        user.id,
        f"character:{character.id}",
        {
            "name": character.name,
            "outfit": str(character.spec.get("outfit", "")),
            "catchphrase": str(character.spec.get("catchphrase", "")),
        },
    )
    if not verdict.allowed:
        raise ApiError(422, "unsafe", verdict.message(SAFETY_LABELS))

    job = jobs.create("character_sheet", character.id)
    spec = character_sheet.SheetSpec.of(character, version=character.sheet_version + 1)
    character.status = "generating"
    character.last_job_id = job.id
    _save(session, character)
    jobs.start(
        job.id,
        partial(
            character_sheet.run_sheet_job,
            spec=spec,
            engine=engine,
            provider=provider,
            storage=storage,
        ),
        on_error=lambda _message: character_sheet.mark_failed(engine, spec.id),
    )
    return JobStarted(job_id=job.id, kind="character_sheet", target_id=character.id)


@router.post("/{character_id}/unlock")
def unlock_character(character_id: str, session: SessionDep, user: UserDep) -> CharacterRead:
    """Back to editing. The sheet files stay; locking again draws a new version."""
    character = get_character(session, user, character_id)
    if character.status == "generating":
        raise _busy(character)
    character.status = "draft"
    return _save(session, character)


@router.get("/{character_id}/manifest")
def read_manifest(
    character_id: str,
    session: SessionDep,
    user: UserDep,
    storage: StorageDep,
    version: int | None = None,
) -> CharacterManifest:
    """The current manifest, or an older version's (old comics keep the one they used)."""
    character = get_character(session, user, character_id, include_deleted=True)
    if version is not None and version != character.sheet_version:
        key = f"{character_sheet.sheet_prefix(character.id, version)}/manifest.json"
        if version < 1 or not storage.exists(key):
            raise _no_manifest(character)
        return CharacterManifest.model_validate_json(storage.read(key))
    if character.manifest is None:
        raise _no_manifest(character)
    return CharacterManifest.model_validate(character.manifest)


@router.patch("/{character_id}/heads/{pose}")
def update_head_offset(
    character_id: str,
    pose: Pose,
    body: HeadOffset,
    session: SessionDep,
    user: UserDep,
    storage: StorageDep,
) -> CharacterRead:
    """Nudges where the face goes on one pose. Allowed while locked: placement, not looks."""
    character = get_character(session, user, character_id)
    if character.manifest is None:
        raise _no_manifest(character)
    manifest = CharacterManifest.model_validate(character.manifest)
    head = manifest.body_sheet.heads.get(pose)
    if head is None:
        raise not_found("pose")
    head.offset = body
    character.manifest = manifest.model_dump(mode="json")
    _write_manifest_file(storage, manifest)
    return _save(session, character)


def _write_manifest_file(storage: Storage, manifest: CharacterManifest) -> None:
    key = f"{character_sheet.sheet_prefix(manifest.id, manifest.version)}/manifest.json"
    storage.save(key, manifest.model_dump_json(indent=2).encode())
