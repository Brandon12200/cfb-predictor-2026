"""Prediction schema v2 — definition, record builder, and the 2025 v1→v2 converter (Phase 3d).

Freeze-exempt serialization layer (SPEC §7 item 6). The frozen engine's in-memory result is a
pure function of the snapshot; this module turns that result into the persisted **schema-v2**
record and defines the on-disk contract documented in ``docs/SCHEMA.md``. The v1→v2 converter is
**read-only** on the append-only 2025 archive — it never rewrites those files, only maps a loaded
v1 dict to a v2 dict.

Grading-filled fields (`closing_spread`, `clv`, `graded_at`) are `null` at write time; Phase 4
fills them per the documented CLV convention (positive = our number beat the close). `model_version`
is stamped by the writer (VOLATILE — changes per commit until the freeze tag).
"""

from __future__ import annotations

from typing import Any

PREDICTION_SCHEMA_VERSION = 2

# Canonical per-record key inventory (the parity test pins the live writer + the golden example to
# this exact set). On disk the keys are written sort_keys=True (alphabetical); this tuple is the
# authoritative key SET, not the serialized order.
V2_RECORD_KEYS: tuple[str, ...] = (
    "game_id", "home_team", "away_team", "week",
    "vegas_spread", "contrarian_spread", "predicted_edge", "edge_direction",
    "prediction_type", "no_bet", "no_bet_reason", "confidence_tier", "confidence",
    "power_rating_spread", "factor_breakdown", "data_quality", "line_as_of",
    "closing_spread", "clv", "graded_at",
)

# Confidence tier boundaries live with the engine (single source); imported here for the converter,
# which derives a tier from the legacy 0–100 confidence.
from engine.prediction_engine import CONFIDENCE_TIER_A_MIN, CONFIDENCE_TIER_B_MIN  # noqa: E402


def game_id(home_team: Any, away_team: Any, week: Any) -> str:
    """New-format id: ``{away}-vs-{home}-week{N}`` (matches ``prediction_storage``)."""
    return (f"{str(away_team).lower().replace(' ', '-')}-vs-"
            f"{str(home_team).lower().replace(' ', '-')}-week{week}")


def _round(x: Any, n: int) -> float | None:
    return round(x, n) if isinstance(x, (int, float)) else None


def v2_factor_breakdown(factor_breakdown: dict) -> dict[str, dict]:
    """Per-sub-signal breakdown: each factor's contribution (vs the v1 flat ``{category: float}``).

    Keeps the load-bearing, JSON-safe fields only (drops reasoning/explanation blobs and the
    ``FactorConfidence`` enum). Deterministic ordering by factor name.
    """
    out: dict[str, dict] = {}
    for name in sorted(factor_breakdown):
        fr = factor_breakdown[name]
        out[name] = {
            "value": _round(fr.get("value"), 3),
            "weighted_value": _round(fr.get("weighted_value"), 3),
            "activated": bool(fr.get("activated", False)),
            "category": fr.get("category"),
        }
    return out


def build_v2_record(result: dict, *, week: Any, line_as_of: str | None) -> dict:
    """Serialize one frozen-engine result into a schema-v2 record (keys per ``V2_RECORD_KEYS``).

    Grading-filled fields start ``null``; `line_as_of` is the prediction-time observation's
    ``fetched_at`` (from the snapshot's betting line).
    """
    home, away = result.get("home_team"), result.get("away_team")
    return {
        "game_id": game_id(home, away, week),
        "home_team": home,
        "away_team": away,
        "week": week,
        "vegas_spread": _round(result.get("vegas_spread"), 2),
        "contrarian_spread": _round(result.get("contrarian_spread"), 2),
        # 4 dp, not 2 (reverse-audit A4 sub-decision). The measured 2026 edge distribution spans
        # [0, 0.2338] pts, so 2 dp left ~24 distinct values and collapsed the in-season median
        # (0.0244) to 0.02 with ~40% of games rounding to 0.00. `predicted_edge` is the primary
        # attribution dimension for the 2027 reasoned->measured conversion (the discrete
        # `prediction_type` ladder never persists — it is overwritten by the NO_BET verdict), so
        # the resolution has to survive to disk.
        "predicted_edge": _round(result.get("edge_size"), 4),
        "edge_direction": result.get("edge_direction"),
        "prediction_type": result.get("prediction_type"),
        "no_bet": bool(result.get("no_bet", False)),
        "no_bet_reason": result.get("no_bet_reason"),
        "confidence_tier": result.get("confidence_tier"),
        "confidence": _round(result.get("confidence_score"), 4),   # 0–1 (v1 stored 0–100)
        "power_rating_spread": _round(result.get("power_rating_spread"), 2),
        "factor_breakdown": v2_factor_breakdown(result.get("factor_breakdown", {})),
        "data_quality": _round(result.get("data_quality"), 3),
        "line_as_of": line_as_of,
        # Grading-filled (Phase 4): null = not yet graded (distinct from honest-missing).
        "closing_spread": None,
        "clv": None,
        "graded_at": None,
    }


