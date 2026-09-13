"""Tripwires on the two assumptions D41's rounded gate rests on.

D41 moved the behavioural fingerprint gate to a 10-dp-rounded hash. Review found two properties of
the payload that the method silently depends on, both true when measured on 2026-09-04 and both
enforced by nothing until now:

1. **No NaN or infinity.** `round(nan, 10)` is `nan` on every platform, so a NaN propagates
   identically everywhere and would HIDE a change rather than expose one. Infinity is the same shape.
2. **No number reaches `json.dumps` as a string, and nothing reaches its `default=str`.** A float that
   arrives stringified bypasses `_round_floats` entirely and puts raw platform bits back into the
   hash — recreating exactly the image-dependence D41 removed. An object `json.dumps` cannot
   serialise would be stringified by `default=str`, with the same effect.

Both are asserted here against the real payload. The synthetic tests prove each tripwire fires, so a
walker that silently stopped looking would fail rather than pass.
"""
from __future__ import annotations

import math

import pytest

from scripts.slate_fingerprint import build_payload

_JSON_NATIVE = (dict, list, str, int, float, bool, type(None))


def _walk(obj, path="$"):
    """Yield (path, problem) for every value that breaks one of the two assumptions."""
    if isinstance(obj, bool) or obj is None:
        return
    if isinstance(obj, float):
        if math.isnan(obj):
            yield path, "NaN"
        elif math.isinf(obj):
            yield path, "infinity"
        return
    if isinstance(obj, int):
        return
    if isinstance(obj, str):
        try:
            float(obj)
        except ValueError:
            return
        yield path, f"numeric string {obj!r}"
        return
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from _walk(v, f"{path}.{k}")
        return
    if isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _walk(v, f"{path}[{i}]")
        return
    if not isinstance(obj, _JSON_NATIVE):
        yield path, f"non-JSON-native {type(obj).__name__} — would reach default=str"


def _count_floats(obj) -> int:
    if isinstance(obj, bool):
        return 0
    if isinstance(obj, float):
        return 1
    if isinstance(obj, dict):
        return sum(_count_floats(v) for v in obj.values())
    if isinstance(obj, list):
        return sum(_count_floats(v) for v in obj)
    return 0


@pytest.fixture(scope="module")
def payload():
    return build_payload()


def test_the_walk_actually_reaches_the_payload(payload):
    """Guard the guard. An empty or truncated payload would pass both tripwires vacuously."""
    assert len(payload["games"]) == 338
    assert _count_floats(payload) > 10_000, "the walker saw almost no floats — it is not looking"


def test_the_payload_holds_no_nan_or_infinity(payload):
    bad = [(p, why) for p, why in _walk(payload) if why in ("NaN", "infinity")]
    assert not bad, (
        "the fingerprint payload contains NaN/infinity, which rounds to itself on every platform "
        f"and would hide a model change behind an unchanged hash: {bad[:5]}"
    )


def test_no_number_reaches_the_hash_as_a_string_or_via_default_str(payload):
    bad = [(p, why) for p, why in _walk(payload) if why not in ("NaN", "infinity")]
    assert not bad, (
        "a number reaches json.dumps as a string (or an object reaches default=str), bypassing "
        f"_round_floats and restoring platform bits to the hash D41 made image-independent: {bad[:5]}"
    )


@pytest.mark.parametrize("value, expected", [
    (float("nan"), "NaN"),
    (float("inf"), "infinity"),
    (float("-inf"), "infinity"),
    ("0.1403", "numeric string '0.1403'"),
    ("-7.5", "numeric string '-7.5'"),
])
def test_each_tripwire_fires_on_a_synthetic_payload(value, expected):
    synthetic = {"games": {"01|A@B": {"confidence": 0.8, "edge_size": value}}}
    assert list(_walk(synthetic)) == [("$.games.01|A@B.edge_size", expected)]


def test_a_non_json_native_object_is_caught():
    class Opaque:
        pass
    synthetic = {"games": {"01|A@B": {"model": Opaque()}}}
    [(path, why)] = _walk(synthetic)
    assert path == "$.games.01|A@B.model" and "default=str" in why


def test_ordinary_values_are_not_flagged():
    """The other direction: team names, keys, ints and bools must not trip a false alarm."""
    synthetic = {"games": {"01|CAL@SYRACUSE": {"home_team": "SYRACUSE", "week": 2, "no_bet": True,
                                               "confidence": 0.913, "prediction_type": "NO_BET",
                                               "factors": ["Altitude", "Sandwich"], "note": None}}}
    assert list(_walk(synthetic)) == []
