"""LLM_PROVIDER=meta: settings are checked at startup, and calls go out the way we expect."""

from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.providers.llm import LLMError
from app.providers.meta import MetaLLMProvider
from app.services import safety
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


def test_the_classifier_leaves_room_to_think() -> None:
    fake = FakeMeta()
    llm = provider(fake)
    safety.classify(llm, {"text": "A kind robot"})
    assert fake.calls[0]["max_tokens"] >= 1500


def test_half_a_reply_cut_off_at_the_limit_is_out_of_tokens_too() -> None:
    cut_off = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content='{"parts": {"ha'), finish_reason="length"
            )
        ],
        usage=None,
    )
    fake = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **_: cut_off))
    )
    llm = MetaLLMProvider(
        api_key="k", model="m", vision_model="v", base_url="http://x", client=fake
    )

    with pytest.raises(LLMError):
        llm.complete_json("system", "prompt", {"type": "object"}, schema_name="thing")

    assert llm.last_call is not None and llm.last_call["error"] == "OutOfTokens"


def test_a_long_call_can_have_its_own_timeout() -> None:
    fake = FakeMeta()
    fake.replies["thing"] = {"ok": True}
    provider(fake).complete_json(
        "system", "prompt", {"type": "object"}, schema_name="thing", timeout=60
    )
    assert fake.calls[0]["timeout"] == 60
