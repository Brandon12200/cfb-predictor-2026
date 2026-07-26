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

**Deliberately STRICTER than `protect_immutable.py` in one respect.** That hook permits *creating*
a new file under a protected directory (the pipeline's normal write) and blocks only modifying an
existing one. This guard blocks shell writes into those directories **unconditionally**, because
every legitimate writer in this project is Python (`open()` inside `scripts/`/`analytics/`), never
shell redirection — so there is no benign shell case to preserve, and deciding existence would mean
parsing a path out of an arbitrary command line. The asymmetry is extra friction, not a hole: it
fails closed. Recorded here so it reads as intended rather than as drift between the two guards.

**Known, accepted false positive.** Matching is over the raw command string, so ANY command whose
*text* contains a denied shape is blocked, even when nothing destructive would execute and even
when git is never invoked — a `git commit` heredoc describing this hook, a `python3 - <<EOF` block
embedding one of these strings as test data, a `grep` for the pattern. Distinguishing a quoted
body from a real argument means parsing shell, which is where guards acquire holes. A guard whose
job is friction should fail closed, so this is left as-is. **Workaround:** put the text in a file
(`git commit -F <file>`, a heredoc-free script) instead of inline. Pinned by a test so the
behaviour is intended, not rediscovered.

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

# Global options that may sit BETWEEN `git` and its subcommand. Without these, every destructive
# rule below is bypassed by one extra flag — `git -C <dir> checkout -- data/predictions/` was
# ALLOWED by the first version of this hook, which is the exact escape it exists to prevent.
# Enumerated explicitly (rather than a permissive `-\S+` wildcard) so the pattern cannot
# over-consume the subcommand token itself.
_GIT_GLOBAL = (
    r"(?:\s+(?:"
    r"-C\s+\S+|-c\s+\S+"
    r"|--git-dir(?:=|\s+)\S+|--work-tree(?:=|\s+)\S+|--namespace(?:=|\s+)\S+"
    r"|--exec-path(?:=\S+)?"
    r"|-P|--no-pager|--bare|--no-replace-objects"
    r"|--literal-pathspecs|--glob-pathspecs|--noglob-pathspecs|--icase-pathspecs"
    r"))*"
)
# `git` plus any run of global options, up to (not including) the subcommand.
_GIT = rf"git{_GIT_GLOBAL}\s+"

# Subcommand flags that may precede a commit-ish. `(?:=\S+)?` is load-bearing: without it
# `git checkout --track=origin/main <sha>` slipped through, because an `=`-form flag broke the
# skip and the whole alternation failed rather than stepping over the flag.
_SUBFLAG = r"(?:-[a-zA-Z-]+(?:=\S+)?\s+)*"


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
    if re.search(rf"{_GIT}checkout\b{_SEG}\s--\s", command):
        _block(
            "Blocked: `git checkout -- <pathspec>` overwrites working-tree files. If this targets "
            "a protected artifact directory it would also revert append-only history (D22/D23). "
            "Use `git diff` to inspect; restore deliberately outside the agent session."
        )
    # `-B` force-creates-or-RESETS an existing branch over the working tree — destructive, unlike
    # `-b`, which errors if the branch exists. Checked before the `-b` exemption below.
    if re.search(rf"{_GIT}checkout\s+{_SUBFLAG}?-B\b", command):
        _block(
            "Blocked: `git checkout -B <branch>` force-resets an existing branch. "
            "Use `git checkout -b` for a new branch."
        )
    # `git checkout <sha>` (a commit-ish, not a branch) — but `-b` is branch CREATION, always fine.
    if not re.search(rf"{_GIT}checkout\s+-b\b", command):
        # `{7,}` not `{7,40}`: an over-long hex token is not a valid sha, but it must not slip
        # through on a length technicality either. A branch named in 7+ hex chars is collateral.
        if re.search(rf"{_GIT}checkout\s+{_SUBFLAG}[0-9a-f]{{7,}}\b", command):
            _block(
                "Blocked: `git checkout <sha>` detaches HEAD over the working tree. "
                "Use `git show <sha>` / `git diff <sha>` to inspect a commit read-only."
            )
    if re.search(rf"{_GIT}restore\b", command):
        _block("Blocked: `git restore` discards working-tree changes. Inspect with `git diff`.")
    if re.search(rf"{_GIT}reset\b{_SEG}--hard\b", command):
        _block("Blocked: `git reset --hard` discards committed and working-tree state.")
    if re.search(rf"{_GIT}clean\b{_SEG}-[a-zA-Z]*f", command):
        _block("Blocked: `git clean -f` deletes untracked files irrecoverably.")
    if re.search(rf"{_GIT}stash\s+(pop|apply)\b", command):
        _block("Blocked: `git stash pop|apply` mutates the working tree. (`git stash list` is fine.)")
    if re.search(rf"{_GIT}apply\b", command):
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
