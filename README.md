# Comickatha

Comickatha lets kids under 16 make their own comics. They design up to three characters and a few places, lock them so they look the same everywhere, write a short story, and Comickatha turns it into comic panels they can edit and export as a PDF.

**Status:** Phase 3 of 6. Locking a character draws its full character sheet (16 poses, 6 faces) live in the Character Lab, and locking a place paints its picture. Everything runs on a built-in mock artist, so no API keys are needed. Story planning and comic drawing arrive in Phases 4 and 5.

## Quick start

You need [uv](https://docs.astral.sh/uv/) and Node 20.15 or newer. No API keys are needed: everything runs on mock providers. The commands work in Windows PowerShell; run them one line at a time.

```powershell
# 1. API (http://localhost:8010). Creates and seeds the database on first start.
cd api
uv sync
uv run uvicorn app.main:app --reload --port 8010

# 2. Web app (http://localhost:5173), in a second terminal
cd web
npm install
npm run dev
```

Reset to the demo data (one kid, 3 characters, 3 places, 3 comics): `uv run python -m app.seed` from `api/`.

Or with Docker Desktop running: `docker compose up --build`.

To change settings, copy `.env.example` to `.env`.

## What's inside

| Path | What it is |
| --- | --- |
| `web/` | React + Vite + TypeScript + Tailwind app (Home, Character Lab, Story Studio, My Comics, Reader) |
| `web/src/styles/tokens.css` | "Sunday Funnies" design tokens: colours, borders, radii, hard shadows |
| `api/` | FastAPI service (Python 3.11, managed by uv) |
| `docker-compose.yml` | Runs both for local development |
| `CLAUDE.md` | Conventions, architecture decisions and the phase plan |

## Checks

```powershell
# from api/
uv run pytest
uv run ruff check .
uv run mypy app tests

# from web/
npm run lint
npm run build
npm run gen:types   # regenerate src/types/api.ts after API schema changes
```
