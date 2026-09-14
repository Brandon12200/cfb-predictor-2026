"""`scripts/resolve_locators.py` checks every locator in a document on three axes: exists, says, reachable.

D43 (b): the tool never existed, so it is built from the owner's three-axis specification. Each test
below pins one axis or one parsing rule against a throwaway git repository. Two of them pin the
defects the season handoff actually carried: C2's truncated test name, and C3-shaped bare `:N` rows
inheriting a file from an unrelated row.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from scripts import resolve_locators as rl

ROOT = Path(__file__).resolve().parent.parent


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True,
                          text=True).stdout.strip()


@pytest.fixture
def repo(tmp_path: Path) -> dict[str, str]:
    """main: c1 (mod.py, 3 lines) -> c2 (mod.py, 4 lines; a line inserted at the top).
    side: s1, on no path to main. Two `manifest.json` files make a basename ambiguous."""
    r = tmp_path / "repo"
    r.mkdir()
    _git(r, "init", "-q", "-b", "main")
    _git(r, "config", "user.email", "t@example.invalid")
    _git(r, "config", "user.name", "t")
    _git(r, "config", "commit.gpgsign", "false")
    (r / "pkg").mkdir()
    (r / "pkg" / "mod.py").write_text("def check_timing():\n    pass\nEXIT_DEGRADED = 2\n")
    (r / "a").mkdir()
    (r / "b").mkdir()
    (r / "a" / "manifest.json").write_text("{}\n")
    (r / "b" / "manifest.json").write_text("{}\n")
    (r / "ci.yml").write_text("on: push\nconcurrency:\n  cancel-in-progress: true\n")
    _git(r, "add", "-A")
    _git(r, "commit", "-q", "-m", "c1")
    c1 = _git(r, "rev-parse", "HEAD")
    (r / "pkg" / "mod.py").write_text("import os\ndef check_timing():\n    pass\nEXIT_DEGRADED = 2\n")
    _git(r, "commit", "-q", "-am", "c2")
    c2 = _git(r, "rev-parse", "HEAD")
    _git(r, "checkout", "-q", "-b", "side")
    (r / "side.txt").write_text("x\n")
    _git(r, "add", "-A")
    _git(r, "commit", "-q", "-m", "s1")
    s1 = _git(r, "rev-parse", "HEAD")
    _git(r, "checkout", "-q", "main")
    return {"root": str(r), "c1": c1, "c2": c2, "s1": s1}


def _run(repo: dict[str, str], doc_text: str, capsys, *extra: str) -> tuple[int, str]:
    doc = Path(repo["root"]).parent / "doc.md"
    doc.write_text(doc_text)
    rc = rl.main([str(doc), "--root", repo["root"], "--ref", "main", "--all", *extra])
    return rc, capsys.readouterr().out


# --- axis 1: exists -------------------------------------------------------------------------------

def test_a_line_that_exists_passes_and_shows_what_is_there(repo, capsys):
    rc, out = _run(repo, "`check_timing` is at `pkg/mod.py:2`.\n", capsys)
    assert rc == rl.EXIT_OK
    assert "pkg/mod.py:2: def check_timing():" in out
    assert "match: `check_timing`" in out


@pytest.mark.parametrize("text, status", [
    ("see `pkg/mod.py:99`", "NO SUCH LINE"),
    ("see `pkg/gone.py:1`", "MISSING"),
    ("see `manifest.json`", "AMBIGUOUS"),
    ("see `pkg/mod.py::no_such_function`", "NO SUCH SYMBOL"),
])
def test_a_locator_that_does_not_exist_fails(repo, capsys, text, status):
    rc, out = _run(repo, text + "\n", capsys)
    assert rc == rl.EXIT_FAIL
    assert status in out


def test_a_basename_resolves_when_it_names_exactly_one_file(repo, capsys):
    rc, out = _run(repo, "`ci.yml:3` sets cancel-in-progress\n", capsys)
    assert rc == rl.EXIT_OK
    assert "ci.yml:3: cancel-in-progress: true" in out


def test_a_truncated_symbol_name_is_not_a_prefix_match(repo, capsys):
    """C2: `test_predict_week_save_refuses_overwrite_d` for `..._d22`. A prefix match would pass it."""
    rc, out = _run(repo, "`pkg/mod.py::check_timin`\n", capsys)
    assert rc == rl.EXIT_FAIL and "NO SUCH SYMBOL" in out


# --- axis 2: says ---------------------------------------------------------------------------------

def test_a_line_that_says_something_else_is_a_check_not_a_failure(repo, capsys):
    """The sentence claims `EXIT_DEGRADED`, but the cited line is `check_timing`. A human decides."""
    rc, out = _run(repo, "`EXIT_DEGRADED` is defined at `pkg/mod.py:2`\n", capsys)
    assert rc == rl.EXIT_OK
    assert "[CHECK]" in out and "CHECK: none of `EXIT_DEGRADED`" in out


# --- axis 3: reachable, and frames ----------------------------------------------------------------

def test_a_sha_on_main_is_reachable_and_one_off_it_is_not(repo, capsys):
    rc, out = _run(repo, f"merged as `{repo['c1']}`\n", capsys)
    assert rc == rl.EXIT_OK and "c1" in out
    rc, out = _run(repo, f"stashed as `{repo['s1']}`\n", capsys)
    assert rc == rl.EXIT_FAIL and "UNREACHABLE" in out


def test_an_all_digit_token_is_a_sha_only_if_it_is_a_commit(monkeypatch):
    """Found as a flaky test: the fixture's short SHA was sometimes all digits and silently skipped."""
    monkeypatch.setattr(rl, "_is_commit", lambda tok: tok == "1234567")
    assert rl._is_sha_token("1234567") is True
    assert rl._is_sha_token("34256103940") is False
    assert rl._is_sha_token("abcdef1") is True


