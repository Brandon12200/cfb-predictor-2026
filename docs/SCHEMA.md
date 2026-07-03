# Canonical Data Schema (Phase 1, SPEC §5.2)

**Status: WORK IN PROGRESS (Phase 1a).** This document seeds the canonical typed
schema from a full audit of what the engine and factors actually consume. The
dataclasses in `data/normalize/` are being built to match it. Nothing here may
be *neutral-filled*: a field is either present with a value + provenance, or
recorded as `missing` in the provenance manifest (SPEC §5.2, binding principle 4).

---

## 1. Context the engine feeds factors (the raw material a snapshot must produce)

Today assembled by `data/data_manager.py::get_game_context` (`:97-173`) and passed
to `factor_registry.calculate_all_factors` (`engine/prediction_engine.py:83,97`).
Phase 1 reproduces this from the snapshot instead of live fetches.

### Top-level context keys
| Key | Type | Consumed by | Notes |
|---|---|---|---|
| `home_team`, `away_team` | str (normalized UPPERCASE) | all | canonical registry form |
| `week` | int | nearly every factor + engine | from `resolve_week` |
| `year` | int | scheduling_fatigue, style_mismatch, market_sentiment | 2026 |
| `timestamp` | ISO str | — | **VOLATILE** (see §3) |
| `data_sources` | list[str] | confidence_calculator (`:131`) | replaced by provenance manifest |
| `vegas_spread` | float \| None | **engine gate** (`:89`), pressure, close-game, market_sentiment | **load-bearing**: if None, engine hard-fails the prediction and team/coaching context is empty |
| `has_betting_data` | bool | `_assess_data_quality` (`:502`) | |
| `home_team_data`, `away_team_data` | dict | many factors | see below |
| `coaching_comparison` | dict | coaching factors | see below |
| `data_quality` | float 0–1 | engine confidence, edge_detector | becomes an **itemized** report in v2, not a single % |

### `home_team_data` / `away_team_data` sub-fields (`get_team_data`, `:196-247`)
- `team_name` (str) — *factors inject this if absent* (`coaching_edge.py:214-217`, `situational_context.py:52-53`, `momentum_factors.py:56-57,270-271`); snapshot should pre-populate it.
- `info` → `status`; `conference.name` (read by `confidence_calculator.py:304-305`)
- `coaching` (dict), `stats` → `status`
- `schedule` (list[game]) — game shape: `completed` (bool), `date` (str), `result` ('W'/'L'), `team_score` (int), `opponent_score` (int), `is_home_game` (bool). Read by momentum + desperation (`momentum_factors.py:78,151,289,375`).
- `derived_metrics` (`_calculate_derived_metrics`, `:453-481`):
  - `current_record` → `{wins, losses, win_percentage}` (pressure `coaching_edge.py:246-260`, desperation `situational_context.py:73-82`)
  - `venue_performance` → `{home_record, away_record}`, each `{wins, losses, total_games, win_percentage}`
- `is_home` (bool) — read by `momentum_factors.py:363` (defaults False; never set today)

### `coaching_comparison` sub-fields (`get_coaching_comparison`, `:316-325`)
- `home_coaching` / `away_coaching` → `head_coach_experience` (int, default 5), `tenure_years` (int, default 3), `status`
- `experience_differential` (float)
- `head_to_head_record` → `{home_wins, away_wins, total_games, note}` — **currently a placeholder that always returns zeros** (`data_manager.py:444-451`); real H2H is a Phase-1 gap to fill (multi-season lookback is the §16.7 coach-history exception).

### Out-of-band datasets (3 factors fetch these live today — the determinism gap)
These bypass the context dict and hit CFBD directly at prediction time; the snapshot must pre-fetch them:
- **season games** — `scheduling_fatigue.py:94` `get_games(year, team)`; per-game reads `week, awayTeam, homeTeam, homePoints, awayPoints, startDate`.
- **advanced season stats** — `style_mismatch.py:108` `get_advanced_stats(year, team)`; reads offense/defense `successRate, explosiveness, ppa, plays, havoc.total, standardDowns/passingDowns/rushingPlays/passingPlays successRate, powerSuccess, stuffRate`.
- **betting lines** — `market_sentiment.py:167` `get_betting_lines(year, week)`; reads per-book `spread, spreadOpen, provider`.

### Schedule-intelligence fields (new in 1c, from CFBD `/venues` + `/games`)
Per team-week: `rest_days`, `bye`/`opponent_bye`, `short_week`, `travel_distance` (great-circle from venue lat/long), `time_zones_crossed` (+direction), `altitude`, `consecutive_road_games`, `sandwich_spot`. Must be computable for hypothetical matchups. Venue source fields: `latitude`, `longitude`, `elevation`, `timezone`, `dome`.

---

## 2. Provenance manifest (SPEC §5.2)

Per field-group per team/game, the snapshot records: `source` (which client answered — CFBD / ESPN / Odds / …), `fetched_at` (ISO), `cache` (hit/miss), `fallback_reason` (if the fallback chain was used), or `missing` (nothing available). This replaces the coarse `data_sources` string list. `data_quality` becomes an itemized report derived from these facts, not a single percentage.

---

## 3. Prediction result schema + reproducibility contract

