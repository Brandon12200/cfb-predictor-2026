"""
Factor registry for College Football Market Edge Platform.
Manages dynamic loading, weight distribution, and execution of all factors.
"""

import logging
from typing import Dict, List, Any, Optional, Type
from importlib import import_module
import inspect

from config import config
from factors.base_calculator import BaseFactorCalculator, FactorType, FactorConfidence

SITUATIONAL_CATEGORY = "situational_context"
PHYSICAL_CATEGORY = "physical"


def _sign(x: Optional[float]) -> int:
    """-1 / 0 / +1 sign of a spread-space value (None -> 0)."""
    if x is None or x == 0:
        return 0
    return 1 if x > 0 else -1


def confirm_situational(factor_results: List[Dict[str, Any]],
                        base_gap: Optional[float]) -> set:
    """L2 confirming-signal gate (SPEC §7.3, D15).

    Situational signals are motivational hypotheses, not team-quality facts — the L2 lesson is
    to raise the bar on them. Given every factor's result dict for one matchup and the
    model-vs-market **BASE** gap (D15 — the base gap only, NEVER the total gap, so a factor is
    never confirmed by a gap containing its own schedule signal), return the set of situational
    factor NAMES that are UNCONFIRMED and must not contribute.

    `base_gap` MUST be in the **factor sign convention: positive favours home**. The engine injects
    `vegas − base_spread` as `context['base_gap_favors_home']` — NOT the diagnostic `base_spread −
    vegas`, which is inverted (a more-negative model spread means the model favours home MORE).
    Every factor `value` uses the same positive-favours-home convention, so "agree in direction"
    == "same sign".

    An activated situational factor is CONFIRMED iff its direction agrees with either:
      (a) the base gap (the model's team-quality disagreement with the market), or
      (b) at least one activated physical factor.
    A situational factor with no directional corroboration is a solo guess and is dropped.
    """
    physical_signs = {
        _sign(fr.get('value'))
        for fr in factor_results
        if fr.get('activated') and fr.get('category') == PHYSICAL_CATEGORY
        and _sign(fr.get('value')) != 0
    }
    gap_sign = _sign(base_gap)
    unconfirmed = set()
    for fr in factor_results:
        if not fr.get('activated') or fr.get('category') != SITUATIONAL_CATEGORY:
            continue
        s = _sign(fr.get('value'))
        if s == 0:
            continue
        confirmed = (s == gap_sign) or (s in physical_signs)
        if not confirmed:
            unconfirmed.add(fr.get('factor_name'))
    return unconfirmed


