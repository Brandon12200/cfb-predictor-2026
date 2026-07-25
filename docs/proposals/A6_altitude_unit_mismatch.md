# Proposal — A6 (late A-class): `Altitude` never fires — metres compared against a feet threshold

> **Lifecycle.** Working document, not an authoritative record. **Once ratified, its content moves to
> `docs/CALIBRATION_LOG.md` and this file is deleted at the next phase/session boundary**, with the
> other `docs/proposals/` files. Not authoritative over `docs/SPEC.md`.
>
> **Status:** PROPOSED — awaiting owner ruling (§6). **Nothing has been fixed.**
> **Origin:** B-batch ruling item 9 (owner, 2026-07-16) — "investigate before the tag; if a bug, it's
> a late A-class item and gets the full treatment."
> **Class:** the *silently-never-fires* family — same shape as **A1**, third occurrence overall.
> **Touches:** `factors/physical_coefficients.py` (freeze-bound) and/or the venue normalizer →
> **pre-tag**.

---

## 1. The finding

`altitude_points()` (`factors/physical_coefficients.py:81-87`) compares a venue's elevation against
the ratified 3b.1 constant `altitude_threshold_ft = 4000.0`:

```python
elev = home_intel.get("altitude")
if elev is not None and elev >= cfg.altitude_threshold_ft:
    return cfg.altitude_value
```

`home_intel["altitude"]` comes from `data/schedule_intel.py:115` — `game_venue.get("elevation")`,
passed straight through from the snapshot's venue records.

**Those elevations are in metres, not feet.** Verified against ground truth:

| Venue | Snapshot `elevation` | × 3.28084 | Real elevation | Verdict |
|---|---|---|---|---|
| Colorado (Boulder) | 1634.04 | **5,361 ft** | ~5,328 ft | **metres** |
| BYU (Provo) | 1412.10 | **4,633 ft** | ~4,600 ft | **metres** |
| Utah (Salt Lake City) | 1411.54 | **4,631 ft** | ~4,600 ft | **metres** |
| Alabama (Tuscaloosa) | 70.05 | 230 ft | ~230 ft | **metres** |

The **maximum elevation value in the entire dataset is 1634.04**, and the threshold is `4000.0`. The
comparison `elev >= 4000` is therefore **false for every venue, in every week, for the whole season**.
`Altitude` fires **0/734** — not because no stadium is high, but because the units don't match.

This is a ratified 3b.1 coefficient (`altitude_value = 1.2`, `altitude_threshold_ft = 4000.0`)
silently neutered by a comparison that cannot be true — structurally identical to **A1**
(`HeadToHeadRecord` threshold == output max) and to the same family the ledger has now hit three
times.

## 2. Impact if corrected

| | |
|---|---|
| Venues clearing 4,000 ft once converted | **3** — Colorado (5,361), BYU (4,633), Utah (4,631) |
| Non-neutral home games at those venues | **17 of 734 (2.3%)** |
| Points at stake per affected game | `altitude_value` **1.2** pts ≈ **48% of the ratified ~2.5-pt HFA** |

Small in frequency, large in per-game magnitude — 1.2 pts is ~5× the season's *maximum observed edge*
(0.2338). On those 17 games it would be the single largest physical contribution in the model.

## 3. ⚠ Secondary finding — venue coverage is 49%, and the highest-altitude programs are missing

The venue dataset holds **68 of 138 FBS teams (49%)**. Absent entirely:

**Air Force (~7,258 ft) · Wyoming (~7,220 ft) · Colorado State · New Mexico · Utah State**

These are the five best-known high-altitude programs in the sport — Air Force and Wyoming are the two
highest venues in FBS, both materially higher than Colorado. So **even after a unit fix, altitude
would be measured on a population that excludes the strongest cases.**

This also caps `TravelBurden` (which needs venue coordinates and fired 152/734): roughly half of all
matchups cannot compute travel distance or time-zone crossings at all. That is honest-missing and
correctly handled — but it means two of the four LIVE physical factors are running on half a slate.

**Not proposed for a pre-tag fix** (it is a data-coverage issue in `data/`, freeze-exempt, and
enlarging the venue set before the tag would change physical signal on an unmeasured population).
Recorded here so it is a known limitation rather than a later surprise.

