"""Canonical season team registry (SPEC §5.5).

Conference/FBS membership is season-specific *data*, not code. This module is the
single source of truth for it, sourced from CFBD v2 `/teams?year=YYYY` and cached
to a committed, provenance-stamped artifact under `data/registry/`. It replaces the
interim hardcoded `data/conferences.py`, the normalizer's hardcoded team/FCS lists,
and `schedule_client._get_hardcoded_conference` — the "no hardcoded team/conference
names" rule (binding principle 2) is enforced by a CI grep once those are gone.

Why an on-disk artifact and not a live fetch: the normalizer singleton imports this
module at process start and the whole test suite runs with networking blocked, so a
network call on import is impossible. Live fetching lives only in `refresh_registry`
(run via `python scripts/refresh_registry.py`; a `cfb data registry` CLI wrapper lands
with the 1c `cfb data` tooling), which is diff-aware and confirm-before-write so a CFBD
hiccup can't silently rewrite slate scope.

The artifacts under `data/registry/` are committed to git — the offline invariant
depends on them being present, so a fresh checkout/CI has them without any fetch.

Canonical team names stay the normalizer's existing UPPERCASE vocabulary: each CFBD
`school` maps to a canonical name via `canonical_name()` (exact `school.upper()`,
or an explicit `CANONICAL_OVERRIDES` entry where CFBD's spelling diverges), and
genuinely new FBS members get a new canonical name (`school.upper()`) enumerated in
`NEW_FBS_MEMBERS_2026`. Every override/new-member is justified by a live reconciliation
mismatch — see `tests/test_registry_reconciliation.py`.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_YEAR = 2026
_REGISTRY_DIR = Path(__file__).parent / "registry"
_TEAMS_ARTIFACT = _REGISTRY_DIR / "fbs_teams_2026.json"
_CALENDAR_ARTIFACT = _REGISTRY_DIR / "calendar_2026.json"
_SEASON_CALENDAR = Path(__file__).parent / "season_calendar_2026.json"

# --- slate-scope / validation policy (NOT per-team membership) ---------------
# These small constants are scope/validation *policy*, not hardcoded membership
# lists; `season.yaml` owns slate scope later (SPEC §5.5.1). The verify grep
# allows exactly these two documented constants.

# CFBD conference display name -> canonical UPPERCASE key used across the app.
_CONFERENCE_KEYS: dict[str, str] = {
    "SEC": "SEC",
    "Big Ten": "BIG TEN",
    "Big 12": "BIG 12",
    "ACC": "ACC",
    "FBS Independents": "INDEPENDENT",
}
# Power-Four conference keys that form the tracked betting slate.
P4_CONFERENCES: frozenset[str] = frozenset({"SEC", "BIG TEN", "BIG 12", "ACC"})
# Conference-name strings (uppercased) matched by the weekly schedule/slate filter.
# Legacy Pac-12 spellings are preserved to keep prior filter behavior.
_P4_API_CONFERENCE_NAMES: frozenset[str] = frozenset(
    {"SEC", "BIG TEN", "BIG 12", "ACC", "PAC-12", "PACIFIC-12"}
)
# Tracked FBS independents (betting slate). Notre Dame only, matching prior
# behavior; UConn is a known 2026 FBS independent but is intentionally NOT in the
# P4 betting slate (documented, overridable via slate scope later).
TRACKED_INDEPENDENTS: frozenset[str] = frozenset({"NOTRE DAME"})
# Expected P4 membership counts (SPEC §5.5.2 season-start hard validation).
EXPECTED_COUNTS_2026: dict[str, int] = {"SEC": 16, "BIG TEN": 18, "BIG 12": 16, "ACC": 17}

# --- canonical-name reconciliation (owner decision, this session) ------------
# CFBD `school` -> existing canonical UPPERCASE where the two diverge. Every entry
# corresponds to a real reconciliation mismatch; anything not listed maps by
# `school.upper()`. Kept small and explicit as the human review checkpoint.
CANONICAL_OVERRIDES: dict[str, str] = {
    "Ole Miss": "MISSISSIPPI",
    "Hawai'i": "HAWAII",
    "San José State": "SAN JOSE STATE",
    "Florida Atlantic": "FAU",
    "App State": "APPALACHIAN STATE",
    "California": "CAL",
    "Massachusetts": "UMASS",
    "UL Monroe": "LOUISIANA MONROE",
}
# Genuinely new FBS members absent from the 2025 canonical vocabulary (recent
# FCS->FBS transitions). Their canonical name is `school.upper()`. Enumerated here
# so the reconciliation gate can tell "new member" from "silently shoehorned".
NEW_FBS_MEMBERS_2026: frozenset[str] = frozenset(
    {"DELAWARE", "MISSOURI STATE", "NORTH DAKOTA STATE", "SACRAMENTO STATE"}
)


class RegistryError(RuntimeError):
    """Raised when the registry artifact is missing/malformed or validation fails."""


def canonical_name(school: str) -> str:
    """Map a CFBD `school` string to its canonical UPPERCASE team name."""
    return CANONICAL_OVERRIDES.get(school, school.upper())


def conference_key(cfbd_conference: str | None) -> str | None:
    """Map a CFBD conference display name to the canonical UPPERCASE key, or None."""
    if not cfbd_conference:
        return None
    return _CONFERENCE_KEYS.get(cfbd_conference, cfbd_conference.upper())


def _read_json(path: Path) -> dict:
    try:
        with path.open() as f:
            return json.load(f)
    except FileNotFoundError as exc:
        raise RegistryError(f"Registry artifact not found: {path}") from exc
    except json.JSONDecodeError as exc:
        # A corrupted artifact fails the same (loud, caught-at-singleton) way a
        # missing one does — never a silent partial load.
        raise RegistryError(f"Registry artifact is not valid JSON: {path}: {exc}") from exc


def _write_json(path: Path, payload: dict) -> None:
    with path.open("w") as f:
        json.dump(payload, f, indent=2, sort_keys=False)
        f.write("\n")


class TeamRegistry:
    """Loads the committed registry artifact and answers membership/name queries."""

    def __init__(self, teams_artifact: Path = _TEAMS_ARTIFACT,
                 calendar_artifact: Path = _CALENDAR_ARTIFACT):
        self._teams_artifact = teams_artifact
        self._calendar_artifact = calendar_artifact
        data = _read_json(teams_artifact)
        self.provenance: dict[str, Any] = data.get("_provenance", {})
        self._fbs: list[dict] = data.get("fbs", [])
        self._fcs: list[dict] = data.get("fcs", [])
        if not self._fbs:
            raise RegistryError(
                f"Registry artifact {teams_artifact} has no FBS teams — "
                "run `python scripts/refresh_registry.py`."
            )
        self._build_indexes()

    # -- indexing -------------------------------------------------------------
    def _build_indexes(self) -> None:
        self._canonical_by_conf: dict[str, list[str]] = {}
        self._conf_by_team: dict[str, str] = {}
        self._aliases_by_team: dict[str, list[str]] = {}
        self._location_by_team: dict[str, dict] = {}
        self._fbs_canonical: set[str] = set()
        for row in self._fbs:
            name = canonical_name(row["school"])
            self._fbs_canonical.add(name)
            self._aliases_by_team[name] = list(row.get("alternateNames") or [])
            if row.get("location"):
                self._location_by_team[name] = row["location"]
            key = conference_key(row.get("conference"))
            if key:
                self._conf_by_team[name] = key
                self._canonical_by_conf.setdefault(key, []).append(name)
        # FCS names deliberately skip canonical_name(): CANONICAL_OVERRIDES are
        # FBS-vocabulary specific (e.g. California->CAL) and must not apply here.
        # is_fcs_team only needs school-name membership matching, not reconciliation
        # against a legacy canonical set; accent/punctuation edge cases ride with the
        # staged alias work. Coverage is guarded by test_curated_fcs_programs_stay_flagged.
        self._fcs_names: set[str] = {row["school"].upper() for row in self._fcs}

    # -- conferences.py surface (drop-in replacement) -------------------------
    def get_conference_map(self) -> dict[str, list[str]]:
        """Tracked P4 conferences + INDEPENDENT bucket -> sorted canonical names."""
        result: dict[str, list[str]] = {}
        for key in ("SEC", "BIG TEN", "BIG 12", "ACC"):
            result[key] = sorted(self._canonical_by_conf.get(key, []))
        result["INDEPENDENT"] = sorted(
            t for t in self._canonical_by_conf.get("INDEPENDENT", [])
            if t in TRACKED_INDEPENDENTS
        )
        return result

    def get_all_tracked_teams(self) -> set[str]:
        """Every team in the tracked P4 + independents slate."""
        teams: set[str] = set()
        for members in self.get_conference_map().values():
            teams.update(members)
        return teams

    def get_team_conference(self, team: str) -> str | None:
        """Conference key for a canonical team name if it is in the tracked slate."""
        if not team:
            return None
        key = self._conf_by_team.get(team.upper())
        if key in P4_CONFERENCES:
            return key
        if key == "INDEPENDENT" and team.upper() in TRACKED_INDEPENDENTS:
            return key
        return None

    def get_p4_conference_names(self) -> set[str]:
        """P4 conference-name strings for the schedule-API slate filter."""
        return set(_P4_API_CONFERENCE_NAMES)

    # -- normalizer data source (feeds utils/normalizer.py) -------------------
    def get_fbs_canonical_names(self) -> set[str]:
        """All FBS canonical team names for the season."""
        return set(self._fbs_canonical)

    def get_aliases(self, canonical: str) -> list[str]:
        """CFBD `alternateNames` observed for a canonical team name."""
        return list(self._aliases_by_team.get(canonical, []))

    def get_fcs_names(self) -> set[str]:
        """UPPERCASE FCS school names (for `is_fcs_team`)."""
        return set(self._fcs_names)

    def get_venue(self, team: str) -> Any:
        """Canonical `Venue` (lat/long/elev/tz/dome) for an FBS team, or None. Sourced
        from the committed CFBD `location` rows — the schedule-intelligence substrate."""
        # Lazy import: data.normalize.cfbd -> utils.normalizer -> data.team_registry
        # would be circular at module load.
        from data.normalize.cfbd import normalize_venue
        loc = self._location_by_team.get(str(team).upper())
        return normalize_venue(loc) if loc is not None else None

    def iter_fbs(self) -> Iterable[tuple[str, str | None, list[str]]]:
        """Yield (canonical_name, conference_key, aliases) for every FBS team."""
        for row in self._fbs:
            name = canonical_name(row["school"])
            yield name, conference_key(row.get("conference")), list(
                row.get("alternateNames") or []
            )

    # -- validation (SPEC §5.5.2 / D1) ----------------------------------------
    def validate_membership_counts(self) -> None:
        """Assert 2026 P4 counts + a non-empty independent slate. Hard-fail on drift."""
        conf_map = self.get_conference_map()
        problems: list[str] = []
        for conf, expected in EXPECTED_COUNTS_2026.items():
            actual = len(conf_map.get(conf, []))
            if actual != expected:
                problems.append(f"{conf}: expected {expected}, got {actual} "
                                f"({sorted(conf_map.get(conf, []))})")
        if not conf_map.get("INDEPENDENT"):
            problems.append("INDEPENDENT: expected >=1 tracked independent, got none")
        if problems:
            raise RegistryError(
                "Registry membership-count validation FAILED (season-start check, "
                "SPEC §5.5.2):\n  " + "\n  ".join(problems)
            )
        logger.info("Registry membership counts validated for 2026: %s",
                    {c: len(conf_map[c]) for c in conf_map})

    def corroborate_calendar(self) -> list[str]:
        """Compare the persisted CFBD calendar to season_calendar_2026.json (D1).

        Returns a list of human-readable mismatch warnings (also logged). This is a
        loud warning, not a hard failure: the hand-built calendar is Saturday-anchored
        week boundaries and the CFBD calendar uses its own week windows, so some
        divergence is expected and worth surfacing rather than silently trusting.
        """
        if not self._calendar_artifact.exists():
            logger.warning("No CFBD calendar artifact at %s — skipping corroboration.",
                           self._calendar_artifact)
            return []
        cfbd_weeks = _read_json(self._calendar_artifact).get("weeks", [])
        hand = _read_json(_SEASON_CALENDAR).get("weeks", {})
        cfbd_by_week = {w["week"]: w for w in cfbd_weeks
                        if w.get("seasonType") == "regular"}
        warnings: list[str] = []
        for wk, bounds in sorted(hand.items(), key=lambda kv: int(kv[0])):
            wk_i = int(wk)
            cfbd = cfbd_by_week.get(wk_i)
            if cfbd is None:
                warnings.append(f"week {wk_i}: present in season_calendar_2026.json "
                                "but absent from CFBD /calendar (regular season)")
                continue
            cfbd_start = str(cfbd.get("startDate", ""))[:10]
            if bounds.get("start") and cfbd_start and bounds["start"] != cfbd_start:
                warnings.append(f"week {wk_i}: hand start {bounds['start']} vs "
                                f"CFBD startDate {cfbd_start}")
        for w in warnings:
            logger.warning("Calendar corroboration (D1): %s", w)
        return warnings


# --- module-level singleton + drop-in functional surface ---------------------
try:
    registry: TeamRegistry | None = TeamRegistry()
except (FileNotFoundError, RegistryError) as exc:  # artifact not yet built
    logger.warning("Team registry not loaded: %s", exc)
    registry = None


def _require() -> TeamRegistry:
    if registry is None:
        raise RegistryError(
            "Team registry artifact is missing — run `python scripts/refresh_registry.py`."
        )
    return registry


def get_conference_map() -> dict[str, list[str]]:
    return _require().get_conference_map()


def get_all_tracked_teams() -> set[str]:
    return _require().get_all_tracked_teams()


def get_team_conference(team: str) -> str | None:
    return _require().get_team_conference(team)


def get_p4_conference_names() -> set[str]:
    return _require().get_p4_conference_names()


def get_fbs_canonical_names() -> set[str]:
    return _require().get_fbs_canonical_names()


def get_fcs_names() -> set[str]:
    return _require().get_fcs_names()


# --- refresh (the ONLY networked path) ---------------------------------------
def _diff_membership(old: dict, new_fbs: list[dict]) -> list[str]:
    """Human-readable membership diff (old artifact vs freshly fetched FBS teams)."""
    def _by_conf(fbs: list[dict]) -> dict[str, set[str]]:
        out: dict[str, set[str]] = {}
        for row in fbs:
            key = conference_key(row.get("conference")) or "?"
            out.setdefault(key, set()).add(canonical_name(row["school"]))
        return out

    old_map = _by_conf(old.get("fbs", []))
    new_map = _by_conf(new_fbs)
    lines: list[str] = []
    for conf in sorted(set(old_map) | set(new_map)):
        old_teams, new_teams = old_map.get(conf, set()), new_map.get(conf, set())
        added, removed = new_teams - old_teams, old_teams - new_teams
        if added or removed or len(old_teams) != len(new_teams):
            lines.append(f"  {conf}: {len(old_teams)} -> {len(new_teams)}"
                         + (f"  +{sorted(added)}" if added else "")
                         + (f"  -{sorted(removed)}" if removed else ""))
    return lines


def refresh_registry(client: Any, *, year: int = DEFAULT_YEAR, confirm: bool = True,
                     teams_artifact: Path = _TEAMS_ARTIFACT,
                     calendar_artifact: Path = _CALENDAR_ARTIFACT) -> dict[str, Any]:
    """Fetch `/teams` + `/calendar` live, diff, confirm, then write the artifacts.

    `confirm=True` prints the membership diff and requires an interactive `yes` before
    overwriting an existing artifact — a CFBD-side error must never silently rewrite
    slate scope. Returns a summary dict. This is the only code path that hits the net.
    """
    teams = client.get_teams(year)
    calendar = client.get_calendar(year)
    fbs = [t for t in teams if t.get("classification") == "fbs"]
    fcs = [{"id": t.get("id"), "school": t["school"],
            "alternateNames": t.get("alternateNames") or []}
           for t in teams if t.get("classification") == "fcs"]

    if teams_artifact.exists():
        diff = _diff_membership(_read_json(teams_artifact), fbs)
        if diff:
            print(f"Registry membership change for {year}:")
            print("\n".join(diff))
        else:
            print(f"No FBS membership change for {year}.")
        if confirm:
            reply = input("Overwrite the committed registry artifact? [yes/N] ").strip().lower()
            if reply != "yes":
                print("Aborted — artifact unchanged.")
                return {"written": False, "diff": diff}

    fetched_at = datetime.now(UTC).isoformat()
    teams_artifact.parent.mkdir(parents=True, exist_ok=True)
    _write_json(teams_artifact, {
        "_provenance": {"source": "cfbd", "endpoint": "/teams", "year": year,
                        "fetched_at": fetched_at, "counts": {"fbs": len(fbs), "fcs": len(fcs)}},
        "fbs": fbs,
        "fcs": fcs,
    })
    _write_json(calendar_artifact, {
        "_provenance": {"source": "cfbd", "endpoint": "/calendar", "year": year,
                        "fetched_at": fetched_at, "count": len(calendar)},
        "weeks": calendar,
    })
    print(f"Wrote {teams_artifact} (fbs={len(fbs)}, fcs={len(fcs)}) and "
          f"{calendar_artifact} (weeks={len(calendar)}).")
    return {"written": True, "counts": {"fbs": len(fbs), "fcs": len(fcs)},
            "calendar_weeks": len(calendar)}
