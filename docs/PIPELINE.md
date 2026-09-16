# The automation pipeline (Phase 5, SPEC §10)

How the 2026 season runs itself: what fires when, what each run commits, what happens when a step
fails, and why several non-obvious choices are the way they are. Written so a session with no
conversational context can operate or repair the pipeline.

**Binding refinements live in `docs/PHASE5_NOTES.md`; owner decisions in `docs/DECISIONS.md`
(D29–D38).** Where SPEC §10's original sketch and `PHASE5_NOTES` differ, `PHASE5_NOTES` wins.

---

## 1. The cadence

| Job | Fires | Does |
|---|---|---|
| **Weekly predict** | Tue 09:17 ET | **catch-up grade first** (CLV sign check per week), then snapshot → quality gate → predict |
| **Daily capture** | Tue 12:50; Wed–Fri 12:50 and 17:23; Sat 05:50 / 09:20 / 09:25 / 12:50 / 12:55 / 16:20 / 16:25 / 19:55 ET (D44, from week 4) | append one line observation per slate game |
| **Weekly grade** | Sun 12:47 ET | finals → grade → CLV sign check → regenerate reports |
| **Freeze integrity** | daily 07:43 ET | frozen-tree assertion + fingerprint + SP+ watch |
| **CI** | push to `main`, every PR | lint, tests, all seven verify targets |

**Tuesday grades before it predicts.** The catch-up covers Sunday/Monday finishers and
postponements, and running it first means a broken grade is found before an Odds credit is spent.

**Both grading paths check CLV signs before committing grades** (`scripts/check_clv.py`, owner
ruling 2026-09-13). `data/graded/` is append-only, so a wrong sign must be refused, not corrected
later. On Sunday a disagreement skips the grading commit and everything after it. On Tuesday the
check runs inside the catch-up loop, once per graded week, and a disagreement **fails the whole job,
claim included**. Skipping only the commit would leave modified graded files in the working tree
and stamp the week's claim `-dirty`. Recovery: fix the code, then re-dispatch (§10).

**Capture is daily, not Saturday-only** — Thursday and Friday games need honest pre-kickoff closes.
Each game's close is *the last observation before that game's own kickoff*
(`data.normalize.odds.closing_observation`), per-game, so the schedule's only job is to have a
recent observation standing before each kickoff window. A single Saturday-morning fetch would
leave a 22:30 ET kickoff with a 12-hour-stale "close", and `closing_observation` would faithfully
report that stale number — CLV noise across the largest part of the slate.

**Two slots per kickoff window (D44, from week 4).** Through week 3 there was one wave per window,
and GitHub's scheduler fired every in-season capture 97–485 min late, so each wave landed after the
window it was meant to precede: Saturday noon games took a 16.7 h-stale close. Each capture slot in
`season.json` now names the window it `precedes` and its `kind`:

* **guarantee**, at window − 6 h 10 min. It clears the worst Saturday lateness observed (309 min)
  by 61 minutes. The lead was 5 h 10 min until review: one minute of margin on twelve samples is a
  point estimate, not margin. A test pins the 370-min lead and exactly one guarantee slot per window.
* **best_effort**, at window − 2 h 35 min on Saturday, timed to the median lateness: it usually lands
  shortly before kickoff, and is designed to miss about four times in ten. The Wed–Fri 17:23 slot is
  best-effort too, but its lead is only 97 min, and all nine measured weekday samples exceed that —
  it has missed the nominal 19:00 window every time. It is kept because weekday kickoffs mostly run
  19:30 or later, which it does serve.

The cost of the longer lead is about an hour of typical guarantee-close freshness, and a measured
step down in the 22:30 window (median 0.62 h → 0.97 h). D44 carries the figures.

The **Tuesday 13:50 slot** exists because Tuesday games start in week 6. Without a capture, a Tuesday
game's only close would be the claim's own snapshot observation, and its CLV would be zero by
construction. Cost: 16 credits a week (15 captures plus the snapshot), with
`odds_budget.expected_weekly_credits` moved to match. The boundary is week 4 (D44). Marking it in the
reports, and never blending the season across it, is the report PR's work.

### Why the crons are UTC and anchored to EDT

