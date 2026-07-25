# CFB Contrarian Predictor — 2026 Season Rebuild Specification

**Audience:** project owner and implementers.
**Repo:** `Brandon12200/cfb-predictor-2026`
**Status:** Approved for implementation — all owner decisions resolved (§16). Implement in the phase order below. Each phase has executable acceptance criteria (`make verify-phase-N`), and a phase is complete only when its verification passes.

---

## 1. Mission

Evolve the 2025 fixed-weight contrarian spread model into a 2026 system that is:

1. **Better measured** — closing line value (CLV), calibration, and per-factor attribution, not just raw ATS%.
2. **Fully automated** — a zero-touch weekly pipeline that fetches the slate, generates predictions, commits them to git *before* kickoff, grades results after games, and regenerates the performance report.
3. **More capable** — a power-rating layer that can price *any* matchup, including hypothetical games, plus an expanded physical/scheduling factor set.
4. **Still credible** — the frozen-model, git-audit-trail identity is the project's brand. Nothing may compromise it.

Dual purpose: genuine betting performance research **and** a portfolio-quality engineering showcase. When those goals conflict, prefer the choice that keeps the system explainable and auditable.

## 2. 2025 Baseline (context for all decisions)

Forward-tested, frozen 2025-08-25, weeks 1–14, 300 games. **The original scorecard reported 57.0% ATS / +8.82% ROI, but that number was a measurement artifact** — `scripts/calculate_accuracy.py`/`calculate_roi.py` graded "did the home team cover the model's *own* number," always betting home against the model's own spread rather than the market. That is a home-rating **bias diagnostic, not a placeable bet.** Re-graded as the actual strategy (the model's favored side vs the Vegas line) with this repo's own harness (`analytics/calibration_evidence.py`), the honest 2025 result is **46.6% ATS / −11.0% ROI over 294 graded bets (95% CI ~41–52%)** — below the ~52.4% break-even. **The 2025 model did not beat the market.** Full side-by-side regrade: `docs/DECISIONS.md` D17.

The four lessons below were drawn partly from the 57%-world, so each is restated with its status under honest grading. They remain **binding requirements** for 2026:

- **L1 — Physical > motivational (UNVERIFIED by the archive).** The archive stores only category-level factor contributions, and scheduling fatigue sits *inside* the `situational_context` category, so physical-factor attribution cannot be isolated. "Physical was strongest" was a season-level impression, not an archive-derived result. → 2026 still shifts weight toward physical factors, but on **documented reasoning** (rest/travel effects, the priced home-field scale), **not** on 2025 evidence; Phase-4 attribution measures it for the first time in 2026. **3b weight entries may not cite "it worked in 2025."**
- **L2 — Situational factors were noisy (plausible, not isolable).** Cannot be separated from the physical signal in the archive's category-level data; the whole model was below break-even, consistent with situational noise but not singling it out. → Raising activation thresholds and requiring a confirming factor is prudent regardless.
- **L3 — Confidence had ranking signal, but too compressed to act on (partially survives).** Confidence was nearly constant (range 63–71). Split at the median, higher-confidence bets did outperform (50.3% vs 42.3% ATS) — a real but soft ranking signal (overlapping intervals on ~150-game halves) — yet even the top half stayed below break-even. The ordering lesson holds; the original "high-confidence predictions won" does not. → Make confidence tiers first-class **with real separation** (Phase 3c), calibrated honestly.
- **L4 — Too many marginal bets, and the marginal edge was worthless (strengthened).** The contrarian picks (46.5% ATS) did no better than the consensus games (46.7%) — the contrarian adjustment added no measurable value in 2025, on tiny edges, below break-even. → `NO_BET` as a first-class output matters more than the 57%-world implied.

### Data Recency Principle (binding)

Roster turnover (transfer portal, NIL) makes prior-season **team performance data** unreliable for judging current teams. Therefore:

- **Team quality inputs use current (2026) season data only.** No prior-season team stats (EPA, records, point differentials) may feed a 2026 prediction.
- **Prior-season data is permitted for exactly two purposes:** (a) *market-behavior calibration* — the 2025 prediction/result archive (14 weeks in `data/predictions/` and `data/results/`) tunes factor weights and thresholds, because it measures how the market prices situations, not how teams perform; and (b) *roster-continuity-aware preseason priors* (see Phase 2), which explicitly discount last season by returning production rather than assuming continuity.
- **Coach-level history (H2H records, experience) keeps multi-season lookback** — a deliberate, documented exception to this principle, decided by the owner (§16.7): coach identity is stable across roster churn.
- Structural/physical factors (rest, travel, bye weeks, altitude) require no team history at all and are therefore the most trustworthy signals in early season.

## 3. Model Philosophy: Calibrated Freeze

**Decision:** Neither pure re-freeze of 2025 weights nor a learned/ML model.

