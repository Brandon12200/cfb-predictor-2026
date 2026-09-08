"""Every week that can have a graded file must be re-rendered by the Sunday job.

**The defect this pins.** Grading and rendering live in different jobs. `weekly-predict.yml`'s
catch-up loop grades earlier weeks — that is how 2026 week 1 closed at 11/11 on 2026-09-08 — and it
renders nothing. `weekly-grade.yml` then rendered only `pipeline_week`. So week 1's graded file said
11/11 while `reports/2026_week_01.md` still said *"8/11 games graded"*, and no scheduled run would
ever have corrected it: `pipeline_week` had moved on and never comes back.

Nothing went red. A stale rendering is not a failure, it is a quiet wrong answer — and the README's
follow-along line points at exactly that file, so the artifact a reader is sent to would have been
the out-of-date one.

Two assertions, because either alone is insufficient in the way D39 recorded: one proves the SET is
right, the other proves it is WIRED. D39's defect was an output that was computed correctly and
never declared, which no amount of testing the computation would have caught.
"""
from __future__ import annotations

import re
from pathlib import Path

from scripts.pipeline_week import gradable_weeks

ROOT = Path(__file__).resolve().parent.parent
WEEKLY_GRADE = ROOT / ".github" / "workflows" / "weekly-grade.yml"
YEAR = 2026


def _graded_weeks_on_disk() -> set[int]:
    out = set()
    for p in (ROOT / "data" / "graded").glob(f"{YEAR}_week_*.json"):
        try:
            out.add(int(p.stem.split("_week_")[1]))
        except (ValueError, IndexError):
            continue
    return out


def test_the_render_set_covers_every_week_that_has_been_graded():
    """The set handed to the renderer must contain every week with a graded file.

    Behavioural: calls the real `gradable_weeks`, the function whose output the workflow passes to
    `build_reports`. If it ever stopped including an earlier week, the loop below would still run
    and still look correct while silently skipping it.
    """
    graded = _graded_weeks_on_disk()
    if not graded:
        return                      # preseason: nothing graded yet, nothing to cover
    rendered = set(gradable_weeks(max(graded), YEAR))
    missing = sorted(graded - rendered)
    assert not missing, (
        f"weeks {missing} have a graded file but are not in the set the Sunday job renders — "
        "their reports would silently fall behind their data, which is how "
        "reports/2026_week_01.md sat at '8/11 games graded' after week 1 closed at 11/11"
    )


def test_the_sunday_job_renders_that_whole_set_not_just_the_current_week():
    """...and the workflow must actually consume it.

    This reads YAML, which HANDOFF §(g).1 warns is not behaviour. The caveat is accepted for the
    same reason as in `test_workflow_tee_masking.py`: what is under test is which value a shell loop
    iterates, and that is a property of the workflow text — the behaviour underneath it is bash's,
    not ours. The companion assertion above covers the part that is ours.
    """
    text = WEEKLY_GRADE.read_text()
    block = text.split("- name: Regenerate reports", 1)
    assert len(block) == 2, "the 'Regenerate reports' step is gone or was renamed"
    step = block[1].split("- uses:", 1)[0]

    assert "grade_weeks" in step, (
        "the report step does not reference `grade_weeks` — if it renders only "
        "`steps.setup.outputs.week`, every week graded by the Tuesday catch-up keeps a stale report"
    )
    assert re.search(r"for\s+\w+\s+in\s+\$", step), (
        "the report step does not iterate the week set; a single `--week` render cannot cover it"
    )
    # The per-week render must use the loop variable, not the scalar week output.
    per_week = re.search(r"build_reports\.py --week \"?\$\{?(\w+)", step)
    assert per_week and per_week.group(1) not in ("{", ""), \
        "the per-week render does not take its week from the loop variable"
    assert "--season" in step, "the season roll-up must still be regenerated alongside the weeks"
