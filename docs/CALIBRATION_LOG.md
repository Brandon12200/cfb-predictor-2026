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

## Phase 3 — status: FROZEN-FORM (constants final in all but the tag)

Phase 3 (3a → 3d) is **complete and merged**. Every constant below is **RATIFIED** and in its final
form; the model is **frozen-form**. **Before the `v2026-frozen` tag** (on FREEZE-READY, target ~2026-08-08, per owner ruling 2026-08-03 (originally g1, July); SPEC §3/§16.2): any
change to a calibration constant, factor logic, or threshold requires **owner ratification** and a new
CALIBRATION_LOG entry — the same propose→pause→ratify rule that produced these. **After the tag:** the
freeze is binding — `factors/`, `engine/`, and weight/threshold config are immutable for the season, and
any output-altering change requires the **documented exception process** (SPEC §3: a dated exception
entry + a new tag). The formal pre-freeze **calibration audit** (SPEC §14 / `calibration-auditor` agent)
runs immediately before the tag (per owner ruling 2026-08-03 (originally g1, July)) and is on `docs/FREEZE_CHECKLIST.md`.

Evidence-class recap (SPEC §3 Bug-#7 constraint): every Phase-3 entry is **`reasoned`** unless it rests
on model-independent market data (`hfa_elo`, `margin_sigma`) — the 2025 archive's confidence→ATS /
edge→ATS tables are **inadmissible**. The `reasoned` entries are measured for real by **Phase-4
attribution** in 2026, which is what converts them to `measured` for the 2027 recalibration.

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
**3c.10 `StyleMismatch` deferral**, which carries a hard pre-freeze due date — resolved in Phase 3d below.*

---

## Phase 3d — `StyleMismatch` pre-freeze resolution (3c.10)  — **RATIFIED** (owner, 2026-07-04)

The 3c.10 deferral, now due before the freeze. Structured **diagnosis-first** (3d.1), with the three
ratified dispositions following from it (3d.2–3d.4). Evidence class **`reasoned`** (a `matchup`-factor
calibration; the archive is inadmissible, SPEC §3). Scale-checked against the ratified ~2.5-pt HFA (D9).

### 3d.1 — Pace-bug diagnosis  (the finding that drives 3d.2–3d.4)

- `StyleMismatch` reads only `context['advanced_stats']`, which is **empty preseason** (CFBD posts no
  2026 advanced stats until games are played) → the factor is **already fully dormant early season**
  (returns 0.0 when either team's stats are missing). This is another honest-missing-preseason case: the
  ±4.0 range and the pace bug have **zero effect** until in-season.
- The pace formula `plays / max(1, season)` divided by a **non-existent `season` count** (→ /1), and the
  canonical `AdvancedStats` payload (`offense`/`defense` open dicts) carries **no games-played count** —
  games-played is **not in the factor's data contract**. Worse than "absolute value wrong": the firing
  condition `abs(home_pace − away_pace) > 10` compares **raw season play totals**, whose difference
  tracks games-played / blowouts / OT, **not tempo** — a Bug-#7-adjacent phantom (**Bug #16** on the
  tally: the running fabrication count is now #7 [MarketSentiment] + #12–14 [the six-factor hash template]
  + #15 [ExperienceDifferential neutral-fill] + #16 [this pace phantom]).

### 3d.2 — Pace component → DORMANT (not fixed)  (behavior-change)  — **RATIFIED** (owner, 2026-07-04)

**Decision-tree outcome (honest data path in the factor's inputs? → no):** the per-game denominator is
not in the payload the factor consumes; bolting cross-source games-played plumbing into a `matchup`
factor for a single weak tempo sub-signal (1 of 6, overlapping the efficiency components) at freeze time
is disproportionate risk. **DORMANT:** `_calculate_pace_mismatch` returns 0.0; the fabricated
`plays_per_game` field + its confidence/explanation branches are removed. The other **five** components
(real rate stats: success rate, explosiveness, run/pass, havoc) carry the factor. The dormancy is pinned
by a **pace-invariance regression test** (`tests/test_phase3d.py`): on synthetic team pairs that differ
only in per-play/pace, the factor's output must be unchanged — the *meaning* is pinned (the factor no
longer responds to raw play-count differences), not just the arithmetic. *(Fix alternative — plumb a
completed-games count — remains available in 2027 if attribution shows tempo has independent value.)*

### 3d.3 — Output range ±4.0 → **±1.5**  (`reasoned`)  — **RATIFIED** (owner, 2026-07-04)

**±1.5 = 0.6 × the ~2.5-pt HFA** (was ±4.0 = **1.6× HFA**, the largest single-factor range in the
system). A style/efficiency mismatch is a **secondary `matchup` read** and must be capped well below home
field; ±1.5 sits alongside the physical factors (bye 1.0, travel cap 1.5) — **well under 1.0× HFA**, as
required. **The old ±4.0 was never scale-argued, merely inherited** — unlike every other coefficient in
the system, it arrived without a stated magnitude justification, which is exactly why 3c.10 refused to
let it freeze unexamined. **Early-season relevance (from 3d.1):** the factor is dormant until advanced
stats arrive, so the range binds only in-season — but it freezes now, examined, closing the due date.

### 3d.4 — Confidence bands rescaled to the ±1.5 range  (behavior-change)  — **RATIFIED** (owner, 2026-07-04)

The confidence bands were keyed to the old ±4.0 range (`>3.0` VERY_HIGH, `>2.0` HIGH), leaving the top
two tiers **dead** under ±1.5. Rescaled proportionally (`>1.2` / `>0.9` / `>0.6` / `>0.3`) so the factor
uses its full range and can report meaningful confidence in-season. No new signal — a consequence of
3d.3.

*All ratified 2026-07-04; freeze at `v2026-frozen`. Not measured against 2025 (inadmissible); measured
for real by Phase-4 attribution in 2026.*

---

## Phase-3 reverse-audit (calibration-auditor shakedown, 2026-07-09)  — **A + B DISPOSITIONED. One late item (A6) open.**

> **Status.** **A1–A5 dispositioned** (owner, 2026-07-25) — see "A-item dispositions" below.
> **B1–B10 ratified** (owner, 2026-07-16) — see "B-item ratifications" below. A-before-B was
> deliberate: the A retirements deleted paths B would otherwise have had to cover.
> **A6 (late A-class) ratified and fixed** (owner, 2026-07-16) — see the "A6" entry at the end of
> this log. **The reverse-audit ledger is now fully dispositioned; no items remain open.** Remaining
> pre-tag work is the lint-scope fold-in and the `calibration-auditor` pre-flight.

The `calibration-auditor` agent's first run did the reverse check (grep frozen paths for numeric literals
lacking a log entry) and found the log's **forward** coverage (Phases 2/3b/3c/3d) is clean but its
**reverse** coverage is materially incomplete: the *outer* gates (NO_BET floors, tiers, physical
coefficients, Elo) are logged, but the **internal factor formulas** and a **second scoring engine** are
not. **This blocks the freeze** (`docs/FREEZE_CHECKLIST.md`): every item below needs owner disposition —
**ratify** the value as-is, **revise** it, or **retire** the path — before the `v2026-frozen` tag. Nothing
here is auto-ratified; entries are grouped by the *kind* of disposition needed. Structural literals were
excluded via `docs/CALIBRATION_EXCLUSIONS.md` (signal-only). Verified spot-checks: findings A1 and A2 below
confirmed against source.

### A. BUGS / dead-or-duplicate paths — need a **DECISION** (fix or retire), not just a value ratification

- **A1 — `HeadToHeadRecord` can only fire at saturation (never, in practice).** Registry threshold **1.0**
  (`factors/factor_registry.py:173`) **equals** the factor's own output-range max (`_max_output=1.0`,
  `factors/coaching_edge.py:270`) — the *identical* bug 3c.3 diagnosed + fixed for `DesperationIndex`
  (2.0==±2.0), here **unnoticed** and silently neutering a **SPEC §16.7-mandated KEEP** factor. Decision:
  set a firing threshold below the max (as 3c.3 did) or consciously accept it dormant. **Verified.**
