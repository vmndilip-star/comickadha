"""The builder helper (/api/builder): offline, and on Meta's API through a fake OpenAI client."""

from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, col, select

from app.avatar import spec as avatar_spec
from app.avatar.catalog import load_catalog
from app.models import ModerationLog
from app.services.builder_helper import META_LABEL, OFFLINE_LABEL, RESTING
from app.services.helper_meta import colour_ids
from app.services.helper_offline import TRAITS
from tests.conftest import app_state
from tests.fakes import (
    TEXT_MODEL,
    schema_of,
    server_error,
    suggestion,
    timeout_error,
    use_meta,
    user_text,
)

CAT = load_catalog()
KID = avatar_spec.validate({"body_type": "kid"})
WISH = "a brave girl with curly red hair, a purple hoodie, a cape and dragon wings"


def describe(client: TestClient, text: str, spec: dict[str, Any] = KID) -> Any:
    return client.post("/api/builder/describe", json={"text": text, "spec": spec})


def logs(client: TestClient) -> list[ModerationLog]:
    with Session(app_state(client).engine) as session:
        return list(session.exec(select(ModerationLog).order_by(col(ModerationLog.created_at))))


def builder_logs(client: TestClient) -> list[tuple[str, str, list[str]]]:
    return [
        (log.target, log.verdict, log.categories)
        for log in logs(client)
        if log.target.startswith("builder:")
    ]


def assert_drawable(spec: dict[str, Any]) -> None:
    assert avatar_spec.validate(spec) == spec  # complete, and every choice is in the catalog


# ---- offline helper (LLM_PROVIDER=mock) ------------------------------------------------------


def test_info_reports_the_offline_helper(client: TestClient) -> None:
    info = client.get("/api/builder/info").json()

    assert info == {
        "source": "mock",
        "label": OFFLINE_LABEL,
        "drawing_needs_consent": False,
        "drawing_consent": False,
        "last_call": None,  # offline: no Meta calls to report
    }


def test_offline_describe_picks_real_parts_and_notes_unmatched_wishes(client: TestClient) -> None:
    res = describe(client, WISH)

    assert res.status_code == 200, res.json()
    out = res.json()
    assert_drawable(out["spec"])
    assert out["spec"]["parts"]["hair"] == "curly"
    assert out["spec"]["parts"]["top"] == "hoodie"
    assert out["spec"]["colors"]["top"] == "#7A4FC9"  # purple
    assert "cape" in out["spec"]["extras"]
    assert "brave" in out["spec"]["personality"]["traits"]
    assert out["unmatched"] == ["dragon wings"]
    assert "dragon wings" in out["reply"]
    assert {"hair", "top", "extras"} <= set(out["changed"])
    assert (out["source"], out["fallback"], out["label"]) == ("mock", False, OFFLINE_LABEL)


def test_offline_describe_with_nothing_it_knows_changes_nothing(client: TestClient) -> None:
    out = describe(client, "something mysterious").json()

    assert out["spec"]["parts"] == KID["parts"] and out["changed"] == []
    assert out["unmatched"] == ["something mysterious"]


@pytest.mark.parametrize("body_type", [None, "kid", "robot", "cat"])
def test_offline_surprise_is_drawable(client: TestClient, body_type: str | None) -> None:
    for _ in range(5):
        res = client.post("/api/builder/surprise", json={"body_type": body_type})

        assert res.status_code == 200, res.json()
        out = res.json()
        assert_drawable(out["spec"])
        if body_type:
            assert out["spec"]["body_type"] == body_type
        assert len(out["name_ideas"]) == 3 and out["reply"].startswith("Surprise!")


def test_offline_surprise_keeps_the_role(client: TestClient) -> None:
    hero = KID | {"role": "hero"}

    out = client.post("/api/builder/surprise", json={"spec": hero}).json()

    assert out["spec"]["role"] == "hero"


