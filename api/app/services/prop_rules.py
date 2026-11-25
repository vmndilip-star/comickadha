"""Props and words agree: every prop a bubble or caption names is drawn in that panel.

`named_props` finds the props a text names (the prop library's words: "torch", "paw prints",
"red turban"...). `prop_problems` lists, for the planner's checks, what a panel's words name that
it doesn't draw (and a scarecrow drawn on its pole when the words say the pole is empty), so Meta
is asked again with the problem; `add_named_props` is the last word, adding what is still missing
in a sensible state, held by whoever names it when it can be held.
"""

import re
from collections.abc import Iterable, Mapping, Sequence
from typing import Any, Protocol

from app.props import PROPS

NARRATOR = "narrator"
_EMPTY_POLE = re.compile(
    r"\b(pole\s+(is|was|stands|looks|still)?\s*(totally\s+)?empty|empty\s+pole|nothing\s+on\s+"
    r"(the|its)\s+pole|bare\s+pole)\b"
)
TURBANS = ("red_turban", "orange_turban")


class BubbleLike(Protocol):
    speaker: str
    text: str


def _words(text: str) -> str:
    return " " + " ".join(re.findall(r"[a-z0-9']+", text.lower())) + " "


def named_props(text: str) -> list[str]:
    """The props a text names, in library order. A plain "turban" names a turban of any colour
    (returned as "turban"); a scarecrow on its pole counts as drawing the pole."""
    said = _words(text)
    found = [
        prop.id
        for prop in PROPS.values()
        if prop.id not in TURBANS and any(f" {w} " in said for w in prop.words)
    ]
    coloured = [t for t in TURBANS if any(f" {w} " in said for w in PROPS[t].words)]
    found += coloured
    if not coloured and (" turban " in said or " turbans " in said):
        found.append("turban")
    return found


def without_props(description: str) -> str:
    """A place's description without the parts that name a prop ("Tall sugarcane, a scarecrow
    with a red turban, a bamboo machan" -> "Tall sugarcane, a bamboo machan"): props are drawn on
    top of the place, per panel, so the picture must not have them painted in."""
    parts = re.split(r"(,\s*(?:and\s+)?|;\s*|\s+and\s+|\s+with\s+)", description.strip())
    kept: list[str] = []
    for i in range(0, len(parts), 2):
        clause, joint = parts[i], parts[i + 1] if i + 1 < len(parts) else ""
        if named_props(clause) or (
            " pole" in f" {clause.lower()}" and "scarecrow" in description.lower()
        ):
            continue
        kept += [clause, joint]
    text = "".join(kept).strip().rstrip(",;").strip()
    text = re.sub(r"\s+(and|with)$", "", text)
    if text and description.strip().endswith(".") and not text.endswith("."):
        text += "."
    return text[:1].upper() + text[1:] if text else ""


def says_pole_is_empty(text: str) -> bool:
    return bool(_EMPTY_POLE.search(" ".join(re.findall(r"[a-z0-9']+", text.lower()))))


def _drawn(props: Sequence[dict[str, Any]]) -> set[str]:
    out = {str(p.get("id")) for p in props}
    if any(p.get("id") == "scarecrow" and p.get("state") == "on_pole" for p in props):
        out.add("pole")  # a scarecrow on its pole shows the pole too
    if out & set(TURBANS):
        out.add("turban")
    return out


def prop_problems(
    bubbles: Iterable[BubbleLike], props: Sequence[dict[str, Any]], names: dict[str, str]
) -> list[str]:
    """What this panel's bubbles and captions name but don't draw. `names` maps prop ids to the
    words used in the message."""
    drawn = _drawn(props)
    problems: list[str] = []
    for b in bubbles:
        for prop_id in named_props(b.text):
            if prop_id not in drawn:
                label = "a turban" if prop_id == "turban" else f"the {names.get(prop_id, prop_id)}"
                problems.append(
                    f"a bubble says {b.text!r}, which names {label}: add it to this panel's props "
                    "(or don't name it)"
                )
                drawn.add(prop_id)
        if says_pole_is_empty(b.text) and any(
            p.get("id") == "scarecrow" and p.get("state") == "on_pole" for p in props
        ):
            problems.append(
                f"a bubble says {b.text!r}, but the scarecrow is drawn on its pole: show the empty "
                "pole (and the scarecrow somewhere else, or not at all)"
            )
    return problems