1. **Recalibration window (now → freeze date).** Use the 300-game 2025 prediction/result archive — a dataset about market mispricing patterns, not team quality, and therefore exempt from the Data Recency Principle — to adjust factor weights, activation thresholds, and confidence mappings. Every change must be recorded in `docs/CALIBRATION_LOG.md` with: the 2025 evidence motivating it, the old value, the new value, and the expected effect. Changes are justified by evidence and reasoning, not by optimizing backtest ATS% (no grid searches over 2025 outcomes — that is the overfitting this project exists to avoid).
   - **⚠ Bug #7 constraint (D17 addendum / D19), binding on 3c and after:** the archive's **confidence→ATS and edge→ATS tables are phantom-contaminated** — the 2025 model's entire output was a near-constant +1.0 shove (a MarketSentiment wiring bug), so its confidence and edge distributions measured the bug, not the market. They may **NOT** be cited as measured evidence. In the 3c batch, every entry is evidence-class **`reasoned`** unless it rests on **model-independent market data** (e.g. the price-derived HFA/σ), and the monotonic-tier gate is a **structural sanity check on the NEW model's dry-run output, not a 2025-evidence gate.** (Market-behaviour constants like `hfa_elo`/`margin_sigma`, derived from lines/outcomes rather than the model's own predictions, remain admissible.)
   - **⚠ Derived-artifact invariant (binding):** any calibration change that alters the pricer (`engine/matchup_pricer.py` or the coefficients/weights it consumes) must **regenerate the committed `data/projections/` artifacts** in the same change, because `make verify-phase-2` byte-checks them against a fresh recompute. Omitting this broke `verify-phase-2` on `main` when the 3b `travel_cap` change wasn't propagated. (`data/ratings/` is likewise a committed derived export with the same regenerate-on-pricer-change obligation.)
2. **Freeze date: tag `v2026-frozen` by 2026-08-24** — Week 0 (2026-08-29) is in scope per §16.2, so the freeze must precede the first prediction run (~Tue 2026-08-25); the owner's stated 2026-08-29 date is the absolute outer bound. After this date, no changes to weights, thresholds, factor logic, or confidence math for the entire season. Bug fixes that alter outputs require a documented exception entry and a new tag.
3. **Shadow model (stretch, Phase 6).** A learned model may run alongside for comparison but never drives a recommendation. Its predictions are logged and graded identically. `tests/test_shadow_mode.py` already exists — audit and build on it if useful.

## 4. Phase 0 — Repo Hygiene & Audit (do first)

Before any feature work:

1. **Delete the stray 2.8 MB binary file named `venv`** in the repo root and replace `.gitignore` with the corrected version supplied by the owner. Critical: the old `.gitignore` ends with `*.md` / `!README.md`, which silently ignores ALL markdown except the README — this would exclude `docs/`, `reports/`, and the calibration log, breaking the documentation and audit-trail plan. The old `venv/` rule also only matched directories, which is how the stray `venv` FILE got committed. Verify after replacement: `git check-ignore -v docs/SPEC.md docs/CALIBRATION_LOG.md reports/x.md` returns nothing.
2. **Fix the README setup section** — it points to `CFB-Market-Edge-Platform` instead of this repo.
3. **Preserve the 2025 audit trail.** The 2026 repo has a single squashed initial commit, but the README's credibility claim rests on git history. The 2025 repo is private and will not be linked (§16.5), so: import the 2025 prediction/result JSONs into `data/archive/2025/` with a README note explaining provenance. The 2026 pipeline (Phase 5) makes future audit trails automatic.
4. **Fix the silent week-default bug.** `main.py:_get_current_week()` contains leftover test code (`return 1  # Default to week 1`), so omitting `--week` silently analyzes games with week-1 context and produces different results than the same command run with the correct week. Until CLI v2 (Phase 4.5) lands: derive the week from the actual date via the season calendar, print the week being used on every run, and hard-fail if it cannot be determined. Omitted-week and explicit-correct-week runs must produce identical output; add a regression test.
5. **Known bug — hardcoded, stale, duplicated conference lists.** P4 conference membership is hardcoded in `main.py` in at least three places, and the ACC list has 14 teams — missing Stanford, Cal, and SMU (ACC members since 2024). Because the P4 slate filter requires both teams to be listed, games involving those teams were silently dropped during the 2025 season. Phase 1's team registry (§5.5) is the real fix; in Phase 0, delete the duplicated dicts and route all conference lookups through one function so there is a single point to replace.
6. **Dead-code audit.** `engine/` contains modules the README does not document: `adaptive_calibrator.py`, `dynamic_weighter.py`, `market_efficiency_detector.py`, `game_filter.py`, `factor_validator.py`. `utils/` contains `bet_evaluator.py`, `monitoring.py`, `health_check.py`, `performance_analyzer.py`. For each: determine whether it is wired into `main.py`/the engine, tested, both, or neither. Produce `docs/CODE_AUDIT.md` listing keep / refactor / delete decisions. Delete confidently; git remembers.
7. **Decompose `main.py` (~54 KB).** Extract into a `cli/` package (argument parsing, commands) and keep `main.py` as a thin entry point. No behavior changes in this phase.
8. **Packaging & tooling.** Add `pyproject.toml`, pin dependencies, add `ruff` + formatting config, and a `Makefile` or task runner with `make test`, `make predict`, `make grade`, `make report`.

**Acceptance:** repo installs cleanly from scratch; all existing tests pass; `docs/CODE_AUDIT.md` exists; no binary junk tracked; README accurate.

## 5. Phase 1 — Data Layer v2

### 5.1 The problem being fixed

The 2025 data layer has invisible data lineage. `data/data_manager.py` wraps calls in a `@safe_api_call` decorator that silently swallows exceptions and substitutes neutral placeholder values; provenance is a coarse `data_sources` string list (appended inaccurately in places); and data is fetched live during prediction, so identical commands can yield different results depending on transient API behavior. The owner cannot tell whether a given number came from CFBD, ESPN, or a made-up neutral value. Phase 1's primary job is eliminating this.

