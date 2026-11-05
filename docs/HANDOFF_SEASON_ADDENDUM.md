# HANDOFF_SEASON addendum — state at 2026-09-13 (read this FIRST, then confirm back against it)

A context-free successor reads this file before anything else and **confirms each item back to the
owner** before acting. Written at a context compaction; it records owner rulings from 2026-09-13 that
exist nowhere else in the repository yet. **Not authoritative over `docs/SPEC.md` or
`docs/DECISIONS.md`.** Frame: `main` at **`043be6a`** unless a line says otherwise. Then read
`docs/HANDOFF_SEASON.md` (updated by #59) and `docs/DECISIONS.md` D41–D42.

**Merged unreviewed, then audited.** This file merged as #61 (`bfdd025`) before its `code-reviewer`
verdict, the second such inversion after #52. A post-merge audit found errors and stale statuses. They
are corrected in place and recorded as **C10–C14 in `docs/HANDOFF_SEASON.md` §9, fourth round**.

---

## 1. State at the time of writing

- `main` = **`043be6a`**. Merged today: **#59** (PR A, docs: D42, shutdown ruling, measured cadence,
  graded-week README) as `9559b0a`; **#60** (PR B, pipeline: CLV sign gate in `weekly-grade`, report
  commit message names every changed report, #51 regression test, fingerprint payload tripwires,
  `leans | graded` column split) as `043be6a`.
