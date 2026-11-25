"""Which prop states go where: on the ground at a spot, or held or worn by someone."""

from app.props.library import PROPS


def check_prop(prop_id: str, state: str, position: str | None, held_by: str | None) -> str | None:
    """A problem with this prop in a panel (in words for the planner and the error), or None."""
    prop = PROPS.get(prop_id)
    if prop is None:
        return f"{prop_id!r} isn't in the prop library"
    found = prop.states.get(state)
    if found is None:
        return f"the {prop.name.lower()} can be: {', '.join(prop.states)}"
    if found.placement == "ground":
        if not position:
            return f"the {prop.name.lower()} ({state}) needs a position"
        if held_by:
            return f"the {prop.name.lower()} ({state}) stands on the ground, so nobody holds it"
    elif not held_by:
        who = "wears" if found.placement == "worn" else "holds"
        return f"say who {who} the {prop.name.lower()} ({state})"
    return None