### 5.2 Data Architecture v2 (snapshot-first, provenance-everywhere)

Four strictly separated layers:

1. **Clients** (`data/clients/`): one module per source (CFBD v2, ESPN, Odds API, availability reports). Dumb and honest — fetch, parse to source-native structures, raise on failure. No fallback logic, no neutral values, no cross-source knowledge.
2. **Normalizer** (`data/normalize/`): converts each source's native structures into one canonical, typed schema (dataclasses/pydantic; documented in `docs/SCHEMA.md`). Team names resolve through the existing normalizer. After this layer, the rest of the system never sees source-specific shapes.
3. **Snapshot builder** (`data/snapshot/`): the ONLY place fallback policy lives. For each week it orchestrates fetches (respecting API budgets and cache), applies explicit fallback rules (CFBD → ESPN → declared-missing), and writes a single versioned bundle: `data/snapshots/2026_week_NN/` containing the canonical data plus a **provenance manifest** recording, per field group per team/game: source used, fetch timestamp, cache hit/miss, fallback reason if any, and `missing` where nothing was available. **Neutral value fabrication is abolished** — absence is recorded as absence, and downstream consumers decide how to handle it.
4. **Engine** (pure): factor calculators and the rating layer read ONLY snapshots. The engine has zero network access — enforced by a test that runs a full prediction with networking disabled. Prediction outputs embed the snapshot ID they were computed from, making every prediction exactly reproducible (`cfb predict rerun`).

Consequences that fall out for free: offline reruns, bit-identical reproducibility, honest `data_quality` (now an itemized report, not a single percentage), and a `NO_BET`/confidence-penalty path driven by *actual* missing-critical-field facts. Delete `safe_api_call` and the `_get_neutral_*` methods entirely.

### 5.3 Inspection tooling

`cfb data inspect --week N [--game "AWAY @ HOME"]` renders the provenance manifest: which fields came from CFBD vs ESPN vs missing, fetch times, cache status. `cfb status` reports per-source health and remaining API quota. Weekly pipeline logs a one-line provenance summary per game (e.g., `OSU@MICH: cfbd 94%, espn 4%, missing 2% [travel_distance]`).

### 5.4 Content additions:

1. **Migrate to CFBD API v2** (v1 is shut down; free tier ~1,000 calls/month, paid tiers higher — see Appendix A) and update rate-limit config accordingly. Then pull **advanced team metrics:** EPA/play (offense & defense), success rate, explosiveness, havoc rate, SP+ (or equivalent public rating), returning production, and pace (plays/game, seconds/play). Cache season-to-date snapshots weekly to `data/cache/` so reruns are deterministic and API budgets are respected.
2. **Schedule intelligence dataset.** For every team-week, precompute: days of rest, bye-week status (coming off bye / opponent off bye), short week (games on ≤6 days rest, incl. weekday games), travel distance (great-circle between campus/stadium coordinates), time zones crossed and direction, altitude of venue, consecutive road games count, and sandwich-spot flags (ranked opponent last week or next week). Store as a season-long table built once schedules are known and refreshed weekly; this is the substrate for Phase 3 factors and must also be computable for hypothetical matchups.
3. **Closing line capture.** The pipeline must record the spread at prediction time AND the closing spread (final pre-kickoff fetch) for every predicted game. This is required for CLV in Phase 4. Budget: the config caps The Odds API at 83 calls/day — design the fetch schedule (e.g., one slate fetch at prediction time, one near kickoff windows) to fit within it, and make the budget configurable.
4. **Line movement history (best effort).** Where the API allows, snapshot lines at fixed times (e.g., Tue/Thu/Sat-morning) to feed the market-sentiment factor with real movement rather than a single observation.
5. **Availability reports (new).** Ingest official Power Four player-availability reports per Appendix A — new public data since v1 and the highest-value injury signal available.
6. **Determinism & degradation.** Keep the existing "degraded data lowers confidence" behavior; extend `data_quality` to itemize which sources were live vs fallback vs neutral-filled.

### 5.5 Canonical Team Registry (fixes the missing-teams bug)

Conference membership is season-specific data, not code. Build a **team registry** per season, sourced from CFBD's teams/conferences endpoints, cached in the snapshot with provenance like everything else:

1. Registry contents per team: canonical name, CFBD id, conference (for THIS season), division/FBS status, aliases observed across sources (Odds API name, ESPN name), venue reference. Slate-scope filters (P4 + major independents, or whatever `season.yaml` selects) query the registry — no team or conference name may ever be hardcoded in application code (enforce with a lint/grep check in CI).
2. **Season-start validation:** on first snapshot of the season, assert expected membership counts (2026: SEC 16, Big Ten 18, Big 12 16, ACC 17 incl. Stanford/Cal/SMU, plus tracked independents — Notre Dame at minimum; verify the independent list at implementation time since realignment is ongoing). Mismatch = hard failure with a clear message, not a silent filter.
3. **Weekly slate reconciliation:** every pipeline run cross-references the Odds API game list against the CFBD schedule for the week. Any game present in one source but not the other, or dropped by scope filtering, is logged explicitly in the weekly report (`dropped: X @ Y — reason`). Silent game loss becomes structurally impossible: a game can be excluded, but never invisibly.
4. **Name-resolution coverage test:** a fixture test resolves every FBS team's name variants across all three sources through the normalizer; any unmapped alias fails CI. When the pipeline meets an unknown team name at runtime, it raises a visible warning and lists the game as `unresolved` rather than skipping it.

