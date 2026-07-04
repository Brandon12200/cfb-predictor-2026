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
- **season games** — read from the snapshot's `games` (context), never live. Phase 3b's **physical factor layer** (`factors/scheduling_fatigue.py`: `ByeAdvantage`, `ShortWeek`, `TravelBurden`, `Altitude`, `ConsecutiveRoad`, `Sandwich`) reads the per-team **`home_intel`/`away_intel`** tables that `data_manager.get_game_context` precomputes once via `data.schedule_intel.compute_schedule_intel` — not a direct `get_games` call. (Retired: the pre-1c `SchedulingFatigueCalculator` and situational `LookaheadSandwich`.)
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

**Hash-exclusion rule (1c, non-negotiable).** `snapshot_id` is a content hash over the
snapshot's `data` only. The growing "as-of T" line-observation series (SPEC §5.4.3) is
therefore **never** written back into `snapshot.json` — that would change the hash and
break reproducibility. The snapshot's `betting_lines[game]` holds only the **frozen
prediction-time observation** (`{home, away, kickoff, observation, vegas_spread}`, in the
hash); the full series lives in the append-only `data/lines/YYYY_week_NN.json` store,
**excluded from `snapshot_id`**. `predict rerun` reads the snapshot's frozen observation,
so appending a closing line leaves `snapshot_id` and every rerun byte-identical (asserted
by `test_append_does_not_change_snapshot_id_or_bytes`).

**As built (1b):** the engine's result `timestamp` is set from the snapshot's `built_at`
(`prediction_engine._build_prediction_result`), and `market_sentiment`'s deterministic
team-hash uses stable `hashlib.md5` (not PYTHONHASHSEED-randomized `hash()`). Because the
snapshot-first flow has no wall-clock "live" prediction to diverge from, two snapshot-based
predictions are in practice identical over the **full** payload — `test_two_reruns_are_bit_identical`
asserts byte-equality including `timestamp`. `VOLATILE_FIELDS` remains the documented contract
for any future comparison against a wall-clock-stamped record (e.g. the storage envelope's
`generated_date`, which is still set at write time).

---

## 4. `market_sentiment` in core Phase 1 (documented deliberate state)

Line-movement history is deferred to slice 1.5 (D6). In core Phase 1 the factor
consumes only the **prediction-time spread** (Odds API) plus, where present,
**CFBD's opening line**. **Line-movement is recorded as `missing` in the
manifest.** On missing movement the factor **reduces its contribution and applies
a confidence penalty** — it never fabricates a movement of 0. This is intended
behavior, not a defect.

