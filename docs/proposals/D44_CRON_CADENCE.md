# D44 candidate: capture cadence, the timing guard, and its escalation path

> **Lifecycle: working document.** Not authoritative over `docs/SPEC.md` or `docs/DECISIONS.md`. Once
> ruled, the ruling moves to `docs/DECISIONS.md` as D44 and this file is **deleted** at the next
> session boundary.
>
> **Status: PROPOSED, awaiting owner ruling.** Nothing here changes a cron, config value, workflow or
> script. No `factors/`, `engine/`, weight or threshold change is proposed; the freeze is untouched.
> §10 lists what the owner is asked to rule on.
>
> **Measured 2026-09-14** from `gh run list --event schedule`, the per-run Actions logs, and the
> committed `data/lines`, `data/graded`, `data/quota` and snapshot files. §11 gives the method. The
> external facts in §5 were checked against official documentation (GitHub Docs, The Odds API).

---

## 1. Summary

1. **Every capture since 2026-08-26 has fired after the kickoff window it exists to precede: 21 of
   21 runs**, 97–485 minutes after their slots. Pre-season (Aug 19–22) the same crons fired 18–28
   minutes late; the Saturday 20:23 slot, at +101, was the one exception. No slot was dropped.
2. **The damage is concentrated.** The late waves still leave most games with a close under 3.5 h. The
   exceptions are **Saturday's noon window** and, in week 1, **Sunday and Monday** games, which have no
   capture at all. **8 of the 27 graded games carry a close more than 12 h old**, up to 42.7 h.
3. **The timing guard's signal is inverted.** It reported "ok" on **13 of the 21** missed captures,
   warned on the other 8, and warned on **every scheduled Sunday grade (6 of 6)**, a job for which timing does
   not matter. It measures slack against the next kickoff window still ahead today, not against the
   window a run was scheduled to precede.
4. **Two seams ahead that the current cadence does not cover:**
   - **Tuesday games from week 6 (first: 2026-10-06).** Their only close would be the claim's own
     snapshot observation, which makes CLV zero by construction.
   - **No pre-kickoff filter on the claim path** (§4.2). That is a claim-integrity question, not a
     cadence one, and is flagged here for a separate ruling.
5. **Recommended:**
   - **Option B4**: two Saturday slots per window, two weekday slots, and one Tuesday slot. That is
     15 credits a week (about 65 a month of 500) plus the Tuesday slot.
   - **A timing-guard fix with a four-tier escalation path.**
   - **Close-age buckets in the reports**, so CLV is never blended across the change.
   - **Effective from week 4** if ruled by Fri 2026-09-18, otherwise week 5. The Tuesday slot is
     needed before week 6 either way.

## 2. The measurement

### 2.1 Scheduler lateness by job

Lateness is each scheduled run's `createdAt` minus its matched cron slot: the most recent slot at or
before the run, from `season.json` `pipeline.schedule_et.*.cron_utc`.

| job | runs | slots 2026-08-18 to 08-25 | slots 2026-08-26 to 09-13 |
|---|---|---|---|
| capture | 28 | +18 to +28 min (one +101) | **+97 to +485 min** (n=21) |
| predict (Tue 09:17) | 4 | +42, +51 | +243, +240 |
| grade (Sun 12:47) | 4 | +16 | +162, +112, +132 |
| freeze-integrity (daily 07:43) | 27 | +12 to +17 | +18 on 08-26, then **+137 to +588** |

The in-season capture samples:
- **Saturday waves (n=12):** 97, 103, 123, 124, 135, 148, 155, 172, 202, 267, 275, 309.
- **Weekday 17:23 (n=9):** 102, 110, 116, 117, 117, 119, 208, 349, 485. The 485 and 349 are
  2026-08-27/28, the same bad-episode days as freeze-integrity's +575/+588.

