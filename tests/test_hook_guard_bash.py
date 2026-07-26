"""Allow/deny matrix for the `guard_bash.py` PreToolUse hook.

The hook is regex-driven and sits between an agent and the working tree, so it is exactly the kind
of code that must not ship untested: a silently over-broad pattern blocks ordinary work, and a
silently under-broad one reads as protection while providing none (the state this hook was in when
a read-only reviewer agent ran `git checkout <sha> -- .`).

Each case runs the real hook as a subprocess with a real PreToolUse payload on stdin and asserts the
exit code — 2 blocks the call, 0 allows it. That tests the actual contract the harness uses, not a
reimplementation of the patterns.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

HOOK = Path(__file__).resolve().parents[1] / ".claude" / "hooks" / "guard_bash.py"

BLOCKED, ALLOWED = 2, 0


REPO = Path(__file__).resolve().parents[1]


def run_hook(command: str, cwd: str | None = None) -> int:
    """Invoke the real hook with a real payload. `cwd` is project-root-relative."""
    payload = {
        "tool_name": "Bash",
        "tool_input": {"command": command},
        "cwd": str(REPO / cwd) if cwd else str(REPO),
    }
    proc = subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=30,
        env={**os.environ, "CLAUDE_PROJECT_DIR": str(REPO)},
    )
    return proc.returncode


# ── Destructive git — denied globally (ruling 1) ──────────────────────────────────────────────
DENIED_GIT = [
    # The incident that prompted the hook extension.
    "git checkout af7b0ea -- .",
    # The append-only bypass (ruling 2): neither hook caught this before.
    "git checkout af7b0ea -- data/predictions/",
    "git checkout HEAD -- data/predictions/2026_week_01.json",
    "git checkout main -- data/results/",
    "git checkout -- .",
    "git checkout -- factors/factor_registry.py",
    "git checkout af7b0ea",
    "git checkout a5d8d689903f6abedce6a1fa52d11f264cc0be3680",  # over-long: no length loophole
    "git checkout 9903f6a0be3680bedce6a1fa52d1d29fe605e7fdf1",
    "git restore .",
    "git restore --staged data/predictions/2026_week_01.json",
    "git restore --source=HEAD~3 engine/prediction_engine.py",
    "git reset --hard",
    "git reset --hard origin/main",
    "git clean -f",
    "git clean -fd",
    "git clean -xfd",
    "git stash pop",
    "git stash apply",
    "git apply /tmp/some.patch",
    "git apply --3way fix.patch",
    # Compound commands: the destructive clause must still be caught.
    "make test && git reset --hard",
    "echo hi; git checkout -- .",
]

# ── Escapes found by review — every one of these was ALLOWED by the first version of the hook ──
# Kept as a named block because they are regression pins on real misses, not hypotheticals: a
# global git option or an `=`-form flag defeated every "denied globally" rule.
DENIED_GIT_ESCAPES = [
    # -C <dir>: the whole (b) ruleset was bypassed by one flag.
    "git -C . checkout -- data/predictions/2026_week_01.json",
    "git -C /Users/x/repo checkout af7b0ea -- data/predictions/",
    "git -C . checkout af7b0ea",
    "git -C . restore .",
    "git -C . reset --hard",
    "git -C . clean -fd",
    "git -C . stash pop",
    "git -C . apply patch.diff",
    # Other global options in the same position.
    "git --git-dir=.git checkout -- .",
    "git --git-dir .git reset --hard",
    "git --work-tree=. restore data/predictions/",
    "git -c core.pager=cat checkout af7b0ea",
    "git --no-pager checkout -- data/results/",
    "git -P reset --hard",
    "git --literal-pathspecs checkout -- .",
    # `=`-form subcommand flags before a commit-ish broke the flag-skip.
    "git checkout --track=origin/main abc1234567",
    "git checkout --orphan=foo abc1234567",
    "git -C . checkout --track=origin/main abc1234567",
    # -B force-resets an existing branch (unlike -b, which errors if it exists).
    "git checkout -B main origin/main",
    "git checkout -B main",
    "git -C . checkout -B main origin/main",
    # --- Second review round: the enumerate-the-global-options approach was itself the bug. ---
    # Inline alias substitution through the whitelisted -c: git resolves `co` into `checkout`,
    # so no literal-token check could ever see the real verb.
    "git -c alias.co=checkout co -- data/predictions/2026_week_01.json",
    "git -c alias.co=checkout co af7b0ea",
    "git -c alias.rs=reset rs --hard",
    "git -c alias.cl=clean cl -fd",
    "git -c alias.st2=stash st2 pop",
    # Global options absent from any enumeration — the closed-set failure mode.
    "git --no-optional-locks reset --hard",
    "git -p checkout af7b0ea",
    "git --no-optional-locks checkout -- data/predictions/",
    "git -C . --no-optional-locks checkout -- data/predictions/2026_week_01.json",
    # An unknown option that takes a SEPARATE value shifts the verb out of the parsed position.
    # Found while re-reading my own fix: positional parsing cannot be trusted at all.
    "git --unknown-opt somevalue reset --hard",
    "git --unknown-opt somevalue checkout -- data/predictions/",
    # git reached by absolute path or through env.
    "/usr/bin/git reset --hard",
    "env git checkout -- data/predictions/",
    "GIT_DIR=.git git reset --hard",
    # Other history/working-tree rewrites in the same class.
    "git rebase -i HEAD~3",
    "git cherry-pick af7b0ea",
    "git revert af7b0ea",
    "git rm data/predictions/2026_week_01.json",
    "git mv data/predictions/a.json data/predictions/b.json",
    "git worktree add /tmp/wt af7b0ea",
    "git worktree remove /tmp/wt",
    "git stash drop",
    "git stash clear",
    "git clean --force",
]

# ── Benign git — must remain allowed (ruling 1) ───────────────────────────────────────────────
ALLOWED_GIT = [
    "git checkout -b hook-guard-extension",
    "git checkout -b af7b0ea-experiment",  # -b is branch CREATION even with a hex-ish name
    "git checkout main",
    "git checkout lint-scope-fold-in",
    "git diff main...HEAD",
    "git diff -w -- factors/factor_registry.py",
    "git diff --stat",
    "git status --porcelain",
    "git log --oneline -5",
    "git show af7b0ea",
    "git show af7b0ea --stat",
    "git blame factors/factor_registry.py",
    "git stash list",
    "git add -A",
    "git commit -m 'lint: mechanical style fixes'",
    "git push -u origin hook-guard-extension",
    "git reset --soft HEAD~1",
    "git clean -n",  # dry run
    # Global options must not turn a READ-ONLY git command into a blocked one.
    "git -C . diff main...HEAD",
    "git -C /Users/x/repo status --porcelain",
    "git --no-pager log --oneline -5",
    "git -c core.pager=cat show af7b0ea",
    "git -C . stash list",
    "git -C . checkout -b new-branch",
    # Read-only git must survive the conservative token scan, including unknown global options
    # and a -c that is NOT an alias definition.
    "git --no-optional-locks status",
    "git -c core.pager=cat show af7b0ea",
    "git -c user.name=x log --oneline",
    "git worktree list",
    "git stash show",
    "git rev-parse HEAD",
    "git describe --tags",
    "git fetch origin",
    "git branch -a",
    "git tag -l",
    # A destructive WORD as data, not a verb — these are ordinary commands and must not block.
    "git log --grep revert",
    "git log --grep rebase",
    "git log --grep='reset --hard'",
    "git log --oneline -- rm",
    "git show HEAD -- mv",
    "git log --author revert",
    "git commit -m 'revert the earlier change'",
    "git diff -- data/predictions/2026_week_01.json",
]

# ── Protected-directory mutation — denied, scoped (ruling 1: no global mutation block) ────────
DENIED_PROTECTED = [
    "rm data/predictions/2026_week_01.json",
    "rm -rf data/results/",
    "rmdir data/archive/",
    "mv data/predictions/2026_week_01.json /tmp/",
    "cp /tmp/fake.json data/predictions/2026_week_01.json",
    "sed -i 's/0.5/0.9/' data/predictions/2026_week_01.json",
    "cat /tmp/x.json | tee data/graded/2026_week_01.json",
    "echo '{}' > data/predictions/2026_week_01.json",
    "echo '{}' >> data/lines/2026_week_01.json",
    "python scripts/x.py > data/ratings/2026_week_01.json",
    "rm data/projections/2026_week_01.json",
    # --- Third review round: the trailing slash was load-bearing and should not have been. ---
    # `rm -rf data/predictions` (no trailing slash) is the MORE natural spelling and matched
    # nothing. This would also have silently defeated the freeze-day extension to factors/.
    "rm -rf data/predictions",
    "rmdir data/predictions",
    "mv /tmp/x.json data/predictions",
    "cp /tmp/2026_week_01.json data/predictions",
    "rm -rf data/graded",
    # Overwrite verbs missing from the list, and the clobber redirection form.
    "dd if=/dev/zero of=data/predictions/2026_week_01.json",
    "truncate -s 0 data/predictions/2026_week_01.json",
    "install -m 644 /tmp/fake.json data/predictions/2026_week_01.json",
    "shred data/predictions/2026_week_01.json",
    "echo hi >| data/predictions/2026_week_01.json",
    # --- Fourth review round: the terminator was enumerated, so ordinary shell punctuation
    # walked straight past it. No evasion technique required — just a `;`.
    "rm -rf data/predictions; echo done",
    "rm -rf data/predictions;echo done",
    "mv /tmp/x.json data/predictions; echo done",
    "(rm -rf data/predictions)",
    "if true; then rm -rf data/predictions; fi",
    "rm -rf data/predictions && echo done",
    "rm -rf data/graded|cat",
    "rm -rf data/lines,",
    # --- Fifth review round: the shell expands globs and braces BEFORE the guard sees a path,
    # so a protected directory can be reached without ever being spelled.
    "rm -rf data/pred*",
    "rm -rf data/{predictions,results}",
    "rm -rf data/*",
    "rm -rf data*",
    "mv data/pred* /tmp/",
    "cp /tmp/x.json data/predi?tions/",
    "rm -rf ./data/pred*",
    "rm -rf data/[pr]*",
    # --- Sixth review round: the glob rule was verb-scoped and root-anchored. Three write verbs
    # and two path shapes walked past it.
    "sed -i s/x/y/ data/pred*",
    "tee data/pred*",
    "echo x > data/pred*",
    "echo x >data/pred*",
    "cat /tmp/x | tee data/predi*/out.json",
    # The root need not be spelled in full: `dat*` uniquely expands to `data`, and `*/predictions`
    # to `data/predictions` — neither contains the literal protected path.
    "rm -rf dat*",
    "rm -rf */predictions",
    "rm -rf */pred*",
    "rm -rf ../repo/data/pred*",
    "rm -rf /Users/x/proj/data/pred*",
    "rm -rf $HOME/proj/data/pred*",
    # --- Seventh review round: a SPACELESS redirect is one shlex token, so the path hides
    # mid-token after the operator. `echo foo>bar` is an ordinary shell habit, not evasion.
    "echo x>data/pred*",
    "printf y>>data/pred*.json",
    "cat /tmp/a>data/predi*/out.json",
    # Evasion shapes that defeat tokenizing. Denied wholesale — never needed for ordinary work.
    "git config alias.co checkout",
    "git config alias.wipe '!git reset --hard'",
    "git config alias.co checkout && git co -- data/predictions/2026_week_01.json",
    "git $(echo checkout) -- data/predictions/2026_week_01.json",
    'git commit -m "$(git checkout -- data/predictions/2026_week_01.json)"',
    "git checkout$IFS-- data/predictions/2026_week_01.json",
    "git checkout \\\n-- data/predictions/2026_week_01.json",
]

# ── The same verbs OUTSIDE protected directories — must remain allowed ────────────────────────
ALLOWED_UNPROTECTED = [
    "rm /tmp/scratch.json",
    "rm -rf /tmp/claude-scratch/",
    "mv /tmp/a.json /tmp/b.json",
    "cp docs/SPEC.md /tmp/spec-backup.md",
    "sed -i 's/foo/bar/' /tmp/notes.txt",
    "echo 'hello' > /tmp/out.txt",
    "python scripts/build_predictions.py > /tmp/run.log",
    "cat docs/SPEC.md | tee /tmp/spec.txt",
    "rm reports/weekly_2026_week_01.md",  # D23: renderings are regenerable, NOT guarded
    "echo x > reports/season_2026.md",
    # Sibling directories whose names merely START with a protected name must NOT be swept in —
    # the risk the round-4 boundary fix introduces if the lookahead is too loose.
    "rm -rf data/predictions_backup",
    "rm -rf data/predictions-old",
    "mv data/results_scratch /tmp/",
    "echo x > data/graded_tmp/notes.txt",
    # A `.`-suffixed sibling is a sibling too — the round-4 lookahead swept these in until `.`
    # joined the exclusion set. A backup named `.bak` is the likeliest real-world spelling.
    "rm -rf data/predictions.bak",
    "rm data/results.old",
    "mv data/graded.tmp /tmp/",
    # Names that merely CONTAIN a protected root as a substring are unrelated directories —
    # blocking them was a real round-6 false positive, not an accepted over-block.
    "rm -rf metadata/file*",
    "rm -rf validated_data/*",
    "rm -rf /tmp/scratch/*",
    # The "abbreviation could expand to the root" rule is scoped to a RELATIVE, single-component
    # path. Applying it filesystem-wide made these false positives — unrelated trees, unrelated `d`.
    "rm -rf /tmp/d*",
    "rm -rf /tmp/da*",
    "rm -rf ~/scratch/d*",
    "rm -rf docs/*",
    "rm -rf dist/*",
    "mv build/* /tmp/",
    # Read-only commands are outside every write context, so globs there are never touched.
    "ls data/*",
    "grep -rn game_id data/pred*",
    "cat data/snapshots/*/snapshot.json",
    "python scripts/build_reports.py data/*.json",
]

# ── Secret hygiene — the pre-existing rules must still hold ───────────────────────────────────
DENIED_SECRETS = [
    "git add .env",
    "git add .env.local",
    "git add secrets.txt",
    "git add api_keys.txt",
    "git add server.pem",
    "git commit -m 'add .env'",
]

# ── Ordinary work — the hook must stay out of the way ─────────────────────────────────────────
ALLOWED_ORDINARY = [
    "make test",
    "make lint",
    "make verify-phase-3",
    "ruff check factors/factor_registry.py",
    "mypy engine/power_ratings.py",
    "python scripts/build_predictions.py --week 1",
    "grep -rn 'PROPOSED' factors/ engine/",
    "ls data/predictions/",
    "cat data/predictions/2026_week_01.json",
    "python -c 'import json; print(1)'",
]


@pytest.mark.parametrize("command", DENIED_GIT)
def test_destructive_git_is_blocked(command):
    assert run_hook(command) == BLOCKED, f"should be BLOCKED: {command}"


@pytest.mark.parametrize("command", DENIED_GIT_ESCAPES)
def test_review_found_escapes_stay_closed(command):
    """Regression pins on real escapes: each of these was ALLOWED before review caught it."""
    assert run_hook(command) == BLOCKED, f"escape must stay closed: {command}"


@pytest.mark.parametrize("command", ALLOWED_GIT)
def test_benign_git_is_allowed(command):
    assert run_hook(command) == ALLOWED, f"should be ALLOWED: {command}"


@pytest.mark.parametrize("command", DENIED_PROTECTED)
def test_protected_dir_mutation_is_blocked(command):
    assert run_hook(command) == BLOCKED, f"should be BLOCKED: {command}"


@pytest.mark.parametrize("command", ALLOWED_UNPROTECTED)
def test_same_verbs_outside_protected_dirs_are_allowed(command):
    assert run_hook(command) == ALLOWED, f"should be ALLOWED: {command}"


@pytest.mark.parametrize("command", DENIED_SECRETS)
def test_secret_staging_is_blocked(command):
    assert run_hook(command) == BLOCKED, f"should be BLOCKED: {command}"


@pytest.mark.parametrize("command", ALLOWED_ORDINARY)
def test_ordinary_work_is_allowed(command):
    assert run_hook(command) == ALLOWED, f"should be ALLOWED: {command}"


def test_shell_writes_to_protected_dirs_are_blocked_even_for_a_new_file():
    """DELIBERATELY stricter than `protect_immutable.py`, which permits creating a NEW file.

    That hook allows the pipeline to add `data/predictions/2026_week_NN.json`; this one blocks the
    same creation via shell. That is not drift — every legitimate writer here is Python `open()`
    inside `scripts/`/`analytics/`, never shell redirection, so there is no benign shell case to
    preserve, and deciding existence would mean parsing a path out of an arbitrary command line.
    The asymmetry fails closed. Pinned so a future reader sees it as intended.
    """
    # A file that does not exist — creation, not modification — is still blocked from the shell.
    assert run_hook("echo '{}' > data/predictions/2099_week_99.json") == BLOCKED
    assert run_hook("cp /tmp/new.json data/predictions/2099_week_99.json") == BLOCKED

    # The Python writers the pipeline actually uses are untouched.
    assert run_hook("python scripts/build_predictions.py --week 1") == ALLOWED
    assert run_hook("python scripts/grade.py --week 1") == ALLOWED
    # Committing an artifact is how the pipeline publishes it — never blocked.
    assert run_hook("git add data/predictions/2026_week_01.json") == ALLOWED
    assert run_hook("git add -A && git commit -m 'predictions: 2026 week 01 (pre-kickoff)'") == ALLOWED


def test_prose_mentioning_a_denied_shape_is_allowed():
    """Tokenizing per clause removed the old false positive — pinned so it stays removed.

    The first (regex) implementation matched the RAW command string, so a commit message merely
    *describing* a denied command was blocked; it fired on this hook's own commit. Splitting into
    clauses and tokenizing fixed that as a side effect: a heredoc line that starts with prose is a
    clause whose first token is not `git`, and a quoted argument is a single token that never
    equals a subcommand name.
    """
    commit_with_heredoc = (
        "git commit -F - <<'EOF'\n"
        "hooks: deny destructive shell commands\n\n"
        "Prevents `git checkout <old-sha> -- data/predictions/` from reverting an artifact.\n"
        "EOF"
    )
    assert run_hook(commit_with_heredoc) == ALLOWED

    # A quoted argument that contains a denied shape is one token, not a subcommand.
    assert run_hook('git commit -m "fix the git checkout -- . bug"') == ALLOWED
    assert run_hook('echo "git checkout -- data/predictions/"') == ALLOWED
    assert run_hook("grep -rn 'git reset --hard' docs/") == ALLOWED


def test_working_directory_is_resolved_not_ignored():
    """`cd data && rm -rf predictions` names no protected path — and used to be allowed.

    The guard matched text like `data/predictions` while having no concept of where the shell was
    standing, so one ordinary `cd` removed guard (c) entirely. Its sibling `protect_immutable.py`
    had always read `cwd`; this one did not, and the asymmetry was the hole. Relative tokens are
    now resolved against the working directory, and a `cd` between clauses is followed.
    """
    # A `cd` earlier in the same command line.
    assert run_hook("cd data && rm -rf predictions") == BLOCKED
    assert run_hook("cd data && rm -rf pred*") == BLOCKED
    assert run_hook("cd data && sed -i s/a/b/ predictions/2026_week_01.json") == BLOCKED
    assert run_hook("cd data; mv predictions /tmp/") == BLOCKED

    # The Bash tool's working directory persisting from an earlier call.
    assert run_hook("rm -rf predictions", cwd="data") == BLOCKED
    assert run_hook("mv results /tmp/", cwd="data") == BLOCKED
    assert run_hook("echo x > graded/2026_week_01.json", cwd="data") == BLOCKED

    # Standing INSIDE a protected directory: every relative write is indistinguishable from an
    # edit to history, so the write context itself is refused.
    assert run_hook("rm -rf old.json", cwd="data/predictions") == BLOCKED
    assert run_hook("sed -i s/a/b/ f.json", cwd="data/predictions") == BLOCKED
    assert run_hook("echo x > f.json", cwd="data/predictions") == BLOCKED

    # Ordinary work from a non-protected directory is untouched.
    assert run_hook("rm -rf __pycache__", cwd="factors") == ALLOWED
    assert run_hook("rm -rf snapshots/tmp", cwd="data") == ALLOWED
    assert run_hook("cd docs && rm -rf build") == ALLOWED
    assert run_hook("ls predictions", cwd="data") == ALLOWED
    assert run_hook("cat predictions/2026_week_01.json", cwd="data") == ALLOWED


def test_reading_out_of_a_protected_dir_is_blocked_accepted_over_block():
    """Third accepted over-block: guard (c) does not distinguish source from destination.

    `cp data/predictions/x.json /tmp/` leaves the original untouched but is blocked, because
    telling source from destination means encoding each verb's argument grammar — another
    enumerated set, the shape that has already failed twice in this guard. Use `Read`, or copy via
    Python. Pinned so it reads as intended rather than as a bug.
    """
    assert run_hook("cp data/predictions/2026_week_01.json /tmp/backup.json") == BLOCKED
    # Reading with non-mutating tools is unaffected — the common case stays open.
    assert run_hook("cat data/predictions/2026_week_01.json") == ALLOWED
    assert run_hook("ls data/predictions") == ALLOWED
    assert run_hook("grep -rn game_id data/predictions") == ALLOWED
    assert run_hook("python -c \"import json; json.load(open('data/predictions/x.json'))\"") == ALLOWED


def test_known_residual_backtick_substitution_is_not_guarded():
    """Documented gap, pinned so it is not mistaken for coverage.

    `$(…)` around a destructive verb is denied, but BACKTICK substitution is not: prose quoting a
    command with backticks is textually identical to real substitution, and this project's commit
    messages use backticks constantly — guarding it made the hook refuse ordinary commits.
    Telling them apart requires heredoc-quoting state, i.e. parsing shell.

    This is in D25's stated threat model: the guard stops accident and carelessness, not a caller
    deliberately evading it (`eval`, base64, `python -c`, a previously-defined alias all remain
    open by construction). Pinned as KNOWN, not as acceptable-because-unnoticed.
    """
    assert run_hook("git `echo checkout` -- data/predictions/2026_week_01.json") == ALLOWED


def test_residual_false_positive_prose_containing_the_substitution_form():
    """Second known over-block: prose that merely CONTAINS `$(` near a destructive verb.

    Hit for real while opening this PR — the description explained the substitution rule, so the
    description tripped it. Same shape as the heredoc case: the guard reads text, and text about a
    command is indistinguishable from the command. Fails closed; workaround is `--body-file` /
    `-F <file>`, which is how that PR was opened.
    """
    assert run_hook('gh pr create --body "denies $( ) around git checkout"') == BLOCKED
    # From a file, the same content carries no denied shape on the command line.
    assert run_hook("gh pr create --body-file /tmp/body.md") == ALLOWED


def test_residual_false_positive_a_heredoc_line_that_is_itself_a_git_command():
    """The one remaining over-block: a heredoc LINE that literally begins with a denied command.

    Such a line is indistinguishable from a real clause without tracking heredoc delimiters, which
    is where guards acquire holes. It fails closed, which is the right direction. Pinned as
    intended, not rediscovered. Workaround: put the text in a file and use `git commit -F <file>`.
    """
    body_line_is_a_command = (
        "git commit -F - <<'EOF'\n"
        "hooks: deny destructive shell commands\n\n"
        "git checkout -- data/predictions/\n"
        "EOF"
    )
    assert run_hook(body_line_is_a_command) == BLOCKED


def test_protected_list_is_shared_not_duplicated():
    """Both hooks must read the same tuple — a second copy is how guards drift apart.

    At the v2026-frozen tag, `factors/`, `engine/` and the calibration config join PROTECTED;
    this pin is what makes that one edit propagate to both guards.
    """
    hooks = Path(__file__).resolve().parents[1] / ".claude" / "hooks"
    shared = (hooks / "protected_paths.py").read_text()
    assert "PROTECTED = (" in shared, "protected_paths.py must define the tuple"

    for name in ("guard_bash.py", "protect_immutable.py"):
        src = (hooks / name).read_text()
        assert "from protected_paths import PROTECTED" in src, f"{name} must import the shared tuple"
        assert "PROTECTED = (" not in src, f"{name} must NOT define its own copy of PROTECTED"


def test_guard_inherits_new_protected_entries(tmp_path, monkeypatch):
    """A directory added to PROTECTED is guarded by guard_bash without editing guard_bash.

    This is the freeze-day contract: at the tag, `factors/` and `engine/` are appended to
    PROTECTED and the git-bypass/mutation denials must cover them automatically.
    """
    hooks = Path(__file__).resolve().parents[1] / ".claude" / "hooks"
    sandbox = tmp_path / "hooks"
    sandbox.mkdir()
    for name in ("guard_bash.py", "protect_immutable.py"):
        (sandbox / name).write_text((hooks / name).read_text())
    # A PROTECTED tuple with one extra entry, standing in for the freeze-day addition.
    (sandbox / "protected_paths.py").write_text(
        'PROTECTED = ("data/predictions/", "factors/")\n'
    )

    payload = {"tool_name": "Bash", "tool_input": {"command": "rm factors/factor_registry.py"}}
    proc = subprocess.run(
        [sys.executable, str(sandbox / "guard_bash.py")],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert proc.returncode == BLOCKED, "a newly PROTECTED directory must be guarded automatically"
