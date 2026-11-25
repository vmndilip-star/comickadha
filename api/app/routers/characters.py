import copy
from functools import partial

from fastapi import APIRouter
from sqlalchemy import or_
from sqlmodel import Session, col, select

from app.avatar import spec as avatar_spec
from app.deps import EngineDep, JobsDep, SessionDep, SheetsDep, StorageDep, UserDep
from app.errors import ERROR_RESPONSES, ApiError, invalid, not_found
from app.models import Character, User
from app.models.base import utcnow
from app.schemas.avatar import AvatarSpec
from app.schemas.character import CharacterCreate, CharacterRead, CharacterUpdate
from app.schemas.common import MAX_CAST
from app.schemas.job import JobStarted
from app.schemas.manifest import CharacterManifest
from app.services import character_safety, character_sheet, safety

router = APIRouter(prefix="/api/characters", tags=["characters"], responses=ERROR_RESPONSES)

SAFETY_LABELS = {"name": "name", "catchphrase": "catchphrase"}
STARTER_MESSAGE = "Starter characters can't be changed. Tap Make it mine to get your own copy!"


def active_characters(session: Session, user: User) -> list[Character]:
    """The kid's own characters (the 3 cast slots), oldest first."""
    stmt = (
        select(Character)
        .where(Character.user_id == user.id, col(Character.deleted_at).is_(None))
        .order_by(col(Character.created_at))
    )
    return list(session.exec(stmt))


def starter_characters(session: Session) -> list[Character]:
    """The ready-made starter characters (app/starters.py), in the order kids see them."""
    stmt = (
        select(Character)
        .where(col(Character.starter).is_(True), col(Character.deleted_at).is_(None))
        .order_by(col(Character.created_at))
    )
    return list(session.exec(stmt))


def usable_character_ids(
    session: Session, user: User, ids: list[str], *, active: bool = False
) -> set[str]:
    """Which of these ids a comic may use: the kid's own characters and the starters (active:
    leave out deleted ones)."""
    if not ids:
        return set()
    stmt = select(Character.id).where(
        col(Character.id).in_(ids),
        or_(col(Character.user_id) == user.id, col(Character.starter).is_(True)),
    )
    if active:
        stmt = stmt.where(col(Character.deleted_at).is_(None))
    return set(session.exec(stmt))


def get_character(
    session: Session, user: User, character_id: str, *, include_deleted: bool = False
) -> Character:
    """One of the kid's own characters, or a starter (read-only: see `not_starter`)."""
    character = session.get(Character, character_id)
    if character is None or (character.user_id != user.id and not character.starter):
        raise not_found("character")
    if character.deleted_at is not None and not include_deleted:
        raise not_found("character")
    return character


def to_read(character: Character) -> CharacterRead:
    return CharacterRead.model_validate(
        {
            **character.model_dump(),
            "starter": bool(character.starter),
            "deleted": character.deleted_at is not None,
        }
    )


def not_starter(character: Character) -> None:
    """Starters are the same for every kid: editing, deleting, locking or unlocking one is a 409."""
    if character.starter:
        raise ApiError(409, "starter", STARTER_MESSAGE)


def _save(session: Session, character: Character) -> CharacterRead:
    character.updated_at = utcnow()
    session.add(character)
    session.commit()
    session.refresh(character)
    return to_read(character)


def checked_spec(spec: AvatarSpec) -> dict[str, object]:
    """The full spec, checked against the parts catalog."""
    try:
        return avatar_spec.validate(spec.model_dump())
    except avatar_spec.SpecError as error:
        raise ApiError(422, "unknown_part", str(error)) from error


def _apply_spec(character: Character, spec: dict[str, object]) -> None:
    character.spec = spec
    character.kind = avatar_spec.KIND_OF_BODY[str(spec["body_type"])]
    character.role = str(spec["role"])


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


def _room_in_cast(session: Session, user: User) -> list[Character]:
    """The kid's own cast, if there's room for one more (starters don't count); else cast_full."""
    cast = active_characters(session, user)
    if len(cast) >= MAX_CAST:
        raise ApiError(
            409,
            "cast_full",
            f"Your cast is full! You can have {MAX_CAST} characters. "
            "Delete one to make room for someone new.",
        )
    return cast


@router.get("")
def list_characters(session: SessionDep, user: UserDep) -> list[CharacterRead]:
    """The kid's own characters, then the starter characters (`starter: true`)."""
    return [to_read(c) for c in [*active_characters(session, user), *starter_characters(session)]]


@router.post("", status_code=201)
def create_character(body: CharacterCreate, session: SessionDep, user: UserDep) -> CharacterRead:
    cast = _room_in_cast(session, user)
    # The same name rules as /builder/create: word list, personal info, famous and real people.
    character_safety.check_name(session, user.id, "character:new", body.name)
    card = avatar_spec.SLOT_CARDS[len(cast) % len(avatar_spec.SLOT_CARDS)]
    spec = checked_spec(body.spec) if body.spec else avatar_spec.default_spec("kid", card=card)
    character = Character(
        user_id=user.id, name=body.name, role="friend", kind="kid", designed_by=body.designed_by
    )
    _apply_spec(character, spec)
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
    not_starter(character)
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
    if body.spec is not None:
        spec = checked_spec(body.spec)
        if spec != character.spec:
            character.designed_by = None  # the kid made it their own: no more "Designed by" badge
        _apply_spec(character, spec)
    return _save(session, character)


@router.delete("/{character_id}", status_code=204)
def delete_character(character_id: str, session: SessionDep, user: UserDep) -> None:
    """Soft delete: frees the cast slot; comics that already use the character keep it."""
    character = get_character(session, user, character_id)
    not_starter(character)
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
    sheets: SheetsDep,
    storage: StorageDep,
) -> JobStarted:
    """Checks the words are kid-safe, then draws the character sheet as a job (follow it over SSE).

    The builder draws all 22 cells from the parts library in a couple of seconds.
    """
    character = get_character(session, user, character_id)
    not_starter(character)
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
            "catchphrase": str(character.spec.get("personality", {}).get("catchphrase", "")),
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
            sheets=sheets,
            storage=storage,
        ),
        on_error=lambda _message: character_sheet.mark_failed(engine, spec.id),
    )
    return JobStarted(job_id=job.id, kind="character_sheet", target_id=character.id)


@router.post("/{character_id}/unlock")
def unlock_character(character_id: str, session: SessionDep, user: UserDep) -> CharacterRead:
    """Back to editing. The sheet files stay; locking again draws a new version."""
    character = get_character(session, user, character_id)
    not_starter(character)
    if character.status == "generating":
        raise _busy(character)
    character.status = "draft"
    return _save(session, character)


@router.post("/{character_id}/copy", status_code=201)
def copy_character(character_id: str, session: SessionDep, user: UserDep) -> CharacterRead:
    """Make it mine: copies a starter character into the kid's own cast as an editable draft.
    The copy counts toward their own characters (cast_full still applies)."""
    source = get_character(session, user, character_id)
    if not source.starter:
        raise invalid("Only starter characters can be copied. This one is already yours!")
    _room_in_cast(session, user)
    character = Character(user_id=user.id, name=source.name, role=source.role, kind=source.kind)
    _apply_spec(character, copy.deepcopy(source.spec))
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
