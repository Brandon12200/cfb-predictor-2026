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
- **Caveat-string thresholds** — a literal that gates only a human-readable warning appended to a
  `caveats` list, with no path to any spread/edge/confidence value. Named instance:
  `engine/matchup_pricer.py:205`'s `uncertainty > 0.5`, which appends a "high rating uncertainty"
  string; the rating-signal weight itself comes from the ratified **D11** formula at `:167`,
  independent of this literal. *(Added 2026-08-05 as pre-flight finding S-2. **This needs no third
  pre-flight run:** the auditor verified the literal non-tunable in the very run that recommended
  listing it, so recording that conclusion is a scope no-op against its own finding — it removes an
  item from the reverse check rather than changing what the check would conclude.)*
- **Indices / loop & slice bounds / enum ordering** — e.g. `weights[:len(differentials)]`, list indices.

## Out of the reverse-check scope entirely

- **`data/` clients** (HTTP status codes, retry counts, timeouts, quota literals) — the reverse check scans
  only the frozen model paths (`factors/`, `engine/`); operational literals in the data layer are not model
  calibration and are out of scope.
- **`tests/`** — fixtures/tolerances are out of scope by design.

## NOT excluded — these ARE calibration and must be logged (see the reverse-audit ledger in CALIBRATION_LOG)

**The purpose of this section is unchanged and still binding: the surfaces named below are
calibration, and none of them may ever be moved into the exclusion list.** What has changed is their
status — all are now dispositioned (refreshed 2026-08-03, pre-flight N-2):

- **Internal factor formulas** — `DesperationIndex` blend/scale **B3**; coaching **B6**; momentum
  **B7** *and* its branch arithmetic **B-2** (pre-flight); `StyleMismatch` outer weighting **B8**,
  with its ~20 branch constants **still unratified** and the factor therefore **dormant for 2026**
  (**B-1**, pre-flight) — that dormancy is *why* they are unlogged, and it is itself the disposition.
- **`factor_registry._configure_factor_hierarchy` overrides** — **B2**, completed by **S-5**.
- **`variance_detector` CV cutoffs** (a hard NO_BET gate) — **B4**, ratified 2026-08-03; the file's
  residual diagnostic literals are logged DEAD in **S-3**, and `:225`'s bare `0.3` is a logged
  known state.
- **`prediction_engine._calculate_confidence_score`** — **B1**; the **`prediction_type` ladder** —
  **A4**.
- **The standalone `confidence_calculator`/`edge_detector` engine** — **RETIRED**, not logged: the
  whole cluster was deleted under **A2**, so there is no longer a second scoring surface in
  `engine/`.

**Nothing in this section is PROPOSED or decision-pending any longer** — the A1–A6 / B1–B10 ledger
closed 2026-07-25, B4 landed 2026-08-03, and the pre-flight dispositions closed the remainder.
