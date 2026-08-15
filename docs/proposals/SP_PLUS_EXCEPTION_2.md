# SPEC §3.1 Exception 2 — CFBD published 2026 SP+ ratings

**Lifecycle:** PROPOSED — awaiting owner ratification. Nothing is committed to `docs/SPEC.md`, no
tag has moved, no PR is open. On ratification the content of §5 moves into `docs/SPEC.md` §3.1 and
`docs/CALIBRATION_LOG.md`, and this file is deleted at the next phase/session boundary.

**Measured:** 2026-08-14, on branch `rehearsal/sp-plus` cut from `origin/main` @ `679eadf9`.
**Author:** rehearsals session. **Ratifier:** owner. **Tag:** owner-cut (§7).
**Revision 2** (2026-08-14): tier mechanism measured (§4.10), PR artifact list completed and the
provenance-test CI question answered (§4.11, §6), harness committed (§6.8), Aug-18 expectation
corrected (§4.12).

---

## 1. Trigger

`sp_watch` fired on the scheduled freeze-integrity run **2026-08-14 08:27 ET** (run
`31800413579`), reporting `sp_ratings` **0 → 139 rows** against the Exception-1 baseline. Issue
**#42** opened, labels `stage:freeze` + `pipeline-transition`; the job stayed **green**, exactly as
D33 requires. This is the probe doing its job, not a defect.

SPEC §3.1 Exception 1 closed with *"`Sandwich` did NOT wake and will not until preseason SP+ ranks
publish specifically."* They have published.

## 2. Method — three vehicles, so SP+ is isolated from ambient drift

The week-1 snapshot rebuild refreshes **all seven** fetch groups, not just SP+. A bare before/after
would therefore conflate the two. Three vehicles were measured:

| | Vehicle |
|---|---|
| **A** | pinned `v2026-frozen-2` tag-time vehicle — the ratified "before" |
| **B** | rebuilt 2026-08-14 snapshot with `sp_ratings := {}` — **control**: drift *without* SP+ |
| **C** | rebuilt 2026-08-14 snapshot as-is — the "after" |

`A → B` = ambient drift. **`B → C` = SP+'s isolated contribution.**

Every engine call is wrapped in `scripts.slate_fingerprint.engine_reads(bundle)`, per D29's recorded
trap: without it, enumeration is redirected but **pricing still reads disk**, giving a split read
that looks correct and is not.

Keys are read **strictly** — a missing key raises rather than defaulting. Exception 1's first draft
recorded `0.0000` from a silent `.get()` on a key that did not exist; that failure mode is
structurally excluded.

**Cross-checks performed:** vehicle A's fingerprint independently re-derives to the committed
constant `1c5187eb…0434` / 338 games; the pinned vehicle's own SHA-256 (`12df953d…90d7`) matches
`store.py`; the lean-split arithmetic reconciles against the per-game direction-transition counter
(§4.3); the tier arithmetic reconciles against the per-game transition matrix (§4.10).

## 3. Measured delta

| | **A** `v2026-frozen-2` | **B** rebuilt, SP+ removed | **C** rebuilt, SP+ live |
|---|---|---:|---:|
| behavioural fingerprint | `1c5187eb…0434` | `50a114a7…c375` | **`b9c00a94…2532`** |
| tracked-slate games | 338 | 338 | 338 |
| `sp_ratings` teams | 0 | 0 | **138** |
| `returning_production` teams | 136 | 136 | 136 |
| **manifest coverage** | **63.3%** (358/566) | *n/a — see note* | **75.3%** (426/566) |
| lean home / away / neutral | 198 / 33 / 107 | 198 / 33 / 107 | **205 / 67 / 66** |
| confidence tier A / B / C | 322 / 6 / 10 | 322 / 6 / 10 | **297 / 10 / 31** |
| `NO_BET` | 338 of 338 | 338 of 338 | **338 of 338** |
| max \|`edge_size`\| (vehicle) | 0.3156 | 0.3156 | 0.3156 |
| max \|`edge_size`\| (real-lined) | 0.1403 | 0.1403 | 0.1403 |
| games with non-zero `edge_size` | 231 | 231 | **272** |
| Σ \|`edge_size`\| | 20.1633 | 20.1633 | **23.8510** |
| distinct `edge_size` values | 36 | 36 | **55** |
| Σ `model_vs_market_gap` | 196.34 | 195.74 | **130.08** |
| max `model_vs_market_gap` | 19.94 | 19.94 | **11.98** |
| `Sandwich` games firing | 0 | 0 | **114** |
| preseason prior source (team-slots) | `returning_production` 676 | `returning_production` 676 | **`sp+` 676** |

*Coverage note:* B is an in-memory control; `manifest.json` is not recomputed for it, so it has no
coverage figure of its own. A's is read from `v2026-frozen-2:data/snapshots/2026_week_01/manifest.json`.
**The entire +68 fields is `sp_rating` (0 → 68); every other field group is unchanged**
(`advanced_stats` 0→0, `coaching` 68→68, `info` 68→68, `returning_production` 68→68, `schedule`
68→68, `stats` 0→0, `venue` 68→68) — so the coverage rise is attributable to SP+ alone.

