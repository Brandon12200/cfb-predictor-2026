"""Model-version provenance helper (Phase 3d) — freeze-exempt.

`model_version()` returns the git identifier of the model that produced a prediction
(SPEC §7 item 6). It is stamped at WRITE time by the prediction writer, never inside the
frozen engine, so the engine stays a pure function of the snapshot. Before the
``v2026-frozen`` tag exists it returns the ``git describe`` fallback (nearest tag or short
commit, ``-dirty`` when the tree is modified). **After the tag it does NOT collapse to a bare
``v2026-frozen``** — `git describe` returns the bare tag only at the tagged commit, so every
freeze-exempt commit widens it to ``v2026-frozen-N-g<sha>`` (D34). That is the better provenance,
because it names the exact tree that produced the claim; it is also why anything *displaying* a
"frozen tag" must use `frozen_tag()`, not this. Because the value changes per commit,
``model_version`` is a VOLATILE field for the reproducibility / golden-file comparison
(see ``docs/SCHEMA.md``).
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


def _git(*args: str) -> str | None:
    try:
        out = subprocess.run(["git", "-C", str(_ROOT), *args],
                             capture_output=True, text=True, timeout=5)
        return out.stdout.strip() if out.returncode == 0 else None
    except Exception:  # noqa: BLE001
        return None


def frozen_tag() -> str | None:
    """The nearest tag itself — ``v2026-frozen``, never the ``-N-g<sha>`` build stamp.

    Distinct from `model_version()` on purpose: a display that labels
    ``v2026-frozen-15-g8715415-dirty`` as "the frozen tag" is simply wrong, and reads as though the
    freeze had moved.
    """
    return _git("describe", "--tags", "--abbrev=0")


def frozen_tree_hashes(tag: str, trees: tuple[str, ...] = ("factors", "engine")
                       ) -> dict[str, tuple[str | None, str | None]]:
    """``{tree: (HEAD hash, tag hash)}`` for the frozen directories.

    The single primitive behind every "is the model still frozen?" answer — the pipeline preflight,
    the daily freeze-integrity job and `cfb status` all read it, so they cannot drift apart (the
    D25.4 lesson: a second copy of a guard is how two guards disagree). A `None` on either side
    means the ref could not be resolved, which on a runner means the tag was not fetched.
    """
    return {t: (_git("rev-parse", f"HEAD:{t}"), _git("rev-parse", f"{tag}:{t}")) for t in trees}


def frozen_trees_match(tag: str, trees: tuple[str, ...] = ("factors", "engine")) -> bool | None:
    """True/False, or None when the comparison could not be made (tag or git unavailable)."""
    pairs = frozen_tree_hashes(tag, trees)
    if any(h is None or t is None for h, t in pairs.values()):
        return None
    return all(h == t for h, t in pairs.values())
