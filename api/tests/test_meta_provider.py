"""LLM_PROVIDER=meta: settings are checked at startup, and calls go out the way we expect."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.providers.llm import LLMError
from app.providers.meta import MetaLLMProvider
from tests.conftest import make_settings
from tests.fakes import FakeMeta, server_error


def meta_settings(tmp_path: Path, **meta: str) -> Settings:
    values = {"meta_api_key": "test-key", "meta_model": "muse-test"} | meta
    return make_settings(tmp_path / "storage", llm_provider="meta", **values)


@pytest.mark.parametrize(
    "meta",
    [
        {"meta_model": "muse-spark-1.3-contributor"},
        {"meta_vision_model": "muse-vision-contributor"},
    ],
    ids=["text-model", "vision-model"],
)
def test_startup_refuses_contributor_models(tmp_path: Path, meta: dict[str, str]) -> None:
    app = create_app(meta_settings(tmp_path, **meta))

    with pytest.raises(ValueError, match="contributor"), TestClient(app):
        pass
    assert not (tmp_path / "storage").exists()  # refused before anything was created


@pytest.mark.parametrize(
    ("meta", "says"),
    [({"meta_api_key": ""}, "META_API_KEY"), ({"meta_model": ""}, "META_MODEL")],
)
def test_startup_needs_a_key_and_a_model(tmp_path: Path, meta: dict[str, str], says: str) -> None:
    app = create_app(meta_settings(tmp_path, **meta))

    with pytest.raises(ValueError, match=says), TestClient(app):
        pass


def test_the_vision_model_defaults_to_the_text_model(tmp_path: Path) -> None:
    with TestClient(create_app(meta_settings(tmp_path))) as client:
        llm = client.app.state.llm  # type: ignore[attr-defined]
        health = client.get("/api/health").json()

    assert isinstance(llm, MetaLLMProvider)
    assert llm.vision_model == llm.model == "muse-test"
    assert health["llm_provider"] == "meta"


def provider(fake: FakeMeta) -> MetaLLMProvider:
    return MetaLLMProvider(
        api_key="test-key", model="m", vision_model="v", base_url="http://x", client=fake
    )


def test_structured_output_is_requested_with_a_strict_schema() -> None:
    fake = FakeMeta()
    fake.replies["thing"] = {"ok": True}
    schema = {"type": "object", "properties": {"ok": {"type": "boolean"}}}

    assert provider(fake).complete_json("sys", "hi", schema, schema_name="thing") == {"ok": True}

    [call] = fake.calls
    assert call["model"] == "m"
    assert call["response_format"] == {
        "type": "json_schema",
        "json_schema": {"name": "thing", "schema": schema, "strict": True},
    }
    assert call["messages"] == [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "hi"},
    ]


def test_errors_and_unusable_replies_become_llm_errors() -> None:
    fake = FakeMeta()
    llm = provider(fake)
    for reply in (server_error(), "not json", "[1, 2]", ""):
        fake.replies["thing"] = reply
        with pytest.raises(LLMError):
            llm.complete_json("sys", "hi", {}, schema_name="thing")
