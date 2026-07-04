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

# === 3b / 3c / 3d — PENDING (freeze-disciplined; ratify before the tag) ======
todo("physical factors from schedule-intel; each sub-signal in factor_breakdown (L1, 3b)")
todo("reweight toward physical + factor-contribution-budget gate (L1, 3b) — CALIBRATION_LOG batch")
todo("situational thresholds + confirming-factor via base gap (L2, 3c)")
todo("NO_BET first-class prediction type — edge/confidence/variance floors (L4, 3c)")
todo("confidence v2 A/B/C tiers, monotonic-ATS% gated (L3, 3c) — CALIBRATION_LOG batch")
todo("prediction schema v2 + 2025 converter + 2026 dry-run acceptance (3d)")
todo("CALIBRATION_LOG evidence-class-labeled entry for every changed number (3b/3c)")

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
