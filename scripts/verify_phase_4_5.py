#!/usr/bin/env python3
"""Executable acceptance criteria for Phase 4.5 — CLI v2 (SPEC §9).

The `cfb` subcommand set is a thin human interface over the existing `analytics/`/`scripts/` seams.
Acceptance (SPEC §9): omitted-week == explicit-week (bit-identical — the silent-week-1 fix); `--offline`
rerun identical to the original run; the whole weekly routine in ≤2 commands; `cfb --help` renders the
contract; every command supports `--format json` with meaningful exit codes. `cfb predict game` uses
the ratified slate, never the parked A2 engine.

Offline. Run via ``make verify-phase-4-5``. Exits non-zero only on real FAILs.
"""

from __future__ import annotations

import contextlib
import io
import json
import subprocess
import sys
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import cli.cfb as cfb  # noqa: E402
import data.snapshot.store as _store  # noqa: E402
from data.snapshot.store import load_frozen_vehicle  # noqa: E402
from scripts.slate_fingerprint import engine_reads  # noqa: E402

# === the pinned slate ============================================================================
# These are acceptance gates on the CLI, not on today's calendar. `data/snapshots/2026_week_01/` is
# LIVE — the pipeline rebuilds it on every week-1 run, and books de-list a game once it has been
# played. From the first post-kickoff rebuild (2026-09-01) the live bundle is therefore a DEGRADED
# slate, and every `== 0` below became `== 2`: SPEC §9 requirement 5 ("2 degraded data") working
# exactly as written, failing an acceptance script that had only ever seen a complete slate.
#
# So pin the pre-kickoff vehicle, which lives under the append-only `data/archive/frozen/` and
# cannot rot. BOTH read paths need pinning: `cli.cfb` enumerates the slate through the store, while
# the frozen engine prices each game through `data.data_manager` (`analytics/predictions.py` says
# so). Pinning one gives the split read `engine_reads` exists to prevent — which looks correct.
# The stack is process-lifetime by design; this script is one-shot.
_VEHICLE = load_frozen_vehicle()
_store.load_snapshot = lambda week, year=2026, base=None: _VEHICLE  # noqa: ARG005
_PIN = contextlib.ExitStack()
_PIN.enter_context(engine_reads(_VEHICLE))

