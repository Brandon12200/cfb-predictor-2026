# CLI tests read a regenerated artifact — PR summary

> **Lifecycle.** A PR summary — a durable record of what shipped and why, **RETAINED, not retired.**
> `docs/pr-summaries/` sits outside the proposal lifecycle (owner ruling, 2026-07-25). The
> authoritative records remain `docs/2027_NOTES.md` §8 (items 27–30, added here) and `docs/SPEC.md`.
>
> **Status:** open, awaiting owner merge. **Branch:** `fix-cli-tests-live-snapshot` (base `8f7a5ff`).

---

## What broke, and why it was not a code defect

`main` went red on 2026-09-01 (run `33537284634`, push of `8f7a5ff`), 8 of 9 jobs failing. Four
tests, one cause — **line numbers are as at `8f7a5ff`**, the frame this log came from; this PR moves
them (D40's frame-pinning convention):

```
tests/test_cfb_cli.py:47   test_omitted_week_equals_explicit_week
tests/test_cfb_cli.py:69   test_offline_rerun_identical_to_predict_week
tests/test_cfb_cli.py:111  test_slate_returns_ok_when_all_games_have_lines
tests/test_cfb_cli.py:137  test_predict_week_save_refuses_overwrite_d22
E  AssertionError: assert 2 == 0
```

`8f7a5ff` was the **first post-kickoff rebuild** of `data/snapshots/2026_week_01/`. Books de-list a
game once it has been played, so the bundle lost two lines — measured directly from the two commits:

| | `betting_lines` | with a line | without |
|---|---|---|---|
| `d358db5` (pre-kickoff) | 11 | 11 | — |
| `8f7a5ff` (today) | 11 | **9** | `NC STATE@VIRGINIA`, `NORTH CAROLINA@TCU` |

Those two are **exactly** the two of the eleven that had been played. `analytics/predictions.py:49-50`
records a game with no prediction-time line under `meta.coverage.skipped`;
`cli/cfb.py::_slate_degraded` maps a non-empty `skipped` to `EXIT_DEGRADED`; `cli/output.py:20`
defines `EXIT_DEGRADED = 2`.

**Owner ruling (2026-09-01):** `docs/SPEC.md:371` (SPEC §9 requirement 5, *"Exit codes are
meaningful (0 ok, 1 error, 2 degraded data)"*) **is** the contract. The CLI is correct as written;
the tests were the defect. No CLI behaviour change, no SPEC amendment. The alternative reading —
that a game dropped *because it was played* is not the same condition as one dropped *because its
line never posted* — is recorded as a 2027 design note (`2027_NOTES` §8 item 29), not implemented.

## The mechanism the fix had to get right

There are **two independent snapshot reads**, and pinning one is worse than pinning neither:

- `cli.cfb._load_slate` **enumerates** the slate via `data.snapshot.store.load_snapshot`.
- The frozen engine **prices** each game via `data.data_manager.load_snapshot`
  (`data/data_manager.py:70`), which `data_manager` binds at import time, so a store-level patch
  never reaches it. `analytics/predictions.py:28-31` documents exactly this.

`scripts/slate_fingerprint.py::engine_reads` already exists to prevent the resulting **split read**
— enumeration pinned, pricing live — and its docstring says it "looks correct" when wrong. Measured,
because the trap is real and was fallen into once while diagnosing:

```
build_predictions(frozen_vehicle)                    -> written  9, skipped 2   # split read
with engine_reads(vehicle): build_predictions(...)   -> written 11, skipped 0   # both pinned
```

The fix reuses `engine_reads` rather than reimplementing it, so there stays one definition of how
the engine gets pinned.

## What shipped

**(1) The four failing tests now read a pinned bundle.** Each is pinned to
`data/archive/frozen/2026_week_01_snapshot_v2026-frozen-3.json` — the tag-time vehicle, which lives
under the **append-only** tier and therefore cannot rot the way a regenerated bundle does. The
premise is **asserted, not assumed**: `_all_lines_bundle()` fails with an explicit
"fixture premise violated" message if the vehicle ever lacks a line, rather than failing later as a
bare `assert 2 == 0`. The same guard is added to `scripts/verify_phase_4_5.py` as a named check.

**(2) One new test pins the newly reachable state** —
`test_a_mid_week_slate_degrades_on_games_the_books_de_listed`. It derives a mid-week bundle from the
pre-kickoff one (de-listing chosen **positionally**, so no team literal can rot), marks those games
played, and asserts: `slate` exits **2**, `meta.coverage.skipped` equals **exactly** the de-listed
set, `written` equals the remainder, and `predict week` **names** them in its degraded message.

**(3) The sweep.** `scripts/verify_phase_4_5.py` carried the same two assertions plus a
`CLEMSON @ LSU` slate-membership check against the live bundle — CI runs it, so it was part of the
same red. Full findings below.

**(4) Drawer lines** — `docs/2027_NOTES.md` §8 items **27–30**.

## The sweep (item 3) — every test reading live repo data

Method: enumerate reads of regenerated artifacts (`data/snapshots/`, `data/graded/`,
`data/projections/`, `data/lines/`) across `tests/` and the `verify_phase_*` scripts, then read each
call site's assertions and ask what the calendar changes.

### Time-breakable — fixed in this PR

| Site | Property | Would have broken |
|---|---|---|
| `tests/test_cfb_cli.py` ×4 | `EXIT_OK` on a whole-slate command | **already red**, 2026-09-01 |
| `scripts/verify_phase_4_5.py` — omitted==explicit, offline rerun | `== 0` on both | **already red**, 2026-09-01 |
| `tests/test_cfb_cli.py::test_predict_game_matches_the_slate_row` | `CLEMSON @ LSU` is in the slate | next rebuild after its **2026-09-05** kickoff |
| `tests/test_cfb_cli.py::test_predict_game_exit_code_ignores_unrelated_slate_drops` | same matchup | **2026-09-05** |
| `scripts/verify_phase_4_5.py` — predict-game check | same matchup | **2026-09-05** |
| `tests/test_lean_attribution.py::_partial_week_join` | `0 < graded < total` | **2026-09-13**, when week 1 finishes grading |

The last is the most instructive: it would have failed **on the very test that pins the D40 defect**,
for a scheduling reason. Its fallback only fired when the artifacts were *absent*, never when
grading completed. Fixed by truncating to a strict subset, so partiality is guaranteed by
construction — verified to hold at every grading depth from 1/11 to 11/11.

### Read live data but not time-breakable — left alone, with the reason

| Site | Why it is safe |
|---|---|
| `tests/test_slate_reconciliation.py:47,70` | monkeypatch `_SNAPSHOTS_DIR` to `tmp_path` first — not a live read |
| `tests/test_pipeline_cycle.py:60` | same; builds into `tmp_path` inside the fixture |
| `tests/test_slate_reconciliation.py:180,197-201` | render-shape assertions only (`"reconciliation:" in text`) |
| `tests/test_inspection.py` | structural assertions; the drill-down game is `next(iter(...))`, not named |
| `tests/test_normalizer_fails_closed.py:104-130` | asserts **absence** of self-matchups / fabricated signatures — monotone; de-listing cannot reintroduce one |
| `tests/test_schedule_intel.py:194,273` | venues — not slate-dependent |
| `tests/test_pipeline_preflight.py:193` | thresholds vs manifest summary; `min_snapshot_coverage_pct` is warn-only and `min_slate_games` is 1 |
| `tests/test_project_cli.py:129` | `unscheduled == []` is a season-schedule property, not a weekly one |

## Evidence

| Check | Result |
|---|---|
| `make test` | **1043 passed, 2 skipped** (was 1038 passed / 4 failed / 2 skipped; +1 new test) |
| `make lint` | ruff **All checks passed**; mypy **no issues in 48 source files** |
| `make verify-phase-0` | ALL CHECKS PASSED |
| `make verify-phase-1` | ALL PHASE 1 CHECKS PASSED |
| `make verify-phase-2` | ALL PHASE 2 CHECKS PASSED |
| `make verify-phase-3` | ALL PHASE 3 CHECKS PASSED |
| `make verify-phase-4` | ALL PHASE 4 CHECKS PASSED |
| `make verify-phase-4-5` | ALL PHASE 4.5 CHECKS PASSED (13 checks, incl. the new premise check) |
| `make verify-phase-5` | ALL PHASE 5 CHECKS PASSED |
| `factors/` tree vs `v2026-frozen-3` | `bf543c8a5358` == `bf543c8a5358` — **identical** |
| `engine/` tree vs `v2026-frozen-3` | `0a4c0aec031b` == `0a4c0aec031b` — **identical** |

## Freeze and immutability

Diff touches `tests/` (2 files), `scripts/verify_phase_4_5.py`, and `docs/` only. **Nothing under
`factors/`, `engine/`, or calibration config; no fingerprint constant touched; no artifact written
or edited.** The fix is code-only and the next scheduled run needs no help from it.

Worth recording alongside: in run `33537284634` **every freeze check passed**, fingerprint included
(`sha256 b9c00a947cd539db…`, matching the frozen constant). `verify-freeze` went red only because
`scripts/verify_phase_3.py` also runs the suite — yet CI's one failure surface reported *"model
output moved — do NOT update the fingerprint constant"*. That false diagnosis is `2027_NOTES` §8
item 27.