**Public-betting share is also unavailable** (no free data source) and is therefore
UNAVAILABLE, not simulated: the trap/line-freeze/reverse-line-movement signals that
depend on it return no-signal (0.0). The prior implementation fabricated a public
betting % from hardcoded team-popularity/rivalry lists + `random`/`hashlib` noise — all
removed in 1b (SPEC §5.2, binding principles #2/#4). The factor now runs only on real
signals: spread size/week/spread-type characteristics, cross-book steam dispersion, and
the deferred missing line-movement state.

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

## 6. Phase 2 — Power rating layer (SPEC §6)

### 6.1 Power-rating record (`data/ratings/2026_week_NN.json`, D13)
A **derived** artifact (written by `scripts/update_ratings.py`) for inspection + the 2b
projections. **Not read on the prediction path** — the engine recomputes ratings from the
snapshot via `engine.matchup_pricer.compute_ratings_for_snapshot` (memoized by
`snapshot_id`), so the reproducibility contract (§3) is untouched. Byte-reproducible:
`generated_at` is frozen from the snapshot's `built_at`.

```
{ "meta": { "snapshot_id", "week", "year", "generated_at" (= snapshot built_at),
            "engine": "power_ratings", "elo_config": {…EloConfig…} },
  "ratings": { "<TEAM>": { "rating": float, "rating_uncertainty": 0–1,
                           "games_played": int, "prior_source": "sp+"|"returning_production"|"flat",
                           "prior_elo": float }, … } }
```

### 6.2 In-house Elo (D9) + hybrid preseason prior (D10)
`engine/power_ratings.py` — classic Elo, current-season completed games only (never seeded
from 2025), MOV-dampened, **decaying K** (high early → low late), zero-sum updates (mean
stays at baseline 1500). Constants live in the frozen `EloConfig` (owner-ratified via the
dispersion acceptance test; see `CALIBRATION_LOG.md`). Preseason prior is hybrid: **SP+
`rating` preferred** (a point value → Elo offset `rating*elo_per_point`), else a bounded
**returning-production** continuity nudge (±`prior_rp_max_elo`), else honest **flat** baseline.
Missing SP+/RP is recorded, never fabricated (binding principle 4).

### 6.3 `rating_uncertainty` + early-season cap (D11)
Per-matchup scalar in `[floor, 1]`, driven by games played (decays 1.0 → `uncertainty_floor`
by `uncertainty_games_full`), inflated for the RP-fallback prior. The pricer scales the
**rating differential** (not home-field/schedule) by `rating_signal_weight = floor +
(1−floor)·(1−uncertainty)` so weeks 1–3 lean on physical/scheduling signals; the engine
widens bands / NO_BETs on high uncertainty.

### 6.4 Matchup-pricer output — **decomposed** spread (`engine/matchup_pricer.py`, §6.3, **D15**)
`price()` returns a decomposed spread so each consumer takes the honest lane:
- **`base`** = rating differential (early-season-capped) + home-field — **team quality only**
  (`base_margin`, positive = home favored; `base_spread = −base_margin`).
- **`schedule_adjustment`** (`schedule_component`) = the physical component (bye, short-week,
  travel/timezone, altitude) from `compute_schedule_intel`.
- **`total`** = `base + schedule_adjustment` (`home_margin`; `model_spread = −home_margin`).
  Test-pinned: `base_margin + schedule_component == home_margin`.
**Sign convention:** spreads are home-perspective, **negative = home favored** (matches
`vegas_spread`). **Consumers:** hypothetical mode → **`total`** (travel must show); the
model-vs-market diagnostic + any confirming-signal rule → the **`base`** lane (§6.5). Schedule
coefficients live in a **single calibrated source** (`factors/physical_coefficients.py`, D15)
consumed by the pricer's model-spread subset here AND the six Phase-3b contrarian physical
factors — no parallel copy. The pricer's `physical_adjustments()` is the **fatigue/location**
subset (bye, short-week, travel/tz, altitude); `consecutive_road` and `sandwich` are
**contrarian-only** physical factors and do NOT feed the model spread (D18).

### 6.5 Model-vs-market diagnostic (real-game output, §6.6, **D15**)
`_build_prediction_result` adds, **diagnostic-only** (does NOT drive the 2026 edge/rec):
`power_rating_spread` (= total), `power_rating_base_spread` (team quality),
`model_vs_market_gap` (= **`base_spread − vegas_spread`** — the BASE gap; the ONLY gap a
confirming-signal rule may use), `model_vs_market_gap_total` (= `total − vegas`, **labeled**,
diagnostic-only — never confirms a schedule factor), `rating_uncertainty`,
`power_rating_breakdown`, `power_rating_caveats`. **Circularity rule (D15):** a schedule/physical
factor must not be confirmed by a gap that contains the same schedule signal — the base gap
excludes schedule and satisfies this by construction.

### 6.6 spread → win-probability conversion (D12, required here by §6.5)
`spread_to_win_prob(margin_points)` uses the **normal CDF**:
`P(win) = Φ(margin_points / margin_sigma)`, with **`margin_sigma` = 16.0 points**. σ is
grounded in CFB, not the NFL 13.5: the 2025 P4 archive **market-residual SD is 14.1**
(`actual_margin + vegas_spread`, mean ≈ 0), lifted for our noisier-than-market model + the
wider full-slate margins. Using 2025 margins for σ is **Data-Recency-compliant** — a
sport-level statistical constant, not team-quality data. Used by the 2b projections to sum
per-game win probabilities into projected win totals.

### 6.7 Season projection record (`data/projections/2026_week_NN.json`, Phase 2b, D14)
A **derived, experimental** artifact (`analytics/projections.py::build_projections`, written by
`scripts/build_projections.py`). Pure computation over the snapshot + the 2a pricer — zero API
cost, deterministic, byte-reproducible (`generated_at` frozen from the snapshot's `built_at`).
**Never drives bet recommendations** (SPEC §6.5). Committed + immutable-history-hook-protected
(like `data/ratings/`). Read by `main.py project`.

```
{ "meta": { "schema_version" (int; drift/history reader keys off it to tolerate schema
                               evolution across weeks), "snapshot_id", "week", "year",
            "generated_at" (= snapshot built_at), "engine": "power_ratings",
            "margin_sigma", "experimental": true, "counts": <convention string>,
            "coverage": { "fbs_total", "scheduled", "unscheduled": [<TEAM>…] } },
  "teams": { "<FBS TEAM>": { "rating", "rating_uncertainty",
              "wins_so_far", "losses_so_far", "remaining",
              "projected_wins", "projected_losses", "schedule_missing" (bool),
              "games": [ { "week", "opponent", "is_home", "neutral_site",
                           "model_spread" (team-perspective; null for completed),
                           "win_prob", "completed", "won" }, … ] }, … } }
```
- **Coverage is explicit — no team silently dropped.** *Every* FBS team appears; a team with no
  games in the snapshot gets `schedule_missing: true`, `projected_wins: null`, empty `games`,
  and is listed in `meta.coverage.unscheduled`. `main.py project` shows it as "—" with a
  coverage note. (Current snapshot: 134/138 scheduled — 4 teams have no resolved FBS-vs-FBS
  game; a pre-existing Phase-1 data/normalizer gap surfaced, not caused, here.)

- **Scope:** only **FBS** teams are projected (registry-scoped, no hardcoded names). Opponents
  absent from ratings (incl. FCS) are priced from the flat baseline prior via the pricer
  fallback — they get a `win_prob` for the FBS team's row but are not themselves projected.
- **Counting convention (stated so an external comparison isn't misread as a model
  discrepancy):** `projected_wins` = `wins_so_far` + Σ(remaining-game `win_prob`) over **all
  scheduled games incl. FCS opponents, regular season only** (matches the snapshot `games`).
  External totals (media/market) are sometimes FBS-only or include postseason — a mismatch
  there is a convention difference, not a model error.
- **Preseason state (not a defect):** with SP+/RP empty, all priors are flat → projections are
  near-uniform (~6 wins; variation comes from schedule length/home games, not team quality).
  The drift/risers-fallers view earns its keep from ~weeks 4–6 as ratings differentiate.
- **Market win total (§6.5) deferred:** no futures data source in 2026 core → recorded
  not-available (honest-missing), never fabricated.
