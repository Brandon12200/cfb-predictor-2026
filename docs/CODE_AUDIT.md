# Code Audit (Phase 0 — SPEC §4.6)

Audit of undocumented modules and the pre-existing test baseline, with keep /
refactor / delete decisions. Deletions are recoverable via git history.

## Method

For each candidate module: is it imported by the live prediction path
(`main.py` → `engine.prediction_engine` / `edge_detector` /
`confidence_calculator` / `variance_detector` → `factors.factor_registry`,
`data.data_manager`), and is it covered by tests? Neither `engine/__init__.py`
nor `utils/__init__.py` re-exports anything, so all imports are explicit.

## Decisions

| Module | Wired to live path? | Tested? | Decision |
|---|---|---|---|
| `engine/adaptive_calibrator.py` | No | Only its own test | **Deleted** |
| `engine/dynamic_weighter.py` | No (only a stale check in `validate_performance_metrics.py`) | Only its own test | **Deleted** |
| `engine/market_efficiency_detector.py` | No | Only its own test | **Deleted** |
| `engine/game_filter.py` | No | Only its own test | **Deleted** |
| `utils/monitoring.py` | No | Only end-to-end `test_monitoring_system` | **Deleted** |
| `utils/health_check.py` | No | Only end-to-end `test_health_check_comprehensive` | **Deleted** |
| `engine/factor_validator.py` | No (dev script `scripts/validate_factors.py`) | No | **Keep** (retire in Phase 4) |
| `utils/performance_analyzer.py` | No (dev script `scripts/generate_report.py`) | No | **Keep** (retire in Phase 4) |
| `utils/bet_evaluator.py` | No (`performance_analyzer` + `scripts/check_results.py`) | No | **Keep** (retire in Phase 4) |

### Deleted (dead code — no live importers, only their own tests)
`engine/adaptive_calibrator.py`, `engine/dynamic_weighter.py`,
`engine/market_efficiency_detector.py`, `engine/game_filter.py`,
`utils/monitoring.py`, `utils/health_check.py`. Also removed:
- `tests/test_engine_components.py` (tested only the four deleted engine modules).
- The `test_health_check_comprehensive` and `test_monitoring_system` methods
  from `tests/test_end_to_end.py` (rest of the file tests live behavior).
- The stale `dynamic_weighter` check in `validate_performance_metrics.py`.

### Kept — off the live path but consumed by dev/CLI scripts
`factor_validator` (`scripts/validate_factors.py`), `performance_analyzer`
(`scripts/generate_report.py`), and `bet_evaluator`
(`scripts/check_results.py` + `performance_analyzer`) form a cluster with the
ad-hoc reporting/validation scripts. SPEC Phase 4 replaces those scripts with a
coherent `analytics/` module; deleting them now would remove working tooling for
no Phase 0 benefit. Retire this cluster with its scripts in Phase 4.

## Test baseline remediation (decision D4)

The committed `Initial commit: 2026 season rebuild` baked in code/test drift:
the suite had ~18 genuine failures on the fast files plus network-dependent
tests that hung (real API calls through a sleeping rate limiter), so it could
not run offline. Per D4 the full suite is now green and deterministic offline.

**Infrastructure**
- `tests/conftest.py`: autouse fixtures neutralize the rate-limiter `time.sleep`
  (kills hangs; `wait_if_needed` still returns the correct computed wait) and
  block real HTTP (un-mocked calls fail fast with a clear message instead of
  hitting the network). Exempts genuinely timing-sensitive files
  (`test_performance_tracker`, `test_cache_manager`) so their assertions on real
  elapsed time hold.

**Stale tests fixed / removed**
- `test_factors.py`: removed references to three factor classes that don't exist
  in this codebase (`VenuePerformanceCalculator`, `StatementOpportunityCalculator`,
  `ATSRecentFormCalculator`) and their test methods; these NameErrors in `setUp`
  were failing every test in three `TestCase` classes.
- `test_factors.py::test_safe_calculate`: asserted a stale literal
  `weighted_value == 0.1`; now asserts the plumbing relationship
  `weighted_value == value * dynamic_weight` (confidence-adjusted weighting).
- `test_config.py::test_validate_api_keys`: updated to the current dict shape
  (`status['odds_api']['configured']`, etc.).
- `test_api_clients.py`: `team_id_cache` assertion updated (the ESPN client
  pre-seeds the cache); removed `test_safe_api_call_decorator` (the
  `safe_api_call` decorator is abolished by SPEC §5.2 and no longer exists).
