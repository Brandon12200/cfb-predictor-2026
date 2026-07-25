"""The autouse guard in `conftest.py` that keeps tests out of the real artifact directories.

A guard that has never fired proves nothing, so its detection primitive is pinned here. The guard
exists because a manual `--save` run once left a stray file under `data/predictions/`; the save
test avoids that only by monkeypatching `PREDICTIONS_DIR` to `tmp_path`, and that patch binds
solely because the save path imports the constant at call time. If that import is ever hoisted to
module level the patch silently stops working — this guard turns that into a loud failure rather
than an untracked prediction claim (a byte-immutable D22 artifact) in the working tree.
"""

from __future__ import annotations

import tests.conftest as conftest


def test_fingerprint_detects_a_new_file(tmp_path):
    before = conftest._artifact_fingerprint((tmp_path,))
    (tmp_path / "2026_week_01.json").write_text("{}")
    after = conftest._artifact_fingerprint((tmp_path,))
    assert set(after) - set(before), "a newly created artifact must be detected"


def test_fingerprint_detects_a_modified_file(tmp_path):
    f = tmp_path / "2026_week_01.json"
    f.write_text("{}")
    before = conftest._artifact_fingerprint((tmp_path,))
    import os
    st = f.stat()
    f.write_text('{"mutated": true}')
    os.utime(f, (st.st_atime, st.st_mtime + 10))  # deterministic; avoids mtime granularity flake
    after = conftest._artifact_fingerprint((tmp_path,))
    assert [p for p in set(before) & set(after) if before[p] != after[p]], \
        "an in-place edit of an existing artifact must be detected"


def test_fingerprint_detects_a_deleted_file(tmp_path):
    f = tmp_path / "2026_week_01.json"
    f.write_text("{}")
    before = conftest._artifact_fingerprint((tmp_path,))
    f.unlink()
    after = conftest._artifact_fingerprint((tmp_path,))
    assert set(before) - set(after), "a deleted artifact must be detected"


def test_guard_covers_all_three_append_only_data_dirs():
    """Claims + outcomes both guarded (D22/D23 taxonomy)."""
    names = {p.name for p in conftest._PROTECTED_ARTIFACT_DIRS}
    assert {"predictions", "results", "graded"} <= names
