#!/usr/bin/env python3
"""PreToolUse hook (IMPLEMENTATION §2.1): protect append-only historical artifacts.

Artifact taxonomy (D23): **claims** (`data/predictions/`) are byte-immutable forever (D22);
**outcomes + derived computations** (`data/results/`, `data/archive/`, `data/lines/`,
`data/ratings/`, `data/projections/`, `data/graded/`) are append-only (new files/entries added,
existing ones never edited). Both are guarded here. **Renderings** (`reports/`) are pure functions
over those artifacts, regenerable at will — their audit trail is git history — so they are NOT
guarded (D23, owner 2026-07-09).

Blocks Edit/Write/NotebookEdit that would MODIFY an existing guarded file; creating a brand new file
there (what the pipeline does) is allowed. Exit code 2 blocks the call.
"""

import json
import os
import sys

PROTECTED = ("data/predictions/", "data/results/", "data/archive/", "data/lines/",
             "data/ratings/", "data/projections/", "data/graded/")

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

for prefix in PROTECTED:
    if rel.startswith(prefix):
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
