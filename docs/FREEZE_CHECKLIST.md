# Freeze checklist — before tagging `v2026-frozen`

Durable home for everything that **must happen before the freeze tag** (target **~2026-08-24**, before the
Week-0 prediction run; SPEC §3 / §16.2). Anything that touches `factors/`, `engine/`, or weight/threshold
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
  one deliberate **failure-injection drill** proving the auto-Issue path; and a graded **Week-0 /
  opening-weekend** cycle as the live dress rehearsal. Rehearsals run **after** the tag (they exercise the
  frozen model end-to-end).

## Done (for the record)

- All calibration entries ratified through 3d (CALIBRATION_LOG Phases 2 / 3b / 3c / 3d).
- `StyleMismatch` ±4.0 range examined + tightened to ±1.5, pace phantom (Bug #16) neutralized (3c.10 → 3d)
  — the last deferred pre-freeze calibration item.

## Explicitly NOT freeze-prep (Phase 4, post-freeze, freeze-exempt `analytics/`)

- Filling `closing_spread` / `clv` at grading (the schema-v2 fields + convention are frozen; the grading
  path is Phase 4).
- Per-factor attribution that converts this season's `reasoned` entries → `measured` for 2027.
