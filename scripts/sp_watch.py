#!/usr/bin/env python3
"""Watch for CFBD publishing 2026 SP+ / returning production — the external-data-event probe.

**Why a separate probe.** `verify-phase-3`'s behavioural fingerprint reads a *committed* snapshot
(the pinned vehicle, D29), so it is a deterministic function of the commit: re-running it on a
timer detects nothing about the outside world. Yet the outside world holds an event that changes
the model's inputs — CFBD has not published 2026 preseason SP+ or returning production (verified
0 rows on 2026-08-03, while the 2025 equivalents return 137/134). D10 makes both auto-activate the
moment they appear, with **no code change**.

**What happens when they land**, and why this is worth 30 lines and 2 CFBD calls:
  * `Sandwich` wakes up (currently 0/330 activations, for want of SP+ ranks).
  * The returning-production prior starts moving preseason ratings off the flat baseline.
  * Model output therefore moves, and the next snapshot rebuild makes the fingerprint gate fail —
    **correctly**. That is the gate doing its job, not a defect.
  * The correct response is the SPEC §3 exception process — a dated exception entry and a NEW tag.
    **Never a constant update.**

That last step needs owner turnaround against a fixed 2026-08-29 kickoff, which is the whole point
of learning about it on the day rather than discovering it mid-rehearsal.

This **opens an Issue; it does not fail a check.** The correct response is a decision process, not
a revert, and a red required check would only pressure someone into making the change quietly.

Usage: python scripts/sp_watch.py [--year 2026] [--json]
Exit codes: 0 unchanged (still dormant), 1 fetch failed, **2 the data has ARRIVED**.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

EXIT_UNCHANGED, EXIT_ERROR, EXIT_ARRIVED = 0, 1, 2

# The state at the freeze, verified live 2026-08-03 and unchanged at the tag. These are a
# BASELINE, not a target: when either goes non-zero the model's inputs have changed and the
# response is a SPEC §3 exception plus a new tag. Updating these numbers is part of ratifying
# that transition — it is deliberately a code change, not a config tweak.
BASELINE = {"sp_ratings": 0, "returning_production": 0}


def counts(year: int) -> dict[str, int]:
    from data.clients.cfbd_v2 import get_cfbd_v2_client
    client = get_cfbd_v2_client()
    return {
        "sp_ratings": len(client.get_sp_ratings(year) or []),
        "returning_production": len(client.get_returning_production(year) or []),
    }


def arrivals(observed: dict[str, int], baseline: dict[str, int] | None = None) -> list[str]:
    """Sources that have gone from dormant to populated. Pure."""
    base = baseline if baseline is not None else BASELINE
    return sorted(k for k, n in observed.items() if n > base.get(k, 0))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Probe for 2026 SP+ / returning production.")
    parser.add_argument("--year", type=int, default=2026)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    try:
        observed = counts(args.year)
    except Exception as exc:
        print(f"CFBD probe failed: {type(exc).__name__}: {exc}")
        return EXIT_ERROR

    landed = arrivals(observed)
    if args.json:
        print(json.dumps({"observed": observed, "baseline": BASELINE, "arrived": landed},
                         indent=2, sort_keys=True))

    if not landed:
        body = (f"SP+ watch ({args.year}): still dormant — "
                + ", ".join(f"{k} {v} rows" for k, v in sorted(observed.items())))
    else:
        body = "\n".join([
            f"### ⚠ CFBD has published {args.year} " + " and ".join(landed),
            "",
            *(f"- `{k}`: {observed[k]} rows (baseline {BASELINE.get(k, 0)})" for k in landed),
            "",
            "**Consequences, in order:**",
            "1. `Sandwich` wakes up and the returning-production prior starts moving preseason "
            "ratings — D10 activates both with no code change.",
            "2. Model output therefore moves. The next snapshot rebuild will fail "
            "`verify-phase-3`'s behavioural fingerprint **correctly**.",
            "3. That needs a **SPEC §3 exception entry and a NEW tag** — never a constant update.",
            "4. Re-measure the slate and record the delta BEFORE the graded dress rehearsal "
            "(HANDOFF §(e)): a frozen model with a newly-populated input is not the model that "
            "was characterised at the tag.",
        ])

    if not args.json:
        print(body)
    if (summary := os.environ.get("GITHUB_STEP_SUMMARY")):
        with open(summary, "a") as fh:
            fh.write(body + "\n")

    return EXIT_ARRIVED if landed else EXIT_UNCHANGED


if __name__ == "__main__":
    raise SystemExit(main())
