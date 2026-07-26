# A6 PR summary — Altitude metres/feet unit mismatch (PR #20)

> **Lifecycle.** A PR summary — a durable record of what shipped and why, **RETAINED, not retired.**
> `docs/pr-summaries/` is a stable home explicitly **outside** the proposal lifecycle (owner ruling,
> 2026-07-25): these are not proposals and they do not expire. The authoritative records remain
> `docs/CALIBRATION_LOG.md` ("A6") and `docs/FREEZE_CHECKLIST.md`; this captures the review context
> around them. **PR #20 is MERGED.**
>
> **Status:** MERGED. Reviewer verdict was **GO**.
> **PR:** https://github.com/Brandon12200/cfb-predictor-2026/pull/20
> **Branch:** `freeze-prep-a6` (3 commits, base `830f92c`).

---

**PR #20 open — pausing here as instructed.** https://github.com/Brandon12200/cfb-predictor-2026/pull/20

To be clear on what I found when I checked: **#19 was the only merged PR** — the `freeze-prep-a6` branch had zero commits, so A6 was ruled but unimplemented. It's implemented now.

## A6 fixed, all four requirements met

Elevation stays **metres at rest**, `elevation_feet()` is the single conversion at the intel seam, and `factors/`/`engine/` are **untouched** — the ratified 3b.1 constants stay byte-identical. Measured **0 → 16 of 330** tracked-slate activations at Colorado/BYU/Utah, max edge unchanged at 0.2338.

**Requirement 3 resolved cleanly:** no wk1 game has a high-altitude home venue (Colorado is *away* at Georgia Tech), so the golden hash is identical and was correctly not regenerated.

## Three things worth your attention

**1. `verify-phase-2` caught a stale derived artifact.** The fix moves the *matchup pricer*, not just the contrarian factor, so `model_spread` changed at altitude venues and left the committed projections stale — 17 of 138 teams. Regenerated. The part worth noting: **`make test` and `verify-phase-3` were both green while it was stale.** Only the six-target sweep found it. Same failure mode as the 3b `travel_cap` change, so the log now states the rule outright.

**2. Your coverage question had a third answer, and it corrects me.** Not a join defect, not CFBD absence — **deliberate scope**. The committed registry holds all 138 teams with locations (132 with elevation), Air Force and Wyoming included; the snapshot builds over the tracked P4+independents slate, which is SPEC §5.5's specification, asserted by the season-start membership check. My PR-#19 "five absent high-altitude programs" claim was a misreading. **No action needed** — but I'd still like your explicit confirmation of that framing, since it's neither disposition you offered.

**3. A denominator correction that goes against me.** `both teams tracked = 330` — *exactly* 3c.5's basis. My A4/B measurements used 734, including 404 games with untracked empty-data teams. Re-measured on 330: p50 and mean rise, but **max is identical and zero games clear 0.5 or 0.75 either way** — all A4/B conclusions stand, only the stated denominator was wrong. 3c.5 was right all along.

## Reviewer: GO

It reproduced the pre-fix behaviour by patching the conversion to identity and independently confirmed 0→16. Three should-fixes applied — including a good catch I'd missed: `inspect_snapshot` displays the pre-fix stored intel blob, which now reads `alt(as-stored)` with a SCHEMA caveat. Its one nit was mistaken (the 138/132 figure *is* repo-reproducible from the committed registry); the entry now cites the source.

**Gates:** 449 passed / 2 skipped, lint clean, all six verify targets PASS.

## On session depth — my recommendation stands, more firmly

This session has now produced **two corrections to claims I made in merged PRs**. That's the signal. I'd stop here: merge #20, then **hand off before the lint-scope fold-in and pre-flight**. Those touch ~200 style errors across two freeze-bound files where the entire job is proving no behaviour changed, followed by the audit that gates an irreversible tag — and today's `verify-phase-2` catch is a live demonstration that stale-artifact propagation is easy to miss when you're deep in it.

Say the word and I'll write `docs/HANDOFF_FREEZE.md` with the full carry-forward: ledger closed, the two corrections, the six-target-sweep rule, and the fold-in → pre-flight → tag sequence.

---

## Appendix — commits on this branch

| | |
|---|---|
| `bf2a5b1` | the fix, log entry, SCHEMA unit contract, regression pins |
| `3b42793` | reviewer fixes — retire spent proposals, label pre-fix stored altitude |
| `adc4441` | regenerate `data/projections/` for the pricer change |

## Appendix — the defect

`venues[*].elevation` is served by CFBD in **metres**; `altitude_points()` compared it against the
ratified 3b.1 `altitude_threshold_ft = 4000.0` (**feet**). The dataset's maximum elevation is
**1634.04**, so the comparison was false for every venue in every week — `Altitude` fired **0/330**
and could never have fired at any point in the season.

