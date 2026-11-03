from fastapi import APIRouter
from sqlmodel import Session, col, select

from app.deps import SessionDep, UserDep
from app.errors import ERROR_RESPONSES, ApiError, not_found
from app.models import Character, User
from app.models.base import utcnow
from app.schemas.character import CharacterCreate, CharacterRead, CharacterSpec, CharacterUpdate
from app.schemas.common import MAX_CAST
from app.schemas.manifest import CharacterManifest

router = APIRouter(prefix="/api/characters", tags=["characters"], responses=ERROR_RESPONSES)

# One card colour per cast slot (sun, coral and sky tints from the boards).
SLOT_TINTS = ("#FFE9A8", "#FFD0C2", "#DDF0FC")


def active_characters(session: Session, user: User) -> list[Character]:
    stmt = (
        select(Character)
        .where(Character.user_id == user.id, col(Character.deleted_at).is_(None))
        .order_by(col(Character.created_at))
    )
    return list(session.exec(stmt))


def get_character(session: Session, user: User, character_id: str) -> Character:
    character = session.get(Character, character_id)
    if character is None or character.user_id != user.id or character.deleted_at is not None:
        raise not_found("character")
    return character


def to_read(character: Character) -> CharacterRead:
    return CharacterRead.model_validate(character, from_attributes=True)


def _save(session: Session, character: Character) -> CharacterRead:
    character.updated_at = utcnow()
    session.add(character)
    session.commit()
    session.refresh(character)
    return to_read(character)


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
    return to_read(get_character(session, user, character_id))


@router.patch("/{character_id}")
def update_character(
    character_id: str, body: CharacterUpdate, session: SessionDep, user: UserDep
) -> CharacterRead:
    character = get_character(session, user, character_id)
    if character.status in ("locked", "generating"):
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
    """Soft delete: frees the cast slot; comics that already use the character keep their data."""
    character = get_character(session, user, character_id)
    character.deleted_at = utcnow()
    _save(session, character)


@router.post("/{character_id}/lock")
def lock_character(character_id: str, session: SessionDep, user: UserDep) -> CharacterRead:
    """Phase 2 only flips the status. Phase 3 returns 202 {job_id} and generates the sheets."""
    character = get_character(session, user, character_id)
    character.status = "locked"
    return _save(session, character)


@router.post("/{character_id}/unlock")
def unlock_character(character_id: str, session: SessionDep, user: UserDep) -> CharacterRead:
    character = get_character(session, user, character_id)
    character.status = "draft"
    return _save(session, character)


@router.get("/{character_id}/manifest")
def read_manifest(character_id: str, session: SessionDep, user: UserDep) -> CharacterManifest:
    character = get_character(session, user, character_id)
    if character.manifest is None:
        raise ApiError(
            404,
            "no_manifest",
            f"{character.name} doesn't have a character sheet yet. "
            f"Lock {character.name} to make one.",
        )
    return CharacterManifest.model_validate(character.manifest)