- `test_error_handler.py`: fixed a stale patch target
  (`normalizer.normalizer` → `utils.normalizer.normalizer`).

**Genuine product bugs fixed**
- `utils/rate_limiter.py`: zero per-minute/day limits raised `IndexError` on an
  empty deque and `can_make_call()` crashed; now a zero limit means "no calls"
  and `get_remaining_calls()` reports `0` (not `None`) for an explicit zero day
  limit.
- `factors/base_calculator.py`: `FactorConfidence` now subclasses `float` so it
  is JSON-serializable wherever prediction/shadow output is written.

**Skipped (documented, not failed) — 5 total**
- 2 pre-existing skips from the original suite.
- `test_api_clients::test_real_odds_api_call`: live API integration test
  (network + real key), excluded from the offline suite.
- `test_real_world_scenarios::test_early_season_limited_data` and
  `::test_system_resilience_to_api_failures`: both assert that missing/failed
  data lowers `data_quality`, but the current neutral-fill code reports `1.0`
  even when every fetch fails — exactly the bug the Phase 1 data layer removes
  (SPEC §5.1/§5.2, no neutral fabrication). Forcing them green in Phase 0 would
  require either reimplementing Phase 1 or asserting the buggy value; they are
  skipped with a Phase 1 reference and should be re-enabled there.

**Result:** `279 passed, 5 skipped, 0 failed` in ~5s, offline.

## Phase 1a — team registry migration (SPEC §5.5)

Replaced hardcoded, divergent membership with the CFBD-sourced season registry
(`data/team_registry.py`, D7). Deletions are recoverable via git history.

**Deleted**
- `data/conferences.py` — the interim Phase-0 single-source, folded into the registry.
- `data/schedule_client.py::_get_hardcoded_conference` (was `:410-452`) — the
  ESPN-fallback conference lookup now normalizes then queries the registry.

**Re-sourced (kept public API, replaced hardcoded bodies)**
- `utils/normalizer.py::_build_team_mappings` / `_build_fcs_teams` — now read
  `registry.get_fbs_canonical_names()` (138) / `get_fcs_names()` (127). The alias /
  ESPN / Odds **format** dicts are intentionally retained (name-format plumbing, not
  membership) and staged to a later Phase-1 slice.

**Added**
- `CFBDv2Client.get_teams(year)` (all-division `/teams`, one call → FBS + FCS split).
- Committed provenance-stamped artifacts `data/registry/{fbs_teams_2026.json,calendar_2026.json}`.
- Tests: `test_team_registry.py` (17), `test_registry_reconciliation.py` (9),
  fixture `tests/fixtures/legacy_normalizer_vocab.json` (frozen pre-migration vocab).
- `scripts/verify_phase_1.py` + `make verify-phase-1`.

**Result:** `312 passed, 5 skipped, 0 failed`, offline; lint + mypy clean on new code.

## Phase 1b — snapshot-first data layer + engine cutover (SPEC §5.2)

Replaced the live-fetch, neutral-fill data path with a snapshot-first one. Deletions
are recoverable via git history.

**Deleted (fabrication — the core of §5.1/§5.2)**
- `data/data_manager.py`: `safe_api_call` decorator + `_get_neutral_data_structure` /
  `_get_neutral_fallback` / `_initialize_fallback_data` / `safe_data_fetch` /
  `get_data_quality_report` (rewrote the module as a snapshot reader).
- `data/cfbd_client.py` (v1): `_get_default_coaching_data/_stats_data/_ratings_data` +
  the now-unused `get_coaching_data`/`get_team_stats`/`get_team_ratings`/`get_betting_lines`/
  `get_advanced_stats` + their processing helpers (715→146 lines; kept `get_games`/`test_connection`).
- `data/espn_client.py`: `_get_neutral_team_data/_coaching_data/_stats_data` + the unused
  `get_coaching_data`/`get_team_stats` (970→802; `get_team_info` now **raises** `ESPNError`).
- `factors/market_sentiment.py`: **all fabrication + hardcoded team names** (770→452 lines).
  Removed `_simulate_line_movement` (hash-based line-movement fabricator) and the entire
  public-betting-simulation subsystem — `_get_public_betting_percentage` (invented a "public
  betting %" from hardcoded `popular_teams`/`rivalry_pairs`/`service_academies` lists +
  `hashlib`/`random.uniform` noise) plus its now-dead consumers `_analyze_public_betting`,
  `_detect_reverse_line_movement`, `_detect_trap_patterns`, `_check_key_number_freeze`,
  `_is_reverse_line_movement`, and the `big_names` bias block in `_analyze_game_characteristics`.
  Public betting has no free data source, so it is now honestly UNAVAILABLE: `_detect_line_freeze`
  returns 0.0 (missing). The factor now runs only on real signals — spread size/week/spread-type
  characteristics, cross-book steam dispersion, and the (deferred) missing line-movement state.
  `verify_phase_1`'s fabrication grep now also fails on `random.uniform`/`random.seed`.
