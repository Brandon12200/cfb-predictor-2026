"""No test may assert a moving quantity as a literal against live committed data.

**The defect this pins.** `test_cal_now_has_a_schedule` asserted the string `"remaining 11"` against
`data/projections/`, which the Tuesday job rebuilds every week. Cal played in week 1, the week-2
rebuild rendered `record 0-1 | remaining 10`, and `main` went red on the week-2 claim push for a
calendar reason (run 34256174509) — no code had changed.

**Why the earlier sweep missed it.** PR #53 swept the same class by asking, of each test that reads a
regenerated artifact, "does it assert a property time can break?" — and answered by reading the call
site. That found `EXIT_OK`-on-a-complete-slate and slate-membership assertions, because in those the
time-dependence is visible *at the read*. Here it is not: the read is an ordinary `run_project` call
and the coupling is a number typed into a string, whose provenance is a file the test never names.
This test is keyed on the **assertion** rather than the read, which is the axis that was missing.

Scope is deliberately narrow — the two shapes that actually bit (`remaining N`, `record W-L`) plus
bare `W-L` strings — rather than every integer literal in the suite. A broad "no magic numbers" rule
would flag hundreds of legitimate pins (exit codes, schema versions, ratified constants) and be
switched off within a week. A test nobody trusts is not a guard.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEST_FILES = sorted((ROOT / "tests").glob("test_*.py"))

# Readers that resolve to the committed, pipeline-regenerated tree.
_LIVE_DIRS = ("data/projections", "data/results", "data/graded", "data/predictions",
              "data/snapshots", "data/lines", "data/ratings")
_LIVE_CALLS = ("run_project", "_load_projection", "_projection_weeks", "_projections_dir",
               "load_snapshot", "load_manifest", "latest_odds_quota")

# A test that redirects the reader at a temp tree or patches it is asserting about its own
# fixture, where a literal is not merely allowed but correct.
_FIXTURED = ("tmp_path", "monkeypatch")

_SHAPES = {
    "remaining <N>": re.compile(r"\bremaining \d+"),
    "record <W>-<L>": re.compile(r"\brecord \d+-\d+"),
    "bare <W>-<L> string": re.compile(r"^\d+-\d+$"),
}


def _code_strings(fn: ast.FunctionDef) -> list[str]:
    """Every string constant in the function's CODE — docstring excluded.

    Scanning raw source text instead would flag the prose: the rewritten Cal test quotes the very
    literal it was fixed for while explaining the defect, and a guard that cannot tell an assertion
    from its own postmortem is a guard people delete. An f-string's literal parts are included
    (they are `Constant` nodes inside `JoinedStr`), which is correct and harmless — the interpolated
    form `f"remaining {rec['remaining']}"` carries no digits to match.
    """
    body = fn.body[1:] if (fn.body and isinstance(fn.body[0], ast.Expr)
                           and isinstance(fn.body[0].value, ast.Constant)
                           and isinstance(fn.body[0].value.value, str)) else fn.body
    out = []
    for stmt in body:
        for node in ast.walk(stmt):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                out.append(node.value)
    return out


def _offending_tests() -> list[tuple[str, int, str, list[str]]]:
    out: list[tuple[str, int, str, list[str]]] = []
    for f in TEST_FILES:
        if f.name == Path(__file__).name:
            continue                      # this file names the shapes while describing them
        src = f.read_text()
        for node in ast.walk(ast.parse(src)):
            if not isinstance(node, ast.FunctionDef) or not node.name.startswith("test_"):
                continue
            seg = ast.get_source_segment(src, node) or ""
            if any(t in seg for t in _FIXTURED):
                continue
            if not (any(d in seg for d in _LIVE_DIRS) or any(c in seg for c in _LIVE_CALLS)):
                continue
            strings = _code_strings(node)
            found = sorted({name for name, pat in _SHAPES.items()
                            for s in strings if pat.search(s)})
            if found:
                out.append((str(f.relative_to(ROOT)), node.lineno, node.name, found))
    return out


def test_the_scan_sees_the_suite():
    """Guard the guard: a broken parser would make the real assertion pass vacuously."""
    assert len(TEST_FILES) > 40, f"only found {len(TEST_FILES)} test files — parser or glob broke"
    live = 0
    for f in TEST_FILES:
        src = f.read_text()
        for node in ast.walk(ast.parse(src)):
            if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
                seg = ast.get_source_segment(src, node) or ""
                if any(c in seg for c in _LIVE_CALLS) or any(d in seg for d in _LIVE_DIRS):
                    live += 1
    assert live >= 5, f"expected several tests reading live artifacts, classified {live}"


def test_no_test_asserts_a_moving_quantity_as_a_literal():
    bad = _offending_tests()
    assert not bad, (
        "these tests assert a literal count or record against data the pipeline rebuilds, so they "
        "go red on a calendar event rather than a code change:\n  "
        + "\n  ".join(f"{f}:{ln} {name} — {', '.join(shapes)}" for f, ln, name, shapes in bad)
        + "\nAssert the invariant instead (derive the expected value from the same record the "
          "output renders), or point the reader at a fixture."
    )