**Slate membership verified by identity, not arithmetic:** 0 games entered, 0 left. `A`, `B` and `C`
carry the identical 338-game tracked slate. SP+ changes no game's membership.

## 4. Findings

**4.1 — `Sandwich` wakes. Measured from activation output, not inferred from row count.**
`_sandwich_spot` (`data/schedule_intel.py:217`) keys on `sp_ratings[opponent]["ranking"]` against
`_RANKED_THRESHOLD = 25`, returning `None` when no adjacent opponent's strength is known — which is
why it was dormant at 0 rows. The normalizer emits `ranking` (`data/normalize/cfbd.py:154`), and the
measured payload carries it for **138 of 138 teams**, non-null, range 1–138, with exactly **25 teams
at rank ≤ 25**. Result: **`Sandwich` fires on 114 of 338 tracked games (33.7%)** at the ±1.0
coefficient. Had CFBD served `ranking: null`, `_int()` would have yielded `None` and Sandwich would
have stayed dormant against a fully-populated table. It is populated. It fires.

**4.2 — The larger structural change is the prior source, and it is total.** Every team-slot's
preseason prior flips `returning_production` → `sp+`: **676 of 676**. `preseason_prior`
(`engine/power_ratings.py:171`) prefers SP+ where present — D10 auto-activation working as designed
— but no team's base rating is now derived the way it was at the tag.

**4.3 — The lean split moves materially, which touches D27.** Away leans **33 → 67 (+103%)**;
neutral **107 → 66 (−38%)**; home **198 → 205**. Per-game transitions: `neutral→away` 23,
`neutral→home` 18, `home→away` 15, `away→home` 4 — reconciling exactly to the totals. **The
structural home:away skew falls from ~6.0:1 to ~3.06:1.** `_lean_block`'s inline "away cell is thin"
caveat was written for a ~35-game away cell; at 67 it is roughly twice as populated. Flagged, not
fixed — `analytics/` is out of scope for this exception.

**4.4 — "Max edge unchanged" is true and would be misleading alone.** Max \|`edge_size`\| is
identical to four decimals across all three vehicles because the single top game is unaffected. But
**113 games' `edge_size` moved**, non-zero edges rose 231 → 272, Σ\|edge\| rose 18.3%, distinct
values rose 36 → 55, and ranks 2–5 all moved up. Reporting only the max would repeat Exception 1's
recorded measuring error in a new form. Both figures are in the table for that reason.

**4.5 — The model moves materially closer to the market.** Σ `model_vs_market_gap` falls
**196.34 → 130.08 (−33.7%)**, maximum **19.94 → 11.98 (−40%)**. SP+ priors are better informed than
the flat/RP fallback, so the contrarian gap narrows.

**4.6 — No bet changes today. All 338 games remain `NO_BET`.** The edge ceiling is untouched and
every edge stays far below the week-1 threshold. This transition changes *characterisation*, not any
recommendation, in the preseason state.

**4.7 — Ambient drift alone also moves the fingerprint.** `A → B` moves `1c5187eb…` → `50a114a7…`
while **every** aggregate is identical. The fingerprint hashes full engine output — factor
internals, variance analysis, power ratings — so sub-aggregate drift is visible to it and to nothing
else. **The retag is required regardless of SP+.** See §4.12 for the operational consequence.

**4.8 — No gate detects any of this. Verified by experiment.** With the SP+-carrying snapshot on
disk, **`make verify-phase-3` passes in full** — frozen-vehicle SHA, the 338-game fingerprint, the
3d golden byte-identity reproduction, the L4 all-`NO_BET` assertion, and the whole suite (1038
passed / 2 skipped; the 2 skips are unrelated live-network tests). Consequences: **main's scheduled
Aug 18 rebuild will not turn CI red**, and **#42's stated consequence #2 is wrong** — *"The next
snapshot rebuild will fail `verify-phase-3`'s behavioural fingerprint correctly."* It will not, and
cannot: D29 pinned the gate to a committed vehicle precisely so the pipeline could not move it.
`sp_watch` is the only detector of this class of event. Corrected in §6.3.

**4.9 — The 139/138 discrepancy is benign, and the baseline value 139 is correct.** Run down by
identity: the 139th raw row is CFBD's **`nationalAverages`** aggregate, not a team. `_norm` drops it
correctly (it is also the single row with null `ranking`). 138 real FBS teams reach the snapshot.
`sp_watch` counts **raw API rows**, so `sp_ratings: 139` is the right baseline — recorded so a
future reader does not "fix" a non-existent off-by-one.

**4.10 — The tier shift: mechanism isolated, and it is the OPPOSITE of Exception 1's.**

