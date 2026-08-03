# B4 — `variance_detector` CV cutoffs: the gap the ledger's B1→B5 numbering skipped

> **Lifecycle: working document.** Not authoritative over `docs/SPEC.md`. Once ratified, its content
> moves to `docs/CALIBRATION_LOG.md` (B-item section) and this file is **deleted** at the next
> phase/session boundary. Proposals are scaffolding, not records.
>
> **Status: PROPOSED — awaiting owner ratification.** Docs-only: no `factors/`, `engine/`, or
> config change is proposed. Must land **before the tag** — it is the last unlogged live constant.

## 0. Why this exists

The reverse-audit ledger enumerated **B1–B10**. The ratification batch (owner, 2026-07-16) runs
**B1, B2, B3, → B5**, B6–B10. **B4 was never ratified**, and the omission is invisible from the log
alone because every neighbouring item is present. `docs/proposals/B_batch_unlogged_constants.md`
skips it identically (its §4 is headed "B2–B7" and goes B3 → B5), so the proposal, the ratification,
and the log all inherited one enumeration slip. Confirmed by three-source grep: B4 appears nowhere
outside the original ledger listing.

**B4 is `engine/variance_detector.py:41-47`** — the five coefficient-of-variation cutoffs:

```python
self.thresholds = {
    'consensus': 0.15,   'mild': 0.30,   'moderate': 0.50,   'strong': 0.75,   'extreme': 1.0,
}
```

## 1. The liveness chain — why this is a live constant, not a diagnostic

Stated explicitly, because **A3 downgraded a neighbouring item in this same file to diagnostic-only**
and the two must not be confused. A3 concerned the `factor_categories` **map**; B4 concerns the
**cutoffs**. They are different code, with different reach:

```
_determine_variance_level(cv)          variance_detector.py:266-277   ← THE B4 CUTOFFS
        ↓  sets
variance_level                         variance_detector.py:97,103
        ↓  consumed by TWO ratified gates
 (1) 3c.5 floor 3 — hard NO_BET        prediction_engine.py:411-413
     `if level in NO_BET_VARIANCE_LEVELS` (= frozenset{'extreme'})
     plus `recommendation.action in NO_BET_VARIANCE_ACTIONS` (= {'AVOID_OR_MINIMUM'}),
     which `_generate_recommendation` derives from the SAME level ladder (:323-342)
 (2) B1 variance adjustments           prediction_engine.py:504-520, 557-566
     `consensus +0.25 / mild +0.1 / moderate −0.1 / strong −0.2 / extreme −0.3`
     — keyed on the label these cutoffs produce
```

So: **3c.5's floor 3 and B1's ratified adjustments were both ratified against labels that these
five unratified numbers produce.** That is the reverse-coverage failure the audit exists to catch —
the outer gate is logged, the number that decides which side of the gate you land on is not.

`variance_level` derives from the **overall** CV (`variance_detector.py:97`), never from the A3
category map — so A3's "diagnostic only" finding does **not** transfer here.

## 2. Method

