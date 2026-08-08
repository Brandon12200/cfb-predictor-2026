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
- **advanced season stats** — `style_mismatch.py` reads offense/defense `successRate, explosiveness, ppa, havoc.total, standardDowns/passingDowns/rushingPlays/passingPlays successRate, powerSuccess, stuffRate`. (`plays` is present in the payload but **no longer consumed** — the pace component was neutralized to dormant in Phase 3d, Bug #16.)
- **betting lines** — `market_sentiment.py:167` `get_betting_lines(year, week)`; reads per-book `spread, spreadOpen, provider`.

### Schedule-intelligence fields (new in 1c, from CFBD `/venues` + `/games`)
Per team-week: `rest_days`, `bye`/`opponent_bye`, `short_week`, `travel_distance` (great-circle from venue lat/long), `time_zones_crossed` (+direction), `altitude`, `consecutive_road_games`, `sandwich_spot`. Must be computable for hypothetical matchups. Venue source fields: `latitude`, `longitude`, `elevation`, `timezone`, `dome`.

> **⚠ Elevation units (A6, 2026-07-16).** `venues[*].elevation` is stored **at rest in METRES** — CFBD's native unit, kept unconverted so the snapshot mirrors its source. `schedule_intel[*].altitude` is emitted in **FEET**. `data.schedule_intel.elevation_feet()` is the single conversion point, and the ratified 3b.1 constant it feeds (`altitude_threshold_ft = 4000.0`) is in feet. **Any new consumer of `elevation` must convert.** Before A6 the two met unconverted, so the altitude comparison was false for every venue in every week and the factor could never fire — the maximum elevation in the dataset is ~1634 m against a 4000 ft threshold. Honest-missing is `None`, never `0.0` (which would read as sea level).
>
> **Pre-A6 snapshots:** a snapshot's stored `schedule_intel` blob is frozen at build time, so bundles built before this fix hold the raw **metres**-scale `altitude`. That staleness is harmless to predictions — `data_manager.get_game_context` **recomputes** intel on every call and never reads the stored blob — but `scripts/inspect_snapshot.py` displays the stored value and labels it `alt(as-stored)` unless the bundle records `meta.schedule_intel_altitude_unit == "ft"`.

> **⚠ Venue timezone contract (owner-ratified, 2026-08-03).** `venues[*].timezone` is an **IANA zone name** sourced from CFBD. CFBD serves it as **`null` for 8 of 138 FBS venues** — the key is present, only the value is absent — two of them in the tracked slate (**Northwestern**, **Rutgers**). Because `factors.physical_coefficients.travel_points` keys **only** on `time_zones_crossed`, a null made a real multi-zone trip score as **zero zones**, silently neutering the ratified `tz_per_zone`. **Resolution order, and it is the same table on both sides:** the source value, else **`data/venue_timezones.py`'s static IANA table** (SPEC Appendix A's long-specified "static timezone table"), else **`None` — never a fabricated offset**. `data.schedule_intel.resolve_venue_timezone()` applies it at the **read seam** (so already-built bundles are covered and committed snapshot bytes / `snapshot_id` stay untouched — the A6 precedent), and `data.normalize.cfbd.normalize_venue()` applies it at **build** (so every future bundle bakes it in). **Deliberate, recorded deviation:** SPEC §5.2 puts fallback policy in the *snapshot builder*, and A6's precedent touched only the read seam; this touches the **normalizer** as well, so an already-built bundle and a future rebuild can never disagree. Appendix A's "static timezone table" sanctions the table itself. A test pins that both layers resolve identically — the guarantee that makes the two-layer exception safe. **Any new consumer of `timezone` must go through the resolver, not `venue["timezone"]`.**
>
> **Provenance limitation, recorded deliberately.** The provenance manifest's granularity is the **field group**, not the field — Northwestern reports `"venue": "registry"` (counted *present*) while four of its venue fields are null — and there is no sub-field `fallback_reason` mechanism. So this fallback's provenance lives **here and in the table itself** (each entry carries its source city), not in the manifest. **Adding sub-field provenance is a 2027 item.**
>
> **Timezone is date-dependent, unlike elevation.** `time_zones_crossed` needs a game **date** because UTC offsets are DST-dependent, so a **dateless hypothetical** correctly yields `None` while `travel_distance` — date-free geometry — still computes. That asymmetry is by design, not a defect.

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

