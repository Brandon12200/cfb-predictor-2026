"""A secret the preflight consumes must be threaded to the step that runs the preflight.

**This test exists because of a live failure.** Every cadence workflow set its API keys on the
later step that *spends* them, but `cfb-setup`'s Preflight step — which runs
`check_secrets` — had no `env:` at all. Secrets are not ambient environment variables in Actions:
they exist only where `${{ secrets.* }}` is interpolated. So the preflight read `os.environ` and
found nothing, and aborted with **"ODDS_API_KEY is unset or empty"** — a message that was true
about the step's environment and false about the repository's configuration, which is the worst
kind of error message because it sends you to the wrong place.

`freeze-integrity.yml` was unaffected and is the control: its preflight is an inline `run:` step
with its own `env:`, so its CFBD check passed with the identical repo configuration.

All three cadence workflows would have aborted on their first live run. This is precisely the class
the Rehearsal-0 dry run existed to catch; it surfaced earlier, via a real scheduled run.

The requirement is derived from `ROLE_SECRETS` — the same mapping `check_secrets` uses — so adding
a role or changing its needs cannot leave this test asserting the old contract.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from scripts.pipeline_preflight import ROLE_SECRETS

ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = ROOT / ".github" / "workflows"
SETUP_ACTION = ROOT / ".github" / "actions" / "cfb-setup" / "action.yml"

# input name on cfb-setup -> environment variable the preflight reads
INPUT_FOR_SECRET = {"CFBD_API_KEY": "cfbd-api-key", "ODDS_API_KEY": "odds-api-key"}

_SETUP_CALL = re.compile(
    r"uses:\s*\./\.github/actions/cfb-setup\s*\n(?P<body>(?:\s+.*\n)+?)(?=\s*(?:-\s|\Z))")


def setup_call_sites() -> list[tuple[str, str, str]]:
    """(workflow, role, the `with:` block text) for every cfb-setup invocation."""
    sites = []
    for wf in sorted(WORKFLOWS.glob("*.yml")):
        text = wf.read_text()
        for m in _SETUP_CALL.finditer(text):
            body = m.group("body")
            role = re.search(r"role:\s*(\w+)", body)
            if role:
                sites.append((wf.name, role.group(1), body))
    return sites


def test_there_is_at_least_one_call_site():
    """Guards the regex itself — a silent zero-match would make every test below vacuous."""
    sites = setup_call_sites()
    assert sites, "no cfb-setup call sites found; the parser is broken, not the workflows"
    assert {s[1] for s in sites} == {"capture", "predict", "grade"}


@pytest.mark.parametrize("workflow,role,body", setup_call_sites(),
                         ids=[f"{w}:{r}" for w, r, _ in setup_call_sites()])
def test_every_required_secret_is_threaded_to_the_preflight(workflow, role, body):
    for secret in ROLE_SECRETS.get(role, ()):
        param = INPUT_FOR_SECRET[secret]
        assert f"{param}:" in body, (
            f"{workflow} calls cfb-setup with role '{role}', which needs {secret}, but does not "
            f"pass `{param}`. The preflight reads os.environ and will abort '{secret} is unset or "
            f"empty' — a message about the STEP's environment, not the repo's configuration."
        )
        assert f"secrets.{secret}" in body, (
            f"{workflow}: `{param}` must be wired to secrets.{secret}"
        )


@pytest.mark.parametrize("workflow,role,body", setup_call_sites(),
                         ids=[f"{w}:{r}" for w, r, _ in setup_call_sites()])
def test_no_unnecessary_secret_is_passed(workflow, role, body):
    """Least privilege: a role must not receive a key it does not need."""
    for secret, param in INPUT_FOR_SECRET.items():
        if secret not in ROLE_SECRETS.get(role, ()):
            assert f"{param}:" not in body, (
                f"{workflow} (role '{role}') passes {param} but ROLE_SECRETS does not require it"
            )


def test_the_setup_action_declares_the_inputs_and_sets_them_on_the_preflight_step():
    text = SETUP_ACTION.read_text()
    for param in INPUT_FOR_SECRET.values():
        assert f"  {param}:" in text, f"cfb-setup does not declare the `{param}` input"
    preflight = text.split("- name: Preflight", 1)
    assert len(preflight) == 2, "cfb-setup has no Preflight step"
    for secret, param in INPUT_FOR_SECRET.items():
        assert f"{secret}: ${{{{ inputs.{param} }}}}" in preflight[1], (
            f"the Preflight step does not set {secret} from inputs.{param} — the secret would not "
            f"exist in the environment check_secrets reads"
        )


def test_freeze_integrity_threads_its_own_preflight_secret():
    """The control case: it works because its preflight step carries its own env."""
    text = (WORKFLOWS / "freeze-integrity.yml").read_text()
    block = text.split("Freeze + provenance preflight", 1)
    assert len(block) == 2
    head = block[1][:400]
    assert "CFBD_API_KEY: ${{ secrets.CFBD_API_KEY }}" in head


def test_every_role_the_preflight_knows_is_reachable():
    """A role in ROLE_SECRETS with no caller is either dead config or a missing workflow."""
    called = {r for _, r, _ in setup_call_sites()}
    # `freeze` is invoked directly by freeze-integrity.yml rather than through cfb-setup.
    assert set(ROLE_SECRETS) - called == {"freeze"}
