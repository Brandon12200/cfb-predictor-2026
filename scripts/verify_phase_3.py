#!/usr/bin/env python3
"""Executable acceptance criteria for Phase 3 — Factor System v2 (Calibrated Freeze, SPEC §7).

Phase 3 ships as sub-PRs 3a (foundations: decomposed pricer + calibration evidence) → 3b
(physical factors + reweight, L1) → 3c (situational discipline + NO_BET + confidence tiers,
L2/L4/L3) → 3d (schema v2 + converter + dry-run). This script encodes the checks a given
sub-PR satisfies and marks the rest PENDING — an honest running scorecard. Exits non-zero only
on real FAILs. Offline. Run via ``make verify-phase-3``.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

results: list[tuple[bool, str]] = []
pending: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((ok, name + (f" — {detail}" if detail else "")))


def todo(name: str) -> None:
    pending.append(name)


# === 3a — decomposed-and-shared pricer (D15) =================================
from engine.matchup_pricer import price  # noqa: E402
from engine.power_ratings import TeamRating  # noqa: E402

_ATHENS = {"name": "Sanford", "latitude": 33.9497, "longitude": -83.3733,
           "elevation": 220.0, "timezone": "America/New_York"}
_LA = {"name": "Coliseum", "latitude": 34.0141, "longitude": -118.2879,
       "elevation": 50.0, "timezone": "America/Los_Angeles"}


def _tr(t: str, e: float) -> TeamRating:
    return TeamRating(team=t, rating=e, games_played=6, prior_elo=e, prior_source="sp+")


_p = price("GEORGIA", "USC",
           ratings={"GEORGIA": _tr("GEORGIA", 1500), "USC": _tr("USC", 1500)},
           season_games=[{"week": 1, "home_team": "GEORGIA", "away_team": "USC",
                          "start_date": "2026-09-12T16:00:00Z", "completed": False}],
           venues={"GEORGIA": _ATHENS, "USC": _LA}, week=2, game_date="2026-09-12")
_decomp_ok = (abs(_p.base_margin + _p.schedule_component - _p.home_margin) < 1e-9
              and abs(_p.base_spread + _p.base_margin) < 1e-9
              and _p.schedule_component != 0
              and abs(_p.base_spread - _p.model_spread) > 1e-6)
check("pricer decomposed base/schedule/total; base excludes schedule (D15)", _decomp_ok,
      f"base={_p.base_spread:+.1f} schedule={_p.schedule_component:+.1f} total={_p.model_spread:+.1f}")

# Engine diagnostic uses the BASE gap and labels the total gap (circularity rule, D15).
_eng = (ROOT / "engine" / "prediction_engine.py").read_text()
check("engine exposes base gap + labeled total gap (D15 circularity rule)",
      "model_vs_market_gap_total" in _eng and "power_rating_base_spread" in _eng)
_wiring = (ROOT / "tests" / "test_power_rating_wiring.py").read_text()
check("circularity guard test present (gap uses base, not total)",
      "test_model_vs_market_gap_uses_base_not_total_when_schedule_fires" in _wiring)
check("decomposition test present (base+schedule==total)",
      "test_decomposition_base_plus_schedule_equals_total" in
      (ROOT / "tests" / "test_matchup_pricer.py").read_text())

# === 3a — calibration evidence harness (SPEC §3; read-only, no fit) ==========
from analytics.calibration_evidence import build_calibration_evidence  # noqa: E402

archive = ROOT / "data" / "archive" / "2025"
if archive.exists():
    ev = build_calibration_evidence(str(archive))
    # Convention sanity: a real contrarian season lands near 50%, not the flipped-convention 15%.
    ats = ev["overall"]["ats_win_pct"]
    conv_ok = ev["meta"]["graded"] > 250 and ats is not None and 0.35 < ats < 0.55
    check("calibration evidence harness grades the 2025 archive with the canonical ATS convention",
          conv_ok, f"{ev['meta']['graded']} graded, overall ATS {ats:.1%}")
    ev_file = ROOT / "data" / "calibration" / "2025_evidence.json"
    reproduces = ev_file.exists() and json.loads(ev_file.read_text()) == ev
    check("2025 evidence pack committed + reproducible from the archive", reproduces,
          "run `python scripts/build_calibration_evidence.py`" if not reproduces else "byte-stable")
else:
    check("calibration evidence harness grades the 2025 archive", False, "no data/archive/2025")

# D15/D16 recorded.
_dec = (ROOT / "docs" / "DECISIONS.md").read_text()
check("D15 (decomposed pricer) + D16 (2026 dry-run vehicle) recorded",
      "## D15 " in _dec and "## D16 " in _dec)

# === 3b — physical factor layer + reweight (L1), owner-ratified 2026-07-03 ====
from collections import defaultdict as _dd  # noqa: E402

from factors.factor_registry import factor_registry  # noqa: E402
from factors.physical_coefficients import DEFAULT_PHYSICAL_COEFFICIENTS as _PC  # noqa: E402
from factors.physical_coefficients import altitude_points as _ap  # noqa: E402
from factors.physical_coefficients import bye_points as _bp  # noqa: E402
from factors.physical_coefficients import physical_adjustments as _padj  # noqa: E402
from factors.physical_coefficients import short_week_points as _swp  # noqa: E402
from factors.physical_coefficients import travel_points as _tp  # noqa: E402

_PHYS = {"ByeAdvantage", "ShortWeek", "TravelBurden", "Altitude", "ConsecutiveRoad", "Sandwich"}
_loaded = set(factor_registry.factors)
check("6 physical sub-signal factors registered; old SchedulingFatigue + LookaheadSandwich retired",
      _PHYS <= _loaded and "SchedulingFatigue" not in _loaded and "LookaheadSandwich" not in _loaded,
      f"{sorted(_PHYS & _loaded)}")

# Each physical sub-signal appears separately in factor_breakdown on a firing context (SPEC §7.2).
_ctx = {"home_intel": {"bye": True, "altitude": 7000.0, "time_zones_crossed": 0},
        "away_intel": {"short_week": True, "time_zones_crossed": 3, "consecutive_road_games": 3,
                       "sandwich_spot": True},
        "neutral_site": False, "vegas_spread": -3.0}
_fb = set(factor_registry.calculate_all_factors("HOME", "AWAY", _ctx)["factors"])
check("each physical sub-signal appears separately in factor_breakdown (SPEC §7.2)", _PHYS <= _fb)

# Pricer/factor single source (D15): model-spread subset == Σ shared fatigue/location fns; the two
# contrarian-only signals stay out of the model spread.
_hi, _ai = {"bye": True, "altitude": 7000.0}, {"short_week": True, "time_zones_crossed": 3}
_total, _parts = _padj(_hi, _ai, False)
_manual = _bp(_hi, _ai) + _swp(_hi, _ai) + _tp(_hi, _ai) + _ap(_hi, False)
check("pricer schedule adjustment == Σ shared fatigue/location coefficients (D15 single source)",
      abs(_total - _manual) < 1e-9 and "consecutive_road" not in _parts and "sandwich" not in _parts)

# Contribution budget (weight-based tripwire, ratified): physical dominant, no runaway factor.
_add = {n: f for n, f in factor_registry.factors.items() if not f.is_multiplicative}
_tw = sum(f.weight for f in _add.values())
_cat = _dd(float)
for _n, _f in _add.items():
    _cat[_f.category] += _f.weight / _tw
_max_single = max(f.weight / _tw for f in _add.values())
_ratio = _cat["physical"] / _cat["situational_context"]
check("factor-contribution budget: no single factor >15%, physical:situational >=2:1 (tripwire)",
      _max_single < 0.15 and _ratio >= 2.0,
      f"max single {_max_single:.0%}, physical {_cat['physical']:.0%}, phys:sit {_ratio:.1f}:1")

check("travel_cap ratified at 1.5 (0.6 HFA — humility on an unmeasured extreme)",
      abs(_PC.travel_cap - 1.5) < 1e-9)

_cal = (ROOT / "docs" / "CALIBRATION_LOG.md").read_text()
check("CALIBRATION_LOG carries the 3b batch (coefficients, reweight, budget, retirements, base-calc fix)",
      "Phase 3b" in _cal and "travel_cap" in _cal and "activation" in _cal.lower())

# === 3c — situational discipline + NO_BET + confidence tiers (L2/L4/L3) ========
# Fabrication extermination tripwire (owner rider): the MD5-hash-of-team-name + hardcoded-team
# pattern was ONE author's template in SIX factors (market sentiment #7, desperation, revenge,
# momentum ×2, coaching pressure — Bugs #12–14). The Phase-1 grep only caught conference-name
# lists + random.*, so the team-name-hash cousins slipped through. factors/ READ data — they
# never hash or randomise (the snapshot layer legitimately hashes, which is why this scan is
# factors/-scoped, not repo-wide). This is the repo-wide extermination tool.
_FACT_FILES = sorted((ROOT / "factors").rglob("*.py"))
_fab_tokens = ("hashlib", "md5", "random.")
_fab_hits = [f"{_pf.relative_to(ROOT).as_posix()}:{_i}"
             for _pf in _FACT_FILES
             for _i, _ln in enumerate(_pf.read_text().splitlines(), 1)
             if any(tok in _ln for tok in _fab_tokens)]
check("no hash/random fabrication tell-tales anywhere in factors/ (Bug #7/#12–14 tripwire)",
      not _fab_hits, "; ".join(_fab_hits) if _fab_hits else "clean")

# L2 neutralization — the fabricated fallbacks + hardcoded team tables are gone (binding #2/#4).
_sit_blob = ((ROOT / "factors" / "situational_context.py").read_text()
             + (ROOT / "factors" / "momentum_factors.py").read_text()
             + (ROOT / "factors" / "coaching_edge.py").read_text())
_removed = ("_simulate_desperation", "_simulate_differential_trend", "_simulate_clutch_performance",
            "revenge_scenarios", "bubble_teams", "clutch_teams")
check("situational/momentum/coaching fabrication fallbacks removed (L2 neutralization)",
      not any(tok in _sit_blob for tok in _removed))

# L2 confirming-signal gate (SPEC §7.3 / D15): a situational factor contributes only if the BASE
# gap or an activated physical factor agrees in direction; solo situational guesses are withheld.
from factors.factor_registry import confirm_situational  # noqa: E402


def _sit(v):
    return {"factor_name": "D", "category": "situational_context", "value": v, "activated": True}


def _phys(v):
    return {"factor_name": "P", "category": "physical", "value": v, "activated": True}


_l2_ok = (confirm_situational([_sit(1.2)], None) == {"D"}                    # no corroboration -> withheld
          and confirm_situational([_sit(1.2)], 2.0) == set()                # base gap agrees -> kept
          and confirm_situational([_sit(1.2)], -2.0) == {"D"}               # base gap disagrees -> withheld
          and confirm_situational([_sit(1.2), _phys(0.8)], -2.0) == set())  # physical agrees -> kept
check("L2 confirming-signal gate: situational withheld unless base gap or a physical factor agrees (D15 base-only)",
      _l2_ok)

# Cleanup items folded into the confidence rework.
from factors.coaching_edge import ExperienceDifferentialCalculator  # noqa: E402
from factors.market_sentiment import MarketSentimentCalculator  # noqa: E402

_ms = MarketSentimentCalculator().safe_calculate("A", "B", {"week": 5, "vegas_spread": -3.0})
check("dormant multiplicative modifier at 1.0 is NOT counted activated (avg_confidence not diluted)",
      _ms["activated"] is False and abs(_ms["value"] - 1.0) < 1e-9)

_none_ctx = {"coaching_comparison": {"home_coaching": {"head_coach_experience": None, "tenure_years": None},
                                     "away_coaching": {"head_coach_experience": 5, "tenure_years": 3}}}
_ed = ExperienceDifferentialCalculator().safe_calculate("A", "B", _none_ctx)
check("ExperienceDifferential handles None/missing coaching data (honest-missing 0.0, no crash)",
      _ed["value"] == 0.0 and _ed.get("error") is None)

# L4 NO_BET acceptance — the 2026 wk1 dry-run (D16 vehicle) has no completed games/records, so
# every factor is dormant and edges collapse; the floors correctly refuse to bet a no-signal slate.
# Asserting this so nobody mistakes an empty bettable slate for breakage in August — selectivity
# working as DESIGNED, not a bug.
_snap_f = ROOT / "data" / "snapshots" / "2026_week_01" / "snapshot.json"
if _snap_f.exists():
    import logging as _lg  # noqa: E402
    from engine.prediction_engine import PredictionEngine  # noqa: E402
    _lg.disable(_lg.CRITICAL)
    _eng2 = PredictionEngine()
    _types = []
    for _line in json.loads(_snap_f.read_text())["data"]["betting_lines"].values():
        _h, _a = _line.get("home_team"), _line.get("away_team")
        if _h and _a:
            _types.append(_eng2.generate_prediction(_h, _a, week=1).get("prediction_type"))
    _lg.disable(_lg.NOTSET)
    check("L4 NO_BET: 2026 wk1 dry-run slate is all NO_BET (no signal preseason — selectivity, not breakage)",
          len(_types) > 0 and all(t == "NO_BET" for t in _types),
          f"{_types.count('NO_BET')}/{len(_types)} NO_BET")
else:
    check("L4 NO_BET dry-run slate", False, "no 2026 wk1 snapshot")

# L3 confidence tiers — monotonic in confidence_score is a STRUCTURAL sanity check on the NEW
# model (SPEC §3/§7.5), NEVER a 2025-ATS gate (the archive confidence→ATS table is inadmissible).
# Synthetic confidence sweep, in the spirit of the D9 dispersion test.
from engine.prediction_engine import CONFIDENCE_TIER_B_MIN, NO_BET_CONFIDENCE_FLOOR  # noqa: E402
from engine.prediction_engine import PredictionEngine as _PE  # noqa: E402

_pe = _PE()
_rank = {"A": 3, "B": 2, "C": 1, None: 0}
_scores = [i / 100 for i in range(15, 96, 5)]
_tiers = [_pe._confidence_tier(s, "MODERATE_CONTRARIAN") for s in _scores]
_l3_ok = (all(_rank[_tiers[i]] <= _rank[_tiers[i + 1]] for i in range(len(_tiers) - 1))
          # confidence floor == B/C boundary -> tier C is never a live bet grade (only a NO_BET diagnostic)
          and NO_BET_CONFIDENCE_FLOOR == CONFIDENCE_TIER_B_MIN
          and _pe._confidence_tier(0.30, "NO_BET") == "C"
          and _pe._confidence_tier(0.9, "NO_BETTING_DATA") is None)
check("L3 tiers monotonic in confidence_score; C is a NO_BET diagnostic grade, never a bet (floor==B/C boundary)",
      _l3_ok)

# The consolidated, evidence-class-labeled 3c batch is recorded.
check("CALIBRATION_LOG carries the 3c batch (neutralization, thresholds, NO_BET floors, tiers), evidence-class labeled",
      "Phase 3c" in _cal and "NO_BET" in _cal and "reasoned" in _cal and "neutraliz" in _cal.lower())

# === 3d — PENDING (freeze-disciplined; ratify before the tag) ==================
todo("prediction schema v2 + 2025 converter + 2026 dry-run acceptance (3d)")

# --- Report -------------------------------------------------------------------
print("Phase 3 acceptance checks:")
failed = 0
for ok, name in results:
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
    failed += not ok
for name in pending:
    print(f"  [PENDING] {name}")

print("\nRunning full test suite (make test)...")
suite = subprocess.run([sys.executable, "-m", "pytest", "-q"], cwd=str(ROOT))
suite_ok = suite.returncode == 0
print(f"  [{'PASS' if suite_ok else 'FAIL'}] full test suite")
failed += not suite_ok

_pending_note = f" ({len(pending)} pending — 3d)" if pending else " — Phase 3 complete"
print(f"\n{'ALL PHASE 3 CHECKS PASSED' if failed == 0 else f'{failed} CHECK(S) FAILED'}"
      f"{_pending_note}")
sys.exit(1 if failed else 0)
