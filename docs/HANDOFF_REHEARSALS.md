# HANDOFF → the rehearsal window (temporary — delete when the season runs cleanly)

A briefing for a fresh session with zero conversational context. **Not authoritative over
`docs/SPEC.md`.** Written 2026-08-10, at the close of the Phase-5 build session.

Read this, then `docs/PIPELINE.md` (the operating manual), then SPEC §10.

**Your first task is in §(b). Do it before you touch anything else.**

---

## (a) Current state — the pipeline is BUILT, LIVE, and RUNNING ON ITS OWN

Phase 5 is complete and merged. The model is frozen at **`v2026-frozen-2`**; `main` is at `ab6ce73`
(the PR #39 merge). Gates on `main`: `make test` **1015 passed / 2 skipped**, `make lint` clean, all
`verify-phase-*` targets PASS.

**The single most important thing to understand before you act:** the workflows are on live cron
schedules *right now*. Nobody has to start them. Between today and Rehearsal 0 the repository will
push commits to `main` **by itself** — daily captures Wed/Thu/Fri and four Saturday waves
(`season.json` → `pipeline.schedule_et`), plus a daily freeze-integrity check. New commits authored
by `cfb-pipeline <cfb-pipeline@cfb-predictor-2026.invalid>` appearing on `main` with no human
involved are **the system working**, not an intrusion. Do not "clean them up".

**One wrinkle you will see in the history and should not investigate.** Pipeline commits made before
2026-08-11 — including `d54ac10` below — carry the *superseded* address
`pipeline@users.noreply.github.com`, and GitHub renders them with the avatar and profile link of a
**real, unrelated user** who happens to hold the login `pipeline`. That was a provenance defect in
D30's original address, fixed by the D30 as-built amendment; it was never a security issue (push
authority is the deploy key, and the author field is a string, not a credential). **History is not
rewritten**, so the attribution window is permanent. Read those commits as machine commits.

### What has been proven at runtime, not merely tested

Each of these was observed in a real Actions run, not asserted in a unit test:

| Proven | Evidence |
|---|---|
| Secrets reach every job that spends | Live capture run; preflight found `ODDS_API_KEY` present |
| Freeze assertion against `v2026-frozen-2` | Tree-hash equality passed on a runner with `fetch-depth: 0` |
| Odds fetch + budget guard + quota ledger | Live capture wrote a real observation |
| **Autonomous push to protected `main`** | **`d54ac10`** — the first machine-authored commit in project history, via the deploy key |
| CI green on a pipeline data commit | The push triggered CI and it passed |
| `clear-failure` closes a stale issue | Issue #33 auto-closed on the clean run |
| Full predict path, end to end | Rehearsal smoke: catch-up grade → commit → snapshot → quality gate → derived exports → commit → build predictions |
| Full grade path | Rehearsal smoke: fetch finals → "nothing to grade yet" as a green notice |
| Dry runs have no issue side effects, **in both directions** | Both smokes left #36 and #38 untouched |

**What is NOT yet proven at runtime: a live predict and a live grade.** Predict writes the week-1
claim, and by standing guardrail (§d) that waits for the scheduled Aug 25 run. This gap is
deliberate, not an oversight.

### The queue is empty

There is no carried-forward defect list. The nine-item hardening batch (PR #39) closed the last of
it. Merged this session: **#30** (the pipeline), **#31** (reporting split + fixes), **#34** (normalizer
fails closed + the retag), **#35** (tag references), **#37** (deploy-key push + derived exports),
**#39** (the hardening batch).

**Five of the six carry a `code-reviewer` GO recorded in the repo** — in the PR body, or in
`docs/pr-summaries/`. **#35 does not.** It was reviewed in-session, but that review left no durable
artifact, so from the repository alone it is unverifiable. Recorded here rather than smoothed over,
because "every PR was reviewed" is exactly the kind of claim a context-free successor would take as
established. **The lesson, which applies to you: a review that is not written down did not happen,
as far as the repo is concerned.** Put the verdict and the reviewed SHA in the PR body or a
`docs/pr-summaries/` file, every time.

### Open issues — one, and it is by design

**#36 (`pipeline: grade failure — 2026 week 01`) is deliberately still open.** It was a false alarm
from before `EXIT_NO_CLAIM` existed. It closes through `clear-failure` on the **first clean live
grade run — Sunday 2026-08-16, 12:47 ET**. A dry run *cannot* close it, because hardening item 9
gates `clear-failure` off during dry runs; that is the correct behaviour and the reason the issue
outlived its cause by five days.

