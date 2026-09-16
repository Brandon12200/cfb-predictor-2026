"""Replace a file in one step, so a killed run can never leave a truncated artifact.

**The defect this exists to prevent.** `Path.write_text` truncates the file and then writes it. A run
killed in that window — a 20-minute job timeout, a cancelled run, a runner reset — leaves a
half-written file. For an *append-only* artifact that is unrecoverable by design: `data/quota/`'s
ledger is committed by the next `cfb-commit`, so a torn write becomes part of the record, and
`data/lines/`'s store is read by `closing_observation`, by grading, and by the capture preflight,
which turned one torn write into every remaining capture of that week failing before it fetched.

One copy, shared by every writer of a durable artifact. Two copies of a guard is how two guards
drift apart (D25.4).

Identical input still produces identical bytes: the same string is written, so the append-only hooks
and `tests/test_golden_byte_identity.py` are unaffected.
"""
from __future__ import annotations

import os
from pathlib import Path


def write_text_atomic(path: Path, text: str) -> None:
    """Write ``text`` to ``path`` via a temp file in the SAME directory, then `os.replace`.

    Same directory because `os.replace` is only atomic within one filesystem. The temp name starts
    with a dot and ends in `.tmp`, which `.gitignore` already excludes, so a hard kill (SIGKILL,
    where the `finally` never runs) cannot leave anything committable behind.
    """
    tmp = path.with_name(f".{path.name}.tmp")
    try:
        tmp.write_text(text)
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)
