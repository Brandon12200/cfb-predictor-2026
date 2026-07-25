# B-batch PR summary — B1–B10 ratifications + late A6 finding (PR #19)

> **Lifecycle.** Working document, not an authoritative record. It captures the state of PR #19 at
> the point it was opened, for owner review. The authoritative records are `docs/CALIBRATION_LOG.md`
> ("B-item ratifications"), `docs/FREEZE_CHECKLIST.md`, and — for the open item —
> `docs/proposals/A6_altitude_unit_mismatch.md`. **Delete once PR #19 is merged and A6 is ruled on**,
> together with `B_batch_unlogged_constants.md`. Not authoritative over `docs/SPEC.md`.
>
> *Note: the equivalent file for PR #18 (`ledger_pr_summary.md`) was deleted in this very branch as a
> reviewer should-fix, being past its own lifecycle. This file is the same class of artifact and
> should not outlive its PR either — it exists because the owner asked for the summary in file form.*
>
> **Status:** PR open, paused for owner review. Reviewer verdict **GO**.
> **PR:** https://github.com/Brandon12200/cfb-predictor-2026/pull/19
> **Branch:** `freeze-prep-b-batch` (5 commits, base `d5329b8`).

---

**PR #19 open.** https://github.com/Brandon12200/cfb-predictor-2026/pull/19

## Item 9 found a real bug — and it blocks the tag

**`Altitude` can never fire.** `venues[*].elevation` is in **metres**; `altitude_threshold_ft` is **4000 feet**. Ground-truth check: Boulder reads `1634.04`, and 1634.04 × 3.28084 = 5,361 ft against an actual ~5,328 ft. The **maximum value in the entire dataset is 1634.04** against a threshold of 4000 — the comparison is false for every venue, every week, all season.

Ratified 3b.1 constants silently neutered by a comparison that cannot be true. **Same never-fires family as A1 — third occurrence.** Correcting it moves output on **17 of 734 games** at 1.2 pts each (~48% of HFA), so it's calibration-affecting and pre-tag. **Nothing implemented** — it's written up as `A6` awaiting your ruling, per "gets the full treatment."

I recommend fixing at the **data boundary** rather than in the frozen factor: `data/` is freeze-exempt, the ratified 3b.1 constants stay byte-identical, and the unit gets asserted where it's actually known. The root cause is a contract ambiguity — nothing in the schema states the unit, CFBD returns metres, and the constant was named `_ft` and reasoned in feet. Both halves are sensible; only the join is wrong.

**Secondary finding you should see:** venue data covers **68 of 138 FBS teams (49%)**, and the five highest-altitude programs — **Air Force (~7,258 ft), Wyoming (~7,220 ft)**, Colorado State, New Mexico, Utah State — are absent entirely. Even a corrected altitude signal would be measured on a population that excludes the strongest cases. It also caps `TravelBurden`. I did not propose fixing it pre-tag.

**Sandwich is not a bug.** The logic correctly returns `None` on unknown opponent strength, the normalizer emits exactly the `ranking` key it reads, and `sp_ratings` is empty only because CFBD hadn't published 2026 preseason SP+ at build time — the state **D10 already ratified**, auto-resolving on the Phase-5 weekly rebuild.

## B1–B10 landed as ruled

All nine rulings recorded, including the three-site root cause, the consensus +0.25 re-measure instruction for 2027, and B9's dormant-and-unwired ruling written as *fixing what "data landing" means* rather than re-opening MSF.3.

The method note is in the log: my first flat scan gave a **false DEAD** on B7's nested config, caught before it reached the batch. A false DEAD would have retired live calibration — worth the next audit knowing to use the parent-key check.

## Reviewer: GO

It independently re-verified every code-adjacent claim against source — including cross-checking Folsom Field's elevation against real-world data and reproducing the 17/734 count. Two should-fixes, both fixed in `b810afd`: a checked checklist box sitting directly above prose declaring A6 an open blocker (a real contradiction in the document that gates the tag), and spent working docs past their own lifecycle. I deleted the A4 proposal and the ledger summary, but **kept** `B_batch_unlogged_constants.md` — the CALIBRATION_LOG cites it by name for the per-number derivations, so deleting it would dangle that reference. The deferral and its removal condition are now stated in the file rather than left implicit.

**Gates:** 446 passed / 2 skipped, lint clean, all six verify targets PASS. No file under `factors/` or `engine/` touched.

Three rulings needed: **A6's fix option**, the **49% venue coverage** call, and whether the SCHEMA annotation + regression test ride along. After that, only the lint-scope fold-in and the `calibration-auditor` pre-flight stand between you and the tag.

---

## Appendix — commits on this branch

| | |
|---|---|
| `cf39a9d` | SPEC Week-0 naming, post-tag cleanup list, suite-level golden pin |
| `3184232` | B1–B10 consolidated proposal |
| `4bb6a33` | B1–B10 ratified log entries |
| `911150b` | A6 late A-class proposal (Altitude metres vs feet) |
| `b810afd` | reviewer fixes |

## Appendix — A6 evidence as filed

