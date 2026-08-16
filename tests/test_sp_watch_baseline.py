"""The SP+ watch alerts on DEVIATION from the ratified baseline, and stays quiet at it.

**Why this file exists.** After returning production arrived and was ratified, `BASELINE` still
read `returning_production: 0`. Left that way, the probe would have reported the same,
already-ratified arrival on every daily run forever — and when preseason SP+ finally landed,
`arrivals()` would have returned **both** sources, deduping onto the stale open issue under a title
naming both, instead of opening a clean "SP+ has arrived".

So the requirement is sharper than "it alerts": a transition must open a **fresh,
correctly-labelled** issue. Silence is one failure; alerting for the wrong reason, or on top of a
stale alert, is the other. Both are pinned here.

**Both transitions have now landed** — returning production (exception 1, `v2026-frozen-2`) and
preseason SP+ (exception 2, `v2026-frozen-3`). Nothing is outstanding, so the probe's job changed:
it now watches for **revisions to either ratified source, in either direction**. The comparison in
`arrivals()` is `!=`, not `>`; a provider withdrawing rows moves model output just as surely as
publishing them, and nothing else in the codebase observes either (the fingerprint gate reads a
pinned committed vehicle, D29). That closes `docs/2027_NOTES.md` §8 item 8.

Updating the baseline is a **step of the exception process** (SPEC §3.1), not an afterthought.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from scripts.sp_watch import BASELINE, arrivals

ROOT = Path(__file__).resolve().parent.parent
RATIFIED_RP_ROWS = 136
RATIFIED_SP_ROWS = 139  # raw API rows; the snapshot carries 138 (see below)


def observe(sp: int, rp: int) -> dict[str, int]:
    return {"sp_ratings": sp, "returning_production": rp}


# --- both transitions are ratified; the baseline records them ------------------------------------

def test_the_baseline_records_both_ratified_row_counts():
    assert BASELINE["returning_production"] == RATIFIED_RP_ROWS
    assert BASELINE["sp_ratings"] == RATIFIED_SP_ROWS, (
        "SP+ landed 2026-08-14 and was ratified under SPEC §3.1 exception 2 — leaving this at 0 "
        "makes the probe re-report a ratified arrival on every run forever"
    )


def test_the_sp_baseline_counts_raw_api_rows_not_snapshot_teams():
    """139 vs 138 is not an off-by-one and must not be 'fixed'.

    `counts()` measures `len(client.get_sp_ratings(year))` — RAW API rows. The 139th row is CFBD's
    `nationalAverages` aggregate, which the normalizer correctly drops, so the snapshot carries
    138 teams. Recorded in SPEC §3.1 exception 2.
    """
    assert RATIFIED_SP_ROWS == 139
    assert arrivals(observe(sp=138, rp=RATIFIED_RP_ROWS)) == ["sp_ratings"], (
        "138 is the NORMALIZED team count; the probe compares raw rows, so 138 is a deviation"
    )


# --- the ratified state must be quiet ------------------------------------------------------------

def test_the_ratified_state_no_longer_alerts():
    """The defect this file was written for: a permanent daily false alarm."""
    assert arrivals(observe(sp=RATIFIED_SP_ROWS, rp=RATIFIED_RP_ROWS)) == []


def test_a_reverted_baseline_would_be_caught():
    """Guards the regression directly: resetting a ratified source to 0 makes the probe cry wolf."""
    reverted = {"sp_ratings": 0, "returning_production": 0}
    assert arrivals(observe(sp=RATIFIED_SP_ROWS, rp=RATIFIED_RP_ROWS), reverted) == [
        "returning_production", "sp_ratings"]
    assert arrivals(observe(sp=RATIFIED_SP_ROWS, rp=RATIFIED_RP_ROWS), BASELINE) == []


# --- still sensitive to genuine change -----------------------------------------------------------

def test_further_growth_still_alerts():
    """More teams published is more model input — the fingerprint would move, so this must too."""
    assert arrivals(observe(sp=RATIFIED_SP_ROWS, rp=RATIFIED_RP_ROWS + 1)) == [
        "returning_production"]


def test_a_revision_names_only_the_source_that_moved():
    """A fresh, correctly-labelled alert — not one blended with a source sitting at its baseline."""
    assert arrivals(observe(sp=RATIFIED_SP_ROWS + 2, rp=RATIFIED_RP_ROWS)) == ["sp_ratings"]


def test_both_sources_moving_reports_both():
    assert arrivals(observe(sp=RATIFIED_SP_ROWS + 1, rp=RATIFIED_RP_ROWS + 5)) == [
        "returning_production", "sp_ratings"]


def test_a_source_going_backwards_NOW_alerts():
    """**Inverted under SPEC §3.1 exception 2.** This previously asserted silence on a shrink.

    That was the old `>` comparison encoded as the contract, and it was a real gap: the fingerprint
    gate reads the pinned static vehicle (D29) and never re-queries CFBD, so a provider withdrawing
    rows had **no observer at all**. A shrink moves model output just as surely as growth — the
    affected teams fall back to D10's flat-prior path, which is a documented state, but the model
    is then no longer the one the tag was measured against, and that is what an exception exists
    to record.

    The accepted cost, stated in `scripts/sp_watch.py` and in the exception entry: CFBD revises row
    counts routinely, so this fires on ordinary revisions. Alarm volume is paid deliberately.
    Closes `docs/2027_NOTES.md` §8 item 8.
    """
    assert arrivals(observe(sp=RATIFIED_SP_ROWS, rp=RATIFIED_RP_ROWS - 10)) == [
        "returning_production"]
    assert arrivals(observe(sp=RATIFIED_SP_ROWS - 1, rp=RATIFIED_RP_ROWS)) == ["sp_ratings"]


def test_the_shrink_assertion_can_actually_fail():
    """**Proof of discriminating power.** The same observation must be SILENT under the superseded
    `>` comparison — otherwise this test would pass whether or not the inversion actually shipped,
    which is the failure mode this project keeps recording."""
    def old_growth_only(observed, base):
        return sorted(k for k, n in observed.items() if n > base.get(k, 0))

    shrunk = observe(sp=RATIFIED_SP_ROWS, rp=RATIFIED_RP_ROWS - 10)
    assert old_growth_only(shrunk, BASELINE) == [], "the control is wrong, not the code"
    assert arrivals(shrunk, BASELINE) == ["returning_production"]


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


def test_the_sp_baseline_matches_the_row_count_recorded_in_exception_2():
    """Same single-source-of-truth rule for the SP+ transition."""
    spec = (ROOT / "docs" / "SPEC.md").read_text()
    block = spec.split("Exception 2 —", 1)
    assert len(block) == 2, "SPEC §3.1 exception 2 not found"
    entry = block[1][:4000]
    assert re.search(rf"\b{RATIFIED_SP_ROWS}\b", entry), (
        f"SPEC §3.1 exception 2 does not record {RATIFIED_SP_ROWS} sp_ratings rows"
    )
    assert BASELINE["sp_ratings"] == RATIFIED_SP_ROWS


# The specific language the process guarantee lives in. Substring-matching "sp_watch" and
# "baseline" was NOT enough: both already appeared in SPEC before this guarantee existed (the
# exception-1 trigger sentence, and the unrelated "## 2. 2025 Baseline" heading), so the assertion
# passed against a SPEC that documented nothing. A test that cannot fail reads as protection while
# providing none — the precise failure this project keeps recording.
REQUIRED_PROCESS_LANGUAGE = (
    "Ratifying a transition includes updating",
    "newly-ratified row counts",
    "tests/test_sp_watch_baseline.py",
)


def _normalised(text: str) -> str:
    """Collapse whitespace so a phrase still matches across the source's line wrapping."""
    return " ".join(text.split())


