"""Static IANA timezone fallback for venues CFBD serves without one (SPEC Appendix A).

**Why this exists.** CFBD returns `"timezone": null` for 8 of 138 FBS venues — the key is present,
only the value is absent, so `normalize_venue` faithfully passes a null through. Two of the eight
are in the tracked P4+independents slate (Northwestern, Rutgers), and because
`factors.physical_coefficients.travel_points` keys **only** on `time_zones_crossed`, a null made a
real multi-zone trip score as zero time zones — silently neutering the ratified `tz_per_zone`
coefficient. Same family as A6: *a ratified coefficient that cannot fire because an input never
arrives.*

SPEC **Appendix A** already specified the remedy — *"Geo math (travel distance, time zones,
altitude) | Computed from CFBD venue data **+ static timezone table**"* — and the table was never
built. This is it.

**Provenance (ratified 2026-08-03).** Values are looked up **by city** in the IANA time-zone
database; they are facts about geography, not inferences, and not neutral fills. The provenance
manifest cannot record them — its granularity is the field *group*, not the field, so Northwestern
already reports `"venue": "registry"` while four of its fields are null — so provenance lives here,
with the data, and as a contract note in `docs/SCHEMA.md`. Adding sub-field provenance to the
manifest is a **2027** item.

**Keyed by venue NAME, not team**, because `compute_schedule_intel` receives venue dicts and never
learns the host's team name. Venue names are unique across the tracked slate except
`Memorial Stadium` (Kansas / Missouri) — both of which already carry a timezone, and the same one —
so no key here is ambiguous. A regression pin asserts that.

**A venue in neither CFBD nor this table stays `None`** — honest-missing, never a fabricated
offset (binding principle #4).
"""

from __future__ import annotations

from typing import Any

# Venue name -> IANA zone. Each entry records the city it was sourced from and the reason the
# fallback is needed. Kept small and explicit as the human review checkpoint, following the
# `data/team_registry.py::CANONICAL_OVERRIDES` precedent.
#
# All eight CFBD-null venues are covered. Only the two marked TRACKED are in the P4+independents
# slate and can affect a 2026 prediction; the other six are out of slate scope by design (the same
# finding shape as A6's venue-coverage investigation) and are included so the table is complete
# rather than slate-shaped.
STATIC_VENUE_TIMEZONES: dict[str, str] = {
    # -- TRACKED (in slate; these are the two that move model output) ------------------------
    "Lanny and Sharon Martin Stadium": "America/Chicago",     # Northwestern — Evanston IL
    "SHI Stadium": "America/New_York",                        # Rutgers — Piscataway NJ
    # -- Out of slate scope (completeness only; cannot affect a 2026 tracked prediction) -----
    "Pitbull Stadium": "America/New_York",                    # FIU — Miami FL
    "Clarence T.C. Ching Athletics Complex": "Pacific/Honolulu",  # Hawai'i — Honolulu HI
    "Fifth Third Stadium": "America/New_York",                # Kennesaw State — Kennesaw GA
    "Hancock Whitney Stadium": "America/Chicago",             # South Alabama — Mobile AL
    "Protective Stadium": "America/Chicago",                  # UAB — Birmingham AL
    "Allegiant Stadium": "America/Los_Angeles",               # UNLV — Las Vegas NV
}


def static_timezone_for(venue: Any) -> str | None:
    """The static-table timezone for a venue dict, or `None` if it is not covered.

    Takes the venue mapping (not a name) so callers cannot accidentally key on the wrong field.
    """
    if not isinstance(venue, dict):
        return None
    name = venue.get("name")
    if not isinstance(name, str):
        return None
    return STATIC_VENUE_TIMEZONES.get(name)
