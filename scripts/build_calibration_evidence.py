#!/usr/bin/env python3
"""Build the 2025 calibration evidence pack (Phase 3, SPEC §7/§3) — freeze-exempt.

Reads `data/archive/2025/` and writes `data/calibration/2025_evidence.json` (+ prints a
readable table): confidence/edge/type → realized ATS% with Wilson 95% intervals. This is the
evidence every Phase-3 CALIBRATION_LOG proposal cites. Deterministic (static archive input);
**descriptive only — never a fit** (SPEC §3/§12).

Usage: python scripts/build_calibration_evidence.py   (offline)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analytics.calibration_evidence import build_calibration_evidence, format_table  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
ARCHIVE_DIR = ROOT / "data" / "archive" / "2025"
OUT = ROOT / "data" / "calibration" / "2025_evidence.json"


def main() -> int:
    if not ARCHIVE_DIR.exists():
        print(f"No 2025 archive at {ARCHIVE_DIR}.")
        return 1
    evidence = build_calibration_evidence(str(ARCHIVE_DIR))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n")
    print(format_table(evidence))
    rel = OUT.relative_to(Path.cwd()) if OUT.is_relative_to(Path.cwd()) else OUT
    print(f"\nWrote {rel}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
