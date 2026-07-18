"""Grading core (Phase 4, SPEC §8, D22) — freeze-exempt.

Grades predictions against final scores + each game's **as-of-T closing line** into a **separate
append-only** graded artifact (``data/graded/YYYY_week_NN.json``). It **NEVER** edits
``data/predictions/`` (D22, owner 2026-07-09): predictions are byte-immutable *claims*; gradings are
evented *outcomes*. The "filled" schema-v2 record exists only as an in-memory JOIN (predictions ⋈
graded) rendered in reports.

`grade_game` is **pure + idempotent + callable per-game for arbitrary past games** — the shape the
Phase-5 Tuesday catch-up grade needs (grade whatever completed since the last run, re-grading an
already-graded game is a no-op). CLV uses each game's own ``closing_observation`` (per-game as-of-T,
from the append-only ``data/lines/`` store), never a single weekly cutoff.
"""

from __future__ import annotations

from typing import Any

from analytics.calibration_evidence import ats_outcome
from data.normalize.odds import closing_observation
from utils.prediction_schema import (
    GRADED_SCHEMA_VERSION,
    build_graded_record,
    clv,
)


def _gradable(result: dict | None) -> bool:
    if not result:
        return False
    return result.get("home_score") is not None and result.get("away_score") is not None


def grade_game(pred: dict, result: dict, closing_obs: dict | None, *, graded_at: str) -> dict:
    """Grade one prediction against its final ``result`` + its ``closing_obs`` (the game's as-of-T
    closing observation, or ``None`` if no closing line was captured). Pure — a function of the three
    inputs; deterministic apart from the caller-supplied ``graded_at`` stamp.

    ``closing_spread`` ← the closing observation's ``consensus_spread`` (``None`` = honest-missing);
    ``clv`` ← ``prediction_schema.clv`` (``None`` for no-side/neutral or no close); ``ats_result`` ←
    ``analytics.calibration_evidence.ats_outcome`` (the single ATS source of truth, push = ``abs<1e-9``).
    """
    close = closing_obs.get("consensus_spread") if closing_obs else None
    close_at = closing_obs.get("fetched_at") if closing_obs else None
    return build_graded_record(
        pred, result,
        closing_spread=close, close_as_of=close_at,
        clv_points=clv(pred.get("vegas_spread"), close, pred.get("edge_direction")),
        ats_result=ats_outcome(pred, result), graded_at=graded_at,
    )


def lines_key(pred: dict) -> str:
    """The ``data/lines/`` store key (``{AWAY}@{HOME}``) for a prediction. Team names are already
    canonical UPPERCASE throughout the pipeline (the snapshot builder writes the same key), so this
    does not re-normalize; it relies on that upstream invariant holding on both sides of the join."""
    return f"{pred.get('away_team')}@{pred.get('home_team')}"


def build_graded(predictions_env: dict, results: Any, lines_store: dict | None, *,
                 graded_at: str, meta_extra: dict | None = None) -> dict:
    """Grade a whole slate: predictions ⋈ results ⋈ lines → the graded envelope (mirrors
    ``analytics.predictions.build_predictions``). ``results`` may be a ``{game_id: result}`` map or a
    list of result dicts; ``lines_store`` is the loaded ``data/lines/`` dict (keyed ``{AWAY}@{HOME}``),
    or ``None`` (e.g. the 2025 retro has no closing lines → CLV honest-missing throughout).

    Games with no gradable result are surfaced in ``coverage.ungraded`` (never a half-null record).
    Deterministic ordering by ``game_id``.
    """
    results_by_id: dict[Any, dict] = (
        results if isinstance(results, dict) else {r.get("game_id"): r for r in (results or [])})
    preds = predictions_env.get("predictions", [])
    meta_in = predictions_env.get("meta", {})

    records: list[dict] = []
    ungraded: list[str] = []
    no_close: list[str] = []
    for pred in preds:
        gid = pred.get("game_id")
        result = results_by_id.get(gid)
        if not _gradable(result):
            ungraded.append(gid)
            continue
        assert result is not None  # narrowed by _gradable
        entry = (lines_store or {}).get(lines_key(pred))
        closing_obs = closing_observation(entry) if entry else None
        rec = grade_game(pred, result, closing_obs, graded_at=graded_at)
        records.append(rec)
        if rec["closing_spread"] is None:
            no_close.append(gid)

    records.sort(key=lambda r: r["game_id"])
    meta = {
        "schema_version": GRADED_SCHEMA_VERSION,
        "week": meta_in.get("week"),
        "year": meta_in.get("year"),
        "generated_at": graded_at,
        "engine": "grading_v1",
        "graded_count": len(records),
        "coverage": {"predicted": len(preds), "graded": len(records),
                     "ungraded": sorted(ungraded), "no_closing_line": sorted(no_close)},
    }
    if meta_extra:
        meta.update(meta_extra)
    return {"meta": meta, "graded": records}


