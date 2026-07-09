"""Full-slate prediction writer → schema v2 (Phase 3d) — freeze-exempt.

Runs the **frozen** `PredictionEngine` over a snapshot's bettable slate (games with a
prediction-time line) and serializes **every** game — including `NO_BET` — into the schema-v2
envelope defined in `utils/prediction_schema.py`. This is the persistence path the legacy
`cli/app.py` P4 flow never provided (it filtered non-edge games before writing); NO_BET games are
now logged and graded (SPEC §7 item 4 / §16.3).

Deterministic: `generated_at` is frozen from the snapshot's `built_at` (mirrors
`analytics/projections.build_projections`) and every engine field is a pure function of the
snapshot, so the output is byte-reproducible given (snapshot, week, model_version). Freeze-exempt
(`analytics/`, not `engine/`), like projections.
"""

from __future__ import annotations

from typing import Any

from data.team_registry import get_fbs_canonical_names
from engine.prediction_engine import PredictionEngine
from utils.prediction_schema import PREDICTION_SCHEMA_VERSION, build_v2_record


def build_predictions(snapshot: dict, *, week: Any, model_version: str | None) -> dict[str, Any]:
    """Schema-v2 prediction envelope for a loaded snapshot's bettable slate.

    Enumerates the snapshot's betting lines (the FBS-vs-FBS games with a prediction-time line),
    prices each via the frozen engine, and serializes all of them. The engine reads the same
    committed snapshot for `week` via the data manager, so `snapshot` here is used for enumeration,
    the line `fetched_at`, and the deterministic `generated_at` — consistent when `snapshot` is the
    committed snapshot for `week`.
    """
    data = snapshot["data"]
    meta = snapshot["meta"]
    lines = data.get("betting_lines", {})
    fbs = get_fbs_canonical_names()
    engine = PredictionEngine()

    records: list[dict] = []
    skipped: list[str] = []
    for key in sorted(lines):
        line = lines[key]
        home, away = line.get("home_team"), line.get("away_team")
        if not home or not away or home not in fbs or away not in fbs:
            continue
        result = engine.generate_prediction(home, away, week=week)
        # A valid prediction has a line; an ERROR / no-line result is surfaced in coverage, not
        # written as a half-null record.
        if result.get("prediction_type") == "ERROR" or result.get("vegas_spread") is None:
            skipped.append(f"{away}@{home}")
            continue
        obs = line.get("observation") or {}
        records.append(build_v2_record(result, week=week, line_as_of=obs.get("fetched_at")))

    records.sort(key=lambda r: r["game_id"])
    return {
        "meta": {
            "schema_version": PREDICTION_SCHEMA_VERSION,
            "model_version": model_version,
            "snapshot_id": meta.get("snapshot_id"),
            "week": meta.get("week"),
            "year": meta.get("year"),
            "generated_at": meta.get("built_at"),
            "engine": "contrarian_v2",
            "prediction_count": len(records),
            "coverage": {"lines": len(lines), "written": len(records), "skipped": skipped},
        },
        "predictions": records,
    }
