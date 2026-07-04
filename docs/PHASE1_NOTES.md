# Phase 1 Implementation Notes (Data Layer v2)

> **✅ PHASE 1 COMPLETE — merged to `main`** (1a PR #1/#2, 1b PR #3, 1c PR #4).
> `make verify-phase-1` → ALL PHASE 1 CHECKS PASSED; 376 passed / 4 skipped offline.
> **Next work is Phase 2 — see `docs/PHASE2_NOTES.md`.** This file is the Phase 1 record.

Working handoff notes for Phase 1 (SPEC §5). Companion to the approved plan (see
`docs/DECISIONS.md` D5/D6 and the plan referenced in MEMORY.md), `docs/SCHEMA.md`
(canonical schema + contracts), and `docs/CODE_AUDIT.md`. Captures the
exploration so no session has to re-derive it.

## Current status (branch `phase-1-data-layer`)
- **Done (commit 5f364e9):** `data/clients/cfbd_v2.py` — dumb fetch-parse-raise CFBD **v2** client, live-verified against Tier 1; `tests/test_cfbd_v2_client.py`; D5/D6 in `docs/DECISIONS.md`.
- **Done (1a — team registry):** `data/team_registry.py` + committed `data/registry/{fbs_teams_2026.json,calendar_2026.json}` (provenance-stamped; D7). Added `CFBDv2Client.get_teams`. Retired `data/conferences.py`, `schedule_client._get_hardcoded_conference`, and the normalizer's `_build_team_mappings`/`_build_fcs_teams` (now sourced from the registry; public API unchanged). `validate_membership_counts` + `corroborate_calendar` (D1) + diff-aware `refresh_registry`. Tests: `test_team_registry.py` (17), `test_registry_reconciliation.py` (9), fixture `tests/fixtures/legacy_normalizer_vocab.json`. `scripts/verify_phase_1.py` + `make verify-phase-1` (1a checks pass; 1b/1c PENDING). Suite: **312 passed, 5 skipped**, offline; lint/mypy clean.
- **Done (1b — snapshot-first + engine cutover):** `data/clients/odds.py` (dumb Odds client); `data/normalize/` canonical dataclasses + CFBD/Odds converters; `data/snapshot/` builder → `data/snapshots/YYYY_week_NN/` (canonical data + 100%-coverage provenance manifest; runs `validate_membership_counts` hard-fail + `corroborate_calendar` warn at build start, §5.5.2). Rewrote `data_manager.get_game_context` to read only the snapshot; **deleted `safe_api_call` + every `_get_neutral_*`/`_get_default_*`** (grep-clean); slimmed v1 `cfbd_client` (715→146) + `espn_client` (970→802, `get_team_info` now raises). 3 factors read `context` datasets (dropped `self.cfbd_client`); `market_sentiment` line-movement is the documented `missing` state (removed a hash-based fabrication). `data_quality` = honest scalar + itemized report; engine embeds `snapshot_id` + frozen-clock timestamp (bit-identical reruns). Scripts: `build_snapshot.py`, `rerun_prediction.py`. Tests: `test_odds_client`, `test_normalize`, `test_snapshot`, `test_no_network` + `tests/context_factory.py`; 2 D4 tests re-enabled. `make verify-phase-1` → **ALL 1a+1b PASS** (3 pending for 1c). Suite: **345 passed, 4 skipped**; lint/mypy clean.
- **Done (1c — schedule-intel + closing lines + tooling):** `data/schedule_intel.py` `compute_schedule_intel` (pure; rest/bye/short-week/travel-haversine/tz-zoneinfo/altitude/consecutive-road/sandwich-SP+) + fixture tests; venues + SP+ ratings into the snapshot (new field-groups, manifest-covered). Closing-line **as-of-T** model: snapshot holds only the frozen prediction-time observation (in the hash); the observation **series** is the append-only `data/lines/YYYY_week_NN.json` store (`data/snapshot/lines.py`), seeded by the build and grown by `scripts/fetch_lines.py` (Odds **monthly-credit** guard, D5) — `snapshot_id` is provably unchanged by an append (SCHEMA §3 hash-exclusion). Inspection: `scripts/{inspect_snapshot,status}.py`. **Calendar reconciled from CFBD (D8: no Week 0)** — corroboration = 0 warnings. **v1 `data/cfbd_client.py` deleted**; `results_fetcher`/`schedule_client`/`data_manager` on v2. Scenario tests re-wired (mock_espn data now drives the engine). `make verify-phase-1` → **ALL PHASE 1 CHECKS PASSED**. Immutable-history hook extended to `data/lines/`.
- **Deferred → 1.5:** availability reports + line-movement history; normalizer alias/ESPN/Odds **format** dicts (staged — need ESPN/Odds client sampling; CFBD `alternateNames` already captured via `registry.get_aliases`).

## Deletion map — what Phase 1 REMOVES (SPEC §5.2 acceptance: these must not exist)
`safe_api_call` decorator + all neutral/default fabrication. Verify with grep at the end.
- `data/data_manager.py`: `safe_api_call` def `:19-37` (used `:96,175,254`); `_get_neutral_data_structure` `:545-575`; `_get_neutral_fallback` `:577-588`; `_initialize_fallback_data` `:590-597`; `safe_data_fetch` `:340-356`.
- `data/cfbd_client.py` (the **v1** client — replaced by `data/clients/cfbd_v2.py`): `_get_default_coaching_data` `:512-521`; `_get_default_stats_data` `:523-541`; `_get_default_ratings_data` `:543-550`; hardcoded `3`/`2` experience fallbacks `:358,376,380,388,392,418,438`.
- `data/espn_client.py`: `_get_neutral_team_data` `:771-778`; `_get_neutral_coaching_data` `:780-790`; `_get_neutral_stats_data` `:792-808`; `_estimate_coaching_experience` `:765-769` (hardcoded 5).
- Status sentinels `'neutral_fallback'`/`'default_fallback'`/`'cfbd_data'` leak through quality/source logic — remove with the provenance manifest.

## Hardcoded team/conference lists — retirement status (registry replaces membership)
- ✅ `data/conferences.py` — **deleted** (folded into `data/team_registry.py`; 3 importers repointed: `cli/app.py`, `data/schedule_client.py`, `scripts/verify_phase_0.py`).
- ✅ `data/schedule_client.py::_get_hardcoded_conference` — **deleted**; the `_extract_conference_name` fallback now normalizes then calls `registry.get_team_conference`.
- ✅ `utils/normalizer.py` `_build_team_mappings` + `_build_fcs_teams` — **re-sourced** from `registry.get_fbs_canonical_names()` / `get_fcs_names()` (public API unchanged). Canonical went 134→138 (adds the 4 new FBS members; bonus: `normalize('Missouri State')` no longer fuzzy-matches to `MISSISSIPPI STATE`).
- ⏳ `_build_espn_mappings`, `_build_odds_mappings`, `_build_alias_mappings` — **staged** (name-format plumbing, not membership; need ESPN/Odds client sampling to re-source safely). `registry.get_aliases()` exposes CFBD `alternateNames` ready for this.
- ✅ `engine/confidence_calculator.py::_is_major_conference_game` — the last hardcoded `{'SEC','BIG TEN',...}` set (a pre-existing initial-commit residual, surfaced by the code review) now reads `registry.get_p4_conference_names()`.
- ✅ `scripts/verify_phase_1.py` greps **all application code** (`data/`, `utils/`, `engine/`, `factors/`, `cli/`, `main.py`) for `BIG TEN`/`PAC-12` conference-name literals (not colon-anchored — catches sets/lists/dict-keys), excluding only the sanctioned `data/team_registry.py` (documented `P4_CONFERENCES`/`EXPECTED_COUNTS_2026`). `verify_phase_0` updated: ACC check now `CAL` (canonical) not `CALIFORNIA`.

## 1c / later follow-ups (recorded so they aren't re-derived)
- **v1 `cfbd_client.get_games` is a lingering dead-API risk (migrate in 1c).** The 1b cutover
  surgically slimmed the v1 client to `get_games`/`test_connection` (owner's "surgical" choice over
  full removal), but two consumers still use its **v1** `/games` call on what is now the v2 host:
  `utils/results_fetcher.py:172` and `data/schedule_client.py:102`. The v1 response shape is not
  guaranteed by the v2 API, so these can silently return wrong/empty data. **1c: repoint both to
  `data/clients/cfbd_v2.py::get_games` and adapt their parsing to the raw v2 shape, then delete the
  v1 `data/cfbd_client.py` shim entirely.**
- **Calendar corroboration diagnosis (D1, 16 warnings — expected, mostly benign).** `corroborate_calendar`
  surfaces two distinct things: (a) **weeks 2–15** — a ≤2-day boundary-convention offset (hand calendar
  is Sunday-anchored 7-day weeks; CFBD `startDate` is mid-week). **Benign**: both put identical Saturday
  game dates in the same week number (`resolve_week` verified correct for real Saturdays), so no
  misclassification. (b) **week 0** — CFBD **folds Week 0 into Week 1** (its wk1 window 08-29→09-08
  absorbs the 8/29 openers), so CFBD has no Week 0 while SPEC §16.2 defines Week 0 = 2026-08-29. Not a
  1b bug (the snapshot slate filters by CFBD's own `week` field consistently; the hand calendar is only
  `resolve_week` for CLI date→week), but a **week-numbering reconciliation for Phase 4.5** when the
  calendar folds into `season.yaml`. No calendar change made in 1b — the warning is the intended surfacing.

## 1b code-review follow-ups (recorded from the pre-commit review)
- **Blocker FIXED:** `market_sentiment` public-betting simulation + hardcoded team lists removed
  (see CODE_AUDIT Phase-1b) — the audit docs and `verify_phase_1` fabrication grep are corrected.
- **Scenario-test coverage loss (do in 1c):** the ~12 migrated tests in `test_real_world_scenarios.py`
  still build elaborate `mock_espn` payloads that are now dead — the engine runs against
  `context_factory`'s generic defaults, so those tests are effectively **smoke tests** (engine runs
  end-to-end), not the specific-behavior tests their names imply (e.g. an asymmetric venue-boost
  assertion passes for structural reasons). Re-wire real per-test data via `patched_context(**kwargs)`
  (as the 2 D4 tests already do) or trim the misleading setup.
