# HANDOFF → Phase 5 + freeze (temporary — delete when Phase 5 closes)

A briefing for a fresh session with zero conversational context. Read this, then the reading list,
then start with the reverse-audit ledger (it gates the tag). **Not authoritative over `docs/SPEC.md`.**

## (a) Current state

- **`main`, clean; merged through PR #17.** Phases 3 (3a–3d, #8–14), **4** (SPEC §8 — grading + CLV +
  reporting/attribution; D22 taxonomy + D23 renderings; **#16**), **4.5** (SPEC §9 — the `cfb` CLI v2 +
  `season.json` config home + `main.py` deprecation shim; D24; **#17**) are done.
- **Gates green:** `make test` (~527 passed / 4 skipped), `make lint` clean, `make verify-phase-0/1/2/3/4/4-5`
  all PASS.
- **The model is frozen-form but NOT freeze-ready.** The `v2026-frozen` tag is **NOT** cut — the
  **reverse-audit ledger gates it** (below). `factors/`/`engine/`/calibration are final in all but the tag.

## (b) WORK ORDER (do in this order — the first item gates the tag)

1. **Reverse-audit ledger disposition — FIRST; gates the tag.** `docs/CALIBRATION_LOG.md` "Phase-3
   reverse-audit" (2026-07-09). **A1–A5 are owner fix/retire DECISIONS; B1–B10 are owner ratifications
   (values as-found). Resolve A before B** (bugs/retirements change what B must cover). **A2's retire case
   is pre-built** — `run_single_prediction` + `cli.app.main` + the standalone `confidence_calculator`/
   `edge_detector` are **consumer-less** after 4.5 (D24), so retirement only deletes dead code.
   `data_quality` weight 0.4 (B1) is already RATIFIED; the rest of B is PROPOSED. These edit freeze-bound
   `factors/`/`engine/`, so they **must** precede the tag. Propose→pause→ratify; `code-reviewer` before the PR.
   *(Also pre-tag, same window: the **lint-scope fold-in** — `factors/factor_registry.py` +
   `engine/prediction_engine.py` into `LINT_PATHS`/`TYPED_PATHS`; fixing their style debt edits
   freeze-bound files.)*
2. **Phase 5 proper (SPEC §10 + `docs/PHASE5_NOTES.md`)** — GitHub Actions pipeline + a NEW
   `docs/PIPELINE.md`. Workflow files call the **`scripts/*.py` entry points, NEVER `cfb`**. Refined cadence
   (Tuesday catch-up-grade→predict; daily Wed–Sat capture; cron slack). Secrets (`ODDS_API_KEY`,
   `CFBD_API_KEY`). Run the **`pipeline-adversary`** failure-class audit during dev + before each rehearsal.
   Resolve the two open design questions (see (c)). `season.json` is the config home — §10.6's fields ADD to it.
3. **Freeze sequence (`docs/FREEZE_CHECKLIST.md`)** — `calibration-auditor` pre-flight (~Aug 20, must return
   **FREEZE-READY**) → **tag `v2026-frozen`** (owner-only) + extend the freeze-enforcement hook to
   `factors/`/`engine/`/calibration → then **AFTER the tag**: two full-cycle rehearsals (rehearsal-marked
   commits) + a failure-injection drill (proves the auto-Issue path) + a graded **opening-weekend (Week 1) dress rehearsal** (D8 abolished Week 0).

## (c) Ordered reading list (one line each)

1. `docs/SPEC.md` §10 (pipeline) + §3 (freeze) + §16 (binding owner decisions) — the build plan.
2. `docs/PHASE5_NOTES.md` — the BINDING cadence refinements + §6 (season.json config home) + the rehearsal
   regimen (acceptance criteria, not suggestions).
3. `docs/FREEZE_CHECKLIST.md` — every pre-tag obligation + the after-tag rehearsals.
4. `docs/CALIBRATION_LOG.md` "Phase-3 reverse-audit" — the A1–A5/B1–B10 ledger you disposition first.
5. `docs/DECISIONS.md` **D22–D24** — three-layer artifact taxonomy; reports-as-renderings; CLI-v2 dispositions.
6. **Pinned Phase-5 contract paths** (from the ratified Phase-4 plan): claims `data/predictions/2026_week_NN.json`
   (byte-immutable); grading `data/graded/2026_week_NN.json`; reports `reports/2026_week_NN.md` +
   `reports/2026_season.md` + `reports/2025_retro.md`.
7. **The pipeline entry points** (what workflow files invoke): `scripts/build_snapshot.py` (online),
   `scripts/build_predictions.py`, `scripts/fetch_lines.py` (daily capture), `scripts/grade.py` (idempotent
   catch-up), `scripts/build_reports.py`. All expose `main(argv=None)`.
8. **Two open design questions** to resolve in Phase-5 planning: pipeline **commit identity** (Actions-bot vs
   authored — reconcile with D3's no-AI-attribution) and **branch-protection interaction** with bot pushes.
9. Memory: `phase3-calibration-judgment` (project state + doctrines), `custom-subagents`, `owner-working-style`.

## (d) Standing constraints (imperative)

- **Workflow files call `scripts/*.py`, never `cfb`** (the CLI is the human interface; scripts are canonical).
- **Report commits are renderings (D23)** — regenerable, overwritten each run, NOT hook-protected; git history
  is their audit trail. **Predictions are byte-immutable (D22)** — grading writes `data/graded/`, never edits
  `data/predictions/`.
- **Rehearsal commits are clearly marked as rehearsals** — never mistaken for live predictions.
- **Reverse-audit ledger is FIRST and gates the tag**; A-before-B; propose→pause→ratify for every calibration
  disposition; `code-reviewer` on the diff before each PR (NO-GO binding).
- **No AI attribution** in commits/PRs (`includeCoAuthoredBy: false`); no hardcoded team/conference names;
  no fabricated/neutral-filled data.

---
*Delete this file in the PR that closes Phase 5 once its content is absorbed.*
