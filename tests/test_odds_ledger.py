"""The append-only Odds spend ledger (SPEC §10.5).

Replaces an `actions/cache` workaround that lost the balance on any cache eviction and left the
pre-spend guard blind in between. The ledger is committed, so it survives a fresh checkout — which
is the property the guard actually needed — and being a spend *series* rather than a single number
it answers the question that matters: the cadence spends ~8 credits/week against a 500/month tier,
so exhaustion was never the risk. A retry storm is, and only a series shows one.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from data.odds_budget import append_ledger, last_remaining, ledger_path, read_ledger

AT = datetime(2026, 9, 12, 17, 23, tzinfo=UTC)


def test_month_partitioned(tmp_path):
    assert ledger_path(AT, tmp_path).name == "odds_2026_09.json"
    assert ledger_path(datetime(2026, 12, 1, tzinfo=UTC), tmp_path).name == "odds_2026_12.json"


def test_an_entry_records_the_spend_with_its_context(tmp_path):
    assert append_ledger({"remaining": 481, "used": 19}, caller="fetch_lines", week=3,
                         run_id="123", base=tmp_path, when=AT) is True
    entries = read_ledger(ledger_path(AT, tmp_path))
    assert len(entries) == 1
    e = entries[0]
    assert (e["remaining"], e["used"], e["caller"], e["week"], e["run_id"]) == (
        481, 19, "fetch_lines", 3, "123")
    assert e["at"] == AT.isoformat()


def test_entries_append_and_are_never_rewritten(tmp_path):
    for remaining in (490, 489, 488):
        append_ledger({"remaining": remaining, "used": 500 - remaining},
                      caller="fetch_lines", base=tmp_path, when=AT)
    entries = read_ledger(ledger_path(AT, tmp_path))
    assert [e["remaining"] for e in entries] == [490, 489, 488]


def test_a_missing_quota_header_writes_nothing(tmp_path):
    """Recording a null balance would be fabricating a measurement (binding principle #4)."""
    assert append_ledger(None, caller="x", base=tmp_path, when=AT) is False
    assert append_ledger({"remaining": None}, caller="x", base=tmp_path, when=AT) is False
    assert not ledger_path(AT, tmp_path).exists()


def test_read_ledger_is_empty_before_any_spend(tmp_path):
    assert read_ledger(ledger_path(AT, tmp_path)) == []


def test_the_ledger_is_preferred_over_the_gitignored_cache(tmp_path, monkeypatch):
    """The cache is gitignored, so on a fresh checkout only the ledger is present."""
    import data.odds_budget as ob
    monkeypatch.setattr(ob, "_LEDGER_DIR", tmp_path)
    monkeypatch.setattr(ob, "ledger_path",
                        lambda when=None, base=None: tmp_path / "odds_2026_09.json")
    (tmp_path / "odds_2026_09.json").write_text(json.dumps(
        {"entries": [{"at": AT.isoformat(), "remaining": 400, "used": 100}]}) + "\n")

    cache = tmp_path / "odds_quota.json"
    cache.write_text(json.dumps({"remaining": 999}) + "\n")

    assert last_remaining(cache) == (400, "ledger")


def test_falls_back_to_the_cache_then_the_snapshot(tmp_path, monkeypatch):
    import data.odds_budget as ob
    monkeypatch.setattr(ob, "ledger_path",
                        lambda when=None, base=None: tmp_path / "absent.json")

    cache = tmp_path / "odds_quota.json"
    cache.write_text(json.dumps({"remaining": 321}) + "\n")
    assert last_remaining(cache) == (321, "persisted")

    # No ledger and no cache → the snapshot manifest's build-time figure, or unknown.
    remaining, source = last_remaining(tmp_path / "nope.json")
    assert source in ("snapshot", "unknown")


def test_the_ledger_directory_is_hook_guarded():
    """It is an append-only artifact, so both hooks must cover it (D23/D25.4 shared tuple)."""
    import importlib.util
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    spec = importlib.util.spec_from_file_location(
        "protected_paths", root / ".claude" / "hooks" / "protected_paths.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert "data/quota/" in mod.PROTECTED


def test_the_capture_workflow_commits_the_ledger_instead_of_caching_it():
    from pathlib import Path
    wf = (Path(__file__).resolve().parent.parent
          / ".github" / "workflows" / "daily-capture.yml").read_text()
    assert "data/quota" in wf, "the capture job must stage the ledger"
    # Match actual USAGE, not the bare string: a comment explaining why the cache was dropped
    # would otherwise fail this — the prose-vs-code false positive D25 documents.
    assert "uses: actions/cache" not in wf, (
        "the cache workaround is superseded by the committed ledger — an evicted cache left the "
        "pre-spend guard blind, which is the failure the ledger exists to remove."
    )


@pytest.mark.parametrize("workflow", ["daily-capture.yml", "weekly-predict.yml"])
def test_no_workflow_still_caches_the_quota(workflow):
    from pathlib import Path
    text = (Path(__file__).resolve().parent.parent / ".github" / "workflows" / workflow).read_text()
    assert "odds-quota-" not in text


# --- the ledger is replaced in one step, never truncated in place --------------------------------
#
# This ledger is COMMITTED and append-only (SPEC §10.5): `cfb-commit` stages `data/quota` on the very
# next capture, so a run killed between truncate and write would put a torn file into the record
# itself. Found by an adversarial review of the D44 cadence PR, alongside the same defect in the
# line store.

def test_a_killed_ledger_write_leaves_the_previous_ledger_intact(tmp_path, monkeypatch):
    import os

    append_ledger({"remaining": 480, "used": 20}, caller="fetch_lines", week=4,
                  base=tmp_path, when=AT)
    path = ledger_path(AT, tmp_path)
    before = path.read_bytes()

    def killed(*args, **kwargs):
        raise OSError("runner died between the write and the rename")

    monkeypatch.setattr(os, "replace", killed)
    with pytest.raises(OSError):
        append_ledger({"remaining": 479, "used": 21}, caller="fetch_lines", week=4,
                      base=tmp_path, when=AT)
    assert path.read_bytes() == before, "a torn write must never reach the committed record"
    assert [p.name for p in path.parent.iterdir()] == [path.name], "no temp file left behind"
    assert len(read_ledger(path)) == 1


def test_identical_ledger_input_still_produces_identical_bytes(tmp_path):
    """The append-only hooks and the record compare bytes, so the atomic write must not reformat."""
    append_ledger({"remaining": 480, "used": 20}, caller="fetch_lines", week=4,
                  base=tmp_path, when=AT)
    path = ledger_path(AT, tmp_path)
    first = path.read_bytes()
    assert append_ledger(None, caller="fetch_lines", week=4, base=tmp_path, when=AT) is False
    assert path.read_bytes() == first


def test_an_observation_survives_a_ledger_write_that_fails(tmp_path, monkeypatch):
    """Order of writes in `fetch_lines.main`: the observation is recorded BEFORE the accounting.

    The credit is spent the moment the response arrives, and the observation is the only part that
    cannot be reconstructed — the market moves on. With the accounting first, a ledger failure threw
    away an observation already paid for. The ledger failure must still fail the run loudly, so the
    spend is never silently unrecorded (review of the D44 PR, finding 1).

    **D46 changed HOW it fails, not whether.** This asserted `pytest.raises(OSError)`, which is what
    an uncaught exception did: exit 1, and `daily-capture.yml` then skipped the commit step (gated on
    `rc == '0'`), so the observation on disk never reached the repository and the runner was thrown
    away with it — the reason D44's finding 1 is recorded as PARTIAL. The exception is now caught and
    turned into exit 5, which the workflow commits on *before* failing the job. The on-disk
    assertions below are unchanged; only the failure channel moved.
    """
    import scripts.fetch_lines as fl
    from data.snapshot.lines import lines_path, load_lines

    monkeypatch.setattr(fl, "load_snapshot", lambda w, y: {"data": {"betting_lines": {"G@H": {}}}})
    monkeypatch.setattr(fl, "last_remaining", lambda: (400, "ledger"))

    class _Client:
        last_quota = {"remaining": 399, "used": 101}

        def get_ncaaf_spreads(self):
            return [{"home_team": "H", "away_team": "G", "commence_time": "2026-09-26T16:00:00Z",
                     "bookmakers": []}]

    monkeypatch.setattr("data.clients.odds.get_odds_client", lambda: _Client())
    monkeypatch.setattr(fl, "record_observation",
                        lambda week, games, year=2026: (
                            __import__("data.snapshot.lines", fromlist=["x"]).record_observation(
                                week, {"G@H": {"home_team": "H", "away_team": "G",
                                               "kickoff": "2026-09-26T16:00:00Z",
                                               "observations": [{"fetched_at": "2026-09-26T10:00:00Z",
                                                                 "lines": [], "consensus_spread": -3.0}]}},
                                year=year, base=tmp_path)))

    def ledger_dies(*a, **k):
        raise OSError("ledger write failed")

    monkeypatch.setattr(fl, "append_ledger", ledger_dies)
    monkeypatch.setattr(fl, "record_quota", lambda *a, **k: None)
    rc = fl.main(["--week", "4"])
    assert rc == fl.EXIT_ACCOUNTING_FAILED, "an unrecorded spend must still end the run red"
    assert rc != fl.EXIT_OK, "exit 5 is not a designed state; the job fails after committing"
    assert load_lines(4, base=tmp_path)["G@H"]["observations"], (
        "the observation was paid for and must be on disk before the accounting runs"
    )
    assert lines_path(4, base=tmp_path).exists()


def test_either_accounting_writer_failing_gives_exit_five(tmp_path, monkeypatch, capsys):
    """`record_quota` is inside the same `try:` as `append_ledger`.

    Guarding only the ledger would leave the quota cache — the first of the two calls — able to
    raise past it, restoring exactly the behaviour D46 removed: exit 1, no commit, observation lost
    on the runner. Mutation-checked by narrowing the `try:` to `append_ledger` alone, which fails
    this test and no other.
    """
    import scripts.fetch_lines as fl
    from data.snapshot.lines import load_lines

    monkeypatch.setattr(fl, "load_snapshot", lambda w, y: {"data": {"betting_lines": {"G@H": {}}}})
    monkeypatch.setattr(fl, "last_remaining", lambda: (400, "ledger"))

    class _Client:
        last_quota = {"remaining": 399, "used": 101}

        def get_ncaaf_spreads(self):
            return [{"home_team": "H", "away_team": "G", "commence_time": "2026-09-26T16:00:00Z",
                     "bookmakers": []}]

    monkeypatch.setattr("data.clients.odds.get_odds_client", lambda: _Client())
    monkeypatch.setattr(fl, "record_observation",
                        lambda week, games, year=2026: (
                            __import__("data.snapshot.lines", fromlist=["x"]).record_observation(
                                week, {"G@H": {"home_team": "H", "away_team": "G",
                                               "kickoff": "2026-09-26T16:00:00Z",
                                               "observations": [{"fetched_at": "2026-09-26T10:00:00Z",
                                                                 "lines": [], "consensus_spread": -3.0}]}},
                                year=year, base=tmp_path)))

    reached_ledger = []
    monkeypatch.setattr(fl, "record_quota", lambda *a, **k: (_ for _ in ()).throw(OSError("quota cache full")))
    monkeypatch.setattr(fl, "append_ledger", lambda *a, **k: reached_ledger.append(True))

    rc = fl.main(["--week", "4"])
    assert rc == fl.EXIT_ACCOUNTING_FAILED
    assert reached_ledger == [], "record_quota raised, so append_ledger is skipped by the same try"
    assert load_lines(4, base=tmp_path)["G@H"]["observations"], "the observation is still on disk"
    out = capsys.readouterr().out
    assert "::error::" in out and "NOT recorded" in out, (
        "the unrecorded spend must be visible in the log, not only in the exit code"
    )


def test_the_observation_is_written_before_any_accounting(monkeypatch):
    """Order, not just survival: BOTH `record_quota` and `append_ledger` must run after the
    observation is on disk. Asserting only that a ledger failure spares the observation passes even
    if the quota cache is written first (mutation-checked)."""
    import scripts.fetch_lines as fl

    calls: list[str] = []
    monkeypatch.setattr(fl, "load_snapshot", lambda w, y: {"data": {"betting_lines": {"G@H": {}}}})
    monkeypatch.setattr(fl, "last_remaining", lambda: (400, "ledger"))

    class _Client:
        last_quota = {"remaining": 399, "used": 101}

        def get_ncaaf_spreads(self):
            return []

    monkeypatch.setattr("data.clients.odds.get_odds_client", lambda: _Client())
    monkeypatch.setattr(fl, "record_observation", lambda *a, **k: calls.append("observation") or 0)
    monkeypatch.setattr(fl, "record_quota", lambda *a, **k: calls.append("quota"))
    monkeypatch.setattr(fl, "append_ledger", lambda *a, **k: calls.append("ledger"))
    assert fl.main(["--week", "4"]) == fl.EXIT_OK
    assert calls[0] == "observation", f"the unrecoverable write must go first, got {calls}"
    assert set(calls[1:]) == {"quota", "ledger"}
