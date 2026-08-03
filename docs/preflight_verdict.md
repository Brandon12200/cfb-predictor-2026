# Pre-freeze `calibration-auditor` verdict — **NOT-FREEZE-READY**

**Run:** 2026-08-03, on `main` @ `560d268` (immediately after PR #23 closed the ledger with B4).
**Scope:** the complete `docs/CALIBRATION_LOG.md` (1,325 lines) + the frozen paths `factors/` and
`engine/`, filtered through `docs/CALIBRATION_EXCLUSIONS.md`.
**Verdict: NOT-FREEZE-READY — 2 blockers, 5 should-fix, 2 nits.**

> **Early by choice.** This pre-flight ran on **ledger-close** rather than the original ~2026-08-20
> calendar date, per **D26**: the tag trigger is the FREEZE-READY verdict, not a date. Running it
> early is what created the room to disposition what it found — see §5.
>
> **Re-run condition (standing, on the record):** if anything touching `factors/`, `engine/`, the
> weight/threshold/calibration config, or `docs/CALIBRATION_LOG.md` changes after this pre-flight
> and before the tag, **this verdict is invalidated and the pre-flight re-runs.** A verdict does not
> carry across a change to what it graded.

**Nothing in this file has been fixed.** Findings are reported for owner disposition, per the
standing rule that the auditor reports and the owner resolves.

---

## 1. Verification note — I re-checked the blockers against source before reporting

The auditor is the grader, but a false blocker costs real schedule days, so both blockers and the
two most consequential should-fixes were independently verified against source before being written
here. **All four confirmed.** Evidence is inline below.

---

## 2. BLOCKERS — tag-blocking under the ratified triage standard

Both meet the bar exactly: **unlogged live calibration constants** in frozen files. Neither is dead
code, neither is documented as a known state, and both shape real predictions once in-season data
arrives — which is inside the freeze window.

### B-1. `factors/style_mismatch.py:164-315` — ~20 unlogged branch weights/thresholds

**B8 covers only the outer layer.** Its RATIFIED text cites `style_mismatch.py:44-52,85-91` — the
top-level `config` dict and the `/6.0` combination. It does **not** cover the private helpers that
compute the terms *fed into* that combination:

| Method | Unlogged constants |
|---|---|
| `_calculate_success_rate_mismatch` (`:164-202`) | weights **×8** (overall), **×4** (standard downs), **×6** (passing downs); **two hardcoded `0.05` thresholds** distinct from `config['min_success_diff']` |
| `_calculate_explosiveness_mismatch` (`:204-240`) | thresholds `0.5`, `0.1`; weights **×1.5**, **×3**; `total_explosiveness > 3.0` → `variance_bonus ±0.3` |
| `_calculate_run_pass_mismatch` (`:255-292`) | thresholds `0.08` (×2), `0.15`; weights **×4** (×2), **×2**; a `stuff_rate_def × 2` conversion |
| `_calculate_havoc_mismatch` (`:295-315`) | `total_havoc > 0.20` → `−0.3`; `home_havoc > away_havoc × 1.3` → `±0.5` |

**Verified live, not permanently dead.** `StyleMismatch` reads `context['advanced_stats']`
(`:68-72`, `:323`, `:346-347`) and activates as soon as that map populates in-season — 3d.1 called
it "fully dormant **early** season," not forever. These constants determine the value that is then
clamped into the ratified ±1.5 range, so the ratified range governs the *output* while the numbers
producing it are unlogged.

**The ledger predicted this and the ratification did not close it.** B8's original PROPOSED text
flagged "*~20 internal branch thresholds… 3d ratified only the output range + confidence bands, not
the pre-clamp weighting*". The RATIFIED entry never followed up.

**Recommended disposition (owner's call):** the B3/B6/B7 treatment — per-number magnitude arguments,
or an explicit "inherits the set's reasoning" note, or a considered **DORMANT/DEAD** disposition if
the weighting is judged unearned pre-freeze (the precedent exists: the `StyleMismatch` pace
component, `PressureSituation`, and `RevengeGame`'s sub-estimators were all dispositioned that way).

### B-2. `factors/momentum_factors.py` — unlogged scaling constants for two live-in-season factors

**B7 covers the config dict, not the arithmetic.** It ratifies `trend_weights`,
`recent_games_window`, `improvement_thresholds`, `consistency_bonus`, `clutch_weights`,
`close_game_threshold`, `min_close_games` — but not:

| Method | Unlogged constants |
|---|---|
| `_scale_trend_improvement` (`:154-164`) | hardcoded returns **`1.5` / `1.0` / `−1.0`**, and the linear-scaling divisor **`/10.0`** — the actual point-scale mapping for a real trend |
| `_calculate_consistency_bonus` (`:166-180`) | std-dev cutoffs **`7`** / **`14`**, and the **`×0.5`** middle-band multiplier |
| `_calculate_team_clutch_performance` (`:296-311`) | the **`×0.8`** close-game / **`×0.2`** blowout split, and the `min(len(close_games)/4, 1.0) × 0.2` experience bonus |

**Verified against source** — these are the live return paths, not commentary. They are the point
magnitude math for two `momentum_factors` (7% of the additive budget, 3b.2), vehicle-dormant only in
the sense that no completed games exist yet — the same caveat the B-batch applies everywhere else
("*0/734 means this vehicle cannot exercise it, NOT that it is dead code*").

**Recommended disposition:** same as B-1.

---

## 3. SHOULD-FIX — real gaps, none behavior-affecting today

Under the triage standard these are **not** tag-blocking: each is either a documentation defect or a
structurally dead constant. Recommended disposition for all five: **one log line each**, no proposal
cycle.

**S-1. `momentum_factors.py:237` — B7 ratified a DEAD constant as live.**
`experience_multiplier = 1.2` is ratified in B7 as "20% amplification". **Verified: it appears
exactly once in `factors/` and `engine/` — its own assignment. Nothing reads it.**
`_calculate_team_clutch_performance` hardcodes `0.2`/`4` instead. This is the **inverse** of the
false-DEAD risk B7's own method note warns about: here a genuinely dead constant was ratified as
though live. → Recommend re-dispositioning as DEAD alongside the six already logged.

**S-2. B3's DesperationIndex scale-check uses the wrong weight — arithmetic verified wrong.**
B3 states "*±2.0 output at weight 0.13 ⇒ ≤0.26 pts ≈ 10% of HFA*". **Computed live from the
registry:** raw weight sum across all 15 factors = **1.54**; `DesperationIndex` raw `0.10`
(`situational_context.py:23`) normalises to **0.0649**, not 0.13. True max contribution =
`2.0 × 0.0649` = **0.13 pts ≈ 5.2% of HFA**, not 0.26 pts / 10%. The `0.13` figure is the
*situational category's* share, not the factor's own weight.
**The conclusion is unaffected and conservative** — the real number is *half* the stated one, so
"in band" holds with more room. → Recommend correcting the arithmetic in the entry.

**S-3. `engine/variance_detector.py` — unlogged literals beyond B4's scope, all structurally dead.**
`_analyze_directional_agreement` (`:180-189`) `0.7`/`0.5`; `_identify_outlier_factors` (`:252`)
z-cutoff `1.5`; `_interpret_variance_implications` (`:308`) `inter_cat_var > 0.5` (a *different*
metric from the CV cutoffs); `_generate_recommendation` (`:322-349`) `bet_size_adjustment`
`1.0/0.9/0.7/0.5/0.25`, the `×0.7` dampener, the `>0.8` / `×1.1` boost.
Auditor grep-confirmed `bet_size_adjustment`, `outlier_factors`, `agreement_ratio` are populated but
**never consumed** outside the file except via the unpersisted `implications` list — the same
dead-diagnostic pattern already dispositioned for the A3 map and B4's `:225`. **Structurally** dead
(no vehicle dependency), so unlike B-1/B-2 it stays unread regardless of season progress.
→ Recommend a single DEAD/diagnostic-only entry.

**S-4. `factors/situational_context.py:203-212` — `RevengeGame`'s 6 dead config constants unlogged.**
`revenge_timeframes` (`1.0`/`0.6`/`0.3`), `coaching_connection_weight 0.7`,
`margin_of_defeat_weight 0.3`, `rivalry_amplifier 1.2` — 0 references, and
`RevengeGameCalculator.calculate()` is provably always `0.0` (all three sub-estimators
`return 0.0`, `:250-278`). Same pattern B3 caught for `DesperationIndex` **in the same file**,
missed for its sibling. → Recommend logging DEAD.

**S-5. `factors/factor_registry.py:178-179` — two registry overrides unnamed by B2.**
`PressureSituation {0.75, 3.0}` and `RevengeGame`'s `max_impact 4.0`. Both confirmed inert
(`PressureSituation.calculate()` returns `0.0` per ratified 3c.2; `RevengeGame` per S-4). Rule-6
completeness gap only. → Recommend one line.

---

## 4. NITS

**N-1. Stamp terminology.** 3c.7 and 3c.8 are stamped **APPROVED** (owner, 2026-07-04) where the
log's legend defines only PROPOSED / RATIFIED / FROZEN. Both carry owner + date and are clearly
resolved — **not** orphaned PROPOSED entries. Terminology drift only.

**N-2. `docs/CALIBRATION_EXCLUSIONS.md:64-66` is stale.** Its "NOT excluded" section still describes
the internal-factor formulas, the CV cutoffs and the confidence/edge engine as
"*PROPOSED / decision-pending*" — untrue now that A1–A6 and B1–B10 are closed and the A2 cluster is
retired. Descriptive staleness only; does not affect what is actually excluded.

---

## 5. Clean rule-by-rule results (what the audit did NOT find)

Recorded because a verdict that lists only failures misrepresents the state of the log.

| Rule | Result |
|---|---|
| 1. Evidence class honesty | **Clean.** No `measured` label cites the Bug-#7-contaminated archive. A4/B-batch `measured` claims are correctly scoped to the corrected model's real-schedule behaviour; D9/D12 to price/outcome-derived market data. |
| 2. Scale-check | Clean except **S-2**. **The B4 dimensionless-ratio exemption was judged LEGITIMATE, not an evasion** — the auditor read `_calculate_variance_metrics` and confirmed the CV is genuinely not a point magnitude. |
| 3. Ratification stamps | **No orphaned PROPOSED entries.** D20's PROPOSED language is historical narration, correctly superseded. |
| 4. Cross-entry consistency | Clean except S-2 and N-2. D9/D11/D12 vs `power_ratings.py`, 3b.1 vs `physical_coefficients.py`, the floors/tiers vs `prediction_engine.py:23-32`, the B2 overrides, and **D26's freeze-date propagation** all matched source exactly. |
| 5. Reverse check | The findings above. **No exclusion-list entry was challenged as wrongly excluded.** |
| 6. Per-number composites | **The core defect class.** B3 and B6 did this correctly; B7 and B8 ratified the outer block but not the inner arithmetic — which is B-1, B-2 and S-1. |

---

## 6. Schedule conflict — surfaced, not absorbed

**The binding tag date is Aug 8; today is Aug 3.** Clearing the two blockers is not a documentation
edit — it is a **calibration ratification batch** (per-number arguments for ~30 constants across two
factors), which under the standing process means: measured evidence → proposal file → owner
pause → ratification → log entry → reviewer → PR → merge → **pre-flight re-runs** (§ re-run
condition). That is the B-batch shape, and the B-batch took multiple sessions.

**This is a real risk to Aug 8 and I am not going to absorb it.** Three paths, for your call:

1. **Full per-number batch** (the B3/B6/B7 treatment) — highest fidelity, likeliest to slip Aug 8.
2. **Blanket dormancy disposition** — rule both factors' branch arithmetic DORMANT/unearned pre-freeze
   and log it as such, with 2027 owning the per-number work. Precedent exists (pace component,
   `PressureSituation`, `RevengeGame`). Fast, honest, and it makes the *factors* dormant rather than
   pretending the numbers are justified.
3. **Accept and log as a known state** — record the two surfaces as unlogged-but-frozen with an
   explicit 2027 obligation. **I do not recommend this**: it is exactly the reverse-coverage failure
   the July shakedown existed to close, and it would make the FREEZE-READY verdict a formality.

**My recommendation is (2)** for `StyleMismatch` — it is genuinely unexercised and its pace component
is already dormant — and **(1) scoped narrowly** for momentum's three methods, which are fewer
constants and will fire the moment games are played. That is achievable before Aug 8 if the proposal
goes to you tomorrow.

The downstream dates (pipeline PR Aug 14, first rehearsal Aug 17) are **not** at risk from this
either way — they depend on the tag existing, and even the slower path lands well inside them.