def clv(vegas_spread: Any, closing_spread: Any, edge_direction: Any) -> float | None:
    """Closing-line value in points, from the **bet side's** perspective — **positive = our number
    beat the close** (we locked a more-favourable number for our side than where the market closed).

    A **home** bet beats the close when ``vegas_spread > closing_spread`` (a higher / more
    home-favourable number) ⇒ ``clv = vegas_spread − closing_spread``. An **away** bet beats the
    close when ``closing_spread > vegas_spread`` ⇒ ``clv = closing_spread − vegas_spread``. Returns
    ``None`` when either spread is missing (**not yet graded**, or honest-missing at grading) **or
    when no side was taken** (``edge_direction`` neither ``"home"`` nor ``"away"``): CLV is defined
    from the bet side's perspective, so no side ⇒ no perspective ⇒ undefined ⇒ ``None`` (D22 / SCHEMA
    §3). ``0.0`` means "our number exactly matched the close" and nothing else. This is the documented
    convention (SPEC §7 item 6); Phase 4 fills ``closing_spread`` from the closing observation and
    calls this at grading time.
    """
    if not isinstance(vegas_spread, (int, float)) or not isinstance(closing_spread, (int, float)):
        return None
    if edge_direction == "home":
        return round(vegas_spread - closing_spread, 2)
    if edge_direction == "away":
        return round(closing_spread - vegas_spread, 2)
    return None  # no side taken (neutral) — CLV undefined, never 0.0 (D22 / f3)


# ── Graded-record schema (Phase 4, D22) ─────────────────────────────────────────────────────────
# Grading NEVER edits the byte-immutable ``data/predictions/`` files (D22, owner 2026-07-09). It
# writes a SEPARATE append-only artifact ``data/graded/2026_week_NN.json`` keyed by ``game_id``; the
# "filled" schema-v2 record exists only as an in-memory JOIN (predictions ⋈ graded) rendered in
# reports, never materialized back to disk. This is a NEW schema, defined here at birth (define-
# semantics-at-birth). Reproducibility carve-out: predictions are *claims* and are deterministic
# from a frozen snapshot; gradings are *evented* outcomes stamped at wall-clock ``graded_at`` — the
# graded artifact is deliberately NOT part of the snapshot reproducibility contract (SCHEMA §3).

GRADED_SCHEMA_VERSION = 1

# Canonical per-record key inventory for the graded artifact (the parity test pins the live writer +
# the graded golden example to this exact set, mirroring V2_RECORD_KEYS).
def is_no_bet(pred: dict) -> bool:
    """Was this prediction a NO_BET? Derived from the CLAIM, which is the only source that exists
    for every row.

    **Never infer this from `is_hypothetical`.** That field is written onto GRADED records only
    (`_GRADED_FIELDS`, `analytics/join.py`), so an ungraded row simply has no such key — and
    `not r.get("is_hypothetical")` then reads absence as an affirmative "this was a placed bet".
    That produced the 2026 week-1 report's "placed bets: 9" on an 11/11 NO_BET slate (D40).
    """
    if "no_bet" in pred or "prediction_type" in pred:
        return bool(pred.get("no_bet", False)) or pred.get("prediction_type") == "NO_BET"
    # A caller holding GRADED-only records (no claim fields) still has the derived flag. Falling
    # back to it is safe *because it is present*; what is never safe is reading its ABSENCE as
    # "placed", which is the inversion this helper exists to prevent.
    return bool(pred.get("is_hypothetical", False))


GRADED_RECORD_KEYS: tuple[str, ...] = (
    "game_id", "home_team", "away_team", "week",
    "closing_spread", "close_as_of", "clv", "ats_result", "is_hypothetical",
    "home_score", "away_score", "graded_at",
)


