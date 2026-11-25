# Character safety policy

Comickadha is for children aged about 7–12 (and up to 15). Characters are built from a fixed,
reviewed parts library; AI only suggests choices from that library. This policy says what a kid
can ask for, what the helpers may answer, and what happens when something isn't right. The code
that enforces it is listed at the end.

The rule behind everything: **a child always gets a friendly result or a gentle message, never an
error page, and nothing unsafe is drawn, said or sent on.** Every check fails closed: if a check
can't run, the safe choice is taken. Every decision is written to `moderation_log`.

## 1. What a kid can ask for (`POST /api/builder/create`)

| Input | Allowed values |
| --- | --- |
| `kind` | `person`, `robot`, `cat`, `dog`, `bear` |
| `age` | people only: `little_kid`, `big_kid` (both drawn with the kid body), `grown_up`, `grandparent` (both drawn with the grown-up body; grandparents lean towards grey or white hair). Default `big_kid`. Sending an age for a robot or animal is refused. |
| `face_shape` | a face shape from the parts library that fits that body (`round`, `oval`, `square`, `heart` for people; `box`, `dome`, `screen` for robots; `cat`, `dog`, `bear` for animals) |
| `description` | optional free text, up to 300 characters, checked as in section 4 |
| `follow_up_answer` | the answer to the helper's follow-up question: one catalog choice (a part, or a colour from the palette) that fits the body type. It can never be free text. |
| `look` | only together with `follow_up_answer`: the character so far, checked exactly like a saved look (unknown or ill-fitting parts and off-palette colours are refused, and it must match the kind and age). Its personality is removed before anything is sent to Meta. Meta is told to change only what the answer is about, and the server enforces it: the answer keeps every part, colour and extra of the look except the choice the answer maps to (a dress also brings its leggings). |
| `name` | optional, up to 24 characters, checked like any text, and against famous names and real people |
| `role` | `hero`, `sidekick`, `friend` |

Saving the character (`POST /api/characters`) checks the name again with the same rules. Any other field is refused (422). A part or colour that doesn't exist or doesn't fit the body is
refused with a message under that field.

## 2. What the helper answers

- **Looks:** parts, colours and extras from the library only (colours are palette entries). People
  are always clothed (section 3).
- **Traits:** up to 3 from this fixed list of positive or neutral traits: brave, curious, funny,
  kind, clever, creative, calm, cheerful, helpful, honest, adventurous, caring, energetic, gentle,
  patient, playful, shy, silly, sporty, thoughtful. Anything else is dropped.
- **Role suggestion:** `hero`, `sidekick` or `friend` (anything else is replaced by one that suits the traits). The child picks the final role.
- **Words:** up to 3 name ideas (made-up and kind, never famous or real people), a catchphrase
  (at most 12 words), an intro line (at most 15 words), a short reply.
- **Follow-up:** at most one question about the character's looks or personality (never about the
  child), with 2–4 options. Each option is one catalog choice; if any option isn't, the whole
  follow-up is left out.

Existing characters were moved to the trait list: traits on the list were kept, the rest dropped.

## 3. The parts library

The library is checked by a test every time the tests run (`tests/test_catalog_audit.py`):

- **People are always dressed.** Kid and grown-up bodies must have a top and a bottom: there is
  no "none" top, bottom or shoes for them. A dress still comes with a bottom; when a dress is
  picked (by a kid or a helper), the bottom becomes leggings in a matching, darker colour.
- **Only robots and animals** may go without clothes.
- **No weapons.** The only hand-held "power" item is the magic wand. Wishes for weapons get a
  stand-in (a sword becomes the wand).
- **No text, brand names or logos** on any clothes or extras.
- **Cultural and religious items** (hijab, turban) are available to every human body type, have
  plain, respectful labels, and are never combined with silly items (star glasses) by
  "Surprise me". They can be picked at random with ordinary clothes, superhero suits and capes
  included: kids should see characters who look like them and their families.
- **Every option is reviewed.** Each part and extra must be listed in the generator's review table
  (`REVIEWED` in `shared/avatar/build_catalog.py`), which writes `reviewed: true` into the catalog.
  A new option is unreviewed until a person checks its art and adds it; the test fails until then.

## 4. Checking a description, before anything is sent

In this order, stopping at the first block:

1. **Length:** at most 300 characters.
2. **Personal information:** phone numbers, email addresses, street addresses, school names,
   self-identifying full names (existing check).
3. **Word list:** violence, weapons, adult themes, drugs, self-harm, hate, bullying (existing).
4. **Real people:** a character based on a real, named person (family, classmates, teachers,
   celebrities). Local patterns ("look like my sister Priya", "like my teacher", "based on my
   friend") and a short list of famous names; with Meta on, the AI classifier's `real_person`
   category too. Message: *"Let's make up a brand-new character instead!"*
5. **Rule-bending:** "ignore the rules", "pretend", "without clothes" and similar. Message:
   *"Let's stick to the Comickadha rules and keep building together!"*
6. **Body comments:** words about weight or body shape ("fat", "skinny"...) are taken out before
   the description goes anywhere. The character is made without them, with the note
   *"Every character is awesome just as they are!"*

Blocks are a 422 with the message under the description; nothing is sent to Meta. The same checks
run on the Lab helper's "describe" box.

## 5. What Meta is told (`api/app/prompts/builder_create.md`)

The audience is 7–12; pick only from the options given; keep characters friendly and positive;
never describe bodies, weight or attractiveness; never base a character on a real person; names
are made-up and kind (no insults, no celebrities); clothing is everyday, costume or sports wear
suitable for school; follow-up questions are only about looks or personality, never about the
child.

## 6. Checking what comes back

After every answer (Meta or offline):

- Parts and colours must be library choices that fit the body type; people must be clothed,
  otherwise the default outfit for that body type is used.
- Traits must be on the list; text must fit its length limit.
- Every piece of text (names, catchphrase, intro line, reply, follow-up) goes through the local
  checks and, with Meta, the classifier. Names are also checked against famous names and
  real-person patterns. If the classifier can't answer, the text counts as unsafe.
- Anything that fails is replaced with a safe default (default outfit, a name from the offline
  list, a friendly catchphrase and intro line) or left out (follow-up, unmatched wishes), and the
  replacement is logged with its reason. The child sees a friendly result.

## Where it lives

| Rule | Code |
| --- | --- |
| Request and answer shapes | `api/app/schemas/builder.py` (`CreateRequest`, `Created`) |
| Trait list and migration | `api/app/schemas/common.py` (`Trait`), `api/app/avatar/migrate.py` (`migrate_traits`) |
| Description and name checks | `api/app/services/character_safety.py` |
| Classifier categories | `api/app/services/safety.py`, `api/app/prompts/safety_classifier.md` |
| Create flow and output checks | `api/app/services/builder_create.py` |
| Library review and tags | `shared/avatar/build_catalog.py` (`REVIEWED`, `CULTURAL`, `SILLY`) |
| Tests | `api/tests/test_catalog_audit.py`, `api/tests/test_character_safety.py` |
