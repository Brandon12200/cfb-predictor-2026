#!/usr/bin/env python3
"""PreToolUse hook (IMPLEMENTATION §2.1): protect append-only historical artifacts.

Blocks Edit/Write/NotebookEdit that would MODIFY an existing file under
data/predictions/, data/results/, data/archive/, or reports/. Creating a brand
new file there (what the pipeline does) is allowed; overwriting/editing an
existing one is not (CLAUDE.md binding principle 5). Exit code 2 blocks the call.
"""

import json
import os
import sys

PROTECTED = ("data/predictions/", "data/results/", "data/archive/", "data/lines/",
             "data/ratings/", "reports/")

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
                f"(CLAUDE.md principle 5). Editing/overwriting existing "
                f"prediction/result/archive/report files is not allowed; only "
                f"the pipeline appends new files.\n"
            )
            sys.exit(2)
        break

sys.exit(0)
