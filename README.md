# CFB Predictor — 2026

A college football spread model that commits each week's predictions to this public repository
**before kickoff**, then grades itself in the open.

The model is rule-based, and its weights are locked behind a git tag before the season starts.
Nothing is tuned after the fact. The commit timestamps are the evidence — **the audit trail is the
product**, not the picks. 2026 is the first season run under this discipline end to end; the first
claim is committed **2026-08-25**.

It's built for three kinds of reader: someone following a public forecasting experiment week to
week; someone who wants to price a matchup, real or hypothetical, and see the reasoning; and anyone
curious whether a disciplined rule-based model can beat closing betting lines without fooling
itself.

**Status: the pipeline is live; the first claim commits Tuesday 2026-08-25.** The model is frozen at
`v2026-frozen-3` and the automation runs itself on GitHub Actions, with no human in the loop:

| When | What happens |
|---|---|
| **Tuesday** | grade anything that finished, rebuild the data snapshot, commit the week's predictions **before kickoff** |
| **Wed–Fri** | capture betting lines once daily |
| **Saturday** | four capture waves through the day, ahead of each kickoff window |
| **Sunday** | fetch finals, grade, regenerate reports |
| **Daily** | check the frozen code still matches its tag; watch for upstream data changes |

**Following along without cloning anything:** each week's claim appears in
[`data/predictions/`](data/predictions/) on Tuesday, and the graded report appears in
[`reports/`](reports/) as `2026_week_NN.md` on Sunday. Neither exists for 2026 yet — **the first
claim lands Tuesday 2026-08-25, the first graded report Sunday 2026-08-30.** Until then, the only
rendered report is [`reports/2025_retro.md`](reports/2025_retro.md), the predecessor season regraded
(see [the record](#the-record)).

## See it run

*Outputs below were captured 2026-08-16 and are real, keyless, from the snapshot committed in this
repo. Snapshots rebuild every Tuesday, so exact numbers will drift — this section is designed to
age.*

**Price any matchup**, including one that isn't scheduled:

```
$ cfb hypothetical "Texas vs Ohio State" --show-factors
Hypothetical: TEXAS @ OHIO STATE — priced from 2026 week 1 snapshot (87e472ff1fe3)
  Model spread : OHIO STATE -6.5
  Components    : rating +4.0 (weight 40%, uncertainty 1.00) | home field +2.5 | schedule +0.0
  Ratings       : OHIO STATE 2154 (sp+) | TEXAS 1956 (sp+)
  Confidence    : LOW
  Caveats:
    - Early season (week 1 ≤ 3): ratings unsettled; rating signal capped at 40%. Treat as low confidence.
```

The number decomposes: where it came from, how much weight the rating carries, and why. Note what it
refuses to do — with no 2026 games played it caps the rating's influence and calls its own
confidence LOW, rather than manufacturing a number.

**The weekly artifact** — the slate, with a recommendation per game:

```
$ cfb slate 1
Week 1 slate — 11 game(s) with a line

MATCHUP                      VEGAS  DATA_Q  REC
---------------------------  -----  ------  ------
BAYLOR @ AUBURN              -7.2   0.833   NO_BET
BOSTON COLLEGE @ CINCINNATI  -7.5   0.833   NO_BET
CLEMSON @ LSU                -9.4   0.833   NO_BET
COLORADO @ GEORGIA TECH      -6.9   0.833   NO_BET
```

Every game says `NO_BET`. The model only picks when the edge clears its threshold, and before any
games are played it never does — so this is selectivity visible in the output, not a failure.
[Grading](#how-it-is-graded) explains why the preseason edge cannot clear it.

**Missing data is recorded as missing**, never filled with a neutral guess:

```
$ python scripts/inspect_snapshot.py --week 1
snapshot 87e472ff1fe3adc9  (2026 week 1)
coverage: 426/566 present (75.3%), 140 missing
  betting_lines   source=odds   count=111
  sp_ratings      source=cfbd   count=139
  advanced_stats  source=cfbd   count=0
  season_stats    source=cfbd   count=0
```

`advanced_stats` and `season_stats` are `0` because no 2026 games have been played. They read as
absent, not zero — so the engine can always tell a real number from a gap.

Run `./demo.sh` for a longer guided tour. Everything above works with no API keys.

## The record

**The 2026 record does not exist yet, and that is the design.**
[`data/predictions/`](data/predictions/) holds no 2026 file, because a prediction cannot be written
before the claim window opens. **The first one lands Tuesday 2026-08-25** — committed before that
week's games, timestamped by the commit, and byte-immutable afterwards. From that point the
guarantee is checkable by anyone: compare the commit date against the kickoff.

One 2026 artifact is already accumulating: **[`data/lines/`](data/lines/)** — append-only betting-line
observations, captured daily, and the raw material closing-line value is computed from. It fills in
between each Tuesday claim and the Sunday grade.

**The 2025 files in `data/predictions/` are inherited, not pre-registered here.** They are the
predecessor model's forward-test record, imported wholesale in a single commit roughly ten months
after those games were played, so their timestamps in this repository prove nothing and are not
offered as evidence of anything. They are here because regrading them honestly — it was a losing
season — is the reason this rebuild exists.

- **[`reports/2025_retro.md`](reports/2025_retro.md)** — that season graded end to end by this
  repo's own code, split by lean side, CLV recorded as honest-missing because 2025 captured no
  closing lines.
- **[`data/archive/2025/`](data/archive/2025/)** — the archived record and its provenance note.
- **[`data/results/`](data/results/)** — the outcomes those grades were computed from.

**2025 is inherited evidence. 2026 is the experiment.** The verify-it-yourself claim below applies
to 2026 onward, where this repository's own machinery enforces it.

## How it is graded

Three terms, once. The **closing line** is the final betting spread before kickoff — the market's
best guess, and the fairest available benchmark. **CLV** (closing line value) is whether the model's
number beat that line. **ATS** ("against the spread") is whether a pick would have won relative to
the spread.

- **CLV is the primary measure, not win rate.** It is the signal that survives small samples. A
  season is ~14 weeks; win rate over that is mostly noise.
- **Results are split by which side the model leaned — never one blended number.** The model's
  schedule factors can only ever penalise the visitor, so it leans home far more often than away. A
  single blended figure over that skew measures the skew, not the model. Every report also grades a
  naive "always take the home team" baseline over the same games, so the model is measured against
  something rather than against zero.
- **Skipped games are still graded.** When the edge is too small the model outputs `NO_BET`, and the
  report records what would have happened anyway — selectivity is measured, not assumed.

*In the preseason, every game prices to `NO_BET` — by design.* The factors nudge the market's
number, they don't replace it, and the maximum total adjustment the factor set can produce is
structurally bounded. Before any games are played the achievable edge sits far below the threshold
required to make a pick, so the model declines. That bound is measured and documented, not asserted
— see [`docs/CALIBRATION_LOG.md`](docs/CALIBRATION_LOG.md).

## What is guaranteed

**From 2026 onward, every prediction in this repository is committed before kickoff — and you can
verify that yourself from the commit history.** That is the whole promise, and the scope is
deliberate: the imported 2025 files carry no such guarantee (see [the record](#the-record)), so the
claim is made only where this repository's machinery enforces it. Everything below is how it is
kept.

- **Missing data is recorded as missing.** Never neutral-filled, so a real value is always
  distinguishable from a gap.
- **Selectivity is an output, not an excuse.** `NO_BET` is a first-class result and is graded like
  any other.
- **Measurement lives outside the freeze.** `analytics/` can improve; the model it measures cannot.
- **The record is immutable.** `data/predictions/` is byte-immutable — a claim is never edited,
  because its timestamp *is* the claim, and no file in it has been modified since it was written.
  Results and line observations are append-only. Reports are regenerable renderings of them. Commit
  hooks enforce this, not convention.

**How the freeze is enforced.** When a season tag is cut, `factors/` and `engine/` become fixed:
commit hooks block edits locally, every automated run re-checks the directory tree hashes against
the tag, and a behavioural fingerprint hashes what the model actually *produces* over a fixed slate
of games. Path protection alone is not enough, because a prediction depends on the data the model
reads as well as its code — so both are checked. Every prediction records the exact build that
produced it.

**Why there are three tags.** Every prediction records the model version that produced it, and the
model's inputs changed twice during the preseason — before any game had been predicted. Each change
was measured, ratified and given a **new tag** rather than quietly absorbed; both are documented
with their measured deltas in [`docs/SPEC.md`](docs/SPEC.md) §3.1.

Commits authored by `cfb-pipeline` are automated writes from the season pipeline (GitHub Actions) —
see [`docs/PIPELINE.md`](docs/PIPELINE.md). Solo project otherwise.

## Getting started

Requires **Python 3.11+**. No API keys needed for any of this.

```bash
git clone https://github.com/Brandon12200/cfb-predictor-2026.git
cd cfb-predictor-2026
make install    # editable install, with dev tools
make test       # full suite — offline, no credentials
```

The suite is fully offline — network calls are blocked in tests — so a fresh clone runs green with
no setup beyond `make install`.

**Keys are only needed to fetch new data.** To rebuild a snapshot or capture live lines, add a
`.env` (both providers have usable free tiers):

```
CFBD_API_KEY=...   # collegefootballdata.com — schedules, stats, ratings
ODDS_API_KEY=...   # the-odds-api.com — betting lines
```

Without them, everything that reads committed data works normally; `cfb status` notes the missing
key and still runs.

## Commands

`cfb --help` lists the full set.

| Command | Does |
|---|---|
| `cfb status` | freeze state, build stamp, data-source health, API quota |
| `cfb slate 1` | week 1's games with a line, and the call on each |
| `cfb predict week 1` | price the slate, `NO_BET` games included |
| `cfb hypothetical "A vs B"` | price any matchup, real or invented |
| `cfb project --team "Georgia"` | season win-total projections — **experimental; never drives a recommendation** |
| `python scripts/inspect_snapshot.py --week 1` | what the engine can see, and what is missing |
| `python scripts/slate_fingerprint.py` | hash of the frozen model's output — the behavioural freeze check |

The automation calls `scripts/*.py` directly rather than the CLI — those entry points and the
weekly choreography are documented in [`docs/PIPELINE.md`](docs/PIPELINE.md); the verification and
build targets are in the `Makefile`. (`scripts/build_predictions.py` is claim-gated to a pre-kickoff
window.)

## Documentation

| Doc | What it is |
|---|---|
| [`docs/SPEC.md`](docs/SPEC.md) | the contract — what gets built, and what "done" means |
| [`docs/DECISIONS.md`](docs/DECISIONS.md) | every binding decision with its reasoning, superseded rather than edited |
| [`docs/PIPELINE.md`](docs/PIPELINE.md) | the operating manual for the automation |
| [`docs/CALIBRATION_LOG.md`](docs/CALIBRATION_LOG.md) | every frozen constant, with the evidence for it |

## Non-goals

This project does not place bets or integrate with sportsbooks, does not change the model in-season
after the freeze, does not optimise weights by fitting to past outcomes, and does not model player
props, totals, or moneylines. It is a research instrument and a portfolio project — **nothing here
is betting advice, and there are no profit claims anywhere in this repository.**

## License

MIT — see [`LICENSE`](LICENSE).