class FactorRegistry:
    """
    Registry for managing and executing all prediction factors.
    
    Features:
    - Dynamic loading of factor calculators
    - Weight normalization and validation
    - Factor execution with error handling
    - Performance tracking and monitoring
    """
    
    def __init__(self):
        """Initialize factor registry."""
        self.factors: Dict[str, BaseFactorCalculator] = {}
        
        # Reverse-audit A5: `category_weights` (config's 60/30/10) and `legacy_category_weights`
        # (40/40/20) were removed here. They were keyed on 'primary'/'secondary'/'modifier' while
        # live factors carry the 3b.3 taxonomy categories ('physical', 'situational_context',
        # 'coaching_edge', 'matchup', 'momentum_factors', 'market') — ZERO key overlap, so the
        # validator they fed reported `valid: False` on every run it was ever called. Neither map
        # reached scoring; their only consumers were the dead diagnostics retired with the A2
        # cluster. The per-factor `weight` on each registered factor is the single source of truth.

        # Weighting strategy configuration
        self.use_dynamic_weights = True  # Enable confidence-based dynamic weighting
        self.apply_thresholds = True     # Enable threshold filtering
        self.hierarchical_mode = True    # Enable primary/secondary hierarchy
        
        # Performance tracking
        self.execution_stats = {
            'total_calculations': 0,
            'successful_calculations': 0,
            'failed_calculations': 0,
            'factor_performance': {}
        }
        
        # Logging
        self.logger = logging.getLogger(__name__)
        
        # Load all factors
        self._load_all_factors()
        
        # Configure factor types and thresholds
        self._configure_factor_hierarchy()
        
        # Validate weights
        self._validate_and_normalize_weights()
        
        self.logger.info(f"Factor registry initialized with {len(self.factors)} factors")
    
    def _load_all_factors(self) -> None:
        """
        Dynamically load all factor calculator classes from the factors directory.
        
        This modular approach automatically discovers and loads any factor that:
        1. Is in a .py file in the factors directory
        2. Contains a class that inherits from BaseFactorCalculator
        3. Has a proper __init__ method
        
        This allows new factors to be added simply by creating a new file,
        without modifying the registry.
        """
        import os
        import importlib
        import inspect
        
        factors_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Iterate through all Python files in the factors directory
        for filename in os.listdir(factors_dir):
            if filename.endswith('.py') and not filename.startswith('__') and filename != 'base_calculator.py' and filename != 'factor_registry.py':
                module_name = filename[:-3]  # Remove .py extension
                
                try:
                    # Dynamically import the module
                    module = importlib.import_module(f'factors.{module_name}')
                    
                    # Find all classes in the module that inherit from BaseFactorCalculator
                    for name, obj in inspect.getmembers(module):
                        if inspect.isclass(obj) and issubclass(obj, BaseFactorCalculator) and obj != BaseFactorCalculator:
                            try:
                                # Instantiate the factor
                                factor_instance = obj()
                                self.factors[factor_instance.name] = factor_instance
                                self.logger.debug(f"Loaded factor: {factor_instance.name} from {module_name}.py")
                            except Exception as e:
                                self.logger.warning(f"Could not instantiate {name} from {module_name}: {e}")
                                
                except ImportError as e:
                    self.logger.warning(f"Could not import module {module_name}: {e}")
                except Exception as e:
                    self.logger.error(f"Error loading factors from {module_name}: {e}")
        
        self.logger.info(f"Dynamically loaded {len(self.factors)} factors")
    
    
    def _configure_factor_hierarchy(self) -> None:
        """Configure factor types and thresholds for contrarian system."""
        # PRIMARY factors (60% weight) - Direct contrarian signals
        # These are the factors that most contradict public perception
        primary_factors = {
            'HeadToHeadRecord': {'threshold': 1.0, 'max_impact': 5.0},      # 20% of total
            # DesperationIndex threshold 2.0 -> 1.0 (Phase 3c, PROPOSED — CALIBRATION_LOG 3c).
            # The old 2.0 equalled the factor's max output (±2.0), so it could only fire at exact
            # saturation (never, in practice). 1.0 lets a genuine half-max desperation differential
            # fire, and the L2 confirmation gate (confirm_situational) supplies the real selectivity.
            'DesperationIndex': {'threshold': 1.0, 'max_impact': 7.0},      # 20% of total
            # 'SchedulingFatigue': {'threshold': 1.5, 'max_impact': 3.5},   # 20% of total (to be added)
        }
        
        # SECONDARY factors (30% weight) - Supporting evidence
        # These provide additional context but aren't primary contrarian signals
        secondary_factors = {
            'ExperienceDifferential': {'threshold': 1.0, 'max_impact': 3.0},
            'PressureSituation': {'threshold': 0.75, 'max_impact': 3.0},
            'RevengeGame': {'threshold': 1.5, 'max_impact': 4.0},
            # 'LookaheadSandwich' removed (reverse-audit A3, same class as the variance_detector
            # map): the factor was retired in 3b.6, so this override matched nothing. The live
            # `Sandwich` factor is deliberately NOT added here — it keeps the physical layer's
            # own ratified activation threshold (3b), which this hierarchy must not override.
            'PointDifferentialTrends': {'threshold': 0.75, 'max_impact': 3.0},
            'CloseGamePerformance': {'threshold': 0.5, 'max_impact': 2.0},
            # 'StyleMismatch': {'threshold': 1.0, 'max_impact': 4.0},       # 15% of total (to be added)
        }
        
        # MODIFIER factors (10% weight) - Situational adjustments
        # These amplify or dampen predictions based on market conditions
        # 'MarketSentiment': {'threshold': 0.5, 'max_impact': 2.5},        # 10% of total (to be added)
        
        # Configure each factor
        for factor_name, factor in self.factors.items():
            if factor_name in primary_factors:
                factor.factor_type = FactorType.PRIMARY
                factor.activation_threshold = primary_factors[factor_name]['threshold']
                factor.max_impact = primary_factors[factor_name]['max_impact']
                self.logger.debug(f"Configured {factor_name} as PRIMARY factor")
            elif factor_name in secondary_factors:
                factor.factor_type = FactorType.SECONDARY
                factor.activation_threshold = secondary_factors[factor_name]['threshold']
                factor.max_impact = secondary_factors[factor_name]['max_impact']
                self.logger.debug(f"Configured {factor_name} as SECONDARY factor")
    
    def _validate_and_normalize_weights(self) -> None:
        """Validate and normalize factor weights to sum to 1.0."""
        # Calculate current total weight across all factors
        total_weight = sum(f.weight for f in self.factors.values())
        
        if total_weight == 0:
            # If no weights set, distribute evenly
            equal_weight = 1.0 / len(self.factors)
            for factor in self.factors.values():
                factor.normalized_weight = equal_weight
            self.logger.warning("No weights set, using equal distribution")
        else:
            # Normalize all weights to sum to 1.0
            normalization_factor = 1.0 / total_weight
            for factor_name, factor in self.factors.items():
                # Store both original and normalized weights
                factor.original_weight = factor.weight
                factor.normalized_weight = factor.weight * normalization_factor
                # Use normalized weight for calculations
                factor.weight = factor.normalized_weight
            
            self.logger.info(f"Normalized {len(self.factors)} factor weights (was {total_weight:.2f}, now 1.00)")
            
            # Log the normalized weights for transparency
            for factor_name, factor in self.factors.items():
                self.logger.debug(f"  {factor_name}: {factor.original_weight:.3f} -> {factor.normalized_weight:.3f}")
        
        # Final validation
        final_total = sum(f.weight for f in self.factors.values())
        if abs(final_total - 1.0) > 0.001:
            self.logger.error(f"Normalization failed! Total weight is {final_total:.3f}")
        else:
            self.logger.info("Factor weights successfully normalized to 1.0")
    
    def calculate_all_factors(self, home_team: str, away_team: str, 
                            context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Calculate all factors for a given matchup with enhanced weighting.
        
        Args:
            home_team: Normalized home team name
            away_team: Normalized away team name
            context: Game context data
            
        Returns:
            Dictionary with factor results and summary
        """
        results = {
            'home_team': home_team,
            'away_team': away_team,
            'factors': {},
            'multiplicative_factors': [],
            'summary': {
                'total_adjustment': 0.0,
                'multiplicative_adjustment': 1.0,
                'category_adjustments': {},
                'factors_calculated': 0,
                'factors_successful': 0,
                'factors_failed': 0,
                'factors_activated': 0,
                'primary_signals': 0,
                'secondary_signals': 0,
                'avg_confidence': 0.0,
                'data_quality_impact': 0.0
            }
        }
        
        self.execution_stats['total_calculations'] += 1
        
        confidence_sum = 0.0
        confidence_count = 0
        
        # ── Phase 1: compute every factor's result (no activation-dependent aggregation yet),
        # so the L2 confirmation gate below can see ALL factor signs before any situational
        # contribution is counted or summed. ────────────────────────────────────────────────
        for factor_name, factor in self.factors.items():
            try:
                # Check if factor can be calculated with available data
                can_calculate, reason = factor.can_calculate(context)

                if can_calculate:
                    factor_result = factor.safe_calculate(home_team, away_team, context)
                    if factor_result['success']:
                        self.execution_stats['successful_calculations'] += 1
                        results['summary']['factors_successful'] += 1
                    else:
                        self.execution_stats['failed_calculations'] += 1
                        results['summary']['factors_failed'] += 1
                    results['factors'][factor_name] = factor_result
                else:
                    # Factor cannot be calculated
                    results['factors'][factor_name] = {
                        'factor_name': factor_name,
                        'factor_type': factor.factor_type.value,
                        'category': factor.category,
                        'home_team': home_team,
                        'away_team': away_team,
                        'value': 0.0,
                        'success': False,
                        'activated': False,
                        'error': f"Cannot calculate: {reason}",
                        'weight': factor.weight,
                        'weighted_value': 0.0,
                        'explanation': f"Insufficient data: {reason}"
                    }
                    results['summary']['factors_failed'] += 1

                results['summary']['factors_calculated'] += 1

            except Exception as e:
                self.logger.error(f"Error calculating factor {factor_name}: {e}")
                results['factors'][factor_name] = {
                    'factor_name': factor_name,
                    'category': getattr(factor, 'category', 'unknown'),
                    'home_team': home_team,
                    'away_team': away_team,
                    'value': 0.0,
                    'success': False,
                    'activated': False,
                    'error': str(e),
                    'weight': factor.weight,
                    'weighted_value': 0.0,
                    'explanation': f"Calculation error: {e}"
                }
                results['summary']['factors_failed'] += 1
                results['summary']['factors_calculated'] += 1

        # ── L2 confirming-signal gate (SPEC §7.3 / D15): de-activate any situational factor whose
        # direction is NOT confirmed by the model-vs-market BASE gap or an activated physical
        # factor, BEFORE aggregation — so total_adjustment, the signal counts, and avg_confidence
        # all reflect the gate. The engine injects the base gap (base only, never total) onto the
        # context; absent (e.g. a minimal/no-snapshot context) it falls back to physical-only
        # confirmation. ─────────────────────────────────────────────────────────────────────
        # `base_gap_favors_home` is the base gap in the factor sign convention (positive favours
        # home), injected by the engine (= vegas − base_spread; D15 base-only). Absent on a
        # minimal/no-snapshot context -> physical-only confirmation.
        base_gap = context.get('base_gap_favors_home') if context else None
        unconfirmed = confirm_situational(list(results['factors'].values()), base_gap)
        for name in unconfirmed:
            fr = results['factors'][name]
            fr['activated'] = False
            fr['confirmation'] = 'unconfirmed'
            fr['reasoning'] = list(fr.get('reasoning') or []) + [
                "Situational signal unconfirmed by the base gap or a physical factor (L2) — "
                "contribution withheld"
            ]

        # ── Phase 2: activation-dependent aggregation over the (now gated) results. ──────────
        for factor_name, factor_result in results['factors'].items():
            if not factor_result.get('success') or not factor_result.get('activated', False):
                continue

            results['summary']['factors_activated'] += 1

            # Track primary vs secondary
            if factor_result.get('factor_type') == FactorType.PRIMARY.value:
                results['summary']['primary_signals'] += 1
            elif factor_result.get('factor_type') == FactorType.SECONDARY.value:
                results['summary']['secondary_signals'] += 1

            # Track confidence (activated factors only)
            if isinstance(factor_result.get('confidence'), FactorConfidence):
                confidence_sum += factor_result['confidence'].value
                confidence_count += 1

            # Handle multiplicative vs additive factors
            if factor_result.get('is_multiplicative', False):
                results['multiplicative_factors'].append(factor_result)
                results['summary']['multiplicative_adjustment'] *= factor_result['weighted_value']
            else:
                weighted_val = factor_result.get('weighted_value', 0.0)
                if self.use_dynamic_weights:
                    weighted_val = (factor_result.get('dynamic_weight', factor_result.get('weight', 0.0))
                                    * factor_result.get('value', 0.0))

                results['summary']['total_adjustment'] += weighted_val

                # Track category adjustments
                category = factor_result.get('category', 'unknown')
                results['summary']['category_adjustments'].setdefault(category, 0.0)
                results['summary']['category_adjustments'][category] += weighted_val

        # Calculate average confidence
        if confidence_count > 0:
            results['summary']['avg_confidence'] = confidence_sum / confidence_count
        
        # Calculate data quality impact
        success_rate = (results['summary']['factors_successful'] / 
                       max(results['summary']['factors_calculated'], 1))
        results['summary']['data_quality_impact'] = success_rate
        
        self.logger.debug(f"Calculated {results['summary']['factors_calculated']} factors for {away_team} @ {home_team}")
        self.logger.debug(f"Activated: {results['summary']['factors_activated']}, Primary: {results['summary']['primary_signals']}")
        self.logger.debug(f"Total adjustment: {results['summary']['total_adjustment']:.3f}, Multiplier: {results['summary']['multiplicative_adjustment']:.3f}")
        
        return results
    
    def get_factor_info(self, factor_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Get information about factors.
        
        Args:
            factor_name: Specific factor name, or None for all factors
            
        Returns:
            Dictionary with factor information
        """
        if factor_name:
            if factor_name in self.factors:
                return self.factors[factor_name].get_factor_info()
            else:
                raise ValueError(f"Factor '{factor_name}' not found")
        
        # Return info for all factors
        factor_info = {}
        for name, factor in self.factors.items():
            factor_info[name] = factor.get_factor_info()
        
        return factor_info
    

# Global factor registry instance
factor_registry = FactorRegistry()
