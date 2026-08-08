# 2027 notes — the drawer

Everything the 2026 season deliberately deferred, in one place, seeded at the `v2026-frozen`
F-close (2026-08-05). **Nothing here was an accident.** Each item was found, measured, argued and
consciously left — usually because fixing it days before an irreversible tag would have been worse
than carrying it. This file is the receipt.

Read alongside `docs/CALIBRATION_LOG.md` (the authoritative record of every constant) and
`docs/DECISIONS.md` (D1–D27).

---

## 0. Your charter — start here

An external reviewer reduced this project's whole audit posture to three questions. **They are the
2027 charter, and they should be asked of every factor before anything else:**

> ### 1. Does the input arrive?
> ### 2. Does it ever fire?
> ### 3. Does the tier separate?

Every internal gate this project built asked *"is this number justified?"* — and every gate passed
while three real defects sat in plain sight, because **none of them asked whether the input the
number multiplies ever shows up.** A6 (elevation in metres against a feet threshold), the
venue-timezone nulls, and the whole dormant set were all found by someone exercising the system from
outside its own checks.

**Concretely, before recalibrating anything: for each ratified coefficient, confirm the field it
consumes is non-null somewhere in a real slate, and that the factor fired at least once.** That pass
would have caught A6 in July instead of August.

---

## 1. The dormant set — with A1-style blockers

**A dormant factor is not a broken factor.** Each of these is honestly dormant by ratified decision.
**⚠ Every one has MORE THAN ONE blocker. Clearing one and assuming it is restored is the single
most likely 2027 mistake** — the A1 lesson, which is why each is written out in full.

