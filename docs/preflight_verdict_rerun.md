# Pre-freeze `calibration-auditor` RE-RUN verdict — **FREEZE-READY**

**Run:** 2026-08-04, on `main` @ `d112d4e`. **Second and final run.**
**Scope:** the complete `docs/CALIBRATION_LOG.md` (1,767 lines) + the frozen paths `factors/` and
`engine/`, filtered through `docs/CALIBRATION_EXCLUSIONS.md`. **Full charter, not a delta review** —
prior findings can regress, and three PRs of new content had landed.
**Covers:** PR **#25** (nine dispositions), PR **#26** (venue-timezone fallback), PR **#27**
(edge-ceiling entry + two integrity fixes).

> ## Verdict: **FREEZE-READY — 0 blockers, 2 should-fix, 1 nit.**
>
> **Nothing on this list is tag-blocking** under the ratified triage standard (blocks only for an
> **unlogged live constant** or a **behavior-affecting defect**). Both should-fix items and the nit
> are one-line known states, dispositioned below.

**Re-run condition, still standing:** any change to `factors/`, `engine/`, the calibration config, or
`docs/CALIBRATION_LOG.md` after this verdict and before the tag **invalidates it and forces another
run**. Nothing has been merged since `d112d4e`.

---

## 1. Both prior blockers are closed, verified in source

The 2026-08-03 run returned **NOT-FREEZE-READY** on two blockers. Both are closed, and the auditor
confirmed the dispositions **in source rather than from the log's claims**:

| Prior blocker | Disposition | Verified |
|---|---|---|
| `style_mismatch.py` — ~20 unratified branch constants | **Dormant for all of 2026** (B-1) | `calculate()` returns `0.0` unconditionally; `_calculate_2027_reference` has **no caller** outside its own definition and the repointed pace-invariance test. *The dormancy is real, not cosmetic.* |
| `momentum_factors.py` — unlogged scaling arithmetic | **Eleven constants ratified per-number** (B-2) | Arithmetic re-verified line-for-line against the log entry; scale-checks tied to the **true normalized weight**, closing the S-2 lesson |

**All five prior should-fix items and both nits are verified dispositioned in source, not merely
claimed. No regressions.**

## 2. Independent recomputation — the auditor did not take the numbers on trust

It rebuilt the edge-ceiling arithmetic by hand from the factor modules, rather than reading
`scripts/measure_edge_ceiling.py`'s output:

| Quantity | Documented | Recomputed | |
|---|---:|---:|---|
| Raw weight sum (15 factors) | 1.5400 | **1.5400** | ✓ |
| Theoretical ceiling | 1.0023 | **1.00227** | ✓ |
| Vehicle ceiling | 0.8269 | **0.82695** | ✓ |
| Dormancy share | 30.5% | **30.5%** | ✓ |
| Live share of unity | 69.5% | **69.5%** | ✓ |
| 0.75 / 1.0 vs theoretical | 74.8% / 99.8% | **74.8% / 99.8%** | ✓ |
| 0.75 vs vehicle | 90.7% | **90.7%** | ✓ |

It also verified the **registry-integrity check is ordered before the ceiling check**, exactly as the
entry claims, and validated all 8 `data/venue_timezones.py` entries against real geography.

## 3. Findings

### S-1 — `docs/HANDOFF_FREEZE.md` is stale *(should-fix, not blocking)*

`docs/HANDOFF_FREEZE.md:48-52`. It still frames the remaining path as "lint fold-in → pre-flight"
(the fold-in is done; this is the *second* pre-flight), and its §(b) defect-family tally says "now
three occurrences" for two families that the log now tracks at **4 / 3** and **4**, with a third
family ("input never arrives", 2 members) the handoff never mentions.

**Why it isn't blocking:** it is a **temporary handoff document** whose own header says to delete it
in the PR that closes the freeze sequence. It is not part of the ratification trail and misstates no
ratified constant — only narrative tallies.

**Recommended disposition: delete it in the tag-cutting PR**, which its lifecycle already requires.
Its durable content lives in `CALIBRATION_LOG` and `FREEZE_CHECKLIST`. **Not a 2027 item — a
this-week cleanup.**

### S-2 — `engine/matchup_pricer.py:205`, an unlogged literal in a frozen path *(should-fix, not blocking)*

