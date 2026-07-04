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

*Phase 3 will add the calibrated factor-weight / activation-threshold / confidence-tier
entries here, each with 2025 evidence, under the same propose→approve rule.*
