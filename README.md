# CFB Contrarian Predictor — 2026

A college football spread model built as a research instrument, not a betting product. Each week it makes one falsifiable claim — where the market's number is wrong — writes that claim to git *before* kickoff, and grades itself after the games. The weights are frozen before the season starts and never touched again. The question it exists to answer is a narrow, honest one: can a disciplined, rule-based model beat the closing line without fooling itself?

Two things make it more than a list of picks:

- **A frozen, pre-registered model.** Factor weights, activation thresholds, and confidence tiers are calibrated from prior-season evidence and then locked behind a git tag before Week 1. No mid-season tuning, no fitting to results. A wrong assumption gets exposed cleanly instead of quietly patched.
- **An independent power rating.** Alongside the contrarian factor system, an in-house Elo prices any matchup from current-season games — real or hypothetical — and the gap between that number and the market is a logged diagnostic rather than a hidden knob.

## Why it might interest you

Most "beat the spread" projects are backtests: tune the parameters until the historical curve looks good, then publish the curve. That process manufactures its own evidence. This one inverts it. The model is committed, timestamped, and frozen; the season is the test set; the git history is the receipt. If it is wrong, the record says so.

Measurement is built around **closing line value** — did the model's number beat where the line actually closed — rather than raw win rate, because CLV is the signal that survives small samples and separates skill from variance. Everything else (calibration curves, per-factor attribution, bet-or-skip selectivity) exists to answer "which parts actually worked," so the next version is revised from evidence instead of intuition.

## The 2025 baseline

A predecessor model ran frozen through the 2025 season and motivated this rebuild:

| Metric | 2025 (Weeks 1–14, 300 games) |
|---|---|
| Against the spread | 57.0% |
| ROI at −110 | +8.82% |

Read this cautiously. Over 300 games the 95% confidence interval on 57% is roughly **51–63%** — suggestive, not conclusive: enough to justify a more careful second version, not enough to claim a durable edge. There are **no 2026 performance figures** in this repository, and there will not be any until games are played and graded in the open. Nothing here is a profit claim.

## Design principles

- **Calibrated freeze.** Prior-season data — a 300-game archive of *market-mispricing* outcomes, not team quality — sets weights and thresholds by reasoning and evidence, never by grid-searching a backtest (the overfitting this project exists to avoid). Every constant is recorded in `docs/CALIBRATION_LOG.md` with its supporting evidence, an evidence class (measured from data vs. reasoned from domain knowledge), and the old→new change, and is ratified before the freeze.
- **Data recency.** Team-quality inputs use current-season data only. Prior seasons are allowed for exactly two things: modeling market behavior, and roster-continuity-aware preseason priors. A team is judged on who it is now, not who it was.
- **Provenance everywhere.** The engine reads only versioned weekly snapshots. Every field records where it came from and when; missing data is recorded as missing, never quietly replaced with a neutral value, so a real number is always distinguishable from a gap. Two runs over the same snapshot are byte-for-byte identical.
- **Append-only audit trail.** Predictions, results, ratings, and line observations are write-once historical artifacts, protected by commit-time hooks. The history is the product.

## What the system does

**The contrarian model.** It starts from the Vegas spread and applies a fixed-weight set of factors — physical and scheduling signals (rest, travel, altitude, short weeks, byes), situational ones (revenge, lookahead, desperation), and coaching and market-structure signals — to produce its own number. The edge is the disagreement. Situational factors, historically the noisiest, must be corroborated by an independent signal before they fire, and a marginal edge resolves to an explicit **NO_BET** rather than a coin-flip wager.

**The power rating.** An independent in-house Elo, built only from current-season results with roster-continuity preseason priors, prices any matchup: `price(home, away, venue, date) → model spread`. One function drives three features — a **model-vs-market diagnostic** on real games, a **hypothetical mode** ("what does the model make of Texas at Oregon in November?"), and **season win-total projections** with week-over-week belief drift. Projections are labeled experimental and never drive a recommendation.

## How a season runs

The finished weekly loop is zero-touch, on a schedule, via GitHub Actions:

- **Tuesday — predict.** Fetch the slate, build the data snapshot, run the engine, and commit the week's predictions to git *before* kickoff. The commit timestamp is the tamper-evident record.
- **Saturday — closing lines.** Capture near-kickoff spreads for the predicted games, added alongside the prediction and never editing it.
- **Sunday — grade.** Fetch final scores, compute ATS outcomes and CLV, regenerate the reports, and commit results.