**Acceptance:** `cfb data snapshot --week N` produces a complete versioned bundle with a provenance manifest covering 100% of fields (source, timestamp, or `missing`); the engine passes a no-network test; two runs of `cfb predict rerun` on the same snapshot are bit-identical; `safe_api_call` and neutral-value fabrication no longer exist in the codebase; unit tests cover schedule-intelligence calculations (travel distance, rest days, time zones) with known fixtures; the team registry validates 2026 membership counts and the name-coverage test passes for all FBS teams; grep-based CI check confirms no hardcoded team/conference lists remain.

## 6. Phase 2 — Power Rating Layer & Hypothetical Matchup Mode

The 2025 system could only adjust an existing Vegas line. 2026 adds an independent rating so the system can price any matchup.

1. **Team power ratings (current-season only, per the Data Recency Principle).** Ratings are built from 2026 games as they occur — an in-house Elo (owner decision §16.4) with margin-of-victory dampening, updated weekly by the pipeline, stored as JSON per week. They do **not** seed from 2025 results. Preseason priors, needed only so week 1–3 output isn't garbage, must be roster-continuity-aware: use public preseason ratings that already model transfers/returning production/recruiting (e.g., preseason SP+), or a simple in-house prior from returning-production %, and attach high uncertainty that decays as real 2026 games accumulate. Must be explainable and reproducible; no black boxes.
2. **Early-season mode (weeks 1–3).** While ratings are uncertain: widen confidence bands, emit more `NO_BET`s, cap the influence of rating-derived signals, and lean on physical/scheduling factors — which need no team history and were 2025's strongest signal anyway. The engine must expose a `rating_uncertainty` value in every output during this window.
3. **Matchup pricer.** `price(home, away, venue, date, context)` → model spread, built from rating differential + home-field value + Phase 1 schedule-intelligence adjustments (rest, travel, altitude...). Works for real games and hypotheticals identically.
4. **Hypothetical mode (CLI):**
   `python main.py hypothetical --home "Ohio State" --away "Texas" [--neutral-site] [--venue "..."] [--date YYYY-MM-DD] [--show-factors]`
   Output mirrors the real-game format: model spread, factor breakdown, confidence, caveats (e.g., early-season rating uncertainty). No Vegas line required.
5. **Season projection & belief-drift tracking.** Each week, after ratings update, price every remaining game of the season with the matchup pricer and roll up per-team projected win totals (sum of per-game win probabilities via a standard spread→win-prob conversion; document the conversion in `docs/SCHEMA.md`). Write `data/projections/2026_week_NN.json` (per team: projected wins, per-game model spreads/win probs, rating, rating_uncertainty). This is pure computation over the existing snapshot — zero additional API cost. The weekly report gains a drift section: biggest risers/fallers in projected wins, teams whose trajectory diverged most from preseason priors, and (where futures data is available) model win total vs market win total. Purpose: (a) diagnostic — measures how fast priors converge and where the model misjudged; (b) showcase — season-long belief time-lapse charts; (c) signal research — logged cases where the model's number moved before the market's. Projections are explicitly labeled experimental and never drive bet recommendations in 2026.
6. **Model-vs-market signal.** For real games, the gap between the power-rating spread and the Vegas spread becomes an additional logged diagnostic (and a candidate confirming signal for factor activation per L2). It does **not** replace the contrarian factor adjustment in 2026 — it runs alongside and is evaluated at season's end.

**Acceptance:** hypothetical command works for any two FBS teams; for real games, model spread and Vegas spread are both logged; rating update logic has tests with synthetic seasons; weekly projection files exist for every completed week and a `cfb project [--team X]` command renders current projected win totals and week-over-week drift.

## 7. Phase 3 — Factor System v2 (Calibrated Freeze applied)

Keep the architecture: factors inherit `BaseFactorCalculator` with `calculate()`, `calculate_with_confidence()`, `get_output_range()`, registered via `factor_registry.py`, with activation thresholds and the primary/secondary/modifier weight tiers.

Changes:

1. **Reweight per L1.** Shift weight toward physical/structural factors (scheduling fatigue and the new factors below). Document in `CALIBRATION_LOG.md`.
2. **New physical factors** (powered by the Phase 1 schedule-intelligence table): bye-week advantage, short-week penalty, travel/time-zone burden (upgrade of existing fatigue factor), altitude, consecutive-road-games wear, sandwich spot. Some may fold into an upgraded `scheduling_fatigue.py` rather than new files — implementer's judgment, but each sub-signal must appear separately in `factor_breakdown`.
3. **Raise situational thresholds per L2.** Revenge, lookahead, desperation: higher activation thresholds and/or require a confirming factor (e.g., situational signal only fires when a physical factor or the model-vs-market gap agrees in direction).
4. **`NO_BET` per L4.** Add a first-class prediction type emitted when edge is below a floor, confidence below a floor, or variance detection flags factor disagreement. Purely threshold-driven (§16.3): no weekly volume target exists, and thresholds must never be adjusted to hit one. `NO_BET` games are still logged and graded (what would have happened) so selectivity itself can be evaluated.
5. **Confidence calculator v2 per L3.** Map confidence to explicit tiers (e.g., A/B/C) with defined score ranges; tiers appear in output and reports. Tier boundaries are set before freeze. **⚠ Per the §3 Bug #7 constraint, NOT calibrated against the archive's confidence→ATS table (phantom-contaminated).** Boundaries are `reasoned`; the monotonic-ATS%-by-tier property is a **structural sanity check on the NEW model's dry-run output**, not a 2025-evidence gate. (This supersedes any earlier "calibrate tier boundaries using 2025 data" reading.)
6. **Prediction schema v2.** Extend the existing JSON with: `schema_version`, `model_version` (git tag), `closing_spread`, `clv` (filled at grading), `power_rating_spread`, `no_bet` flag + reason, `confidence_tier`, per-sub-signal `factor_breakdown`, and prediction-time line snapshot metadata. Maintain a documented schema in `docs/SCHEMA.md`; keep a converter for 2025-format archives.

