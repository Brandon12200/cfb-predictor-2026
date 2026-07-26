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
    "data/predictions/",
    "data/results/",
    "data/archive/",
    "data/lines/",
    "data/ratings/",
    "data/projections/",
    "data/graded/",
)