- A grep gate in `verify_phase_1` confirms `safe_api_call`/`_get_neutral_*`/`_get_default_*`/
  `neutral_fallback` exist nowhere in application code.

**Changed**
- 3 factors read `context['games'|'advanced_stats'|'betting_lines']` (dropped `self.cfbd_client`).
- `data_quality`: honest scalar (from field presence) + itemized `data_quality_report`.
- Engine embeds `snapshot_id` + a snapshot-frozen `timestamp`; a stable hashlib replaces the
  PYTHONHASHSEED-randomized `hash()` in `market_sentiment` → bit-identical reruns.

**Tests**
- New: `test_odds_client`, `test_normalize`, `test_snapshot`, `test_no_network` + shared
  `tests/context_factory.py`. Migrated ~20 scenario/e2e/backtest tests off the retired
  odds/ESPN mocking. Re-enabled the 2 D4 skips (now assert honest low quality on missing data).

**Result:** `345 passed, 4 skipped, 0 failed`, offline; `make verify-phase-1` ALL 1a+1b PASS.

## Phase 1c — schedule intelligence + closing lines + inspection tooling (SPEC §5.4.2/.3, §5.3)

**Deleted**
- `data/cfbd_client.py` — the v1 client shim (kept in 1b for `get_games`). Its last two
  consumers (`utils/results_fetcher.py`, `data/schedule_client.py`) and the `data_manager`
  diagnostic ping are repointed to `data/clients/cfbd_v2.py` (same `/games` endpoint/shape;
  v2 sends correct `seasonType`). Closes the 1b-review dead-API follow-up.

**Added**
- `data/schedule_intel.py` — pure `compute_schedule_intel` (haversine travel via stdlib
  `math`, time-zone crossings via stdlib `zoneinfo`, rest/bye/short-week/altitude/consecutive-
  road/sandwich-spot). Serves the builder and Phase-2 hypotheticals. Fixture unit tests.
- Snapshot field-groups `venues` (from the registry `location` rows) + `sp_ratings`
  (`cfbd_v2.get_sp_ratings`) + `schedule_intel`, all manifest-covered.
- `data/snapshot/lines.py` + `data/lines/YYYY_week_NN.json` — the append-only "as-of T"
  line-observation store (OUTSIDE the snapshot content hash — SCHEMA §3). `scripts/fetch_lines.py`
  appends; the snapshot keeps only the frozen prediction-time observation.
- `scripts/{inspect_snapshot,status}.py` — manifest inspection + per-source quota.
- Regenerated `data/season_calendar_2026.json` from CFBD (D8: no Week 0).

**Changed**
- `data/normalize/{models,odds}.py`: line-observation model (`LineObservation`/`GameLines`) +
  `closing_observation`. `data_manager`/`market_sentiment` read the frozen observation.
- Scenario tests re-wired: `context_factory.patched_context_from_mocks` now folds each test's
  `mock_espn` team data into the context, so the setups drive the engine (no longer vacuous).
- `.claude/hooks/{protect_immutable,guard_bash}.py`: append-only protection extended to `data/lines/`.

**Result:** offline suite green; `make verify-phase-1` **ALL PHASE 1 CHECKS PASSED**.

---

## Phase 2a — Power rating layer, pricer, hypothetical (SPEC §6; branch `phase-2a-power-ratings`)

**Added**
- `engine/power_ratings.py` — in-house transparent Elo (D9): decaying K, MOV dampener,
  zero-sum updates over completed games only (never seeded from 2025); hybrid preseason prior
  (D10: SP+ preferred → returning-production fallback → flat); `rating_uncertainty` + early-season
  cap (D11); `spread_to_win_prob` (D12). All constants in the frozen `EloConfig` (PROPOSED,
  `CALIBRATION_LOG.md`). Pure + deterministic.
- `engine/matchup_pricer.py` — `price()` (rating diff + HFA + `compute_schedule_intel`
  adjustments), identical for real + hypothetical; `compute_ratings_for_snapshot` (memoized by
  `snapshot_id`; the prediction path reads ONLY the snapshot); `build_ratings_export`;
  `ScheduleAdjustmentConfig` (conservative Phase-2 baseline; Phase 3 recalibrates).