GitHub cron is UTC and has no date ranges. EDT is UTC−4; EST (from **2026-11-01**) is UTC−5, so a
fixed UTC time lands **one hour earlier in ET** after the flip — always the safe direction for a
pre-kickoff capture. The alternative, two crons with `if: github.event.schedule == '<literal>'`
guards, duplicates every cron as a string literal and silently stops a job the moment the two
drift. The intended ET time is recorded in `season.json`, every run logs its actual ET time, and a
test re-derives each cron from its ET time — so the DST drift is *auditable* rather than silent.

Minutes are never `:00`: top-of-hour Actions crons are the most heavily delayed.

**Lateness is expected and is not fatal.** The preflight *warns* and continues, because aborting
converts a degraded capture into no capture at all. A late observation is simply not selected as
the close for a game that already kicked, whereas skipping loses the close for the whole slate
(owner ruling 2026-08-07, kept by D44).

**The timing guard (D44).** `pipeline_preflight.check_timing` reads `github.event.schedule`
(`CFB_EVENT_SCHEDULE`) to find the slot that fired the run. It judges the run against **that slot's
window on that slot's ET date**. Until week 3 it measured slack against the next window still ahead
*today*, so a capture that missed its window reported "slack" before a later one (13 of 21 missed
captures). A Saturday slot firing after midnight was scored against Sunday, and the Sunday grade
warned every week. Only `capture` is judged; a manual dispatch is labelled `manual`; a cron that is not
in `season.json` warns as config drift. Escalation:

| tier | when | what |
|---|---|---|
| 0 | every capture | a step-summary line: slot, kind, lateness, margin to the window, status |
| 1 | a **guarantee** slot lands at or after its window | a warning plus a `::warning::` annotation naming the window and its games |
| 2 | a guarantee miss | opens or comments on one `pipeline-late` issue per week (`report-failure`, `kind: late`, cooldown 0); the Sunday grade closes it with the week's tally |
| 3 | every Sunday render | capture timeliness line in the report (the report PR) |
| 4 | a guarantee slot misses in 2 or more weeks of any 3 | escalation to the owner (the report PR) |

