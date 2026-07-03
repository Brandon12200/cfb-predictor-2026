"""Unit tests for the snapshot builder + manifest (offline, fake clients/registry)."""


import pytest

from data.snapshot import SnapshotBuilder, compute_snapshot_id, load_snapshot
from data.snapshot.store import SnapshotNotFoundError, load_manifest


class _FakeCFBD:
    """Canned CFBD responses; raise_on lets a group fail to exercise the missing path."""

    def __init__(self, raise_on=None):
        self.raise_on = raise_on or set()

    def get_games(self, year):
        if "games" in self.raise_on:
            raise RuntimeError("cfbd down")
        return [
            {"week": 1, "homeTeam": "Georgia", "awayTeam": "Clemson",
             "homePoints": 34, "awayPoints": 3, "startDate": "2026-08-30", "completed": True},
            {"week": 1, "homeTeam": "Alabama", "awayTeam": "Duke",
             "homePoints": None, "awayPoints": None, "completed": False},
        ]

    def get_advanced_season_stats(self, year):
        return [{"team": "Alabama", "offense": {"successRate": 0.5}, "defense": {}}]

    def get_coaches(self, year):
        return [{"firstName": "Kirby", "lastName": "Smart",
                 "seasons": [{"school": "Georgia", "year": 2026},
                             {"school": "Georgia", "year": 2025}]}]

    def get_season_stats(self, year):
        return [{"team": "Georgia", "statName": "totalYards", "statValue": 5000}]


class _FakeOdds:
    last_quota = {"remaining": 490, "used": 10}

    def get_ncaaf_spreads(self):
        return [{"home_team": "Georgia", "away_team": "Clemson", "bookmakers": [
            {"key": "fanduel", "markets": [{"key": "spreads", "outcomes": [
                {"name": "Georgia", "point": -7.5}, {"name": "Clemson", "point": 7.5}]}]}]}]


class _FakeRegistry:
    provenance = {"fetched_at": "2026-07-03T00:00:00Z"}

    def __init__(self, tracked=None, valid=True):
        self._tracked = tracked or {"GEORGIA", "CLEMSON", "ALABAMA", "DUKE"}
        self._valid = valid
        self._conf = {"GEORGIA": "SEC", "ALABAMA": "SEC", "CLEMSON": "ACC", "DUKE": "ACC"}

    def get_all_tracked_teams(self):
        return set(self._tracked)

    def get_team_conference(self, team):
        return self._conf.get(team)

    def validate_membership_counts(self):
        if not self._valid:
            from data.team_registry import RegistryError
            raise RegistryError("membership-count validation FAILED (test)")

    def corroborate_calendar(self):
        return ["week 0: absent from CFBD (test warning)"]


def _builder(tmp_path, cfbd=None, registry=None):
    return SnapshotBuilder(cfbd or _FakeCFBD(), _FakeOdds(), registry or _FakeRegistry(),
                           clock=lambda: "2026-07-03T12:00:00Z", base_dir=tmp_path)


def test_build_writes_bundle_and_manifest(tmp_path):
    manifest = _builder(tmp_path).build(week=1)
    snap = load_snapshot(1, base=tmp_path)
    assert (tmp_path / "2026_week_01" / "snapshot.json").exists()
    assert snap["meta"]["snapshot_id"] == manifest["meta"]["snapshot_id"]
    assert set(snap["data"]["teams"]) == {"GEORGIA", "CLEMSON", "ALABAMA", "DUKE"}


def test_manifest_covers_every_team_and_field_group(tmp_path):
    manifest = _builder(tmp_path).build(week=1)
    teams_cov = manifest["coverage"]["teams"]
    assert set(teams_cov) == {"GEORGIA", "CLEMSON", "ALABAMA", "DUKE"}
    for cov in teams_cov.values():
        assert set(cov) == {"info", "coaching", "stats", "schedule", "advanced_stats"}
        assert all(v == "cfbd" or v == "missing" for v in cov.values())
    # coverage accounting is exact — no field unaccounted (100%).
    s = manifest["summary"]
    assert s["fields_present"] + s["fields_missing"] == s["fields_total"]


def test_missing_recorded_honestly_not_fabricated(tmp_path):
    cov = _builder(tmp_path).build(week=1)["coverage"]["teams"]
    # Only Georgia has a coach / season stats; only Alabama has advanced stats.
    assert cov["GEORGIA"]["coaching"] == "cfbd"
    assert cov["CLEMSON"]["coaching"] == "missing"
    assert cov["ALABAMA"]["advanced_stats"] == "cfbd"
    assert cov["GEORGIA"]["advanced_stats"] == "missing"
    assert cov["DUKE"]["stats"] == "missing"


def test_betting_line_coverage_and_vegas_spread(tmp_path):
    manifest = _builder(tmp_path).build(week=1)
    snap = load_snapshot(1, base=tmp_path)
    games_cov = manifest["coverage"]["games"]
    # Georgia-Clemson has a posted line; Alabama-Duke does not.
    assert games_cov["CLEMSON@GEORGIA"]["betting_lines"] == "odds"
    assert games_cov["DUKE@ALABAMA"]["betting_lines"] == "missing"
    assert snap["data"]["betting_lines"]["CLEMSON@GEORGIA"]["vegas_spread"] == -7.5
    assert snap["data"]["betting_lines"]["DUKE@ALABAMA"]["vegas_spread"] is None


def test_coaching_experience_and_tenure_computed(tmp_path):
    snap = load_snapshot(1, base=tmp_path) if (tmp_path / "2026_week_01").exists() \
        else (_builder(tmp_path).build(week=1), load_snapshot(1, base=tmp_path))[1]
    coaching = snap["data"]["teams"]["GEORGIA"]["coaching"]
    assert coaching["head_coach_experience"] == 2  # two seasons in the fixture
    assert coaching["tenure_years"] == 2  # both at Georgia through 2026


def test_fetch_failure_degrades_to_missing_not_crash(tmp_path):
    manifest = _builder(tmp_path, cfbd=_FakeCFBD(raise_on={"games"})).build(week=1)
    assert manifest["sources"]["games"]["source"] is None
    assert "RuntimeError" in manifest["sources"]["games"]["fallback_reason"]
    # schedule for every team is now missing, but the build still produced a bundle.
    assert all(c["schedule"] == "missing" for c in manifest["coverage"]["teams"].values())


def test_membership_count_mismatch_aborts_build(tmp_path):
    from data.team_registry import RegistryError
    with pytest.raises(RegistryError, match="validation FAILED"):
        _builder(tmp_path, registry=_FakeRegistry(valid=False)).build(week=1)
    assert not (tmp_path / "2026_week_01").exists()  # nothing written on abort


def test_snapshot_id_is_deterministic(tmp_path):
    m1 = _builder(tmp_path).build(week=1)
    m2 = _builder(tmp_path / "again").build(week=1)
    assert m1["meta"]["snapshot_id"] == m2["meta"]["snapshot_id"]  # same data → same id


def test_calendar_warnings_recorded(tmp_path):
    manifest = _builder(tmp_path).build(week=1)
    assert manifest["calendar_warnings"]  # D1 corroboration surfaced, not silent


def test_load_missing_snapshot_raises(tmp_path):
    with pytest.raises(SnapshotNotFoundError):
        load_snapshot(9, base=tmp_path)
    with pytest.raises(SnapshotNotFoundError):
        load_manifest(9, base=tmp_path)


def test_compute_snapshot_id_order_independent():
    assert compute_snapshot_id({"a": 1, "b": 2}) == compute_snapshot_id({"b": 2, "a": 1})
