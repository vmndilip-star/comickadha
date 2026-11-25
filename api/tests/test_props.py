"""Props drawn as their own layer (Phase 8, step 1): the library, where props go in a panel, the
art, the planner's rule that every prop a bubble or caption names is drawn, and the panel API."""

import io
from dataclasses import replace
from typing import Any, get_args

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlmodel import Session

from app.avatar.spec import normalize
from app.models import Panel
from app.props import PROPS, STATES
from app.props.images import ensure_images, image_key, render_state
from app.schemas.common import PropId, PropState
from app.schemas.studio import PanelPlan, PlannedBubble
from app.services import compositor, stage, story_planner
from app.services.prop_rules import add_named_props, named_props, prop_problems
from app.services.storage import LocalStorage
from tests.conftest import IDS, app_state
from tests.test_long_comics import ctx
from tests.test_make_comic import comic, generate, planned_comic

KID = normalize({"body_type": "kid"})
BEAR = normalize({"body_type": "bear"})


def char(cid: str, position: str, pose: str = "front") -> dict[str, Any]:
    return {"id": cid, "sheet_version": 1, "pose": pose, "expression": "happy",
            "position": position, "scale": 1.0}  # fmt: skip


def say(text: str, speaker: str = "a") -> PlannedBubble:
    return PlannedBubble(speaker=speaker, type="talk", text=text)


# ---- the library ------------------------------------------------------------------------------


def test_the_api_names_every_prop_and_state_in_the_library() -> None:
    assert set(get_args(PropId)) == set(PROPS)
    assert set(get_args(PropState)) == set(STATES)


@pytest.mark.parametrize("prop_id", list(PROPS))
def test_every_prop_state_draws_a_transparent_picture(prop_id: str) -> None:
    for state_id, state in PROPS[prop_id].states.items():
        _x, _y, w, h = state.box
        png = render_state(prop_id, state_id, round(w * 2), round(h * 2))
        with Image.open(io.BytesIO(png)) as image:
            alpha = image.getchannel("A")
            assert image.size == (round(w * 2), round(h * 2))
            assert alpha.getpixel((0, 0)) == 0  # transparent around the drawing
            assert alpha.getbbox() is not None  # and something drawn


def test_each_picture_is_made_once_and_cached(tmp_path: Any) -> None:
    storage = LocalStorage(tmp_path)
    ensure_images(storage)
    key = image_key("scarecrow", "on_pole")
    first = storage.local_path(key)
    assert first is not None and first.is_file()
    stamp = first.stat().st_mtime_ns
    ensure_images(storage)
    assert first.stat().st_mtime_ns == stamp  # not drawn again


# ---- where props go ----------------------------------------------------------------------------


def test_a_held_torch_sits_in_the_hand_and_shines_toward_the_middle() -> None:
    chars = [char("a", "left", "point"), char("b", "right")]
    laid = stage.layout(
        chars, {"a": KID, "b": KID}, [{"id": "torch", "state": "held", "held_by": "a"}]
    )
    torch = laid.props[0]
    hand = stage.holding_hand(laid.characters[0])
    grip = (
        torch.box[0] + torch.origin[0] * torch.box[2],
        torch.box[1] + torch.origin[1] * torch.box[3],
    )
    assert grip == pytest.approx(hand, abs=1e-6)
    assert not torch.flip  # on the left, so its beam points right, at the others

    mirrored = stage.layout(
        list(reversed(chars)),
        {"a": KID, "b": KID},
        [{"id": "torch", "state": "held", "held_by": "b"}],
    ).props[0]
    assert mirrored.flip  # on the right: the beam points left


def test_a_worn_turban_sits_on_the_head() -> None:
    laid = stage.layout(
        [char("b", "center")], {"b": BEAR}, [{"id": "red_turban", "state": "worn", "held_by": "b"}]
    )
    turban, head = laid.props[0], laid.characters[0].head
    band = turban.box[1] + turban.origin[1] * turban.box[3]
    assert turban.box[0] + turban.box[2] / 2 == pytest.approx(head[0] + head[2] / 2, abs=1e-6)
    assert head[1] + head[3] * 0.3 < band < head[1] + head[3] * 0.6  # just above the eyes
    assert head[2] < turban.box[2] < head[2] * 1.3  # about as wide as the head