**Nothing was dropped.** 21 in-season capture slots produced 21 runs, and 27 freeze-integrity slots
produced 27. GitHub documents that scheduled runs "can be delayed during periods of high loads" and that
"some queued jobs may be dropped". It publishes no bound (§5.3).

### 2.2 Each capture against the window it precedes

Target window = the first `kickoff_windows_et` entry after the slot's ET time, on the slot's own ET
day. In brief:

| slot | in-season runs | fired (ET) | target | before target |
|---|---|---|---|---|
| Wed–Fri 17:23 | 9 | 19:04–23:11, one at 01:28 next day | 19:00 | **0 of 9** |
| Sat 10:23 | 3 | 12:51–13:44 | 12:00 | **0 of 3** |
| Sat 14:23 | 3 | 16:27–16:58 | 15:30 | **0 of 3** |
| Sat 17:23 | 3 | 19:00–19:25 | 19:00 | **0 of 3** |
| Sat 20:23 | 3 | 00:49–01:32 Sun | 22:30 | **0 of 3** |

The per-run table (28 rows: slot, fire time, lateness, target, guard verdict) is reproducible with
the method in §11.

### 2.3 What it did to the closes

The close is `closing_observation`: the last observation at or before that game's kickoff. For all 27
graded games in weeks 1–2, the graded `close_as_of` equals what `closing_observation` returns today.

| window | games | close age | why |
|---|---|---|---|
| Sat 12:00 | 5 (wk1: 1, wk2: 4) | **12.8 h; 16.7 h ×4** | the 10:23 wave has never landed before noon, so the close falls back to Friday's capture |
| Sat 15:30 | 9 | 1.8–2.6 h | served by the late 10:23 wave |
| Sat 19:00–19:30 | 4 | 0.4–2.4 h | served by the late 14:23 or 17:23 wave |
| Sat 22:15–22:30 | 2 | 3.2–3.5 h | served by the late 17:23 wave |
| Thu/Fri evening | 4 | 0.2–1.9 h | kickoffs ran later than the nominal 19:00, so the late run still preceded them |
| **Sun / Mon (wk1)** | 3 | **18.7 h, 18.7 h, 42.7 h** | no capture slot exists on Sun or Mon |

**8 of 27 graded games (30%) have a close more than 12 h old.** The lateness shifts each wave onto
the *next* window, so the first window of the day is the casualty. The Sun/Mon gap is structural and
unrelated to lateness. After week 1, the 2026 schedule has **no** Sunday or Monday FBS-vs-FBS game
(§4.1).

### 2.4 Credits

Odds API: 500 credits a month on the free tier, 1 credit per `regions=us&markets=spreads` call (§5.3).
The ledger (`data/quota/odds_2026_09.json`) shows **16 used in September through 2026-09-13, 484
remaining**: 2 Tuesday snapshots + 14 captures = **8 a week**, matching `expected_weekly_credits: 8`.
Every capture run costs 1 credit whether or not a game is ahead; `fetch_lines` has no skip.

## 3. The timing guard

`check_timing` (`scripts/pipeline_preflight.py:128`) takes `now`, reads **today's**
`kickoff_windows_et`, and reports slack before the first window whose deadline (`window − 60 min`) is
still ahead. It warns only when `now` is past every one of today's deadlines (`:144`). It does not know
which slot fired the run or which window that slot serves. It runs for every role, via `cfb-setup`.

**Its verdicts, from the run logs:**

| runs | verdict | correct? |
|---|---|---|
| 21 in-season captures that missed their window | **"ok" ×13**, warn ×8 | the 13 "ok" are affirmative false all-clears |
| — Saturday waves (12) | "ok" ×12, e.g. 13:15 "74 min of slack before the 15:30 ET window" | false |
| — Sat 20:23 slot firing after midnight | scored against **Sunday's** 13:00 window (627–670 min slack) | false |
| — Thu 08-27 slot firing Fri 01:28 | scored against **Friday's** 19:00 window, "991 min of slack" | false |
| — weekday runs past 18:00 ET | warn ×8, "past every kickoff window for today" | true, by accident |
| Sunday grade runs (all 6, 2026-08-09 to 09-13) | **warn ×6 of 6**, including the two fastest, 15 and 16 min after the 12:47 slot | noise: grade is not time-critical, and a 12:47 slot is already past the 13:00 − 60 min deadline |
| Tuesday predict runs | no timing line (no `tue` window) | blind: Tuesday games start in week 6 |