**If #36 is still open after Aug 16, that is a real signal.** It means the Sunday grade job did not
run, or did not finish green. Investigate before Rehearsal 0.

---

## (b) YOUR FIRST TASK — `pipeline-adversary` has not been run against the current pipeline

`CLAUDE.md` mandates the `pipeline-adversary` agent **before each rehearsal**. It has not been run
since the pipeline reached its current shape — PRs #35, #37 and #39 all landed after the last audit,
and #39 alone changed nine things including the commit action, the failure-signature computation and
the dry-run gating. **The audit is stale by three PRs.**

Run it before Rehearsal 0. Read-only, no branch needed.

Its findings are dispositioned under a standing rule you must not soften: **a finding blocks only if
the pipeline fails its own written acceptance criteria** (§c). Everything else is one line appended
to `docs/2027_NOTES.md` and no further work. This rule exists because an adversarial audit of a
system with a fixed kickoff date will always find more than can be fixed, and unbounded fixing is
how the Aug 29 date gets missed.

---

## (c) The rehearsal calendar — acceptance criteria, not suggestions

Kickoff is **Saturday 2026-08-29**. The live week-1 predict is **Tuesday 2026-08-25**. Neither moves.

Run `pipeline-adversary` before each rehearsal below. Rehearsal branches are tagged
(`rehearsal-1`, `rehearsal-2`) and left **unmerged** as acceptance evidence — `ci.yml` fails any PR
whose head ref matches `rehearsal/*`, so they cannot be merged by accident (D32).

### Already banked — the dry-run smokes (2026-08-10)

Both `weekly-predict` and `weekly-grade` dispatched with `dry_run: true` on `rehearsal/wk1-smoke`,
both green, zero commits, claim slot untouched, no issue opened or closed. This satisfied the
original dry-run form of Rehearsal 0. **Rehearsal 0 proper is now the full-cycle version below** —
the owner upgraded it, because a dry run exercises everything *except* the commit-and-push
choreography, which is where the taxonomy can break.

### Rehearsal 0 — Monday 2026-08-17 — full cycle, `dry_run: false`, on a rehearsal branch

Branch `rehearsal/wk1-r0` cut fresh from `main`. Dispatch all three cadence workflows against it
with **`dry_run: false`** so artifacts are really written, committed and pushed **to the rehearsal
branch**. This is the first time the commit choreography runs for real on a predict cycle.

**Written pass criteria — all must hold:**

1. All three workflows conclude `success`.
2. **Commit taxonomy intact.** The Tuesday cycle produces commits in order — `grading:` → `snapshot:`
   (carrying `data/snapshots/` **and** `data/lines/`) → `predictions:`. The claim commit **stands
   alone**: exactly one file, nothing riding along. This is the pre-registration evidence and the
   single most important assertion in the rehearsal.
3. **The snapshot commit precedes the predict step.** If it does not, `git describe --dirty` stamps
   every claim with a `-dirty` suffix (D34).
4. Every commit is authored `cfb-pipeline <cfb-pipeline@cfb-predictor-2026.invalid>` and carries a
   `Run: <actions-run-url>` trailer (D30 as amended). **The author must render UNLINKED on GitHub** —
   no avatar, no profile link. If it links to any account, the address has reverted or the domain
   has become resolvable, and `tests/test_pipeline_commit_identity.py` should have caught it.
5. **No commit lands on `main`.** Verify by ref, not by memory.
6. **The week-1 claim slot on `main` is still empty.** `git ls-tree -r origin/main --name-only |
   grep predictions/2026` returns nothing.
