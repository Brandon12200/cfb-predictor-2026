"""Suite-level byte-identity pin on the committed schema-v2 golden example.

`verify-phase-3` has carried this check since 3d, but `make test` did not — and that gap bit for
real: the reverse-audit A4 sub-decision raised `predicted_edge` from 2 dp to 4 dp, leaving the
committed golden stale, and the full pytest suite passed anyway. Only `verify-phase-3` caught it.

Regenerating the golden is a normal consequence of a ratified schema change; silently diverging from
it is not. Having the pin in the suite means any change to the prediction-writing path surfaces on
`make test` alone, not only when someone remembers to run the phase target.

Compared minus `VOLATILE` meta (`docs/SCHEMA.md` §3): `model_version` churns per commit until the
freeze tag and `generated_at` is a wall-clock-shaped stamp. Semantics deliberately mirror
`scripts/verify_phase_3.py` so the two gates cannot disagree about what "identical" means.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from analytics.predictions import build_predictions
from data.snapshot.store import FROZEN_VEHICLE, load_frozen_vehicle
from scripts.slate_fingerprint import engine_reads

ROOT = Path(__file__).resolve().parent.parent
GOLDEN = ROOT / "docs" / "examples" / "prediction_schema_v2_2026_week_01.json"

# Mirrors `scripts/verify_phase_3.py:_VOLATILE_META`.
_VOLATILE_META = ("model_version", "generated_at")

pytestmark = pytest.mark.skipif(
    not (GOLDEN.exists() and FROZEN_VEHICLE.exists()),
    reason="requires the pinned gate vehicle and golden example",
)


def _strip_volatile(doc: dict) -> dict:
    doc = json.loads(json.dumps(doc))
    for key in _VOLATILE_META:
        doc.get("meta", {}).pop(key, None)
    return doc


def _canonical(doc: dict) -> str:
    return json.dumps(_strip_volatile(doc), sort_keys=True)


def test_golden_reproduces_byte_identical_from_the_snapshot():
    """The live writer must reproduce the committed golden exactly, minus VOLATILE meta.

    Reads the pinned tag-time vehicle (D29), not `data/snapshots/2026_week_01/`, which the
    Phase-5 pipeline rebuilds. `engine_reads` is required, not decorative: `build_predictions`
    uses its argument for enumeration and prices through the data manager.
    """
    golden = json.loads(GOLDEN.read_text())
    bundle = load_frozen_vehicle()
    with engine_reads(bundle):
        live = build_predictions(
            bundle, week=1, model_version=golden["meta"].get("model_version")
        )
    if _canonical(golden) != _canonical(live):
        g = {r["game_id"]: r for r in golden["predictions"]}
        live_recs = {r["game_id"]: r for r in live["predictions"]}
        diffs = []
        for gid in sorted(set(g) | set(live_recs)):
            gr, lr = g.get(gid, {}), live_recs.get(gid, {})
            for k in sorted(set(gr) | set(lr)):
                if gr.get(k) != lr.get(k):
                    diffs.append(f"  {gid}.{k}: golden={gr.get(k)!r} live={lr.get(k)!r}")
        raise AssertionError(
            "committed golden no longer reproduces from the snapshot. If this follows a RATIFIED "
            "schema/engine change, regenerate it:\n"
            "  python scripts/build_predictions.py --week 1 "
            "--out docs/examples/prediction_schema_v2_2026_week_01.json\n"
            "(preserving the committed `model_version`, which is VOLATILE and excluded here).\n"
            + "\n".join(diffs[:40])
        )


def test_volatile_exclusions_match_verify_phase_3():
    """The suite gate and the phase gate must agree on what 'identical' means."""
    src = (ROOT / "scripts" / "verify_phase_3.py").read_text()
    block = src.split("_VOLATILE_META = (", 1)[1].split(")", 1)[0]
    verify_fields = {tok.strip().strip('"\'') for tok in block.split(",") if tok.strip()}
    assert verify_fields == set(_VOLATILE_META), (
        f"verify-phase-3 excludes {verify_fields}, this test excludes {set(_VOLATILE_META)}"
    )
