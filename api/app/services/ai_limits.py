"""Every Meta call's max_tokens and timeout, in one place (decision 80; measured in Phase 6a).

muse-spark-1.3 thinks before it answers, and the thinking counts toward max_tokens. A reply cut
off at the limit raises LLMError, and the Guard treats LLMError as an outage: the offline helper
answers, silently. So a limit that is too low quietly turns a Meta feature offline (before Phase 6a
nearly every describe, surprise and from-drawing call was cut off at 1,024). Each limit is about
twice the largest completion seen on real calls, and each timeout about twice the slowest call
(never under 20 s). The openai client may retry once on top (max_retries=1).

Measured on 2026-11-22 with muse-spark-1.3 (completion tokens min-max, slowest call; CLAUDE.md
decision 83 has the table): describe 2,039-2,681 (17.7 s), surprise 2,488-2,834 (19.3 s), ideas
942-1,172 (6.8 s), from-drawing 1,957-4,352 (34.2 s), classifier 364-1,948 (12.7 s, over 53
calls), image check 472-654 (6.0 s), Story Buddy idea 1,095-1,567 (9.6 s), spelling 1,125-1,779
(11.7 s), scene titles 919-1,252 (7.5 s), scenes 2,020-2,987 (17.1 s), panels 3,403-4,685 (22.2 s).

Re-measured on 2026-11-22 with long comics (Phase 7 part C, decision 110: a 16- and a 30-panel
plan, 33 calls): scenes 2,904-5,464 (68.1 s for 8 scenes, maybe with one client retry), panels a
part at a time 4,028-5,711 (33.7 s), classifier batches of up to 20 texts 571-3,627 (22.4 s);
`seed --paint` (3 places): image check 661-999 (7.1 s), classifier 505-599 (3.9 s). Live test 2:
scene planning took about 85 s (against 90 s), so its timeout is now 140 s. The live test 2 check
(a 10-panel plan) had a single scene's panel call take 41.4 s, the slowest yet: panels now 85 s.

Phase 8 (2026-11-23, the Sniffy test comic, 25 panels): with props, sizes and key moments in
every panel, a first plan's part calls wrote 5,400-8,171 completion tokens in 51.5-76.2 s and one
ran past the 85 s timeout (its part fell back to the offline planner); the plan again, 9 parts all
by Meta, wrote 6,786-10,127 tokens in 56.5-95.4 s. Panels are now 20,500 / 190 s, and asking
single panels again the same. A 20-text classifier batch took 31.5 s: 65 s now.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Limit:
    max_tokens: int
    timeout: float  # seconds, for this one call


LIMITS: dict[str, Limit] = {
    # The Lab helper (services/helper_meta.py).
    "describe": Limit(5500, 40.0),
    "surprise": Limit(6000, 40.0),
    "ideas": Limit(2500, 20.0),
    "from_drawing": Limit(9000, 70.0),  # vision model
    "create": Limit(6000, 60.0),  # decision 80: 2,000-2,500 tokens, ~15 s (not re-measured)
    # The safety checks (services/safety.py).
    "classifier": Limit(7500, 65.0),  # a 20-text batch reached 3,627 tokens; 31.5 s (Phase 8)
    "image_check": Limit(2000, 20.0),  # vision model; was 1500: seed --paint reached 999
    # Story Studio (services/story_buddy.py, services/story_planner.py).
    "buddy_idea": Limit(3200, 20.0),
    "buddy_spelling": Limit(3600, 25.0),
    "buddy_name_scene": Limit(2600, 20.0),
    "plan_scenes": Limit(11000, 140.0),  # 8 scenes: 5,464 tokens; 68 s, then 85 s (live test 2)
    "plan_panels": Limit(20500, 190.0),  # one call per part; Phase 8: 10,127 tokens, 95.4 s
    # Phase 8: only the panels of a part that broke a rule, asked for again (at most a part's
    # worth, so the part's limit; not called in the Phase 8 run).
    "fix_panels": Limit(20500, 190.0),
}

# Long comics (Phase 7 part C): one call can't write 30 panels, so the panel plan is written one
# part at a time (a scene, or a run of a big scene's panels), a few parts at once.
PANELS_PER_CALL = 8  # the most panels one plan_panels call writes (what the limit was measured on)
PLAN_PARTS_AT_ONCE = 3  # parts of one comic planned at the same time
# The classifier checks at most this many texts per call (a 30-panel plan has about 60), so its
# reply stays well inside its max_tokens. Every batch must answer, or the whole check fails closed.
CLASSIFIER_BATCH = 20
