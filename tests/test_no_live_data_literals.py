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
# ...and the same directories reached a segment at a time, `ROOT / "data" / "projections" / …`,
# which is the DOMINANT style in this suite (test_normalizer_fails_closed, test_lean_attribution,
# test_pipeline_preflight, test_slate_reconciliation and others all build paths this way). Matching
# only the joined form would leave the guard blind exactly where offenders are most likely to live —
# review demonstrated the evasion with a working counter-example that passed clean.
_LIVE_TIERS = ("projections", "results", "graded", "predictions", "snapshots", "lines", "ratings")

# A test that redirects the reader at a temp tree is asserting about its own fixture, where a
# literal is not merely allowed but correct. The redirect must be VISIBLE: a bare mention of
# `monkeypatch` proves nothing, since a test can patch something unrelated and still read the real
# tree. Requiring the patched target to be a live reader keeps the exemption honest.
_REDIRECT = re.compile(
    r"monkeypatch\.setattr\([^)]*(?:" + "|".join(_LIVE_CALLS) + r"|_SNAPSHOTS_DIR|_LINES_DIR|"
    r"PREDICTIONS_DIR)"
    r"|base\s*=\s*tmp_path"
    r"|_projections_dir\s*=|_load_projection\s*=",
    re.S,
)

_SHAPES = {
    "remaining <N>": re.compile(r"\bremaining \d+"),
    "record <W>-<L>": re.compile(r"\brecord \d+-\d+"),
    "bare <W>-<L> string": re.compile(r"^\d+-\d+$"),
}


def _code_strings(fn: ast.FunctionDef) -> list[str]:
    """Every string constant in the function's CODE and its DECORATORS — docstring excluded.

    Scanning raw source text instead would flag the prose: the rewritten Cal test quotes the very
    literal it was fixed for while explaining the defect, and a guard that cannot tell an assertion
    from its own postmortem is a guard people delete. An f-string's literal parts are included
    (they are `Constant` nodes inside `JoinedStr`), which is correct and harmless — the interpolated
    form `f"remaining {rec['remaining']}"` carries no digits to match.

    Decorators are walked explicitly. `ast.get_source_segment` on a `FunctionDef` starts at `def`
    and excludes them, so a `@pytest.mark.parametrize("expected", ["remaining 11"])` would
    otherwise be invisible to a guard whose whole job is to find that literal.
    """
    body = fn.body[1:] if (fn.body and isinstance(fn.body[0], ast.Expr)
                           and isinstance(fn.body[0].value, ast.Constant)
                           and isinstance(fn.body[0].value.value, str)) else fn.body
    out = []
    for stmt in list(fn.decorator_list) + list(body):
        for node in ast.walk(stmt):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                out.append(node.value)
    return out


def _reaches_live_data(fn: ast.FunctionDef, seg: str) -> bool:
    """Does this test read the committed tree — by joined path, by call, or segment by segment?"""
    if any(c in seg for c in _LIVE_CALLS) or any(d in seg for d in _LIVE_DIRS):
        return True
    strings = set(_code_strings(fn))
    return "data" in strings and bool(strings & set(_LIVE_TIERS))


def _scan_source(src: str, label: str) -> list[tuple[str, int, str, list[str]]]:
    """Scan one module's source. Factored out so the discrimination tests below can feed it
    synthetic modules — a guard whose evasions are only ever checked by hand, once, is a guard
    whose next regression is silent."""
    out: list[tuple[str, int, str, list[str]]] = []
    for node in ast.walk(ast.parse(src)):
        if not isinstance(node, ast.FunctionDef) or not node.name.startswith("test_"):
            continue
        seg = ast.get_source_segment(src, node) or ""
        deco = "\n".join(ast.get_source_segment(src, d) or "" for d in node.decorator_list)
        if _REDIRECT.search(seg):
            continue
        if not _reaches_live_data(node, seg + "\n" + deco):
            continue
        strings = _code_strings(node)
        found = sorted({name for name, pat in _SHAPES.items()
                        for s in strings if pat.search(s)})
        if found:
            out.append((label, node.lineno, node.name, found))
    return out