results: list[tuple[bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((ok, name + (f" — {detail}" if detail else "")))


def run(argv: list[str]) -> tuple[int, str, str]:
    """Invoke the CLI in-process, capturing (exit_code, stdout, stderr)."""
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = cfb.main(argv)
    return code, out.getvalue(), err.getvalue()


class _Wk1:
    @staticmethod
    def now() -> datetime:
        return datetime(2026, 9, 1)   # a week-1 date


# === config home (season.json) ==================================================================
_season = json.loads((ROOT / "season.json").read_text())
_cal = json.loads((ROOT / "data" / "season_calendar_2026.json").read_text())
check("season.json is the config home; weeks folded from the CFBD-corroborated calendar (D8/D24)",
      _season["weeks"] == _cal["weeks"] and _season["season"] == _cal["season"]
      and "cli_defaults" in _season)

# === the pinned slate is complete ================================================================
# Asserted, not assumed: if a retag ever re-points the vehicle at a post-kickoff snapshot, the
# checks below must fail saying THAT, not fail as an unexplained `exit 2`.
_no_line = sorted(k for k, v in _VEHICLE["data"]["betting_lines"].items()
                  if v.get("vegas_spread") is None)
check("the pinned pre-kickoff vehicle is a COMPLETE slate (every game bettable)",
      not _no_line, f"no line for {_no_line}" if _no_line else "")

# === §9.1 week inference: omitted == explicit (bit-identical) ====================================
_orig_dt = cfb.datetime
cfb.datetime = _Wk1  # type: ignore[assignment]
try:
    _ci, _inferred, _echo = run(["predict", "week", "--format", "json"])
    _ce, _explicit, _ = run(["predict", "week", "1", "--format", "json"])
finally:
    cfb.datetime = _orig_dt  # type: ignore[assignment]
check("omitted-week == explicit-week, bit-identical (the silent-week-1 fix)",
      _ci == 0 and _ce == 0 and _inferred == _explicit and json.loads(_inferred)["meta"]["week"] == 1)
check("the inferred week is echoed to stderr, not stdout (clean --format json)",
      "inferred from" in _echo and "inferred from" not in _inferred)

# === §9.3 --offline rerun identical to the original run =========================================
_c1, _run1, _ = run(["predict", "week", "1", "--format", "json"])
_c2, _run2, _ = run(["predict", "rerun", "--week", "1", "--format", "json"])
check("`predict rerun` (offline) is byte-identical to the original `predict week`",
      _c1 == 0 and _c2 == 0 and _run1 == _run2)

# === predict game: ratified slate, never A2 =====================================================
check("cfb never references the A2 single-game engine (run_single_prediction)",
      "run_single_prediction" not in (ROOT / "cli" / "cfb.py").read_text())
_cg, _game, _ = run(["predict", "game", "CLEMSON @ LSU", "--week", "1", "--format", "json"])
_rec = json.loads(_game)["predictions"] if _cg == 0 else []
check("cfb predict game prices from the ratified schema-v2 slate (confidence 0–1, one matchup)",
      _cg == 0 and len(_rec) == 1 and 0.0 <= _rec[0]["confidence"] <= 1.0)
_cn, _, _nerr = run(["predict", "game", "OHIO STATE @ TEXAS", "--week", "1"])
check("a non-slate matchup errors (exit 1) suggesting cfb hypothetical",
      _cn == 1 and "cfb hypothetical" in _nerr)

# === §9.5 help contract + exit codes ============================================================
try:
    run(["--help"])
    _help_code, _help_out = 0, ""
except SystemExit as exc:
    _hbuf = io.StringIO()
    with redirect_stdout(_hbuf):
        try:
            cfb.main(["--help"])
        except SystemExit:
            pass
    _help_code, _help_out = int(exc.code or 0), _hbuf.getvalue()
check("cfb --help renders the full command contract (all subcommands)",
      _help_code == 0 and all(c in _help_out for c in
                              ("predict", "grade", "report", "project", "hypothetical",
                               "slate", "data", "status")))

cfb.datetime = type("D", (), {"now": staticmethod(lambda: datetime(2026, 7, 24))})  # type: ignore[assignment]
try:
    _co, _, _ = run(["predict", "week"])
finally:
    cfb.datetime = _orig_dt  # type: ignore[assignment]
check("out-of-season inference exits 2 (degraded), never a silent guess", _co == 2)

# === weekly routine in ≤2 commands (snapshot → predict week) + console script ===================
_pyproject = (ROOT / "pyproject.toml").read_text()
check("`cfb` console script registered (weekly routine: `cfb data snapshot` → `cfb predict week`)",
      'cfb = "cli.cfb:main"' in _pyproject
      and cfb.build_parser().prog == "cfb")

# === main.py deprecation shim (delegates; orphans run_single_prediction) =========================
_main_src = (ROOT / "main.py").read_text()
check("main.py is a deprecation shim delegating to cfb (no A2 call site here)",
      "cli.cfb" in _main_src and "= run_single_prediction(" not in _main_src)

# === D24 recorded ================================================================================
check("D24 recorded (CLI v2 dispositions: season.json, predict-game routing, shim, A2 orphaned)",
      "## D24 " in (ROOT / "docs" / "DECISIONS.md").read_text())

# --- Report -------------------------------------------------------------------
print("Phase 4.5 acceptance checks:")
failed = 0
for ok, name in results:
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
    failed += not ok

print("\nRunning full test suite (make test)...")
suite = subprocess.run([sys.executable, "-m", "pytest", "-q"], cwd=str(ROOT))
failed += suite.returncode != 0
print(f"  [{'PASS' if suite.returncode == 0 else 'FAIL'}] full test suite")

print(f"\n{'ALL PHASE 4.5 CHECKS PASSED' if failed == 0 else f'{failed} CHECK(S) FAILED'}")
sys.exit(1 if failed else 0)
