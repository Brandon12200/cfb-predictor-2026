#!/usr/bin/env python3
"""Executable acceptance criteria for Phase 2 — Power Rating Layer & Hypothetical
Matchup Mode (SPEC §6).

Phase 2 ships as two sub-PRs: 2a (freeze-disciplined — ratings, pricer, hypothetical,
model-vs-market logging) and 2b (freeze-exempt cut-first — season projections +
`cfb project`). This script encodes the checks a given sub-PR satisfies and marks the
rest PENDING, so `make verify-phase-2` is an honest running scorecard. Exits non-zero
only on real FAILs. Offline. Run via ``make verify-phase-2``.
"""

from __future__ import annotations

import contextlib
import io
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


# === 2a — in-house Elo power ratings (owner §16.4; D9) =======================
from engine.power_ratings import DEFAULT_CONFIG, EloConfig  # noqa: E402

cfg = DEFAULT_CONFIG
d9_knobs = ("k_early", "k_late", "k_decay_games", "mov_c", "mov_b", "hfa_elo",
            "elo_per_point", "margin_sigma", "rating_signal_floor")
check("in-house Elo rating layer present (EloConfig with D9 constants; not blended public)",
      isinstance(cfg, EloConfig) and all(hasattr(cfg, k) for k in d9_knobs),
      f"K={cfg.k_early}->{cfg.k_late}, HFA={cfg.hfa_elo}elo, {cfg.elo_per_point}elo/pt, σ={cfg.margin_sigma}")

# The dispersion acceptance test that GATES the D9 constants must pass (crux check).
try:
    from tests.test_power_ratings import (
        test_dispersion_recovers_realistic_point_spread as _disp,
    )
    _disp()
    check("dispersion acceptance test passes (recovers ~30pt top-vs-bottom; gates D9)", True)
except Exception as exc:  # noqa: BLE001
    check("dispersion acceptance test passes (recovers ~30pt top-vs-bottom; gates D9)",
          False, str(exc))

# Rating-update logic has SYNTHETIC-SEASON tests + a determinism guarantee.
tp = (ROOT / "tests" / "test_power_ratings.py").read_text()
check("rating-update logic has synthetic-season tests (SPEC §6 acceptance)",
      "def synthetic_season" in tp and "test_compute_ratings_is_order_independent" in tp)
tm = (ROOT / "tests" / "test_matchup_pricer.py").read_text()
check("matchup pricer has a determinism (bit-identical) test",
      "test_pricer_is_deterministic" in tm)

# Preseason prior is the hybrid (D10): SP+ preferred, returning-production fallback.
check("hybrid preseason prior (SP+ preferred, returning-production fallback, flat otherwise)",
      "def preseason_prior" in (ROOT / "engine" / "power_ratings.py").read_text()
      and all(s in tp for s in ('"sp+"', '"returning_production"', '"flat"')))

# returning_production is a snapshot field-group at 100% manifest coverage (D10 plumbing).
snap_manifest = ROOT / "data" / "snapshots" / "2026_week_01" / "manifest.json"
if snap_manifest.exists():
    man = json.loads(snap_manifest.read_text())
    has_rp = all("returning_production" in cov for cov in man["coverage"]["teams"].values())
    check("returning_production field-group present in snapshot (hybrid prior, D10)", has_rp)
else:
    check("returning_production field-group present in snapshot (hybrid prior, D10)",
          False, "no data/snapshots/2026_week_01 — run build_snapshot.py --week 1")

# === Hypothetical mode: works for ANY two FBS teams (SPEC §6.4 acceptance) ====
from cli.app import run_hypothetical  # noqa: E402


def _hypothetical(home: str, away: str) -> dict:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = run_hypothetical(["--home", home, "--away", away, "--format", "json", "--quiet"])
    payload = json.loads(buf.getvalue())
    payload["_rc"] = rc
    return payload


hypo_ok, hypo_detail = True, ""
try:
    for home, away in [("Ohio State", "Texas"), ("Sacramento State", "Wyoming")]:
        d = _hypothetical(home, away)
        hypo_ok = hypo_ok and d["_rc"] == 0 and isinstance(d.get("model_spread"), (int, float))
except Exception as exc:  # noqa: BLE001
    hypo_ok, hypo_detail = False, str(exc)
check("hypothetical command works for any two FBS teams (no Vegas line needed)",
      hypo_ok, hypo_detail or "priced 2 arbitrary FBS pairs incl. a new member")

# === Real games log BOTH model spread and Vegas spread (SPEC §6.6) ===========
mvm_ok, mvm_detail = False, "no snapshot"
if snap_manifest.exists():
    try:
        from engine.prediction_engine import prediction_engine
        r = prediction_engine.generate_prediction("Notre Dame", "Wisconsin", week=1)
        mvm_ok = (r.get("vegas_spread") is not None
                  and r.get("power_rating_spread") is not None
                  and "model_vs_market_gap" in r
                  and "rating_uncertainty" in r)
        mvm_detail = (f"vegas={r.get('vegas_spread')} model={r.get('power_rating_spread')} "
                      f"gap={r.get('model_vs_market_gap')} u={r.get('rating_uncertainty')}")
    except Exception as exc:  # noqa: BLE001
        mvm_detail = str(exc)
