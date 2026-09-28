"""Close-age buckets and capture timeliness (D44 §(4) and tiers 3–4) — freeze-exempt.

Two questions the reports could not answer before, both computed from committed artifacts only:

1. **How stale was the close each CLV came from?** CLV compares our number to *the last observation
   before that game's kickoff*. If that observation is sixteen hours old, the comparison is honest
   but nearly meaningless, and a blended CLV figure hides which it was. D44 §(4) rules that CLV is
   reported by close age in three buckets, with counts.
2. **Did the capture cadence do its job?** D44 tiers 3–4: a timeliness line in the Sunday report, and
   escalation to the owner when a guarantee slot misses in 2 or more weeks of any 3.

**Both are derived, and the derivation is stated wherever the numbers are rendered.** Close age is
`kickoff − close_as_of`, so weeks 1–3 bucket correctly with no relabel of any append-only file
(D44 §(4)). Timeliness comes from the *observation timestamps in the line store*, not from run logs:
the distinct `fetched_at` values in a week's store are that week's capture runs, so the run a slot
produced is the earliest capture at or after the slot's scheduled time, and the slot covered its
window if that run landed before it. A run that produced no new observation for any game would be
invisible here; none has occurred, and the alternative — parsing Actions history — is not available
to a renderer reading committed JSON.

**The week-4 boundary is load-bearing, not cosmetic.** Weeks 1–3 ran one wave per window with no
guarantee slots at all (D44 §(2)), so judging them against D44's slots would manufacture misses for
a cadence that was never scheduled. Timeliness therefore applies from `BOUNDARY_WEEK` onward, and
the close-age tables are rendered per era and never blended across it.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

# D44 §(2): the workflow PR merged before Wed 2026-09-23, so week 4 is the first week captured under
# the new cadence. Week 4's CLAIM was still made on pre-D44 code (D46 §(4).1) — the boundary is about
# capture, which is what close age and timeliness measure.
BOUNDARY_WEEK = 4

# D44 §(4). The upper edge of each bucket in hours; the last is open.
CLOSE_AGE_BUCKETS: tuple[tuple[str, float | None], ...] = (
    ("≤3 h", 3.0),
    ("3–12 h", 12.0),
    (">12 h", None),
)

_DOW = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}


def _parse(ts: str | None) -> datetime | None:
    if not isinstance(ts, str) or not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None


def close_age_hours(kickoff: str | None, close_as_of: str | None) -> float | None:
    """Hours between the close observation and kickoff. ``None`` when either end is missing or
    unparseable — an unknown age is never silently bucketed as a fresh one."""
    ko, close = _parse(kickoff), _parse(close_as_of)
    if ko is None or close is None:
        return None
    return (ko - close).total_seconds() / 3600.0


def bucket_for(hours: float | None) -> str | None:
    """The bucket label for an age, or ``None`` when the age is unknown.

    A negative age (an observation timestamped after kickoff) falls in the first bucket by the same
    rule as a tiny positive one. `closing_observation` selects only pre-kickoff observations, so it
    should not arise; if it ever does, the count in the table is what surfaces it.
    """
    if hours is None:
        return None
    for label, upper in CLOSE_AGE_BUCKETS:
        if upper is None or hours <= upper:
            return label
    return CLOSE_AGE_BUCKETS[-1][0]


def kickoffs_from_lines(lines: dict[str, Any] | None) -> dict[str, str]:
    """``{"AWAY@HOME": kickoff}`` from a week's line store, the only committed artifact that carries
    a kickoff time per game (the claim does not)."""
    if not lines:
        return {}
    return {key: entry["kickoff"] for key, entry in lines.items()
            if isinstance(entry, dict) and entry.get("kickoff")}


def kickoff_for(kickoffs: dict[Any, str], row: dict) -> str | None:
    """The row's kickoff, preferring a week-scoped key.

    `AWAY@HOME` is unique within a week but **not** across a season: the same two teams can meet
    twice in one era (a conference-championship rematch), and a flat season-wide dict would let the
    later week's kickoff silently overwrite the earlier one's, dating a close against the wrong
    game. The season report therefore keys by `(week, matchup)`; the weekly report passes flat keys,
    which this still accepts (review of this PR).
    """
    key = f"{row.get('away_team')}@{row.get('home_team')}"
    week = row.get("week")
    if (week, key) in kickoffs:
        return kickoffs[(week, key)]
    return kickoffs.get(key)


def close_age_table(joined: list[dict], kickoffs: dict[Any, str]) -> dict[str, Any]:
    """CLV by close-age bucket over the graded rows that carry a CLV.

    Rows with no CLV are **excluded and counted**, never coerced: CLV is defined from the bet side's
    perspective, so a neutral lean has none (D22 f3), and bucketing it as 0.0 would pad the
    denominator of a CLV table with games that can never contribute one. `n_no_clv` is reported so
    the table can say why it counts fewer games than the week graded — the gap is the question a
    reader asks, and an unexplained one invites exactly the coercion this avoids.
    """
    rows: list[dict[str, Any]] = []
    unknown = 0
    no_clv = 0
    for r in joined:
        if r.get("clv") is None:
            no_clv += 1
            continue
        age = close_age_hours(kickoff_for(kickoffs, r), r.get("close_as_of"))
        label = bucket_for(age)
        if label is None:
            unknown += 1
            continue
        rows.append({"bucket": label, "clv": float(r["clv"]), "hours": age})

    buckets = []
    for label, _ in CLOSE_AGE_BUCKETS:
        mine = [x for x in rows if x["bucket"] == label]
        clvs = [x["clv"] for x in mine]
        buckets.append({
            "bucket": label,
            "n": len(mine),
            "avg_clv": (sum(clvs) / len(clvs)) if clvs else None,
            "beat_close_pct": (sum(1 for c in clvs if c > 0) / len(clvs)) if clvs else None,
            "max_hours": max((x["hours"] for x in mine), default=None),
        })
    return {"buckets": buckets, "n_clv": len(rows), "n_unknown_age": unknown, "n_no_clv": no_clv}


def capture_runs(lines: dict[str, Any] | None, tz: str) -> list[datetime]:
    """The week's capture runs, as the distinct observation timestamps in its line store.

    Each run appends one observation per game with that run's `fetched_at`, and `record_observation`
    dedupes on it, so the distinct set is the set of runs. Includes the Tuesday snapshot's seed
    observation, which is a real pre-kickoff observation even though no capture cron produced it.
    """
    if not lines:
        return []
    seen = {
        parsed.astimezone(ZoneInfo(tz))
        for entry in lines.values() if isinstance(entry, dict)
        for obs in entry.get("observations", []) or []
        if (parsed := _parse(obs.get("fetched_at"))) is not None
    }
    return sorted(seen)


def _at(day: datetime, hhmm: str) -> datetime:
    hour, minute = (int(x) for x in hhmm.split(":"))
    return day.replace(hour=hour, minute=minute, second=0, microsecond=0)


def guarantee_slots(week: int, calendar: dict, runs: list[datetime]) -> list[dict[str, Any]]:
    """Every guarantee slot scheduled inside the week, and whether the run it produced beat its
    window. `covered` is False when the slot produced no run at all."""
    pipeline = calendar.get("pipeline", {})
    tz = ZoneInfo(pipeline.get("timezone", "America/New_York"))
    weeks = calendar.get("weeks", {})
    if str(week) not in weeks:
        return []
    start = datetime.fromisoformat(weeks[str(week)]["start"]).replace(tzinfo=tz)
    end = datetime.fromisoformat(weeks[str(week)]["end"]).replace(tzinfo=tz)

    out: list[dict[str, Any]] = []
    for entry in pipeline.get("schedule_et", {}).get("capture", []):
        if entry.get("kind") != "guarantee":
            continue
        for day_name in entry.get("days", []):
            if day_name not in _DOW:
                continue
            cursor = start
            while cursor.date() <= end.date():
                if cursor.weekday() == _DOW[day_name]:
                    slot = _at(cursor, entry["time_edt"])
                    window = _at(cursor, entry["precedes"])
                    produced = next((r for r in runs if r >= slot), None)
                    out.append({
                        "day": day_name,
                        "slot_et": slot,
                        "window_et": window,
                        "run_et": produced,
                        "covered": produced is not None and produced < window,
                    })
                cursor += timedelta(days=1)
    return sorted(out, key=lambda s: s["slot_et"])


def timeliness(week: int, calendar: dict, lines: dict[str, Any] | None) -> dict[str, Any]:
    """D44 tier 3: one week's guarantee-slot record.

    ``applies`` is False before the cadence boundary — weeks 1–3 had no guarantee slots, so a miss
    count for them would describe a schedule that never ran (D44 §(2)).
    """
    if week < BOUNDARY_WEEK:
        return {"week": week, "applies": False, "reason": (
            f"weeks 1–{BOUNDARY_WEEK - 1} ran one capture wave per window with no guarantee slots "
            f"(D44 §(2)), so there is nothing to judge against")}
    tz = calendar.get("pipeline", {}).get("timezone", "America/New_York")
    slots = guarantee_slots(week, calendar, capture_runs(lines, tz))
    missed = [s for s in slots if not s["covered"]]
    return {"week": week, "applies": True, "n_slots": len(slots), "n_missed": len(missed),
            "missed": missed, "runs": len(capture_runs(lines, tz))}


def escalation_due(misses_by_week: dict[int, int]) -> dict[str, Any]:
    """D44 tier 4: escalate when a guarantee slot misses in **2 or more weeks of any 3**.

    Evaluated over every 3-week window of the weeks supplied, so it fires on 2-of-3 anywhere in the
    season rather than only on the most recent three. Weeks before the boundary are not supplied and
    cannot contribute.
    """
    weeks = sorted(misses_by_week)
    for i in range(len(weeks)):
        window = [w for w in weeks if weeks[i] <= w <= weeks[i] + 2]
        hits = [w for w in window if misses_by_week[w] > 0]
        if len(hits) >= 2:
            return {"due": True, "window": (weeks[i], weeks[i] + 2), "weeks_with_misses": hits}
    return {"due": False, "window": None, "weeks_with_misses":
            [w for w in weeks if misses_by_week[w] > 0]}
