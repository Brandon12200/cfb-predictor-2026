# Calibration Log

Every calibration constant in the model, with its evidence and ratification status.
**Calibration is owner-only (SPEC §14.3):** the agent *proposes* a value with evidence;
it is not ratified until the owner approves the entry. Ratified constants are frozen at
`v2026-frozen`. This log is the audit trail for how each number was chosen — no borrowed
magic numbers.

Status legend: **PROPOSED** (awaiting owner approval) · **RATIFIED** (owner-approved) ·
**FROZEN** (locked at the tag).

---

## Phase 2 — Power ratings (`engine/power_ratings.py`, `engine/matchup_pricer.py`)

### D9 — Elo constants  — **RATIFIED** (owner, 2026-07-03)
Set empirically by the **dispersion acceptance test** (`tests/test_power_ratings.py::
test_dispersion_recovers_realistic_point_spread`, a first-class `make verify-phase-2` check),
NOT borrowed from FiveThirtyEight's NFL Elo (that regime starts from carried-over priors;
ours is flat-prior, current-season-only, ~12 games — a naive K=20 compresses ratings so the
model-vs-market diagnostic becomes noise).

| Constant | Proposed | Rationale / evidence |
|---|---|---|
| `k_early` | 64 | Decaying K, high early to differentiate a flat-prior field fast. |
| `k_late` | 22 | **Asymptote** of the decaying K (reached as n→∞), not the mid-season value; shares the games-played curve with D11. |
| `k_decay_games` | 6 | e-folding scale of the K decay (avg games played of the two teams). |
| `mov_c` / `mov_b` | 2.2 / 0.0018 | MOV dampener `ln(|m|+1)·C/(b·|ΔR|+C)`: log damps blowouts, ΔR term corrects autocorrelation. |
| `hfa_elo` | 50 (= **2.5 pts**) | Matches the measured 2025 P4 home edge; below the eroding historical CFB HFA. |
| `elo_per_point` | 20 | Tuned so the dispersion test **recovers** the injected 30-pt true spread (ratio ≈ 1.0). |

**Decaying-K schedule:** `K(n) = 22 + (64−22)·exp(−n/6)` → K = **64** (game 0), **37.5** (game 6),
**27.7** (game 12); `k_late=22` is the asymptote, so a full-season team settles near K≈28, not 22.

**Data-Recency note (`hfa_elo`):** the 2.5-pt home edge is measured from the 2025 archive, and is
**compliant** for the same reason as σ (D12) — home-field advantage is a sport-level structural
constant (the magnitude of playing at home), not team-quality data for any current team.

**Dispersion evidence:** synthetic double round-robin, 7 teams, true strengths −15…+15 (incl.
strong-vs-strong peer games). Recovered top-vs-bottom = **30.8 pts** neutral / 33.3 home (band
24–40); rank-fidelity **r = 0.998** (separation is real signal developed in one season, not a
rescaled artifact). Naive K=20 gave ~19.7 (compressed). The two-part test (recovery + fidelity)
prevents masking a too-low K by inflating `elo_per_point`.

### D11 — `rating_uncertainty` + early-season cap  — **RATIFIED** (owner, 2026-07-03)
| Constant | Proposed | Rationale |
|---|---|---|
| `uncertainty_floor` | 0.2 | Floor of the per-team uncertainty once settled. |
| `uncertainty_games_full` | 5 | Games at which uncertainty decays from 1.0 to the floor. |
| `rp_prior_uncertainty_penalty` | 1.15 | Any non-SP+ prior (returning-production OR flat) is a weaker seed than SP+ → more uncertain. |
| `rating_signal_floor` | 0.4 | Rating differential scaled by `floor+(1−floor)·(1−u)`; floor (not 0) so a strong SP+ prior still shows through preseason. Home-field/schedule are NOT capped (structural). |
| `prior_rp_max_elo` / `rp_reference` / `rp_span` | 40 / 0.60 / 0.35 | Bounded returning-production continuity nudge (±~2 pts) around a league-typical `percentPPA` ≈ 0.60. NOT a talent ranking. |

### D12 — spread → win-probability σ  — **RATIFIED** (owner, 2026-07-03)
`P(win)=Φ(margin/σ)`, **`margin_sigma` = 16.0 points**. Measured from CFB, not the NFL 13.5:
the 2025 P4 archive **market-residual SD is 14.1** (`actual_margin + vegas_spread`, mean ≈ 0.8
over N=300), lifted for our noisier-than-market model + the wider full-slate margins.
**Data-Recency note:** using 2025 margins for σ is compliant — σ is a sport-level statistical
constant (dispersion of outcomes), not team-quality data for a current team.
**Sensitivity:** σ=14 vs σ=16 shifts a team's **projected win total by ≈0.2 wins** over a 12-game
season (max per-game swing ~3.2 pct-pts near margin ≈ σ; near-.500 teams ≈0) — low leverage, so
the exact σ within 14–16 barely moves the (experimental, non-betting) projections.

