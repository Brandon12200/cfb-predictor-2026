"""Season calendar loading and date->week inference (Phase 0 interim, D1).

Fixes the silent week-1 default in the old ``main._get_current_week``: omitting
``--week`` used to analyze games with week-1 context, producing different results
than passing the correct week. Here the week is derived from the date via the
config home ``season.json``; when the date falls outside the season we raise rather
than guess. Phase 4.5 **folded the calendar into ``season.json``** (D24, the config
home for the ``cfb`` CLI — stdlib JSON, not the SPEC's ``season.yaml``, to avoid a
YAML dependency). ``season.json``'s ``weeks`` are kept in sync with the CFBD-
corroborated ``data/season_calendar_2026.json`` (D8) by a test.

Pure and network-free so it is deterministically testable.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

_CONFIG_PATH = Path(__file__).resolve().parent.parent / "season.json"


class WeekInferenceError(Exception):
    """Raised when the CFB week cannot be determined from the date."""


def load_calendar(path: Path | str = _CONFIG_PATH) -> dict:
    """Load the season config (season, weeks -> {start, end}, cli_defaults)."""
    with open(path) as f:
        return json.load(f)


def cli_defaults(path: Path | str = _CONFIG_PATH) -> dict:
    """The ``cfb`` CLI defaults from ``season.json`` (config-over-flags, SPEC §9.6).
    Empty dict if the section is absent so callers fall back to argparse defaults."""
    try:
        return load_calendar(path).get("cli_defaults", {}) or {}
    except (OSError, ValueError):
        return {}


def infer_week_for_date(today: date, calendar: dict | None = None) -> int:
    """Return the week whose inclusive [start, end] range contains ``today``.

    Raises ``WeekInferenceError`` when ``today`` is outside every week range.
    """
    cal = calendar if calendar is not None else load_calendar()
    weeks = cal["weeks"]
    for wk, span in weeks.items():
        start = date.fromisoformat(span["start"])
        end = date.fromisoformat(span["end"])
        if start <= today <= end:
            return int(wk)
    season = cal.get("season", "?")
    first = weeks[min(weeks, key=lambda k: int(k))]["start"]
    last = weeks[max(weeks, key=lambda k: int(k))]["end"]
    raise WeekInferenceError(
        f"Cannot infer CFB week: {today.isoformat()} is outside the {season} "
        f"season ({first} .. {last}). Re-run with an explicit --week."
    )


DEFAULT_PIPELINE_TIMEZONE = "America/New_York"


def pipeline_timezone(calendar: dict | None = None) -> str:
    """IANA zone the pipeline's cadence is expressed in (``season.json`` ``pipeline.timezone``).

    Falls back to ET so this stays usable if the config block is absent.
    """
    cal = calendar if calendar is not None else load_calendar()
    return (cal.get("pipeline") or {}).get("timezone") or DEFAULT_PIPELINE_TIMEZONE


def pipeline_today(calendar: dict | None = None, now: datetime | None = None) -> date:
    """Today's date **in the pipeline's timezone**, not the runner's.

    GitHub Actions runners are UTC. A Saturday-evening ET capture is already Sunday in UTC, so a
    UTC-derived date can resolve into the following week and file an observation under the wrong
    one. Every pipeline entry point takes its date from here.
    """
    tz = ZoneInfo(pipeline_timezone(calendar))
    return (now.astimezone(tz) if now is not None else datetime.now(tz)).date()


def pipeline_week(today: date, calendar: dict | None = None) -> int:
    """The week the PIPELINE should operate on for ``today`` — a different question from
    ``infer_week_for_date``, which answers "which week's games are being played right now".

    ``weeks`` is a **game-window** calendar (D8, CFBD-corroborated): week 1 is
    ``2026-08-29 … 2026-09-07``. But the week-1 prediction run happens on the Tuesday *before*
    kickoff — **2026-08-25** — which is inside no window at all, so ``infer_week_for_date`` raises
    and the entire first live cycle dies before it does anything. The pipeline needs "the next week
    still open for work", not "the week containing today".

    Rule: **the lowest-numbered week whose ``end`` is on or after ``today``**, clamped to the last
    week once the season's final window has closed. Never raises — a pipeline that cannot name its
    week has no safe fallback, and an operator reading a wrong-but-stated week is far better off
    than a workflow that aborts at 09:17 on a Tuesday.

    Consequence worth knowing: this returns 1 for every day from before the season through
    2026-09-07, so the Tuesday job runs "week 1" twice. That is handled by the byte-immutable claim
    file already existing (D22) — the predict step is skipped, which is also its idempotency guard.
    """
    cal = calendar if calendar is not None else load_calendar()
    weeks = cal["weeks"]
    for wk in sorted(weeks, key=lambda k: int(k)):
        if today <= date.fromisoformat(weeks[wk]["end"]):
            return int(wk)
    return int(max(weeks, key=lambda k: int(k)))


def resolve_week(explicit: int | None, today: date | None = None,
                 calendar: dict | None = None) -> int:
    """Return ``explicit`` if provided, else infer the week from ``today``.

    This is the single point that guarantees an omitted week resolves to the
    same value an explicit correct ``--week`` would supply.
    """
    if explicit is not None:
        return explicit
    if today is None:
        today = datetime.now().date()
    return infer_week_for_date(today, calendar)