- **A2 — A second, unlogged, contradictory confidence/edge engine is wired LIVE.** The single-game CLI path
  (`cli/app.py::run_single_prediction`, `:475,480,510,556`) shows confidence + recommendation from the
  **standalone** `engine/confidence_calculator.py` (`ConfidenceCalculator`: 6 component weights, `[0.15,0.85]`
  clamp, edge-tier + type-adjustment + early-season dicts) and `engine/edge_detector.py` (`edge_thresholds`
  3.0/2.0/1.0/0.5, `confidence_thresholds`, `risk_parameters`) — **not** the 3c/3d-ratified
  `confidence_score`/`prediction_type`. Both modules live in `engine/` → they **freeze wholesale** as a
  second calibration surface with zero log coverage, and "confidence" means different things on different CLI
  paths. Decision: **retire** these (route the single-game path through the ratified engine) or log+ratify
  them. Retire is the likely honest call. **Verified.**
  **Update (Phase 4.5, D24):** `cfb predict game` routes through the **ratified** slate
  (`build_predictions`), and `main.py`'s deprecation shim no longer calls `run_single_prediction` — so
  `run_single_prediction` + the standalone `confidence_calculator`/`edge_detector` + the now-unused
  `cli.app.main` flat dispatch are **consumer-less** (no live entry point). The code is untouched
  (parked); this **strengthens retire-over-fix** — the freeze-prep retirement now only deletes dead code.
- **A3 — `variance_detector` category map references retired factors.** `engine/variance_detector.py:50-55`
  `factor_categories` names the **deleted** `LookaheadSandwich`/`SchedulingFatigue` (3b.6) and omits every
  current physical factor + the `matchup`/`market` categories, so category-variance is blind to the 56%
  physical category. Decision: fix the map (and log the CV cutoffs — see B4) or retire category-variance.
- **A4 — Contrarian `prediction_type` ladder is structurally unreachable at the top.**
  `engine/prediction_engine.py:282-291` needs 1.5–3.0-pt edges for MODERATE/STRONG/VERY_STRONG, but 3c.5
  *measured* real edges cap ~0.2 pts — the same "floor an order of magnitude too high" finding 3c.5 made for
  NO_BET, recurring unlogged. Decision: rescale to the real edge distribution or accept the ladder collapses
  to SLIGHT/CONSENSUS/NO_BET (and log that).
