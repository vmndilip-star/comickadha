# Phase 7: fixes from the live test, 12 starter characters, longer comics

Saved as given on 2026-11-22. The prompt arrived in two messages: the first ended mid-sentence in Part C (the safety bullet), and the rest of Part C followed with the plan's approval. Both are below as given.

---

Build the next round for Comickatha in three parts:
  A) fixes from the live test
  B) 12 starter characters
  C) longer comics

First save this prompt to docs/phases/phase-7.md. Then reply with a short plan for all
three parts and WAIT for my OK.

Rules:
- Do the parts in order A, B, C. Run all 9 checks after each part.
- Back up api/storage before any database change.
- Test only on a throwaway API and web server.
- Ask me before any paid Meta or Muse call.
- Don't commit until I ask. Then make one commit per part.

==================================================================
PART A: FIXES FROM THE LIVE TEST ("The Mango Mystery")
==================================================================

A1. SHOUT TEXT SPILLS OUT OF THE STARBURST
    Fix: fit shout text inside the inner part of the burst, in the Reader and in the
    server lettering (final.png and the PDF). If it still doesn't fit, make the burst
    bigger.
    Test: a long shout stays inside the burst.

A2. DEMO PLACES ARE PLACEHOLDER ART (white ovals, "MOCK" badges, name labels)
    Fix: add "uv run python -m app.seed --paint" to repaint the 3 demo places with Muse,
    through the normal place checks. It refuses to run when IMAGE_PROVIDER is mock. Normal
    seeding and tests keep using the mock. Add it to the README.
    Ask me before running it for real (about $0.03-0.06).

A3. THINKING POSE WITH A TALK BUBBLE
    Fix: the thinking pose only goes with a think bubble or no bubble. Add the rule to the
    planner prompt, check_panels and the offline planner. If a kid picks the thinking
    pose in the editor, switch that character's bubble to think and say so.
    Test: the rule in all three places, and the editor switch.

A4. A NEW KID CAN'T START A STORY
    Fix: in the Studio, when a picked character isn't locked, show a "Lock <name> now"
    button that locks them right there with progress, so the kid stays in the Studio.
    Keep the Lab link as a second option.
    Test: both states, and that locking from the Studio unblocks planning.

A5. REPETITIVE DIALOGUE
    Fix:
    - Use each catchphrase at most once per comic, across all scenes.
    - Don't start a character's lines the same way every time (Robo-Tik said "Beep boop"
      in every line).
    - Give characters in the same panel different reactions.
    Add these to the planner prompt, check_panels (sent back in the existing retry) and
    the offline planner.
    Test: the new checks.

A6. LONG WAITS FEEL STUCK
    Fix: while planning and while Story Buddy thinks, rotate short fun lines every 3-4
    seconds ("Sharpening pencils...", "Asking Mira for ideas..."). Use only cast names,
    never other kid text. No animation for reduced motion.
    Test: the lines rotate and use cast names.

A7. CHARACTER LAB CAST LIST SHOWS LETTERS (M, R, R)
    Fix: show each character's face there, like on Home.

==================================================================
PART B: 12 STARTER CHARACTERS
==================================================================

Goal: a kid can make a story straight away, without designing anyone first.

How they work:
- Ready-made, already locked, and the same for every kid.
- They don't count toward the kid's 3 own characters.
- Read-only. Editing, deleting, locking or unlocking one gives a 409: "Starter
  characters can't be changed. Tap Make it mine to get your own copy!"
- "Make it mine" copies a starter into the kid's own cast as an editable draft. That
  copy does count toward the 3 (cast_full still applies).
- Each is locked with a frozen look (CharacterVersion, version 1), so comics using them
  never change.
- Store them in the character table with a flag (e.g. starter=True, added by
  add_missing_columns with the startup backup). Use fixed uuid5 ids, create them in the
  seed (idempotent), and draw their sheets offline with the builder (free).

Where they show up:
- Character Lab: a "Starter characters" section under the kid's own cast. A starter opens
  in the locked view with "Make it mine".
- Studio cast picker: "Your characters" first, then "Starter characters".
- Home: the kid's own cast, plus a "Meet the starter cast" link.
- The Reader, covers and PDF treat starters like any other character.

