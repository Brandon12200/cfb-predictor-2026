# Ledger PR summary — reverse-audit A-item dispositions (PR #18)

> **Lifecycle.** Working document, not an authoritative record. It captures the state of PR #18 at
> the point it was opened, for owner review. The authoritative records are `docs/CALIBRATION_LOG.md`
> ("A-item dispositions"), `docs/FREEZE_CHECKLIST.md`, and `docs/CODE_AUDIT.md`. **Delete at the next
> phase/session boundary**, together with `A4_prediction_type_rescale.md`. Not authoritative over
> `docs/SPEC.md`.
>
> **Status:** PR open, paused for owner review. Reviewer verdict **GO**.
> **PR:** https://github.com/Brandon12200/cfb-predictor-2026/pull/18
> **Branch:** `freeze-prep-ledger` (6 commits, base `1855e04`).

---

**PR #18 open — pausing here as instructed.** https://github.com/Brandon12200/cfb-predictor-2026/pull/18

## What landed

Six commits, individually reviewable per the standing rule:

| | |
|---|---|
| `77dfa34` | A3 — variance_detector category map (2 files, 23 lines) |
| `7888586` | A2+A5 — deletion event (27 files, −8,731) |
| `92e1d20` | A4 sub-decision — `predicted_edge` 4 dp + golden |
| `928818f` | artifact-write guard |
| `80ac157` | docs — dispositions, Week-0 naming, proposal practice |
| `57e6699` | reviewer fixes |

`factors/factor_registry.py` carried both A3 and A5 edits, so I split the file across the two commits rather than merging the items into one diff.

**Gates:** `make test` 444 passed / 2 skipped · `make lint` clean · all six verify targets PASS.

**The strongest evidence** is end-to-end output-neutrality: the committed Week-1 payload is byte-identical to the pre-ledger baseline on every field except `predicted_edge`, which changed exactly as ratified. A3 specifically: 744 games, zero records differ.

## Amendments applied as ruled

Both went into the A4 entry, and your amendment 1 was a genuine correction to my proposal — I verified it before writing it in. The current ladder reads SLIGHT→MODERATE→STRONG→VERY_STRONG cleanly across the bet region, while my candidate boundaries would have flattened **every** persisted bet to `VERY_STRONG`. I had optimized for the region where the ladder never persists.

## Reviewer: GO

One should-fix — my guard covered 3 dirs while `protect_immutable.py` protects 7, and `data/archive/` is named in CLAUDE.md principle 5. Fixed in `57e6699`, and coverage is now asserted **against the hook's own tuple** so the two can't drift apart silently.

## Three things to flag

1. **`verify-phase-3` caught the stale golden; the pytest suite did not.** The 4 dp change left the committed golden at 2 dp and 444 tests passed anyway. Worth knowing which gate actually has byte-identity coverage.
2. **Deletion scope grew by one file I didn't enumerate**: `scripts/check_results.py`, a `bet_evaluator` consumer that's unreferenced and superseded by `scripts/grade.py`. It fell inside item 5 naturally, but it wasn't in the list you approved.
3. **Deliberately not expanded**: removing `cli.app.main` orphaned `run_weekly_analysis` and `run_p4_predictions` (~430 lines). `cli/` isn't freeze-bound, so that can land post-tag — flagged rather than silently widening scope.

One item from earlier remains unresolved and is yours: `docs/SPEC.md:197` still says "graded Week-0 dress rehearsal." I fixed FREEZE_CHECKLIST, PHASE5_NOTES, HANDOFF and CODE_AUDIT as ruled, but SPEC is authoritative and editing it wasn't in scope.

**Still before the tag:** the B1–B10 batch (which per the new practice goes to `docs/proposals/` as one consolidated file), the lint-scope fold-in, and the `calibration-auditor` pre-flight returning FREEZE-READY.

---

## Appendix — per-item disposition status (as committed)

| Item | Ruling | Change | Status |
|---|---|---|---|
| **A1** `HeadToHeadRecord` | Accept **dormant**, on the record | No code change — logged | RATIFIED, landed |
| **A2** second confidence/edge scoring surface | **Full retire** | ~8,700 lines deleted | RATIFIED, landed |
| **A3** `variance_detector` category map | **Fix** | ~20 lines, output-neutral | RATIFIED, landed |
| **A4** `prediction_type` ladder | **Accept collapse, do NOT rescale** | No ladder change — logged | RATIFIED, landed |
| **A4 sub** `predicted_edge` precision | 2 dp → **4 dp** | Schema + golden | RATIFIED, landed |
| **A5** stale category weights | **Retire** (inside A2) | Removed; `cli status` repointed | RATIFIED, landed |