- **A5 — `config.py:54-61` category weights contradict the ratified shares** (60/30/10 + legacy 40/40/20 vs
  the ratified physical 56 / situational 14 / coaching 12 / matchup 10 / momentum 7) and are surfaced to
  users via `cli status`. Decision: retire/correct the stale config (confirm it doesn't feed the engine) —
  cross-entry inconsistency.

### B. Genuinely unlogged calibration constants — **PROPOSED** for ratification (values as-found; ratify / revise)

- **B1 — `_calculate_confidence_score` (`engine/prediction_engine.py:524-573`)** — the formula behind the
  ratified `confidence_score` that 3c.6/3c.5 key off but never logged. **Audited per-number** (a composite
  block; each member gets its own disposition):
  - `data_quality` weight **0.4** — **RATIFIED as drafted (owner, 2026-07-04).** Data completeness is the
    dominant input to confidence — `confidence_score` should track how much real data backs a prediction
    above any single factor's signal; 0.4 (40%, the largest single component) encodes that. `reasoned`.
  - **PROPOSED (awaiting ratification):** the remaining component weights `0.3` (factor success rate) / `0.2`
    (edge) / `0.1` (betting-data present); the edge-scaling divisor `/5.0`; the variance adjustments
    `+0.25/+0.1/-0.1/-0.2/-0.3`; the clamp `[0.15, 0.95]`. Each needs its own magnitude argument (or an
    explicit "inherits the set's reasoning" note). **The tier/floor entries assumed this whole formula; it
    must be fully logged for them to stand.**
- **B2 — `factor_registry._configure_factor_hierarchy` overrides** (`:172-196`) — `HeadToHeadRecord {1.0,5.0}`
  (see A1), `ExperienceDifferential {1.0,3.0}`, `PointDifferentialTrends {0.75,3.0}`, `CloseGamePerformance
  {0.5,2.0}` (only `DesperationIndex 1.0` is logged, 3c.3).
- **B3 — `DesperationIndex` internal formula** (`factors/situational_context.py:94-155`) — live in-season:
  blend 0.4/0.3/0.3, bowl/playoff/late-season branch values, `×4.0` differential scale, and the
  `bowl_eligibility_threshold=6`/`playoff_contender_threshold=1`/`conference_championship_weeks=[13,14]`
  config. Only the outer activation threshold is logged.
- **B4 — `variance_detector` CV cutoffs** (`engine/variance_detector.py:41-47`: 0.15/0.30/0.50/0.75/1.0) —
  set `variance_level`, which is a **hard NO_BET gate** (`NO_BET_VARIANCE_LEVELS`) and drives the B1 variance
  adjustments. A gate this load-bearing must be logged.
- **B5 — physical factors' shared cutoffs** (`factors/scheduling_fatigue.py`) — uniform
  `activation_threshold=0.4` (×6) and the `max_impact*0.6` strong-confidence cutoff (`:59`).
- **B6 — `ExperienceDifferential` internal** (`factors/coaching_edge.py:36-39,99`) — `max_experience_edge=15`,
  `tenure_weight=0.3`, `rookie_penalty=0.5`, `×2.0` scale; plus the three coaching factors' individual 0.06
  weights (only the 12% category total is logged).
- **B7 — momentum internals** (`factors/momentum_factors.py`) — `PointDifferentialTrends` trend-weights,
  improvement thresholds, consistency bonus, std-dev bands; `CloseGamePerformance` clutch-weights,
  `close_game_threshold=7`, split weights, `experience_multiplier=1.2`, `min_close_games=2`.
- **B8 — `StyleMismatch` internal weighting** (`factors/style_mismatch.py:44-52,85-91`) — the `÷6.0`
  denominator + component weights (`success_rate 2.0/explosiveness 1.5/havoc 0.8`; note `pace_mismatch_weight`
  is inert per 3d.2 and `redzone_weight` appears **dead** — verify) + ~20 internal branch thresholds. 3d
  ratified only the output range + confidence bands, not the pre-clamp weighting.
- **B9 — `MarketSentiment` internals** (`factors/market_sentiment.py:48-55`) — dormant today but **frozen**:
  the movement/steam/sharp/public thresholds + signal-strength bands that activate the moment slice-1.5 data
  lands mid-season. Only the outer `[0.85,1.15]` range is logged (MSF.3).
- **B10 — SPEC §16.7 exception is undocumented in this log.** §16.7 requires noting the coaching multi-season
  lookback exception **here**; no entry exists. Add it (and note `HeadToHeadRecord.config`
  `recent_game_weight/max_lookback_years` appear dead — verify).

### Disposition process

Each A-item is a **freeze-blocker decision**; each B-item is a **PROPOSED** constant awaiting your
ratify/revise. Recommended order: resolve **A** first (bugs/retirements change what B needs to cover), then
ratify **B** as one consolidated batch. Track on `docs/FREEZE_CHECKLIST.md`. The auditor re-runs (~Aug 20)
as the final pre-flight and must come back **FREEZE-READY** before the tag.

---

## A-item dispositions (reverse-audit ledger)  — **RATIFIED (owner, 2026-07-25)**

All five A-items were dispositioned individually (no batch approval); each touches freeze-bound
`factors/`/`engine/`/config and therefore had to land **pre-tag**. Evidence was measured read-only
before each proposal. Two ledger findings were **corrected against source** during that work and the
corrections are recorded in the entries below (A2's blast radius, A5's severity).

### A1 — `HeadToHeadRecord`: accepted **DORMANT**, not fixed  (`reasoned` / structural)  — **RATIFIED**

**Two independent blockers, and fixing only the first accomplishes nothing.** The ledger recorded one;
the second was found on inspection and is the decisive one.

1. **Threshold == output max.** Registry `activation_threshold = 1.0`
   (`factors/factor_registry.py:167`) equals the factor's own `_max_output = 1.0`
   (`factors/coaching_edge.py:270`). Activation is `abs(value - neutral) < activation_threshold → no-op`
   (`factors/base_calculator.py:215`), so the factor can fire only at exact ±1.0 saturation — the same
   defect 3c.3 fixed for `DesperationIndex` (2.0 == ±2.0), here on a **SPEC §16.7 KEEP** factor.
2. **The input is a hardcoded placeholder that is always zero.** `data/data_manager.py:32-35` injects
   `_H2H_PLACEHOLDER = {"home_wins": 0, "away_wins": 0, "total_games": 0, "note": "Historical
   coaching H2H not yet implemented"}` at `:140`, and `calculate()` returns `0.0` whenever
   `total_games < min_games_for_significance` (=3) — `coaching_edge.py:296-297`. **`total_games` is
   always 0**, so the factor returns 0.0 on every game of 2026 *at any threshold*.

**Decision: accept dormant, consciously and on the record.** Lowering the threshold (the 3c.3 remedy)
would be a freeze-bound edit with **provably zero** behavioural effect. Making the factor genuinely fire
would require building a CFBD coaching-H2H ingest — new data-layer work, days before the freeze,
injecting a brand-new *unmeasured* signal into a model about to be frozen. That is precisely what the
freeze exists to prevent. **§16.7's KEEP mandate is satisfied by keeping the factor registered and
honestly dormant** (dormancy-as-design, 3c.9 / binding principle #4) — never by manufacturing a signal
from a placeholder.

**⚠ Note for 2027 — do not "fix the threshold" and believe the factor is restored.** Both blockers must
be cleared, and the *data* one is the real work. A threshold change alone leaves it returning 0.0.

**B10 confirmation (carried to the B-batch):** `HeadToHeadRecord.config`'s `recent_game_weight = 1.5`
and `max_lookback_years = 10` are confirmed **dead** — `calculate()` reads only
`min_games_for_significance`. B10 should log them as dead-not-calibrated rather than ratify values that
nothing reads.

### A2 — Second confidence/edge scoring surface: **RETIRED** (full cluster deleted)  — **RATIFIED**

`engine/confidence_calculator.py` (6 component weights, `[0.15,0.85]` clamp, edge-tier + type-adjustment
+ early-season dicts) and `engine/edge_detector.py` (`edge_thresholds` 3.0/2.0/1.0/0.5,
`confidence_thresholds`, `risk_parameters`) were a **second, unlogged calibration surface inside
`engine/`** that would have frozen wholesale, with "confidence" meaning different things on different
paths. Phase 4.5 (D24) had already orphaned them from production: `cfb predict game` prices from the
ratified `build_predictions` slate and `main.py` no longer calls `run_single_prediction` — enforced
structurally by `scripts/verify_phase_4_5.py:76` and `tests/test_cfb_cli.py:80`.

**Correction to the ledger's framing.** The handoff recorded that retirement "only deletes dead code."
That was **not accurate**: the two engine modules still had **nine consumers** (six test modules, the
`EdgeType` enum consumed by `output/insights_generator.py`, `scripts/clean_predict.py` via `demo.sh`,
and `validate_performance_metrics.py`). The retirement is a real deletion with a test-and-script
cascade, and was scoped and approved as such.

**`EdgeType` relocation was considered and found unnecessary.** The owner's ruling was to relocate the
enum to its consumer if live presentation code imported it. Verified: its only non-test importer was
`output/insights_generator.py`, which is itself consumed only by its own tests — dead code importing
dead code. The enum was deleted with the cluster.

**Deleted:** `engine/confidence_calculator.py`, `engine/edge_detector.py`, `cli/app.py`'s
`run_single_prediction` + the `cli.app.main` flat dispatch (its only caller;
`run_hypothetical`/`run_project` are **kept** — `cfb` uses them), `output/insights_generator.py`,
`output/formatter.py`, `output/__init__.py`, `scripts/clean_predict.py` (+ its `demo.sh` block),
`validate_performance_metrics.py`, and six test modules. **Folded in per owner ruling (carry-forward
item 5, the Phase-0 dev-script cluster):** `engine/factor_validator.py`,
`utils/performance_analyzer.py`, `utils/bet_evaluator.py`, `scripts/validate_factors.py`,
`scripts/generate_report.py`, and `scripts/check_results.py` (a `bet_evaluator` consumer, unreferenced
and superseded by `scripts/grade.py` — surfaced during the sweep, not in the original enumeration).
**Kept per item 5:** `scripts/grading.py` + `scripts/calculate_accuracy.py` — the D17 "where the 57%
came from" exhibit must stay findable.

**Not expanded (flagged, freeze-exempt):** deleting `cli.app.main` orphans `run_weekly_analysis` and
`run_p4_predictions` (~430 lines), which were reachable only from it. `cli/` is **not** freeze-bound,
so this cleanup can land post-tag; it was deliberately left rather than silently widening scope.

**Result:** the ratified `prediction_engine` is now the **only** scoring surface in `engine/`.

### A3 — `variance_detector` category map: **FIXED** (output-neutral)  — **RATIFIED**

`engine/variance_detector.py:50-55` mapped factors by name to categories, but named the **retired**
`LookaheadSandwich`/`SchedulingFatigue` (3b.6) and **omitted every physical factor** — so
category-variance was blind to the 56% physical category. Two distinct causes: `SchedulingFatigue` was
deleted, and `Sandwich` was missed by a **rename**. `StyleMismatch` was additionally mislabelled
`statistical` against its real category `matchup`.

**Severity corrected downward from the ledger.** The map is **diagnostic only**: `variance_level` — the
hard NO_BET gate (`prediction_engine.py:335`) and the driver of the B1 confidence adjustments
(`:504-520`, `:557-566`) — derives from the **overall** coefficient of variation
(`variance_detector.py:87`), never from this map. `category_variance` feeds only
`_interpret_variance_implications` → a narrative `implications` list, and neither is persisted (absent
from `V2_RECORD_KEYS`).

**Fix:** the map now mirrors the ratified 3b.3 taxonomy keyed on live factor names (adds `Altitude`,
`ByeAdvantage`, `ConsecutiveRoad`, `Sandwich`, `ShortWeek`, `TravelBurden`; drops the two retired names;
relabels `matchup`). The stale `LookaheadSandwich` override in `factors/factor_registry.py:188` was
removed as the same defect class.

**Deliberately NOT done:** the live `Sandwich` was **not** added to the registry hierarchy dict. That
dict sets `activation_threshold`, so adding it would have silently overridden the physical layer's
ratified 3b threshold — a calibration change disguised as a map fix. Removal only.

**Output-neutrality — proven, not asserted.** Week-1 slate `predictions` payload SHA-256 identical
across the change (`fdb3da473dadc1455cab9dba8ff577ee4fd875638136338da2cd42f677553c04`), and over the
**744-game** before/after comparison (10 wk1 + 734 in-season) **zero records differ**:
`max|Δ edge| = 0.000000000000`, `max|Δ confidence| = 0.000000000000`.

### A4 — Contrarian `prediction_type` ladder: collapse **ACCEPTED and logged, not rescaled**  — **RATIFIED**

**Evidence class: `measured`** — the edge distribution is a deterministic property of the frozen model
over the real 2026 schedule, not an outcome-fitted quantity, and is **not** drawn from the
Bug-#7-contaminated 2025 archive tables (which remain inadmissible).

**Measured on two vehicles.** Vehicle A: the 10 wk1 games with real prediction-time lines. Vehicle B
(the 3c.5 vehicle): **all 734 real 2026 FBS-vs-FBS season games**, each driven at its own week against
the committed bundle so `compute_schedule_intel` fires at real in-season rates. `edge_size` is
independent of the line's *value* but requires a line to exist; Vehicle B's placeholder-line injection
was **proven neutral** (same 40 games at `-3.0` vs `+10.5`: `max|Δ| = 0.000000000000`).

| vehicle | n | p50 | p75 | p90 | p95 | p99 | max | mean |
|---|---|---|---|---|---|---|---|---|
| A — wk1 (real lines) | 10 | 0.0000 | 0.0468 | 0.1150 | 0.1276 | 0.1377 | **0.1403** | 0.0346 |
| B — in-season | 734 | 0.0244 | 0.0935 | 0.1179 | 0.1510 | 0.2057 | **0.2338** | 0.0483 |

*(Denominator note: 3c.5 recorded "330 real games"; this run enumerates **734**, verified unique — the
committed snapshot's entire schedule is 734 FBS-vs-FBS games across 138 teams, weeks 1–15. Same order,
same conclusion, fuller denominator.)*

**The ladder is correctly scaled where it persists, and unreachable only where it does not.** This is
the load-bearing distinction. The ladder and the 3c.5 floors are **in the same units at the same
scale**: a bet only persists when `edge ≥ min_edge_threshold` (0.75/1.0/1.5), and in that region the
**current** boundaries read correctly — measured: edge 0.75 → `SLIGHT`, 1.00/1.20/1.50 → `MODERATE`,
2.00 → `STRONG`, 2.50 → `VERY_STRONG`. The contrarian rungs are unreachable **only in the pre-floor
region**, where `base_type` is overwritten by the `NO_BET` verdict (`prediction_engine.py:393-394`) and
never persists — it is a local, absent from `V2_RECORD_KEYS`. **The ladder is not broken-but-inert; it
is correctly scaled where it persists and unreachable where it doesn't.**

**A rescale was measured and REJECTED as mis-scaled for the bet region.** Candidate boundaries fit to
the dormant-state distribution (`VERY_STRONG ≥ 0.200`, `STRONG ≥ 0.125`, `MODERATE ≥ 0.075`,
`SLIGHT ≥ 0.025`) yield a clean in-season spread (1.4% / 8.2% / 20.7% / 18.0% / 51.8%) — but because
every persisted bet has `edge ≥ 0.75`, **they would classify every actual bet as `VERY_STRONG`**
(verified across the bet region). Fitting to the dormant region would corrupt the region that matters.

**Scale-check (×HFA, D9 ~2.5 pts):** the entire measured edge range is ≤ **9.4% of HFA**; the rejected
top rung sat at 8.0%. Recorded so 2027 reads these labels at their true magnitude. The rung *names* are
semantically inflated relative to pre-floor quantities — renaming is **out of scope** (it would ripple
into `by_prediction_type` attribution, the v1→v2 converter, and stored 2025 archive values): recorded,
not acted on.

**⚠ The 100%-NO_BET result is the DORMANT-STATE projection, i.e. a lower bound.** Vehicle B runs with
situational/momentum/sentiment dormant and no results, so it measures the floor of the model's
in-season behaviour, not its ceiling. In-season activations are *designed* to lift rare games above the
floors — 3c.5's ratified posture is "**bets rarely**," not "never." When that happens `prediction_type`
varies and `SLIGHT`/`MODERATE` attribution rows populate: **that is the system working, not a
regression.** Do not read the preseason 734/734 `NO_BET` as a permanent property.

**For 2027 — do NOT "deduplicate" these dimensions.** `prediction_type` (edge magnitude) and
`confidence_tier` (conviction) are **deliberately distinct**. In the dormant state they look redundant
only because `prediction_type` is constant (`NO_BET`) while `confidence_tier` varies (measured
in-season: A 2 / B 405 / C 327). That asymmetry is the 3c.5 floors working as designed (L4), not
evidence that a field is surplus.

### A4 sub-decision — `predicted_edge` persisted at **4 dp** (was 2)  — **RATIFIED**

`utils/prediction_schema.py` rounded `predicted_edge` to 2 dp. Against a measured range of
**[0, 0.2338]** that leaves ~24 distinct values: the in-season median (0.0244) collapsed to `0.02` and
~40% of games rounded to `0.00`. Under the A4 disposition **`predicted_edge` is the primary attribution
dimension** for the 2027 `reasoned`→`measured` conversion (the discrete ladder never persists), so the
resolution must survive to disk. **Changed to 4 dp.** Freeze-exempt (`utils/`), but it regenerates the
committed v2 golden example — done, with `model_version` (VOLATILE, excluded from the parity check)
preserved so the golden carries no working-tree `-dirty` marker. `verify-phase-3`'s byte-identity check
caught the stale golden; the pytest suite did **not** — worth knowing which gate has that coverage.

### A5 — Stale category weights: **RETIRED** (with A2)  — **RATIFIED**

`config.py:54-61` carried `primary/secondary/modifier` 60/30/10 plus a legacy 40/40/20, contradicting
the ratified 3b.2 shares and surfaced to users by `cli status`.

**Severity corrected in both directions.** The ledger asked to "confirm it doesn't feed the engine."
It does **not** feed scoring — a mid-investigation flag that it "reaches `factors/`" was right about
the import path and wrong about the consequence. But the maps were worse than cosmetic in one respect:
`category_weights` was keyed `{primary, secondary, modifier}` while live factors carry the 3b.3
taxonomy (`physical`, `situational_context`, `coaching_edge`, `matchup`, `momentum_factors`, `market`)
— **zero key overlap**, so `validate_factor_configuration()` returned `valid: False` with three
spurious warnings on **every run it was ever called**. `legacy_category_weights` was **write-only
dead** (set, never read).

**Their only consumers were A2-cluster dead code**, so A5 executed inside the A2 deletion event as
ratified. Removed: both registry maps, `get_category_summary`, `validate_factor_configuration`,
`get_execution_stats`, `prediction_engine`'s `get_prediction_stats` + `validate_prediction_setup` (zero
callers anywhere, including tests), and the `config.py` weight blocks with their now-vacuous validator.

**User-visible surface fixed, not dropped** (owner ruling: no surface may state 40/40/20). `cli status`
now renders weights **live from the ratified registry**, shown both raw and as a share of the
**additive** budget — the multiplicative MODIFIER (market) is excluded from that subtotal, which is why
the live physical share reads 51.95% raw but **55.6% of additive = the ratified 56%**. Presenting only
the raw share would have created a *new* surface appearing to contradict 3b.2.

`tests/test_config.py`'s weight assertions were repointed at the registry (the invariant now lives
where the weights do) plus a regression pin that the removed constants never return.

