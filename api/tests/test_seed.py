from fastapi.testclient import TestClient
from sqlalchemy import func
from sqlmodel import Session, SQLModel, select

from app.models import Background, Character, Comic, Panel, Scene, User
from app.seed import seed
from app.starters import STARTERS
from tests.conftest import own_cast

MODELS: list[type[SQLModel]] = [User, Character, Background, Comic, Scene, Panel]


def counts(session: Session) -> dict[str, int]:
    return {m.__name__: session.exec(select(func.count()).select_from(m)).one() for m in MODELS}


# The demo kid and their 3 characters, plus the starter cast profile and its 12 characters.
SEEDED = {"User": 2, "Character": 15, "Background": 3, "Comic": 3, "Scene": 5, "Panel": 20}


def test_seed_is_idempotent(client: TestClient) -> None:
    state = client.app.state  # type: ignore[attr-defined]
    with Session(state.engine) as session:
        assert counts(session) == SEEDED

        assert seed(session, state.storage) is False
        assert seed(session, state.storage) is False

        assert counts(session) == SEEDED


def test_reset_restores_the_demo_data(client: TestClient) -> None:
    client.delete("/api/characters/" + own_cast(client)[2]["id"])
    client.post("/api/characters", json={"name": "Zara"})
    client.post("/api/comics", json={"title": "Extra"})

    state = client.app.state  # type: ignore[attr-defined]
    with Session(state.engine) as session:
        assert seed(session, state.storage, reset=True) is True
        assert counts(session) == SEEDED

    assert [c["name"] for c in own_cast(client)] == ["Mira", "Raju", "Robo-Tik"]
    starters = [c["name"] for c in client.get("/api/characters").json() if c["starter"]]
    assert starters == [s["name"] for s in STARTERS]  # the reset brings the starters back
