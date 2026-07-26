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

**How git is matched, and why it is not a regex.** Two earlier versions matched
``git\\s+<verb>`` against the raw string and both leaked: `git -C <dir> checkout -- data/predictions/`
slipped past every rule, and after global options were enumerated, any option *outside* that
enumeration (`--no-optional-locks`, `-p`) slipped past just as silently — a closed set is the wrong
shape for this. So the command is split into clauses, each clause is tokenized, and for a git
invocation **every token is scanned** for a destructive subcommand. No verb position is assumed,
so an unknown global option cannot shift the verb out of view. `-c alias.X=<verb>` is denied
outright, since git resolves the alias itself and no token check could see the real verb.

**Residual over-blocks, accepted — two of them, both hit for real.** A heredoc LINE that itself
begins with a denied command reads as a real clause; and prose containing the `$(` substitution
form near a destructive verb trips the substitution rule (this blocked the PR description that
*explained* the substitution rule). Distinguishing either would mean tracking heredoc and quoting
state, which is where guards acquire holes. Both fail closed; the workaround in both cases is to
put the text in a file (`git commit -F <file>`, `gh pr create --body-file <file>`). Tokenizing did
remove the broader false positive the regex version had, where any prose *mentioning* a denied
command was blocked — a quoted argument is now a single token and never equals a subcommand name.

**A third accepted over-block: reading OUT of a protected directory.** Guard (c) matches its verbs
without distinguishing source from destination, so `cp data/predictions/x.json /tmp/backup.json`
— which leaves the original untouched — is blocked. Telling source from destination means knowing
each verb's argument grammar (`cp SRC DST`, `dd if=/of=`, `install -m MODE SRC DST`), i.e. another
enumerated set, which is the shape that has now failed twice here. Use `Read`, or copy via Python.

All three over-blocks are pinned by tests so they read as intended rather than as bugs.