def _offending_tests() -> list[tuple[str, int, str, list[str]]]:
    out: list[tuple[str, int, str, list[str]]] = []
    for f in TEST_FILES:
        if f.name == Path(__file__).name:
            continue                      # this file names the shapes while describing them
        out.extend(_scan_source(f.read_text(), str(f.relative_to(ROOT))))
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


# --- the guard's own evasions, pinned ------------------------------------------------------------
# All three were found by review AFTER the first version shipped clean, each demonstrated with a
# working counter-example that the guard passed. They are pinned here rather than fixed and
# forgotten, because every one of them is a way for a future offender to be invisible.

_EVASION_SPLIT_PATH = '''
def test_reads_live_data_a_segment_at_a_time():
    p = ROOT / "data" / "projections" / "2026_week_02.json"
    out = render(p)
    assert "remaining 11" in out
'''

_EVASION_DECORATOR = '''
@pytest.mark.parametrize("expected", ["remaining 11"])
def test_literal_hides_in_the_decorator(expected):
    assert expected in run_project(["--team", "Cal"])
'''

_EVASION_IRRELEVANT_PATCH = '''
def test_mentions_monkeypatch_for_something_unrelated(monkeypatch):
    monkeypatch.setenv("TZ", "UTC")
    out = run_project(["--team", "Cal", "--quiet"])
    assert "remaining 11" in out
'''

_LEGITIMATE_REDIRECT = '''
def test_actually_redirects_the_reader(tmp_path, monkeypatch):
    monkeypatch.setattr(cli.app, "_projections_dir", lambda: tmp_path)
    _write(tmp_path, 2026, 2, {"CAL": {"remaining": 11}})
    out = run_project(["--team", "Cal", "--quiet"])
    assert "remaining 11" in out
'''


def test_the_guard_catches_a_split_path_read():
    """`ROOT / "data" / "projections"` is the dominant path style in this suite; matching only the
    joined `"data/projections"` form left the guard blind exactly where offenders would live."""
    assert _scan_source(_EVASION_SPLIT_PATH, "<split>"), "split-path read evades the guard"


def test_the_guard_catches_a_literal_in_a_decorator():
    """`ast.get_source_segment` on a FunctionDef starts at `def`, so a parametrize literal is
    invisible unless decorators are walked explicitly."""
    assert _scan_source(_EVASION_DECORATOR, "<deco>"), "decorator literal evades the guard"


def test_an_unrelated_monkeypatch_does_not_buy_an_exemption():
    """The fixture exemption must be earned by redirecting a live READER, not by mentioning the
    fixture. `monkeypatch.setenv` proves nothing about where the data came from."""
    assert _scan_source(_EVASION_IRRELEVANT_PATCH, "<patch>"), \
        "an unrelated monkeypatch bought an exemption"


def test_a_real_redirect_is_still_exempt():
    """The other half: a test that genuinely points the reader at its own fixture must NOT be
    flagged, or the guard becomes noise and gets switched off."""
    assert not _scan_source(_LEGITIMATE_REDIRECT, "<ok>"), \
        "a legitimately fixtured test was flagged — the exemption is too tight"


def test_no_test_asserts_a_moving_quantity_as_a_literal():
    bad = _offending_tests()
    assert not bad, (
        "these tests assert a literal count or record against data the pipeline rebuilds, so they "
        "go red on a calendar event rather than a code change:\n  "
        + "\n  ".join(f"{f}:{ln} {name} — {', '.join(shapes)}" for f, ln, name, shapes in bad)
        + "\nAssert the invariant instead (derive the expected value from the same record the "
          "output renders), or point the reader at a fixture."
    )
