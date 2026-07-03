.PHONY: help install test lint predict grade report verify-phase-0 verify-phase-1

PY ?= python

# Genuinely new logic authored in Phase 0. cli/ is lifted-and-shifted legacy
# (rewritten in Phase 4.5, SPEC 9), so it is not held to strict lint here.
LINT_PATHS := main.py data/team_registry.py data/data_manager.py data/clients data/normalize data/snapshot utils/season_calendar.py tests/conftest.py tests/test_week_inference.py tests/test_cfbd_v2_client.py tests/test_team_registry.py tests/test_registry_reconciliation.py tests/test_odds_client.py tests/test_normalize.py tests/test_snapshot.py tests/test_no_network.py tests/test_market_sentiment.py tests/context_factory.py
TYPED_PATHS := data/team_registry.py data/data_manager.py data/clients/cfbd_v2.py data/clients/odds.py data/normalize data/snapshot utils/season_calendar.py

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