check("real games log both model spread and Vegas spread + model-vs-market gap (§6.6)",
      mvm_ok, mvm_detail)

# === Derived ratings export + reproducibility (D13) ==========================
# Ratings are checked for EVERY built week. Note this is now STRICTER than the projections check
# below, which reproduces only the latest week and does existence-only for the rest — not a defect,
# but do not read "matching" into it. Ratings used to look
# only at week 1 — an asymmetry that went operationally live when the Tuesday job began
# regenerating ratings weekly: a later week's export could have gone stale or missing with nothing
# noticing, while the identical obligation for projections was enforced.
from data.snapshot.store import available_weeks as _weeks  # noqa: E402

_built = _weeks(2026)
_ratings_dir = ROOT / "data" / "ratings"
_ratings_files = {w for w in _built if (_ratings_dir / f"2026_week_{w:02d}.json").exists()}
if _built and _ratings_files == set(_built) and snap_manifest.exists():
    from data.snapshot.store import load_snapshot
    from engine.matchup_pricer import build_ratings_export
    _bad = []
    for _w in _built:
        _f = json.loads((_ratings_dir / f"2026_week_{_w:02d}.json").read_text())
        _snap = load_snapshot(_w, 2026)
        if build_ratings_export(_snap) != _f or _f["meta"]["snapshot_id"] != _snap["meta"]["snapshot_id"]:
            _bad.append(_w)
    check("data/ratings export exists for every built week + reproduces from its snapshot (D13)",
          not _bad,
          f"weeks {sorted(_built)}; " + (f"stale: {_bad}" if _bad else "all reproduce"))
else:
    check("data/ratings export exists and is reproducible from the snapshot (D13)",
          False, "run `python scripts/update_ratings.py --week 1`")

# spread → win-probability conversion documented in SCHEMA.md (D12, §6.5).
schema = (ROOT / "docs" / "SCHEMA.md").read_text().lower()
check("spread→win-probability conversion documented in SCHEMA.md (D12, §6.5)",
      "win-prob" in schema and "margin_sigma" in schema)

# Immutable-history hook extended to data/ratings/ (D13).
check("immutable-history hook protects data/ratings/ (D13)",
      "data/ratings/" in (ROOT / ".claude" / "hooks" / "protect_immutable.py").read_text())

# === 2b — season projections + belief-drift (freeze-exempt, cut-first §15) ====
# A projection file exists for each built snapshot week, is well-formed (experimental flag +
# schema_version + FBS teams with projected_wins), and reproduces from the snapshot.
from data.snapshot.store import available_weeks  # noqa: E402

projections_dir = ROOT / "data" / "projections"
built = available_weeks(2026)
proj_files = {w for w in built
              if (projections_dir / f"2026_week_{w:02d}.json").exists()}
proj_ok = bool(built) and proj_files == set(built)
proj_detail = f"weeks with projections: {sorted(proj_files)} of built {built}"
if proj_ok:
    from analytics.projections import build_projections
    from data.snapshot.store import load_snapshot
    w0 = built[-1]
    on_disk = json.loads((projections_dir / f"2026_week_{w0:02d}.json").read_text())
    rebuilt = build_projections(load_snapshot(w0, 2026))
    cov = on_disk["meta"].get("coverage", {})
    proj_ok = (on_disk == rebuilt and on_disk["meta"]["experimental"] is True
               and "schema_version" in on_disk["meta"] and bool(on_disk["teams"])
               and all("projected_wins" in r for r in on_disk["teams"].values())
               # coverage is explicit (every FBS team present, unscheduled ones surfaced)
               and len(on_disk["teams"]) == cov.get("fbs_total"))
    proj_detail = (f"{cov.get('scheduled')}/{cov.get('fbs_total')} FBS teams scheduled "
                   f"(unscheduled surfaced: {cov.get('unscheduled')}); reproducible; "
                   f"weeks {sorted(proj_files)}")
check("weekly projection files exist for every built week + reproduce (§6.5, 2b)",
      proj_ok, proj_detail)

# `cfb project` (main.py project) renders projected win totals (+ drift when ≥2 weeks).
proj_cli_ok, proj_cli_detail = False, ""
try:
    from cli.app import run_project
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = run_project(["--format", "json", "--quiet"])
    payload = json.loads(buf.getvalue())
    proj_cli_ok = (rc == 0 and payload.get("experimental") is True
                   and isinstance(payload.get("teams"), list) and bool(payload["teams"])
                   and all("delta_week" in t and "projected_wins" in t for t in payload["teams"]))
    proj_cli_detail = (f"rendered {len(payload['teams'])} teams, "
                       f"drift={'on' if payload.get('has_drift') else 'awaiting week 2'}")
except Exception as exc:  # noqa: BLE001
    proj_cli_detail = str(exc)
check("cfb project renders projected win totals + week-over-week drift (2b)",
      proj_cli_ok, proj_cli_detail)

# --- Report -------------------------------------------------------------------
print("Phase 2 acceptance checks:")
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

_pending_note = f" ({len(pending)} pending — 2b)" if pending else " — Phase 2 complete"
print(f"\n{'ALL PHASE 2 CHECKS PASSED' if failed == 0 else f'{failed} CHECK(S) FAILED'}"
      f"{_pending_note}")
sys.exit(1 if failed else 0)