| Factor | Blockers — ALL must clear |
|---|---|
| **`HeadToHeadRecord`** (A1) | (1) registry `activation_threshold 1.0` **equals** the factor's own `_max_output 1.0`, so it can only fire at exact saturation; (2) `data_manager._H2H_PLACEHOLDER` makes `total_games` permanently **0**, and `calculate()` returns 0.0 below `min_games_for_significance = 3`. **The data blocker is the real one** — a threshold change alone leaves it returning 0.0. Restoring it means building a CFBD coaching-H2H ingest. |
| **`StyleMismatch`** (B-1) | (1) `calculate()` returns 0.0 unconditionally for 2026; (2) its **~20 internal branch constants are UNRATIFIED and UNMEASURED** (`×8`, `×4`, `×6`, `×1.5`, `×3`, `×4`, `×2`, `±0.3`, `±0.5`, plus eight thresholds) — no magnitude argument exists in the log, because none could honestly be written against a vehicle holding `advanced_stats` for **zero** teams; (3) the **pace component is separately dormant** per 3d.2 (Bug #16). **Clearing (1) without ratifying (2) restores an unlogged calibration surface** — exactly the reverse-coverage failure the July shakedown existed to close. The 2026 implementation is preserved uncalled as `_calculate_2027_reference()` **precisely so you can back-compute it offline** against a real season of `advanced_stats`, which the snapshots now carry. |
| **`PressureSituation`** (3c.2) | Returns 0.0 unconditionally. Its original content was **fabricated** — MD5-of-team-name, a hardcoded `popular_teams` list, and a home-field term double-counting the pricer's HFA. Do not "restore" it; a real coaching-pressure signal would have to be built from scratch. |
| **`RevengeGame`** (S-4) | All three sub-estimators `return 0.0`, and its six config constants are logged **DEAD** (0 references). |
| **`MarketSentiment`** (B9) | **Dormant AND unwired for all of 2026** by ruling. Movement data **is** collected into `data/lines/` all season — so 2027 inherits a full season of real movement to calibrate against, which is the entire point. Also note: **MODIFIER-type factors ignore `self.weight` entirely** (`get_dynamic_weight` returns a flat 1.0) — a "reweight" is a no-op; calibrate its **range**. |

**Input-dormant but not decision-dormant** (they fire the moment data arrives — do not confuse these
with the above): `ExperienceDifferential` (coaching fields never populated), `Sandwich` (needs SP+
ranks; see §6), `DesperationIndex` / `PointDifferentialTrends` / `CloseGamePerformance` (need
completed games), `Altitude` (fires now — 16 of 330 — after the A6 fix).

## 2. The seven dead constants — logged, never ratified

Ratifying a value nothing reads asserts a claim the code does not make. All verified statically.

| Constant | Where | Note |
|---|---|---|
| `redzone_weight` | `style_mismatch.py` (B8) | 0 references |
| `pace_advantage_slower` | `style_mismatch.py` (B8) | 0 references |
| `recent_game_weight` | `coaching_edge.py` H2H config (B10) | 0 references |
| `max_lookback_years` | `coaching_edge.py` H2H config (B10) | 0 references |
| `conference_championship_weeks` | `situational_context.py` (B3) | 0 references |
| `desperation_multipliers` | `situational_context.py` (B3) | 0 references |
| **`experience_multiplier`** | `momentum_factors.py:237` (S-1) | **B7 originally RATIFIED it as a live "20% amplification" — it has exactly one reference, its own assignment.** The first time this project ratified a dead constant as live; the inverse of the false-DEAD risk B7's own method note warns about. |

Plus one **known state, not ratified**: `variance_detector.py:225`'s bare `0.3` — **doubly
unreachable** (its only consumer tests a category key the A3 fix renamed, *and* the outer branch
needs the dormant `MarketSentiment`).

**Method note that saved a real mistake:** a flat scan initially flagged B7's `trend_weights` /
`clutch_weights` as dead. **False positive** — they are nested dicts consumed via their parent key.
**Nested config needs the parent-key check, not a flat one.** A false DEAD in a ratification batch
would have retired live calibration.

## 3. Defect-family tallies — assume a fourth of each

Four distinct families, each with its own count. **The instruction is uniform: sweep for one more
than we found, because in every case the last one was found after we thought we were done.**

| Family | Count | Members |
|---|---:|---|
| **Never-true comparison** — a ratified constant neutered by a comparison that cannot be true | **4** | A1 (`threshold == _max_output`), B2 (`max_impact > _max_output`), the momentum unreachable `±2.0`, A6 (metres vs feet) |
| **Unreachable bound** (a subfamily of the above) | **3** | A1, B2, momentum `±2.0` |
| **Input never arrives** — the constant is right, the value it consumes is unusable as delivered | **2** | A6 (arrived but mis-scaled), venue timezone (never arrived at all). **Note the two differ in shape — look for both.** |
| **Point-scale artifact** — the pre-Bug-#7 assumption that model edges live at ~1–5 pts | **4** | 3c.5 NO_BET floors, A4 `prediction_type` ladder, B1's `/5.0` divisor, B4's CV cutoffs |
| **Found outside the audit** — real defects every internal gate passed over | **3** | A6, the venue-timezone gap, the edge-ceiling structural property |

## 4. The ceiling and the denominator — the single highest-value fix

**Measured at the tag** (reproduce with `scripts/measure_edge_ceiling.py`): the maximum attainable
`|total_adjustment|` is **1.0023** theoretical and **0.8269** on the 2026 vehicle. Against the
ratified `min_edge` ladder: **1.5 is structurally unreachable**, **1.0 is vehicle-unreachable**, and
**0.75 needs 90.7% of the entire vehicle budget pulling one way.**

**Mechanism — the dormancy share.** `_validate_and_normalize_weights` divides every factor's raw
weight by the raw sum across **all 15 registered factors (1.5400)**, dormant ones included. A dormant
factor keeps its slice of the denominator while contributing zero, so the **live** factors'
normalized weights sum to only **~69.5% of unity**. The 3c.5 ladder was ratified against an
implicitly full budget; ~30% of it is held by factors that cannot fire.

> **The single change most likely to restore the ladder's intended scale without touching any
> ratified coefficient: exclude dormant factors from the normalization denominator.** Decide this
> against 2026 attribution — and note it interacts with §1, because waking a factor changes the
> denominator for every other factor.

**Corollary — `confidence_score` is near-degenerate.** 38 distinct values over 330 games, one value
covering 30.3%, tiers **A 2 / B 318 / C 10**. It is **coarsely quantized and data-availability
driven** — B1's ratified consequence (it is in practice a data-availability score) made visible.
**Phase-4 attribution must treat `confidence_tier` as a coarse data-availability stratum, not a
per-game conviction signal.** That is charter question 3: *does the tier separate?* On this evidence,
barely.

## 5. `reasoned` → `measured` — the charter this season exists to serve

Almost every constant in `CALIBRATION_LOG` is evidence-class **`reasoned`**: argued from stated
reasoning, never fitted. That was correct — the 2025 archive's confidence→ATS and edge→ATS tables
are **Bug-#7 phantom-contaminated and inadmissible**, so there was nothing honest to fit to.

**2026 is the experiment that converts them.** Phase-4 attribution answers exactly the open entries'
questions — per-sub-signal ATS% and CLV when each factor fired — so next July reads this season's
log like a lab notebook with results pending.

**Binding constraints on that conversion:**

- **D27 — the home-lean split is mandatory.** Preseason leans run **195 home / 35 away (5.57:1)**,
  structural because `TravelBurden` and `ConsecutiveRoad` only ever penalise the visitor and
  `Altitude` only advantages the host. **CLV and ATS% must be reported split by lean side and
  against a naive always-lean-home baseline.** An unsplit headline repeats D17's failure exactly:
  it would measure how home teams did against the spread and report it as skill.
- **230 of 330 games carry a gradable lean** — NO_BET games persist hypothetical leans and are
  graded (D22), so ~70% coverage survives a season in which every preseason game is NO_BET. The 100
  neutral games are honestly unscoreable (CLV `null`, never `0.0`).
- **Read the Wilson intervals, not the point estimates.** The away-lean cell is ~35 games. A 12-point
  ATS gap on a 45-game cell is weaker than it looks — this is the 3c discipline, and it applies with
  more force to thin strata.
- **A quiet season is not a broken season.** 3c.5's ratified posture is "bets rarely" (L4). Do not
  read a low bet count as breakage; read it against §4's ceiling, which explains it.

## 6. Standing items, smallest to largest

- **SP+ and returning production were still unpublished at the freeze.** Verified live on 2026-08-03:
  `/ratings/sp?year=2026` and `/player/returning?year=2026` both returned **0 rows**, while the 2025
  equivalents returned 137/134 — the endpoints work, the data was not posted. D10 holds with no code
  change (they auto-activate when CFBD posts). **`Sandwich` goes live the moment they land**, so the
  first snapshot that carries them changes model behaviour — and will trip the slate-hash gate,
  correctly.
- **Dropped-game detector.** CFBD returned **888** games; the snapshot stores **734**. The 154
  dropped are FBS-vs-FCS (correct per §16.1 scope) — but **nothing records the count or the reason**,
  and `normalize_games`' comment claiming "the slate reconciler logs them" is not true. No tracked
  FBS-vs-FBS game is currently lost (all 138 canonical names resolve), but **there is no detector**:
  an unaliased name variant would vanish silently. Cheap fix — the count is already computable at
  build time. *(SPEC §5.5.3 wants excluded-with-reason.)*
- **Sub-field provenance.** The manifest's granularity is the **field group**, not the field:
  Northwestern reads `"venue": "registry"` — counted *present* — while four of its venue fields are
  null. The venue-timezone fallback therefore could not be recorded there, and lives in
  `docs/SCHEMA.md` and the table instead.
- **Northwestern's null `latitude`/`longitude`** — so its `travel_distance` is `None`.
  **`travel_distance` has zero consumers** in `factors/`/`engine/`/`analytics/`; display-only.
- **`cfb hypothetical` gives no hint** that `time_zones_crossed` needs `--date` (UTC offset is
  DST-dependent, so a dateless matchup honestly has no answer). A one-line CLI hint would have saved
  an investigation.
- **`main.py`'s deprecation shim retires in 2027** (D24, one release). An incomplete
  `--home`-without-`--away` invocation currently gets a bare argparse error with no migration hint.
- **`config.py`'s residual thresholds are dead** — `min_confidence_threshold`,
  `max_confidence_threshold`, `edge_thresholds`: zero consumers across `factors/`, `engine/`,
  `analytics/`, `cli/`. Left unfrozen deliberately (the file also holds live operational settings
  Phase 5 needs). Clean up in 2027.
- **`TYPED_PATHS` excludes `factors/factor_registry.py` and `engine/prediction_engine.py`.** Honest
  typing needs attributes declared on `base_calculator.py` and an annotation in `variance_detector.py`
  — two *more* frozen files. **At an unfreeze, type all four together or not at all.**
- **The rest of `factors/`/`engine/` is frozen un-linted.** Style is not behaviour; the tag froze
  code, not cosmetics.
- **B8's `/6.0` divisor** is ratified as-found with a **quantified** discrepancy: its comment says
  "normalize by total weights", the referenced weights sum to **6.5** (5.3 live), so it
  under-normalises by ~8% against its own stated intent.
- **B7's `trend_weights` are consumed POSITIONALLY** (`list(...values())[:n]`) — the key names are
  decorative, and **reordering the dict silently re-weights the factor** with no error and no test
  failure.

## 7. How to change a frozen constant in 2027

1. The tag freezes `factors/` and `engine/`; `.claude/hooks/protected_paths.py` enforces it and
   `verify-phase-3`'s **slate-hash gate** enforces the *behaviour* — including changes arriving
   through the freeze-exempt `data/` seam, which is how output moved twice in 2026.
2. An in-season output-altering change needs a **documented SPEC §3 exception entry plus a new tag**.
   **Updating the gate's constant is not the remedy** — that hides the very thing it exists to show.
3. For the 2027 rebuild proper, the freeze lifts; then every change still needs its CALIBRATION_LOG
   entry with an evidence class, a magnitude argument scale-checked against the ratified **~2.5-pt
   HFA (D9)**, and an owner ratification stamp.
4. **Scale-check against the factor's own normalized weight, never its category share** — the S-2
   lesson, which put B3's DesperationIndex check out by a factor of two.
5. **Composite blocks are audited per-number.** "The block is ratified" never ratifies the numbers
   inside it — and B7/B8 proved the corollary: ratifying a `config` dict does not cover the branch
   arithmetic in the methods it feeds.

---

## 8. Phase-5 pipeline — carry-forward from the `pipeline-adversary` audit (2026-08-07)

Enumerated against the finished pipeline before the PR. **None blocks the pipeline's own written
acceptance criteria** (`scripts/verify_phase_5.py`, `docs/PIPELINE.md`), so all are inherited
deliberately rather than fixed at the deadline. Ordered by 2027 value.

1. **Postponement blind spot on the CAPTURE side (the one with in-season consequence).**
   `scripts/fetch_lines.py` scopes each capture to the *current* week's snapshot slate, while the
   workflow resolves the week from today's date. A game postponed across a `pipeline_week` boundary
   is in no later week's slate, so it **receives no further line observations**, and
   `closing_observation` then honestly reports the last pre-postponement observation as its
   "close" — a stale close for exactly the games most likely to move. The grading side handles
   postponements correctly (`fetch_results` matches by pair across the whole season and records
   `completed_in_week`); only capture is week-scoped. Fix shape: key capture off *claims with no
   result yet* rather than off the calendar week's snapshot.
2. **CFBD spend is unguarded and the catch-up loop is unbounded.** There is no CFBD analogue to
   `data/odds_budget.py`, and `pipeline_week.gradable_weeks` returns every week with a claim, so
   the Tuesday catch-up makes one `get_games(year)` call per historical week, every week, forever
   (~15/Tuesday by season's end). Harmless against Tier-1's 5,000/mo — but that quota is **shared
   with basketball** (D5) and nothing tracks the creep. Fix shape: bound the loop to weeks with an
   open `ungraded`/`pending` remainder, and add a CFBD budget note.
3. **No season-end kill switch.** The cadence keeps firing after week 15 (`pipeline_week` clamps
   there by design). The runs are idempotent no-ops, but they are an unbounded silent tail — and
   they compound item 2.
4. **A mid-run credential revocation degrades quietly.** `SnapshotBuilder._fetch` correctly records
   each failed source as `missing` with a `fallback_reason` (binding #4, no fabrication), and
   `min_snapshot_coverage_pct` is `warn` by ratified policy — so a key revoked *between* source
   fetches yields a claim built on holes, announced only in a step-summary warning. The claim is
   honest and the coverage is recorded; what is missing is an **alert path** distinguishing "early
   season, data genuinely absent" from "credential died mid-run".
5. **No simulated-date test for the 2026-11-01 DST flip.** The mechanism is DST-immune by
   construction (fixed UTC crons anchored to EDT shift *earlier* in ET, the safe direction; the
   timing check localises to ET), so this is coverage, not a defect.

**Two of these — 1 and the direct-overwrite path in item 6 below — were independently surfaced by
both `pipeline-adversary` and `code-reviewer`.** That convergence is the signal worth remembering:
the same gap found by an adversarial enumeration *and* by a line-by-line diff review is the one to
point the failure-injection drill at first.

6. **Fixed at review, recorded because the asymmetry is the lesson:** `write_predictions` overwrote
   unconditionally while the *human* CLI path (`cli/cfb.py::_save_slate`) had refused since 4.5.
   The byte-immutable guarantee therefore held for the interactive path and not for the automated
   one — the reverse of where it matters. Now enforced at the shared seam, scoped to the claim tier.