def test_a_worn_turban_stays_above_the_eyes() -> None:
    for spec in (KID, BEAR, normalize({"body_type": "grown_up"})):
        laid = stage.layout(
            [char("b", "center")],
            {"b": spec},
            [{"id": "red_turban", "state": "worn", "held_by": "b"}],
        )
        turban, (_hx, hy, _hw, hh) = laid.props[0], laid.characters[0].head
        width, height = round(turban.box[2] * 800), round(turban.box[3] * 600)  # a normal panel
        alpha = Image.open(
            io.BytesIO(render_state("red_turban", "worn", width, height))
        ).getchannel("A")
        lowest = turban.box[1] + (alpha.getbbox() or (0, 0, 0, height))[3] / height * turban.box[3]
        eye_tops = hy + hh * (1 - 4 + 36) / 66  # the eyes sit at y=1 in the 66-unit head box
        assert lowest < eye_tops, spec["body_type"]


def test_a_held_thing_never_hides_its_holders_face() -> None:
    # Thinking, one hand at the chin (panel 10 of the Sniffy test): the notebook goes in the other.
    laid = stage.layout(
        [char("a", "left", "thinking"), char("b", "right")],
        {"a": KID, "b": KID},
        [{"id": "notebook", "state": "held", "held_by": "a"}],
    )
    notebook, thinker = laid.props[0], laid.characters[0]
    assert stage._covered(notebook.box, stage._face(thinker)) <= stage.FACE_COVER
    grip = (
        notebook.box[0] + notebook.origin[0] * notebook.box[2],
        notebook.box[1] + notebook.origin[1] * notebook.box[3],
    )
    assert grip == pytest.approx(stage.holding_hand(thinker, 1), abs=1e-6)  # the other hand


def test_a_torch_beam_turns_down_off_the_others_heads() -> None:
    # A grown-up pointing a torch at a kid's head height (panel 12 of the Sniffy test).
    grown_up = normalize({"body_type": "grown_up"})
    laid = stage.layout(
        [char("k", "left"), char("g", "right", "point")],
        {"k": KID, "g": grown_up},
        [{"id": "torch", "state": "held", "held_by": "g"}],
    )
    torch, held = laid.props[0], PROPS["torch"].states["held"]
    frame = stage.frame_for(None)
    level = stage._prop_points(held.beam or (), held, torch.box, torch.origin, torch.flip, 0, frame)
    kid = laid.characters[0].head
    assert stage._beam_hits(level, kid, frame) > 0  # held level, the beam would light the face
    beam = stage._prop_points(
        held.beam or (), held, torch.box, torch.origin, torch.flip, torch.rotate, frame
    )
    assert stage._beam_hits(beam, kid, frame) == 0
    assert torch.flip and torch.rotate < 0  # pointing left, so turned anticlockwise: down
    hand = stage.holding_hand(laid.characters[1])
    grip = (torch.box[0] + torch.origin[0] * torch.box[2],
            torch.box[1] + torch.origin[1] * torch.box[3])  # fmt: skip
    assert grip == pytest.approx(hand, abs=1e-6)  # still in the hand: it turns about the grip


def test_a_turban_can_sit_on_the_scarecrow_even_when_it_has_fallen_over() -> None:
    props = [{"id": "scarecrow", "state": "on_pole", "position": "far_left"},
             {"id": "orange_turban", "state": "worn", "held_by": "scarecrow"}]  # fmt: skip
    laid = stage.layout([char("a", "right")], {"a": KID}, props)
    scarecrow, turban = laid.props
    assert scarecrow.box[0] < turban.box[0] < scarecrow.box[0] + scarecrow.box[2]
    assert turban.box[1] < scarecrow.box[1] + scarecrow.box[3] * 0.25  # up top, on its head
    assert laid.order[laid.order.index(("prop", 0)) + 1] == ("prop", 1)  # drawn just after it

    fallen = stage.layout(
        [char("a", "right")], {"a": KID}, [{**props[0], "state": "lying_down"}, props[1]]
    )
    assert fallen.props[1].rotate == -90