## 4. Root-cause note — where the unit is wrong

The defect is a **contract ambiguity**, not a typo: nothing in the snapshot schema states the unit of
`venues[*].elevation`. CFBD returns metres; the constant was named `_ft` and reasoned in feet at 3b.1
(4,000 ft is the conventional "high altitude" line in sports-science literature). Both halves are
individually sensible; only the join is wrong.

## 5. Options

| | Change | Freeze-bound? | Notes |
|---|---|---|---|
| **(a) Convert at the boundary** — normalize `elevation` to feet where venues are ingested, leave the ratified constant untouched | `data/normalize/` (+ snapshot rebuild) | **No** — `data/` is freeze-exempt | Keeps the ratified 3b.1 number exactly as ratified; fixes the units where the unit is actually known. **Recommended.** |
| **(b) Convert at the comparison** — `elev * 3.28084 >= threshold_ft` in `altitude_points()` | `factors/` | **Yes** | Smallest diff, but edits a frozen-path file and leaves the ambiguous field unlabelled for every future consumer |
| **(c) Re-express the constant in metres** — `altitude_threshold_m = 1219.2` | `factors/` | **Yes** | Changes a ratified constant's value and name; worst audit-trail outcome for the same effect |
| **(d) Accept dormant** — log `Altitude` as never-firing for 2026, like A1 | none | — | Defensible on the A1 precedent, but here the data is *present and correct* and the fix is a unit conversion, not new signal. A1 was accepted dormant because its input was a placeholder; that reasoning does not transfer |

**Recommendation: (a).** It fixes the defect in freeze-exempt code, leaves the ratified 3b.1 constants
byte-identical, and puts the unit where it belongs — on the data contract. It should be paired with:

- an explicit **unit annotation in `docs/SCHEMA.md`** for `venues[*].elevation` (feet after
  normalization), so the ambiguity that caused this cannot recur; and
- a **regression test** pinning that a known high-altitude venue clears the threshold and a sea-level
  venue does not — the check that would have caught this originally.

Whichever option is chosen, it **changes model output on 17 games** and is therefore a pre-tag
calibration-affecting change requiring individual ratification — which is why nothing has been
implemented.

## 6. What the owner is asked to rule

1. **Is A6 fixed or accepted dormant?** If fixed: **option (a)**, (b), or (c)? *(Recommended: (a).)*
2. **The 49% venue coverage** (§3) — accept and log as a known 2026 limitation [recommended], or
   expand the venue set before the tag?
3. If fixed, confirm the **SCHEMA unit annotation + regression test** ride with it.

---

## Appendix — Sandwich (item 9's other half): **honest input absence, NOT a bug**

`Sandwich` also fires 0/734, but the cause is entirely different and requires no action:

- `_sandwich_spot()` (`data/schedule_intel.py:158-172`) reads each adjacent opponent's SP+ `ranking`
  and returns **`None` when no adjacent opponent's strength is known** — honest-missing by design
  (binding principle #4). `sandwich_points()` treats `None` as no signal. **The logic is correct.**
- The snapshot's `sp_ratings` is **empty (0 entries)** — CFBD had not published 2026 preseason SP+ at
  the 2026-07-03 build. `returning_production` is likewise empty.
- **No wiring or field-name defect:** `normalize_sp_ratings()` (`data/normalize/cfbd.py:102-118`)
  emits exactly the `ranking` key `_sandwich_spot` reads. The names match.
- **This state is already ratified and documented** — **D10** says the prior is *"robust to SP+
  staying empty at freeze; auto-activates when CFBD posts either source — **data, not code**"*, and
  the empty-preseason state is recorded in `docs/CODE_AUDIT.md:209`, `docs/DECISIONS.md:127`, and
  `docs/PHASE2_NOTES.md:28,51`.
- **Auto-resolves:** the Phase-5 pipeline rebuilds the snapshot weekly, so `Sandwich` begins
  evaluating as soon as CFBD posts SP+ — no code change, exactly as D10 designed.

**Disposition: log as honest input absence in the B5 entry; no action.** The distinction matters —
`Altitude` is a defect that would have stayed silent all season; `Sandwich` is the system behaving
exactly as ratified.
