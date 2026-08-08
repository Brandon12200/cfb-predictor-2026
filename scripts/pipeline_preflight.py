#!/usr/bin/env python3
"""Pre-run checks for every pipeline job — runs BEFORE any API spend or commit (Phase 5).

**Two severities, deliberately (owner ruling, 2026-08-07).** Confusing them is how a guard becomes
either useless or unusable:

* **ABORT (exit 1) — the freeze and provenance preconditions.** A run that cannot prove it is the
  frozen model, or cannot stamp a claim with the frozen tag, must not spend a credit or write a
  claim. Failing here is cheap; failing after the claim is committed is not, because
  `data/predictions/` is byte-immutable forever (D22) and a mis-stamped claim cannot be corrected.
* **WARN (exit 0, message only) — the timing check.** Aborting a jittered run converts a *degraded*
  capture into *no* capture. `closing_observation` is per-game as-of-T, so a late observation is
  simply not selected as the close for a game that already kicked; the damage from lateness is
  bounded, while the damage from not running at all is a missing close for the whole slate.

The freeze assertion is a **tree-hash equality**, not a file scan: `git rev-parse HEAD:factors`
against `<freeze_tag>:factors`. It is exact, costs milliseconds, and cannot be fooled by a
whitespace-preserving edit. Note it requires the tag to be present — `actions/checkout` with the
default `fetch-depth: 1` fetches no tags, which is also what the `model_version` check catches.

Budget note: this REPORTS the Odds balance and burn rate; it does not gate the spend. The
pre-spend refusal lives in `scripts/fetch_lines.py` (exit 3) where the credit is actually about to
be spent. Two gates on one resource would disagree eventually.

Usage:
  python scripts/pipeline_preflight.py --role predict|capture|grade|freeze --week N
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from data.odds_budget import last_remaining  # noqa: E402
from utils.season_calendar import load_calendar, pipeline_timezone  # noqa: E402
from utils.version import frozen_tree_hashes, model_version  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
FROZEN_TREES = ("factors", "engine")
EXIT_OK, EXIT_ABORT = 0, 1

# Roles that spend an Odds credit, and the season.json floor each is reported against.
_CREDIT_FLOOR = {"predict": "min_credits_snapshot", "capture": "min_credits_capture"}


class Preflight:
    def __init__(self) -> None:
        self.aborts: list[str] = []
        self.warns: list[str] = []
        self.notes: list[str] = []

    def abort(self, msg: str) -> None:
        self.aborts.append(msg)

    def warn(self, msg: str) -> None:
        self.warns.append(msg)

    def note(self, msg: str) -> None:
        self.notes.append(msg)


def check_freeze(pf: Preflight, freeze_tag: str) -> None:
    """ABORT: the frozen trees must be byte-identical to the tag.

    Reads the shared `utils.version.frozen_tree_hashes` primitive rather than shelling git here —
    `cfb status` and the daily freeze-integrity job answer the same question, and a second copy is
    how two guards drift apart (D25.4).
    """
    for tree, (head, tagged) in frozen_tree_hashes(freeze_tag, FROZEN_TREES).items():
        if tagged is None:
            pf.abort(
                f"cannot resolve `{freeze_tag}:{tree}` — the freeze tag is not in this checkout. "
                f"Actions needs `fetch-depth: 0`; without tags the freeze cannot be proven."
            )
            continue
        if head != tagged:
            pf.abort(
                f"{tree}/ has drifted from {freeze_tag} (HEAD {head} != tag {tagged}). "
                f"The model is frozen: this needs a SPEC §3 exception and a new tag, not a run."
            )
        else:
            pf.note(f"{tree}/ matches {freeze_tag} ({(head or '')[:12]})")


def check_model_version(pf: Preflight, freeze_tag: str) -> None:
    """ABORT: every claim is stamped with this, and `data/predictions/` is immutable forever."""
    mv = model_version()
    if mv == "unknown":
        pf.abort("model_version() is 'unknown' (git unavailable) — a claim cannot be stamped.")
    elif not mv.startswith(freeze_tag):
        pf.abort(
            f"model_version() is '{mv}', which does not start with '{freeze_tag}'. On a shallow "
            f"checkout `git describe --always` silently returns a bare SHA, which would stamp "
            f"every claim this season with a commit hash where the freeze tag belongs. "
            f"Set `fetch-depth: 0`."
        )
    else:
        pf.note(f"model_version {mv}")


# Which secrets each role needs. Module-level and exported because the workflow files must thread
# exactly these into the step that runs the preflight, and a test asserts they do — a second copy
# of this mapping in the test is how the two would drift apart (D25.4).
ROLE_SECRETS: dict[str, tuple[str, ...]] = {
    "predict": ("CFBD_API_KEY", "ODDS_API_KEY"),
    "capture": ("ODDS_API_KEY",),
    "grade": ("CFBD_API_KEY",),
    "freeze": ("CFBD_API_KEY",),
}


def check_secrets(pf: Preflight, role: str) -> None:
    """ABORT: fail here, not forty lines into a snapshot build."""
    needed = ROLE_SECRETS.get(role, ())
    for name in needed:
        if not (os.environ.get(name) or "").strip():
            pf.abort(f"{name} is unset or empty — required for role '{role}'.")
    if needed and not pf.aborts:
        pf.note(f"secrets present: {', '.join(needed)}")


def check_timing(pf: Preflight, cal: dict, now: datetime) -> None:
    """WARN ONLY: a late run still produces a usable observation; no run produces nothing."""
    pipeline = cal.get("pipeline", {})
    slack = int(pipeline.get("jitter_slack_minutes", 60))
    windows = (pipeline.get("kickoff_windows_et") or {}).get(
        ["mon", "tue", "wed", "thu", "fri", "sat", "sun"][now.weekday()], [])
    if not windows:
        return
    for w in windows:
        hh, mm = (int(x) for x in w.split(":"))
        kickoff = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
        deadline = kickoff - timedelta(minutes=slack)
        if now <= deadline:
            pf.note(f"{int((deadline - now).total_seconds() // 60)} min of slack before the "
                    f"{w} ET window (slack {slack} min)")
            return
    pf.warn(
        f"ran at {now:%H:%M} ET, inside or past every kickoff window for today "
        f"({', '.join(windows)}) minus {slack} min of slack. Continuing deliberately: a late "
        f"observation is simply not selected as the close for a game that already kicked, whereas "
        f"skipping the run loses the close for the whole slate."
    )


def report_budget(pf: Preflight, cal: dict, role: str) -> None:
    """Reporting only — the pre-spend refusal is fetch_lines' (exit 3)."""
    budget = (cal.get("pipeline", {}) or {}).get("odds_budget", {})
    remaining, source = last_remaining()
    if remaining is None:
        pf.note(f"Odds credits: unknown ({source}) — the pre-spend guard will use its own default")
        return
    floor_key = _CREDIT_FLOOR.get(role)
    floor = budget.get(floor_key) if floor_key else None
    pf.note(f"Odds credits: {remaining} remaining ({source})"
            + (f", floor for '{role}' is {floor}" if floor is not None else ""))
    if budget.get("alert_below") is not None and remaining < budget["alert_below"]:
        pf.warn(f"Odds credits {remaining} below alert_below {budget['alert_below']}.")
    weekly = budget.get("expected_weekly_credits")
    monthly = budget.get("monthly_credits")
    if weekly and monthly and remaining < monthly - weekly * 6:
        pf.warn(f"Odds burn is ahead of the expected {weekly}/week — check for a retry storm "
                f"(only {remaining} of {monthly} left).")


