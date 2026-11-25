"""The compositor, stage geometry, lettering and bubble layout (no HTTP)."""

import io
from typing import Any

import pytest
from PIL import Image

from app.avatar.spec import normalize
from app.services import bubbles, compositor, lettering, stage

KID = normalize({"body_type": "kid"})
ROBOT = normalize({"body_type": "robot"})


def char(cid: str, position: str, pose: str = "front", expression: str = "happy") -> dict[str, Any]:
    return {"id": cid, "sheet_version": 1, "pose": pose, "expression": expression,
            "position": position, "scale": 1.0}  # fmt: skip


def png_pixel(png: bytes, xy: tuple[int, int]) -> tuple[int, ...]:
    with Image.open(io.BytesIO(png)) as image:
        return tuple(image.convert("RGB").getpixel(xy))  # type: ignore[arg-type]


# ---- art.png -----------------------------------------------------------------------------


def test_the_same_inputs_make_a_byte_identical_png() -> None:
    chars = [char("a", "left"), char("b", "right", "wave", "laughing")]
    specs = {"a": KID, "b": ROBOT}
    first = compositor.render_art(chars, specs, None, "#DDF0FC", [])
    second = compositor.render_art(chars, specs, None, "#DDF0FC", [])
    assert first == second
    with Image.open(io.BytesIO(first[0])) as art, Image.open(io.BytesIO(first[1])) as thumb:
        assert art.size == (1600, 1200) and thumb.size == compositor.THUMB


def test_a_missing_place_image_falls_back_to_the_tint() -> None:
    art, _ = compositor.render_art([char("a", "center")], {"a": KID}, None, "#123456", [])
    assert png_pixel(art, (4, 4)) == (0x12, 0x34, 0x56)


def test_a_place_image_is_cover_cropped_to_4_by_3() -> None:
    wide = Image.new("RGB", (1600, 600), (200, 10, 10))
    buf = io.BytesIO()
    wide.save(buf, "PNG")
    art, _ = compositor.render_art([], {}, buf.getvalue(), "#123456", [])
    assert png_pixel(art, (4, 4)) == (200, 10, 10)  # filled edge to edge, no tint showing


def test_everyone_stands_on_the_ground_line() -> None:
    chars = [char("a", "left"), char("b", "center"), char("c", "right")]
    placed = stage.place(chars, {"a": KID, "b": ROBOT, "c": KID})
    for p in placed:
        foot = p.cell[1] + stage.foot_line(p.spec["body_type"]) / 200 * p.cell[3]
        assert foot == pytest.approx(stage.GROUND, abs=0.002)


# ---- facing -------------------------------------------------------------------------------


def test_standing_characters_turn_to_face_each_other() -> None:
    placed = stage.place([char("a", "left"), char("b", "right")], {"a": KID, "b": KID})
    assert [(p.pose, p.mirror) for p in placed] == [
        ("three_quarter_right", False),
        ("three_quarter_left", False),
    ]


def test_point_aims_at_the_middle_and_action_poses_stay_front() -> None:
    assert stage.drawn_pose("point", "left", 2) == ("point", False)
    assert stage.drawn_pose("point", "right", 2) == ("point", True)
    assert stage.drawn_pose("wave", "right", 3) == ("wave", False)
    assert stage.drawn_pose("front", "center", 3) == ("front", False)


def test_a_lone_character_stays_as_planned() -> None:
    for position in ("left", "center", "right"):
        assert stage.drawn_pose("front", position, 1) == ("front", False)
        assert stage.drawn_pose("point", position, 1) == ("point", False)


def test_the_speaker_is_drawn_in_front() -> None:
    placed = stage.place(
        [char("a", "left"), char("b", "center"), char("c", "right")],
        {"a": KID, "b": KID, "c": KID},
    )
    assert [p.id for p in stage.z_order(placed)] == ["a", "b", "c"]
    assert [p.id for p in stage.z_order(placed, "a")] == ["b", "c", "a"]


# ---- tails --------------------------------------------------------------------------------


@pytest.mark.parametrize("body_type", ["kid", "grown_up", "robot", "cat", "dog", "bear"])
@pytest.mark.parametrize("pose", ["front", "point", "jump", "celebrate"])
def test_the_tail_target_is_inside_the_head(body_type: str, pose: str) -> None:
    spec = normalize({"body_type": body_type})
    for p in stage.place(
        [char("a", "left", pose), char("b", "right", pose)], {"a": spec, "b": spec}
    ):
        x, y, w, h = p.head
        tx, ty = p.head_target
        assert x < tx < x + w and y < ty < y + h


def test_bubble_tails_point_at_the_speakers_head() -> None:
    chars = [char("a", "left", "point"), char("b", "right")]
    specs = {"a": KID, "b": KID}
    laid = bubbles.layout(
        [
            {"id": "1", "speaker": "b", "type": "talk", "text": "Hi!"},
            {"id": "2", "speaker": "a", "type": "shout", "text": "Look!"},
        ],
        chars,
        specs,
    )
    heads = {p.id: p.head_target for p in stage.place(chars, specs)}
    assert [tuple(b["tail"]) for b in laid] == [heads["b"], heads["a"]]


# ---- lettering and layout -----------------------------------------------------------------


