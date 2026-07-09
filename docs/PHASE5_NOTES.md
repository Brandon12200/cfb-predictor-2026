# Phase 5 — Automation Pipeline: settled operational decisions

Binding refinements to SPEC §10, recorded from owner discussions so they aren't lost between sessions.
These **supersede** the original §10 cadence sketch where they differ. Phase 5 is GitHub Actions; these
are the constraints its workflow files must satisfy. (The freeze precedes all of it — `docs/FREEZE_CHECKLIST.md`.)

## 1. Cadence accounts for the real CFB week

The naïve "Tuesday predict / Saturday close / Sunday grade" sketch misses how the football week actually
runs. The binding cadence:

- **Tuesday — predict, but grade first.** The Tuesday job **BEGINS with a catch-up grade** of any
  previously-ungraded completed games, *then* runs the week's predictions. The catch-up grade covers
  Sunday/Monday games and any **postponements/reschedules** that completed since the last grade, and it is
  **idempotent** (re-grading an already-graded game is a no-op). Then fetch slate + snapshot → run engine →
  write `data/predictions/2026_week_NN.json` → commit (`predictions: 2026 week NN (pre-kickoff)`).
- **Daily Wed–Sat — line capture.** Line capture is **daily**, not Saturday-only. Thursday and Friday games
  must have honest **pre-kickoff** closing observations, which a Saturday-only capture would miss; daily
  capture also handles the weekday scatter of championship/bowl games if those come into scope. Each
  observation is appended to the append-only `data/lines/YYYY_week_NN.json` store (never mutates the
  snapshot — the 1c hash-exclusion rule).
- **Sunday — grade** the main slate as planned (final scores → `data/results/` → ATS + CLV → analytics →
  reports).
- **Each game's closing line = the last observation before THAT game's own kickoff** — the 1c **as-of-T**
  model (`data.normalize.odds.closing_observation`). This is per-game, not a single weekly cutoff, and
  needs **no schema work** — the machinery already exists.

## 2. GitHub cron jitter is real

GitHub Actions scheduled runs can fire **late** (minutes, sometimes more, under load). Schedule every
capture/predict job with **slack before the earliest relevant kickoff window** so a jittered run still
completes pre-kickoff. Never schedule a capture to land at the kickoff minute.

## 3. Preseason validation regimen (part of Phase-5 acceptance)

Beyond the SPEC §10 "one simulated cycle + one live dry-run," acceptance **requires**, in mid-August, run
AFTER the `v2026-frozen` tag (they exercise the frozen model end-to-end):

- **Two clean full-cycle rehearsals** against the real week-1 slate (predict → daily capture → grade →
  report), on **rehearsal-marked commits** (clearly labeled, not mistaken for live predictions).
- **One deliberate failure-injection drill** — revoke a key / kill a source mid-run — that **proves the
  auto-Issue path** actually opens a GitHub Issue with logs and the pipeline degrades/recovers as designed.
- **A graded Week-0 / opening-weekend cycle** as the live dress rehearsal (real slate, real grading).

These are on `docs/FREEZE_CHECKLIST.md` under "after the tag."

## 4. Design questions to resolve in Phase-5 planning

- **Pipeline commit identity** — do the automated commits come from the **GitHub Actions bot** or an
  **authored** identity? (Affects the audit-trail story: SPEC §10 leans on the commit as tamper-evident
  provenance, and D3 forbids AI attribution — reconcile these for machine commits.)
- **Branch-protection interaction with bot pushes** — if `main` gets branch protection, confirm the
  Actions bot can push the weekly prediction/result/report commits (or route through a PR/allowlist).

## 5. Freeze-prep

All freeze obligations live in `docs/FREEZE_CHECKLIST.md` (tag by ~Aug 24; freeze-enforcement hook extended
to `factors/`/`engine/`/calibration config at tag time; the `calibration-auditor` pre-flight; the lint-scope
follow-up). Rehearsals (item 3) run **after** the tag.
