"""`cfb` CLI v2 acceptance (Phase 4.5, SPEC §9). Offline — over a PINNED week-1 bundle.

Pins the §9 acceptance gates: omitted-week == explicit-week (bit-identical, the silent-week-1 fix),
`--offline` rerun identical to the original run, the deprecation shim orphans the A2 single-game
path, exit codes are meaningful, and `season.json` stays in sync with the corroborated calendar.

**Why nothing here reads `data/snapshots/2026_week_01/`.** That bundle is LIVE: the Phase-5 pipeline
rebuilds it on every week-1 run, and books de-list a game once it has been played. On 2026-09-01 the
first post-kickoff rebuild took it from 11 lines to 9, and every test below that assumed a complete
slate went red on `main` (run 33537284634) — for a calendar reason, not a code reason. The CLI was
correct throughout: SPEC §9 requirement 5 makes exit 2 "degraded data", and a mid-week slate is
degraded. So each test is pinned to a bundle on which its own premise is permanently true, and the
mid-week state that broke them is now itself pinned by
`test_a_mid_week_slate_degrades_on_games_the_books_de_listed`.
"""
from __future__ import annotations

import contextlib
import copy
import json
from datetime import date, datetime
from pathlib import Path

import pytest

import cli.cfb as cfb
from data.snapshot.store import load_frozen_vehicle
from scripts.slate_fingerprint import engine_reads

ROOT = Path(__file__).resolve().parent.parent


class _FakeDatetime:
    """`datetime.now()` pinned to a week-1 date (2026-08-29..09-07) for deterministic inference."""
    @staticmethod
    def now() -> datetime:
        return datetime(2026, 9, 1)


# ── the pinned slate ─────────────────────────────────────────────────────────────────────────────

def _all_lines_bundle() -> dict:
    """A week-1 bundle in its PRE-KICKOFF state: every enumerated game still has a line.

    This is the tag-time vehicle under `data/archive/frozen/`, which is append-only — so unlike the
    live bundle its completeness cannot rot out from under a test. The premise is asserted rather
    than assumed: if a future retag ever re-points `FROZEN_VEHICLE` at a post-kickoff snapshot, the
    tests that need a complete slate must fail saying so, not fail as a bare `assert 2 == 0`.
    """
    bundle = copy.deepcopy(load_frozen_vehicle())
    missing = sorted(k for k, v in bundle["data"]["betting_lines"].items()
                     if v.get("vegas_spread") is None)
    assert not missing, (
        f"fixture premise violated — the pinned vehicle has no line for {missing}. The tests using "
        "this bundle assert properties that require a COMPLETE slate; re-point them at a bundle "
        "that has one rather than relaxing the assertion."
    )
    return bundle


@pytest.fixture
def pinned_slate(monkeypatch):
    """Point BOTH of the CLI's snapshot reads at an in-memory bundle.

    There are two and they are independent. `cli.cfb._load_slate` ENUMERATES the slate via
    `data.snapshot.store.load_snapshot`; the frozen engine PRICES each game via
    `data.data_manager.load_snapshot`, which `data/data_manager.py` binds at import time so the
    store-level patch does not reach it. `analytics/predictions.py` says as much in its docstring.
    Pinning one and not the other produces the split read that
    `scripts.slate_fingerprint.engine_reads` exists to prevent — enumeration from the fixture,
    pricing from whatever the pipeline last committed — which is worse than either because it looks
    correct. `engine_reads` is reused rather than reimplemented so there stays exactly one
    definition of how the engine gets pinned.
    """
    import data.snapshot.store as store
    stack = contextlib.ExitStack()

    def pin(bundle: dict) -> dict:
        monkeypatch.setattr(store, "load_snapshot",
                            lambda week, year=2026, base=None: bundle)  # noqa: ARG005
        stack.enter_context(engine_reads(bundle))
        return bundle

    yield pin
    stack.close()


@pytest.fixture
def complete_slate(pinned_slate):
    """The pre-kickoff week-1 slate — every game bettable. The premise of every `== EXIT_OK` below."""
    return pinned_slate(_all_lines_bundle())


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

def test_omitted_week_equals_explicit_week(capsys, monkeypatch, complete_slate):
    monkeypatch.setattr(cfb, "datetime", _FakeDatetime)
    assert cfb.main(["predict", "week", "--format", "json"]) == 0     # inferred (week 1)
    inferred = capsys.readouterr().out
    assert cfb.main(["predict", "week", "1", "--format", "json"]) == 0  # explicit
    explicit = capsys.readouterr().out
    assert inferred == explicit and json.loads(inferred)["meta"]["week"] == 1


def test_out_of_season_inference_exits_degraded(capsys, monkeypatch):
    monkeypatch.setattr(cfb, "datetime", type("D", (), {"now": staticmethod(lambda: datetime(2026, 7, 24))}))
    assert cfb.main(["predict", "week"]) == 2          # exit 2, never a silent guess


