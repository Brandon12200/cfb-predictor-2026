"""Calibration evidence harness (Phase 3, SPEC §7 / §3) — freeze-exempt analytics.

Reads the 300-game 2025 archive (`data/archive/2025/`) and reports how the OLD system's
**confidence / predicted-edge / prediction-type** related to realized **ATS outcomes**, each
with **Wilson 95% intervals + sample sizes**. This is the evidence every Phase-3 calibration
proposal cites (confidence tiers L3, `NO_BET` floors L4). **Read-only over the archive; NO
fitting / grid-search** (SPEC §3 & §12 — the overfitting this project exists to avoid).

**ATS convention** is the project's canonical one (`scripts/calculate_accuracy.py`): home covers
a spread `S` iff `(home_score − away_score) + S > 0`. The contrarian bet is the model's
`edge_direction` side vs the **Vegas** line; **pushes excluded from win%**. Verified sane: overall
contrarian ATS ≈ 46.6% over 2025 (the honest slightly-losing season behind L4).

**Read the intervals, not the point estimates.** 300 games sliced into buckets leaves ~40–60-game
cells with wide Wilson intervals — a 12-pt ATS gap on 45 games is weaker evidence than it looks.
"""

from __future__ import annotations

import glob
import json
import math
import os
from pathlib import Path
from typing import Any

# Bucket edges (illustrative; the ratified A/B/C tier + NO_BET-floor boundaries are set in 3c
# FROM this evidence, not hard-coded here).
CONFIDENCE_EDGES = (50.0, 60.0, 70.0, 80.0)
EDGE_EDGES = (1.0, 2.0, 3.0, 5.0)


