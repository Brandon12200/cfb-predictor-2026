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

# ── protect_immutable.py, invoked as the harness invokes it ───────────────────────────────────
# Until the freeze this hook had NO subprocess-level coverage anywhere in the suite — its only
# tests were indirect (shared-tuple + import checks). That gap hid a real hole: the frozen paths
# inherited the artifact directories' "new files may be added" exemption, so a NEW file could be
# written into `factors/`. These run the real hook the way the harness does.

def _run_protect_immutable(rel_path: str, tool: str = "Edit") -> int:
    import json
    import os
    import subprocess
    import sys

    hook = conftest._REPO_ROOT / ".claude" / "hooks" / "protect_immutable.py"
    payload = {"tool_name": tool,
               "tool_input": {"file_path": str(conftest._REPO_ROOT / rel_path)},
               "cwd": str(conftest._REPO_ROOT)}
    proc = subprocess.run([sys.executable, str(hook)], input=json.dumps(payload),
                          capture_output=True, text=True, timeout=30,
                          env={**os.environ, "CLAUDE_PROJECT_DIR": str(conftest._REPO_ROOT)})
    return proc.returncode


BLOCKED, ALLOWED = 2, 0


def test_frozen_model_code_refuses_edits_to_existing_files():
    """The core of the v2026-frozen tag: `factors/` and `engine/` are immutable."""
    for rel in ("factors/physical_coefficients.py", "factors/factor_registry.py",
                "engine/prediction_engine.py", "engine/power_ratings.py",
                "engine/variance_detector.py"):
        assert _run_protect_immutable(rel) == BLOCKED, rel


def test_frozen_model_code_refuses_NEW_files_too():
    """Regression pin on a real hole found at F-close review.

    The frozen paths originally inherited the artifact rule "only modification is refused; new
    files may be added" — correct for `data/predictions/`, where the pipeline writes a new file
    every week, and WRONG for frozen code. `factor_registry._load_all_factors` discovers factors by
    SCANNING THE DIRECTORY, so a new file dropped into `factors/` would be auto-registered, shrink
    nothing but change the normalization denominator, and renormalize every other factor's weight —
    a different model under the same tag, added rather than edited.
    """
    for rel in ("factors/brand_new_factor.py", "engine/brand_new_module.py",
                "factors/nested/deeper.py"):
        assert _run_protect_immutable(rel, tool="Write") == BLOCKED, rel


def test_append_only_artifacts_still_permit_NEW_files():
    """The contrast that makes the above a real distinction, not a blanket rule.

    The weekly pipeline MUST be able to write a new prediction file; only overwriting an existing
    one is refused. Breaking this would break the season.
    """
    assert _run_protect_immutable("data/predictions/2026_week_99.json", tool="Write") == ALLOWED
    # ...while an existing artifact stays immutable.
    existing = sorted((conftest._REPO_ROOT / "data" / "predictions").glob("*.json"))
    if existing:
        rel = existing[0].relative_to(conftest._REPO_ROOT)
        assert _run_protect_immutable(str(rel)) == BLOCKED


def test_freeze_exempt_paths_remain_writable():
    """The freeze must not seize the paths Phase 5 has to work in."""
    for rel in ("analytics/predictions.py", "data/schedule_intel.py", "scripts/grade.py",
                "cli/cfb.py", "docs/SCHEMA.md"):
        assert _run_protect_immutable(rel) == ALLOWED, rel
