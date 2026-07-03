# Phase 2 Notes — Power Rating Layer & Hypothetical Matchup Mode (SPEC §6)

Kickoff/handoff doc for Phase 2. Companion to `docs/SPEC.md` §6 (authoritative),
`docs/DECISIONS.md` (D1–D8), `docs/SCHEMA.md` (canonical data), `docs/PHASE1_NOTES.md`
(what shipped in Phase 1). Read SPEC §6 and §14 (Agentic Guide) before any work.

## Status

- **Phase 1 (data layer) is COMPLETE and merged to `main`:** 1a registry (PR #1/#2),
  1b snapshot-first + engine cutover (PR #3), 1c schedule-intel + closing lines +
  tooling (PR #4). `make verify-phase-1` → **ALL PHASE 1 CHECKS PASSED**. Suite: 376
  passed / 4 skipped, offline; lint + mypy clean.
- **Phase 2 has not started.** One phase = one branch (`phase-2-...`) = one PR to main.

## What Phase 2 delivers (SPEC §6)

1. **In-house Elo power ratings** (owner decision **§16.4**: build our own transparent Elo,
   do NOT blend public ratings). Current-season-only (Data Recency Principle); MOV-dampened;
   updated weekly from 2026 games; stored per week. **No seeding from 2025 results.**
   Explainable + reproducible, no black boxes.
2. **Roster-continuity preseason priors** (so weeks 1–3 aren't garbage): a prior that discounts
   last season by returning production — e.g. preseason SP+, or an in-house prior from
   returning-production %. High uncertainty that **decays** as 2026 games accumulate.
3. **Early-season mode (weeks 1–3):** widen confidence bands, more `NO_BET`, cap rating-derived
   signal influence, lean on physical/scheduling factors. Engine exposes a `rating_uncertainty`
   value in every output during this window.
4. **Matchup pricer** `price(home, away, venue, date, context) → model spread` = rating
   differential + home-field value + Phase-1 schedule-intelligence adjustments. **Identical for
   real games and hypotheticals.**
5. **Hypothetical CLI:** `main.py hypothetical --home "..." --away "..." [--neutral-site] [--venue]
   [--date] [--show-factors]` — model spread, factor breakdown, confidence, caveats; no Vegas line.
6. **Season projections + belief-drift** (§6.5) + **model-vs-market diagnostic** (§6.6). Both are
   **CUT-FIRST / freeze-exempt tooling** (§15 timeline "cut first") — ship after the freeze if time
   is tight. `data/projections/2026_week_NN.json`; `cfb project [--team X]`. The spread→win-prob
   conversion must be **documented in `docs/SCHEMA.md`**.

## What Phase 1 already gives you (reuse — don't rebuild)

The engine reads ONLY the weekly snapshot; the pricer should too (zero new API cost for projections).
Snapshot `data` keys (`data/snapshots/2026_week_NN/snapshot.json`): `teams, games, advanced_stats,
sp_ratings, venues, schedule_intel, betting_lines`.

- **`data/schedule_intel.py::compute_schedule_intel(team, opponent, game_week, game_date, is_home,
  game_venue, season_games, venues, ratings)`** — the pure function the pricer's schedule adjustments
  AND hypothetical mode both call (travel/rest/tz/altitude/sandwich). Already serves arbitrary matchups.
- **`sp_ratings` snapshot field-group** + `data/clients/cfbd_v2.py::get_sp_ratings(year)` — the SP+
  prior source. ⚠ **CFBD has NOT posted 2026 preseason SP+ yet** (all `missing` in the current
  snapshot) — the prior must not depend solely on SP+ this far out (see decisions below).
- **`data/clients/cfbd_v2.py::get_returning_production(year)`** — exists but NOT yet fetched into the
  snapshot; the returning-production-% prior would add it as a new snapshot field-group.
- **`games`** (league-wide, per-game scores/dates) — the Elo update input; already in the snapshot.
- **`betting_lines[game].vegas_spread`** (frozen consensus) — the market spread for the model-vs-market
  diagnostic (§6.6). Closing spreads for CLV live in the append-only `data/lines/` store (Phase 4).
- **`data/team_registry.py`** — every FBS team + `get_venue(team)` (for hypotheticals at any venue).
- **Reproducibility contract (SCHEMA §3):** predictions embed `snapshot_id`; result timestamp is
  frozen from the snapshot; `market_sentiment` uses stable hashlib. **The pricer must be deterministic**
  (a rating for a given snapshot is fixed). Bit-identical rerun test guards it.
- **`engine/prediction_engine.py`** — where the pricer/rating integrate (the model spread + model-vs-market
  gap join the result). Reads context via `data_manager.get_game_context` (snapshot-only, no network).

## Binding owner decisions (do NOT re-litigate; propose, never decide, on anything new)

- **§16.4:** in-house transparent Elo, not blended public ratings. Public preseason ratings permitted as
  roster-continuity priors ONLY.
- **Data Recency Principle (SPEC §2):** team-quality inputs use current-season (2026) data only. Prior
  seasons allowed for exactly two things: market-behavior calibration (the 2025 archive → Phase 3
  weights) and roster-continuity-aware preseason priors (discount 2025 by returning production).
- **D8 (this project):** for 2026 there is **no Week 0** — CFBD numbering, opener = **week 1**
  (2026-08-29). SPEC §16.2 still says "Week 0 games ARE in scope"; those games are in scope, just
  named week 1. Don't be confused by the §16.2 "Week 0" label.
- **Freeze discipline (§16.2):** `v2026-frozen` tag must exist **before the week-1 prediction run**
  (~Aug 24 target; Aug 29 absolute outer bound). After the tag, `factors/`, `engine/`, weight/threshold
  config are immutable. **The pricer LOGIC and rating-update LOGIC are freeze-disciplined; the rating
  VALUES update weekly (data, not code).** Projections/hypothetical polish are cut-first, freeze-exempt.
- No hardcoded team/conference names (registry only); no fabricated/neutral-filled data (missing stays
  missing + provenance); no AI attribution in commits/PRs (`includeCoAuthoredBy: false`).

## Decisions Phase 2 must PROPOSE to the owner (record in DECISIONS.md as D9+)

- **Elo formulation:** K-factor, MOV-dampening function, home-field-advantage points, starting rating,
  regression-to-mean between weeks. Must be explainable.
- **Preseason prior source given SP+ is empty preseason:** returning-production-% in-house prior now
  (add `get_returning_production` to the snapshot) vs. wait for SP+ to populate closer to the season.
  This is the highest-priority open question.
- **`rating_uncertainty`** definition + decay schedule (weeks 1–3 window) and the early-season signal caps.
- **spread→win-prob conversion** constant/curve (document in SCHEMA §, per §6.5).
- **Storage:** `data/ratings/2026_week_NN.json` (new; per-week, append-only-ish historical) +
  `data/projections/2026_week_NN.json`. Confirm gitignore posture (projections already listed as
  "intentionally NOT ignored"; add `data/ratings/`).

## Likely new files (implementer's judgment)

- `engine/power_ratings.py` (Elo update + preseason prior + `rating_uncertainty`), `engine/matchup_pricer.py`
  (`price(...)`), `scripts/update_ratings.py` + `scripts/build_projections.py` (script entries, consistent
  with 1b/1c; the polished `cfb` CLI is Phase 4.5), `main.py hypothetical` + `cfb project` wiring, tests
  (synthetic-season rating updates, pricer determinism, hypothetical for any 2 FBS teams).
- `scripts/verify_phase_2.py` + `make verify-phase-2` encoding SPEC §6 acceptance.

## Acceptance (SPEC §6) — `make verify-phase-2`

Hypothetical command works for any two FBS teams; for real games both model spread and Vegas spread are
logged; rating-update logic has tests with **synthetic seasons**; weekly projection files exist for every
completed week; `cfb project [--team X]` renders projected win totals + week-over-week drift.

## Working agreement (from the owner, proven across Phase 1)

Verify before asserting (paste evidence). Precise up-front contracts, not mid-implementation fixes. Run the
`code-reviewer` subagent on the diff **before** opening the PR (it caught real fabrication in 1b and a dead
budget guard + mislabeled data in 1c — the author isn't the grader). Owner-only decisions (spend,
calibration, the freeze, changes to §16) are proposed, never decided, and recorded in DECISIONS.md. Keep
docs current (`SCHEMA.md`, `PHASE1_NOTES.md`/this file, `CODE_AUDIT.md`, `DECISIONS.md`). See the
`owner-working-style` auto-memory for the full list.
