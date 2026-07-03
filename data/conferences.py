"""Single source of truth for Power Four conference membership (2026).

INTERIM Phase 0 fix (SPEC §4.5): the previous codebase hardcoded P4 membership
in at least three places with divergent, stale lists — the ACC list was missing
Stanford, Cal, and SMU (ACC members since 2024), so games involving those teams
were silently dropped by the P4 slate filter. Consolidating every conference
lookup here gives a single point to correct and, later, to replace.

This module is deliberately the ONE place team/conference names are hardcoded in
application code. Phase 1's season team registry (SPEC §5.5), sourced from CFBD
with provenance, is the real fix and will retire this module; the no-hardcoded
grep check in CI lands with it.

Team names are the normalizer's canonical UPPERCASE form.
"""

from __future__ import annotations

# Conference -> canonical team names (2026 season). Insertion order is the
# display order used by `list_teams`.
CONFERENCE_TEAMS: dict[str, list[str]] = {
    'SEC': [
        'ALABAMA', 'ARKANSAS', 'AUBURN', 'FLORIDA', 'GEORGIA', 'KENTUCKY',
        'LSU', 'MISSISSIPPI', 'MISSISSIPPI STATE', 'MISSOURI', 'OKLAHOMA',
        'SOUTH CAROLINA', 'TENNESSEE', 'TEXAS', 'TEXAS A&M', 'VANDERBILT',
    ],
    'BIG TEN': [
        'ILLINOIS', 'INDIANA', 'IOWA', 'MARYLAND', 'MICHIGAN', 'MICHIGAN STATE',
        'MINNESOTA', 'NEBRASKA', 'NORTHWESTERN', 'OHIO STATE', 'OREGON',
        'PENN STATE', 'PURDUE', 'RUTGERS', 'UCLA', 'USC', 'WASHINGTON',
        'WISCONSIN',
    ],
    'BIG 12': [
        'ARIZONA', 'ARIZONA STATE', 'BAYLOR', 'BYU', 'CINCINNATI', 'COLORADO',
        'HOUSTON', 'IOWA STATE', 'KANSAS', 'KANSAS STATE', 'OKLAHOMA STATE',
        'TCU', 'TEXAS TECH', 'UCF', 'UTAH', 'WEST VIRGINIA',
    ],
    # ACC = 17 for 2026, including California, Stanford, and SMU (members since
    # 2024). The old 14-team list here is exactly what dropped their games.
    'ACC': [
        'BOSTON COLLEGE', 'CALIFORNIA', 'CLEMSON', 'DUKE', 'FLORIDA STATE',
        'GEORGIA TECH', 'LOUISVILLE', 'MIAMI', 'NC STATE', 'NORTH CAROLINA',
        'PITTSBURGH', 'SMU', 'STANFORD', 'SYRACUSE', 'VIRGINIA',
        'VIRGINIA TECH', 'WAKE FOREST',
    ],
    # Tracked FBS independents (not a conference). Notre Dame at minimum; verify
    # against the registry in Phase 1 as realignment continues.
    'INDEPENDENT': ['NOTRE DAME'],
}

# Expected membership counts for the 2026 season (SPEC §5.5 season-start
# validation; Phase 1 turns this into a hard assertion against the registry).
EXPECTED_COUNTS_2026: dict[str, int] = {
    'SEC': 16,
    'BIG TEN': 18,
    'BIG 12': 16,
    'ACC': 17,
}

# P4 conference-name strings as returned (uppercased) by the schedule/CFBD API,
# used to filter the weekly slate. Includes legacy Pac-12 spellings to preserve
# prior filter behavior; independents are matched via team membership, not here.
_P4_API_CONFERENCE_NAMES: set[str] = {'SEC', 'BIG TEN', 'BIG 12', 'ACC', 'PAC-12', 'PACIFIC-12'}


def get_conference_map() -> dict[str, list[str]]:
    """Conference -> team names, including the INDEPENDENT bucket."""
    return CONFERENCE_TEAMS


def get_all_tracked_teams() -> set[str]:
    """Every team we track for the P4 slate, including tracked independents."""
    teams: set[str] = set()
    for members in CONFERENCE_TEAMS.values():
        teams.update(members)
    return teams


def get_team_conference(team: str) -> str | None:
    """Return the conference key for a canonical team name, or None."""
    if not team:
        return None
    key = team.upper()
    for conf, members in CONFERENCE_TEAMS.items():
        if key in members:
            return conf
    return None


def get_p4_conference_names() -> set[str]:
    """P4 conference-name strings for the schedule-API slate filter."""
    return set(_P4_API_CONFERENCE_NAMES)
