#!/usr/bin/env python3
"""Executable acceptance criteria for Phase 0 (SPEC §4).

Encodes the repo-hygiene/audit acceptance as pass/fail checks and then runs the
full test suite. Exits non-zero if any check fails; prints evidence for the PR.
Run via ``make verify-phase-0``.
"""

from __future__ import annotations

import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
results: list[tuple[bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((ok, name + (f" — {detail}" if detail else "")))


def _git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True)


# 1. Stray venv binary is gone and untracked.
check("venv file removed from disk", not (ROOT / "venv").exists())
check("venv not tracked in git", _git("ls-files", "venv").stdout.strip() == "")

# 2. .gitignore no longer hides docs/reports/AI tooling.
ci = _git("check-ignore", "-v", "docs/SPEC.md", "docs/DECISIONS.md",
          "CLAUDE.md", "reports/x.md")
check("docs/CLAUDE.md/reports not gitignored", ci.returncode == 1, ci.stdout.strip())

# 3. IMPLEMENTATION.md folded into SPEC; §14 guide + §16 owner decisions present.
spec = (ROOT / "docs" / "SPEC.md").read_text()
check("docs/IMPLEMENTATION.md deleted", not (ROOT / "docs" / "IMPLEMENTATION.md").exists())
check("SPEC §14 Agentic Implementation Guide present", "## 14. Agentic Implementation Guide" in spec)
check("SPEC §16 Owner Decisions present", "## 16. Owner Decisions" in spec)
check("no stale §15.x owner-decision refs remain", "§15." not in spec)

# 4. Silent week-1 default is gone; week inference hard-fails off-season and
#    an omitted week resolves to the same value an explicit week supplies.
sys.path.insert(0, str(ROOT))
from utils.season_calendar import (  # noqa: E402
    WeekInferenceError,
    infer_week_for_date,
    resolve_week,
)

src_blob = "\n".join(p.read_text() for p in [ROOT / "main.py", *(ROOT / "cli").glob("*.py")])
check("no leftover 'Default to week 1' test code", "Default to week 1" not in src_blob)

offseason_fails = False
try:
    infer_week_for_date(date(2026, 7, 2))
except WeekInferenceError:
    offseason_fails = True
check("off-season date hard-fails week inference", offseason_fails)

in_season = date(2026, 10, 8)
check("omitted week == explicit week for same date",
      resolve_week(None, today=in_season) == resolve_week(6, today=in_season) == 6)

# 5. Conference membership resolves through one module; ACC corrected to 17.
from data.conferences import get_conference_map  # noqa: E402

conf = get_conference_map()
check("ACC has 17 members", len(conf["ACC"]) == 17, f"got {len(conf['ACC'])}")
check("ACC includes Stanford, California, SMU",
      all(t in conf["ACC"] for t in ("STANFORD", "CALIFORNIA", "SMU")))

# No hardcoded conference membership lists survive in the CLI/entry code — a
# 'BIG TEN': [...] dict-key literal must only live in data/conferences.py.
conf_literals = [p.name for p in [ROOT / "main.py", *(ROOT / "cli").glob("*.py")]
                 if "'BIG TEN':" in p.read_text() or '"BIG TEN":' in p.read_text()]
check("no hardcoded conference lists outside data/conferences.py",
      not conf_literals, ", ".join(conf_literals) or "none")

# 6. Required Phase 0 docs exist.
for doc in ("CODE_AUDIT.md", "DECISIONS.md"):
    check(f"docs/{doc} exists", (ROOT / "docs" / doc).exists())

# 7. main.py is a thin entry point delegating to the cli package.
main_src = (ROOT / "main.py").read_text()
check("main.py is thin (delegates to cli)", "from cli.app import main" in main_src
      and len(main_src.splitlines()) < 30)

# 8. Packaging present.
check("pyproject.toml exists", (ROOT / "pyproject.toml").exists())

# --- Report structural checks -------------------------------------------------
print("Phase 0 acceptance checks:")
failed = 0
for ok, name in results:
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
    failed += not ok

# 9. Full test suite must pass.
print("\nRunning full test suite (make test)...")
suite = subprocess.run([sys.executable, "-m", "pytest", "-q"], cwd=str(ROOT))
suite_ok = suite.returncode == 0
print(f"  [{'PASS' if suite_ok else 'FAIL'}] full test suite")
failed += not suite_ok

print(f"\n{'ALL CHECKS PASSED' if failed == 0 else f'{failed} CHECK(S) FAILED'}")
sys.exit(1 if failed else 0)
