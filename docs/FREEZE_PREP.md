# Freeze-prep checklist — before tagging `v2026-frozen`

Durable home for items that **must be resolved before the freeze tag** (target **2026-08-24**, before
the Week-0 prediction run; SPEC §3 / §16.2). Items that touch `factors/`, `engine/`, or weight/threshold
config **cannot** be done after the tag (those become immutable), so they belong here, not in an
evaporating PR body. Phase 3 is complete (3a→3d); this is the Phase-3 → freeze handoff.

## Open

- [ ] **Fold `factors/factor_registry.py` + `engine/prediction_engine.py` into CI `LINT_PATHS` / `TYPED_PATHS`.**
  Carried from the **3c** code-review (should-fix #2) and **3d** — deferred both times because these
  legacy files carry ~200 pre-existing ruff style errors (mostly blank-line whitespace) that would bury a
  phase diff. 3d only added `follow_imports = "skip"` for them in `pyproject.toml` (so mypy **skips** them
  as imports) — it did **not** lint or type-check them. **This must land before the freeze:** fixing the
  style errors *edits* these freeze-bound files, which is impossible after the tag. Scope: add both to the
  Makefile paths, run `ruff --fix`, resolve the residual mypy errors (or scope them), one focused cleanup PR.

- [ ] **Tag `v2026-frozen`** (the freeze itself) — owner-only, after all calibration is locked and every
  verify target is green. Freezes `factors/`, `engine/`, and weight/threshold config for the season.

## Done (for the record)

- All `reasoned` calibration entries ratified through 3d (CALIBRATION_LOG Phases 2 / 3b / 3c / 3d).
- `StyleMismatch` ±4.0 range examined + tightened to ±1.5 (3c.10 → 3d), closing the last deferred
  pre-freeze calibration item.

## Explicitly NOT freeze-prep (Phase 4, post-freeze)

- Filling `closing_spread` / `clv` at grading (the schema-v2 fields exist + the convention is documented;
  the grading path is Phase 4, freeze-exempt `analytics/`).
- Per-factor attribution that converts this season's `reasoned` entries → `measured` for 2027.
