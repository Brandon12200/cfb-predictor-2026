"""Reconciliation gate (SPEC §5.5, owner decision this session).

Proves the CFBD-sourced registry can *replace* the hardcoded normalizer vocabulary
before any of it is deleted. The contract is frozen in
`tests/fixtures/legacy_normalizer_vocab.json` (the pre-Phase-1a canonical + FCS sets).

The test enforces *structure*, not the *correctness of any single pairing*: every
CFBD FBS team resolves to a canonical name by exactly one of three explicit routes —
exact `school.upper()`, an entry in `CANONICAL_OVERRIDES`, or an enumerated
`NEW_FBS_MEMBERS_2026` addition — with **no implicit fuzzy matching allowed here**.
The small override map and new-member list are the human review checkpoint surfaced
in the PR; this test just guarantees nothing slips in outside them.
"""

import json
from pathlib import Path

from data.team_registry import (
    CANONICAL_OVERRIDES,
    NEW_FBS_MEMBERS_2026,
    TeamRegistry,
    canonical_name,
)

_FIXTURE = Path(__file__).parent / "fixtures" / "legacy_normalizer_vocab.json"


def _legacy() -> dict:
    return json.loads(_FIXTURE.read_text())


def _fbs_rows() -> list[dict]:
    reg = TeamRegistry()
    return reg._fbs  # raw CFBD FBS rows


# -- every CFBD FBS team maps by exactly one explicit route (no fuzzy) ---------
def test_every_fbs_team_resolves_structurally():
    legacy_canonical = set(_legacy()["canonical_fbs"])
    unexplained = []
    for row in _fbs_rows():
        school = row["school"]
        name = canonical_name(school)
        exact = school.upper() in legacy_canonical and name == school.upper()
        via_override = school in CANONICAL_OVERRIDES and name in legacy_canonical
        via_new_member = name in NEW_FBS_MEMBERS_2026
        if not (exact or via_override or via_new_member):
            unexplained.append((school, name))
    assert not unexplained, (
        "CFBD FBS teams with no explicit resolution route (add a CANONICAL_OVERRIDES "
        f"entry or enumerate as a new member): {unexplained}"
    )


# -- the two cases are disjoint and correctly typed ---------------------------
def test_overrides_target_existing_canonical():
    legacy_canonical = set(_legacy()["canonical_fbs"])
    for school, target in CANONICAL_OVERRIDES.items():
        assert target in legacy_canonical, (
            f"override {school!r} -> {target!r} does not target an existing canonical "
            "name (a genuinely new team must be a new member, not an override)"
        )


def test_new_members_are_not_existing_canonical():
    legacy_canonical = set(_legacy()["canonical_fbs"])
    for name in NEW_FBS_MEMBERS_2026:
        assert name not in legacy_canonical, (
            f"{name!r} is enumerated as a new member but already exists in the legacy "
            "canonical set — it should be a plain exact match, not a new member"
        )


def test_override_sources_are_real_cfbd_schools():
    cfbd_schools = {row["school"] for row in _fbs_rows()}
    stale = set(CANONICAL_OVERRIDES) - cfbd_schools
    assert not stale, f"CANONICAL_OVERRIDES has entries for non-existent CFBD schools: {stale}"


# -- the registry preserves the entire legacy canonical vocabulary ------------
def test_all_legacy_canonical_names_preserved():
    legacy_canonical = set(_legacy()["canonical_fbs"])
    produced = {canonical_name(row["school"]) for row in _fbs_rows()}
    missing = legacy_canonical - produced
    assert not missing, (
        f"legacy canonical names no longer produced by the registry (would silently "
        f"drop these teams): {sorted(missing)}"
    )


def test_new_members_are_exactly_the_additions():
    # The FBS canonical names beyond the legacy set must be EXACTLY the enumerated
    # new members — no more (unexpected additions), no fewer (stale enumeration).
    legacy_canonical = set(_legacy()["canonical_fbs"])
    produced = {canonical_name(row["school"]) for row in _fbs_rows()}
    additions = produced - legacy_canonical
    assert additions == set(NEW_FBS_MEMBERS_2026), (
        f"registry additions {sorted(additions)} != enumerated "
        f"NEW_FBS_MEMBERS_2026 {sorted(NEW_FBS_MEMBERS_2026)}"
    )


def test_canonical_mapping_is_one_to_one():
    # No two CFBD FBS teams may collapse onto the same canonical name.
    names = [canonical_name(row["school"]) for row in _fbs_rows()]
    dupes = {n for n in names if names.count(n) > 1}
    assert not dupes, f"canonical-name collisions across FBS teams: {dupes}"


# -- FCS coverage does not regress or collide with FBS ------------------------
def test_new_fbs_members_left_the_fcs_set():
    reg = TeamRegistry()
    fcs = reg.get_fcs_names()
    for name in NEW_FBS_MEMBERS_2026:
        assert name not in fcs, f"{name} is FBS in 2026 but still flagged FCS"


def test_fbs_and_fcs_name_spaces_are_disjoint():
    reg = TeamRegistry()
    overlap = reg.get_fbs_canonical_names() & reg.get_fcs_names()
    assert not overlap, f"teams classified as both FBS and FCS: {overlap}"


# Curated coverage guard: the legacy hardcoded FCS list is over-broad noise (aliases,
# now-FBS teams) and is NOT a preservation contract, so instead of asserting the whole
# legacy set we assert a hand-picked set of well-known, still-FCS programs that the
# FBS-vs-FCS matchup guard must keep flagging. Catches CFBD's FCS set silently losing
# real-program coverage on refresh.
_CURATED_FCS = {
    "MONTANA", "MONTANA STATE", "NORTH DAKOTA", "SOUTH DAKOTA STATE", "VILLANOVA",
    "ELON", "FURMAN", "MERCER", "WEBER STATE", "NORTHERN IOWA", "YOUNGSTOWN STATE",
    "CHATTANOOGA", "IDAHO", "WILLIAM & MARY",
}


def test_curated_fcs_programs_stay_flagged():
    fcs = TeamRegistry().get_fcs_names()
    missing = _CURATED_FCS - fcs
    assert not missing, (
        f"well-known FCS programs no longer in the registry FCS set (coverage "
        f"regression on refresh?): {sorted(missing)}"
    )
