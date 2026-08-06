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


def test_guard_coverage_matches_the_immutability_hook():
    """The guard and the hooks' shared `PROTECTED` tuple must protect the same set.

    The hooks intercept an agent's Edit/Write calls (`protect_immutable.py`) and its shell commands
    (`guard_bash.py`); this guard catches runtime file I/O inside a test. A dir covered by one but
    not the others is a hole. `reports/` is excluded from ALL of them: it holds regenerable
    renderings (D23), not history.

    Reads `.claude/hooks/protected_paths.py` — the single source both hooks import (D25). The tuple
    formerly lived in `protect_immutable.py`; it was extracted so the Bash guard could share it
    rather than keep a second copy that drifts.
    """
    import importlib.util

    # IMPORT the tuple rather than text-parsing it. The previous version sliced on the first ")"
    # after `PROTECTED = (`, which silently produced an EMPTY set once explanatory comments
    # containing parentheses were added at the freeze — a test that would have passed vacuously.
    spec = importlib.util.spec_from_file_location(
        "protected_paths", conftest._REPO_ROOT / ".claude" / "hooks" / "protected_paths.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    hook_dirs = {p.rstrip("/").split("/")[-1] for p in mod.PROTECTED}
    guard_dirs = {p.name for p in conftest._PROTECTED_ARTIFACT_DIRS}

    # The runtime guard covers the append-only ARTIFACT dirs; the hook additionally covers the
    # FROZEN MODEL paths added at the v2026-frozen tag. The artifact set must match exactly; the
    # frozen additions are the only permitted difference.
    frozen = {"factors", "engine"}
    assert hook_dirs - frozen == guard_dirs, f"hook={hook_dirs} guard={guard_dirs}"
    assert frozen <= hook_dirs, "factors/ and engine/ must be frozen at the tag"
    assert "reports" not in hook_dirs, "reports/ is a rendering (D23), never guarded"
