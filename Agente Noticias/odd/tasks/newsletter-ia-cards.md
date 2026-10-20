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
- [x] T1 Fix scheduler call (`run_scheduled.ps1` → valid `run.py` flags; log real exit code). Route: inline (1 file, mechanical). Commit `28ed57e`. RDD assess: medium, under_budget.
- [x] T2 SQLite history store replacing Supabase (`db.py`), same public interface; tests. Route: delegated (writer; 4+ files trigger).
- [x] T3 Article model: `image_url`, `company`; researcher collects images/og:image; evaluator extracts company. Route: delegated (writer, combined with T4).
- [x] T4 Card image pipeline: OpenRouter illustration + Pillow logo badge + og:image fallback; logo library. Route: delegated.
- [ ] T5 Template redesign: image-left cards, concept + joke kept, TL;DR removed, CID for all images, mobile + Outlook. Route: delegated.
- [ ] T6 Prompts/tone for all staff (short punchy titles, 2-sentence summaries ~20–30 words). Route: delegated with T5 or inline.
- [ ] T7 End-to-end dry run → `output/preview.html`; manual check in Outlook desktop + mobile. Route: inline.

## Acceptance criteria
- Dry run produces a preview with 5 cards, each with an image + company badge, concept and joke.
- History persists in SQLite and repeated URLs are filtered on the next run.
- Scheduled script runs without argument errors and logs the real exit status.

## Progress / Evidence
- T1: `run.py --auto-approve` → `error: unrecognized arguments` exit=2 (bug confirmed); fixed script parse errors: 0.
- T2: `pytest -q tests` → 7 passed; import smoke ok; no `supabase` references left. New DB starts empty (old history unrecoverable).
- Image model verified on OpenRouter: `openai/gpt-image-2` available (2026-10-20); configurable via env.

- T2 commit `a1835f3`. RDD assess (base master, committed-only, untracked excluded): medium, `slice_budget_reached` (1087 lines, mostly uv.lock) → review due. Preflight STATUS asks for `intended_untracked_selection` (unrelated `Agente IA Personal/CLAUDE.md`); exact v1 JSON shape undocumented, 5 attempts refused → user chose to exclude it via `.git/info/exclude`. Review granted by user → lineage `review-1f2e491b339502b9`, 1 lens (reliability) → **approved**, acknowledged, authority burned. Reviewed boundary advances to `a1835f3`.
  - Follow-up (advisory R3-001, WARNING): `db.py:180` `int(relevance_score)` runs outside the try, so a non-numeric score would raise out of `save_briefing` and break the graceful contract. Fold into next DB-touching task.
- OPENROUTER_API_KEY set by user in `.env` (2026-10-20).

- T3+T4: `pytest -q tests` → 19 passed (parent re-run); `build_graph(send=False)` ok; 1 real OpenRouter call (`POST /api/v1/images`, `data[0].b64_json`, aspect 3:2) → on-style card with OpenAI badge, visually checked by parent. Graph: ranker → [summarizer ‖ card_images] → email_writer. 14 logos from Wikimedia Commons in `assets/logos/`.
  - Open: per-card cost unknown (NEWS_IMAGE_QUALITY=medium default); google/gemini and alibaba/qwen are separate keys.

- T3+T4 commit `cfaae43`. RDD: medium, slice_budget_reached (1003) → user granted review → lineage `review-b0300017cb41c054` (untracked T5 files excluded), 1 lens reliability, running.
- T5+T6 (uncommitted): writer reports 30 tests pass, graph ok, `scripts/render_sample.py` → `output/sample_preview.html`; parent visually checked desktop (640) + mobile (390) screenshots: cards, concept, joke, footer render; mobile stacks. R3-001 fixed (`_as_int`). Also fixed pre-existing KeyError in `service._refresh_briefing_text`.
  - Open: `notebooks/agente_noticias.ipynb` still uses `briefing.tldr`; WIN logo PNG has large padding (looks small); Outlook desktop shows square corners on boxes (cards are baked).
- Review 2 (`review-b0300017cb41c054`) → **approved**, acknowledged, authority burned. Boundary → `cfaae43`. Advisory follow-ups (non-blocking, fold into T7 hardening): graph.py:53-54 fan-out (checked: summarizer returns only `briefing`, no key collision), card_images node 52-69 (`fut.result()` unguarded), service.py:236-238 (replacement card generation inline in webapp request), persist_history.py:43-44, card_images.py:155-170 (suggestion).
- Delivery: running count ~3000 lines (incl. uv.lock) > 400 → ask-on-risk: chain strategy must be asked before committing T5+T6.

- T5+T6 commit `adcc03f` (30 tests pass). Review 3 granted, running.
- Delivery decided (user delegated choice, wants it on GitHub; repo is PUBLIC): **stacked PRs to master**.
  - PR #1 `feat/news-01-scheduler-sqlite` (28ed57e..a1835f3) → master. 630 authored lines, size:exception (code+tests).
  - PR #2 `feat/news-02-card-images` (cfaae43) → PR1 branch. 909 lines, size:exception.
  - PR #3 `feat/newsletter-ia-cards` (adcc03f + T7) → PR2 branch. Pending review 3.

- Review 3 (`review-ecd8260fc5eefccd`) → approved, acknowledged, burned. Boundary → `adcc03f`. Advisory: outlook_sender.py:103-108 send errors crash the graph.
- PRs opened: #1, #2, #3 (https://github.com/Sleeperstar/Langchain-Agente-Noticias/pull/1..3).
- T7a (hardening of all advisories + logo crop) delegated to one writer.

- T7a commit `ec980c7` (pushed to PR #3): 43 tests pass (parent re-run); header logo visually checked. RDD assess: medium, under_budget (331) → pending in slice.
- T7b real dry run started (`run.py --dry-run --headless`).

- T7b dry run #1: Tavily ok (29 unique), all 29 evaluator calls failed with OpenAI 429 `insufficient_quota` → 0 articles, empty "(sin noticias relevantes)" briefing, exit 0. **Bug found**: a scheduled run would email an empty newsletter to all staff.
- Decision (user, 2026-10-20): route text LLM through OpenRouter as well; default `openai/gpt-5-mini` (OpenRouter: $0.25/M in, $2/M out, structured outputs supported).
- [x] T7c LLM factory via OpenRouter + never-send-empty guard (exit 1). Route: delegated (6+ files). Commit `3f69fcb`, 54 tests pass.
- Review 4 (`review-8a3460738fc70b3b`, T7a+T7c, 753 lines) → approved, acknowledged, burned. Boundary → `3f69fcb`. Advisories: legacy bare model id (fixed: `get_model()` prefixes `openai/` + test); webapp `send_now` (no change needed: already refuses empty draft and persists only after a non-raising send); brittle private-API test (suggestion, left).
- T7b dry run #2 (OpenRouter): 29 evaluated → 5 selected, 5/5 AI cards, preview rendered; parent screenshot checked (`real_desktop.png`). exit 0. Note: 3/5 news had no company badge (government/industry news) — expected.

## Next step
Ask user before a real test send to jquispeh@win.pe only (outward-facing); then Outlook desktop + phone check.
