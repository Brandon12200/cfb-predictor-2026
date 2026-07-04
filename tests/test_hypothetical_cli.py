"""`main.py hypothetical` acceptance (SPEC §6.4): prices any two FBS teams from the
committed snapshot, offline, with model spread + confidence + caveats (no Vegas line)."""

from __future__ import annotations

import json

from cli.app import run_hypothetical


def test_hypothetical_json_prices_any_two_teams(capsys):
    rc = run_hypothetical(["--home", "Ohio State", "--away", "Texas",
                           "--format", "json", "--quiet"])
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert data["home_team"] == "OHIO STATE" and data["away_team"] == "TEXAS"
    assert "model_spread" in data and data["snapshot_id"]
    assert data["confidence"] in ("LOW", "MEDIUM", "HIGH")
    # No Vegas line involved anywhere in the output.
    assert "vegas_spread" not in data


def test_hypothetical_neutral_site_drops_home_field(capsys):
    rc = run_hypothetical(["--home", "Georgia", "--away", "USC",
                           "--neutral-site", "--format", "json", "--quiet"])
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert data["neutral_site"] is True
    assert data["breakdown"]["hfa_points"] == 0.0


def test_hypothetical_rejects_same_team(capsys):
    assert run_hypothetical(["--home", "Texas", "--away", "Texas", "--quiet"]) == 1
    assert "cannot be the same" in capsys.readouterr().out


def test_hypothetical_reports_unresolvable_team(capsys):
    assert run_hypothetical(["--home", "Notateam XYZ", "--away", "Texas", "--quiet"]) == 1
    assert "Could not resolve" in capsys.readouterr().out


def test_hypothetical_table_shows_spread_and_caveats(capsys):
    rc = run_hypothetical(["--home", "Ohio State", "--away", "Texas", "--quiet"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Model spread" in out and "OHIO STATE" in out
    assert "Confidence" in out
