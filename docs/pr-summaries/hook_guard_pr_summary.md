# Hook-guard extension PR summary — the shell path to the immutable artifacts

> **Lifecycle.** A PR summary — a durable record, **RETAINED, not retired.** `docs/pr-summaries/`
> is outside the proposal lifecycle. The authoritative record is **`docs/DECISIONS.md` D25**; this
> carries the review context around it.
>
> **Status:** open, awaiting owner merge. **Branch:** `hook-guard-extension`, base `a5d8d68`.

---

## What shipped

The `guard_bash.py` extension ruled in D25, plus the shared `PROTECTED` tuple, the
`code-reviewer.md` briefing fixes, and D25 itself.

**No `factors/` or `engine/` path is touched, so the output-hash instrument does not apply** — this
change cannot move a prediction. `make test` **672 passed, 2 skipped** (was 449; **+223-case hook
matrix**). `make lint` clean on a scope that now includes both the new test file **and the three
hook source files themselves**, which had never been linted. *(Counts re-measured at the close of
round 8 and reconciled against `make test` and `pytest --collect-only`; earlier drafts of this file
and of D25 quoted 619/170, 633/184 and 644/195 and went stale every round — a reviewer nit three times over.)*

## The gap this closes

`data/predictions/` is byte-immutable forever (D22) and six more directories are append-only (D23),
but that was enforced **only against `Edit`/`Write`**: `protect_immutable.py` keys off
`tool_input.file_path`, which a shell command does not have, so **it never fired for Bash at all**.
Reverting a committed pre-registration artifact from the shell was blocked by neither hook.

Now: destructive git is denied **globally**; in-place mutation of the protected directories is
denied **scoped**; and both hooks read **one** `PROTECTED` tuple, so the freeze-day addition of
`factors/`/`engine/` propagates from a single edit.

## Eight NO-GO rounds — what the reviewer caught that I did not

This is the part worth reading. Each round I believed the guard was correct; each round it was not.

| Round | What I shipped | What review found |
|---|---|---|
| 1 | Regex anchored on `git\s+<verb>` | **One global option bypassed every rule** — `git -C <dir> checkout -- data/predictions/` was ALLOWED. Also `=`-form flags defeated sha detection |
| 2 | Enumerated the known global options | **The fix closed the instances, not the class.** Any option outside the enumeration (`--no-optional-locks`, `-p`) defeated the rule again, and `git -c alias.co=checkout co …` defeated it *through an option the fix had just whitelisted*. A closed set was the wrong shape |
| 3 | Replaced regex with clause-splitting + tokenizing + a positionless token scan | **The trailing slash was load-bearing**: `rm -rf data/predictions` (no slash) matched nothing — no cleverness required, and it would have silently defeated the freeze-day extension to `factors/`. Plus `dd`/`truncate`/`install`/`>|`, persistent aliases, `$IFS`, `$(…)`, backslash-newline continuation, and spurious blocks on `git log --grep revert` |
| 4 | Terminator widened to `/`, whitespace, quote, end-of-string | **The same closed-set mistake, one layer down.** `rm -rf data/predictions; echo done` walked straight past it — a semicolon, on the artifact this PR exists to defend. Also: D25 and this summary had stale counts, and the read-out over-block was undocumented |
| 5 | Terminator replaced with a boundary lookahead | **Globs and braces reach the path without spelling it**: `rm -rf data/pred*` and `rm -rf data/{predictions,results}` were ALLOWED — the shell expands before the hook ever sees a path. Also `data/predictions.bak` was newly over-blocked, because `.` was missing from the sibling exclusion the round-4 fix had just introduced |
| 6 | A glob rule scoped to mutation verbs and anchored on the literal root | **Still a literal-text rule.** `rm -rf dat*` and `rm -rf */predictions` resolve to the protected path without containing it; `sed -i`, `tee` and redirection were never covered; and `metadata/`, `validated_data/` were falsely blocked as substring matches. D25 itself had gone stale on the over-block count and NO-GO tally |

| 7 | A token-level glob check | **A spaceless redirect hides the path mid-token.** `echo x>data/pred*` is one shlex token, so stripping *leading* operators missed it — an ordinary shell habit, not evasion. Also `rm -rf /tmp/d*` was over-blocked, because the "abbreviation could expand to the root" rule was applied filesystem-wide |

| 8 | Everything above — all of it text-matching | **The guard never read `cwd`.** A relative delete of a protected directory, after an ordinary `cd` or from a persisted working directory, bypassed guard (c) entirely — no glob, no evasion. The sibling hook had always read `cwd`; this one never did |

### Round 8 in full

