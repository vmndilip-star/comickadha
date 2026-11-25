"""The kid-written words a Meta prompt includes, gathered in one place and checked together, in one
classifier call, just before the prompt is sent (decision 55: nothing unchecked reaches Meta).

Cast names and catchphrases and place names and descriptions were only word-list checked when
they were saved or locked (decision 31), maybe while Meta was off. So every prompt that includes
them checks them again here, with the story text, wherever the text is sent (not at lock):

- a block is a 422 "unsafe" whose message names the character or field to change;
- a place whose words don't pass is left out instead (like an unlocked cast member, decision
  46): out of the prompt, out of the offline plan, with a note naming it. Locked places can't be
  edited, so blocking would leave the kid stuck (decision 89);
- a classifier outage means "offline only": the offline helper answers (the decision 55 path).

Each prompt builder has a matching `*_fields` function next to it (story_planner.planner_fields,
story_buddy.buddy_fields) built from the same context object, so the two can't drift apart.
CLAUDE.md lists every Meta prompt, the kid-written fields it includes and where they're checked.
"""

from dataclasses import dataclass, field

from sqlmodel import Session

from app.errors import ApiError
from app.providers.llm import LLMProvider
from app.services import safety
from app.services.safety import SafetyUnavailable, Verdict

FRIENDLY = "Let's keep Comickadha friendly for everyone!"
# Fields the Studio shows the message under, so it needn't say where the words are.
SHOWN_ON_FIELD = ("title", "synopsis", "buddy", "scenes.")
ORDINALS = ["first", "second", "third", "fourth", "fifth", "sixth", "seventh", "eighth"]


def ordinal(i: int) -> str:
    return ORDINALS[i] if i < len(ORDINALS) else f"number {i + 1}"


@dataclass
class KidFields:
    """field name -> the kid's text, and field name -> how to tell a kid where it is."""

    texts: dict[str, str] = field(default_factory=dict)
    labels: dict[str, str] = field(default_factory=dict)
    # Fields that belong to a place (field -> place id), and the places' names.
    place_of: dict[str, str] = field(default_factory=dict)
    place_names: dict[str, str] = field(default_factory=dict)

    def add(self, name: str, text: str, label: str) -> None:
        if text.strip():
            self.texts[name] = text
            self.labels[name] = label

    def add_title_and_story(self, title: str, synopsis: str | None = None) -> None:
        self.add("title", title, "the title")
        if synopsis is not None:
            self.add("synopsis", synopsis, "the story")

    def add_character(self, i: int, cid: str, name: str, catchphrase: str | None = None) -> None:
        # A blocked name is never repeated back: the character is named by its place in the cast.
        self.add(
            f"cast.{cid}.name",
            name,
            f"the name of the {ordinal(i)} character in your cast (in the Character Lab)",
        )
        if catchphrase is not None:
            self.add(
                f"cast.{cid}.catchphrase",
                catchphrase,
                f"{name}'s catchphrase (in the Character Lab)",
            )

    def add_place(self, i: int, pid: str, name: str, description: str | None = None) -> None:
        self.place_names[pid] = name
        self.add(f"places.{pid}.name", name, f"the name of your {ordinal(i)} place")
        self.place_of[f"places.{pid}.name"] = pid
        if description is not None:
            self.add(
                f"places.{pid}.description",
                description,
                f'the description of the place "{name}"',
            )
            self.place_of[f"places.{pid}.description"] = pid

    def message(self, verdict: Verdict) -> str:
        name = verdict.field_name or ""
        label = self.labels.get(name, "the words")
        # The personal-info messages talk about "your story", so they're only used on story fields.
        if verdict.kid_message and name.startswith(SHOWN_ON_FIELD):
            return verdict.kid_message
        if name == "buddy":
            return f"{FRIENDLY} Please try different words."
        return f"{FRIENDLY} Please change {label} and try again."


@dataclass
class Checked:
    # True when the classifier couldn't answer: the words only passed the local checks, so only
    # the offline helper may use them.
    pending: bool = False
    # Places whose words didn't pass, as {place id: name}, in prompt order: leave them out.
    left_out: dict[str, str] = field(default_factory=dict)


def check_before_meta(
    session: Session,
    user_id: str,
    target: str,
    fields: KidFields,
    llm: LLMProvider | None,
) -> Checked:
    """The local checks, then (with an LLM) one classifier call over every field, all logged.

    Raises 422 "unsafe" naming the first blocked field that isn't a place's. A place whose name or
    description doesn't pass is returned in `left_out` (logged as a block on that place)."""

    def block(verdict: Verdict) -> ApiError:
        safety.log_verdict(session, user_id, target, verdict, "text")
        return ApiError(422, "unsafe", fields.message(verdict), verdict.field_name)

    story = {name: text for name, text in fields.texts.items() if name not in fields.place_of}
    local = safety.check_local(story)
    if not local.allowed:
        raise block(local)
    bad: dict[str, Verdict] = {}
    for name, pid in fields.place_of.items():
        if pid not in bad and name in fields.texts:
            verdict = safety.check_local({name: fields.texts[name]})
            if not verdict.allowed:
                bad[pid] = verdict

    pending = False
    if llm is not None:
        rest = {n: t for n, t in fields.texts.items() if fields.place_of.get(n) not in bad}
        try:
            verdicts = safety.classify_each(llm, rest)
        except SafetyUnavailable:
            pending = True
        else:
            for name in rest:  # in order, so the first blocked story field is the one named
                found = verdicts.get(name)
                if found is None or found.allowed:
                    continue
                if name not in fields.place_of:
                    raise block(found)
                bad.setdefault(fields.place_of[name], found)

    for pid, verdict in bad.items():
        safety.log_verdict(session, user_id, f"background:{pid}", verdict, "text")
    overall = Verdict(True, None, ["unavailable"], pending=True) if pending else Verdict(True)
    safety.log_verdict(session, user_id, target, overall, "text")
    left_out = {pid: name for pid, name in fields.place_names.items() if pid in bad}
    return Checked(pending=pending, left_out=left_out)
