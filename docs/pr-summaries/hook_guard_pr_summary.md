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
change cannot move a prediction. `make test` **633 passed, 2 skipped** (was 449; **+184-case hook
matrix**). `make lint` clean on a scope that now includes the new test file. *(These are the
authoritative counts, re-measured at the close of round 4; earlier drafts of this file and of D25
quoted 619/170 and were stale by one round — reconciled here and in D25.)*

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
| 4 | Terminator widened to `/`, whitespace, quote, end-of-string | **The same closed-set mistake, one layer down.** `rm -rf data/predictions; echo done` walked straight past it — a semicolon, on the artifact this PR exists to defend. Also: D25 and this summary had stale counts, and the read-out over-block was undocumented |

### Round 4 in full

The reviewer's root-cause note is the part worth keeping: I had **hand-enumerated the terminator
characters** instead of using a boundary — *the identical mistake round 2 rejected*, committed
again in a different function, in the commit whose headline claim was fixing the round-3 version of
it. `_PDIR_END` is now a negative lookahead (`(?![-\w])`), which closes the class rather than
adding instances, and sibling directories (`data/predictions_backup`, `data/predictions-old`) are
pinned as **not** swept in — the false-positive risk the boundary introduces.

Also from round 4: the `_OPTIONS_TAKING_A_VALUE` skip now carries its **stated invariant** (the
subcommand-only flags in it are invalid in git's global position, so a crafted `git -m reset
--hard` is rejected by git itself before any subcommand runs — verified against the real binary,
recorded rather than assumed); a duplicated docstring sentence was removed; and the third
over-block — reading *out* of a protected directory — is now documented and pinned instead of
being silently surprising.

Two things I caught myself, before review: in round 2's rewrite, an unknown option taking a
*separate value* makes positional parsing resolve the wrong token — which is why the scan is
positionless; and a prior test asserted the regex version's broad false positive as *intended*,
which tokenizing removed, so keeping it would have **enshrined the old bug** — the exact
tests-can-enforce-a-broken-contract failure this project already has a doctrine about. That test
was rewritten to pin reality, not preserved.

**45 git escapes plus the round-4 protected-path escapes are pinned as named regression cases**,
each a demonstrated miss rather than a hypothetical, in a **184-case** matrix that runs the real
hook as a subprocess against real payloads.

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

## The threat model — ratified

Accepted as narrowed (owner, 2026-07-25) and stated in D25: the guard closes **accident and
carelessness**; it is **not** a security boundary against deliberate evasion; residuals stay pinned
by tests as known. The sandbox / `permissions.deny` alternative is recorded in D25 as
**considered and declined** — disproportionate for a single-maintainer private repo whose real
failure mode is a careless command — so 2027 does not re-litigate it from scratch. The backtick
exception is accepted on the same basis: `$(…)` denied, backticks allowed, both over-blocks pinned
with the `-F` / `--body-file` workaround noted.

## Reviewer

**Four rounds, four NO-GOs, every one binding and every one correct.** That record is the strongest
evidence in this PR, and it cuts against me: on each round I believed the guard was finished, and
on each round it was not. Twice the finding was that I had closed the reported *instances* while
leaving the *class* open — and round 4 caught me making that exact mistake a second time, inside
the commit that claimed to fix the first one.

Every finding is now fixed or pinned as a known residual. Counts in this file and in D25 are
re-measured and reconciled against `make test` and `pytest --collect-only`.
