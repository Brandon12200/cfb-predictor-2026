"""The SP+ watch alerts on the OUTSTANDING transition, and stays quiet about ratified ones.

**Why this file exists.** After returning production arrived and was ratified, `BASELINE` still
read `returning_production: 0`. Left that way, the probe would have reported the same,
already-ratified arrival on every daily run forever — and when preseason SP+ finally landed,
`arrivals()` would have returned **both** sources, deduping onto the stale open issue under a title
naming both, instead of opening a clean "SP+ has arrived".

So the requirement is sharper than "it alerts": the remaining transition must open a **fresh,
correctly-labelled** issue. Silence is one failure; alerting for the wrong reason, or on top of a
stale alert, is the other. Both are pinned here.

Updating the baseline is a **step of the exception process** (SPEC §3.1), not an afterthought.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from scripts.sp_watch import BASELINE, arrivals

ROOT = Path(__file__).resolve().parent.parent
RATIFIED_RP_ROWS = 136


def observe(sp: int, rp: int) -> dict[str, int]:
    return {"sp_ratings": sp, "returning_production": rp}


# --- the outstanding transition ------------------------------------------------------------------

def test_sp_plus_is_the_one_source_still_being_watched():
    assert BASELINE["sp_ratings"] == 0, (
        "SP+ must stay at 0 until it actually publishes — this is the live tripwire"
    )


def test_sp_plus_arrival_alerts_and_names_only_itself():
    """The requirement: a fresh, correctly-labelled alert — not one blended with a ratified source."""
    assert arrivals(observe(sp=137, rp=RATIFIED_RP_ROWS)) == ["sp_ratings"]


def test_a_single_sp_plus_row_is_enough():
    """Partial publication still changes the model's inputs."""
    assert arrivals(observe(sp=1, rp=RATIFIED_RP_ROWS)) == ["sp_ratings"]


# --- the ratified transition must be quiet -------------------------------------------------------

def test_the_ratified_returning_production_no_longer_alerts():
    """The defect this file was written for: a permanent daily false alarm."""
    assert arrivals(observe(sp=0, rp=RATIFIED_RP_ROWS)) == []


def test_the_baseline_records_the_ratified_row_count():
    assert BASELINE["returning_production"] == RATIFIED_RP_ROWS


def test_a_reverted_baseline_would_be_caught():
    """Guards the regression directly: resetting RP to 0 makes the probe cry wolf forever."""
    reverted = {"sp_ratings": 0, "returning_production": 0}
    assert arrivals(observe(sp=0, rp=RATIFIED_RP_ROWS), reverted) == ["returning_production"]
    assert arrivals(observe(sp=0, rp=RATIFIED_RP_ROWS), BASELINE) == []


# --- still sensitive to genuine change -----------------------------------------------------------

def test_further_returning_production_growth_still_alerts():
    """More teams published is more model input — the fingerprint would move, so this must too."""
    assert arrivals(observe(sp=0, rp=RATIFIED_RP_ROWS + 1)) == ["returning_production"]


def test_both_sources_moving_reports_both():
    assert arrivals(observe(sp=137, rp=RATIFIED_RP_ROWS + 5)) == [
        "returning_production", "sp_ratings"]


def test_a_source_going_backwards_does_not_alert():
    """A provider withdrawing rows is not an input-arrival event; the fingerprint gate owns that."""
    assert arrivals(observe(sp=0, rp=RATIFIED_RP_ROWS - 10)) == []


# --- the baseline cannot drift from the ratified record ------------------------------------------

def test_the_baseline_matches_the_row_count_recorded_in_the_spec_exception():
    """One source of truth. If the exception entry and the tripwire disagree, one of them is lying
    about what the current tag was measured against."""
    spec = (ROOT / "docs" / "SPEC.md").read_text()
    block = spec.split("Exception 1 —", 1)
    assert len(block) == 2, "SPEC §3.1 exception 1 not found"
    entry = block[1][:4000]
    assert re.search(rf"\b{RATIFIED_RP_ROWS}\b", entry), (
        f"SPEC §3.1 does not record {RATIFIED_RP_ROWS} returning-production rows"
    )
    assert BASELINE["returning_production"] == RATIFIED_RP_ROWS


def test_the_exception_process_documents_updating_the_baseline():
    """So the SP+ transition cannot repeat this."""
    spec = (ROOT / "docs" / "SPEC.md").read_text()
    assert "sp_watch" in spec and "baseline" in spec.lower(), (
        "SPEC §3.1 must state that ratifying a transition includes updating the sp_watch baseline"
    )


@pytest.mark.parametrize("source", ["sp_ratings", "returning_production"])
def test_every_watched_source_has_a_baseline(source):
    assert source in BASELINE
