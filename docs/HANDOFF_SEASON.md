# HANDOFF → the season (temporary — delete when the season closes)

A briefing for a fresh session with zero conversational context. **Not authoritative over
`docs/SPEC.md`.** Written 2026-09-01 at the retirement of the rehearsals session, which ran from the
Rehearsal-0 boundary through the live claim and the first graded Sunday.

Read this, then `docs/PIPELINE.md`, then the reading list in §6.

**Your first task is in §2. It is a red `main`. Do it before anything else.**

---

## 1. Season state — as of 2026-09-01 13:37 ET

The model is frozen at **`v2026-frozen-3`**. `main` is at **`8f7a5ff`**, today's scheduled snapshot
commit. Tags: `v2026-frozen`, `-2`, `-3`, plus `rehearsal-0`, `rehearsal-1`, `rehearsal-2`,
`rehearsal-drill` (all unmerged acceptance evidence — leave them).

**The week-1 claim is committed and immutable.** `2a331e6`, written by the scheduled Tuesday predict
on 2026-08-25, `data/predictions/2026_week_01.json`:

| | |
|---|---|
| games | 11 |
| prediction_type | **NO_BET 11 of 11** |
| tiers | A 11 |
| lean | neutral 7 / home 4 |
| max \|edge\| | **0.1403**, against a `min_edge` threshold of **1.50** |
| `model_version` | `v2026-frozen-3-23-g7485244` — describe form, not a bare SHA, not `-dirty` |

All 11 are `NO_BET` because the achievable edge sits far below the floor — selectivity working, not
breakage (3c.9). **Do not read the quiet as a fault.**

**Grading: 2 of 11.** Week 1 spans **Aug 29 – Sep 7**, so most of the slate had not kicked off by the
first graded Sunday. Graded so far: `north-carolina-vs-tcu-week1`, `nc-state-vs-virginia-week1` —
both `edge_direction: neutral`, so `clv` and `ats_result` are correctly null (f3). Both carry real
closing lines (`-8.5`, `-4.1`). The remaining nine — **four of them `home`-lean** — grade on the
Sunday after their kickoffs. **That is when the lean table and the CLV cell populate for the first
time.**

**The skip path is proven live.** Today's scheduled predict (run `33537284634`'s sibling, predict run
at 17:20 UTC, `success`) found the claim already committed and took `Claim already made` — no second
claim, no overwrite, claim blob unchanged, a fresh `snapshot:` commit at `8f7a5ff` as designed.

**Cadence** (`season.json` → `pipeline.schedule_et`), with observed jitter:

| Job | Scheduled ET | Observed |
|---|---|---|
| predict | Tue 09:17 | +40–60 min (09:58, 13:20) |
| capture | Wed–Fri 17:23 | +20–25 min |
| capture (Sat waves) | 10:23 / 14:23 / 17:23 / 20:23 | similar |
| grade | Sun 12:47 | +15 min |
| freeze-integrity | daily 07:43 | +10–25 min |

Jitter is normal; `check_timing` is WARN-only by design.

**The weekly cancelled-CI signature is expected, not a fault.** `ci.yml:14-16` sets
`cancel-in-progress: true`, so a multi-commit push cancels its own intermediate runs — only the
**final** commit's CI completes. Sunday 08-30: `results:` and `grading:` cancelled, `report:` green.
Tuesday 08-25: `snapshot:` cancelled, **the claim's CI green only because the claim is committed
last**. Recorded as `2027_NOTES` §8 items 25–26. A `cancelled` conclusion does **not** fire
`if: failure()`, so nothing reports it (item 15).

**Zero open issues.** Six PRs merged in this tenure: #45 (README), #46 (record), #49 (drawer),
#50 (D39), #51 (D40).

---

## 2. YOUR FIRST TASK — `main` is red

**Run `33537284634`, push of `8f7a5ff`, conclusion `failure`.** Every job fails (`test`,
`verify (0)`–`(5)`, `verify-freeze`) because they all run the suite. **Four tests, one cause:**

```
tests/test_cfb_cli.py::test_slate_returns_ok_when_all_games_have_lines
tests/test_cfb_cli.py::test_omitted_week_equals_explicit_week
tests/test_cfb_cli.py::test_offline_rerun_identical_to_predict_week
tests/test_cfb_cli.py::test_predict_week_save_refuses_overwrite_d

E  AssertionError: assert 2 == 0
E   +  where 2 = cfb.main(['slate', '1', '--format', 'json'])
```

**Diagnosis state — measured, not assumed.** Today's rebuild is the **first post-kickoff snapshot**.
Books de-list games once played, so the week-1 slate went from **11 lines to 9**:

```
d358db5 (pre-kickoff):  betting_lines=11  with a line=11
8f7a5ff (today):        betting_lines=11  with a line= 9
```

