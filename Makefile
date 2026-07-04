.PHONY: help install test lint predict grade report verify-phase-0 verify-phase-1 verify-phase-2 verify-phase-3

PY ?= python

# Genuinely new logic authored in Phase 0. cli/ is lifted-and-shifted legacy
# (rewritten in Phase 4.5, SPEC 9), so it is not held to strict lint here.
LINT_PATHS := main.py data/team_registry.py data/data_manager.py data/schedule_intel.py data/odds_budget.py data/clients data/normalize data/snapshot engine/power_ratings.py engine/matchup_pricer.py analytics/projections.py analytics/calibration_evidence.py scripts/update_ratings.py scripts/build_projections.py scripts/build_calibration_evidence.py scripts/grading.py scripts/calculate_accuracy.py scripts/calculate_roi.py scripts/calculate_sharpe.py utils/season_calendar.py tests/conftest.py tests/test_week_inference.py tests/test_cfbd_v2_client.py tests/test_team_registry.py tests/test_registry_reconciliation.py tests/test_odds_client.py tests/test_normalize.py tests/test_snapshot.py tests/test_no_network.py tests/test_market_sentiment.py tests/test_schedule_intel.py tests/test_inspection.py tests/test_lines.py tests/test_power_ratings.py tests/test_matchup_pricer.py tests/test_hypothetical_cli.py tests/test_update_ratings.py tests/test_power_rating_wiring.py tests/test_projections.py tests/test_project_cli.py tests/test_calibration_evidence.py tests/context_factory.py
TYPED_PATHS := data/team_registry.py data/data_manager.py data/schedule_intel.py data/odds_budget.py data/clients/cfbd_v2.py data/clients/odds.py data/normalize data/snapshot engine/power_ratings.py engine/matchup_pricer.py analytics/projections.py analytics/calibration_evidence.py scripts/update_ratings.py scripts/build_projections.py scripts/build_calibration_evidence.py utils/season_calendar.py

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
	@echo "grade: the grading pipeline lands in Phase 5 (SPEC section 10)."

report:
	@echo "report: the analytics report lands in Phase 4 (SPEC section 8)."

verify-phase-0:
	$(PY) scripts/verify_phase_0.py

verify-phase-1:
	$(PY) scripts/verify_phase_1.py

verify-phase-2:
	$(PY) scripts/verify_phase_2.py

verify-phase-3:
	$(PY) scripts/verify_phase_3.py