def _free_spot(props: Sequence[dict[str, Any]], prefer: Sequence[str]) -> str:
    taken = {p.get("position") for p in props if p.get("position")}
    return next((s for s in prefer if s not in taken), prefer[0])


_HOLDING = r"(?:is |are )?(?:hugging|hugs|hugged|holding|holds|held|carrying|carries|carried|with)"


def holder_named(text: str, prop_id: str, names: Mapping[str, str]) -> str | None:
    """Who a text says holds a prop: "Barnaby hugging the scarecrow" -> Barnaby's id."""
    said = _said(text)
    for name, character_id in names.items():
        who = _said(name)
        for word in _prop_words(prop_id):
            if who and re.search(rf"\b{re.escape(who)} {_HOLDING} (?:the |a |his |her |their )?"
                                 rf"(?:\w+ )?{re.escape(word)}\b", said):  # fmt: skip
                return character_id
            if who and re.search(rf"\b{re.escape(who)}'s (?:\w+ )?{re.escape(word)}\b", said):
                return character_id  # "Sniffy's torch"
    return None


_WEARING = r"(?:is |are )?(?:wearing|wears|wore|in)"
_ON_HEAD = r"(?: \w+){0,3} on (?:his|her|their) head\b"  # a person's head
_ON_ITS_HEAD = r"(?: \w+){0,3} on its head\b"  # the scarecrow's


def _said(text: str) -> str:
    return " ".join(re.findall(r"[a-z0-9']+", text.lower()))


def _prop_words(prop_id: str) -> tuple[str, ...]:
    """The words that name a prop; a plain "turban" names either turban."""
    extra = ("turban", "turbans") if prop_id in TURBANS else ()
    return (*PROPS[prop_id].words, *extra)


def wearer_named(text: str, prop_id: str, names: Mapping[str, str]) -> str | None:
    """Who a text says wears a turban: "Barnaby wearing the red turban", "the scarecrow's red
    turban", "Leo in an orange turban", "the turban on Leo's head", or "the red turban crooked on
    his head" (the last one named before it). `names` maps names (the scarecrow's too, when it is
    drawn) to ids."""
    said = _said(text)
    last: tuple[int, str] | None = None  # the last one named before "... on his head"
    for word in _prop_words(prop_id):
        at = re.search(rf"\b{re.escape(word)}\b", said)
        if at is None:
            continue
        thing = re.escape(word)
        for name, character_id in names.items():
            who = re.escape(_said(name))
            if not who:
                continue
            patterns = (
                rf"\b{who} {_WEARING} (?:the |a |an |his |her |their |its )?(?:\w+ )?{thing}\b",
                rf"\b{who}'s (?:\w+ )?{thing}\b",
                rf"\b{thing}\b(?: \w+){{0,3}} on {who}'s head\b",
            )
            if any(re.search(pattern, said) for pattern in patterns):
                return character_id
            if character_id == "scarecrow":
                if re.search(rf"\b{thing}\b{_ON_ITS_HEAD}", said):
                    return character_id
            elif re.search(rf"\b{thing}\b{_ON_HEAD}", said):
                named = [m.start() for m in re.finditer(rf"\b{who}\b", said[: at.start()])]
                if named and (last is None or named[-1] > last[0]):
                    last = (named[-1], character_id)
    return last[1] if last else None