The two now line-less games are exactly the two that have been played. `analytics/predictions.py`
records them in `meta.coverage.skipped`, and `cli/cfb.py:103-111` returns **`EXIT_DEGRADED`** when
the whole-slate commands find anything skipped — `cli/output.py:20` defines `EXIT_DEGRADED = 2`.

So **exit 2 is the CLI behaving as written**: a degraded-but-honest slate, not an error. The tests
assert exit 0 and were authored pre-season, when every game had a line.

**The un-ruled question — owner decision, do not decide it yourself.** Is exit 2 the *contracted*
degraded exit for this case, meaning the tests are what should change? `cli/cfb.py:10` and `:103`
document the intent, but **find and cite the SPEC / CLI-docs statement of the exit-code contract
before proposing either fix.** The two candidate shapes:

1. **Tests are stale** — assert `in (EXIT_OK, EXIT_DEGRADED)` for a post-kickoff slate, or build
   their fixture from a pre-kickoff snapshot so they test the property they meant to.
2. **The degraded trigger is too broad** — a game dropped *because it was played* is not the same
   condition as a game dropped *because its line never posted*, and only the latter deserves
   degraded. This is the more interesting reading and the one worth measuring.

**Do not "fix" it by loosening an assertion until the contract is cited.** A test that pins a defect
is a recorded failure mode here (HANDOFF §(g).4).

Note this is **freeze-exempt** (`cli/`, `tests/`), so it is fixable — but it is *also* the third
time this season a seam has fired on its first post-transition execution. Expect that pattern.

---

## 3. Deferred queue

**Next Sunday (2026-09-06 grade), once more games are graded:**

- **README graded-week edit** — deferred twice by owner ruling. Replace the preseason `NO_BET`
  caveat with one real graded-week example in **lean-split format, never a blended headline
  figure**, and point the follow-along line at `reports/2026_week_01.md` directly. It needs a
  correct report *and* a meaningfully graded week; 2/11 with both graded games neutral was never
  the showcase.
- **`by_lean_side` discriminating test** — the lean table has never rendered with a populated side.
  When it does, pin it.
- Any drawer lines the week produces.

**Open questions the owner may send:** a feasibility question (raised, not yet asked).

**Dec 6–7 cron shutdown — unruled.** `season.json` week 15 ends **2026-12-12**, and the cadence is
regular-season only (`get_games(season_type="regular")`, `data/clients/cfbd_v2.py:86-91`).
`pipeline_week` clamps, so the crons keep firing into the postseason with nothing to do —
`2027_NOTES` §8 item 3, "no season-end kill switch". The owner must rule *when* the cadence stops.
Do not switch it off unilaterally.

---

## 4. Standing doctrines — binding, carried from the whole freeze and rehearsal sequence

- **Never touch `factors/`, `engine/`, or calibration config.** Any finding requiring it escalates
  to the SPEC §3 exception process. The fingerprint constant moves only inside a ratified exception
  with a new tag — never as a fix, never as a convenience.
- **Claims are byte-immutable, and history is welded shut.** D38 §6: after the first predicted event
  — which occurred **2026-08-29** — claims and history are permanently immutable with **no**
  override, not by owner ruling, not under a SPEC §3 exception. The void performed on 2026-08-11 was
  the only one this project will ever do, and it was legitimate solely because it preceded kickoff.
  **That door is now closed.**
- **Fix forward; never hand-write an artifact.** If a scheduled run fails, the recovery is to fix the
  code and let the next scheduled run produce the artifact. Never write a claim by hand.
- **Reports are regenerable renderings (D23).** A renderer bug is fixed and the report regenerated —
  that is the designed remedy, and it is what D40 used. `data/predictions/` is byte-immutable;
  `data/results/`, `data/graded/`, `data/lines/`, `data/quota/`, `data/ratings/`,
  `data/projections/` are append-only. Hooks enforce it; do not work around a hook block.
- **`code-reviewer` before every PR; a NO-GO is binding; the GO must cover the FINAL diff at branch
  head.** Fix anything after a GO and the delta gets re-reviewed. This tenure took three NO-GO/GO
  cycles on one docs paragraph — that is the process working, not overhead.
- **Per-criterion reporting, never rolled up.** Every rehearsal criterion gets its own pass/fail with
  the command output or run link that decided it. A summary verdict hides the one that failed.
- **Supersede, never edit.** A ratified entry is corrected by a new block that says what changed and
  why, not by rewriting the original. Commit messages carrying an error stay as written.
- **Read the failing log before theorizing.** Every real diagnosis this tenure produced came from
  reading run output or committed artifacts; every wrong one came from reasoning about what the code
  probably did.
