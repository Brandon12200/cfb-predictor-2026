.PHONY: help install test lint predict grade report verify-phase-0 verify-phase-1 verify-phase-2 verify-phase-3 verify-phase-4 verify-phase-4-5

PY ?= python

# Genuinely new logic authored in Phase 0. cli/ is lifted-and-shifted legacy
# (rewritten in Phase 4.5, SPEC 9), so it is not held to strict lint here.
LINT_PATHS := main.py data/team_registry.py data/data_manager.py data/schedule_intel.py data/odds_budget.py data/clients data/normalize data/snapshot engine/power_ratings.py engine/matchup_pricer.py analytics/projections.py analytics/calibration_evidence.py scripts/update_ratings.py scripts/build_projections.py scripts/build_calibration_evidence.py scripts/grading.py scripts/calculate_accuracy.py scripts/calculate_roi.py scripts/calculate_sharpe.py utils/season_calendar.py tests/conftest.py tests/test_week_inference.py tests/test_cfbd_v2_client.py tests/test_team_registry.py tests/test_registry_reconciliation.py tests/test_odds_client.py tests/test_normalize.py tests/test_snapshot.py tests/test_no_network.py tests/test_market_sentiment.py tests/test_schedule_intel.py tests/test_inspection.py tests/test_lines.py tests/test_power_ratings.py tests/test_matchup_pricer.py tests/test_hypothetical_cli.py tests/test_update_ratings.py tests/test_power_rating_wiring.py tests/test_projections.py tests/test_project_cli.py tests/test_calibration_evidence.py tests/context_factory.py factors/physical_coefficients.py factors/scheduling_fatigue.py tests/test_physical_coefficients.py tests/test_physical_factors.py tests/test_phase3c.py utils/version.py utils/prediction_schema.py analytics/predictions.py scripts/build_predictions.py tests/test_phase3d.py analytics/grading.py analytics/kpis.py analytics/calibration.py analytics/attribution.py analytics/selectivity.py analytics/join.py analytics/reports.py scripts/grade.py scripts/build_reports.py tests/test_phase4.py cli/cfb.py cli/output.py tests/test_cfb_cli.py tests/test_artifact_write_guard.py tests/test_golden_byte_identity.py
TYPED_PATHS := data/team_registry.py data/data_manager.py data/schedule_intel.py data/odds_budget.py data/clients/cfbd_v2.py data/clients/odds.py data/normalize data/snapshot engine/power_ratings.py engine/matchup_pricer.py analytics/projections.py analytics/calibration_evidence.py scripts/update_ratings.py scripts/build_projections.py scripts/build_calibration_evidence.py utils/season_calendar.py factors/physical_coefficients.py factors/scheduling_fatigue.py utils/version.py utils/prediction_schema.py analytics/predictions.py scripts/build_predictions.py analytics/grading.py analytics/kpis.py analytics/calibration.py analytics/attribution.py analytics/selectivity.py analytics/join.py analytics/reports.py scripts/grade.py scripts/build_reports.py cli/cfb.py cli/output.py main.py

help:
	@echo "targets: install  test  lint  predict  grade  report  verify-phase-0  verify-phase-1"

install:
	$(PY) -m pip install -e ".[dev]"

test:
	$(PY) -m pytest

lint:
	ruff check $(LINT_PATHS)
	mypy $(TYPED_PATHS)

predict:
	$(PY) main.py $(ARGS)

grade:
	$(PY) scripts/grade.py $(ARGS)

report:
	$(PY) scripts/build_reports.py $(ARGS)

verify-phase-0:
	$(PY) scripts/verify_phase_0.py

verify-phase-1:
	$(PY) scripts/verify_phase_1.py

verify-phase-2:
	$(PY) scripts/verify_phase_2.py

verify-phase-3:
	$(PY) scripts/verify_phase_3.py

verify-phase-4:
	$(PY) scripts/verify_phase_4.py

verify-phase-4-5:
	$(PY) scripts/verify_phase_4_5.py