### Engine in-memory result (`prediction_engine.py::_build_prediction_result`, `:215-256`)
`home_team, away_team, week, timestamp, vegas_spread, contrarian_spread, edge_size, edge_direction, has_edge, prediction_type, total_adjustment, factor_breakdown (rich per-factor safe_calculate dicts), category_adjustments, data_quality, data_sources, factors_calculated, factors_successful, variance_analysis, recommendation, confidence_score (0.15–0.95), context{...}`.

Each `factor_breakdown` entry (`base_calculator.py:238-255`): `factor_name, factor_type, home_team, away_team, value, raw_value, confidence, success, error, weight, dynamic_weight, weighted_value, explanation, reasoning[], is_multiplicative, activated`.

### Stored record (v1 — schema v2 in Phase 3 must stay converter-compatible)
Envelope (`prediction_storage.py:54-67`): `{week, season, generated_date, prediction_count, predictions[], system_stats{...}}`. Per record: `game_id` (`{AWAY}_{HOME}_week{N}`), `home_team, away_team, week, timestamp, vegas_spread, contrarian_spread, predicted_edge, edge_direction, prediction_type, confidence (0–100 scale), factor_breakdown ({category: float}), data_quality (0–100 scale), recommendation, variance_analysis`.
⚠ Incompatibilities to preserve/convert: stored `factor_breakdown` is flat `{category: float}` vs the engine's rich per-factor dict; `confidence`/`data_quality` stored 0–100 but computed 0–1.

### Reproducibility contract (define once; CLI + test share it)
`cfb predict rerun` runs in **frozen-clock** mode: it reuses the snapshot's recorded `fetched_at` timestamps and sets prediction wall-clock fields from the snapshot, **not** `datetime.now()`. Two reruns on the same snapshot must be **byte-for-byte identical over the payload minus `VOLATILE_FIELDS`**.

```
VOLATILE_FIELDS = { "generated_at", "timestamp", "generated_date" }   # wall-clock only
```
Everything outside this set (spreads, edges, factor values, provenance) must match exactly. Predictions embed the `snapshot_id` they were computed from.

---

## 4. `market_sentiment` in core Phase 1 (documented deliberate state)

Line-movement history is deferred to slice 1.5 (D6). In core Phase 1 the factor
consumes only the **prediction-time spread** (Odds API) plus, where present,
**CFBD's opening line**. **Line-movement is recorded as `missing` in the
manifest.** On missing movement the factor **reduces its contribution and applies
a confidence penalty** — it never fabricates a movement of 0. This is intended
behavior, not a defect.

---

## 5. Team registry surface (SPEC §5.5) — **built in 1a**, replaces `data/conferences.py`

`data/team_registry.py` is the single sourced home for season membership. It loads
two committed, provenance-stamped artifacts and answers all membership/name queries
offline; a live CFBD fetch happens only in `refresh_registry` (see D7).

**Artifacts** (`data/registry/`, each with a `_provenance` header — `source`, `endpoint`,
`year`, `fetched_at`, counts):
- `fbs_teams_2026.json` — `fbs`: 138 full CFBD `/teams` rows (incl. `location` venue
  object for 1c: lat/long/elevation/timezone/dome); `fcs`: 127 trimmed rows.
- `calendar_2026.json` — 16 CFBD `/calendar` week rows (for the D1 corroboration).

**Surface (drop-in for the retired `conferences.py`):** `get_conference_map()` (P4 +
`INDEPENDENT` bucket → sorted canonical names), `get_all_tracked_teams()`,
`get_team_conference(team)` (tracked-slate key or `None`), `get_p4_conference_names()`.
**Normalizer data source:** `get_fbs_canonical_names()` (138), `get_fcs_names()` (127),
`get_aliases(canonical)`, `iter_fbs()`.

**Name reconciliation:** canonical form is the normalizer's existing UPPERCASE vocabulary.
`canonical_name(school)` = `CANONICAL_OVERRIDES.get(school, school.upper())`; the 8
overrides and the enumerated `NEW_FBS_MEMBERS_2026` (4 recent FCS→FBS transitions) are
the human review checkpoint, gated by `tests/test_registry_reconciliation.py` (structural:
exact / override / new-member, **no implicit fuzzy**). `conference_key()` maps CFBD's
title-case conference names ("Big Ten") to the canonical UPPERCASE key ("BIG TEN").

**Validation (built + unit-tested in 1a; wired into the snapshot build in 1b):**
`validate_membership_counts()` hard-fails on 2026 count drift (SEC 16, Big Ten 18,
Big 12 16, ACC 17, ≥1 tracked independent); `corroborate_calendar()` emits loud
warnings (not a hard fail) where the hand-built `season_calendar_2026.json` week
boundaries diverge from CFBD `/calendar` — currently a systematic ~1-day offset + no
week 0 in CFBD, surfaced rather than silently trusted (D1).

**Retirement status:** membership + FCS lists retired in 1a. The normalizer's alias /
ESPN / Odds **format** dicts (`_build_alias/_espn/_odds_mappings`) stay for now (they need
ESPN/Odds client sampling) and are staged to a later Phase-1 slice — CFBD `alternateNames`
is captured in the artifact (`get_aliases`) ready to feed that step.

---

## Design notes
- Factors defensively default almost every field (e.g. `head_coach_experience` 5, `week` 1/8, `year` 2024) — the snapshot must record **presence/provenance**, not just values, so a real value is distinguishable from a default.
- The betting line is load-bearing: no spread ⇒ empty context ⇒ engine skips the prediction.
- Stdlib **dataclasses** (not pydantic) per the minimal-deps policy.