- **`style_mismatch.py:127` latent calc (Phase 3):** `offense.get('plays', 70) / max(1, team_stats.get('season', 1))`
  — the canonical `AdvancedStats` carries no `season` key, so this always divides by 1, making
  "plays per game" a raw season total. The pace *comparison* is still directionally valid (both teams
  scaled identically), but the absolute value is wrong; fix when the factor is calibrated in Phase 3.
- **Committed snapshot is a manual artifact:** `data/snapshots/2026_week_01/` is a hand-run
  `build_snapshot.py` bundle (real 2026 data, honest `missing` coverage) checked in ahead of the
  Phase-5 automation as the reproducibility fixture verified by `verify_phase_1`; it will be
  superseded by pipeline-generated bundles once Phase 5 lands (it is not an audit-trail artifact).

## The 3 network-bypassing factors (move behind the snapshot in 1b)
- `factors/scheduling_fatigue.py:94` → `get_games` → snapshot `games`
- `factors/style_mismatch.py:108` → `get_advanced_stats` → snapshot `advanced_stats`
- `factors/market_sentiment.py:167` → `get_betting_lines` → snapshot `betting_lines` (+ missing-movement state, SCHEMA §4)

## Existing data layer (reuse where noted)
- `data/data_manager.py`: `get_game_context` is the single engine entry point; short-circuits to empty context (quality 0) when no betting line. Global singleton `data_manager` (`:648`). Rewrite to read the snapshot in 1b.
- `data/cache_manager.py`: **memory-only** (no disk) — §5.4 needs disk snapshotting to `data/cache/`. Semantic keys/TTL/LRU reusable; extend to disk.
- `utils/normalizer.py`: `normalize` → clean → alias → mascot-strip → fuzzy (`difflib`). Keep API; re-source data.
- `utils/season_calendar.py`: `resolve_week` for snapshot week selection.
- `utils/rate_limiter.py`: sliding-window; `setup_api_rate_limiters(odds_limit=83, espn_limit=60)`. **CFBD limiter is NOT created here** — the v1 client self-registers 10/min·150/day (`cfbd_client.py:41-46`); config `rate_limit_cfbd` (150/day) is dead. Replace with a v2 monthly-quota budget guard (5,000/mo **shared with basketball**, D5).

