# Venue timezone fallback — a ratified coefficient that cannot fire because an input never arrives

> **Lifecycle: working document.** Not authoritative over `docs/SPEC.md`. Once ratified, its content
> moves to `docs/CALIBRATION_LOG.md` / `docs/SCHEMA.md` and this file is **deleted** at the next
> phase/session boundary.
>
> **Status: PROPOSED — awaiting owner ratification.** Behavior-change class, data-layer, A6-adjacent.
> Found by owner testing of `cfb hypothetical`. Must land **pre-tag**, ahead of the single
> pre-flight re-run.

---

## 1. Root cause — a CFBD upstream gap, not a build defect

CFBD returns `"timezone": null` for **8 of 138** FBS venues. The *key* is present on every venue
object; only the value is null. `normalize_venue` (`data/normalize/cfbd.py:157`) does
`timezone=loc.get("timezone")` — faithful pass-through, correct honest-missing behaviour. The
normalizer and builder are both working as designed; **there was simply no table to fall back to.**

SPEC **Appendix A** (`SPEC.md:322`) already specifies the missing piece — *"Geo math (travel
distance, time zones, altitude) | Computed from CFBD venue data **+ static timezone table**"* —
and that table was never built. This proposal builds it.

**Only 2 of the 8 are in the tracked P4+independents slate:** Northwestern and Rutgers. The other
six (FIU, Hawai'i, Kennesaw State, South Alabama, UAB, UNLV) are non-P4 and **out of slate scope by
design** — the same finding shape as A6's venue-coverage investigation. One line, no action.

**Why it matters:** `travel_points` (`factors/physical_coefficients.py:74-77`) keys **only** on
`time_zones_crossed`. A null timezone means `(None or 0) - (None or 0) = 0` → the ratified
`tz_per_zone` coefficient returns `0.0` for a real cross-country trip. **Same family as A6: a
ratified coefficient silently neutered because an input never arrives.**

## 2. Measured impact (read-only, on the 330 both-teams-tracked basis)

**21 intel rows** gain a timezone. **8 of 330 tracked games move `model_spread`:**

| wk | matchup | before | after | Δ | zones |
|---|---|---:|---:|---:|---|
| 3 | USC @ RUTGERS | −3.5000 | −5.0000 | **−1.5000** | 3 east, **clamped by `travel_cap`** |
| 9 | NORTHWESTERN @ OREGON | −2.5000 | −3.7000 | −1.2000 | 2 west |
| 3 | COLORADO @ NORTHWESTERN | −2.5000 | −3.1000 | −0.6000 | 1 east |
| 4 | NORTHWESTERN @ INDIANA | −2.5000 | −3.1000 | −0.6000 | 1 east |
| 7 | NORTHWESTERN @ MICHIGAN STATE | −2.5000 | −3.1000 | −0.6000 | 1 east |
| 10 | RUTGERS @ WISCONSIN | −2.5000 | −3.1000 | −0.6000 | 1 west |
| 11 | NEBRASKA @ RUTGERS | −2.5000 | −3.1000 | −0.6000 | 1 east |
| 11 | NORTHWESTERN @ OHIO STATE | −2.5000 | −3.1000 | −0.6000 | 1 east |

**Max Δ = 1.5000 pts = 60% of the ratified ~2.5-pt HFA.**

**Every delta reproduces the ratified 3b.1 constants exactly** — `tz_per_zone = 0.6`
(1 zone → 0.6, 2 → 1.2), and 3 zones → 1.8 **clamped to `travel_cap = 1.5`**. That internal
consistency is the strongest evidence the fix is behaving as the ratified coefficients specify,
rather than introducing a new magnitude.

## 3. Design — ratified, with two flagged deviations

**Static IANA table in a new module, consumed at two points:**

- **`data/normalize/cfbd.py::normalize_venue`** — every **future** snapshot bakes the value in,
  satisfying SPEC §5.2 (*"the snapshot builder is the ONLY place fallback policy lives"*).
- **`data/schedule_intel.py`** — a read-seam resolver backfills **already-built** bundles, so the
  committed snapshot's bytes and `snapshot_id` stay untouched. This is the A6 shape
  (`elevation_feet()` at the read seam), and it works for the same reason A6 did:
  `data_manager.get_game_context` **recomputes** intel on every call and never reads the stored
  blob (`docs/SCHEMA.md:57`).

### 3.1 Why the snapshot is NOT rebuilt — evidence, not preference

- `scripts/build_snapshot.py` is a **networked** entry; the builder makes **7 live CFBD/Odds
  fetches**. A rebuild is **not byte-reproducible**.
- `snapshot_id` is a SHA-256 over the **entire** `data` block **including `venues`**
  (`data/snapshot/store.py:27-30`). Verified: filling Rutgers' timezone moves it
  `c86311adcba8c096 → 5e599a28d49f56b6`.
- Prediction / projection / ratings **envelopes embed `snapshot_id`**, so a change breaks **four
  gates**: `tests/test_golden_byte_identity.py`, `verify-phase-3` (3d), and both `verify-phase-2`
  clauses (ratings + projections).
- **Decisive:** the committed bundle was built **2026-07-03** with a preseason profile that no
  longer exists — `sp_ratings` 0, `advanced_stats` 0, `returning_production` 0, coverage **39.0%**.
  Rebuilding today is **not a venues-only delta**; it is a wholesale different artifact that would
  cascade into every value and would likely break `verify-phase-3`'s ratified all-NO_BET premise.

### 3.2 ⚠ Deviation 1 — the provenance manifest cannot record this

**Ruling 2 asked for `source=static_iana_table`, `fallback_reason=cfbd_timezone_null` in the
provenance manifest. That is not achievable as specified, for two independent reasons:**

1. **The manifest's granularity is the field GROUP, not the field** (`builder.py:201-226`).
   Northwestern already reads `"venue": "registry"` — counted **present** — while its `timezone`,
   `latitude`, `longitude` and `elevation` are all null. There is no sub-field `fallback_reason`
   mechanism; `fallback_reason` exists only per top-level source group, and only on an exception.
2. **A read-seam fill never touches the manifest at all** — the manifest records what the *builder*
   did, and the committed bundle is not being rebuilt.

**Proposed instead — the A6 mitigation, which faced exactly this and resolved it the same way:**

- an explicit **contract note in `docs/SCHEMA.md`** (mirroring the A6 elevation note at `:55`);
- a **self-documenting table** — each entry carries its city and the reason (`cfbd timezone: null`),
  so provenance lives with the data;
- the manifest limitation recorded as a **known state + a 2027 item** (add sub-field provenance).

**This is the one part of ruling 2 I cannot implement literally, so it needs your explicit call.**

### 3.3 Deviation 2 — the table is keyed by venue NAME, not team

`compute_schedule_intel` receives venue *dicts* and does not know the host's team name, so a
team-keyed table cannot be consulted at the read seam. Venue names are unique across the 68 tracked
venues except **`Memorial Stadium`** (Kansas / Missouri) — both of which already have timezones and
both `America/Chicago`, so **no fallback key collides**. A regression pin asserts that.

## 4. The table (all 8, values sourced by city from the IANA database)

All eight verified to resolve via `zoneinfo` on a 2026 game date:

| Venue | Team | City | IANA zone | In slate? |
|---|---|---|---|---|
| Lanny and Sharon Martin Stadium | Northwestern | Evanston IL | `America/Chicago` | **yes** |
| SHI Stadium | Rutgers | Piscataway NJ | `America/New_York` | **yes** |
| Pitbull Stadium | FIU | Miami FL | `America/New_York` | no |
| Clarence T.C. Ching Athletics Complex | Hawai'i | Honolulu HI | `Pacific/Honolulu` | no |
| Fifth Third Stadium | Kennesaw State | Kennesaw GA | `America/New_York` | no |
| Hancock Whitney Stadium | South Alabama | Mobile AL | `America/Chicago` | no |
| Protective Stadium | UAB | Birmingham AL | `America/Chicago` | no |
| Allegiant Stadium | UNLV | Las Vegas NV | `America/Los_Angeles` | no |

## 5. Expected hash outcomes — stated BEFORE implementation

| Artifact | Expectation | Why |
|---|---|---|
| Snapshot bytes / `snapshot_id` | **UNCHANGED** | read-seam fill; committed bundle never rewritten |
| wk1 predictions payload + envelope | **UNCHANGED** (`0cf87d68…2371`, measured both sides) | neither team is on the wk1 slate |
| `data/ratings/2026_week_01.json` | **UNCHANGED** (measured identical; matches on-disk today) | Elo has no completed games; tz does not enter ratings |
| Golden byte-identity | **UNCHANGED** | the golden is wk1 |
| `data/projections/2026_week_01.json` | **CHANGES — 10 of 138 teams** | projections price every remaining game; weeks 3–11 move |
| Tracked-slate spreads | **8 of 330 move**, max Δ 1.5 pts | the fix, working |

**Stop-and-report commitment:** if anything in the UNCHANGED column moves, the premise is wrong —
**I stop and report rather than regenerate.**

**Derived-artifact invariant:** projections regenerate through the pipeline writer
(`python scripts/build_projections.py --week 1`) — verified this command passes both hooks, while a
direct Write to that path is correctly blocked. Then the **full six-target sweep**: `verify-phase-2`
is the only gate that catches stale projections, and it was green *while the artifact was stale*
twice before (3b `travel_cap`, A6).

## 6. Regression pins — assert MEANING, not stored values

1. **All 68 tracked venues resolve a timezone** — the load-bearing pin; fails if CFBD drops another.
2. **A 3-zone eastward trip prices at the cap** — USC → Rutgers yields `tz=3, east` and a travel
   term clamped to `1.5`, not `1.8`.
3. **Neutral-site rows stay honestly `None`** — no acclimation edge however far the travel.
4. **A venue in neither CFBD nor the table records missing** — `None`, never a fabricated offset.
5. **A dateless input still yields `None`** — pins the confirmed-correct hypothetical behaviour so a
   later change cannot silently fabricate an offset.
6. **No fallback key is ambiguous** — guards the `Memorial Stadium` duplicate class.

## 7. Draft `CALIBRATION_LOG` entry (behavior-change, D19 pattern)

> **Venue timezone fallback — a ratified coefficient neutered by a null input (behavior-change)**
> — *RATIFIED (owner, 2026-08-03).* CFBD returns `timezone: null` for 8 of 138 FBS venues, 2 of them
> tracked (Northwestern, Rutgers). `travel_points` keys only on `time_zones_crossed`, so real
> multi-zone trips scored as zero. **Found by owner testing of `cfb hypothetical`**, not by any
> automated gate — worth recording, because the reverse-audit, the B-batch and the pre-flight all
> passed over it. Fixed with the static IANA table SPEC Appendix A already specified, applied at the
> `data/` read seam (A6 precedent) so committed snapshot bytes and `snapshot_id` are untouched.
> Measured: 8 of 330 tracked games move, max Δ **1.5 pts (60% of HFA)**, every delta reproducing the
> ratified `tz_per_zone 0.6` / `travel_cap 1.5` exactly. `data/projections/` regenerated.
> **Family: "input never arrives" — A6 (metres vs feet) and this. The broader
> never-true-comparison family is now FIVE; the unreachable-bound subfamily stays at THREE.**

## 8. What the owner is asked to rule

1. The fix as designed — static table, normalize + read-seam, **snapshot not rebuilt**? *(recommended)*
2. **§3.2** — provenance recorded as a **SCHEMA contract + self-documenting table + 2027 item**,
   since the manifest cannot express sub-field provenance and a read-seam fill never reaches it?
   **(this is the deviation from ruling 2 that needs your explicit call)**
3. **§3.3** — venue-name keying, with the ambiguity pin?
4. The table's 8 entries (§4) as the ratified values?
5. The §5 expected-hash table as the proof standard, including stop-and-report?
6. The §7 log entry, including counting this as the **fifth** never-true-comparison family member?
