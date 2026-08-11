"""The pipeline's committer identity must not resolve to a GitHub account.

**The defect this pins.** D30 ratified `cfb-pipeline <pipeline@users.noreply.github.com>`. That
address is GitHub's **legacy** noreply form, `<username>@users.noreply.github.com`, which GitHub
resolves to the account whose login is `pipeline` — a real, unrelated user (id 403371). Every
machine commit therefore rendered on GitHub with a stranger's avatar and a link to their profile.
Confirmed on a live commit, not inferred: the API's `author` field for `745b1cf` returned
`login: pipeline`, `html_url: https://github.com/pipeline`.

No security exposure — push authority is the deploy key, and the author field is a string, not a
credential. It is a **provenance** defect, and provenance is the whole point of SPEC §10's
tamper-evidence story: the commit is supposed to identify the mechanism that produced it.

**Why `.invalid` is the fix and not just a different string.** RFC 6761 §6.4 reserves `.invalid`
permanently; IANA never delegates it, so the domain has no A and no MX record. Mail to it can never
be delivered, GitHub can never verify it against an account, and an unverifiable address can never
be linked. The guarantee is structural rather than "no one has claimed this yet".

**Why these assertions are offline.** The suite takes no network (`tests/test_no_network.py`), so
these tests assert the *property that makes resolution impossible* rather than performing a lookup.
To re-verify against the live services:

    dig +short cfb-predictor-2026.invalid MX          # expect: empty
    gh api "search/users?q=cfb-pipeline%40cfb-predictor-2026.invalid+in:email" -q .total_count
                                                      # expect: 0
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
ACTION = ROOT / ".github" / "actions" / "cfb-commit" / "action.yml"

# RFC 6761 reserved TLDs that are guaranteed never to be delegated, plus RFC 2606's `.test`/
# `.example`. An address under any of these cannot receive mail, so it cannot be verified against a
# GitHub account. `.invalid` is the one this project uses.
UNRESOLVABLE_TLDS = (".invalid", ".test", ".example", ".localhost")

EXPECTED_NAME = "cfb-pipeline"
EXPECTED_EMAIL = "cfb-pipeline@cfb-predictor-2026.invalid"


def committer_email() -> str:
    """Read the address out of the live action, so the test cannot drift from what ships."""
    body = ACTION.read_text()
    m = re.search(r'-c\s+user\.email="([^"]+)"', body)
    assert m, "no `-c user.email=\"…\"` in the cfb-commit action — the identity wiring moved"
    return m.group(1)


def committer_name() -> str:
    body = ACTION.read_text()
    m = re.search(r'-c\s+user\.name="([^"]+)"', body)
    assert m, "no `-c user.name=\"…\"` in the cfb-commit action"
    return m.group(1)


def test_the_committer_email_is_on_a_permanently_unresolvable_domain():
    """The load-bearing assertion. If this fails, machine commits can attribute to a real account."""
    email = committer_email()
    domain = email.rpartition("@")[2].lower()
    assert any(domain.endswith(tld) for tld in UNRESOLVABLE_TLDS), (
        f"the pipeline committer email {email!r} is on {domain!r}, which is a resolvable domain. "
        f"An address that can receive mail can be verified against a GitHub account, and the "
        f"machine commits will attribute to whoever holds it — which is exactly the defect this "
        f"pins (D30 as-built amendment). Use a domain under one of {UNRESOLVABLE_TLDS}."
    )


def test_the_committer_email_is_not_a_github_noreply_address():
    """**The revert guard.** This is the specific form that caused the defect.

    `<username>@users.noreply.github.com` is GitHub's legacy noreply format and it resolves to the
    account with that login. The numeric `<id>+<username>@` form resolves too. Neither is safe here,
    because this project's committer is not a GitHub account at all — so the whole domain is banned
    rather than just the one address.
    """
    email = committer_email()
    assert "users.noreply.github.com" not in email.lower(), (
        f"{email!r} is a GitHub noreply address. Every address on that domain is designed to map to "
        f"an account — that is its purpose. `pipeline@users.noreply.github.com` mapped to a real, "
        f"unrelated user with 13 followers."
    )


def test_the_committer_identity_matches_the_amended_d30_exactly():
    assert committer_name() == EXPECTED_NAME
    assert committer_email() == EXPECTED_EMAIL


def test_no_file_configures_git_with_the_superseded_address():
    """**Scope is assignment position, not any mention — and the name says so.**

    The first version of this test banned the string `pipeline@users.noreply.github.com` anywhere in
    the repo, and it failed on its own fix: the action's explanatory comment, `PIPELINE.md` and
    `HANDOFF_REHEARSALS.md` all *name* the old address in order to explain why it was wrong. That is
    the same distinction `test_no_stale_tag_name_in_live_config` draws for the freeze tag — **prose
    legitimately describes the past; what must never go stale is the configuration that acts.**

    So this scans for the superseded address in an *assignment* position (`user.email=`, `email:`,
    `EMAIL=`), which is the only place it could change what a commit actually says.
    """
    pattern = re.compile(
        # `user.email="…"`, `email: …`, `GIT_AUTHOR_EMAIL=…` — and, because it is the single most
        # idiomatic way to set an identity, the SPACE-SEPARATED `git config user.email <addr>` form,
        # which carries no `=` or `:` at all and slipped past the first version of this pattern.
        r"""(user\.email|email|EMAIL|GIT_AUTHOR_EMAIL|GIT_COMMITTER_EMAIL)"""
        r"""\s*(?:[:=]\s*|\s+)["']?"""
        r"""pipeline@users\.noreply\.github\.com""",
    )
    offenders = []
    skip_dirs = {".git", "node_modules", "__pycache__", ".pytest_cache", "data", "reports"}
    for path in ROOT.rglob("*"):
        if not path.is_file() or path == Path(__file__):
            continue
        if any(part in skip_dirs for part in path.parts):
            continue
        if path.suffix not in {".yml", ".yaml", ".py", ".md", ".json", ".sh", ".toml", ".cfg"}:
            continue
        try:
            text = path.read_text()
        except (UnicodeDecodeError, OSError):
            continue
        for i, line in enumerate(text.splitlines(), 1):
            if pattern.search(line):
                offenders.append(f"{path.relative_to(ROOT)}:{i}")
    assert not offenders, (
        f"the superseded committer address is configured (not merely mentioned) at: {offenders}. "
        f"An address in assignment position changes what a commit actually says."
    )


