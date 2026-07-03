# Phase 1 Implementation Notes (Data Layer v2)

Working handoff notes for Phase 1 (SPEC §5). Companion to the approved plan (see
`docs/DECISIONS.md` D5/D6 and the plan referenced in MEMORY.md), `docs/SCHEMA.md`
(canonical schema + contracts), and `docs/CODE_AUDIT.md`. Captures the
exploration so no session has to re-derive it.

## Current status (branch `phase-1-data-layer`)
- **Done (commit 5f364e9):** `data/clients/cfbd_v2.py` — dumb fetch-parse-raise CFBD **v2** client, live-verified against Tier 1; `tests/test_cfbd_v2_client.py` (7 mocked); D5/D6 in `docs/DECISIONS.md`; lint scope extended to `data/clients/`. Suite: 286 passed, 5 skipped, offline.
- **Next (1a):** `data/team_registry.py` (see §5.5 + SCHEMA §5) → then finish `docs/SCHEMA.md` dataclasses in `data/normalize/`.
- **Then 1b:** snapshot builder + provenance + gut `safe_api_call`/neutral-fill + engine-reads-snapshot + no-network test + reproducibility contract.
- **Then 1c:** schedule intelligence + closing-line "as-of T" capture + `cfb data inspect`/`status`.
- **Deferred → 1.5:** availability reports + line-movement history.

## Deletion map — what Phase 1 REMOVES (SPEC §5.2 acceptance: these must not exist)
`safe_api_call` decorator + all neutral/default fabrication. Verify with grep at the end.
- `data/data_manager.py`: `safe_api_call` def `:19-37` (used `:96,175,254`); `_get_neutral_data_structure` `:545-575`; `_get_neutral_fallback` `:577-588`; `_initialize_fallback_data` `:590-597`; `safe_data_fetch` `:340-356`.
- `data/cfbd_client.py` (the **v1** client — replaced by `data/clients/cfbd_v2.py`): `_get_default_coaching_data` `:512-521`; `_get_default_stats_data` `:523-541`; `_get_default_ratings_data` `:543-550`; hardcoded `3`/`2` experience fallbacks `:358,376,380,388,392,418,438`.
- `data/espn_client.py`: `_get_neutral_team_data` `:771-778`; `_get_neutral_coaching_data` `:780-790`; `_get_neutral_stats_data` `:792-808`; `_estimate_coaching_experience` `:765-769` (hardcoded 5).
- Status sentinels `'neutral_fallback'`/`'default_fallback'`/`'cfbd_data'` leak through quality/source logic — remove with the provenance manifest.

## Hardcoded team/conference lists to retire (registry replaces all)
- `data/conferences.py` (interim Phase-0 module — fold into `data/team_registry.py`).
- `data/schedule_client.py::_get_hardcoded_conference` `:410-452` (Phase-0 residual; the Phase-0 verify grep only covered `cli/`+`main.py`).
- `utils/normalizer.py` hardcoded dicts: `_build_team_mappings` `:202-261`, `_build_espn_mappings` `:263-344`, `_build_odds_mappings` `:345-388`, `_build_alias_mappings` `:389-647`, `_build_fcs_teams` `:649-786`. Keep the public API (`normalize`, `is_fcs_team`, `is_fbs_vs_fcs_matchup`); source its data from the registry (CFBD `/teams/fbs.alternateNames`).
- Extend `scripts/verify_phase_*` grep for `'BIG TEN':` etc. to `data/`, `utils/normalizer.py`, `schedule_client`.

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

## Verification target — `make verify-phase-1` (per SPEC §5 acceptance)
1. `cfb data snapshot --week N` → 100%-covered provenance manifest (source/timestamp/`missing`).
2. No-network test: full prediction with networking disabled passes.
3. Two `cfb predict rerun` bit-identical (minus `VOLATILE_FIELDS`, frozen clock).
4. Grep: no `safe_api_call`/neutral fabrication; no hardcoded team/conference lists anywhere.
5. Registry validates 2026 counts; name-coverage test passes for all FBS teams.
6. Schedule-intel unit tests (travel/rest/timezone) with fixtures.
7. Full suite green offline (keep/exceed current count).