def test_things_on_the_ground_stand_on_the_ground_line_behind_everyone() -> None:
    props = [{"id": "scarecrow", "state": "on_pole", "position": "far_right"}]
    laid = stage.layout([char("a", "left"), char("b", "center")], {"a": KID, "b": KID}, props)
    scarecrow = laid.props[0]
    x, y, w, h = scarecrow.box
    assert x + scarecrow.origin[0] * w > 0.7  # over on the right
    assert x > 0 and x + w < 1  # nudged in: nothing cut off at the side
    assert y + scarecrow.origin[1] * h == pytest.approx(stage.GROUND, abs=0.002)
    assert laid.order[0] == ("prop", 0)  # behind the characters


def test_a_hugged_scarecrow_goes_behind_its_holder() -> None:
    laid = stage.layout(
        [char("b", "center")], {"b": BEAR}, [{"id": "scarecrow", "state": "held", "held_by": "b"}]
    )
    assert laid.order == [("prop", 0), ("character", 0)]


def test_props_whose_holder_is_missing_are_left_out() -> None:
    laid = stage.layout(
        [char("a", "left")], {"a": KID}, [{"id": "torch", "state": "held", "held_by": "zz"}]
    )
    assert laid.props == []


# ---- the art -----------------------------------------------------------------------------------


def test_props_are_drawn_into_the_art_and_the_same_inputs_give_the_same_png() -> None:
    chars = [char("a", "left"), char("b", "right")]
    specs = {"a": KID, "b": KID}
    plain = compositor.render_art(chars, specs, None, "#DDF0FC", [])
    assert (
        compositor.render_art(chars, specs, None, "#DDF0FC", [], []) == plain
    )  # no props: as before
    props = [{"id": "paw_prints", "state": "on_ground", "position": "center"}]
    with_prints = compositor.render_art(chars, specs, None, "#DDF0FC", [], props)
    assert with_prints == compositor.render_art(chars, specs, None, "#DDF0FC", [], props)
    assert with_prints[0] != plain[0]
    box = stage.layout(chars, specs, props).props[0].box
    with Image.open(io.BytesIO(with_prints[0])) as art, Image.open(io.BytesIO(plain[0])) as before:
        x0, y0 = round(box[0] * art.width), round(box[1] * art.height)
        x1, y1 = round((box[0] + box[2]) * art.width), round((box[1] + box[3]) * art.height)
        assert art.crop((x0, y0, x1, y1)).tobytes() != before.crop((x0, y0, x1, y1)).tobytes()


# ---- words and props agree -----------------------------------------------------------------------


def test_the_props_a_bubble_names() -> None:
    assert named_props("Shine the torch! The scarecrow moves!") == ["scarecrow", "torch"]
    assert named_props("Fallen scarecrow... and big round footprints nearby?") == [
        "scarecrow",
        "paw_prints",
    ]
    assert named_props("I tied a fresh orange turban today.") == ["orange_turban"]
    assert named_props("He wipes his hands on the turban.") == ["turban"]
    assert named_props("I will bring my notebook and the tiffin box!") == ["notebook", "tiffin"]
    assert named_props("Warm laddoos for brave friends!") == ["laddoos"]
    assert named_props("That smells sweet like jaggery!") == []  # not a prop
    assert named_props("Sniffy notes the clues.") == []  # "notes" isn't a notebook


def test_a_named_prop_that_isnt_drawn_is_a_problem() -> None:
    names = {p.id: p.name.lower() for p in PROPS.values()}
    problems = prop_problems(
        [say("Shine torch! The scarecrow moves!")], [{"id": "torch", "state": "held"}], names
    )
    assert len(problems) == 1 and "scarecrow" in problems[0]
    on_pole = [{"id": "scarecrow", "state": "on_pole", "position": "far_left"}]
    assert prop_problems([say("The scarecrow is back on its pole!")], on_pole, names) == []
    assert "empty pole" in prop_problems([say("The pole is empty!")], on_pole, names)[0]


def test_missing_props_are_added_where_they_fit() -> None:
    added = add_named_props([say("Let's pack the torch and the tiffin!", "b")], [], ["a", "b"])
    assert added == [{"id": "torch", "state": "held", "held_by": "b"},
                     {"id": "tiffin", "state": "held", "held_by": "b"}]  # fmt: skip
    prints = add_named_props([say("Look, paw prints!")], [], ["a"])
    assert prints == [{"id": "paw_prints", "state": "on_ground", "position": "center"}]
    empty = add_named_props(
        [say("The pole is empty!")],
        [{"id": "scarecrow", "state": "on_pole", "position": "far_left"}],
        ["a"],
    )
    assert {"id": "scarecrow", "state": "lying_down", "position": "far_left"} in empty
    assert any(p["id"] == "pole" for p in empty)


