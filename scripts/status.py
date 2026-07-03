#!/usr/bin/env python3
"""Per-source health + remaining API quota (SPEC §5.3, `cfb status`).

Reports which sources are configured, the last-known Odds credit balance (read from
the most recent snapshot's manifest — no wasted credits), and the configured Odds
monthly budget. `--ping` does one cheap live CFBD reachability check.

Usage: python scripts/status.py [--ping]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

_SNAPSHOTS = Path(__file__).resolve().parent.parent / "data" / "snapshots"


def latest_odds_quota() -> tuple[str | None, dict | None]:
    """Most recent snapshot's (name, Odds quota) from its manifest — last-known balance."""
    dirs = sorted((p for p in _SNAPSHOTS.glob("*_week_*") if (p / "manifest.json").exists()),
                  reverse=True)
    if not dirs:
        return None, None
    m = json.loads((dirs[0] / "manifest.json").read_text())
    return dirs[0].name, m.get("sources", {}).get("betting_lines", {}).get("quota")


def render_status(cfbd_key: bool, odds_key: bool, odds_budget: int,
                  quota_snapshot: str | None, quota: dict | None,
                  cfbd_ping: bool | None = None) -> str:
    lines = ["source status:"]
    cfbd_h = "ping OK" if cfbd_ping else ("ping FAILED" if cfbd_ping is False else "not pinged")
    lines.append(f"  CFBD v2   key={'yes' if cfbd_key else 'NO'}   {cfbd_h}")
    if quota:
        used, remaining = quota.get("used"), quota.get("remaining")
        lines.append(f"  Odds API  key={'yes' if odds_key else 'NO'}   "
                     f"credits: {remaining} remaining / {odds_budget} monthly budget "
                     f"(used {used}; as of snapshot {quota_snapshot})")
    else:
        lines.append(f"  Odds API  key={'yes' if odds_key else 'NO'}   "
                     f"credits: unknown (no snapshot yet); monthly budget {odds_budget}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Per-source health + quota.")
    parser.add_argument("--ping", action="store_true", help="live CFBD reachability check")
    args = parser.parse_args()

    from config import config

    cfbd_ping = None
    if args.ping and config.cfbd_api_key:
        try:
            from data.clients.cfbd_v2 import get_cfbd_v2_client
            get_cfbd_v2_client().get_conferences()
            cfbd_ping = True
        except Exception:  # noqa: BLE001
            cfbd_ping = False

    snap, quota = latest_odds_quota()
    print(render_status(bool(config.cfbd_api_key), bool(config.odds_api_key),
                        config.odds_monthly_budget, snap, quota, cfbd_ping))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
