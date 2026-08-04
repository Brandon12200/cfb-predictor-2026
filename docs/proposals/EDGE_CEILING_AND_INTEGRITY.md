# Edge-ceiling structural property + two integrity fixes

> **Lifecycle: working document.** Not authoritative over `docs/SPEC.md`. Once ratified, its content
> moves to `docs/CALIBRATION_LOG.md` and this file is **deleted** at the next phase/session boundary.
>
> **Status: PROPOSED — awaiting owner ratification.** Item 1 is **document-not-retune**: no threshold,
> weight, or normalization value changes. Items 2 and 3 are mechanical integrity fixes.

---

## 1. Edge ceiling — verified independently, with three corrections to the review's figures

**I recomputed from the live registry rather than accepting the review's arithmetic.** The mechanism
is confirmed; three of its numbers are not.

### 1.1 Method

`weighted_value = validated_value × dynamic_weight` (`base_calculator.py:320`), where
`dynamic_weight = weight × max(conf, 0.5)` for PRIMARY and `weight × conf` for SECONDARY
(`:229-234`), and `weight` is the **normalized** weight the registry installs. `total_adjustment`
sums those; `edge = |total_adjustment × multiplicative_adjustment|`, and the sole MODIFIER
(`MarketSentiment`) is dormant at 1.0, so edge = `|total_adjustment|`.

Ceiling = every **live additive** factor simultaneously at max output, max confidence
(`VERY_HIGH = 0.9`), and the same direction.

### 1.2 Measured

| Scenario | Ceiling | 0.75 | 1.0 | 1.5 |
|---|---:|---|---|---|
| **Theoretical** — all live additive aligned | **1.0023** | reachable (74.8% of ceiling) | reachable at **99.8%** | **unreachable** |
| **Physically realizable** — `ByeAdvantage` XOR `ShortWeek` | **0.8795** | reachable (85.3%) | **unreachable** | **unreachable** |
| **On the current vehicle** — also minus input-dormant | **0.7042** | **unreachable** | unreachable | unreachable |

**Correction A — the 1.0 branch.** The review called it unreachable. **Arithmetically it is
reachable**, at 99.8% of the absolute ceiling. It is **physically** unreachable, because
`ByeAdvantage` (a bye last week) and `ShortWeek` (`rest_days ≤ 6`) are **mutually exclusive** — a
bye guarantees long rest. Dropping the smaller leaves 0.8795 < 1.0. The distinction matters in a
frozen record: the branch is not impossible by construction, it is impossible given the schedule.

**Correction B — the 0.75 alignment figure.** The review said ~87%; it is **74.8%** of the
theoretical ceiling, or **85.3%** of the realizable one. The 85.3% figure is the fair one to quote.

**Correction C — the dormancy share.** The review said ~25.7%; I measure **30.5%**
(`0.4700 / 1.5400`). The gap is **our own doing**: `StyleMismatch` (0.15 raw) became dormant
yesterday under B-1, after the review was written. Dormant/multiplicative raw weight is now
`HeadToHeadRecord 0.06 + PressureSituation 0.06 + RevengeGame 0.10 + StyleMismatch 0.15 +
MarketSentiment 0.10`.

**The mechanism is confirmed exactly as described.** Dormant factors keep their raw weight in the
normalization denominator (1.5400) while contributing zero, so the live factors' normalized weights
sum to only ~69.5% of unity. **The edge scale is suppressed by the dormancy share**, and the
ratified thresholds were set against an implicitly full budget.

### 1.3 Confidence corollary — the mechanism holds, the specific claim does not

Measured over the 330-game tracked slate: **38 distinct** `confidence_score` values, range
`0.3337–0.7444`, stdev `0.0538`. A single value (`0.6332`) covers **30.3%** of all games; the top
two cover ~52%. Per week: 8–13 distinct values across 10–33 games, and the same values recur across
different weeks.

**So "tier is effectively week-level" is not quite right either** — it is **coarsely quantized and
data-availability-driven**, which is B1's ratified consequence (`confidence_score` is in practice a
data-availability score) showing up as near-degeneracy. Values cluster because the inputs that move
them are week-uniform, not because the tier is computed per week.

**The "five matchups at 0.72" claim does NOT verify.** Zero games fall in `[0.715, 0.725]`; no game
rounds to 0.72; the maximum observed is **0.7444**. Reported as unverified rather than repeated.

Tier distribution on the 330: **A 2 / B 318 / C 10** — consistent with A4's recorded pattern on its
734-game basis.

### 1.4 Why this is document-not-retune

