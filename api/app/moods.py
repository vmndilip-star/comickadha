"""Story moods: everything a mood means to the planner and the Story Buddy, in one table.

Adding a mood: add its id to `Mood` (schemas/common.py), an entry here, then its label and hint in
the web (`MOODS` in web/src/types/index.ts, `MOOD_LABEL` and `MOOD_HINT` in web/src/lib/labels.ts)
and run `npm run gen:types`. Ids fit the comic table's mood column (16 characters at most).
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class MoodInfo:
    # What the mood means, for Meta prompts ("Mood: pirate (...)"). Our words, never a kid's, so
    # they can steer a mood away from anything unkind (no fighting, nobody gets eaten).
    about: str
    # The offline planner's first and last captions ({place} is the first scene's place).
    opener: str
    closer: str
    # The offline Story Buddy: words for scene titles, and questions ({name}, {place}).
    title_words: tuple[str, str, str]
    questions: tuple[str, str]


MOODS: dict[str, MoodInfo] = {
    "mystery": MoodInfo(
        "clues, secrets and a puzzle to solve",
        "Something strange was happening at {place}...",
        "And that is how the mystery was solved!",
        ("Missing", "Secret", "Mysterious"),
        ("What clue could {name} find first?", "Who might be hiding a secret at {place}?"),
    ),
    "funny": MoodInfo(
        "silly mix-ups, jokes and things going wonderfully wrong",
        "It was a very silly day at {place}.",
        "Everyone laughed all the way home. The end!",
        ("Silly", "Wobbly", "Giggly"),
        ("What silly thing could go wrong for {name}?", "What could make the ending funny?"),
    ),
    "adventure": MoodInfo(
        "a daring quest, discoveries and big challenges",
        "An adventure was about to begin at {place}!",
        "What an adventure! The end.",
        ("Great", "Daring", "Amazing"),
        ("What big challenge does {name} face?", "What could {name} discover at {place}?"),
    ),
    "spooky": MoodInfo(
        "a little bit spooky but never too scary: creaky doors, shadows and brave friends",
        "It was a spooky evening at {place}...",
        "And the spooky night ended with big smiles.",
        ("Spooky", "Midnight", "Shivery"),
        ("What spooky sound could {name} hear?", "Who could help {name} feel brave?"),
    ),
    "magical": MoodInfo(
        "wizards, fairies, spells and enchanted places",
        "A little bit of magic was in the air at {place}...",
        "And the magic sparkled on, happily ever after.",
        ("Magic", "Enchanted", "Sparkling"),
        ("What spell could {name} learn?", "What enchanted thing could be hiding at {place}?"),
    ),
    "fairy_tale": MoodInfo(
        'castles, talking animals and "once upon a time"',
        "Once upon a time, at {place}...",
        "And they all lived happily ever after. The end.",
        ("Royal", "Golden", "Wishing"),
        ("Which talking animal could help {name}?", "What wish could {name} make at {place}?"),
    ),
    "folk_tale": MoodInfo(
        "clever animals and a wise lesson at the end, in the style of the Panchatantra",
        "Long ago, at {place}, there lived some very clever friends...",
        "And the lesson? Brains beat brawn, and kindness wins. The end.",
        ("Clever", "Wise", "Little"),
        ("How could {name} use brains instead of strength?", "What lesson could {name} learn?"),
    ),
    "underwater": MoodInfo(
        "mermaids, sea creatures and sunken treasure",
        "Deep down under the waves, near {place}...",
        "And the friends swam home with the tide. The end!",
        ("Sunken", "Sparkling", "Deep-Sea"),
        ("Which sea creature could {name} meet?", "What treasure could be under the sand?"),
    ),
    "dinosaur": MoodInfo(
        "a prehistoric world with friendly dinosaurs (nobody gets eaten)",
        "Stomp, stomp! The dinosaurs were awake at {place}!",
        "And the dinosaurs waved goodbye with a happy ROAR. The end!",
        ("Stomping", "Giant", "Roaring"),
        ("Which dinosaur could become {name}'s friend?", "What could a baby dino need help with?"),
    ),
    "jungle_safari": MoodInfo(
        "wild animals and exploring the forest",
        "The jungle was buzzing at {place}...",
        "What a safari! The end.",
        ("Wild", "Jungle", "Roaring"),
        ("Which wild animal could {name} spot first?", "What path could {name} follow?"),
    ),
    "pirate": MoodInfo(
        "treasure maps, ships and hidden islands; the pirates are friendly treasure hunters, with "
        "no fighting and no weapons",
        "Ahoy! A treasure map was found at {place}!",
        "And the treasure was shared by everyone. The end, me hearties!",
        ("Treasure", "Hidden", "Golden"),
        ("Where could the X on {name}'s map be?", "What could the treasure really be?"),
    ),
    "space": MoodInfo(
        "rockets, planets and friendly aliens",
        "3, 2, 1... blast off from {place}!",
        "And the rocket zoomed home through the stars. The end!",
        ("Cosmic", "Starry", "Rocket"),
        ("Which planet could {name} visit?", "What could a friendly alien teach {name}?"),
    ),
    "robots_future": MoodInfo(
        "gadgets, flying cars and robot buddies in the future",
        "In the future, at {place}, the gadgets were buzzing...",
        "And the future looked bright. The end!",
        ("Robot", "Turbo", "Future"),
        ("What gadget could {name} invent?", "What could a robot buddy help with?"),
    ),
    "time_travel": MoodInfo(
        "jumping into the past or the future, then finding the way home",
        "Whoosh! The time machine landed at {place}...",
        "And they got home just in time. The end!",
        ("Time-Twisting", "Ancient", "Future"),
        ("Which time would {name} visit first?", "How could {name} find the way home?"),
    ),
    "sporty": MoodInfo(
        "the big match, teamwork and the underdog winning, with good sportsmanship",
        "It was the day of the big match at {place}!",
        "Win or lose, the team cheered together. The end!",
        ("Big", "Winning", "Champion"),
        ("What could {name}'s team practise?", "How could {name} help a teammate?"),
    ),
    "school_days": MoodInfo(
        "classroom fun, lunch breaks and school trips",
        "The school bell rang at {place}...",
        "And that was the best school day ever. The end!",
        ("School", "Classroom", "Lunchtime"),
        ("What could happen at lunch break?", "Where could {name}'s class go on a trip?"),
    ),
    "festival": MoodInfo(
        "celebrations, birthdays, holidays and fireworks",
        "Lights and music filled {place}: it was festival time!",
        "And the fireworks lit up the sky. The end!",
        ("Festival", "Party", "Sparkly"),
        ("What could {name} make for the celebration?", "What surprise could the party need?"),
    ),
    "nature_hero": MoodInfo(
        "saving the forest, helping animals and caring for the planet",
        "The trees were whispering for help at {place}...",
        "And the forest grew green and happy again. The end!",
        ("Green", "Wild", "Helping"),
        ("Which animal could {name} help?", "How could {name} help the forest grow again?"),
    ),
}


def mood_info(mood: str) -> MoodInfo:
    """The mood's table entry (adventure for one this table doesn't know)."""
    return MOODS.get(mood, MOODS["adventure"])


def mood_line(mood: str) -> str:
    """The mood as a prompt line's value: "pirate (treasure maps, ...)"."""
    return f"{mood.replace('_', ' ')} ({mood_info(mood).about})"
