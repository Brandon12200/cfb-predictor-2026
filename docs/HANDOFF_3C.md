# HANDOFF → Phase 3c (temporary — delete when 3c is done)

A briefing for a fresh session with zero conversational context. Read this, then the reading list, then plan 3c. **Do not treat this as authoritative over `docs/SPEC.md`** — it points you at the truth, it doesn't replace it.

## (a) Current state
- **Branch: `main`**, clean. Everything below is merged.
- **Merged through PR #12:** Phase 3a (decomposed pricer + calibration-evidence harness), Phase 3b (physical factor layer + reweight, PR #11), and the **MarketSentiment wiring fix / Bug #7** (PR #12).
- **Gates green:** `make test` → 456 passed / 4 skipped; `make lint` clean; `make verify-phase-1`, `-2`, `-3` all PASS (3c/3d checks show PENDING in verify-3 — that's correct).
- **Phase 3 status:** 3a ✅, 3b ✅, **3c = next (unstarted)**, 3d after it.

## (b) What 3c must deliver (SPEC §7.5, lessons L2/L3/L4)
1. **Situational thresholds + confirmation (L2):** raise activation thresholds on revenge/lookahead/desperation; require a confirming factor (a physical factor or the **model-vs-market _base_ gap** — base only, never total; D15 circularity rule).
2. **`NO_BET` as a first-class prediction type (L4):** emitted when edge / confidence / variance fall below floors. Purely threshold-driven — **no weekly volume target** (§16.3). `NO_BET` games still logged + graded.
3. **Confidence calculator v2 (L3):** explicit A/B/C tiers with real separation; tiers in output + reports.
4. **Three cleanup items** (all fold into the confidence rework — see `docs/CODE_AUDIT.md` → *Consolidated 3c/3d carry-forward*):
   - `ExperienceDifferential` crashes on missing coaching data (only caught+zeroed) — add explicit `None`-handling.
   - Dormant-multiplicative-modifier activation bookkeeping: activation should key on `abs(value − 1.0)`, not raw magnitude (a dormant MarketSentiment at 1.0 is wrongly counted `activated`, diluting `avg_confidence`).
5. **Ship as a consolidated CALIBRATION_LOG batch** for owner ratification (see protocol below).

**3d still owes after 3c:** prediction schema v2 + 2025 converter + 2026 dry-run acceptance (SPEC §7). Then Phase 3 is complete → freeze prep.

## (c) Ordered reading list (why each matters)
1. `docs/SPEC.md` §7 (Phase 3 build) + §3 (Calibrated Freeze) + §14 (agentic process) + §16 (binding owner decisions) — **the authoritative plan; §3 carries the Bug #7 constraint below.**
2. `docs/DECISIONS.md` **D17 + the D17 addendum** (the 2025 model was a phantom; root cause) and **D19** (the MarketSentiment fix) — indispensable context for why 3c can't trust the archive's confidence/edge tables. Also D15 (base-gap circularity rule you'll reuse for L2 confirmation).
3. `docs/CALIBRATION_LOG.md` — the ledger; read the Phase 3b batch + the *MarketSentiment wiring fix* section; every 3c number you propose gets an entry here.
4. `docs/CODE_AUDIT.md` → *Consolidated 3c/3d carry-forward* — your cleanup checklist.
5. `factors/base_calculator.py` (activation/threshold/confidence machinery — cleanup item 2 lives here), `factors/factor_registry.py` (combination + summary stats: `primary_signals`, `avg_confidence`), `engine/prediction_engine.py` (`_calculate_contrarian_prediction`, prediction-type tiering).
6. `factors/situational_context.py` (`DesperationIndex`, `RevengeGame` — the L2 targets), `factors/coaching_edge.py` (`ExperienceDifferential` — cleanup item 1).
7. `analytics/calibration_evidence.py` + `data/archive/2025/` — the harness. **Usable only for admissible slices (see constraint) — NOT for confidence→ATS / edge→ATS tables.**
8. `scripts/verify_phase_3.py` — flip the 3c PENDING checks to real acceptance checks as you build.
9. Memory: `phase3-calibration-judgment.md` + `owner-working-style.md`.

## (d) Standing constraints (imperative)
- **Do NOT cite the archive's confidence→ATS or edge→ATS tables as measured evidence.** They are Bug-#7-contaminated (the 2025 model's whole output was a ~+1.0 constant; its confidence/edge distributions measured the bug). Every 3c entry is evidence-class **`reasoned`** unless it rests on **model-independent market data** (price-derived, like `hfa_elo`/`margin_sigma`). The monotonic-ATS%-by-tier property is a **structural sanity check on the NEW model's dry-run output**, not a 2025-evidence gate. (Ref: SPEC §3, D17 addendum.)
- **Confirming-signal rules use the BASE gap only** (`model_vs_market_gap`), never the total gap (D15).
- **No fabricated/neutral-filled data** (record `missing` + provenance); **no hardcoded team/conference names** (registry only); **no AI attribution** in commits/PRs (`includeCoAuthoredBy: false`).
- **Freeze discipline:** after tag `v2026-frozen` (~2026-08-24) `factors/`, `engine/`, weights/thresholds are immutable. 3c must land + be ratified before then.
- **A calibration change that alters the pricer must regenerate `data/projections/`** (that omission broke `verify-phase-2` on `main` this session).
- `data/predictions/`, `data/results/`, `data/archive/` are append-only (hook-enforced).

## (e) Ratification protocol
Calibration = owner-only. **Propose → pause → owner ratifies; never treat a number as final first.** One phase = one branch (`phase-3c-...`) = one PR. Present a **single consolidated CALIBRATION_LOG batch** with each entry evidence-class-labeled + scale-checked (magnitudes vs the ratified ~2.5-pt HFA). Expect **humble, reasoned tiers** — the owner bounces unlabeled or argued-from-vibes numbers. Run the **`code-reviewer` subagent on the diff before opening the PR**. Paste `make verify-phase-3` output as PR evidence.

---
*Delete this file in the 3c PR once its content is absorbed into the permanent docs.*
