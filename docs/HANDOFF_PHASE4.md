# HANDOFF → Phase 4 (temporary — delete when Phase 4 is done)

A briefing for a fresh session with zero conversational context. Read this, then the reading list, then
plan Phase 4. **Not authoritative over `docs/SPEC.md`** — it points at the truth, it doesn't replace it.

## (a) Current state
- **Branch `main`, clean; Phase 3 COMPLETE + MERGED** through PR #14. 3a (decomposed pricer + calibration
  evidence), 3b (physical factors + reweight), Bug #7 fix, 3c (situational discipline + NO_BET + confidence
  tiers), 3d (prediction schema v2 + 2025 converter + dry-run acceptance).
- **Gates green:** `make test` (~497 passed / 4 skipped), `make lint` clean, `make verify-phase-1/2/3` all
  PASS — **"Phase 3 complete."** The 2026 wk1 dry-run is 10/10 NO_BET (honest preseason).
- **The model is frozen-form** (constants final in all but the tag). The `v2026-frozen` tag is NOT yet cut —
  see `docs/FREEZE_CHECKLIST.md`. Phase 4 is **freeze-exempt** (lives in `analytics/`), so it can proceed
  in parallel with freeze prep, but must build to the already-ratified conventions.

## (b) What Phase 4 delivers (SPEC §8) — measurement, NOT calibration
Phase 4 has **no calibration batches**; it consumes prediction/result JSON only (no live API). Build a
coherent `analytics/` module (extends the existing `analytics/projections.py`, `calibration_evidence.py`,
`predictions.py`):
1. **CLV** — the primary KPI. Fill `closing_spread`/`clv`/`graded_at` at grading per the **ratified
   convention** (`docs/SCHEMA.md`: positive = our number beat the close; home ⇒ `vegas−close`, away ⇒
   `close−vegas`; null vs push semantics). The pure `utils.prediction_schema.clv` already encodes it; wire
   `data.normalize.odds.closing_observation` (per-game as-of-T) into grading. Report CLV overall + by tier.
2. **Calibration** — Brier score + a calibration table/curve by **A/B/C tier** (do 65%-ish picks win ~65%?).
3. **Classic KPIs** — ATS%, ROI @ -110, Sharpe, max drawdown, longest losing streak, with Wilson intervals.
4. **Attribution** — per-factor: when factor X fired ≥ threshold, its ATS% + CLV. **This must answer the
   open `reasoned` CALIBRATION_LOG questions** (per-sub-signal) — it is what converts them to `measured`
   for 2027. Design it around the open log entries.
5. **Selectivity** — grade `NO_BET` games (what would have happened) + high-variance-filtered games: is the
   skip validated? Add an ATS win/loss/**push** outcome field alongside `clv`.
6. **Weekly + season report generator** — one command → `reports/2026_week_NN.md` + `reports/2026_season.md`
   (plain markdown tables; committed by the Phase-5 pipeline). Say plainly when a quiet slate is selectivity,
   not breakage.

**Acceptance (SPEC §8):** running analytics over the archived 2025 data produces a full retro report
(validates the analytics code + becomes README material). Use the pure v1→v2 converter for the 2025 archive.

**After Phase 4:** **4.5** (CLI v2 subcommands, SPEC §9) and **5** (automation pipeline, SPEC §10 +
`docs/PHASE5_NOTES.md`) — plus the freeze itself (`docs/FREEZE_CHECKLIST.md`).

## (c) Ordered reading list (why each matters)
1. `docs/SPEC.md` §8 (Phase 4 build + the freeze-prep pointer banner) + §3 (Calibrated Freeze) + §14
   (agentic process) + §16 (binding owner decisions).
2. `docs/SCHEMA.md` §3 — the **schema v2** record + the **CLV convention** (sign, null-vs-push) you implement
   + the reproducibility/VOLATILE contract. The golden `docs/examples/prediction_schema_v2_2026_week_01.json`
   is the canonical shape.
3. `docs/CALIBRATION_LOG.md` — the frozen-form Phase-3 batch; the `reasoned` entries whose questions
   attribution must answer. Do NOT cite the archive confidence→ATS / edge→ATS tables as evidence (Bug #7).
4. `docs/DECISIONS.md` — D15 (base/total gap), D16 (dry-run vehicle), D17 (2025 regrade — the honest 46.6%
   baseline), D19/D20/D21 (fabrication sweep + schema v2). `docs/CODE_AUDIT.md` — the module map + the
   rebuilt Phase-4/5 carry-forward.
5. `analytics/calibration_evidence.py` (the archive reader/join + `ats_outcome`, incl. the push rule),
   `analytics/predictions.py` + `utils/prediction_schema.py` (schema v2 + `clv`), `data/snapshot/lines.py`
   + `data/normalize/odds.py::closing_observation` (the as-of-T closing line), `scripts/grading.py`.
6. `docs/PHASE5_NOTES.md` + `docs/FREEZE_CHECKLIST.md` — the operational constraints Phase 4's reports feed
   into, and the freeze obligations.
7. Memory: `phase3-calibration-judgment` (the forward doctrines) + `owner-working-style` + `custom-subagents`.

## (d) Standing constraints (imperative)
- **Phase 4 is measurement, not calibration** — build to the frozen conventions; don't re-open a ratified
  number. Any new constant Phase 4 introduces still gets a logged, evidence-class-labeled justification.
- **CLV/grading uses each game's own as-of-T close** (`closing_observation`), never a single weekly cutoff;
  fill the documented convention, don't invent one. Distinguish `null` (not graded / honest-missing) from a
  real `0.0` and from an ATS push.
- **No fabricated / neutral-filled data** (record `missing` + provenance); **no hardcoded team/conference
  names** (registry only); **no AI attribution** in commits/PRs (`includeCoAuthoredBy: false`).
- `data/predictions|results|archive|lines|ratings|projections` and `reports/` are **append-only** (hook-
  enforced); the 2025 archive is **read-only** — the converter never rewrites it.
- **Freeze discipline:** the `v2026-frozen` tag (~Aug 24) freezes `factors/`/`engine/`/calibration; Phase 4
  is freeze-exempt (`analytics/`), but the freeze must precede the first live prediction run.
- **Run `code-reviewer` on the diff before each PR (NO-GO binding); paste `make verify-phase-N` output as PR
  evidence; propose→pause→ratify for anything owner-only.**

---
*Delete this file in the Phase-4 PR once its content is absorbed / no longer needed.*