**So the guard warns every week where timing is irrelevant, and says "ok" where it matters.** The
tests (`tests/test_pipeline_preflight.py`) pin a run past every window warning and an early run
recording slack. None pins a run that missed its target but precedes a later window, a run that
crosses midnight, or the grade role.

**A correction to an earlier draft.** An earlier draft on an unmerged branch (`0f21b96`, 2026-09-13)
states that "the timing guard warned on all seven runs" of week 2. The logs show the four Saturday runs as "ok" and only the three weekday
runs warning. That draft is the source of the premise `docs/HANDOFF_SEASON.md` §9 (third round)
records as overturned. Its lateness and staleness tables agree with §2.

## 4. Seams ahead

### 4.1 Tuesday and Wednesday games (weeks 6–13)

From the week-2 snapshot's schedule, grouped by the ET day of `start_date`. All 761 games in
`data.games` are FBS-vs-FBS under the season registry's canonical names.

| week | Tue | Wed | Thu | Fri | Sat | Sun | Mon |
|---|---|---|---|---|---|---|---|
| 3 | 0 | 0 | 1 | 2 | 54 | 0 | 0 |
| 4 | 0 | 0 | 1 | 4 | 53 | 0 | 0 |
| 5 | 0 | 0 | 2 | 3 | 51 | 0 | 0 |
| 6 | **1** | 2 | 4 | 5 | 46 | 0 | 0 |
| 7 | **2** | 2 | 3 | 3 | 49 | 0 | 0 |
| 8 | **3** | 1 | 3 | 5 | 44 | 0 | 0 |
| 9 | **2** | 2 | 2 | 3 | 47 | 0 | 0 |
| 10 | **2** | 3 | 2 | 5 | 50 | 0 | 0 |
| 11 | **3** | 3 | 2 | 3 | 56 | 0 | 0 |
| 12 | **3** | 2 | 1 | 5 | 55 | 0 | 0 |
| 13 | **2** | 0 | 1 | 13 | 49 | 0 | 0 |
| **6–13 total** | **18** | **15** | 18 | 42 | 396 | 0 | 0 |

The first Tuesday game is **`SOUTHERN MISS@TROY`, 2026-10-06 20:00 ET**. Tuesday start times are 19:00
×13, 19:30 ×1 and 20:00 ×3, plus one at exactly 00:00. Wednesday: 19:00–20:00 ×7, 00:00 ×8.

**Many future start times are unset.** From week 4 on, 36–42 Saturday games a week have a
`start_date` of exactly 00:00 ET; weeks 2 and 3 have none. That pattern reads as "time not yet
announced", not as real midnight kickoffs. It is an inference from the committed snapshot, which has
no time-confirmed field. The closes are unaffected, because `data/lines` takes each game's `kickoff`
from the Odds API's `commence_time`, not from CFBD. It does mean this table's day-of-week counts for
later weeks can shift as times are announced.

Whether a game enters the tracked slate depends on Odds coverage at snapshot time; week 2 tracked 16
of its 49 games.

**A Tuesday game's close would be the claim's own number.** The Tuesday predict job builds the snapshot,
which seeds line observation #1 at the claim's `vegas_spread` (verified on week 2: `ALABAMA@KENTUCKY`
claim +10.4, first observation 10.4 at 2026-09-08 17:17 UTC). No capture runs on Tuesday, so that
observation is the close. **CLV would then be exactly 0 by construction**, a measurement artifact
that the beat-close rate would count as "did not beat the close". The `kickoff_windows_et` config
also has no `tue` entry.

