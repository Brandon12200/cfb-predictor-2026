# Hook-guard extension PR summary — the shell path to the immutable artifacts

> **Lifecycle.** A PR summary — a durable record, **RETAINED, not retired.** `docs/pr-summaries/`
> is outside the proposal lifecycle. The authoritative record is **`docs/DECISIONS.md` D25**; this
> carries the review context around it.
>
> **Status:** open, awaiting owner merge. **Branch:** `hook-guard-extension`, 4 commits, base `a5d8d68`.

---

## What shipped

The `guard_bash.py` extension ruled in D25, plus the shared `PROTECTED` tuple, the
`code-reviewer.md` briefing fixes, and D25 itself.

**No `factors/` or `engine/` path is touched, so the output-hash instrument does not apply** — this
change cannot move a prediction. `make test` **619 passed, 2 skipped** (was 449; +170 hook matrix).
`make lint` clean on a scope that now includes the new test file.

## The gap this closes

`data/predictions/` is byte-immutable forever (D22) and six more directories are append-only (D23),
but that was enforced **only against `Edit`/`Write`**: `protect_immutable.py` keys off
`tool_input.file_path`, which a shell command does not have, so **it never fired for Bash at all**.
Reverting a committed pre-registration artifact from the shell was blocked by neither hook.

Now: destructive git is denied **globally**; in-place mutation of the protected directories is
denied **scoped**; and both hooks read **one** `PROTECTED` tuple, so the freeze-day addition of
`factors/`/`engine/` propagates from a single edit.

## Three NO-GO rounds — what the reviewer caught that I did not

This is the part worth reading. Each round I believed the guard was correct; each round it was not.

| Round | What I shipped | What review found |
|---|---|---|
| 1 | Regex anchored on `git\s+<verb>` | **One global option bypassed every rule** — `git -C <dir> checkout -- data/predictions/` was ALLOWED. Also `=`-form flags defeated sha detection |
| 2 | Enumerated the known global options | **The fix closed the instances, not the class.** Any option outside the enumeration (`--no-optional-locks`, `-p`) defeated the rule again, and `git -c alias.co=checkout co …` defeated it *through an option the fix had just whitelisted*. A closed set was the wrong shape |
| 3 | Replaced regex with clause-splitting + tokenizing + a positionless token scan | **The trailing slash was load-bearing**: `rm -rf data/predictions` (no slash) matched nothing — no cleverness required, and it would have silently defeated the freeze-day extension to `factors/`. Plus `dd`/`truncate`/`install`/`>|`, persistent aliases, `$IFS`, `$(…)`, backslash-newline continuation, and spurious blocks on `git log --grep revert` |

Two things I caught myself, before review: in round 2's rewrite, an unknown option taking a
*separate value* makes positional parsing resolve the wrong token — which is why the scan is
positionless; and a prior test asserted the regex version's broad false positive as *intended*,
which tokenizing removed, so keeping it would have **enshrined the old bug** — the exact
tests-can-enforce-a-broken-contract failure this project already has a doctrine about. That test
was rewritten to pin reality, not preserved.

**45 escapes are pinned as named regression cases**, each a demonstrated miss rather than a
hypothetical, in a 170-case matrix that runs the real hook as a subprocess against real payloads.

## The open question for you — the threat model

Round 3 also surfaced evasions that are **not fixable by this mechanism at all**: `eval`, base64,
`python -c`, backtick substitution, and any alias defined in an *earlier* call. A `PreToolUse`
string hook cannot interpret shell — it sees text, and text that is about to be expanded, aliased
or decoded is indistinguishable from text that is not.

I have therefore written a **stated threat model into D25**: this guard stops **accident and
carelessness** — which is precisely what the incident was, an agent casually running a destructive
command — and is **not a security boundary against a caller deliberately working around it**.
Known residuals are pinned by tests *as known*, so they can never be mistaken for coverage.

One judgement call inside that, worth your explicit eye: **backtick substitution is deliberately
left unguarded.** Prose quoting a command in backticks is textually identical to real substitution,
this project's commit messages use backticks constantly, and guarding it made the hook refuse
ordinary commits — it blocked one of mine. `$(…)` is denied, since it is rare in prose.

**If you want the stronger claim** — "destructive git is *categorically* impossible from an agent
session" — that is not a hook, it is a sandbox or a `permissions.deny` layer, and it is a different
piece of work. My recommendation is to accept the narrowed model: it closes the realistic failure
(a careless command) at proportionate cost, and it is honest about what it does not do.

## Reviewer

Three rounds, three NO-GOs, all binding and all correct; every finding is either fixed or recorded
as a known residual in D25. **The branch has not been re-reviewed since the round-3 fixes** — I
paused here rather than start a fourth round, because the threat-model narrowing is a decision that
amends a decision you ratified hours ago, and that is yours to make, not mine to assume.
