# HANDOFF → the season (temporary — delete when the season closes)

A briefing for a fresh session with zero conversational context. **Not authoritative over
`docs/SPEC.md`.** Written 2026-09-01 at the retirement of the rehearsals session, which ran from the
Rehearsal-0 boundary through the live claim and the first graded Sunday.

Read this, then `docs/PIPELINE.md`, then the reading list in §6.

**§2's task is DONE — see the banner there. Start at §1.** Eight errors found in this document after
it was written are corrected in place and recorded in **§9**, which also explains why the first pass
that looked for them found only half.

---

## 1. Season state — as of 2026-09-01 13:37 ET

The model is frozen at **`v2026-frozen-3`**. `main` **was** at **`8f7a5ff`** at the timestamp above —
it has moved since (PR #53 `8ee3874`, then this document's own merge); **read `git log origin/main`,
not this line** (C5). `8f7a5ff` was that day's scheduled snapshot
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
| max \|edge\| | **0.1403** (`MIAMI@STANFORD`), against **that game's** `min_edge` floor of **1.00** — see C1 |
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

**Zero open issues.** **Five** PRs merged in this tenure (C6): #45 (README), #46 (record),
#49 (drawer), #50 (D39), #51 (D40). Like every count in §1 this is **as of the timestamp above** —
#52 (this document) and #53 (the §2 fix) merged later the same day and are not counted.

---

## 2. ~~YOUR FIRST TASK~~ — `main` was red; RESOLVED 2026-09-01

> **RESOLVED.** Owner ruling 2026-09-01: **`docs/SPEC.md:371` (SPEC §9 requirement 5) is the
> contract — exit 2 *is* "degraded data", so the CLI was correct and the TESTS were the defect**
> (candidate shape 1 below). Candidate 2 — distinguishing a de-listed *played* game from a line that
> never posted — was ruled a 2027 design note, not a 2026 change; it is `docs/2027_NOTES.md` §8
> item 29. Fixed in **PR #53** (`5cef42c`, merged `8ee3874`): the affected tests are re-premised
> onto the append-only pre-kickoff vehicle rather than the regenerated live bundle, and a new test
> pins the mid-week degraded state. Write-up:
> `docs/pr-summaries/cli_tests_live_snapshot_pr_summary.md`.
>
> **The diagnosis below is left as written** — it is the record of how the defect was read, and its
> two candidate shapes are what the ruling chose between. Two things it did not know:
>
> 1. There are **two** independent snapshot reads — `cli.cfb` enumerates via
>    `data.snapshot.store.load_snapshot`, the frozen engine prices via
>    `data.data_manager.load_snapshot` (`data/data_manager.py:70`, bound at import so a store-level
>    patch never reaches it). Pinning one gives a **split read** that looks correct;
>    `scripts/slate_fingerprint.py::engine_reads` exists to prevent exactly that.
> 2. The same defect class held **three more** instances, two of them dated: the `CLEMSON @ LSU`
>    slate-membership assertions (would break after its 2026-09-05 kickoff) and
>    `_partial_week_join`'s `0 < graded < total` guard (would invert on 2026-09-13 when week 1
>    finished grading). All fixed in the same PR; the sweep is in the write-up and the class is
>    `2027_NOTES` §8 item 28.

**Run `33537284634`, push of `8f7a5ff`, conclusion `failure`.** Every job fails (`test`,
`verify (0)`, `(1)`, `(2)`, `(4)`, `(4-5)`, `(5)`, `verify-freeze`) because they all run the suite —
that is the whole `ci.yml:52` matrix; there is no `verify (3)`, phase 3 being `verify-freeze`'s job
(C7). **Four tests, one cause:**

Line numbers below are **as at `8f7a5ff`** — the fix moved them (C2, C3):

