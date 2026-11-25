# Comickadha

Web app where kids under 16 design characters and places, write a story, and get a comic.
Hackathon build: optimise for a working end-to-end demo and clean, easy-to-extend code. Don't over-engineer.
Details live in `docs/architecture.md` (full architecture) and `docs/decisions.md` (every decision).

## Working agreement

- Build in phases. After each phase: run it, run the checks, summarise, then STOP for review.
- This folder is its own git repo. Never commit to or touch the parent `Assigment` repo.
- Commit only when asked. No secrets in code: `.env` is gitignored; `.env.example` is committed and holds placeholders only (`your-key-here`).
- Secret check: `.githooks/pre-commit` runs `scripts/check_secrets.py --staged` and blocks a commit that stages `.env` or anything shaped like an API key. Enable it once per clone with `git config core.hooksPath .githooks`. Scan everything tracked with `python scripts/check_secrets.py`.
- Keep this file, `docs/architecture.md` and `docs/decisions.md` current when the code or a decision changes (new decisions go at the end of `docs/decisions.md`, numbered on).
- Phase prompts aren't kept in the repo: `docs/decisions.md` and the git history are the record of what each phase asked for and decided.
- Testing in the browser: never use the dev servers on 8010/5173 or `api/storage`. Run a test API with `STORAGE_DIR` pointing at a throwaway folder (e.g. port 8021) and `API_PROXY_TARGET=http://localhost:8021 npx vite --port 5176`.

## Run it (Windows PowerShell)

