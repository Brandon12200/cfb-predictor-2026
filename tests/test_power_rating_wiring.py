"""Engine wiring of the power-rating diagnostic (SPEC §6.6): real predictions log
`power_rating_spread` + `model_vs_market_gap` + `rating_uncertainty`, computed from the
snapshot on the context, and these are DIAGNOSTIC ONLY — they never alter the contrarian
edge/recommendation in 2026."""

from __future__ import annotations

from engine.prediction_engine import prediction_engine
from tests.context_factory import make_context, patched_context


def _games(home, away):
    # A short completed history so the pricer has real (non-flat) ratings to price.
    return [
        {"week": 1, "home_team": home, "away_team": "CUPCAKE", "home_points": 45,
         "away_points": 3, "completed": True, "start_date": "2026-09-05", "neutral_site": False},
        {"week": 1, "home_team": "PATSY", "away_team": away, "home_points": 40,
         "away_points": 7, "completed": True, "start_date": "2026-09-05", "neutral_site": False},
        {"week": 2, "home_team": home, "away_team": away, "home_points": None,
         "away_points": None, "completed": False, "start_date": "2026-09-12", "neutral_site": False},
    ]


def test_real_prediction_logs_model_and_market():
    with patched_context(vegas_spread=-7.0, games=_games("GEORGIA", "ALABAMA"),
                         snapshot_id="wiring_test_1"):
        r = prediction_engine.generate_prediction("Georgia", "Alabama", week=2)
    assert r.get("vegas_spread") == -7.0
    assert isinstance(r.get("power_rating_spread"), (int, float))
    assert isinstance(r.get("model_vs_market_gap"), (int, float))
    assert isinstance(r.get("rating_uncertainty"), (int, float))
    # gap = model - market, by definition
    assert abs(r["model_vs_market_gap"] - (r["power_rating_spread"] - r["vegas_spread"])) < 1e-6
    assert isinstance(r.get("power_rating_breakdown"), dict)


def test_power_rating_is_diagnostic_only(monkeypatch):
    """The contrarian edge/recommendation must be identical whether or not the power
    rating is computed — it does NOT feed the 2026 edge (§6.6)."""
    ctx_kwargs = dict(vegas_spread=-7.0, games=_games("GEORGIA", "ALABAMA"))
    with patched_context(snapshot_id="wiring_test_2", **ctx_kwargs):
        full = prediction_engine.generate_prediction("Georgia", "Alabama", week=2)

    # Reprice with the power-rating step neutered → edge/recommendation must be unchanged.
    monkeypatch.setattr(prediction_engine, "_compute_power_rating", lambda *a, **k: None)
    with patched_context(snapshot_id="wiring_test_3", **ctx_kwargs):
        without = prediction_engine.generate_prediction("Georgia", "Alabama", week=2)

    assert full["contrarian_spread"] == without["contrarian_spread"]
    assert full["edge_size"] == without["edge_size"]
    assert full["edge_direction"] == without["edge_direction"]
    assert full["recommendation"] == without["recommendation"]
    # ...but only the full run carries the diagnostic.
    assert full["power_rating_spread"] is not None
    assert without["power_rating_spread"] is None


def test_model_vs_market_gap_uses_base_not_total_when_schedule_fires():
    # D15 circularity guard: when a schedule adjustment is present (USC travels 3 tz east to
    # Athens), the confirming-signal lane `model_vs_market_gap` must be the BASE gap (team
    # quality, excludes schedule) — NOT the total gap. A schedule factor can't be confirmed by
    # a gap that already contains the same schedule signal.
    athens = {"name": "Sanford", "latitude": 33.9497, "longitude": -83.3733,
              "elevation": 220.0, "timezone": "America/New_York"}
    la = {"name": "Coliseum", "latitude": 34.0141, "longitude": -118.2879,
          "elevation": 50.0, "timezone": "America/Los_Angeles"}
    games = [{"week": 2, "home_team": "GEORGIA", "away_team": "USC", "home_points": None,
              "away_points": None, "completed": False, "start_date": "2026-09-12",
              "neutral_site": False}]
    context = {"snapshot_id": "d15_gap_test", "games": games, "sp_ratings": {},
               "returning_production": {}, "venues": {"GEORGIA": athens, "USC": la},
               "neutral_site": False, "game_date": "2026-09-12"}
    pr = prediction_engine._compute_power_rating("GEORGIA", "USC", 2, -3.0, context)
    assert pr is not None
    # schedule fired → the two gaps genuinely differ
    assert pr["model_vs_market_gap"] != pr["model_vs_market_gap_total"]
    # the confirming lane is the BASE gap (excludes schedule)
    assert abs(pr["model_vs_market_gap"] - (pr["power_rating_base_spread"] - (-3.0))) < 0.02
    # the labeled total gap includes schedule (diagnostic only, never confirms)
    assert abs(pr["model_vs_market_gap_total"] - (pr["power_rating_spread"] - (-3.0))) < 0.02


def test_missing_snapshot_context_skips_power_rating_gracefully():
    # A minimal context without snapshot_id/games must not crash; fields are None.
    ctx = make_context(home="GEORGIA", away="ALABAMA", week=2)
    ctx.pop("snapshot_id", None)
    ctx["games"] = None
    r = prediction_engine._build_prediction_result(
        "GEORGIA", "ALABAMA", 2, -7.0, {"factors": {}, "summary": {}},
        {"contrarian_spread": -8.0, "edge_size": 1.0}, ctx, None,
        prediction_engine._compute_power_rating("GEORGIA", "ALABAMA", 2, -7.0, ctx))
    assert r["power_rating_spread"] is None and r["rating_uncertainty"] is None