### 4.2 No pre-kickoff filter on the claim path (claim integrity — a separate ruling)

- `get_ncaaf_spreads()` is called with no `commenceTimeFrom` (`data/snapshot/builder.py:88`,
  `scripts/fetch_lines.py:70`).
- Neither `build_predictions.py` nor `analytics/predictions.py` excludes a game that has already
  kicked off.
- From week 6 a Tuesday claim includes games kicking off that evening.

**If a Tuesday predict run ever fires after a Tuesday kickoff, a started game is claimed**, with
whatever line the snapshot holds, and the claim is byte-immutable (D22, D38 §6). The worst in-season
predict lateness is 243 min, landing about 13:20 ET, which leaves roughly 6.5 h before a 20:00 kickoff.
The worst lateness on any job is freeze-integrity's +588 min; at predict that would land about 19:05.
The Odds API's `/odds` endpoint "Returns a list of upcoming and **live** games" (v4 guide). No field
marks an event as live, and the docs do not say whether a started event's spreads are in-play odds
or the pre-game line. `commenceTimeFrom` exists (ISO 8601 UTC); the docs say nothing on whether it
changes the credit cost.

This is not a cadence question, and D44 does not decide it. It is flagged so the owner can rule before
2026-10-06. A guard would belong on the claim path, which is freeze-exempt (`scripts/`, `analytics/`),
and would be its own reviewed PR.

## 5. Options

### 5.1 Replay against the measured lateness

Each Saturday slot is given a lateness drawn from the 12 in-season Saturday samples, 20,000 draws, and
each window takes the latest landed observation before it. Otherwise it falls back to Friday: 16.7 h,
as measured. **Assumption: lateness is independent of the slot's hour.** The data half-contradict
this: the 20:23 slot, which is 00:23 UTC, was the latest all three Saturdays. So treat the medians
as indicative. The **guarantee column is exact**: a slot at `window − 5 h 10 min` lands before the window
at the worst observed Saturday lateness (309 min). Slots at minute 23 miss that guarantee by 2 minutes, which is why the proposed early slots sit at
minutes 20 and 50.

| option | Sat slots (ET) | Sat credits | 12:00 median / worst | 15:30 | 19:00 | 22:30 |
|---|---|---|---|---|---|---|
| **S0** status quo | 10:23 14:23 17:23 20:23 | 4 | **16.7 h / 16.7 h** | 2.9 / 20.2 h | 2.1 / 7.0 h | 1.8 / 6.5 h |
| **A** shift each to W−5h10m | 06:50 10:20 13:50 17:20 | 4 | 2.6 / 3.5 h | 2.6 / 3.5 h | 2.6 / 3.5 h | 2.6 / 3.5 h |
| **B** S0 + W−5h10m, deduped | 06:50 10:20 13:50 14:23 17:20 20:23 | 6 | 2.6 / 3.5 h | 2.6 / 3.5 h | 1.7 / 3.5 h | 0.7 / 3.5 h |
| **B4** W−5h10m + W−2h40m per window | 06:50 09:20 10:20 12:50 13:50 16:20 17:20 19:50 | 8 | **0.6 / 3.5 h** | 0.6 / 3.5 h | 0.6 / 3.5 h | 0.6 / 3.5 h |

"Worst" is the worst simulated age. Share of simulated closes at 3 h or less: S0 0% / 58% / 91% / 75%;
A about 70% everywhere; B 69 / 70 / 98 / 80%; **B4 87 / 92 / 91 / 91%**. The second slot per window
(W−2h40m) is timed to the median lateness (about 150 min), so it usually lands shortly before kickoff;
the first slot is the guarantee.

**Weekday** (19:00 nominal; real kickoffs 19:00–22:30), with the 9 weekday samples:

