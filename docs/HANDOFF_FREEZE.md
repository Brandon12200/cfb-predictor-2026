# HANDOFF → freeze sequence (temporary — delete when `v2026-frozen` is cut)

A briefing for a fresh session with zero conversational context. **The reverse-audit ledger is
CLOSED.** What remains before the tag is two steps, in order, and neither was started in the session
that wrote this. **Not authoritative over `docs/SPEC.md`.**

Read this, then `docs/FREEZE_CHECKLIST.md`, then `docs/CALIBRATION_LOG.md`'s three ledger sections
("A-item dispositions", "B-item ratifications", "A6").

---

## (a) State — merged through PR #20, `main` clean

**Gates, run at the close of the writing session (2026-07-25, `main` @ `89371c4`):**

```
make test    449 passed, 2 skipped

verify-phase-0:   PASS
verify-phase-1:   PASS
verify-phase-2:   PASS
verify-phase-3:   PASS
verify-phase-4:   PASS
verify-phase-4-5: PASS

make lint    All checks passed!  /  Success: no issues found in 40 source files
```

*(`make lint` is green on its **current** `LINT_PATHS` — the two legacy files are not yet in scope.
That is the fold-in below, not a regression.)*

**Phases 0–4.5 complete and merged** (PRs #8–#14, #16, #17). Freeze-prep merged as **#18** (A-items),
**#19** (B-batch + the A6 finding), **#20** (the A6 fix). The model is **frozen-form**; the
`v2026-frozen` tag is **NOT** cut.

## (b) The reverse-audit ledger is CLOSED — A1–A6 and B1–B10 all dispositioned

| Item | Disposition |
|---|---|
| **A1** `HeadToHeadRecord` | **Accepted dormant**, logged with **BOTH blockers** — registry threshold `1.0` == the factor's `_max_output` `1.0`, **and** `_H2H_PLACEHOLDER` makes `total_games` permanently 0 so `calculate()` returns 0.0 at any threshold. **A 2027 reader must not "fix the threshold" and believe it restored** — the data blocker is the real one. |
| **A2 + A5** | **Retired together** — ~8,700 lines. A second unlogged confidence/edge scoring surface in `engine/` plus carry-forward item 5's dev-script cluster. `prediction_engine` is now the **only** scoring surface in `engine/`. A5's stale category weights had A2-cluster dead code as their only consumers, so they died together; `cli status` now renders weights live from the ratified registry. |
| **A3** `variance_detector` map | **Fixed**, proven **output-neutral** over 744 games (zero records differ, max Δ 0.000000000000). The map is diagnostic only — `variance_level` derives from the overall CV, never from it. |
| **A4** `prediction_type` ladder | **Option A — accepted, NOT rescaled.** Rationale is **floor-scale coherence**: the ladder and the 3c.5 NO_BET floors are in the same units at the same scale, so in the region where a bet actually persists (`edge ≥ 0.75`) the **current** boundaries read correctly (0.75→SLIGHT, 1.0–1.5→MODERATE, 2.0→STRONG). The rungs are unreachable only **pre-floor**, where `base_type` is overwritten by `NO_BET` and never persists. A candidate rescale fitted to the dormant-state distribution was measured and **rejected — it would classify every actual bet as VERY_STRONG.** Sub-decision: `predicted_edge` persistence raised **2 dp → 4 dp**. |
| **A6** `Altitude` | **Fixed at the data boundary.** Venue `elevation` is CFBD-native **metres**, compared against the ratified `altitude_threshold_ft = 4000.0` (**feet**); dataset max is 1634, so the factor could never fire. Elevation stays **metres at rest**; `data.schedule_intel.elevation_feet()` is the single conversion; `factors/`/`engine/` untouched, so the ratified 3b.1 constants stay byte-identical. Measured **0 → 16 of 330** tracked-slate activations. |
| **B1–B10** | **Ratified per-number** (a block is never ratified by one entry naming it). **Six constants logged DEAD, not ratified** — `redzone_weight`, `pace_advantage_slower`, `recent_game_weight`, `max_lookback_years`, `conference_championship_weeks`, `desperation_multipliers`. B1's `/5.0` edge divisor ratified as-found with its consequence logged: **`confidence_score` is in practice a data-availability score**. |
| **B9** `MarketSentiment` | **Dormant AND unwired for ALL of 2026.** Movement data **is collected** (Phase-5 `data/lines/` store) but is **not wired into the factor**; activation deferred to 2027, to be calibrated against a season of real movement data. This is **not** a re-opening of MSF.3 — it fixes what "data landing" means for 2026: **collected, not wired.** |

**Recurring defect family, now three occurrences:** a ratified constant silently neutered by a
comparison that can never be true — A1 (threshold == output max), B2 (`max_impact > _max_output`,
logged not fixed), A6 (metres vs feet). **Separately**, the pre-Bug-#7 point-scale assumption also has
three sites: the 3c.5 NO_BET floors, the A4 ladder, and B1's `/5.0` divisor. **2027 should sweep for a
fourth of each rather than assume these were all of them.**

## (c) Two corrections to claims made in already-merged PRs — on the record

Both were found by continuing to verify after the claim shipped. Neither changed a conclusion, but
both changed a stated fact:

1. **PR #19's "venue coverage is 68 of 138, five high-altitude programs absent" was a misreading.**
   The committed registry artifact `data/registry/fbs_teams_2026.json` holds **all 138 FBS teams with
   locations (132 with elevation)** — Air Force and Wyoming included. The snapshot builds `teams`/
   `venues` over `get_all_tracked_teams()` = *"the tracked **P4 + independents** slate"* = SEC 16 +
   Big Ten 18 + ACC 17 + Big 12 16 + Notre Dame = **exactly 68**, which is **SPEC §5.5's specified
   scope**, asserted by the season-start `validate_membership_counts()` check. The five are Mountain
   West / non-P4 and are **correctly out of scope by design**. **No finding; no action.**
2. **The A4/B measurement denominator was wrong: 734 → 330.** `both teams tracked = 330` is **exactly
   3c.5's basis**. The 734-game FBS-vs-FBS basis included 404 games involving untracked teams carrying
   `_empty_team()` honest-missing data. Re-measured on 330: p50 0.0244 → 0.0468, mean 0.0483 →
   0.0551, but the **maximum is identical (0.2338) and zero games clear 0.5 or 0.75 on either basis**.
   **Every A4 and B-batch conclusion stands unchanged; only the stated denominator was wrong. 3c.5 was
   right all along.**

## (d) New doctrine — imperative, carry these

### 1. The six-target-sweep rule

**Any pricer-affecting change MUST run all six verify targets. `make test` alone is insufficient, and
so is `make test` plus the phase target you think you touched.**

The A6 fix moved `model_spread` at high-altitude venues, which flows into the committed
`data/projections/` artifact. **`make test` (449 passed) and `verify-phase-3` were both green while
`data/projections/2026_week_01.json` was stale — 17 of 138 teams wrong.** Only `verify-phase-2`'s
reproduce-from-snapshot check caught it. This is the **second** occurrence of the same failure mode
(the first was the 3b `travel_cap` change). A calibration change that alters the pricer **must
regenerate `data/projections/`** through the pipeline writer.

### 2. Reports go to files — paste transit fails

**Terminal output does not survive paste transit** for anything table-dense; it garbled twice (the
3c.5 floors table, the A4 proposal). Therefore:

- **Ratification proposals** → `docs/proposals/<ITEM>.md`, with a lifecycle header. Working documents:
  once ratified their content moves to `CALIBRATION_LOG`/`DECISIONS` and the file is **deleted** at
  the next boundary. (Already in CLAUDE.md.)
- **PR summaries** → **`docs/pr-summaries/`** — a **stable home, explicitly OUTSIDE the proposal
  lifecycle. Retained, not retired.** Three were written into `docs/proposals/` and two were then
  deleted a cycle later as "spent", flagged by the reviewer both times. They are not proposals; they
  do not expire.
- The terminal reply carries the headline finding, the recommendation, and the file path — nothing
  that needs a table.

### 3. A test can enforce a broken contract — the LARAMIE lesson

`tests/test_schedule_intel.py` carried a fixture `"elevation": 2194.0` annotated **`# ~7200 ft`**, and
`test_altitude_passthrough_for_high_venue` asserted `intel["altitude"] == 2194.0`. The comment said
feet, the value was metres, and **the test pinned the unconverted passthrough** — enshrining the bug
it should have caught, and passing for the entire life of the defect.

**Therefore: regression pins assert PHYSICAL MEANING, not stored values.** Not *"altitude equals
2194.0"* but *"a ~7,200 ft venue clears the 4,000 ft threshold and produces `altitude_value`"*, plus
the negative case (*"a sea-level venue does not"*), the boundary case (*"a neutral site yields no
edge however high"*), and the honest-missing case (*"no elevation yields `None`, never `0.0`"*). A
passthrough assertion tests that the plumbing runs; it does not test that the number means anything.

## (e) The remaining path, in order

1. **Lint-scope fold-in (pre-tag).** Fold `factors/factor_registry.py` + `engine/prediction_engine.py`
   into the Makefile's `LINT_PATHS` / `TYPED_PATHS`, `ruff --fix`, resolve or scope residual mypy
   errors. ~200 pre-existing style errors (mostly blank-line whitespace). **Must land pre-tag because
   fixing them EDITS freeze-bound files**, impossible after the tag.
   **Success criterion: ZERO behaviour change, PROVEN — not asserted.** Capture a full-slate output
   hash before and after and show they are identical. The method used for A3 works: build the wk1
   predictions payload and hash it, and diff the 330-game tracked-slate run field-by-field. Per
   doctrine (d)(1), run **all six** verify targets afterwards.
2. **`calibration-auditor` pre-flight.** Run the agent over the complete `docs/CALIBRATION_LOG.md`:
   every entry evidence-class-labelled with the class matching the claim; magnitudes HFA-scale-checked;
   ratification stamps present; **no orphaned PROPOSED entries**; cross-entry consistency; plus the
   reverse check (grep `factors/`/`engine/` for numeric literals lacking a log entry). **It must
   return FREEZE-READY.** Resolve every finding before tagging.
3. **Owner cuts `v2026-frozen` manually.** Owner-only action; never do this.
4. **Then Phase 5** — the automation pipeline — is the next work stream, **post-tag**, with its own
   plan-mode cycle. See `docs/PHASE5_NOTES.md` (binding cadence refinements) and SPEC §10. The
   rehearsal regimen runs **after** the tag.

## (f) Freeze-hook obligation — at tag time

From `docs/FREEZE_CHECKLIST.md`: **when the tag is cut, extend `.claude/hooks/protect_immutable.py`
so `factors/`, `engine/`, and the weight/threshold/calibration config become immutable.** Today the
hook protects only the append-only data directories. After the tag it must also refuse edits to the
frozen code paths unless a documented SPEC §3 exception plus a new tag is in play. **The friction is
the point.**

Also on the checklist, already recorded: a **post-tag cleanup list** carrying the orphaned
`cli/app.py` legacy functions (`run_weekly_analysis`, `run_p4_predictions`, ~430 lines, unreachable
since the A2 retirement removed their only caller). `cli/` is freeze-exempt, so that lands after the
tag.

## (g) Session-depth lesson

**A session that has corrected its own already-merged claims is at the handoff signal.** The writing
session produced two such corrections (§c). Both were caught, neither was harmful — but the remaining
work is a freeze-bound refactor whose entire success criterion is *proving nothing changed*, followed
by an audit gating an **irreversible tag**. That is the wrong work to carry on accumulated context,
which is why this file exists and why the fold-in was deliberately **not** started.

---

## Standing constraints (imperative, unchanged)

- **No AI attribution** in commits or PR text; `includeCoAuthoredBy` stays `false`.
- **No hardcoded team/conference names** outside the registry. **No fabricated or neutral-filled
  data** — record `missing` with provenance.
- **`data/predictions/` is byte-immutable forever (D22)**; `data/results|archive|lines|ratings|
  projections|graded/` are append-only (D23); **`reports/` are regenerable renderings** — not
  hook-protected, git history is their audit trail.
- **Propose → pause → ratify** for every calibration disposition; **`code-reviewer` on the diff before
  every PR — a NO-GO is binding.** Its record here is real: it caught the checklist self-contradiction
  and the `inspect_snapshot` stale-unit display in this stretch alone.
- **Owner-only:** calibration changes, the freeze itself, changes to SPEC §16, anything that spends
  money.

*Delete this file in the PR that closes the freeze sequence, once its content is absorbed.*
