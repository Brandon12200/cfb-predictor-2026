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

---

## D14 — Phase-2b projection scope, freeze-exempt home, market-total deferral (approved via plan)
**Date:** 2026-07-03
**Context:** Phase 2b (SPEC §6.5) is freeze-exempt/cut-first. Three implementation choices needed recording; none are calibration (2b reuses the ratified D12 σ=16, adds no constants).
**Decision (approved by ratifying the Phase-2b plan):**
- **Freeze-exempt home:** the projection roll-up lives in a **new `analytics/` package** (`analytics/projections.py`), NOT frozen `engine/` — 2b must stay editable after `v2026-frozen`. It calls the frozen `engine.matchup_pricer`/`engine.power_ratings` but is not part of them. Phase 4 expands `analytics/` (CLV, calibration, reports).
- **Scope:** project **all FBS teams** (scoped via `data.team_registry.get_fbs_canonical_names()` — no hardcoded names), per §6.5's "every remaining game" + the season-long time-lapse purpose. Opponents absent from ratings (incl. FCS) price from the flat baseline prior via the pricer fallback; they are not themselves projected. Counting convention documented in `SCHEMA.md` §6.7: all scheduled games incl. FCS, regular season only.
- **Market win total (§6.5) deferred:** no futures data source in 2026 core (Odds free tier has no season win totals) → recorded **not-available** (honest-missing), never fabricated. Revisit if a source is added.
- **Reproducibility/immutability:** projections are a derived export (never on the prediction path); `data/projections/` is committed and the immutable-history hook is extended to it (same posture as `data/ratings/`, D13). A per-week `meta.schema_version` lets the season-spanning drift/history reader tolerate schema evolution (2b is freeze-exempt, so a later week's file may add a field).
**Implication verified:** preseason (SP+/RP empty → flat priors), projections are near-uniform (~6 wins, variation from schedule length only) — the honest "no signal yet" state; the drift view earns value from ~weeks 4–6.

---

## D15 — Decomposed-and-shared pricer + circularity prohibition (Phase 3a) — **CONFIRMED (owner)**
**Date:** 2026-07-03
**Context:** Phase 2's pricer applies schedule intel (bye/short-week/travel/altitude) to the model spread; Phase 3 adds physical FACTORS that adjust the Vegas line for the contrarian bet. The pricer is diagnostic-only in 2026 (factors alone drive recommendations), so there is no double-count in the bet. The real trap is SPEC §6/§7's **model-vs-market gap as a confirming signal** (the L2 fix): if the model spread contains the same bye/travel adjustment, using the gap to confirm a schedule factor is **circular** — confirming a signal with itself.
**Decision (owner, via the Phase-3 plan):**
1. **Decompose, don't merge or delete.** `engine/matchup_pricer.price()` returns a decomposed spread: `base` (Elo diff + HFA — team quality only), `schedule_adjustment` (physical), `total = base + schedule_adjustment` (test-pinned: `base_margin + schedule_component == home_margin`).
2. **Consumers pick the honest lane:** hypothetical mode → `total` (travel must show); the model-vs-market diagnostic → the **`base` gap** (`base_spread − vegas`; the total gap is logged too, LABELED); any Phase-3 **confirming-signal rule → the `base` gap ONLY, never `total`**.
3. **Explicit circularity prohibition (written rule + test):** *a schedule/physical factor must not be confirmed by a gap that contains the same schedule signal.* The `base` gap excludes schedule → satisfies it by construction. The engine exposes `model_vs_market_gap` = **base** gap (the only gap a confirming rule may use) + `model_vs_market_gap_total` (labeled, diagnostic-only). A test proves the two differ when schedule fires and that the confirming lane reads base.
4. **One source of truth for schedule coefficients:** Phase-3's calibrated schedule coefficients **supersede** the 2a `ScheduleAdjustmentConfig` (as CALIBRATION_LOG promised); the pricer's `schedule_adjustment` consumes those same values — **no parallel copy**. Both lanes freeze together at the tag. *(Sequencing: the decomposition landed in 3a while 2a is unfrozen; the coefficient relocation to the factor-owned source lands in 3b with the physical factor that becomes the second consumer — the single meaningful move point, avoiding a throwaway 3a rename.)*

---

## D16 — Phase-3 "2025 dry-run" vehicle = the 2026 snapshot (owner, via plan)
**Date:** 2026-07-03
**Context:** SPEC §7 acceptance wants a "full-slate dry run over an archived 2025 week," but no 2025 input snapshots exist and Odds-API historical lines are paid (10×); building a faithful 2025 snapshot means year-parameterizing the builder + CFBD `/lines`.
**Decision:** Satisfy the dry-run by running the new schema-v2 engine over the **existing committed 2026 week-1 snapshot** (proves sensible schema-v2 output over a real slate). Calibration **evidence** comes from the 300-game 2025 archive via `analytics/calibration_evidence.py`. The deviation from the "2025 week" literal is a documented, deliberate choice (recorded in `CODE_AUDIT.md`) — the archive still carries the 2025 weight; the dry-run only needs a realistic slate.

---

## D17 — 2025 baseline regraded; the 57% headline was a measurement artifact — **RATIFIED (owner, 2026-07-03)**
**Date:** 2026-07-03
**Context:** The 2025 scorecard reported **57.0% ATS / +8.82% ROI** (SPEC §2, README, `scripts/calculate_accuracy.py` + `calculate_roi.py`). The Phase-3a calibration harness independently graded the same 300-game archive at **46.6% ATS**, and the two numbers sat unreconciled — including, briefly, both in the README's front door.
**Investigation:** graded the archive under both conventions side by side (both use the canonical cover rule `home covers S iff (home_score−away_score)+S>0`):

| bet side \ graded against | model's contrarian spread | Vegas line |
|---|---|---|
| **always home** | **57.0%** (171/300) | 54.4% (160/294) |
| **model's pick side** | 45.0% (135/300) | **46.6%** (137/294) |

**Finding:** the 57% comes from the win condition "the **home** team covered the model's **own** contrarian spread" — it always bets home and grades against the model's own number, not the market. That is a home-rating **bias diagnostic, not a placeable bet**. Graded as the actual contrarian strategy (the model's `edge_direction` side vs the Vegas line), 2025 was **46.6% ATS / −11.0% ROI** (294 graded bets, 6 pushes; 95% CI ~41–52%) — below the ~52.4% break-even. No subset rescues it: contrarian-edge-only games are 46.5%, and the contrarian picks (46.5%) matched the consensus games (46.7%), i.e. the contrarian adjustment added no value.
**Decision (owner-ratified 2026-07-03):**
- The honest 2025 baseline is **46.6% ATS / −11.0% ROI**. SPEC §2 and the README are corrected to lead with it.
- Each L1–L4 lesson is restated in SPEC §2 with its post-regrade status: **L4 strengthened**, **L3 partial** (compressed but real ranking signal), **L2 not isolable**, **L1 unverified** — physical weights rest on documented reasoning, not 2025 authority, and **3b calibration entries citing 2025 performance must use the post-regrade evidence**.
- The buggy scripts are **relabeled** in a follow-up PR (not silently fixed): keep the always-home diagnostic under an honest name (`home_vs_model_spread_diagnostic`), and make the default "ATS" path measure the placeable strategy. Deleting the old convention would orphan the explanation of where 57% came from.
**Why it's in the log:** the project's thesis is "can it beat the line without fooling itself." Here its own measurement infrastructure regraded its headline claim and found it didn't hold; the correction is published, with commits to prove it. The model is worse than yesterday's story and the project is stronger for proving it — and this entry is the audit-trail artifact the whole system exists to produce.

