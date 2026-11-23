"""Phase 7 A3 and A5: thinking characters only think, catchphrases once, varied line openings, in
check_panels (sent back in the retry), the planner prompt and the offline planner."""

import pytest

from app.prompts import render
from app.schemas.studio import PanelPlan, PlannedBubble, PlannedCharacter, PlannedPanel
from app.services.story_planner import (
    CastMember,
    Place,
    SceneInfo,
    StoryContext,
    check_panels,
    dialogue_problems,
    offline_panels,
    opening,
)

AVA = CastMember("ava", "Ava", 1, "Let's go, go, go!", ("brave",))
BO = CastMember("bo", "Bo", 1, "Beep boop!", ("clever",))


def ctx(panel_count: int = 4, synopsis: str = "Ava and Bo look for a clue.") -> StoryContext:
    scenes = [
        SceneInfo(
            "s1", "park", ("ava", "bo"), "Ava and Bo arrive at the park and wonder what to do."
        ),
        SceneInfo("s2", "park", ("ava", "bo"), "They find a clue, think hard and celebrate."),
    ]
    return StoryContext(
        "Clue", synopsis, "adventure", panel_count, [AVA, BO], [Place("park", "Park")], scenes
    )


def panel(
    *lines: tuple[str, str, str], pose: dict[str, str] | None = None, expression: str = "happy"
) -> PlannedPanel:
    """A panel with Ava (left) and Bo (right) and these (speaker, type, text) bubbles."""
    pose = pose or {}
    return PlannedPanel(
        scene_id="s1",
        beat="Something happens",
        characters=[
            PlannedCharacter(
                id="ava", pose=pose.get("ava", "front"), expression=expression, position="left"
            ),
            PlannedCharacter(
                id="bo", pose=pose.get("bo", "front"), expression=expression, position="right"
            ),
        ],
        bubbles=[PlannedBubble(speaker=s, type=t, text=x) for s, t, x in lines],
    )


def plan(*panels: PlannedPanel) -> PanelPlan:
    filler = [panel(("narrator", "narrator", f"Later, part {i}.")) for i in range(4 - len(panels))]
    return PanelPlan(panels=[*panels, *filler])


# ---- A3: the thinking pose --------------------------------------------------------------------


@pytest.mark.parametrize("kind", ["talk", "shout"])
def test_a_thinking_character_cannot_talk_or_shout(kind: str) -> None:
    problems = dialogue_problems(
        plan(panel(("ava", kind, "Hmm."), pose={"ava": "thinking"})), ctx()
    )

    assert any("Ava is in the thinking pose" in p and "think bubble" in p for p in problems)


def test_a_thinking_character_may_think_or_say_nothing() -> None:
    thinks = panel(("ava", "think", "Hmm, where is it?"), pose={"ava": "thinking"})
    quiet = panel(("bo", "talk", "Over here!"), pose={"ava": "thinking"})

    assert dialogue_problems(plan(thinks, quiet), ctx()) == []


def test_check_panels_sends_the_rules_back_in_the_retry() -> None:
    bad = plan(panel(("ava", "talk", "Hmm."), pose={"ava": "thinking"}))

    assert any("thinking pose" in p for p in check_panels(bad, ctx()))


# ---- A5: catchphrases, openings, reactions ----------------------------------------------------


def test_a_catchphrase_twice_in_a_comic_is_a_problem() -> None:
    twice = plan(
        panel(("ava", "talk", "Let's go, go, go!")), panel(("ava", "shout", "LET'S GO GO GO!"))
    )

    problems = dialogue_problems(twice, ctx())

    assert any("Ava's catchphrase" in p and "at most once" in p for p in problems)
    once = plan(panel(("ava", "talk", "Let's go, go, go!")), panel(("ava", "talk", "Follow me!")))
    assert dialogue_problems(once, ctx()) == []


def test_two_lines_in_a_row_starting_alike_is_a_problem() -> None:
    robo = plan(
        panel(("bo", "talk", "Beep boop, hello!")), panel(("bo", "talk", "Beep boop, a clue!"))
    )

    problems = dialogue_problems(robo, ctx())

    assert any("Bo's line starts like their last one" in p and "beep boop" in p for p in problems)


def test_an_opening_at_most_twice_and_never_in_a_row() -> None:
    lines = ["Look here!", "Wow, a clue!", "Look there!", "Nice work!"]
    twice_apart = plan(*[panel(("ava", "talk", t)) for t in lines])
    assert dialogue_problems(twice_apart, ctx()) == []  # "look here" / "look there" differ anyway

    three = PanelPlan(
        panels=[
            panel(("ava", "talk", t))
            for t in ["Look at this!", "Wow!", "Look at that!", "Yes!", "Look at me!", "Go!"]
        ]
    )
    problems = dialogue_problems(three, ctx(6))
    assert any("Ava starts 3 lines with 'look at'" in p for p in problems)


def test_everyone_celebrating_together_is_fine() -> None:
    party = plan(
        panel(
            ("ava", "shout", "Hooray!"),
            ("bo", "talk", "We did it!"),
            pose={"ava": "celebrate", "bo": "celebrate"},
            expression="laughing",
        )
    )

    assert dialogue_problems(party, ctx()) == []


def test_openings_ignore_case_and_punctuation() -> None:
    assert opening("Beep-boop! Hello") == opening("beep boop, hi") == "beep boop"


# ---- the prompt and the offline planner -------------------------------------------------------


def test_the_planner_prompt_has_the_rules() -> None:
    text = render("planner_panels", panel_count=6)

    assert "thinking pose has a think bubble or no bubble" in text
    assert "catchphrase at most once in the whole comic" in text
    assert "Catchphrases are optional" in text and "Never force one in" in text  # live test 2
    assert "pose and face fit what they say and feel" in text  # advice, not a check (live test 2)
    assert "same first two words at most twice" in text
    assert "different reactions" in text


SYNOPSES = [
    "Ava and Bo look for a clue. They find footprints, think of a plan and find the treasure.",
    "Bo wonders where the cake went. Ava thinks. Bo thinks harder. They think, then find it.",
    "Ava finds a clue. Bo finds a clue. They find more clues, find a door and find a party inside.",
]


@pytest.mark.parametrize("count", [4, 6, 8])
@pytest.mark.parametrize("synopsis", SYNOPSES)
def test_offline_plans_keep_every_dialogue_rule(count: int, synopsis: str) -> None:
    c = ctx(count, synopsis)

    plan_ = offline_panels(c)

    assert len(plan_.panels) == count
    assert check_panels(plan_, c) == []
