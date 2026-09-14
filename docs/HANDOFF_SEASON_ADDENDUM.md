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

1. **PR C — `resolve_locators` as a make target** (D42 (a)3). The `LINT_PATHS` conflict with #60 is
   cleared now that #60 is merged. **Blocked on a source (C13):** there is no `resolve_locators`
   implementation anywhere in the repository. It is not in any local or remote branch, not in any
   commit's tree, and not in the stash. D42 (a)3 says only "delivered separately". Before PR C starts,
   the owner says where the tool comes from. Do not write one from its description.
2. **PR D — CLV gate in `weekly-predict`'s catch-up** (ruling 2). **Deadline: before 2026-09-22.**
3. **Then four proposals for the owner's ruling — proposals, not PRs:**
   - **D43 candidate — cron cadence**, with an **escalation path for the timing guard.** Measured
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
- **A background reviewer can run git and tests in the shared working tree.** Either do not switch
  branches, edit or commit while one runs, or instruct it to work in an isolated `git clone`. On 2026-09-13 one
  ran `git stash` in the shared tree mid-review — that is the stash in §1.
- **Prose claims are re-derived, not proofread** (D42 (d)): resolve every locator, then separately
  re-derive every count, date, SHA and status. Every error caught this tenure was caught that way.
- **No AI attribution** in commits or PR text (D3). Freeze untouched: `factors/`, `engine/`.
