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
