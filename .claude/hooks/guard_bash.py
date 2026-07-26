#!/usr/bin/env python3
"""PreToolUse hook (IMPLEMENTATION §2.3 + §2.1): secret hygiene, history guard, shell-bypass guard.

Three jobs, in order:

(a) **Secret hygiene** — refuse to `git add` / `git commit` anything referencing `.env` or key
    material.

(b) **Destructive git, denied globally** — `git checkout` with a pathspec or a commit-ish,
    `git restore`, `git reset --hard`, `git clean -f`, `git stash pop|apply`, `git apply`. These
    overwrite working-tree state that nothing else in the project can reconstruct. Benign git is
    explicitly still allowed: `checkout -b`, plain branch switching, `diff`, `log`, `show`,
    `status`, `stash list`.

(c) **In-place mutation of the protected artifact directories** — `rm`/`rmdir`/`mv`/`cp`,
    `sed -i`, `tee`, and `>`/`>>` redirection targeting anything under `PROTECTED`. Scoped to
    those directories only; there is deliberately **no global file-mutation block**.

**Why (b) is global while (c) is scoped.** `git checkout <sha> -- data/predictions/` would revert a
byte-immutable prediction artifact (D22) and was blocked by neither hook before this: the
`Edit`/`Write` guard never fires for Bash (a shell command has no `file_path`), and the old
`rm|rmdir|mv` rule matched only three verbs. Rather than enumerate every shell shape that could
reach a protected path through git, the destructive git subcommands are denied outright — they are
never the right move inside an agent session, where the working tree is the only copy of
uncommitted work.

The protected-path list is imported from `protected_paths.py` — the SAME tuple
`protect_immutable.py` uses. Never duplicate it here: at the `v2026-frozen` tag, `factors/`,
`engine/` and the calibration config join that tuple and this guard must inherit them.

**Known, accepted false positive.** Matching is over the raw command string, so a command whose
*text* merely mentions a denied shape — most commonly a `git commit` heredoc whose message
describes this hook — is blocked even though it would execute nothing destructive. Distinguishing a
heredoc body from an argument means parsing shell, which is where guards acquire holes. A guard
whose job is friction should fail closed, so this is left as-is. **Workaround:** write the message
to a file and use `git commit -F <file>`. Pinned by a test so the behaviour is intended, not
discovered.

Exit code 2 blocks the call.
"""

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from protected_paths import PROTECTED  # noqa: E402  (single source of truth — never duplicate)

# `data/predictions/` -> `data/predictions`, joined into one alternation.
_PROTECTED_ALT = "|".join(re.escape(p.rstrip("/")) for p in PROTECTED)

# A command segment: stop at a pipe/semicolon/&& so one clause's arguments cannot leak into the
# next clause's match.
_SEG = r"[^|;&]*"


def _block(message: str) -> None:
    sys.stderr.write(message if message.endswith("\n") else message + "\n")
    sys.exit(2)


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    command = (payload.get("tool_input", {}) or {}).get("command", "")
    if not command:
        sys.exit(0)

    # ── (a) Secret hygiene ────────────────────────────────────────────────────────────────────
    secret_pat = r"(\.env(\.|\b)|secrets?\.txt|api[_-]?keys?\.txt|\.pem\b|\.key\b)"
    if re.search(r"git\s+add\b", command) and re.search(secret_pat, command):
        _block("Blocked: refusing to `git add` secrets (.env/keys). They stay gitignored.")
    if re.search(r"git\s+commit\b", command) and re.search(r"\.env(\.|\b)", command):
        _block("Blocked: refusing to commit anything referencing .env.")

    # ── (b) Destructive git, denied globally ──────────────────────────────────────────────────
    # `git checkout ... -- <pathspec>` restores files over the working tree.
    if re.search(rf"git\s+checkout\b{_SEG}\s--\s", command):
        _block(
            "Blocked: `git checkout -- <pathspec>` overwrites working-tree files. If this targets "
            "a protected artifact directory it would also revert append-only history (D22/D23). "
            "Use `git diff` to inspect; restore deliberately outside the agent session."
        )
    # `git checkout <sha>` (a commit-ish, not a branch) — but `-b` is branch CREATION, always fine.
    if not re.search(r"git\s+checkout\s+-b\b", command):
        # `{7,}` not `{7,40}`: an over-long hex token is not a valid sha, but it must not slip
        # through on a length technicality either. A branch named in 7+ hex chars is collateral.
        if re.search(r"git\s+checkout\s+(?:-[a-zA-Z-]+\s+)*[0-9a-f]{7,}\b", command):
            _block(
                "Blocked: `git checkout <sha>` detaches HEAD over the working tree. "
                "Use `git show <sha>` / `git diff <sha>` to inspect a commit read-only."
            )
    if re.search(r"git\s+restore\b", command):
        _block("Blocked: `git restore` discards working-tree changes. Inspect with `git diff`.")
    if re.search(rf"git\s+reset\b{_SEG}--hard\b", command):
        _block("Blocked: `git reset --hard` discards committed and working-tree state.")
    if re.search(rf"git\s+clean\b{_SEG}-[a-zA-Z]*f", command):
        _block("Blocked: `git clean -f` deletes untracked files irrecoverably.")
    if re.search(r"git\s+stash\s+(pop|apply)\b", command):
        _block("Blocked: `git stash pop|apply` mutates the working tree. (`git stash list` is fine.)")
    if re.search(r"git\s+apply\b", command):
        _block("Blocked: `git apply` patches the working tree. Inspect the patch instead.")

    # ── (c) In-place mutation of the protected artifact directories ───────────────────────────
    protected_note = (
        "append-only historical artifacts (CLAUDE.md principle 5 / D22 / D23). "
        "New files may be added; existing ones are never modified, moved or deleted."
    )
    if re.search(rf"\b(rm|rmdir|mv|cp)\b{_SEG}\b({_PROTECTED_ALT})/", command):
        _block(f"Blocked: refusing to delete/move/overwrite {protected_note}")
    if re.search(rf"\bsed\s+-i{_SEG}\b({_PROTECTED_ALT})/", command):
        _block(f"Blocked: refusing in-place `sed -i` edit of {protected_note}")
    if re.search(rf"\btee\b{_SEG}\b({_PROTECTED_ALT})/", command):
        _block(f"Blocked: refusing to `tee` over {protected_note}")
    if re.search(rf">>?\s*[\"']?({_PROTECTED_ALT})/", command):
        _block(f"Blocked: refusing shell redirection into {protected_note}")

    sys.exit(0)


if __name__ == "__main__":
    main()
