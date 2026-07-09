# Calibration-audit exclusion list

Persisted allow-list of frozen-path numeric literals that are **structural / non-calibration** — the
`calibration-auditor` reverse check reads this and **excludes** these so its findings are signal-only
(a frozen number here does NOT need a CALIBRATION_LOG entry). Established at the 2026-07-09 shakedown.
**Only add a genuinely non-tunable literal here** — when in doubt, it belongs in the log, not this file.

## Excluded (structural / covered / inert)

- **`engine/power_ratings.py` `EloConfig` fields** — fully covered by CALIBRATION_LOG D9 / D11 / D12
  (`k_early/k_late/k_decay_games/mov_c/mov_b/hfa_elo/elo_per_point/margin_sigma/uncertainty_*/…`).
  `baseline = 1500.0` — standard Elo convention, structural.
- **`engine/power_ratings.py:81` `early_season_weeks = 3`** — SPEC §6.2/§16.2 season structure, not a tunable
  magnitude.
- **`factors/physical_coefficients.py`** — every coefficient covered by CALIBRATION_LOG 3b.1.
- **`engine/prediction_engine.py:24-33`** — `NO_BET_CONFIDENCE_FLOOR` (0.50), `CONFIDENCE_TIER_A_MIN` (0.65),
  `CONFIDENCE_TIER_B_MIN` (0.50), and the dynamic `min_edge_threshold` ladder (0.75/1.0/1.5) — covered by
  CALIBRATION_LOG 3c.5 / 3c.6.
- **`factors/base_calculator.py:44-60`** — `BaseFactorCalculator.__init__` defaults (`activation_threshold=0.5`,
  `max_impact=5.0`, `±5.0` range): every live factor overrides them; inert.
- **`factors/base_calculator.py` `get_explanation` cutoffs (`abs(value) < 0.1` etc.)** — human-readable text
  only, no output effect.
- **Rounding / formatting** — every `round(x, N)`, `f"{x:.2f}"`, width specifier.
- **Epsilons / tolerances** — `1e-9` push/float comparisons.
- **Loop / array bounds, enum ordering, indices** — `weights[:len(...)]`, slice bounds, etc.
- **HTTP status codes, retry counts, timeouts** in the data clients (operational, not model calibration).
- **`tests/`** — all fixtures/tolerances are out of scope by design.

## NOT excluded — these ARE calibration and must be logged (see the reverse-audit ledger in CALIBRATION_LOG)

The shakedown found large **unlogged** calibration surface that does NOT belong here: the internal factor
formulas (DesperationIndex blend/scale, momentum/coaching/style-mismatch component weights + thresholds),
the `factor_registry._configure_factor_hierarchy` threshold/max_impact overrides, `variance_detector`
CV cutoffs (a hard NO_BET gate), `prediction_engine._calculate_confidence_score` + the `prediction_type`
ladder, and the standalone `confidence_calculator`/`edge_detector` engine. These are PROPOSED /
decision-pending in `docs/CALIBRATION_LOG.md` (Phase-3 reverse-audit) and on `docs/FREEZE_CHECKLIST.md`.
