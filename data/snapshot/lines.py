"""Append-only line-observation store (SPEC §5.4.3).

The content-addressed snapshot is immutable — its `snapshot_id` anchors reproducible
reruns and is embedded in every prediction. So the growing "as-of T" line series is
NOT written back into `snapshot.json`; it lives here, in an append-only historical
artifact `data/lines/YYYY_week_NN.json` (CLAUDE.md principle 5, like `predictions/`),
outside the hash. The build seeds observation #1; `scripts/fetch_lines.py` appends more.
Closing line = the last observation before each game's own kickoff (`closing_observation`).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_LINES_DIR = Path(__file__).resolve().parent.parent / "lines"


def lines_path(week: int, year: int = 2026, base: Path | None = None) -> Path:
    return (base or _LINES_DIR) / f"{year}_week_{week:02d}.json"


def load_lines(week: int, year: int = 2026, base: Path | None = None) -> dict[str, Any]:
    path = lines_path(week, year, base)
    return json.loads(path.read_text()) if path.exists() else {}


def record_observation(week: int, games: dict[str, dict], year: int = 2026,
                       base: Path | None = None) -> int:
    """Append each game's new observation(s) to the store (append-only; deduped by
    `fetched_at` so re-runs are idempotent). Returns the number of observations added."""
    store = load_lines(week, year, base)
    added = 0
    for key, gl in games.items():
        entry = store.setdefault(key, {"home_team": gl["home_team"],
                                       "away_team": gl["away_team"],
                                       "kickoff": gl.get("kickoff"), "observations": []})
        seen = {o["fetched_at"] for o in entry["observations"]}
        for obs in gl.get("observations", []):
            if obs["fetched_at"] not in seen:
                entry["observations"].append(obs)
                added += 1
        entry["observations"].sort(key=lambda o: o.get("fetched_at") or "")
    path = lines_path(week, year, base)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(store, indent=2, sort_keys=True) + "\n")
    return added
