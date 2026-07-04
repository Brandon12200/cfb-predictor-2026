"""
Factors package for College Football Market Edge Platform.
Contains all factor calculators and the factor registry.
"""

from factors.base_calculator import BaseFactorCalculator

# NOTE: `factor_registry` is intentionally NOT eagerly imported here. Instantiating the registry
# has heavy side effects (it dynamically loads every factor), and importing a leaf module like
# `factors.physical_coefficients` (which the pricer consumes, D15) must not drag that in. Import
# the singleton directly where needed: `from factors.factor_registry import factor_registry`.
__all__ = ['BaseFactorCalculator']