def test_offline_ideas(client: TestClient) -> None:
    res = client.post("/api/builder/ideas", json={"spec": KID, "name": "Zara"})

    assert res.status_code == 200
    out = res.json()
    assert 1 <= len(out["name_ideas"]) <= 3 and "Zara" not in out["name_ideas"]
    assert out["traits"] and set(out["traits"]) <= set(TRAITS)
    assert out["catchphrase"]
    assert (out["source"], out["fallback"]) == ("mock", False)


def test_unsafe_words_are_refused_and_logged(client: TestClient) -> None:
    res = describe(client, "a pirate with a gun")

    assert res.status_code == 422
    assert res.json()["code"] == "unsafe"
    assert builder_logs(client) == [("builder:describe", "block", ["weapons"])]


def test_an_unsafe_name_for_ideas_is_refused(client: TestClient) -> None:
    res = client.post("/api/builder/ideas", json={"spec": KID, "name": "Beer Boy"})

    assert res.status_code == 422 and res.json()["code"] == "unsafe"


def test_a_bad_spec_in_a_request_is_422(client: TestClient) -> None:
    res = describe(client, "a cape", KID | {"outfit": "old style"})

    assert res.status_code == 422 and res.json()["code"] == "invalid"


# ---- Meta's API (LLM_PROVIDER=meta) through a fake client -----------------------------------


def test_info_reports_meta_and_drawing_consent(client: TestClient) -> None:
    use_meta(client)

    info = client.get("/api/builder/info").json()

    assert (info["source"], info["label"]) == ("meta", META_LABEL)
    assert info["drawing_needs_consent"] is True and info["drawing_consent"] is False


def test_meta_describe_returns_valid_parts_and_keeps_unmatched_wishes(client: TestClient) -> None:
    fake = use_meta(client)
    fake.replies["avatar_suggestion"] = suggestion(
        KID,
        parts={"hair": "curly", "top": "hoodie"},
        colors={"hair": "ginger", "top": "purple"},
        extras=["cape"],
        traits=["brave"],
        unmatched=["dragon wings"],
        reply="We don't have dragon wings yet, so I gave you a cape!",
    )

    out = describe(client, WISH).json()

    assert_drawable(out["spec"])
    assert out["spec"]["parts"]["hair"] == "curly"
    assert out["spec"]["colors"]["hair"] == "#C8552B"  # palette id -> hex
    assert out["spec"]["colors"]["top"] == "#7A4FC9"
    assert out["spec"]["extras"] == ["cape"]
    assert out["unmatched"] == ["dragon wings"]
    assert out["name_ideas"] == ["Nova", "Pip", "Zuri"]
    assert (out["source"], out["fallback"], out["label"]) == ("meta", False, META_LABEL)
    [call] = fake.calls_for("avatar_suggestion")
    assert call["model"] == TEXT_MODEL
    assert WISH in user_text(call)


def test_meta_parts_that_do_not_fit_are_swapped_for_defaults(client: TestClient) -> None:
    fake = use_meta(client)
    robot = avatar_spec.validate({"body_type": "robot"})
    fake.replies["avatar_suggestion"] = suggestion(
        robot, parts={"hair": "afro", "nose": "pointy"}, extras=["freckles"]
    )

    out = describe(client, "a robot with an afro", robot).json()

    assert_drawable(out["spec"])
    assert "hair" not in out["spec"]["parts"] and out["spec"]["extras"] == []


def test_the_schema_enums_come_from_the_catalog(client: TestClient) -> None:
    fake = use_meta(client)
    fake.replies["avatar_suggestion"] = suggestion(KID)

    describe(client, "a kid in a cap")

    schema = schema_of(fake.calls_for("avatar_suggestion")[0])
    assert schema["strict"] is True
    props = schema["schema"]["properties"]
    assert props["body_type"]["enum"] == list(CAT["body_types"])
    assert set(props["parts"]["properties"]) == set(CAT["categories"])
    for category, info in CAT["categories"].items():
        assert props["parts"]["properties"][category]["enum"] == list(info["options"])
    for slot in CAT["color_slots"]:
        assert props["colors"]["properties"][slot]["enum"] == colour_ids(slot, CAT)
    assert props["colors"]["properties"]["top"]["enum"] == [
        e["id"] for e in CAT["palettes"]["cloth"]
    ]
    assert props["extras"]["items"]["enum"] == list(CAT["extras"])
    assert props["traits"]["items"]["enum"] == TRAITS
    assert set(schema["schema"]["required"]) == set(props)