- Snapshot `returning_production` field-group (`data/normalize/cfbd.normalize_returning_production`,
  builder + manifest, 100% covered). Week-1 fixture rebuilt (hash changed). **Both SP+ and RP are
  empty at this date → flat prior for all, `rating_uncertainty=1.0`, honest (never fabricated).**
- `main.py hypothetical` CLI (`cli/app.run_hypothetical`, routed before the flat parser;
  full subcommands are Phase 4.5) — table/json/neutral-site/show-factors, no Vegas line.
- `scripts/update_ratings.py` → committed `data/ratings/2026_week_NN.json` (derived; not on the
  prediction path). `data/snapshot/store.{available_weeks,latest_snapshot_week}`.
- `scripts/verify_phase_2.py` + `make verify-phase-2`.

**Changed**
- `data/data_manager.get_game_context`: surfaces `sp_ratings`/`returning_production`/`venues` +
  the game's `neutral_site`/`game_date` for the pricer.
- `engine/prediction_engine`: `_compute_power_rating` + `_build_prediction_result` add
  `power_rating_spread`, `model_vs_market_gap`, `rating_uncertainty`, breakdown, caveats —
  **diagnostic only** (§6.6), additive, does not touch the contrarian edge (bit-identical rerun
  still holds).
- `.claude/hooks/protect_immutable.py`: append-only protection extended to `data/ratings/`.
- `.gitignore`: `data/ratings/` documented as intentionally NOT ignored.

**Result:** offline suite **410 passed / 4 skipped**; lint + mypy clean; `make verify-phase-2`
**ALL PHASE 2 CHECKS PASSED** (2 pending — 2b projections). Model-vs-market on the real week-1
slate correctly reads high gaps at `rating_uncertainty=1.0` (no team-quality data preseason).

---

## Phase 2b — Season projections + belief-drift (SPEC §6.5; branch `phase-2b-projections`)

**Added**
- `analytics/` package (**freeze-exempt**, NOT `engine/`; D14) — `analytics/projections.py::
  build_projections(snapshot, cfg)`: prices every remaining game with the 2a pricer, sums win
  probs (`spread_to_win_prob`, D12 σ=16) into per-**FBS**-team projected win totals
  (registry-scoped, no hardcoded names). Pure, deterministic, byte-reproducible (`generated_at`
  frozen from snapshot `built_at`); `meta.schema_version` + `experimental: true`.
- `scripts/build_projections.py` (+ importable `write_projections`) → committed
  `data/projections/2026_week_NN.json`.
- `cli/app.py::run_project` (routed before the flat parser, like `run_hypothetical`) — `main.py
  project [--team X] [--history] [--format json]`: projected-win-total table + Δwk/Δpreseason
  drift + risers/fallers, per-team per-game breakdown, week-by-week history. Drift/history reader
  is **schema-evolution-tolerant** (keys off `meta.schema_version`, defensive `.get`).
- Tests: `tests/test_projections.py` (win-total arithmetic, FBS scoping, determinism, repro),
  `tests/test_project_cli.py` (render/team/history/json + mixed-schema drift).

**Changed**
- `.claude/hooks/protect_immutable.py`: append-only protection extended to `data/projections/`.
- `scripts/verify_phase_2.py`: the two 2b checks flipped from PENDING to real assertions
  (projection file per built week + reproduces; `cfb project` renders totals + drift).
- `Makefile`: new `analytics/`/scripts/tests added to `LINT_PATHS`/`TYPED_PATHS`.

**Coverage (pre-commit review follow-up):** `build_projections` includes **every** FBS team; a
team with no games in the snapshot is surfaced with `schedule_missing: true` + null totals + a
`meta.coverage.unscheduled` entry (never silently dropped). Current snapshot: **134/138**
scheduled — `APPALACHIAN STATE`/`CAL`/`LOUISIANA MONROE`/`UMASS` have no resolved FBS-vs-FBS
game (a **pre-existing Phase-1 normalizer gap** in the CFBD `/games` feed, tracked in
`PHASE2_NOTES.md`). The `--team` view is defensive (`.get`) so it tolerates schema evolution.

**Result:** offline suite **433 passed / 4 skipped**; lint + mypy clean (20 typed source files);
`make verify-phase-2` **ALL PHASE 2 CHECKS PASSED — Phase 2 complete** (0 pending). Preseason
projections are near-uniform (~6 wins; variation from schedule length only) — the honest state;
the drift view differentiates from ~weeks 4–6. Market win total (§6.5) deferred — no futures source.

