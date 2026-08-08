# The automation pipeline (Phase 5, SPEC §10)

How the 2026 season runs itself: what fires when, what each run commits, what happens when a step
fails, and why several non-obvious choices are the way they are. Written so a session with no
conversational context can operate or repair the pipeline.

**Binding refinements live in `docs/PHASE5_NOTES.md`; owner decisions in `docs/DECISIONS.md`
(D29–D36).** Where SPEC §10's original sketch and `PHASE5_NOTES` differ, `PHASE5_NOTES` wins.

---

## 1. The cadence

| Job | Fires | Does |
|---|---|---|
| **Weekly predict** | Tue 09:17 ET | **catch-up grade first**, then snapshot → quality gate → predict |
| **Daily capture** | Wed/Thu/Fri 17:23 ET; Sat 10:23 / 14:23 / 17:23 / 20:23 ET | append one line observation per slate game |
| **Weekly grade** | Sun 12:47 ET | finals → grade → regenerate reports |
| **Freeze integrity** | daily 07:43 ET | frozen-tree assertion + fingerprint + SP+ watch |
| **CI** | push to `main`, every PR | lint, tests, all seven verify targets |

**Tuesday grades before it predicts.** The catch-up covers Sunday/Monday finishers and
postponements, and running it first means a broken grade is found before an Odds credit is spent.

**Capture is daily, not Saturday-only** — Thursday and Friday games need honest pre-kickoff closes.
Each game's close is *the last observation before that game's own kickoff*
(`data.normalize.odds.closing_observation`), per-game, so the schedule's only job is to have a
recent observation standing before each kickoff window. The four Saturday waves exist because a
single Saturday-morning fetch leaves a 22:30 ET kickoff with a 12-hour-stale "close", and
`closing_observation` would faithfully report that stale number — CLV noise across the largest part
of the slate.

### Why the crons are UTC and anchored to EDT

GitHub cron is UTC and has no date ranges. EDT is UTC−4; EST (from **2026-11-01**) is UTC−5, so a
fixed UTC time lands **one hour earlier in ET** after the flip — always the safe direction for a
pre-kickoff capture. The alternative, two crons with `if: github.event.schedule == '<literal>'`
guards, duplicates every cron as a string literal and silently stops a job the moment the two
drift. The intended ET time is recorded in `season.json`, every run logs its actual ET time, and a
test re-derives each cron from its ET time — so the DST drift is *auditable* rather than silent.

Minutes are never `:00`: top-of-hour Actions crons are the most heavily delayed.

**Jitter is expected and is not fatal.** The preflight *warns* on a late run and continues, because
aborting converts a degraded capture into no capture at all — a late observation is simply not
selected as the close for a game that already kicked, whereas skipping loses the close for the
whole slate.

---

## 2. Which week is it?

Two resolvers answer two different questions. Conflating them was a live bug (F2).

* **`resolve_week` / `infer_week_for_date`** — "which week's games are being played today". Used by
  the human `cfb` CLI. Raises outside the season, deliberately.
* **`pipeline_week`** — "which week am I working on". The lowest-numbered week whose `end` is on or
  after today, clamped to the last week. **Never raises.**

The week-1 prediction run is the Tuesday *before* kickoff — **2026-08-25** — which falls inside no
game window, so the game-window resolver raises there and the entire first live cycle would die
before doing anything. Wed–Fri captures on Aug 26–28 fail the same way.

Dates come from `pipeline_today`, which reads the **pipeline timezone**, never the runner's clock.
Actions runners are UTC, and a Saturday 20:23 ET capture is already Sunday in UTC — that cron is
literally `23 0 * * 0`. A UTC-derived date would file the observation under the following week.

**Known consequence:** `pipeline_week` returns 1 for every date through 2026-09-07, so the Tuesday
job runs "week 1" twice. The byte-immutable claim already existing is the skip condition, and
therefore also the idempotency guard.

---

## 3. Commit choreography

One push per run; **one commit per artifact tier**. The tiers are D22/D23:

| Tier | Paths | Contract |
|---|---|---|
| **Claims** | `data/predictions/` | byte-immutable forever |
| **Outcomes + derived** | `data/results/`, `data/graded/`, `data/lines/`, `data/snapshots/` | append-only |
| **Renderings** | `reports/` | regenerable; git history is the audit trail |

| Job | Commits, in order |
|---|---|
| Tuesday | `grading: … catch-up` → `snapshot: …` (+`data/lines`) → **`predictions: … (pre-kickoff)`** |
| Wed–Sat | `lines: … observation HH:MM ET` |
| Sunday | `results: …` → `grading: …` → `report: …` |

Three things here are load-bearing:

1. **The claim commit stages `data/predictions/` and nothing else.** Its author timestamp *is* the
   pre-registration evidence. No report, snapshot or graded file rides in it.
