#!/usr/bin/env python3
"""Executable acceptance criteria for Phase 1 — Data Layer v2 (SPEC §5).

Phase 1 ships as sequential sub-PRs (1a registry/schema → 1b snapshot/provenance →
1c schedule-intel/closing-lines). This script encodes the acceptance checks that a
given sub-PR can satisfy and marks the rest PENDING, so `make verify-phase-1` is an
honest running scorecard rather than a wall of red. Exits non-zero only on real
FAILs (PENDING items do not fail the build). Run via ``make verify-phase-1``.
"""

from __future__ import annotations

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


# === 1a — team registry, canonical schema, CFBD v2 client ====================
from data.team_registry import (  # noqa: E402
    EXPECTED_COUNTS_2026,
    NEW_FBS_MEMBERS_2026,
    TeamRegistry,
)

reg = TeamRegistry()

# Registry validates 2026 membership counts (SPEC §5.5.2 hard check).
try:
    reg.validate_membership_counts()
    check("registry validates 2026 membership counts", True,
          str({c: EXPECTED_COUNTS_2026[c] for c in EXPECTED_COUNTS_2026}))
except Exception as exc:  # noqa: BLE001
    check("registry validates 2026 membership counts", False, str(exc))

# Name-coverage: every legacy canonical FBS name is preserved by the registry, and
# the only additions are the enumerated new FBS members (no silent shoehorning).
import json  # noqa: E402

legacy = json.loads((ROOT / "tests" / "fixtures" / "legacy_normalizer_vocab.json").read_text())
from data.team_registry import canonical_name  # noqa: E402

produced = {canonical_name(r["school"]) for r in reg._fbs}
missing = set(legacy["canonical_fbs"]) - produced
additions = produced - set(legacy["canonical_fbs"])
check("name-coverage: all legacy FBS canonical names preserved", not missing,
      f"missing {sorted(missing)}" if missing else f"{len(produced)} FBS teams")
check("registry additions == enumerated new FBS members",
      additions == set(NEW_FBS_MEMBERS_2026),
      f"{sorted(additions)}")

# The interim hardcoded module and the schedule-client residual are gone.
check("data/conferences.py deleted (folded into registry)",
      not (ROOT / "data" / "conferences.py").exists())
check("schedule_client._get_hardcoded_conference removed",
      "_get_hardcoded_conference" not in (ROOT / "data" / "schedule_client.py").read_text())

# No hardcoded conference names remain outside the sanctioned registry — anywhere
# in application code (SPEC §5.5 acceptance: "no hardcoded team/conference lists").
# `BIG TEN` / `PAC-12` string literals are the tell-tale (they appear only as
# hardcoded conference names, whether in a dict key, set, or list), so the probe
# is not colon-anchored. The season registry (data/team_registry.py) is the one
# allowed home for the documented scope/validation constants and is excluded.
probes = ("'BIG TEN'", '"BIG TEN"', "'PAC-12'", '"PAC-12"')
scan_roots = ["data", "utils", "engine", "factors", "cli"]
scan_files = [p for root in scan_roots for p in (ROOT / root).rglob("*.py")]
scan_files.append(ROOT / "main.py")
scan_files = [p for p in scan_files if p.name != "team_registry.py"]
offenders = [p.relative_to(ROOT).as_posix() for p in scan_files
             if any(tok in p.read_text() for tok in probes)]
check("no hardcoded conference lists in application code (data/utils/engine/factors/cli/main)",
      not offenders, ", ".join(offenders) or "none")

# Registry artifact carries provenance (source/fetched_at), and D1 calendar
# corroboration runs and surfaces the known hand-vs-CFBD offset as warnings.
prov = reg.provenance
check("registry artifact has provenance", prov.get("source") == "cfbd"
      and bool(prov.get("fetched_at")), str({k: prov.get(k) for k in ("source", "year")}))
# D8: the calendar is regenerated from CFBD, so corroboration must now be silent (0 warnings).
_cal_warnings = reg.corroborate_calendar()
check("calendar corroboration returns 0 warnings (D8 — regenerated from CFBD)",
      len(_cal_warnings) == 0, f"{len(_cal_warnings)} warning(s)")

# === 1b — snapshot-first data layer + engine cutover =========================
# safe_api_call + all neutral/default fabrication removed from application code.
# `random.uniform`/`random.seed` are the tell-tale of a simulated (fabricated) signal
# — this rule-based, frozen-weight model must never invent data (SPEC §5.1/§5.2).
fab_probes = ("safe_api_call", "_get_neutral_", "_get_default_", "neutral_fallback",
              "random.uniform", "random.seed", "_get_public_betting_percentage")