Exit code 2 blocks the call.
"""

import json
import os
import re
import shlex
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from protected_paths import PROTECTED  # noqa: E402  (single source of truth — never duplicate)

# `data/predictions/` -> `data/predictions`, joined into one alternation.
_PROTECTED_ALT = "|".join(re.escape(p.rstrip("/")) for p in PROTECTED)

# What may follow a protected directory name. TWO rounds of review died here, both to the same
# mistake — enumerating the allowed terminators instead of using a boundary:
#   round 3: requiring a literal `/` missed `rm -rf data/predictions` (no trailing slash);
#   round 4: enumerating `/`, whitespace, quote, end-of-string missed `rm -rf data/predictions;`
#            and `(rm -rf data/predictions)` — ordinary shell punctuation, no evasion needed.
# A negative lookahead closes the class instead of adding instances: match unless the next
# character continues the NAME. `_` and `-` are excluded so a sibling directory
# (`data/predictions_backup`, `data/predictions-old`) is not swept in.
_PDIR_END = r"(?![-\w])"

# A command segment: stop at a pipe/semicolon/&& so one clause's arguments cannot leak into the
# next clause's match.
_SEG = r"[^|;&]*"

# Git global options that take a SEPARATE value token. Needed only so the token walk knows how
# many tokens to step over; an option missing from this set costs nothing, because an unknown
# option is skipped and a mis-parse resolves to an unrecognised subcommand, which DENIES.
_GIT_GLOBAL_WITH_VALUE = {
    "-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path", "--super-prefix",
}

# Options whose VALUE is free text that may legitimately contain a destructive verb —
# `git log --grep revert` must not be blocked. The value token is skipped, not scanned.
#
# ⚠ Stated invariant, since skipping a value could in principle skip a real verb: the
# subcommand-only entries here (`-m`, `--grep`, `--author`, `-F`, …) are NOT valid in git's global
# position, so a crafted `git -m reset --hard` is rejected by git itself (`unknown option: -m`,
# exit 129) before any subcommand runs — the skip cannot hide a verb that would actually execute.
# Verified against the real git binary. Recorded rather than assumed, because the enumerate-and-
# hope pattern has already failed twice in this file.
_OPTIONS_TAKING_A_VALUE = {
    "--grep", "-S", "-G", "--author", "--committer", "-m", "--message", "--pretty", "--format",
    "-F", "--file", "-L", "--since", "--until", "--before", "--after",
    "-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path", "--super-prefix",
}

# Subcommands that mutate the working tree, the index, or history. Each gets a nuanced rule in
# `_check_git`; everything not listed here is allowed through.
_DESTRUCTIVE_SUBCOMMANDS = {
    "checkout", "restore", "reset", "clean", "stash", "apply", "worktree",
    "rebase", "cherry-pick", "revert", "rm", "mv", "filter-branch",
}


def _block(message: str) -> None:
    sys.stderr.write(message if message.endswith("\n") else message + "\n")
    sys.exit(2)


def _clauses(command: str) -> list[str]:
    """Split a command line into clauses on `|`, `;`, `&&`, `||`, newline.

    Backslash-newline continuations are joined FIRST: bash treats them as one logical command, and
    splitting on the raw newline sliced `git checkout \\<newline>-- <path>` into two clauses, which
    separated the pathspec from the verb and let it through.
    """
    command = re.sub(r"\\\n", " ", command)
    return [c for c in re.split(r"\|\||&&|[|;&\n]", command) if c.strip()]


def _tokenize(clause: str) -> list[str]:
    """Best-effort token split. On failure, fall back to whitespace — never raise.

    A tokenizer failure must not silently allow: callers treat an unresolvable git invocation as
    denied, so degrading to a coarser split is safe.
    """
    try:
        return shlex.split(clause)
    except ValueError:
        return clause.split()


def _resolve_git_subcommand(tokens: list[str]) -> tuple[str | None, list[str], list[str]]:
    """Return (subcommand, global-option values seen, remaining args) for a git invocation.

    Walks past global options to find the first bare token. This is a BEST-EFFORT resolution used
    for the `-c alias.…` check only — it cannot be trusted to find the verb, because an unknown
    option that takes a separate value causes the walk to read that value as the subcommand
    (`git --unknown-opt value reset --hard` resolves to `value`, not `reset`). `_check_git`
    therefore does not rely on it for the destructive rules; it scans EVERY token instead.
    """
    i = 1
    c_values: list[str] = []
    while i < len(tokens):
        tok = tokens[i]
        if not tok.startswith("-"):
            return tok, c_values, tokens[i + 1:]
        if "=" in tok:  # self-contained, e.g. --git-dir=.git
            i += 1
            continue
        if tok in _GIT_GLOBAL_WITH_VALUE:
            if tok == "-c" and i + 1 < len(tokens):
                c_values.append(tokens[i + 1])
            i += 2  # step over the option AND its value
            continue
        i += 1  # unknown bare option: step over it alone
    return None, c_values, []


def _check_git(tokens: list[str]) -> None:
    """Deny the destructive git subcommands. Called once per git clause.

    **Scans every token rather than trusting a parsed subcommand position.** Positional parsing is
    what made the two earlier versions of this guard leaky: any global option the enumeration did
    not know about shifted the verb out of the position being inspected, and the rule silently
    failed open. Here, if a destructive verb appears ANYWHERE in a git invocation, its rule runs —
    an unlisted global option cannot hide it, because no position is assumed.

    The cost is a little over-blocking (a branch literally named `reset` passed where a flag is
    expected). That is the correct direction for a guard protecting a byte-immutable artifact.
    """
    _, c_values, _ = _resolve_git_subcommand(tokens)

    # `-c alias.X=<verb>` makes git resolve an arbitrary token into any subcommand, so no
    # token-level check can see the real verb. Alias definition is never legitimate here.
    for val in c_values:
        if val.startswith("alias."):
            _block(
                "Blocked: `git -c alias.…` defines an inline alias, which can resolve to any "
                "subcommand and defeat this guard. Invoke the subcommand directly."
            )

    # Two positions where a destructive WORD is data, not a verb, and blocking it breaks ordinary
    # work: the value of a search/message option (`git log --grep revert`), and anything after the
    # `--` pathspec separator (`git log --oneline -- rm`, a file named `rm`). Everything else is
    # still scanned positionlessly.
    skip_next = False
    for idx, tok in enumerate(tokens[1:], start=1):
        if tok == "--":
            break
        if skip_next:
            skip_next = False
            continue
        if tok in _OPTIONS_TAKING_A_VALUE:
            skip_next = True
            continue
        if tok in _DESTRUCTIVE_SUBCOMMANDS:
            _check_git_subcommand(tok, tokens[idx + 1:])


def _check_git_subcommand(sub: str, rest: list[str]) -> None:
    """Apply the rule for one destructive subcommand, given the tokens that follow it."""
    flags = [t for t in rest if t.startswith("-")]
    bare = [t for t in rest if not t.startswith("-")]

    if sub == "checkout":
        if "--" in rest:
            _block(
                "Blocked: `git checkout -- <pathspec>` overwrites working-tree files. If this "
                "targets a protected artifact directory it would also revert append-only history "
                "(D22/D23). Use `git diff` to inspect; restore deliberately outside the session."
            )
        if "-B" in flags:
            _block(
                "Blocked: `git checkout -B <branch>` force-resets an existing branch. "
                "Use `git checkout -b` for a new branch."
            )
        if "-b" in flags:
            return  # branch CREATION — always fine
        # `{7,}` not `{7,40}`: an over-long hex token is not a valid sha, but it must not slip
        # through on a length technicality either. A branch named in 7+ hex chars is collateral.
        if any(re.fullmatch(r"[0-9a-f]{7,}", t) for t in bare):
            _block(
                "Blocked: `git checkout <sha>` detaches HEAD over the working tree. "
                "Use `git show <sha>` / `git diff <sha>` to inspect a commit read-only."
            )
        return

    if sub == "restore":
        _block("Blocked: `git restore` discards working-tree changes. Inspect with `git diff`.")
    if sub == "reset":
        if "--hard" in flags:
            _block("Blocked: `git reset --hard` discards committed and working-tree state.")
        return
    if sub == "clean":
        if any(re.fullmatch(r"-[a-zA-Z]*f[a-zA-Z]*", f) or f == "--force" for f in flags):
            _block("Blocked: `git clean -f` deletes untracked files irrecoverably.")
        return
    if sub == "stash":
        # `git stash list|show` is read-only; a bare `git stash` saves but does not destroy.
        if bare and bare[0] in {"pop", "apply", "drop", "clear"}:
            _block(
                "Blocked: `git stash pop|apply|drop|clear` mutates the working tree or discards "
                "stashed work. (`git stash list` is fine.)"
            )
        return
    if sub == "apply":
        _block("Blocked: `git apply` patches the working tree. Inspect the patch instead.")
    if sub == "worktree":
        if bare and bare[0] != "list":
            _block("Blocked: `git worktree add|remove|prune` mutates checkouts on disk.")
        return
    # rebase / cherry-pick / revert / rm / mv / filter-branch: history or working-tree rewrites.
    _block(
        f"Blocked: `git {sub}` rewrites history or the working tree. "
        "Perform it deliberately outside the agent session."
    )


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
    # Evasion shapes that defeat tokenizing outright. None is ever needed for ordinary work here,
    # so they are denied wholesale rather than parsed.
    if re.search(r"\bgit\b[^|;&\n]*\bconfig\b[^|;&\n]*\balias\.", command):
        _block(
            "Blocked: defining a git alias (`git config alias.…`) creates a name this guard "
            "cannot recognise as a destructive verb. Invoke subcommands directly."
        )
    if "$IFS" in command:
        _block("Blocked: `$IFS` splits a command into tokens this guard cannot see.")
    # `$(…)` only, NOT backticks. Backticks are how this project's own commit messages and
    # docstrings quote commands, and prose quoting is textually identical to real substitution —
    # telling them apart needs heredoc-quoting state. Blocking backticks made the guard refuse
    # ordinary commits; `$(` in prose is rare enough to deny outright. Backtick substitution is
    # therefore a KNOWN RESIDUAL, recorded in D25's threat model rather than half-guarded.
    if "$(" in command and re.search(
        rf"\b({'|'.join(sorted(_DESTRUCTIVE_SUBCOMMANDS))})\b", command
    ):
        _block(
            "Blocked: command substitution `$(…)` around a destructive git subcommand hides the "
            "real command from this guard. Run the steps separately."
        )

    for clause in _clauses(command):
        tokens = _tokenize(clause)
        # Step over leading `env` and VAR=value assignments so `env git …` is still seen as git.
        while tokens and (tokens[0] == "env" or re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", tokens[0])):
            tokens = tokens[1:]
        if not tokens or os.path.basename(tokens[0]) != "git":
            continue
        _check_git(tokens)

    # ── (c) In-place mutation of the protected artifact directories ───────────────────────────
    protected_note = (
        "append-only historical artifacts (CLAUDE.md principle 5 / D22 / D23). "
        "New files may be added; existing ones are never modified, moved or deleted."
    )
    if re.search(rf"\b(rm|rmdir|mv|cp|dd|truncate|install|shred)\b{_SEG}\b({_PROTECTED_ALT}){_PDIR_END}",
                 command):
        _block(f"Blocked: refusing to delete/move/overwrite {protected_note}")
    if re.search(rf"\bsed\s+-i{_SEG}\b({_PROTECTED_ALT}){_PDIR_END}", command):
        _block(f"Blocked: refusing in-place `sed -i` edit of {protected_note}")
    if re.search(rf"\btee\b{_SEG}\b({_PROTECTED_ALT}){_PDIR_END}", command):
        _block(f"Blocked: refusing to `tee` over {protected_note}")
    # `>`, `>>`, and `>|` (clobber). The `|` in `>|` is why this cannot reuse `_SEG`.
    if re.search(rf">[>|]?\s*[\"']?({_PROTECTED_ALT}){_PDIR_END}", command):
        _block(f"Blocked: refusing shell redirection into {protected_note}")

    sys.exit(0)


if __name__ == "__main__":
    main()
