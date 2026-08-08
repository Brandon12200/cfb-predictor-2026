# Phase 5 — Automation Pipeline (PR-1)

**Branch:** `phase-5-pipeline` → `main` (base `7d869c8`) · **9 commits** · 2026-08-08
**Verdict:** `code-reviewer` **GO**; `pipeline-adversary` — **no finding blocks the written
acceptance criteria** (all CARRY-FORWARD).
**Gates:** `make test` **838 passed / 2 skipped** · `make lint` clean · **all seven** verify targets
PASS including the new `make verify-phase-5`.

---

## What shipped

The season's automation (SPEC §10): three cadence workflows, CI, a daily freeze-integrity job, four
composite actions, six new scripts, and `docs/PIPELINE.md`. Everything is freeze-exempt —
`factors/` and `engine/` are tree-identical to `v2026-frozen`, verified in the diff and asserted by
`verify-phase-5` itself.

| Job | Fires | Commits (one per artifact tier) |
|---|---|---|
| Predict | Tue 09:17 ET | `grading:` catch-up → `snapshot:` (+`data/lines`) → **`predictions:` alone** |
| Capture | Wed/Thu/Fri 17:23; Sat 10:23 / 14:23 / 17:23 / 20:23 ET | `lines:` |
| Grade | Sun 12:47 ET | `results:` → `grading:` → `report:` (gated, see D36) |

New: `pipeline_week.py`, `pipeline_preflight.py`, `check_snapshot_quality.py`, `fetch_results.py`,
`sp_watch.py`, `verify_phase_5.py`; `pipeline_week`/`pipeline_today` in `utils/season_calendar.py`;
the `pipeline` block in `season.json`.

## Three findings that reshaped the plan

**F1 — the pipeline would have destroyed its own freeze gate.** `verify-phase-3`'s fingerprint, its
L4 assertion and the schema-v2 golden all read `data/snapshots/2026_week_01/snapshot.json`. That is
a *live* bundle — committed but not in `PROTECTED`, and `write_snapshot` overwrites unconditionally
— so the live Week-1 run on **2026-08-25** would have replaced it and made all three gates report
"model output moved" because the pipeline merely ran. Fixed by pinning a byte-for-byte copy under
the append-only tier (**D29**). **The fingerprint constant `eab7ffdb…20e2d` is unchanged**; the
pinned vehicle reproduces it exactly (330 games). Sensitivity is preserved because the gate re-runs
the frozen engine over the pinned input rather than replaying a stored result — so a change reaching
output through the freeze-exempt read seam still trips it, which is the class that moved output
twice before (A6, venue timezones).

**F2 — the Week-1 run could not name its own week.** `infer_week_for_date` returns the week whose
window contains today; week 1 is `08-29 … 09-07`, but the week-1 predict run is Tuesday **08-25**
and the captures are 08-26→28. All four fall inside no window, so the resolver raises and the first
live cycle dies before doing anything. Added `pipeline_week` (lowest-numbered week whose `end >=`
today, clamped, never raises) beside the unchanged game-window resolver — with a test asserting
`resolve_week` **still raises** there, so the two questions cannot be conflated later.

**F3 — `cfb status`'s tag label was wrong, and the cause was bigger than the label.**
`model_version()` returns the bare tag only at the tagged commit; HEAD was already
`v2026-frozen-2-gea21d28`. Worse, `actions/checkout` defaults to `fetch-depth: 1` and fetches no
tags, so on a runner `git describe --always` silently returns a **bare SHA** — a commit hash in the
provenance field every claim of the season carries, in files that are byte-immutable forever.
Guarded three ways: `fetch-depth: 0` everywhere (pinned by tests), a `cfb-setup` refusal when no
tags are present, and a preflight **ABORT** unless `model_version()` starts with the freeze tag.
**D34** supersedes D21.2's phrasing without editing it; `SCHEMA.md` is corrected directly.

## Decisions ratified