---

## D18 — Physical factor scope: sandwich & consecutive-road are contrarian-only (Phase 3b) — **RATIFIED (owner, 2026-07-03)**
**Date:** 2026-07-03
**Context:** Phase 3b makes the schedule-intelligence coefficients a single source (D15) consumed by both the matchup pricer's model-spread schedule adjustment and the six contrarian physical factors. Two of the six sub-signals — `sandwich` (a ranked opponent in an adjacent week) and `consecutive_road` (cumulative road wear) — are not straightforwardly "how good is this team in this game."
**Decision:** the pricer's model spread consumes only the **fatigue/location** subset (`bye`, `short_week`, `travel`/tz, `altitude`). **`sandwich` and `consecutive_road` are contrarian-only** — they are physical *factors* that adjust the contrarian line but do **not** feed the team-quality model spread. Rationale (owner): a letdown/look-ahead spot is a **market-mispricing hypothesis, not a team-quality fact**; the model spread should price how good a team is, and bet the motivational edge separately. `physical_adjustments()` (the pricer's call) deliberately excludes them; the two factors read the shared coefficients directly.
**Also ratified in the same batch (see CALIBRATION_LOG Phase 3b):** `travel_cap` trimmed 2.0 → 1.5 (0.6 HFA, humility on an unmeasured extreme); physical reweight to 52% additive share framed as **demotion of measured non-signal** (situational noise L2 + contrarian-adds-nothing D17), not promotion on 2025 authority; `MarketSentiment` 35% → 6% additive; the base-calculator activation fix (raw 0.0 → not activated) logged as behavior-changing; `StyleMismatch`/`MarketSentiment` re-categorized `matchup`/`market` so the contribution-budget ratio measures physical vs the motivational factors; budget bounds (single-factor < 15%, physical:situational ≥ 2:1) ratified as a drift **tripwire**.

