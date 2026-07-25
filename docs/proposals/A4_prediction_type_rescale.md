# Proposal — A4: `prediction_type` ladder rescale (reverse-audit ledger)

> **Lifecycle.** This is a **working document**, not an authoritative record. It exists to carry a
> table-dense ratification proposal to the owner in reviewable form. **Once ratified, its content
> lives in `docs/CALIBRATION_LOG.md` (the calibration entry) and `docs/DECISIONS.md` (any decision
> it settles); this file is then redundant and may be deleted at the next phase/session boundary.**
> Nothing here is binding until the owner ratifies it. Not authoritative over `docs/SPEC.md`.
>
> **Status: RATIFIED (owner, 2026-07-25) — Option A, with two amendments.** The ratified content now
> lives in `docs/CALIBRATION_LOG.md` ("A-item dispositions" → A4 + the `predicted_edge` sub-decision),
> which is authoritative. Amendments applied there and NOT reflected in the body below: (1) the ladder
> is **correctly scaled in the bet region** and unreachable only pre-floor — the rejected rescale would
> have classified every actual bet as VERY_STRONG; (2) the 100%-NO_BET figure is the **dormant-state
> lower bound**, not a permanent property. **This file is now redundant — delete at the next boundary.**
> **Ledger item:** A4, `docs/CALIBRATION_LOG.md` "Phase-3 reverse-audit" (2026-07-09).
> **Touches:** `engine/prediction_engine.py:282-291` — freeze-bound, therefore **pre-tag**.
> **Author's recommendation:** **Option A** (do not rescale) — see §6.

---

## 1. What A4 said, and what the measurement found

The ledger recorded: *"Contrarian `prediction_type` ladder is structurally unreachable at the top —
needs 1.5–3.0-pt edges for MODERATE/STRONG/VERY_STRONG, but 3c.5 measured real edges cap ~0.2 pts.
Decision: rescale to the real edge distribution or accept the ladder collapses to
SLIGHT/CONSENSUS (and log that)."*

The measurement confirms the diagnosis but **corrects its severity in two directions** — one worse,
one that makes the proposed remedy ineffective:

1. **Worse than logged.** The collapse is not to "SLIGHT/CONSENSUS". The ladder's *lowest* contrarian
   rung, `SLIGHT_CONTRARIAN`, requires `edge ≥ 0.5` — **2.1× the entire season's maximum edge**
   (0.2338). All five contrarian rungs are unreachable; the base ladder emits `CONSENSUS_ALIGNMENT`
   for **100%** of games on both vehicles.

2. **The remedy is invisible.** `prediction_engine.py:386` assigns the ladder's output to a **local
   variable** `base_type`; `:393-394` overwrites it with `'NO_BET'` whenever the 3c.5 floors bind —
   which, at floors of 0.75–1.5 pts against a maximum edge of 0.2338, is **every game**. `base_type`
   is never persisted: it does not appear in `V2_RECORD_KEYS` (`utils/prediction_schema.py:23-31`).
   Measured on disk: **734/734** in-season and **10/10** Week-1 records carry
   `prediction_type: "NO_BET"`, a single constant.

**Consequence:** rescaling the ladder — to any boundaries whatsoever — changes **no persisted
output**. It would be a pre-tag edit to a freeze-bound file with a provably empty effect.

---

## 2. Measurement methodology

Two vehicles, per the owner's scope rider (preseason edges are near-zero by design; boundaries fit
to Week 1 alone would misclassify October).

| | Basis |
|---|---|
| **Vehicle A** — wk1 dry-run | The 10 Week-1 games carrying a real prediction-time line in the committed `2026_week_01` snapshot. |
| **Vehicle B** — in-season (the 3c.5 vehicle) | **All 734 real 2026 FBS-vs-FBS season games**, each driven at **its own week** against the committed bundle (which carries the full-season `games`, `venues`, `sp_ratings`), so `compute_schedule_intel` fires at real in-season rates. Situational/momentum dormant (no results); sentiment dormant. |

`edge_size = |contrarian_spread − vegas_spread| = |total_adjustment × multiplicative|` — independent
of the line's **value**, but requiring a line to **exist** (else the engine short-circuits to
`NO_BETTING_DATA`). Vehicle B therefore injects a placeholder line where none exists.

**That injection is proven measurement-neutral, not assumed:** the same 40 games run at injected
lines of `-3.0` and `+10.5` produce **max |Δ edge_size| = 0.000000000000**.