`elif uncertainty > 0.5:` is a numeric literal in `engine/` with no log entry and no exclusion-list
coverage — precisely the shape the reverse check exists to surface.

**Verified independently: it is non-tunable.** It gates **only** a `caveats.append(...)` — a
human-readable string. The rating-signal weight `w` is computed at `:167` from
`rating_signal_weight(uncertainty, cfg)` using the already-ratified **D11** formula, entirely
independent of this literal. It touches no spread, edge, confidence, or persisted field.

This is the identical shape to the already-excluded `get_explanation` text cutoffs
(`CALIBRATION_EXCLUSIONS.md:41-42`, *"gate only the human-readable explanation string; no effect on
any spread/edge/confidence value"*) — it simply was never added to the list.

**Recommended disposition: one line added to `docs/CALIBRATION_EXCLUSIONS.md`** under the existing
"non-tunable literal KINDS" section, as a **caveat-string threshold**. Owner's call whether that
rides in the tag-cutting PR or goes to 2027; it changes no behaviour either way.

### N-1 — two tier splits on different vehicles sit near each other *(nit)*

`CALIBRATION_LOG.md:826` carries A4's "A 2 / B 405 / C 327" (734-game basis, pre-dating the altitude
and timezone fixes); `:1705` carries the edge-ceiling entry's "A 2 / B 318 / C 10" (330-game basis,
current). **Both are correct for their stated vehicle and date**, and each says so. Flagged only
because tallies were called out for hard scrutiny.

**Recommended disposition: no action.** Adding a cross-reference risks implying one supersedes the
other, which would be wrong.

## 4. Clean results, rule by rule

| Rule | Result |
|---|---|
| 1. Evidence class honesty | **Clean.** No `measured` label rests on the Bug-#7-contaminated archive. The edge-ceiling entry is `reasoned`; the venue-timezone entry is a D19-pattern data-layer wiring fix claiming no measured evidence. |
| 2. Scale-check | **Clean.** B4's dimensionless-CV exemption re-confirmed legitimate on a fresh read of `_calculate_variance_metrics`. The edge-ceiling entry's normalized-weight checks are methodologically identical to A4/B-2 — "not vibes". |
| 3. Ratification stamps | **Clean. No orphaned PROPOSED entries.** Every surviving `PROPOSED` is historical narration inside superseded ledger sections, each followed by its RATIFIED disposition. |
| 4. Cross-entry consistency | **Clean on every flagged item:** dead-constant count **7** (both citations agree), all four defect-family tallies internally consistent, ceiling figures matching the standing gate in `verify_phase_3.py`, and `SCHEMA.md` carrying both the elevation-unit and venue-timezone contracts verbatim. Only staleness is S-1, in a non-authoritative document. |
| 5. Reverse check | **Only S-2.** Every module in `factors/`/`engine/` grepped. **No exclusion-list entry challenged as wrongly excluded.** |
| 6. Per-number composites | **The prior run's core defect class is closed.** B-1 resolved by honest dormancy rather than manufactured per-number arguments; B-2 by genuine per-number scale-checks tied to true normalized weight. |

## 5. Gate state at `d112d4e`

`make test` **684 passed, 2 skipped** · `make lint` clean · **all six verify targets PASS**
(30 checks in phase 3, including the new registry-integrity and edge-ceiling standing gates).

---

## 6. What this means for the tag

**The model is FREEZE-READY.** The reverse-coverage failure that opened this whole sequence on
2026-07-09 — *"the outer gates are logged, the internal formulas are not"* — is closed: every live
calibration constant in `factors/` and `engine/` now carries a log entry, a dormancy disposition, or
a DEAD/known-state record.

**The tag is the owner's to cut, and nothing else runs until then.** Recommended, in the tag-cutting
PR: delete `docs/HANDOFF_FREEZE.md` (S-1, its lifecycle already requires it) and optionally add the
S-2 exclusion line. Neither gates the tag.

**Post-tag, per `docs/FREEZE_CHECKLIST.md`:** extend `.claude/hooks/protected_paths.py` so `factors/`,
`engine/` and the calibration config join `PROTECTED` — edit the shared tuple, not the hooks (D25) —
then Phase 5.
