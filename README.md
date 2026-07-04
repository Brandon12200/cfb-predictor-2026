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

## A guided tour

Everything below runs offline against the committed Week-1 snapshot (`data/snapshots/2026_week_01/`), and every block is real output — pasted from the command, trimmed with `...` where long, never hand-edited. It helps to know *when* that snapshot was taken: early July, before any 2026 game is played and before the providers post preseason ratings. So the model knows almost nothing yet — and says so. That honesty is the demo.

**What the engine reads.** No API calls at prediction time — one versioned snapshot, every field stamped with its source and time.

```
$ python scripts/inspect_snapshot.py --week 1
snapshot c86311adcba8c096  (2026 week 1, built 2026-07-03T23:37:10...)
coverage: 220/564 present (39.0%), 344 missing

sources:
  betting_lines    source=odds  count=78   quota={'remaining': 481, 'used': 19}
  games            source=cfbd  count=888
  sp_ratings       source=cfbd  count=0
  returning_production source=cfbd  count=0
  ...
team field-group coverage:
  sp_rating            {'missing': 68}
  returning_production {'missing': 68}
  venue                {'registry': 68}
  ...
```

Coverage is 39%, and the gaps are recorded as gaps: preseason SP+ and returning production aren't posted yet (`count=0`, `missing`), so they are absent, not faked. The engine can always tell a real number from a hole.

**Pricing a matchup.** Ask it for a marquee game:

```
$ python main.py hypothetical --home "Ohio State" --away "Texas" --show-factors
Hypothetical: TEXAS @ OHIO STATE — priced from 2026 week 1 snapshot (c86311adcba8)
  Model spread : OHIO STATE -2.5
  Model favors : OHIO STATE by 2.5
  Components    : rating +0.0 (weight 40%, uncertainty 1.00) | home field +2.5 | schedule +0.0
  Ratings       : OHIO STATE 1500 (flat) | TEXAS 1500 (flat)
  Confidence    : LOW
  Caveats:
    - No preseason prior for one/both teams (SP+ & returning production unposted) — rating starts at baseline.
    - Early season (week 1 ≤ 3): ratings unsettled (uncertainty 1.00); rating signal capped at 40%. Treat as low confidence.
  Schedule factors (points, + favors home):
    (none active)
  ...
```

The number is Ohio State −2.5 — and all of it is home field. Both teams sit at the flat baseline (1500), the rating signal is capped because uncertainty is maxed, and the output says so plainly. A model that invented a confident spread here would be lying; this one tells you it has no team-quality signal yet. In October, with real games banked, the same command yields a real rating differential.

**Season projections.** The same pricer, run over every remaining game, rolls up win totals:

```
$ python main.py project
Season projections — 2026 as of week 1 (EXPERIMENTAL — never drives bets; SPEC §6.5)
  (only one week of projections so far — drift begins once week 2 exists.)
  TEAM                  RATING  PROJ W    ΔWK   ΔPRE
  USC                     1500    6.89      —      —
  NORTHWESTERN            1500    6.25      —      —
  NORTH DAKOTA STATE      1500    6.24      —      —
  MICHIGAN                1500    6.21      —      —
  ...
```

Every team projects near .500 because every rating is still flat — the spread you see is schedule shape (how many games, how many at home), not team quality. That is the honest preseason state, not a bug; the feature is the time-lapse, as the `ΔWK`/`ΔPRE` drift columns fill in from Week 2 and teams separate. Drilling into one team shows the per-game reasoning:

```
$ python main.py project --team "Georgia"
GEORGIA — 2026 projection as of week 1 (EXPERIMENTAL)
  rating 1500 (uncertainty 1.00) | record 0-0 | remaining 11 | projected 5.69-5.31
   WK OPP                  SITE      SPREAD   WIN%  RESULT
    2 WESTERN KENTUCKY     home        -4.5    61%
    3 ARKANSAS             away        +2.1    45%
    ...
    9 FLORIDA              neutral     -0.0    50%
```

Road games take a home-field penalty, the neutral-site game prices to a coin flip — the mechanics are visible even while the ratings behind them are still empty.

**The evidence the model is calibrated against.** The frozen weights aren't guesses; they're set against a 300-game archive of the 2025 forward test, reported without flattering it:

```
$ python scripts/build_calibration_evidence.py
2025 calibration evidence — 294 graded (win/loss) of 300 joined, 6 pushes
  CLV: unavailable — the 2025 archive has no closing lines

OVERALL
  all            n=294  ATS=46.6%  [95% 41%–52%]  (137-157-6)

By confidence
  60-70          n=293  ATS=46.8%  [95% 41%–52%]  (137-156-6)
  70-80          n=1    ATS=0.0%   [95% 0%–79%]   (0-1-0)
  ...
By predicted edge
  <1             n=155  ATS=46.5%  ...
  1-2            n=139  ATS=46.8%  ...
```

This is the humbling part, and it is the whole reason for the rebuild. Graded honestly, the 2025 model went **46.6% ATS** — below break-even — its confidence score barely moved (293 of 294 bets fell in one 60–70 bucket), and its edges were all tiny. Those three facts are exactly the case for the new version: be selective enough to skip marginal bets (`NO_BET`), make confidence tiers that actually separate, and lean on the physical factors that held up. And note the harness's own instruction — read the intervals, not the point estimates; on small cells they are wide.

Every command here is reproducible: rerun any of them and the output is byte-identical, with no API calls.

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
