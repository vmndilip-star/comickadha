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
    "classifier": Limit(4000, 30.0),
    "image_check": Limit(1500, 20.0),  # vision model
    # Story Studio (services/story_buddy.py, services/story_planner.py).
    "buddy_idea": Limit(3200, 20.0),
    "buddy_spelling": Limit(3600, 25.0),
    "buddy_name_scene": Limit(2600, 20.0),
    "plan_scenes": Limit(6000, 35.0),
    "plan_panels": Limit(9500, 45.0),
}