Prerequisites: [uv](https://docs.astral.sh/uv/) (downloads Python 3.11 itself), Node 20.15+, Docker Desktop (optional).
PowerShell 5.1 has no `&&`: run commands one line at a time, from the repo root.

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

# Or both in Docker (start Docker Desktop first; Compose 2.17+)
docker compose up --build
```

- First start creates the tables and seeds the demo data (`api/storage/comickadha.db`, files in `api/storage/media/`). Reset: `uv run python -m app.seed` (from `api/`). `--paint` repaints the demo places with Muse (paid; Meta on; decision 96). `--portraits [--mine]` paints the 12 starters' portraits (and with `--mine` the kid's locked characters without one; decision 132): on the mock it's free, on Muse it's paid.
- Before adding a column to an existing database the API backs up `api/storage` to `api/storage-backups/<timestamp>-before-migration/` (newest 5 kept). By hand: `uv run python -m app.backup`.
- Settings: `Copy-Item .env.example .env`. Defaults need no keys (mock providers). Read from the process environment, then the repo-root `.env`, then `api/.env`; tests pin the mocks.
- The demo runs on Meta: `.env` needs `META_API_KEY`, `LLM_PROVIDER=meta`, `META_MODEL=muse-spark-1.3`, `IMAGE_PROVIDER=muse`, `META_IMAGE_MODEL=muse-image-1.0`. `IMAGE_PROVIDER=muse` without `LLM_PROVIDER=meta` stops startup.
- Pauses so things visibly fill in (0 = instant): `BUILDER_REVEAL_SECONDS` 0.08, `MOCK_DELAY_SECONDS` 1.2, `PANEL_REVEAL_SECONDS` 0.4. `RECHECK_SECONDS` (60; 0 = off) re-checks story text saved during a Meta outage.
- Ports: API 8010 (8000 inside Docker), web 5173 proxying to `API_PROXY_TARGET` (default `http://localhost:8010`).
- Windows: if `uvicorn --reload` serves old code, restart it; with conda's `(base)` showing, `conda deactivate`; if `npm.ps1 cannot be loaded`, `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.

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
npm test           # Vitest: src/**/*.test.{ts,tsx} (pure rules, store tests, render-to-string components)
npm run build      # runs tsc -b (strict) first
```

## Generated files (never edit by hand)

| File | Regenerate (needs uv) | Guarded by |
| --- | --- | --- |
| `shared/avatar/catalog.json` | `uv run python ../shared/avatar/build_catalog.py` (from `api/`) | an API test fails if stale |
| `shared/avatar/golden.json` | `uv run python -m app.avatar.golden` (from `api/`) | an API test fails if stale; Vitest parity |
| `web/src/types/api.ts` | `npm run gen:types` (from `web/`; the API needn't run) | `tsc` |
| `api/uv.lock`, `web/package-lock.json` | `uv sync` / `npm install` | |

Run `gen:types` after any change to `api/app/schemas/` or a router signature, then fix the web. After changing the catalog or either avatar twin, regenerate `golden.json` and run both test suites. `src/types/index.ts` gives generated schemas friendly names and holds the option lists (checked against `api.ts` both ways).

## Rules that must always hold

- **Mock-first.** Defaults run end to end with no keys: `LLM_PROVIDER=mock` means no LLM (offline helpers, local checks only); `MockImageProvider` paints places.
- **Nothing unchecked reaches Meta.** Every kid-written word in a Meta prompt passes the local checks (personal info, word list) and, with Meta, the classifier first, where it is sent (table below). A classifier outage means offline only, never "blocked" (decision 55). The kid's words are never logged; usage logs carry call names and token counts only.
- **Every generated picture is checked** by the vision model before it is saved or shown (`safety.check_image` in the place and portrait jobs, through `services/painting.py`), and painted character pictures also pass the look check (`services/look_check.py`, decision 132); mock pictures are drawn locally. `PAINTING_ENABLED` and the daily caps bound painting (decision 134).
- **Old comics never change.** Panels pin a `sheet_version` and draw from its frozen look (`CharacterVersion`), and a `place_version` and draw that version's pictures; re-locking keeps old versions; a locked place painted again is a new version; deletes are soft and comics keep what they use; up to 3 characters at left, middle and right stand where they always did, and comics drawn before panel sizes keep their old pages.
- **Kid-friendly errors.** Every API error is `{code, message, field?}` with a message written for kids; the web shows it inline under `field` or as a toast, never raw.
- **At most 40 own characters** (any number up to `MAX_CAST`, decision 130; 409 `cast_full`); the 12 starter characters are read-only (409 `starter`) and don't count; a comic has up to 5 characters, and a scene or a panel can hold them all (no 3-character limit); only locked characters and places go into a comic.
- **Words and pictures agree.** Every prop a bubble or caption names is drawn in that panel; a sleeping character never has a bubble; bubbles hold 12 words at most (a hard stop).
- **No secrets** in code or logs. Model names come from `.env`; `-contributor` models are refused at startup.
- Every prompt is a file in `api/app/prompts/` (checked at startup); every Meta call's token limit and timeout is in `api/app/services/ai_limits.py`.

## Architecture map

- **API** (`api/app/`, FastAPI, Python 3.11, uv): `main.py` (`create_app`: providers → prompts → backup → tables → seed), `config.py` (`Settings`), `deps.py` (the one seeded kid, never the starter cast profile; no auth), `errors.py`, `models/` (SQLModel tables), `schemas/` (Pydantic; `Literal`s become TS unions), `routers/` (`profile`, `characters`, `builder`, `backgrounds`, `comics`, `studio`, `jobs`, `media`; `/api/health` in `main.py`).
- **AI and safety**: `providers/` (`MetaLLMProvider` for text and vision, `MuseImageProvider`, `MockImageProvider`), `services/ai_guard.py` (the one safe path to Meta, with offline fallback), `services/kid_fields.py` (checks a prompt's kid words in one classifier call), `services/safety.py` (local checks, classifier, image check), `services/character_safety.py`, `services/ai_limits.py`, `services/painting.py` (paint → image check → look check, the paint log and daily caps), `services/look_check.py`.
- **Characters**: `avatar/` (catalog, compose, rig, resvg render, spec; TypeScript twin in `web/src/avatar/`, kept equal by golden files), Lab helper (`builder_helper.py`, `helper_meta.py`, `helper_offline.py`), Create (`builder_create.py`), Lock (`character_sheet.py` job + `builder_sheet.py`), pinned looks (`looks.py`), the 12 starter characters (`app/starters.py`, `ensure_starters` at startup).
- **Places**: `routers/backgrounds.py`, `services/image_gen.py` (paint → image check → save; each version at day, sunset and night; `place_picture` for a panel's version and time of day).
- **Props**: `app/props/` (`library.py` the drawings, `images.py` the cached pictures), `services/prop_rules.py` (props a text names, adding what's missing, place words without props).
- **Story and comics**: `app/moods.py` (the 18 moods: prompt line, offline captions, Story Buddy words), `story_planner.py` (scenes, then panels a part at a time; checks, failing panels asked again, repairs), `plan_job.py` (the panel plan job, followed over SSE), `story_buddy.py`, `recheck.py` (decision 55), `stage.py` + `bubbles.py` (panel geometry: sizes, crowds, props, hands, "Zzz"), `staging.py` (`PanelRead.stage` for previews), `pages.py` (pages by slots), `compositor.py` (art, final.png, cover), `lettering.py`, `comic_maker.py` (Make my comic! job, `reshape`), `pdf_export.py`.
- **Jobs and storage**: `services/jobs.py` (`JobRunner`, SSE with replay), `storage.py`, `backup.py`, `db.py` (`add_missing_columns`), `seed.py`.
- **Web** (`web/src/`, React 19, Vite 6, TypeScript, Tailwind 4, React Router 7, Zustand 5): `api/` (typed fetch, `ApiError`), `store/` (data; autosave in `save.ts`), `pages/` (the Lab, Create, Studio and Reader load lazily: `pages/lazyPages.tsx`), `components/{ui,layout,home,character,story,comic}`, `avatar/`, `lib/` (pure helpers), `types/`. Tokens in `styles/tokens.css`; use theme classes, raw hex only for data colours.
- **Tests**: `api/tests/` (pytest; seeds once per session; `fakes.py` has fake Meta and Muse clients); Vitest next to the code.

## What each Meta prompt carries

| Meta call | Kid-written words in it | Checked in |
| --- | --- | --- |
| Lab describe / surprise / ideas / from-drawing | description or name, plus the current catchphrase (from-drawing: the drawing, with a grown-up's OK) | `Helper` in `builder_helper.py` → `Guard.check_input` |
| Create character | description, name | `Creator.create` in `builder_create.py` |
| Planner scenes / panels (one call per part, and `panel_fix` for panels asked again) | title, synopsis, scene summaries and key moments, cast names and catchphrases, place names and descriptions | `routers/studio.py` `_check_story(planner_fields(ctx))`; a place that fails is left out with a note |
| Story Buddy | the kid's text, title, cast names, place names | `Buddy.answer` (`buddy_fields`) |
| Muse Image place (day, sunset, night) | place name, description (props taken out) | place lock, New version and Sunset & night in `routers/backgrounds.py`; each picture by the image check |
| Muse Image portrait | none: the look in catalog words and colour values, plus the builder's front drawing | the picture by the image check, then the look check (`services/portraits.py`) |
| Look check | none: the drawing and the painting side by side, looks in catalog words and colour values, characters by position | it is a check |
| Classifier, image check | the text or picture being checked | they are the checks |

Keep this table (full version in `docs/architecture.md`) current when a prompt changes.

## Decisions still in force (details in `docs/decisions.md`)

Providers and AI: 1, 15 (Claude still an option), 24, 27 (superseded in part by 131), 43, 50, 81, 82, 83, 110, 131, 134 · Safety: 10, 31, 48, 51, 55, 71, 72, 84, 85, 86, 89, 107 · Characters and Lab: 12, 29, 32, 34–36, 38–42, 66–70, 73–79, 87, 92, 93, 99, 100, 102, 112, 129, 130, 132 · Places: 7, 8, 21, 90, 96, 117, 124 · Studio: 6, 13, 44–47, 52, 53, 97, 98, 101, 103–106, 108, 109, 113, 114, 116, 118–120, 122, 123, 128 · Comics and Reader: 2, 4, 5, 14, 23, 56–64, 95, 115, 121 · Data: 16, 19, 20, 45, 54, 60, 91 · Design and build: 9, 11, 37, 57, 58, 94, 111, 125, 126, 127. Superseded or history only: 3, 17, 18, 22, 25, 26, 28, 30, 33, 49, 65, 80, 88.

## Future features

- "Share with a grown-up" (a read-only link a parent can open), hidden in the Reader until it's built. Sharing must wait for decision 55's AI check, like the PDF.
- Unlock (and edit) for places (decision 90): panels already pin their place version (decision 117), so editing a place's words could simply paint a new version.

## Environment notes

- The dev machine has Node 20.15, below what Vite 8, React Router 8 and ESLint 10 need: the web app pins Vite 6, React Router 7 and ESLint 9. TypeScript is 5.9 because openapi-typescript supports TypeScript 5 only. Bump them after upgrading Node to 22+.
- The API's default port is 8010 because another local project uses 8000.
- The project lives in OneDrive: exclude `web/node_modules`, `api/.venv` and `api/storage` from sync.
- Starlette warns that its TestClient prefers `httpx2`. Harmless; swap once the package is verified.

## Phases

- [x] 1. Scaffolding, compose, tokens, NavBar and the 5 pages as static UIs on mock data
- [x] 2. API models, CRUD routers, seed data; wire web to API
- [x] 3. Provider interfaces + MockImageProvider; jobs + SSE; character sheets; place images; Lock flow
- [x] 3.5 Character builder: parts library, rig and 16 poses; avatar spec, builder sheets, Meta helper, AI safety; `<Avatar>` + golden-file parity, Lab builder UI
- [x] 4. Story planner, Story Studio steps 1–3, Story Buddy, safety on story text
- [x] 5. Pinned looks, compositor, Make my comic!, Reader with draggable bubbles, final.png, covers, PDF, decision 55 re-checks
- [x] Character safety: `/builder/create` contract, trait list, catalog audit, input/output checks
- [x] Lab: Lock at the bottom, guided Create character flow
- [ ] 6. Real LLM and image providers, Redraw panel, polish
  - [x] 6a. Meta on, measured token limits, Lab face fix, Muse Image places with the image check, kid words checked before every Meta prompt, blocked places left out of plans, Paint it again / Delete on place tiles
  - [x] Cleanup 1: dead code, one-time migrations, the image-sheet pipeline, stale docs, this shorter file (awaiting review)
  - [ ] 6b. Painted portraits (A, done: awaiting review) and painted panels (B, after the B0 measurements) on Muse Image
- [x] 7. Live-test fixes, 12 starter characters, long comics (4 to 30 panels)
- [x] 8. Drawing what the story says: props as their own layer, planner fixes (scenes kept, key moments, story positions, asleep, panels asked again), big panels, no 3-character limit, quick fixes (awaiting review)