### Schedule-adjustment coefficients (`ScheduleAdjustmentConfig`)  — **RATIFIED** (owner, 2026-07-03)
Conservative Phase-2 baseline over the most robust physical signals; **Phase 3's calibrated
factor system recalibrates and supersedes** these. Kept small and bounded so a mis-set value
can't dominate a model spread.

| Constant | Proposed | Signal |
|---|---|---|
| `bye_value` | 1.0 | Prep advantage off a bye (opponent didn't). |
| `short_week_penalty` | 1.0 | < 7 days' rest and opponent isn't. |
| `tz_per_zone` / `travel_cap` | 0.6 / 2.0 | Per net time-zone the away team crosses more (capped). |
| `altitude_threshold_ft` / `altitude_value` | 4000 / 1.2 | Home acclimated at a high-elevation home stadium (non-neutral only). |

---

## Phase 3b — Physical factor layer + reweight (L1)  — **RATIFIED** (owner, 2026-07-03)

Consolidated batch. Evidence class **`reasoned`** throughout: after the D17 regrade the 2025 model
**lost** (46.6% ATS), so L1 "physical was strongest" is **unverified** — nothing here cites 2025
performance as authority; magnitudes are argued from rest/travel effects and the ratified ~2.5-pt
home-field scale. Each coefficient is measured for real, per-sub-signal, in 2026 (Phase 4), which
is what makes the separate-factor granularity worth its cost.

### 3b.1 — Physical coefficients (`factors/physical_coefficients.py`, D15 single source)

The pricer's model-spread schedule adjustment and the six contrarian physical factors consume
**these same values** — one source, both lanes freeze together.

| Coefficient | Value | = % of 2.5 HFA | Status |
|---|---|---|---|
| `bye_value` | 1.0 | 40% | 2a baseline → **ratified 2026 value** |
| `short_week_penalty` | 1.0 | 40% | 2a baseline → **ratified 2026 value** |
| `tz_per_zone` | 0.6 | 24%/zone | 2a baseline → **ratified 2026 value** |
| `travel_cap` | **1.5** (was 2.0) | **60%** (was 80%) | 2a baseline → **ratified, trimmed** |
| `altitude_threshold_ft` / `altitude_value` | 4000 / 1.2 | 48% | 2a baseline → **ratified 2026 value** |
| `consecutive_road_value` / `_cap` | 0.5 / 1.5 | 20%/game, 60% cap | **NEW** |
| `sandwich_value` | 1.0 | 40% | **NEW** |

**"Carried from 2a" is not "waved through."** The four 2a values were ratified once as a
conservative baseline *explicitly destined to be superseded*; this is the ratification where they
stop being placeholders and become the numbers we bet on, so each got the same scale-judgment as
the two new ones. All sit under the ⅓–½-of-HFA guideline. **The one change: `travel_cap` 2.0 → 1.5**
(0.8 → 0.6 HFA). Reasoning (owner): a full cross-country trip is already partially expressed through
altitude and short-week when they co-occur, and a cap nearly the size of home field lets one
*reasoned, unmeasured* signal be almost the whole structural story of a game — first season of a
fresh hypothesis, caps err humble. If 2026 attribution shows extreme travel is underpriced, 2027
raises it **with evidence**. The `consecutive_road` cap (0.6 HFA) survived as-is: it takes a 4th
straight road game to reach and 0.5/game is modest.

**Sandwich scope (D18, ratified):** `sandwich` is a physical *factor* (contrarian) but is
**excluded from the model spread** — a letdown/look-ahead spot is a market-mispricing hypothesis,
not a team-quality fact. `consecutive_road` likewise stays contrarian-only. The pricer consumes only
the fatigue/location subset (bye, short-week, travel/tz, altitude).

### 3b.2 — Reweight toward physical (L1): factor weights

Additive-weight shares (normalized), current → ratified:

| Category | Before | After |
|---|---|---|
| **physical** (6 factors) | 23% | **52%** |
| situational (Desperation, Revenge) | — | 13% |
| coaching (3) | 10% | 12% |
| matchup (StyleMismatch) | — | 10% |
| momentum (2) | 4% | 7% |
| market (MarketSentiment) | 35%† | 6%† |

† **Nominal weight share only — inert at runtime** (MODIFIER weight is ignored; see the MarketSentiment
note below). MarketSentiment's real effect is a ≈+1 additive phantom independent of its weight, addressed
in the standalone follow-up. So the *effective* additive budget is over the **14 non-modifier factors**;
`market` is listed here for continuity with the (mistaken) pre-fix accounting.

**Post-D19 (Bug #7 fix) renormalization — the current-on-`main` numbers:** once `MarketSentiment` is
excluded from additive accounting (`is_multiplicative=True`), the shares renormalize over the 14
additive factors: **physical 56%**, situational 14%, coaching 12%, matchup 10%, momentum 7%; max single
factor ~11% (Bye/Travel tied); physical:situational still 4:1 — all inside the tripwire. The **52%**
above is the correct at-3b-time figure (computed over 15, with MarketSentiment then wrongly additive);
`verify-phase-3` measures the live **56%**.

Biggest single factor among the real additive factors: **ByeAdvantage/TravelBurden ~10%** (tied, 0.16
each); physical:situational **4 : 1**.

**Why physical is set this high — the honest framing (owner):** this is *not* backing a proven
winner. Physical-dominant is **maximum allocation to the best-reasoned but unverified hypothesis**.
It is defensible because the categories it takes weight from carry **measured negative evidence**:
situational is noisy (L2) and the entire contrarian output added nothing over consensus (D17). So
the reweight is **demotion of demonstrated non-signal**, not promotion on 2025 authority — and the
weight has to live somewhere. That is the sentence 2027-us will want when judging whether 52% was
right.

**MarketSentiment (the intended `35% → 6%` change is a RUNTIME NO-OP — corrected below):** 1b deleted
this factor's fabricated line-movement sim and its hashed public-betting engine; what remains runs on
honest cross-book statistics, with movement legitimately missing until slice 1.5. A factor whose main
historical inputs were fabrications should not be a third of the model — hence the intent to demote it.
**But the weight change has no runtime effect,** and honesty requires saying so here rather than after
merge:
- `MarketSentimentCalculator` is `factor_type=MODIFIER`, and `get_dynamic_weight` returns a **flat
  1.0 for MODIFIER factors, ignoring `self.weight`** (`base_calculator.py:221-223`). Verified: setting
  its weight to 0.10 vs 0.9 yields **identical** output. So the ratified 1.0 → 0.10 reweight changed
  nothing at runtime; MODIFIER weights are inert **by design**, and the additive-budget shares above
  that include `market` are nominal for this one factor.
- Worse, it never sets `is_multiplicative = True`, so despite its type it is summed **additively**;
  and its `calculate()` returns a multiplier in [0.5, 1.5] **centered on 1.0**, so it injects a
  **roughly-constant ≈ +1.0 additive shove into `total_adjustment` on essentially every game**
  (measured mean +0.99, stdev 0.07 across the 2025 archive). This is a **pre-existing bug (on `main`,
  and in the 2025-era model)**, not introduced by 3b.
- **This is the mechanical root cause of the D17 artifact** (see the D17 addendum): the constant +1
  is exactly the 57.0%-vs-54.4% gap in the D17 diagnostic table, and it manufactured the entire
  small-edge distribution L4 rested on.

The real fix (`is_multiplicative = True` + use the multiplier directly + apply it to `total_adjustment`
only + tighten the range) is a **behavior change on every prediction** and is therefore a **standalone
ratified follow-up PR** with its own measured before/after evidence — not silently flipped here.

### 3b.3 — Category taxonomy (enables the budget gate)

`StyleMismatch` and `MarketSentiment` were mis-labeled `situational_context` in the code. They are
re-categorized `matchup` and `market` respectively so the physical:situational ratio measures what
it claims (physical vs the *motivational* factors). No weight or behavior change — grouping only.

### 3b.4 — Factor-contribution-budget bounds (governance tripwire)

Ratified: **no single additive factor > 15%** of normalized weight; **physical:situational ≥ 2 : 1**.
The proposal clears both comfortably (10% max, 4:1) — these are deliberately a **tripwire for
dramatic drift, not a corset**. Enforced in `make verify-phase-3`.
*Observation for 3c (not a 3b blocker):* `StyleMismatch` has a wide ±4.0 output range, so its
*potential* contribution (weight × range) is larger than its 10% weight share suggests — revisit its
range when situational thresholds are calibrated in 3c.

### 3b.5 — Base-calculator activation semantics (behavior-changing — logged per our standard)

`factors/base_calculator.py::safe_calculate`: a factor whose thresholded value is **0.0 now counts
as NOT activated** (previously a raw 0.0 slipped through as "activated"). This is a correctness fix
— a zero is not a signal — but it is **behavior-changing**: it lowers `primary_signals` counts and
raises `avg_confidence` for predictions where factors return exactly 0 (common now that physical
factors return 0 when their signal is absent), which shifts confidence scores **ahead of 3c's tier
calibration**. Logged here as its own entry because our standard is that behavior-changing changes
get a CALIBRATION_LOG record, not just a commit message. Deterministic; suite green.

### 3b.6 — Retirements

- **`SchedulingFatigueCalculator`** (the pre-1c crude fatigue heuristic: road-count / date-diff /
  "emotional game") — replaced wholesale by the six schedule-intel physical factors.
- **`LookaheadSandwichCalculator`** (situational team-data "distraction" + threshold config) —
  superseded by the physical `Sandwich` factor (schedule-intel: a top-25 SP+ opponent in an
  adjacent week — cleaner, attributable, audited free of hardcoded rivalry lists).

---

## MarketSentiment wiring fix (Bug #7) — **RATIFIED** (owner, 2026-07-04)

Standalone follow-up to the 3b review finding. Three coupled defects, all pre-existing (on `main`
and in the 2025-era model); this is the **mechanical root cause of the D17 artifact** (see the D17
addendum in DECISIONS). Fixed **before 3c** so NO_BET floors and confidence tiers calibrate against a
clean model, not a phantom.

### MSF.1 — Multiplicative wiring (behavior-change class)
`MarketSentimentCalculator.is_multiplicative` was never set, so a value **centered on 1.0** was summed
**additively** — injecting a ≈+1.0 constant into `total_adjustment` on essentially every game.
- `is_multiplicative = True`; the value is now used **directly as the multiplier**
  (`base_calculator.py`: multiplicative branch = `validated_value`, no re-centering).
- Applied to **`total_adjustment` only** — `contrarian = vegas + total_adjustment · m`
  (`prediction_engine.py`), never `(vegas + total_adjustment) · m`. Sentiment scales the model's
  **edge**, never the market's own number (D19). This also removes a second latent distortion that
  was dormant only because the flag was unset.
- **MODIFIER factors are weightless by design**: `get_dynamic_weight` returns 1.0 for MODIFIER, so
  `self.weight` is inert — a modifier is calibrated by its **range**, not a weight. It is now removed
  from additive accounting (the additive budget is over the **14 non-modifier factors**; physical
  share is **56%**, max single ~11%, physical:situational 4:1 — all still inside the tripwire).

### MSF.2 — Team-name hash removed (binding principle #4)
`_analyze_game_sentiment` added `hash_adjustment = (md5(home_away) % 1000 / 1000 − 0.5)·0.2` (±0.10)
plus spread-size/week heuristics — a signal **manufactured from nothing**, mislabeled "market
sentiment." Both are deleted. **This produced the stdev-0.066 wiggle** around the +1 constant seen in
the 2025 archive (the factors were otherwise silent). Locked out by a source-scan test.

### MSF.3 — Dormant until real data + tightened range (`reasoned`)
- **Dormant gate:** with line-movement history deferred to slice 1.5 (D6), the factor now returns a
  neutral **1.0 (no effect)** whenever no real movement data exists — the honest state of a factor
  whose inputs haven't arrived, matching the physical factors' missing-data behavior.
- **Range `[0.5, 1.5] → [0.85, 1.15]`** (evidence-class `reasoned`): the ratified **cap for when
  slice 1.5 brings real movement**. Halving/1.5×-ing an edge is huge leverage for a factor with a
  fabrication history; a first-season cap errs tight, widened in 2027 with attribution. Inactive now
  (the factor is dormant at 1.0), but ratified consciously so the leverage is on the record.

### Measured before/after (2026 wk1 dry-run slate, 10 games with lines)
| | contrarian − vegas (edge) |
|---|---|
| **before** (phantom) | 0.93 … 1.15 — **~1.0 on every game** |
| **after** (fixed) | 0.00 … 0.15 — **0 where no factor fires**, small where physical fires |

Mean contrarian-spread shift **+0.97, on 10/10 games**. The MarketSentiment multiplier is **1.0 on
every game** (correctly dormant). **Rerun contract:** the fix is *supposed* to break bit-identity vs
the old model — determinism *within* the corrected model holds (pure function of the snapshot); these
deltas are the evidence, not a regression.

---

## Phase 3c — Situational discipline (L2) + NO_BET (L4) + confidence tiers (L3)  — **RATIFIED** (owner, 2026-07-04)

*(3c.5 NO_BET floors was bounced once for a missing selectivity scale-check, then ratified as restated once the in-season selectivity was measured — see the entry.)*

Consolidated batch. Evidence class **`reasoned`** throughout unless a constant rests on
model-independent market data — after Bug #7 the 2025 archive's confidence→ATS and edge→ATS tables
are **inadmissible** (SPEC §3): no number below is fit to them. The monotonic-ATS%-by-tier property
is a **structural sanity check on the NEW model's dry-run output**, never a 2025-evidence gate. Every
magnitude is scale-checked against the ratified **~2.5-pt HFA** (D9).

**Batch scope note — the fabrication sweep grew (owner-ratified this session, D20).** Recon for the
L2 situational work found the Bug-#7 fabrication pattern — an **MD5-hash-of-team-name ± hardcoded team
lists**, emitted whenever real data is absent — was **one author's template in six places**:
`MarketSentiment` (Bug #7, already fixed / D19), `DesperationIndex`, `RevengeGame`, momentum
`PointDifferentialTrends` + `CloseGamePerformance`, and coaching `PressureSituation`. Calibrating 3c's
floors/tiers against a model still running three live hash engines would re-create the very
producer/consumer trap the wiring fix was sequenced to avoid, so the owner ratified neutralising **all**
of it in this batch (the widened tripwire is repo-wide by design). **Bugs #12–14** for the tally
(desperation-hash, momentum-hash ×2 grouped, pressure-hash).

### 3c.1 — Situational + momentum + coaching neutralization (behavior-change; binding #2/#4)

Not calibration constants — the removal of manufactured signal. Each factor keeps its honest
real-data path and returns **0.0 (honest-missing / dormant)** when the real inputs are absent, exactly
like the physical factors' missing-data behaviour and the D19 MarketSentiment fix.

| Factor | Removed (fabrication) | Honest path that survives | Preseason/dry-run state |
|---|---|---|---|
| `DesperationIndex` | `_simulate_desperation` (MD5 hash + `bubble_/playoff_/struggling_teams` lists); shared-context mutation | bowl-eligibility / playoff / late-season math from a **real W-L record** | dormant (no record) |
| `RevengeGame` | hardcoded 6-team `revenge_scenarios` rivalry table | (none sourced in 2026 core) | dormant → 0.0 |
| `PointDifferentialTrends` | `_simulate_differential_trend` (hash + `elite_/struggling_teams`) | real recent point-differential trend (≥3 completed games) | dormant (no games) |
| `CloseGamePerformance` | `_simulate_clutch_performance` (hash + `clutch_/anti_clutch_teams`) | real close-game history | dormant (no games) |
| `PressureSituation` | hash base-pressure, hardcoded `popular_teams`, **a home-field term that double-counted the pricer HFA** | — see 3c.2 (dormant) | dormant → 0.0 |
| `ExperienceDifferential` | `.get(key, 5)` **neutral-fill** default (masked missing coaches AND crashed on present-`None`) | real coach experience/tenure differential | dormant (no coaching data) |

**Measured before/after (2026 wk1 dry-run, 10 games with lines — D16 vehicle):**
- **BEFORE (`main`, post-Bug-#7):** fabricated momentum fired on real slates — `PointDifferentialTrends`
  activated (hash values, e.g. **+1.42**) in **3/10** games, `CloseGamePerformance` in **2/10**; and the
  dormant `MarketSentiment` multiplier (1.0) was **wrongly counted `activated` in 10/10** games (diluting
  `avg_confidence` on every prediction). All 10 typed `CONSENSUS_ALIGNMENT`.
- **AFTER (3c):** **zero** fabricated-factor activations; `MarketSentiment` correctly not-activated
  (0/10); edges collapse to **0.00–0.14** (unchanged in magnitude — the phantoms were small/offsetting
  on this slate, but they were real activations that would matter on other slates and contaminated the
  activation/confidence counts everywhere). All 10 typed `NO_BET` (see 3c.5).
- **Rerun contract:** like D19, the fix is *meant* to break bit-identity vs `main`; determinism within
  the corrected model holds (pure function of the snapshot).

### 3c.2 — `PressureSituation` disposition: DORMANT  (`reasoned` — owner rider 1)  — **RATIFIED** (owner, 2026-07-04)

The factor was almost entirely fabricated. Stripping the hash + `popular_teams` + the HFA-double-count
leaves only thin week-of-season and spread heuristics that **overlap `DesperationIndex`** (record-based
motivation) and the market factors, and whose home-field term **double-counted the pricer's ~2.5-pt
HFA**. The honest argument is that this residue does **not** earn an independent reasoned coefficient, so
rather than let it ride in as residue of the fix, the proposed disposition is **dormant** — the factor
returns 0.0 until a genuine coaching-pressure signal exists (revisit with 2026 attribution in 2027).
*(Alternative considered and rejected: a week/spread `reasoned` heuristic — rejected as overlapping +
double-counting.)*

### 3c.3 — Situational activation threshold: `DesperationIndex` 2.0 → **1.0**  (`reasoned`)  — **RATIFIED** (owner, 2026-07-04)

The old threshold **equalled the factor's max output (±2.0)**, so it could fire only at exact saturation
(never, in practice) — a latent bug, not selectivity. **1.0** (half of max range, = **0.4 × HFA** in
output space) lets a genuine desperation differential fire; the real L2 selectivity now comes from the
confirmation gate (3c.4), not an unreachable threshold. `RevengeGame`'s threshold (1.5) is **moot** — the
factor is dormant (0.0) until real prior-meeting data exists. Scale check: 1.0 output ≈ 0.4 × HFA — a
situational factor, gated, capped well below home field. **Applies in-season only** (dormant on the
dry-run), so it is not dry-run-measurable — a reasoned constant to be measured by Phase-4 attribution.

### 3c.4 — L2 confirming-signal gate  (`reasoned` / structural — SPEC §7.3, D15)  — **RATIFIED** (owner, 2026-07-04)

> **The rating's only path into the edge is as a veto on situational factors — it can subtract noise, never inject signal.** (Owner, verbatim: the eyes-open acknowledgment that this supersedes the 3a diagnostic-only property, and the boundary 2027 must not mistake for license.)


An activated **situational** factor contributes only if its direction is confirmed by **(a)** the
model-vs-market **BASE** gap (D15 — the base gap ONLY, never the total gap, so a factor is never
confirmed by a gap carrying its own schedule signal), or **(b)** at least one activated **physical**
factor of the same sign. Unconfirmed situational signals are withheld (de-activated before aggregation,
so `total_adjustment`, the signal counts, and `avg_confidence` all reflect the gate). "Agree in
direction" = same sign, in the factor convention where **positive favours home**. **Sign convention
(load-bearing):** the diagnostic `model_vs_market_gap` is `base_spread − vegas`, which is *negative* when
the model favours home (a more-negative spread = more home-favoured) — the OPPOSITE of the factor
convention. So the engine injects the gap for confirmation as its negation, **`vegas − base_spread`**
(`context['base_gap_favors_home']`), positive ⇒ the base read favours home. Comparing a raw
`base_spread − vegas` here would confirm situational factors *backwards* (a code-review NO-GO, fixed
before merge; end-to-end sign test in `tests/test_phase3c.py`). This is the primary L2 selectivity
mechanism; it raises the bar on solo motivational guesses (SPEC §7.3's "raise thresholds and/or require a
confirming factor"). **Architecture note:** the engine computes the base gap **before** the factors and
injects it on the context — so the base gap, previously diagnostic-only (3a), now legitimately feeds the
edge via this gate. Rerun determinism is unaffected (pure function of the snapshot). Pure, test-covered.

### 3c.5 — NO_BET floors (L4)  (`reasoned` — SPEC §7.4, §16.3)  — **RATIFIED as restated** (owner, 2026-07-04, after one bounce for the selectivity scale-check)

`NO_BET` is a first-class prediction type, emitted when **ANY** of three floors is breached — purely
threshold-driven, **no weekly volume target** (§16.3). NO_BET games keep their hypothetical pick
(`contrarian_spread` + edge) so they are still logged and graded ("what would have happened").

**The three floors (RATIFIED values):**

| # | Floor | Value / condition | Evidence class |
|---|---|---|---|
| 1 | **edge (dynamic gate)** | the **existing dynamic, confidence-aware `min_edge_threshold`** — **0.75** pts (≥2 primary signals & conf ≥0.7), **1.0** pts (≥1 primary or conf ≥0.6), else **1.5** pts. Retained **as-is**. NO_BET if `edge < min_edge_threshold`. | `reasoned` (inherited) |
| 2 | **confidence (static floor under the dynamic gate)** | `NO_BET_CONFIDENCE_FLOOR = 0.50` on the [0.15, 0.95] `confidence_score` — **set to the B/C tier boundary** (see the C-tier consequence below). NO_BET if `confidence < 0.50`. | `reasoned` |
| 3 | **variance** | hard gate: `variance_level == 'extreme'` **OR** a primary-factor directional split (`primary_disagreement`) **OR** the detector's `AVOID_OR_MINIMUM` action. | `reasoned` / structural |

**C-tier consequence (owner, stated explicitly):** the confidence floor `0.50` **equals the B/C tier
boundary** (3c.6). So any prediction whose confidence lands in the C band is below the floor → NO_BET.
**Tier C is therefore a diagnostic grade, never a bet grade** — a live bet is only ever tier A or B, and
C appears only on NO_BET games (explaining *why* it was passed: a C = confidence too low, vs a B/A NO_BET
that was edge- or variance-gated). Encoded: `NO_BET_CONFIDENCE_FLOOR == CONFIDENCE_TIER_B_MIN`, asserted
in `verify-phase-3`.

**Post-freeze acknowledgment (owner, deliberate):** if in-season selectivity runs **materially quieter**
than the synthetic below implied, that is **observable via the Phase-4 reports but frozen** — the freeze
does not reopen on a quiet slate. **Erring quiet is deliberate per L4**: a model that declines a marginal
edge is behaving as designed, not failing.

**⚠ The missing scale-check — and why this entry is BOUNCED.** The owner asked the entry's version of
the ×HFA check: *on a real in-season slate, what fraction of games clear these floors?* Measured over
**330 real 2026 FBS-vs-FBS games** with the **actual full-season schedule intel** (deterministic from the
schedule — the honest in-season physical-signal distribution; situational/momentum dormant without
results, sentiment dormant):

| edge floor | in-season bet rate |
|---|---|
| 0.05 pts | 26% |
| 0.08 pts | 21% |
| 0.10 pts | 4% |
| **0.75–1.5 pts (proposed)** | **0%** |

**The physical edge distribution maxes at 0.200 pts** (median 0.000, p90 0.094, p99 0.175, mean 0.028);
even a *synthetically maximal* game with **all six** physical factors firing (raw 6.7 pts) yields an edge
of **0.528 pts**. So at the proposed floors (0.75–1.5) the model **NO_BETs 100% of games, in-season, at
any week — it never places a bet.** The floor value is almost irrelevant: the edges live an **order of
magnitude below** it.

**Root cause (structural, pre-existing):** the contrarian edge is a **normalized-weight × value** sum
(3b weights are shares that total ~1), so `total_adjustment` is effectively a *weighted average* of
factor signals — bounded to ~0.1–0.2 pts even when strong physical spots align — while the floor is in
**points**. The 0.75–1.5 floor is a relic of the pre-Bug-#7 era, when the ≈+1.0 phantom made every
edge clear ~1.0; with the phantom and the fabrication gone, the model's honest disagreement with Vegas
is ~0.1 pts (**it essentially agrees with the market** — consistent with D17: the contrarian adjustment
added nothing over consensus).

**Resolution (owner, 2026-07-04) — option (A): freeze the honest "rarely bets" model.** The owner
reviewed the selectivity curve and **accepted the evidence**, choosing to keep the **dynamic edge gate
as-is** (0.75–1.5) rather than lower it to force a bet rate — the model's honest disagreement with an
efficient market is small, and manufacturing a larger edge (option B, reopening the 3b weight
magnitudes) would echo the phantom just removed. The confidence floor is set at **0.50** as the static
floor beneath the dynamic gate (making tier C unbettable, above). **Erring quiet is deliberate** (see the
post-freeze acknowledgment above): a quieter-than-synthetic in-season slate is observable in the reports
but does not reopen the freeze. *(The measured caveat is on the record for 2027: the 3b reweight ratified
factor **shares** + budget bounds but never scale-checked the resulting edge in **points** — whether a
weighted-**average** aggregation can produce point-scale edges is the open question Phase-4 attribution
informs. Option B remains available in 2027 with a season of evidence, not reopened now.)*

### 3c.6 — Confidence v2: A/B/C tiers (L3)  (`reasoned` — SPEC §7.5)  — **RATIFIED as reasoned first boundaries** (owner, 2026-07-04)

> **Placeholder-grade confidence (owner):** these boundaries are **reasoned first cuts, not measured**. Phase-4 attribution in 2026 measures whether they *separate anything* (per-tier ATS%/CLV); **2027 re-derives them from that evidence.** They are ratified to be *used and measured*, not asserted as correct — hold them loosely.


Tiers key off the engine's `confidence_score` (the persisted [0.15, 0.95] one). Boundaries are
**`reasoned`** — explicitly NOT fit to the archive confidence→ATS table (inadmissible, SPEC §3):

| Tier | `confidence_score` | Meaning |
|---|---|---|
| **A** | ≥ 0.65 | strong conviction |
| **B** | 0.50 – 0.65 | standard |
| **C** | < 0.50 | **diagnostic only — never a live bet** (the B/C boundary == the NO_BET confidence floor, 3c.5) |

A `NO_BET` / no-line / error prediction has **no tier** (`None`) — it is a decision not to bet, not a
graded conviction. The **monotonic-tier property is a structural sanity check on the NEW model's output**
(verified synthetically over a confidence sweep, in the spirit of the D9 dispersion test), never a
2025-ATS gate; per-tier ATS%/CLV is what Phase-4 attribution measures in 2026. Tiers are surfaced
in-object + in reports/CLI; the **on-disk schema-v2 field + 2025 converter are Phase 3d** — 3c carries
`prediction_type`/`no_bet`/`confidence_tier` through the storage writer so they are not silently dropped
(surfaced-but-unpersisted is fine for this slice; silently lost is not).

### 3c.7 — Cleanup: multiplicative-modifier activation bookkeeping  (behavior-change)  — **APPROVED** (owner, 2026-07-04)

`base_calculator.apply_threshold` now measures activation as **distance from the factor's neutral value**
— `1.0` for a multiplicative modifier, `0.0` additive (`abs(value − neutral) < threshold`). A dormant
`MarketSentiment` at 1.0 is therefore **not** counted `activated` (it was, on 10/10 dry-run games,
inflating `factors_activated` and diluting `avg_confidence`). Additive behaviour is unchanged
(neutral 0.0). Harmless to spreads (the multiplier is 1.0 either way); it corrects the confidence
distribution 3c calibrates.

### 3c.8 — Cleanup: `ExperienceDifferential` — TWO defects fixed  (correctness / behavior-change)  — **APPROVED** (owner, 2026-07-04)

This entry fixes **two distinct defects**, named honestly:
1. **The None-crash.** `min(None, 15)` crashed on present-but-`None` coaching experience (the preseason
   norm), only caught+zeroed by `safe_calculate` — "crash caught by a wrapper" ≠ "handles missing data".
2. **Bug #15 — the `.get(key, 5)` neutral-fill.** A separate, silent defect: absent coaching data was
   **neutral-filled to a default of 5 years' experience / 3 years' tenure** — a fabricated team-quality
   input (binding #4), distinct from the crash. It silently invented a mid-career coach for every team
   with no data, and would have contributed a real (fabricated) differential whenever the two teams'
   missing-ness differed. **Bug #15 on the tally.**

Fix: read with **no default** so a missing OR `None` value stays `None`, and return **0.0
honest-missing** when any of experience/tenure is absent/`None` — no crash, no fabricated default. The
confidence path guards `None` identically.

### 3c.9 — Preseason dormancy inventory  (owner rider 2)

With the situational pair + momentum ×2 + pressure neutralised on top of the D19 sentiment fix, state
plainly what the model consists of **preseason** (weeks 0–~3, before real results accrue): the **physical
factors + the power-rating base gap**, essentially — everything data-derived-from-results is dormant, and
`MarketSentiment` is dormant until slice-1.5 line-movement. This is the design's own logic converging,
not a defect: an honest model with no current-season signal declines to bet (10/10 NO_BET on the dry-run).
The early-season quiet is deliberate and ratified as such.

### 3c.10 — DEFERRED: `StyleMismatch` output range  (carried, with a hard due date)  — **RATIFIED as written** (owner, 2026-07-04)

`StyleMismatch`'s ±4.0 range is **1.6 × the ~2.5-pt HFA** — the largest single-factor output range in the
system, flagged in 3b.4. It is a genuine calibration question, but it is a **`matchup`-factor** question
(what is the honest cap on a pace/efficiency mismatch from advanced stats?) with **nothing to do with
L2's situational-threshold reasoning** — folding it in would be scope creep wearing a baton costume.
**Deferred to 3d or a pre-freeze mini-batch — but MUST be resolved before the `v2026-frozen` tag:** a
±4.0 range (1.6 × HFA) cannot freeze unexamined. This deferral carries its own due date.

*Every constant above is **RATIFIED** (owner, 2026-07-04) and freezes at `v2026-frozen`, except the
**3c.10 `StyleMismatch` deferral**, which carries a hard pre-freeze due date.*
