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
check("D1 calendar corroboration runs (loud warning, not silent)",
      len(reg.corroborate_calendar()) > 0)

# === 1b / 1c — recorded now, satisfied by later sub-PRs ======================
todo("1b: `cfb data snapshot --week N` writes a 100%-covered provenance manifest")
todo("1b: no-network test — full prediction with networking disabled passes")
todo("1b: two `cfb predict rerun` are bit-identical (minus VOLATILE_FIELDS)")
todo("1b: safe_api_call + all neutral/default fabrication removed")
todo("1c: schedule-intelligence unit tests (travel/rest/timezone) with fixtures")
todo("1c: closing-line 'as-of T' capture + Odds budget guard")

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

print(f"\n{'ALL 1a CHECKS PASSED' if failed == 0 else f'{failed} CHECK(S) FAILED'}"
      f" ({len(pending)} pending for 1b/1c)")
sys.exit(1 if failed else 0)