---

## D19 — MarketSentiment: multiplicative on the edge, dormant until real data, no fabrication (Bug #7 fix) — **RATIFIED (owner, 2026-07-04)**
**Date:** 2026-07-04
**Context:** The 3b review surfaced that `MarketSentimentCalculator` never set `is_multiplicative`; investigation found three coupled defects (all pre-existing) that together were the mechanical root cause of the D17 artifact (see the D17 addendum).
**Decision:**
- **Multiplicative, used directly, on the edge only.** `is_multiplicative = True`; the value is the multiplier (no re-centering); it scales **`total_adjustment` only** — `contrarian = vegas + total_adjustment · m`, never `(vegas + total_adjustment) · m`. Sentiment may amplify/dampen the model's *disagreement* with the market; it must never rescale the market's own number.
- **MODIFIER factors are weightless by design.** `self.weight` is inert for modifiers (`get_dynamic_weight` returns 1.0); a modifier is calibrated by its **range**, not a weight, and is excluded from additive-budget accounting.
- **No fabrication (#4).** The team-name MD5 hash and the spread/week "characteristic" heuristics — signal manufactured from nothing — are removed.
- **Dormant until real data.** With line-movement history deferred to slice 1.5 (D6), the factor returns neutral **1.0 (no effect)** whenever no real movement exists — the honest state of a factor whose inputs haven't arrived.
- **Range `[0.5, 1.5] → [0.85, 1.15]`** (`reasoned`): the ratified cap for when slice 1.5 brings real movement; a first-season, fabrication-history factor gets a tight cap, widened in 2027 with attribution.
**Evidence:** on the 2026 wk1 dry-run slate the fix removes a **+0.97-pt mean shift on 10/10 games**; edges collapse from ~1.0-everywhere to 0–0.15 (0 where no factor fires). Rerun is intentionally not bit-identical vs the old model; determinism within the corrected model holds.

## D17 addendum — root cause of the 2025 artifact identified (Bug #7) — **RATIFIED (owner, 2026-07-04)**
**Date:** 2026-07-04
D17 established that the 57.0% headline was a measurement artifact. This addendum records the **mechanical cause**, found while fixing the MarketSentiment wiring (D19).
**The 2025 "contrarian" model was a near-constant +1.0 shove, not a set of factor signals.** Across all 300 archive predictions, `contrarian_spread − vegas_spread` has **mean 0.986, median exactly 1.000, stdev 0.066**, and **300/300** games land within ±0.5 of +1.0. The constant is MarketSentiment's additive-vs-multiplicative bug (a 1.0-centered multiplier summed as points); the tiny stdev-0.066 wiggle around it was the now-removed team-name hash + spread/week heuristics. The factor system was otherwise effectively silent.
**It reconciles the D17 diagnostic table exactly** (always-home, canonical cover rule):

| always-home graded against | result |
|---|---|
| the model's contrarian spread | **57.0%** (171-129) |
| contrarian **minus the +1 phantom** | **54.2%** (161-136) |
| the Vegas line directly | **54.4%** (160-134) |

Removing the +1 collapses 57.0% onto the independent Vegas number — **the entire 57-vs-54.4 gap in the D17 table *is* the phantom.**
**edge_direction accounting.** All 300 signed edges are +1.0 (home-ward in spread space), yet the stored `edge_direction` splits 120 home / 180 away. That split is **100% determined by the sign of each game's Vegas line** (home-favored → "away" 180×; away-favored → "home" 113×; 7 boundary cases), i.e. the constant phantom mechanically bets the underdog every game, refracted through which side the line favored. It was never a directional signal.
**L3/L4 restatement.** The 2025 confidence and edge distributions L3/L4 rested on were phantom-contaminated: the "155-ish sub-1pt / rest 1–2pt" edge bucket (**0 games above 2pt**) was the constant, not hundreds of real marginal disagreements. Their *directives survive as design principles* — L4: don't fire on marginal edges; L3: confidence should rank ATS — but their **"2025 evidence" is now understood as measurement of the bug**, not of the market. Per the 3c constraint, the harness's confidence→ATS and edge→ATS tables may NOT be cited as measured evidence.
**Why it's in the log:** D17 said the headline was an artifact; this says *why*, and proves it to the decimal. Bug #7 — the most explanatory finding yet: the 2025 model wasn't a weak contrarian edge, it was one wiring bug applied 300 times.