2. **The snapshot is committed *before* predictions are built.** `model_version` is
   `git describe --tags --always --dirty`; an uncommitted snapshot in the working tree would stamp
   every claim of the week `-dirty`. This ordering is invisible unless you read `utils/version.py`,
   so it is pinned by a test.
3. **The snapshot commit also stages `data/lines/`**, because `SnapshotBuilder` seeds line
   observation #1. Leaving it unstaged means the next capture's commit silently carries this run's
   write.

Empty commits are never created (`git add -- <paths>` then `git diff --cached --quiet`, never
`--allow-empty`). `record_observation` rewrites the lines file every run even when it appends
nothing, but writes sorted, indented JSON — so the bytes are identical and the check correctly
reports "no change".

**Concurrency.** All three cadence workflows share `cfb-pipeline-${{ github.ref }}` with
`cancel-in-progress: false` — they push to the same branch and must serialize, and cancelling could
tear a run between an Odds spend and `record_quota`, or between two of the Sunday commits. Every job
carries `timeout-minutes: 20` so a hung job cannot hold the group. Push races are handled by a
rebase-retry, safe because every pipeline commit is an *addition* under an append-only tree.

**Identity (D30).** Commits are authored by `cfb-pipeline <pipeline@users.noreply.github.com>` with a
`Run: <actions-run-url>` trailer. A project machine identity is not AI attribution (D3); the trailer
is the tamper-evident link SPEC §10 wants the commit to carry.

---

## 4. Failure handling (SPEC §10.4)

Every step tees to `$RUNNER_TEMP/pipeline.log`. On failure, `report-failure`:

1. uploads the log plus `git status --porcelain` and the diffs — *what was half-written when it
   died*, the single most useful artifact when a run dies between producing and committing;
2. inlines the last 120 log lines in the issue body, so the issue is useful from a phone;
3. opens **or comments on** an issue deduped by the **label triple** `pipeline-failure` +
   `stage:<x>` + `week:NN`.

**Dedupe is by label, never by `--search "in:title"`.** GitHub's issue search index is eventually
consistent and lags seconds to minutes — exactly the window in which back-to-back failures need to
find each other. Comments are also cooled down (default 6h), so a job failing all weekend leaves one
issue rather than a hundred comments.

**Recovery closes the issue.** Every cadence workflow ends with an `if: success()` step that closes
the matching issue. Without self-clearing you hand-close issues all season and stop trusting the
label; with it, an open `pipeline-failure` label always means a live problem.

**Not every non-zero is a failure.** `fetch_lines` exit **3** is a budget refusal and
`fetch_results` exit **3** is "no games finished yet" — both leave the job green and commit nothing.

---

## 5. Budget guard (SPEC §10.5)

One `get_ncaaf_spreads(regions=us, markets=spreads)` call = **1 credit**. The cadence spends ~8/week
(~35/month) against a 500/month tier, so **exhaustion is not the risk — a retry storm is.**

* **Pre-spend refusal** lives in `fetch_lines.py` (exit 3), where the credit is about to be spent.
* **Preflight reports** balance, provenance and burn rate to the step summary. It does *not* gate;
  two gates on one resource eventually disagree.
* **Cross-run memory:** `data/odds_quota.json` is gitignored, so a fresh Actions checkout would lose
  the balance and fall back to the last snapshot manifest's build-time figure (bounded to a week,
  but blind in between). The capture job restores it via `actions/cache`. Committing the file was
  rejected: it belongs to no artifact tier, and two workflows writing it concurrently is a merge
  conflict on a file whose whole purpose is being trivially correct. An append-only `data/quota/`
  ledger is the honest long-term answer and is queued, not on the critical path.

---

## 6. The freeze, and the two gates that protect it

`factors/` and `engine/` are hook-immutable, but a prediction is a function of the frozen code **and**
the freeze-exempt `data/` read seam — which has moved model output twice after ratification (A6's
metres/feet fix, the venue-timezone fallback). So the freeze is enforced twice:

* **Path level** — the preflight asserts `git rev-parse HEAD:factors == <freeze_tag>:factors` (and
  `engine`) before any spend. Exact, milliseconds, immune to a whitespace-preserving edit.
* **Behavioural** — `verify-phase-3` hashes what the model produces over the 330-game tracked slate.

**If the fingerprint fails, do NOT update the constant.** Either the change was unintended — revert
it — or it was intended, in which case it needs a documented **SPEC §3 exception and a new tag**.

The gate reads a **pinned** vehicle, `data/archive/frozen/2026_week_01_snapshot.json` (D29), not the
live week-1 bundle the pipeline rebuilds. Its own SHA-256 is asserted first, so "the gate's input
changed" reports differently from "the model moved".

