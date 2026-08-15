#!/usr/bin/env python3
"""Measure a freeze-transition delta for a SPEC §3.1 exception — offline, freeze-exempt.

**Why this exists.** SPEC §3.1 exceptions must record a *measured* delta: what moved when an
external input arrived under a D10 auto-activation. Exception 1's harness was ad-hoc and its
first draft published `0.0000` for the edge figures — the measuring script read a key that did
not exist and silently defaulted to zero. An audit-trail entry carrying a wrong number is worse
than no entry, so the harness is committed with the exception it produced.

**The three-vehicle method.** A snapshot rebuild refreshes ALL seven fetch groups, not only the
one that arrived, so a bare before/after conflates the transition with ambient data drift. Three
vehicles separate them:

    A = the pinned tag-time vehicle (data/archive/frozen/, D29) -- the ratified "before"
    B = the rebuilt snapshot with the ARRIVING GROUP REMOVED    -- control: drift without it
    C = the rebuilt snapshot as-is                              -- the "after"

    A -> B  = ambient drift        B -> C  = the transition's ISOLATED contribution

Report both. `A -> B` moving the fingerprint while every aggregate stays identical is normal and
expected: the fingerprint hashes full engine output, so sub-aggregate drift is visible to it and
to nothing else. It also means a live bundle will not reproduce vehicle C's fingerprint, and must
not be read as a confirmation of it.

**⚠ The trap that makes a measurement silently wrong (D29).** `PredictionEngine` loads its own
snapshot through `data.data_manager`. Handing a bundle to a caller redirects **enumeration only**
— pricing still reads whatever is on disk. Every engine call here is therefore wrapped in
`scripts.slate_fingerprint.engine_reads(bundle)`. Without it you get a **split read** (enumeration
pinned, pricing live) that looks correct and is not. Do not remove the wrapper.

Keys are read STRICTLY via `_strict`: a missing key raises rather than defaulting. That is the
structural fix for Exception 1's recorded failure.

Usage:
    python scripts/measure_transition.py --group sp_ratings
    python scripts/measure_transition.py --group sp_ratings --json
    python scripts/measure_transition.py --group sp_ratings --rows   # + raw-vs-normalized identity
"""

from __future__ import annotations

import argparse
import copy
import json
import logging
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from data.snapshot import load_frozen_vehicle  # noqa: E402
from data.snapshot.store import FROZEN_VEHICLE_SOURCE  # noqa: E402
from engine.prediction_engine import PredictionEngine  # noqa: E402
from scripts.slate_fingerprint import (  # noqa: E402
    PLACEHOLDER_SPREAD,
    engine_reads,
    fingerprint,
    tracked_slate,
)

ROOT = Path(__file__).resolve().parent.parent
LIVE_SNAPSHOT = ROOT / "data/snapshots/2026_week_01/snapshot.json"
LIVE_MANIFEST = ROOT / "data/snapshots/2026_week_01/manifest.json"

# Physical-factor sub-signals whose activation can make variance computable. Named for the
# cross-tab, not used to gate anything.
_SANDWICH_VALUE_KEYS = ("value", "adjustment", "points", "contribution", "raw_value")


def _strict(d: dict[str, Any], key: str) -> Any:
    """Fetch or raise. No silent defaults — Exception 1's recorded measuring error."""
    if key not in d:
        raise KeyError(f"expected key {key!r} absent; present keys={sorted(d)[:20]}")
    return d[key]


def _factor_value(rec: dict[str, Any], factor: str) -> float:
    """Numeric contribution of `factor`, 0.0 when absent or non-numeric."""
    breakdown = _strict(rec, "factor_breakdown")
    raw = breakdown.get(factor)
    if isinstance(raw, dict):
        for key in _SANDWICH_VALUE_KEYS:
            candidate = raw.get(key)
            if isinstance(candidate, (int, float)):
                return float(candidate)
        return 0.0
    return float(raw) if isinstance(raw, (int, float)) else 0.0


