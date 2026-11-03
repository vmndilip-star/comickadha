# Comickatha

Web app where kids under 16 design characters and places, write a story, and get a comic.
Hackathon build: optimise for a working end-to-end demo and clean, easy-to-extend code. Don't over-engineer.

## Working agreement

- Build in the phases below. After each phase: run it, run the checks, summarise, then STOP for review.
- This folder is its own git repo. Never commit to or touch the parent `Assigment` repo.
- Commit only when asked. No secrets in code: `.env` is gitignored; `.env.example` is committed and holds placeholders only (`your-key-here`).
- Secret check: `.githooks/pre-commit` runs `scripts/check_secrets.py --staged` and blocks a commit that stages `.env` or anything shaped like an API key. Enable it once per clone with `git config core.hooksPath .githooks`. Scan everything tracked with `python scripts/check_secrets.py`.
- Keep this file current when decisions change.

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
- Reset to the demo data at any time: `uv run python -m app.seed` (from `api/`). It wipes the database and generated files, then draws the demo sheets again (about 8 seconds).
- The mock image provider waits `MOCK_DELAY_SECONDS` (default 1.2) per image so the live sheet build is visible; set 0 for instant locks.
- On Windows, `uvicorn --reload` sometimes stops picking up changes after a reload. If the API serves old code, stop it and start it again.
- Settings: `Copy-Item .env.example .env`, then edit `.env`. Defaults need no API keys.
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
npm run build      # runs tsc -b (strict) first
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
  - `CharacterFace` draws the placeholder SVG characters from the boards; it stays as the fallback for unlocked drafts.
- `api/`: FastAPI on Python 3.11 through uv.
  - `app/main.py`: `create_app(settings)` wires the engine, storage, routers and error handlers; the lifespan creates tables and seeds the demo data.
  - `app/models/`: SQLModel tables (`user`, `character`, `background`, `comic`, `scene`, `panel`, `job`, `moderation_log`) with UUID string ids, JSON columns and timezone-aware UTC timestamps. No ORM relationships are declared, so flush parents before children.
  - `app/schemas/`: Pydantic request/response models; `Literal` types become TypeScript unions. `separate_input_output_schemas=False` keeps one schema name per model.
  - `app/routers/`: `profile`, `characters`, `backgrounds`, `comics` (comics, `PUT /comics/{id}/scenes`, `PATCH /panels/{id}`), `media` (`/media/{key}` from storage).
  - `app/errors.py`: every error is `{code, message}` with a message written for kids (`cast_full`, `locked`, `not_found`, `invalid`, `no_manifest`, `server_error`).
  - `app/deps.py`: DB session, storage and the current kid (the one seeded profile; no auth).
  - `app/services/storage.py`: `Storage` protocol + `LocalStorage` (validated keys, files under `storage/media/`).
  - `app/providers/`: `ImageProvider.generate(prompt, size, seed, reference_images) -> PNG bytes` (chosen by `IMAGE_PROVIDER`), optional `KnowsHeadBoxes`, and the `LLMProvider` interface for Phase 4. `MockImageProvider` draws the character in its colours on magenta `#FF00FF`, deterministic per seed, reading the same `Layout:` / `Cells:` / `Palette:` / `Place:` prompt lines a real model gets (`app/prompts/*.md`).
  - `app/services/jobs.py`: `JobRunner` runs job work on the server's asyncio loop (blocking steps in threads). Every event (`progress`, `cell_ready`, `done`, `error`) is stored on the job row; `GET /api/jobs/{id}/events` (SSE) replays after `?after=` or `Last-Event-ID`, then streams live. On startup, jobs left running are failed with "Oops, the drawing got interrupted. Tap Lock to try again!"
  - `app/services/character_sheet.py`: `POST /characters/{id}/lock` → safety check → job: front view, then the other 15 poses in 1x4 strips with the front view as reference, then the 2x3 faces. Each batch is validated (shape, 3–92% coverage per cell after keying) and retried once. Cells are keyed (`services/imaging.py`: magenta tolerance + 1px erosion), sliced, saved under `characters/{id}/v{n}/`, and announced as `cell_ready`. The manifest adds `cell_urls`, `heads` (box + source + editable offset), `face_visible`, `face_sheet.head_box` and `thumb_url`. Re-locking writes a new version; old versions stay (`GET .../manifest?version=n`).
  - `app/services/image_gen.py`: place lock job, one 1024x768 (4:3, panel-shaped) reference image + 320px thumb.
  - `app/services/safety.py`: word blocklist on names, outfits, catchphrases and place descriptions; blocked → 422 `unsafe`; every verdict in `moderation_log`.
  - `app/db.py`: `add_missing_columns` adds new nullable columns to an older SQLite file on startup (no Alembic yet).
  - `app/avatar/`: Bitmoji-style avatars (Phase 3.5). `shared/avatar/build_catalog.py` writes `shared/avatar/catalog.json`: the parts library as SVG fragments with colour placeholders (`{{skin}}`, `{{top_shade}}`, ...), drawn for 4 views (front, three_quarter, side, back) and per body type where shapes depend on the body (6 types: kid, grown_up, robot, cat, dog, bear). It also holds the palettes, the rig (bones with per-view offsets), the layer order per view, the 6 expressions and the 16 poses (bone angles; `*_left` poses are mirrored). Never edit the JSON by hand: change the generator and run `uv run python ../shared/avatar/build_catalog.py` (a test fails if the JSON is stale). `compose.py` turns an avatar spec into SVG, `rig.py` does the bone transforms and head boxes, `render.py` rasterises with resvg. Catalog numbers are ints or ≤2-decimal floats so Python and the TypeScript twin print identical SVG. Contact sheets: `uv run python -m app.avatar.preview` → `shared/avatar/preview/` (gitignored).
  - `app/seed.py`: demo data with fixed `uuid5` ids, so URLs survive a reset. Seeded sheets and places come from the real pipelines (mock provider). `seed()` is idempotent; `python -m app.seed` resets. Tests seed once per session and copy the result per test.
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

## Environment notes

- The dev machine has Node 20.15, which is below what Vite 8, React Router 8 and ESLint 10 need. The web app pins Vite 6, React Router 7 and ESLint 9. TypeScript is 5.9 because openapi-typescript supports TypeScript 5 only. Bump them after upgrading Node to 22+.
- The API's default port is 8010 because another local project uses 8000.
- The project lives in OneDrive: exclude `web/node_modules`, `api/.venv` and `api/storage` from sync.
- Starlette warns that its TestClient prefers `httpx2`. Harmless; swap once the package is verified.

## Phases

- [x] 1. Scaffolding, compose, tokens, NavBar and the 5 pages as static UIs on mock data
- [x] 2. API models, CRUD routers, seed data; wire web to API
- [x] 3. Provider interfaces + MockImageProvider; jobs + SSE; character_sheet service (generate, slice, manifest); place images; Lock flow (awaiting review)
- [ ] 3.5 Character Builder: 3.5a parts library, rig and 16 poses (committed); 3.5b `<Avatar>` + parity tests, builder sheet provider, avatar spec, Meta helper, Lab UI. When the builder is wired to Lock, add `shared/` to the API Docker image.
- [ ] 4. story_planner, Story Studio steps 1–3, safety service
- [ ] 5. Compositor, generate SSE, Reader Read/Edit, PDF export
- [ ] 6. Real LLM and image providers, Redraw panel, polish
