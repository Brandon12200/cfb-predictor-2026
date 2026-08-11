"""`cfb` CLI v2 acceptance (Phase 4.5, SPEC §9). Offline — over the committed 2026 wk1 snapshot.

Pins the §9 acceptance gates: omitted-week == explicit-week (bit-identical, the silent-week-1 fix),
`--offline` rerun identical to the original run, the deprecation shim orphans the A2 single-game
path, exit codes are meaningful, and `season.json` stays in sync with the corroborated calendar.
"""
from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path

import pytest

import cli.cfb as cfb

ROOT = Path(__file__).resolve().parent.parent


class _FakeDatetime:
    """`datetime.now()` pinned to a week-1 date (2026-08-29..09-07) for deterministic inference."""
    @staticmethod
    def now() -> datetime:
        return datetime(2026, 9, 1)


# ── config home (season.json) ────────────────────────────────────────────────────────────────────

def test_season_json_weeks_match_corroborated_calendar():
    """D8/D24: season.json's folded calendar must not drift from the CFBD-corroborated source."""
    season = json.loads((ROOT / "season.json").read_text())
    cal = json.loads((ROOT / "data" / "season_calendar_2026.json").read_text())
    assert season["weeks"] == cal["weeks"]
    assert season["season"] == cal["season"]


def test_cli_defaults_present():
    from utils.season_calendar import cli_defaults
    d = cli_defaults()
    assert d.get("year") == 2026 and d.get("format") == "table" and d.get("save") is False


# ── §9.1 week inference: omitted == explicit ─────────────────────────────────────────────────────

def test_omitted_week_equals_explicit_week(capsys, monkeypatch):
    monkeypatch.setattr(cfb, "datetime", _FakeDatetime)
    assert cfb.main(["predict", "week", "--format", "json"]) == 0     # inferred (week 1)
    inferred = capsys.readouterr().out
    assert cfb.main(["predict", "week", "1", "--format", "json"]) == 0  # explicit
    explicit = capsys.readouterr().out
    assert inferred == explicit and json.loads(inferred)["meta"]["week"] == 1


def test_out_of_season_inference_exits_degraded(capsys, monkeypatch):
    monkeypatch.setattr(cfb, "datetime", type("D", (), {"now": staticmethod(lambda: datetime(2026, 7, 24))}))
    assert cfb.main(["predict", "week"]) == 2          # exit 2, never a silent guess


def test_week_echoed_to_stderr_not_stdout(capsys, monkeypatch):
    monkeypatch.setattr(cfb, "datetime", _FakeDatetime)
    cfb.main(["predict", "week", "--format", "json"])
    cap = capsys.readouterr()
    assert "inferred from" in cap.err and "inferred from" not in cap.out   # json stdout stays clean


# ── §9.3 offline rerun identical ─────────────────────────────────────────────────────────────────

def test_offline_rerun_identical_to_predict_week(capsys):
    assert cfb.main(["predict", "week", "1", "--format", "json"]) == 0
    original = capsys.readouterr().out
    assert cfb.main(["predict", "rerun", "--week", "1", "--format", "json"]) == 0
    rerun = capsys.readouterr().out
    assert original == rerun


# ── predict game: ratified slate, never the A2 path ──────────────────────────────────────────────

def test_predict_game_uses_ratified_slate_not_a2():
    # Static guarantee: the CLI never references the A2 single-game engine.
    assert "run_single_prediction" not in (ROOT / "cli" / "cfb.py").read_text()


def test_predict_game_matches_the_slate_row(capsys):
    assert cfb.main(["predict", "game", "CLEMSON @ LSU", "--week", "1", "--format", "json"]) == 0
    rec = json.loads(capsys.readouterr().out)["predictions"]
    assert len(rec) == 1 and rec[0]["home_team"] == "LSU" and rec[0]["away_team"] == "CLEMSON"
    assert 0.0 <= rec[0]["confidence"] <= 1.0        # schema-v2 confidence (ratified), not A2's 0.15–0.85


def test_predict_game_not_in_slate_suggests_hypothetical(capsys):
    assert cfb.main(["predict", "game", "OHIO STATE @ TEXAS", "--week", "1"]) == 1
    assert "cfb hypothetical" in capsys.readouterr().err


def test_predict_game_unparseable_errors(capsys):
    assert cfb.main(["predict", "game", "just one team", "--week", "1"]) == 1


# ── §9.5 help contract + exit codes ──────────────────────────────────────────────────────────────

def test_help_renders_the_command_contract(capsys):
    with pytest.raises(SystemExit) as exc:
        cfb.main(["--help"])
    assert exc.value.code == 0
    out = capsys.readouterr().out
    for cmd in ("predict", "grade", "report", "project", "hypothetical", "slate", "data", "status"):
        assert cmd in out


def test_slate_returns_ok_when_all_games_have_lines(capsys):
    assert cfb.main(["slate", "1", "--format", "json"]) == 0


def test_predict_game_exit_code_ignores_unrelated_slate_drops(capsys, monkeypatch):
    """A single-game query's exit code reflects THAT game, not the whole week's dropped games."""
    real = cfb._load_slate

    def _with_a_drop(week, year):
        env = real(week, year)
        env["meta"]["coverage"]["skipped"] = ["some-other-game"]   # unrelated drop
        return env
    monkeypatch.setattr(cfb, "_load_slate", _with_a_drop)
    assert cfb.main(["predict", "game", "CLEMSON @ LSU", "--week", "1", "--format", "json"]) == 0


def test_predict_week_save_refuses_overwrite_d22(tmp_path, monkeypatch, capsys):
    """`--save` writes the claim once; re-saving refuses (predictions are byte-immutable, D22).

    Pinned to a date inside week 1's claim window: this test is about **overwrite** semantics, and
    since D38 a claim also cannot be written before its week is due. Without the pin it would fail
    for a scheduling reason that has nothing to do with what it asserts — and would start passing
    or failing depending on the day it runs.
    """
    import scripts.build_predictions as bp
    monkeypatch.setattr(bp, "PREDICTIONS_DIR", tmp_path)
    monkeypatch.setattr(bp, "pipeline_today", lambda cal=None: date(2026, 8, 25))
    assert cfb.main(["predict", "week", "1", "--save", "--format", "json"]) == 0
    assert (tmp_path / "2026_week_01.json").exists()
    capsys.readouterr()
    assert cfb.main(["predict", "week", "1", "--save", "--format", "json"]) == 1  # refuses overwrite
    assert "byte-immutable" in capsys.readouterr().err


# ── main.py deprecation shim orphans run_single_prediction ───────────────────────────────────────

def test_shim_delegates_and_does_not_call_a2(capsys, monkeypatch):
    import main as main_module
    calls = {}
    monkeypatch.setattr(cfb, "main", lambda argv=None: calls.setdefault("argv", argv) is None or 0)
    monkeypatch.setattr("sys.argv", ["main.py", "--home", "lsu", "--away", "clemson", "--week", "1"])
    rc = main_module.main()
    assert rc == 0 and calls["argv"][:2] == ["predict", "game"]