def test_week_echoed_to_stderr_not_stdout(capsys, monkeypatch, complete_slate):
    monkeypatch.setattr(cfb, "datetime", _FakeDatetime)
    cfb.main(["predict", "week", "--format", "json"])
    cap = capsys.readouterr()
    assert "inferred from" in cap.err and "inferred from" not in cap.out   # json stdout stays clean


# ── §9.3 offline rerun identical ─────────────────────────────────────────────────────────────────

def test_offline_rerun_identical_to_predict_week(capsys, complete_slate):
    assert cfb.main(["predict", "week", "1", "--format", "json"]) == 0
    original = capsys.readouterr().out
    assert cfb.main(["predict", "rerun", "--week", "1", "--format", "json"]) == 0
    rerun = capsys.readouterr().out
    assert original == rerun


# ── predict game: ratified slate, never the A2 path ──────────────────────────────────────────────

def test_predict_game_uses_ratified_slate_not_a2():
    # Static guarantee: the CLI never references the A2 single-game engine.
    assert "run_single_prediction" not in (ROOT / "cli" / "cfb.py").read_text()


def test_predict_game_matches_the_slate_row(capsys, complete_slate):
    assert cfb.main(["predict", "game", "CLEMSON @ LSU", "--week", "1", "--format", "json"]) == 0
    rec = json.loads(capsys.readouterr().out)["predictions"]
    assert len(rec) == 1 and rec[0]["home_team"] == "LSU" and rec[0]["away_team"] == "CLEMSON"
    assert 0.0 <= rec[0]["confidence"] <= 1.0        # schema-v2 confidence (ratified), not A2's 0.15–0.85


def test_predict_game_not_in_slate_suggests_hypothetical(capsys, complete_slate):
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


def test_slate_returns_ok_when_all_games_have_lines(capsys, complete_slate):
    assert cfb.main(["slate", "1", "--format", "json"]) == 0


def test_a_mid_week_slate_degrades_on_games_the_books_de_listed(capsys, pinned_slate):
    """The state that reddened `main` on 2026-09-01 (run 33537284634), pinned as correct behaviour.

    Books de-list a game once it has been played, so a bundle rebuilt mid-week carries games with no
    prediction-time line. `analytics.predictions.build_predictions` records those under
    `meta.coverage.skipped` rather than writing half-null records, and `cli.cfb._slate_degraded` maps
    a non-empty `skipped` to `EXIT_DEGRADED`. SPEC §9 requirement 5 defines exit 2 as "degraded
    data", so this is the contract being met over a mid-week slate — a state no test covered until
    the calendar produced it.

    The de-listed games are chosen positionally, not by name: nothing here should rot when the 2027
    slate differs.
    """
    bundle = _all_lines_bundle()
    lines = bundle["data"]["betting_lines"]
    de_listed = sorted(lines)[:2]
    by_key = {f"{g.get('away_team')}@{g.get('home_team')}": g for g in bundle["data"]["games"]}

    for key in de_listed:
        lines[key]["vegas_spread"] = None      # the book dropped the game...
        lines[key]["observation"] = None
        game = by_key[key]                     # ...because it was played
        game["home_points"], game["away_points"], game["completed"] = 21, 17, True
    pinned_slate(bundle)

    # `slate` reports degraded, and drops EXACTLY the played games — no more, no fewer.
    assert cfb.main(["slate", "1", "--format", "json"]) == 2
    meta = json.loads(capsys.readouterr().out)["meta"]
    assert meta["coverage"]["skipped"] == de_listed
    assert meta["coverage"]["written"] == len(lines) - len(de_listed)

    # ...and the whole-slate predict names them in its degraded message rather than failing silently.
    assert cfb.main(["predict", "week", "1", "--format", "json"]) == 2
    err = capsys.readouterr().err
    assert "degraded" in err and all(key in err for key in de_listed)


def test_predict_game_exit_code_ignores_unrelated_slate_drops(capsys, monkeypatch, complete_slate):
    """A single-game query's exit code reflects THAT game, not the whole week's dropped games."""
    real = cfb._load_slate

    def _with_a_drop(week, year):
        env = real(week, year)
        env["meta"]["coverage"]["skipped"] = ["some-other-game"]   # unrelated drop
        return env
    monkeypatch.setattr(cfb, "_load_slate", _with_a_drop)
    assert cfb.main(["predict", "game", "CLEMSON @ LSU", "--week", "1", "--format", "json"]) == 0


def test_predict_week_save_refuses_overwrite_d22(tmp_path, monkeypatch, capsys, complete_slate):
    """`--save` writes the claim once; re-saving refuses (predictions are byte-immutable, D22).

    Pinned to a date inside week 1's claim window: this test is about **overwrite** semantics, and
    since D38 a claim also cannot be written before its week is due. Without the pin it would fail
    for a scheduling reason that has nothing to do with what it asserts — and would start passing
    or failing depending on the day it runs.

    Pinned to a complete slate for the same reason in the other axis: the first `--save` asserts
    `EXIT_OK`, which a mid-week slate turns into `EXIT_DEGRADED` for a reason that has nothing to do
    with overwrite semantics either.
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