- `reports/2026_week_02.md` reads 16/16 graded; `reports/2026_week_01.md` reached 11/11 in `535d2b9`.
  All 19 graded leans across weeks 1–2 pass the two-check CLV sign test (#60).
- ~~`stash@{0}` "pre-review-stash-retro" still exists~~ — **dropped after this was written**, per
  ruling 1 (C12). `git stash list` is empty. Its commit survives unreferenced as `0bcd378`, and it
  holds only `reports/2025_retro.md`: the index and untracked-files parents are both empty.
- **Tuesday 2026-09-15: the week-3 claim runs on schedule regardless of anything below.**

## 2. Owner rulings, 2026-09-13

1. **`reports/2025_retro.md` stays as-is.** The defect is not the stale retro — it is that
   `scripts/verify_phase_4.py` **writes to a committed path** (`reports/2025_retro.md`) as a side
   effect of its acceptance check. Remedy: render to a **temp path and compare**, never write into
   `reports/`. **No hand-render.** **The stash is to be dropped** — it holds only that side-effect
   copy of the retro and belongs to no PR. (Not yet dropped when this was written; dropped since — C12.)
2. **CLV gate into `weekly-predict`'s Tuesday catch-up**, before its `data/graded` commit — the
   same two-check validator #60 put in `weekly-grade` (`scripts/check_clv.py`). This is **PR D**, and
   it must **land before 2026-09-22**. Reason: the catch-up grades weeks and commits append-only
   `data/graded` with no sign check; that is how week 1 closed at 11/11.
3. **`_lean_cell` wording → the drawer** (`docs/2027_NOTES.md`), not a fix now. `_lean_cell` keys
   "no games graded on this side yet" off `n_graded` (wins + losses, excludes pushes), so an all-push
   side would claim nothing was graded.
4. **"Will it ever bet" — measurement population = the 338-game vehicle + the live graded weeks**,
   with **2025 as labelled, non-comparable context only.** Reason: the 2025 archive holds the
   *predecessor* model's predictions and there are no 2025 snapshots to re-run the frozen engine over,
   so the 90.7%-of-vehicle-ceiling threshold cannot be applied to 2025 for this model.

## 3. Queue, in order

**Queue as ruled 2026-09-15 — this supersedes the numbered list below** (orientation update per
D42 (a)1). **D44 is ratified** (proposal #65):

* **The D44 workflow PR** — cadence, `season.json`, guard fix, tiers 0–2. Merges before
  **Wed 2026-09-23**.
* **The D44 report PR** — close-age buckets, the week-4 boundary, no cross-boundary season blend,
  tiers 3–4. Merges before **Sun 2026-09-27 12:47 ET**.
* **D45, the claim-path ruling** — exclude any game whose scheduled kickoff precedes the claim run
  plus a margin, and list each exclusion in the claim's meta with its reason. A Tuesday game with no
  post-claim observation gets `closing_spread` null with a reason, never a zero CLV. Implementation
  PR before **2026-10-06**, with a GO before merge.
* Then the proposals for **variance/tier visibility**, **CFBD retry** and **feasibility**.

**Appended 2026-09-28 — correction to the queue above, which is record and is not edited.** All
three dated items have since landed: the D44 workflow PR as #66, the report PR as #68 (merged
2026-09-27 23:04 ET, after its deadline moved to 10-04), and D46 as #67. **D45's 2026-10-06 deadline
is withdrawn and it is now undated** (owner, 2026-09-28). The date, and the "Tuesday game" it was
built around, rested on a premise this document also carries at §3's D44-candidate bullet below —
*"Tuesday games from week 6"* — which is **false**: the tracked slate is P4 + Notre Dame (68 teams),
it plays Thursday/Friday/Saturday, and it has no Tuesday games at all. The premise entered from
`ADVISOR_HANDOFF_4`, carried unverified, and was never checked against `data/team_registry.py`, which
is the authority for any slate question. The full re-derivation, including why the exposure now needs
a predict **58+ hours** late rather than the hours implied by a Tuesday kickoff, is in `DECISIONS.md`
D46 §(1), appended the same day. D45 itself is unchanged in shape and stays queued as insurance.

The list below is the earlier order, kept for the record.

1. **PR C — `resolve_locators` as a make target** (D42 (a)3). The `LINT_PATHS` conflict with #60 is
   cleared now that #60 is merged. ~~Blocked on a source (C13)~~ — **ruled 2026-09-13 (D43 (b)):** the
   tool exists nowhere, in the repository or in any scratchpad, so PR C **builds it** from the
   three-axis specification (exists / says what the document claims / reachable). It comes after PR D.
   **Built** as `make resolve-locators DOC=…` (`scripts/resolve_locators.py`). The appended rulings and
   measured limits are in D43. **Merged as #64 (`0876a6e`).** Its two known limits were ruled on
   2026-09-14 and are documented in the tool's docstring, with the proper fix as drawer item 32.
2. **PR D — CLV gate in `weekly-predict`'s catch-up** (ruling 2). **Deadline: before 2026-09-22.**
   **Taken first, ahead of PR C, by owner ruling 2026-09-13**, and it also carries D43. **Merged as #63
   (`5eb8453`).** The fail-closed design stands, with the narrower shape recorded as rejected (D43, appended).
3. **Then four proposals for the owner's ruling — proposals, not PRs:**
   - **D44 candidate** (was "D43" before D43 was taken, 2026-09-13) **— cron cadence**, with an **escalation path for the timing guard.**
     **Filed as `docs/proposals/D44_CRON_CADENCE.md` (2026-09-14)**, which supersedes the figures in this
     bullet. The measurement widened the defect: 13 of 21 missed captures logged "ok", including a
     cross-midnight case, and every Sunday grade warns. It also found two seams: Tuesday games from
     week 6, and no pre-kickoff filter on the claim path. Measured
     lateness is in `docs/HANDOFF_SEASON.md` §1. Note the guard is not merely unescalated: `check_timing`
     (`scripts/pipeline_preflight.py:128` at `535d2b9`, same line at `bfdd025`) counts slack against
     the first kickoff window still ahead **today**, not the window a run was scheduled to precede.
     It warns only when a run is past every one of today's windows (`:144`). So it logged healthy
     slack on all four week-2 Saturday captures and warned on none (C14).
   - **Variance/tier visibility** — ruled to be selectivity attribution. (`no_bet_reason` does not
     appear in `analytics/reports.py` at `043be6a`.)
   - **CFBD retry.**
   - **Feasibility analysis ("will it ever bet")** — on ruling 4's population. Dense proposals go to
     `docs/proposals/` as files (CLAUDE.md).

## 4. Open items — not ruled

- **`freeze-integrity`'s fate past 2026-12-13.** D42 (b) rules the three cadence crons stop after the
  final regular-season grade (Sunday 2026-12-13); the daily integrity check is explicitly left open.
- **Report commit-message template.** #60 labels the commit from the changed report files
  (`scripts/changed_report_weeks.py`); the template itself is not ruled.
- **`verify-phase-4`'s side-effect write** to `reports/2025_retro.md` — ruled a defect with its remedy
  (ruling 1); not yet placed in the queue above.

## 5. Doctrines a successor must not relearn the hard way

- **Green CI is not a GO.** Never report a PR ready while its `code-reviewer` verdict is outstanding
  (D42 (a)4). The GO must cover the final diff at branch head (`docs/HANDOFF_SEASON.md` §4;
  `docs/HANDOFF_REHEARSALS.md:274`). Record the verdict and the reviewed SHA in the PR body or in
  `docs/pr-summaries/` (`docs/HANDOFF_REHEARSALS.md:79-85`). C11: this line originally cited all
  three to D42 (a)4.
- **Expect a seam at every state transition** (`docs/HANDOFF_SEASON.md` §7). Transitions still ahead
  at 2026-09-13: the first bye week; the first postponement; the first runs after the
  **2026-11-01** EST flip, when the UTC crons land an hour earlier in ET (`season.json`
  `pipeline.dst_note`); and the **week-15 end of schedule**, with the last grade on
  **Sun 2026-12-13** (D42 (b)). Two changes from §7's list: it predates D42 (b), which rules out the
  postseason, and the first fully-graded week has already happened. Also ahead: **Sun 2026-09-20** is
  the first scheduled `weekly-grade` since #60. That run is the first live `check_clv.py` gate, the
  first render with the `leans | graded` split (the committed reports still show `games`), and the
  first `changed_report_weeks.py` label.
- **A background reviewer can run git and tests in the shared working tree, and telling it not to
  does not work.** The mechanism, measured after it happened three times (2026-09-13, and twice on
  2026-09-23): a subagent's shell resets its working directory between calls, so a chained
  `cd <clone> && git …` runs that git command **in this checkout** the moment the `cd` fails — and a
  failed `cd` inside a chain is silent. The first left a `git stash` here (§1); the other two left
  stray branches and a moved `HEAD`, each after a prompt that explicitly demanded an isolated clone.
  Nothing was lost in any of them, but each needed restoring by hand. **The fix is structural, not a
  stronger instruction:** build the clone yourself before spawning the reviewer (`git clone --branch`
  avoids a `git checkout <sha>` the bash hook blocks), hand over the absolute path, require
  `git -C "<path>" …` for every git command, and ban `cd` and every writing git verb — `checkout`,
  `switch`, `branch`, `stash`, `reset` — everywhere, clone included. A reviewer already at the right
  commit needs none of them. Then check this tree afterwards rather than trusting the report.
- **Prose claims are re-derived, not proofread** (D42 (d)): resolve every locator, then separately
  re-derive every count, date, SHA and status. Every error caught this tenure was caught that way.
- **No AI attribution** in commits or PR text (D3). Freeze untouched: `factors/`, `engine/`.

### The season's remaining dated obligations (appended 2026-10-01, revised 2026-11-05 for D48)

So a successor reads the calendar rather than reconstructing it:

| when | what |
|---|---|
| **2026-11-01 — HAPPENED, and it moved every slot** | the EST flip. The crons are single UTC expressions anchored to EDT, so from this date each fires **an hour earlier in ET**: `43 11 * * *` is now **06:43 ET**, not the 07:43 ET written beside it in `freeze-integrity.yml` and in `HANDOFF_SEASON` §1's cadence table. Those stated ET times are EDT times and are now an hour fast; the cron expressions themselves are correct and unchanged (`season.json` `pipeline.dst_note` is the design note). Live until the stop PR merges |
| **Sun 2026-11-29** | the **D48 November batch** is on `main` by this date: the probe kind, the CFBD retry, the catch-up narrowing and the docs |
| **Sun 2026-12-13** | the final regular-season grade (D42 (b)). **The owner merges the season-stop PR after this grade lands** — it is prepared, reviewed and held open, not merged early, because merging it first would stop the grade it is waiting for |
| **Tue 2026-12-15, 09:00 ET** | the deadline for that merge. Past it the pipeline is still safe — `pipeline_week` clamps to 15, the claim is welded, outcomes are idempotent — but it spends Odds credits and CI minutes on a season that has ended (D48's recorded fallback) |
| **Sun 2026-12-20** | **D47, the post-season threshold analysis** — `scripts/threshold_sweep.py` + `docs/analysis/2026_THRESHOLD_SWEEP.md`, one week after the final grade. Ruled 2026-10-01; nothing about the 2026 model changes, the zero-bet result is the pre-registered outcome |
| undated | **D45**, the claim-path ruling — queued as insurance, no deadline (its 10-06 date was withdrawn); the margin and its reference timestamp are still unruled |

What `freeze-integrity` does after 2026-12-13 is **answered by D48**: it stops with the other three.
Whether anything should watch for a *missing* run of it is in the drawer, not this batch.

**The crons are still running as this is written (2026-11-05).** D48's stop PR is prepared, reviewed
and held open; nothing in that ruling's §(1) is true of `main` until the owner merges it after the
12-13 grade.

---

# Generation 4 handoff — written 2026-11-05, owner-called at a quiet moment

This section is appended by the generation that read §§1–5 above as its own briefing on 2026-09-13
and worked through 2026-11-05. It merges **ahead of its review under D43 (a)**, so — exactly as D43
requires — **your first task is the post-merge audit of this section, with a fix-forward, before
anything else.** Not CI, not the next feature. D43's condition moves the review; it does not remove
it.

**Read this section as claims to verify, not as state.** Everything below was queried from the
repository, `gh`, or the Actions API at the time of writing and is marked **(u)** where it was not.
A figure here that disagrees with the repository means the repository is right.

## G4.1 State at 2026-11-05 22:00 UTC

| | |
|---|---|
| `main` head | **`f56a243`** — "Merge pull request #75 from Brandon12200/pipeline/nov-batch", a true merge commit (parents `d6c5267` + `72d1a3d`) |
| CI on that head | **success**, run created 2026-11-05T21:51:49Z (`push`) |
| open PRs | exactly one: **#76** |
| freeze tag | `v2026-frozen-3`; `factors/` and `engine/` untouched this tenure |
| `DECISIONS.md` | **49** `## D` entries; the last is **D48** (2026-11-05) |
| latest claimed week | week 10; `data/predictions/2026_week_10.json` committed as `1bacd90` |
| latest graded week | week 10 is **claimed but not yet graded** — `grade_weeks = 1 … 10`, `catchup_weeks = 10` |

### PR #76 — the season stop, HELD OPEN

- Branch **`pipeline/season-stop-v7`**, head **`9e5e069`**, base `main`.
- **`code-reviewer`: GO for `9e5e069`**, that exact SHA, quoted in the PR body. No blockers, no
  should-fixes.
- It carries **four** commits of its own — `5874279`, `88f2a6b`, `3d99b10`, `9e5e069` — over eleven
  files. GitHub's PR view shows **eleven commits and 19 files** and will keep showing them: it is
  not a recompute lag. *(Corrected by the G5 audit.)* The PR's stored `base.sha` is still
  `d6c5267`, recorded when it opened, and it had not refreshed by the time of this audit. By
  2026-11-05 22:20 UTC `mergeable` had already settled to `MERGEABLE` / `clean`, and
  `gh api repos/Brandon12200/cfb-predictor-2026/compare/main...9e5e069` gave **ahead 4, behind 3, 11
  files, merge base `72d1a3d`**. The truth is `git log origin/main..9e5e069` or that compare call.
  The PR page's counts are not.
- **It is not a deletions-only PR.** Besides the four `schedule:` blocks it adds
  `scripts/workflow_triggers.py` (a new module, test/verifier-only — its importers are
  `tests/test_workflow_schedules.py` and `scripts/verify_phase_5.py`, plus the `Makefile` path
  lists; **no workflow job imports it**), inverts both anti-drift guards, rewrites nine passages of
  `docs/PIPELINE.md`, and touches `.github/actions/cfb-setup/action.yml` — **comment only**, zero
  non-comment lines in the diff, mode-derivation shell byte-identical.

**The merge-day procedure, in order. Do not shorten it.**

1. `git fetch origin` first, before any other git command.
2. `gh pr view 76` — read the state from GitHub, do not assume it is still open.
3. **The D46 §(4).2 base-movement check.** A GO survives base movement only when `main` moved in
   files **disjoint** from the diff:
   ```
   git diff --name-only 72d1a3d origin/main
   git diff --name-only 72d1a3d 9e5e069
   comm -12 <(git diff --name-only 72d1a3d origin/main | sort) \
            <(git diff --name-only 72d1a3d 9e5e069 | sort)
   ```
   `72d1a3d` is the reviewed base. **Empty overlap ⇒ the GO stands.** Any overlap voids it and needs
   a fresh `code-reviewer` pass at the head, which in December is under deadline — so run this
   *before* the grade if you want warning. Baseline run 2026-11-05 at `f56a243`: `main` had moved
   in zero files, overlap empty. **Re-run 2026-11-05 at `8b7af00` (G5 audit):** `main` had moved in
   one file, `docs/HANDOFF_SEASON_ADDENDUM.md` (this section's own merge, #77), and the overlap was
   empty, so the GO stands. Expect movement under `data/` (daily `lines:` commits, the weekly claim
   and grade) **and under `docs/HANDOFF_*`** (handoffs and their audits, this one included). Both
   are disjoint from all eleven files. *(Corrected by the G5 audit: the original said "only under
   `data/`", and the merge that carried that sentence was itself a counter-example.)* **But run it;
   do not reason that it must be fine.** The owner ruled this check and asked for it to be reported.
4. **Merge with a merge commit.** #75 landed as one, which is why the stack's base is on `main`:
   `72d1a3d` (the parent of #76's first commit `5874279`) is `f56a243`'s second parent.
   *(Corrected by the G5 audit: the original said "`9e5e069`'s parent". That parent is `3d99b10`,
   which is on #76's branch, not on `main`.)*
   A squash here is harmless to #76 itself (nothing is stacked on it) but breaks the repo's
   practice; PRs #63–#70 and #75 all landed as merge commits and no squash-merged title appears in
   `main`'s history.
5. **Window: after the 2026-12-13 grade lands, before Tue 2026-12-15 09:00 ET.** Not before the
   grade — merging first would stop the grade it is waiting for. Past the deadline nothing breaks
   (see D48 §(1)'s recorded fallback) but credits and CI minutes are spent on an ended season.

### D47 — the one unbuilt deliverable

Due **Sun 2026-12-20**, ruled 2026-10-01. Spec: **`docs/DECISIONS.md` D47, at line 1388**, which
names both artifacts — **`scripts/threshold_sweep.py`** and
**`docs/analysis/2026_THRESHOLD_SWEEP.md`**. Neither exists yet; `make resolve-locators
DOC=docs/HANDOFF_SEASON_ADDENDUM.md` reports both as MISSING at `:154`, and that is **expected**,
not a defect to fix. Read D47 itself rather than this paragraph: it fixes the method, the pre-
registered framing ("the zero-bet result is the outcome, not a failure to be tuned away"), and the
two corrections the owner's own ruling needed — the field is **`ats_result`**, not `ats_outcome`,
and the win-return convention is **`analytics.kpis.WIN_RETURN = 0.909`**, not "+0.91".

## G4.2 The calendar, and what runs for the first time at each point

The dated table in §5 above ("The season's remaining dated obligations") is the calendar and was
revised for D48 on 2026-11-05. This subsection adds only **what is newly exercised** at each point,
because D48's code merged **after** today's scheduled runs: the merge was 21:51:46Z and the last
scheduled run before it was `Freeze integrity (daily)` at 18:57:11Z. **As of this writing no
scheduled job has ever run the D48 code.** The only run on `f56a243` is CI.

| when (UTC) | what fires | first time for |
|---|---|---|
| **Fri 2026-11-06 11:43** | `freeze-integrity` | **the probe kind and the CFBD retry** — `sp_watch` is the only daily CFBD caller |
| Fri 2026-11-06 16:50, 21:23 | `daily-capture` | nothing new: capture spends the **Odds** API, not CFBD |
| **Sun 2026-11-08 16:47** | `weekly-grade` | the CFBD retry in `fetch_results`; week 10 is graded |
| **Tue 2026-11-10 13:17** | `weekly-predict` | **the narrowed catch-up**, and the retry in `build_snapshot` |
| Sun 2026-11-29 | — | D48's own deadline, already met by #75 |
| Sun 2026-12-13 16:47 | `weekly-grade` | the final regular-season grade (D42 (b)) |
| after it, before Tue 12-15 09:00 ET | — | the owner merges #76 |
| Sun 2026-12-20 | — | D47 due |

**The log lines to read, by name.** All are per-job logs — read the job, never the concatenated run
log, and remember the attempts rule in G4.3.

- **Probe kind.** In `freeze-integrity`'s job `integrity`: step **"SP+ / returning-production
  watch"** (`id: spwatch`) writes `rc=<n>` to `$GITHUB_OUTPUT`; step **"Fail on a probe error"**
  emits `::error::sp_watch exited <rc>`. A probe outage must now open an issue titled **"CFBD probe
  unreachable — sp_watch could not observe SP+/returning production"** with label `kind: probe` —
  **not** "pipeline: freeze failure", which is what three outages this season wrongly produced. The
  job still goes red. Exits 0 and 2 are unchanged, and exit 2 is the designed "SP+ has arrived"
  state with its own `kind: transition` issue.
- **CFBD retry.** Any job using the client logs, at WARNING, **`CFBD GET <path> failed (<error>);
  retrying once in 2.0s`**. Its presence in a run that then **succeeds** is the only evidence the
  outage happened — that is why it is WARNING and not DEBUG. Two of those lines for one path means
  the retry was spent and the call still failed. 4xx never retries.
- **Narrowed catch-up.** In `weekly-predict`, the step `id: setup` runs the composite action
  `.github/actions/cfb-setup`. Inside it, step **"Resolve week"** (`id: resolve`,
  `.github/actions/cfb-setup/action.yml:127`) pipes `scripts/pipeline_week.py` through
  `tee -a "$GITHUB_OUTPUT"`, so the setup step's log shows both **`grade_weeks=…`** and
  **`catchup_weeks=…`**. The workflow reads the result as `steps.setup.outputs.catchup_weeks`.
  *(Corrected by the G5 audit: the original named the step "Resolve the week" and placed it in
  `weekly-predict.yml` itself. No step by that name exists.)* The step **"Catch-up grade (Sunday/Monday
  finishers + postponements)"** iterates `catchup_weeks` only. On 2026-11-10 expect `grade_weeks` to list every
  claimed week that is gradable and `catchup_weeks` to be **much shorter**; one CFBD call per week
  iterated is the cost the narrowing removes. Today, on `main`, they are `1 2 3 4 5 6 7 8 9 10` and
  `10`. `weekly-grade` deliberately still uses the full `grade_weeks`
  for its render (#58's self-healing property).

## G4.3 Rules, as rules

These are not preferences. Each exists because something went wrong without it.

1. **`git fetch origin` is the first command of any turn that mentions `main`, a PR, or a merge** —
   before any other git command, no exceptions. Owner-imposed after **three** wrong statements about
   `main`'s state (#68, #69, #70).
2. **Query the thing itself, every time.** `gh pr view`, `gh run view`, `gh api`. Never carry a PR's
   state forward from earlier in a conversation, and **never infer state from not having heard
   otherwise** — the third violation above was not a stale ref but a remembered answer. Silence is
   not evidence.
3. **Reviewers get a pre-built clone.** A subagent's working directory **resets between tool
   calls**, so a failed `cd` runs git in the owner's checkout. Build the clone yourself, hand over
   an **absolute path**, require every command be spelled `git -C <that path> <verb>`, and ban `cd`
   and every writing git verb. Telling a reviewer to clone for itself has failed three times
   (2026-09-13, and twice on 09-23 — **(u)**, dates carried from memory, not re-queried).
4. **Per-attempt truth comes from the attempts API.** `gh run view` and the top-level runs API
   return the **latest attempt**, so a run whose attempt 1 failed and whose attempt 2 was re-run
   reads as a clean success. Query `/actions/runs/<id>/attempts/<n>`. **A run with more than one
   attempt has no single conclusion.** #55 recorded this and an independent review of the D48 batch
   fell into it anyway, disputing a true owner account of run `37365254988`.
5. **Commit messages are written from a file**, `git commit -F <path>`, never `-m`. `zsh`
   command-substituted the backticks inside a `-m` body and silently blanked three phrases of
   `66f3313`. Amend-plus-force-push was refused as destructive, which is also the right rule.
6. **Dense proposals go to `docs/proposals/` as a file; PR summaries to `docs/pr-summaries/`.** The
   terminal reply points at the file. Tables garble in paste transit.
7. **Prose claims are re-derived, not proofread** (D42 (d)), and `make resolve-locators` is **half a
   tool** (D43 (b)): it checks file, line and SHA locators — it does not check a count, a date, a
   draft tally or a cross-reference like "the paragraph after next". Every error this tenure was
   caught by the second pass, never the first.
8. **No AI attribution** in commit messages or PR text; `includeCoAuthoredBy` stays `false` (D3).

## G4.4 Ledger — every error this tenure, and what caught it

Recorded because the pattern matters more than the items: **of the errors below, none was caught by
a test or by CI.** Review and re-derivation caught all of them.

### The delay-band paragraph — four successive wrong drafts of one paragraph

Worth its own heading as the tenure's worst single artifact. **It started from the owner's own
figure**: the record-only ruling of 2026-10-05 stated "8 h is the longest scheduler delay measured;
the band is now 1.5–8 h". That was right about the run in front of it — `37365254988` is **8.01 h**
late — and wrong in calling it the longest; the 1.5 h lower bound was never re-derived by anyone.
The drafts, in order:

| draft | SHA | what it said | what caught it |
|---|---|---|---|
| 1 | `0390df7` | "Across the season it is 1.5–8 h" — the owner's figure, carried | an independent read-only review of the batch |
| 2 | `bd147fb` | "**The season maximum is 9.15 h**" — false, and it contradicted `HANDOFF_SEASON`'s own table two lines above, which said 9.8 h | `code-reviewer`, NO-GO |
| 3 | `245aeb6` | fixed the ranking, left the table's cells printing the superseded values the note said had moved | `code-reviewer`, should-fix |
| 4 | `d6620d4`–`120f5d2` | stated the draft count in **two** places, which disagreed ("two" vs "three") | `code-reviewer`, NO-GO at `120f5d2`, having missed it on two earlier passes and said so |

Measured truth, from all 90 scheduled `freeze-integrity` runs against the unchanged 11:43 UTC slot:
largest **9.79 h** (`33212867178`, 08-28), then 9.59, **9.15** (`41523134721`, 11-02 — largest since
08-29, **third** of the season), 8.70, 8.01, 7.24. Since 08-29: predict 3.99–6.85 h (n=10), grade
1.88–4.07 (n=10), freeze-integrity 2.28–9.15 (n=69).

**And the finding that came out of chasing it: capture's delay is not measurable at all.** Capture
runs carry no `github.event.schedule`, so pairing is by nearest preceding slot — and D44 pins 30
minutes as the minimum gap between two slots on a day, which two Saturday pairs sit at. A wave 31
minutes late pairs to the **next** slot and reports a near-zero delay. 2026-10-10: seven capture
runs against eight Saturday slots, `17:29:07Z` and `17:54:16Z` both pairing to `50 16` while `50 9`,
`50 12` and `20 16` pair to nothing. The error only ever **understates** lateness, so capture's
figures are *unverifiable rather than wrong*, and the `all four` row's **first**-column lower bound
(1.6 h) is capture's and goes with them. The second column's 0.3 h is freeze-integrity's own.

### Everything else

**Mine, caught by review:**

- **"#73 was closed as recovered"** — false. #73 was *created* 2026-10-22 by run `39810193934` and
  is itself a fourth probe outage. What actually happened is sharper: `clear-failure` keys on
  **labels**, so attempt 4 of the 10-21 run (`39631525799`, started 10-23 04:58) closed an issue a
  different run had opened the day before. A real freeze alarm cleared by a probe recovery is
  **latent, not demonstrated**. The CFBD fault count was also wrong: **four** (#56, #71, #72, #73),
  three of them the probe, and only #71 ever blocked a claim. Both corrected in `bd147fb`.
- **An alarm hole of my own making** — the tripwire steps run under `!cancelled()`, so a probe error
  *plus* a tripwire error filed the probe issue and **suppressed** the generic one; a missing claim
  would have gone unreported behind a CFBD outage. Gate widened, mutation-checked.
- **A test that could not fail** — `sum([x, not x]) == 1`, true for every bool, never read the
  workflow. Replaced with one that parses both real gate strings and evaluates them over every
  combination.
- **Both handoffs described the stop as done** while the crons had six weeks to run — and the
  addendum had the EST-flip row struck out as moot when the flip happened 11-01 and is **live**.
- **The stop's own guards had three holes**, each found by review, none by the tests, because the
  stop inverts the rule into *"no cron exists"* — the one direction where a parser bug reports
  success: an **unquoted** cron (`- cron: 1 2 * * 3`), a **column-0 comment** truncating the `on:`
  block and hiding everything below it, and a **quoted key** (`"push":`) or `- push` list item
  escaping the dispatch-only check. All closed in one shared parser, nine shapes mutation-checked
  against the real workflow file.
- **A cross-reference two paragraphs short**, and the duplicate draft count above.

**Mine, caught by me:**

- **Comment-bleed, three times in this tenure**: my own comments matched my own selectors
  (`kind: transition`, `cancel-in-progress: true`, `schedule:` inside a verification script). Four
  times across the project's history. Strip comments, or assert on YAML keys.
- **A mutation-check script was SIGKILLed** partway through and left `freeze-integrity.yml` mutated
  in the working tree — its restore was in a `finally`, which SIGKILL does not run. Caught by
  `git status` before any commit; restored from `HEAD`, byte-identical, and verified independently
  by the reviewer at every commit on the branch. Rewritten to restore **before** the first mutation
  as well as after the last.
- **A wrong verification command handed to a reviewer** ("this diff should be empty" — it should
  have equalled the base's own commit), corrected within the minute; and the wrong diff base used
  twice while verifying a rebuild, caught by the diff itself failing.
- **"20 cases"** claimed for `tests/test_probe_kind.py`, which has **8**. Caught by querying it
  while writing the PR body — which is the whole argument for querying.
- **A stale figure in my own memory index** ("delay band now 1.5–8 h"), caught while updating it.

**The owner's, caught by me, corrected in the open rather than silently:**

- **`ats_outcome` and "+0.91"** in the D47 ruling — the field is `ats_result`, the convention is
  `analytics.kpis.WIN_RETURN = 0.909`.
- **"~36 h"** for a claim-exposure floor — measured **58.2 h**.
- **"First Tuesday game SOUTHERN MISS@TROY 2026-10-06"** — the tracked slate is P4 + Notre Dame, 68
  teams, Thu/Fri/Sat, and has **no** Tuesday games. `data/team_registry.py` answers slate questions.
- **The 1.5–8 h band** above.

**A reviewer's, caught by me:** the attempts-API dispute on `37365254988` (the owner's account was
right); and a count of "nine capture runs" on 2026-10-10 when the API gives **seven** on the
Saturday — an eighth at `00:56:34Z` belongs to Friday's `23 21` slot. Both recorded, not quietly
dropped. **A reviewer's finding is a claim too.**

**Recorded at the owner's instruction by generation 5 (2026-11-05):** generation 4 **merged its own
handoff PR, #77**, as `8b7af00` at 2026-11-05T22:12:49Z. It was docs-only, under D43 (a), on a green
gate (every check `SUCCESS`). The owner records it as **the first session-performed merge of the
season**. The API cannot confirm or refute that: `mergedBy` reads `Brandon12200` on every merge,
because sessions act through the owner's `gh` credentials. **Owner ruling, 2026-11-05: sessions open
PRs and the owner merges, D43 included.** D43 waives *review before merge*. It does not waive the
owner's hand on the merge. This is appended to D43 in `docs/DECISIONS.md`.

## G4.5 The drawer as it stands

- **Watching `freeze-integrity` for a *missing* run.** The 2026-10-05 cancellation showed a
  pre-step cancellation is invisible: it fires no `if: failure()`, opens no issue, and reaches the
  owner only by email. `queue: max` (D46) does **not** cover it. Deliberately not built — a watcher
  is new unattended machinery, and D48 is the opposite of that (D48, "Explicitly not in this
  batch").
- **D45, the claim-path ruling — queued as insurance and UNDATED.** Its 2026-10-06 deadline was
  **withdrawn** (owner, 2026-09-28). The shape is settled: exclude any game whose scheduled kickoff
  precedes the claim run. The **margin and its reference timestamp are not ruled**, and the handoff
  that said otherwise overstated it. **Do not implement D45** until the owner rules those. Nothing
  depends on it.
- **The 2025 retro's staleness**, and **`verify-phase-4`'s side-effect write** — both open.
- **2027 drawer** (`docs/2027_NOTES.md` §8, items numbered to **39**). Three to know: **item 38** —
  nothing in this repository parses a workflow file; there is no `yaml.safe_load` in `tests/`, no
  `actionlint` in `ci.yml`, PyYAML is not a dependency, so an *invalid* workflow passes every check
  we have, and **`scripts/workflow_triggers.py` does not close this** — it reads YAML as text by
  design (SPEC §13, D24) and is mutation-tested rather than validating. The durable fix is
  `actionlint` as a CI step. **Item 39** — the Tuesday 12:50 capture slot serves a game type this
  slate does not have; its removal was ruled a 2027 item rather than a mid-season workflow change.
  **Item 33** — whether capture should leave the shared `cfb-pipeline` concurrency group.

## G4.6 Memory, and how to reconstitute

Machine-local memory lives at
`~/.claude/projects/-Users-brandonkenney-Projects-cfb-contrarian-predictor-2026/memory/` — **13
files** including the `MEMORY.md` index. It is **not** in the repository and is not authoritative.
The ones that matter, in reading order:

1. `season-era-cadence-and-rulings.md` — start here in-season: slate scope, the cancelled-run blind
   spot, the CFBD thread, the re-derived delay figures.
2. `nov-batch-prs-and-stop.md` — #75 merged, #76 held, and the merge-day check as commands.
3. `fetch-before-stating-main.md`, `reviewers-share-the-working-tree.md` — rules 1–3 above, with
   the incidents that produced them.
4. `custom-subagents.md`, `owner-working-style.md`, `proposal-files-not-terminal.md` — how to work.
5. `phase3-calibration-judgment.md`, `freeze-prep-ledger-closed.md`, `phase1-progress-state.md`,
   `phase2-kickoff.md`, `calibration-constants-methodology.md` — historical.

**The instruction that matters more than the files: reconstitute from the repository and its git
history, and treat both memory and this section as claims to verify.** `docs/SPEC.md` and
`docs/DECISIONS.md` are authoritative; this file is not, and a memory file reflects only what was
true when it was written. If a memory names a file, function or flag, check it still exists before
acting on it. The predecessor to this generation was retired at a context compaction and its last
writing could not be trusted near that boundary; assume the same of this section if you find it
disagreeing with `git log`.

**(u) markers — what was not queried for this section:** the generation boundary itself. That this
tenure began with the post-merge audit of this file as **#62** (`fccfd50`, merged 2026-09-14
01:56 UTC), with #59–#61 belonging to the predecessor, is **inferred from merge timestamps** and
from D43's condition; no record in the repository assigns PRs to generations. The reviewer-tree
failure dates in G4.3 rule 3 are carried from memory rather than re-queried. Everything else in this
section was queried at 2026-11-05 ~22:00 UTC.

**`make resolve-locators DOC=docs/HANDOFF_SEASON_ADDENDUM.md` at the head that merged this section
reports 113 locators, 37 failed, 3 by eye** — up from 4 failed before it. Classified below, so your
audit need not rediscover it, and so the number is not read as 33 new defects. *(The classification
you are reading cites those same SHAs and paths again, so it is itself counted in the 37 — writing
down that a locator is deliberately unreachable creates another deliberately unreachable locator.
Drafting this paragraph moved the figure from 29/103 to 37/113, which is the kind of thing only
re-running the tool tells you.)*

- **UNREACHABLE** — PR #76's four commit SHAs (`5874279`, `88f2a6b`, `3d99b10`, `9e5e069`), cited
  several times. They are real and the tool's *says* axis matches; they are simply not ancestors of
  `main` while #76 is held open. These resolve themselves on the merge, and **one line of the audit
  is to re-run this and confirm they did** — if they are still unreachable after #76 merges,
  something went wrong with the merge. Plus the pre-existing stash SHA at `:24`. **Also
  `66f3313`, the commit cited in G4.3 rule 5**, which this classification left out *(G5 audit)*. It
  is real, and its message really does have the blanked phrases. But it lives only on
  `origin/pipeline/season-stop-v2`, an abandoned earlier stack, so **#76's merge will not make it
  reachable.** The G5 audit below adds a third permanent one, `b2cab2e`, #76's pre-rebuild head.
  After #76 merges, expect exactly **three** unreachable SHAs: `0bcd378`, `66f3313` and `b2cab2e`.
  A fourth means something went wrong.
- **MISSING** — `scripts/workflow_triggers.py`: on #76's branch only, same resolution.
  `scripts/threshold_sweep.py` and `docs/analysis/2026_THRESHOLD_SWEEP.md`: D47's unbuilt
  deliverables, expected absent until 12-20. `docs/proposals/D44_CRON_CADENCE.md` at `:88`:
  pre-existing, deleted per its own lifecycle line. The rest are the **memory filenames** in G4.6,
  which live outside the repository by design.

**No locator in this section fails for being wrong.** That distinction is the reason D43 (b) calls
the tool half a tool: it cannot tell a deliberate forward reference from a typo, and only the
re-derivation pass can.

## G5 audit — the post-merge audit of G4.1–G4.6, 2026-11-05 (D43 (a))

Performed by generation 5 against `8b7af00`. Every claim was re-derived from the repository, `gh`,
or the Actions API. The section's prose was not proofread instead. **Four corrections**, each made
in place above and marked *(Corrected by the G5 audit)*, plus one omission:

| # | where | what was wrong | what is true |
|---|---|---|---|
| G5.1 | G4.1, #76 bullet 3 | eleven commits / `UNKNOWN` described as a recompute lag | `mergeable` has settled to `MERGEABLE`; the 11 commits / 19 files persist because the PR's stored `base.sha` is `d6c5267` |
| G5.2 | G4.1, merge-day step 3 | "expect movement only under `data/`" | #77 moved `main` in `docs/HANDOFF_SEASON_ADDENDUM.md`. Re-run at `8b7af00`: overlap empty, so the GO stands |
| G5.3 | G4.1, merge-day step 4 | "`9e5e069`'s parent is on `main`" | `9e5e069`'s parent is `3d99b10` (branch-only). The stack's base `72d1a3d` is `f56a243`'s second parent |
| G5.4 | G4.2, catch-up bullet | step "Resolve the week" in `weekly-predict.yml` | step "Resolve week", `id: resolve`, inside `.github/actions/cfb-setup`, invoked as `id: setup` |
| G5.5 | G4.6, locator classification | `66f3313` (G4.3 rule 5) unclassified | permanently unreachable (on `pipeline/season-stop-v2` only). With `b2cab2e` cited below, expect three unreachable SHAs after #76 merges, not one |

**Re-derived and found correct:** `main` head and parents at the time of writing. CI on `f56a243`
was success (run `42116445053`). There were 49 `## D` entries, ending at D48. Week 10 was claimed as
`1bacd90`. `pipeline_week` gave `grade_weeks = 1 … 10`, `catchup_weeks = 10`. D47 was at
`docs/DECISIONS.md:1388` at `8b7af00` (1398 after this audit's D43 appendix). `WIN_RETURN = 0.909` is right, and so is `ats_result`. The last scheduled
run before the merge was `42089182312`, at 18:57:11Z, and **still no scheduled run has executed the
D48 code** (the runs since are CI only). The probe step names, the issue title and the `kind:
probe` label match `freeze-integrity.yml`. The retry is one retry, and it never fires on a 4xx
(`data/clients/cfbd_v2.py`). Its WARNING text matches the log format. `tests/test_probe_kind.py`
has 8 tests. Every delay figure was recomputed from all 90 scheduled `freeze-integrity` runs:
largest 9.79 h (`33212867178`), then 9.59 and 9.15 (`41523134721`), then 8.70, 8.01
(`37365254988`) and 7.24. Since 08-29 the range is 2.28–9.15 h, n=69. Issues #56, #71, #72 and #73
are as described. #73 came from run `39810193934`, and attempt 4 of `39631525799` started 10-23
04:58:15Z. PRs #63–#70, #75 and #77 are all merge commits. `#62` = `fccfd50` at 01:56:51Z. The
2027 drawer items 33, 38 and 39 say what G4.5 says. The memory directory holds 13 files.
`make resolve-locators` at `8b7af00` reported 113 locators, 37 failed and 3 to check by eye. The
tally matches.

**Not touched:** the PR #76 body. It still says "Head: `b2cab2e`" in its opening line, while its own
review table names `9e5e069`. And its "Merge the batch first (by 11-29)" was overtaken when #75
merged 11-05. Both are stale history, not wrong instructions. This audit edits only the section it
audits.

**`make resolve-locators` at this audit's head:** 152 locators, 51 failed, 5 to check by eye. Every
new failure falls into a class G4.6 already names: #76's branch SHAs, the three permanent SHAs, the
expected-absent files, and the memory filenames. Most of them are this section citing those same
locators again. None fails for being wrong.