Ground truth: Boulder stores `1634.04`; 1634.04 × 3.28084 = **5,361 ft** against a real ~5,328 ft.

Ratified constants silently neutered by a comparison that cannot be true — **same family as A1,
third occurrence** in this ledger.

**The defect was documented in a comment while being asserted through.** `tests/test_schedule_intel.py`
carried `LARAMIE` with `"elevation": 2194.0` annotated `# ~7200 ft altitude`, and the test asserted
`intel["altitude"] == 2194.0`. The author knew it was metres, the comment said feet, and the test
pinned the unconverted passthrough. A test can enforce a contract and still enshrine a units bug.

**Root cause is a contract ambiguity, not a typo.** Nothing stated the unit; CFBD serves metres; the
constant was named `_ft` and reasoned in feet at 3b.1. Both halves individually correct — only the
join was wrong.

## Appendix — the four requirements

| # | Requirement | Status |
|---|---|---|
| 1 | Snapshot bytes unchanged; conversion at the read seam in freeze-exempt `data/` | ✅ elevation stays **metres at rest**; `elevation_feet()` is the single conversion; `factors/` and `engine/` **untouched** |
| 2 | Full behavior-change treatment, D19 pattern, before/after evidence | ✅ own CALIBRATION_LOG entry |
| 3 | Regenerate the golden only if a wk1 game is touched | ✅ **no wk1 altitude game** — golden hash **identical**, not regenerated |
| 4 | (d)-rejection rationale verbatim | ✅ *"dormancy-as-design covers absent inputs, never broken joins"* |

`docs/SCHEMA.md` now states the unit contract (metres at rest → feet at the intel seam; any new
consumer must convert), closing the ambiguity that caused this.

## Appendix — measured before / after (tracked slate, 330 games)

| | before | after |
|---|---|---|
| `Altitude` activations | **0 / 330** | **16 / 330** (4.8%) |
| max edge | 0.2338 | **0.2338** (unchanged) |
| mean edge | 0.0551 | 0.0592 |

The 16 are every non-neutral tracked game at Colorado (5,361 ft), BYU (4,633), Utah (4,631) — all
Big 12 — each taking the full 1.2 pts (~48% of HFA). Max edge is unchanged: the affected games all
sat below the prior maximum.

**Week-1 golden:** `85442a791bc395bfed830d31e929eccf72c52af7ad5f329c303b5f1808b8ee41` — identical
across the fix.

**Determinism re-verified while measuring:** shared vs per-game `PredictionEngine` instances agree
across all 330 games, so `build_predictions`' single-instance reuse carries no order dependence.

## Appendix — all FBS venues clearing 4,000 ft (correct units)

| venue | feet | tracked? |
|---|---|---|
| Wyoming | 7,218 | no (MW) |
| Air Force | 6,643 | no (MW) |
| **Colorado** | **5,361** | **yes** |
| New Mexico | 5,100 | no (MW) |
| Colorado State | 5,014 | no (MW) |
| Utah State | 4,685 | no (MW) |
| **BYU** | **4,633** | **yes** |
| **Utah** | **4,631** | **yes** |
| Nevada | 4,615 | no (MW) |

## Appendix — regression pins

High-altitude venue must **clear** the threshold and produce `altitude_value`; sea-level must
**not** (guards blanket-fire); neutral site yields no edge however high; missing elevation yields
**`None`, never `0.0`** (binding principle #4). These are the checks that would have caught the
original defect.

## Appendix — evidence as pasted in the PR

```
make test    449 passed, 2 skipped
make lint    All checks passed! / Success: no issues found in 40 source files

verify-phase-0: PASS   verify-phase-1: PASS   verify-phase-2: PASS
verify-phase-3: PASS   verify-phase-4: PASS   verify-phase-4-5: PASS
```

## Appendix — open items for the owner

1. **Merge PR #20.**
2. **Confirm the venue-coverage framing** — "no finding; scope working as specified" (neither the
   fix-it nor the log-a-limitation disposition offered, because it is neither).
3. **Session-depth decision** — hand off before the lint-scope fold-in and pre-flight (recommended),
   or continue in-session.
4. **PR-summary home** — keep creating/retiring these under `docs/proposals/`, or give them a stable
   directory outside the proposal lifecycle.

**Remaining pre-tag path:** lint-scope fold-in (`factors/factor_registry.py` +
`engine/prediction_engine.py` into `LINT_PATHS`/`TYPED_PATHS`) → `calibration-auditor` pre-flight →
**FREEZE-READY** → owner cuts `v2026-frozen`.