def test_meta_surprise_and_ideas_return_valid_output(client: TestClient) -> None:
    fake = use_meta(client)
    cat = avatar_spec.validate({"body_type": "cat"})
    fake.replies["avatar_suggestion"] = suggestion(
        cat, body_type="cat", colors={"skin": "grey", "card": "mint_tint"}, extras=["wand"]
    )
    fake.replies["character_ideas"] = {
        "name_ideas": ["Whisk", "Pebble", "Mochi"],
        "traits": ["curious", "kind", "sneaky"],
        "catchphrase": "Purr-fect!",
        "reply": "How about Whisk?",
    }

    surprise = client.post("/api/builder/surprise", json={"body_type": "cat"}).json()
    ideas = client.post("/api/builder/ideas", json={"spec": cat, "name": ""}).json()

    assert_drawable(surprise["spec"])
    assert surprise["spec"]["body_type"] == "cat" and surprise["spec"]["extras"] == ["wand"]
    assert surprise["spec"]["colors"]["skin"] == "#A9A9AE"
    assert surprise["source"] == "meta"
    assert ideas["name_ideas"] == ["Whisk", "Pebble", "Mochi"]
    assert ideas["traits"] == ["curious", "kind"]  # "sneaky" isn't a trait
    assert (ideas["catchphrase"], ideas["source"], ideas["label"]) == (
        "Purr-fect!",
        "meta",
        META_LABEL,
    )


def test_a_malformed_meta_reply_is_retried_once(client: TestClient) -> None:
    fake = use_meta(client)
    fake.replies["avatar_suggestion"] = [{"parts": "curly"}, suggestion(KID, extras=["cape"])]

    out = describe(client, "a cape").json()

    assert len(fake.calls_for("avatar_suggestion")) == 2
    assert (out["source"], out["spec"]["extras"]) == ("meta", ["cape"])


def test_two_malformed_meta_replies_fall_back_to_the_offline_helper(client: TestClient) -> None:
    fake = use_meta(client)
    fake.replies["avatar_suggestion"] = [{"parts": "curly"}, {"extras": "cape"}]

    out = describe(client, "a cape").json()

    assert len(fake.calls_for("avatar_suggestion")) == 2
    assert (out["source"], out["fallback"], out["label"]) == ("mock", True, OFFLINE_LABEL)
    assert "cape" in out["spec"]["extras"]


def test_a_reply_that_is_not_json_counts_as_meta_being_down(client: TestClient) -> None:
    fake = use_meta(client)
    fake.replies["avatar_suggestion"] = "not json at all"

    out = describe(client, "a cape").json()

    assert len(fake.calls_for("avatar_suggestion")) == 1
    assert (out["source"], out["fallback"]) == ("mock", True)


# ---- safety on the way in and on the way out --------------------------------------------------


def test_word_list_runs_before_any_model_sees_the_words(client: TestClient) -> None:
    fake = use_meta(client)

    res = describe(client, "a pirate with a gun")

    assert res.status_code == 422 and res.json()["code"] == "unsafe"
    assert fake.calls == []


def test_the_classifier_can_refuse_the_kids_words(client: TestClient) -> None:
    fake = use_meta(client)
    fake.replies["safety_verdicts"] = {"verdicts": [{"safe": False, "categories": ["bullying"]}]}

    res = describe(client, "a kid who is mean to everyone")

    assert res.status_code == 422 and res.json()["code"] == "unsafe"
    assert fake.calls_for("avatar_suggestion") == []
    assert builder_logs(client) == [("builder:describe", "block", ["bullying"])]


def test_unsafe_model_output_is_never_shown(client: TestClient) -> None:
    fake = use_meta(client)
    fake.replies["avatar_suggestion"] = suggestion(KID, catchphrase="Time for a beer!")

    out = describe(client, "a cheerful kid").json()

    assert (out["source"], out["fallback"]) == ("mock", True)
    assert "beer" not in str(out).lower()
    assert ("builder:reply", "block", ["drugs"]) in builder_logs(client)