def build_graded_record(pred: dict, result: dict, *, closing_spread: Any, close_as_of: str | None,
                        clv_points: float | None, ats_result: str | None, graded_at: str) -> dict:
    """Serialize one grading into a graded-record (keys per ``GRADED_RECORD_KEYS``).

    Pure serializer — the grading computation (``closing_observation`` → ``closing_spread``, ``clv``,
    ``analytics.calibration_evidence.ats_outcome`` → ``ats_result``) is orchestrated by
    ``analytics.grading`` and passed in here, so ``utils`` stays free of an ``analytics`` dependency.

    - ``closing_spread`` ``null`` = honest-missing (no closing line captured); a real ``0.0`` is a value.
    - ``clv`` ``null`` = no closing line **or** no side taken (neutral); ``0.0`` = our number matched
      the close (D22 / f3). ``clv_points`` is already rounded by ``prediction_schema.clv``.
    - ``ats_result`` ``"win"``/``"loss"``/``"push"`` from the bet side, or ``null`` (not gradable / no side).
    - ``is_hypothetical`` — the game was ``NO_BET`` (graded "what would have happened").
    """
    return {
        "game_id": pred.get("game_id"),
        "home_team": pred.get("home_team"),
        "away_team": pred.get("away_team"),
        "week": pred.get("week"),
        "closing_spread": _round(closing_spread, 2),
        "close_as_of": close_as_of,
        "clv": clv_points,
        "ats_result": ats_result,
        "is_hypothetical": is_no_bet(pred),
        "home_score": result.get("home_score"),
        "away_score": result.get("away_score"),
        "graded_at": graded_at,
    }


def _tier_from_pct_confidence(pct: Any) -> str | None:
    """Derive an A/B/C tier from the legacy 0–100 confidence, using the ratified boundaries."""
    if not isinstance(pct, (int, float)):
        return None
    score = pct / 100.0
    if score >= CONFIDENCE_TIER_A_MIN:
        return "A"
    if score >= CONFIDENCE_TIER_B_MIN:
        return "B"
    return "C"


def convert_v1_to_v2(v1_pred: dict) -> dict:
    """Map a legacy 2025 (v1) prediction dict to a schema-v2 record. **Pure + read-only** — never
    mutates the append-only ``data/archive/2025`` files.

    Lossy mappings (documented in ``docs/SCHEMA.md``), for fields v1 never recorded:
      - `game_id`: kept as-is (the archive join key — v1 ``{AWAY}_{HOME}_week{N}`` format).
      - `no_bet`: ``False`` (v1 predates NO_BET; every v1 pick was a bet-or-consensus).
      - `confidence_tier`: derived from v1's 0–100 confidence via the ratified boundaries.
      - `confidence`: v1's 0–100 value carried through as ``confidence_pct`` (kept distinct from
        the v2 0–1 ``confidence`` so a reader never mixes the scales).
      - `factor_breakdown`: v1's flat ``{category: float}`` kept, tagged ``_v1_flat: true`` — the
        per-sub-signal breakdown cannot be recovered.
      - `power_rating_spread`, `closing_spread`, `clv`, `graded_at`, `line_as_of`,
        `model_version`: ``null`` (v1 has no such data).
    """
    conf_pct = v1_pred.get("confidence")
    fb = dict(v1_pred.get("factor_breakdown") or {})
    fb["_v1_flat"] = True
    return {
        "schema_version": PREDICTION_SCHEMA_VERSION,
        "model_version": None,
        "game_id": v1_pred.get("game_id"),
        "home_team": v1_pred.get("home_team"),
        "away_team": v1_pred.get("away_team"),
        "week": v1_pred.get("week"),
        "vegas_spread": v1_pred.get("vegas_spread"),
        "contrarian_spread": v1_pred.get("contrarian_spread"),
        "predicted_edge": v1_pred.get("predicted_edge"),
        "edge_direction": v1_pred.get("edge_direction"),
        "prediction_type": v1_pred.get("prediction_type"),
        "no_bet": False,
        "no_bet_reason": None,
        "confidence_tier": _tier_from_pct_confidence(conf_pct),
        "confidence": None,                 # v2 0–1 confidence not recoverable from v1
        "confidence_pct": conf_pct,         # v1's 0–100 value, kept distinct
        "power_rating_spread": None,
        "factor_breakdown": fb,
        "data_quality": v1_pred.get("data_quality"),
        "line_as_of": None,
        "closing_spread": None,
        "clv": None,
        "graded_at": None,
        "_converted_from": "v1",
    }
