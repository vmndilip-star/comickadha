# Comickatha: decision log

Every decision, in order, moved out of CLAUDE.md unchanged in Cleanup 1 (2026-11-22).
CLAUDE.md lists the ones still in force. Add new decisions at the end, numbered on.

## Decisions (approved 2026-11-02)

1. Mock-first: `LLM_PROVIDER=mock` (no LLM at all: `app.state.llm` is `None` and each helper answers offline; there is no `MockLLMProvider` class) and `MockImageProvider` are the defaults. The app must run end to end with zero keys. (Corrected 2026-11-22.)
2. Lock and generate return `202 {job_id}`. Progress streams from `GET /api/jobs/{id}/events` (SSE), replayed on reconnect. (Corrected 2026-11-22: re-drawing a panel, `POST /panels/{id}/render` or a characters change in `PATCH /panels/{id}`, is synchronous and returns the panel; there is no redraw job kind yet.)
3. The character manifest has a head box per body cell, plus a tweakable offset. (Corrected 2026-11-22: the compositor never pastes faces or reads the manifest; it draws every panel character from the pinned avatar spec, in its pose and expression. Only the Lab pastes, and only for image-model sheets, decision 87.)
4. Panels are `art.png` (background + characters) plus bubble data. The Reader draws bubbles as HTML; the compositor bakes `final.png` for covers and the PDF (thumbnails come from `art.png`, decision 63).
5. Re-locking bumps `sheet_version` and keeps old files. Deletes are soft. Old comics never change.
6. The planner runs twice: `plan-scenes` (step 1→2), then `plan-panels` (step 2→3). Kids edit scenes in between.
7. Places are created in `PlaceDialog` (from Home and Studio step 2). There is no places route.
8. Background removal: the image model draws on flat magenta `#FF00FF` and Pillow keys it out (no rembg).
9. PDF via Pillow. Web fonts are self-hosted via `@fontsource` so the demo works offline.
10. Safety fails closed: blocklist, plus an LLM classifier when a real LLM is set. Verdicts go to `moderation_log`. Seeded demo content must pass the mock check.
11. Extra tokens from the boards: sun-tint `#FFE9A8`, coral-tint `#FFD0C2`, sky-tint `#DDF0FC`, coral-light `#FF8A6B`, rule `#EFE6D3`, sun-dot `#E8B800`.
12. The Character Lab adds a role pill row and hair-colour swatches (not on the board). Traits max out at 3.
13. Each panel in the plan carries a one-line `beat`, shown on `PanelPlanCard`.
14. Only locked characters can be in a comic that gets made; Studio step 3 disables "Make my comic!" until the cast is locked.
15. Phase 6 providers: Claude `claude-sonnet-5-5` for planner, buddy and safety; Gemini's image model as primary and OpenAI's image API as secondary. Check current model names at Phase 6. (The image half is superseded by decisions 81-82: Phase 6 uses Meta's Muse Image. Claude stays an option for 6b.)

Phase 2 (2026-11-03):

16. Schema additions beyond the agreed list: `background.tint` (placeholder colour), `comic.deleted_at` (soft delete), `panel.beat` (decision 13). `panel.scene_id` is nullable: removing a scene keeps its panels.
17. Lock/unlock only flip `status` in Phase 2 and return the item. Phase 3 turns them into `202 {job_id}` jobs that bump `sheet_version`. Seeded locked characters get placeholder sheets + manifest (v1) from `MockImageProvider`; seeded places get a placeholder reference image.
18. Studio step 3 shows the stored panel plan; "Make my comic!" stays disabled until Phases 4 and 5 add the planner and drawing (done in Phase 5).
19. New scenes and bubbles get client-made ids, so ids do not change after saving.

Before Phase 3 (2026-11-03):

20. Secrets: `META_API_KEY` moved to `.env`; `.env.example` has placeholders; a pre-commit hook runs `scripts/check_secrets.py`.
21. Deleted characters and places stay resolvable for comics (`deleted: true`), see Architecture.
22. Phase 1 and Phase 2 are separate commits. Phase 1 was rebuilt from the session record and verified with the same 40 browser checks before committing.

Phase 3 (2026-11-03), superseding 17:

23. Lock is a job: `POST .../lock` returns `202 {job_id, kind, target_id}`; `last_job_id` is stored so the web app reconnects after a refresh. Locking while drawing returns the same job; a locked item → 409 `already_locked`; unlock, edit or delete while drawing → 409 `busy`; a failed job sets status `failed` and Lock can be tapped again.
24. `ImageProvider` keeps the exact `generate(prompt, size, seed, reference_images)` signature; the mock gets everything from the prompt text.
25. Head offsets are edited with `PATCH /characters/{id}/heads/{pose}` (allowed while locked). For image-model sheets the Lab pastes the chosen face onto the chosen pose's head box (`src/lib/sheet.ts`). (Corrected 2026-11-22: the compositor has no such maths and never reads offsets, so they change only the Lab view, not comics.)
26. Places that fail to paint show "Couldn't paint"; there is no retry button on the tile yet (describe the place again). Superseded by decision 90: draft and failed places have "Paint it again".

Phase 3.5 (2026-11-03):

27. Characters are built Bitmoji-style from the SVG parts library in `shared/avatar/` (art generated by `build_catalog.py`, signed off from the contact sheets). Meta's model API suggests parts; it never draws.
28. Builder characters are drawn directly in any pose with any expression, so ¾ poses get proper ¾ faces. Manifests keep head boxes so nothing else breaks; pasting a face onto a head box stays only for `SHEET_PROVIDER=image` sheets.

Phase 3.5b API (2026-11-07):

29. The character spec is the avatar spec; `role` and `kind` move into it (`kind` derives from `body_type`: cat, dog and bear are `animal`). PATCH replaces the whole spec. The spec models forbid unknown keys so an old-style partial spec is a 422, not a silent reset to the default kid.
30. `SHEET_PROVIDER=builder` is the default; the image pipeline stays behind `SHEET_PROVIDER=image`. Seeding draws without the reveal pause.
31. The builder helper's safety runs on the kid's words and on the model's words, and fails closed: if the classifier can't answer, the words never reach Meta and the offline helper answers. Lock and place checks stay word-list only for now (a classifier outage would block every Lock).
32. A drawing over 5 MB is a 413 at any size (checked on the base64 length before decoding), so the request schema has no length cap of its own.
33. The API commit leaves `web/src/types/api.ts` as it was; it is regenerated, and the web fixed to match, with the web half of 3.5b.

Phase 3.5b web (2026-11-07):

34. The web twin is checked by golden files written from Python (SHA-256 of 545 SVGs plus two full samples, every head box, `normalize` cases), not by a shared implementation. Vitest 3.2 (Vite 6 / Node 20.15).
35. The old `CharacterFace` placeholder and `LookPanel` are gone; every character is drawn from its avatar spec.
36. Options a body type can't wear stay in the trays, dimmed; tapping one makes the buddy say why (`whyNot`), so the rule is learnt, not hidden.
37. The parts catalog ships in the JS bundle (now 1.12 MB minified, 208 KB gzipped as of 2026-11-22, so Vite warns about chunk size); split it out if load time matters.

Lab drag-and-drop (2026-11-07):

38. `@dnd-kit/core` 6.3.1 (stable, React 19 compatible; `@dnd-kit/react` is still 0.x). Mouse and touch sensors rather than pointer sensors, so only touch waits 150 ms.
39. Paint on the head colours the hair whenever there is hair (even under a hat); hats are painted there only on bald heads, robots and animals, or with a tap in the Hats tab. Body paint is the top (from the back: cape, then backpack). Paint from another palette snaps to the slot's nearest swatch, and the words name the colour it became.
40. Only the sticker trays auto-scroll while dragging (sideways). The page never does: it would slide the stuck preview away from the finger.
41. Stickers carry a scroll margin the height of the stuck preview in one-column layouts, so focus and scroll-into-view never land them under it.
42. Hair can't be dragged off (tap Bald instead); kids' and grown-ups' clothes can't either (no "none" option for them), and the buddy says so. No sounds.

Phase 4 (2026-11-07):

43. The LLM is the existing `MetaLLMProvider` (`META_MODEL=muse-spark-1.3`), reached only through `services/ai_guard.py`; the offline mock stays the default.
44. The planner reads the saved comic (the web app flushes autosave first) instead of taking the story in the request.
45. Kid edits are tracked with nullable `scene.edited_at` / `panel.edited_at` (added on startup, after a backup).
46. Unlocked cast members are left out of a plan with a note, not refused, as long as one cast member is locked.
47. "The first panel sets the scene, the last resolves it" is in the prompt and the offline planner, not the validator.
48. Full-name detection only catches self-identifying phrases ("my name is Priya Sharma"), so made-up character names aren't blocked; the Meta classifier's `personal_info` covers more.
49. Bubble boxes are recomputed on every panel save (kids can't move bubbles until Phase 5). Superseded in Phase 5: a bubble the kid moved keeps its box (`fixed: true`); only its tail is re-aimed.
50. All prompts live in `app/prompts/` (the Lab helper's and the classifier's were moved, wording unchanged) and are checked at startup.
51. Synopsis safety in two parts: autosave runs the instant local checks (draft still saved, message shown right away); plan-scenes runs the full check with the classifier, so nothing reaches Meta unless it passes.
52. A plan from the offline fallback shows "Our helper was resting, so here's an offline plan" with Try again.
53. Scenes reorder with up/down buttons only; drag with `@dnd-kit/sortable` is a nice-to-have if time is left.
54. Backups go to `api/storage-backups/` (gitignored), the newest 5 kept.
55. (Approved 2026-11-07, built in Phase 5.) During a full Meta outage the offline planner takes over instead of blocking. The local checks (personal info + word list) still run and still block. Text that only passed the local checks is marked "not yet AI-checked"; the classifier re-checks it in the background once Meta answers again. Sharing and PDF export wait until that check passes. Nothing unchecked is ever sent to Meta. With `LLM_PROVIDER=mock` there is no classifier, so the local checks count as the full check.

Phase 5 (2026-11-07):

56. Facing: in panels with 2–3 characters, only the plain standing `front` pose turns toward the middle (`three_quarter_right` on the left, `three_quarter_left` on the right). `point` is mirrored for the right-hand character so the arm aims at the middle. Other action poses keep their front view; a lone character, or anyone in the centre, stays as planned.
57. Fonts: Bangers and Nunito TTFs (SIL OFL 1.1) in `api/assets/fonts/` with their licence files, copied into the Docker image; credited in the README.
58. One PDF page size, 8.27 x 11 in (A4's width, Letter's height); the README says "Prints on A4 or Letter. Use Fit to page."
59. "Share with a grown-up" is hidden for now (future feature, see below).
60. Pinned looks live in a `character_version` table (not just manifest.json), frozen on lock, seed and a startup backfill (with a backup first).
61. The character cell is 0.64 of the panel height (not taller), so bubbles fit above the heads; speech bubbles slide down toward the heads to keep tails short.
62. Generate requires a pinned look for every panel character (what drawing needs) and Studio's button requires them to be locked now (decision 14). Try again and Reader edits of an old comic still work after a character is unlocked, because their look is pinned.
63. The Reader letters bubbles as HTML with the same size steps as the server's Pillow lettering; final.png is only for covers and the PDF, baked lazily.
64. A blocked bubble (local checks at draw time) blocks only its panel; fixing the words in the Reader re-draws that panel straight away.

Character safety (2026-11-08):

65. `/builder/create` is an API endpoint with tests in this commit; the guided Create character screens (and moving Lock to the bottom) come in the next prompt and build on it. **Next prompt's lead line:** "/builder/create and the character safety rules now exist. Build the screens below on top of them; don't create a second endpoint. Where these prompts say /builder/describe for the flow, use /builder/create."
66. Follow-up answers are any catalog choice valid for the body type (no signed token): each option maps to one catalog choice, so free text can never get in.
67. A dress still has a bottom (no art changes); picking a dress sets leggings in a matching, darker colour.
68. "Surprise me" may pick hijab and turban at random with ordinary clothes (superhero suits and capes included), never with silly items.
69. Traits are a fixed list of 20 positive or neutral traits (max 3). `grumpy` and `loud` were dropped (the offline word "loud" now means energetic); Raju's seed trait is `energetic`.
70. Grandparents get grey or white hair from two new hair palette entries (no new art).
71. Body words are removed, not blocked; real people and rule-bending are blocked. All description checks also guard `/builder/describe`.
72. Moderation verdicts gain `filtered` (body words removed) and `replaced` (an output swapped for a safe default).

Lab create flow (2026-11-08):

73. Lock moves to a bottom action bar under the whole Lab layout (sticky until `lg`); Undo/Redo move there too, and the duplicate save status leaves the details column. `LockToggle` is gone.
74. The create flow is its own route inside the page shell (leaving it is just navigating away); the character is saved only at the reveal.
75. `/builder/create` gains `look` (only with `follow_up_answer`) and `role_suggestion`; the server guarantees an answer changes only its own choice, whatever the model returns. The offline seed no longer includes the answer.
76. Name check on `POST /characters` (same rules as create); `designed_by` stored on the character and cleared by the first look edit; only Meta-made characters show the card badge.
77. Wording is honest offline: "Meta AI is designing…" and "Designed by Meta AI" only when Meta answered.
78. The dev-only helper indicator lives in the profile button's menu (development builds only), fed by `last_call` on `/builder/info` (no prompts or keys).
79. Vitest stays dependency-free: pure rules and store tests (API mocked), and components rendered with `react-dom/server`.
80. (Limits now in `services/ai_limits.py`, re-measured in decision 83.) Real runs with `muse-spark-1.3` (2026-11-08): the model thinks before it answers. The safety classifier used ~450-500 completion tokens (its old 300 limit cut every verdict off, so all Meta features fell back offline); it now gets 1,500. A character design used 2,000-2,500 tokens and ~15 s; it gets 6,000 and a 60 s per-call timeout (`complete_json(..., timeout=)`). A reply cut off at the limit raises `LLMError` and shows as `OutOfTokens` in the dev menu. Other Meta calls (Story Buddy 600, planner 1,200/3,000, builder describe/surprise/ideas 1,024) may need the same headroom: check in Phase 6.

Phase 6a (2026-11-22):

81. Meta is on for the demo: `.env` gets `LLM_PROVIDER=meta`, `META_MODEL=muse-spark-1.3`, `IMAGE_PROVIDER=muse`, `META_IMAGE_MODEL=muse-image-1.0` (with `META_API_KEY`). Fail closed by configuration: `IMAGE_PROVIDER=muse` without `LLM_PROVIDER=meta` stops startup, because real pictures need the classifier and the image check. The image provider is built first in the lifespan (with the LLM), so a bad setting stops startup before any backup, migration or seed. Mocks stay the defaults; seeding and tests use them.
82. Muse Image (`muse-image-1.0`), measured 2026-11-22 with 6 pictures (~$0.06): responses are `b64_json` WebP (`output_format: webp`, `background: opaque`, `revised_prompt: null`) with a `usage` block (e.g. 18,632 input / 2,071 output tokens for one 4:3 picture; Meta's docs price it per picture, $0.01, not checked against billing). `size` only picks the aspect: 1024x768 and 1600x1200 both came back 1792x1344; 1024x1024 came back 1600x1600 (so up to 1792 px, not 1600). Latency: 18.8 s for a picture, 10-11 s for a one-reference edit, 17.1 s for a three-reference edit, about 21-25 s for a whole place lock with the image check. `seed` is refused (400 "unknown parameter `seed`"), so retries just draw again. `images.edit` through the SDK fails (400: Meta wants `image[0]`, `image[1]`... not `image[]`); a multipart post with indexed fields works with 1 and 3 input images (6b needs 2-3). Restyle test for 6b (a 1600x1200 `art.png` plus two "3D toy" portraits made from builder front renders): both characters stayed recognisable, in the same order and poses, and the mock place's label text was dropped, but the characters came out ~30% larger with feet lower and one head ~5% of the width nearer the middle, and Raju gained backpack straps; so bubble tails can't assume head positions survive a restyle exactly (6b should re-find heads or keep restyles conservative). Places in "Sunday Funnies" style matched the 2D characters; a pink and purple sweet shop was not mistaken for magenta (its pinks have green ~130, outside the key's 80), so `_valid_place` keeps tolerance 80.
83. Meta token limits, measured 2026-11-22 (completion tokens, slowest call) and set to ~2x the largest completion with a timeout ~2x the slowest call (min 20 s), all in `services/ai_limits.py`: describe 2,039-2,681 (17.7 s) → 5,500 / 40 s; surprise 2,488-2,834 (19.3 s) → 6,000 / 40 s; ideas 942-1,172 (6.8 s) → 2,500 / 20 s; from-drawing 1,957-4,352 (34.2 s) → 9,000 / 70 s; classifier 364-1,948 over 53 calls (12.7 s; more than decision 80's 450-500 because planner and Buddy checks now carry more fields) → 4,000 / 30 s; image check 472-654 (6.0 s) → 1,500 / 20 s; Buddy idea 1,095-1,567 (9.6 s) → 3,200 / 20 s, spelling 1,125-1,779 (11.7 s) → 3,600 / 25 s, scene titles 919-1,252 (7.5 s) → 2,600 / 20 s; scenes 2,020-2,987 (17.1 s) → 6,000 / 35 s; panels 3,403-4,685 (22.2 s) → 9,500 / 45 s; create unchanged (6,000 / 60 s, decision 80). The old limits (1,024 / 600 / 1,200 / 3,000) cut off nearly every describe, surprise, from-drawing, Buddy and planner reply, which silently went offline. No reply was malformed JSON in these runs, so the Guard's retry rule is unchanged (the docs now say what it does). Measuring cost about $0.50 in text and vision calls ($1.25 / $4.25 per million input / output tokens).
84. Nothing unchecked goes to Meta, checked where it is sent (not at lock): `services/kid_fields.py` gathers every kid-written field a prompt includes, built from the same context object as the prompt (`story_planner.planner_fields`, `story_buddy.buddy_fields`), and checks them in one classifier call (`check_story`). A block is a 422 `unsafe` naming the character, place or field; an outage means offline only (decision 55). This covers cast names and catchphrases and places locked while offline. The Lab helper also checks the current catchphrase, and Create character the name. The full list is under "What each Meta prompt carries". (The plan review said Story Buddy sends the synopsis: the code doesn't, so its fields match its prompt.) (Places whose words fail are left out instead of blocking: decision 89.)
85. Place lock: the classifier runs on the name and description only when the picture will come from a real image model (`IMAGE_PROVIDER=muse`), because only then do the words leave the machine at lock. An outage sends nothing: 503 `not_checked`, the place stays as it was. Character locks and mock-place locks stay local-checks only (decision 31: an outage shouldn't block every Lock).
86. Pictures out: every picture from a provider that isn't the mock is checked by the vision model (`META_VISION_MODEL`, = `META_MODEL`; confirmed it reads images) before it is saved or announced. One retry after a block, told "no signs, letters or logos" when the block was for writing; both verdicts are logged; an outage fails the job at once; nothing is saved unless a picture passes. Mock pictures are drawn locally and carry the place name as text, so they aren't sent to the checker (it would block every one).
87. The Lab draws a locked builder character live from the frozen look (`<Avatar spec={manifest.spec} pose expression>`), as panels do; image-model sheets keep the pasted face. Confirmed in headless Edge on a throwaway server: before, ¾, run and sit poses showed a front face pasted over a turned head.
88. (Superseded by decision 90.) Places had no Lock-again button in the web app (decision 26).
89. A locked place whose name or description doesn't pass the checks where a prompt is sent (the local checks, or the classifier) is left out, like an unlocked cast member (decision 46): out of the Meta prompt and out of the offline plan (the checks said its words aren't OK), with `left_out_places` on `ScenesPlanned` / `PanelsPlanned` for the note ("Delete it and describe a new place"). Story Buddy leaves such a place name out of its prompt too. A scene at a left-out place is a 422 on that scene in plan-panels; with no usable place left, plan-scenes is a 409 `needs_locked` naming them. Panels already drawn stay as they are. A classifier outage is never a block: places that passed the local checks stay in, the plan goes offline (decision 55) and there's no note. Blocking would have left the kid stuck: locked places can't be edited.
90. Place tiles get "Paint it again" (draft or failed: `POST /backgrounds/{id}/lock`) and Delete (any place, with `ConfirmDialog`; soft, so comics keep it, decision 21). The place error messages now say "Tap Paint it again". No Unlock or edit yet: panels store only `background_id`, not a place version, so repainting a locked place would change old comics the next time a panel is redrawn (breaking decision 5). See Future features.

Cleanup 1 (2026-11-22):

91. The one-time startup migrations are gone: `app/avatar/migrate.py` (pre-3.5b specs, traits off the 20-trait list), `db.has_old_character_specs`, `looks.needs_backfill` and `looks.backfill_versions`, with their tests. A read-only check of a copy of `api/storage/comickatha.db` found no old spec, no off-list trait and no locked version without a frozen look. `add_missing_columns` and the startup backup stay (general mechanisms). A database from before Phase 5 would now need those migrations from git history (`316dde3` and earlier).

92. The image-sheet pipeline is gone (supersedes decisions 28 and 30): `SHEET_PROVIDER`, `ImageSheets` and its batching, validation and prompt (`prompts/character_sheet.md`), `KnowsHeadBoxes`, the mock's figure drawing, `imaging.slice_grid` / `estimate_head_box` / `alpha_box`, head offsets (`PATCH /characters/{id}/heads/{pose}`, `HeadOffset`, `HeadBox.offset`, `HeadPositionEditor`, `faceOverlay`, `applyOffset`) and `Health.sheet_provider`. Comics never used image sheets (the compositor draws every character from its pinned spec), and 6b restyles pose drawings or whole panels instead. `BuilderSheets` is the only sheet provider. The live database still has two manifests with `renderer: "image"` (Mira and Raju, from Phase 3; both drafts now), so the manifest schema still reads them, and the Lab draws such characters live from their locked spec.

93. The profile button opens a menu in every build, with a "Grown-up" section: "Drawing uploads: on/off" and "Turn off drawing uploads" while consent is on (`DELETE /me/drawing-consent`, no times-table check: taking the OK back is the safe direction). The helper info stays in development builds. The Lab's consent dialog now stores the profile it gets back, so the menu is right without a reload. Also in Cleanup 1: one copy of the option lists (`types/index.ts`, checked against `api.ts` both ways; `avatar/spec.ts` imports them), one `strict_object` JSON-schema helper (`services/strict_schema.py`; the 10 schemas sent to Meta compared byte-identical before and after), one `STORY_LABELS` (`services/recheck.py`), and `POST /backgrounds/{id}/unlock` removed (decision 90).
94. The Lab, Create character, Studio and Reader pages load on first visit (`React.lazy`, `web/src/pages/lazyPages.tsx`); the catalog stays in the main chunk because Home's avatars need it. First-load JS went from 1,118.85 kB (208.08 kB gzipped) to 964.05 kB (161.46 kB gzipped), 22.4% less, past the 15% bar set for keeping it.

Phase 7 part A (2026-11-22):

95. Shout bubbles have one starburst shape on the server and in the Reader (tips 1.16 x 1.44 of the bubble's half-size, valleys 0.82 of the tips; `lettering.BURST_*`, `lib/bubbles.ts` `SHOUT_OUTLINE`). Shout words fit the largest rectangle inside the valleys with a 5% margin (`SHOUT_TEXT_W/H` 0.639 x 0.7932 of the bubble), stepping 26 to 18 px; past that the burst grows taller (the layout, final.png, the PDF and the Reader all agree). The layout keeps a shout's spikes inside the panel, and `compositor.LETTERING_VERSION` (now 2) is part of `final_hash`, so every final.png baked with the old lettering re-letters itself on its next request.
96. `uv run python -m app.seed --paint` repaints the 3 demo places with the real image model through the normal place path (classifier on the words, Muse, the image check with one retry after a block), backing up `api/storage` first; it refuses `IMAGE_PROVIDER=mock`. Old panels using those places pick up the new pictures when redrawn (they're placeholder art; no place versions yet, decision 90).
97. Dialogue rules, in the planner prompt, `check_panels` (sent back in the existing retry, `story_planner.dialogue_problems`) and the offline planner: a character in the thinking pose has a think bubble or none; each catchphrase at most once per comic; the same first two words start at most 2 of a character's lines and never two in a row. "Different reactions in the same panel" is prompt advice only. The offline planner has several lines per beat type (`LINES`) and a `Voices` record, and falls back to a narrator caption rather than break a rule. In both editors, picking the thinking pose turns that character's talk/shout bubbles into thoughts (with a note), and talk/shout are disabled while they think (`lib/studio.ts` `withPose`, `blockedTypes`, `speakerPatch`).
98. Studio and Lab polish: a picked character who isn't locked gets "Lock <name> now" in the Studio (the same Lock job, with its progress; the Lab link stays second); the planning loader and Story Buddy show rotating fun lines every 3.5 s built from cast names only (`waitingLines`, `RotatingLine`, no slide-in for reduced motion, hidden from screen readers); the Lab cast list shows faces (`CastSlot`, `CharacterAvatar`).

Phase 7 part B (2026-11-22):

99. Starter characters: 12 ready-made characters, locked and the same for every kid (`app/starters.py`). They are character rows with `starter=True` (a nullable column added by `add_missing_columns`, so the startup backup runs first), owned by a fixed "starter cast" profile that `get_current_user` never picks (the table needs an owner). Fixed uuid5 ids, sheets drawn by the builder (free, offline) and a frozen look (CharacterVersion 1), so comics using them never change. `ensure_starters()` runs at every startup (demo data or not) and after `seed --reset`; it only adds what's missing and redraws a sheet whose files are gone. Looks follow decisions 68 and 70: a spread of skin tones and hair, Aisha's hijab and Arjun's turban with ordinary clothes, Nana Rose's white hair.
100. Starters are read-only: editing, deleting, locking or unlocking one is a 409 `starter` ("Starter characters can't be changed. Tap Make it mine to get your own copy!"). `GET /characters` lists the kid's own characters, then the starters (`starter: true`); only the kid's own count toward 3. `POST /characters/{id}/copy` (Make it mine) makes an editable draft copy in the kid's own cast, which counts (cast_full applies); only starters can be copied (422). Starter names and catchphrases go through the same pre-Meta checks as any cast member's.
101. Cast sizes: a kid has up to 3 own characters (`MAX_CAST`); a comic up to 5, own and starters mixed (`MAX_COMIC_CAST`); a scene up to 5; a panel at most 3 (`MAX_PANEL_CAST`: left, center, right). `check_panels` also wants each panel's characters from its own scene. The offline planner puts everyone a scene names on stage by taking turns, 3 at a time with the lead always in (`story_planner.on_stage`); the Meta prompts say the same.
102. Web: the cast store keeps the kid's own `characters` and the `starters` apart (`splitCast`), so slot counts and cast_full stay right. The Lab lists starters as face tiles under the kid's cast (`StarterGrid`) and opens one in the locked view with Make it mine (disabled with a note when the cast is full; the builder's locked note and the buddy point starters at Make it mine, and the stale "Locked · tap to edit" hint now says Unlock to edit); the Studio picker shows "Your characters" then "Starter characters" and stops at 5 with a hint; Home has "Meet the starter cast"; the Reader, covers and PDF need nothing new (comics already carry the characters they use).

Phase 7 part C (2026-11-22):

103. Comic lengths: Short 4, 6, 8 and Long 10, 16, 20, 25, 30 panels (the default stays 6). Scenes: 4→2, 6→3, 8→4, 10→3, 16→4, 20→5, 25→7, 30→8 (about one per 4 panels, at most 8, with a beginning, middle and end). Each scene gets an even share of the panels, earlier scenes first (`scene_shares`); more scenes than panels is a 422 on plan-panels.
104. Planning panels is a job (`panel_plan`, `services/plan_job.py`), followed over SSE like Make my comic!. The request still runs the quick checks and the full safety check on every kid word, then clears the panels the plan replaces (edited or drawn ones stay) and returns 202 (pressing it again returns the same job). The job plans parts (a scene, or runs of at most `PANELS_PER_CALL` = 8 panels of a big scene), `PLAN_PARTS_AT_ONCE` = 3 at a time; each part has its own `check_panels` (count, its scene's characters, its catchphrases), one retry and its own offline fallback (wrong twice is now the offline plan for that part, not a 422). Each part is saved the moment it's ready (`scene_planned`), with `progress` ("Planning scene 3 of 7…") and a `done` summary; `ComicRead.plan_job_id` lets a refreshed Studio follow the job again. A restart fails a plan job kindly and keeps the parts saved so far. Offline plans pause `PLAN_REVEAL_SECONDS` (0.3 s) per part so the Studio fills in.
105. The comic-wide dialogue rules with parts planned side by side: each catchphrase is given to one part beforehand (one the character is in: the fewest so far, then the earliest). Once every part is in, parts whose line openings clash across parts (a third use, or twice in a row) are asked once more with the openings to avoid, and `repair_dialogue` turns any line still breaking the rules into a narrator caption of the beat (or leaves it out if the panel already has one). Offline plans are made in one pass with one record of who said what, so the rules hold by construction.
106. The offline planner at every length: 30 filler beats (one per panel slot), the summary's moments spread from a scene's first panel to its last, no beat twice in a comic (a repeat becomes a filler), everyone but the lead reacting with their own pose and a different face, characters swapping sides every other panel, varied middle-scene summaries, and narrator links between scenes ("Later, at…", "Back at…" for a place the story returns to, "A little later…" at the same place).
107. The classifier checks at most `CLASSIFIER_BATCH` = 20 texts per call (a 30-panel plan has about 60); every batch must answer, or the whole check fails closed (`SafetyUnavailable`), as before.
108. Web: the panel count picker has a Short and a Long row; `store/studio.ts` follows the plan job (`followPlanJob`, one follow per job: the comic as saved, then the replayed events) and resumes it after a refresh; step 3 opens as soon as planning starts, with "Planning scene 3 of 7…", a bar and the A6 lines (`PlanProgressCard`), and the panels grouped by scene, each scene collapsible, with placeholders for panels still being planned (`panelsByScene`, `sceneShares` mirrors the server). The Reader shows longer comics as pages of 6 numbered like the PDF (page 1 is the cover), and panel images load lazily; 25 and 30 panels print as 6 PDF pages.

109. The synopsis limit is 1,000 characters for every comic (was 600; `MAX_SYNOPSIS`), so a 30-panel comic's 8 scenes have room; Story Buddy's spelling check takes the same. The title stays 60. SQLite doesn't enforce column lengths, so no migration (a Postgres database would need its column widened).

110. Token limits re-measured with long comics (one real 16-panel and one 30-panel plan, 33 calls, $0.42): 8 scenes took 5,464 completion tokens and 68 s (the old limit was 6,000 and 35 s), classifier batches up to 3,627 (limit 4,000), panel parts up to 5,711 and 33.7 s. New limits, about twice the largest seen: scenes 11,000 / 90 s, panels 11,500 / 70 s, classifier 7,500 / 45 s, and the image check 2,000 (the real `seed --paint` run reached 999 of 1,500) (`ai_limits.py`). No reply was cut off and no part fell back in those runs.

Docs (2026-11-22):

111. Phase prompts are no longer kept in the repo (`docs/phases/` is gone): `docs/decisions.md` and the git history are the record. `docs/character-safety.md`, the safety policy, stays.

## Phase history

The phase list as CLAUDE.md had it before Cleanup 1 (CLAUDE.md now keeps a shorter one).

- [x] 1. Scaffolding, compose, tokens, NavBar and the 5 pages as static UIs on mock data
- [x] 2. API models, CRUD routers, seed data; wire web to API
- [x] 3. Provider interfaces + MockImageProvider; jobs + SSE; character_sheet service (generate, slice, manifest); place images; Lock flow
- [x] 3.5 Character Builder: 3.5a parts library, rig and 16 poses; 3.5b API: avatar spec, migration, builder sheets, Meta helper, AI safety, `shared/` in the Docker image; 3.5b web: `<Avatar>` + golden-file parity tests, Lab builder UI, regenerated `api.ts`
- [x] 4. story_planner, Story Studio steps 1–3, Story Buddy, safety on story text
- [x] 5. Pinned looks, compositor, Make my comic! (generate job + SSE), Reader Read/Edit with draggable bubbles, final.png, covers, PDF export, decision 55 re-checks (awaiting review)
- [x] Character safety: `/builder/create` contract, trait list, catalog audit, input/output checks
- [x] Lab: Lock at the bottom, guided Create character flow (awaiting review)
- [ ] 6. Real LLM and image providers, Redraw panel, polish
  - [x] 6a. Meta on, measured token limits, Lab face fix, Muse Image places with the image check, kid words checked before every Meta prompt, blocked places left out of plans, Paint it again / Delete on place tiles (awaiting review)
  - [ ] 6b. 3D-look panels (Redraw panel) on Muse Image