def test_the_words_say_who_holds_or_wears_a_prop() -> None:
    names = {"Sniffy": "s", "Barnaby": "b", "Leo": "l"}
    reveal = (
        "Sniffy's torch finds Barnaby hugging the scarecrow, the red turban crooked on his head"
    )
    assert add_named_props([say(reveal, "s")], [], ["s", "b"], names) == [
        {"id": "scarecrow", "state": "held", "held_by": "b"},
        {"id": "torch", "state": "held", "held_by": "s"},
        {"id": "red_turban", "state": "worn", "held_by": "b"},
    ]
    # Drawn in the wrong hands (or held when the words say worn): the words win.
    wrong = [
        {"id": "torch", "state": "held", "held_by": "b"},
        {"id": "red_turban", "state": "held", "held_by": "b"},
    ]
    fixed = add_named_props([say(reveal, "s")], wrong, ["s", "b"], names)
    assert {"id": "torch", "state": "held", "held_by": "s"} in fixed
    assert {"id": "red_turban", "state": "worn", "held_by": "b"} in fixed
    # The scarecrow wears a turban the words put on it.
    pole = {"id": "scarecrow", "state": "on_pole", "position": "far_left"}
    for text in (
        "Back on its pole with a new orange turban, the scarecrow smiles.",
        "Mr Hari wipes his hands on the scarecrow's orange turban.",
        "The scarecrow has an orange turban on its head.",
    ):
        worn = {"id": "orange_turban", "state": "worn", "held_by": "scarecrow"}
        assert worn in add_named_props([say(text, "s")], [dict(pole)], ["s", "l"], names), text
    # Held when the words say so, worn when they say that (a plain "turban" is the red one).
    held = add_named_props([say("Leo holds the turban.", "s")], [], ["s", "l"], names)
    assert held == [{"id": "red_turban", "state": "held", "held_by": "l"}]
    wearing = add_named_props([say("Leo is wearing an orange turban!")], [], ["s", "l"], names)
    assert wearing == [{"id": "orange_turban", "state": "worn", "held_by": "l"}]
    # Nothing says who: a drawn prop stays where it is.
    torch = [{"id": "torch", "state": "held", "held_by": "b"}]
    assert add_named_props([say("What a bright torch!", "s")], torch, ["s", "b"], names) == torch


# ---- the planner ----------------------------------------------------------------------------


def test_the_planner_check_asks_again_when_a_named_prop_is_missing() -> None:
    story = ctx(4)
    a, b = story.cast[0].id, story.cast[1].id
    bubble = {"speaker": a, "type": "talk", "text": "Pass me the torch!"}
    figures = [
        {"id": a, "pose": "front", "expression": "happy", "position": "left"},
        {"id": b, "pose": "front", "expression": "happy", "position": "right"},
    ]
    panel = {"scene_id": story.scenes[0].id, "beat": "They hunt", "characters": figures}
    raw: dict[str, Any] = {"panels": [{**panel, "bubbles": [bubble], "props": []}]}
    one = replace(story, panel_count=1, scenes=[story.scenes[0]])
    problems = story_planner.check_panels(PanelPlan.model_validate(raw), one)
    assert any("torch" in p for p in problems)
    raw["panels"][0]["props"] = [{"id": "torch", "state": "held", "position": "", "held_by": a}]
    problems = story_planner.check_panels(PanelPlan.model_validate(raw), one)
    assert not [p for p in problems if "torch" in p]


def test_metas_panel_schema_offers_the_prop_library() -> None:
    schema = story_planner.panels_schema(ctx(4))
    prop = schema["properties"]["panels"]["items"]["properties"]["props"]["items"]
    assert set(prop["properties"]["id"]["enum"]) == set(PROPS)
    assert (
        "" in prop["properties"]["held_by"]["enum"]
        and "scarecrow" in prop["properties"]["held_by"]["enum"]
    )


