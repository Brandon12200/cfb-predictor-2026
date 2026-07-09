"""Model-version provenance helper (Phase 3d) — freeze-exempt.

`model_version()` returns the git identifier of the model that produced a prediction
(SPEC §7 item 6). It is stamped at WRITE time by the prediction writer, never inside the
frozen engine, so the engine stays a pure function of the snapshot. Before the
``v2026-frozen`` tag exists it returns the ``git describe`` fallback (nearest tag or short
commit, ``-dirty`` when the tree is modified); once the tag is cut it resolves to
``v2026-frozen``. Because the value changes per commit until the freeze, ``model_version``
is a VOLATILE field for the reproducibility / golden-file comparison (see ``docs/SCHEMA.md``).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent


def model_version() -> str:
    """``git describe --tags --always --dirty``; ``"unknown"`` when git is unavailable."""
    try:
        out = subprocess.run(
            ["git", "-C", str(_ROOT), "describe", "--tags", "--always", "--dirty"],
            capture_output=True, text=True, timeout=5,
        )
        val = out.stdout.strip()
        return val if out.returncode == 0 and val else "unknown"
    except Exception:  # noqa: BLE001 — provenance stamp must never break a prediction write
        return "unknown"