- **Frame-pin your citations (D40's lesson).** A `file:line` in a document describing a *past* state
  rots the moment the fix lands — pin the commit and give the current line alongside. And before
  publishing any document with citations, **resolve every one mechanically against the file it
  names.** See §7.
- **No AI attribution** in commit messages or PR text; `includeCoAuthoredBy` stays `false`.
- **Dense proposals go to `docs/proposals/<ITEM>.md`** and are deleted once ratified; **PR summaries
  go to `docs/pr-summaries/` and are retained.** Merges and tags are the owner's.

---

## 5. Things that will look like bugs and are not

- **Machine commits on `main` with no human involved** — `cfb-pipeline <…invalid>`, rendering
  unlinked. Working as designed.
- **Cancelled CI on intermediate commits of a multi-commit push** — §1.
- **`Nothing to grade yet (not a failure)`** — `EXIT_NO_CLAIM` (4) is a designed state.
- **`Claim window not open yet`** on a green predict — the D38 gate; correct for any week whose start
  is more than `CLAIM_LEAD_DAYS = 7` away.
- **A `grading:` commit with an empty envelope** — it requires a *claim*, not a graded game.
- **`model_version` reading `v2026-frozen-3-N-g<sha>`** — the build stamp, and the normal post-tag
  form. A bare short SHA means a shallow checkout and the preflight aborts on it.
- **`sp_watch` silent** — both sources sit at the ratified baseline `{"sp_ratings": 139,
  "returning_production": 136}`. It now arms on **any** deviation, including a shrink, so it will
  fire on ordinary CFBD revisions. Owner ruling: accepted as re-described; resolve via
  measure → rule → baseline-update PR carrying `Closes #NN`; interim daily comments are the designed
  nag (`2027_NOTES` §8 item 12).

---

## 6. Reading list, in order

1. **`docs/DECISIONS.md` D38, D39, D40** — the claim gate and weld-shut rule; the composite-output
   defect that would have silently prevented every claim; the selectivity bucketing defect and its
   correction blocks.
2. **`docs/HANDOFF_REHEARSALS.md` §(g)** — the seven generalising lessons, all paid for with defects.
   §(g).1 ("string-presence-in-YAML is not behaviour") predicted D39 exactly.
3. **`docs/2027_NOTES.md` §8 items 18–26** — this tenure's carry-forwards: the grading-commit
   trigger, the sp_watch alarm shape, the grade-stage testability boundary, the tracked-slate scope
   requirement, the cancelled-CI signature.
4. **`docs/PIPELINE.md`** — the operating manual.
5. **`data/predictions/2026_week_01.json`** — read the claim itself. It is the thing the whole
   project exists to produce, and its shape explains most design decisions faster than prose.

---

## 7. Error patterns from this tenure — inherit these, they cost real time

**The five locator errors.** Five times this session a *specific pointer* was asserted from stale or
unverified context, always inside an argument that was substantively correct: a confidence figure
attributed to the wrong population (21 games, not 25); a citation true of one source stated of two;
a line number one off; a render path never traced; and two line numbers invalidated by the fix in
the same commit. **Every one was caught by something independently re-deriving the claim — never by
re-reading the prose**, because the sentence always read perfectly well.

The durable fix is mechanical, not attitudinal: **when a sentence names a specific locator, resolve
that token in isolation against the file it names, in the frame it names.** A script that extracts
every `file:line` from a document and prints what is actually there takes a minute and would have
caught all five. Careful reading caught none of them.

**The merge-into-the-owner's-checkout habit.** Twice this session a `git merge --ff-only` of a
rehearsal branch into the working checkout left the owner's local tree on unexpected content and
snagged his next `git pull`. Rehearsal artifacts belong on their branches; if you need them locally,
read with `git show <ref>:<path>` rather than moving the working tree. **The owner's checkout is not
yours.**

**A pattern worth expecting, not just avoiding.** Three defects this tenure — D39, D40, and today's
red `main` — all fired on the **first execution of a path after a state transition**: the first run
with the claim window open, the first partially-graded render, the first post-kickoff snapshot. The
system is well covered for steady states and thin at transitions. When the season changes state
(first bye week, first postponement, first fully-graded week, week 15 → postseason), **expect a seam
and look for it before it renders.**

---

## 8. What this tenure caught

Recorded plainly, because the record is the product:

- **D39** — `cfb-setup` never declared `claim_window_open`, so every claim gate in
  `weekly-predict.yml` read the empty string and inverted. The pipeline **could not write a claim at
  all**. Found by Rehearsal 2 on 2026-08-24, **one day before** the live run that would have gone
  green and produced nothing. The failure was fail-closed only because D38's seam gate sat in
  `write_predictions()` rather than the caller — its most contested design choice.
- **D40** — the selectivity table rendered "placed bets: 9" over an 11/11 NO_BET claim, because
  `not r.get("is_hypothetical")` read a graded-only field's *absence* as an affirmative placed bet.
  Caught within hours of rendering by the owner reading his own report. The claim, the graded data
  and every immutable tier were untouched; D23 had pre-authorised regeneration in July.

**When the season has run cleanly, delete this file.**