def test_the_offline_planner_draws_what_its_panels_name() -> None:
    story = ctx(8)
    story.scenes[0] = story_planner.SceneInfo(
        story.scenes[0].id, story.scenes[0].background_id, story.scenes[0].character_ids,
        "Mira finds a torch. The scarecrow stands in the field.",
    )  # fmt: skip
    plan = story_planner.offline_panels(story)
    names = {p.id: p.name.lower() for p in PROPS.values()}
    for panel in plan.panels:
        said = [say(panel.beat), *panel.bubbles]
        assert prop_problems(said, [p.saved() for p in panel.props], names) == [], panel.beat


# ---- the panel API ---------------------------------------------------------------------------


def test_a_kid_puts_props_in_a_panel_and_the_drawing_shows_them(client: TestClient) -> None:
    made = planned_comic(client, 4)
    generate(client, made["id"])
    panel = comic(client, made["id"])["panels"][0]
    holder = panel["characters"][0]["id"]
    before = panel["art_url"]
    props = [{"id": "torch", "state": "held", "held_by": holder},
             {"id": "scarecrow", "state": "on_pole", "position": "far_right"}]  # fmt: skip
    res = client.patch(f"/api/panels/{panel['id']}", json={"props": props})
    assert res.status_code == 200, res.json()
    saved = res.json()
    assert [{k: v for k, v in p.items() if v is not None} for p in saved["props"]] == props
    assert saved["art_url"] != before  # drawn again with the props
    layers = [layer for layer in saved["stage"]["layers"] if layer["kind"] == "prop"]
    assert {layer["id"] for layer in layers} == {"torch", "scarecrow"}
    for layer in layers:
        assert client.get(layer["image_url"]).status_code == 200


def test_a_prop_needs_its_holder_in_the_panel_and_a_place_to_be(client: TestClient) -> None:
    made = planned_comic(client, 4)
    panel = made["panels"][0]
    nobody = client.patch(
        f"/api/panels/{panel['id']}",
        json={"props": [{"id": "torch", "state": "held", "held_by": IDS["robo"]}]},
    )
    assert nobody.status_code == 422 and nobody.json()["field"] == "props"
    floating = client.patch(
        f"/api/panels/{panel['id']}", json={"props": [{"id": "torch", "state": "on_ground"}]}
    )
    assert floating.status_code == 422


def test_the_library_lists_every_prop_with_its_pictures(client: TestClient) -> None:
    library = client.get("/api/props").json()
    assert [p["id"] for p in library] == list(PROPS)
    scarecrow = next(p for p in library if p["id"] == "scarecrow")
    assert [s["id"] for s in scarecrow["states"]] == ["on_pole", "lying_down", "held"]
    assert client.get(scarecrow["states"][0]["image_url"]).status_code == 200


def test_planned_panels_pin_their_place_version_and_carry_props(client: TestClient) -> None:
    made = planned_comic(client, 4)
    versions = {b["id"]: b["version"] for b in made["backgrounds"]}
    with Session(app_state(client).engine) as session:
        for p in made["panels"]:
            row = session.get(Panel, p["id"])
            assert row is not None and row.place_version == versions[row.background_id]
    assert all(isinstance(p["props"], list) and p["stage"] for p in made["panels"])


def test_the_stage_key_is_the_one_the_web_app_builds() -> None:
    """web/src/lib/stage.test.ts checks the same string from the same panel."""
    from app.services.staging import stage_key

    characters = [{"id": "a", "position": "left"}, {"id": "b", "position": "far_right"}]
    props = [{"id": "torch", "state": "held", "held_by": "a"},
             {"id": "pole", "state": "standing", "position": "center"}]  # fmt: skip
    assert stage_key(characters, props, "wide") == (
        '[[["a","left"],["b","far_right"]],[["torch","held","","a"],["pole","standing","center",""]],'
        '"wide"]'
    )


def test_the_panel_prompt_asks_for_props_and_only_names_drawn_ones() -> None:
    from app.prompts import template

    text = template("planner_panels")
    assert "props: the story objects the panel shows, only from the prop library" in text
    assert "Only name an object in a bubble or caption if it is in that panel's props." in text
    assert "Props you can draw (id: states):" in story_planner.prop_lines()
