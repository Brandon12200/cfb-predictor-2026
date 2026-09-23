"""The report commit message must name every report the commit changes.

Since PR #58 the Sunday job re-renders every gradable week, but the commit message still named only
`pipeline_week`: commit `535d2b9` (2026-09-13) was titled "report: 2026 week 02 + season to date"
and also rewrote `reports/2026_week_01.md`. `git log -- reports/` is the only index to a rendering's
history (D23), so a message that omits a week misdescribes that history.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from scripts.changed_report_weeks import label_from_porcelain

ROOT = Path(__file__).resolve().parent.parent


def test_the_2026_09_13_commit_is_named_correctly():
    """The exact contents of `535d2b9`: week 01 rewritten, week 02 new, season rewritten."""
    porcelain = (" M reports/2026_season.md\n"
                 " M reports/2026_week_01.md\n"
                 "?? reports/2026_week_02.md\n")
    assert label_from_porcelain(porcelain, 2026) == "weeks 01, 02 + season to date"


@pytest.mark.parametrize("porcelain, label", [
    (" M reports/2026_week_02.md\n M reports/2026_season.md\n", "week 02 + season to date"),
    (" M reports/2026_season.md\n", "season to date"),
    ("", "no report changes"),
    ("?? reports/2026_week_10.md\n M reports/2026_week_03.md\n", "weeks 03, 10"),
])
def test_labels(porcelain, label):
    assert label_from_porcelain(porcelain, 2026) == label


def test_weeks_are_ordered_numerically_not_by_the_order_git_lists_them():
    porcelain = " M reports/2026_week_12.md\n M reports/2026_week_02.md\n M reports/2026_week_09.md\n"
    assert label_from_porcelain(porcelain, 2026) == "weeks 02, 09, 12"


def test_other_years_and_unrelated_files_are_ignored():
    """The 2025 retro and a stray file must not leak into a 2026 message."""
    porcelain = (" M reports/2025_retro.md\n"
                 " M reports/2025_week_04.md\n"
                 "?? reports/notes.txt\n"
                 " M reports/2026_week_05.md\n")
    assert label_from_porcelain(porcelain, 2026) == "week 05"


def test_the_commit_message_uses_the_label_not_the_scalar_week():
    """Wired, not just written — and the label step must not be able to swallow its own failure."""
    text = (ROOT / ".github/workflows/weekly-grade.yml").read_text()
    # The step ends at the next step of EITHER shape. Splitting only on `- uses:` read into the D44
    # `- name:` step that follows, which names `week_padded` for a different reason.
    commit = re.split(r"\n\s+- (?:uses|name):", text.split("paths: reports", 1)[1], maxsplit=1)[0]
    assert "steps.reportweeks.outputs.label" in commit
    assert "week_padded" not in commit, "the report message still names only pipeline_week"

    step = text.split("id: reportweeks", 1)[1].split("- uses:", 1)[0]
    assert "scripts/changed_report_weeks.py" in step
    assert 'echo "label=$(' not in step, (
        "`echo \"label=$(cmd)\"` takes echo's exit status and swallows a failing script"
    )
