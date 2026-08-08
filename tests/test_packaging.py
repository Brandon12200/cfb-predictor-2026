"""The installed package contains everything the `cfb` CLI imports.

**Why this defect survived Phase 4.5's acceptance, and why the obvious test would not catch it.**
`cli/cfb.py` imports from `scripts` and `analytics` lazily, inside its command handlers, and
neither package was in `[tool.setuptools.packages.find] include`. Running `python -m cli.cfb …` or
`cfb …` **from the repo root** works anyway, because the cwd is on `sys.path` — so every
development and test invocation passed while 9 of 11 subcommands were broken on a clean install,
including `cfb predict week`.

An **editable** install masks it the same way: `pip install -e .` adds a path hook pointing at the
project directory, so `import scripts` resolves regardless of the `include` list. A subprocess test
under an editable install therefore proves nothing about packaging — it would have passed before
the fix.

So the load-bearing test here does not import anything. It runs setuptools' own package discovery
against the configured `include` patterns and asserts the result covers what the CLI imports —
i.e. what a built wheel would actually contain. The subprocess test is a second, weaker layer that
catches gross breakage of the console script itself.
"""

from __future__ import annotations

import ast
import re
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = tomllib.loads((ROOT / "pyproject.toml").read_text())
INCLUDE = PYPROJECT["tool"]["setuptools"]["packages"]["find"]["include"]
PY_MODULES = set(PYPROJECT["tool"]["setuptools"].get("py-modules", []))


def _top_level_imports(source: Path) -> set[str]:
    """Top-level package names imported anywhere in a module, including inside functions."""
    tree = ast.parse(source.read_text())
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.add(node.module.split(".")[0])
    return names


def _discovered_packages() -> set[str]:
    """What setuptools would actually ship, given the configured include patterns."""
    from setuptools import find_packages
    return {p.split(".")[0] for p in find_packages(where=str(ROOT), include=INCLUDE)}


# --- the real check ------------------------------------------------------------------------------

def test_every_package_the_cli_imports_is_shipped():
    """Derived from the source, so it cannot go stale when a new import is added."""
    imported = _top_level_imports(ROOT / "cli" / "cfb.py")
    first_party = {n for n in imported
                   if (ROOT / n).is_dir() or (ROOT / f"{n}.py").exists()}
    shipped = _discovered_packages() | PY_MODULES

    missing = sorted(first_party - shipped)
    assert not missing, (
        f"cli/cfb.py imports {missing}, which a built wheel would not contain. "
        f"Add to [tool.setuptools.packages.find] include. Note an editable install hides this."
    )


def test_both_scripts_and_analytics_are_shipped():
    """Named explicitly: fixing only one leaves the other half of the CLI broken — `cfb slate` and
    all three `predict` subcommands fail on `analytics`, while `grade`/`report`/`status`/`data *`
    fail on `scripts`."""
    shipped = _discovered_packages()
    assert "scripts" in shipped
    assert "analytics" in shipped


def test_scripts_is_a_regular_package():
    """`find_packages` (as opposed to `find_namespace_packages`) requires `__init__.py`; without it
    the `scripts*` include pattern matches nothing and the fix silently does not apply."""
    assert (ROOT / "scripts" / "__init__.py").exists()
    assert "scripts" in _discovered_packages()


def test_the_pipeline_entry_points_are_shipped():
    """The workflows call scripts/*.py directly, so these must survive packaging too."""
    shipped = {p for p in __import__("setuptools").find_packages(where=str(ROOT), include=INCLUDE)}
    assert "scripts" in shipped
    for entry in ("build_snapshot", "build_predictions", "fetch_lines", "fetch_results",
                  "grade", "build_reports", "pipeline_week", "pipeline_preflight"):
        assert (ROOT / "scripts" / f"{entry}.py").exists(), entry


# --- the weaker second layer ----------------------------------------------------------------------

@pytest.mark.skipif(shutil.which("cfb") is None, reason="console script not installed")
def test_console_script_runs_from_a_neutral_cwd(tmp_path):
    """From outside the repo, so the cwd cannot supply the packages.

    Under an editable install this passes either way (see the module docstring) — it is here to
    catch a broken entry point, not to prove packaging.
    """
    out = subprocess.run([shutil.which("cfb"), "--help"],
                         capture_output=True, text=True, cwd=str(tmp_path), timeout=60)
    assert out.returncode == 0, out.stderr
    assert "hypothetical" in out.stdout


@pytest.mark.skipif(shutil.which("cfb") is None, reason="console script not installed")
def test_a_scripts_backed_subcommand_runs_from_a_neutral_cwd(tmp_path):
    """`cfb status` is the cheapest subcommand whose handler imports `scripts` — it was one of the
    nine that raised ModuleNotFoundError. Offline without `--ping`."""
    out = subprocess.run([shutil.which("cfb"), "status"],
                         capture_output=True, text=True, cwd=str(tmp_path), timeout=120)
    assert "ModuleNotFoundError" not in out.stderr, out.stderr
    assert out.returncode in (0, 2), out.stderr  # 2 = degraded, still a real answer


def test_the_installed_metadata_lists_both_packages():
    """Belt and braces on the current environment, when the metadata is present."""
    top_level = ROOT / "cfb_contrarian_predictor.egg-info" / "top_level.txt"
    if not top_level.exists():
        pytest.skip("no egg-info in this environment")
    listed = set(top_level.read_text().split())
    assert {"scripts", "analytics"} <= listed, (
        f"installed metadata lists {sorted(listed)} — re-run `make install` after changing "
        f"the include list."
    )


def test_no_subcommand_imports_an_unshipped_package():
    """Sweep every handler in cli/cfb.py, not just the ones we happen to remember."""
    source = (ROOT / "cli" / "cfb.py").read_text()
    lazily_imported = set(re.findall(r"^\s+from (\w+)[\w.]* import", source, re.M))
    first_party = {n for n in lazily_imported if (ROOT / n).is_dir()}
    shipped = _discovered_packages()
    assert first_party <= shipped, f"unshipped: {sorted(first_party - shipped)}"


def test_python_version_floor_is_honoured():
    assert PYPROJECT["project"]["requires-python"] == ">=3.11"
    assert sys.version_info >= (3, 11)