**`sp_watch` exists because the fingerprint structurally cannot detect an external event** — it reads
a committed snapshot, so it is a function of the commit. CFBD has not published 2026 SP+ or returning
production; when it does, D10 activates both with no code change, `Sandwich` wakes up, model output
moves, and the fingerprint will fail *correctly*. The daily probe turns that from a discovery into a
countdown. It opens an Issue and leaves the job green: the right response is a decision process, and
a red required check only pressures someone into making the change quietly.

---

## 7. Rehearsals

**Mode is derived from the ref, never from a dispatch input** — a mode that cannot be typed cannot be
mistyped. `main` + `schedule` ⇒ live. `rehearsal/*` ⇒ rehearsal (commits get a ` [rehearsal]` suffix
and issues a `rehearsal` label). Anything else refuses to run.

Rehearsals run on an **unmerged branch** (D32) rather than writing to a separate artifact tree,
because every script then runs its exact production code path with zero flags — a rehearsal that
exercises different code is not a rehearsal. `main` keeps both the pristine gate vehicle and the
untouched week-1 claim slot. CI **fails any PR from a `rehearsal/*` branch**, so rehearsal artifacts
cannot reach the live claim slots by merge.

Sequence: dry-run pass (`dry_run: true`, commits nothing) → full cycle on the rehearsal branch →
failure-injection drill → a second rehearsal from a fresh branch → live Week 1 on `main`.

**Failure injection is environmental only** — an invalid key in the step env, `min_credits`
set absurdly high, a conflicting push. There is deliberately **no `if os.getenv("INJECT_FAILURE")`
branch in production code**: a test seam in the production path is a worse defect than the one it
tests.

---

## 8. `season.json` → consumer

Every key has a consumer; `verify-phase-5` fails if one appears here without one, or vice versa.

| Key | Read by |
|---|---|
| `timezone` | `utils.season_calendar.pipeline_today` / `pipeline_timezone` → all week resolution |
| `freeze_tag` | `scripts/pipeline_preflight.py` (tree-hash assertion), `freeze-integrity.yml` |
| `slate_filter` | documents SPEC §16.1 scope; the dropped-game detector will consume it |
| `schedule_et` | `pipeline_preflight` (intended-vs-actual ET) + the cron-agreement test |
| `kickoff_windows_et` | `pipeline_preflight.check_timing` (warn-only slack check) |
| `jitter_slack_minutes` | `pipeline_preflight.check_timing` |
| `data_quality` | `scripts/check_snapshot_quality.py` (per-threshold `fail`/`warn`) |
| `odds_budget` | `fetch_lines --min-credits`, `pipeline_preflight.report_budget` |
| `rehearsal` | the live/rehearsal guard in `.github/actions/cfb-setup` |

`schedule_et.*.cron_utc` is the one deliberately non-executable key — Actions cannot read this file,
so the crons are duplicated into the workflows and a test asserts the two agree.

---

## 9. What the Sunday report leads with (D27)

**The report opens with the lean-side split, not a blended headline** — and that ordering is
behaviour, pinned by tests, not a layout preference.

Preseason leans run **195 home / 35 away — 5.57:1, and structural**: `TravelBurden` and
`ConsecutiveRoad` can only ever penalise the visitor, and `Altitude` only advantages the host. A
single blended number over that skew is dominated by how home teams happened to do against the
spread, and is uninterpretable as evidence about the model. That is precisely D17's retired "57.0%
ATS" — a systematic home lean measured and reported as skill.

So every report carries, before anything else: ATS% and CLV **split by lean side**, each with its
Wilson interval; a **naive always-lean-home baseline** over the same games, graded against the
**Vegas line**; and the difference. The away cell is thin (~35 preseason) and the report says so
inline rather than letting a point estimate stand.

The naive baseline is *not* the retired D17 diagnostic, which graded always-home against the
model's **own** contrarian number — that survives under its honest name in
`scripts/grading.py::home_covered_model_spread_diagnostic` and must never be confused with this one.

Validated against an independent oracle: over the 2025 archive the baseline reproduces D17's
separately-recorded **54.4% (160/294)** to the game, and the model's **46.6%**, giving the −7.8%
delta the comparison exists to surface.

*(A temporary D36 gate withheld the Sunday report commit until this landed. It is removed; the risk
is closed at the source instead of held back at the commit.)*

---

## 10. Operating notes

* **Manual run:** `workflow_dispatch` on any cadence workflow; `week` blank resolves from ET.
  `dry_run: true` runs everything and commits nothing.
* **Backfill a week:** dispatch with an explicit `week`. Explicit always wins.
* **A claim already exists:** the predict step skips. That is correct and not an error — claims are
  byte-immutable forever.
* **Superseded:** `scripts/setup_cron.sh` is dead (it hard-exits on a missing `automate_weekly.sh`
  and assumes a `venv/` Phase 0 deleted). Kept only until it is deleted in the follow-up PR.
* **Local checks:** `make verify-phase-5`; `python scripts/pipeline_week.py --format human`;
  `python scripts/pipeline_preflight.py --role capture --skip-secrets`.
