"""The rounded companion fingerprint: blind to platform noise, sensitive to a real move.

**Why it exists.** The exact fingerprint hashes every bit of every float, so it also measures the
platform's libm. `engine/power_ratings.py` calls `math.exp`, `math.log` and `math.erf`, none of
which glibc guarantees to round correctly, and a runner-image roll on 2026-09-02 moved the hash from
`b9c00a94…` to `496da012…` with the repository byte-identical and the same Python (3.11.16). The
companion hash rounds every float to `ROUNDING_DP` places first, which puts it far below anything
the model can express (spreads in hundredths of a point) and far above double-precision noise.

These two tests bound it from both sides: it must ignore a perturbation ~1e-15 and must notice one
at 1e-4. A rounding that failed the first would not solve the problem; one that failed the second
would hide a real model change, which is far worse.
"""
from __future__ import annotations

import copy
import math

from scripts.slate_fingerprint import ROUNDING_DP, _round_floats, _sha256_of


def _payload() -> dict:
    """A payload shaped like the real one — nested dicts, lists, mixed types, a negative zero."""
    return {
        "volatile_excluded": ["built_at", "generated_at"],
        "placeholder_spread": -3.0,
        "games": {
            "01|CLEMSON@LSU": {
                "confidence": 0.7332,
                "predicted_edge": 0.1403,
                "vegas_spread": -10.6,
                "no_bet": True,
                "prediction_type": "NO_BET",
                "factor_breakdown": {
                    "Altitude": {"activated": False, "value": 0.0, "weighted_value": 0.0},
                    "Sandwich": {"activated": True, "value": 1.0, "weighted_value": 0.0413},
                },
                "history": [1.5, 2.25, -0.125],
            },
            "12|INDIANA@WASHINGTON": {"power_rating_spread": -0.0, "confidence": 0.5},
        },
    }


def _nudge(payload: dict, key: str, delta: float) -> dict:
    """Return a copy with one specific float moved by `delta`.

    `copy.deepcopy`, deliberately not `_round_floats(payload, 15)` — using the function under test
    to build the test's own fixture would make a broken `_round_floats` corrupt both sides equally
    and hide itself.
    """
    out = copy.deepcopy(payload)
    out["games"]["01|CLEMSON@LSU"][key] += delta
    return out


def test_the_rounded_hash_ignores_a_1e_15_perturbation():
    """Platform noise: a change ~1e-15 is a last-ULP difference, not a model change."""
    base = _payload()
    nudged = _nudge(base, "confidence", 1e-15)

    assert nudged["games"]["01|CLEMSON@LSU"]["confidence"] != \
        base["games"]["01|CLEMSON@LSU"]["confidence"], (
        "the perturbation did not survive into the payload — this test would pass vacuously"
    )
    assert _sha256_of(base) != _sha256_of(nudged), (
        "the EXACT hash must see the perturbation; if it does not, this test proves nothing about "
        "the rounded one"
    )
    assert _sha256_of(_round_floats(base)) == _sha256_of(_round_floats(nudged)), (
        f"the {ROUNDING_DP}dp hash moved on a 1e-15 perturbation — it is still measuring the "
        "platform, which is the defect it exists to fix"
    )


def test_the_rounded_hash_changes_under_a_1e_4_perturbation():
    """A real move: 1e-4 of a point is far below anything meaningful and must still be caught."""
    base = _payload()
    nudged = _nudge(base, "predicted_edge", 1e-4)

    assert _sha256_of(_round_floats(base)) != _sha256_of(_round_floats(nudged)), (
        f"the {ROUNDING_DP}dp hash did NOT move on a 1e-4 perturbation — rounding that coarse would "
        "hide a genuine model change, which is worse than the platform sensitivity it replaces"
    )


def test_negative_zero_is_normalised():
    """`-0.0` and `0.0` are the same number and must not hash differently.

    The pinned vehicle carries exactly one negative zero, so this is a live case: without
    normalisation a platform that computes `+0.0` there would move the rounded hash with the model
    unchanged, defeating the point of having it.
    """
    neg, pos = _payload(), _payload()
    assert math.copysign(1.0, neg["games"]["12|INDIANA@WASHINGTON"]["power_rating_spread"]) < 0
    pos["games"]["12|INDIANA@WASHINGTON"]["power_rating_spread"] = 0.0

    assert _sha256_of(neg) != _sha256_of(pos), "json.dumps should render -0.0 and 0.0 differently"
    assert _sha256_of(_round_floats(neg)) == _sha256_of(_round_floats(pos)), (
        "the rounded hash must treat -0.0 and 0.0 as the same value"
    )


def test_rounding_leaves_non_floats_alone():
    """Ints, bools and strings must pass through untouched — bools are ints and must not become
    floats, and a silently coerced type would change the hash for a non-numeric reason."""
    src = {"i": 3, "b": True, "f": 1.0, "s": "x", "n": None, "lst": [1, 2.5, False]}
    out = _round_floats(src)
    assert out["i"] == 3 and isinstance(out["i"], int) and not isinstance(out["i"], bool)
    assert out["b"] is True and out["s"] == "x" and out["n"] is None
    assert out["lst"][0] == 1 and out["lst"][2] is False
    # Values, not just types: a rounding that preserved `float`-ness while altering the number
    # would satisfy an isinstance-only check and still change the hash.
    assert out["f"] == 1.0 and isinstance(out["f"], float)
    assert out["lst"][1] == 2.5


def test_the_real_fingerprint_reports_both_hashes():
    """The gate's classification depends on both being present and different keys."""
    from scripts.slate_fingerprint import fingerprint

    fp = fingerprint()
    assert set(fp) == {"n_games", "sha256", "sha256_rounded"}
    assert len(fp["sha256"]) == 64 and len(fp["sha256_rounded"]) == 64
    assert fp["sha256"] != fp["sha256_rounded"], (
        "the two hashes are over differently-serialised payloads and should not collide"
    )
