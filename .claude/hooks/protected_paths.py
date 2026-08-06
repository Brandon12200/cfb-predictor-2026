#!/usr/bin/env python3
"""Single source of truth for the guarded artifact directories (D22 / D23).

Both `PreToolUse` hooks import `PROTECTED` from here — `protect_immutable.py` (which guards
Edit/Write/NotebookEdit) and `guard_bash.py` (which guards the shell paths that would otherwise
bypass it). **Never duplicate this tuple**: a second copy is how the two guards drift apart, and a
drifted guard is worse than none because it reads as covered.

Taxonomy (D23, owner 2026-07-09):
  * **claims** — `data/predictions/` — byte-immutable forever (D22)
  * **outcomes + derived** — `data/results/`, `data/archive/`, `data/lines/`, `data/ratings/`,
    `data/projections/`, `data/graded/` — append-only
  * **renderings** — `reports/` — regenerable, git history is their audit trail, deliberately
    **NOT** guarded

**At the `v2026-frozen` tag** the frozen code paths (`factors/`, `engine/`, weight/threshold
config) join this tuple — see `docs/FREEZE_CHECKLIST.md`. Both hooks inherit the addition
automatically, which is the point of keeping the list here.
"""

PROTECTED = (
    # --- Append-only artifact history (D22 / D23) ---------------------------------------------
    "data/predictions/",
    "data/results/",
    "data/archive/",
    "data/lines/",
    "data/ratings/",
    "data/projections/",
    "data/graded/",
    # --- FROZEN MODEL CODE — added at the `v2026-frozen` tag, 2026-08-05 -----------------------
    # The tag freezes the model for the season (SPEC §3, CLAUDE.md binding principle 3). Every
    # ratified calibration constant lives inside these two directories: the 3b.1 physical
    # coefficients, `prediction_engine`'s NO_BET floors and confidence tiers (3c.5/3c.6), the
    # `factor_registry` hierarchy overrides (B2), `power_ratings`' EloConfig (D9/D11/D12), and
    # `variance_detector`'s CV cutoffs (B4). Output-altering changes now require a documented
    # SPEC §3 exception plus a NEW tag — the friction is the point.
    "factors/",
    "engine/",
)

# `config.py` is deliberately NOT frozen (ratified: DECISIONS.md **D28**). Its residual threshold-shaped literals
# (`min_confidence_threshold`, `max_confidence_threshold`, `edge_thresholds`) have **zero
# consumers** — verified by grep across `factors/`, `engine/`, `analytics/` and `cli/`; the A5
# retirement removed the live category weights and left these orphaned. Freezing the file would
# lock nothing calibrational while blocking the API budget, rate limits and cache settings that
# Phase 5 legitimately needs to change. The dead literals are a 2027 cleanup item, not a freeze
# target. `season.json` is likewise operational (calendar + CLI defaults), not calibration.
#
# ⚠ Path-based protection cannot see a change that reaches model output through the freeze-EXEMPT
# `data/` seam — which has happened twice (A6's metres/feet fix, the venue-timezone fallback).
# `scripts/slate_fingerprint.py` + the `verify-phase-3` slate-hash gate close that gap
# BEHAVIOURALLY. Both layers are required; neither is sufficient alone.
