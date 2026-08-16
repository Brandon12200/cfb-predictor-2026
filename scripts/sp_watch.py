#!/usr/bin/env python3
"""Watch for CFBD publishing 2026 SP+ / returning production — the external-data-event probe.

**Why a separate probe.** `verify-phase-3`'s behavioural fingerprint reads a *committed* snapshot
(the pinned vehicle, D29), so it is a deterministic function of the commit: re-running it on a
timer detects nothing about the outside world. Yet the outside world holds events that change the
model's inputs, and D10 makes them auto-activate the moment they appear, with **no code change**.

**Status.** Both watched transitions have now landed and been ratified: returning production on
2026-08-08 (0 → 136 rows, exception 1, tag `v2026-frozen-2`) and preseason SP+ on 2026-08-14
(0 → 139 rows, exception 2, tag `v2026-frozen-3`). **No transition is outstanding.** The probe now
watches for *revisions* to either ratified source.

**The comparison is a strict deviation, not growth.** `arrivals()` reports any source whose row
count differs from its ratified baseline in **either direction**. Growth is a new activation;
a *shrink* is a provider withdrawing rows, which changes the model's inputs just as surely — the
affected teams fall back to D10's flat-prior path, a documented state, but the model is then no
longer the one characterised at the tag. Nothing else observes either direction: the fingerprint
gate reads the pinned static vehicle (D29) and never re-queries CFBD, by design, which makes this
probe the **only live observer of CFBD state in the codebase**. This closes the gap recorded in
`docs/2027_NOTES.md` §8 item 8. Accepted tradeoff, stated plainly: CFBD row counts are revised
routinely, so this will fire on ordinary revisions, and alarm volume is a cost paid deliberately.

**What happens when a source moves**, and why this is worth 30 lines and 2 CFBD calls:
  * A newly-populated source auto-activates under D10 with **no code change** — SP+ ranks waking
    `Sandwich` was exactly this.
  * Model output therefore moves, while **no gate can see it**. The fingerprint reads a committed
    vehicle, so an external input change is invisible to it by construction (measured under
    exception 2: `verify-phase-3` passed in full with SP+ already live). This probe is the detector.
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

# The RATIFIED state — what the current freeze tag was measured against. An observation that
# DIFFERS from a baseline in either direction means the model's inputs have moved since that tag,
# and the response is a SPEC §3 exception plus a new tag.
#
# **Updating these numbers is part of ratifying a transition, not an afterthought.** Leaving a
# ratified arrival at 0 makes this probe re-report it on every run forever, and — worse — the next,
# genuinely new arrival dedupes onto that stale issue instead of opening a fresh one. That is
# exactly what would have happened to the SP+ transition: with `returning_production` left at 0,
# SP+ landing would have returned BOTH sources under a title naming both, rather than a clean
# "SP+ has arrived". Recorded in SPEC §3.1 as a step of the exception process.
#
# Current state (SPEC §3 exception 2, tag `v2026-frozen-3`): both sources are published and
# ratified — returning production at 136 rows (exception 1) and SP+ at 139 rows (exception 2).
# **No transition is outstanding; the probe now watches for revisions in either direction.**
#
# `sp_ratings: 139` counts RAW API rows, which is what `counts()` measures. The snapshot carries
# 138 teams: the 139th row is CFBD's `nationalAverages` aggregate, which the normalizer correctly
# drops. Recorded so the difference is not later "fixed" as an off-by-one (SPEC §3.1 exception 2).
BASELINE = {"sp_ratings": 139, "returning_production": 136}


def counts(year: int) -> dict[str, int]:
    from data.clients.cfbd_v2 import get_cfbd_v2_client
    client = get_cfbd_v2_client()
    return {
        "sp_ratings": len(client.get_sp_ratings(year) or []),
        "returning_production": len(client.get_returning_production(year) or []),
    }


def arrivals(observed: dict[str, int], baseline: dict[str, int] | None = None) -> list[str]:
    """Sources whose row count DEVIATES from its ratified baseline, in either direction. Pure.

    Strict inequality, not `>`. A source growing is a new activation; a source shrinking is a
    provider withdrawal that moves model output just as surely, and no other check in the codebase
    observes either (the fingerprint gate reads a pinned committed vehicle, D29). Both are the
    same event class — "the inputs are no longer what the tag was measured against" — and both
    need the same response, a SPEC §3 exception and a new tag.
    """
    base = baseline if baseline is not None else BASELINE
    return sorted(k for k, n in observed.items() if n != base.get(k, 0))


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
        # Name the state per source against its ratified baseline: "dormant" is wrong for a source
        # that has published and been ratified — it is at its expected level, not asleep.
        parts = []
        for k, v in sorted(observed.items()):
            base = BASELINE.get(k, 0)
            state = "awaited" if base == 0 and v == 0 else "at ratified level"
            parts.append(f"{k} {v} rows ({state}, baseline {base})")
        body = f"SP+ watch ({args.year}): no new arrival — " + ", ".join(parts)
    else:
        grew = [k for k in landed if observed[k] > BASELINE.get(k, 0)]
        verb = "revised" if not grew else ("published" if all(
            BASELINE.get(k, 0) == 0 for k in grew) else "changed")
        body = "\n".join([
            f"### ⚠ CFBD has {verb} {args.year} " + " and ".join(landed),
            "",
            *(f"- `{k}`: {observed[k]} rows "
              f"({observed[k] - BASELINE.get(k, 0):+d} vs ratified baseline "
              f"{BASELINE.get(k, 0)})" for k in landed),
            "",
            "**Consequences, in order:**",
            "1. The source auto-activates or re-weights under **D10, with no code change** — so "
            "model output moves on the next snapshot rebuild.",
            "2. **No gate will catch this, and none can.** `verify-phase-3` reads a *committed* "
            "pinned vehicle (D29), so an external input change is invisible to it by "
            "construction — measured under SPEC §3.1 exception 2, where it passed in full with "
            "SP+ already live. **This probe is the only detector.** Do not wait for a red check.",
            "3. That needs a **SPEC §3 exception entry and a NEW tag** — never a constant update. "
            "The tag must be cut BEFORE any affected claim is written; claims are byte-immutable.",
            "4. Re-measure the slate and record the delta BEFORE the next rehearsal "
            "(HANDOFF §(e)): a frozen model with a changed input is not the model that was "
            "characterised at the tag. Use `python scripts/measure_transition.py` — its "
            "three-vehicle method isolates this source from ambient data drift.",
            "5. **Ambient drift alone also moves the fingerprint**, so no live bundle will "
            "reproduce a previously recorded hash. A live re-run is not a confirmation and its "
            "difference is not a fault.",
        ])

    if not args.json:
        print(body)
    if (summary := os.environ.get("GITHUB_STEP_SUMMARY")):
        with open(summary, "a") as fh:
            fh.write(body + "\n")

    return EXIT_ARRIVED if landed else EXIT_UNCHANGED


if __name__ == "__main__":
    raise SystemExit(main())
