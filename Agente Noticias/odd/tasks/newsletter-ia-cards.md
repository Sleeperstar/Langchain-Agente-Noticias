# Feature: newsletter-ia-cards

## Objective
Turn the weekly AI briefing into a short, attractive newsletter for **all WIN staff**:
news cards with an illustration on the left (company logo badge baked in, DataCamp
"This week in AI" style) and a short summary on the right. Keep "Concepto del día"
and the closing joke. Drop the TL;DR block.

## Problem / Why
- The old briefing targeted managers; the new audience is every employee, so tone must be
  simpler and lighter, and the layout less dense.
- The Supabase project used for anti-repetition history was deleted
  (`nknpunmqivtvbiwaubqd` no longer resolves), so history is silently disabled.
- The scheduled task passes `--auto-approve`, which `scripts/run.py` does not accept.

## Scope (authorized)
- Replace Supabase with local SQLite (images stored as files on disk, DB stores paths).
- Add per-news image + company fields; build card images (AI illustration via OpenRouter
  + logo badge composited with Pillow; fallback to article og:image).
- Redesign the email template (cards, WIN palette, mobile-friendly, Outlook-safe, CID images).
- Adjust prompts/tone for all staff. Keep concept + joke; remove TL;DR.
- Fix scheduler invocation.

Out of scope: changing the sending channel (stays Outlook COM), webapp redesign beyond
what the new template requires.

## Constraints
- Images embedded as CID attachments (Outlook blocks remote images by default).
- Never let the image model draw logos; logos are composited from official files.
- Do not read `.env` from the assistant (deny rule); user provides keys there.
- Artifacts in English; email copy in Spanish (neutral, friendly).

## Decisions
- 2026-10-20: SQLite over Supabase/Docker — agent runs on one PC (Outlook COM); no external
  service to pause/delete. Images on disk, not in DB.
- 2026-10-20: Keep "Concepto del día" and joke; remove TL;DR.

## TDD
- Mode: off (no project/session TDD configuration). Source: none configured.
- Runner: pytest (to be added as dev dependency). Ordinary functional checks + unit tests
  for new pure logic (SQLite store, badge compositing).

## Delivery
- Branch: `feat/newsletter-ia-cards` (repo root: `Escritorio/Langchain`).
- Strategy: ask-on-risk. Forecast: ~900–1200 authored changed lines → will ask chain
  strategy before exceeding ~400.
- RDD: on (global).

## Tasks
- [ ] T1 Fix scheduler call (`run_scheduled.ps1` → valid `run.py` flags; log real exit code). Route: inline.
- [ ] T2 SQLite history store replacing Supabase (`db.py`), same public interface; tests. Route: delegated (writer).
- [ ] T3 Article model: `image_url`, `company`; researcher collects images/og:image; evaluator extracts company. Route: delegated.
- [ ] T4 Card image pipeline: OpenRouter illustration + Pillow logo badge + og:image fallback; logo library. Route: delegated. Needs: OPENROUTER_API_KEY, model verification.
- [ ] T5 Template redesign: image-left cards, concept + joke kept, TL;DR removed, CID for all images, mobile + Outlook. Route: delegated.
- [ ] T6 Prompts/tone for all staff (short punchy titles, 2-sentence summaries ~20–30 words). Route: delegated with T5 or inline.
- [ ] T7 End-to-end dry run → `output/preview.html`; manual check in Outlook desktop + mobile. Route: inline.

## Acceptance criteria
- Dry run produces a preview with 5 cards, each with an image + company badge, concept and joke.
- History persists in SQLite and repeated URLs are filtered on the next run.
- Scheduled script runs without argument errors and logs the real exit status.

## Progress / Evidence
- (none yet)

## Next step
T1.