Changing any threshold or the normalization would move `confidence_score` and the edge on every
game, re-opening **3c.5's floors** and **3c.6's tiers** — both ratified against this formula — with
**four days to the tag** and no measured basis for choosing a replacement. Same argument that
carried B1's `/5.0` divisor and B4's CV cutoffs.

**The mitigation is real and worth stating:** NO_BET games still persist a hypothetical lean and are
graded (D22/3c.5), so **the measurement season is intact** — 2027 gets per-sub-signal ATS% and CLV
whether or not a bet cleared the floor. The season still produces the evidence needed to fix this.

### 1.5 Proposed log entry (structural property, `reasoned`)

> **Edge ceiling vs the min_edge ladder — a structural property, logged not retuned.** The maximum
> attainable `|total_adjustment|` with every live additive factor at max output, max confidence and
> aligned direction is **1.0023 pts** theoretically, **0.8795** once `ByeAdvantage`/`ShortWeek`
> mutual exclusivity is applied, and **0.7042** on the current vehicle. Against the ratified ladder:
> **1.5 is unreachable**; **1.0 is arithmetically reachable at 99.8% of the absolute ceiling but
> physically unreachable** (the bye/short-week exclusivity); **0.75 requires ~85.3% of the realizable
> budget in one direction**. **Mechanism: the dormancy share.** Dormant factors retain their raw
> weight in the 1.5400 normalization denominator while contributing zero, so live normalized weights
> sum to ~69.5% of unity — the thresholds were ratified against an implicitly full budget.
> **Corollary (sharpens B1):** `confidence_score` is near-degenerate — 38 distinct values over 330
> games, one value covering 30.3% — which is B1's ratified "data-availability score" consequence
> made visible, and it means Phase-4 attribution must treat `confidence_tier` as a coarse,
> data-driven stratum rather than a per-game conviction signal. **Mitigation:** NO_BET games persist
> hypothetical leans and are graded, so the measurement season is intact. **2027 obligation:**
> recalibrate the thresholds *and* the normalization against this season's attribution — in
> particular decide whether dormant factors should be excluded from the denominator.

---

## 2. `data/calibration/2025_evidence.json` — a machine-dependent value inside a reproducibility gate

**Confirmed defect.** `meta.source` is
`"/Users/brandonkenney/Projects/cfb-contrarian-predictor-2026/data/archive/2025"` — an absolute path
baked into a committed artifact. `verify_phase_3.py:75-83` rebuilds the evidence with
`build_calibration_evidence(str(ROOT / "data" / "archive" / "2025"))` and asserts the result **equals
the committed file**. On any other machine or checkout location the rebuilt `meta.source` differs and
**`verify-phase-3` fails** — a reproducibility gate that is itself not reproducible.

**Proposed fix:** `analytics/calibration_evidence.py:121` stores the path **repo-relative**
(`data/archive/2025`) when it lies inside the repo, falling back to the given string otherwise; then
regenerate the committed artifact via `scripts/build_calibration_evidence.py`. `data/calibration/`
is **not** in the append-only `PROTECTED` set, so the regeneration is permitted. Verified the
relative form resolves correctly. Freeze-exempt (`analytics/`, `data/calibration/`).

## 3. Registry-integrity pin

**Proposed:** assert at load that the registry holds **15 registered factors** with **raw weight sum
1.5400** (both independently verified twice this session). Placement: a `verify-phase-3` check plus a
unit pin, rather than a hard runtime `assert` in `factor_registry` — a raised assertion inside a
frozen path would turn a degraded import into a crash mid-season, whereas a gate fails loudly at
verification time.

**Why it matters post-freeze:** `_load_all_factors` discovers factors by scanning the directory and
swallows per-module import errors (`factor_registry.py:151-154` logs and continues). A silent import
failure would drop a factor, change the denominator, **renormalize every remaining weight, and
produce a different model under the same tag** — with no signal. This pin is the tripwire.

---

## 4. What the owner is asked to rule

1. The §1.5 log entry as drafted — including **corrections A, B and C** to the review's figures?
2. The confidence corollary recorded as **"coarsely quantized / data-availability-driven"** rather
   than "week-level", with the **0.72 claim explicitly recorded as unverified**?
3. Item 2's fix — repo-relative `meta.source` + regenerate the committed artifact?
4. Item 3's placement — **verify-phase-3 check + unit pin**, not a runtime `assert` in the frozen
   registry?
5. Confirmation that all three land in **one PR**, then reviewer → your merge → the re-run.

**Calendar:** Aug 8 holds. Item 1 is one log entry, items 2–3 are mechanical, and the measurement is
already done. Item 2 touches a verify gate, so the full six-target sweep runs regardless.