def test_long_text_shrinks_then_grows_the_bubble() -> None:
    width, height = bubbles.SPEECH_W, bubbles.MIN_H  # units
    short = lettering.fit("Hi!", "talk", width, height)
    medium = lettering.fit(
        "We have to find the mango before the festival starts!", "talk", width, height
    )
    long = lettering.fit(" ".join(["mango"] * 30), "talk", width, height)
    assert short.size == lettering.SIZES[0] and short.height == height
    assert medium.size < lettering.SIZES[0] and medium.height == height
    assert long.size == lettering.SIZES[-1] and long.height > height


def test_narrator_boxes_stay_on_top() -> None:
    laid = bubbles.layout(
        [
            {"id": "1", "speaker": "a", "type": "talk", "text": "Where is it?"},
            {"id": "2", "speaker": "narrator", "type": "narrator", "text": "Later that day..."},
        ],
        [char("a", "center")],
        {"a": KID},
    )
    talk, narrator = laid  # the kid's order is kept
    assert narrator["box"][1] == bubbles.MARGIN_Y / stage.PANEL_H and narrator["tail"] is None
    assert talk["box"][1] >= narrator["box"][1] + narrator["box"][3]


def test_a_moved_bubble_keeps_its_box_and_re_aims_its_tail() -> None:
    chars = [char("a", "left")]
    moved = {"id": "1", "speaker": "a", "type": "talk", "text": "Hi", "fixed": True,
             "box": (0.5, 0.6, 0.3, 0.12)}  # fmt: skip
    (laid,) = bubbles.layout([moved], chars, {"a": KID})
    assert laid["box"] == (0.5, 0.6, 0.3, 0.12)
    assert laid["tail"] == stage.place(chars, {"a": KID})[0].head_target


# ---- final.png ----------------------------------------------------------------------------


def test_final_png_letters_every_bubble_type_and_is_deterministic() -> None:
    chars = [char("a", "left"), char("b", "right")]
    specs = {"a": KID, "b": KID}
    laid = bubbles.layout(
        [
            {"id": "1", "speaker": "narrator", "type": "narrator", "text": "One day..."},
            {"id": "2", "speaker": "a", "type": "think", "text": "Hmm."},
            {"id": "3", "speaker": "b", "type": "shout", "text": "Wow!"},
        ],
        chars,
        specs,
    )
    art, _ = compositor.render_art(chars, specs, None, "#DDF0FC", laid)
    final = compositor.bake_final(art, laid)
    assert final == compositor.bake_final(art, laid) and final != art
    renamed = [{**b, "text": "Changed"} if b["id"] == "2" else b for b in laid]
    assert compositor.final_hash("k", 1, laid) != compositor.final_hash("k", 1, renamed)


# ---- Phase 7 A1: shout words stay inside the burst ---------------------------------------------


def test_a_long_shout_stays_inside_the_burst() -> None:
    from app.services import lettering

    text = "WATCH OUT EVERYBODY THE GIANT MANGO IS ROLLING DOWN THE HILL AGAIN"
    w, h, scale = 0.42 * 1600, 0.12 * 1200, 2  # the layout's speech width, at 2x art
    fitted = lettering.fit(text, "shout", w, h, scale)
    height = max(h, fitted.height)
    # The burst's valleys: an ellipse around the bubble's middle. Every line's corners are inside.
    a = lettering.BURST_VALLEYS[0] * w / 2
    b = lettering.BURST_VALLEYS[1] * height / 2
    f = lettering.font("shout", fitted.size)
    line_h = fitted.size * lettering.LINE
    top = -line_h * len(fitted.lines) / 2
    for i, line in enumerate(fitted.lines):
        half = f.getlength(line) / 2
        for dy in (top + i * line_h, top + (i + 1) * line_h):
            assert (half / a) ** 2 + (dy / b) ** 2 <= 1, (line, dy)


def test_a_shout_too_long_for_its_box_makes_the_burst_taller() -> None:
    from app.services import bubbles, lettering

    text = "WATCH OUT EVERYBODY THE GIANT MANGO IS ROLLING DOWN THE HILL AGAIN AND AGAIN"
    short = lettering.fit(text, "shout", 336, 40)

    assert short.height > 40
    grown = bubbles.fitted_height(text, "shout", 0.42)
    assert grown > bubbles.MIN_H / stage.PANEL_H  # the layout grows it too


def test_final_png_letters_a_long_shout() -> None:
    from app.services import compositor

    art = compositor.render_art([], {}, None, "#FFE9A8", [])[0]
    bubble = {
        "id": "s",
        "speaker": "narrator",
        "type": "shout",
        "text": "WATCH OUT EVERYBODY THE GIANT MANGO IS ROLLING DOWN THE HILL",
        "box": [0.3, 0.2, 0.42, 0.12],
        "tail": None,
    }
    assert compositor.bake_final(art, [bubble]).startswith(b"\x89PNG")


def test_old_final_pngs_re_letter_after_a_lettering_change(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services import compositor

    before = compositor.final_hash("art.png", 1, [])
    monkeypatch.setattr(compositor, "LETTERING_VERSION", compositor.LETTERING_VERSION + 1)

    assert compositor.final_hash("art.png", 1, []) != before


def test_a_shout_burst_stays_inside_the_panel() -> None:
    from app.services import bubbles, lettering

    shout = {"id": "s", "speaker": "a", "type": "shout", "text": "LOOK OUT!"}
    laid = bubbles.layout([shout], [{"id": "a", "position": "left"}])
    x, _y, w, _h = laid[0]["box"]

    spikes = w * (lettering.BURST_TIPS[0] - 1) / 2
    margin = bubbles.MARGIN_X / stage.PANEL_W
    assert x - spikes >= margin - 1e-9 and x + w + spikes <= 1 - margin + 1e-9