---

## B-item ratifications (reverse-audit ledger, consolidated batch)  — **RATIFIED (owner, 2026-07-16; B4 added 2026-08-03)**

The unlogged internal-formula constants, audited **per-number** (a block is never ratified by one
entry that names it). Measured on the same two vehicles as A4: the 10-game wk1 dry-run slate and the
real 2026 season games driven at their own week — reported here over a **734**-game FBS-vs-FBS basis
and later corrected to the **330** both-teams-tracked basis (see "A6 → Denominator correction"; every
conclusion stood, only the stated denominator changed). **B4 was added on 2026-08-03 and is measured
on the corrected 330 basis.**

**This log is the complete and self-contained record.** The consolidated working proposal that
carried the original derivations was retired at the freeze boundary per its own lifecycle header;
every figure, argument, per-number disposition, dead-constant finding, method note and cross-cutting
observation it contained is reproduced in the entries below. **No external document is needed to
audit this batch.**

> **⚠ Reachability caveat, governing every entry below.** The vehicle is the **preseason** snapshot:
> no completed games, no in-season advanced stats, no line-movement series. A factor reading
> "0/734" means **this vehicle cannot exercise it**, NOT that it is dead code — except where an entry
> says **DEAD**, which is a static-analysis result independent of any vehicle. Same distinction A4
> turned on; do not collapse it.

