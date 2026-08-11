#!/usr/bin/env python3
"""PreToolUse hook (IMPLEMENTATION §2.1): protect append-only artifacts AND the frozen model.

Two guarded classes, with **different rules** — see the loop below:

1. **Append-only historical artifacts.** Taxonomy (D23): **claims** (`data/predictions/`) are
   byte-immutable forever (D22); **outcomes + derived computations** (`data/results/`,
   `data/archive/`, `data/lines/`, `data/ratings/`, `data/projections/`, `data/graded/`) are
   append-only. Only MODIFYING an existing file is refused — creating a new one is what the
   pipeline does every week. **Renderings** (`reports/`) are regenerable and NOT guarded (D23).

2. **Frozen model code** (`factors/`, `engine/`), added at the `v2026-frozen` tag. Refused
   **unconditionally**, new files included — see the loop for why.

Exit code 2 blocks the call.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from protected_paths import PROTECTED  # noqa: E402  (single source of truth — never duplicate)

try:
    payload = json.load(sys.stdin)
except Exception:
    sys.exit(0)

tool_input = payload.get("tool_input", {}) or {}
path = tool_input.get("file_path") or tool_input.get("notebook_path") or ""
if not path:
    sys.exit(0)

project_dir = payload.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
try:
    rel = os.path.relpath(os.path.abspath(path), project_dir).replace(os.sep, "/")
except ValueError:
    rel = path.replace(os.sep, "/")

# Frozen model code is guarded MORE strictly than the append-only artifact directories. For
# artifacts, adding a new file is the pipeline's normal operation, so only modification is refused.
# For frozen code there is no legitimate new-file case at all — and
# `factor_registry._load_all_factors` DISCOVERS FACTORS BY SCANNING THE DIRECTORY, so a new file
# dropped into `factors/` would be auto-registered, change the normalization denominator, and
# renormalize every other factor's weight. Inheriting the artifact exemption here left exactly that
# hole; it is closed.
FROZEN_CODE = ("factors/", "engine/")

for prefix in PROTECTED:
    if not rel.startswith(prefix):
        continue

    if prefix in FROZEN_CODE:
        sys.stderr.write(
            f"Blocked: {rel} is FROZEN MODEL CODE (the freeze tag; SPEC §3, CLAUDE.md "
            f"binding principle 3). Weights, thresholds, factor logic and confidence math are "
            f"immutable for the 2026 season — and this applies to NEW files too, because "
            f"`factors/` is scanned for factor classes at load, so adding one changes the "
            f"registry and renormalizes every weight. An output-altering change requires a "
            f"documented SPEC §3 exception entry AND a new tag, not an edit. If you believe the "
            f"change does not alter output, it still waits: the freeze is enforced behaviourally "
            f"too, and `scripts/slate_fingerprint.py` will prove whether it does.\n"
        )
        sys.exit(2)

    if os.path.exists(path):
        sys.stderr.write(
            f"Blocked: {rel} is an append-only historical artifact "
            f"(CLAUDE.md principle 5 / D22 / D23). Editing/overwriting existing "
            f"prediction/result/archive/graded files is not allowed; only "
            f"new files may be added. (Renderings under reports/ are regenerable — not guarded.)\n"
        )
        sys.exit(2)
    break

sys.exit(0)