def test_the_exception_process_documents_updating_the_baseline():
    """So the SP+ transition cannot repeat this."""
    spec = _normalised((ROOT / "docs" / "SPEC.md").read_text())
    for phrase in REQUIRED_PROCESS_LANGUAGE:
        assert phrase in spec, (
            f"SPEC §3.1 no longer states the process step ({phrase!r} missing). Ratifying a "
            f"transition must include updating the sp_watch baseline, or the next arrival dedupes "
            f"onto a stale issue."
        )


def test_that_assertion_can_actually_fail():
    """**Proof of discriminating power.** The same assertion must FAIL against the SPEC as it stood
    before this guarantee was written — otherwise it is matching text that predates the guarantee
    and protects nothing, which is exactly what the first version of this test did."""
    import shutil
    import subprocess

    if shutil.which("git") is None:
        pytest.skip("git unavailable")
    before = subprocess.run(["git", "show", "81f837a:docs/SPEC.md"],
                            capture_output=True, text=True, cwd=str(ROOT))
    if before.returncode != 0:
        pytest.skip("pre-guarantee revision unavailable (shallow checkout)")

    prior = _normalised(before.stdout)
    assert not all(p in prior for p in REQUIRED_PROCESS_LANGUAGE), (
        "the required phrases were already present before this PR added the guarantee — the "
        "assertion is matching pre-existing text and would pass whether or not the process step "
        "is documented"
    )


@pytest.mark.parametrize("source", ["sp_ratings", "returning_production"])
def test_every_watched_source_has_a_baseline(source):
    assert source in BASELINE