| weekday slots | 19:30 median | 20:00 | 21:00 | 22:30 | credits/day |
|---|---|---|---|---|---|
| S0 17:23 | 0.3 h (p90: previous day) | 0.8 h | 1.7 h | 3.2 h | 1 |
| A 13:50 | 3.7 h | 4.2 h | 5.2 h | 6.7 h | 1 |
| **B 13:50 + 17:23** | 0.3 h (p90 4.0 h) | 0.7 h (p90 4.3 h) | 1.7 h | 3.2 h | 2 |

A alone makes weekday closes worse; the 17:23 slot's lateness is what currently serves 19:30+ kickoffs.

### 5.2 All options, with credit cost

Weekly credits = 1 Tuesday snapshot + weekday captures (Wed–Fri) + Saturday captures (+ Tuesday slot).
A month is about 4.35 weeks.

| option | what changes | credits/week | ≈/month (of 500) | other cost | risk |
|---|---|---|---|---|---|
| **S0** status quo | nothing | 8 | 35 | — | noon closes stay 12.8–16.7 h; Tuesday CLV ≡ 0 |
| **A** shift | Sat to W−5h10m; weekday unchanged | 8 | 35 | none | median close 2.6 h; no margin beyond 309 min |
| **B** | A's slots + S0's 14:23, 20:23; weekday 13:50 + 17:23 | 13 | 57 | none | 22:30 better than A, noon/15:30 equal |
| **B4** (recommended) | two slots per Sat window; weekday 13:50 + 17:23 | 15 | 65 | none | worst observed lateness bounded at 3.5 h |
| **+T** Tuesday slot (with any of the above) | Tue 13:50 ET capture (lands before 19:00 at up to 309 min) | +1 | +4 | none | spends a credit on weeks with no Tuesday game (weeks 1–5, 14–15) unless gated |
| **C** external dispatch | cron-job.org or Cloudflare Workers fires `workflow_dispatch` at W−60 | 8 (+ GitHub crons kept as backstop) | 35+ | $0 on free tiers; a fine-grained PAT with **Actions: write** stored at a third party | GitHub documents **no latency guarantee** for dispatch runs; a new external dependency and secret |
| **D** sleep in the job | cron fires early; the job sleeps to W−60 | 8 | 35 | public-repo minutes are free; 6 h job limit | a sleeping capture holds the shared `cfb-pipeline` group, which keeps **one** pending run and cancels older pending runs, so Saturday waves could cancel each other unless capture gets its own group |
| **F** accept and annotate | reports mark stale closes | 8 | 35 | — | keeps 30% stale closes |

**Budget after the change:** B4 + T at 16 a week is about 70 a month, 14% of 500. That stays above
`alert_below: 100` all month. **`expected_weekly_credits` must move with the cadence.** The
retry-storm warning fires when `remaining < monthly − weekly × 6` (`scripts/pipeline_preflight.py:167`).
At 8 it would fire falsely by the fourth week of any month under B4. The next Odds tier is
$30/month for 20,000 credits; nothing here needs it.

**Concurrency under B4.** Saturday slots are 60–150 min apart and a capture runs 1–3 minutes, so two
runs queue together only if two late runs are created within minutes of each other. That did not
happen in season: the closest two consecutive capture runs were 148 min apart (n=21). With the shared group's
one-pending rule, three runs queued together would lose the middle one.

### 5.3 External facts (checked 2026-09-14)