def test_output_the_classifier_flags_is_never_shown(client: TestClient) -> None:
    fake = use_meta(client)
    fake.replies["avatar_suggestion"] = suggestion(KID, reply="You look like my neighbour Bob!")
    safe_input = {"verdicts": [{"safe": True, "categories": []}]}
    flagged = {"verdicts": [{"safe": False, "categories": ["personal_info"]}] * 3}
    fake.replies["safety_verdicts"] = [safe_input, flagged]

    out = describe(client, "a cheerful kid").json()

    assert (out["source"], out["fallback"]) == ("mock", True)
    assert "neighbour" not in out["reply"]
    assert ("builder:reply", "block", ["personal_info"]) in builder_logs(client)


@pytest.mark.parametrize(
    "broken",
    [server_error(), timeout_error(), {"verdicts": []}, {"nope": True}],
    ids=["5xx", "timeout", "wrong-count", "wrong-shape"],
)
def test_safety_fails_closed_when_the_classifier_cannot_answer(
    client: TestClient, broken: Any
) -> None:
    """Unchecked words never reach the model: the offline helper answers instead."""
    fake = use_meta(client)
    fake.replies["safety_verdicts"] = broken
    fake.replies["avatar_suggestion"] = suggestion(KID)

    out = describe(client, "a kid with a cape").json()

    assert fake.calls_for("avatar_suggestion") == []
    assert (out["source"], out["fallback"], out["label"]) == ("mock", True, OFFLINE_LABEL)
    assert out["reply"].startswith(RESTING)
    assert ("builder:describe", "block", ["unavailable"]) in builder_logs(client)


def test_unchecked_model_output_is_not_used(client: TestClient) -> None:
    fake = use_meta(client)
    fake.replies["avatar_suggestion"] = suggestion(KID, extras=["cape"])
    safe_input = {"verdicts": [{"safe": True, "categories": []}]}
    fake.replies["safety_verdicts"] = [safe_input, server_error()]

    out = describe(client, "a kid").json()

    assert (out["source"], out["fallback"]) == ("mock", True)
    assert ("builder:reply", "block", ["unavailable"]) in builder_logs(client)


# ---- Meta down: the offline helper answers, labelled as such --------------------------------


@pytest.mark.parametrize("error", [timeout_error(), server_error()], ids=["timeout", "5xx"])
def test_meta_timeout_or_5xx_falls_back_to_the_offline_helper(
    client: TestClient, error: Exception
) -> None:
    fake = use_meta(client)
    fake.replies["avatar_suggestion"] = error

    out = describe(client, WISH).json()

    assert len(fake.calls_for("avatar_suggestion")) == 1  # an outage isn't retried here
    assert (out["source"], out["fallback"], out["label"]) == ("mock", True, OFFLINE_LABEL)
    assert out["reply"].startswith(RESTING)
    assert_drawable(out["spec"])
    assert out["spec"]["parts"]["hair"] == "curly"  # the offline helper still did its job


@pytest.mark.parametrize("error", [timeout_error(), server_error()], ids=["timeout", "5xx"])
def test_surprise_and_ideas_fall_back_too(client: TestClient, error: Exception) -> None:
    fake = use_meta(client)
    fake.replies["avatar_suggestion"] = error
    fake.replies["character_ideas"] = error

    surprise = client.post("/api/builder/surprise", json={}).json()
    ideas = client.post("/api/builder/ideas", json={"spec": KID}).json()

    for out in (surprise, ideas):
        assert (out["source"], out["fallback"], out["label"]) == ("mock", True, OFFLINE_LABEL)
        assert out["reply"].startswith(RESTING)
    assert_drawable(surprise["spec"])


def test_without_meta_the_offline_helper_is_not_a_fallback(client: TestClient) -> None:
    assert app_state(client).llm is None

    out = describe(client, WISH).json()

    assert out["fallback"] is False and not out["reply"].startswith(RESTING)
