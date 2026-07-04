# Decisions Log

Binding owner decisions made outside the resolved SPEC §16 set. Each entry records the question, the decision, and the rationale. Referenced by the phase work as `D<N>`. SPEC §16 remains the authoritative source for the originally-resolved decisions; this log captures decisions taken since.

---

## D1 — Phase 0 week-inference source
**Date:** 2026-07-02
**Context:** SPEC §4.4 says the silent-week-default fix should "derive the week from the actual date via the season calendar," but no calendar file exists yet and `season.yaml` is formally a Phase 4.5/5 artifact (SPEC §9, §10.6).
**Decision:** The Phase 0 date→week deriver reads a dedicated **`data/season_calendar_2026.json`** (season + per-week start/end dates), not `season.yaml`. Phase 4.5 later folds this calendar into `season.yaml`.
**Rationale:** Unblocks the Phase 0 bug fix with an honest, testable date→week source without prematurely claiming the Phase 4.5 config filename. Week boundaries are Saturday-anchored from Week 0 = 2026-08-29 (SPEC §16.2) on standard cadence; exact boundaries are correctable data, not code.

---

## D2 — 2025 audit-trail archive
**Date:** 2026-07-02
**Context:** SPEC §4.3 + §16.5 require importing the 2025 prediction/result JSONs into `data/archive/2025/` with a provenance note. Those JSONs currently live in `data/predictions/` and `data/results/` as `2025_week_NN*.json`.
**Decision:** **Copy** the 14 prediction + 14 result JSONs into `data/archive/2025/{predictions,results}/` with a `data/archive/2025/README.md` provenance note; leave the originals in place.
**Rationale:** `data/predictions/`, `data/results/`, and `data/archive/` are append-only historical artifacts (CLAUDE.md principle 5). Copying (not moving) satisfies §4.3/§16.5 without disturbing paths existing scripts read.

---

## D3 — Repo goes private; AI tooling is committed, not hidden
**Date:** 2026-07-02
**Context:** Policy reversal from the original "nothing AI-related may be committed" rule. The repo is going private on GitHub and may be published in Aug 2026.
**Decision:**
- Repo visibility flips to **private** (`gh repo edit Brandon12200/cfb-predictor-2026 --visibility private`).
- `.gitignore` stops ignoring `CLAUDE.md`, `IMPLEMENTATION.md`, `KICKOFF_PROMPT.md`, and `.claude/`. Still ignored: `.claude/settings.local.json`, `.claude/memory/`, `CLAUDE.local.md`, `.env*`.
- `docs/IMPLEMENTATION.md` folded into `docs/SPEC.md` as **§14 "Agentic Implementation Guide"**; Timeline renumbered §14→§15 (incl. §14.1→§15.1), Owner Decisions §15→§16 (incl. §15.1–.7→§16.1–.7); all `§15.x` cross-refs updated in SPEC.md and CLAUDE.md; `docs/IMPLEMENTATION.md` deleted.
- CLAUDE.md's "nothing AI-related may be committed" rule removed; `.claude/` config + docs now commit normally.
**Surviving constraint:** `"includeCoAuthoredBy": false` stays set and commit messages / PR text contain **no AI attribution** — history can't be easily scrubbed once the repo is published.
**Rationale:** Committing the agent infrastructure and decision docs makes future agent sessions reproducible and the engineering showcase legible, while the private-until-review posture plus the no-attribution constraint protects the publishable history.

---

## D4 — Phase 0 makes the full test suite green offline
**Date:** 2026-07-02
**Context:** The squashed `Initial commit: 2026 season rebuild` baked in code/test drift: the committed suite has ~18 genuine pre-existing failures (stale tests referencing removed classes e.g. `ATSRecentFormCalculator`; tests asserting old API shapes e.g. `validate_api_keys`; bugs inside dead-code modules) and a large block of tests that make **real network calls** through a sleeping rate limiter, so the suite cannot run offline/deterministically. This contradicts SPEC Phase 0 acceptance ("all existing tests pass") and the README's "305 tests" claim. Verified: stashing all Phase-0 changes reproduces the identical failure count, so the drift predates this work.
**Decision:** Get the **entire** suite green and offline within Phase 0 (owner choice over the lighter "quarantine network tests" option): delete dead modules with their tests (item 5); fix or remove stale unit tests; and mock all client/network calls (and neutralize rate-limiter sleeps) via a shared test fixture layer so `make test` runs the full suite deterministically with no network.
**Note:** This front-runs part of Phase 1's snapshot/no-network architecture (SPEC §5). Phase 1 still owns the canonical `engine passes a no-network test` enforcement; the Phase 0 mocking layer is an interim guard, not the permanent data architecture.
**Rationale:** A trustworthy green suite is the guard rail for the `main.py` decomposition (item 6) and every later phase; leaving a broken baseline would undermine the freeze/audit-trail credibility the project is built on.

