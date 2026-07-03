# 2025 Season Archive

Frozen copy of the 2025 forward-test prediction and result JSONs — the audit
trail behind the project's credibility claim (300 games, 57.0% ATS, +8.82% ROI
at -110; see the root `README.md`).

## Provenance

- **Source:** produced by the 2025 model, frozen 2025-08-25 and run forward
  through Week 14 with no algorithmic modifications. Predictions were committed
  to git before each week's games; results recorded after.
- **Origin repo:** the original 2025 repository is **private and will not be
  linked** (SPEC §16.5). These JSONs are imported here so the 2026 repo carries
  the audit trail directly (SPEC §4.3 / §16.5).
- **Relationship to `data/predictions/` & `data/results/`:** identical copies of
  the same 14 weekly prediction files and 14 result files that also live in
  `data/predictions/2025_week_NN.json` and `data/results/2025_week_NN_results.json`.
  This archive is a stable, clearly-labeled home for the 2025 record; the
  originals are left in place so existing scripts keep working (decision D2 in
  `docs/DECISIONS.md`).

## Contents

- `predictions/2025_week_01.json … 2025_week_14.json` — pre-game predictions
  (Vegas spread, factor breakdown, confidence, timestamps).
- `results/2025_week_01_results.json … 2025_week_14_results.json` — graded
  outcomes.

## Immutability

Per CLAUDE.md binding principle 5, everything under `data/archive/` is an
append-only historical artifact. Do not edit or delete these files. From 2026
onward the automated pipeline (SPEC Phase 5) produces future audit trails
automatically via timestamped commits.