def merge_graded(existing: dict | None, fresh: dict) -> tuple[dict, int]:
    """Idempotent append: preserve every already-graded entry as-is (immutable once graded — a
    re-grade is a no-op), add only game_ids not yet present. Returns ``(merged_envelope, n_added)``;
    ``n_added == 0`` ⇒ nothing new completed ⇒ the caller should not rewrite the file (true no-op).
    Mirrors ``data.snapshot.lines.record_observation`` semantics for the graded store.
    """
    by_id: dict[str, dict] = {r["game_id"]: r for r in (existing or {}).get("graded", [])}
    added = 0
    for rec in fresh.get("graded", []):
        if rec["game_id"] not in by_id:
            by_id[rec["game_id"]] = rec
            added += 1
    records = sorted(by_id.values(), key=lambda r: r["game_id"])
    no_close = [r["game_id"] for r in records if r["closing_spread"] is None]
    meta = dict(fresh.get("meta", {}))
    cov = dict(meta.get("coverage", {}))
    cov["graded"] = len(records)
    cov["no_closing_line"] = sorted(no_close)
    meta["coverage"] = cov
    meta["graded_count"] = len(records)
    return {"meta": meta, "graded": records}, added


def grade_fixture(predictions_env: dict, fixture: dict) -> dict:
    """Reproduce the SYNTHETIC graded golden from the committed v2 golden slate + the committed
    fixture of INVENTED finals/closings (``docs/examples/graded_fixture_2026_week_01.json``). Uses the
    real ``grade_game``; feeds each game a synthetic ``closing_obs`` from the fixture rather than a
    ``data/lines/`` store. The one path that stamps the envelope ``_synthetic: true`` (D22 golden
    rider). Shared by ``tests/test_phase4.py`` and ``scripts/verify_phase_4.py`` so the golden has a
    single reproduction source."""
    games = fixture["games"]
    graded_at = fixture["graded_at"]
    records: list[dict] = []
    ungraded: list[str] = []
    no_close: list[str] = []
    for pred in predictions_env.get("predictions", []):
        gid = pred.get("game_id")
        fx = games.get(gid)
        if fx is None:
            ungraded.append(gid)
            continue
        result = {"game_id": gid, "home_score": fx["home_score"], "away_score": fx["away_score"]}
        closing_obs = None
        if fx.get("closing_spread") is not None or fx.get("close_as_of") is not None:
            closing_obs = {"consensus_spread": fx["closing_spread"], "fetched_at": fx["close_as_of"]}
        rec = grade_game(pred, result, closing_obs, graded_at=graded_at)
        records.append(rec)
        if rec["closing_spread"] is None:
            no_close.append(gid)

    records.sort(key=lambda r: r["game_id"])
    return {
        "meta": {
            "schema_version": GRADED_SCHEMA_VERSION, "week": 1, "year": 2026,
            "generated_at": fixture["generated_at"], "engine": "grading_v1",
            "graded_count": len(records),
            "coverage": {"predicted": len(predictions_env.get("predictions", [])),
                         "graded": len(records), "ungraded": sorted(ungraded),
                         "no_closing_line": sorted(no_close)},
            "_synthetic": True,
            "note": ("SYNTHETIC illustrative golden — 2026 wk1 unplayed; finals INVENTED for schema "
                     "demonstration (D22 rider). Reproduced from the v2 golden slate + "
                     "docs/examples/graded_fixture_2026_week_01.json. See docs/SCHEMA.md §3a."),
        },
        "graded": records,
    }