**Discrepancy to note:** 3c.5 records *"330 real 2026 FBS-vs-FBS games"*. This measurement enumerates
**734**, verified unique (zero duplicate `(home, away, week)` keys); the committed snapshot's entire
schedule is 734 FBS-vs-FBS games across 138 FBS teams, weeks 1–15. 3c.5's 330 was a narrower basis.
The measured maximum here (0.2338) sits slightly above 3c.5's stated 0.200 — same order of
magnitude, same conclusion, on a fuller denominator.

---

## 3. Measured edge distributions

| Vehicle | n | p50 | p75 | p90 | p95 | p99 | **max** | mean |
|---|---|---|---|---|---|---|---|---|
| **A** — wk1 dry-run (real lines) | 10 | 0.0000 | 0.0468 | 0.1150 | 0.1276 | 0.1377 | **0.1403** | 0.0346 |
| **B** — in-season, 734 games | 734 | 0.0244 | 0.0935 | 0.1179 | 0.1510 | 0.2057 | **0.2338** | 0.0483 |

The rider is vindicated by the numbers: Vehicle A's median is **0.0000** and it never exceeds
0.1403. Boundaries fit to Week 1 alone would have been fit to near-noise.

**In-season exceedance** (fraction of the 734 games with `edge ≥ x`):

| edge ≥ | 0.020 | 0.050 | 0.080 | 0.100 | 0.125 | 0.150 | 0.175 | 0.200 | 0.250 |
|---|---|---|---|---|---|---|---|---|---|
| share | 59.9% | 37.5% | 30.2% | 14.4% | 9.5% | 5.7% | 4.4% | **1.4%** | **0.0%** |

Nothing in the season reaches 0.25 pts.

**Other persisted dimensions, same run** (relevant to §5):

- `confidence_tier` — Vehicle A: all `B` (10/10). Vehicle B: **`A` 2 / `B` 405 / `C` 327**. The
  conviction dimension **varies in-season** and survives the `NO_BET` override.
- `avg_confidence` ranges 0.0000–0.9000; `primary_signals` reaches 3 in-season (max 1 in Week 1).

---

## 4. Proposed boundaries, derivation, and scale-check

**Proposed ladder — pure edge-magnitude, dropping the `avg_confidence` coupling:**

| Rung | Proposed boundary | Current boundary | Derivation |
|---|---|---|---|
| `VERY_STRONG_CONTRARIAN` | `edge ≥ 0.200` | `primary ≥ 2 and edge ≥ 2.5` | ≈ in-season p99 (0.2057); the top ~1% tail |
| `STRONG_CONTRARIAN` | `edge ≥ 0.125` | `edge ≥ 3.0 or (edge ≥ 2.0 and conf ≥ 0.7)` | just above p90 (0.1179) |
| `MODERATE_CONTRARIAN` | `edge ≥ 0.075` | `edge ≥ 1.5 or (edge ≥ 1.0 and conf ≥ 0.6)` | between p50 and p75 (0.0935) |
| `SLIGHT_CONTRARIAN` | `edge ≥ 0.025` | `edge ≥ 0.5` | ≈ in-season median (0.0244) — below it the model effectively agrees with the market |
| `CONSENSUS_ALIGNMENT` | otherwise | otherwise | — |

**Why not pure quantile anchors.** Anchoring each boundary exactly on p50/p75/p90/p99 (0.025 /
0.095 / 0.120 / 0.205) was tried and **rejected on measurement**: the distribution is lumpy, so
rounding to convenient values moves large mass across boundaries — it yields `MODERATE` at **4.9%**
and `SLIGHT` at **33.8%**, a badly unbalanced set for attribution. The boundaries above are
quantile-*informed* but chosen so every bucket stays populated enough to compute a season ATS%.
This is stated rather than hidden: the derivation is principled, not fitted, and the tuning that was
done was for bucket adequacy, never for an outcome.

**Dropping the `avg_confidence` coupling** implements the owner's rider directly: `prediction_type`
(edge magnitude) and `confidence_tier` (conviction) are **deliberately distinct dimensions**. The
current ladder conflates them (`edge ≥ 2.0 and conf ≥ 0.7`); the proposal separates them cleanly so
2027 cannot "deduplicate" one into the other.

### HFA scale-check (the ×HFA test, against the ratified ~2.5-pt HFA — D9)

