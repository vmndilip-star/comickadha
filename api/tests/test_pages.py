"""Big panels (Phase 8, step 3): normal, wide and splash panels fill pages by slots (6 a page),
nothing is left mostly empty, sizes are drawn at their page shape, and the PDF lays pages out
the same way."""

import io
from typing import Any

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.services import compositor, story_planner
from app.services.pages import comic_pages, pages_of, shown_sizes
from app.services.story_planner import big_size, limit_splashes, plan_parts, splash_limit
from tests.test_long_comics import ctx
from tests.test_make_comic import comic, generate, page_count, planned_comic

N, W, S = "normal", "wide", "splash"


def rows_of(sizes: list[str]) -> list[Any]:
    return [
        p.splash if p.splash is not None else (p.rows, p.the_end)
        for p in pages_of(shown_sizes(sizes))
    ]


# ---- pages by slots ------------------------------------------------------------------------------


def test_normal_panels_pair_up_and_a_lone_one_is_shown_wide() -> None:
    assert shown_sizes([N] * 6) == [N] * 6
    assert shown_sizes([N] * 7)[-1] == W
    assert shown_sizes([N, W, N, N]) == [W, W, N, N]  # alone before a wide panel


def test_no_page_is_mostly_empty() -> None:
    for count in range(4, 31):
        for sizes in ([N] * count, [N] * (count // 2) + [S] + [N] * (count - count // 2 - 1)):
            shown = shown_sizes(sizes)
            for page in pages_of(shown):
                if page.splash is None:
                    used = len(page.rows) + (3 - len(page.rows) if page.the_end else 0)
                    assert used >= 2, (sizes, page)  # at most one empty row, never two
            last = pages_of(shown)[-1]
            assert last.splash is not None or len(last.rows) == 3 or last.the_end


def test_a_splash_fills_its_own_page_and_a_lone_row_between_splashes_grows() -> None:
    assert rows_of([N, N, N, N, S, N, N, N, N]) == [
        ([[0, 1], [2, 3]], False),
        4,
        ([[5, 6], [7, 8]], True),
    ]
    shown = shown_sizes([N, N, S, N, N, S])
    assert shown == [W, W, S, W, W, S]  # a single row on a page becomes two rows
    assert shown_sizes([S, W, S]) == [S, S, S]  # a single wide panel between splashes: a splash


def test_a_short_last_page_gets_the_end() -> None:
    assert rows_of([N] * 4) == [([[0, 1], [2, 3]], True)]
    assert rows_of([N] * 2) == [([[0], [1]], True)]  # one row of two: both wide, then The End
    assert rows_of([N] * 6) == [([[0, 1], [2, 3], [4, 5]], False)]  # full: no tile


def test_old_comics_keep_their_old_pages() -> None:
    old = comic_pages([None] * 25)  # drawn before panel sizes
    assert [len(p.rows) for p in old] == [3, 3, 3, 3, 1] and not any(p.the_end for p in old)
    assert old[-1].rows == [[24]]


# ---- the planner picks sizes ---------------------------------------------------------------------


def test_a_key_moment_near_the_end_is_a_splash_page() -> None:
    story = ctx(16)
    last = story.scenes[-1]
    story.scenes[-1] = story_planner.SceneInfo(
        last.id,
        last.background_id,
        last.character_ids,
        last.summary,
        key_moment="The bear is found",
    )
    part = plan_parts(story)[-1]
    assert big_size(part) == "splash"
    plan = story_planner.offline_part(story, part, story_planner.Voices())
    assert [p.size for p in plan.panels if p.key_moment] == ["splash"]
    first = plan_parts(story)[0]
    assert big_size(first) == "wide"


def test_splash_pages_stay_rare() -> None:
    assert [splash_limit(n) for n in (4, 12, 13, 25, 30)] == [1, 1, 2, 3, 3]
    story = ctx(8)
    parts = plan_parts(story)
    plans = [story_planner.offline_part(story, p, story_planner.Voices()) for p in parts]
    plans = [
        p.model_copy(update={"panels": [x.model_copy(update={"size": "splash"}) for x in p.panels]})
        for p in plans
    ]
    changed = limit_splashes(plans, parts, story)
    after = [changed.get(i, plan) for i, plan in enumerate(plans)]
    sizes = [x.size for plan in after for x in plan.panels]
    assert sizes.count("splash") == 1 and sizes.count("wide") == len(sizes) - 1


# ---- drawn at the page shape --------------------------------------------------------------------


@pytest.mark.parametrize(
    ("size", "shape"), [("normal", (1600, 1200)), ("wide", (2050, 750)), ("splash", (2050, 2350))]
)
def test_each_size_is_drawn_at_its_page_shape(size: str, shape: tuple[int, int]) -> None:
    art, _ = compositor.render_art([], {}, None, "#DDF0FC", [], [], size)
    with Image.open(io.BytesIO(art)) as image:
        assert image.size == shape


def test_a_new_size_reshapes_its_neighbours_and_draws_them_again(client: TestClient) -> None:
    made = planned_comic(client, 4)
    generate(client, made["id"])
    before = comic(client, made["id"])
    assert [p["shown_size"] for p in before["panels"]] == [N, N, N, N]
    first, second = before["panels"][0], before["panels"][1]

    res = client.patch(f"/api/panels/{second['id']}", json={"size": "wide"})

    assert res.status_code == 200
    assert (res.json()["size"], res.json()["shown_size"]) == ("wide", "wide")
    after = comic(client, made["id"])
    assert [p["shown_size"] for p in after["panels"]] == [W, W, N, N]  # panel 1 is alone now
    assert after["panels"][0]["art_url"] != first["art_url"]  # drawn again, wide
    with Image.open(io.BytesIO(client.get(after["panels"][0]["art_url"]).content)) as art:
        assert art.size == (2050, 750)
    assert after["pages"] == [
        {"number": 2, "rows": [[0], [1], [2, 3]], "splash": None, "the_end": False}
    ]


def test_the_pdf_lays_pages_out_by_slots(client: TestClient) -> None:
    made = planned_comic(client, 8)
    panels = made["panels"]
    assert (
        client.patch(f"/api/panels/{panels[4]['id']}", json={"size": "splash"}).status_code == 200
    )
    generate(client, made["id"])
    final = comic(client, made["id"])
    assert [p["splash"] for p in final["pages"]] == [None, 4, None]
    pdf = client.get(f"/api/comics/{made['id']}/pdf")
    assert pdf.status_code == 200
    assert page_count(pdf.content) == 1 + len(final["pages"])  # the cover too
