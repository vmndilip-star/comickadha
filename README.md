# Comickatha

Comickatha lets kids under 16 make their own comics. They design up to three characters and a few places, lock them so they look the same everywhere, write a short story, and Comickatha turns it into comic panels they can edit and export as a PDF.

**Status:** Phase 4 of 6. Kids build characters Bitmoji-style in the Character Lab, then write a story in the Story Studio: the planner turns it into scenes and a panel plan with their real characters in every pose, and they can tweak every word, face and pose. A Story Buddy asks questions to help them think, and story text is safety-checked (personal details stay secret). Everything runs offline by default, so no API keys are needed. Drawing the finished comic arrives in Phase 5.

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
npm test
npm run build
npm run gen:types   # regenerate src/types/api.ts after API schema changes
```
