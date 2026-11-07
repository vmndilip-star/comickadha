# Phase 5: Make my comic (compositor, generate job, Reader with real art, PDF)

Saved as given on 2026-11-07. Decision 55 (offline planner during a Meta outage, "not yet AI-checked" text) was approved in the same message and applies here.

---

Read all of this, reply with a short plan and any deviations, then WAIT for approval.
Same ground rules as Phase 4: back up api/storage before any migration, and test only
against a separate API and web server with throwaway data.

### 1. Pinned looks (check this first)
Old comics must never change. Characters are now drawn from their spec, so each
sheet_version must keep a frozen copy of the spec it was locked with. Panels render
from the spec of their pinned sheet_version, never the current one. If this isn't
already true, fix it first (migration + backfill from the current spec for existing
versions) and add a test: re-lock a character with a new hat, and an old comic's
panel still draws without it.

### 2. Compositor (services/compositor.py)
Each panel renders to art.png (background + characters, no bubbles):
- Background: the scene's locked place image, cover-cropped to the panel aspect
  (4:3), or the place's tint colour if the image is missing.
- Characters: rendered straight from the pinned spec with resvg in the planned pose
  and expression (no face pasting), sized by scale, standing on a shared ground line
  at about 88% of the panel height.
- Position left/center/right sets x. Characters face each other: the left character
  faces right and the right one faces left (mirror the cell when needed); a lone
  center character faces the viewer unless the pose is directional.
- Z-order: back to front by position, and the speaker of the first bubble in front.
- Render at 2x for crisp output, and also save a small thumbnail.
- Deterministic: the same inputs make a byte-identical PNG (test this).

### 3. Bubbles
- The Reader draws bubbles as HTML over art.png, so text edits are instant.
- Bubble tails point at the speaker's head, using the rig's head box for the drawn
  pose and position. Narrator boxes sit across the top.
- Text fits automatically: font size steps down to a minimum, then the bubble grows.
  Shout bubbles use Bangers with a spiky outline; think bubbles are cloud-shaped with
  small trailing circles.
- In Edit mode, kids can drag a bubble to move it and drag a corner to resize it
  (reuse @dnd-kit), with the tail re-aimed automatically. Store box and tail in 0–1
  coordinates, as already planned.
- final.png (art + bubbles baked in) is made by the compositor with Pillow for
  thumbnails, covers and the PDF. It's regenerated lazily when it's stale.

### 4. Generate job ("Make my comic!")
- POST /comics/{id}/generate → 202 {job_id}. Requires a full panel plan and all cast
  in it locked (decision 14). Renders every panel, emitting panel_ready per panel over
  the existing jobs SSE, with replay on reconnect.
- Before rendering, re-check every bubble and the title/synopsis with the full
  safety check, unless already AI-checked (decision 55 rules apply).
- check_image runs on every place image used (mock allows; real providers later).
  A blocked image fails that panel with a friendly message.
- The Reader opens as soon as the job starts and fills in panel by panel with a fun
  comic-style "Inking panel 3…" state.
- After rendering, the comic gets a cover: panel 1's final.png with the title in
  Bangers. My Comics and Home cards use it.

### 5. Reader
- Read mode: the comic page laid out as a grid of panels (2 columns on wide screens,
  1 on phones), with the title, the cast row drawn with <Avatar>, and the bubbles.
- Edit mode: select a panel to open the inspector. Change bubble text and type, drag
  bubbles, change a character's expression, pose or position. A face, pose or
  position change re-composites only that panel (fast, with a small spinner). Text
  edits never re-render art.
- Each panel shows its status: planned, rendering, ready, blocked or failed. Failed
  and blocked panels get a friendly message and a "Try again" button.
- "Finish my comic!" sets status finished, with a celebration (confetti, respecting
  reduced motion). Kids can still edit after finishing; that sets it back to draft.

### 6. PDF export
- GET /comics/{id}/pdf: built with Pillow from final.png files. A cover page with
  the title, cast avatars and "Made with Comickatha", then panels laid out 2 per row
  on A4/Letter-friendly pages, with page numbers. Fonts are embedded from api/assets.
- It only works when every panel is ready and all text has passed the AI check
  (decision 55); otherwise a friendly 409 explains what's missing.
- The Reader's "Download PDF" button uses it.

### 7. Housekeeping
- Add shared/ to the API Docker image if it's still missing, and confirm
  `docker compose up --build` can generate a comic.
- Update CLAUDE.md: the compositor, pinned looks, bubbles, the generate job and PDF.

### Tests
- Pinned looks: re-lock with a new hat, and the old comic's panels are unchanged.
- Compositor: deterministic output; characters face each other; a missing place
  image falls back to the tint; the head-box tail target is inside the head.
- Bubble fitting: long text shrinks then grows the box; narrator boxes stay on top.
- Generate: requires a full plan and locked cast (409 otherwise); emits panel_ready
  for each panel; replays on reconnect; a blocked bubble fails only that panel.
- Re-composite: a face change re-renders only that panel; a text change re-renders
  nothing.
- PDF: correct page count for 4/6/8 panels; 409 when a panel isn't ready or text
  isn't AI-checked.
- Vitest: bubble layout and tail aiming; bubble drag updates 0–1 coordinates.

### Done means
In the browser, against the test API: open a planned 6-panel comic, press "Make my
comic!", watch the panels fill in live, refresh halfway and see it pick up again, then
see real avatar art in every panel with bubbles pointing at the speakers. Drag a bubble,
change a face (only that panel redraws), finish the comic with confetti, see the cover
on My Comics, and download a PDF that opens correctly. All tests and the build pass.
Commit as "Phase 5: compositor, Make my comic, Reader, PDF", then STOP.