fab_offenders = []
for p in scan_files:  # same application-code scan set as the conference grep
    text = p.read_text()
    for tok in fab_probes:
        # ignore prose in comments/docstrings that merely name the retired symbol
        hits = [ln for ln in text.splitlines()
                if tok in ln and not ln.lstrip().startswith("#")
                and "no neutral" not in ln.lower() and "never fabricat" not in ln.lower()
                and "not fabricated" not in ln.lower() and "removed" not in ln.lower()]
        if hits:
            fab_offenders.append(f"{p.relative_to(ROOT).as_posix()}:{tok}")
check("safe_api_call + neutral/default fabrication removed from application code",
      not fab_offenders, ", ".join(fab_offenders) or "none")

# `build_snapshot` produces a provenance manifest that accounts for 100% of fields.
snap_manifest = ROOT / "data" / "snapshots" / "2026_week_01" / "manifest.json"
if snap_manifest.exists():
    m = json.loads(snap_manifest.read_text())
    s = m["summary"]
    accounted = s["fields_present"] + s["fields_missing"] == s["fields_total"]
    every_group = all(set(cov) >= {"info", "coaching", "stats", "schedule", "advanced_stats"}
                      for cov in m["coverage"]["teams"].values())
    check("snapshot provenance manifest covers 100% of fields (source/timestamp/missing)",
          accounted and every_group and s["fields_total"] > 0,
          f"{s['fields_present']}/{s['fields_total']} present, "
          f"{s['fields_missing']} missing (all accounted)")
else:
    check("snapshot provenance manifest covers 100% of fields", False,
          "no data/snapshots/2026_week_01 — run `python scripts/build_snapshot.py --week 1`")

# No-network + bit-identical rerun are enforced by the offline suite (run below).
for name in ("test_full_prediction_runs_with_all_networking_disabled",
             "test_two_reruns_are_bit_identical"):
    present = name in (ROOT / "tests" / "test_no_network.py").read_text()
    check(f"acceptance test present: {name}", present)

# === 1c — schedule intelligence + closing lines + inspection tooling =========
# Schedule-intelligence fixture unit tests (SPEC §5 acceptance: travel/rest/timezone).
si_tests = (ROOT / "tests" / "test_schedule_intel.py").read_text()
for name in ("test_haversine_known_city_pair", "test_road_game_travel_and_westward_tz",
             "test_short_week_flag", "test_utc_offset_dst_aware", "test_bye_detection"):
    check(f"schedule-intel fixture test present: {name}", name in si_tests)
check("data/schedule_intel.py provides compute_schedule_intel",
      "def compute_schedule_intel" in (ROOT / "data" / "schedule_intel.py").read_text())

# Closing-line 'as-of T' capture: append-only store + snapshot immutability.
check("append-only line store exists (data/snapshot/lines.py)",
      (ROOT / "data" / "snapshot" / "lines.py").exists())
check("closing-line append leaves snapshot_id unchanged (immutability test present)",
      "test_append_does_not_change_snapshot_id_or_bytes" in
      (ROOT / "tests" / "test_lines.py").read_text())
check("D8 calendar: season_calendar has no Week 0",
      "0" not in json.loads((ROOT / "data" / "season_calendar_2026.json").read_text())["weeks"])

# v1 CFBD client shim retired; consumers on v2.
v1_gone = not (ROOT / "data" / "cfbd_client.py").exists()
v1_refs = [p.relative_to(ROOT).as_posix() for p in
           [*(ROOT / "data").rglob("*.py"), *(ROOT / "utils").rglob("*.py")]
           if "data.cfbd_client" in p.read_text() or "CFBDataClient" in p.read_text()]
check("v1 data/cfbd_client.py deleted; no v1 references remain",
      v1_gone and not v1_refs, ", ".join(v1_refs) or "clean")

# --- Report -------------------------------------------------------------------
print("Phase 1 acceptance checks:")
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

_pending_note = f" ({len(pending)} pending)" if pending else " — Phase 1 data layer complete"
print(f"\n{'ALL PHASE 1 CHECKS PASSED' if failed == 0 else f'{failed} CHECK(S) FAILED'}"
      f"{_pending_note}")
sys.exit(1 if failed else 0)