| claim | status | source |
|---|---|---|
| `schedule` runs "can be delayed during periods of high loads … some queued jobs may be dropped"; avoid the top of the hour; no bound or SLA given | verified | docs.github.com, events that trigger workflows, `schedule` |
| `github.event.schedule` holds the cron line that triggered the run | verified | same page |
| `POST /repos/{o}/{r}/actions/workflows/{id}/dispatches` needs fine-grained PAT **Actions: write** (App: `actions:write`) | verified | docs.github.com REST, workflows; PAT permissions |
| dispatch-triggered runs start promptly | **unverifiable**: no GitHub doc says so | — |
| public repo, standard hosted runners: free (fair use); job limit 6 h | verified | docs.github.com, Actions limits and billing |
| a concurrency group keeps at most one pending run; a newer pending run cancels the older, regardless of `cancel-in-progress` | verified; no workflow here sets `queue:` | docs.github.com, using concurrency |
| cron-job.org: free, 1-minute minimum, custom headers; no documented timing accuracy | verified (accuracy unverifiable) | cron-job.org FAQ |
| Cloudflare Workers Cron Triggers: 5 on the free plan, 1-minute minimum; no documented precision | verified (precision unverifiable) | developers.cloudflare.com |
| Odds API: cost = markets × regions (1); free tier 500 credits/month; next tier $30/month for 20K | verified | the-odds-api.com v4 guide, pricing |

## 6. Recommendation

1. **Cadence: B4 + T.** Saturday 06:50, 09:20, 10:20, 12:50, 13:50, 16:20, 17:20, 19:50 ET; Wed–Fri
   13:50 and 17:23; Tuesday 13:50.
   - All stay single UTC crons anchored to EDT, per `season.json` `dst_note`, and off the top of the hour.
   - `season.json` `schedule_et` and `tests/test_workflow_schedules.py` agree by construction.
   - `expected_weekly_credits` moves to 16.
2. **Timing guard fixed and escalated** as in §9.
3. **Reports bucket CLV by close age** as in §8, starting with the first render after the change. The
   same buckets apply to weeks 1–3 retroactively, with nothing relabelled.
4. **C held in reserve**, with an explicit trigger (§9, tier 4). **D is not recommended**: its
   concurrency behaviour is the kind of seam this season keeps paying for.
5. **§4.2 ruled separately before 2026-10-06.**

**Why not A**, the zero-credit option. A bounds the worst case as well as B4 does, but its median close
is 2.6 h against B4's 0.6 h, and on weekdays it is worse than today. The 7 extra credits a week buy
the difference, about 30 credits a month, or 6% of the monthly budget.

## 7. Effective week

A cadence change applies to captures only. The claim, its snapshot and grading are unaffected.
**It should take effect at a week boundary**, so that no week's closes come from two regimes:

- **The merge window** is after the Sunday grade and before the week's first capture. Under B4 that
  capture is Wed 13:50, so the window runs from Sunday afternoon to Wednesday midday.
- **Week 4 (captures from Wed 2026-09-23)** requires a ruling by **Fri 2026-09-18**, leaving time for a
  reviewed PR. It would merge Mon 2026-09-21 or Tue 2026-09-22 after the predict run. It should not
  merge on Sun 2026-09-20, which is already the first live CLV gate and the first `leans | graded`
  render.
- **Otherwise week 5** (merge window Sun 2026-09-27 to Wed 2026-09-30).
- **The Tuesday slot must be live before week 6** (2026-10-06), whichever week the rest lands.
- **DST, 2026-11-01** (the end of week 9): from week 10 every UTC cron lands one hour earlier in ET.
  Under B4 that adds up to 1 h to close ages and strengthens the guarantee. It is a second, smaller
  boundary; §8's buckets absorb it without a new regime label.

## 8. CLV comparability across the boundary

CLV is measured against the close. A close taken 16.7 h before kickoff misses the last 16.7 h of market
movement, often the largest part. **So CLV before and after a cadence change is not the same
measurement, even though the claims are identical.**

- **What the data can and cannot say today.** Graded leans by close age: at 3 h or less, n=13, mean
  CLV +0.01, beat the close 6/13; 3–12 h, n=1; over 12 h, n=5, mean −0.08, 2/5. **These counts are far
  too small to show an effect in either direction**, and the proposal does not claim one.
