"""Unit tests for the canonical season team registry (SPEC §5.5). Offline."""

import json
from pathlib import Path

import pytest

from data import team_registry as R
from data.team_registry import (
    RegistryError,
    TeamRegistry,
    canonical_name,
    conference_key,
    refresh_registry,
)

ARTIFACT = Path(__file__).parent.parent / "data" / "registry" / "fbs_teams_2026.json"


@pytest.fixture
def real_registry() -> TeamRegistry:
    return TeamRegistry()


# -- name/conference mapping helpers ------------------------------------------
def test_canonical_name_override_and_default():
    assert canonical_name("Ole Miss") == "MISSISSIPPI"  # explicit divergence
    assert canonical_name("Alabama") == "ALABAMA"  # default school.upper()
    assert canonical_name("Delaware") == "DELAWARE"  # new member -> default


def test_conference_key_mapping():
    assert conference_key("Big Ten") == "BIG TEN"
    assert conference_key("Big 12") == "BIG 12"
    assert conference_key("FBS Independents") == "INDEPENDENT"
    assert conference_key("SEC") == "SEC"
    assert conference_key(None) is None


# -- conferences.py surface parity --------------------------------------------
def test_conference_map_keys_and_counts(real_registry):
    cm = real_registry.get_conference_map()
    assert set(cm) == {"SEC", "BIG TEN", "BIG 12", "ACC", "INDEPENDENT"}
    assert len(cm["SEC"]) == 16
    assert len(cm["BIG TEN"]) == 18
    assert len(cm["BIG 12"]) == 16
    assert len(cm["ACC"]) == 17
    assert cm["INDEPENDENT"] == ["NOTRE DAME"]  # UConn tracked-out by design


def test_conference_map_members_sorted_and_canonical(real_registry):
    cm = real_registry.get_conference_map()
    assert cm["ACC"] == sorted(cm["ACC"])
    assert "CAL" in cm["ACC"] and "CALIFORNIA" not in cm["ACC"]  # normalizer canonical wins


def test_get_team_conference_tracked_only(real_registry):
    assert real_registry.get_team_conference("GEORGIA") == "SEC"
    assert real_registry.get_team_conference("NOTRE DAME") == "INDEPENDENT"
    assert real_registry.get_team_conference("") is None
    # A real FBS team outside the tracked slate resolves to None (parity with the
    # retired conferences.py, which only knew P4 + tracked independents).
    assert real_registry.get_team_conference("AIR FORCE") is None


def test_p4_conference_names(real_registry):
    assert real_registry.get_p4_conference_names() == {
        "SEC", "BIG TEN", "BIG 12", "ACC", "PAC-12", "PACIFIC-12"
    }


def test_all_tracked_teams_is_union(real_registry):
    cm = real_registry.get_conference_map()
    expected = {t for members in cm.values() for t in members}
    assert real_registry.get_all_tracked_teams() == expected


def test_normalizer_data_accessors(real_registry):
    assert len(real_registry.get_fbs_canonical_names()) == 138
    assert len(real_registry.get_fcs_names()) == 127
    assert real_registry.get_aliases("MISSISSIPPI")  # Ole Miss has alternateNames
    # FBS and FCS name spaces must not overlap (no team is both).
    assert not real_registry.get_fbs_canonical_names() & real_registry.get_fcs_names()


# -- membership validation (SPEC §5.5.2, hard-fail) ---------------------------
def test_validate_membership_counts_passes_on_real_artifact(real_registry):
    real_registry.validate_membership_counts()  # must not raise


def _artifact_with_counts(tmp_path: Path, fbs_rows: list[dict]) -> TeamRegistry:
    teams = tmp_path / "teams.json"
    teams.write_text(json.dumps({
        "_provenance": {"source": "test"}, "fbs": fbs_rows, "fcs": [],
    }))
    return TeamRegistry(teams_artifact=teams, calendar_artifact=tmp_path / "cal.json")


def test_validate_membership_counts_hard_fails_on_wrong_count(tmp_path):
    # One SEC team instead of 16 -> hard failure with a clear message.
    reg = _artifact_with_counts(tmp_path, [
        {"school": "Georgia", "conference": "SEC", "alternateNames": []},
    ])
    with pytest.raises(RegistryError, match="validation FAILED"):
        reg.validate_membership_counts()