def test_that_guard_catches_the_revert_it_exists_for():
    """Proof the scan above can fail — the pattern is matched against the exact line that shipped."""
    pattern = re.compile(
        # `user.email="…"`, `email: …`, `GIT_AUTHOR_EMAIL=…` — and, because it is the single most
        # idiomatic way to set an identity, the SPACE-SEPARATED `git config user.email <addr>` form,
        # which carries no `=` or `:` at all and slipped past the first version of this pattern.
        r"""(user\.email|email|EMAIL|GIT_AUTHOR_EMAIL|GIT_COMMITTER_EMAIL)"""
        r"""\s*(?:[:=]\s*|\s+)["']?"""
        r"""pipeline@users\.noreply\.github\.com""",
    )
    must_catch = [
        # the exact line that shipped
        '            -c user.email="pipeline@users.noreply.github.com" \\',
        # the space-separated `git config` forms — no `=` or `:` anywhere, and the form the first
        # version of this pattern missed entirely
        "git config --global user.email pipeline@users.noreply.github.com",
        'git config user.email "pipeline@users.noreply.github.com"',
        # environment-variable forms
        "GIT_AUTHOR_EMAIL=pipeline@users.noreply.github.com",
        "GIT_COMMITTER_EMAIL: pipeline@users.noreply.github.com",
        "        email: pipeline@users.noreply.github.com",
    ]
    for line in must_catch:
        assert pattern.search(line), f"the guard would not catch a revert of the form: {line!r}"

    must_not_catch = [
        "D30 originally specified `pipeline@users.noreply.github.com`, which resolved to a user.",
        "commits before 2026-08-11 carry pipeline@users.noreply.github.com and link to a stranger",
    ]
    for line in must_not_catch:
        assert not pattern.search(line), (
            f"the guard fires on prose describing the defect, which would make the fix's own "
            f"explanation unwritable: {line!r}"
        )


@pytest.mark.parametrize("doc", ["docs/PIPELINE.md", "docs/HANDOFF_REHEARSALS.md"])
def test_the_operating_docs_name_the_address_the_action_actually_uses(doc):
    """A successor reads these to know what a healthy commit looks like. If they name a different
    address than the action writes, the successor cannot tell a real anomaly from a stale doc."""
    path = ROOT / doc
    if not path.exists():
        pytest.skip(f"{doc} not present (deleted when the season runs cleanly)")
    assert committer_email() in path.read_text(), (
        f"{doc} does not name the committer address the action uses ({committer_email()!r})"
    )