---

## D5 — API tier for Phase 1: existing CFBD Tier 1 + Odds API free
**Date:** 2026-07-03
**Context:** Phase 1 (data layer v2) needs a decided API budget; CFBD moved from request-throttling to monthly call quotas, and any paid tier is an owner spend decision.
**Decision:** Use the owner's existing **CFBD Tier 1** subscription — **$1/mo, 5,000 requests/mo shared between the football and basketball APIs** — plus **The Odds API free tier** (500 credits/mo). Verified live: CFBD v2 (`https://api.collegefootballdata.com`, Bearer auth) returns 200 for `/conferences`, `/teams/fbs?year=2026`, `/calendar?year=2026`.
**Implications:** The 5,000-cap is **shared with basketball**, so the design fetches **league-wide** (year/week-scoped, all teams per call ≈ 110 CFBD calls/season) and caches to disk; the config budget guard must treat 5,000/mo as the shared ceiling. Tier 1 also exposes Weather / Live Scoreboard / Live PBP — unused by the batch weekly pipeline (Weather stays out of 2026 core per SPEC Appendix A).

---

## D6 — Phase 1 scope: core now, availability + line-movement deferred to slice 1.5
**Date:** 2026-07-03
**Context:** Phase 1 is the largest phase (~7 weeks to the freeze). Availability-report ingestion is "cut second" per SPEC §14.1, and the four Power-Four report pages are JS-rendered Sidearm `.aspx` whose data format could not be confirmed without a headless-browser pass.
**Decision:** Ship **core Phase 1** — 4-layer data architecture (clients/normalize/snapshot/engine-reads-snapshot), CFBD v2 migration, provenance manifest, canonical team registry, schedule-intelligence dataset, closing-line capture, inspection tooling — and **defer availability-report ingestion and best-effort line-movement history to a follow-up slice (1.5)**.
**Implications:** In core Phase 1, `market_sentiment` consumes only the prediction-time spread (+ CFBD opening line where present); line-movement is recorded as `missing` in the manifest and the factor's missing-movement behavior is a documented, deliberate state — never fabricated.

---

## D7 — Team registry is a committed, provenance-stamped artifact (Phase 1a)
**Date:** 2026-07-03
**Context:** The season team registry (SPEC §5.5) is built from a live CFBD `/teams?year=2026` call, but the whole suite runs offline (network blocked, `tests/conftest.py`) and the `normalizer` singleton is imported at process start nearly everywhere — a network call on import is impossible. Three sub-decisions were needed on how the registry data lives and how CFBD names reconcile against the existing canonical vocabulary.
**Decision:**
- **Committed artifact.** The live payload is persisted to committed `data/registry/fbs_teams_2026.json` (138 FBS + 127 FCS rows) and `data/registry/calendar_2026.json`, each with a `_provenance` header (`source`, `endpoint`, `year`, `fetched_at`, counts). Consistent with the already-committed `data/season_calendar_2026.json`. Live fetching is confined to `refresh_registry` (`python scripts/refresh_registry.py`; the `cfb data registry` CLI wrapper lands with the 1c `cfb data` tooling), which is **diff-aware and confirm-before-overwrite** so a CFBD hiccup can't silently rewrite slate scope.
  - *On SPEC §5.5's "cached in the snapshot with provenance":* the registry is season-scoped and needed **before** any weekly snapshot exists (and at import time by the normalizer), so it lives in a standalone committed `data/registry/` rather than inside `data/snapshots/2026_week_NN/`. It still carries provenance like everything else; 1b's snapshot builder references this registry rather than re-deriving membership per week.
