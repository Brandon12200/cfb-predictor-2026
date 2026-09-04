"""No `| tee` in any workflow may swallow its command's exit status.

**The defect this pins.** A GitHub `run:` block executes under `bash -e {0}`. In `cmd | tee f` the
pipeline's status is *tee's*, and tee effectively always succeeds — so `-e` never fires and a failing
`cmd` leaves the step green. `freeze-integrity.yml`'s "Behavioural fingerprint" step had exactly this
shape: on 2026-09-02 and 2026-09-03 the fingerprint gate printed `[FAIL]` and `1 CHECK(S) FAILED`,
`make` exited 1, and the job reported **success** both days. The freeze's own alarm was the one check
in that workflow that could not ring.

**Why the test is general rather than a pin on that one line.** Three of the seventeen `| tee` sites
were masking when this was written, and only one of them had fired. A test asserting "the fingerprint
step contains `exit ${PIPESTATUS[0]}`" would have proven that string present and caught neither of the
other two, nor the next one someone adds. This classifies *every* site instead. (HANDOFF §(g).1 warns
that string-presence-in-YAML is not behaviour; the caveat is noted and accepted here, because what is
being asserted **is** a textual property of the run block — the behaviour at stake is bash's pipeline
semantics, which are fixed and not ours to test.)

Three constructs defuse the mask, and all three are in use in this repo:
  * `set -o pipefail` (or `set -euo pipefail`) anywhere in the same run block;
  * a trailing `exit "${PIPESTATUS[0]}"`;
  * capturing `${PIPESTATUS[0]}` into a step output that a later step's `if:` acts on — the
    designed-exit-code pattern (`fetch_lines` 3 = budget refusal, `fetch_results` 3/4, `sp_watch` 2).
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORKFLOW_FILES = sorted((ROOT / ".github" / "workflows").glob("*.yml")) + \
    sorted((ROOT / ".github" / "actions").glob("*/action.yml"))

_PIPEFAIL = re.compile(r"set\s+-[a-zA-Z]*o\s+pipefail|set\s+-o\s+pipefail")
_EXIT_PS = re.compile(r"""exit\s+"?\$\{PIPESTATUS\[0\]\}"?""")
_CAPTURE_PS = re.compile(r"""rc=\$\{PIPESTATUS\[0\]\}""")


def _run_blocks(lines: list[str]) -> list[tuple[int, int]]:
    """(start, end) line indices of every `run:` block, delimited by indentation.

    A line indented no further than the `run:` key ends the block — **including a comment line.**
    A YAML block scalar's content must be indented deeper than its key, so a `#` at or below that
    indent is a sibling comment, not part of the script.

    This once excluded comments, and that was a real hole rather than a harmless one: a comment
    belonging to the *next* step extended the previous step's block, so an unguarded `| tee` could
    be classified safe on the strength of a `pipefail` or `PIPESTATUS` mention in prose that was
    never going to run. This repository comments heavily and quotes those very tokens when
    explaining them — the fix for this defect does it twice — so the shape is not hypothetical here.
    """
    out: list[tuple[int, int]] = []
    for i, ln in enumerate(lines):
        m = re.match(r"^(\s*)run:\s*(\|.*)?$", ln.rstrip())
        if not m:
            continue
        indent = len(m.group(1))
        j = i + 1
        while j < len(lines):
            s = lines[j]
            if s.strip() and (len(s) - len(s.lstrip())) <= indent:
                break
            j += 1
        out.append((i, j))
    return out


def _tee_sites() -> list[tuple[Path, int, str, str]]:
    """(file, 1-based line, verdict, block text) for every `| tee` in every workflow."""
    sites = []
    for f in WORKFLOW_FILES:
        lines = f.read_text().splitlines()
        blocks = _run_blocks(lines)
        for i, ln in enumerate(lines):
            # A YAML comment is not a pipeline. Skipping these is not cosmetic: the comments
            # explaining this very defect quote `| tee`, and counting them made the sweep flag
            # its own documentation.
            if "| tee" not in ln or ln.lstrip().startswith("#"):
                continue
            blk = next(((a, b) for a, b in blocks if a <= i < b), None)
            text = "\n".join(lines[blk[0]:blk[1]]) if blk else ln
            if _PIPEFAIL.search(text):
                verdict = "pipefail"
            elif _EXIT_PS.search(text):
                verdict = "exit-pipestatus"
            elif _CAPTURE_PS.search(text):
                verdict = "captured-rc"
            else:
                verdict = "MASKED"
            sites.append((f, i + 1, verdict, text))
    return sites


def test_the_sweep_actually_finds_the_tee_sites():
    """Guard the guard: if the block parser breaks, every other assertion here passes vacuously."""
    sites = _tee_sites()
    assert len(sites) >= 15, f"expected the workflows' many `| tee` sites, found {len(sites)}"
    assert any("freeze-integrity" in str(f) for f, _, _, _ in sites)


def test_no_tee_pipeline_can_swallow_a_failure():
    masked = [f"{f.relative_to(ROOT)}:{n}" for f, n, v, _ in _tee_sites() if v == "MASKED"]
    assert not masked, (
        "these `| tee` pipelines return tee's exit status, so the command before them can fail "
        "while the step stays green:\n  " + "\n  ".join(masked) +
        "\nAdd `set -euo pipefail` to the run block, or `exit \"${PIPESTATUS[0]}\"` after the "
        "pipeline, or capture `rc=${PIPESTATUS[0]}` and have a later step act on it."
    )


def test_every_captured_rc_has_a_step_that_acts_on_it():
    """`rc=${PIPESTATUS[0]}` only defuses the mask if something downstream reads it."""
    checked = 0
    for f in WORKFLOW_FILES:
        lines = f.read_text().splitlines()
        text = "\n".join(lines)
        for start, end in _run_blocks(lines):
            if not _CAPTURE_PS.search("\n".join(lines[start:end])):
                continue
            # The owning step's `id:` is the nearest one ABOVE this run block, not the first in
            # the file — scanning forward from the top matched an unrelated earlier step.
            step_id = None
            for k in range(start, -1, -1):
                m = re.match(r"^\s*id:\s*(\S+)\s*$", lines[k])
                if m:
                    step_id = m.group(1)
                    break
                if re.match(r"^\s*-\s+name:", lines[k]) and k < start:
                    break
            assert step_id, (
                f"{f.relative_to(ROOT)}:{start + 1}: a run block captures rc=${{PIPESTATUS[0]}} "
                "but its step has no `id:`, so no later step can possibly read it."
            )
            checked += 1
            assert f"steps.{step_id}.outputs.rc" in text, (
                f"{f.relative_to(ROOT)}: step '{step_id}' captures rc from a `| tee` pipeline but "
                f"no later step reads `steps.{step_id}.outputs.rc` — the failure is captured and "
                "then dropped, which masks it just as thoroughly as not capturing it."
            )
    assert checked >= 3, f"expected the known designed-exit-code steps, classified {checked}"


def test_a_following_comment_does_not_extend_the_previous_block(tmp_path):
    """Regression: a comment belonging to the NEXT step must not vouch for the previous one.

    The parser once treated comment lines as non-terminating, so the prose introducing step B
    landed inside step A's block. Because this repository explains a fix by quoting the very
    tokens that defuse it, an unguarded step sitting above such a comment was classified safe on
    the strength of words that never execute. Reproduced here as the minimal shape.
    """
    doc = (
        "jobs:\n"
        "  j:\n"
        "    steps:\n"
        "      - name: A\n"
        "        run: |\n"
        "          python foo.py 2>&1 | tee -a \"$RUNNER_TEMP/pipeline.log\"\n"
        "\n"
        "      # Prose for the NEXT step that happens to mention set -euo pipefail\n"
        "      # and exit \"${PIPESTATUS[0]}\" while explaining them.\n"
        "      - name: B\n"
        "        run: |\n"
        "          set -euo pipefail\n"
        "          python bar.py 2>&1 | tee -a \"$RUNNER_TEMP/pipeline.log\"\n"
    )
    f = tmp_path / "wf.yml"
    f.write_text(doc)
    lines = doc.splitlines()
    blocks = _run_blocks(lines)

    a_start = next(i for i, ln in enumerate(lines) if ln.strip() == "python foo.py 2>&1 | tee -a \"$RUNNER_TEMP/pipeline.log\"")
    a_block = next((s, e) for s, e in blocks if s <= a_start < e)
    a_text = "\n".join(lines[a_block[0]:a_block[1]])

    assert "set -euo pipefail" not in a_text and "PIPESTATUS" not in a_text, (
        "step A's block absorbed step B's comment — an unguarded `| tee` would be reported safe "
        f"on the strength of prose. Block captured:\n{a_text}"
    )


def test_the_fingerprint_step_is_guarded():
    """The specific regression: freeze-integrity's fingerprint step reported success on a [FAIL]."""
    text = (ROOT / ".github" / "workflows" / "freeze-integrity.yml").read_text()
    block = text.split("- name: Behavioural fingerprint", 1)
    assert len(block) == 2, "the 'Behavioural fingerprint' step is gone or was renamed"
    step = block[1].split("- name:", 1)[0]
    assert "| tee" in step and _EXIT_PS.search(step), (
        "freeze-integrity's fingerprint step must propagate the make exit code — without it a "
        "[FAIL] from verify-phase-3 reports as a green job (observed 2026-09-02 and 2026-09-03)."
    )