| Rung boundary | pts | **as % of ratified HFA** |
|---|---|---|
| `VERY_STRONG` | 0.200 | **8.0%** |
| `STRONG` | 0.125 | 5.0% |
| `MODERATE` | 0.075 | 3.0% |
| `SLIGHT` | 0.025 | 1.0% |
| *(season max observed edge)* | *0.2338* | *9.4%* |

**The whole ladder lives inside ~9% of one home-field advantage.** This passes the scale-check in the
sense that every magnitude is small and none is unbounded — but it also surfaces an honesty problem
the boundaries cannot fix: a rung named `VERY_STRONG_CONTRARIAN` denotes a disagreement with the
market of roughly **one-twelfth of home field**. The *labels* are semantically inflated relative to
the quantities they now describe. Renaming them is **out of scope** for A4 (it would ripple into
`analytics/calibration_evidence.py`'s `by_prediction_type` tables, the v1→v2 converter, and the 2025
archive's stored values) — flagged here for the record, not proposed.

---

## 5. Re-run evidence — type distribution under the new ladder

Both vehicles, current vs proposed ladder, computed from the captured
(`edge_size`, `avg_confidence`, `primary_signals`) triples:

**Vehicle A — wk1 dry-run slate (n = 10)**

| Rung | Current | Proposed |
|---|---|---|
| `VERY_STRONG_CONTRARIAN` | 0 (0.0%) | 0 (0.0%) |
| `STRONG_CONTRARIAN` | 0 (0.0%) | 1 (10.0%) |
| `MODERATE_CONTRARIAN` | 0 (0.0%) | 1 (10.0%) |
| `SLIGHT_CONTRARIAN` | 0 (0.0%) | 2 (20.0%) |
| `CONSENSUS_ALIGNMENT` | **10 (100.0%)** | 6 (60.0%) |

**Vehicle B — in-season, 734 real FBS-vs-FBS games (n = 734)**

| Rung | Current | Proposed |
|---|---|---|
| `VERY_STRONG_CONTRARIAN` | 0 (0.0%) | 10 (1.4%) |
| `STRONG_CONTRARIAN` | 0 (0.0%) | 60 (8.2%) |
| `MODERATE_CONTRARIAN` | 0 (0.0%) | 152 (20.7%) |
| `SLIGHT_CONTRARIAN` | 0 (0.0%) | 132 (18.0%) |
| `CONSENSUS_ALIGNMENT` | **734 (100.0%)** | 380 (51.8%) |

Monotone-decreasing conviction with every bucket populated; the `VERY_STRONG` tail is thin (10 games)
by design — it is the top 1%.

### ⚠ The decisive caveat on this table

**The "Proposed" column never reaches disk.** It is the value of `base_type` *before*
`prediction_engine.py:393-394` overwrites it. Because the 3c.5 floors (0.75–1.5 pts) bind on every
game at these edge magnitudes, the persisted `prediction_type` remains `NO_BET` for **734/734** and
**10/10** games under the proposed ladder exactly as under the current one. The re-run evidence the
owner asked for is presented in full above — and what it demonstrates is that the rescale is
**correct in isolation and inert in situ**.

---

## 6. Options

| | Engine change | Serves the 2027 `reasoned`→`measured` obligation | Cost / risk |
|---|---|---|---|
| **A — recommended** | **none** | ✅ via `predicted_edge` bucketing in freeze-exempt `analytics/` | Raise `predicted_edge` persistence precision (§7); log the collapse in CALIBRATION_LOG. No freeze-bound edit. |
| **B** | rescale per §4 | ✅ same as A (ladder still never persisted) | A provably no-op edit to a freeze-bound file, frozen for the season. |
| **C** | rescale **+** persist `base_type` as a new record field | ✅ | Schema amendment to the **pinned** `V2_RECORD_KEYS` — contradicts **D22 consequence f1** ("`V2_RECORD_KEYS` and the v2 golden file do NOT change"); needs golden + parity + fixture updates and its own ratification. |

**Recommendation: Option A.** The conviction dimension is not lost — it is already persisted in
*better* form than a frozen discrete ladder:

- **`predicted_edge`** — continuous; the exact quantity the ladder discretizes.
- **`confidence`** (4 dp) and **`confidence_tier`** — measured above as genuinely varying in-season
  (A 2 / B 405 / C 327).
- **`no_bet_reason`** — which floor bound (e.g. `"edge 0.00 below threshold 1.50"`).

Attribution can bucket by `predicted_edge` quantiles entirely inside freeze-exempt `analytics/` — no
engine change, no schema change, and **re-tunable after the tag** as real edges accrue. A frozen
discrete ladder could never be re-tuned. Under Option A the ladder is documented as superseded-in-
effect rather than edited.

---

## 7. Sub-decision surfaced by this measurement — `predicted_edge` precision

`utils/prediction_schema.py:78` persists `predicted_edge` as `_round(edge_size, 2)`. Over an observed
range of **[0, 0.2338]** that leaves ~24 distinct values: the in-season median (0.0244) collapses to
`0.02`, and the Week-1 file already shows `predicted_edge: 0.0` with a maximum of `0.14`.

Under Option A, `predicted_edge` **becomes the primary attribution dimension** — so quantizing it to
2 dp discards most of the signal 2027 depends on. **Proposed: 4 dp.**

Freeze-exempt (`utils/`), but it changes the v2 golden example and the parity test, so it is its own
small ratification. Owner to say whether it rides in the ledger PR or lands separately.

---

## 8. Draft `CALIBRATION_LOG.md` entry (Option A wording)

> ### A4 — Contrarian `prediction_type` ladder: collapse ACCEPTED and logged (not rescaled) — **PROPOSED**
>
> **Evidence class: `measured`** (model-independent in the relevant sense: the edge distribution is a
> deterministic property of the frozen model over the real 2026 schedule, not an outcome-fitted
> quantity, and it is **not** derived from the Bug-#7-contaminated 2025 archive tables).
>
> The ladder at `engine/prediction_engine.py:282-291` requires `edge ≥ 0.5` for its lowest contrarian
> rung. Measured over **734 real 2026 FBS-vs-FBS games** driven at their own week with real
> schedule intel, the edge distribution is p50 **0.0244**, p90 **0.1179**, p99 **0.2057**, max
> **0.2338** (wk1 dry-run, 10 games with real lines: p50 0.0000, max 0.1403). The lowest rung sits at
> **2.1× the season maximum**, so the base ladder emits `CONSENSUS_ALIGNMENT` for 100% of games.
>
> This is **moot in persisted output**: `base_type` is a local overwritten by the `NO_BET` verdict
> (`:393-394`) whenever the 3c.5 floors bind, which at these magnitudes is every game. Measured:
> **734/734** in-season and **10/10** wk1 records persist `prediction_type: "NO_BET"`. `base_type`
> is absent from `V2_RECORD_KEYS`.
>
> **Disposition: accept the collapse; do NOT rescale.** A rescale (candidate boundaries
> 0.200/0.125/0.075/0.025, ≈ p99/p90/p50–p75/p50, yielding 1.4%/8.2%/20.7%/18.0%/51.8% in-season)
> was measured and is **correct in isolation but inert in situ** — it would be a frozen-for-the-season
> edit to `engine/` with no observable effect. The conviction dimension is instead carried by the
> already-persisted continuous `predicted_edge` (see the precision entry) plus `confidence_tier`
> (measured in-season: A 2 / B 405 / C 327), bucketed by freeze-exempt `analytics/` attribution and
> therefore re-tunable post-tag as real edges accrue.
>
> **Scale-check (×HFA, D9 ~2.5 pts):** the entire measured edge range is ≤ **9.4% of HFA**; the
> candidate top rung sits at 8.0%. Recorded so 2027 reads these rung labels at their true magnitude —
> `VERY_STRONG_CONTRARIAN` would denote ~1/12 of home field. The labels are semantically inflated
> relative to the quantities; renaming is out of scope here.
>
> **For 2027 — do NOT "deduplicate" these dimensions.** `prediction_type` (edge magnitude) and
> `confidence_tier` (conviction) are **deliberately distinct**. This season they look redundant only
> because `prediction_type` is a *constant* (`NO_BET`) while `confidence_tier` *varies* — that
> asymmetry is the 3c.5 floors working as designed (L4, "erring quiet is deliberate"), not evidence
> that one field is surplus.

---

## 9. What the owner is being asked to rule

1. **A4 disposition — Option A, B, or C** (§6). Recommendation: **A**.
2. **`predicted_edge` precision** — 2 dp → 4 dp (§7): in the ledger PR, or separately?

Nothing in this proposal has been implemented. `engine/prediction_engine.py` is untouched.