**Liveness map (measured).** Only **4 of 15** registered factors fire in the measured state, all
physical: `ByeAdvantage` 191/734, `ConsecutiveRoad` 185/734, `TravelBurden` 152/734, `ShortWeek`
79/734. Vehicle-dormant (needs in-season data): `DesperationIndex`, `PointDifferentialTrends`,
`CloseGamePerformance`, `StyleMismatch`. Input-dormant: `ExperienceDifferential`, `Altitude`,
`Sandwich`, `PressureSituation`, `RevengeGame`. Design-dormant: `MarketSentiment`. Structurally
dormant: `HeadToHeadRecord` (A1).

### B1 — `_calculate_confidence_score` (`engine/prediction_engine.py:524-573`)  (`reasoned`)

The formula 3c.5's NO_BET floor and 3c.6's A/B/C tiers both key off.

**Component weights — a partition of one unit** (they sum to exactly 1.0; ratifying the set ratifies
the ordering *input quality > model coverage > edge > line presence*):

| Component | Weight | Measured mean contribution | Argument |
|---|---|---|---|
| `data_quality` | **0.4** | 0.1679 | **Previously RATIFIED** (owner, 2026-07-04); not re-opened |
| factor success rate | **0.3** | 0.2780 | How much of the model actually ran — the best proxy for trustworthiness after input quality |
| edge size | **0.2** | **0.0019** | See the divisor entry below |
| betting data present | **0.1** | 0.1000 | Binary presence gate; smallest share — a line existing says nothing about its quality |

**Edge-scaling divisor `/5.0` — RATIFIED AS-FOUND, with its consequence logged.** The divisor assumes
edges reaching ~5 pts. Measured: the season maximum edge is **0.2338**, so `edge_size/5.0` peaks at
0.0468 and the edge term contributes **at most 0.00935 of its nominal 0.20 budget — 4.68% of its own
range** (2.81% on the wk1 slate; mean 0.0019). **Consequence, ratified explicitly: `confidence_score`
is in practice a DATA-AVAILABILITY score** — quality + coverage + presence carry ~0.8 of the budget
and the edge term is negligible. This is consistent with 3c.5's ratified "erring quiet is deliberate"
posture. Not rescaled: doing so would move `confidence_score` on every game and thereby re-open the
3c.5 confidence floor and the 3c.6 tier boundaries, both ratified *against this formula*.

**⚠ FOUR-site root cause (updated 2026-08-03; recorded for 2027).** The pre-Bug-#7 point-scale
assumption — that model edges live at ~1–5 points — has **four** known sites: the NO_BET floors
(found by 3c.5), the `prediction_type` ladder (A4), this divisor (B1), and the **variance CV
cutoffs (B4)**, whose stated 0–1-ish dispersion scale does not match the unbounded values the
formula actually produces. **The sweep that this note asked for in July found the fourth.** One
phantom, four surviving calibration artifacts — **2027 should sweep for a fifth rather than assume
these were all of them.**

**Variance adjustments — RATIFIED as proposed:** `consensus` **+0.25**, `mild` **+0.1**, `moderate`
**−0.1**, `strong` **−0.2**, `extreme` **−0.3**. Monotone in disagreement; `mild`/`moderate` are
deliberately symmetric; `extreme` is largest but only labels the tier of an already-declined game
(3c.5 floor 3 forces NO_BET on `extreme` independently). **Logged observation (owner, for 2027):
`consensus` +0.25 is theoretically dominant and empirically near-inert.** On a [0,1] score with a
0.50 NO_BET floor and a 0.65 A-tier boundary, +0.25 can move a game from below the floor to A-tier by
itself — the single most powerful term in the formula. Measured, it fired on **1 of 734** games, with
711/734 at `insufficient_data` (no adjustment at all). **2027 must re-measure this term against a
season of real variance states** rather than inherit it on preseason evidence.

**Clamp `[0.15, 0.95]` — RATIFIED.** Never claims certainty or total ignorance. **Measured: it never
binds** — Vehicle B range `[0.1635, 0.7862]`, Vehicle A `[0.6332, 0.6388]`, zero games at either
bound. A guard rail, not an active shaper.

### B2 — registry hierarchy overrides (`factors/factor_registry.py`)  (`reasoned`)  — **RATIFIED**

`ExperienceDifferential {1.0, 3.0}` (threshold = 50% of its real ±2.0 max — sound),
`PointDifferentialTrends {0.75, 3.0}` and `CloseGamePerformance {0.5, 2.0}` (both **inherit the
secondary-factor set's reasoning**: thresholds scale with signal strength, weakest signal gets the
lowest bar). `HeadToHeadRecord {1.0, 5.0}` is **logged structurally dormant per A1**, not ratified as
a live value.

**⚠ Logged defect, deliberately NOT fixed pre-tag: `max_impact` exceeds `_max_output`.**
`ExperienceDifferential` is configured `max_impact = 3.0` while `validate_output` clamps to ±2.0, so
the declared cap is **unreachable** — an "unreachable bound", the same family as A1's
`threshold == _max_output`. It changes no output (the clamp binds first), so harmonising the numbers
would edit freeze-bound config to no observable effect — the A4 lesson. **Logged so the pattern is
recognisable in 2027; not corrected.**

### B3 — `DesperationIndex` internals (`factors/situational_context.py:94-155`)  (`reasoned`)  — **RATIFIED**

Vehicle-dormant (0/734); expected to fire in-season once records exist.

Blend **0.4 / 0.3 / 0.3** (bowl / playoff / late-season): bowl eligibility is the most broadly
applicable motivation — it applies to every team every year — while playoff and late-season pressure
apply to narrower populations and are weighted equally. Base neutral **0.5** (midpoint of the [0,1]
pre-scaling band). Bowl branch **−0.3 / 0.6 / 0.4 / 0.2 / 0.0** and playoff branch **0.5 / 0.3 / 0.1 /
0.0**: both monotone in urgency, with elimination the only negative (motivation *removed*); the
playoff branch is gated on `week ≥ 10` so it cannot fire early. Late-season ladder **0.4 / 0.3 / 0.2 /
0.0** by week — monotone step. Differential scale **×4.0** maps a ±0.5 differential onto the ±2.0
output range — a definitional mapping, not a free parameter. `bowl_eligibility_threshold = 6` is a
**rule of the sport** (structural, not calibration); `playoff_contender_threshold = 1` is `reasoned`.

**Scale-check:** ±2.0 output at weight 0.13 ⇒ ≤0.26 pts ≈ **10% of the ratified ~2.5-pt HFA**. In band.

**DEAD — logged, not ratified:** `conference_championship_weeks = [13, 14]` (0 references) and
`desperation_multipliers = {2.0, 1.5, 1.0, 0.3}` (0 references). Both verified statically.

### B4 — `variance_detector` CV cutoffs (`engine/variance_detector.py:41-47`)  (`reasoned`)  — **RATIFIED (owner, 2026-08-03)**

> **⚠ This entry was written 18 days after the rest of the batch, because B4 was SKIPPED.** The
> ledger enumerated B1–B10; the ratification batch ran B1, B2, B3, **→ B5**, B6–B10. The
> consolidated proposal skipped it identically (its §4 was headed "B2–B7" and went B3 → B5), so the
> proposal, the ratification and the log all inherited one enumeration slip, invisible from the log
> alone because every neighbouring item is present. Found by a three-source grep during freeze prep
> and dispositioned before the tag. **Method note for 2027: verify a batch's enumeration against its
> source list by count, not by reading — a missing middle item reads as continuous prose.**