## Verified source facts (data-source-scout, 2026-07-03)
### CFBD v2 — base `https://api.collegefootballdata.com`, `Authorization: Bearer <key>`
- v1 shapes are GONE (breaking changes) — map fields against the current OpenAPI (`https://apinext.collegefootballdata.com`).
- Per-season conference membership = `GET /teams?year=YYYY` (or `/teams/fbs`), NOT `/conferences` (year-agnostic).
- Endpoints used: `/teams/fbs`, `/conferences`, `/calendar`, `/games`, `/coaches`, `/stats/season`, `/stats/season/advanced` (EPA/PPA, successRate, explosiveness, havoc), `/ratings/sp`, `/player/returning`, `/venues` (lat/long, **elevation**, **timezone**, dome), `/lines`. **No injury endpoint exists.**
- Rate model = **monthly call quotas** (not throttling). Free 1,000/mo; **owner has Tier 1 ($1/mo, 5,000/mo shared FB+BB)** (D5). GraphQL/realtime = Tier 3 ($10) — not needed for batch.
- **Live-verified 2026-07-03:** `/conferences`→106; `/teams/fbs?year=2026`→138 (SEC=16), each with `conference`, `division`, `alternateNames`; `/calendar?year=2026`→16 weeks with `startDate`/`endDate`/`week`/`seasonType`.
### The Odds API — `GET /v4/sports/americanfootball_ncaaf/odds`
- Cost = markets×regions; use `regions=us&markets=spreads` ≈ 1 credit/call. Free = 500 credits/mo. **Historical odds are paid (10×)** → do fixed-time current-odds snapshots for line movement, not historical. Cheaper `/events` and `/scores` where possible.
### Availability reports (DEFERRED → 1.5, D6)
- No JSON API. SEC/Big Ten/Big 12/ACC = JS-rendered Sidearm `.aspx` (plain fetch returns only page chrome → needs headless render/spike). Differing status vocab (SEC uses 0/25/50/75/100% + "Game-Time Decision"; ACC "uncertain for any reason"). Conference games only. Record `availability_data: null` for non-P4; never penalize confidence for absence.

