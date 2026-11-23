"""Phase 7 A2: `python -m app.seed --paint` repaints the demo places with the real image model,
through the normal place checks; it refuses the mock. Fake Meta and Muse clients, no real calls."""

from pathlib import Path

import pytest
from sqlmodel import Session, col, select

from app.config import Settings
from app.db import make_engine
from app.models import Background, ModerationLog
from app.providers.meta import MetaLLMProvider
from app.seed import GARDEN, KITCHEN, SPACE, paint_places
from app.services.backup import backups_dir
from tests.fakes import (
    TEXT_MODEL,
    VISION_MODEL,
    FakeImages,
    FakeMeta,
    flag,
    muse,
    picture,
    user_text,
)


def meta(fake: FakeMeta) -> MetaLLMProvider:
    return MetaLLMProvider(
        api_key="k",
        model=TEXT_MODEL,
        vision_model=VISION_MODEL,
        base_url="http://meta.invalid/v1",
        client=fake,
    )


def muse_settings(settings: Settings) -> Settings:
    return settings.model_copy(update={"llm_provider": "meta", "image_provider": "muse"})


def test_it_refuses_the_mock(settings: Settings) -> None:
    with pytest.raises(SystemExit, match="IMAGE_PROVIDER=muse"):
        paint_places(settings)


def test_it_repaints_the_three_demo_places_through_the_checks(settings: Settings) -> None:
    fake, images = FakeMeta(), FakeImages()

    report = paint_places(muse_settings(settings), llm=meta(fake), provider=muse(images))

    assert len(report) == 3 and all("painted (version 2)" in line for line in report)
    assert len(images.calls) == 3
    checked = " ".join(user_text(c) for c in fake.calls_for("safety_verdicts"))
    assert "Grandma's kitchen" in checked and "School garden" in checked  # words first
    assert len(fake.calls_for("image_safety")) == 3  # every picture checked
    with Session(make_engine(settings.resolved_database_url)) as session:
        for place_id in (KITCHEN, GARDEN, SPACE):
            bg = session.get(Background, place_id)
            assert bg is not None and bg.version == 2 and "/v2/" in (bg.image_key or "")
    assert any(p.name.endswith("before-paint") for p in backups_dir(settings.storage_dir).iterdir())


def test_a_blocked_picture_is_painted_again_and_unsafe_words_send_nothing(
    settings: Settings,
) -> None:
    fake, images = FakeMeta(), FakeImages()
    fake.replies["safety_verdicts"] = flag("cheesy yellow moon")  # Outer space's description
    fake.replies["image_safety"] = [picture(has_text_or_logos=True), picture()]

    report = paint_places(muse_settings(settings), llm=meta(fake), provider=muse(images))

    assert any("Outer space" in line and "nothing sent" in line for line in report)
    assert sum("painted" in line for line in report) == 2
    assert len(images.calls) == 3  # one retry after the blocked picture, none for Outer space
    with Session(make_engine(settings.resolved_database_url)) as session:
        space = session.get(Background, SPACE)
        assert space is not None and space.version == 1  # unchanged
        verdicts = session.exec(
            select(ModerationLog)
            .where(ModerationLog.kind == "image")
            .order_by(col(ModerationLog.created_at))
        )
        assert [v.verdict for v in verdicts] == ["block", "allow", "allow"]


def test_the_report_says_when_the_checker_is_down(settings: Settings, tmp_path: Path) -> None:
    from tests.fakes import server_error

    fake = FakeMeta()
    fake.replies["safety_verdicts"] = server_error()
    images = FakeImages()

    report = paint_places(muse_settings(settings), llm=meta(fake), provider=muse(images))

    assert all("didn't answer, nothing sent" in line for line in report)
    assert images.calls == []
