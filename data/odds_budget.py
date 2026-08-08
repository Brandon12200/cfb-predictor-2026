"""Odds API monthly-credit tracking for the budget guard (D5) — freeze-exempt.

The Odds API returns remaining credits only in a response header, so an honest *pre-spend* guard
needs the last response's balance persisted across process invocations (each `fetch_lines.py` run
is its own process).

**Two stores, deliberately.**

* **`data/quota/odds_YYYY_MM.json` — an append-only ledger, one entry per spend.** This is the
  committed artifact and the SPEC §10.5 "logs remaining quota" record: month-partitioned, immutable
  once written, and readable as a spend series rather than a single number. It answers "is the burn
  rate what we expect", which is the actual risk — the cadence spends ~8 credits/week against a
  500/month tier, so exhaustion was never the danger; a retry storm is.
* **`data/odds_quota.json` — the legacy single-value cache.** Gitignored, still read as a fallback
  so an environment without a ledger keeps working.

The ledger is what the pipeline commits; it replaces the `actions/cache` workaround, which lost the
balance whenever a cache was evicted and left the guard blind in between.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_DATA = Path(__file__).resolve().parent
_QUOTA_FILE = _DATA / "odds_quota.json"
_SNAPSHOTS = _DATA / "snapshots"
_LEDGER_DIR = _DATA / "quota"


def ledger_path(when: datetime | None = None, base: Path | None = None) -> Path:
    """Month-partitioned ledger file. Partitioning matches the tier's monthly reset."""
    stamp = when or datetime.now(UTC)
    return (base or _LEDGER_DIR) / f"odds_{stamp.year}_{stamp.month:02d}.json"


def read_ledger(path: Path | None = None) -> list[dict[str, Any]]:
    p = path or ledger_path()
    if not p.exists():
        return []
    return json.loads(p.read_text()).get("entries", [])


def append_ledger(quota: dict | None, *, caller: str, week: int | None = None,
                  run_id: str | None = None, base: Path | None = None,
                  when: datetime | None = None) -> bool:
    """Append one spend entry. Append-only: existing entries are never rewritten.

    Returns True when an entry was written. A no-op when the response carried no quota header —
    recording a null balance would be fabricating a measurement.
    """
    if not quota or quota.get("remaining") is None:
        return False
    stamp = when or datetime.now(UTC)
    path = ledger_path(stamp, base)
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = json.loads(path.read_text()) if path.exists() else {"entries": []}
    existing["entries"].append({
        "at": stamp.isoformat(),
        "remaining": quota.get("remaining"),
        "used": quota.get("used"),
        "caller": caller,
        "week": week,
        "run_id": run_id,
    })
    path.write_text(json.dumps(existing, indent=2, sort_keys=True) + "\n")
    return True


def record_quota(quota: dict | None, path: Path = _QUOTA_FILE) -> None:
    """Persist the latest Odds credit balance (no-op if the header wasn't present)."""
    if not quota or quota.get("remaining") is None:
        return
    path.write_text(json.dumps(
        {"remaining": quota.get("remaining"), "used": quota.get("used"),
         "recorded_at": datetime.now(UTC).isoformat()}, indent=2) + "\n")


def last_remaining(path: Path = _QUOTA_FILE) -> tuple[int | None, str]:
    """Last-known remaining credits + provenance ('ledger'|'persisted'|'snapshot'|'unknown').

    The ledger is preferred: it survives a fresh checkout because it is committed, whereas the
    single-value cache is gitignored and the snapshot fallback is up to a week stale.
    """
    entries = read_ledger()
    if entries:
        return entries[-1].get("remaining"), "ledger"
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
