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
