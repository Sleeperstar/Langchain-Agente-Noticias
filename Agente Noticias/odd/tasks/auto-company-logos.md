# Feature: auto-company-logos

## Objective
Every news card shows its company badge. Prioritize news from the 14 key companies,
keep variety (max one per company), and when a selected news item is about a company
without a stored logo, a LangChain agent finds the official logo, saves it, and only
then the card image is composed.

## Problem / Why
- `company` is a closed enum of 14 keys (the stored logos). News about other companies
  (Walmart, 1Password) get `company=None` → card without badge (draft 2026-10-27).
- The variety rule made non-listed companies more frequent.

## Decisions (user, 2026-10-27)
- Priority to the 14 key companies; if one company dominates, vary the other picks.
- Unknown company → agent searches its logo, saves it, then the card is generated.

## Scope (authorized)
- Evaluator returns the company display name for ANY company (known keys still mapped).
- Ranker prioritizes the 14 key companies, keeps one-per-company.
- Logo finder: LangChain agent (tool-calling) over Wikidata/Wikimedia Commons
  (P154 logo / P8972 small logo); LLM only disambiguates the entity; download, validation
  and normalization are deterministic code. Learned logos persisted in a runtime cache
  (gitignored) + registry (slug → display name, source URL, license page).
- Badge: logo + name; wordmark-style logos (very wide) render logo only; no logo found →
  name-only badge.
- Tests (no network) + README.

Out of scope: webapp changes; manual curation UI.

## Constraints
- Never read/modify `.env`. Keep inline images ≤ 100 KB. A logo lookup failure never
  blocks the run (fallback: name-only badge).

## TDD
- Mode: off (no config). Runner: pytest.

## Delivery
- Branch `feat/auto-company-logos` stacked on `feat/approve-before-send` (PR #4).

## Tasks
- [x] L1 Free company names + ranker priority + logo-finder agent + badge rules + tests. Route: delegated (writer; 5+ files).
- [x] L2 Real dry run: confirm Walmart/1Password-type news get a badge; show preview; send after user approval (pending from approve-before-send A3).

## Progress / Evidence
- PR #4 (approve-before-send) opened; review 6 run from a clean worktree (untracked logo files blocked the main tree) → approved, acknowledged, burned. Advisories to fold here: ranker company case-sensitivity (covered by slug normalization in L1); ranker tops up beyond the model's picks (intended: always 3); `send_draft.py` should mark the draft sent BEFORE persisting history so a crash in between can't allow a resend.

- L1 done: commit `2a8f2d9` (134 tests pass, parent re-run). Live smoke: Walmart Q483551 (P8972 spark) and 1Password Q2150861 (P8972) saved to data/logos; cards visually checked. send_draft ordering fix `25cf217`.
- L2 draft #3 (2026-10-27): OpenAI (GPT-6.1 Terra), Walmart (learned logo badge ✔), UK biosecurity lab (company null → no badge, government story). Parent screenshot reviewed.

- User decision (2026-10-27): only news WITH a logo (a badgeless card breaks the pattern). Commit `bbef1f6`: candidates need a protagonist company; `pick_diverse(accept=_has_logo)` runs ensure_logo per pick and falls back to the next candidate. 136 tests pass.
- L2 draft #4: OpenAI (GPT-6.1 Terra), Walmart, 1Password — all 3 with logo badges. Parent screenshot reviewed.

- User asked to keep draft #4 but restore the draft #3 joke ('compras para la oficina' / 'paquete en la nube'): swapped in draft html + history + preview via one-off script; verified both contain only the new joke.
- **Sent 2026-10-27** (user-approved) with `send_draft.py --yes` to 4 recipients (addresses not recorded in repo): Outlook OK, draft marked sent, history saved (briefing_id 8d5d4087…). Inline images 17–35 KB.

## Next step
Push + PR #5 (stacked on #4); RDD review of the logos slice.
