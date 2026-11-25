"""The prop library (GET /api/props): what the panel editor offers to put in a panel."""

from fastapi import APIRouter
from pydantic import BaseModel

from app.deps import StorageDep
from app.errors import ERROR_RESPONSES
from app.props import PROPS
from app.props.images import image_key
from app.schemas.common import PropId, PropState

router = APIRouter(prefix="/api/props", tags=["props"], responses=ERROR_RESPONSES)


class PropStateInfo(BaseModel):
    id: PropState
    label: str
    # Where it goes: on the ground at a spot, in someone's hand, or on someone's head.
    placement: str
    image_url: str


class PropInfo(BaseModel):
    id: PropId
    name: str
    states: list[PropStateInfo]
    default_state: PropState
    # Props it can sit on when worn (a turban on the scarecrow).
    worn_by_props: list[PropId]


@router.get("")
def list_props(storage: StorageDep) -> list[PropInfo]:
    return [
        PropInfo.model_validate(
            {
                "id": prop.id,
                "name": prop.name,
                "default_state": prop.default_state,
                "worn_by_props": list(prop.worn_by_props),
                "states": [
                    {
                        "id": state_id,
                        "label": state.label,
                        "placement": state.placement,
                        "image_url": storage.url(image_key(prop.id, state_id)),
                    }
                    for state_id, state in prop.states.items()
                ],
            }
        )
        for prop in PROPS.values()
    ]