- **Existing canonical vocabulary stays authoritative.** Each CFBD `school` maps to the normalizer's existing UPPERCASE canonical name; where CFBD's spelling diverges (8 cases, e.g. `Ole Miss→MISSISSIPPI`, `California→CAL`) an explicit `CANONICAL_OVERRIDES` entry handles it. Genuinely new FBS members absent from the 2025 vocabulary (`DELAWARE`, `MISSOURI STATE`, `NORTH DAKOTA STATE`, `SACRAMENTO STATE`) get a new canonical name. A reconciliation test (`tests/test_registry_reconciliation.py`) fails CI if any CFBD team resolves by implicit fuzzy match rather than one of these three explicit routes — this caught `Missouri State` silently fuzzy-matching to `MISSISSIPPI STATE`.
- **Incremental retirement.** 1a retires the hardcoded **membership + FCS** lists (`data/conferences.py`, `schedule_client._get_hardcoded_conference`, normalizer `_build_team_mappings`/`_build_fcs_teams`). The normalizer's alias / ESPN / Odds **format** dicts stay for now (they need ESPN/Odds client sampling that doesn't exist yet) and are staged to a later Phase-1 slice.
**Implications:** `data/team_registry.py` is the single sourced home for membership; the `verify-phase-1` grep forbids conference-membership dict literals everywhere except that module (which holds the small documented scope/validation constants `P4_CONFERENCES` and `EXPECTED_COUNTS_2026`). `validate_membership_counts()` and `corroborate_calendar()` are built and unit-tested in 1a but must be **wired into the snapshot builder at build time in 1b** (SPEC §5.5.2). UConn is a known 2026 FBS independent intentionally kept out of the tracked P4 betting slate (Notre Dame only), matching prior behavior.

---

## D8 — 2026 season calendar adopts CFBD week numbering; **abolishes Week 0** (supersedes SPEC §16.2, approved by owner)
**Date:** 2026-07-03
**Context:** The Phase-0 interim `data/season_calendar_2026.json` (D1) used hand-built, Saturday-anchored Sunday–Saturday weeks with a **Week 0** (per SPEC §16.2, "Week 0 = 2026-08-29"). 1b's D1 corroboration (`corroborate_calendar()` vs CFBD `/calendar?year=2026`) surfaced 16 warnings: a systematic boundary offset (weeks 2–15) plus **CFBD has no Week 0** — it folds the Aug-29 openers into **week 1** (its week-1 window 08-29→09-08). Two independent week-numbering systems (the hand calendar vs CFBD's `week` field, which the snapshot slate filter uses) is a permanent off-by-one hazard at the season opener.
**Decision:** Regenerate `data/season_calendar_2026.json` from CFBD `/calendar` as the source of truth, adopting CFBD's regular-season week numbering. **There is no Week 0 for 2026** — the Aug-29 opener games are **week 1**. Weeks are `[start, end]` inclusive and non-overlapping (`start` = CFBD `startDate`; `end` = day before the next week's start). This **supersedes SPEC §16.2's Week-0 convention** for 2026. **Owner-approved amendment** (ratified by approving the 1c plan) — an explicit audit-trail choice, not drift. `corroborate_calendar()` now returns **zero** warnings; `verify-phase-1` asserts it.
**Implications:** The opener games remain fully in scope, just named week 1 — no games are dropped. **Freeze timing is unchanged in substance:** the `v2026-frozen` tag must still precede the first prediction run — now "before the late-August week-1 build" (~Aug 24 target). The disappearance of the "Week 0" label must not relax that. `resolve_week`/`test_week_inference` updated to the new boundaries; Phase 4.5 folds this calendar into `season.yaml`.

---