## Slice 1.5 / Phase 6 LLM design notes (owner discussion, July 2026 — design direction, NOT ratified decisions)
Context preservation for the future 1.5 / Phase 6 planning session. **Design direction only — nothing here is a ratified decision or committed scope.**

1. **Availability-report parsing — candidate approach: local-LLM extraction.** Run a local model (Ollama, ~8B class — owner already has it installed) over the scraped Sidearm page text, with a constrained schema `{player, position, status ∈ {out, doubtful, questionable, probable, available}}`; emit `"unknown"` for anything unclear, never invent. Chosen over a deterministic parser (brittle against 4 conferences' differing vocab + format drift) and over paid API calls (owner declines recurring cost).
2. **Treat LLM output as an untrusted API:** schema-checked, player/team names resolved through the normalizer, rejects logged — never trusted raw.
3. **Provenance:** LLM-extracted facts carry `source: "llm_extracted"` + model name + the raw source text they came from.
4. **Influence boundary (reaffirms SPEC Phase 6 + Appendix A):** LLM-derived facts feed **confidence / NO_BET only — never the spread**.
5. **Architecture: a local, manual companion step** (e.g. `make qualitative`) run on the owner's machine — **NOT a GitHub Actions dependency** (Actions runners can't reach local Ollama; the paid-API alternative is declined). Skipped weeks are fine: availability stays honestly `missing`, pipeline unaffected. If the feature proves functional **and** actually used through the first half of the season, a self-hosted runner on the owner's Mac may later automate it as a secondary **allowed-to-fail** job — automation must be **earned by usage evidence**, never added to the never-cut pipeline.
6. **Viability gate first:** before any 1.5 planning, a ~20-minute prototype (one conference page's text through the extraction prompt) decides whether the LLM approach is viable at all.
7. **Weekly-report LLM narrative is deprioritized** (weakest use case; the report is generated by Actions, where local models can't run). Interactive uses (devil's-advocate on A-tier picks, hypothetical-game color) need no automation by nature.

## Verification target — `make verify-phase-1` (per SPEC §5 acceptance)
1. `cfb data snapshot --week N` → 100%-covered provenance manifest (source/timestamp/`missing`).
2. No-network test: full prediction with networking disabled passes.
3. Two `cfb predict rerun` bit-identical (minus `VOLATILE_FIELDS`, frozen clock).
4. Grep: no `safe_api_call`/neutral fabrication; no hardcoded team/conference lists anywhere.
5. Registry validates 2026 counts; name-coverage test passes for all FBS teams.
6. Schedule-intel unit tests (travel/rest/timezone) with fixtures.
7. Full suite green offline (keep/exceed current count).
