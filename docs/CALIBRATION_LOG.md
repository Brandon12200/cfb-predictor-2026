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
| market (MarketSentiment) | 35% | 6% |

Biggest single factor: **MarketSentiment 35% → ByeAdvantage 10%**; physical:situational **4 : 1**.

**Why physical is set this high — the honest framing (owner):** this is *not* backing a proven
winner. Physical-dominant is **maximum allocation to the best-reasoned but unverified hypothesis**.
It is defensible because the categories it takes weight from carry **measured negative evidence**:
situational is noisy (L2) and the entire contrarian output added nothing over consensus (D17). So
the reweight is **demotion of demonstrated non-signal**, not promotion on 2025 authority — and the
weight has to live somewhere. That is the sentence 2027-us will want when judging whether 52% was
right.

**MarketSentiment 35% → 6%** (least controversial number here): 1b deleted this factor's fabricated
line-movement sim and its hashed public-betting engine; what remains runs on honest cross-book
statistics, with movement legitimately missing until slice 1.5. A factor whose main historical
inputs were fabrications should not be a third of the model. 6% additive + its multiplicative
modifier role is appropriate for what it currently is.

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

*Phase 3c/3d will add the situational-threshold / NO_BET / confidence-tier / schema entries here,
each evidence-class-labeled, under the same propose→approve rule.*
