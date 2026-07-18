#!/usr/bin/env python3
"""Executable acceptance criteria for Phase 4 — Measurement & Analytics v2 (SPEC §8).

Phase 4 is measurement built to the frozen conventions — no calibration batches. It grades
predictions into a SEPARATE append-only artifact (D22: prediction files are byte-immutable; the
"filled" record is a JOIN), computes CLV / calibration / KPIs / per-factor attribution / selectivity,
and renders markdown reports. Acceptance: the analytics over the 2025 archive reproduce the honest
D17 baseline (~46.6% ATS), and the grading path is pinned to the canonical schema-v2 golden.

Offline. Run via ``make verify-phase-4``. Exits non-zero only on real FAILs.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

results: list[tuple[bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((ok, name + (f" — {detail}" if detail else "")))


# === schema gate: D22 + the graded-record schema + the clv neutral fix ==========================
from utils.prediction_schema import (  # noqa: E402
    GRADED_RECORD_KEYS,
    GRADED_SCHEMA_VERSION,
    build_graded_record,
    clv,
)

_dec = (ROOT / "docs" / "DECISIONS.md").read_text()
check("D22 recorded (grading writes a separate artifact; predictions byte-immutable)",
      "## D22 " in _dec and "byte-immutable" in _dec)

_schema = (ROOT / "docs" / "SCHEMA.md").read_text()
check("SCHEMA §3a documents the graded artifact + graded_at reproducibility carve-out",
      "3a. Graded artifact" in _schema and "reproducibility carve-out" in _schema.lower()
      and "GRADED_RECORD_KEYS" in _schema)

# f3 — CLV is null (never 0.0) for a no-side game; 0.0 is a legit value for a taken side.
check("clv() neutral/no-side returns None, never 0.0 (f3)",
      clv(-3.0, -4.0, "neutral") is None and clv(2.8, 2.8, None) is None
      and clv(2.8, 2.8, "home") == 0.0)

# === grading core: golden pin + full ATS ternary + idempotency + per-game as-of-T ===============
from analytics.grading import build_graded, grade_fixture, grade_game, merge_graded  # noqa: E402
from analytics.calibration_evidence import ats_outcome  # noqa: E402
from data.normalize.odds import closing_observation  # noqa: E402

_V2 = json.loads((ROOT / "docs/examples/prediction_schema_v2_2026_week_01.json").read_text())
_FIX = json.loads((ROOT / "docs/examples/graded_fixture_2026_week_01.json").read_text())
_GOLDEN = json.loads((ROOT / "docs/examples/graded_record_2026_week_01.json").read_text())

_repro = grade_fixture(_V2, _FIX)
check("graded golden reproduces byte-identical from the v2 golden slate + committed fixture",
      json.dumps(_repro, sort_keys=True) == json.dumps(_GOLDEN, sort_keys=True))
check("graded records match the ratified key inventory + schema_version, and announce _synthetic",
      GRADED_SCHEMA_VERSION == 1 and _GOLDEN["meta"]["_synthetic"] is True
      and all(set(r) == set(GRADED_RECORD_KEYS) for r in _GOLDEN["graded"]))

# Requirement-2: grading the canonical v2 record exercises the FULL ATS ternary (win/loss/push/null).
# Each outcome is its own check so a regression pinpoints the broken game, not one opaque line.
_by = {r["game_id"]: r for r in _GOLDEN["graded"]}
check("golden ATS 'win' + clv +1.0 (clemson-vs-lsu)",
      _by["clemson-vs-lsu-week1"]["ats_result"] == "win" and _by["clemson-vs-lsu-week1"]["clv"] == 1.0)
check("golden ATS 'loss' with honest-missing close ⇒ closing/clv null, ats present (miami-vs-stanford)",
      _by["miami-vs-stanford-week1"]["ats_result"] == "loss"
      and _by["miami-vs-stanford-week1"]["closing_spread"] is None
      and _by["miami-vs-stanford-week1"]["clv"] is None)
check("golden no-side (neutral) ⇒ ats/clv null even with a captured close (baylor-vs-auburn, f3)",
      _by["baylor-vs-auburn-week1"]["ats_result"] is None
      and _by["baylor-vs-auburn-week1"]["clv"] is None
      and _by["baylor-vs-auburn-week1"]["closing_spread"] == -7.0)
check("golden clv exactly 0.0 is a legit value for a taken side (smu-vs-florida-state)",
      _by["smu-vs-florida-state-week1"]["clv"] == 0.0)
# push needs an integer line the golden can't provide → pinned on a crafted v2-shaped record.
_push_pred = {"game_id": "x-vs-y-week1", "home_team": "Y", "away_team": "X", "week": 1,
              "vegas_spread": -7.0, "edge_direction": "home", "no_bet": False,
              "prediction_type": "SLIGHT_CONTRARIAN"}
check("ATS 'push' ternary (margin + spread == 0, integer line)",
      ats_outcome(_push_pred, {"home_score": 28, "away_score": 21}) == "push")

# Idempotent + per-game: grade_game is pure; merge_graded is a no-op when nothing new completed.
_g1 = grade_game(_push_pred, {"home_score": 28, "away_score": 21}, None, graded_at="t")
_g2 = grade_game(_push_pred, {"home_score": 28, "away_score": 21}, None, graded_at="t")
_merged, _added = merge_graded({"graded": [_g1]}, {"meta": {}, "graded": [_g1]})
check("grade_game idempotent + merge_graded is a no-op on already-graded games (Phase-5 catch-up)",
      _g1 == _g2 and _added == 0)

# Per-game as-of-T close (SPEC §5.4.3): the last observation ≤ THAT game's kickoff, not a weekly cutoff.
_entry = {"kickoff": "2026-09-05T00:00:00+00:00",
          "observations": [{"fetched_at": "2026-09-02T12:00:00+00:00", "consensus_spread": -3.0},
                           {"fetched_at": "2026-09-04T23:00:00+00:00", "consensus_spread": -3.5},
                           {"fetched_at": "2026-09-06T12:00:00+00:00", "consensus_spread": -4.0}]}
_close = closing_observation(_entry)
check("closing_observation picks the last obs before each game's own kickoff (per-game as-of-T)",
      _close is not None and _close["consensus_spread"] == -3.5)

# === immutability: data/graded/ is guarded (append-only, like data/lines/) =======================
_hook = (ROOT / ".claude" / "hooks" / "protect_immutable.py").read_text()
check("immutability hook guards data/graded/ (append-only graded store)", "data/graded/" in _hook)

# === attribution answers the reasoned entries; unavailable (never faked) on v1-flat ==============
from analytics.attribution import per_factor  # noqa: E402
from analytics.join import join  # noqa: E402
from utils.prediction_schema import convert_v1_to_v2  # noqa: E402

_attr = per_factor(join(_V2, _GOLDEN))
_tb = _attr["factors"].get("TravelBurden", {})
check("per-factor attribution measures per-sub-signal ATS%/CLV when a factor fired (reasoned→measured)",
      _attr["meta"]["attributable"] is True and _tb.get("n_activated") == 4
      and _tb.get("wins") == 2 and _tb.get("losses") == 2)

_arch1 = json.loads((ROOT / "data/archive/2025/predictions/2025_week_01.json").read_text())
_v1joined = [convert_v1_to_v2(p) for p in _arch1["predictions"]]
for _r in _v1joined:
    _r["ats_result"] = "win"
check("per-factor attribution is honestly UNAVAILABLE on the v1-flat 2025 archive (never faked)",
      per_factor(_v1joined)["meta"]["attributable"] is False)

# === acceptance: the 2025 retro reproduces the honest D17 baseline ================================
from analytics.kpis import kpi_pack  # noqa: E402

_all_graded = []
for _pf in sorted((ROOT / "data/archive/2025/predictions").glob("*.json")):
    _wk = int(_pf.stem.split("_week_")[1])
    _v1 = json.loads(_pf.read_text())
    _env = {"meta": {"week": _wk, "year": 2025},
            "predictions": [convert_v1_to_v2(p) for p in _v1["predictions"]]}
    _res = json.loads((ROOT / f"data/archive/2025/results/2025_week_{_wk:02d}_results.json").read_text())
    _all_graded += build_graded(_env, _res["results"], None, graded_at="t")["graded"]
_pack = kpi_pack(_all_graded)
_ats = _pack["ats"]["ats_win_pct"]
check("2025 retro reproduces the honest D17 baseline (~46.6% ATS over 294 bets, negative ROI)",
      _pack["ats"]["n_graded"] == 294 and _ats is not None and 0.45 <= _ats <= 0.48
      and _pack["roi_at_110"]["roi"] < 0, f"{_ats:.1%} ATS, ROI {_pack['roi_at_110']['roi']:.1%}")

# === acceptance: the retro report generates (SPEC §8) ============================================
_retro = subprocess.run([sys.executable, "scripts/build_reports.py", "--retro"], cwd=str(ROOT),
                        capture_output=True, text=True)
_retro_md = ROOT / "reports" / "2025_retro.md"
check("`build_reports.py --retro` renders reports/2025_retro.md (full retro report)",
      _retro.returncode == 0 and _retro_md.exists()
      and "2025 Retro" in _retro_md.read_text() and "46.6%" in _retro_md.read_text())

# --- Report -------------------------------------------------------------------
print("Phase 4 acceptance checks:")
failed = 0
for ok, name in results:
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
    failed += not ok

print("\nRunning full test suite (make test)...")
suite = subprocess.run([sys.executable, "-m", "pytest", "-q"], cwd=str(ROOT))
failed += suite.returncode != 0
print(f"  [{'PASS' if suite.returncode == 0 else 'FAIL'}] full test suite")

print(f"\n{'ALL PHASE 4 CHECKS PASSED' if failed == 0 else f'{failed} CHECK(S) FAILED'}")
sys.exit(1 if failed else 0)