def test_validate_membership_counts_hard_fails_on_no_independent(tmp_path):
    reg = _artifact_with_counts(tmp_path, [
        {"school": "Georgia", "conference": "SEC", "alternateNames": []},
    ])
    with pytest.raises(RegistryError, match="INDEPENDENT"):
        reg.validate_membership_counts()


def test_empty_fbs_artifact_raises(tmp_path):
    teams = tmp_path / "teams.json"
    teams.write_text(json.dumps({"_provenance": {}, "fbs": [], "fcs": []}))
    with pytest.raises(RegistryError, match="no FBS teams"):
        TeamRegistry(teams_artifact=teams)


# -- calendar corroboration (D1, loud warning not hard-fail) ------------------
def test_corroborate_calendar_reports_real_offset(real_registry):
    # The hand-built Sunday-anchored calendar differs from CFBD by design; the
    # corroboration must surface those as warnings (not silently pass, not raise).
    warnings = real_registry.corroborate_calendar()
    assert warnings, "expected calendar corroboration to surface the known offset"
    assert any("week 0" in w for w in warnings)  # week 0 absent from CFBD


def test_corroborate_calendar_missing_artifact_is_quiet(tmp_path):
    teams = tmp_path / "teams.json"
    teams.write_text(json.dumps({
        "_provenance": {}, "fbs": [{"school": "Georgia", "conference": "SEC",
                                    "alternateNames": []}], "fcs": [],
    }))
    reg = TeamRegistry(teams_artifact=teams, calendar_artifact=tmp_path / "missing.json")
    assert reg.corroborate_calendar() == []


# -- diff-aware refresh (offline, fake client) --------------------------------
class _FakeClient:
    def __init__(self, teams, calendar):
        self._teams, self._calendar = teams, calendar

    def get_teams(self, year):
        return self._teams

    def get_calendar(self, year):
        return self._calendar


def test_refresh_writes_artifacts_with_provenance(tmp_path):
    teams = [
        {"school": "Georgia", "conference": "SEC", "classification": "fbs",
         "alternateNames": ["UGA"], "id": 1},
        {"school": "Football Bruins", "conference": "UAC", "classification": "fcs",
         "alternateNames": [], "id": 2},
    ]
    calendar = [{"season": 2026, "week": 1, "seasonType": "regular",
                 "startDate": "2026-08-29T07:00:00.000Z", "endDate": "2026-09-08"}]
    client = _FakeClient(teams, calendar)
    ta, ca = tmp_path / "t.json", tmp_path / "c.json"

    summary = refresh_registry(client, year=2026, confirm=False,
                               teams_artifact=ta, calendar_artifact=ca)

    assert summary == {"written": True, "counts": {"fbs": 1, "fcs": 1},
                       "calendar_weeks": 1}
    written = json.loads(ta.read_text())
    assert written["_provenance"]["source"] == "cfbd"
    assert written["_provenance"]["counts"] == {"fbs": 1, "fcs": 1}
    assert "fetched_at" in written["_provenance"]
    assert len(written["fbs"]) == 1 and len(written["fcs"]) == 1
    assert json.loads(ca.read_text())["_provenance"]["endpoint"] == "/calendar"


def test_refresh_diff_requires_confirmation(tmp_path, monkeypatch, capsys):
    ta, ca = tmp_path / "t.json", tmp_path / "c.json"
    base = [{"school": "Georgia", "conference": "SEC", "classification": "fbs",
             "alternateNames": [], "id": 1}]
    refresh_registry(_FakeClient(base, []), confirm=False, teams_artifact=ta,
                     calendar_artifact=ca)
    # Now a "hiccup" fetch drops Georgia; declining the prompt must NOT overwrite.
    monkeypatch.setattr("builtins.input", lambda *a: "no")
    result = refresh_registry(_FakeClient([], []), confirm=True, teams_artifact=ta,
                              calendar_artifact=ca)
    assert result["written"] is False
    assert len(json.loads(ta.read_text())["fbs"]) == 1  # unchanged
    assert "SEC" in capsys.readouterr().out  # printed the diff


def test_module_surface_matches_singleton():
    # The functional surface delegates to the loaded singleton.
    assert R.get_conference_map() == R.registry.get_conference_map()
    assert R.get_p4_conference_names() == R.registry.get_p4_conference_names()
