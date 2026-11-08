# Character safety (Create character work)

Saved as given on 2026-11-08. The written policy it asks for goes in `docs/character-safety.md`.

---

Character safety: define the creation parameters and enforce kid-safe rules.
Add this to the Create character work. Save it to docs/character-safety.md as a
written policy, then implement it. Reply with a short plan first and WAIT for approval.

## 1. Parameter contract for /builder/create
Inputs: kind (person|robot|cat|dog|bear), age (little_kid|big_kid|grown_up|grandparent,
people only), face_shape (catalog enum), description (free text, ≤ 300 chars,
optional), follow_up_answer (must be one of the offered options), name (≤ 24 chars),
role (hero|sidekick|friend).
Outputs: parts and colours (catalog/palette enums only), traits (enum, see 2),
name_ideas, catchphrase (≤ 12 words), intro_line (≤ 15 words), follow_up question
and options (options must map to catalog choices). Reject unknown fields.

## 2. Traits become a fixed list
Replace free-text traits with an enum of 20 positive or neutral traits, e.g. brave,
curious, funny, kind, clever, creative, calm, cheerful, helpful, honest, adventurous,
caring, energetic, gentle, patient, playful, shy, silly, sporty, thoughtful.
Migrate existing characters' traits: keep matches, drop the rest. Update the builder
UI to pick traits as chips.

## 3. Catalog safety audit (a test that runs every time)
- Every person outfit combination covers the body: for kid and grown_up, top and
  bottom are required (a dress counts as both). No "none" top/bottom for people.
- Only robots and animals may have "none" for clothes.
- No weapons in extras except the magic wand; no brand logos or text on clothes.
- Cultural/religious items (hijab, turban) are available to every human body type,
  are never chosen by the offline "Surprise me" as a random joke combination with
  silly items (e.g. no hijab + clown-style extras), and are never mocked in labels.
- Any new catalog option needs a "reviewed: true" flag in the generator; the test
  fails on unreviewed options.

## 4. Input checks on the description (before anything goes to Meta)
Run in this order: length, personal info (existing), word list (existing), then new:
- Real people: block requests to base a character on a real, named person
  (classmates, family, teachers, celebrities). Use simple patterns locally ("look
  like my <relation/classmate> <Name>", "like <well-known name>") plus the AI
  classifier's real_person category when Meta is on. Friendly redirect:
  "Let's make up a brand-new character instead!"
- Rule-bending: "ignore the rules", "pretend", "without clothes", and similar →
  blocked with a gentle message.
- Body comments: requests about weight or body shape ("fat", "skinny") are not
  passed to Meta. The character is made without them, with a kind note:
  "Every character is awesome just as they are!"
All checks fail closed and are logged in moderation_log.

## 5. Meta prompt rules (prompts/builder_create.md)
State: audience ages 7–12; pick only from the provided options; keep characters
friendly and positive; never describe bodies, weight or attractiveness; never base
a character on a real person; names must be made-up and kind (no insults, no
real celebrity names); clothing is always everyday, costume or sports wear suitable
for school; follow-up questions are only about looks or personality, never about the
kid themselves.

## 6. Output checks (after Meta answers)
- Enums and body-type compatibility (existing), plus: people must be clothed (top +
  bottom or dress), traits from the enum, text lengths.
- Every text output through check_text (fail closed). Names also checked against a
  short list of famous names and real-person patterns.
- Anything failing is replaced with a safe default (default outfit for that body
  type, a name from the offline list, a generic friendly catchphrase) and logged with
  the reason. The kid sees a friendly result, never an error.

## 7. Tests
- Catalog audit (section 3) as a permanent test.
- A model that returns a "none" top for a kid → replaced with the default outfit.
- A model that returns an unknown trait or a free-text trait → dropped.
- Descriptions with a real person, rule-bending, body comments, personal info →
  handled as in section 4, nothing sent to Meta (fake client records no call).
- Unsafe name/catchphrase/intro line from the model → replaced and logged.
- Follow-up options that don't map to catalog choices → follow-up dropped.

Commit as "Character safety: parameter contract, trait list, catalog audit,
input/output checks", then STOP.
