"""`main.py project` acceptance (SPEC §6.5): renders projected win totals + week-over-week
drift from the committed projection files, offline; tolerant of schema evolution across weeks."""

from __future__ import annotations

import json

import cli.app
from cli.app import run_project


def _write(d, year, week, teams, schema_version=1):
    (d / f"{year}_week_{week:02d}.json").write_text(json.dumps({
        "meta": {"schema_version": schema_version, "year": year, "week": week,
                 "experimental": True},
        "teams": teams}))


# -- against the real committed data/projections/2026_week_01.json --------------
def test_project_default_renders_totals(capsys):
    assert run_project(["--quiet"]) == 0
    out = capsys.readouterr().out
    assert "Season projections" in out and "PROJ W" in out and "EXPERIMENTAL" in out


def test_project_json_is_experimental_and_listed(capsys):
    assert run_project(["--format", "json", "--quiet"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["experimental"] is True and isinstance(data["teams"], list) and data["teams"]
    assert all("projected_wins" in t for t in data["teams"])


def test_project_team_breakdown(capsys):
    assert run_project(["--team", "Georgia", "--quiet"]) == 0
    out = capsys.readouterr().out
    assert "GEORGIA" in out and "WIN%" in out


def test_project_unknown_team_errors(capsys):
    assert run_project(["--team", "Notateam XYZ", "--quiet"]) == 1
    assert "No projection for team" in capsys.readouterr().out


# -- drift + schema-version tolerance (controlled tmp files) -------------------
def test_project_drift_tolerates_older_schema(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli.app, "_projections_dir", lambda: tmp_path)
    # Week 1: an OLDER file (schema_version 0) missing later fields — reader must not choke.
    _write(tmp_path, 2026, 1, {"GEORGIA": {"projected_wins": 6.0, "rating": 1500}},
           schema_version=0)
    # Week 2: richer record.
    _write(tmp_path, 2026, 2, {"GEORGIA": {
        "projected_wins": 7.5, "rating": 1560, "rating_uncertainty": 0.6,
        "wins_so_far": 1, "losses_so_far": 0, "remaining": 10,
        "projected_losses": 3.5, "games": []}})
    assert run_project(["--quiet"]) == 0  # latest = week 2, drift vs week 1
    out = capsys.readouterr().out
    assert "GEORGIA" in out and "+1.50" in out          # Δwk = 7.5 − 6.0
    assert "Biggest risers" in out


def test_project_history_spans_weeks(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli.app, "_projections_dir", lambda: tmp_path)
    _write(tmp_path, 2026, 1, {"GEORGIA": {"projected_wins": 6.0, "rating": 1500}}, schema_version=0)
    _write(tmp_path, 2026, 2, {"GEORGIA": {"projected_wins": 7.5, "rating": 1560}})
    assert run_project(["--history", "--quiet"]) == 0
    out = capsys.readouterr().out
    assert "wk 1" in out and "wk 2" in out and "6.00" in out and "7.50" in out


def test_project_no_files_errors(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli.app, "_projections_dir", lambda: tmp_path)
    assert run_project(["--quiet"]) == 1
    assert "No projections" in capsys.readouterr().out


def test_project_team_tolerates_older_schema(tmp_path, monkeypatch, capsys):
    # --team against an OLDER-schema file missing rating_uncertainty/games/etc. must NOT crash
    # (regression for the reviewer-found KeyError; the --team path is now defensive too).
    monkeypatch.setattr(cli.app, "_projections_dir", lambda: tmp_path)
    _write(tmp_path, 2026, 4, {"GEORGIA": {"projected_wins": 8.0, "rating": 1600}},
           schema_version=0)
    assert run_project(["--team", "Georgia", "--week", "4", "--quiet"]) == 0
    out = capsys.readouterr().out
    assert "GEORGIA" in out and "8.00" in out  # renders from the sparse record


def test_project_surfaces_unscheduled_fbs_team(capsys):
    # Cal has no games in the committed snapshot → surfaced (not silently dropped).
    assert run_project(["--team", "Cal", "--quiet"]) == 0
    assert "No schedule data" in capsys.readouterr().out


def test_project_json_includes_all_fbs_and_coverage(capsys):
    assert run_project(["--format", "json", "--quiet"]) == 0
    data = json.loads(capsys.readouterr().out)
    teams = {t["team"] for t in data["teams"]}
    assert "CAL" in teams  # unscheduled FBS team is present, not dropped
    cal = next(t for t in data["teams"] if t["team"] == "CAL")
    assert cal["projected_wins"] is None
