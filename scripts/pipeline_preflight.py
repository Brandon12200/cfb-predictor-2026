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
import json
import os
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
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
        self.annotations: list[str] = []

    def abort(self, msg: str) -> None:
        self.aborts.append(msg)

    def warn(self, msg: str) -> None:
        self.warns.append(msg)

    def note(self, msg: str) -> None:
        self.notes.append(msg)

    def annotate(self, msg: str) -> None:
        """A `::warning::` annotation on the run page, for warnings that must not be scrolled past."""
        self.annotations.append(msg)


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


@dataclass
class TimingVerdict:
    """What the timing guard concluded about one run (D44).

    ``status``: ``not_time_critical`` (not a capture) | ``manual`` (no scheduled slot) |
    ``unknown_slot`` (the triggering cron is not in season.json) | ``on_time`` | ``late`` (after the
    slack, still before its window) | ``missed`` (at or after the window its slot precedes).
    """
    status: str
    kind: str | None = None
    slot_et: datetime | None = None
    window_et: datetime | None = None
    lateness_min: int | None = None
    margin_min: int | None = None
    games: list[str] = field(default_factory=list)
    slate_problem: str | None = None

    @property
    def guarantee_miss(self) -> bool:
        return self.status == "missed" and self.kind == "guarantee"


def _norm_cron(cron: str) -> str:
    return " ".join(cron.split())


def slot_fired_at(cron: str, now: datetime) -> datetime:
    """The most recent UTC time at or before ``now`` that ``cron`` (``m h * * dow``) names."""
    minute, hour, _, _, dow = _norm_cron(cron).split()
    days = None if dow == "*" else {int(d) for d in dow.split(",")}
    now_utc = now.astimezone(UTC)
    for back in range(8):
        day = now_utc - timedelta(days=back)
        cand = day.replace(hour=int(hour), minute=int(minute), second=0, microsecond=0)
        if cand <= now_utc and (days is None or (cand.weekday() + 1) % 7 in days):
            return cand
    raise ValueError(f"cron {cron!r} names no time in the last week")


def _games_in_window(window: datetime, windows: list[str], week: int | None,
                     year: int | None) -> tuple[list[str], str | None]:
    """(games kicking off in this window, problem reading the store).

    Never raises. The game list is colour on a warning; the store it reads is a live append-only
    file that a killed run could leave truncated, and a timing check must not be the thing that
    decides whether a capture happens (WARN-not-ABORT).
    """
    if week is None or year is None:
        return [], None
    path = ROOT / "data" / "lines" / f"{year}_week_{week:02d}.json"
    if not path.exists():
        return [], None
    try:
        store = json.loads(path.read_text())
        later = sorted(t for t in (window.replace(hour=int(w[:2]), minute=int(w[3:])) for w in windows)
                       if t > window)
        until = later[0] if later else window.replace(hour=23, minute=59, second=59)
        games = []
        for key, entry in store.items():
            kick = entry.get("kickoff")
            if not kick:
                continue
            k = datetime.fromisoformat(kick.replace("Z", "+00:00")).astimezone(window.tzinfo)
            if window <= k < until:
                games.append(key)
        return sorted(games), None
    except Exception as exc:                       # noqa: BLE001 — see the docstring
        return [], f"{path.name} could not be read ({type(exc).__name__}: {exc})"