A failed step opens an issue and degrades gracefully; the pipeline is idempotent, and any run can be reproduced from the cached snapshot with zero API calls and identical output.

## Measurement

- **CLV** is the primary KPI — per bet and aggregate, overall and by confidence tier.
- **Calibration** — a Brier score and a reliability curve by tier: did 70%-confidence picks win about 70% of the time?
- **Attribution** — when a given factor fired, what were its ATS% and CLV? This is what keeps the next calibration honest.
- **Selectivity** — NO_BET games are still graded (what would have happened), so skipping is measured, not assumed.

## Quickstart

```bash
git clone https://github.com/Brandon12200/cfb-predictor-2026.git
cd cfb-predictor-2026
make install          # editable install with dev tools
make test             # full offline test suite
```

API keys go in `.env` (both have usable free tiers):

```
CFBD_API_KEY=...   # collegefootballdata.com — schedules, stats, ratings, historical lines
ODDS_API_KEY=...   # the-odds-api.com — prediction-time and closing spreads
```

Commands that run today:

```bash
python main.py hypothetical --home "Ohio State" --away "Texas" --show-factors
python main.py project --team "Georgia"        # experimental season projections + drift
python scripts/build_snapshot.py --week 1      # cache a week's inputs as a snapshot
python scripts/build_calibration_evidence.py   # 2025 evidence pack for calibration
make verify-phase-1                            # executable acceptance checks for a phase
```

The polished, slate-first `cfb` command set (`cfb predict week`, `cfb grade`, `cfb report`, …) is the Phase 4.5 target interface; today's entry points are the `main.py` subcommands and the `scripts/` tools above.

## Repository map

```
engine/         power rating (Elo), matchup pricer, prediction engine, confidence
factors/        fixed-weight factor calculators + registry (the frozen model)
analytics/      freeze-exempt tooling: season projections, calibration evidence
data/
  snapshots/    versioned weekly input bundles — the only thing the engine reads
  registry/     season team registry (membership, venues, aliases)
  lines/        append-only "as-of" line observations (closing lines, CLV)
  ratings/      per-week power ratings (derived)
  projections/  per-week season win-total projections (experimental)
  predictions/  +  results/   pre-kickoff predictions and graded outcomes (append-only)
  archive/2025/ the frozen 2025 forward-test record
docs/           SPEC (the build plan), DECISIONS, CALIBRATION_LOG, SCHEMA, CODE_AUDIT
scripts/        snapshot / ratings / projection builders, accuracy tools, verify targets
```

Key docs: **SPEC.md** is the authoritative build plan; **DECISIONS.md** logs binding choices; **CALIBRATION_LOG.md** records every frozen constant with its evidence; **SCHEMA.md** defines the data contracts; **CODE_AUDIT.md** tracks what each slice changed.

## Status

The system is being built in phases against `docs/SPEC.md`. This table is the honest ledger: the prose above describes the design, and here is what is actually merged to `main`.

| Phase | Scope | State |
|---|---|---|
| 0 | Repo hygiene, audit, packaging, week-inference fix | Done |
| 1 | Snapshot-first data layer, team registry, schedule intelligence, closing-line capture | Done |
| 1.5 | Injury/availability reports, line-movement history | Planned |
| 2 | In-house Elo power rating, matchup pricer, hypothetical mode, season projections | Done |
| 3 | Factor system v2: physical reweight, corroboration, NO_BET, confidence tiers, schema v2 | In progress (foundations merged) |
| 4 | Measurement: CLV, calibration, per-factor attribution, weekly reports | Planned |
| 4.5 | `cfb` subcommand CLI | Planned |
| 5 | Zero-touch GitHub Actions pipeline | Planned |
| 6 | Stretch: shadow ML model, local LLM advisory layer, static dashboard | Planned |

## 2025 audit trail

The full 2025 record lives in `data/archive/2025/` with a provenance note. The original 2025 repository is private and will not be linked, so the prediction and result JSONs are imported here to keep the audit trail attached to this repo. From 2026 onward the automated pipeline commits predictions before kickoff and results after games, so future audit trails are generated automatically.

## Non-goals

By design (SPEC §12), this project does **not** place bets or integrate with sportsbooks, change the model in-season after the freeze, optimize weights by fitting to past outcomes, or model player props, totals, or moneylines. It is a research tool. Nothing here is betting advice.

## License

MIT