7. **Re-dispatch predict on the same branch and check the RIGHT idempotency property.** The claim is
   idempotent; the cycle is not.

   - **Must hold:** the "Build predictions" step **skips** (`Claim already made` runs instead) and
     the `predictions:` commit is **not** created — both are gated on
     `steps.setup.outputs.prediction_exists` (`weekly-predict.yml:143-160`). Byte-immutability is
     also the idempotency guard, and it is what makes week 1's 10-day window safe.
   - **Expected, and NOT a failure — on any run that reaches the commit step:** a **new `snapshot:`
     commit, regardless of whether the Odds call succeeded.** "Build the snapshot" and "Regenerate
     the derived exports" are deliberately **ungated**, and `SnapshotBuilder._fetch()` stamps a
     fresh `fetched_at` into `manifest.json` for **all seven** fetch groups — games, advanced stats,
     coaching, **season stats**, SP+, returning production, betting lines — in **both** its success
     and `except` branches (a failed fetch degrades to `missing`, it does not raise), and
     `write_snapshot()` overwrites with no dedup. So the commit fires even if Odds fails outright.

     When Odds *does* succeed you additionally get a new line observation and a quota-ledger entry;
     when it fails you get neither, but still the commit. Do not read "no new observation" as "the
     re-dispatch did nothing". Fresh market data on a re-run is the point of the daily cadence.

     **The scope of that guarantee is the Odds call, not everything.** `build()` calls
     `registry.validate_membership_counts()` (`builder.py:54`) *before* any fetch, and it raises
     `RegistryError` on membership drift with no `try` around it in `scripts/build_snapshot.py` —
     the step fails and **nothing commits at all**. That is a genuine failure and criterion 1
     already catches it.

   **Do not write this criterion as "zero commits are produced."** That is what the pipeline is
   *not* designed to do, and a successor holding the cycle to it would either flag a healthy
   pipeline as broken or lose trust in the rehearsal as evidence.
8. No `pipeline-failure` issue opens; none closes.
9. `verify-phase-3` stays green throughout.

### Rehearsal 1 — Aug 18–19 — the second full cycle

A second clean full cycle on `rehearsal/wk1-r1`, cut fresh from `main` after any Rehearsal-0 fixes
merge. Same criteria, plus:

10. `sp_watch` is run and its verdict recorded (§e). If SP+ has landed, the §3.1 process starts
    **that day** — it has a multi-day turnaround against a fixed kickoff.
11. `git diff rehearsal-0 rehearsal-1 -- data/predictions/` is inspected. Differences are expected
    (lines move); *unexplainable* differences are a finding.

**Two clean full-cycle rehearsals is the bar.** One is not.

### Failure-injection drill — Thursday 2026-08-20 — `rehearsal/wk1-drill`

Injection is **environmental only** — an invalid key in the step env, `--min-credits 999999`, a
conflicting push. **Never an `if os.getenv("INJECT_FAILURE")` branch in production code**; a drill
that requires editing the code under test is not a drill.

**Written pass criteria:**

12. Exactly **one** correctly-labelled issue opens (`pipeline-failure` + `stage:<x>` + `week:01`).
13. Its body carries the **real** error (e.g. the 401) and a **working** run link.
14. Re-running the same failure inside the cooldown creates **zero** new issues *and* **zero** new
    comments.
15. A **different** failure mode bypasses the cooldown and comments — the failure-signature path
    (this is the one that shipped broken once; see §f).
16. A clean re-run **auto-closes** the issue.
17. The budget-refusal path leaves the job **green** with `data/lines/` untouched.
18. **Nothing was committed on any failing run.**

### Rehearsal 2 — Aug 24 — final dress, fresh from `main`

Cut from `main` after all fixes have merged. Full cycle. Criteria 1–9. This is the last rehearsal
before the live run and its purpose is to prove that the *merged* state works, not that a fix branch
did.

### LIVE — Tuesday 2026-08-25, 09:17 ET — schedule-driven predict on `main`

**Not dispatched. Not on a branch. Left alone.** The first run that writes the real week-1 claim.
Watch it; do not touch it. If it fails, the guardrail in §(d) still holds — the recovery is to fix
and let the next scheduled run write the claim, never to hand-write the artifact.

### Aug 26–28 — live captures; Aug 29 — KICKOFF; Aug 30 — first graded Sunday

19. The first graded Sunday publishes a report led by D27's **lean-side split** and the naive
    always-lean-home baseline — "games of interest", not a blended headline dominated by the 5.57:1
    structural home skew.

    **Note the as-built deviation from D36.** D36 ratified a *gate*: `build_reports.py` runs but the
    workflow withholds the `reports/` commit until the split lands. The split landed in PR #31, so
    the gate was **removed** rather than left in place — the risk is closed at the source instead of
    held back at the commit (see the comment at `.github/workflows/weekly-grade.yml:126`). The
    protection D36 bought is therefore now a property of `analytics/attribution.py`, not of the
    workflow. **If anyone ever reverts or weakens the split, nothing in the pipeline will stop the
    blended headline from being published automatically.**

---

## (d) Standing rules — binding, carried from the whole freeze and Phase-5 sequence

**On the claim slot and rehearsals**

- **The week-1 claim slot on `main` stays empty until the scheduled Aug 25 run writes it.** Any
  predict or grade dispatch before then is `dry_run: true` **or** on a `rehearsal/*` branch — never
  live on `main`. Verify the slot is empty after every dispatch; do not assume.