def test_an_unknown_sha_fails_and_an_all_digit_run_id_is_not_a_sha(repo, capsys):
    rc, out = _run(repo, "commit `abcdef1`, run `34256103940`\n", capsys)
    assert rc == rl.EXIT_FAIL
    assert "UNKNOWN COMMIT" in out and "34256103940" not in out


def test_a_frame_pin_reads_the_file_as_it_was(repo, capsys):
    """At c1 `check_timing` is line 1. At c2 a line was inserted above it, so it is line 2."""
    rc, out = _run(repo, f"`pkg/mod.py:1` (as at `{repo['c1']}`)\n", capsys)
    assert rc == rl.EXIT_OK and "pkg/mod.py:1: def check_timing():" in out
    rc, out = _run(repo, "`check_timing` at `pkg/mod.py:1`\n", capsys)
    assert "pkg/mod.py:1: import os" in out and "[CHECK]" in out


def test_every_frame_on_a_line_is_checked(repo, capsys):
    rc, out = _run(repo, f"`pkg/mod.py:4` at `{repo['c2']}`, same line at `{repo['c1']}`\n", capsys)
    assert rc == rl.EXIT_FAIL, "line 4 does not exist at c1, and that frame must be checked too"
    assert f"@{repo['c2']}" in out and f"@{repo['c1']}" in out and "NO SUCH LINE" in out


def test_a_frame_off_main_is_unreachable(repo, capsys):
    rc, out = _run(repo, f"`side.txt` at `{repo['s1']}`\n", capsys)
    assert rc == rl.EXIT_FAIL and "UNREACHABLE" in out


def test_the_default_frame_applies_to_unpinned_locators(repo, capsys):
    rc, out = _run(repo, "`pkg/mod.py:1`\n", capsys, "--frame", repo["c1"])
    assert "pkg/mod.py:1: def check_timing():" in out


# --- parsing rules --------------------------------------------------------------------------------

def test_a_bare_line_number_inherits_within_its_paragraph(repo, capsys):
    rc, out = _run(repo, "`pkg/mod.py:2` and\n`:4` agree\n", capsys)
    assert "pkg/mod.py:4: EXIT_DEGRADED = 2" in out


def test_a_bare_line_number_does_not_inherit_across_table_rows(repo, capsys):
    """C3's row cited `:111` for a test file named elsewhere. Inheriting from C1's row read the engine."""
    table = "| C1 | `pkg/mod.py:2` |\n| C3 | `:4` |\n"
    rc, out = _run(repo, table, capsys)
    assert "no file on its line or in its paragraph" in out
    assert "pkg/mod.py:4" not in out


def test_a_bare_line_number_does_not_inherit_across_list_items(repo, capsys):
    """Review of e91c924: a bullet's `:3` silently resolved against the previous bullet's file."""
    rc, out = _run(repo, "- `pkg/mod.py:2`\n- an unrelated bullet with `:3` in it\n", capsys)
    assert "no file on its line or in its paragraph" in out
    assert "pkg/mod.py:3" not in out