- **The proposal: bucket by close age, not by calendar regime.**
  - Every graded record already carries `close_as_of`, and `data/lines` carries `kickoff`, so close age
    is derivable for every week, past and future, with no schema change and no relabel of an
    append-only file.
  - The Sunday reports (renderings, D23; `analytics/` is freeze-exempt) would show CLV per bucket (≤3 h,
    3–12 h, >12 h), with counts. They would never show a season-blended CLV without the split.
  - Games whose close **is** the claim's own observation (§4.1) would be counted separately as "no
    close after claim", not as CLV 0.
- **The regime boundary is still recorded**, as the effective week in D44, so a reader can see why
  the distribution of close ages shifts.

## 9. The timing guard: fix and escalation path

**Fix (`scripts/pipeline_preflight.py`, freeze-exempt).**
- For a scheduled run, read `github.event.schedule` (documented) to know which slot fired.
- Give each `season.json` `schedule_et` entry an explicit `precedes` window rather than inferring it.
- Evaluate lateness against that slot and window **on the slot's ET date**, which fixes the
  cross-midnight case.
- Run the check for the **capture** role only. Grade and freeze-integrity are not time-critical, which
  removes the weekly false warning on grade.
- For a manual dispatch there is no slot, so the verdict is labelled `manual`.
- Add a `tue` window.
- Tests pin the four shapes §3 found unpinned.

**Escalation.** WARN-not-ABORT stands: the owner ruling of 2026-08-07 is unchanged, because a late
observation is still evidence.

| tier | trigger | action | run conclusion |
|---|---|---|---|
| 0 | every capture | step summary line: slot, fired at, lateness, target window, margin | unchanged |
| 1 | landed after its target window | `::warning::` annotation naming the window and the games in it | green |
| 2 | first tier-1 of a week | open (or append to) one issue labelled `pipeline-late` for that week, reusing `report-failure`'s label dedupe and cooldown; the Sunday grade closes it with the week's tally | green |
| 3 | every Sunday render | a "capture timeliness" line in the weekly report: waves landed before their window, k of n; close-age buckets for the week's graded games | — |
| 4 | under the new cadence, a **guarantee** slot (W−5h10m) misses in 2 or more weeks of any 3 | escalate to the owner, re-opening option C | — |

## 10. What the owner is asked to rule on

1. **Cadence:** B4 + T (recommended), A, B, C, F, or another shape, together with the new
   `expected_weekly_credits`.
2. **Effective week:** week 4 (ruling by 2026-09-18) or week 5. The Tuesday slot is live before week 6
   in either case.
3. **Timing guard:** the §9 fix and the tier 0–4 escalation path, or a subset.
4. **Comparability:** close-age buckets in the reports (§8), with "close = claim observation" counted
   separately.
5. **§4.2, separately:** whether the claim path excludes games that have already kicked off, to be
   ruled before 2026-10-06.

## 11. Reproducing the measurements

All read-only.
- **Lateness:** `gh run list --workflow <file> --event schedule --limit 100 --json databaseId,createdAt,conclusion`
  for the four cadence workflows. Match each run to the latest `cron_utc` slot at or before `createdAt`.
- **Guard verdicts:** `gh run view <id> --log`, then grep `min of slack before` or
  `inside or past every kickoff window`. Exclude echoed script source.
- **Close age:** for each game in `data/lines/2026_week_0{1,2}.json`, `kickoff` minus
  `closing_observation(entry)["fetched_at"]`. Compare with `data/graded` `close_as_of`.
- **Replay:** the §5.1 method, seed 7 (Saturday) and 11 (weekday).
- **Schedule:** `data/snapshots/2026_week_02/snapshot.json` `data.games`, grouped by ET weekday of
  `start_date`. Filter both teams against `{canonical_name(t["school"]) for t in fbs_teams_2026.json["fbs"]}`
  (`data/team_registry.py::canonical_name`). The snapshot's names are already canonical, so all 761 pass.
  **Do not** build the set from `school.upper()`: that drops the 86 games whose canonical name differs,
  and it produced this table's first, wrong version (caught by review).
- **Credits:** `data/quota/odds_2026_09.json` entries.
