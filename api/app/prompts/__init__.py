"""Prompt templates (.md files next to this module), filled with str.format."""

from pathlib import Path

PROMPTS_DIR = Path(__file__).parent


def render(template_name: str, /, **values: object) -> str:
    template = (PROMPTS_DIR / f"{template_name}.md").read_text(encoding="utf-8")
    return template.format(**values).strip()