- Rehearsals run on **unmerged rehearsal branches** (D32). Mode is derived from the ref, and there is
  deliberately **no `rehearsal` dispatch input** — a mode that cannot be typed cannot be mistyped.

**On decisions**

- **Propose → pause → ratify.** Owner-only: calibration and weight changes, the freeze itself,
  changes to SPEC §16 decisions, and anything that costs money. Propose; never decide.
- Dense proposals go to **`docs/proposals/<ITEM>.md`** as a file — the terminal reply is a headline
  and a path. Proposals are deleted once ratified (their content moves to `CALIBRATION_LOG.md` /
  `DECISIONS.md`); **PR summaries go to `docs/pr-summaries/` and are retained**.
- Merges are the owner's. **The tag is cut by the owner's hand.**

**On review**

- `code-reviewer` before every PR; **a NO-GO is binding until resolved**.
- **The GO must cover the FINAL diff at branch head.** If you fix anything after a GO, the delta gets
  re-reviewed. This rule exists because a GO was once cited for a commit that was no longer head.
- **Hard stop on review cycles: cap any oscillating fix-cycle on the FIRST oscillation.** If a fix
  reintroduces something a previous fix removed, stop and escalate rather than iterating.

**On honesty of record**

- **Cite command outputs, never expectations.** A PR number comes from `gh pr create`'s output. This
  rule exists because a PR that did not exist was once cited from an inferred number.
- No AI attribution in commit messages or PR text; `includeCoAuthoredBy` stays `false`.

**On the freeze**

- **Never touch `factors/`, `engine/`, or calibration config.** Any finding that would require it
  escalates to the owner for the SPEC §3 exception process.
- **The fingerprint constant is never updated** — not as a fix, not as a convenience, under no
  option. It changes only as part of a ratified SPEC §3 exception accompanied by a new tag. If the
  slate-hash gate fails, either the change was unintended (revert it) or it was intended (it needs
  the exception process). Updating the constant hides exactly what the gate exists to show.
- **Retagging includes every tag-name reference**, and tests must **derive** the tag, never hardcode
  it. `season.json` → `pipeline.freeze_tag` is the single source of truth (D24), and
  `tests/test_frozen_status.py` enforces that nothing in live config names a superseded tag.
- **Ratifying a transition includes updating the `sp_watch` baseline.**

**On artifacts**

- `data/predictions/` is **byte-immutable**; `data/results/`, `data/graded/`, `data/lines/`,
  `data/quota/` are **append-only**; `reports/` are **renderings** and regenerable (D22/D23).
  Hooks enforce the first two — do not attempt to work around a hook block.

---

## (e) SP+ posture — armed, half-fired

The returning-production half of the transition **already landed**: CFBD published 136 rows, SPEC §3.1
exception 1 ran, and the model was retagged **`v2026-frozen`** → **`v2026-frozen-2`**. The baseline in
`scripts/sp_watch.py` was updated to the ratified post-transition state:

```python
BASELINE = {"sp_ratings": 0, "returning_production": 136}
```

**`sp_watch` is therefore now armed for `sp_ratings` alone.** It exits 2 and opens an Issue when SP+
ratings publish. It does not fail a check — the correct response to SP+ landing is a decision
process, not a revert.

**When it fires:**

1. It is **not a defect**. It is an external data event the model was designed to absorb.
2. **SPEC §3.1 runs again** — the same exception process, start to finish. It is written down; follow
   it rather than re-deriving it.
3. A **new tag** is required, and it must be cut **before any affected claim is written**. A claim
   stamped with a superseded tag cannot be un-stamped; `data/predictions/` is byte-immutable.
4. The retag propagates to **every** tag reference (see §d).
5. The `sp_watch` baseline is updated **as part of the ratification**, not after it.

Timing risk: SP+ ratings typically publish in the preseason window, i.e. **plausibly before Aug 29**.
The turnaround is multi-day against a fixed kickoff. This is why §c asks for the `sp_watch` verdict
at Rehearsal 1 rather than waiting for the daily job to surprise you.

---

## (f) Things that will look like bugs and are not

- **Machine commits on `main` with no human involved.** Working as designed (§a).
- **`Nothing to grade yet (not a failure)`** on a green grade run — `EXIT_NO_CLAIM` (4) is a
  preseason state. It used to be `EXIT_ERROR`, which opened a failure issue every preseason Sunday
  for a pipeline that was working correctly. That issue is #36.
