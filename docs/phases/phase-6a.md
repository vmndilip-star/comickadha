# Phase 6a: Meta on, token limits, Lab face fix, Muse Image places with an image check

Saved as given on 2026-11-22.

---

Save this prompt as given to docs/phases/phase-6a.md before starting.

Read all of this, reply with a short plan and any deviations, then WAIT for approval. Same ground rules as before: back up api/storage before any migration, test only against a separate API and web server with throwaway data (e.g. API on 8021, web on 5176), never touch .env yourself (tell me the exact lines to add), and never print keys.

Context: Phase 6 now uses Meta for images too. muse-image-1.0 is listed for my key on https://api.meta.ai/v1. This prompt switches Meta on properly, fixes three problems the repo audit found, and adds Muse Image for places, with a real image safety check so no generated picture reaches a kid unchecked. 3D-look panels (Redraw panel) come in 6b and build on this.

1. Meta on for the demo
My .env has only META_API_KEY, so the app runs offline. Tell me the lines to add (LLM_PROVIDER=meta, META_MODEL=muse-spark-1.3, and the image settings from part 4).
Update README and CLAUDE.md so the demo setup lists every line needed.
2. Token limits (decision 80)
These calls still use limits set before the model was measured: describe, surprise and ideas (helper_meta.py, default 1024 tokens, 20 s), from-drawing (vision, 1024, 20 s; it is missing from decision 80's list), Story Buddy (story_buddy.py:284, 600), planner (story_planner.py:459 and :478, 1200 and 3000).
A cut-off reply raises LLMError in MetaLLMProvider, and Guard.ask treats LLMError as an outage and goes straight to the offline helper, with no retry. So a low limit silently turns Meta features offline.
Put every Meta call's max_tokens and timeout in one constants block. With my OK, make a few real calls per site (throwaway server, LLM_PROVIDER=meta), then set each limit to about twice the largest completion you see, with a matching per-call timeout, as helper_meta.create already does (6000 tokens, 60 s).
Fix the docs that say "a malformed reply is retried once" (CLAUDE.md, ai_guard.py docstring) to say what the code does. Only change the code if real runs show malformed JSON that a retry would fix.
3. Lab: locked builder characters get the wrong face
SheetStage pastes the front face cell over every face-visible pose, whatever the renderer (web/src/components/character/SheetStage.tsx, lib/sheet.ts faceOverlay). Builder sheets already draw each pose with its own face, so ¾ and action poses get a front face pasted on top. First confirm it in the browser on the throwaway server.
Fix: when manifest.renderer is "builder", draw <Avatar spec={manifest.spec} pose expression> (the frozen look, exactly how panels draw it) instead of cell + pasted face. Keep the paste for "image" sheets.
Fix the stale comment in lib/sheet.ts ("The Phase 5 compositor uses the same maths"): the compositor never pastes faces.
4. Muse Image provider (places first)

What the Muse Image docs say (verify each with real calls before relying on it):

Model muse-image-1.0 on Meta Model API, $0.01 per image, base URL https://api.meta.ai/v1.
The endpoints mirror the OpenAI Images API: POST /v1/images/generations (text to image) and POST /v1/images/edits (image to image, and composition with several input images).
Output up to 1600 px. size sets an aspect ratio; the server reduces it to a ratio rather than exact pixels (their example uses 1536x1024).
References are named by position in the prompt ("the second reference"). Reopen or recreate each reference file object for every call: an exhausted one silently breaks it.
Not documented: seed support, response format (b64_json or URL), accepted ratios.

Build:

config.py: image_provider Literal["mock", "muse"]; META_IMAGE_MODEL (model names come from .env, as for META_MODEL); an image timeout setting. Refuse "-contributor" models with the existing check_model_name.
Startup refuses IMAGE_PROVIDER=muse unless LLM_PROVIDER=meta, with a clear message: real images need the classifier and the image check. Fail closed by configuration.
providers/muse_image.py: MuseImageProvider implementing the existing ImageProvider protocol unchanged. images.generate without references, images.edit with them (fresh BytesIO per reference per call). Decode the result and re-encode with imaging.to_png (no metadata). If the returned aspect differs from the requested size, cover-crop to the requested aspect before returning (the protocol promises the aspect). Ignore seed if the API has none, and say so in a comment. Wrap openai errors in one error type.
Keep MockImageProvider the default; seeding and tests keep using the mock.
Places use it through the existing place job (image_gen.build_place). Keep the "Sunday Funnies" style in background.md so places still match the 2D characters; the 3D look comes in 6b.
An image error at place lock becomes the existing kid message ("We couldn't paint X. Tap Lock to try again!"), not the generic one.
Check _valid_place against real Muse output: the magenta keying (tolerance 80) may count pink or purple scenery as background and reject good images. If it does, use a stricter tolerance for full scenes only, with a test.
5. Nothing unchecked goes to Meta, and nothing unchecked comes back
Words in: today place lock runs only the local checks (check_and_log with no llm). With IMAGE_PROVIDER=muse, the place name and description must also pass the classifier before anything is sent to Muse. A classifier outage means nothing is sent: the place stays draft and the kid gets a friendly message (503 not_checked, or a better existing code).
Pictures out: make safety.check_image real when an LLM is set: one vision call through LLMProvider.complete_json(image_png=...) with a strict schema (safe for kids; no real people; no text, logos or brands; not scary) and its prompt in app/prompts/image_safety.md (registered in REQUIRED). Fails closed: a block or an outage is not allowed. Logged as kind "image" as now. Without an LLM it keeps today's behaviour.
Run it at place lock, before the image is saved or announced (cell_ready). A block or an outage fails the job with a kid message and saves nothing. Images are only created at lock, so the panel-time call in comic_maker can stay the cheap check.
The vision model is META_VISION_MODEL (defaults to META_MODEL). Confirm with one real call that it accepts an image. If it doesn't, stop and tell me: 6b would add Claude as the checker instead.
6. Real calls (ask me first)
At most about 10 Muse calls (about $0.10) plus the text and vision calls from parts 2 and 5.
Confirm and write down: the response format, which sizes and ratios come back, latency, whether images.edit accepts 2–3 input images in one call (6b needs this), and whether the vision model accepts images.
Record the findings in CLAUDE.md as decisions.
7. Docs
CLAUDE.md: new decisions for this phase; mark decision 15's Gemini/OpenAI image plan as superseded by Muse Image; fix the drift the audit found (decision 1's MockLLMProvider does not exist; decisions 3 and 25 describe face pasting the compositor never does; decision 37's bundle is now 1.12 MB / 208 KB gzipped; the error-code list is missing already_locked, busy, no_profile, not_allowed and http_error; the routers list is missing jobs and health).
.env.example: IMAGE_PROVIDER=muse documented, META_IMAGE_MODEL= (empty), the image timeout, and the missing PANEL_REVEAL_SECONDS, RECHECK_SECONDS and SEED_ON_STARTUP.
README: the demo setup, and the 3 checks its Checks list is missing.
Tests (offline, with fake clients, like tests/fakes.py)
MuseImageProvider: generate without references uses images.generate; with references uses images.edit with every reference; a wrong aspect is cover-cropped; errors become one error type; "-contributor" is refused; IMAGE_PROVIDER=muse with LLM_PROVIDER=mock stops startup.
Place lock with muse: the classifier runs on name and description first; a classifier outage sends nothing to the image provider and leaves the place draft; a blocked image or an image-check outage fails the job and saves nothing.
Token limits: every Meta call site sends its configured max_tokens and timeout.
Lab: a builder manifest draws the live avatar with no pasted face; an image manifest still pastes.
All 9 CLAUDE.md checks pass.
