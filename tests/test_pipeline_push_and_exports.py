"""Two invariants learned from a live failure, pinned so they cannot regress.

**1. Pushes need the deploy key.** `main-protection`'s required-status-checks rule blocks DIRECT
PUSHES, not merely merges: a brand-new commit has no check results, so every push is refused
("9 of 9 required status checks are expected"). Observed on 2026-08-08 — the capture run resolved
its secrets, fetched, committed, retried three times and fired its stranded-commit diagnostic, all
correctly, and was refused at the last step. The default `GITHUB_TOKEN` cannot push to `main`;
"Deploy keys" is on the ruleset bypass list, so `actions/checkout` must use `ssh-key`.

**2. A built week must carry its derived exports.** `verify-phase-2` asserts a projection file
exists for *every* built week, and SPEC §3's derived-artifact invariant says the committed exports
track their inputs. The Tuesday job built snapshots and never regenerated ratings/projections — so
week 2's snapshot would have turned `verify-phase-2` red. It stayed latent only because
`GITHUB_TOKEN` pushes skip CI; the deploy key makes every data commit run it, which is how a latent
gap became a weekly red main. Fixing the push exposed the second bug — worth remembering that the
two are connected.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = ROOT / ".github" / "workflows"
CADENCE = ["weekly-predict.yml", "daily-capture.yml", "weekly-grade.yml"]


def text(name: str) -> str:
    return (WORKFLOWS / name).read_text()


# --- 1. the push credential ----------------------------------------------------------------------

@pytest.mark.parametrize("workflow", CADENCE)
def test_a_pushing_workflow_checks_out_with_the_deploy_key(workflow):
    body = text(workflow)
    assert "ssh-key: ${{ secrets.DEPLOY_KEY }}" in body, (
        f"{workflow} pushes to main but checks out with the default GITHUB_TOKEN, which the "
        f"required-status-checks rule refuses — every push would be declined."
    )


@pytest.mark.parametrize("workflow", CADENCE)
def test_the_deploy_key_is_on_the_checkout_that_the_commit_step_uses(workflow):
    """The key must be on the FIRST checkout — the one whose credentials the later push inherits."""
    body = text(workflow)
    first_checkout = body.index("actions/checkout@v4")
    assert body.index("ssh-key: ${{ secrets.DEPLOY_KEY }}") > first_checkout
    assert body.index("ssh-key: ${{ secrets.DEPLOY_KEY }}") < body.index("cfb-commit")


def test_workflows_that_never_push_do_not_take_the_key():
    """Least privilege: CI and freeze-integrity read only, so they must not carry a write key."""
    for name in ("ci.yml", "freeze-integrity.yml"):
        assert "DEPLOY_KEY" not in text(name), f"{name} does not push and must not hold a push key"


@pytest.mark.parametrize("workflow", CADENCE)
def test_tags_are_still_fetched(workflow):
    """`ssh-key` must not have displaced `fetch-depth: 0` — without tags, model_version() degrades
    to a bare SHA and the freeze assertion cannot resolve its reference."""
    assert "fetch-depth: 0" in text(workflow)


# --- 2. the derived-export obligation -------------------------------------------------------------

def test_the_tuesday_job_regenerates_ratings_and_projections():
    body = text("weekly-predict.yml")
    assert "scripts/update_ratings.py" in body, "ratings export is never regenerated"
    assert "scripts/build_projections.py" in body, "projections are never regenerated"


def test_the_exports_are_regenerated_after_the_snapshot_is_built():
    """They are pure functions OF the snapshot, so they must be derived from the new one."""
    body = text("weekly-predict.yml")
    assert body.index("scripts/build_snapshot.py") < body.index("scripts/update_ratings.py")


def test_the_exports_ship_in_the_same_commit_as_their_snapshot():
    """Split across pushes, CI would see a week with a snapshot and no projections and go red."""
    body = text("weekly-predict.yml")
    staged = re.search(r"paths: (data/snapshots[^\n]*)", body)
    assert staged, "the snapshot commit step is missing"
    for path in ("data/snapshots", "data/ratings", "data/projections"):
        assert path in staged.group(1), f"{path} is not staged with the snapshot"


def test_the_claim_commit_still_stands_alone():
    """The derived exports ride with the snapshot — they must NOT leak into the claim commit,
    whose isolation is the pre-registration evidence (D22)."""
    body = text("weekly-predict.yml")
    claim = body.split("paths: data/predictions", 1)
    assert len(claim) == 2
    assert claim[1].splitlines()[0].strip() == ""


def test_the_exports_are_regenerated_before_predictions_are_built():
    """Ordering keeps the working tree clean when `model_version` is stamped — an uncommitted
    export would make `git describe --dirty` mark every claim of the week."""
    body = text("weekly-predict.yml")
    assert body.index("scripts/build_projections.py") < body.index("scripts/build_predictions.py")


def test_verify_phase_2_still_demands_a_projection_per_built_week():
    """The assertion this obligation exists to satisfy. If it is ever relaxed, the pipeline step
    becomes optional — so the two are pinned together."""
    src = (ROOT / "scripts" / "verify_phase_2.py").read_text()
    assert "proj_files == set(built)" in src