def add_named_props(
    bubbles: Iterable[BubbleLike],
    props: list[dict[str, Any]],
    characters: Sequence[str],
    names: Mapping[str, str] | None = None,
) -> list[dict[str, Any]]:
    """The props with everything the words name added (a new list): held or worn by whoever the
    words say (`names`: character names -> ids), else by the one who names it when it can be held
    (or the first character), else on the ground at a free spot. A prop already drawn moves to
    whoever the words say holds or wears it ("Sniffy's torch" drawn in Barnaby's hand)."""
    out = [dict(p) for p in props]
    for b in bubbles:
        empty = says_pole_is_empty(b.text)
        if empty:
            for p in out:  # "the pole is empty": the scarecrow comes off it
                if p.get("id") == "scarecrow" and p.get("state") == "on_pole":
                    p.update(state="lying_down")
        for prop_id in named_props(b.text) + (["pole"] if empty else []):
            if prop_id in _drawn(out) and not (prop_id == "pole" and empty):
                _give_to_owner(b.text, prop_id, out, characters, names or {})
                continue
            if prop_id == "pole" and any(p.get("id") == "pole" for p in out):
                continue
            if prop_id == "turban":
                prop_id = "red_turban"
            owner = _owner(b.text, prop_id, out, characters, names or {})
            if owner:
                out.append({"id": prop_id, "state": owner[0], "held_by": owner[1]})
                continue
            holder = b.speaker if b.speaker in characters else (characters[0] if characters else "")
            out.append(_new_prop(prop_id, holder, out))
    return out


def _owner(
    text: str,
    prop_id: str,
    props: Sequence[dict[str, Any]],
    characters: Sequence[str],
    names: Mapping[str, str],
) -> tuple[str, str] | None:
    """(state, holder) when the words say who wears or holds a prop and they're in the panel: a
    turban on someone's head (the scarecrow's too), anything else that can be held in a hand."""
    if prop_id in TURBANS:
        wearer = _turban_wearer(text, prop_id, props, names)
        if wearer and (wearer in characters or wearer == "scarecrow"):
            return ("worn", wearer)
    holder = holder_named(text, prop_id, names)
    if holder and holder in characters and "held" in PROPS[prop_id].states:
        return ("held", holder)
    return None


def _give_to_owner(
    text: str,
    prop_id: str,
    props: list[dict[str, Any]],
    characters: Sequence[str],
    names: Mapping[str, str],
) -> None:
    """Moves a drawn prop to whoever the words say holds or wears it, when it's someone else."""
    if prop_id == "turban":
        drawn = [p for p in props if p.get("id") in TURBANS]
        if len(drawn) != 1:
            return  # "the turban" with both drawn (or none): nothing says which
        prop_id = str(drawn[0]["id"])
    if prop_id not in PROPS:
        return
    owner = _owner(text, prop_id, props, characters, names)
    prop = next((p for p in props if p.get("id") == prop_id), None)
    if owner is None or prop is None:
        return
    if (prop.get("state"), prop.get("held_by")) != owner:
        prop.pop("position", None)
        prop.update(state=owner[0], held_by=owner[1])


def _turban_wearer(
    text: str, prop_id: str, props: Sequence[dict[str, Any]], names: Mapping[str, str]
) -> str | None:
    """Who wears a turban the words name: whoever they put it on, else the scarecrow when it
    stands on its pole in the panel and the words name it without anyone holding the turban
    ("the scarecrow is back on its pole with a new orange turban")."""
    scarecrow = next((p for p in props if p.get("id") == "scarecrow"), None)
    heads = {**names, **({"scarecrow": "scarecrow"} if scarecrow else {})}
    wearer = wearer_named(text, prop_id, heads)
    on_pole = scarecrow is not None and scarecrow.get("state") == "on_pole"
    if wearer is None and on_pole and " scarecrow " in _words(text):
        return None if holder_named(text, prop_id, names) else "scarecrow"
    return wearer


def _new_prop(prop_id: str, holder: str, props: Sequence[dict[str, Any]]) -> dict[str, Any]:
    prop = PROPS[prop_id]
    if "held" in prop.states and holder and prop_id != "scarecrow":
        return {"id": prop_id, "state": "held", "held_by": holder}
    if prop_id == "scarecrow":
        return {
            "id": prop_id,
            "state": "on_pole",
            "position": _free_spot(props, ("far_left", "far_right")),
        }
    state = next(s for s, st in prop.states.items() if st.placement == "ground")
    spot = _free_spot(props, ("center", "far_right", "far_left", "right", "left"))
    return {"id": prop_id, "state": state, "position": spot}
