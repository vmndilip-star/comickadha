# Cleanup 1: dead code, the unused image-sheet pipeline, stale docs, a slimmer CLAUDE.md

Saved as given on 2026-11-22. Phase 6a was committed first (`316dde3`), so this cleanup starts from a clean tree.

---

Save this prompt as given to docs/phases/cleanup-1.md before starting.

Read all of this, reply with a short plan and any deviations, then WAIT for approval.

Before anything else: if Phase 6a isn't committed yet, stop and tell me. This cleanup must start from a clean tree so it can be reviewed and reverted on its own.

Ground rules

Behaviour stays the same, except where a part below says otherwise.
Before removing anything, show the grep evidence that nothing uses it. Remove its tests with it. After any API change, run npm run gen:types and fix the web.
Run all 9 checks after each part.
Don't merge or move files just to have fewer. Merge only real duplicates (part 1 names one) and list any others you find, then wait.
Don't touch .env. Don't write to api/storage. Leave everything uncommitted. At the end I'll ask for one commit per part.
1. Dead code

API:

LLMProvider.complete and MetaLLMProvider.complete: no callers except tests/test_meta_provider.py. Remove them and that test.
looks.pinned_spec: no callers. Remove it.
pdf_export.page_count: used only by tests. Use it in build_pdf if build_pdf works out the page count itself; otherwise remove it.
POST /backgrounds/{id}/unlock: remove it. Decision 90 says no place unlock until place versions are pinned, and this endpoint lets any client unlock and repaint a place, which changes old comics on their next redraw. Keep PATCH, since editing a draft is harmless and a locked place already returns 409.

Web:

Remove the Swatch component (components/ui/Swatch.tsx), PLACE_TINTS in lib/labels.ts and the PanelStatus type in types/index.ts: nothing uses them.
Merge the duplicated option lists. types/index.ts (TRAITS, BODY_TYPES, ROLES, ...) and avatar/spec.ts (TRAIT_IDS, BODY_TYPES, ROLE_IDS) are two TypeScript copies of the same lists. Keep one source and import it in the other place. If it's simple, add a type-level check against the unions in the generated api.ts.
Don't delete revokeDrawingConsent. Wire it up instead: add "Turn off drawing uploads" to the profile menu, shown only while consent is on, calling DELETE /me/drawing-consent. A kids' app should let a grown-up take back that OK. Include a render-to-string test.

Find the rest with tools, without adding them as dependencies: npx knip for unused web files and exports, and uvx vulture for the API. List what they find and wait before deleting anything that isn't named above. Some hits will be false positives (FastAPI routes, pytest fixtures, Pydantic fields).

2. One-time migrations (check first)
Candidates: app/avatar/migrate.py (old pre-3.5b specs, off-list traits), db.has_old_character_specs, looks.needs_backfill and looks.backfill_versions, their startup hooks and their tests.
With my OK, copy api/storage/comickatha.db to the scratchpad and check the copy, read-only. Remove them only if no character has an old spec, an off-list trait or a missing frozen look. If anything still needs them, keep them and tell me.
Keep add_missing_columns and the startup backup: they're general mechanisms. Keep avatar/words.py: the offline helper uses it.
3. The image-sheet pipeline (SHEET_PROVIDER=image)

This is the biggest removal. List exactly what you'd remove and keep, then wait.

Why: comics never use image sheets, because the compositor draws every character from its pinned spec. 6b won't use them either: it restyles each character's pose drawing on its own (or whole panels). Today the pipeline only feeds a Lab preview of a look kids never see in their comics.
Remove: ImageSheets, build_sheet, draw_cells, validated_cells, the batch and grid constants only it uses, prompts/character_sheet.md, the SHEET_PROVIDER setting (builder becomes the only sheet provider), KnowsHeadBoxes and the mock's sheet drawing (its Layout/Cells/Sheet parsing), imaging.estimate_head_box and slice_grid if nothing else uses them, HeadPositionEditor, PATCH /characters/{id}/heads/{pose}, HeadOffset, faceOverlay and applyOffset in lib/sheet.ts, SheetStage's image branch, and the image tests in test_character_sheet.py.
Keep: MuseImageProvider, the mock's place drawing, imaging.key_magenta, coverage and fit_size (places use them and 6b will), SheetProvider, SheetSpec, SheetCells, run_sheet_job and BuilderSheets.
Data: if any manifest in the copied database has renderer "image", keep the schema able to read it, so old characters still display.
CLAUDE.md: a new decision that supersedes decisions 28 and 30.
4. Stale comments, docstrings and config

Fix whatever is still stale after 6a:

services/init.py ("planner, compositor and safety arrive in later phases")
models/job.py (mentions redraw jobs, which don't exist)
routers/jobs.py (the event list leaves out panel_ready and panel_failed)
providers/llm.py ("the planner in Phase 4")
schemas/manifest.py ("so the compositor can paste an expression")
the config.py and .env.example comments on LLM_PROVIDER and IMAGE_PROVIDER

Also remove ANTHROPIC_API_KEY, GEMINI_API_KEY and OPENAI_API_KEY from .env.example: no code reads them. A key gets added back when code uses it.

5. A slimmer CLAUDE.md

CLAUDE.md is about 54 KB and is loaded into every Claude Code session.

Move the full decision log (1 to the latest) to docs/decisions.md, unchanged.
CLAUDE.md keeps:
the working agreement, how to run it and the checks, and the generated files
a short architecture map: a few lines per area, pointing at files
the rules that must always hold: mock-first; nothing unchecked reaches Meta and every generated picture is checked; old comics never change (pinned looks); kid-friendly errors; at most 3 characters; no secrets
the environment notes and the phase list
a one-line index of the decisions still in force, linking to docs/decisions.md
Aim for under 15 KB. Nothing is lost: anything taken out of CLAUDE.md is in docs/decisions.md or the code.
Update the README's "What's inside" table (add shared/, scripts/ and docs/).
6. Optional: a smaller first load
Lazy-load the Lab, Create character, Studio and Reader pages with React.lazy, and leave the catalog where it is.
Measure the main chunk before and after. Keep the change only if the first load shrinks noticeably.
Leave alone (not trash)
Generated files: catalog.json, golden.json, api.ts and the lock files. The tests and the web need them.
The fonts and their licences, and the phase prompts (working agreement).
The Python and TypeScript avatar twins: they're duplicated on purpose and tested against each other.
Panel.mode, Panel.image_key and PanelMode "redraw": 6b uses them.
GET /characters/{id}/manifest?version=, GET /panels/{id}/final.png and GET /api/health: they're cheap and useful.
