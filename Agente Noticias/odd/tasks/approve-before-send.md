# Feature: approve-before-send

## Objective
Let the user review the exact newsletter before it goes out, then send that same
draft (not a regenerated one) to an explicit recipient list.

## Problem / Why
- Every `run.py` execution searches and writes new content, so a preview cannot be
  "approved" and then sent: the send run produces a different email.
- `.env` is loaded with `override=True`, so recipients cannot be overridden via process
  env; a CLI `--to` is needed (and keeps ad-hoc recipient lists out of committed files).
- First real use (2026-10-27): user wants to preview, then send to 4 colleagues.

## Scope (authorized)
- `run.py --dry-run` saves a send-ready draft (subject, CID HTML, inline image files,
  history payload) next to the preview.
- New `scripts/send_draft.py --to a,b,c`: shows a summary, sends exactly that draft via
  Outlook, persists history, marks the draft as sent (refuses to resend unless forced).
- Tests + README.

Out of scope: webapp changes, Task Scheduler setup.

## Constraints
- Never read/modify `.env`. Recipient addresses never committed.
- Keep the empty-newsletter guard (no draft is sendable with 0 articles).
- Inline images stay ≤ 100 KB (Outlook web limit).

## TDD
- Mode: off (no project/session config). Runner: pytest. Ordinary checks + unit tests.

## Delivery
- Branch `feat/approve-before-send` from master `7376c34`. Single PR (forecast < 400 lines).
- RDD: on (global).

## Tasks
- [x] A1 Save draft on dry run + `send_draft.py` + tests + README. Route: delegated (writer; 3+ files). Commit `3f3aa89`, 80 tests pass (parent re-run).
- [ ] A2 Generate today's draft, show preview to user, wait for approval. Route: inline.
- [ ] A3 Send approved draft to the user-given recipients. Route: inline (after explicit approval).

## Progress / Evidence
- PRs #1–#3 merged into master with merge commits (2026-10-27): `b24046b`, `37de293`, `7376c34`.

- A2 draft generated 2026-10-27 (run_id 01a17f55…): 30 evaluated → 3 selected, all three OpenAI; inline images 17–56 KB. Parent screenshot reviewed. Concerns: no company diversity; first summary too technical ("hipótesis del tiempo exponencial (ETH)").

- User decision: apply one-news-per-company rule + change joke. Commit `e6f1cc1` (prompt VARIEDAD/CERCANIA + `pick_diverse` enforced in code, 84 tests pass).
- Draft #2 (2026-10-27): OpenAI, Walmart, 1Password; new joke (1Password password dialogue); images 18–30 KB. Parent screenshot reviewed.

## Next step
Wait for user approval of draft #2 → A3 `send_draft.py --to <4 recipients>`.
