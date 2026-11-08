# Comickatha

Comickatha lets kids under 16 make their own comics. They design up to three characters and a few places, lock them so they look the same everywhere, write a short story, and Comickatha turns it into comic panels they can edit and export as a PDF.

**Status:** Phase 5 of 6. Kids build characters Bitmoji-style in the Character Lab, then write a story in the Story Studio: the planner turns it into scenes and a panel plan with their real characters in every pose. "Make my comic!" draws every panel live (place, characters facing each other, speech bubbles pointing at the speaker), and the Reader lets them drag bubbles, change words, faces, poses and places to stand, finish the comic and download a PDF. A Story Buddy asks questions to help them think, and story text is safety-checked (personal details stay secret). Everything runs offline by default, so no API keys are needed. Real image models arrive in Phase 6.

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

### Printing a comic

The PDF uses one page size, 8.27 × 11 in (A4's width, Letter's height). **Prints on A4 or Letter. Use Fit to page.**

## What's inside

| Path | What it is |
| --- | --- |
| `web/` | React + Vite + TypeScript + Tailwind app (Home, Character Lab, Story Studio, My Comics, Reader) |
| `web/src/styles/tokens.css` | "Sunday Funnies" design tokens: colours, borders, radii, hard shadows |
| `api/` | FastAPI service (Python 3.11, managed by uv) |
| `docker-compose.yml` | Runs both for local development |
| `CLAUDE.md` | Conventions, architecture decisions and the phase plan |
| `docs/character-safety.md` | The character safety policy: what kids can ask for, what the helpers may answer, and the checks |

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

## Credits

Bubble lettering, covers and PDFs use two fonts bundled in `api/assets/fonts/` (the web app loads the same fonts through `@fontsource`). Both are licensed under the [SIL Open Font License 1.1](https://openfontlicense.org); the licence texts sit next to the font files.

| Font | Used for | Licence |
| --- | --- | --- |
| [Bangers](https://github.com/googlefonts/bangers), © 2010 The Bangers Project Authors | Shout bubbles, titles, covers | `api/assets/fonts/Bangers-OFL.txt` |
| [Nunito](https://github.com/googlefonts/nunito), © 2014 The Nunito Project Authors | Talk, think and narrator bubbles, page numbers | `api/assets/fonts/Nunito-OFL.txt` |