def test_a_list_item_continuation_line_still_inherits(repo, capsys):
    rc, out = _run(repo, "- `pkg/mod.py:2` and,\n  on the next line, `:4`\n", capsys)
    assert "pkg/mod.py:4: EXIT_DEGRADED = 2" in out


def test_a_frame_pin_governs_only_its_own_sentence(repo, capsys):
    """Review of e91c924: the frame bled into the next sentence, which named no frame, and the stale
    framed content was reported `ok`. At c1 line 1 is `def check_timing`; on the working tree it is
    `import os`."""
    text = f"As at `{repo['c1']}`, `pkg/mod.py:1` was the def. On the branch `pkg/mod.py:1` is `import os`.\n"
    rc, out = _run(repo, text, capsys)
    assert f"pkg/mod.py:1 @{repo['c1']}" in out
    assert "pkg/mod.py:1: def check_timing():" in out
    assert "pkg/mod.py:1: import os" in out, "the unframed sentence must be read from the working tree"


@pytest.mark.parametrize("path", ["../outside.txt:1", "pkg/../../outside.txt"])
def test_a_path_outside_the_repository_fails(repo, capsys, path):
    """Review of e91c924: `../` resolved against the filesystem, not the repository."""
    (Path(repo["root"]).parent / "outside.txt").write_text("secret\n")
    rc, out = _run(repo, f"see `{path}`\n", capsys)
    assert rc == rl.EXIT_FAIL and "OUTSIDE THE REPOSITORY" in out and "secret" not in out


def test_an_indented_assignment_is_a_symbol(repo, capsys):
    """Review of e91c924: a class attribute was NO SUCH SYMBOL. A comparison is still not a definition."""
    mod = Path(repo["root"]) / "pkg" / "attrs.py"
    mod.write_text("class Foo:\n    LIMIT = 5\n    def f(self):\n        OTHER == self.LIMIT\n")
    rc, out = _run(repo, "`pkg/attrs.py::LIMIT`\n", capsys)
    assert rc == rl.EXIT_OK and "pkg/attrs.py:2: LIMIT = 5" in out
    rc, out = _run(repo, "`pkg/attrs.py::OTHER`\n", capsys)
    assert rc == rl.EXIT_FAIL and "NO SUCH SYMBOL" in out


def test_templates_module_names_and_urls_are_not_locators(repo, capsys):
    text = ("`data/graded/2026_week_NN.json`, `docs/proposals/<ITEM>.md`, `cli.cfb`, "
            "`permissions.deny`, https://example.invalid/x/y.md:3\n")
    rc, out = _run(repo, text, capsys)
    assert rc == rl.EXIT_OK
    assert "0 locator(s)" in out


def test_no_document_is_a_usage_error(capsys):
    assert rl.main([]) == rl.EXIT_USAGE


def test_the_make_target_runs_the_script():
    got = subprocess.run(["make", "-n", "resolve-locators", "DOC=docs/X.md"], cwd=ROOT,
                         capture_output=True, text=True)
    assert got.returncode == 0 and "scripts/resolve_locators.py docs/X.md" in got.stdout


# --- the real defect, on the real history ----------------------------------------------------------

def test_it_catches_c2_in_the_season_handoff_as_first_written(tmp_path, capsys):
    """`590f33d` is the season handoff before C1–C4 were corrected; its test list is as at `8f7a5ff`.
    C2 (a truncated test name) must fail. Immutable history, so this is not a live-data literal."""
    have = all(subprocess.run(["git", "-C", str(ROOT), "cat-file", "-e", f"{c}^{{commit}}"],
                              capture_output=True).returncode == 0 for c in ("590f33d", "8f7a5ff"))
    if not have:
        pytest.skip("history not available (shallow clone)")
    doc = tmp_path / "HANDOFF_SEASON_590f33d.md"
    doc.write_text(subprocess.run(["git", "-C", str(ROOT), "show", "590f33d:docs/HANDOFF_SEASON.md"],
                                  check=True, capture_output=True, text=True).stdout)
    rc = rl.main([str(doc), "--root", str(ROOT), "--frame", "8f7a5ff"])
    out = capsys.readouterr().out
    assert rc == rl.EXIT_FAIL
    assert "test_predict_week_save_refuses_overwrite_d" in out and "NO SUCH SYMBOL" in out
