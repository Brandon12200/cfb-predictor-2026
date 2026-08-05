# Freeze checklist — before tagging `v2026-frozen`

> **The reverse-audit ledger is CLOSED** (A1–A6, B1–B10 — 2026-07-25, merged through PR #20).
> Remaining pre-tag work, in order: **lint-scope fold-in → `calibration-auditor` pre-flight →
> FREEZE-READY → owner cuts the tag.** Full carry-forward for a fresh session:
> **`docs/HANDOFF_FREEZE.md`**.

Durable home for everything that **must happen before the freeze tag**. **The tag is cut on
FREEZE-READY, target ~2026-08-08** — per owner ruling 2026-08-03 (originally g1, July), superseding
the earlier ~2026-08-24 planning date. **The `calibration-auditor` verdict is the gate; the date is
a target.** The tag must precede the opening-weekend (Week 1) prediction run (SPEC §3 / §16.2);
2026-08-29 remains the absolute outer bound. Anything that touches `factors/`, `engine/`, or weight/threshold
config **cannot** be done after the tag (those become immutable), so it belongs here — not in an
evaporating PR body. Phase 3 is complete (3a→3d); this is the Phase-3 → freeze handoff.

## Must land BEFORE the tag

- [x] **Fold `factors/factor_registry.py` + `engine/prediction_engine.py` into CI `LINT_PATHS` — DONE
  (2026-07-25).** Carried from the **3c** code-review (should-fix #2) and **3d** — deferred both times
  because these legacy files carried ~200 pre-existing ruff style errors that would bury a phase diff.
  Landed pre-tag because fixing them *edits* freeze-bound files, impossible after the tag. **All 170 ruff
  violations resolved; both files are in `LINT_PATHS`. `TYPED_PATHS` is deliberately unchanged** — see the
  2027 known-state list below. **Zero behaviour change proven, not asserted:** week-1 predictions payload
  and envelope SHA-256 identical, 330-game tracked slate identical (0 of 330 records differ across 154,937
  compared scalar fields, max |Δ| edge / confidence / model_spread = 0.000000000000), `make test` 449
  passed / 2 skipped, `make lint` green on the widened scope, all six verify targets PASS.

- [x] **Disposition the reverse-audit ledger — A1–A5 DONE (2026-07-25); B1–B10 DONE (2026-07-16).**
  The `calibration-auditor` shakedown found the log's **reverse** coverage materially incomplete.
  **A1–A5 are now all dispositioned and ratified** (CALIBRATION_LOG "A-item dispositions"): A1
  `HeadToHeadRecord` accepted **dormant** (threshold==max *and* an always-zero placeholder input —
  both blockers logged so 2027 can't "fix" one and think it restored); A2 the second confidence/edge
  scoring surface **retired** (full cluster + carry-forward item 5's dev-script cluster deleted;
  `prediction_engine` is now the only scoring surface in `engine/`); A3 `variance_detector` category
  map **fixed**, output-neutrality proven over 744 games; A4 ladder collapse **accepted and logged,
  not rescaled** (a rescale was measured and rejected — it would misclassify every actual bet as
  VERY_STRONG), plus `predicted_edge` persistence raised 2 dp → 4 dp; A5 stale category weights
  **retired** with A2 and `cli status` repointed at the live registry.
  **B1–B10 RATIFIED** (owner, 2026-07-16) — audited per-number with liveness measured on both
  vehicles; six dead constants logged rather than ratified; `MarketSentiment` ruled dormant-and-unwired
  for all of 2026 (movement data collected, activation deferred to 2027).
  A1–A5 and B1–B10 are all dispositioned; this item is closed. The late item it surfaced is tracked
  separately immediately below, so this checkbox reflects only what it covers.

- [x] **A6 (late A-class) — `Altitude` unit mismatch: FIXED (owner-ratified, 2026-07-16).** Venue
  `elevation` was metres compared against a 4000-**foot** threshold, so the factor could never fire.
  Fixed at the read/access seam in freeze-exempt `data/` (option (a)): elevation stays **metres at
  rest**, `schedule_intel.altitude` is emitted in **feet**, the ratified 3b.1 constants and the
  committed snapshot bytes are **untouched**. Measured: **0 → 16 of 330** tracked-slate activations;
  max edge unchanged; wk1 golden hash identical (no regeneration). `docs/SCHEMA.md` now states the
  unit contract; regression pins added for high-altitude, sea-level, neutral-site and missing-elevation.
  **Venue coverage investigated and closed: not a defect** — 68 is SPEC §5.5's specified P4+independents
  scope, not a gap. See CALIBRATION_LOG "A6".

- [x] **Formal pre-freeze calibration audit — COMPLETE. FINAL VERDICT: FREEZE-READY**
  (re-run 2026-08-04 @ `d112d4e` — **0 blockers**, 2 should-fix, 1 nit, none tag-blocking).
  **Authoritative verdict: `docs/preflight_verdict_rerun.md`.**

  Two runs, both on `main`, full charter each time:

  | Run | Commit | Verdict |
  |---|---|---|
  | 1 — 2026-08-03 | `560d268` | **NOT-FREEZE-READY** — 2 blockers, 5 should-fix, 2 nits (`docs/preflight_verdict.md`) |
  | 2 — 2026-08-04 | `d112d4e` | **FREEZE-READY** — 0 blockers (`docs/preflight_verdict_rerun.md`) |

  > **⚠ `docs/preflight_verdict.md` (run 1) is SUPERSEDED and retained only as the audit trail of
  > what was found and fixed.** Its NOT-FREEZE-READY verdict and its nine findings are all closed —
  > see PR #25 for the dispositions. **Do not read run 1 as the freeze state.**

  Between the runs: PR **#25** (all nine run-1 findings dispositioned; `StyleMismatch` dormant,
  eleven momentum constants ratified per-number), PR **#26** (venue-timezone fallback — a
  behavior-affecting data fix), PR **#27** (edge-ceiling structural property + two integrity fixes).
  Run 2 re-verified both prior blockers **closed in source**, found **no regressions**, and
  independently recomputed the edge-ceiling figures by hand rather than trusting the script.

  **Early by choice:** ran on *ledger-close* rather than the original ~2026-08-20 calendar date, per
  **D26** — the trigger is the FREEZE-READY verdict, not a date; running early created the room to
  disposition what run 1 found.

  **Re-run condition, STILL BINDING until the tag exists:** any change to `factors/`, `engine/`, the
  weight/threshold/calibration config, or `docs/CALIBRATION_LOG.md` **invalidates the FREEZE-READY
  verdict and forces a third run.** A verdict does not carry across a change to what it graded.

  **Two non-blocking should-fix items carried to the F-close PR** (neither gates the tag; full
  reasoning in the re-run verdict): **S-1** — delete `docs/HANDOFF_FREEZE.md`, which its own
  lifecycle header already requires and which is now stale on the remaining path and two
  defect-family tallies; **S-2** — add `engine/matchup_pricer.py:205`'s `uncertainty > 0.5` to
  `docs/CALIBRATION_EXCLUSIONS.md` as a caveat-string threshold (verified non-tunable: it gates only
  a human-readable string, while the rating-signal weight comes from the ratified D11 formula at
  `:167`, independent of it).

- [ ] **Extend the freeze-enforcement hook** to make `factors/`, `engine/`, and the
  weight/threshold/calibration config **immutable at tag time** (today the hooks protect the append-only
  data dirs; at the freeze they must also refuse edits to the frozen code paths unless a documented
  SPEC §3 exception + new tag is in play).
  **Edit `.claude/hooks/protected_paths.py` — the single shared `PROTECTED` tuple (D25) — not the hooks
  themselves.** Then **verify `guard_bash.py`'s protected-path mutation rules inherit the new entries**:
  after adding `factors/`/`engine/`, confirm that `rm factors/<file>`, `sed -i` on one, and redirection
  into one are all blocked, alongside the `Edit`/`Write` guard. *(Only that scoped-mutation class reads
  `PROTECTED`; the destructive-git denials are global and path-independent, so they need no update — they
  are already what stops `git checkout <sha> -- factors/`.)* `tests/test_hook_guard_bash.py` pins the
  inheritance with a sandboxed `PROTECTED` containing `factors/`; extend its live matrix at the tag.

- [ ] **Confirm all calibration is locked** — every constant ratified (Phases 2 / 3b / 3c / 3d all
  RATIFIED); `make verify-phase-1/2/3` green; `make test` green.

## The tag

- [ ] **Tag `v2026-frozen`** (owner-only) once the above are clean. Freezes `factors/`, `engine/`, and
  weight/threshold config for the season. After this, output-altering changes require the SPEC §3 exception
  process (a dated exception entry + a new tag).

## AFTER the tag (dress rehearsal, not freeze-prep)

- [ ] **Preseason validation regimen** (Phase-5 acceptance; see `docs/PHASE5_NOTES.md`).
  **Binding schedule (owner, 2026-08-03): pipeline PR by Aug 14, first rehearsal cycle by Aug 17.**
  Two clean full-cycle pipeline rehearsals against the real week-1 slate (rehearsal-marked commits);
  one deliberate **failure-injection drill** proving the auto-Issue path; and a graded
  **opening-weekend (Week 1)** cycle as the live dress rehearsal. **D8 abolished Week 0 for 2026**, so
  "Week 0" here means the season's first real slate — Week 1. Rehearsals run **after** the tag (they
  exercise the frozen model end-to-end).