The five coefficient-of-variation cutoffs: `consensus 0.15 / mild 0.30 / moderate 0.50 /
strong 0.75 / extreme 1.0`.

**Liveness chain — a live gate, NOT the diagnostic path A3 downgraded.** The distinction matters
because A3 concerned a *neighbouring* item in this same file. A3 was the `factor_categories`
**map**; B4 is the **cutoffs**, and they reach further:
`_determine_variance_level(cv)` (`:266-277`) → `variance_level` (`:97`) → consumed by **two
ratified gates** — (1) **3c.5 floor 3**, the hard NO_BET gate (`prediction_engine.py:411-413`,
`NO_BET_VARIANCE_LEVELS = {'extreme'}` plus `NO_BET_VARIANCE_ACTIONS = {'AVOID_OR_MINIMUM'}`, which
`_generate_recommendation` derives from the same ladder), and (2) **B1's ratified variance
adjustments** (`+0.25/+0.1/−0.1/−0.2/−0.3`), keyed on the label these cutoffs produce.
**3c.5 and B1 were both ratified against labels these five numbers produce.** `variance_level`
derives from the **overall** CV, never from the A3 map, so A3's "diagnostic only" does not transfer.

**Measured (330 both-teams-tracked games, each at its own week).** The 3-active-factor gate
(`:80-81`) dominates: **312/330 (94.5%) return `insufficient_data` with ZERO active factors**,
before any cutoff is consulted. Only **18** games reach the cutoffs — `extreme` 10, `moderate` 7,
`mild` 1, `consensus` 0, `strong` 0.

**Consequence, ratified explicitly: the hard gate is INERT in the measured preseason state.**
`extreme` fired **10/330** and changed **0** outcomes — all 10 were already NO_BET on *both* other
floors (edge < 0.75 **and** confidence < 0.50). Example (wk3 NC STATE@VANDERBILT): *"edge 0.02 below
threshold 0.75; confidence 0.33 < 0.50; extreme factor variance; variance recommends
AVOID_OR_MINIMUM."* **Reachability caveat (as for the whole B-batch): this is the preseason vehicle;
in-season activations may make the gate decisive, and that is the design working, not a regression.**

**⚠ Structural characterisation — the CV is not the scale it appears to be.** It is
`abs(std_dev / mean)` (`:156-159`) over **signed** factor values (positive favours home). When
factors point in opposite directions — precisely the "disagreement" being measured — the mean
collapses toward zero and the ratio explodes:

| game | active values | mean | CV | level |
|---|---|---:|---:|---|
| wk3 MIAMI@WAKE FOREST | Bye −1.0, ConsecRoad 0.5, ShortWeek −1.0 | −0.500 | 1.73 | extreme |
| wk9 OHIO STATE@USC | Bye −1.0, ConsecRoad 0.5, Travel 1.5 | 0.333 | 3.77 | extreme |
| wk3 NC STATE@VANDERBILT | Bye −1.0, ConsecRoad 0.5, Travel 0.6 | **0.033** | **26.89** | extreme |

So it behaves as a **sign-agreement detector with an unstable magnitude**, not a smooth dispersion
scale: mixed-sign games jump past all five cutoffs at once, same-sign games sit low. The measured
shape confirms it — the **`strong` band (0.50–0.75) is EMPTY and structurally near-unreachable**,
not merely unexercised. **This is a FOURTH member of the point-scale-artifact family** alongside the
3c.5 floors, the A4 ladder and B1's `/5.0` divisor — a number whose stated semantics do not match
its measured behaviour. **2027 should sweep for a fifth.**

