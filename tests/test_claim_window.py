"""The season-aware claim gate (D38) — a claim may only be written when it is due.

**The incident this pins.** `pipeline_week` returns the lowest-numbered week whose `end` has not
passed, so it returned **1** for every date from before the season through 2026-09-07. The cadence
went live when the pipeline merged, and the **first Tuesday after that — 2026-08-11 — the scheduled
predict run wrote the real week-1 claim**, 14 days early, from a preseason snapshot containing 11 of
~138 games. Because a claim is byte-immutable and its prior existence is the predict step's skip
condition, the intended 2026-08-25 run would have skipped, and that thin file would have been the
season's week-1 pre-registration permanently. The claim was voided under D38 (no predicted event had
occurred, so the void could not be outcome-motivated) and this gate shipped in the same change.

`pipeline_week` was not wrong — it answers "which week am I working on". What was missing was any
notion of **when a claim becomes due**, which is what `claim_window_open` adds.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import pytest

from utils.season_calendar import CLAIM_LEAD_DAYS, claim_window_open, pipeline_week

ROOT = Path(__file__).resolve().parent.parent
CAL = json.loads((ROOT / "season.json").read_text())


# --- the dates that actually happened ------------------------------------------------------------

@pytest.mark.parametrize("day,expected,why", [
    (date(2026, 8, 11), False, "the Tuesday that wrote the early claim — 18 days before kickoff"),
    (date(2026, 8, 18), False, "the next Tuesday — 11 days out, would have recreated the defect"),
    (date(2026, 8, 25), True, "the INTENDED predict run — 4 days out, the last before kickoff"),
    (date(2026, 8, 29), True, "kickoff day itself"),
])
def test_the_week_one_claim_window(day, expected, why):
    assert claim_window_open(1, day, CAL) is expected, why


def test_pipeline_week_still_resolves_week_one_on_the_early_dates():
    """The gate must be a SEPARATE guard, not a change to week resolution.

    `pipeline_week` returning 1 on 08-11 is correct and load-bearing — the Tuesday job still builds
    the snapshot, the derived exports and the line observations for week 1 on those dates. Only the
    *claim* waits. If a future change 'fixes' this by making `pipeline_week` raise or return
    something else, the whole preseason cadence stops working.
    """
    for day in (date(2026, 8, 11), date(2026, 8, 18), date(2026, 8, 25)):
        assert pipeline_week(day, CAL) == 1


# --- the general rule, not just week 1 -----------------------------------------------------------

def test_every_week_opens_exactly_one_cadence_before_its_start():
    for wk, span in CAL["weeks"].items():
        start = date.fromisoformat(span["start"])
        assert claim_window_open(int(wk), start - timedelta(days=CLAIM_LEAD_DAYS), CAL) is True
        assert claim_window_open(int(wk), start - timedelta(days=CLAIM_LEAD_DAYS + 1), CAL) is False


def test_a_week_already_under_way_is_never_blocked():
    """Catch-up and backfill must not be gated here — D22's immutability is the guard for those."""
    for wk, span in CAL["weeks"].items():
        assert claim_window_open(int(wk), date.fromisoformat(span["end"]), CAL) is True


# --- the derived constant must not go stale ------------------------------------------------------

def test_the_lead_window_matches_the_predict_cadence_it_is_derived_from():
    """`CLAIM_LEAD_DAYS` is 7 *because* predict fires on one weekday, i.e. weekly. If the cadence
    ever becomes twice-weekly, a 7-day window would admit two predict runs and the earlier one would
    claim the slot — reintroducing the defect in a subtler form. This fails if that happens."""
    predict = CAL["pipeline"]["schedule_et"]["predict"]
    days = [d for entry in predict for d in entry["days"]]
    assert len(days) == 1, (
        f"predict now fires on {days}; CLAIM_LEAD_DAYS={CLAIM_LEAD_DAYS} assumes a weekly cadence "
        f"and must be re-derived (D38)"
    )
    assert CLAIM_LEAD_DAYS == 7


# --- the wiring: a guard nothing consumes is not a guard -----------------------------------------

def test_pipeline_week_script_emits_the_flag():
    from scripts.pipeline_week import resolve
    out = resolve(1, 2026, CAL)
    assert out["claim_window_open"] in ("true", "false")


