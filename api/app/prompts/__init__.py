"""Prompt templates (.md files next to this module), filled with str.format.

Every prompt lives here, never inline in code, so prompt changes are reviewable in one place.
`load_all()` runs at startup: it reads every template once and fails fast if one is missing or
has a placeholder the code doesn't fill. Literal braces in a template are written `{{` and `}}`.
"""

import string
from pathlib import Path

PROMPTS_DIR = Path(__file__).parent

# Each prompt and the placeholders the code fills in.
REQUIRED: dict[str, set[str] | None] = {
    "background": {"name", "description", "aspect", "tint"},
    "builder_helper": {"catalog"},
    "builder_create": {"catalog"},
    "safety_classifier": set(),
    "planner_scenes": {"scene_count"},
    "planner_panels": {"panel_count"},
    "buddy_idea": set(),
    "buddy_spelling": set(),
    "buddy_name_scene": set(),
    "image_safety": set(),
    "background_no_text": set(),
    "background_time": {"time", "light"},
    # Painted portraits and the look check (decisions 131, 132).
    "portrait": {"look"},
    "look_check": set(),
    "paint_keep_look": set(),
}

_cache: dict[str, str] = {}


def load_all() -> dict[str, str]:
    """Reads every required prompt; raises if one is missing or uses an unknown placeholder."""
    for name, allowed in REQUIRED.items():
        path = PROMPTS_DIR / f"{name}.md"
        if not path.exists():
            raise RuntimeError(f"Missing prompt file app/prompts/{name}.md")
        text = path.read_text(encoding="utf-8")
        used = {field for _, field, _, _ in string.Formatter().parse(text) if field}
        if allowed is not None and not used <= allowed:
            raise RuntimeError(f"app/prompts/{name}.md uses unknown placeholders {used - allowed}")
        _cache[name] = text
    return dict(_cache)


def template(name: str) -> str:
    if name not in _cache:
        _cache[name] = (PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8")
    return _cache[name]


def render(template_name: str, /, **values: object) -> str:
    return template(template_name).format(**values).strip()