**Per-number dispositions** (composite doctrine: each member argued, plus the set's progression):

- **`consensus` 0.15** — below 15% relative dispersion the factors tell one story; the most
  confident band, feeding B1's largest single adjustment (+0.25). Fires **0/330**.
- **`mild` 0.30** — 2× `consensus`; a uniform doubling, stated rather than fitted. Fires **1/330**.
- **`moderate` 0.50** — dispersion equals half the mean, the natural "disagree materially" line and
  where B1's adjustment turns negative. Fires **7/330**, the busiest live band.
- **`strong` 0.75** — dispersion at ¾ of the mean. **Ratified as a boundary, not as a live band**
  (0/330, structurally near-unreachable per the characterisation above).
- **`extreme` 1.0** — dispersion ≥ the mean; the only cutoff wired to a hard gate. Fires **10/330**,
  changed **0** outcomes.

The set is a **monotone ladder with one stated progression** — each boundary a fixed fraction of the
mean, ending at parity (0.15 → 0.30 → 0.50 → 0.75 → 1.0); every member both carries its own argument
and inherits that progression.

**`×HFA` scale-check — considered exemption, recorded so the pre-flight does not read it as an
omission.** These five are **dimensionless ratios, not point magnitudes**: "0.30 × 2.5 pts" is
meaningless. The substantive scale-check is the measured behaviour above — what the boundaries do to
real games.

**NOT recalibrated pre-tag (owner ruling).** Changing them moves `confidence_score` on every game
with ≥3 active factors and thereby re-opens **3c.5's floors and 3c.6's tiers**, both ratified
against this formula — the identical argument that carried B1's `/5.0` divisor. The measured state
shows zero outcome impact, so a change would be a freeze-bound edit with provably no behavioural
effect (the A1/A4 precedent). And the honest repair is not a threshold change at all: it is
computing dispersion without dividing by a near-zero signed mean — a **formula** change to a frozen
file, unmeasurable until a season of real in-season activations exists. **Carried to 2027.**

**DEAD/UNREACHABLE — logged as a KNOWN STATE, not ratified:** `variance_detector.py:225`'s bare
`0.3` (`'consensus': cat_metrics['coefficient_of_variation'] < 0.3`) — a sixth literal that is
**not** a member of the `thresholds` dict. **Doubly unreachable, both verified against source:**
(1) its only consumer (`:312-313`) requires `'statistical' in category`, but the **A3 fix relabelled
that key to `matchup`** — the live keys are `market/matchup/momentum/situational/coaching/physical`
(`:57-65`) — so the branch is always False; (2) the outer condition requires `market`, which needs
`MarketSentiment` **active**, ruled dormant-and-unwired for all of 2026 (**B9**). Even if both
fired, the output is a string appended to the unpersisted `implications` list (absent from
`V2_RECORD_KEYS`). Ratifying a value nothing can read would assert a claim the code does not make.

### B5 — physical shared cutoffs (`factors/scheduling_fatigue.py`)  (`reasoned`)  — **RATIFIED**

**The only set governing factors that fire in the measured state.**

`activation_threshold = 0.4` on all six — uniform **by design**: these are structural facts (a bye
either happened or it didn't), so one threshold expresses "at least half of the smallest meaningful
coefficient (0.5, consecutive-road) must be present." Measured: fires on **11–26%** of in-season
games per factor — selective, not chatty. Strong-confidence cutoff **`max_impact × 0.6`** — a signal
at ≥60% of its own cap is `VERY_HIGH` rather than `HIGH`; expressed relatively so it scales with each
factor's cap automatically. Per-factor `cap = 1.5` **inherits 3b.1's ratified `travel_cap`** (0.6×
HFA). The six weights (0.16/0.14/0.16/0.12/0.10/0.12) are **already ratified in 3b.2**; listed for
completeness only.

**Honest input absence, logged (B-batch item 9):** `Sandwich` fires 0/734 because the snapshot's
`sp_ratings` is empty — CFBD had not published 2026 preseason SP+ at the 2026-07-03 build.
`_sandwich_spot()` correctly returns `None` when adjacent-opponent strength is unknown (binding
principle #4), and `normalize_sp_ratings()` emits exactly the `ranking` key it reads — **no wiring or
field-name defect.** This is the state **D10 already ratified** ("robust to SP+ staying empty at
freeze; auto-activates when CFBD posts either source — data, not code"); the Phase-5 weekly rebuild
resolves it with no code change. **`Altitude`'s 0/734 is a DIFFERENT and NOT-honest cause — see the
open A6 item.**

### B6 — `ExperienceDifferential` internals (`factors/coaching_edge.py:36-39,99`)  (`reasoned`)  — **RATIFIED**

Input-dormant (0/734) — the snapshot's coaching fields do not populate. `max_experience_edge = 15`
(years beyond which coaching experience stops differentiating — a diminishing-returns knee);
`tenure_weight = 0.3` (tenure at the *current* school is worth less than total experience, 0.7
implied); `rookie_penalty = 0.5` (extra penalty for a first-year head coach); scale **×2.0** maps a
±1.0 raw differential onto ±2.0 — definitional. The three coaching factors' **0.06** weights are an
equal three-way split of the 12% coaching category total already ratified in 3b.2.

**Scale-check:** ±2.0 at weight 0.06 ⇒ ≤0.12 pts ≈ **5% of HFA**. In band.

### B7 — momentum internals (`factors/momentum_factors.py`)  (`reasoned` + `structural`)  — **RATIFIED**

Vehicle-dormant (0/734) — needs completed-game results. All constants verified **live and
referenced**.

`trend_weights` **0.4 / 0.3 / 0.2 / 0.1** — linear decay over the 4-game window; the last game counts
4× the fourth-last. `recent_games_window = 4` matches. `improvement_thresholds` **+10 / +5 / −5** —
point-differential swings of one-and-a-half to two possessions. `consistency_bonus = 0.3`.
`clutch_weights` — winning a close game is the full clutch signal, a blowout carries **0.3** of it
(less informative about late-game execution); consumed by name. `recent_games_window = 6` for close
games — a larger window than trends because close games are rarer and need more history to sample.
`experience_multiplier = 1.2` (20% amplification).

**Ratified as `structural` (sport convention / sample gate, not magnitudes):**
`close_game_threshold = 7` (one possession) and `min_close_games = 2` (the smallest non-degenerate
sample).

**⚠ Fragility logged: `trend_weights` are consumed POSITIONALLY.** `momentum_factors.py:144` does
`list(self.config['trend_weights'].values())[:n]` — the key names (`last_game`, `second_last`, …) are
**decorative**, and **reordering the dict would silently re-weight the factor** with no error and no
test failure. Recorded as a maintenance hazard, not a value change.

**Scale-check:** ±2.0 at weight 0.036 ⇒ ≤0.07 pts ≈ **3% of HFA**. In band.

### B8 — `StyleMismatch` internal weighting (`factors/style_mismatch.py:44-52,85-91`)  (`reasoned`)  — **RATIFIED as-found**

Vehicle-dormant (0/734). Component weights `success_rate 2.0` (highest — most predictive metric),
`explosiveness 1.5`, `havoc 0.8` (lowest — noisiest), `min_success_diff 0.05` (a 5% gate).
`pace_mismatch_weight 1.2` is referenced but **inert** — the pace component is dormant per 3d.2.

**⚠ The `/6.0` divisor — RATIFIED AS-FOUND with the discrepancy quantified.** Its comment says
"normalize by total weights", but the weights actually referenced in the sum are
`2.0 + 1.5 + 1.2 + 1.0 (a literal, not a config key) + 0.8 = **6.5**`; with pace dormant the *live*
sum is **5.3**. The divisor matches neither its stated intent nor the live total, under-normalising by
~8% against intent. **Not corrected**: the output is clamped to the ratified ±1.5 range (3d.3), the
factor is dormant in the measured state, and changing the divisor is a magnitude change to a frozen
factor. Logged so 2027 inherits a known, quantified discrepancy rather than rediscovering it.

**DEAD — logged, not ratified:** `redzone_weight = 1.0` (0 references — the ledger's suspicion,
confirmed) and `pace_advantage_slower = 0.3` (0 references — new finding).

### B9 — `MarketSentiment` internals: **DORMANT FOR ALL OF 2026, UNWIRED**  (`reasoned`, unexercised)  — **RATIFIED**

Measured: value **1.0 on 744/744** games, never activates — exactly MSF.3's specification.

**Owner ruling (2026-07-16): `MarketSentiment` stays dormant for the ENTIRE 2026 season.** Line
movement **is collected** (the Phase-5 daily `data/lines/` store) but is **not wired into the
factor**. Activation is deferred to **2027**, to be calibrated against a full season of real movement
data.

**This is NOT a re-opening of MSF.3.** The dormant-until-data design stands unchanged; the ruling
fixes what "data landing" means for 2026: **collected, not wired.** Rationale (owner): *activation is
earned with evidence, like automation; the model characterized at the tag is the model that runs the
season.* Without this, thresholds with zero measured backing would begin altering live predictions
mid-season, after the freeze, with the first affected game being the first time they ever ran.

Internal thresholds logged **as-found**, evidence-class `reasoned`, explicitly
**unexercised-and-unwired**: `reverse_movement_threshold 0.7`, `line_move_threshold 0.5`,
`steam_move_threshold 1.0`, `steam_time_window 6` (hours), `sharp_indicator_weight 0.4`,
`public_fade_weight 0.3`, `line_freeze_signal 0.2`. The outer `[0.85, 1.15]` range remains ratified
(MSF.3). **2027 inherits a season of collected movement data and zero in-season activation risk.**

### B10 — SPEC §16.7 exception note + dead H2H config  — **RATIFIED**

**§16.7 multi-season coaching-lookback exception, recorded here as §16.7 requires.** The coaching
factors legitimately read **prior-season coaching history** (identity, tenure, career record). This is
an explicit, owner-resolved carve-out from the **Data Recency Principle**: a coach's experience and
tenure are **not team-quality data** — they are properties of a person, and a coach's record before
2026 is the only way the signal can exist at all. The carve-out is narrow: it licenses prior-season
*coaching* attributes only, never prior-season team performance as a proxy for current team quality.

**DEAD — logged, not ratified** (carried from A1, verified statically): `HeadToHeadRecord.config`'s
`recent_game_weight = 1.5` and `max_lookback_years = 10` — **0 references** each; only
`min_games_for_significance` is read.

### Batch-level notes

**Six dead constants logged rather than ratified** — `redzone_weight`, `pace_advantage_slower` (B8),
`recent_game_weight`, `max_lookback_years` (B10), `conference_championship_weeks`,
`desperation_multipliers` (B3). Ratifying a value nothing reads asserts a claim the code does not
make. **Method note for the next audit:** an initial flat scan also flagged B7's
`trend_weights`/`clutch_weights` members as dead — a **false positive**, since they are nested dicts
consumed via their parent key. Nested config needs the parent-key check, not a flat one; a false DEAD
in a ratification batch would have retired live calibration.

**Two "unreachable bound" defects logged, neither fixed** — A1's `threshold == _max_output` and B2's
`max_impact > _max_output`. Neither changes output; both are logged so the family is recognisable.

**A seventh constant logged as a KNOWN STATE rather than ratified (added with B4, 2026-08-03):**
`variance_detector.py:225`'s bare `0.3`, **doubly unreachable** — its only consumer tests a category
key that the A3 fix renamed, and the outer branch needs the dormant `MarketSentiment`. Same
principle as the six dead constants: a value nothing can read is not ratified.

**Open at the close of this batch (since CLOSED):** the late A-class item **A6** (`Altitude` never
fires — metres compared against a feet threshold) was **not** part of this ratification and was
PROPOSED at the time of writing. It was **ratified and fixed the same day** — see the **A6** entry
immediately below, which is the complete record; its working proposal was retired per lifecycle.

**Also added after this batch closed: B4** (`variance_detector` CV cutoffs) — ratified 2026-08-03,
the item the B1→B5 numbering skipped. See the B4 entry above.

---

## A6 — `Altitude` unit mismatch: metres compared against a feet threshold  (behavior-change)  — **RATIFIED (owner, 2026-07-16)**

Late A-class item, surfaced by the B-batch reachability audit (ruling item 9). Logged under the
**D19 behavior-change pattern**: a wiring defect whose correction changes model output, with the
before/after measured and stated.

### The defect

`altitude_points()` compared a venue elevation against the ratified 3b.1 `altitude_threshold_ft =
4000.0`. **The elevation was in metres.** Verified against ground truth: Boulder's stored value is
`1634.04`, and `1634.04 × 3.28084 = 5,361 ft` against a real ~5,328 ft. The **maximum elevation in
the entire dataset is 1634.04** against a threshold of `4000.0`, so the comparison was **false for
every venue in every week** — `Altitude` fired **0/330** on the tracked slate and could never have
fired at any point in the season.

Ratified 3b.1 constants (`altitude_value` 1.2, `altitude_threshold_ft` 4000.0) silently neutered by a
comparison that cannot be true. **Same family as A1** (`HeadToHeadRecord` threshold == output max) —
**third occurrence** of a never-fires defect in this ledger.

**The defect was documented in a comment while being asserted through.** `tests/test_schedule_intel.py`
carried a `LARAMIE` fixture with `"elevation": 2194.0` annotated `# ~7200 ft altitude`, and
`test_altitude_passthrough_for_high_venue` asserted `intel["altitude"] == 2194.0`. The fixture author
knew the value was metres and the comment said feet; the test pinned the unconverted passthrough. A
test can enforce a contract and still enshrine a units bug — the pin has been rewritten to assert the
conversion.

### Root cause — a contract ambiguity, not a typo

Nothing in the schema stated the unit of `venues[*].elevation`. CFBD serves metres; the constant was
named `_ft` and reasoned in feet at 3b.1 (4,000 ft is the conventional high-altitude line). **Both
halves were individually correct; only the join was wrong.**

### Disposition — option (a), converted at the data boundary

Per owner ruling, the conversion lives at the **read/access seam in freeze-exempt `data/`**:

- **`venues[*].elevation` remains metres at rest** — the snapshot mirrors CFBD's native unit,
  unconverted. **Committed snapshot bytes are unchanged**; `snapshot_id` is untouched.
- **`data.schedule_intel.elevation_feet()`** is the single conversion point; `schedule_intel.altitude`
  is emitted in **feet**, with the unit asserted at the boundary.
- **`factors/physical_coefficients.py` is untouched** — the ratified 3b.1 constants stay
  byte-identical, which is the point of fixing at the boundary rather than in the frozen factor.
- **`docs/SCHEMA.md` now states the unit contract explicitly** (metres at rest → feet at the intel
  seam; any new consumer of `elevation` must convert), closing the ambiguity that caused this.

### Measured before / after (tracked slate, 330 games)

| | before | after |
|---|---|---|
| `Altitude` activations | **0 / 330** | **16 / 330** (4.8%) |
| max edge, tracked slate | 0.2338 | **0.2338** (unchanged) |
| mean edge, tracked slate | 0.0551 | 0.0592 |

The 16 are every non-neutral tracked game at the three tracked venues clearing 4,000 ft — **Colorado
(5,361 ft), BYU (4,633 ft), Utah (4,631 ft)**, all Big 12 — each taking the full `altitude_value`
**1.2 pts** (≈48% of the ratified ~2.5-pt HFA). The maximum edge is **unchanged**: the affected games
all sat below the prior maximum, so correcting the defect adds signal to 16 games without extending
the model's edge range.

**Week-1 slate is untouched — golden NOT regenerated.** No wk1 game has a high-altitude home venue
(Colorado appears, but as the *away* team at Georgia Tech). The committed golden's predictions payload
hashes **identically** across the fix (`85442a791bc395bfed830d31e929eccf72c52af7ad5f329c303b5f1808b8ee41`),
so the artifact was correctly left alone per its own lifecycle rule.

**Determinism re-verified while measuring:** a shared `PredictionEngine` and a fresh instance per game
produce **identical results across all 330 games**, and repeated shared runs are byte-stable — so
`build_predictions`' single-instance reuse over a slate carries no order dependence.

### Why NOT option (d), accept-dormant — the A1 precedent does not transfer

Recorded verbatim per owner ruling:

> **Dormancy-as-design covers absent inputs, never broken joins.**

A1 was accepted dormant because its **input is a placeholder** — `total_games` is structurally 0, so
no threshold could make the factor meaningful and "fixing" it would mean inventing a data source days
before the freeze. A6 is the opposite: **the data is present and correct**, and the only fault is a
unit conversion at the boundary between two individually-correct halves. Declining to fix it would
not be honest dormancy — it would be knowingly shipping a ratified coefficient that cannot fire.

### Derived-artifact propagation — `data/projections/` regenerated

The fix changes the **matchup pricer**, not only the contrarian factor: `model_spread` moves for
every game played at a high-altitude venue, and that flows into the committed weekly projection
artifact. `verify-phase-2`'s reproduce-from-snapshot check caught the staleness (**17 of 138 teams**
differed — exactly those playing at or against Colorado/BYU/Utah), and `data/projections/2026_week_01.json`
was regenerated through the pipeline writer.

This is the **documented precedent repeating**: a calibration change that alters the pricer must
regenerate `data/projections/`, and only the full six-target verify sweep surfaces it — `make test`
and `verify-phase-3` were both green while the artifact was stale. Recorded again here because it has
now bitten twice (first the 3b `travel_cap` change).

### Regression pins added

`tests/test_schedule_intel.py` — a high-altitude venue (~7,198 ft) must **clear** the ratified
threshold and produce `altitude_value`; a sea-level venue must **not** clear it (guards against a
blanket-fire regression); a neutral-site game yields no acclimation edge however high the venue; and a
venue with no elevation yields **`None`, never `0.0`** (a fabricated "sea level" would violate binding
principle #4). These are the checks that would have caught the original defect.

### Venue coverage — investigated, NOT a defect (ruling item 9, second half)

The PR-#19 note that "venue data covers 68 of 138 FBS teams, and the five highest-altitude programs
are absent" was **a misreading, corrected here.** The committed registry artifact `data/registry/fbs_teams_2026.json` holds **all 138 FBS teams with
locations (132 with elevation)** — reproducible from the repo, no live pull needed —, including Air Force (6,643 ft), Wyoming (7,218 ft), Colorado State,
New Mexico and Utah State. The snapshot builds `teams`/`venues` over `get_all_tracked_teams()` — *"the
tracked **P4 + independents** slate"* = SEC 16 + Big Ten 18 + ACC 17 + Big 12 16 + Notre Dame =
**exactly 68**, which is **SPEC §5.5's specified scope**, asserted by the season-start
`validate_membership_counts()` check. The five programs are Mountain West / non-P4 and are **correctly
out of scope by design** — neither a fetch gap nor a join defect. **No action; scope working as
specified.**

**Denominator correction (affects A4 and the B-batch as recorded):** `both teams tracked = 330`, which
is **exactly 3c.5's "330 real 2026 FBS-vs-FBS games."** The A4/B measurements were reported over a
**734**-game FBS-vs-FBS basis that included 404 games involving untracked teams carrying
`_empty_team()` honest-missing data. Re-measured on the correct 330-game tracked basis: p50 rises
0.0244 → 0.0468 and mean 0.0483 → 0.0551, but **the maximum is identical (0.2338) and zero games clear
0.5 or 0.75 on either basis.** Every A4 and B-batch conclusion therefore stands unchanged; only the
stated denominator was wrong. 3c.5's basis was right all along.