---

## Phase 3a — Foundations: decomposed pricer + calibration evidence (SPEC §7; branch `phase-3a-foundations`)

**Added**
- `analytics/calibration_evidence.py` (freeze-exempt) + `scripts/build_calibration_evidence.py` →
  committed `data/calibration/2025_evidence.json`: joins the 300-game archive and reports
  confidence/edge/type → realized **ATS%** with **Wilson 95% intervals**. **Read-only, no fit**
  (SPEC §3/§12). ATS convention reuses the canonical `scripts/calculate_accuracy.py`
  (`home covers S iff margin+S>0`); verified sane (overall contrarian ATS **46.6%**, not the
  flipped-convention 15%).
- `scripts/verify_phase_3.py` + `make verify-phase-3` (3a PASS; 3b/3c/3d PENDING).

**Changed (D15 decomposition, while 2a unfrozen)**
- `engine/matchup_pricer.py::PricedMatchup` gains `base_margin`/`base_spread` (team quality) with
  `total = base + schedule_adjustment` (test-pinned). `engine/prediction_engine.py` diagnostic now
  exposes `model_vs_market_gap` = **base** gap (the only gap a confirming rule may use) +
  `model_vs_market_gap_total` (labeled) — the D15 circularity prohibition, test-guarded.
- Coefficient relocation to the factor-owned single source is sequenced into **3b** (the physical
  factor is the second consumer — the meaningful move point; no throwaway 3a rename).

**Deviation (D16, deliberate):** the §7 "full-slate dry run over an archived **2025** week"
acceptance is satisfied by running the new engine over the committed **2026** week-1 snapshot (a
real slate); the 2025 archive carries the calibration weight. No 2025 snapshot is built (Odds
historical is paid; year-parameterizing the builder isn't worth it). Recorded as D16.

**Finding for 3c (carry forward):** the archive's **confidence is almost entirely 60–70 with tiny
edges (<2)** — near-zero variance. So it strongly supports **L4** (flat sub-50% ATS on marginal
bets) but gives **thin evidence for confidence-tier boundaries** (L3) and no edge-size gradient for
a floor. 3c tier/floor calibration must lean on reasoning + the NEW system's distribution, and each
entry's confidence language must match the (wide) interval width.

**Result:** offline suite **441 passed / 4 skipped**; lint + mypy clean (22 typed source files);
`make verify-phase-3` **ALL PHASE 3 CHECKS PASSED (7 pending — 3b/3c/3d)**; `-1`/`-2` stay green.

## Phase 3b — physical factor layer + reweight (L1), 2026-07-03

**New**
- `factors/physical_coefficients.py` — the D15 single coefficient source (frozen `PhysicalCoefficients`
  + per-sub-signal point fns + `physical_adjustments()`). `engine/matchup_pricer.py` now consumes it
  (behavior-preserving relocation of the 2a `ScheduleAdjustmentConfig`/`schedule_adjustment`).
- `data/data_manager.py::get_game_context` surfaces `home_intel`/`away_intel` (one
  `compute_schedule_intel` call each) for the factor path.
- `factors/scheduling_fatigue.py` rewritten: 6 PRIMARY physical factors (`category="physical"`),
  each separate in `factor_breakdown`. `tests/test_physical_coefficients.py` + `test_physical_factors.py`.

**Changed (calibration batch — CALIBRATION_LOG Phase 3b; owner-ratified)**
- Reweight to physical (52% additive share); `MarketSentiment` 35%→6%; `travel_cap` 2.0→1.5.
- `StyleMismatch`/`MarketSentiment` re-categorized `matchup`/`market` (grouping only, so the
  contribution-budget ratio measures physical vs the motivational factors).
- `factors/base_calculator.py::safe_calculate`: raw-`0.0` value → **not activated** (was activated).
  Behavior-changing (lowers `primary_signals`, raises `avg_confidence` when factors return 0);
  logged as its own CALIBRATION_LOG entry.

**Retired**
- `SchedulingFatigueCalculator` (pre-1c crude fatigue heuristic) — replaced by the 6 physical factors.
- `LookaheadSandwichCalculator` (situational) — superseded by the physical `Sandwich` factor;
  audited free of hardcoded rivalry lists. Three tests re-pointed to the physical `Sandwich`.

**Result:** offline suite **453 passed / 4 skipped**; `make lint` clean (24 typed source files);
`make verify-phase-3` **ALL PHASE 3 CHECKS PASSED (5 pending — 3c/3d)**; `-1`/`-2` stay green.