## AFTER the tag — post-tag cleanup list (freeze-exempt; recorded so it doesn't evaporate)

- [ ] **Remove the orphaned legacy analysis functions in `cli/app.py`** — `run_weekly_analysis` and
  `run_p4_predictions` (~430 lines) became unreachable when the A2 retirement deleted `cli.app.main`,
  their only caller. `cli/` is **freeze-exempt**, so this deliberately did NOT ride in the pre-tag
  ledger PR: the pre-tag window stays focused on what gates the tag, and inert dead code in a
  freeze-exempt path is safe to carry across it (owner ruling, 2026-07-25).

## 2027 known-state list (inherited, NOT defects — do not re-derive these)

Recorded at the freeze so a 2027 reader inherits them as **decided** rather than rediscovering them as
findings. Each is a conscious acceptance under the freeze-session triage standard: **only an unlogged live
constant or a behaviour-affecting defect blocks the tag; everything else is logged as a known state in one
line and inherited.** The project was closing, not opening.

- **`TYPED_PATHS` excludes `factors/factor_registry.py` + `engine/prediction_engine.py`** (they are in
  `LINT_PATHS` only). Honest typing needs `normalized_weight` / `original_weight` **declared on
  `factors/base_calculator.py`** (the registry assigns them dynamically at
  `factor_registry.py:219-225`; 6 mypy `attr-defined` errors) plus a heterogeneous-dict annotation at
  **`engine/variance_detector.py:232`** (1 `assignment` error) — *two further frozen files*, outside the
  ratified two-file scope. The alternative, a blanket per-module suppression, would make the target green
  while checking nothing. **At a 2027 unfreeze, type all four files together or not at all.**