**Acceptance:** all factors have unit tests incl. threshold-boundary cases; a full-slate dry run over an archived 2025 week reproduces sensible output under the new schema; `CALIBRATION_LOG.md` covers every changed number.

## 8. Phase 4 — Measurement & Analytics v2

> **⚠ Freeze-prep + handoff pointers (read before starting Phase 4).** Phase 3 is complete and
> **frozen-form**; Phase 4 is **measurement built to conventions already frozen**, with **no calibration
> batches of its own**. Build to the ratified **schema v2** in `docs/SCHEMA.md`: CLV (item 1) uses the
> ratified sign convention (**positive = our number beat the close**; home ⇒ `vegas−close`, away ⇒
> `close−vegas`) and fills the `closing_spread`/`clv`/`graded_at` fields per the documented null-vs-push
> semantics; calibration/attribution (items 2/4) key off the ratified **A/B/C tiers** (tier C is a
> diagnostic grade, never a live bet). Attribution (item 4) must answer the **open `reasoned` CALIBRATION_LOG
> questions** (per-sub-signal ATS%/CLV when a factor fired) — that is what converts them to `measured` for
> 2027. **The freeze precedes all of this:** see `docs/FREEZE_CHECKLIST.md` (tag `v2026-frozen` by
> ~2026-08-24; calibration audit; freeze-enforcement hook) and the session briefing `docs/HANDOFF_PHASE4.md`.

Replace ad-hoc scripts with a coherent analytics module (`analytics/`), consuming prediction/result JSON only (no live API needed):

1. **CLV** — primary KPI. Per-bet and aggregate: did our number beat the closing line? Report CLV% and average CLV points, overall and by confidence tier.
2. **Calibration** — Brier score and a calibration table/curve for confidence tiers (did 70%-confidence picks win ~70% of the time?).
3. **Classic KPIs** — ATS%, ROI at -110, Sharpe, max drawdown, longest losing streak, with Wilson confidence intervals.
4. **Attribution** — per-factor performance: when factor X fired ≥ threshold, what were ATS% and CLV? This is what makes the 2027 calibration honest.
5. **Selectivity report** — performance of `NO_BET` games (edge validated by skipping?) and of high-variance-filtered games.
6. **Weekly report generator** — one command renders `reports/2026_week_NN.md` (and a season-to-date `reports/2026_season.md`): slate results, running KPIs, tier breakdown, notable hits/misses. Committed by the pipeline (Phase 5). Plain markdown with tables; no external services.

**Acceptance:** running analytics over the archived 2025 data produces a full retro report (this doubles as validation of the analytics code and as new README material).

## 9. Phase 4.5 — CLI v2: Terminal Workflow Overhaul

The 2025 workflow required one manual command per game with fragile flags. The owner wants to stay terminal-native, but with commands that operate on whole slates and never behave differently based on omitted arguments. Replace the flat flag soup with subcommands (keep old flags as deprecated aliases for one release):

```
cfb predict week [N]              # entire slate for week N in one run; N optional
cfb predict game "AWAY @ HOME" [--week N]
cfb predict rerun --week N        # re-run from cached snapshot, no API calls
cfb hypothetical "TEAM A vs TEAM B" [--neutral-site] [--date ...]
cfb project [--team X] [--history]  # projected win totals; --history shows week-by-week drift
cfb slate [N]                     # week's games, lines, data quality, and any dropped/unresolved games with reasons
cfb grade --week N                # fetch finals, grade, compute CLV
cfb report [--week N | --season]
cfb data snapshot --week N        # prefetch/cache all inputs for the week
cfb status                        # API quota, cache freshness, current week, frozen tag
```

Requirements:

