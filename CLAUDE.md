# Comickatha

Web app where kids under 16 design characters and places, write a story, and get a comic.
Hackathon build: optimise for a working end-to-end demo and clean, easy-to-extend code. Don't over-engineer.

## Working agreement

- Build in the phases below. After each phase: run it, run the checks, summarise, then STOP for review.
- This folder is its own git repo. Never commit to or touch the parent `Assigment` repo.
- Commit only when asked. No secrets in code: `.env` is gitignored; `.env.example` is committed and holds placeholders only.
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
- Reset to the demo data at any time: `uv run python -m app.seed` (from `api/`). It wipes the database and generated files.
- Settings: `Copy-Item .env.example .env`, then edit `.env`. Defaults need no API keys.
- Point the web dev server at a different API: `$env:API_PROXY_TARGET = "http://localhost:8000"; npm run dev`
- If the terminal shows conda's `(base)` and Python looks wrong, run `conda deactivate`. uv is set to `python-preference = "only-managed"`, so it should never pick up conda's Python.
- If PowerShell says `npm.ps1 cannot be loaded`, run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once.

## Checks

```powershell
# API (from api/)
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy app tests

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
  - `app/services/storage.py`: `Storage` protocol + `LocalStorage` (validated keys, files under `storage/media/`). `services/character_sheet.py` builds placeholder sheets + manifest; Phase 3 adds the real pipeline.
  - `app/providers/`: `ImageProvider` protocol and `MockImageProvider` (labelled cells on magenta `#FF00FF`).
  - `app/seed.py`: demo data with fixed `uuid5` ids, so URLs survive a reset. `seed()` is idempotent; `python -m app.seed` resets.
  - Rules: at most 3 active characters (409 `cast_full`); PATCH on a locked character or place is 409 `locked`; deletes are soft and lists hide deleted rows.
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

## Environment notes

- The dev machine has Node 20.15, which is below what Vite 8, React Router 8 and ESLint 10 need. The web app pins Vite 6, React Router 7 and ESLint 9. TypeScript is 5.9 because openapi-typescript supports TypeScript 5 only. Bump them after upgrading Node to 22+.
- The API's default port is 8010 because another local project uses 8000.
- The project lives in OneDrive: exclude `web/node_modules`, `api/.venv` and `api/storage` from sync.
- Starlette warns that its TestClient prefers `httpx2`. Harmless; swap once the package is verified.

## Phases

- [x] 1. Scaffolding, compose, tokens, NavBar and the 5 pages as static UIs on mock data
- [x] 2. API models, CRUD routers, seed data; wire web to API (awaiting review)
- [ ] 3. Provider interfaces + MockImageProvider; character_sheet service (generate, slice, manifest); Lock flow
- [ ] 4. story_planner, Story Studio steps 1–3, safety service
- [ ] 5. Compositor, generate SSE, Reader Read/Edit, PDF export
- [ ] 6. Real LLM and image providers, Redraw panel, polish