def emit(pf: Preflight, role: str, week: int | None, *, quiet: bool = False) -> int:
    lines = [f"### Preflight — role `{role}`" + (f", week {week:02d}" if week else "")]
    for n in pf.notes:
        lines.append(f"- ok: {n}")
    for w in pf.warns:
        lines.append(f"- **warn**: {w}")
    for a in pf.aborts:
        lines.append(f"- **ABORT**: {a}")
    body = "\n".join(lines)
    # `quiet` is for the unit tests, which exercise the ABORT/WARN branches and would otherwise
    # print full preflight blocks into the production freeze-integrity log — where a reader sees
    # "ABORT: factors/ has drifted" against a tag that does not exist and reasonably panics.
    if not quiet:
        print(body)

    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a") as fh:
            fh.write(body + "\n")
    return EXIT_ABORT if pf.aborts else EXIT_OK


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Pipeline preflight (freeze + provenance + timing).")
    parser.add_argument("--role", required=True,
                        choices=("predict", "capture", "grade", "freeze"))
    parser.add_argument("--week", type=int)
    parser.add_argument("--skip-secrets", action="store_true",
                        help="local/dry runs that make no API call")
    args = parser.parse_args(argv)

    cal = load_calendar()
    freeze_tag = (cal.get("pipeline", {}) or {}).get("freeze_tag", "v2026-frozen")
    now = datetime.now(ZoneInfo(pipeline_timezone(cal)))

    pf = Preflight()
    check_freeze(pf, freeze_tag)          # ABORT
    check_model_version(pf, freeze_tag)   # ABORT
    if not args.skip_secrets:
        check_secrets(pf, args.role)      # ABORT
    check_timing(pf, cal, now)            # WARN
    report_budget(pf, cal, args.role)     # report / WARN

    return emit(pf, args.role, args.week)


if __name__ == "__main__":
    raise SystemExit(main())