```
tests/test_cfb_cli.py:111  test_slate_returns_ok_when_all_games_have_lines
      E  assert 2 == 0   +  where 2 = cfb.main(['slate', '1', '--format', 'json'])
tests/test_cfb_cli.py:47   test_omitted_week_equals_explicit_week
      E  assert 2 == 0   +  where 2 = cfb.main(['predict', 'week', '--format', 'json'])
tests/test_cfb_cli.py:69   test_offline_rerun_identical_to_predict_week
      E  assert 2 == 0   +  where 2 = cfb.main(['predict', 'week', '1', '--format', 'json'])
tests/test_cfb_cli.py:137  test_predict_week_save_refuses_overwrite_d22
      E  assert 2 == 0   +  where 2 = cfb.main(['predict', 'week', '1', '--save', '--format', 'json'])
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
degraded exit for this case, meaning the tests are what should change? `cli/cfb.py:6` and `:103`
document the intent, but **find and cite the SPEC / CLI-docs statement of the exit-code contract
before proposing either fix.** (C4: this originally cited `cli/cfb.py:10`, which is the *week
inference* exit 2, a different condition. The contract itself turned out to be `docs/SPEC.md:371`,
SPEC §9 requirement 5.) The two candidate shapes:

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

---

## 9. Corrections to this document (added 2026-09-01, after §8 was written)

§7 prescribes resolving every `file:line` mechanically against the file it names before publishing.
That check was run against **this document** before it merged, and found four errors it had missed —
all four of the same shape §7 describes: **a specific locator or figure asserted inside a sentence
that reads perfectly well.** Careful reading found none of them; a script that resolved each token
in isolation found all four in about a minute. Each is corrected in place above and recorded here
with what it replaced, per D40's supersede-don't-silently-edit convention.

**Frames are pinned** because PR #53 moved the very line numbers §2 cites: a `tests/test_cfb_cli.py`
line number in this document means **as at `8f7a5ff`** unless it says otherwise.

| # | Where | Was | Is | Why it was wrong |
|---|---|---|---|---|
| **C1** | §1 slate table | "max \|edge\| **0.1403**, against a `min_edge` threshold of **1.50**" | "**0.1403** (`MIAMI@STANFORD`), against **that game's** floor of **1.00**" | The floor is not one number. `engine/prediction_engine.py:271-276` (at `8f7a5ff`) picks it per game from factor activation — **0.75** when `primary_signals >= 2 and avg_confidence >= 0.7`, **1.00** when `primary_signals >= 1 or avg_confidence >= 0.6`, else **1.50**. The claim's own `no_bet_reason` strings record the split: **1.50 ×7, 1.00 ×3, 0.75 ×1**. The slate's *maximum* edge was measured against **1.00**, so the one figure and the one threshold quoted together never applied to the same game. Carried forward as `2027_NOTES` §8 item 30. |
| **C2** | §2 test list | `test_predict_week_save_refuses_overwrite_d` | `test_predict_week_save_refuses_overwrite_d22` | Truncated name — would not match a `pytest -k` or a grep. |
| **C3** | §2 code block | one `AssertionError` block printed under all four test names, showing `2 = cfb.main(['slate', '1', ...])` | each test shown with **its own** failing call and line | That call belongs only to `test_slate_returns_ok_when_all_games_have_lines` (`:111`). The other three fail on `predict week` variants at `:47`, `:69`, `:137`. One cause, four call sites — the block implied one. |
| **C4** | §2, the un-ruled question | "`cli/cfb.py:10` and `:103` document the intent" | "`cli/cfb.py:6` and `:103`" | `:10` is *"out-of-season → exit 2, never a guess"* — the **week-inference** exit 2 (SPEC §9.1), a different condition. The degraded-data intent is `:6`, *"returns a meaningful exit code (0 ok / 1 error / 2 degraded data)"*. Both lines are identical at `8f7a5ff` and at merge. This mattered more than the others: it was the citation offered as evidence *of the exit-code contract*, in the sentence demanding that contract be cited. The actual contract is **`docs/SPEC.md:371`**. |

**Also changed, and flagged as beyond the four:** §2's heading and the pointer at the top of this
document, which told a context-free reader their first task was a red `main`. That was true when
written and false by the time this merged. The diagnosis in §2 is untouched.

### Second round — C5–C8, found by review *after* this document had already merged

The C1–C4 pass above missed things, and an independent `code-reviewer` audit commissioned over
**every** claim in the document caught them. That audit returned **after** PR #52 merged (merge
`e067744`, 18:32 UTC; the audit finished later), so for a short window `main` carried a successor's
entry-point document with two known errors in it. Recorded plainly because the sequencing is the
lesson: **a review that lands after the merge protects nothing.** These landed as a follow-up.

| # | Where | Was | Is | Why it was wrong |
|---|---|---|---|---|
| **C5** | §1, opening | "`main` is at **`8f7a5ff`**" | "`main` **was** at `8f7a5ff` at the timestamp above … read `git log origin/main`, not this line" | Exactly the defect C1–C4's pass had just rewritten §2's heading to fix — *true when written, false by merge* — left standing in §1, the section the top-of-document pointer sends the reader to **first**. `main` had already moved to `8ee3874`, and §2's RESOLVED banner — added in the same pass — **cites that very SHA**. The fact was in hand and was not propagated. |
| **C6** | §1, closing | "**Six** PRs merged in this tenure" followed by **five** entries | "**Five**" | A count contradicting its own enumeration one clause later. `gh pr list` confirms five merged in the tenure window (#45, #46, #49, #50, #51); #47/#48 do not exist, #52 was open, #53 merged after the stated timestamp. Not a locator error — a claim nobody counted. |
| **C7** | §2 | "`verify (0)`–`(5)`" | the six matrix jobs named individually | Range notation implying a contiguous `verify (0)`…`(5)`. The `ci.yml:52` matrix is `["0","1","2","4","4-5","5"]`: there is no `verify (3)` (phase 3 is `verify-freeze`'s job) and `verify (4-5)` is a distinct job, not an endpoint. Substance was right — all matrix jobs did fail. |
| **C8** | `docs/pr-summaries/cli_tests_live_snapshot_pr_summary.md` | "Status: open, awaiting owner merge" | merged, with both reviewer verdicts and the merge commit | Cross-document staleness in a file this document points readers at. |

**What the two rounds together actually teach.** Round one resolved every `file:line` mechanically
and found four errors; round two found four more that the first pass **could not** have caught,
because none of C5–C8 is a `file:line` — they are a stale SHA, a miscount, a loose range, and a
status header. §7's prescription is necessary and it is not sufficient: *"resolve every locator"*
catches pointer rot, and misses **every claim that has no pointer to resolve**. Before publishing,
run both passes — resolve the locators, then re-derive the bare assertions: counts, dates, SHAs,
statuses, and anything phrased in the present tense about a moving reference.

**The lesson stands and is now doubly paid for.** §7 was written *because* five locator errors got
through this tenure; four more were in the document making the point. The durable fix is not
attitudinal, it is a script — extract every `file:line`, print what is actually there, in the frame
named. Run it on anything with citations before it merges, including a document about running it.

---

**When the season has run cleanly, delete this file.**
