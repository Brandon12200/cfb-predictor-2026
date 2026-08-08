"""Layer 3 — snapshot (SPEC §5.2).

The ONLY place fallback policy lives. Orchestrates a week's league-wide fetch,
normalizes to canonical dataclasses, applies `CFBD → [ESPN staged] → declared-missing`,
and writes a versioned bundle (`data/snapshots/YYYY_week_NN/`) = canonical data +
a provenance manifest covering 100% of fields. Neutral fabrication is abolished:
absence is recorded as `missing`. The engine reads only these snapshots.
"""

from data.snapshot.builder import SnapshotBuilder  # noqa: F401
from data.snapshot.store import (  # noqa: F401
    FROZEN_VEHICLE,
    SnapshotNotFoundError,
    compute_snapshot_id,
    frozen_vehicle_sha256,
    load_frozen_vehicle,
    load_snapshot,
    snapshot_dir,
    write_snapshot,
)
