"""Read a workflow's `on:` triggers out of its text, without a YAML dependency.

This project parses workflow YAML with regex on purpose: it is deliberately minimal-dependency
(SPEC §13) and D24 declined a YAML parser. That is a fine trade while every assertion is a
line-level fact, but the season stop (D48 item 1) changes what is being asserted. Before the stop the
rule was *the crons here equal `season.json`'s*, and a cron the parser read sloppily still failed
that comparison. After the stop the expected set is **empty**, so the rule becomes *no cron exists* —
and a parser that cannot see a cron now reports exactly what the guard wants to hear.

Two shapes have already been found this way, both by review rather than by the tests:

1. A cron with an **unquoted** value. ``- cron: 1 2 * * 3`` is valid YAML and a live schedule, and
   the quoted-value regex that reads crons for the drift comparison cannot see it.
2. A **column-0 comment inside the block**. Ending the `on:` mapping at the first non-whitespace
   character in column 0 ends it at a ``# note`` line too, hiding anything below.

So the block is read once, here, and both guards (``tests/test_workflow_schedules.py`` and
``scripts/verify_phase_5.py``) call it. One parser with tests against mutations beats two copies that
have to agree.

Offline, pure text in / text out: every function takes the file's contents, so a guard can assert
against a mutation it builds in memory rather than against a file it has to write.
"""

from __future__ import annotations

import re

#: A cron whose value is quoted — the only form that can be compared against `season.json`, because
#: it is the only form whose value is unambiguously delimited.
QUOTED_CRON = re.compile(r'^\s*-\s*cron:\s*["\'](?P<cron>[^"\']+)["\']', re.M)

#: The top-level `on:` key. Quoted (`"on":`) because YAML 1.1 reads a bare `on` as a boolean and
#: some authors quote it for that reason; trailing content is captured, because `on: {schedule: …}`
#: puts the whole mapping on this one line.
_ON_KEY = re.compile(r'^["\']?on["\']?[ \t]*:(?P<inline>.*)$', re.M)

#: Keys that make a workflow fire without anybody asking it to. `schedule` is the cron trigger;
#: `cron` is the key under it, checked separately so a malformed block is still caught.
UNATTENDED_KEYS = ("schedule", "cron")

#: A mapping key inside the `on:` block, with the indentation that says which level it sits at.
_BLOCK_KEY = re.compile(r"^(?P<indent>[ \t]+)(?P<key>[A-Za-z_][\w-]*)[ \t]*:", re.M)


def norm_cron(cron: str) -> str:
    """Collapse whitespace so ``23  0 * * 0`` and ``23 0 * * 0`` compare equal."""
    return " ".join(cron.split())


def quoted_crons(text: str) -> set[str]:
    """Every quoted cron value in the file, normalized."""
    return {norm_cron(m.group("cron")) for m in QUOTED_CRON.finditer(text)}


def on_block(text: str) -> str:
    """Everything under the workflow's top-level ``on:`` key, with comment lines removed.

    Scoped to the `on:` mapping so that `github.event.schedule` plumbing elsewhere in the file is not
    mistaken for a trigger, and comment-stripped because prose *about* a setting is not the setting —
    a confusion that has cost this project four defects.

    Raises:
        ValueError: if the file has no top-level ``on:`` key at all. Failing closed is deliberate:
            a workflow whose triggers cannot be located must not read as a workflow with none.
    """
    m = _ON_KEY.search(text)
    if m is None:
        raise ValueError("no top-level `on:` key found")
    out = [m.group("inline")]
    for line in text[m.end() :].splitlines():
        if line.lstrip().startswith("#"):
            continue  # a comment inside the block neither adds a trigger nor ends the block
        if line.strip() and not line[0].isspace():
            break  # a key in column 0 is the next top-level mapping
        out.append(line)
    return "\n".join(out)


def unattended_triggers(text: str) -> list[str]:
    """Which of `UNATTENDED_KEYS` appear in the `on:` block — empty means no cron, in any form."""
    block = on_block(text)
    return [key for key in UNATTENDED_KEYS if key in block]


def on_keys(text: str) -> list[str]:
    """The trigger names declared at the top level of the `on:` block, in file order.

    This is the positive form of the check, and the stronger one: `schedule` is not the only key
    that fires a workflow without anybody asking — `push`, `workflow_run` and `repository_dispatch`
    all do — so a guard that names what IS allowed outlives a list of what is not.

    Block style only. A flow-style mapping (`on: {schedule: ...}`) is reported as the single key
    ``"<flow>"``, so an exact-set assertion fails on it rather than quietly parsing it as nothing;
    `unattended_triggers` is what reads a cron out of that shape.
    """
    block = on_block(text)
    if "{" in block:
        return ["<flow>"]
    matches = list(_BLOCK_KEY.finditer(block))
    if not matches:
        return []
    top = min(len(m.group("indent")) for m in matches)
    return [m.group("key") for m in matches if len(m.group("indent")) == top]