Same vehicle as A4, A6 and the B-batch: the **330 both-teams-tracked games** (3c.5's basis), each
driven at **its own week** so `compute_schedule_intel` fires at real in-season rates, with a
deterministic placeholder line for games lacking one (the engine refuses to price without a line;
the placeholder does not affect factor activation). Read-only; no artifact was written.

> **⚠ Reachability caveat, governing every number below** — the same one that governs the whole
> B-batch. The vehicle is the **preseason** snapshot: no completed games, no in-season advanced
> stats, no movement data. A reading of "never fires" means **this vehicle cannot exercise it**,
> not that it is dead code.

## 3. Measured — the cutoffs barely run, and never decide anything

**The 3-active-factor gate dominates.** `analyze_factor_variance` returns
`insufficient_data` when fewer than 3 factors are active (`variance_detector.py:80-81`), *before*
any cutoff is consulted:

| `variance_level` | games | share |
|---|---:|---:|
| `insufficient_data` (< 3 active factors) | **312** | 94.5% |
| `extreme` | 10 | 3.0% |
| `moderate` | 7 | 2.1% |
| `mild` | 1 | 0.3% |
| `consensus` | 0 | 0.0% |
| `strong` | 0 | 0.0% |

**Only 18 of 330 games reach the cutoffs at all.** Every one of those 18 has exactly 3 active
factors; the other 312 have **zero**.

**The decisive measurement — the gate never changes an outcome:**

| | count |
|---|---:|
| Games NO_BET | 330 of 330 |
| NO_BET citing a variance reason | **10** |
| …where variance is the **only** reason (i.e. it flipped the verdict) | **0** |

All 10 are already NO_BET on **both** other floors — edge below 0.75 *and* confidence below 0.50.
Example (wk3 NC STATE@VANDERBILT): `edge 0.02 below threshold 0.75; confidence 0.33 < 0.50;
extreme factor variance; variance recommends AVOID_OR_MINIMUM`. **In the measured state the B4
cutoffs are load-bearing in principle and inert in practice.**

## 4. What the cutoffs actually measure — a structural finding, stated for the record

The CV is `abs(std_dev / mean)` (`variance_detector.py:156-159`). Factor values are **signed**
(positive favours home). So when factors point in *opposite directions* — precisely the
"disagreement" the detector is looking for — the mean collapses toward zero and the ratio explodes:

| game | active factor values | mean | CV | level |
|---|---|---:|---:|---|
| wk3 MIAMI@WAKE FOREST | Bye −1.0, ConsecRoad 0.5, ShortWeek −1.0 | −0.500 | 1.73 | extreme |
| wk9 OHIO STATE@USC | Bye −1.0, ConsecRoad 0.5, Travel 1.5 | 0.333 | 3.77 | extreme |
| wk8 USC@WISCONSIN | Bye −1.0, ConsecRoad 0.5, Travel 1.2 | 0.233 | 4.82 | extreme |
| wk3 NC STATE@VANDERBILT | Bye −1.0, ConsecRoad 0.5, Travel 0.6 | **0.033** | **26.89** | extreme |

**Consequence, and the honest description of these five numbers:** on signed values the CV is not a
smooth disagreement scale — it is close to a **sign-agreement detector with an unstable magnitude**.
Mixed-sign games jump straight past all five cutoffs; same-sign games sit low. The measured
distribution shows exactly that shape: 7 `moderate`, 10 `extreme`, and the `strong` band
(0.50–0.75) **empty**. The intermediate rungs are structurally hard to land on.

This is the **same family** as the three already-logged pre-Bug-#7 scale artifacts (3c.5 floors, A4
ladder, B1 `/5.0`): a number whose stated semantics ("how much do factors disagree, on a 0–1-ish
scale") do not match its measured behaviour. It is recorded here rather than corrected — see §6.

## 5. Proposed dispositions — per-number, as the composite doctrine requires

**Evidence class: `reasoned`.** Not `measured`: the distribution above characterises *behaviour*,
it does not fit the boundaries to outcomes, and no admissible model-independent market data bears
on them (the 2025 archive tables remain inadmissible, Bug #7).

**On the ×HFA scale-check.** The auditor's rule 2 asks every magnitude to be checked against the
ratified ~2.5-pt HFA. **These five are dimensionless ratios, not point magnitudes** — a CV of 0.30
is not "0.30 points" and multiplying it by HFA is meaningless. The scale-check that *does* apply is
the one in §3–§4: what the boundaries do to real games. Stated explicitly so the pre-flight reads
this as a considered exemption, not an omission.

| # | Constant | Value | Proposed | Argument |
|---|---|---:|---|---|
| B4.1 | `consensus` | **0.15** | **RATIFY as-found** | Below 15% relative dispersion the factors are telling one story; the most confident band, and it feeds B1's largest single adjustment (+0.25). Measured: fires **0/330** on this vehicle — it needs ≥3 same-signed, similar-magnitude factors, which the preseason state cannot produce. |
| B4.2 | `mild` | **0.30** | **RATIFY as-found** | 2× `consensus`; a doubling per band is a stated, uniform progression rather than a fitted one. Fires **1/330**. |
| B4.3 | `moderate` | **0.50** | **RATIFY as-found** | The point where dispersion equals half the mean — the natural "these disagree materially" line, and where B1's adjustment turns negative (−0.1). Fires **7/330**, the busiest live band. |
| B4.4 | `strong` | **0.75** | **RATIFY as-found, with its emptiness logged** | Dispersion at ¾ of the mean. Measured **0/330** — and §4 explains why: the band is structurally hard to land on, not merely unexercised. Ratified as a boundary, not as a live band. |
| B4.5 | `extreme` | **1.0** | **RATIFY as-found, with its consequence logged** | Dispersion ≥ the mean. The only cutoff wired to a **hard gate** (3c.5 floor 3). Fires **10/330** — and per §3 changed **0** outcomes, because those games were already declined twice over. |

**The set is a monotone ladder with a uniform stated rationale** (0.15 → 0.30 → 0.50 → 0.75 → 1.0:
each boundary is a fixed fraction of the mean, ending at parity), so per the composite doctrine each
member above carries its own argument *and* inherits the set's progression reasoning.

## 6. Why NOT recalibrate now — recommendation

Three reasons, in order of weight:

1. **It would move `confidence_score` on every game with ≥3 active factors**, and therefore re-open
   **3c.5's floors and 3c.6's tiers**, both of which were ratified *against this formula*. That is
   the identical argument that carried B1's `/5.0` divisor "ratified as-found with its consequence
   logged", days before the tag.
2. **The measured state shows zero outcome impact** (§3). Changing a gate that decides nothing, to
   fix a shape problem, is exactly the "freeze-bound edit with provably zero behavioural effect"
   that A1 and A4 both declined.
3. **A better fix is not a threshold change.** The honest repair for §4 is to compute dispersion on
   a scale that does not divide by a near-zero signed mean — a *formula* change to a frozen file, an
   order of magnitude beyond a pre-tag calibration tweak, and unmeasurable until a season of real
   in-season activations exists.

**Recommendation: ratify all five as-found, with §4's characterisation logged, and carry the
recalibration question to 2027** alongside the three existing point-scale artifacts.

## 7. The `:225` bare `0.3` — a known state, with code-path evidence

`variance_detector.py:225` carries a **sixth** numeric literal that is *not* a member of the
`self.thresholds` dict B4 covers:

```python
'consensus': cat_metrics['coefficient_of_variation'] < 0.3      # :225
```

**It is provably unreachable in effect — two independent reasons, both verified against source:**

1. **Its only consumer sits inside a branch that cannot be true.** The key is read at exactly one
   site, `_interpret_variance_implications:312-313`:
   ```python
   if 'market' in category and category['market'].get('consensus', False):
       if 'statistical' in category and not category['statistical'].get('consensus', True):
   ```
   **`'statistical'` is not a live category key.** The A3 fix relabelled `StyleMismatch` from
   `statistical` to its real category `matchup`; the live keys are `market`, `matchup`, `momentum`,
   `situational`, `coaching`, `physical` (`:57-65`). So `'statistical' in category` is **always
   False** and the inner branch never fires.
2. **The outer condition cannot be true either.** `_analyze_category_variance` adds a category only
   when it has ≥1 **active** factor (`:214-217`), and `market` contains only `MarketSentiment` —
   ruled **dormant and unwired for all of 2026** (B9). So `'market' in category` is also always
   False.

Even if both fired, the output is a string appended to `implications` — a narrative list that is
**not persisted** (absent from `V2_RECORD_KEYS`), on the same diagnostic path A3 established never
reaches `variance_level`.

**Proposed: log as a KNOWN STATE, not ratified** — the same treatment as the six dead constants in
the B-batch. Ratifying a value that nothing can read asserts a claim the code does not make.

## 8. What the owner is asked to rule

1. **B4.1–B4.5** — ratify all five cutoffs **as-found** (`0.15 / 0.30 / 0.50 / 0.75 / 1.0`),
   evidence class `reasoned`? *(recommended)*
2. **§4's characterisation** — record in the log that the CV is a sign-agreement detector with an
   unstable magnitude on signed values, that the `strong` band is structurally near-unreachable, and
   that this is a **fourth** member of the point-scale-artifact family for the 2027 sweep?
   *(recommended)*
3. **§3's consequence** — record that the `extreme` hard gate fired **10/330** and changed **0**
   outcomes, i.e. it is inert in the measured preseason state, with the reachability caveat that
   in-season activation may change that? *(recommended)*
4. **No recalibration pre-tag**, carrying the question to 2027 (§6)? *(recommended)*
5. **`:225`'s bare `0.3`** — log as a **known state, doubly unreachable**, not ratified?
   *(recommended)*
6. The `×HFA` scale-check exemption for dimensionless ratios (§5) — recorded as a considered
   exemption for the pre-flight?

On ratification the content moves to `CALIBRATION_LOG` under the B-item section, stamped and noted
as the gap the B1→B5 numbering skipped; this file is then deleted.
