"""Layer 2 — normalize (SPEC §5.2).

Converts each source's native structures into one canonical, typed schema
(stdlib dataclasses; documented in docs/SCHEMA.md §1-3). After this layer the rest
of the system never sees source-specific shapes. Team names resolve through the
registry/normalizer. Nothing here neutral-fills: a value is present or it is
recorded absent (Optional / None) with the reason captured in the provenance
manifest — never fabricated.
"""

from data.normalize.models import (  # noqa: F401
    AdvancedStats,
    BookLine,
    Coaching,
    CoachingComparison,
    CurrentRecord,
    DerivedMetrics,
    GameContext,
    GameLines,
    ScheduleGame,
    TeamData,
    TeamInfo,
    TeamScheduleResult,
    Venue,
    VenuePerformance,
    VenueRecord,
)