The most valuable finding of the eight, and the only one that was not a textual edge: every
rule here matched strings like the literal protected path, and **none of them knew where the
shell was standing**. `protect_immutable.py` had read `payload["cwd"]` since it was written;
this guard never did. Because the Bash tool's working directory persists between calls, one
legitimate `cd` into the data tree — to inspect pipeline output, say — silently removed guard
(c) for every command after it.

Relative tokens are now resolved against the working directory, a `cd` between clauses of the
same command is followed, and standing *inside* a protected directory refuses the write
context outright: a relative write there cannot be distinguished from an edit to history.
Ordinary work outside those trees is pinned as unaffected.

### Round 7 in full

Two findings, one in each direction. The blocker: `echo x>data/pred*` — with no space before the
operator, shlex yields the single token `x>data/pred*`, so `lstrip(">|<")` was a no-op and the path
hid mid-token. Every token is now **split on the redirection characters** and each piece checked.

The over-block: the "could this abbreviation expand to the root" rule (`dat*` → `data`) was applied
to any path anywhere, so `rm -rf /tmp/d*` was blocked on an unrelated tree. It is now scoped to a
**relative, single-component** path — which is the only shape where the abbreviation can actually
resolve to the repo-root `data/`. Absolute and multi-component paths still block on an exact
component match (`/Users/x/proj/data/pred*`), which is the case that matters.

### Round 6 in full

The glob rule I shipped in round 5 was **still literal-text matching wearing a different hat** — it
required the token to spell the root. Replaced with a token-level check that is pessimistic by
construction and shared by **every** write context (mutation verbs, `sed -i`, `tee`, redirection),
since the shell expands before this hook ever sees a path. A token is denied if it begins with a
glob, contains a protected leaf name, has a complete path component equal to a protected root, or
has a component adjacent to the glob that is a prefix of a root or extends one (`dat*` → `data`).
A component that merely *contains* a root as a substring does not qualify — that was the
`metadata/` false positive, now pinned as ALLOWED.

Read-only commands (`ls data/*`, `grep -rn x data/pred*`, `cat data/snapshots/*/snapshot.json`) sit
outside every write context and are pinned as unaffected.

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
each a demonstrated miss rather than a hypothetical, in a **223-case** matrix that runs the real
hook as a subprocess against real payloads.

### Round 5 in full

Two findings. The blocker: **globs and braces reach a protected path without ever spelling it** —
`rm -rf data/pred*`, `rm -rf data/{predictions,results}` — because the shell expands before the
hook sees anything. Any glob or brace under a protected *root* is now denied wholesale, the same
posture already used for `$IFS` and `$(…)`. This deliberately also catches globs under
non-protected siblings of that root (`rm -rf data/snapshots/*`): deciding which expansion is safe
would mean performing it. Fourth accepted over-block, documented and pinned.

The second: my own round-4 fix **introduced** a false positive. Excluding `_` and `-` from the
boundary but not `.` meant `rm -rf data/predictions.bak` — the likeliest real backup spelling — was
newly blocked, breaking the very "siblings are not swept in" property that fix claimed to
establish. `.` joined the exclusion, with `.bak`/`.old`/`.tmp` siblings pinned as allowed.

Also closed: the three hook source files were never in `LINT_PATHS`, so "`make lint` clean" did not
actually cover the hook. They are in now. And shell-variable indirection
(`X=data/predictions; rm -rf $X`) is named in the docstring's open-by-construction list rather than
left as an unnamed gap.

## The threat model — ratified

Accepted as narrowed (owner, 2026-07-25) and stated in D25: the guard closes **accident and
carelessness**; it is **not** a security boundary against deliberate evasion; residuals stay pinned
by tests as known. The sandbox / `permissions.deny` alternative is recorded in D25 as
**considered and declined** — disproportionate for a single-maintainer private repo whose real
failure mode is a careless command — so 2027 does not re-litigate it from scratch. The backtick
exception is accepted on the same basis: `$(…)` denied, backticks allowed, both over-blocks pinned
with the `-F` / `--body-file` workaround noted.

## Reviewer

**Eight rounds, eight NO-GOs, every one binding and every one correct.** That record is the strongest
evidence in this PR, and it cuts against me: on each round I believed the guard was finished, and
on each round it was not. Three times the finding was that I had closed the reported *instances*
while leaving the *class* open — round 4 caught me making that exact mistake inside the commit that
claimed to fix the round-3 version of it, and round 5 caught the same shape once more in the glob
case. Twice a fix of mine introduced a *new* defect that the same review round caught.

The honest read: **the reviewer, not the author, is why this guard works.** Everything shipped in
this PR would have gone in broken five separate times on my judgement alone — and it guards the
byte-immutable artifact the whole project's audit trail rests on.

Every finding is now fixed or pinned as a known residual. Counts here and in D25 are re-measured
against `make test` and `pytest --collect-only`.