- **`cfb-commit` reporting `none of '…' exist yet — nothing to commit`.** `data/results` and
  `data/graded` do not exist until something has been graded. `git add` on a pathspec matching
  nothing exits 128 and used to kill the step.
- **`model_version()` returning `v2026-frozen-2-8-g<sha>`.** That is the **build stamp**, not the
  tag, and the describe suffix is the *normal* post-tag form — freeze-exempt commits legitimately
  move HEAD past the tag all season (D34). `frozen_tag()` is the tag. A bare short SHA there,
  however, means a shallow checkout and the preflight aborts on it.
- **A fixed UTC cron landing an hour earlier in ET after the Nov 1 EST flip.** Deliberate — earlier
  is always the safe direction for a pre-kickoff capture. Every run logs its actual ET time.

---

## (g) Lessons this session paid for — the ones that generalise

These were learned by shipping something broken, not by reasoning. Each cost a defect.

1. **String-presence-in-YAML is not behaviour.** The failure-signature computation shipped in a form
   that crashed its own step (`grep` exits 1 on no match → `pipefail` → `set -e`), and it failed on
   exactly the branch it was written for — so a second, different failure would have produced **no
   notification at all**, worse than the throttled duplicate it replaced. It shipped because the
   tests asserted substrings in the YAML and never executed the shell. `tests/test_failure_signature.py`
   now extracts the real block between markers and runs it under the same `set -euo pipefail`.
   **If you write a test that greps a workflow file, ask what would happen if the code inside it
   never ran.**
2. **`dry_run` gates only the push — it does not gate side effects.** A failing dry-run smoke filed a
   real, correctly-labelled issue (#38), and — the worse half — a *passing* dry run would have
   **closed** a real unresolved one. Only run ordering avoided it, and sequencing is not a control.
   Both directions are now gated. Whenever you add a mode flag, enumerate every side effect it must
   suppress, in both directions.
3. **Cite what you created, not what you expect to exist.** A PR number was once inferred from
   GitHub's "create a PR by visiting" hint and cited; it belonged to an unrelated open issue.
4. **A test can pin a defect.** One test asserted that a team showed "No schedule data" — encoding
   the bug as the contract. Another matched two strings that both predated the guarantee it claimed
   to enforce. **Prove a test can fail** — mutate the code and watch it go red — or you have not
   written a test.
5. **Incidental state is not a fixture.** A test compared `docs` at HEAD against `docs` at the tag,
   which differed only *because HEAD happened to be ahead*. A retag put HEAD on the tag and the test
   failed for a reason unrelated to its subject.
6. **A working pipeline in an early-season state must not look like a broken one.** Every false alarm
   spends the operator's trust in the alarm, and the alarm is the only thing between a silent failure
   and the season.
7. **Retagging is a sweep, not an edit.** `season.json` kept pointing at the superseded tag after the
   retag, so every freeze assertion was validating the *wrong reference* — and passing, because the
   frozen trees are identical at both tags. A check that passes against the wrong input is worse than
   one that fails.

This session found and fixed **nine** defects in the hardening batch alone (PR #39), every one of
them in a *guard* rather than in the model. The pattern that keeps recurring across the project is
not bad logic — it is **guards that were never executed**.

---

## (h) Reading list, in order

1. `docs/PIPELINE.md` — the operating manual: cadence, crons and their DST reasoning, commit
   choreography per tier, the failure path, the budget guard, the rehearsal procedure, and the
   `season.json` key → consumer table.
2. `SPEC.md` §10 (the pipeline) and **§3.1** (the freeze-exception process — you will need it if
   SP+ lands).
3. `docs/DECISIONS.md` **D29–D37** plus the D22/D23 addendum — every Phase-5 ruling, with the two
   as-built amendments on D31.
4. `docs/2027_NOTES.md` §8 — carry-forward items deliberately **not** fixed this season. Do not
   start on them; they are next year's.
5. `season.json` → `pipeline` — the config every workflow reads.

**`docs/HANDOFF_PHASE5.md` is this file's predecessor and is now superseded.** It is still on `main`
and its own header says to delete it when Phase 5 closes — which it has. Where the two disagree,
**this file wins**: the older one predates the retag and still describes `v2026-frozen`, the
330-game fingerprint and Phase 5 as "not begun". Its deletion is a one-line docs PR left for the
owner rather than taken unilaterally.

**When the season has run cleanly, delete this file too.**