| Venue | snapshot `elevation` | × 3.28084 | real elevation | verdict |
|---|---|---|---|---|
| Colorado (Boulder) | 1634.04 | **5,361 ft** | ~5,328 ft | **metres** |
| BYU (Provo) | 1412.10 | 4,633 ft | ~4,600 ft | **metres** |
| Utah (Salt Lake City) | 1411.54 | 4,631 ft | ~4,600 ft | **metres** |
| Alabama (Tuscaloosa) | 70.05 | 230 ft | ~230 ft | **metres** |

- Max elevation value in the dataset: **1634.04**; threshold `altitude_threshold_ft = 4000.0`.
- Venues clearing 4,000 ft once converted: **3** — Colorado, BYU, Utah.
- Non-neutral home games at those venues: **17 of 734 (2.3%)**.
- Per-game magnitude if corrected: `altitude_value` **1.2 pts** ≈ **48% of the ratified ~2.5-pt HFA**,
  and ~5× the season's *maximum observed edge* (0.2338).
- Venue coverage: **68 of 138 FBS teams (49%)**; Air Force, Wyoming, Colorado State, New Mexico and
  Utah State absent entirely.

**Options filed in `A6_altitude_unit_mismatch.md` §5:** (a) convert at the data boundary
[recommended, freeze-exempt], (b) convert inside `altitude_points()` [freeze-bound], (c) re-express
the constant in metres [changes a ratified value], (d) accept dormant on the A1 precedent [rejected —
A1's input was a placeholder, here the data is present and correct].

## Appendix — B-batch dispositions as recorded

Audited **per-number** with liveness measured on both A4 vehicles. Governing caveat: the preseason
vehicle is a **lower bound**, so `0/734` means *cannot be exercised here*, not *dead* — except where
marked DEAD, which is static analysis independent of any vehicle.

**Liveness map (measured).** Only **4 of 15** registered factors fire, all physical:
`ByeAdvantage` 191/734 · `ConsecutiveRoad` 185/734 · `TravelBurden` 152/734 · `ShortWeek` 79/734.

| Item | Disposition |
|---|---|
| **B1** component weights 0.4/0.3/0.2/0.1 | RATIFIED — a partition of one unit; ordering = quality > coverage > edge > presence |
| **B1** `/5.0` edge divisor | RATIFIED AS-FOUND; consequence logged — `confidence_score` is a **data-availability score**, edge term reaches ≤**4.68%** of its own range |
| **B1** variance adj `+0.25/+0.1/−0.1/−0.2/−0.3` | RATIFIED; consensus +0.25 logged theoretically dominant, empirically near-inert (**1/734**) — 2027 must re-measure |
| **B1** clamp `[0.15, 0.95]` | RATIFIED; measured **never binds** (range `[0.1635, 0.7862]`) |
| **B2** hierarchy overrides | RATIFIED per-number; `max_impact > _max_output` **log-only**, not harmonised |
| **B3** DesperationIndex | RATIFIED; ≤0.26 pts ≈ 10% HFA. 2 constants logged **DEAD** |
| **B5** physical cutoffs | RATIFIED — the only set governing factors that fire; `Sandwich` honest-absence logged |
| **B6** ExperienceDifferential | RATIFIED; ≤0.12 pts ≈ 5% HFA |
| **B7** momentum | RATIFIED (+ `structural` class for `close_game_threshold=7`, `min_close_games=2`); **positional-consumption fragility logged** |
| **B8** StyleMismatch | `/6.0` RATIFIED AS-FOUND with the discrepancy quantified (intent 6.5, live 5.3); 2 constants **DEAD** |
| **B9** MarketSentiment | **Dormant and unwired for all of 2026**; activation deferred to 2027; not a re-opening of MSF.3 |
| **B10** §16.7 exception | Added, carve-out stated narrowly; 2 H2H keys **DEAD** |

**Six dead constants logged rather than ratified:** `redzone_weight`, `pace_advantage_slower`,
`recent_game_weight`, `max_lookback_years`, `conference_championship_weeks`,
`desperation_multipliers`.

**Three-site root cause recorded:** the pre-Bug-#7 point-scale assumption survives in the NO_BET
floors (3c.5), the `prediction_type` ladder (A4), and B1's `/5.0` divisor — 2027 should sweep for a
fourth rather than assume these were all of them.

## Appendix — evidence as pasted in the PR

```
make test    446 passed, 2 skipped
make lint    All checks passed! / Success: no issues found in 40 source files

verify-phase-0: PASS   verify-phase-1: PASS   verify-phase-2: PASS
verify-phase-3: PASS   verify-phase-4: PASS   verify-phase-4-5: PASS
```

No file under `factors/` or `engine/` is modified on this branch — the B-batch is a documentation
ratification and A6 is proposed, not implemented.

## Appendix — awaiting owner ruling

1. **A6 fix option** — (a) data boundary [**recommended**], (b) in `altitude_points()`, (c) re-express
   the constant in metres, or (d) accept dormant.
2. **49% venue coverage** — accept and log as a known 2026 limitation [**recommended**], or expand the
   venue set before the tag?
3. **If A6 is fixed** — confirm the `docs/SCHEMA.md` unit annotation and the high-altitude/sea-level
   regression test ride with it.
4. **Merge PR #19.**

**Remaining pre-tag work after A6:** the lint-scope fold-in (`factors/factor_registry.py` +
`engine/prediction_engine.py` into `LINT_PATHS`/`TYPED_PATHS`), and the `calibration-auditor`
pre-flight returning **FREEZE-READY**.
