"""`utils/version.py`'s freeze-state helpers and the `cfb status` line built on them.

These are the surface that answers "is the model still frozen?" for a human, and they were the one
new guard surface in this branch with no direct test — precisely the "second copy of a guard"
shape D25.4 flags. `frozen_tree_hashes` is the shared primitive behind the pipeline preflight, the
daily freeze-integrity job and this display, so if it is wrong all three are wrong together.

They also pin the distinction that caused the defect: `model_version()` is the BUILD stamp
(`v2026-frozen-N-g<sha>`), `frozen_tag()` is the TAG. Labelling the former as the latter reads as
though the freeze had moved.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from utils.version import frozen_tag, frozen_tree_hashes, frozen_trees_match, model_version

ROOT = Path(__file__).resolve().parent.parent
TAG = json.loads((ROOT / "season.json").read_text())["pipeline"]["freeze_tag"]


def _skip_without_tag():
    if frozen_tag() is None:
        pytest.skip("no reachable tag (shallow clone)")


def test_the_configured_freeze_tag_is_the_current_tag():
    """**The retag lesson, pinned.** `season.json`'s `freeze_tag` is the single source of truth
    (D24) for every freeze assertion — the preflight's tree-hash check and the daily
    freeze-integrity job both read it. After `v2026-frozen-2` was cut it still said
    `v2026-frozen`, so those checks were validating against a SUPERSEDED tag and passing (the
    frozen trees are identical at both, so nothing complained). Retagging includes moving this."""
    _skip_without_tag()
    assert TAG == frozen_tag(), (
        f"season.json freeze_tag is {TAG!r} but the repository's current tag is {frozen_tag()!r} — "
        f"a retag left the config behind, and every freeze assertion is now checking the wrong "
        f"reference."
    )


def test_no_stale_tag_name_in_live_config():
    """**Scope is `season.json` deliberately, and the name now says so.**

    The previous name promised "no live code" while scanning only this one file — a false sense of
    coverage that let a stale literal survive in `data/snapshot/store.py`'s error message. Prose,
    docstrings and history legitimately name superseded tags (they are describing the past), so a
    repo-wide literal ban is not the right rule. What must never go stale is the CONFIG that
    assertions read.

    **Scope stated honestly, because the first attempt at this docstring overclaimed.** It said
    runtime strings were "covered below", while the sibling test scanned only one function — and a
    second stale instance survived in `.claude/hooks/protect_immutable.py`'s block message. Both
    known runtime strings are now checked by `test_runtime_messages_do_not_name_a_stale_tag`, and
    that test names the files it scans rather than implying it scans everything.
    """
    import re
    current = frozen_tag()
    if current is None:
        pytest.skip("no reachable tag")
    offenders = []
    for path in (ROOT / "season.json",):
        for i, line in enumerate(path.read_text().splitlines(), 1):
            for m in re.finditer(r"v2026-frozen[\w.-]*", line):
                if m.group(0) != current:
                    offenders.append(f"{path.name}:{i}: {m.group(0)}")
    assert not offenders, f"stale tag references in live config: {offenders}"


def test_runtime_messages_do_not_name_a_stale_tag():
    """A message a user SEES must not name a superseded tag — it goes stale at every retag.

    The scanned set is enumerated rather than implied: these are the runtime strings known to
    mention the freeze tag. `load_frozen_vehicle` derives it from `FROZEN_VEHICLE_SOURCE`;
    `protect_immutable`'s block message refers to "the freeze tag" generically, since a hook has no
    reason to name a specific one. Docstrings and module headers are excluded deliberately — they
    describe history, and history legitimately names old tags.
    """
    import re

    store = (ROOT / "data" / "snapshot" / "store.py").read_text()
    body = store.split("def load_frozen_vehicle", 1)[1].split("\ndef ", 1)[0]
    assert "FROZEN_VEHICLE_SOURCE[0]" in body, (
        "load_frozen_vehicle's error message must derive the tag name, not hardcode it"
    )
    assert "`v2026-frozen`" not in body

    hook = (ROOT / ".claude" / "hooks" / "protect_immutable.py").read_text()
    emitted = [ln for ln in hook.splitlines()
               if "Blocked:" in ln and re.search(r"v2026-frozen[\w.-]*", ln)]
    assert not emitted, f"the hook's block message names a specific tag: {emitted}"


def test_frozen_tag_returns_the_bare_tag_not_the_build_stamp():
    _skip_without_tag()
    assert frozen_tag() == TAG
    assert "-g" not in (frozen_tag() or ""), "frozen_tag must not carry the describe suffix"


def test_model_version_is_the_build_stamp_and_relates_correctly_to_the_tag():
    """The whole reason the label was wrong: the build stamp and the tag are different things.

    **This test used a stale constant to decide which state it was in.** It compared
    `model_version()` against `TAG` to infer "are we past the tag", but `TAG` came from a
    `season.json` the retag had not updated — so at HEAD == `v2026-frozen-2` it concluded "past the
    tag" and then asserted the two must differ, which they do not. The state is now derived from
    `frozen_tag()` itself, and BOTH states are asserted explicitly instead of one being inferred.
    """
    _skip_without_tag()
    mv, tag = model_version(), frozen_tag()
    assert tag is not None
    assert mv.startswith(tag), f"build stamp {mv!r} does not begin with the nearest tag {tag!r}"

    if mv == tag:
        # HEAD is exactly at the tagged commit — the two legitimately coincide. This is the state
        # immediately after a retag, and it is correct, not a defect.
        assert "-g" not in mv
    else:
        # Any freeze-exempt commit after the tag: `git describe` appends `-N-g<sha>`.
        assert mv.startswith(f"{tag}-"), mv
        assert mv != tag


def test_the_frozen_trees_currently_match_the_tag():
    _skip_without_tag()
    assert frozen_trees_match(TAG) is True, (
        "factors/ or engine/ has drifted from the freeze tag — this branch must not touch either"
    )


def test_tree_hashes_are_returned_per_directory():
    _skip_without_tag()
    pairs = frozen_tree_hashes(TAG)
    assert set(pairs) == {"factors", "engine"}
    for head, tagged in pairs.values():
        assert head and tagged and head == tagged


def test_an_unresolvable_tag_reports_unknown_rather_than_matching():
    """A shallow checkout must never be mistaken for a passing freeze check."""
    assert frozen_trees_match("v-does-not-exist") is None
    pairs = frozen_tree_hashes("v-does-not-exist")
    assert all(tagged is None for _, tagged in pairs.values())


def test_a_drifted_tree_reports_false():
    """The False branch, forced deterministically.

    This previously compared `docs` at HEAD against `docs` at the tag — which only differed
    *because HEAD happened to be ahead of the tag*. The moment a retag put HEAD exactly on the tag,
    the comparator stopped drifting and the test failed for a reason that had nothing to do with
    the behaviour under test. Incidental state is not a fixture.

    `scripts/` demonstrably changed between `v2026-frozen` and `v2026-frozen-2` (the exception-1
    work lives there), and that is a permanent fact of history rather than a property of where
    HEAD sits, so this comparison is False now and stays False.
    """
    _skip_without_tag()
    import shutil
    import subprocess
    if shutil.which("git") is None:
        pytest.skip("git unavailable")
    if subprocess.run(["git", "rev-parse", "--verify", "v2026-frozen^{commit}"],
                      capture_output=True, cwd=str(ROOT)).returncode != 0:
        pytest.skip("the superseded tag is unreachable (shallow checkout)")
    assert frozen_trees_match("v2026-frozen", trees=("scripts",)) is False


def test_cfb_status_labels_the_tag_and_the_build_separately(capsys, monkeypatch):
    """The defect was one line labelling the build stamp as the frozen tag."""
    from cli import cfb

    monkeypatch.setattr("scripts.status.main", lambda argv=None: 0)
    cfb.main(["status"])
    out = capsys.readouterr().out

    assert "Frozen tag:" in out and "Build:" in out
    tag_line = next(ln for ln in out.splitlines() if ln.startswith("Frozen tag:"))
    build_line = next(ln for ln in out.splitlines() if ln.startswith("Build:"))

    if frozen_tag() is not None:
        assert TAG in tag_line
        # The tag line must not carry the describe suffix — that was the bug.
        assert "-g" not in tag_line.split("—")[0]
        assert "match the tag" in tag_line
    assert model_version() in build_line


def test_cfb_status_says_so_loudly_when_the_frozen_paths_differ(capsys, monkeypatch):
    from cli import cfb

    monkeypatch.setattr("scripts.status.main", lambda argv=None: 0)
    monkeypatch.setattr("utils.version.frozen_trees_match", lambda tag, trees=None: False)
    cfb.main(["status"])
    out = capsys.readouterr().out
    assert "FROZEN PATHS DIFFER" in out