def wilson_interval(wins: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score 95% CI for a binomial proportion (small-sample honest)."""
    if n == 0:
        return (0.0, 0.0)
    phat = wins / n
    denom = 1.0 + z * z / n
    center = (phat + z * z / (2 * n)) / denom
    half = z * math.sqrt(phat * (1 - phat) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, center - half), min(1.0, center + half))


def ats_outcome(pred: dict, result: dict) -> str | None:
    """`"win"`/`"loss"`/`"push"` for the model's `edge_direction` side vs the Vegas line, or
    `None` if not gradable. Canonical convention: home covers `S` iff `margin + S > 0`."""
    direction = pred.get("edge_direction")
    if direction not in ("home", "away"):
        return None
    vegas, hs, as_ = pred.get("vegas_spread"), result.get("home_score"), result.get("away_score")
    if vegas is None or hs is None or as_ is None:
        return None
    cover = (hs - as_) + vegas  # > 0 ⇒ home covers the Vegas line
    if abs(cover) < 1e-9:
        return "push"
    home_covers = cover > 0
    won = (direction == "home" and home_covers) or (direction == "away" and not home_covers)
    return "win" if won else "loss"


def _load_archive(archive_dir: str) -> list[tuple[dict, dict]]:
    """Join predictions↔results by `game_id` → list of (prediction, result) pairs."""
    preds: dict[str, dict] = {}
    for f in sorted(glob.glob(os.path.join(archive_dir, "predictions", "*.json"))):
        for p in json.loads(open(f).read()).get("predictions", []):
            preds[p["game_id"]] = p
    results: dict[str, dict] = {}
    for f in sorted(glob.glob(os.path.join(archive_dir, "results", "*.json"))):
        for r in json.loads(open(f).read()).get("results", []):
            results[r["game_id"]] = r
    return [(preds[g], results[g]) for g in sorted(preds) if g in results]


def _bucket_stats(outcomes: list[str]) -> dict[str, Any]:
    wins, losses, pushes = outcomes.count("win"), outcomes.count("loss"), outcomes.count("push")
    n = wins + losses
    lo, hi = wilson_interval(wins, n)
    return {
        "n_graded": n, "wins": wins, "losses": losses, "pushes": pushes,
        "ats_win_pct": round(wins / n, 4) if n else None,
        "wilson_95": [round(lo, 4), round(hi, 4)] if n else None,
    }


def _binned(pairs: list[tuple[dict, dict]], key: str, edges: tuple[float, ...]) -> list[dict]:
    """Bucket outcomes by a numeric prediction field into `[<e0, e0-e1, …, ≥e_last]` bands."""
    labels = ([f"<{edges[0]:g}"]
              + [f"{edges[i]:g}-{edges[i + 1]:g}" for i in range(len(edges) - 1)]
              + [f">={edges[-1]:g}"])
    buckets: list[list[str]] = [[] for _ in labels]
    for pred, result in pairs:
        outcome = ats_outcome(pred, result)
        if outcome is None:
            continue
        val = pred.get(key)
        if val is None:
            continue
        idx = len(edges)
        for i, e in enumerate(edges):
            if val < e:
                idx = i
                break
        buckets[idx].append(outcome)
    return [{"bucket": labels[i], **_bucket_stats(buckets[i])} for i in range(len(labels))]


def _repo_relative(path: str) -> str:
    """A repo-relative form of `path`, so the committed artifact is machine-independent.

    `meta.source` is compared byte-for-byte by `verify-phase-3`'s reproduce-from-archive check
    (`scripts/verify_phase_3.py`), which rebuilds the pack and asserts equality with the committed
    file. Storing an absolute path made that gate pass only on the machine that generated it — a
    reproducibility gate that was itself not reproducible. Paths outside the repo are returned
    unchanged rather than guessed at.
    """
    repo = Path(__file__).resolve().parent.parent
    try:
        return str(Path(path).resolve().relative_to(repo))
    except ValueError:
        return path


def build_calibration_evidence(archive_dir: str) -> dict[str, Any]:
    """The evidence pack: overall + by confidence / predicted-edge / prediction-type."""
    pairs = _load_archive(archive_dir)
    overall = [o for o in (ats_outcome(p, r) for p, r in pairs) if o is not None]
    overall_stats = _bucket_stats(overall)  # n_graded excludes pushes (matches bucket denominators)

    by_type: dict[str, list[str]] = {}
    for pred, result in pairs:
        outcome = ats_outcome(pred, result)
        if outcome is None:
            continue
        by_type.setdefault(pred.get("prediction_type", "UNKNOWN"), []).append(outcome)

    return {
        "meta": {
            "source": _repo_relative(archive_dir),
            "games_joined": len(pairs),
            "resolved": len(overall),                # had an outcome (win + loss + push)
            "graded": overall_stats["n_graded"],     # win + loss only (excludes pushes; = bucket denominators)
            "pushes": overall_stats["pushes"],
            "ats_convention": "home covers S iff (home_score-away_score)+S>0 "
                              "(scripts/calculate_accuracy.py); bet = edge_direction side vs Vegas; "
                              "pushes excluded from win%",
            "clv": "unavailable — the 2025 archive has no closing lines",
            "caveat": "read the Wilson intervals, not the point estimates; ~40-60-game cells are wide",
            "not_a_fit": "descriptive evidence only; calibration is set by reasoning over this, "
                         "never by optimizing these numbers (SPEC §3/§12)",
        },
        "overall": overall_stats,
        "by_confidence": _binned(pairs, "confidence", CONFIDENCE_EDGES),
        "by_predicted_edge": _binned(pairs, "predicted_edge", EDGE_EDGES),
        "by_prediction_type": [
            {"prediction_type": t, **_bucket_stats(by_type[t])} for t in sorted(by_type)
        ],
    }


def format_table(evidence: dict[str, Any]) -> str:
    """Readable evidence table (for `scripts/build_calibration_evidence.py`)."""
    lines: list[str] = []
    m = evidence["meta"]
    lines.append(f"2025 calibration evidence — {m['graded']} graded (win/loss) of {m['games_joined']} "
                 f"joined, {m['pushes']} pushes ({m['source']})")
    lines.append(f"  ATS: {m['ats_convention']}")
    lines.append(f"  CLV: {m['clv']}")

    def _row(label: str, s: dict) -> str:
        if not s["n_graded"]:
            return f"  {label:<14} n=0"
        lo, hi = s["wilson_95"]
        return (f"  {label:<14} n={s['n_graded']:<4} ATS={s['ats_win_pct']:.1%}  "
                f"[95% {lo:.0%}–{hi:.0%}]  ({s['wins']}-{s['losses']}-{s['pushes']})")

    lines.append("\nOVERALL")
    lines.append(_row("all", evidence["overall"]))
    lines.append("\nBy confidence")
    lines += [_row(b["bucket"], b) for b in evidence["by_confidence"]]
    lines.append("\nBy predicted edge")
    lines += [_row(b["bucket"], b) for b in evidence["by_predicted_edge"]]
    lines.append("\nBy prediction type")
    lines += [_row(b["prediction_type"], b) for b in evidence["by_prediction_type"]]
    lines.append("\n(Read intervals, not point estimates. Descriptive evidence — not a fit.)")
    return "\n".join(lines)
