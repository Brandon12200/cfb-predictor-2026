"""Freeze-exempt analytics (SPEC §6.5 projections now; §8 CLV/calibration/reports later).

Deliberately OUTSIDE frozen `engine/`: this code is cut-first / freeze-exempt (§15) and must
stay editable after `v2026-frozen`. It consumes the frozen model (`engine.matchup_pricer`,
`engine.power_ratings`) but is not part of it.
"""
