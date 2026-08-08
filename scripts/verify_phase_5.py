#!/usr/bin/env python3
"""Executable acceptance criteria for Phase 5 — Automation Pipeline (SPEC §10).

SPEC §10 acceptance: a full simulated cycle against archived data in CI with mocked APIs; a live
end-to-end preseason dry-run; no step requiring manual intervention. `PHASE5_NOTES` §3 expands it
with the preseason validation regimen (two rehearsals + a failure-injection drill + a graded Week-1
dress rehearsal), which is exercised on real runs and tracked on `docs/FREEZE_CHECKLIST.md` — the
checks here are the parts a machine can assert.

Offline. Run via ``make verify-phase-5``. Exits non-zero only on real FAILs.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

results: list[tuple[bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((ok, name + (f" — {detail}" if detail else "")))


SEASON = json.loads((ROOT / "season.json").read_text())
PIPELINE = SEASON.get("pipeline", {})
WORKFLOWS = ROOT / ".github" / "workflows"
ACTIONS = ROOT / ".github" / "actions"

# === §10.6 — the config home is extended, not replaced (D24) =====================================

check("season.json carries the §10.6 pipeline block", bool(PIPELINE),
      f"{len(PIPELINE)} keys")
check("the Phase-4.5 config home is untouched (weeks + cli_defaults still present, D24)",
      "weeks" in SEASON and "cli_defaults" in SEASON and len(SEASON["weeks"]) == 15)
check("freeze tag recorded in config", PIPELINE.get("freeze_tag") == "v2026-frozen",
      str(PIPELINE.get("freeze_tag")))
check("slate filter is FBS-vs-FBS (SPEC §16.1)", PIPELINE.get("slate_filter") == "fbs_vs_fbs")

# Every pipeline key must have a consumer. A key nothing reads is config theatre, and the
# key→consumer table in docs/PIPELINE.md is what this asserts against.
_PIPELINE_DOC = (ROOT / "docs" / "PIPELINE.md")
_doc_text = _PIPELINE_DOC.read_text() if _PIPELINE_DOC.exists() else ""
_undocumented = [k for k in PIPELINE if not k.startswith("_") and k not in ("dst_note",)
                 and f"`{k}`" not in _doc_text]
check("every season.json pipeline key appears in docs/PIPELINE.md's key→consumer table",
      _PIPELINE_DOC.exists() and not _undocumented,
      "missing: " + ", ".join(_undocumented) if _undocumented else "all documented")

# === Workflows exist and agree with the config ===================================================

_expected_workflows = ["weekly-predict.yml", "daily-capture.yml", "weekly-grade.yml",
                       "ci.yml", "freeze-integrity.yml"]
check("the three cadence workflows + CI + freeze-integrity exist",
      all((WORKFLOWS / f).exists() for f in _expected_workflows),
      ", ".join(f for f in _expected_workflows if not (WORKFLOWS / f).exists()) or "all present")
check("the four composite actions exist",
      all((ACTIONS / a / "action.yml").exists()
          for a in ("cfb-setup", "cfb-commit", "report-failure", "clear-failure")))

_CRON = re.compile(r'^\s*-\s*cron:\s*["\']([^"\']+)["\']', re.M)


def _crons(name: str) -> set[str]:
    return {" ".join(c.split()) for c in _CRON.findall((WORKFLOWS / name).read_text())}


_job_file = {"predict": "weekly-predict.yml", "capture": "daily-capture.yml",
             "grade": "weekly-grade.yml", "freeze_integrity": "freeze-integrity.yml"}
_mismatched = [
    job for job, f in _job_file.items()
    if _crons(f) != {" ".join(e["cron_utc"].split()) for e in PIPELINE["schedule_et"][job]}
]
check("workflow crons match season.json schedule_et (duplicated schedules cannot drift)",
      not _mismatched, "mismatched: " + ", ".join(_mismatched) if _mismatched else "all agree")

# Without tags, `git describe --always` returns a bare SHA and every claim of the season would be
# stamped with a commit hash where the freeze tag belongs.
_missing_depth = [f for f in _expected_workflows
                  if (WORKFLOWS / f).read_text().count("fetch-depth: 0")
                  < (WORKFLOWS / f).read_text().count("actions/checkout@") - (1 if f == "ci.yml" else 0)]
check("every pipeline job checks out with fetch-depth: 0 (tags → model_version + freeze proof)",
      not _missing_depth, ", ".join(_missing_depth) or "all jobs")

_cadence = ["weekly-predict.yml", "daily-capture.yml", "weekly-grade.yml"]
check("cadence workflows share one concurrency group and are never cancelled mid-run",
      all("group: cfb-pipeline-${{ github.ref }}" in (WORKFLOWS / f).read_text()
          and "cancel-in-progress: false" in (WORKFLOWS / f).read_text() for f in _cadence))

# === The cadence is the binding one (PHASE5_NOTES §1) ============================================

_predict = (WORKFLOWS / "weekly-predict.yml").read_text()
check("Tuesday grades BEFORE it predicts (catch-up first)",
      _predict.index("Catch-up grade") < _predict.index("Build predictions"))
check("the snapshot is committed BEFORE predictions are built (model_version --dirty)",
      _predict.index("paths: data/snapshots") < _predict.index("Build predictions"))
check("the claim commit stages data/predictions alone (pre-registration artifact, D22)",
      _predict.split("paths: data/predictions", 1)[1].splitlines()[0].strip() == "")
check("the predict step is skipped when the byte-immutable claim already exists (idempotency)",
      "steps.setup.outputs.prediction_exists != 'true'" in _predict)

_capture = (WORKFLOWS / "daily-capture.yml").read_text()
check("line capture is daily Wed–Sat, not Saturday-only (PHASE5_NOTES §1)",
      "3,4,5" in _capture and _capture.count("* * 6") >= 2)
check("a budget refusal (exit 3) leaves the capture job green and commits nothing",
      "rc == '3'" in _capture and "rc != '0' && steps.capture.outputs.rc != '3'" in _capture)

_grade = (WORKFLOWS / "weekly-grade.yml").read_text()
check("Sunday commits results, graded and reports as separate tier commits (D22/D23)",
      all(_grade.count(f"paths: {p}") == 1 for p in ("data/results", "data/graded", "reports")))

# === Failure path + budget guard (SPEC §10.4, §10.5) =============================================

check("every cadence workflow opens an auto-Issue on failure and clears it on recovery",
      all("actions/report-failure" in (WORKFLOWS / f).read_text()
          and "actions/clear-failure" in (WORKFLOWS / f).read_text() for f in _cadence))
_rf = (ACTIONS / "report-failure" / "action.yml").read_text()
check("auto-Issue dedupes by label (the issue search index lags) and cools down its comments",
      "--label" in _rf and "cooldown-minutes" in _rf and "gh issue comment" in _rf)
check("auto-Issue attaches logs (artifact upload + inline tail)",
      "upload-artifact" in _rf and "tail -n 120" in _rf)
check("pipeline logs remaining Odds quota every run (SPEC §10.5)",
      "GITHUB_STEP_SUMMARY" in (ROOT / "scripts" / "pipeline_preflight.py").read_text())

from scripts.fetch_lines import EXIT_BUDGET_REFUSAL  # noqa: E402

check("the Odds budget guard is a distinct exit code, not a stdout string match",
      EXIT_BUDGET_REFUSAL == 3)

# === The freeze holds (this phase must not move the model) =======================================

_tag = PIPELINE.get("freeze_tag", "v2026-frozen")
_trees = {d: (subprocess.run(["git", "rev-parse", f"HEAD:{d}"], capture_output=True, text=True,
                             cwd=str(ROOT)).stdout.strip(),
              subprocess.run(["git", "rev-parse", f"{_tag}:{d}"], capture_output=True, text=True,
                             cwd=str(ROOT)).stdout.strip())
          for d in ("factors", "engine")}
check(f"factors/ and engine/ are tree-identical to {_tag} (Phase 5 is freeze-exempt throughout)",
      all(h and h == t for h, t in _trees.values()),
      ", ".join(f"{d}: {'match' if h == t else 'DRIFT'}" for d, (h, t) in _trees.items()))

from data.snapshot.store import FROZEN_VEHICLE, frozen_vehicle_sha256  # noqa: E402

check("the freeze gate's pinned vehicle is present under the append-only tier (D29)",
      FROZEN_VEHICLE.exists() and "data/archive/" in FROZEN_VEHICLE.as_posix(),
      frozen_vehicle_sha256()[:16] + "…" if FROZEN_VEHICLE.exists() else "missing")

# === The operational week resolver (F2) ==========================================================

from utils.season_calendar import WeekInferenceError, pipeline_week, resolve_week  # noqa: E402

_week1_dates = [date(2026, 8, 25), date(2026, 8, 26), date(2026, 8, 27), date(2026, 8, 28)]
check("pipeline_week resolves the week-1 run dates (Tue 08-25 → Fri 08-28) to week 1",
      all(pipeline_week(d) == 1 for d in _week1_dates),
      ", ".join(f"{d}→{pipeline_week(d)}" for d in _week1_dates))

try:
    resolve_week(None, today=date(2026, 8, 25))
    _still_raises = False
except WeekInferenceError:
    _still_raises = True
check("the game-window resolver is unchanged and still raises there (two distinct questions)",
      _still_raises)

_d = date(2026, 8, 1)
_never_raises, _prev, _monotonic = True, 0, True
while _d <= date(2026, 12, 31):
    try:
        _w = pipeline_week(_d)
        _monotonic &= _w >= _prev
        _prev = _w
    except Exception:
        _never_raises = False
        break
    _d = date.fromordinal(_d.toordinal() + 1)
check("pipeline_week never raises and never goes backwards across the whole season",
      _never_raises and _monotonic)

# === The Sunday reporting gate (D-8) =============================================================

_has_split = "edge_direction" in (ROOT / "analytics" / "attribution.py").read_text()
_gated = "steps.report_gate.outputs.ready == 'true'" in _grade
check("the Sunday report commit is gated until D27's lean-side split lands (or the split is in)",
      _has_split or _gated,
      "split present — remove the gate" if _has_split else "gate closed, split still pending (D-8)")

# === Test coverage of the cycle itself ===========================================================

for name, path in (("full simulated cycle against mocked APIs", "tests/test_pipeline_cycle.py"),
                   ("game_id join pinned end-to-end", "tests/test_fetch_results.py"),
                   ("preflight two-severity split", "tests/test_pipeline_preflight.py"),
                   ("workflow ↔ config agreement", "tests/test_workflow_schedules.py"),
                   ("pinned gate vehicle", "tests/test_frozen_vehicle.py")):
    check(f"regression coverage: {name}", (ROOT / path).exists(), path)

_cycle = (ROOT / "tests" / "test_pipeline_cycle.py").read_text()
check("the simulated cycle covers snapshot → predict → capture → finals → grade → report",
      all(s in _cycle for s in ("SnapshotBuilder", "build_predictions", "record_observation",
                                "build_results", "build_graded", "render_week")))
check("the simulated cycle asserts idempotency (a second run adds nothing)",
      "test_the_whole_cycle_is_idempotent" in _cycle)

# --- Report -------------------------------------------------------------------
print("Phase 5 acceptance checks:")
failed = 0
for ok, name in results:
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
    failed += not ok

print("\nRunning full test suite (make test)...")
suite = subprocess.run([sys.executable, "-m", "pytest", "-q"], cwd=str(ROOT))
failed += suite.returncode != 0
print(f"  [{'PASS' if suite.returncode == 0 else 'FAIL'}] full test suite")

print(f"\n{'ALL PHASE 5 CHECKS PASSED' if failed == 0 else f'{failed} CHECK(S) FAILED'}")
sys.exit(1 if failed else 0)