## D9 — In-house Elo formulation + constants (Phase 2a) — **RATIFIED (owner, 2026-07-03)**
**Date:** 2026-07-03
**Context:** SPEC §6.1/§16.4 require an in-house, transparent Elo (not a public-rating blend). The constants must NOT be borrowed from another sport's Elo — FiveThirtyEight's NFL model starts from carried-over priors and only needs small in-season corrections; a flat-prior, current-season-only, ~12-game CFB system is the opposite regime, and a naive K=20 compresses ratings so badly the model-vs-market diagnostic becomes noise (invisible until October).
**Decision (structure — fixed):** classic Elo (400-scale logistic), completed 2026 games only (never seeded from 2025), MOV dampener `ln(|margin|+1)·mov_c/(mov_b·|ΔR_winner|+mov_c)`, **decaying K** `K(n)=k_late+(k_early−k_late)·exp(−n/k_decay_games)` (n = the two teams' avg games played; shares the games-played curve with D11), zero-sum updates (mean stays at baseline 1500), determinism via completed-only games sorted by `(week, start_date, home, away)`.
**Proposed constants** (`EloConfig`, `engine/power_ratings.py`), gated by the dispersion acceptance test and recorded in `CALIBRATION_LOG.md`: `k_early=64, k_late=22, k_decay_games=6, mov_c=2.2, mov_b=0.0018, hfa_elo=50 (=2.5 pts), elo_per_point=20`. Dispersion evidence: synthetic double round-robin (7 teams, true strengths −15…+15, incl. strong-vs-strong) recovers **30.8 pts** top-vs-bottom neutral (band 24–40), rank-fidelity r=0.998; naive K=20 gave ~19.7.
**Governance:** calibration is owner-only (§14.3). Proposed with the dispersion-test evidence and **ratified by the owner 2026-07-03** (CALIBRATION_LOG entry marked RATIFIED). Frozen at `v2026-frozen`.

---

## D10 — Preseason prior source: hybrid (SP+ preferred, returning-production fallback) — **CONFIRMED (owner)**
**Date:** 2026-07-03
**Context:** CFBD's 2026 preseason SP+ **and** returning production are both still empty at the planning date (verified live). The prior is needed only so weeks 1–3 output isn't garbage (roster-continuity-aware, permitted carve-out to the Data Recency Principle).
**Decision (owner-selected via the Phase-2 plan question):** **Hybrid.** Fetch returning production into the snapshot now (new `returning_production` field-group); the prior code prefers preseason **SP+ automatically** when present (its `rating` is a point value → Elo offset), else a **bounded** returning-production continuity nudge (±`prior_rp_max_elo`=40 Elo, ~±2 pts; NOT a talent ranking), else honest **flat** baseline with max uncertainty. Robust to SP+ staying empty at freeze; auto-activates when CFBD posts either source — **data, not code**. Per-team `prior_source` recorded in the ratings export.
**Implication verified at build time:** since BOTH sources are empty now, the current-date prior is flat-for-all with `rating_uncertainty=1.0` — correct honest state, not a defect.

---

## D11 — `rating_uncertainty` + early-season cap (Phase 2a) — **RATIFIED (owner, 2026-07-03)**
**Date:** 2026-07-03
**Context:** SPEC §6.2 requires an early-season mode (weeks 1–3): widen bands, more NO_BET, cap rating-derived signal influence, expose `rating_uncertainty` in every output.
**Decision:** Per-matchup `rating_uncertainty` ∈ `[uncertainty_floor, 1]` decays from 1.0 (0 games, pure prior) to `uncertainty_floor=0.2` by `uncertainty_games_full=5` games, inflated ×`rp_prior_uncertainty_penalty=1.15` for any **non-SP+** prior (returning-production OR flat — both are weaker seeds than SP+, so both are at least as uncertain); the matchup takes the max (less-established side dominates). The pricer scales the **rating differential** (NOT home-field or schedule — those are structural) by `rating_signal_weight = rating_signal_floor + (1−floor)·(1−uncertainty)`, `rating_signal_floor=0.4` (floor, not 0, so a strong SP+ prior still shows through preseason; the ENGINE widens bands/NO_BETs on high uncertainty). Constants proposed in `CALIBRATION_LOG.md`, owner-ratified, frozen at the tag.

---

## D12 — spread → win-probability σ (Phase 2) — **RATIFIED (owner, 2026-07-03)**
**Date:** 2026-07-03
**Context:** §6.5 requires a documented spread→win-prob conversion (in `docs/SCHEMA.md`) for projected win totals. 13.5 is the NFL margin SD; CFB's is wider.
**Decision:** `P(win)=Φ(margin/σ)`, **σ (`margin_sigma`) = 16.0**. Measured from CFB: the 2025 P4 archive market-residual SD (`actual_margin + vegas_spread`, mean≈0) is 14.1, lifted for our noisier-than-market model + the wider full-slate margins. Using 2025 margins is **Data-Recency-compliant** (a sport-level statistical constant, not team-quality data — noted in CALIBRATION_LOG). Proposed with evidence; owner-ratified; used by the 2b projections.

---

## D13 — Phase-2 split + ratings/projection storage posture — **CONFIRMED (owner)**
**Date:** 2026-07-03
**Context:** SPEC §6.5/§6.6 mark projections + belief-drift + `cfb project` as cut-first/freeze-exempt (§15); ratings + pricer + hypothetical are freeze-disciplined.
**Decision (owner-selected via the Phase-2 plan question):** **Split 2a / 2b** (mirrors 1a/1b/1c). 2a (this work): ratings + pricer + hypothetical + model-vs-market logging + `data/ratings/`. 2b: projections + drift + `cfb project` + `data/projections/`. **Storage:** `data/ratings/2026_week_NN.json` and `data/projections/2026_week_NN.json` are **committed (not gitignored)**; the immutable-history hook is extended to `data/ratings/`. Ratings are a **derived export** — the prediction path recomputes ratings from the snapshot (memoized by `snapshot_id`) and never reads `data/ratings/`, preserving the 1b reproducibility contract.
