# Normalizer fail-closed + SPEC §3 exception 1 (retag to `v2026-frozen-2`)

**Branch:** `fix-normalizer-and-pipeline` → `main` (base `d6715b3`) · **7 commits** · 2026-08-08
**Verdict:** `code-reviewer` **GO** on the full final diff at `00a4734` — no blockers, no
outstanding should-fixes. Two review rounds; 4 should-fixes → 0.
**Gates:** `make test` **940 passed / 4 skipped** · `make lint` clean · **all seven** verify
targets PASS. `factors/` and `engine/`: **zero-line diff**.

---

## Why this exists

`scripts/sp_watch.py` fired: CFBD published **returning production (0 → 136 rows)**. Preseason
**SP+ remains 0**, so `Sandwich` did not wake. D10 activates the RP prior with no code change, so
the frozen model's inputs moved underneath the tag — the gate working as designed.

Measuring that transition rebuilt the week-1 snapshot, which exercised the new dropped-game
detector, which found something else.

## The blocker the detector found

`difflib` fuzzy matching at cutoff 0.8 resolved **16 FCS programs onto FBS teams** — Samford →
STANFORD, Southern → USC, Mississippi Valley State → MISSISSIPPI STATE. Where both sides of an FCS
game resolved, a **fabricated FBS game entered `data["games"]`**, including `NORTH DAKOTA STATE @
NORTH DAKOTA STATE`.

**Ten were already in the `v2026-frozen` vehicle.** Pre-existing, present at the freeze, invisible
because both drop sites simply `continue`d behind comments claiming a "slate reconciler" that did
not exist. Harmless preseason (nothing completed, everything NO_BET) but in-season a completed FCS
result would have moved an FBS team's Elo — Samford's result credited to Stanford.

A second seam, same site: `CANONICAL_OVERRIDES` governed the registry *build* but never reached the
runtime alias vocabulary, so `"California"` resolved to `None` and **all ten of Cal's tracked games
were dropped** (with App State, UL Monroe, Massachusetts).

## The fix

**Membership in the tracked universe is decided only by authoritative routes** — exact canonical,
explicit alias, or a `CANONICAL_OVERRIDES` entry. Fuzzy matching may resolve within the non-FBS
vocabulary but may not confer FBS membership. This is D7's own doctrine applied at runtime.

`CANONICAL_OVERRIDES` is now imported into the alias vocabulary, so one edit serves both the
registry build and name resolution.

The reconciler gains a third class: **114 lower-division matchups a season** would otherwise share a
reason with a genuinely lost FBS game, and nobody reads a warning that cries wolf 114 times.
`non_fbs_matchup` is informational; `unresolved_team_name` now means specifically *an FBS team's
opponent could not be identified*. **That class is now empty.**

**Accepted cost, stated not implied:** fuzzy typo-correction of tracked teams is gone too —
`"Ohio Statee"` returns `None`. The mechanism that forgives a human typo is the one that turned
Samford into Stanford in an authoritative feed.

## Result

| | before | after |
|---|---:|---:|
| fabricated games | 34 (10 at the tag) | **0** |
| self-matchups | 1 | **0** |
| lost tracked games | 10 (all Cal) | **0** |
| tracked slate | 330 | **338** |

Verified by identity, not arithmetic: **+10 real Cal games, −2 fabrications** (`USC@HOUSTON` was
*Southern@Houston*; `STANFORD@AUBURN` was *Samford@Auburn*).

## SPEC §3 exception 1 — the measured delta

| | `v2026-frozen` | `v2026-frozen-2` |
|---|---:|---:|
| fingerprint | `eab7ffdb…20e2d` | **`1c5187eb…0434`** |
| tracked-slate games | 330 | 338 |
| returning production / SP+ | 0 / 0 | 136 / **0** |
| lean home / away / neutral | 195 / 35 / 100 | 198 / 33 / 107 |
| **confidence tier A / B / C** | **2 / 318 / 10** | **322 / 6 / 10** |
| `NO_BET` | 330 of 330 | 338 of 338 |
| max \|`edge_size`\| | 0.2805 | 0.3156 |

**The tier inversion is the consequential line.** A goes 2 → 322 because coverage rose 39.0% →
63.3% and confidence is data-availability-driven (B1). It changes no bet today, but it inverts the
stratification D27's reports rest on — carried to the 2027 drawer as a recalibration obligation.

The fingerprint constant moved **only** under this ratified exception plus a new tag. The
superseded vehicle is **retained**, not overwritten (`data/archive/` is append-only, and it is the
record of what the first freeze measured).

## Two errors of mine, both caught by gates rather than by me

1. **The fingerprint gate caught a sequencing error** — I pinned the vehicle from one rebuild and
   recorded a fingerprint from another. Exactly what it exists for.
2. **`code-reviewer` caught a wrong number in the permanent audit entry.** I recorded
   `max |edge| = 0.0000`; the script read a non-existent `predicted_edge` key and silently
   defaulted to zero. The claim it implied was wrong, not just the digits: every game is NO_BET
   *because edges sit below the 0.75 floor*, not *because they are zero* — physical factors fire
   preseason. Corrected, with the correction recorded inside the entry.

## Security

Actions substitutes `${{ }}` into a `run:` script before bash parses it. A backtick in an issue body
executed — it silently ate `` `Sandwich` `` and `` `verify-phase-3` `` from a real comment. All
untrusted inputs now reach the shell via `env:`, in both issue composites **and** `ci.yml`'s
`github.head_ref` (a fork-controlled branch name; git permits backticks in ref names). That one goes
live on external PRs the moment D37 flips the repo public.

The remaining 31 interpolations are trusted-source (step outputs, `matrix.phase`, our own composite
inputs). The reviewer independently confirmed the triage by checking triggers: the four cadence
workflows are `schedule`/`workflow_dispatch` only, so `no-rehearsal-merge` was the sole
`pull_request`-triggered job. `docs/PIPELINE.md` now states the boundary.

Also fixed: `sp_watch` events get their own `kind` label so an arrival can never be swallowed by an
open failure issue; `freeze-integrity` gains the `clear-failure` step it never had; preflight
self-tests no longer print ABORT blocks into the production log.

## Owner actions

1. Merge (nine required checks now enforced — this is their first real run).
2. Cut the tag on the merge commit:
   ```
   git tag -a v2026-frozen-2 <merge-sha> \
     -m "Freeze exception 1: CFBD returning production + normalizer fabrication fix (SPEC §3.1)"
   git push origin v2026-frozen-2
   ```
   `FROZEN_VEHICLE_SOURCE` points at `v2026-frozen-2`, so
   `test_pinned_sha256_is_the_tag_time_bytes` **skips until the tag exists** and activates after.
   The vehicle is byte-identical to the committed snapshot, so it will pass.
3. Close issue **#32** once its original missing-key condition is confirmed resolved, and let the
   correctly-labelled transition issue be closed by the retag.
