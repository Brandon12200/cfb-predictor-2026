"""Persisted Odds API monthly-credit tracking for the budget guard (D5).

The Odds API returns remaining credits only in a response header, so an honest
*pre-spend* guard needs the last response's balance persisted across process
invocations (each `fetch_lines.py` run is its own process). `record_quota` writes
the latest balance; `last_remaining` reads it (falling back to the most recent
snapshot manifest's build-time quota when no fetch has run yet).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_QUOTA_FILE = Path(__file__).resolve().parent / "odds_quota.json"
_SNAPSHOTS = Path(__file__).resolve().parent / "snapshots"


def record_quota(quota: dict | None, path: Path = _QUOTA_FILE) -> None:
    """Persist the latest Odds credit balance (no-op if the header wasn't present)."""
    if not quota or quota.get("remaining") is None:
        return
    path.write_text(json.dumps(
        {"remaining": quota.get("remaining"), "used": quota.get("used"),
         "recorded_at": datetime.now(UTC).isoformat()}, indent=2) + "\n")


def last_remaining(path: Path = _QUOTA_FILE) -> tuple[int | None, str]:
    """Last-known remaining credits + its provenance ('persisted'|'snapshot'|'unknown')."""
    if path.exists():
        return json.loads(path.read_text()).get("remaining"), "persisted"
    _, quota = _latest_snapshot_quota()
    if quota and quota.get("remaining") is not None:
        return quota["remaining"], "snapshot"
    return None, "unknown"


def _latest_snapshot_quota() -> tuple[str | None, dict[str, Any] | None]:
    dirs = sorted((p for p in _SNAPSHOTS.glob("*_week_*") if (p / "manifest.json").exists()),
                  reverse=True)
    if not dirs:
        return None, None
    m = json.loads((dirs[0] / "manifest.json").read_text())
    return dirs[0].name, m.get("sources", {}).get("betting_lines", {}).get("quota")