Cast size: a comic can now have up to 5 characters (own and starters mixed). A panel still
holds at most 3 (left, middle, right). Update the planner, check_panels and the picker.

The 12 (pick the parts and colours from the catalog):
  Zara       kid        hero      brave, adventurous   "Let's go, go, go!"
  Leo        kid        sidekick  funny, silly         "Did somebody say snacks?"
  Aisha      kid        friend    clever, kind         "Don't worry, I have a plan!"
  Arjun      kid        hero      curious, creative    "Ooh, what does this button do?"
  Kofi       kid        sidekick  sporty, cheerful     "Race you there!"
  Mei        kid        friend    creative, calm       "Let me draw you a map."
  Nana Rose  grown-up   friend    caring, patient      "Cocoa fixes everything."
             (grandparent, grey or white hair)
  Mr. Hari   grown-up   friend    thoughtful, honest   "Every mistake is a clue."
  Pixel      robot      sidekick  clever, playful      "Calculating... fun level: maximum!"
  Whiskers   cat        friend    curious, playful     "Purr-fect!"
  Biscuit    dog        sidekick  cheerful, helpful    "Woof! Follow me!"
  Barnaby    bear       friend    gentle, shy          "Um... can I come too?"

Looks: a spread of skin tones, hair and outfits. Two characters wear a hijab or a turban
with ordinary clothes, never with silly items (decision 68). Don't tie looks to
stereotypes.
Every starter must pass check_name, the local checks on its catchphrase, the 20-trait list
and the catalog audit. Add a test that checks all 12.

==================================================================
PART C: LONGER COMICS
==================================================================

Panel counts: Short 4, 6, 8 and Long 10, 16, 20, 25, 30. The default stays 6.

Planning (one Meta call can't write 30 panels; 4 panels already used up to 4,685 tokens):
- Scenes: about 1 scene per 4 panels, at most 8. Keep a clear beginning, middle and end.
- Plan panels one scene at a time, not in one call. Each scene's share of panels adds up
  to the total, and each scene's plan gets check_panels. Run a few scenes at once (cap
  it). Put the limits in ai_limits.
- Show progress ("Planning scene 3 of 7...") and show each scene as soon as it's ready
  (together with A6). Propose how, e.g. making plan-panels a job with SSE like Make my
  comic!
- The offline planner must handle every length without repeating itself: vary poses,
  expressions and positions, and use narrator links between scenes.
- Safety: batch the classifier (about 20 fields per call), because a 30-panel plan can
  have about

(The first message ended here. The rest of Part C, as given in the second message:)

PART C (continued)
Screens:
- Studio step 3: panel cards grouped by scene, and a kid can collapse a scene.
- Reader: long comics shown as pages of 6 panels with page numbers, matching the PDF.
  Lazy-load the panel images.
- Check Make my comic! and the PDF with 25 and 30 panels (30 panels = 6 PDF pages).
- If 600 characters is too short a synopsis for long comics, propose a higher limit.

Real calls (ask me first): plan one 16-panel and one 30-panel comic with Meta. Report the
time, tokens and cost, and any cut-offs or offline fallbacks. Include one real plan that
shows the A5 rules working.

TESTS (besides the ones you listed)
- Starters: seeded and locked; read-only (409 "starter"); not counted toward 3; Make it
  mine copies one and the copy counts; a 5-character comic plans with at most 3 per panel;
  all 12 pass the checks.
- Long comics: every panel count plans exactly that many panels (fake Meta and offline);
  scene shares add up; a refresh during planning reconnects and keeps planned scenes;
  classifier batching works, and an outage still fails closed; a 30-panel comic generates
  and its PDF has 6 pages.

Not in this round: drawing the story's objects (squirrel, mango, table). That's 6b.

DONE MEANS
- All 9 checks pass after each part.
- One line per item: what changed and which test covers it.
- Before/after screenshots for A1, A4, A6 and A7.
- A kid can open the Studio, pick 2 starter characters, choose 20 panels and get a planned,
  drawn comic and PDF without designing anyone, with progress the whole way. Include a
  screenshot of that 20-panel comic.
Then stop. Make one commit per part (A, B, C) only when I ask.
