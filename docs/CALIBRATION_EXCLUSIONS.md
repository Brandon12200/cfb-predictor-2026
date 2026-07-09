# Calibration-audit exclusion list

Persisted allow-list of frozen-path numeric literals that are **structural / non-calibration** — the
`calibration-auditor` reverse check reads this and **excludes** these so its findings are signal-only
(a frozen number here does NOT need a CALIBRATION_LOG entry). Established at the 2026-07-09 shakedown.
**Only add a genuinely non-tunable literal here** — when in doubt, it belongs in the log, not this file.

## Guard principle (read before excluding anything)

Every exclusion is either **(1) a specific literal pinned to a `file` / `file:line`**, or **(2) a
genuinely non-tunable literal KIND** (a rounding digit, an epsilon, an index/loop bound) — which applies
**only to that structural literal itself**, never to a value it operates on. **Never exclude by domain
flavor.** A geo/physics/market/season-flavored VALUE that tunes model output is **calibration**, not
structural. The canonical example: the 3b **altitude threshold `4000` ft** and `altitude_value 1.2`
(`factors/physical_coefficients.py`) are geo-flavored but are **ratified calibration (CALIBRATION_LOG
3b.1)** and must never fall under a "physics/geo" exclusion by interpretation. Where a location-pinned
entry below excludes a file's constants, it does so **because they are covered by a named CALIBRATION_LOG
entry**, not because of what the numbers are "about."

## Excluded — location-pinned, because covered by a named log entry

- **`engine/power_ratings.py` `EloConfig` fields** — covered by CALIBRATION_LOG **D9 / D11 / D12**
  (`k_early`, `k_late`, `k_decay_games`, `mov_c`, `mov_b`, `hfa_elo`, `elo_per_point`, `margin_sigma`,
  `uncertainty_floor`, `uncertainty_games_full`, `rp_prior_uncertainty_penalty`, `rating_signal_floor`,
  `prior_rp_max_elo`, `rp_reference`, `rp_span`).
- **`factors/physical_coefficients.py`** — every coefficient (incl. the **altitude 4000 ft / 1.2** above)
  covered by CALIBRATION_LOG **3b.1**.
- **`engine/prediction_engine.py:24-33`** — `NO_BET_CONFIDENCE_FLOOR` (0.50), `CONFIDENCE_TIER_A_MIN` (0.65),
  `CONFIDENCE_TIER_B_MIN` (0.50), and the dynamic `min_edge_threshold` ladder (0.75 / 1.0 / 1.5) — covered by
  CALIBRATION_LOG **3c.5 / 3c.6**.

## Excluded — location-pinned structural literals (not model-tuning magnitudes)

- **`engine/power_ratings.py`** `baseline = 1500.0` — the Elo mean anchor (zero-sum updates hold it here);
  standard Elo convention, not a tunable signal.
- **`engine/power_ratings.py:81`** `early_season_weeks = 3` — SPEC §6.2/§16.2 season structure (which weeks
  count as "early"), not a tunable magnitude.
- **`factors/base_calculator.py:44-60`** — `BaseFactorCalculator.__init__` defaults
  (`activation_threshold = 0.5`, `max_impact = 5.0`, `_min_output/_max_output = ±5.0`): every live factor
  overrides these in its own `__init__`, so they never reach output — inert placeholders.
- **`factors/base_calculator.py`** `get_explanation` text cutoffs (e.g. `abs(value) < 0.1`) — gate only the
  human-readable explanation string; no effect on any spread/edge/confidence value.

## Excluded — non-tunable literal KINDS (apply only to the structural literal itself)

- **Rounding digits** — the `N` in `round(x, N)` and the precision in an f-string (`f"{x:.2f}"`). The `N` is
  display/precision, never a model magnitude. (The value `x` being rounded is NOT excluded — audit it on its
  own line.)
- **Epsilons / float tolerances** — e.g. `1e-9` in push / equality comparisons.
- **Indices / loop & slice bounds / enum ordering** — e.g. `weights[:len(differentials)]`, list indices.

## Out of the reverse-check scope entirely

- **`data/` clients** (HTTP status codes, retry counts, timeouts, quota literals) — the reverse check scans
  only the frozen model paths (`factors/`, `engine/`); operational literals in the data layer are not model
  calibration and are out of scope.
- **`tests/`** — fixtures/tolerances are out of scope by design.

## NOT excluded — these ARE calibration and must be logged (see the reverse-audit ledger in CALIBRATION_LOG)

The shakedown found large **unlogged** calibration surface that does NOT belong here: the internal factor
formulas (DesperationIndex blend/scale, momentum/coaching/style-mismatch component weights + thresholds),
the `factor_registry._configure_factor_hierarchy` threshold/max_impact overrides, `variance_detector`
CV cutoffs (a hard NO_BET gate), `prediction_engine._calculate_confidence_score` + the `prediction_type`
ladder, and the standalone `confidence_calculator`/`edge_detector` engine. These are PROPOSED /
decision-pending in `docs/CALIBRATION_LOG.md` (Phase-3 reverse-audit) and on `docs/FREEZE_CHECKLIST.md`.