Transition matrix `B → C`: `A→A 297`, `A→B 4`, `A→C 21`, `B→B 6`, `C→C 10`. **All movement is
downward and all of it leaves tier A** — 25 games, of which 21 fall to C. Reconciles exactly to
A 322→297, B 6→10, C 10→31. (A and B are per-game tier-identical, confirming the shift is SP+'s.)

Cross-tab against `Sandwich` firing:

| set | n | Sandwich-firing | % |
|---|---:|---:|---:|
| **tier moved** | 25 | **25** | **100.0%** |
| newly tier C | 21 | 21 | 100.0% |
| tier unchanged | 313 | 89 | 28.4% |
| all games | 338 | 114 | 33.7% |

**Every game that moved fires `Sandwich`; no non-firing game moved.** Firing is *necessary but not
sufficient* — only 25 of 114 firing games (21.9%) moved.

The sufficient condition, measured: for all 25 movers `variance_analysis.factors_analyzed` goes
**0 → 3** and `variance_level` goes **`insufficient_data` → `extreme` (21) / `moderate` (3) /
`strong` (1)**. Among firing-but-unmoved games, 79 of 89 remain `insufficient_data`. So `Sandwich`
activating is what makes the variance analyzer able to run at all on those games; once it runs, the
physical factors disagree (`agreement_ratio` 0.667, `coefficient_of_variation` 5.29 on a
representative mover), producing `implications: ["Extreme disagreement - avoid or minimum bet
only"]` and `recommendation.confidence: NO_CONFIDENCE`. Mean `confidence_score` on the movers falls
**0.7368 → 0.4648 across all 25 movers**, and **0.7365 → 0.4358 across the 21 that reached tier C**
(the 4 stopping at tier B sit near 0.64 and lift the 25-game mean), crossing the tier floors.

**Correction, recorded rather than quietly fixed (code-reviewer, PR #43).** Revision 3 of this file
stated "0.7365 → 0.4358" for "all 25 movers". That figure is the tier-C subset; the harness printed
both means and the wrong one was attached to the wrong population. It reached `docs/SPEC.md` and
`docs/CALIBRATION_LOG.md` — the permanent audit trail — and was caught by the reviewer
independently re-running `measure_transition.py`, which is the only reason the harness was
committed. The qualitative finding is unchanged (confidence falls from ~0.74 into the mid-0.4s on
every mover, crossing the floors either way), but *"a measured number that does not reproduce"* is
the project's own worst-failure-mode label, and this was one. **`scripts/measure_transition.py` now
emits both populations** so the ambiguity cannot recur. PR #43's commit message `c89d625` carries
the imprecise figure and is left as written — supersede, never edit.

**The coverage channel contributes nothing, and this is the decisive negative.** Manifest coverage
*rose* 63.3% → 75.3%, yet per-game `data_quality` is **unchanged to four decimals (0.8330 → 0.8330)**
for both the movers and the full slate. Exception 1's tier inversion ran through exactly this
channel — coverage 39.0% → 63.3% lifting data-availability-driven confidence (B1) — and it is
**inactive here**. Exception 2's shift runs entirely through the **variance/disagreement** channel.

Stated plainly: *SP+ did not make these games better-informed; it made their disagreement
measurable.* Confidence fell because the model can now see that its physical factors conflict, where
before it had too few active signals to tell.

**4.11 — The D29 provenance assertion cannot run during the PR that establishes it.**

Answering the runtime question directly, from the test code. `tests/test_frozen_vehicle.py:38-44`:
`_git_show` runs `git show <ref>:<path>` and **returns `None` on any non-zero exit**; the two
tag-dependent tests then `pytest.skip`:

- `test_pinned_sha256_is_the_tag_time_bytes` (`:66`) — `pytest.skip(f"git or {TAG} unavailable …")`
- `test_vehicle_bytes_equal_the_tagged_snapshot` (`:75`) — same

`TAG` comes from `FROZEN_VEHICLE_SOURCE[0]`. During the ratification PR that value is
`v2026-frozen-3`, which does not exist until after merge. **Measured, not reasoned:**
`git show v2026-frozen-3:data/snapshots/2026_week_01/snapshot.json` exits **128**, and
`_git_show(...)` returns `None`; with the tag present (`v2026-frozen-2`) it returns bytes, and all
five tests in the file **pass** today. So the mechanism is **skip-on-absent-tag**, and the repo's
2 skips today are unrelated live-network tests — these two are currently executing.

**The implication, recorded rather than smoothed:** the assertion "the pinned vehicle IS the
tag-time bytes" is **not verified by any of the nine required checks during the PR**. It becomes
verified only once the tag exists. Exception 1 had the identical window and nobody wrote it down.

**Mitigation, and it belongs in the tag procedure, not in a test change:** immediately after cutting
the tag, re-run `pytest tests/test_frozen_vehicle.py -v` and confirm **5 passed / 0 skipped**. The
daily freeze-integrity job would catch it within 24h anyway, but the point of a provenance chain is
that it is checked deliberately. Added to §7.

**4.12 — Correction to a standing expectation: Tuesday will NOT reproduce `b9c00a94…`.**

Per §4.7, ambient drift alone moves the fingerprint. Main's scheduled **Aug 18 09:17 ET** rebuild
will fetch fresh data and therefore produce a bundle whose engine output hashes to **neither**
`b9c00a94…2532` nor anything predictable. **That is correct behaviour and must not be read as a
failed confirmation of this measurement.** Expected on Aug 18: the live bundle differs; no gate
reads it (D29); nothing is wrong. The isolation this exception needed came from the control column
(vehicle B), not from a live re-run — which is precisely why the three-vehicle method exists.

**4.13 — The retag cannot be one PR. It is a two-PR sequence, and that is the precedent.**

Found by staging the full §6 change set and running the suite. With `season.json` naming
`v2026-frozen-3`, **`tests/test_frozen_status.py` fails 6 tests** — not skips. Its guard
`_skip_without_tag()` checks `frozen_tag() is not None`, which is satisfied by the *existing*
`v2026-frozen-2`, so it does not skip; it then compares the configured tag against the resolved one
and fails. That is a **merge deadlock**: the nine required checks gate the merge, the tag is cut
after the merge, and the tag cannot exist before it is cut.

**Exception 1 did not hit this because it was already two PRs — verified from tag topology, not
assumed.** `v2026-frozen-2` points at **`5f5d3ee`, the PR #34 merge commit**; `v2026-frozen` points
at `6910675`, the PR #28 merge commit. Both were cut *after* merge. `season.json` was then swept in
a **separate follow-up, PR #35 (`fix-stale-tag-references`)**. SPEC §3.1's own "nine red jobs, one
stale string" paragraph is the record of that gap being discovered.

**Measured confirmation:** with `season.json` left at `v2026-frozen-2` and every other §6 change in
place, the tag-sensitive suites run **29 passed / 2 skipped** — the 2 skips being §4.11's window.

So the sequence is **merge → tag → merge**, three owner actions, reflected in §6 and §7.

**4.14 — The committed golden must be regenerated; this is a consequence of re-pinning, not a defect.**

`tests/test_golden_byte_identity.py` reproduces `docs/examples/prediction_schema_v2_2026_week_01.json`
from `load_frozen_vehicle()`. Re-pinning that vehicle to `v2026-frozen-3` means the golden no longer
reproduces — measured diffs are exactly the prior re-source, e.g. `baylor-vs-auburn-week1.
power_rating_spread: golden=0.8 live=-3.08`. The test prescribes its own fix, and
`build_predictions.py:63` records that `--out` is **scoped outside the claim tier**, so regenerating
the golden cannot touch the claim slot or the D38 window.

**This is the one step I could not execute:** the command was refused by the session's command
classifier, correctly — `scripts/build_predictions.py` is the claim-writing entry point. Handed to
the owner in §6 rather than worked around.

**4.15 — The golden chain is three files deep, and regenerating it nearly deleted a test's coverage.**

Regenerating the prediction golden cascaded: `tests/test_phase4.py::test_grades_schema_v2_golden_record_reproduces_graded_golden`
then failed, because `docs/examples/graded_record_2026_week_01.json` is derived from it via
`grade_fixture` (a pure function — no claim path, no network). One cell moved:
`smu-vs-florida-state-week1.clv: 0.0 → 0.6`.

**Then a second test failed, and this one mattered.**
`test_graded_golden_exercises_win_loss_and_null_no_side` asserts the golden exercises a
**legitimate `clv == 0.0`** as distinct from `null` (honest-missing close). Measured after
regeneration: **no game had `clv == 0.0` at all.** Updating the assertion to `0.6` would have made
the suite green *by deleting the coverage the test exists to provide* — the "a test can pin a
defect" failure in its purest form.

The synthetic fixture's own `_note` states it is *"crafted to exercise every graded-record semantic
(win/loss/null-no-side; clv +/-/**0.0**/honest-missing close…)"*, so restoring the case maintains
its documented contract rather than altering it. One synthetic close was re-chosen:
`graded_fixture_2026_week_01.json` → `smu-vs-florida-state-week1.closing_spread: 1.6 → 2.2`.

**A correction worth recording, because it was found by measuring rather than reasoning.** The first
attempt set the close to `contrarian_spread` (2.25) and produced `clv = -0.05`, not zero. CLV keys
off **`vegas_spread`** — the line at prediction time — not the model's contrarian number. Two data
points confirm it (close 1.6 → +0.6; close 2.25 → −0.05; both `2.2 − close`). Corrected to 2.2,
which yields exactly 0.0. Coverage verified restored: `clv == 0.0` present on the named game, with
win/loss/null and ±1.0 CLV all intact.

**Status of everything else, measured:** `make lint` clean (48 files, ruff + mypy);
`verify-phase-3` passes its own checks including the new vehicle (`b50ba7ec…`) and the new
fingerprint (`b9c00a94…`); `verify-phase-2` passes after regenerating the derived exports (§6.9a).
Every `verify-phase-*` target currently fails on **one** check — "full test suite" — which is this
single golden test and nothing else.

## 5. Draft SPEC §3.1 entry — for ratification

> #### Exception 2 — 2026-08-14 — CFBD published preseason SP+ ratings; `Sandwich` activates and every preseason prior re-sources
> **New tag:** `v2026-frozen-3`, superseding `v2026-frozen-2`.
>
> **Trigger.** `scripts/sp_watch.py` detected `sp_ratings` moving **0 → 139 rows** (138 teams +
> CFBD's `nationalAverages` aggregate, which the normalizer correctly drops). D10 activates SP+ with
> **no code change**, so the frozen model's inputs changed underneath the tag. Exception 1 recorded
> that `Sandwich` would wake "when preseason SP+ *ranks* publish specifically"; they have.
>
> **Two independent activations, both D10, both measured:**
> 1. **`Sandwich` wakes.** `_sandwich_spot` keys on `sp_ratings[opponent]["ranking"]` against a
>    top-25 threshold and returns `None` when adjacent strength is unknown. `ranking` is served
>    non-null for all 138 teams (range 1–138; 25 at rank ≤ 25), so the signal resolves and fires on
>    **114 of 338** tracked games at the ratified ±1.0 coefficient.
> 2. **Every preseason prior re-sources.** `preseason_prior` prefers SP+ where present, so all
>    **676 of 676** team-slots move `returning_production` → `sp+`.
>
> **Measured delta** (`v2026-frozen-2` vehicle → 2026-08-14 rebuild, frozen engine, tracked slate),
> with an SP+-removed control isolating this exception's effect from ambient data drift:
>
> | | v2026-frozen-2 | control (no SP+) | **v2026-frozen-3** |
> |---|---|---:|---:|
> | behavioural fingerprint | `1c5187eb…0434` | `50a114a7…c375` | **`b9c00a94…2532`** |
> | tracked-slate games | 338 | 338 | 338 |
> | `sp_ratings` / `returning_production` teams | 0 / 136 | 0 / 136 | **138 / 136** |
> | manifest coverage | 63.3% (358/566) | *n/a (in-memory control)* | **75.3% (426/566)** |
> | lean home / away / neutral | 198 / 33 / 107 | 198 / 33 / 107 | **205 / 67 / 66** |
> | confidence tier A / B / C | 322 / 6 / 10 | 322 / 6 / 10 | **297 / 10 / 31** |
> | `NO_BET` | 338 of 338 | 338 of 338 | **338 of 338** |
> | max \|`edge_size`\| (vehicle / real-lined) | 0.3156 / 0.1403 | 0.3156 / 0.1403 | 0.3156 / 0.1403 |
> | games with non-zero `edge_size` | 231 | 231 | **272** |
> | Σ \|`edge_size`\| | 20.1633 | 20.1633 | **23.8510** |
> | Σ `model_vs_market_gap` | 196.34 | 195.74 | **130.08** |
> | `Sandwich` games firing | 0 | 0 | **114** |
>
> Slate membership verified **by identity**: 0 games entered, 0 left — SP+ changes no game. The
> coverage rise is attributable to SP+ alone: the entire +68 fields is the `sp_rating` group
> (0 → 68); every other group is unchanged.
>
> **On the edge figures.** The maximum is unchanged to four decimals because the single top game is
> unaffected; the *distribution* moved substantially (113 games' `edge_size` changed, non-zero edges
> 231 → 272, distinct values 36 → 55). Recording only the maximum would understate the transition.
> Every game remains `NO_BET` — the structural edge ceiling is untouched and this exception changes
> no recommendation in the preseason state. **The model moves closer to the market**: Σ
> `model_vs_market_gap` −33.7%, maximum −40%.
>
> **The tier shift, and why it is the inverse of Exception 1's.** Transitions are `A→A 297`,
> `A→B 4`, `A→C 21`, `B→B 6`, `C→C 10`: **all movement is downward and all of it leaves tier A.**
> Every one of the 25 movers fires `Sandwich` (100%); no non-firing game moved. Firing is necessary
> but not sufficient — only 25 of 114 firing games moved. The sufficient condition is that
> `Sandwich` activating makes the variance analyzer able to run at all: for all 25 movers
> `factors_analyzed` goes **0 → 3** and `variance_level` goes **`insufficient_data` → `extreme`
> (21) / `moderate` (3) / `strong` (1)**, dropping mean `confidence_score` **0.7368 → 0.4648
> across all 25 movers**, and **0.7365 → 0.4358 across the 21 that reached tier C** — the 4 that
> stopped at tier B sit near 0.64 and lift the 25-game mean. Both figures are reported because
> quoting one against the other population is how a delta table acquires a number that does not
> reproduce; `scripts/measure_transition.py` emits both.
>
> **Exception 1's explanatory lever is measurably inactive here.** That inversion ran through
> manifest coverage lifting data-availability-driven confidence (B1). Coverage rose again this time
> (63.3% → 75.3%), but per-game `data_quality` is **unchanged to four decimals (0.8330 → 0.8330)**.
> The entire shift runs through the **variance/disagreement** channel instead: SP+ did not make
> these games better-informed, it made their factor disagreement *measurable*. Confidence fell
> because the model can now see a conflict it previously had too few active signals to detect.
>
> Combined with Exception 1's 2 → 322 move, the Phase-4 calibration tables and D27's stratified
> reporting now rest on a tier distribution that has shifted twice, in opposite directions, since it
> was characterised. Carried to `docs/2027_NOTES.md` as an extension of the existing recalibration
> obligation (§8 item 7).
>
> **The lean split moved and D27's reporting inherits it**: the structural home:away skew falls
> ~6.0:1 → ~3.06:1 and the away cell roughly doubles (33 → 67). `_lean_block`'s inline "away cell is
> thin" caveat was calibrated to the old distribution. Flagged; `analytics/` is out of scope here.
>
> **No gate detects this class of event, by construction.** With the SP+-carrying snapshot on disk,
> `verify-phase-3` passes in full — vehicle SHA, fingerprint, 3d golden, L4 `NO_BET`, and the whole
> suite. D29 pinned the gate to a committed vehicle so the pipeline could not move it; the corollary
> is that an *external* input change is invisible to it. `sp_watch` is the only detector, which is
> why D33 built it. **Ambient drift alone also moves the fingerprint, so no live bundle will
> reproduce the figure above** — a live re-run is not a confirmation and its difference is not a
> fault.
>
> **Scope.** No change to `factors/`, `engine/`, or any calibration constant. This exception covers
> the model's *inputs* changing under a ratified auto-activation (D10), plus the freeze-exempt gate
> re-pinning that follows.
>
> **Vehicles are retained, never replaced.** `data/archive/frozen/` holds
> `2026_week_01_snapshot.json` (`v2026-frozen`) and `2026_week_01_snapshot_v2026-frozen-2.json`; this
> exception **adds** `2026_week_01_snapshot_v2026-frozen-3.json` alongside them. Each is the record
> of what its tag was measured against, under the append-only tier — mirroring Exception 1.

**Transient-window note — currently NOT required.** Required only if the tag is cut after
**Tue 2026-08-18 09:17 ET**, when main's scheduled predict rebuilds the committed week-1 snapshot.
Cut before then and no window exists. If it opens, the entry gains:

> **Transient window.** From 2026-08-18 09:17 ET until the retag, `main` carried a committed week-1
> snapshot with SP+ populated under `v2026-frozen-2` — a tag that no longer characterised the model.
> **No claim was written in that window** (the D38 claim gate refuses until 2026-08-22), and no gate
> could have detected it. Recorded rather than elided.

## 6. Ratification PRs — complete contents (TWO PRs, per §4.13)

**Sequence: merge PR 1 → owner cuts the tag → merge PR 2.** A single PR cannot go green (§4.13).
This mirrors exception 1 exactly (PR #34 → tag at `5f5d3ee` → PR #35 sweep). **Freeze-exempt paths
only** throughout. `code-reviewer` reviews each against this list.

**PR 1 — `exception-2/sp-plus`: everything except the tag string.** Items 1–11 below, with
`season.json`'s `freeze_tag` left at `v2026-frozen-2`. Goes green because the old tag still
resolves; `test_frozen_vehicle`'s two provenance assertions skip (§4.11).

**PR 2 — the sweep, after the tag exists.** One line: `season.json:76` → `v2026-frozen-3`. Goes
green because the tag now resolves, and `test_frozen_status`'s 6 assertions plus
`test_frozen_vehicle`'s 2 skipped ones all execute for the first time. **This PR is the moment the
retag is actually verified** — do not skip it, and do not let the weekend end between the tag and
this merge.

**Code and config**

1. **`scripts/sp_watch.py` — `BASELINE` → `{"sp_ratings": 139, "returning_production": 136}`.**
   SPEC §3.1: *"a step of the process, not housekeeping."* A stale baseline re-reports this arrival
   forever and, worse, makes the **next** genuine arrival dedupe onto issue #42.
2. **Strict comparison — arming for revisions.** `arrivals()` moves from "grew past baseline" to
   **any deviation from baseline**, so a revision *or a shrink* also arms. Closes `2027_NOTES` §8
   item 8 (*"An external source SHRINKING is unobserved"*) a season early. **Tradeoff stated, not
   buried:** CFBD row counts wobble, so this will fire on ordinary revisions; alarm volume rises and
   alarm credibility is what this project spends most carefully. Recommend accepting for the ~6
   remaining preseason weeks and revisiting in 2027.
3. **The corrected #42 issue template** — replace consequence #2 with §4.8: `verify-phase-3`
   **cannot** go red for an external input change (D29 pins its vehicle); `sp_watch` is the only
   detector; the real clock is the next Tuesday snapshot rebuild. Include §4.12's warning that no
   live bundle reproduces a recorded fingerprint.
4. **`data/snapshot/store.py`** — `FROZEN_VEHICLE` filename, `FROZEN_VEHICLE_SHA256`,
   `FROZEN_VEHICLE_SOURCE` → the `v2026-frozen-3` vehicle.
5. **`scripts/verify_phase_3.py:198`** — `_FROZEN_SLATE_SHA256` → `b9c00a94…2532`. Moves **only**
   here, inside a ratified exception with a new tag — never as a fix or convenience.
6. **`season.json:76`** — `pipeline.freeze_tag` → `v2026-frozen-3`. **PR 2 ONLY** (§4.13).
6a. **`Makefile`** — `scripts/measure_transition.py` added to `LINT_PATHS` and `TYPED_PATHS`, per
   CLAUDE.md's typed-on-new-code rule. Verified: `make lint` clean over 48 typed files.
6b. **`docs/examples/prediction_schema_v2_2026_week_01.json`** — regenerated; the pinned vehicle
   moved, so the golden no longer reproduces (§4.14). **Owner must run this one command** —
   the classifier refused it to me because `build_predictions.py` is the claim-writing entry point:
   `python scripts/build_predictions.py --week 1 --out docs/examples/prediction_schema_v2_2026_week_01.json`
   `--out` is scoped outside the claim tier (`build_predictions.py:63`), so the claim slot and the
   D38 window are untouched. `model_version` is VOLATILE and excluded from the comparison.
6d. **`docs/examples/graded_record_2026_week_01.json`** — regenerated (derived from 6b via
   `grade_fixture`), and **`docs/examples/graded_fixture_2026_week_01.json`** — one synthetic close
   re-chosen (`smu-vs-florida-state-week1`: 1.6 → 2.2) to restore the `clv == 0.0` case the golden
   is documented to exercise (§4.15). Without it the suite would have gone green by deleting a
   test's coverage.
6c. **`tests/test_sp_watch_baseline.py`** — rewritten for the deviation semantics. The old file
   asserted *silence* on a shrink, encoding the `>` behaviour as the contract; that test is
   inverted, and a companion test proves the inversion has discriminating power by re-running the
   superseded comparison as a control.

**Artifacts — the D29 provenance chain hangs on these being in the merge the tag lands on**

7. **`data/snapshots/2026_week_01/snapshot.json` + `manifest.json`** — the 2026-08-14 rebuild.
   `FROZEN_VEHICLE_SOURCE[1]` is `data/snapshots/2026_week_01/snapshot.json`, so
   `test_vehicle_bytes_equal_the_tagged_snapshot` asserts the archived vehicle equals **this file at
   the tag**. If it is not in the merge, the chain cannot close.
8. **`data/archive/frozen/2026_week_01_snapshot_v2026-frozen-3.json`** — new vehicle copy, a
   byte-identical copy of (7), **added alongside** its two predecessors, never replacing them.
9. **`data/lines/2026_week_01.json` and `data/quota/odds_2026_08.json`** — the rebuild's seeded line
   observation and its 1-credit ledger entry (**487 → 486**). Append-only tier; the snapshot commit
   stages `data/lines/` by design (PIPELINE.md §3), and leaving the quota entry out would falsify a
   measurement of a credit that was actually spent (D22/D23 addendum).
9a. **`data/ratings/2026_week_01.json` and `data/projections/2026_week_01.json`** — regenerated.
   **Measured, not assumed:** with the new snapshot staged, `verify-phase-2` failed two checks —
   `data/ratings export ... reproduces from its snapshot (D13) — weeks [1]; stale: [1]` and
   `weekly projection files exist for every built week + reproduce (§6.5, 2b)`. The 676/676 prior
   re-source changes every rating, and SPEC §3's derived-artifact invariant requires both for every
   built week — the D31 amendment-2 precedent, where omitting them would have turned `main` red.
   Regenerated via `scripts/update_ratings.py --week 1` and `scripts/build_projections.py --week 1`
   (both now stamp snapshot `87e472ff1fe3adc9`); `verify-phase-2` then passes.

**Harness and docs**

10. **`scripts/measure_transition.py`** — the harness that produced every number under ratification,
    folding in the three ad-hoc scripts. Exception 1's harness was ad-hoc and its first draft
    published wrong figures; the strict-comparison arming in (2) makes a third measurement plausibly
    imminent. Its docstring carries the three-vehicle method **and** the `engine_reads(bundle)`
    split-read warning, so the next operator inherits the trap with the tool. Verified: reproduces
    all three fingerprints and every table row exactly; `ruff` and `mypy` clean.
11. `docs/SPEC.md` §3.1 Exception 2 (§5), `docs/CALIBRATION_LOG.md`, `docs/2027_NOTES.md` §8.

## 7. Retag sweep and the owner-cut tag

**Sweep targets, named** (`season.json` is the single source of truth, D24; tests **derive** the tag,
never hardcode it): `season.json:76` · `scripts/verify_phase_3.py:198` ·
`data/snapshot/store.py:26–27,42–43` · `scripts/sp_watch.py:10,61,64`.
**Deliberately not touched:** `docs/examples/…json` and `data/archive/voided/…json` (historical;
`model_version` is in `VOLATILE`, so the golden is unaffected), and test docstrings naming old tags —
SPEC §3.1 permits prose and history to name superseded tags freely.

**Proved by running, not by grep** (condition 4): `tests/test_frozen_status.py::test_the_configured_freeze_tag_is_the_current_tag`
· `::test_no_live_code_hardcodes_a_superseded_tag_name` · `tests/test_sp_watch_baseline.py` ·
`tests/test_frozen_vehicle.py` · `make test` · every `verify-phase-*`.

**The tag is yours to cut, between the two PRs** (§4.13). The commit does not exist yet — it is the
**merge commit of PR 1**, matching where `v2026-frozen` (`6910675`) and `v2026-frozen-2`
(`5f5d3ee`) both sit. The SHA is supplied at that moment, read from `origin/main`, never inferred:

```
git fetch origin --tags
git log --oneline -1 origin/main                 # confirm == the SHA I hand you
git tag -a v2026-frozen-3 <SHA> -m "Freeze exception 2: CFBD published 2026 SP+ ratings"
git push origin v2026-frozen-3
git describe --tags <SHA>                        # expect exactly: v2026-frozen-3
```

**Then close the provenance window opened in §4.11 — this is part of the procedure, not optional:**

```
pytest tests/test_frozen_vehicle.py -v           # expect 5 passed, 0 skipped
```

Two of those five skip during PR 1 because the tag does not exist yet; this is the run that actually
asserts the archived vehicle is the tag-time bytes.

**Then merge PR 2** (the one-line `season.json` sweep). Its CI is the first run in which
`test_frozen_status`'s six tag assertions execute against `v2026-frozen-3` — so PR 2 green *is* the
proof that the sweep landed, which is precisely what SPEC §3.1's "nine red jobs, one stale string"
lesson asks for.

**Issue #42 closes via the retag path**, mirroring Exception 1 — closed by the ratified transition,
not hand-closed.

## 8. Amended rehearsal criteria — one set, all three rehearsals

Criteria **2**, **6** and **11** each assume a claim is written on the Tuesday cycle. The D38 claim
gate (`CLAIM_LEAD_DAYS = 7`; week 1 starts 08-29 ⇒ **window opens 2026-08-22**) makes that false at
R0 and R1 and true at R2. Amended once here rather than renegotiated per rehearsal.

| # | Criterion | **R0** Aug 17 | **R1** Aug 18–19 | **R2** Aug 24 |
|---|---|---|---|---|
| 1 | All three workflows conclude `success` | ✔ | ✔ | ✔ |
| 2 | Commit taxonomy: `grading:` → `snapshot:` (carrying `data/snapshots/` **and** `data/lines/`) | ✔ | ✔ | ✔ |
| **2a** | **`predictions:` commit exists and stands alone — exactly one file** | **N/A — window closed; assert NO `predictions:` commit** | **N/A — same** | **✔ REQUIRED — first real test of the stand-alone claim commit** |
| 3 | `snapshot:` precedes the predict step (else `-dirty` stamps every claim, D34) | ✔ | ✔ | ✔ |
| 4 | Every commit authored `cfb-pipeline <…invalid>` + `Run:` trailer, rendering **UNLINKED** | ✔ | ✔ | ✔ |
| 5 | No commit lands on `main` — verified by ref | ✔ | ✔ | ✔ |
| 6 | Week-1 claim slot on `main` empty | ✔ | ✔ | ✔ |
| **6a** | **…and the gate is why** | **✔ predict logs `Claim window not open yet`, stays GREEN, writes nothing** | **✔ same** | **INVERTS — window is OPEN. Predict WRITES a claim on the rehearsal branch. Assert: claim written, green, and `main`'s slot still empty because the branch is unmerged — not because the gate refused** |
| 7 | Re-dispatch idempotency: build step skips, no `predictions:` commit; a **new `snapshot:` commit is EXPECTED** regardless of Odds success | ✔ | ✔ | ✔ (skip now tested against a real claim) |
| 8 | No `pipeline-failure` issue opens; none closes | ✔ | ✔ | ✔ |
| 9 | `verify-phase-3` green throughout | ✔ | ✔ | ✔ |
| 10 | `sp_watch` verdict recorded | — | ✔ (**already fired — #42**) | ✔ |
| **11** | Cross-rehearsal diff | — | **AMENDED: `data/predictions/` is empty at both R0 and R1, so diff `data/snapshots/` + derived exports instead. Optionally produce a would-be claim under `--ignore-claim-window` with the reason recorded (D38 provides this).** | diff R1→R2 `data/predictions/` **now meaningful** |
| 12–18 | Failure-injection drill | — | — | (drill Aug 20, unchanged) |

**Two upgrades this produces.** R2 becomes the **first runtime proof of a live predict** — the gap
HANDOFF §(a) records as unproven — one day before the real one, on a branch CI refuses to merge. And
R2's claim will be stamped with the **new tag**, itself a check that the sweep landed.

**Note on timing:** if ratification lands this weekend as targeted, **all three rehearsals run under
`v2026-frozen-3`** and the §5 transient-window note stays unnecessary.

## 9. Open questions for the owner

1. **Ratify Exception 2 as drafted in §5?**
2. **Accept the strict-comparison tradeoff** in §6.2 (fires on ordinary CFBD revisions), or arm only
   past a tolerance?
3. **Amended criteria in §8 approved?** Needed before R0 on Aug 17.
4. **§4.11 — accept the mitigation as a tag-procedure step**, or do you want the provenance tests
   changed to fail-loud-on-absent-tag instead? (Recommend the procedure step: making them fail would
   red-light the very PR that must merge before the tag can exist.)
5. **§4.3 lean-split shift** touches D27's reporting calibration. Flag to 2027, or in scope now?

---

### Reproduction

Branch `rehearsal/sp-plus` @ `679eadf9` + the 2026-08-14 rebuild (uncommitted; 1 Odds credit spent,
487 → 486, ledgered). Single command, from the committed harness:

```
python scripts/measure_transition.py --group sp_ratings          # delta + mechanism + coverage
python scripts/measure_transition.py --group sp_ratings --rows   # + the 139/138 identity check
```
