#!/usr/bin/env python3
"""PreToolUse hook (IMPLEMENTATION §2.3 + §2.1): secret hygiene and history guard.

Blocks Bash commands that would (a) stage/commit secrets (.env, key/pem files),
or (b) delete/move append-only artifacts under data/predictions|results|archive
or reports/. Exit code 2 blocks the call.
"""

import json
import re
import sys

try:
    payload = json.load(sys.stdin)
except Exception:
    sys.exit(0)

command = (payload.get("tool_input", {}) or {}).get("command", "")
if not command:
    sys.exit(0)

# (a) Secret hygiene: refuse to add/commit .env or key material.
secret_pat = r"(\.env(\.|\b)|secrets?\.txt|api[_-]?keys?\.txt|\.pem\b|\.key\b)"
if re.search(r"git\s+add\b", command) and re.search(secret_pat, command):
    sys.stderr.write("Blocked: refusing to `git add` secrets (.env/keys). They stay gitignored.\n")
    sys.exit(2)
if re.search(r"git\s+commit\b", command) and re.search(r"\.env(\.|\b)", command):
    sys.stderr.write("Blocked: refusing to commit anything referencing .env.\n")
    sys.exit(2)

# (b) Immutable history: refuse rm/rmdir/mv targeting protected dirs.
if re.search(r"\b(rm|rmdir|mv)\b[^|;&]*\b(data/predictions|data/results|data/archive|data/lines|reports)/",
             command):
    sys.stderr.write(
        "Blocked: refusing to delete/move append-only artifacts under "
        "data/predictions|results|archive|lines or reports/ (CLAUDE.md principle 5).\n"
    )
    sys.exit(2)

sys.exit(0)