1. **Week inference done right.** Week is derived from today's date via the config home `season.json` (**D24** — §9's `season.yaml` became **stdlib `season.json`** to avoid a YAML dependency) and always echoed (`Week 7 — inferred from 2026-10-08`, to stderr so `--format json` stdout stays clean). An explicit `--week` overrides it. Inferred and explicit runs of the same week are bit-identical. If the date falls outside the season, the CLI errors (exit 2) instead of guessing. (Fixes the 2025 silent-week-1 bug permanently. **Delivered in Phase 4.5, PR #17.**)
2. **Slate-first, not game-first.** `cfb predict week` analyzes every game in scope in one command: fetches data once (shared snapshot, respecting API budgets), runs all predictions, saves the weekly JSON, and prints a summary table sorted by edge (columns: matchup, Vegas, model, edge, tier, recommendation). Flags: `--only "TEAM,..."` to restrict, `--min-edge X`, `--tier A|B|C`, `--show-factors` (per-game breakdown), `--format table|json|csv`, `--save/--no-save`.
3. **Cache-backed reruns.** Any predict command can re-execute from the cached snapshot (`rerun` / `--offline`) for instant iteration with zero API spend — useful when tweaking output flags or re-checking a game.
4. **Single-game convenience.** `cfb predict game "Michigan @ Ohio State"` parses one string instead of two flags, resolves names through the existing normalizer, and suggests close matches on failure instead of erroring cryptically.
5. **Human output + machine output.** Every command supports `--format json` for scripting; default is a readable table. Exit codes are meaningful (0 ok, 1 error, 2 degraded data) so shell scripting works.
6. **Config over flags.** Defaults (slate filters, min edge, formats) live in `season.yaml` / user config so routine weekly usage is literally `cfb predict week` with no arguments.

**Acceptance:** the entire manual weekly routine from 2025 (predict slate, inspect factors on interesting games, save JSON) is achievable in ≤2 commands; a regression test proves omitted-week equals explicit-week; `--offline` rerun produces identical output to the original run.

## 10. Phase 5 — Automation Pipeline (highest-priority feature)

> **⚠ Refined by `docs/PHASE5_NOTES.md` (settled operational decisions) + `docs/FREEZE_CHECKLIST.md`.** The
> cadence below is the original sketch; the **binding refinements** are in `docs/PHASE5_NOTES.md`: the
> Tuesday predict job **begins with a catch-up grade** of any previously-ungraded completed games
> (Sunday/Monday games + postponements; idempotent); **line capture is DAILY Wed–Sat**, not Saturday-only
> (Thu/Fri games need honest pre-kickoff closes; each game's close = the last observation before *that*
> game's kickoff — the 1c as-of-T model, no schema work); schedule with **slack before the earliest
> kickoff** (GitHub cron jitter is real). **Acceptance is expanded** with a preseason validation regimen
> (two full-cycle rehearsals + a failure-injection drill + a graded opening-weekend/Week-1 dress
> rehearsal — **D8 abolished Week 0 for 2026**). Two design questions to resolve in planning: pipeline **commit identity** (Actions bot vs authored) and
> **branch-protection interaction** with bot pushes. **The freeze (`docs/FREEZE_CHECKLIST.md`) must land
> before the first live run, and rehearsals run AFTER the tag.**

GitHub Actions (preferred; cron fallback scripts already partially exist in `scripts/setup_cron.sh` — audit and supersede). Secrets (`ODDS_API_KEY`, `CFBD_API_KEY`) via repo secrets.

Weekly cadence (times configurable, ET):

1. **Tuesday — predict.** Fetch slate + data snapshot → run engine → write `data/predictions/2026_week_NN.json` → commit & push with message `predictions: 2026 week NN (pre-kickoff)`. The commit timestamp is the tamper-evident audit trail.
2. **Saturday morning — closing lines.** Fetch near-kickoff spreads for predicted games → append `closing_spread` in a separate commit (never modifying prediction fields; additive only).
3. **Sunday night — grade.** Fetch final scores → write `data/results/2026_week_NN.json`, compute ATS outcomes + CLV → run analytics → commit results + regenerated weekly/season reports.
4. **Failure handling.** Any step failure opens a GitHub Issue automatically with logs; partial data follows the existing degradation rules; the pipeline must be idempotent (safe to rerun).
5. **Budget guard.** Pipeline enforces the daily Odds API call budget and logs remaining quota.
6. **Season config.** The config home is **`season.json`** (**D24** — stdlib JSON, not `season.yaml`), introduced in Phase 4.5 with the `weeks` calendar + `cli_defaults`. Phase 5 **adds** its fields to it: week dates (**no Week 0 for 2026 — D8 abolished it, supersedes §16.2**), freeze tag, kickoff windows, slate filter = FBS-vs-FBS only (§16.1), min data quality thresholds, Odds budget.

**Acceptance:** a full simulated cycle runs against archived data in CI (mock APIs); a live end-to-end test succeeds in one preseason dry-run week; no step requires manual intervention.

## 11. Phase 6 — Stretch Goals (only after Phases 0–5 are done)

1. **Shadow ML model.** Simple, regularized (e.g., logistic/ridge on Phase 1 features), frozen at the same freeze date, logged and graded alongside. Training data is constrained by the Data Recency Principle: it may learn *situation → outcome* relationships from historical CFBD game data (market-behavior patterns), but may not use prior-season team stats as features for current teams. Never drives recommendations. Season-end write-up: fixed weights vs learned model.
2. **Local LLM advisory layer (Ollama).** Strictly outside the deterministic pipeline: summarize injury/news context for the week's slate, generate the narrative section of weekly reports, and produce a "devil's advocate" critique of A-tier picks. Its output is stored in reports, clearly labeled advisory, and never modifies any number.
3. **Read-only dashboard.** Static site (GitHub Pages) rendered from the JSON/report data: season KPIs, week-by-week, calibration chart. No backend.

## 12. Non-Goals (explicitly out of scope for 2026)

- No in-season model changes of any kind after the freeze tag.
- No backtest-driven weight optimization (grid search / fitting to 2025 outcomes).
- No player-level modeling, totals, moneylines, or live betting (candidate for 2027).
- No paid data sources beyond the current APIs.
- No bet placement / sportsbook integration. This is a research tool.

## 13. Engineering Standards

- **Language: Python 3.11+** (decided; do not propose Rust/other rewrites). The workload is I/O-bound API orchestration plus trivial arithmetic over ~60–80 games/week — performance comes from the snapshot/cache architecture, not the language. Typed (mypy-clean on new code), `ruff`-linted.
- Every factor, the rating updater, schedule-intelligence math, and CLV/Brier calculations have unit tests; target: keep/exceed the current 305-test suite, and CI runs it on every push.
- All randomness seeded; all pipeline outputs reproducible from cached snapshots.
- JSON on disk is the source of truth; no databases required.
- Documentation to maintain: `README.md` (rewrite for 2026 once phases land), `docs/CALIBRATION_LOG.md`, `docs/CODE_AUDIT.md`, `docs/SCHEMA.md`, `docs/PIPELINE.md`.

## 14. Agentic Implementation Guide

*(Folded in from the former `docs/IMPLEMENTATION.md` per D3 — this content is now part of the committed spec. Section references (§N) point elsewhere in this document.)*

This project is implemented by Claude Code. The following structures make that reliable.

### 14.1 Repo scaffolding for agents

1. **`CLAUDE.md` at repo root — short (<200 lines).** Contents: build/test/lint commands (`make test`, `make verify-phase-N`), directory layout, and the three binding principles stated in one line each (Data Recency Principle; no hardcoded team/conference names; freeze discipline after the freeze tag). Point to `docs/` for everything else — detailed docs belong in separate files the agent reads on demand, not in CLAUDE.md.
2. **Agent-facing docs are load-bearing.** `docs/SCHEMA.md`, `docs/CODE_AUDIT.md`, `docs/PIPELINE.md`, and `docs/CALIBRATION_LOG.md` are how future agent sessions recover context. Every phase must leave them current; a stale doc is a bug.
3. **Executable verification per phase.** Encode each phase's acceptance criteria as a script: `make verify-phase-0` … `make verify-phase-5` (tests + targeted checks, e.g. the no-network engine test, the no-hardcoded-teams grep, snapshot determinism). A phase is done when its verify target passes — the agent shows the output as evidence, not an assertion of success.

### 14.2 Deterministic guardrails (hooks, not instructions)

Rules that must NEVER break are enforced with Claude Code hooks (PreToolUse blocking), because hooks are deterministic where prompt instructions are probabilistic:

1. **Immutable history:** block any edit/delete under the append-only artifact dirs — `data/predictions/` (byte-immutable claims, D22), `data/results/`, `data/archive/`, `data/lines/`, `data/ratings/`, `data/projections/`, `data/graded/` (outcomes + derived computations). These are append-only artifacts produced by the pipeline. **`reports/` is NOT guarded** — per **D23** it holds *regenerable renderings* (pure functions over the above; git history is their audit trail), which the Sunday pipeline regenerates each run (§10.3).
2. **Freeze enforcement:** after the `v2026-frozen` tag exists, block edits to `factors/`, `engine/`, and weight/threshold config. Changes require the human owner to remove the hook deliberately — that friction is the point.
3. **Secret hygiene:** block committing `.env` or anything matching key patterns.
4. **Quality gate:** a Stop/PostToolUse hook runs `ruff` + the affected tests so sessions can't end with a broken build.

### 14.3 Workflow

1. **One phase = one branch/PR.** Plan first (plan mode), implement, run the verify target, open a PR with the verification output pasted in. The owner reviews at phase boundaries — these are the human checkpoints.
2. **Owner-only decisions.** The agent proposes but never decides: calibration changes (it may draft `CALIBRATION_LOG.md` entries with 2025 evidence; the owner approves each), the freeze itself (human action only), changes to the resolved §16 decisions, and any spend (API tiers).
3. **Scoped work items.** Break phases into tasks the size of one focused session. Avoid unscoped "investigate the codebase" prompts — scope narrowly or delegate exploration to a subagent so the main context stays clean.

### 14.4 Subagents & parallelism

Define in `.claude/agents/` with minimal tool grants (a subagent with no tool list inherits everything — whitelist intentionally):

1. **`test-runner`** — runs the suite, reports only failures with error messages (keeps large output out of the main context).
2. **`code-reviewer`** — read-only; reviews each phase diff against this spec's requirements and the binding principles before the PR is opened, so the agent doing the work isn't the one grading it.
3. **`data-source-scout`** — read-only web/docs research for API details (CFBD v2 endpoints, availability-report page structures) so scraping/HTTP specifics are verified fresh rather than assumed.

Parallelizable workstreams (independent once the canonical schema in `docs/SCHEMA.md` is fixed): the four source clients; individual factor calculators; the analytics module (depends only on prediction/result JSON). Sequential spine: Phase 0 → schema + snapshot builder → engine → pipeline.

### 14.5 Failure patterns to avoid

Named explicitly because they are the common agentic failure modes: trusting plausible-looking code without running the verify target; letting CLAUDE.md bloat until rules get ignored; unscoped exploration flooding context; and marking a phase complete without pasting verification evidence. When the agent hits a spec ambiguity, it asks the owner rather than inventing a resolution — and records the answer in the relevant doc so the question is never asked twice.

## 15. Suggested Timeline (relative)

| Window | Work |
|---|---|
| Now → +2 wks | Phase 0 (hygiene/audit), Phase 1 (data layer) |
| +2 → +6 wks | Phase 2 (ratings + hypothetical), Phase 3 (factors v2) |
| +6 → +8 wks | Phase 4 (analytics, incl. 2025 retro report), Phase 4.5 (CLI v2) |
| +8 → +10 wks | Phase 5 (automation), preseason dry runs |
| Aug 2026 | Calibration review complete → **freeze & tag by 2026-08-24** |
| Season | Zero-touch operation; Phase 6 stretch work only |

### 15.1 De-scoping order (if the freeze date approaches with work unfinished)

The season starts whether the software is ready or not. If time runs short, cut in this order — the guiding rule is that **clean data + automation + honest measurement** constitute the minimum viable season; everything else can land mid-season without violating the freeze (the freeze covers model behavior, not tooling):

**Never cut:** Phase 0 (bug fixes), Phase 1 (snapshot/provenance/team registry), Phase 5 (automation), and CLV capture from Phase 4. A season of clean, automated, provenance-tracked predictions with closing lines recorded is a complete success even if nothing else ships.

**Cut first:** season projections (§6.5), hypothetical mode polish, `cfb project`, report cosmetics — all pure tooling, freeze-exempt, can ship in October.

**Cut second:** power-rating layer entirely (fall back to 2025-style Vegas-anchored adjustments with recalibrated weights); new factors beyond upgrading scheduling fatigue; availability-report ingestion (drop to manual checking).

**Cut last, only under duress:** analytics beyond CLV (Brier, attribution — these can be computed retroactively from stored JSON at any point, so deferring them loses nothing permanently).

## 16. Owner Decisions (RESOLVED — binding; record any future changes in docs/DECISIONS.md)

1. **Slate scope:** FBS-vs-FBS games only.
2. **Season scope & freeze:** Week 0 games ARE in scope. Owner freeze date: **August 29, 2026**. ⚠ Scheduling constraint: Week 0 kicks off Saturday 2026-08-29, and predictions must be generated and committed before kickoff, so the `v2026-frozen` tag must exist **before the Week 0 prediction run** (the Tuesday prior, ~2026-08-25). Practically: complete calibration and tag no later than 2026-08-24; treat Aug 29 as the absolute outer bound, not the target.
3. **`NO_BET` filtering:** purely threshold-driven. No weekly volume target — the model bets what clears the bar, whether that's 5 games or 30.
4. **Power ratings:** build our own Elo (in-house, transparent, per SPEC §6.1) rather than blending public ratings. Public preseason ratings remain permitted as roster-continuity priors only.
5. **2025 audit trail:** the original 2025 repo is private and will NOT be linked. Therefore SPEC §4.3 option (b) is the decision: import the 2025 prediction/result JSONs into `data/archive/2025/` with a provenance note in the README.
6. **Automation platform:** GitHub Actions, confirmed.
7. **Coach-level history:** KEEP the H2H-record and coaching-experience factors with multi-season lookback. This is a documented, deliberate exception to the Data Recency Principle (coach identity is stable across roster churn); note the exception in `docs/CALIBRATION_LOG.md`.

## Appendix A — Data Source Directory

| Need | Source | Access | Notes |
|---|---|---|---|
| Schedules, scores, rosters, team & player stats, advanced stats (EPA, success rate, havoc), coaching records, recruiting, transfer portal, returning production, historical lines, venue lat/long/elevation/timezone | **CollegeFootballData (CFBD) API v2** | Free tier ~1,000 calls/mo; Patreon tiers up to 75k calls/mo + GraphQL realtime (~$10/mo) | Primary source for nearly everything. v1 of this project assumed the old v1 API and 150 calls/day — update client and budgets for v2. Venue endpoint powers the schedule-intelligence table. |
| Preseason priors (SP+, returning production) | CFBD ratings & returning-production endpoints | Included above | Satisfies the Data Recency Principle: these explicitly model roster turnover. |
| Live spreads, multi-book | **The Odds API** | Free tier ~500 credits/mo (verify current) | Keep for prediction-time and closing-line snapshots; budget-guard in pipeline. |
| Schedule/score fallback | **ESPN unofficial API** | Free, no key, unofficial | Existing fallback; treat as unstable. |
| **Injuries / player availability** | **Conference availability reports** — Big Ten (since 2023), SEC (2024), ACC & Big 12 (2025), CFP games | Public web pages on conference sites (secsports.com/fbreports, bigten.org, big12sports.com, theacc.com) | New since v1 and high value. SEC: statuses (out/questionable/probable/available) from 3 days out, final ≤90 min pre-kickoff. Requires scraping/parsing module with per-conference adapters. Use as confidence modifier / NO_BET trigger and as input to the Phase 6 LLM layer — not as a numeric spread factor in 2026. |
| News/media context | RSS (ESPN, CBS, conference sites), Reddit r/CFB JSON API | Free | Advisory/LLM layer ONLY. Never feeds the deterministic engine. 247/On3 are scrape-hostile; exclude from pipeline. |
| Weather | Open-Meteo | Free, keyless | Optional future factor (wind/precip); not in 2026 core scope. |
| Geo math (travel distance, time zones, altitude) | Computed from CFBD venue data + static timezone table | n/a | Part of Phase 1 schedule-intelligence build. |

Rules: verify current rate limits at implementation time and encode them in `config`; every scraped source (availability reports) needs graceful degradation and fixture-based tests; no paid sources beyond low-cost CFBD Patreon tier without owner approval.

### Availability-Report Ingestion (added to Phase 1 scope)

Add `data/availability_client.py` with one adapter per Power Four conference. Output: per-game list of `{player, position, status}` normalized across conferences, cached, refreshed by the pipeline at prediction time and again at the closing-line fetch. v2026 usage is deliberately conservative: a flagged starting QB (or ≥N flagged starters) lowers confidence or triggers `NO_BET` with the reason logged; it never adjusts the spread number directly. Non-Power-Four games simply lack this data — record `availability_data: null` and do not penalize confidence for its absence.
