# Lab: Lock at the bottom, guided Create character flow

Saved as given on 2026-11-08, with the lead line agreed for this prompt (CLAUDE.md decision 65) in front.

---

/builder/create and the character safety rules now exist. Build the screens below on
top of them; don't create a second endpoint. Where these prompts say /builder/describe
for the flow, use /builder/create.

Next: Lock at the bottom, and the guided Create character screens, built on the
existing POST /builder/create (decision 65; no second endpoint). Save this prompt to
docs/phases/lab-create-flow.md. Reply with a short plan and any deviations, then WAIT
for approval before coding.

## 1. Lock button at the bottom
- Move Lock out of the top of the Lab into a bottom action bar under the builder:
  [Undo] [Redo] ... "Saved automatically" ... [Lock character →] (primary, right).
- The bar is sticky at the bottom of the viewport on phones and small screens, so
  Lock is always reachable without scrolling. On wide screens it sits under the
  builder panels.
- When locked, the same spot shows [Unlock to edit] and the "Locked" status.
- The Lock job, progress UI and behaviour stay unchanged.

## 2. Entry points
- A "+ Create character" button at the top of the cast list in the Lab, and on empty
  cast slots on Home.
- Disabled when the cast is full (3), with "Your cast is full! Delete one to make room."

## 3. The flow
A full-panel, step-by-step screen in the comic style. The Story Buddy bubble asks each
question. Progress dots, Back on every step, and a "Skip, surprise me!" link that sends
only the answers given so far and jumps to the reveal.

1. "What kind of character is it?" Picture cards drawn with <Avatar>: Person, Robot,
   Cat, Dog, Bear.
2. People only: "How old is your character?" Little kid, Big kid, Grown-up,
   Grandparent. This is the character's age, never the kid's own.
3. People: "What shape is their face?" Four cards drawn on the character so far.
   Robots get the 3 robot head shapes. Animals skip this step.
4. "Tell me about your character!" Text box (mic-styled, text only): "What do they
   look like? What do they wear? What are they like?", with 3 tappable example chips.
   Optional (Skip). On Next, call /builder/create with all answers so far, with a
   "Meta AI is designing your character…" loader. Safety blocks and the body-words
   note show inline under the box, never as a toast.
5. If the response has a follow_up: show Meta's question in the buddy bubble with its
   options as tappable cards (drawn with <Avatar> where the option is a look), plus
   "Skip". Sending an answer calls /builder/create again with follow_up_answer.
6. "What's their name?" Name ideas as chips plus a text box (safety-checked).
   Then role cards (Hero / Sidekick / Friend), pre-selected from role_suggestion.
7. Reveal: "Ta-da! Meet <name>!" The character pops in (confetti; none with reduced
   motion), says intro_line in a speech bubble, and shows traits and catchphrase.
   A "Designed by Meta AI" badge (or "Made by the offline helper"). Two buttons:
   [Change something] → opens the builder on the new character;
   [Lock <name>] → starts the normal Lock flow.

## 4. Behaviour
- The character is created (POST /characters) only at the reveal. Abandoning the flow
  leaves nothing behind. Answers live in local state; a refresh mid-flow starts over.
- The "Designed by Meta AI" badge stays on the character's card in the Lab until the
  kid edits it.
- Unmatched wishes from the response show as a friendly note on the reveal.
- Phone width: cards in a 2-column grid, buttons ≥ 44px. Each step is a labelled form
  group, and focus moves to the new question for keyboard and screen-reader users.
- A dev-only indicator in the profile menu shows which helper is active (Meta AI or
  offline) and whether the last Meta call succeeded. Document in CLAUDE.md and the
  README that the demo runs with LLM_PROVIDER=meta.

## 5. Tests
- Vitest: step skipping (robots skip age, animals skip age and face shape); the
  follow-up step appears only when follow_up is present; nothing is created before
  the reveal; cast full disables the buttons; the Lock bar renders at the bottom.
- Browser check on throwaway test servers with a fake Meta stand-in: create a
  grandparent with an oval face from "a cosy knitted jumper, round glasses and a big
  smile", answer the follow-up, pick a name idea, choose Friend, see the intro line on
  the reveal, and Lock from the reveal. Then create a robot (skips age and uses robot
  heads), try a description with a phone number (inline block), and check the full
  cast disables the button. At phone width, check the Lock bar stays visible while
  scrolling.
- At the end, ask me before one real run with my Meta key.

Commit as "Lab: Lock at bottom, guided Create character flow", then STOP.
