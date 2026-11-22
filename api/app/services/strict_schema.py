"""Strict JSON-schema pieces for Meta's structured outputs (json_schema with strict: true)."""

from typing import Any


def strict_object(properties: dict[str, Any]) -> dict[str, Any]:
    """An object schema where every property is required and nothing else is allowed, as strict
    structured outputs need. Used by the Lab helper, Story Buddy and planner schemas."""
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }
