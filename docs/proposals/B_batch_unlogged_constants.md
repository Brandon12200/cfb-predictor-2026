# Proposal — B1–B10: unlogged calibration constants (reverse-audit ledger, consolidated batch)

> **Lifecycle.** Working document, not an authoritative record. It carries the consolidated B-batch
> to the owner in reviewable form. **Once ratified, its content moves to `docs/CALIBRATION_LOG.md`
> and this file is deleted at the next phase/session boundary**, together with
> `A4_prediction_type_rescale.md` and `ledger_pr_summary.md`. Not authoritative over `docs/SPEC.md`.
>
> **Status:** PROPOSED — awaiting owner ruling (§7).
> **Ledger:** B1–B10, `docs/CALIBRATION_LOG.md` "Phase-3 reverse-audit" (2026-07-09).
> **Gates the tag.** Most items touch freeze-bound `factors/`/`engine/`.
> **`data_quality` weight 0.4 (B1) is already RATIFIED** (owner, 2026-07-04) and is not re-opened.

---

## 1. Method, and the one caveat that governs every reading below

Per the per-number doctrine: **a block is never ratified by one entry that names it.** Every numeric
member below gets its own magnitude argument, an explicit *"inherits the set's reasoning"* note, or a
disposition of **dead / dormant** — because ratifying a value that nothing reads is worse than
silence: it implies a claim the code does not make.

Measured on the same two vehicles as A4. Vehicle A: the 10 wk1 games with real prediction-time lines.
Vehicle B: **all 734 real 2026 FBS-vs-FBS season games**, each driven at its own week.

> ### ⚠ The vehicle is a DORMANT-STATE LOWER BOUND — this is the single most important caveat
>
> Vehicle B runs against the **preseason** snapshot: no completed games, so no records, no momentum
> history, no in-season advanced stats, and no line-movement series. Factors keyed on those inputs
> return 0.0 **by construction of the vehicle**, not because they are broken and **not** because they
> will stay quiet in October. A "fires 0/734" reading below therefore means *"cannot be exercised by
> this vehicle"*, **not** *"is dead code"* — except where explicitly labelled **DEAD**, which is a
> static-analysis result independent of any vehicle.
>
> This is the same distinction A4 turned on, and it must not be collapsed here either.

## 2. Liveness map — the organizing result

Only **4 of 15** registered factors can fire in the measured state, and all four are physical.

| Class | Meaning | Factors | Governs |
|---|---|---|---|
| **LIVE** | fires in the measured vehicle | `ByeAdvantage` 191/734 · `ConsecutiveRoad` 185/734 · `TravelBurden` 152/734 · `ShortWeek` 79/734 | **B5** |
| **VEHICLE-DORMANT** | needs in-season inputs the preseason snapshot lacks; expected to fire in-season | `DesperationIndex` · `PointDifferentialTrends` · `CloseGamePerformance` · `StyleMismatch` | **B3, B7, B8** |
| **INPUT-DORMANT** | needs data that is missing/absent, not merely not-yet-accrued | `ExperienceDifferential` · `Altitude` · `Sandwich` · `PressureSituation` · `RevengeGame` | **B2, B6** |
| **DESIGN-DORMANT** | deliberately gated off until data lands (MSF.3) | `MarketSentiment` (value 1.0 on 744/744, never activates) | **B9** |
| **STRUCTURALLY DORMANT** | cannot fire at any threshold | `HeadToHeadRecord` (A1: placeholder input) | **B2, B10** |

**Two ratified 3b.1 coefficients govern factors that fire 0/734 even in-season-shaped conditions** —
`altitude_value` 1.2 (`Altitude` 0/734) and `sandwich_value` 1.0 (`Sandwich` 0/734). Both were
ratified in 3b.1 and are **not** re-opened here, but the observation belongs on the record: they may
go the whole season unexercised. Flagged for the owner in §7.

## 3. B1 — `_calculate_confidence_score` (`engine/prediction_engine.py:524-573`)

The formula behind the `confidence_score` that 3c.5's NO_BET floor and 3c.6's A/B/C tiers both key
off. **The most load-bearing item in the batch**: if this formula is wrong, the ratified floors and
tiers inherit the error.

### 3.1 Component weights — a partition of one unit of confidence

| Component | Weight | Status | Measured mean contribution (Vehicle B) | Argument |
|---|---|---|---|---|
| `data_quality` | **0.4** | **RATIFIED** (2026-07-04) | 0.1679 of 0.40 | Already on the record; not re-opened |
| factor success rate | **0.3** | PROPOSED | 0.2780 of 0.30 | Second-largest: *how much of the model actually ran* is the next-best proxy for trustworthiness after input quality |
| edge size | **0.2** | PROPOSED | **0.0019 of 0.20** | See §3.2 — the defect |
| betting data present | **0.1** | PROPOSED | 0.1000 of 0.10 | Binary presence gate; smallest share because it is necessary-but-not-sufficient (a line existing says nothing about its quality) |

The four sum to **exactly 1.0** — they partition a unit budget, which is the structural argument that
holds the set together. Each share above is its own claim about how much that input should move
confidence; ratifying the set means ratifying that ordering (quality > coverage > edge > presence).

### 3.2 ⚠ The edge-scaling divisor `/5.0` — a measured defect, not a value to ratify

`edge_confidence = min(edge_size / 5.0, 1.0)`. The divisor assumes edges reaching ~5 points.

**Measured:** the season's maximum edge is **0.2338**, so `edge_size/5.0` peaks at **0.0468** — the
edge component can contribute **at most 0.00935 of its nominal 0.20 budget**, i.e. it uses **4.68% of
its own range** at the season maximum and **2.81%** on the wk1 slate. Mean contribution: **0.0019**.

**The edge component is effectively absent from the confidence score.** This is the same
order-of-magnitude mis-scaling 3c.5 found in the NO_BET floors and A4 found in the `prediction_type`
ladder — a pre-Bug-#7 constant sized for a world where the phantom +1.0 made every edge clear ~1.0.
Third occurrence of one root cause.

**This is a decision, not a ratification.** Options:
- **(a) Ratify as-found and log the consequence** — confidence becomes a *data-availability* score
  (quality + coverage + presence = 0.8 of the budget) with a negligible edge term. Honest, zero
  freeze-bound change, and consistent with 3c.5's ratified "erring quiet is deliberate" posture.
  **Recommended.**
- **(b) Rescale the divisor** to the measured range (e.g. `/0.25`). This would make the edge term
  live — but it **changes `confidence_score` on every game**, which moves the 3c.5 NO_BET confidence
  floor and the 3c.6 A/B/C tier boundaries that were ratified *against the current formula*. That is
  a re-opening of two ratified batches days before the tag.

I recommend **(a)** for the same reason A4 landed where it did: the alternative re-opens ratified
calibration on a dormant-state measurement, and the post-freeze path (attribution over
`predicted_edge`, now at 4 dp) already captures edge magnitude without touching frozen code.

### 3.3 Variance adjustments `+0.25 / +0.1 / −0.1 / −0.2 / −0.3`

Additive, applied after the weighted sum, keyed on `variance_level`.

| Level | Adj | Argument |
|---|---|---|
| `consensus` | **+0.25** | Factors agreeing is the strongest available corroboration; sized just under the 0.30 success-rate budget so agreement can never outweigh *whether the model ran* |
| `mild` | **+0.1** | A quarter-strength version of the same signal |
| `moderate` | **−0.1** | Symmetric with `mild` — mild disagreement costs what mild agreement earns |
| `strong` | **−0.2** | Twice the moderate penalty |
| `extreme` | **−0.3** | Largest single adjustment; but note **`extreme` already forces NO_BET independently** (3c.5 floor 3), so this penalty only affects the *tier label* on an already-declined game |

**Scale-check:** the band is ±0.3 on a [0,1] score whose NO_BET floor is 0.50 and A-tier boundary
0.65. A `consensus` bonus of +0.25 can therefore move a game from below the floor to A-tier on its
own — the single most powerful term in the formula. **Measured mitigation:** `consensus` occurred on
**1 of 734** games, and 711/734 were `insufficient_data` (no adjustment at all). The term is
theoretically dominant and empirically near-inert in the measured state.

### 3.4 Clamp `[0.15, 0.95]`

Never lets a prediction claim certainty or total ignorance. **Measured: the clamp never binds** —
Vehicle B range `[0.1635, 0.7862]`, Vehicle A `[0.6332, 0.6388]`, zero games at either bound. It is a
guard rail, not an active shaper. Ratify as a bound, evidence-class `reasoned`.

## 4. B2–B7 — per-number dispositions

### B2 — registry hierarchy overrides (`factors/factor_registry.py:~167-190`)

| Factor | threshold | max_impact | Factor's own `_max_output` | Disposition |
|---|---|---|---|---|
| `HeadToHeadRecord` | 1.0 | 5.0 | **1.0** | **Log as structurally dormant** — A1; threshold == output max *and* placeholder input |
| `ExperienceDifferential` | 1.0 | 3.0 | **2.0** | Threshold = 50% of real max: sound. **But `max_impact` 3.0 > `_max_output` 2.0** — see below |
| `PointDifferentialTrends` | 0.75 | 3.0 | — | 0.75 on a ±3 nominal range; inherits the secondary-factor set's reasoning |
| `CloseGamePerformance` | 0.5 | 2.0 | — | Lowest threshold of the set, matching the weakest signal; inherits the set's reasoning |

**⚠ New finding — `max_impact` exceeds `_max_output` on two entries.** `ExperienceDifferential` is
configured `max_impact = 3.0` while `validate_output` clamps to `±2.0`, so the declared cap is
**unreachable**. Same shape as the A1 threshold defect (a bound that cannot be attained), one level
up. It changes no output — the clamp binds first — but it means the registry's declared cap is
fiction. **Recommend: log the discrepancy, do not "fix" it pre-tag** (harmonising the numbers would
edit freeze-bound config to no observable effect — the A4 lesson).

### B3 — `DesperationIndex` internals (`factors/situational_context.py:94-155`)

**Vehicle-dormant (0/734) — will fire in-season once records exist.**

| Constant | Value | Argument |
|---|---|---|
| blend: bowl / playoff / late-season | **0.4 / 0.3 / 0.3** | Bowl eligibility is the most broadly applicable motivation (applies to every team every year); playoff and late-season pressure apply to narrower populations, weighted equally |
| base neutral score | 0.5 | Midpoint of the [0,1] pre-scaling band |
| bowl branch values | eliminated **−0.3**, must-win-out **0.6**, need-one **0.4**, comfortable **0.2**, eligible **0.0** | Monotone in urgency; the only negative is elimination (motivation *removed*) |
| playoff branch | undefeated wk≥10 **0.5**, one-loss wk≥10 **0.3**, else **0.1**, out **0.0** | Monotone; gated on `week ≥ 10` so it cannot fire early |
| late-season | wk≥13 **0.4**, wk≥11 **0.3**, wk≥9 **0.2**, else **0.0** | Monotone step ladder in week |
| differential scale | **×4.0** | Maps a ±0.5 differential onto the ±2.0 output range — a definitional mapping, not a free parameter |
| `bowl_eligibility_threshold` | 6 | **Rule of the sport**, not calibration (6 wins = bowl eligible) |
| `playoff_contender_threshold` | 1 | Reasoned: >1 loss ≈ out of contention |
| **`conference_championship_weeks`** | **[13, 14]** | **DEAD — 0 references** (verified). Log dead, do not ratify |
| **`desperation_multipliers`** | **2.0 / 1.5 / 1.0 / 0.3** | **DEAD — 0 references** (verified). Log dead, do not ratify |

**Scale-check:** ±2.0 output at weight 0.13 ⇒ ≤0.26 pts contribution ≈ **10% of HFA**. In band.

### B5 — physical shared cutoffs (`factors/scheduling_fatigue.py`) — **the only LIVE set**

| Constant | Value | Argument |
|---|---|---|
| `activation_threshold` | **0.4** on all six | Uniform by design: these are *structural facts* (a bye happened or it didn't), so a single threshold expresses "half of the smallest meaningful coefficient (0.5 consecutive-road) must be present". Measured: fires on 11–26% of in-season games per factor — selective, not chatty |
| strong-confidence cutoff | **`max_impact × 0.6`** | A signal at ≥60% of its cap is `VERY_HIGH` confidence rather than `HIGH`. Relative (not absolute), so it scales with each factor's cap automatically |
| per-factor `cap` | **1.5** on all six | = the ratified 3b.1 `travel_cap`; 0.6× HFA. Inherits 3b.1's reasoning |
| weights | 0.16 / 0.14 / 0.16 / 0.12 / 0.10 / 0.12 | **Already ratified in 3b.2**; listed for completeness, not re-opened |

**Scale-check:** cap 1.5 = **60% of HFA**, matching the ratified `travel_cap`. In band.

### B6 — `ExperienceDifferential` internals (`factors/coaching_edge.py:36-39,99`)

**Input-dormant (0/734)** — the snapshot's coaching data does not populate the fields it reads.

| Constant | Value | Argument |
|---|---|---|
| `max_experience_edge` | 15 | Years beyond which coaching experience stops differentiating — diminishing-returns knee |
| `tenure_weight` | 0.3 | Tenure *at the current school* is worth less than total experience (0.7 implied) |
| `rookie_penalty` | 0.5 | Extra penalty for a first-year head coach |
| scale | ×2.0 | Maps a ±1.0 raw differential onto the ±2.0 range — definitional |
| three coaching factors' weights | 0.06 each | The 12% coaching category total is logged in 3b.2; the equal three-way split is the unlogged part |

**Scale-check:** ±2.0 at weight 0.06 ⇒ ≤0.12 pts ≈ **5% of HFA**. In band.

### B7 — momentum internals (`factors/momentum_factors.py`)

**Vehicle-dormant (0/734)** — needs completed-game results.

All of B7's constants are **live-and-referenced** (verified statically — an initial flat scan
suggested several were dead; that was a false positive from nested `config` dicts, and the nested
keys are genuinely consumed).

| Constant | Value | Argument |
|---|---|---|
| `trend_weights` | 0.4 / 0.3 / 0.2 / 0.1 | Linear decay over the 4-game window: the last game counts 4× the fourth-last. **⚠ Consumed POSITIONALLY** — `momentum_factors.py:144` does `list(config['trend_weights'].values())[:n]`, so the key names are decorative and **reordering the dict would silently re-weight the factor**. Worth logging as a fragility, not a value change |
| `recent_games_window` | 4 | Sample window; matches the four trend weights |
| `improvement_thresholds` | +10 / +5 / −5 | Point-differential swings marking significant / moderate improvement and decline — one-and-a-half to two possessions |
| `consistency_bonus` | 0.3 | Reward for low-variance performance |
| `close_game_threshold` | **7** | **Sport convention** — one possession. Structural, not calibration |
| `clutch_weights` | win-close 1.0 / lose-close (neg) / blowout-win 0.3 / blowout-loss (neg) | Winning a close game is the full clutch signal; a blowout carries 30% of it (less informative about late-game execution). Consumed **by name**, so not positionally fragile |
| `recent_games_window` (close) | 6 | Larger window than trends — close games are rarer, so more history is needed for a usable sample |
| `experience_multiplier` | 1.2 | 20% amplification |
| `min_close_games` | **2** | Minimum-sample gate, not a magnitude — the smallest non-degenerate sample |

**Recommend: ratify the sport-convention and sample-gate constants as `structural`** (7 points = one
possession; 2 games = the smallest non-degenerate sample) **and the magnitude constants as
`reasoned`, inheriting the momentum category's 7% budget** — the category total is already ratified
in 3b.2 and bounds every member: ±2.0 at 0.036 weight ⇒ ≤0.07 pts ≈ **3% of HFA**. Plus a logged note
on the positional consumption of `trend_weights`.

## 5. B8 / B9 / B10 — two dead constants, one dormant set, one missing note

### B8 — `StyleMismatch` weighting (`factors/style_mismatch.py:44-52,85-91`)

| Constant | Value | Status |
|---|---|---|
| `success_rate_weight` | 2.0 | used — highest, most predictive metric |
| `explosiveness_weight` | 1.5 | used |
| `pace_mismatch_weight` | 1.2 | **referenced but inert** — pace component is dormant per 3d.2 |
| `havoc_weight` | 0.8 | used — lowest, noisiest metric |
| `min_success_diff` | 0.05 | used — 5% gate |
| **`redzone_weight`** | **1.0** | **DEAD — 0 references** (ledger suspicion confirmed) |
| **`pace_advantage_slower`** | **0.3** | **DEAD — 0 references** (new finding, not in the ledger) |
| divisor | **`/6.0`** | **⚠ inconsistent with its own comment** |

**⚠ The `/6.0` divisor.** Its comment says "normalize by total weights", but the weights actually
referenced in the sum are `2.0 + 1.5 + 1.2 + 1.0 (a literal, not a config key) + 0.8 = **6.5**`. With
pace dormant the *live* sum is **5.3**. So the divisor matches neither its stated intent (6.5) nor
the live total (5.3); it under-normalises by ~8% against intent.

**Recommend: log as-found, do NOT fix.** The output is clamped to the ratified ±1.5 range (3d.3), the
factor is vehicle-dormant, and changing the divisor is a magnitude change to a frozen factor. Logging
it means 2027 inherits a known, quantified discrepancy instead of rediscovering it. **`redzone_weight`
and `pace_advantage_slower` should be logged DEAD, not ratified.**

### B9 — `MarketSentiment` internals (`factors/market_sentiment.py:48-55`)

**Design-dormant, measured: value 1.0 on 744/744 games, never activates** — exactly MSF.3's
specification. The thresholds (`reverse_movement` 0.7, `line_move` 0.5, `steam_move` 1.0,
`steam_time_window` 6h, `sharp_indicator_weight` 0.4, `public_fade_weight` 0.3, `line_freeze_signal`
0.2) are **frozen but unreachable until slice-1.5 line-movement data lands mid-season**.

**This is the batch's sharpest risk.** These constants activate *mid-season, after the freeze*, with
**zero** measured evidence behind them — the first game they affect will be the first time they run.
The outer `[0.85, 1.15]` range is ratified (MSF.3) and bounds the damage to ±15% of the edge.

**Recommend: ratify as `reasoned`, explicitly labelled "unexercised at ratification",** and add a
standing note that the first week they fire is a **watch item** for the in-season reports, not a
silent activation. Alternative worth the owner's consideration: keep the factor dormant for all of
2026 by leaving the data unwired, converting an unmeasured mid-season activation into a 2027 decision
with a season of evidence.

### B10 — SPEC §16.7 exception + dead H2H config keys

1. **§16.7's coaching multi-season lookback exception is not recorded in CALIBRATION_LOG.** §16.7
   requires the note to live here. **Add it** — the coaching factors legitimately read prior-season
   coaching history, which is an explicit, owner-resolved carve-out from the Data Recency Principle
   (coach identity/tenure is not team-quality data).
2. **`HeadToHeadRecord.config` dead keys confirmed** (carried from A1, static check): 
   `recent_game_weight` 1.5 → **0 references**; `max_lookback_years` 10 → **0 references**; only
   `min_games_for_significance` is read. **Log DEAD, do not ratify.**

## 6. Cross-cutting findings

1. **One root cause, three sites.** The pre-Bug-#7 point-scale assumption survives in the NO_BET
   floors (found by 3c.5), the `prediction_type` ladder (A4), and now B1's `/5.0` edge divisor. All
   three are being *logged rather than rescaled*, for the same reason: rescaling on a dormant-state
   measurement re-opens ratified calibration days before the tag.
2. **Six dead constants across the batch**, all verified statically: `redzone_weight`,
   `pace_advantage_slower` (B8), `recent_game_weight`, `max_lookback_years` (B10),
   `conference_championship_weeks`, `desperation_multipliers` (B3). Ratifying a dead value asserts a
   claim the code does not make; all six should be logged **DEAD**, not ratified.
   *(Method note: an initial flat scan also flagged B7's `trend_weights`/`clutch_weights` members as
   dead. That was a false positive — they are nested dicts consumed via their parent key. Verified
   before reporting; nested config needs the parent-key check, not a flat one.)*
3. **Two "unreachable bound" defects** — A1's `threshold == _max_output`, and B2's
   `max_impact > _max_output`. Same family; neither changes output; both worth logging so the pattern
   is recognisable in 2027.
4. **The B-batch is overwhelmingly dormant at ratification.** Only B5 governs a factor that fires in
   the measured state. That is not a reason to wave the rest through — it is a reason to label each
   entry's *reachability* precisely, so 2027 knows which constants have a season of evidence behind
   them and which have none.

## 7. What the owner is asked to rule

1. **B1 `/5.0` edge divisor** — (a) ratify as-found and log the consequence [**recommended**], or
   (b) rescale, accepting that it re-opens the 3c.5 floor and 3c.6 tiers.
2. **B1 remaining component weights** (0.3 / 0.2 / 0.1), variance adjustments, clamp — ratify as
   proposed in §3?
3. **B2–B7** — ratify per-number as proposed, including the "inherits the set's reasoning" notes
   where marked?
4. **B2's `max_impact > _max_output`** — log-only [**recommended**], or harmonise pre-tag?
5. **B8** — log `/6.0` as-found with the quantified discrepancy [**recommended**]; log
   `redzone_weight` + `pace_advantage_slower` DEAD.
6. **B9 `MarketSentiment`** — ratify as `reasoned`/unexercised with a first-fire watch item
   [**recommended**], or keep dormant for all of 2026 and defer to 2027?
7. **B10** — add the §16.7 exception note; log the two H2H keys DEAD.
8. **B7's positionally-consumed `trend_weights`** — log the fragility note as proposed?
9. **Two ratified 3b.1 coefficients may go unexercised all season** (`altitude_value` 1.2,
   `sandwich_value` 1.0 — both 0/734). Accept and note, or investigate why `Altitude`/`Sandwich`
   never fire before the tag?

Nothing in this proposal has been implemented. No `factors/`, `engine/`, or config file has been
modified.
