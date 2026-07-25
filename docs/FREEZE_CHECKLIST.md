# Freeze checklist — before tagging `v2026-frozen`

Durable home for everything that **must happen before the freeze tag** (target **~2026-08-24**, before the
opening-weekend (Week 1) prediction run; SPEC §3 / §16.2). Anything that touches `factors/`, `engine/`, or weight/threshold
config **cannot** be done after the tag (those become immutable), so it belongs here — not in an
evaporating PR body. Phase 3 is complete (3a→3d); this is the Phase-3 → freeze handoff.

## Must land BEFORE the tag

- [ ] **Fold `factors/factor_registry.py` + `engine/prediction_engine.py` into CI `LINT_PATHS` / `TYPED_PATHS`.**
  Carried from the **3c** code-review (should-fix #2) and **3d** — deferred both times because these legacy
  files carry ~200 pre-existing ruff style errors (mostly blank-line whitespace) that would bury a phase
  diff. 3d only added `follow_imports = "skip"` for them in `pyproject.toml` (so mypy **skips** them as
  imports) — it did **not** lint or type-check them. **Must land before the freeze:** fixing the style
  errors *edits* these freeze-bound files, impossible after the tag. Scope: add both to the Makefile paths,
  `ruff --fix`, resolve residual mypy errors (or scope them), one focused cleanup PR.

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

- [ ] **Formal pre-freeze calibration audit (~2026-08-20).** Run the **`calibration-auditor`** agent over
  the complete `docs/CALIBRATION_LOG.md`: every entry evidence-class-labeled with the class matching the
  claim; magnitudes HFA-scale-checked; ratification stamps present; **no orphaned PROPOSED entries**;
  cross-entry consistency; and the reverse check — grep the frozen paths (`factors/`, `engine/`) for numeric
  literals and flag any constant lacking a log entry. This is the freeze's formal pre-flight; resolve every
  finding before tagging.

- [ ] **Extend the freeze-enforcement hook** (`.claude/hooks/protect_immutable.py`) to make `factors/`,
  `engine/`, and the weight/threshold/calibration config **immutable at tag time** (today the hook protects
  the append-only data dirs; at the freeze it must also refuse edits to the frozen code paths unless a
  documented SPEC §3 exception + new tag is in play).

- [ ] **Confirm all calibration is locked** — every constant ratified (Phases 2 / 3b / 3c / 3d all
  RATIFIED); `make verify-phase-1/2/3` green; `make test` green.

## The tag

- [ ] **Tag `v2026-frozen`** (owner-only) once the above are clean. Freezes `factors/`, `engine/`, and
  weight/threshold config for the season. After this, output-altering changes require the SPEC §3 exception
  process (a dated exception entry + a new tag).

## AFTER the tag (dress rehearsal, not freeze-prep)

- [ ] **Preseason validation regimen** (Phase-5 acceptance; see `docs/PHASE5_NOTES.md`): two clean
  full-cycle pipeline rehearsals in mid-August against the real week-1 slate (rehearsal-marked commits);
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

## Done (for the record)

- All calibration entries ratified through 3d (CALIBRATION_LOG Phases 2 / 3b / 3c / 3d).
- `StyleMismatch` ±4.0 range examined + tightened to ±1.5, pace phantom (Bug #16) neutralized (3c.10 → 3d)
  — the last deferred pre-freeze calibration item.

## Explicitly NOT freeze-prep (Phase 4, post-freeze, freeze-exempt `analytics/`)

- Filling `closing_spread` / `clv` at grading (the schema-v2 fields + convention are frozen; the grading
  path is Phase 4).
- Per-factor attribution that converts this season's `reasoned` entries → `measured` for 2027.