def test_the_workflow_gates_both_the_build_and_the_claim_commit_on_it():
    body = (ROOT / ".github" / "workflows" / "weekly-predict.yml").read_text()
    gate = "steps.setup.outputs.claim_window_open == 'true'"
    assert body.count(gate) == 2, (
        "both 'Build predictions' and the data/predictions commit must be gated on the window; "
        "gating only the build would still commit nothing, but gating only the commit would let a "
        "claim be written to the working tree and picked up by a later run"
    )
    assert "claim_window_open != 'true'" in body, "the not-open notice step is missing"


def test_a_closed_window_is_a_notice_not_a_failure():
    """Every Tuesday before the window opens must leave the job GREEN. Failing instead would file a
    `pipeline-failure` issue weekly and spend the alarm's credibility on a working pipeline."""
    body = (ROOT / ".github" / "workflows" / "weekly-predict.yml").read_text()
    block = body.split("Claim window not open yet", 1)[1][:400]
    assert "::notice::" in block
    assert "exit 1" not in block and "::error::" not in block


# --- the guard is EXECUTED here, not grepped for --------------------------------------------------
#
# The first version of this section asserted three substrings in `build_predictions.py`. Review
# mutated the real guard to `if False:` — leaving the matched strings intact but unreachable — and
# all twelve tests still passed. That is the same "string presence is not behaviour" failure the
# failure-signature shell shipped with. These tests call the writers.

def _slate(week: int, year: int = 2026) -> dict:
    """The minimum a claim needs for the seam to identify its week — meta is what the guard reads."""
    return {"meta": {"week": week, "year": year, "schema_version": 2}, "predictions": []}


def test_the_seam_refuses_a_claim_before_its_window(tmp_path, monkeypatch):
    import scripts.build_predictions as bp
    monkeypatch.setattr(bp, "PREDICTIONS_DIR", tmp_path)
    monkeypatch.setattr(bp, "pipeline_today", lambda cal=None: date(2026, 8, 11))
    target = tmp_path / "2026_week_01.json"
    with pytest.raises(bp.ClaimWindowError):
        bp.write_predictions(_slate(1), target)
    assert not target.exists(), "a refused claim must leave NO file behind"


def test_the_seam_allows_the_claim_once_the_window_opens(tmp_path, monkeypatch):
    import scripts.build_predictions as bp
    monkeypatch.setattr(bp, "PREDICTIONS_DIR", tmp_path)
    monkeypatch.setattr(bp, "pipeline_today", lambda cal=None: date(2026, 8, 25))
    target = tmp_path / "2026_week_01.json"
    bp.write_predictions(_slate(1), target)
    assert target.exists(), "the 2026-08-25 run must still be able to write the real claim"


def test_the_cli_save_path_is_gated_too(tmp_path, monkeypatch):
    """**The bypass this exists for.** `cfb predict week N --save` is the documented canonical way a
    human writes a claim, and it reaches disk through `write_predictions` without going anywhere
    near `main()`. With the gate in `main()` only, review reproduced the 2026-08-11 incident through
    this path in one command — exit 0, an 11-game claim on disk, no warning."""
    import scripts.build_predictions as bp
    monkeypatch.setattr(bp, "PREDICTIONS_DIR", tmp_path)
    monkeypatch.setattr(bp, "pipeline_today", lambda cal=None: date(2026, 8, 11))

    from cli.cfb import _save_slate
    rc = _save_slate(_slate(1), week=1, year=2026)
    assert rc != 0, "the CLI save path must refuse a claim outside its window"
    assert not (tmp_path / "2026_week_01.json").exists()


def test_the_out_flag_and_backfills_are_unaffected(tmp_path, monkeypatch):
    """The gate is scoped to the claim tier and the configured season — a scratch path or a 2025
    rebuild must not be blocked, or every golden regeneration breaks."""
    import scripts.build_predictions as bp
    monkeypatch.setattr(bp, "PREDICTIONS_DIR", tmp_path / "claims")
    monkeypatch.setattr(bp, "pipeline_today", lambda cal=None: date(2026, 8, 11))
    (tmp_path / "claims").mkdir()

    scratch = tmp_path / "scratch.json"
    bp.write_predictions(_slate(1), scratch)
    assert scratch.exists(), "--out to a scratch path must not be gated"

    prior = tmp_path / "claims" / "2025_week_01.json"
    bp.write_predictions(_slate(1, year=2025), prior)
    assert prior.exists(), "a prior-season backfill must not be gated"


def test_the_script_exit_code_distinguishes_refusal_from_breakage():
    from scripts.build_predictions import EXIT_CLAIM_WINDOW_CLOSED
    assert EXIT_CLAIM_WINDOW_CLOSED == 5 and EXIT_CLAIM_WINDOW_CLOSED != 1
