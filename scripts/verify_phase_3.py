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

# === 3c / 3d — PENDING (freeze-disciplined; ratify before the tag) ============
todo("situational thresholds + confirming-factor via base gap (L2, 3c)")
todo("NO_BET first-class prediction type — edge/confidence/variance floors (L4, 3c)")
todo("confidence v2 A/B/C tiers, monotonic-ATS% gated (L3, 3c) — CALIBRATION_LOG batch")
todo("prediction schema v2 + 2025 converter + 2026 dry-run acceptance (3d)")
todo("CALIBRATION_LOG evidence-class-labeled entry for every changed number (3c)")

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

_pending_note = f" ({len(pending)} pending — 3b/3c/3d)" if pending else " — Phase 3 complete"
print(f"\n{'ALL PHASE 3 CHECKS PASSED' if failed == 0 else f'{failed} CHECK(S) FAILED'}"
      f"{_pending_note}")
sys.exit(1 if failed else 0)
