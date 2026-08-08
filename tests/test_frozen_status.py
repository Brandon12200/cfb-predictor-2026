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


def test_frozen_tag_returns_the_bare_tag_not_the_build_stamp():
    _skip_without_tag()
    assert frozen_tag() == TAG
    assert "-g" not in (frozen_tag() or ""), "frozen_tag must not carry the describe suffix"


def test_model_version_is_the_build_stamp_and_they_differ_after_the_tag():
    """The whole reason the label was wrong: these are different strings post-tag."""
    _skip_without_tag()
    mv = model_version()
    assert mv.startswith(TAG)
    if mv != TAG:  # any freeze-exempt commit after the tag
        assert frozen_tag() != mv


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
    """Compare a real tree against a directory that is genuinely different."""
    _skip_without_tag()
    assert frozen_trees_match(TAG, trees=("factors", "docs")) is False


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