**A1** is logged with *both* blockers: the registry threshold `1.0` equals the factor's `_max_output` 1.0, **and** `data_manager`'s `_H2H_PLACEHOLDER` leaves `total_games` permanently 0, so `calculate()` returns 0.0 at any threshold. Fixing only the threshold accomplishes nothing — stated explicitly so 2027 cannot make that mistake. §16.7's KEEP is satisfied by registered-and-honestly-dormant.

**A4**: the ladder is **correctly scaled where it persists** and unreachable only in the pre-floor region, where `base_type` is overwritten by the `NO_BET` verdict and never reaches disk. A rescale fit to the dormant-state distribution was measured and **rejected** — it would classify every actual bet (`edge ≥ 0.75`) as `VERY_STRONG`. The 100%-NO_BET figure is the dormant-state **lower bound**, not a permanent property; in-season activations are designed to lift rare games above the floors ("bets rarely", not never).

Two ledger findings were **corrected against source** and the corrections recorded rather than quietly fixed: A2's blast radius (nine consumers, not "dead code only") and A5's severity (never fed scoring, but its validator had returned `valid: False` on every call it ever received).

## Appendix — evidence as pasted in the PR

```
make test    444 passed, 2 skipped
make lint    All checks passed! / Success: no issues found in 40 source files

verify-phase-0: PASS   verify-phase-1: PASS   verify-phase-2: PASS
verify-phase-3: PASS   verify-phase-4: PASS   verify-phase-4-5: PASS
```

**Output-neutrality, end to end.** The committed wk1 prediction payload is byte-identical to the pre-ledger baseline on every field except `predicted_edge`, which changed exactly as ratified:

```
non-edge payload identical to pre-ledger baseline: True
predicted_edge before: [0.0, 0.0, 0.05,   0.11,   0.0, 0.14,   0.0, 0.0, 0.05,   0.0]
predicted_edge after : [0.0, 0.0, 0.0468, 0.1122, 0.0, 0.1403, 0.0, 0.0, 0.0468, 0.0]
```

**A3 neutrality specifically** — 744 games (10 wk1 + 734 in-season), zero records differ:

```
vehicle_a: n= 10  records differing=0  max|d edge|=0.000000000000  max|d conf|=0.000000000000
vehicle_b: n=734  records differing=0  max|d edge|=0.000000000000  max|d conf|=0.000000000000
```

**A4 measurement** (both vehicles, per the owner's scope rider). Placeholder-line injection proven neutral: same 40 games at `-3.0` vs `+10.5`, `max|Δ| = 0.000000000000`.

| vehicle | n | p50 | p90 | p99 | max |
|---|---|---|---|---|---|
| wk1 dry-run (real lines) | 10 | 0.0000 | 0.1150 | 0.1377 | 0.1403 |
| in-season, own week | 734 | 0.0244 | 0.1179 | 0.2057 | 0.2338 |

## Appendix — also in scope

- **Artifact-write guard** — autouse fixture failing any test that creates/modifies/deletes a real committed artifact. A manual `--save` once left a stray file under `data/predictions/`; the save test avoids that only via a monkeypatch that binds because the import is call-time. Coverage is asserted against the immutability hook's own tuple so the two can't drift; its detection primitive is pinned by its own tests.
- **Week-0 naming** corrected to opening-weekend/Week 1 per D8 (historical D8 context left intact).
- **Carry-forward item 5** closed — dev-script cluster deleted. `scripts/grading.py` + `scripts/calculate_accuracy.py` kept (D17 exhibit).
- **Standing practice** in CLAUDE.md: table-dense ratification proposals go to `docs/proposals/` as reviewable files.

## Appendix — awaiting owner ratification / decision

Nothing in PR #18 is blocked on a ratification — all five A-items and the `predicted_edge` sub-decision were ratified before the work landed. Open items are:

1. **Merge PR #18** (owner review of the open PR).
2. **`docs/SPEC.md:197`** — still reads "graded Week-0 dress rehearsal". SPEC is authoritative and editing it was outside the ruled scope; owner to decide whether it is corrected there too.
3. **`scripts/check_results.py` deletion** — inside carry-forward item 5 by dependency, but not in the enumerated list that was approved. Retroactive confirmation.
4. **Orphaned legacy functions** — `run_weekly_analysis` / `run_p4_predictions` (~430 lines), freeze-exempt. Owner to say whether cleanup lands pre- or post-tag.
5. **B1–B10 batch** — the next ratification, to be delivered as a single consolidated file under `docs/proposals/`.
