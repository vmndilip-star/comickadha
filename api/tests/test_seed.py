from fastapi.testclient import TestClient
from sqlalchemy import func
from sqlmodel import Session, SQLModel, select

from app.models import Background, Character, Comic, Panel, Scene, User
from app.seed import seed

MODELS: list[type[SQLModel]] = [User, Character, Background, Comic, Scene, Panel]


def counts(session: Session) -> dict[str, int]:
    return {m.__name__: session.exec(select(func.count()).select_from(m)).one() for m in MODELS}


SEEDED = {"User": 1, "Character": 3, "Background": 3, "Comic": 3, "Scene": 5, "Panel": 20}


def test_seed_is_idempotent(client: TestClient) -> None:
    state = client.app.state  # type: ignore[attr-defined]
    with Session(state.engine) as session:
        assert counts(session) == SEEDED

        assert seed(session, state.storage) is False
        assert seed(session, state.storage) is False

        assert counts(session) == SEEDED


def test_reset_restores_the_demo_data(client: TestClient) -> None:
    client.delete("/api/characters/" + client.get("/api/characters").json()[2]["id"])
    client.post("/api/characters", json={"name": "Zara"})
    client.post("/api/comics", json={"title": "Extra"})

    state = client.app.state  # type: ignore[attr-defined]
    with Session(state.engine) as session:
        assert seed(session, state.storage, reset=True) is True
        assert counts(session) == SEEDED

    names = [c["name"] for c in client.get("/api/characters").json()]
    assert names == ["Mira", "Raju", "Robo-Tik"]