- **`engine/variance_detector.py:232` is typing noise, not a defect** — verified: the only consumer
  (`variance_detector.py:307`) reads `inter_category_variance` as a number via `.get(..., 0)`, so the
  heterogeneous dict is intentional and nothing iterates its values expecting uniformity.
- **The rest of `factors/` and `engine/` is frozen un-linted** — `variance_detector.py`,
  `situational_context.py`, `momentum_factors.py`, `coaching_edge.py`, `style_mismatch.py`,
  `market_sentiment.py`, `base_calculator.py` are outside `LINT_PATHS`. **Style-only; style is not
  behaviour, and the tag freezes code, not cosmetics.** Lint them at the 2027 unfreeze if desired.
- **`data/`, `cli/` and the `pyproject.toml` `follow_imports = "skip"` override list are unchanged** by
  the fold-in; the override still lists modules that are now linted, which is harmless (it governs how
  mypy follows them **as imports**, not whether ruff checks them).

## Done (for the record)

- All calibration entries ratified through 3d (CALIBRATION_LOG Phases 2 / 3b / 3c / 3d).
- `StyleMismatch` ±4.0 range examined + tightened to ±1.5, pace phantom (Bug #16) neutralized (3c.10 → 3d)
  — the last deferred pre-freeze calibration item.

## Explicitly NOT freeze-prep (Phase 4, post-freeze, freeze-exempt `analytics/`)

- Filling `closing_spread` / `clv` at grading (the schema-v2 fields + convention are frozen; the grading
  path is Phase 4).
- Per-factor attribution that converts this season's `reasoned` entries → `measured` for 2027.