### Stored record (v2 — Phase 3d, current)  — `utils/prediction_schema.py`, writer `analytics/predictions.py`

Written by the freeze-exempt slate writer (`analytics.predictions.build_predictions` → `scripts/build_predictions.py`), which runs the **frozen** engine over a snapshot's bettable slate and serializes **every** game incl. `NO_BET` (the legacy `cli/app.py` P4 path filtered non-edge games; NO_BET is now logged + graded per SPEC §7 item 4 / §16.3). Canonical **golden example**: `docs/examples/prediction_schema_v2_2026_week_01.json` (regenerated + byte-identity-pinned by `verify-phase-3`; the schema reference for Phases 4/4.5/5).

**Envelope** `meta`: `schema_version` (int, **= 2**), `model_version` (git tag — see VOLATILE), `snapshot_id`, `week`, `year`, `generated_at` (frozen from the snapshot's `built_at`), `engine`, `prediction_count`, `coverage`.

**Per record** (`V2_RECORD_KEYS`, exact inventory pinned by the parity test): `game_id` (new `{away}-vs-{home}-week{N}` format), `home_team`, `away_team`, `week`, `vegas_spread`, `contrarian_spread`, `predicted_edge`, `edge_direction`, `prediction_type` (incl. `NO_BET`), `no_bet` (bool), `no_bet_reason`, `confidence_tier` (A/B/C; **C is a diagnostic grade, never a live bet** — 3c.6), `confidence` (**0–1** scale, unlike v1's 0–100), `power_rating_spread`, `factor_breakdown` (**per-sub-signal**: `{factor: {value, weighted_value, activated, category}}`, not the v1 flat `{category: float}`), `data_quality` (**0–1**), `line_as_of` (the prediction-time observation's `fetched_at`), and the grading slots `closing_spread`, `clv`, `graded_at` — which stay **`null` on disk forever** (grading writes a separate artifact, D22 / §3a below).

**Grading-filled slots — stay `null` on disk FOREVER (D22).** ⚠ The v2 record's `closing_spread`,
`clv`, `graded_at` are **never written back into `data/predictions/`**. Per **D22** (owner,
2026-07-09) prediction files are **byte-immutable forever** — the pre-kickoff commit is the
pre-registration artifact, verifiable by checksum. Grading writes a **separate append-only graded
artifact** (`data/graded/2026_week_NN.json`, §3a below); the "filled" record exists only as an
in-memory **JOIN** (predictions ⋈ graded) rendered in reports, never materialized to disk. These
three slots remain in the schema (they define the convention *at birth*) but are permanently `null`
in the on-disk prediction file: **predictions are claims, results are outcomes.** The convention the
graded artifact implements:
- `closing_spread` = the home-team consensus spread from `data.normalize.odds.closing_observation` (last observation ≤ that game's own kickoff — per-game as-of-T, never a weekly cutoff); `null` if no closing line was captured (**honest-missing**).
- `clv` = closing-line value **in points, from the bet side's perspective — positive = our number beat the close** (`utils.prediction_schema.clv`): a **home** bet ⇒ `vegas_spread − closing_spread`; an **away** bet ⇒ `closing_spread − vegas_spread`; **`null` when no side was taken** (`edge_direction` neither home nor away — no side ⇒ no perspective ⇒ undefined, f3), distinct from a real `0.0`.
- **`null` vs zero (push) semantics:** `null` is a *missing-ness / no-side* signal, never a value. `clv=null` + `graded_at=null` ⇒ **not yet graded**; `graded_at` set + `closing_spread=null` ⇒ **graded, no closing line (honest-missing)**; `graded_at` set + `closing_spread` present + a side taken ⇒ `clv` computed; a **no-side (neutral) game** ⇒ `clv=null` **even when a closing line was captured** (no perspective to value it from). A **CLV of exactly `0.0`** (our number == the close, on a side that WAS taken) is a **legitimate value, not `null`**. This is distinct from an **ATS push** (the bet ties the number, `home_margin + spread == 0`): a *bet-outcome* concept carried by the graded artifact's `ats_result` (`analytics/calibration_evidence.py::ats_outcome`, `abs < 1e-9` ⇒ `"push"`), **not** encoded as a CLV value. Phase 4 implements this convention — it does not invent one.

### 3a. Graded artifact (`data/graded/2026_week_NN.json`, D22 / Phase 4) — grading output, separate from claims

Grading's output store, keyed by `game_id`, **append-only** (a game's entry is immutable once graded;
new games are appended as they complete — same semantics as `data/lines/`, so the Tuesday catch-up
grade grows the week's file across commits). Built by `analytics.grading` (freeze-exempt), written by
`scripts/grade.py`. The immutability hook (`.claude/hooks/protect_immutable.py`) guards `data/graded/`.
Canonical golden (SYNTHETIC — wk1 unplayed): `docs/examples/graded_record_2026_week_01.json`,
reproduced from the v2 golden slate + `docs/examples/graded_fixture_2026_week_01.json`.

**Envelope** `meta`: `schema_version` (**= 1**, the graded schema), `week`, `year`, `generated_at`,
`engine` (`"grading_v1"`), `graded_count`, `coverage` (`predicted`, `graded`, `ungraded[]`,
`no_closing_line[]`).

**Per record** (`GRADED_RECORD_KEYS`, pinned by the parity test): `game_id`, `home_team`, `away_team`,
`week`, `closing_spread` (`null`=honest-missing), `close_as_of` (the closing observation's `fetched_at`
provenance; `null` if missing), `clv` (per the convention above), `ats_result`
(`"win"`/`"loss"`/`"push"`/`null`, the D22/f2 ratified field — `null` = not gradable or no side),
`is_hypothetical` (bool — the game was `NO_BET`, graded "what would have happened": most NO_BET games
have a hypothetical lean and grade normally; a truly neutral no-lean game gets `ats_result`/`clv`
`null`, its own selectivity bucket), `home_score`, `away_score` (the finals graded against), `graded_at`.

**Reproducibility carve-out (doctrine, not accident — owner rider).** Predictions are **claims** and
are deterministic from a frozen snapshot (§3 byte-identity contract). Gradings are **evented
outcomes** — stamped at wall-clock `graded_at`, dependent on when a game completed and how far the
`data/lines/` series had grown — so the graded artifact is **deliberately NOT part of the snapshot
reproducibility contract**. `graded_at` is a real wall-clock timestamp, not frozen from `built_at`;
the graded golden pins its arithmetic (`closing_spread`/`clv`/`ats_result`) via a fixed synthetic
fixture, not byte-identity over a live-stamped field.

**Artifact taxonomy (D23).** Three tiers, with different mutability contracts:
- **Claims** — `data/predictions/` — **byte-immutable forever** (D22): a pre-kickoff claim is never edited.
- **Outcomes + derived computations** — `data/results/`, `data/archive/`, `data/lines/`, `data/ratings/`, `data/projections/`, `data/graded/` — **append-only** (new files/entries added as events/measurements arrive; existing entries never edited). All guarded by the immutability hook.
- **Renderings** — `reports/` — **pure functions over the above, regenerable at will** (deterministic for frozen inputs like the 2025 retro; fresh for in-season reports as data accrues). A rendering's audit trail is **git history**, not on-disk immutability, so `reports/` is **NOT** hook-guarded and is overwritten on regeneration.

**2025 v1→v2 converter** (`convert_v1_to_v2`, **pure + read-only** — never rewrites the append-only `data/archive/2025` files). Lossy mappings for fields v1 never recorded: `game_id` kept as-is (v1 `{AWAY}_{HOME}_week{N}` join key); `no_bet=False` (v1 predates NO_BET); `confidence_tier` derived from v1's 0–100 confidence via the ratified boundaries; v1's 0–100 confidence carried as `confidence_pct` (kept distinct from the v2 0–1 `confidence`, which is `null`); `factor_breakdown` kept flat + tagged `_v1_flat: true` (per-sub-signal unrecoverable); `power_rating_spread`/`closing_spread`/`clv`/`graded_at`/`line_as_of`/`model_version` `null`.

### Reproducibility contract (define once; CLI + test share it)
`cfb predict rerun` runs in **frozen-clock** mode: it reuses the snapshot's recorded `fetched_at` timestamps and sets prediction wall-clock fields from the snapshot, **not** `datetime.now()`. Two reruns on the same snapshot must be **byte-for-byte identical over the payload minus `VOLATILE_FIELDS`**.

```
VOLATILE_FIELDS = { "generated_at", "timestamp", "generated_date", "model_version" }
#   wall-clock ------------------------------------^   ^-- git-derived, churns per commit until the tag
```
Everything outside this set (spreads, edges, factor values, provenance) must match exactly. Predictions embed the `snapshot_id` they were computed from. **`model_version`** (schema v2) is the `git describe` stamp — it changes on every commit before the `v2026-frozen` tag, so it is VOLATILE and **excluded from the schema-v2 golden byte-identity check** in `verify-phase-3` (which pins the whole prediction-writing path minus these fields). **Corrected 2026-08-07 (D34):** it does **not** resolve to a bare `v2026-frozen` after tagging. `git describe --tags --always --dirty` returns the bare tag only when HEAD *is* the tagged commit; every freeze-exempt commit after it yields `v2026-frozen-N-g<sha>`, which is the form the season's claims actually carry — and is better provenance, since it names the exact tree that produced the claim. Two failure modes this creates, both guarded: a **shallow checkout** fetches no tags, so `--always` silently returns a bare SHA (the pipeline pins `fetch-depth: 0` and the preflight ABORTS unless `model_version()` starts with the freeze tag); and an **uncommitted working tree** at write time stamps `-dirty` (the pipeline commits the snapshot before building predictions).

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
(`prediction_engine._build_prediction_result`). (The `market_sentiment` team-name `hashlib.md5`
"variation" that this paragraph once cited was a fabrication and was **removed in the Bug #7 fix,
D19** — the factor is deterministic simply because it is dormant at 1.0.) Because the
snapshot-first flow has no wall-clock "live" prediction to diverge from, two snapshot-based
predictions are in practice identical over the **full** payload — `test_two_reruns_are_bit_identical`
asserts byte-equality including `timestamp`. `VOLATILE_FIELDS` remains the documented contract
for any future comparison against a wall-clock-stamped record (e.g. the storage envelope's
`generated_date`, which is still set at write time).

---

## 4. `market_sentiment` — dormant multiplicative modifier until slice 1.5 (D19, was Bug #7)

Line-movement history is deferred to slice 1.5 (D6), and it is the factor's **only** real signal.
Until it arrives, `market_sentiment` is a **dormant multiplicative modifier: it returns a neutral
1.0 (no effect on the model edge)** — it does not fabricate a signal. When real movement lands, its
value is the multiplier applied to `total_adjustment` (not the Vegas baseline), clamped to the
ratified `[0.85, 1.15]` cap. See CALIBRATION_LOG *MarketSentiment wiring fix* + DECISIONS D19.

**Superseded (was Bug #7, fixed in D19):** an earlier implementation, while dormant, still
manufactured a signal from a **team-name `hashlib.md5` hash** and **spread-size/week/spread-type
heuristics** (dressed up as "sentiment"), and — worse — never set `is_multiplicative`, so a
1.0-centered multiplier was summed **additively**, injecting a ≈+1.0 constant into every prediction
(the mechanical root cause of the D17 artifact). All of that is removed: the hash and the
`_analyze_game_characteristics` heuristics are deleted (binding #4), and the wiring is multiplicative.
**Public-betting share** remains UNAVAILABLE (no free source) — trap/line-freeze/reverse-line-movement
signals return no-signal (0.0), never simulated.

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