A best-effort miss stays at tier 0: it is expected by design (owner ruling 2026-09-15). Every run
stays green.

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
Actions runners are UTC, and a late-evening ET capture can already be Sunday in UTC: the week-1–3
Saturday 20:23 ET slot was literally `23 0 * * 0`. Under D44 the last Saturday slot is 19:50 ET,
which is 23:50 UTC under EDT but a late run still crosses midnight. A UTC-derived date would file the
observation under the following week.

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
| Tuesday | `grading: … catch-up` → `snapshot: …` (+`data/lines`, `data/quota`, **`data/ratings`, `data/projections`**) → **`predictions: … (pre-kickoff)`** |
| Tue–Sat | `lines: … observation HH:MM ET` (Tuesday's from the 13:50 capture, after the claim; D44) |
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

**Pushes use a deploy key, not `GITHUB_TOKEN`.** `main-protection`'s required-status-checks rule
gates **pushes, not merely merges**: a brand-new commit has no check results, so a direct push is
always refused (*"9 of 9 required status checks are expected"*). Observed live on 2026-08-08 — the
run resolved its secrets, fetched, committed, retried three times and fired its stranded-commit
diagnostic, all correctly, and was refused at the last step. "Deploy keys" is on the ruleset's
bypass list, so `actions/checkout` in the three cadence workflows sets
`ssh-key: ${{ secrets.DEPLOY_KEY }}`. `ci.yml` and `freeze-integrity.yml` deliberately do **not**
take it — they never push (D31, as-built amendment 2).

Consequence, deliberate: **deploy-key pushes trigger workflows** (GITHUB_TOKEN pushes do not), so
every data commit runs CI on `main`. That is why the Tuesday job regenerates `data/ratings/` and
`data/projections/` — `verify-phase-2` requires both for *every built week* (SPEC §3's
derived-artifact invariant), and without them the first snapshot of a new week would turn `main`
red. `verify-phase-3` is unaffected: it reads the pinned vehicle (D29), which the pipeline never
touches.

**A path that does not exist yet is not an error.** `cfb-commit` stages only the pathspecs that
exist: `git add` on a pathspec matching nothing exits 128, and under `set -e` that killed the step
— the Tuesday job stages `data/results data/graded` first, and neither exists until something has
been graded.

**Designed states are not failures.** Distinct exit codes keep the alarm meaningful:
`fetch_lines` **3** = budget refusal, **4** = a scheduled Tuesday capture ran before the predict
job built the week's snapshot (owner ruling 2026-09-15; any other missing snapshot is still 1);
`fetch_results` **3** = no completed games yet, **4** = no
claim for this week yet (the normal preseason state — the Sunday job runs every week, but the
week-1 claim is not written until the Aug 25 predict run). Only anything else fails the job.

**`dry_run` has no issue side effects, in either direction.** It gates `skip-secrets` and `push`,
and — since the fast-follow batch — the `report-failure` and `clear-failure` steps too. A failing
dry run must not open a live-labelled issue, and a *passing* one must not **close** a real
unresolved failure. The second is the worse half, and for one day only run ordering prevented it.
Rehearsals still belong on a `rehearsal/*` branch so `mode` labels their artifacts (D32).

**Concurrency.** All three cadence workflows share `cfb-pipeline-${{ github.ref }}` with
`cancel-in-progress: false` — they push to the same branch and must serialize, and cancelling could
tear a run between an Odds spend and `record_quota`, or between two of the Sunday commits. Every job
carries `timeout-minutes: 20` so a hung job cannot hold the group. Push races are handled by a
rebase-retry, safe because every pipeline commit is an *addition* under an append-only tree.

**Known hazard: a pending run can be cancelled silently.** `cancel-in-progress: false` protects
only a *running* job. GitHub keeps **at most one pending run** per group, and a newer pending run
cancels the older one. A cancelled run concludes `cancelled`, which never fires `if: failure()`
(`2027_NOTES` §8 item 15 records the same blind spot for timeouts), so nothing reports it. Two shapes
matter under D44:

* **A lost predict.** On a Tuesday the predict can be pending behind the running 13:50 capture when
  a third group run, in practice a manual dispatch, is created. The week then has no claim.
  **Detected, not prevented:** the claim tripwire in the daily freeze-integrity job
  (`scripts/claim_tripwire.py`; its own concurrency group, so no cadence run can cancel it). From
  Wednesday to Saturday, once that week's own predict day has passed, it opens a `stage:predict`
  issue if the claim is missing, unreadable, or stamped `-dirty`. **The two are not the same alarm.**
  A *missing* claim is recoverable: re-dispatching predict writes it, and that run closes the issue
  (`kind: failure`). A *dirty* one is not: a claim is byte-immutable (D22), so a re-dispatched
  predict skips it and succeeds while nothing is repaired, which is why it gets `kind: dirty-claim`,
  a kind `clear-failure` never clears. It stands until the owner rules on it.
* **A lost capture.** On a Saturday under scheduler lateness, two adjacent slots (as close as 60 min
  apart) can be pending together with a third arriving. The dropped capture never reaches the
  preflight, so no D44 timing tier fires for it. Nothing detects this yet. A per-slot count of
  observations is the natural detector for the report PR's timeliness line.

Whether capture should leave the shared group (serialization then resting on `cfb-commit`'s
rebase-retry) is a **2027 design question, not ruled** (`2027_NOTES` §8 item 33).

**The tripwire checks only the week in play.** `pipeline_week` resolves one week, so once the week
rolls over, an earlier week's missing claim is never re-examined. Its Wed–Sat checks are four
independent chances, but if all four are missed — GitHub may **drop** scheduled runs under load, and
a dispatch cancels a pending freeze-integrity run — that week's absence is never alarmed again.
Verified by walking dates with a missing week-4 claim: 09-23 and 09-26 check week 4, 09-30 and 10-03
check week 5.

**Identity (D30, as amended 2026-08-11).** Commits are authored by
`cfb-pipeline <cfb-pipeline@cfb-predictor-2026.invalid>` with a `Run: <actions-run-url>` trailer. A
project machine identity is not AI attribution (D3); the trailer is the tamper-evident link SPEC §10
wants the commit to carry.

The `.invalid` domain is deliberate and must not be "tidied up" into a real-looking address. RFC 6761
§6.4 reserves it permanently, so it has no MX record, GitHub can never verify it against an account,
and the author renders **unlinked** — the honest rendering for a machine. D30's original address
(`pipeline@users.noreply.github.com`) used GitHub's legacy `<username>@users.noreply.github.com`
form and resolved to a real, unrelated user, so every machine commit showed a stranger's avatar.
Pinned by `tests/test_pipeline_commit_identity.py`. **History WAS rewritten**: the one commit that
carried the old address, `d54ac10`, was rewritten to `745b1cf` under D38 — superseding the D30
as-built amendment's "history is not rewritten" ruling, which was reversed hours after it was
written once the topology proved the rewrite moved no tag. See D38 §3 and §7.

---

## 4. Failure handling (SPEC §10.4)

Every step tees to `$RUNNER_TEMP/pipeline.log`. On failure, `report-failure`:

1. uploads the log plus `git status --porcelain` and the diffs — *what was half-written when it
   died*, the single most useful artifact when a run dies between producing and committing;
2. inlines the last 120 log lines in the issue body, so the issue is useful from a phone;
3. opens **or comments on** an issue deduped by the **label triple** `pipeline-failure` +
   `stage:<x>` + `week:NN`.

### Rule: untrusted values reach a shell through `env:`, never `${{ }}`

Actions substitutes `${{ }}` into a `run:` script **before bash parses it**, so a backtick or `$( )`
in the value executes. This is not hypothetical here — it silently ate two words from a real issue
comment (`` `Sandwich` `` and `` `verify-phase-3` `` were run as commands), which is how it was
found.

The boundary is **who controls the value**, and it is worth stating precisely rather than
pretending no interpolation exists anywhere:

* **Untrusted → must use `env:`.** Anything a non-collaborator can set: issue/PR text, and
  `github.head_ref` (a fork's branch name — git permits backticks in ref names). Both are now
  routed through `env:`. This became live rather than theoretical when the repo went public (D37).
* **Trusted → interpolation is acceptable.** Values this repo produces: `steps.*.outputs.*` from
  `pipeline_week.py` (digits and ISO dates), `matrix.phase` (a literal list), composite `inputs.*`
  passed from our own workflows, and `github.event.repository.default_branch`. One is deliberately
  unquoted — `git add -- ${{ inputs.paths }}` relies on word-splitting a path list.

When adding a step, ask which side of that line the value sits on. If it could ever originate
outside the repo, it goes in `env:`.

**A changed failure mode is never silenced.** The cooldown throttles *repetition*, but it assumed a
repeat is the same failure — the capture job failed on missing secrets, then two hours later on a
rejected push, and the second diagnosis was suppressed because it shared a stage and a week. The
body now carries a signature of the failing line, and a changed signature bypasses the cooldown.

**Dedupe is by label, never by `--search "in:title"`.** GitHub's issue search index is eventually
consistent and lags seconds to minutes — exactly the window in which back-to-back failures need to
find each other. Comments are also cooled down (default 6h), so a job failing all weekend leaves one
issue rather than a hundred comments.

**Recovery closes the issue.** Every cadence workflow ends with an `if: success()` step that closes
the matching issue. Without self-clearing you hand-close issues all season and stop trusting the
label; with it, an open `pipeline-failure` label always means a live problem.

**Not every non-zero is a failure.** `fetch_lines` exit **3** is a budget refusal, `fetch_lines` exit
**4** is a Tuesday capture that beat the snapshot, and `fetch_results` exit **3** is "no games
finished yet". All three leave the job green and commit nothing.

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
| `schedule_et` | `pipeline_preflight.evaluate_timing` (maps `github.event.schedule` to its slot; capture `precedes`/`kind`) + the cron-agreement test |
| `kickoff_windows_et` | `pipeline_preflight.evaluate_timing` (which games a missed window affects); every `schedule_et.capture.*.precedes` must name one (test) |
| `jitter_slack_minutes` | `pipeline_preflight.evaluate_timing` (`on_time` vs `late`, before the window) |
| `data_quality` | `scripts/check_snapshot_quality.py` (per-threshold `fail`/`warn`) |
| `odds_budget` | `fetch_lines --min-credits`, `pipeline_preflight.report_budget` (`expected_weekly_credits` = capture slots + 1, test-pinned) |
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
* **Superseded and deleted:** `scripts/setup_cron.sh` (SPEC §10's "audit and supersede"). It was
  already dead — it hard-exited on a missing `automate_weekly.sh` and assumed a `venv/` Phase 0
  removed — and these workflows replace it.
* **Local checks:** `make verify-phase-5`; `python scripts/pipeline_week.py --format human`;
  `python scripts/pipeline_preflight.py --role capture --skip-secrets`.
