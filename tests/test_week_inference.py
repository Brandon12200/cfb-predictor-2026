"""Regression tests for date->week inference (SPEC 4.4 / decision D1).

Proves the fix for the silent week-1 default: omitting the week resolves to the
same value a correct explicit --week supplies, and an out-of-season date
hard-fails instead of silently defaulting.
"""

import unittest
from datetime import date

from utils.season_calendar import (
    WeekInferenceError,
    infer_week_for_date,
    load_calendar,
    resolve_week,
)

# Small synthetic calendar so tests don't depend on the exact production dates.
# Post-D8: no Week 0 — the season opens at week 1 (CFBD numbering).
SYNTHETIC = {
    "season": 2026,
    "weeks": {
        "1": {"start": "2026-08-29", "end": "2026-09-07"},
        "2": {"start": "2026-09-08", "end": "2026-09-13"},
        "3": {"start": "2026-09-14", "end": "2026-09-20"},
    },
}


class TestWeekInference(unittest.TestCase):
    def test_infers_week_within_range(self):
        self.assertEqual(infer_week_for_date(date(2026, 8, 29), SYNTHETIC), 1)
        self.assertEqual(infer_week_for_date(date(2026, 9, 10), SYNTHETIC), 2)
        self.assertEqual(infer_week_for_date(date(2026, 9, 16), SYNTHETIC), 3)

    def test_range_boundaries_are_inclusive(self):
        # Week 1 spans 08-29 .. 09-07 inclusive on both ends.
        self.assertEqual(infer_week_for_date(date(2026, 8, 29), SYNTHETIC), 1)
        self.assertEqual(infer_week_for_date(date(2026, 9, 7), SYNTHETIC), 1)

    def test_omitted_week_equals_explicit_week(self):
        """The core regression: inferred == explicit-correct for the same date."""
        for target_week, sample_day in [(1, date(2026, 9, 3)),
                                        (2, date(2026, 9, 10)),
                                        (3, date(2026, 9, 16))]:
            inferred = resolve_week(None, today=sample_day, calendar=SYNTHETIC)
            explicit = resolve_week(target_week, today=sample_day, calendar=SYNTHETIC)
            self.assertEqual(inferred, target_week)
            self.assertEqual(inferred, explicit)

    def test_explicit_week_overrides_inference(self):
        # An explicit week is returned as-is regardless of the date.
        self.assertEqual(resolve_week(7, today=date(2026, 9, 3), calendar=SYNTHETIC), 7)

    def test_out_of_season_hard_fails(self):
        # Offseason (e.g., July) must raise, never silently default to week 1.
        with self.assertRaises(WeekInferenceError):
            infer_week_for_date(date(2026, 7, 2), SYNTHETIC)
        with self.assertRaises(WeekInferenceError):
            resolve_week(None, today=date(2027, 3, 1), calendar=SYNTHETIC)

    def test_production_calendar_matches_cfbd_no_week_zero(self):
        """Post-D8 the production calendar is regenerated from CFBD: no Week 0, the
        opener is week 1 (2026-08-29), and weeks are contiguous."""
        cal = load_calendar()
        self.assertEqual(cal["season"], 2026)
        weeks = cal["weeks"]
        self.assertNotIn("0", weeks)  # D8: Week 0 abolished for 2026
        self.assertEqual(weeks["1"]["start"], "2026-08-29")  # opener is week 1
        # Ranges are contiguous and ordered (no gaps/overlaps).
        ordered = sorted(weeks.items(), key=lambda kv: int(kv[0]))
        for (_, prev), (_, cur) in zip(ordered, ordered[1:], strict=False):
            prev_end = date.fromisoformat(prev["end"])
            cur_start = date.fromisoformat(cur["start"])
            self.assertEqual((cur_start - prev_end).days, 1)
        # The Aug 29 opener resolves to week 1 (was Week 0 pre-D8).
        self.assertEqual(infer_week_for_date(date(2026, 8, 29), cal), 1)


if __name__ == "__main__":
    unittest.main()
