# Pre-flight dispositions — clearing NOT-FREEZE-READY

> **Lifecycle: working document.** Not authoritative over `docs/SPEC.md`. Once ratified, its content
> moves to `docs/CALIBRATION_LOG.md` / `docs/DECISIONS.md` and this file is **deleted** at the next
> phase/session boundary.
>
> **Status: PROPOSED — awaiting owner ratification.** Covers all nine findings in
> `docs/preflight_verdict.md`. One code change is proposed (§1's dormancy); everything else is
> log-only.

---

## 1. B-1 `StyleMismatch` → **blanket dormancy for 2026** (Option 2)

### 1.1 Why dormancy rather than a per-number batch

**The internals are unearned, and B8 said so at the time.** B8's own PROPOSED text flagged
"*~20 internal branch thresholds… 3d ratified only the output range + confidence bands, not the
pre-clamp weighting*" — the ratification then covered the outer `config` dict and the `/6.0`
combination and never returned to the flag. Ratifying ~20 branch weights now would mean asserting
magnitude arguments for `×8`, `×4`, `×6`, `×1.5`, `×3`, `×4`, `×2`, `±0.3`, `±0.5` and eight
thresholds that **have never produced a single measured output** — the vehicle has
`advanced_stats` for **0 teams** (verified against the committed snapshot). That is argument-from-
vibes at ~20× scale, days before an irreversible tag, and it is exactly what the ratification
discipline exists to refuse.

**There is already a ratified precedent for this shape: `MarketSentiment` (B9).** Movement data
**is collected** into `data/lines/`, but the factor is **not wired**, and activation is deferred to
2027 so it can be calibrated against a season of real data. The owner's stated rationale —
*"activation is earned with evidence, like automation; the model characterized at the tag is the
model that runs the season"* — applies here without modification. And the parallel is exact on the
data side: **`advanced_stats` still lands in every weekly snapshot**, so 2027 inherits a full season
of real inputs and can **back-compute this factor offline** against actual outcomes before deciding
what its internals should be. Nothing is lost but a year of unjustified signal.

**Narrower alternatives were considered and rejected.** Ratifying the internals as-found (the B8
`/6.0` treatment) would extend "as-found" from *one* discrepancy to a whole surface. Rescaling them
is a calibration change with no measurement to calibrate against.

### 1.2 The two dormancy blockers — stated A1-style so 2027 cannot half-restore it

**This is the A1 lesson applied deliberately.** A1 recorded *two* independent blockers precisely so
a 2027 reader could not fix one and believe the factor restored. `StyleMismatch` gets the same
treatment:

1. **The proposed dormancy gate** — `calculate()` returns `0.0` unconditionally for 2026, with the
   reason stated inline. Removing this alone restores a factor whose internals are still unlogged.
2. **The internals remain UNRATIFIED and UNMEASURED** — the ~20 branch constants in
   `_calculate_success_rate_mismatch`, `_calculate_explosiveness_mismatch`,
   `_calculate_run_pass_mismatch` and `_calculate_havoc_mismatch` carry **no** magnitude argument in
   the log, because none could honestly be written. **Clearing blocker 1 without ratifying these is
   restoring an unlogged calibration surface**, which is the exact reverse-coverage failure the
   July shakedown existed to close.

> **⚠ For 2027 — do not "remove the dormancy" and believe the factor is restored.** Both blockers
> must clear, and the *second* is the real work: measure the internals against a season of collected
> `advanced_stats`, then ratify them per-number. The pace component (3d.2) is **separately** dormant
> and stays that way until its own bug is addressed — a third, pre-existing blocker.

### 1.3 Implementation — an honest dormant return, NOT deletion

Deletion would (a) destroy the code 2027 needs to back-compute from, (b) change the registered
factor count and the weight normalisation denominator, moving every other factor's normalized
weight and therefore **every prediction**, and (c) contradict SPEC §16.7's KEEP posture. The A1
precedent is to keep the factor registered and honestly dormant.

Proposed change, `factors/style_mismatch.py::calculate()` — a guard at the top returning `0.0`
with the dormancy reason, leaving all helper methods intact and unreferenced. `_max_output`/
`_min_output` (±1.5, ratified 3d.3) are untouched; the registry entry, the weight and the category
are untouched.

### 1.4 Proof plan — expected byte-identical, and why

**The preseason hash cannot move**, because the factor already returns `0.0` on every tracked-slate
game today: `advanced_stats` is empty for all 138 teams in the committed snapshot, and
`calculate()`'s existing guard already short-circuits on that. The dormancy makes permanent a state
the measured vehicle is already in. **If any hash moves, the premise is wrong and I stop and report
rather than regenerate anything.**

| Evidence | Expectation |
|---|---|
| Week-1 `predictions` payload SHA-256 | identical |
| Envelope hash | identical |
| 330-game tracked slate, each at own week | identical, 0 records differ |
| max &#124;Δ&#124; edge / confidence / model_spread | `0.000000000000` |
| `make test` / `make lint` | green |
| **All six** verify targets (the six-target-sweep rule) | PASS |
| Golden byte-identity (`verify-phase-3` + the suite pin) | unchanged, no regeneration |

### 1.5 The regression pin — asserts MEANING, not a stored value

Per the LARAMIE doctrine (a test can enforce a broken contract), the pin asserts the dormancy's
*physical meaning*, not that some number equals zero:

- **populated `advanced_stats` must NOT move the factor in 2026** — build a context with real,
  strongly-mismatched advanced stats (the shape that *would* produce a large value if the internals
  ran) and assert the factor still returns `0.0`. This is the load-bearing pin: it fails the moment
  someone removes the gate.
- the honest-missing case (absent `advanced_stats` → `0.0`, never fabricated) still holds;
- the ratified ±1.5 range and the registry wiring are unchanged.

---

## 2. B-2 momentum → **per-number batch, values as-found** (Option 1)

Evidence class **`reasoned`** throughout: no admissible measured evidence exists (no completed 2026
games; the 2025 archive is inadmissible per Bug #7).

**Scale-check method — the S-2 lesson applied.** S-2 found B3 scale-checking against the *category*
share rather than the factor's own weight. Every magnitude below is therefore checked against the
**true normalized weight, computed live from the registry** (raw weight sum across all 15 registered
factors = **1.5400**):

| Factor | raw | **normalized** | output range | max contribution | ×HFA (2.5 pt) |
|---|---:|---:|---|---:|---:|
| `PointDifferentialTrends` | 0.06 | **0.0390** | ±2.0 | **0.078 pts** | **3.1%** |
| `CloseGamePerformance` | 0.05 | **0.0325** | ±1.5 | **0.049 pts** | **1.9%** |

**Both factors are bounded at ≤3.1% of HFA.** Every constant below is a *fraction* of that ceiling,
which is the honest frame: these are small-signal internals, and no single one can move a spread
more than ~0.08 pts.

### 2.1 `_scale_trend_improvement` (`:154-164`)

| Constant | Value | Proposed | Argument |
|---|---:|---|---|
| strong-trend return | **1.5** | RATIFY as-found | 75% of the ±2.0 range for a ≥10-pt swing (two possessions); ≤0.058 pts, **2.3% of HFA** |
| moderate-trend return | **1.0** | RATIFY as-found | 50% of range at the ≥5-pt (one possession) step; ≤0.039 pts, **1.6% of HFA** |
| decline return | **−1.0** | RATIFY as-found, **asymmetry logged** | mirrors the moderate step, but see the finding below |
| interior divisor | **/10.0** | RATIFY as-found, **incoherence logged** | see §2.2 |

### 2.2 ⚠ The `/10.0` divisor — a finding, stated either way as asked

**It is NOT a fifth member of the point-scale-artifact family.** That family is the pre-Bug-#7
assumption that *model edges* live at ~1–5 points (3c.5 floors, A4 ladder, B1 `/5.0`, B4 CV
cutoffs). This divisor operates on a **point differential**, which genuinely is measured in points —
the input scale is real, not phantom. **Finding recorded: the family remains at four; 2027 should
still sweep for a fifth elsewhere.**

**But it has its own defect, measured:**

| input `improvement` | output |
|---:|---:|
| 4.99 | **0.499** |
| 5.00 | **1.000** |
| −4.99 | −0.499 |
| −5.00 | **−1.000** |

1. **A 2× discontinuity at the ±5 boundary.** A 0.01-pt change in input doubles the output. The
   linear interior (`/10.0`, spanning only ±0.5) never meets the step values it sits between — the
   divisor and the thresholds were evidently chosen independently.
2. **Asymmetry:** positive trends reach **+1.5**, negative trends cap at **−1.0**. A team declining
   is scored two-thirds as strongly as a team improving, with no stated rationale.
3. **The ±2.0 output range is unreachable** — the maximum this function can emit is 1.5 (+0.3
   consistency bonus = 1.8). Same "unreachable bound" family as A1 and B2, now a **third** occurrence.

**Proposed: RATIFY as-found with all three logged, NOT corrected.** Correcting any of them changes
output the moment a game is played — a calibration change days before the tag, with zero measured
basis for choosing the replacement. The magnitudes are all ≤2.3% of HFA, so the defect is real but
small. **2027 inherits a quantified, named discontinuity rather than rediscovering it.**

### 2.3 `_calculate_consistency_bonus` (`:166-180`)

| Constant | Value | Proposed | Argument |
|---|---:|---|---|
| high-consistency cutoff | **7** pts std-dev | RATIFY as-found | one possession of game-to-game spread = "consistent"; a sport-scale convention, matching `close_game_threshold = 7` already ratified in B7 |
| moderate cutoff | **14** pts | RATIFY as-found | exactly 2× the first — a stated doubling, not a fitted value |
| half-bonus multiplier | **×0.5** | RATIFY as-found | the middle band earns half of the ratified `consistency_bonus` (0.3, B7); ≤0.15 raw ⇒ **≤0.006 pts, 0.2% of HFA** |

### 2.4 `_calculate_team_clutch_performance` (`:296-311`)

| Constant | Value | Proposed | Argument |
|---|---:|---|---|
| close-game weight | **×0.8** | RATIFY as-found | close games are the clutch signal; carries 80% |
| blowout weight | **×0.2** | RATIFY as-found | complement; blowouts say little about late-game execution. **Consistent with B7's already-ratified `clutch_weights`**, where a blowout carries 0.3 of a close game's signal — same ordering, same reasoning; **inherits the set's reasoning** |
| experience-bonus divisor | **4** | RATIFY as-found | four close games saturates the sample bonus — same order as `min_close_games = 2` (ratified B7) and the 6-game window |
| experience-bonus cap | **×0.2** | RATIFY as-found | ≤0.2 of a ±1.5 range ⇒ **≤0.0098 pts, 0.4% of HFA** |

---

## 3. Should-fix dispositions

**S-1 — `experience_multiplier = 1.2` re-dispositioned DEAD.** B7 ratified it as a live "20%
amplification"; verified it appears **exactly once** in `factors/`+`engine/` — its own assignment at
`:237`. Nothing reads it; `_calculate_team_clutch_performance` hardcodes `0.2`/`4` instead.
**Joins the six dead constants, making seven.** The B7 entry is corrected in place to say DEAD, with
a note that this is the *inverse* of the false-DEAD risk B7's own method note warns about — the
first time this project ratified a dead constant as live.

**S-2 — B3's arithmetic corrected in place.** "±2.0 at weight 0.13 ⇒ ≤0.26 pts ≈ 10% of HFA" becomes
**"±2.0 at normalized weight 0.0649 ⇒ ≤0.13 pts ≈ 5.2% of HFA"**, with the cause named (the 0.13 was
the situational *category* share, not the factor's own weight) and **"conclusion unaffected and
conservative — the true figure is half the stated one"** recorded explicitly.

**S-3 — `variance_detector` residual literals logged DEAD/diagnostic-only.** One entry covering
`:180-189` (`0.7`/`0.5`), `:252` (z-cutoff `1.5`), `:308` (`inter_cat_var > 0.5` — a *different*
metric from the CV cutoffs), and `:322-349` (`bet_size_adjustment` `1.0/0.9/0.7/0.5/0.25`, the
`×0.7` dampener, the `>0.8`/`×1.1` boost). All populated, none consumed outside the file except via
the unpersisted `implications` list — **structurally** dead, no vehicle dependency.

**S-4 — `RevengeGame`'s six dead config constants logged DEAD** (`situational_context.py:203-212`):
`revenge_timeframes` (1.0/0.6/0.3), `coaching_connection_weight 0.7`, `margin_of_defeat_weight 0.3`,
`rivalry_amplifier 1.2`. Zero references, and `calculate()` is provably always `0.0` (all three
sub-estimators `return 0.0`). Same pattern B3 caught for `DesperationIndex` **in the same file**.

**S-5 — B2 completeness.** Add `PressureSituation {0.75, 3.0}` and `RevengeGame`'s `max_impact 4.0`,
both **logged inert** (3c.2 dormancy; S-4) rather than ratified as live values.

**N-1 — legend line only, history not restamped.** Add to the log's legend: *"**APPROVED** — a
resolved owner stamp used on behavior-change entries (3c.7, 3c.8); equivalent in force to RATIFIED."*
**Existing stamps are not rewritten** — restamping resolved history to match a legend would be the
tail wagging the dog.

**N-2 — `docs/CALIBRATION_EXCLUSIONS.md:59-66` refreshed.** Its "NOT excluded" section still calls
the internal formulas, CV cutoffs and confidence/edge engine "PROPOSED / decision-pending". Rewritten
to state they are now all dispositioned (B1–B10 incl. B4, A2 retired), with the section's *purpose*
preserved: these are calibration and must stay out of the exclusion list.

---

## 4. What the owner is asked to rule

1. **B-1** — `StyleMismatch` dormant for 2026, honest return not deletion, both blockers logged
   A1-style, with the meaning-asserting regression pin? *(recommended)*
2. **B-2** — ratify the eleven momentum constants as-found (§2.1, §2.3, §2.4), `reasoned`,
   scale-checked against true normalized weights?
3. **§2.2** — record the `/10.0` finding as proposed: **not** a fifth point-scale artifact (family
   stays at four), but carrying a logged 2× discontinuity, a logged asymmetry, and a **third**
   unreachable-bound occurrence — all as-found, none corrected?
4. **S-1 … S-5, N-1, N-2** as written above?
5. **Proof standard for the code change** — the §1.4 table, with the explicit commitment that **if
   any hash moves I stop and report rather than regenerate**?

On ratification: one PR — log entries, the dormancy change + pin, the full proof instrument, the
exclusions refresh — then `code-reviewer` (NO-GO binding), then the pre-flight **re-runs in full**
per the standing condition.

**Schedule:** this path is proposal → ratify → PR → re-run → tag. The code change is a single guard
with an expected-identical hash, so the PR is short. **Aug 8 holds** on my read; if the re-run
returns new blockers, that is the point at which it would not, and I will say so immediately.