def predictions_for(snapshot: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Full engine output per tracked game, keyed `WW|AWAY@HOME`.

    Missing lines are filled with `PLACEHOLDER_SPREAD` exactly as `slate_fingerprint` does, so
    the records here and the fingerprint are measured over the identical input.
    """
    games = tracked_slate(snapshot)
    bundle = copy.deepcopy(snapshot)
    lines = bundle["data"]["betting_lines"]
    for game in games:
        lines.setdefault(f"{game['away_team']}@{game['home_team']}", {
            "home_team": game["home_team"], "away_team": game["away_team"],
            "vegas_spread": PLACEHOLDER_SPREAD, "observation": {"fetched_at": None},
        })
    with engine_reads(bundle):
        engine = PredictionEngine()
        return {
            f"{game.get('week'):02d}|{game['away_team']}@{game['home_team']}":
                engine.generate_prediction(
                    game["home_team"], game["away_team"], week=game.get("week"))
            for game in games
        }


def summarise(snapshot: dict[str, Any], label: str) -> dict[str, Any]:
    """Every row of a SPEC §3.1 delta table, for one vehicle."""
    records = predictions_for(snapshot)
    real_lined = set(_strict(snapshot["data"], "betting_lines").keys())

    lean: Counter[str] = Counter()
    tiers: Counter[str] = Counter()
    edges: list[float] = []
    edges_real: list[float] = []
    no_bet = 0
    sandwich_firing = 0
    prior_sources: Counter[str] = Counter()
    gaps: list[float] = []

    for key, record in records.items():
        lean[_strict(record, "edge_direction")] += 1
        tiers[_strict(record, "confidence_tier")] += 1
        if _strict(record, "no_bet"):
            no_bet += 1
        edge = abs(float(_strict(record, "edge_size")))
        edges.append(edge)
        if key.split("|", 1)[1] in real_lined:
            edges_real.append(edge)
        gaps.append(float(_strict(record, "model_vs_market_gap")))
        if _factor_value(record, "Sandwich") != 0.0:
            sandwich_firing += 1
        for side in ("home_prior_source", "away_prior_source"):
            source = _strict(record, "power_rating_breakdown").get(side)
            if source is not None:
                prior_sources[str(source)] += 1

    stamp = fingerprint(snapshot)
    return {
        "label": label,
        "fingerprint": stamp["sha256"],
        "n_games": stamp["n_games"],
        "sp_ratings": len(snapshot["data"].get("sp_ratings") or {}),
        "returning_production": len(snapshot["data"].get("returning_production") or {}),
        "lean": dict(lean),
        "tiers": dict(tiers),
        "no_bet": no_bet,
        "max_edge": round(max(edges), 4) if edges else 0.0,
        "max_edge_real_lined": round(max(edges_real), 4) if edges_real else 0.0,
        "nonzero_edges": sum(1 for e in edges if e > 0),
        "sum_abs_edge": round(sum(edges), 4),
        "distinct_edges": len({round(e, 6) for e in edges}),
        "sum_market_gap": round(sum(gaps), 2),
        "max_market_gap": round(max(gaps), 2) if gaps else 0.0,
        "sandwich_firing": sandwich_firing,
        "prior_sources": dict(prior_sources),
        "_records": records,
    }


def mechanism(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    """Cross-tabulate tier movement against factor activation and variance flags.

    A tier shift is the most consequential line in a delta table and the least self-explanatory.
    Exception 1 explained its inversion through manifest coverage; this reports the evidence for
    or against a coverage explanation as well as a variance one, so an entry can state the
    mechanism the numbers support — or record honestly that none was isolated.
    """
    rb, rc = before["_records"], after["_records"]
    moved = {k for k in rb if rb[k]["confidence_tier"] != rc[k]["confidence_tier"]}
    firing = {k for k in rc if _factor_value(rc[k], "Sandwich") != 0.0}

    def variance_levels(keys: set[str], recs: dict[str, dict[str, Any]]) -> dict[str, int]:
        return dict(Counter(recs[k]["variance_analysis"].get("variance_level") for k in keys))

    def mean(keys: set[str], recs: dict[str, dict[str, Any]], field: str) -> float:
        vals = [recs[k][field] for k in keys if isinstance(recs[k].get(field), (int, float))]
        return round(sum(vals) / len(vals), 4) if vals else float("nan")

    # Report confidence over BOTH populations. Quoting the tier-C subset's mean against the full
    # mover set is exactly how a delta table acquires a number that will not reproduce — it
    # happened in this entry's first draft and was caught only by re-running this harness.
    landed_c = {k for k in moved if rc[k]["confidence_tier"] == "C"}

    return {
        "transitions": dict(Counter(
            f"{rb[k]['confidence_tier']}->{rc[k]['confidence_tier']}" for k in rb)),
        "moved": len(moved),
        "moved_to_tier_c": len(landed_c),
        "moved_firing_pct": round(100.0 * len(moved & firing) / len(moved), 1) if moved else 0.0,
        "unchanged_firing_pct": round(
            100.0 * len((set(rb) - moved) & firing) / len(set(rb) - moved), 1),
        "firing_total": len(firing),
        "variance_before": variance_levels(moved, rb),
        "variance_after": variance_levels(moved, rc),
        "factors_analyzed_before": dict(Counter(
            rb[k]["variance_analysis"].get("factors_analyzed") for k in moved)),
        "factors_analyzed_after": dict(Counter(
            rc[k]["variance_analysis"].get("factors_analyzed") for k in moved)),
        "mean_confidence_all_movers": [mean(moved, rb, "confidence_score"),
                                       mean(moved, rc, "confidence_score")],
        "mean_confidence_movers_reaching_tier_c": [mean(landed_c, rb, "confidence_score"),
                                                   mean(landed_c, rc, "confidence_score")],
        "mean_data_quality_moved": [mean(moved, rb, "data_quality"),
                                    mean(moved, rc, "data_quality")],
    }


def coverage() -> dict[str, Any]:
    """Manifest coverage at the pinned tag vs the working tree — Exception 1's lever.

    Reported so an entry can show whether the data-availability channel (B1) explains a tier
    shift or, as in Exception 2, demonstrably does not.
    """
    out: dict[str, Any] = {}
    tag = FROZEN_VEHICLE_SOURCE[0]
    shown = subprocess.run(
        ["git", "show", f"{tag}:data/snapshots/2026_week_01/manifest.json"],
        capture_output=True, cwd=str(ROOT))
    if shown.returncode == 0:
        out["tag"] = {"ref": tag, **json.loads(shown.stdout)["summary"]}
    if LIVE_MANIFEST.exists():
        out["live"] = json.loads(LIVE_MANIFEST.read_text())["summary"]
    if "tag" in out and LIVE_MANIFEST.exists():
        before = json.loads(shown.stdout)["coverage"]["teams"]
        after = json.loads(LIVE_MANIFEST.read_text())["coverage"]["teams"]
        groups = sorted({g for v in after.values() for g in v})
        out["per_group"] = {
            g: [sum(1 for v in before.values() if v.get(g) not in (None, "missing")),
                sum(1 for v in after.values() if v.get(g) not in (None, "missing"))]
            for g in groups
        }
    return out


def row_identity(group: str) -> dict[str, Any]:
    """Raw API rows vs normalized entries, reconciled by identity (network)."""
    from dotenv import load_dotenv

    load_dotenv()
    from data.clients.cfbd_v2 import get_cfbd_v2_client
    from data.normalize.cfbd import _norm, normalize_sp_ratings

    if group != "sp_ratings":
        return {"skipped": f"row identity implemented for sp_ratings, not {group!r}"}
    raw = get_cfbd_v2_client().get_sp_ratings(2026) or []
    teams = [r.get("team") for r in raw]
    return {
        "raw_rows": len(raw),
        "normalized": len(normalize_sp_ratings(raw)),
        "dropped_by_norm": sorted({t for t in teams if _norm(t) is None}),
        "null_ranking_rows": sum(1 for r in raw if r.get("ranking") is None),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--group", default="sp_ratings",
                        help="the arriving snapshot group to isolate (vehicle B removes it)")
    parser.add_argument("--live", type=Path, default=LIVE_SNAPSHOT,
                        help="the rebuilt snapshot serving as vehicle C")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument("--rows", action="store_true",
                        help="also reconcile raw API rows vs normalized (network)")
    args = parser.parse_args(argv)
    logging.disable(logging.CRITICAL)

    vehicle_a = load_frozen_vehicle()
    vehicle_c = json.loads(args.live.read_text())
    vehicle_b = copy.deepcopy(vehicle_c)
    vehicle_b["data"][args.group] = {}

    a = summarise(vehicle_a, f"A pinned {FROZEN_VEHICLE_SOURCE[0]}")
    b = summarise(vehicle_b, f"B rebuilt, {args.group} removed (control)")
    c = summarise(vehicle_c, f"C rebuilt, {args.group} live (after)")

    slate_a = set(a["_records"])
    slate_c = set(c["_records"])
    report: dict[str, Any] = {
        "vehicles": [{k: v for k, v in x.items() if k != "_records"} for x in (a, b, c)],
        "slate_identity": {
            "entered": sorted(slate_c - slate_a),
            "left": sorted(slate_a - slate_c),
            "membership_changed_by_group": sorted(set(b["_records"]) ^ slate_c),
        },
        "isolation": {
            "ambient_drift_moved_fingerprint": a["fingerprint"] != b["fingerprint"],
            "group_moved_fingerprint": b["fingerprint"] != c["fingerprint"],
        },
        "tier_mechanism": mechanism(b, c),
        "coverage": coverage(),
    }
    if args.rows:
        report["row_identity"] = row_identity(args.group)

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True, default=str))
        return 0

    for vehicle in report["vehicles"]:
        print(json.dumps(vehicle, indent=2, sort_keys=True))
        print()
    for section in ("slate_identity", "isolation", "tier_mechanism", "coverage"):
        print(f"=== {section} ===")
        print(json.dumps(report[section], indent=2, sort_keys=True, default=str))
        print()
    if args.rows:
        print("=== row_identity ===")
        print(json.dumps(report["row_identity"], indent=2, sort_keys=True))
    print("\nAmbient drift alone moves the fingerprint. A live bundle will NOT reproduce "
          "vehicle C's hash and must not be read as confirming it.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