| | Decision |
|---|---|
| **D29** | Freeze gates read a pinned tag-time vehicle; constant untouched; provenance re-derived from the tag on every test run |
| **D30** | Commit identity `cfb-pipeline` + a `Run:` trailer — a machine identity is not AI attribution (D3); a human name on a machine commit would be the actual lie |
| **D31** | Protect `main`, bypass for the Actions app. Auto-merge rejected: **squash-merge would collapse the three-commit Sunday taxonomy into one**, a D22/D23 violation produced by a repo setting |
| **D32** | Rehearsals on an unmerged `rehearsal/*` branch (**reversing the earlier `data/rehearsals/` leaning**) — `build_snapshot.py` has no `--out`, so a rehearsal would also overwrite the gate vehicle, and the branch runs production's exact code path with zero new plumbing |
| **D33** | Fingerprint on push **and** on a timer; `sp_watch` is the external probe, because a gate reading a committed snapshot cannot detect an external event by construction |
| **D34** | `model_version` keeps the descriptive `git describe` form |
| **D35** | Four Saturday capture waves — measured at ~8 credits/week ≈ **7% of the free tier**; no spend decision required |
| **D36** | The Sunday report commit is **gated** until D27's lean-side split lands |

## The D36 gate

`analytics/` has no lean-side stratification and no naive always-lean-home baseline. Preseason leans
run **195 home / 35 away — 5.57:1, structural**. An unsplit season headline over that skew is D17's
exact failure, except re-committed and pushed automatically every Sunday. Reports are generated (so
a rehearsal can inspect them) but **not committed**. The gate greps for the split so it opens by
itself; a test asserts it is still closed and instructs its own removal. **Hard deadline: the first
graded Sunday.**

## Review outcome

`code-reviewer` returned **GO** having independently re-derived the D29 pin from the tag, re-run the
fingerprint, and confirmed `factors/`/`engine/`/`.claude/` are untouched. Its four should-fixes and
the adversary's fixable findings were closed in `fccb2be`.

**The convergence worth recording:** both reviewers independently found that `write_predictions`
overwrote unconditionally, while the *human* CLI path has refused since 4.5 — so the byte-immutable
guarantee held for the interactive path and not the automated one, and `protect_immutable.py` does
not run on a runner at all. Now enforced at the shared seam, scoped to the claim tier.

Also closed: exit-code propagation in the week-resolution step; a push-retry loop that died on
attempt 1 under `set -e` so the documented three attempts never happened; a failure diagnostic that
captured nothing in the push-failure case (now records committed-but-unpushed work); a missing quota
cache on the Tuesday job; a duplicated freeze assertion in `freeze-integrity.yml` (D25.4 — two
copies is how guards drift); and the `D-8` label, which was plan-local and never existed in
`DECISIONS.md`.

**Inherited, not fixed at the deadline** (`docs/2027_NOTES.md` §8): the capture-side postponement
blind spot — the one with in-season consequence — unguarded CFBD spend with an unbounded catch-up
loop, no season-end kill switch, quiet mid-run credential degradation, and a missing DST-boundary
test.

## What this PR does NOT contain

Deliberately deferred to PR-2 (soft target Aug 21): D27's lean-side split (hard deadline the first
graded Sunday), the SPEC §5.5.3 dropped-game detector — held back because it sits on the
snapshot-build path and demands the full six-target sweep, and a snapshot-path change riding inside
the pipeline PR would look exactly like a freeze violation — the `pyproject` packaging fix for
`scripts*`/`analytics*` with a subprocess smoke test, the `cfb status` tag label, `demo.sh` and
README, an append-only `data/quota/` ledger, and deleting `scripts/setup_cron.sh`.

## Owner actions before the first rehearsal (Aug 17)

1. `ODDS_API_KEY` and `CFBD_API_KEY` as repo secrets.
2. Branch protection with the Actions-app bypass (**D31**) — without it the cadence fails on its
   first Tuesday.
3. Merge this PR (merges are the owner's).
