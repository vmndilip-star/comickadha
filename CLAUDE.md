# Comickatha

Web app where kids under 16 design characters and places, write a story, and get a comic.
Hackathon build: optimise for a working end-to-end demo and clean, easy-to-extend code. Don't over-engineer.

## Working agreement

- Build in the phases below. After each phase: run it, run the checks, summarise, then STOP for review.
- This folder is its own git repo. Never commit to or touch the parent `Assigment` repo.
- Commit only when asked. No secrets in code: `.env` is gitignored; `.env.example` is committed and holds placeholders only (`your-key-here`).
- Secret check: `.githooks/pre-commit` runs `scripts/check_secrets.py --staged` and blocks a commit that stages `.env` or anything shaped like an API key. Enable it once per clone with `git config core.hooksPath .githooks`. Scan everything tracked with `python scripts/check_secrets.py`.
- Keep this file current when decisions change.
- Save every phase prompt as given to `docs/phases/phase-N.md` before starting work on it (Phase 5 onwards).

## Run it (Windows PowerShell)

Prerequisites: [uv](https://docs.astral.sh/uv/) (downloads Python 3.11 itself), Node 20.15+, Docker Desktop (optional).
Commands are for Windows PowerShell 5.1, which has no `&&`: run them one line at a time, from the repo root.

```powershell
# One-time: install uv, then open a NEW terminal so it is on PATH
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# Terminal 1: API on http://localhost:8010
cd api
uv sync
uv run uvicorn app.main:app --reload --port 8010

# Terminal 2: web app on http://localhost:5173 (proxies /api and /media to the API)
cd web
npm install
npm run dev

# Or both in Docker (start Docker Desktop first)
docker compose up --build
```

- The API creates its tables and seeds the demo data on first start (SQLite at `api/storage/comickatha.db`, files in `api/storage/media/`).
- Reset to the demo data at any time: `uv run python -m app.seed` (from `api/`). It wipes the database and generated files, then draws the demo sheets and places again (a few seconds).
- Backups: before a startup migration (a missing column, characters still in the old spec format, locked sheet versions without a frozen look, or traits that aren't on the trait list) the API copies `api/storage` to `api/storage-backups/<timestamp>-before-migration/` (gitignored; the newest 5 are kept; the path is printed). By hand: `uv run python -m app.backup` (from `api/`).
- Testing in the browser: never use the dev servers on 8010/5173 or `api/storage`. Run a test API with `STORAGE_DIR` pointing at a throwaway folder (e.g. port 8021) and `API_PROXY_TARGET=http://localhost:8021 npx vite --port 5176`.
- On startup, characters saved before Phase 3.5b (old `{skin, hair_style, outfit, ...}` specs) are converted to builder specs, and traits not on the 20-trait list are dropped from characters and frozen looks (`app/avatar/migrate.py`).
- The builder pauses `BUILDER_REVEAL_SECONDS` (default 0.08) per cell so the sheet visibly fills in; the mock image provider waits `MOCK_DELAY_SECONDS` (default 1.2) per image (`SHEET_PROVIDER=image`, and places); Make my comic! pauses `PANEL_REVEAL_SECONDS` (default 0.4) after each panel so the Reader fills in visibly. Set 0 for instant.
- `RECHECK_SECONDS` (default 60; 0 turns it off) is how often story text saved during a Meta outage is re-checked (decision 55).
- Docker needs Compose 2.17+: the API image gets `shared/avatar/catalog.json` through the `shared` build context (`additional_contexts`). Plain `docker build` needs `--build-context shared=../shared`.
- On Windows, `uvicorn --reload` sometimes stops picking up changes after a reload. If the API serves old code, stop it and start it again.
- Settings: `Copy-Item .env.example .env`, then edit `.env`. Defaults need no API keys.
- The demo runs with `LLM_PROVIDER=meta` (plus `META_API_KEY` and `META_MODEL` in `.env`); `mock` stays the default, and tests always use it. In dev builds the profile button shows the active helper and the last Meta call (`/api/builder/info` `last_call`).
- Ports: API 8010, web 5173. The web dev server proxies to `API_PROXY_TARGET` (default `http://localhost:8010`), read from the shell or the repo-root `.env`; for a one-off: `$env:API_PROXY_TARGET = "http://localhost:8020"; npm run dev`. In Docker the API listens on 8000 inside the container, published as 8010.
- If the terminal shows conda's `(base)` and Python looks wrong, run `conda deactivate`. uv is set to `python-preference = "only-managed"`, so it should never pick up conda's Python.
- If PowerShell says `npm.ps1 cannot be loaded`, run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once.

## Checks

```powershell
# API (from api/)
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy app tests
uv run ruff check ../shared
uv run ruff format --check ../shared

# Web (from web/)
npm run lint
npm test           # Vitest: golden-file parity, builder rules, the create flow, Lab bar (src/**/*.test.{ts,tsx})
npm run build      # runs tsc -b (strict) first
```

The web avatar code (`web/src/avatar/`) is a TypeScript twin of `api/app/avatar/`. After changing the catalog or either side's avatar code, regenerate the golden file and run both test suites:

```powershell
# from api/
uv run python -m app.avatar.golden   # writes shared/avatar/golden.json (an API test fails if it is stale)
```

## Generated API types

`web/src/types/api.ts` is generated from FastAPI's OpenAPI schema. Never edit it by hand.

```powershell
# from web/ (needs uv; the API does not have to be running)
npm run gen:types
```

Run it after any change to `api/app/schemas/` or a router signature, then fix type errors and commit `api.ts`.
`src/types/index.ts` gives the generated schemas friendly names (`Character`, `Comic`, `Panel`, ...) and holds the option lists.

## Architecture

- `web/`: React 19, Vite 6, TypeScript (strict), Tailwind 4, React Router 7, Zustand 5.
  - Tokens: values live in `src/styles/tokens.css` (CSS variables); `tailwind.config.ts` maps theme names to them, loaded through `@config` in `src/styles/index.css`. Use theme classes (`bg-sun`, `shadow-card`, `rounded-card`, `border-3`, `font-display`). Raw hex is only for data colours (character and place tints).
  - Components by area in `src/components/{ui,layout,home,character,story,comic}`, pages in `src/pages`, routes in `src/routes.tsx`.
  - The Reader (`/comics/:id`) sits outside `PageShell` because it has its own `EditorTopBar`.
  - Data: `src/api/*` are typed fetch helpers (`client.ts` turns every error into an `ApiError` carrying the API's kid-friendly message). Zustand stores in `src/store` hold the data; `AppRoot` calls `loadAll()` once, and pages show `PageLoading` (comic-style skeleton, or a Try again card) until `useDataStatus()` is `ready`.
  - Autosave: store actions update the screen immediately and call `useSaveStore.schedule(key, job)`; the job runs 600ms after the last edit and sends the latest state. `editCounter()` stops a slow response overwriting newer typing. `SaveStatus` shows "Saving…" / "Saved automatically". Pending saves flush on `pagehide`, and mutating requests use `keepalive`.
  - Errors reach the kid as toasts (`toast.error(e)` → `Toaster`), never as raw messages.
  - API JSON is snake_case end to end (the planner and manifest contracts are snake_case too), so components use `studio_step`, `cast_ids`, `background_id`.
  - Avatars: `src/avatar/` twins the API's avatar code: `catalog.ts` (imports `@shared/avatar/catalog.json?raw`, parsed once), `rig.ts`, `compose.ts`, `spec.ts` (`normalize`, palettes, `fits`) and `builder.ts` (pure tap/drop rules: `applyPart`, `addExtra`, `toggleExtra`, `setColor`, `setBodyType`, kid-friendly `whyNot`; picking a dress also sets leggings in a matching, darker colour via `withLeggings`, tested in `builder.test.ts`). `compose.test.ts` checks every SVG, head box and `normalize` result against `shared/avatar/golden.json`. `@shared` is a Vite/TS alias for the repo-root `shared/` (dev server `fs.allow`, and Docker mounts it at `/shared`).
  - `<Avatar spec mode="pose|face" pose expression size>` draws a character from its spec (normalized first, so only palette hex reaches the SVG). `CharacterAvatar` shows the locked sheet's face cell, or the live avatar for drafts. Panels in the Reader draw each character in its pose.
  - Traits: `TRAITS` (`types/index.ts`) and `TRAIT_IDS` (`avatar/spec.ts`) are the 20 positive or neutral traits; `PersonalityPanel` shows them as chips, up to 3. `normalize` keeps listed traits once each (max 3) and the catchphrase, like the Python twin (golden cases cover it).
  - Lab action bar (`components/character/LabActionBar.tsx`): Undo, Redo (the preview keeps Ctrl+Z / Ctrl+Shift+Z), "Saved automatically" and Lock (or "Unlock to edit" with "Locked"), under the whole Lab layout. `sticky bottom-0` until `lg`, so Lock is always in reach on phones; stickers carry `scroll-mb-28` so focus never lands under it. The Lock job and `SheetProgress` are unchanged.
  - Create character flow (`/characters/new`, registered before `characters/:id?`; `pages/CreateCharacterPage.tsx`, `components/character/create/CreateFlow.tsx`): kind → age (people) → face shape (people: 4, robots: 3 heads, animals skip) → description (mic-styled box, 3 example chips, Skip) → follow-up (only if the helper asked; options drawn with `<Avatar>` via `choicePreview`) → name (idea chips + text box) and role cards (pre-selected from `role_suggestion`) → reveal (pop-in, confetti, intro line, traits, catchphrase, "Designed by Meta AI" or "Made by the offline helper", unmatched note, Change something / Lock <name>). Progress dots, Back on every step, "Skip, surprise me!" (designs with the answers so far if needed, then reveals with the first name idea and the suggested role), each step a labelled fieldset with focus moved to the question. Pure rules in `lib/createFlow.ts` (`stepsFor`, `requestFor`, `revealCharacter`...); `store/createFlow.ts` is the only part that calls the API: `/builder/create` on Next or Skip at the description step and again for a follow-up answer (with `look` = the character so far, and only `{target, value}`), and `POST /characters` only at the reveal (`designed_by` from the answer's source). Answers live in memory only; the page resets on mount and unmount. Safety blocks and the body-words note show inline (a name blocked at the reveal goes back to the name step). The loader says "Meta AI is designing…" only with Meta.
  - Entry: `CreateCharacterButton` ("+ Create character") at the top of the Lab cast list, on the Lab's empty state and on Home's empty cast slots; disabled with "Your cast is full! Delete one to make room." at 3. `CreateCharacterLink` is the store-free view (tests render it to HTML: zustand's server render reads a store's initial state). Cards show "Designed by Meta AI" while `designed_by` is `meta`.
  - Selectors must return stable values: `s.x ?? []` makes a new array every read and re-renders forever (use a module constant).
  - Character Lab builder (`components/character/builder/`): `LabBuilder` puts `BuilderPreview` (live avatar, Front/¾/Side/Back, undo/redo with Ctrl+Z / Ctrl+Shift+Z, `BuddyBubble`) beside `BuilderTabs` (Body, Face, Eyes, Hair, Hats, Outfit, Extras; 64px+ stickers and paint blobs, options that don't fit shown dimmed with a "no" badge). Two columns only when the stage is wide (container query); otherwise the preview sticks to the top above the tabs. `useBuilder` turns taps into results; `store/lab.ts` keeps per-character undo history of the look (personality and role are never undone) and the buddy message. Every tap is one undo step and autosaves through `useCastStore.update`. Locked characters show their sheet instead of the preview, and the tabs are disabled with an unlock hint. `BuddyHelper` calls `/api/builder/*` (describe, surprise, name ideas, from-drawing with the grown-up times-table check), applying answers as one undo step.
  - Story Studio (Phase 4): `store/studio.ts` runs the planner (`plan(comicId, 'scenes' | 'panels', startOver)`: flushes autosave, calls `/api/studio/{id}/plan-*`, applies the result; `confirm_start_over` opens "Start scenes/panels over?"), keeps the note for the last plan (offline fallback with Try again, kept panels, cast left out) and the Story Buddy reply. Step 1→2 and 2→3 show `PlanningLoader`; steps 2 and 3 are disabled until the cast has a locked character and there's a locked place (`LockedNudge`). Planned panels draw characters from their pinned looks (`lookFor(comic.looks, pc, character)` in `lib/comic.ts`, falling back to the current spec). `SceneRow` reorders with up/down buttons (drag via `@dnd-kit/sortable` is a nice-to-have), and edits place, cast and summary. `PanelPlanCard` draws each planned character with `<Avatar>` in its pose and expression over the place thumbnail, with bubbles where the API laid them out; Edit panel opens bubble text/type/speaker, face and pose pickers (live `<Avatar>` thumbnails) and left/middle/right (moving into an occupied spot swaps, `lib/studio.ts`). "Make my comic!" is enabled once all `panel_count` panels are planned and everyone in them is locked (otherwise a hint says what's missing); it starts the job (`store/making.ts`) and opens the Reader. `ThumbPicker` (`components/ui`) is the shared face/pose picture row.
  - Reader (Phase 5, `/comics/:id`, `?mode=edit`): `ComicPage` shows the title, the cast row (faces from pinned looks) and the panels in a grid (2 columns from `sm`, 1 on phones). `Panel` shows `art_url` (`?v=` art version) with `BubbleLayer` on top; before drawing, a faded sketch of the place and pinned looks. Status overlays: "Inking panel N…" (the job's current panel, or `rendering`), "Waiting for ink" (`planned`), failed/blocked with the API's message and Try again (`POST /panels/{id}/render`), "Redrawing…" while a face/pose/position change is drawn (`useReaderStore.markRedraw`: until the art URL changes, at most 15 s). `BubbleLayer` draws bubbles as HTML: talk (rounded), think (SVG cloud + `thinkTrail`), shout (SVG starburst, Bangers), narrator (sun-tint box); lettering in container units (`@container` on the panel, `fontSize()` = px/8 cqw) stepping 26→18 to fit, then the bubble grows (measured heights feed the tails). Tails are one SVG over the bodies (`tailWedge`: base just inside the nearest edge so the white fill hides the outline). Edit mode on the selected panel: drag a bubble or its yellow corner with `@dnd-kit/core` (mouse 4 px, touch 150 ms hold, keyboard); the drop stores the new box with `fixed: true` (`moveBox` / `resizeBox`, clamped 0–1). The panel size is measured only in drag handlers (the React Compiler lint forbids reading refs while rendering). Geometry is pure in `lib/bubbles.ts` (Vitest).
  - `PanelInspector`: bubble words (inline `FieldMessage` for a blocked save) and style, face and pose pickers (`ThumbPicker` with live `<Avatar>` from the pinned look), Left/Middle/Right (swaps), Undo. "Redraw panel" stays disabled until Phase 6.
  - `store/making.ts`: `make(comicId)` flushes autosave, `POST /comics/{id}/generate`, then follows the job with `followComicJob` (`api/jobs.ts`: `progress` with `stage: "inking"`, `panel_ready` / `panel_failed` carrying the panel, `done` with the cover). Each panel goes straight into the comics store (`applyPanel`); `done` refetches the comic. `resume(comicId, last_job_id)` on Reader load reconnects to a job that is still running (SSE replays every event). `EditorTopBar`: Make my comic! (with "Inking… n/6") until every panel is drawn, then Download PDF (`fetchPdf` → blob download; a 409 is a toast) and Finish my comic! (`useComicsStore.finish` → `Confetti`, skipped for reduced motion). A "Words not double-checked yet" chip shows while any text is pending. "Share with a grown-up" is hidden (future feature). Any panel edit sets the comic back to draft locally, as the API does.
  - Covers: `ComicCard` (My Comics and Home) shows `cover_url` when there is one, else the place tints.
  - Inline field messages: API errors carry `field`; `store/fieldErrors.ts` (`showOnField`) shows them under that input with `FieldMessage` instead of a toast. `ComicRead.safety_notes` (local checks on title and synopsis) show under those fields after every autosave, and after a refresh. A blocked bubble save shows under the bubble and keeps the kid's words on screen.
  - `BuddySpeech` is the shared buddy speech bubble (Lab helper and Story Buddy), with the "Made with Meta AI" / offline helper label. `StorySpark` on Home fetches `/api/studio/spark`.
  - Drag-and-drop (`components/character/builder/dnd/`, `@dnd-kit/core` 6.3, never HTML5 drag events): an extra way to build; taps work as before. Stickers and paint blobs in the trays drag onto the preview; worn things drag off it (to the "back to the box" tray or anywhere off the character). The rules are pure, in `src/avatar/zones.ts`: `computeZones` (head = rig head box; face = the face rig's features; body = neck to hips; legs = hips to ankles; hands and feet past the wrist and ankle joints, one per side, mirrored for `*_left` poses), `CATEGORY_ZONE` / `EXTRA_ZONE`, `paintSlot`, `wornIn` / `removeItem`, and `planDrop`, which drives the ghost, the drop and the screen-reader words alike. Drops are forgiving (anywhere on the character puts a part in its zone); parts that don't fit wobble and the buddy says why. `BuilderDnd` wires sensors (mouse; touch with a 150 ms hold; keyboard with Space to pick up and drop, arrows/Tab hopping zone to zone via `hopZones`, Escape to cancel, Enter still applying directly), the `pointerFirst` collision (box, then the smallest zone, then the character), announcements, the overlay (bigger, tilted, hard shadow) and the bounce/splash/wobble in `motion.ts` (all skipped for `prefers-reduced-motion`). Every drop is one undo step through `useLabStore.apply`. Locked characters can't drag.
- `api/`: FastAPI on Python 3.11 through uv.
  - `app/main.py`: `create_app(settings)` wires the engine, storage, routers and error handlers; the lifespan creates tables and seeds the demo data.
  - `app/models/`: SQLModel tables (`user`, `character`, `character_version`, `background`, `comic`, `scene`, `panel`, `job`, `moderation_log`) with UUID string ids, JSON columns and timezone-aware UTC timestamps. No ORM relationships are declared, so flush parents before children.
  - `app/schemas/`: Pydantic request/response models; `Literal` types become TypeScript unions. `separate_input_output_schemas=False` keeps one schema name per model.
  - `app/routers/`: `profile` (`/me`, `PUT/DELETE /me/drawing-consent`), `characters`, `builder` (`/builder/info`, `create`, `describe`, `surprise`, `ideas`, `from-drawing`), `backgrounds`, `comics` (comics, `PUT /comics/{id}/scenes`, `PATCH /panels/{id}`, `POST /comics/{id}/generate`, `POST /panels/{id}/render`, `GET /panels/{id}/final.png`, `GET /comics/{id}/pdf`), `studio` (`POST /studio/{id}/plan-scenes`, `POST /studio/{id}/plan-panels`, `POST /studio/buddy`, `GET /studio/spark`), `media` (`/media/{key}` from storage).
  - `app/errors.py`: every error is `{code, message, field?}` with a message written for kids; `field` names the input it's about (`synopsis`, `scenes.<id>.summary`, `bubbles.<id>.text`, `cast`, `buddy`...). Codes: `cast_full`, `locked`, `not_found`, `invalid`, `unknown_part`, `unsafe`, `not_a_drawing`, `too_big`, `consent_needed`, `wrong_answer`, `needs_locked`, `needs_scenes`, `needs_plan`, `not_ready`, `not_checked`, `confirm_start_over`, `plan_failed`, `no_manifest`, `server_error`.
  - `app/prompts/`: every prompt is a `.md` file here (never inline), `REQUIRED` lists each with its placeholders, and `load_all()` reads and checks them all at startup.
  - Story planner (`services/story_planner.py`, router `studio.py`): plan-scenes (2–4 scenes) then plan-panels (exactly `panel_count`), from the saved comic. Only locked cast and places; unlocked cast members are left out (`skipped`). The offline planner is deterministic (synopsis → beats, cast taking turns, keyword rules for pose and face, a narrator opening and closing). The Meta planner uses `complete_json` with schemas whose enums are the catalog's poses and expressions and the comic's locked ids. Pydantic first, then `check_scenes` / `check_panels` (catalog names, locked ids, panel count, ≤3 characters, no shared position, bubbles ≤12 words, speakers in the panel); invalid → one retry with the problems sent back, then 422 `plan_failed` with nothing changed. A Meta outage, or model words that fail safety, fall back to the offline planner (`fallback: true`, offline label). The server adds ids, `sheet_version`, scale and bubble boxes (`services/bubbles.py`, 0–1 coordinates from where the characters stand). `scene.edited_at` / `panel.edited_at` mark kid edits: re-planning scenes asks first if any were edited; re-planning panels keeps edited or drawn panels in their slots unless `start_over`.
  - Story Buddy (`services/story_buddy.py`): `idea` (1–2 questions, never story text), `spelling` (corrected text + changes), `name_scene` (3 titles); through the shared Guard. 30 hand-written sparks.
  - `services/ai_guard.py`: `Guard`, the one safe way to ask Meta for a kid (check input → ask → check output → offline fallback, labels, one retry for malformed replies). The Lab helper, Story Buddy and planner all use it.
  - `services/backup.py`: storage backups (SQLite backup API + media), the newest 5 kept.
  - Pinned looks (`services/looks.py`, model `CharacterVersion`): every lock freezes the normalized spec as that `sheet_version` (`freeze`, in the sheet job and the seed). Panels pin a `sheet_version` and are drawn from that spec, never the current one; `specs_for(session, panel.characters)` falls back to the current spec only for versions with no frozen look. `needs_backfill` triggers the startup backup and `backfill_versions` fills in older versions (from `manifest.json`'s spec when it is a builder spec, else the current spec). `ComicRead.looks` = `{character_id: {"<version>": spec}}` for every version the panels use.
  - Stage (`services/stage.py`): the one piece of geometry shared by the compositor and the bubble layout. Panel 4:3 (800 x 600 at 1x); x by position (left 0.22, centre 0.5, right 0.78); a character cell is `FIGURE` (0.64) x scale of the panel height, feet on the ground line at 0.88 (`foot_line` per body type from the front pose's alpha box). Facing (decision 56) in `drawn_pose`. `head` is the rig head box as drawn (mirrored when the cell is), `head_target` the tail tip (centre, 40% down). `z_order`: left, centre, right, then the first bubble's speaker.
  - Lettering (`services/lettering.py`): Bangers for shout and titles, Nunito (variable, weight 800; 700 for narrators) from `api/assets/fonts`; `fit` steps 26/23/20/18 px (at 800 wide), then grows the height. Bubble layout (`services/bubbles.py`): narrators across the top (0.94 wide), speech bubbles (0.42 wide) stacked under them, centred over the speaker, then the stack slides down to `TAIL_MIN` (0.07) above the highest head; a `fixed` bubble keeps its box and only its tail is re-aimed; the kid's order is kept. Layout runs on every panel save, with the pinned specs.
  - Compositor (`services/compositor.py`): `render_art` = place image cover-cropped to 4:3 (or the tint), each character rendered straight from its pinned spec with resvg at 2x (1600 x 1200) in the drawn pose and expression, mirrored if needed, composited in z-order; saved with `imaging.to_png` (no metadata) so the same inputs give byte-identical PNGs; plus a 400 x 300 thumb. `bake_final` letters every bubble with Pillow (talk with a wedge tail, think cloud + trail, shout starburst, narrator box); `final_hash` (art key, art version, bubbles) marks it stale. `cover` = panel 1's final.png with the title on a sun band.
  - Make my comic! (`services/comic_maker.py`): `POST /comics/{id}/generate` needs exactly `panel_count` panels (409 `needs_plan`) and a pinned look for everyone in them (409 `needs_locked`, decision 14); the title and synopsis get the local checks (422 `unsafe`) plus the full check unless already AI-checked. Pressing it while a job runs returns the same job; `comic.last_job_id` lets the Reader reconnect. `run_comic_job` draws panels in order (`rendering` → `ready` / `blocked` / `failed`, each its own `panel_ready` / `panel_failed` event with the `PanelRead`), one bad panel never stops the rest, then the cover. `draw_panel` (also Try again, and a characters change in `PATCH /panels`) = `check_words` (local checks always; the full check when `text_check` isn't `checked`) → `check_image` on the place → layout → `render_art` → `comics/{comic}/panels/{panel}/art.png`, `thumb.png`, `art_version += 1`. Text edits never re-draw; `GET /panels/{id}/final.png` bakes lazily (`ensure_final`). Restarts fail panels left `rendering` (`fail_rendering_panels`). Finishing (`status: finished`) needs every panel drawn (409 `not_ready`) and remakes the cover; any edit (comic fields other than status/step, scenes, panels) sets it back to `draft`.
  - PDF (`services/pdf_export.py`): Pillow, 8.27 x 11 in at 150 dpi (decision 58). Page 1: title on a sun band, panel 1, the cast drawn from pinned looks with names, "Made with Comickatha"; then 6 panels a page (2 x 3) from final.png with page numbers (4/6/8 panels → 2/2/3 pages). `GET /comics/{id}/pdf` needs every panel drawn (409 `not_ready`), re-checks pending words first (`recheck`), then refuses blocked (409 `unsafe`) or still-pending words (409 `not_checked`).
  - Decision 55 (`services/recheck.py`): `check_story` returns `pending` (allowed, logged as `pending`) when the classifier is down and the local checks pass; plan-scenes/plan-panels then set `guard.offline_only` (nothing unchecked reaches Meta), mark `comic.text_check` and the new panels `pending`. Comic autosave of the title/synopsis sets `pending` with Meta (`checked` with mock, `blocked` if the local checks fail). A panel save of a pending panel checks every bubble. `recheck` (background loop every `RECHECK_SECONDS`, and before a PDF) settles pending comics and panels, stopping at the first outage; a later block goes to `comic.check_note` (shown in `safety_notes`) or the panel's `error` with `text_check: blocked`.
  - `app/deps.py`: DB session, storage and the current kid (the one seeded profile; no auth).
  - `app/services/storage.py`: `Storage` protocol + `LocalStorage` (validated keys, files under `storage/media/`).
  - `app/providers/`: `ImageProvider.generate(prompt, size, seed, reference_images) -> PNG bytes` (chosen by `IMAGE_PROVIDER`), optional `KnowsHeadBoxes`, and `LLMProvider` (`complete`, `complete_json` with a strict JSON schema and an optional image; failures raise `LLMError`). `LLM_PROVIDER=meta` is `MetaLLMProvider` (`providers/meta.py`, Meta's OpenAI-compatible API through the `openai` client: `META_MODEL`, `META_VISION_MODEL`, 20 s timeout, one retry on 429/5xx, token counts logged, never prompts); it refuses a missing key or model and any `-contributor` model at startup. `LLM_PROVIDER=mock` means no LLM (`app.state.llm` is `None`). `MockImageProvider` draws the character in its colours on magenta `#FF00FF`, deterministic per seed, reading the same `Layout:` / `Cells:` / `Palette:` / `Place:` prompt lines a real model gets (`app/prompts/*.md`).
  - `app/services/jobs.py`: `JobRunner` runs job work on the server's asyncio loop (blocking steps in threads). Job kinds: `character_sheet`, `background_image`, `comic`. Every event (`progress`, `cell_ready`, `done`, `error`) is stored on the job row; `GET /api/jobs/{id}/events` (SSE) replays after `?after=` or `Last-Event-ID`, then streams live. On startup, jobs left running are failed with "Oops, the drawing got interrupted. Tap Lock to try again!"
  - Character sheets come from a `SheetProvider` chosen by `SHEET_PROVIDER`. `builder` (default, `services/builder_sheet.py`) renders all 16 poses and 6 faces from the avatar spec with resvg, each pose with its own expression (nothing pasted), head boxes exact from the rig, manifest `renderer: "builder"`, style `builder-v1`. `image` (`ImageSheets`) is the image-model pipeline below. Both fill the same manifest through `SheetCells`.
  - `app/services/character_sheet.py`: `POST /characters/{id}/lock` → safety check → job. With `SHEET_PROVIDER=image`: front view, then the other 15 poses in 1x4 strips with the front view as reference, then the 2x3 faces. Each batch is validated (shape, 3–92% coverage per cell after keying) and retried once. Cells are keyed (`services/imaging.py`: magenta tolerance + 1px erosion), sliced, saved under `characters/{id}/v{n}/`, and announced as `cell_ready`. The manifest adds `cell_urls`, `heads` (box + source + editable offset), `face_visible`, `face_sheet.head_box` and `thumb_url`. Re-locking writes a new version; old versions stay (`GET .../manifest?version=n`).
  - `app/services/image_gen.py`: place lock job, one 1024x768 (4:3, panel-shaped) reference image + 320px thumb.
  - `app/services/safety.py`: local checks first (`check_local`: `check_personal` for phone numbers, emails, street addresses, school names and self-identifying full names, then the word list), then with an LLM the classifier (`classify`, strict JSON verdict per text, prompt in `app/prompts/safety_classifier.md`). Fails closed: a classifier that can't answer raises `SafetyUnavailable`. Blocks carry a gentle `kid_message` ("Let's keep real addresses secret! Try a made-up place instead."). Every verdict goes to `moderation_log`. Story text uses `check_story` (a classifier outage leaves locally checked text `pending`, decision 55): title and synopsis on plan-scenes, those plus scene summaries on plan-panels, changed bubble text on `PATCH /panels`. `check_image` checks every place image put in a panel (mock: any PNG passes; logged as kind `image`). Autosave of the title and synopsis runs only the local checks: a blocked draft is still saved, logged, and shown as `safety_notes`. Lock and places use the word list only; the helpers use the Guard.
  - Character safety (`docs/character-safety.md` is the written policy; prompt saved in `docs/phases/character-safety.md`):
    - `POST /builder/create` (`services/builder_create.py`, `schemas/builder.py` `CreateRequest` / `Created`): `kind` (person, robot, cat, dog, bear), `age` (people only: little/big kid → `kid` body, grown-up/grandparent → `grown_up`, grandparents get grey hair offline), `face_shape` (static `FaceShape` literal, a test keeps it equal to the catalog), optional `description` (≤300), `follow_up_answer` (`CatalogChoice {target, value}`: a part category or `colors.<slot>` plus an id; any real choice that fits the body is accepted, no token), `name` (≤24), `role`. Unknown fields are a 422. Answers: spec, `name_ideas`, `catchphrase` (≤12 words), `intro_line` (≤15 words), `follow_up` (question + 2–4 `FollowUpOption`s), `notes`, `reply`, `unmatched`, source/fallback/label. Meta uses `prompts/builder_create.md` and `helper_meta.create` (schema `character_create`); offline is `helper_offline.create` (describe or a seeded surprise, an intro line, a colour follow-up until answered).
    - Input checks (`services/character_safety.py`, also on `/builder/describe`): length → personal info → word list → real people (relation patterns, "looks like <Full Name>", a short `FAMOUS` list) → rule-bending ("ignore the rules", "pretend", "without clothes"...) → body words (weight/shape) taken out with the note "Every character is awesome just as they are!" (logged `filtered`). Blocks are 422 `unsafe` on `description` (or `name`); nothing reaches Meta. Then the Guard's classifier, which now has a `real_person` category (kid message "Let's make up a brand-new character instead!").
    - Output checks (`Creator._finish`): people missing a top, bottom or shoes get the body's default outfit; off-list traits are dropped; lengths enforced; names checked with `name_problem` (local checks, famous names, real-person patterns); every text through the local checks and, for Meta's words, one `safety.classify_each` call (per-field verdicts; an outage counts as unsafe). Failures are replaced (offline names, the trait's offline catchphrase, "Meet <name>, ready for adventure!", a friendly reply) or dropped (follow-up whose options aren't catalog choices, unmatched), each logged as `replaced` with `<field>:<reason>`. `Guard.ask` skips its whole-answer check when `texts` returns nothing (the caller checks field by field).
    - Catalog (`shared/avatar/build_catalog.py`): `REVIEWED` lists every part and extra a person has checked, written as `reviewed: true` (new options are `false` until added); `CULTURAL` (hijab, turban) and `SILLY` (star glasses) become `tags`. "Surprise me" (offline and Meta) never pairs cultural headwear with silly items (`respectful_extras`). Hair palette has `grey` and `white`. `tests/test_catalog_audit.py` checks it all every run: people always dressed, only robots/animals go without clothes, no weapons but the wand, no text or brands, cultural items for every human body with plain labels, every option reviewed.
    - Follow-up answers refine, never re-roll: the optional `look` (only with `follow_up_answer`, validated like a saved look, matching the body) is the character so far; its personality is stripped before Meta, which is told to change only the answered choice, and `Creator._finish` enforces it by returning the look with just that choice applied (plus a dress's leggings), keeping its traits. The offline seed ignores the answer, so names and the intro stay. `role_suggestion` comes from Meta (enum) or `helper_offline.role_for` (brave/adventurous → hero, helpful/caring → sidekick, else friend).
    - Saving: `POST /characters` runs `character_safety.check_name` (422 on `name`) and stores `designed_by` ("meta" / "offline"); a PATCH that changes the spec clears it (renames don't). `MetaLLMProvider.last_call` (`{ok, at, error type}`) feeds `/builder/info` for the dev menu.
    - Dress rule: `with_leggings` (`app/avatar/spec.py`) gives a newly picked dress leggings in the nearest bottom colour to a darker shade of the dress; applied in `build_spec` (describe, surprise, drawing, create) and for a follow-up answer.
  - Builder helper (`services/builder_helper.py`): kid's words → word list → classifier → Meta (`helper_meta.py`: prompts, and JSON schemas whose enums are the catalog's ids, colours as palette ids) or the offline helper (`helper_offline.py`, word matching, seeded surprises, drawing colours; vocabulary in `avatar/words.py`). A malformed Meta reply is retried once; an outage, an unsafe reply or an unchecked one (classifier down) falls back to the offline helper, labelled "Made by the offline helper" with `fallback: true` and a "helper is resting" reply. Every answer is a full, drawable spec (`normalize`), with `changed`, `name_ideas` and `unmatched` wishes.
  - Drawings (`services/drawing.py`): a data URL, decoded and re-encoded in memory (metadata dropped, ≤768 px), never written to disk or the DB. Over 5 MB → 413 `too_big`; photo-like → 422 `not_a_drawing`. With Meta, a grown-up's OK is needed first (`PUT /me/drawing-consent`, a 6–12 times-table question; stored as `user.drawing_consent_at`; `DELETE` takes it back); offline needs none.
  - Avatar specs (`schemas/avatar.py`, `avatar/spec.py`): `{body_type, parts, colors, extras, personality: {traits, catchphrase}, role}`. Character `kind` and `role` are written from the spec. `validate` is strict (422 `unknown_part` for an unknown part, a part the body type can't wear, an off-palette colour, two pairs of glasses); `normalize` swaps bad choices for defaults (migration, AI answers). `PATCH /characters/{id}` takes the whole spec; unknown keys are a 422 `invalid`, never ignored.
  - `app/db.py`: `add_missing_columns` adds new nullable columns to an older SQLite file on startup (no Alembic yet).
  - `app/avatar/`: Bitmoji-style avatars (Phase 3.5). `shared/avatar/build_catalog.py` writes `shared/avatar/catalog.json`: the parts library as SVG fragments with colour placeholders (`{{skin}}`, `{{top_shade}}`, ...), drawn for 4 views (front, three_quarter, side, back) and per body type where shapes depend on the body (6 types: kid, grown_up, robot, cat, dog, bear). It also holds the palettes, the rig (bones with per-view offsets), the layer order per view, the 6 expressions and the 16 poses (bone angles; `*_left` poses are mirrored). Never edit the JSON by hand: change the generator and run `uv run python ../shared/avatar/build_catalog.py` (a test fails if the JSON is stale). `compose.py` turns an avatar spec into SVG, `rig.py` does the bone transforms and head boxes, `render.py` rasterises with resvg. Catalog numbers are ints or ≤2-decimal floats so Python and the TypeScript twin print identical SVG. Contact sheets: `uv run python -m app.avatar.preview` → `shared/avatar/preview/` (gitignored).
  - `app/seed.py`: demo data with fixed `uuid5` ids, so URLs survive a reset. Characters are builder specs; seeded sheets and places come from the real pipelines (builder sheets, mock image provider for places). `seed()` is idempotent; `python -m app.seed` resets. Tests seed once per session and copy the result per test.
  - Rules: at most 3 active characters (409 `cast_full`); PATCH on a locked character or place is 409 `locked`; deletes are soft and lists hide deleted rows.
  - Deleted characters and places never disappear from comics: `GET /characters/{id}` and `GET /backgrounds/{id}` still return them (`deleted: true`), and every comic carries `characters` and `backgrounds` it uses. The web app merges those with the live lists (`castFor`, `placesFor` in `src/lib/comic.ts`) for the Reader, covers and Studio; pickers and libraries show live items only.
- Design source: the claude.ai design canvas "Comickatha – App Design", with boards for Home, Characters, Story Studio, My Comics, Reader and Style Guide. The Style Guide board is the source of truth for tokens.

## Decisions (approved 2026-11-02)

1. Mock-first: `MockLLMProvider` and `MockImageProvider` are the defaults. The app must run end to end with zero keys.
2. Lock, generate and redraw return `202 {job_id}`. Progress streams from `GET /api/jobs/{id}/events` (SSE), replayed on reconnect.
3. The character manifest has a head box per body cell, plus a tweakable offset. The compositor pastes the expression face there for front and ¾ poses.
4. Panels are `art.png` (background + characters) plus bubble data. The Reader draws bubbles as HTML; the compositor bakes `final.png` for thumbnails and PDF.
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
15. Phase 6 providers: Claude `claude-sonnet-5-5` for planner, buddy and safety; Gemini's image model as primary and OpenAI's image API as secondary. Check current model names at Phase 6.

Phase 2 (2026-11-03):

16. Schema additions beyond the agreed list: `background.tint` (placeholder colour), `comic.deleted_at` (soft delete), `panel.beat` (decision 13). `panel.scene_id` is nullable: removing a scene keeps its panels.
17. Lock/unlock only flip `status` in Phase 2 and return the item. Phase 3 turns them into `202 {job_id}` jobs that bump `sheet_version`. Seeded locked characters get placeholder sheets + manifest (v1) from `MockImageProvider`; seeded places get a placeholder reference image.
18. Studio step 3 shows the stored panel plan; "Make my comic!" stays disabled until Phases 4 and 5 add the planner and drawing.
19. New scenes and bubbles get client-made ids, so ids do not change after saving.

Before Phase 3 (2026-11-03):

20. Secrets: `META_API_KEY` moved to `.env`; `.env.example` has placeholders; a pre-commit hook runs `scripts/check_secrets.py`.
21. Deleted characters and places stay resolvable for comics (`deleted: true`), see Architecture.
22. Phase 1 and Phase 2 are separate commits. Phase 1 was rebuilt from the session record and verified with the same 40 browser checks before committing.

Phase 3 (2026-11-03), superseding 17:

23. Lock is a job: `POST .../lock` returns `202 {job_id, kind, target_id}`; `last_job_id` is stored so the web app reconnects after a refresh. Locking while drawing returns the same job; a locked item → 409 `already_locked`; unlock, edit or delete while drawing → 409 `busy`; a failed job sets status `failed` and Lock can be tapped again.
24. `ImageProvider` keeps the exact `generate(prompt, size, seed, reference_images)` signature; the mock gets everything from the prompt text.
25. Head offsets are edited with `PATCH /characters/{id}/heads/{pose}` (allowed while locked: it changes placement, not the look). The Lab previews compositing: the chosen face is pasted onto the chosen pose's head box (`src/lib/sheet.ts`, same maths as the Phase 5 compositor).
26. Places that fail to paint show "Couldn't paint"; there is no retry button on the tile yet (describe the place again).

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
37. The parts catalog ships in the JS bundle (about 1 MB minified, 171 KB gzipped, so Vite warns about chunk size); split it out if load time matters.

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
49. Bubble boxes are recomputed on every panel save (kids can't move bubbles until Phase 5).
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
80. Real runs with `muse-spark-1.3` (2026-11-08): the model thinks before it answers. The safety classifier used ~450-500 completion tokens (its old 300 limit cut every verdict off, so all Meta features fell back offline); it now gets 1,500. A character design used 2,000-2,500 tokens and ~15 s; it gets 6,000 and a 60 s per-call timeout (`complete_json(..., timeout=)`). A reply cut off at the limit raises `LLMError` and shows as `OutOfTokens` in the dev menu. Other Meta calls (Story Buddy 600, planner 1,200/3,000, builder describe/surprise/ideas 1,024) may need the same headroom: check in Phase 6.

## Future features

- "Share with a grown-up" (a read-only link a parent can open), hidden in the Reader until it's built. Sharing must wait for decision 55's AI check, like the PDF.

## Environment notes

- The dev machine has Node 20.15, which is below what Vite 8, React Router 8 and ESLint 10 need. The web app pins Vite 6, React Router 7 and ESLint 9. TypeScript is 5.9 because openapi-typescript supports TypeScript 5 only. Bump them after upgrading Node to 22+.
- The API's default port is 8010 because another local project uses 8000.
- The project lives in OneDrive: exclude `web/node_modules`, `api/.venv` and `api/storage` from sync.
- Starlette warns that its TestClient prefers `httpx2`. Harmless; swap once the package is verified.

## Phases

- [x] 1. Scaffolding, compose, tokens, NavBar and the 5 pages as static UIs on mock data
- [x] 2. API models, CRUD routers, seed data; wire web to API
- [x] 3. Provider interfaces + MockImageProvider; jobs + SSE; character_sheet service (generate, slice, manifest); place images; Lock flow
- [x] 3.5 Character Builder: 3.5a parts library, rig and 16 poses; 3.5b API: avatar spec, migration, builder sheets, Meta helper, AI safety, `shared/` in the Docker image; 3.5b web: `<Avatar>` + golden-file parity tests, Lab builder UI, regenerated `api.ts`
- [x] 4. story_planner, Story Studio steps 1–3, Story Buddy, safety on story text
- [x] 5. Pinned looks, compositor, Make my comic! (generate job + SSE), Reader Read/Edit with draggable bubbles, final.png, covers, PDF export, decision 55 re-checks (awaiting review)
- [x] Character safety: `/builder/create` contract, trait list, catalog audit, input/output checks
- [x] Lab: Lock at the bottom, guided Create character flow (awaiting review)
- [ ] 6. Real LLM and image providers, Redraw panel, polish