def evaluate_timing(cal: dict, role: str, now: datetime, *, event_name: str, schedule: str,
                    week: int | None = None, year: int | None = None) -> TimingVerdict:
    """Judge a run against the slot that fired it and the window that slot precedes (D44).

    The previous check measured slack against the next kickoff window still ahead TODAY. So a
    capture that missed its own window found a later one to count against and reported healthy
    slack (13 of 21 missed captures through week 3), a Saturday slot firing after midnight was
    scored against Sunday's window, and the Sunday grade warned every week. This uses
    ``github.event.schedule`` to identify the slot, and judges the run on the slot's own ET date.
    """
    if role != "capture":
        return TimingVerdict("not_time_critical")
    if event_name != "schedule":
        return TimingVerdict("manual")
    if not schedule.strip():
        # A scheduled run always has `github.event.schedule`. Empty here means the value was not
        # threaded through (the D39 class), and every D44 tier would go silent for this run.
        return TimingVerdict("unknown_slot")
    pipeline = cal.get("pipeline", {})
    entry = next((e for e in pipeline.get("schedule_et", {}).get("capture", [])
                  if _norm_cron(e["cron_utc"]) == _norm_cron(schedule)), None)
    if entry is None:
        return TimingVerdict("unknown_slot")
    tz = now.tzinfo or ZoneInfo(pipeline_timezone(cal))
    slot_et = slot_fired_at(entry["cron_utc"], now).astimezone(tz)
    hh, mm = (int(x) for x in entry["precedes"].split(":"))
    window = slot_et.replace(hour=hh, minute=mm, second=0, microsecond=0)
    lateness = int((now - slot_et).total_seconds() // 60)
    margin = int((window - now).total_seconds() // 60)
    slack = int(pipeline.get("jitter_slack_minutes", 60))
    status = "missed" if now >= window else ("late" if lateness > slack else "on_time")
    day = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"][slot_et.weekday()]
    day_windows = pipeline.get("kickoff_windows_et", {}).get(day, [])
    games, problem = _games_in_window(window, day_windows, week, year)
    return TimingVerdict(status, entry["kind"], slot_et, window, lateness, margin, games, problem)


def check_timing(pf: Preflight, cal: dict, now: datetime, *, role: str, event_name: str,
                 schedule: str, week: int | None = None, year: int | None = None) -> TimingVerdict:
    """WARN ONLY (owner ruling 2026-08-07, kept by D44): a late observation is still evidence.

    Escalation tiers 0-1 live here; tier 2 is the capture workflow acting on the verdict:
    * tier 0, every capture: one summary line with the slot, its lateness and the target window;
    * tier 1, a GUARANTEE slot that landed at or after its window: a warning plus a `::warning::`
      annotation naming the window and its games. A best-effort miss is expected by design
      (owner ruling 2026-09-15), so it stays at tier 0.
    """
    try:
        v = evaluate_timing(cal, role, now, event_name=event_name, schedule=schedule,
                            week=week, year=year)
    except Exception as exc:                       # noqa: BLE001
        # The timing check is WARN-only by ratified ruling (2026-08-07, kept by D44). It runs in the
        # preflight, BEFORE the fetch, so an exception here would fail cfb-setup and the capture
        # would never happen — a guard deciding there is no observation at all, which is the exact
        # inversion the severity split exists to prevent. Reported loudly, never raised.
        msg = (f"timing: the guard could not judge this run ({type(exc).__name__}: {exc}). "
               f"Continuing: timing is WARN-only and the capture matters more than the verdict.")
        pf.warn(msg)
        pf.annotate(msg)
        return TimingVerdict("unknown_slot")
    if v.slate_problem:
        pf.warn(f"timing: {v.slate_problem}. The window's games cannot be listed; the verdict "
                f"below stands, and grading reads the same file.")
    if v.status == "not_time_critical":
        pf.note(f"timing: not evaluated for role '{role}' (only capture is time-critical, D44)")
    elif v.status == "manual":
        pf.note("timing: manual run, no scheduled slot to judge against")
    elif v.status == "unknown_slot":
        msg = (f"timing: the triggering cron '{schedule}' is not in season.json "
               f"schedule_et.capture, so this run's window is unknown. The workflow and the "
               f"config have drifted apart." if schedule.strip() else
               "timing: a SCHEDULED capture arrived with no github.event.schedule, so its slot "
               "cannot be judged and no D44 tier can fire. CFB_EVENT_SCHEDULE is not reaching the "
               "preflight (D39 class).")
        pf.warn(msg)
        pf.annotate(msg)
    else:
        assert v.slot_et and v.window_et and v.lateness_min is not None and v.margin_min is not None
        where = (f"{v.margin_min} min before the {v.window_et:%H:%M} ET window" if v.margin_min > 0
                 else f"{-v.margin_min} min AFTER the {v.window_et:%H:%M} ET window")
        pf.note(f"timing: {v.kind} slot {v.slot_et:%a %H:%M} ET fired {v.lateness_min} min late, "
                f"{where} ({v.status})")
        if v.guarantee_miss:
            games = ", ".join(v.games) if v.games else "no slate games loaded for this window"
            msg = (f"GUARANTEE capture slot {v.slot_et:%a %H:%M} ET missed its {v.window_et:%H:%M} "
                   f"ET window by {-v.margin_min} min ({v.lateness_min} min late). Games in the "
                   f"window: {games}. Their close falls back to an earlier observation. Continuing: "
                   f"a late observation is still evidence (WARN-not-ABORT).")
            pf.warn(msg)
            pf.annotate(msg)
        elif v.status == "missed":
            pf.note("timing: best-effort slot landed after its window, which D44 expects about "
                    "four times in ten; the guarantee slot covers this window")
    return v


def write_timing_outputs(v: TimingVerdict, *, quiet: bool = False) -> None:
    """Tier 2 hand-off: the capture workflow opens the weekly `pipeline-late` issue on a guarantee
    miss. Written to the Preflight step's $GITHUB_OUTPUT; `quiet` keeps unit tests out of it."""
    out = None if quiet else os.environ.get("GITHUB_OUTPUT")
    if not out:
        return
    detail = ""
    if v.slot_et and v.window_et and v.margin_min is not None:
        detail = (f"{v.kind} slot {v.slot_et:%a %Y-%m-%d %H:%M} ET, window {v.window_et:%H:%M} ET, "
                  f"{v.lateness_min} min late, margin {v.margin_min} min; games: "
                  f"{', '.join(v.games) or 'none loaded'}")
    with open(out, "a") as fh:
        fh.write(f"timing_status={v.status}\n")
        fh.write(f"timing_guarantee_miss={'true' if v.guarantee_miss else 'false'}\n")
        fh.write(f"timing_detail={detail}\n")


def report_budget(pf: Preflight, cal: dict, role: str) -> None:
    """Reporting only — the pre-spend refusal is fetch_lines' (exit 3).

    Wrapped like the timing check, and for the same reason: this runs in the preflight, BEFORE the
    fetch, and it reads a committed ledger that a killed run could have left torn. An exception here
    would fail `cfb-setup` and the capture would never happen — a *report* deciding there is no
    observation at all. The pre-spend guard is unaffected: it lives in `fetch_lines` and still
    refuses on its own reading of the balance.
    """
    try:
        _report_budget(pf, cal, role)
    except Exception as exc:                       # noqa: BLE001
        pf.warn(f"budget: the balance could not be reported ({type(exc).__name__}: {exc}). "
                f"Continuing: this is reporting only, and fetch_lines still runs its own pre-spend "
                f"check. A torn `data/quota` ledger is the likely cause and needs looking at.")


def _report_budget(pf: Preflight, cal: dict, role: str) -> None:
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
        for ann in pf.annotations:
            print(f"::warning::{ann}")

    # `quiet` must also suppress the step-summary write. It did not, so in CI the unit tests'
    # synthetic ABORT blocks were appended to the REAL run summary — a reader saw
    # "ABORT: factors/ has drifted" against a tag that does not exist, produced by a passing test.
    # A self-test must not be able to write to the production report.
    summary = None if quiet else os.environ.get("GITHUB_STEP_SUMMARY")
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
    # No silent default. Defaulting to a tag name means a missing/renamed config key would assert
    # the freeze against a SUPERSEDED tag and pass — the freeze check would be validating the wrong
    # reference while reporting success. An absent key must abort instead.
    freeze_tag = (cal.get("pipeline", {}) or {}).get("freeze_tag")
    if not freeze_tag:
        # Routed through emit() like every other abort, so it reaches $GITHUB_STEP_SUMMARY. It
        # previously printed straight to stdout and returned, so this one diagnosis — a missing
        # freeze reference — was the only abort invisible on the Actions summary page.
        pf = Preflight()
        pf.abort("season.json has no `pipeline.freeze_tag` — the freeze cannot be asserted "
                 "against an unknown reference.")
        return emit(pf, args.role, args.week)
    now = datetime.now(ZoneInfo(pipeline_timezone(cal)))

    pf = Preflight()
    check_freeze(pf, freeze_tag)          # ABORT
    check_model_version(pf, freeze_tag)   # ABORT
    if not args.skip_secrets:
        check_secrets(pf, args.role)      # ABORT
    verdict = check_timing(pf, cal, now, role=args.role,   # WARN, tiers 0-1 (D44)
                           event_name=os.environ.get("GITHUB_EVENT_NAME", ""),
                           schedule=os.environ.get("CFB_EVENT_SCHEDULE", ""),
                           week=args.week, year=int(cal.get("season", 0)) or None)
    write_timing_outputs(verdict)                            # tier 2 hand-off
    report_budget(pf, cal, args.role)     # report / WARN

    return emit(pf, args.role, args.week)


if __name__ == "__main__":
    raise SystemExit(main())
