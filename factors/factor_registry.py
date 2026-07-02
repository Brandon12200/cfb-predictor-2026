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
        
        # New contrarian weight structure: PRIMARY/SECONDARY/MODIFIER
        self.category_weights = {
            'primary': config.primary_factors_weight,      # 60% - Direct contrarian signals
            'secondary': config.secondary_factors_weight,  # 30% - Supporting evidence
            'modifier': config.modifier_factors_weight     # 10% - Situational adjustments
        }
        
        # Legacy category mapping (for existing factors)
        self.legacy_category_weights = {
            'coaching_edge': config.coaching_edge_weight,
            'situational_context': config.situational_context_weight,
            'momentum_factors': config.momentum_factors_weight
        }
        
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
            'DesperationIndex': {'threshold': 2.0, 'max_impact': 7.0},      # 20% of total
            # 'SchedulingFatigue': {'threshold': 1.5, 'max_impact': 3.5},   # 20% of total (to be added)
        }
        
        # SECONDARY factors (30% weight) - Supporting evidence
        # These provide additional context but aren't primary contrarian signals
        secondary_factors = {
            'ExperienceDifferential': {'threshold': 1.0, 'max_impact': 3.0},
            'PressureSituation': {'threshold': 0.75, 'max_impact': 3.0},
            'RevengeGame': {'threshold': 1.5, 'max_impact': 4.0},
            'LookaheadSandwich': {'threshold': 1.0, 'max_impact': 4.0},
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
        
        # Calculate each factor
        for factor_name, factor in self.factors.items():
            try:
                # Check if factor can be calculated with available data
                can_calculate, reason = factor.can_calculate(context)
                
                if can_calculate:
                    # Calculate factor with enhanced method
                    factor_result = factor.safe_calculate(home_team, away_team, context)
                    
                    # Track performance
                    if factor_result['success']:
                        self.execution_stats['successful_calculations'] += 1
                        results['summary']['factors_successful'] += 1
                        
                        # Track activation
                        if factor_result.get('activated', False):
                            results['summary']['factors_activated'] += 1
                            
                            # Track primary vs secondary
                            if factor_result.get('factor_type') == FactorType.PRIMARY.value:
                                results['summary']['primary_signals'] += 1
                            elif factor_result.get('factor_type') == FactorType.SECONDARY.value:
                                results['summary']['secondary_signals'] += 1
                            
                            # Track confidence
                            if isinstance(factor_result.get('confidence'), FactorConfidence):
                                confidence_sum += factor_result['confidence'].value
                                confidence_count += 1
                    else:
                        self.execution_stats['failed_calculations'] += 1
                        results['summary']['factors_failed'] += 1
                    
                    # Add to results
                    results['factors'][factor_name] = factor_result
                    
                    # Handle multiplicative vs additive factors
                    if factor_result['success'] and factor_result.get('activated', False):
                        if factor_result.get('is_multiplicative', False):
                            # Store multiplicative factors separately
                            results['multiplicative_factors'].append(factor_result)
                            results['summary']['multiplicative_adjustment'] *= factor_result['weighted_value']
                        else:
                            # Add to total adjustment (additive)
                            weighted_val = factor_result.get('weighted_value', 0.0)
                            if self.use_dynamic_weights:
                                # Use dynamic weight if enabled
                                weighted_val = factor_result.get('dynamic_weight', factor.weight) * factor_result.get('value', 0.0)
                            
                            results['summary']['total_adjustment'] += weighted_val
                            
                            # Track category adjustments
                            category = factor.category
                            if category not in results['summary']['category_adjustments']:
                                results['summary']['category_adjustments'][category] = 0.0
                            results['summary']['category_adjustments'][category] += weighted_val
                
                else:
                    # Factor cannot be calculated
                    results['factors'][factor_name] = {
                        'factor_name': factor_name,
                        'factor_type': factor.factor_type.value,
                        'home_team': home_team,
                        'away_team': away_team,
                        'value': 0.0,
                        'success': False,
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
                    'home_team': home_team,
                    'away_team': away_team,
                    'value': 0.0,
                    'success': False,
                    'error': str(e),
                    'weight': factor.weight,
                    'weighted_value': 0.0,
                    'explanation': f"Calculation error: {e}"
                }
                results['summary']['factors_failed'] += 1
                results['summary']['factors_calculated'] += 1
        
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
    
    def get_category_summary(self) -> Dict[str, Any]:
        """Get summary of factors by category."""
        category_summary = {}
        
        for category, target_weight in self.category_weights.items():
            factors_in_category = [f for f in self.factors.values() if f.category == category]
            
            category_summary[category] = {
                'target_weight': target_weight,
                'actual_weight': sum(f.weight for f in factors_in_category),
                'factor_count': len(factors_in_category),
                'factors': [f.name for f in factors_in_category]
            }
        
        return category_summary
    
    def get_execution_stats(self) -> Dict[str, Any]:
        """Get execution statistics."""
        total_calcs = max(self.execution_stats['total_calculations'], 1)
        
        return {
            'total_calculations': self.execution_stats['total_calculations'],
            'success_rate': self.execution_stats['successful_calculations'] / total_calcs,
            'failure_rate': self.execution_stats['failed_calculations'] / total_calcs,
            'factors_registered': len(self.factors),
            'category_distribution': self.get_category_summary()
        }
    
    def validate_factor_configuration(self) -> Dict[str, Any]:
        """Validate the current factor configuration."""
        validation_results = {
            'valid': True,
            'warnings': [],
            'errors': [],
            'summary': {}
        }
        
        # Check total weights
        total_weight = sum(f.weight for f in self.factors.values())
        if abs(total_weight - 1.0) > 0.001:
            validation_results['errors'].append(f"Total weights sum to {total_weight:.3f}, expected 1.0")
            validation_results['valid'] = False
        
        # Check category weights
        for category, target_weight in self.category_weights.items():
            factors_in_category = [f for f in self.factors.values() if f.category == category]
            actual_weight = sum(f.weight for f in factors_in_category)
            
            if abs(actual_weight - target_weight) > 0.001:
                validation_results['warnings'].append(
                    f"Category '{category}' weights sum to {actual_weight:.3f}, expected {target_weight:.3f}"
                )
        
        # Check for missing factor categories
        expected_categories = set(self.category_weights.keys())
        actual_categories = set(f.category for f in self.factors.values())
        
        missing_categories = expected_categories - actual_categories
        if missing_categories:
            validation_results['errors'].append(f"Missing factor categories: {missing_categories}")
            validation_results['valid'] = False
        
        # Check factor output ranges
        for factor_name, factor in self.factors.items():
            try:
                min_val, max_val = factor.get_output_range()
                if min_val >= max_val:
                    validation_results['errors'].append(
                        f"Factor '{factor_name}' has invalid output range: [{min_val}, {max_val}]"
                    )
                    validation_results['valid'] = False
            except Exception as e:
                validation_results['errors'].append(
                    f"Factor '{factor_name}' failed output range check: {e}"
                )
                validation_results['valid'] = False
        
        validation_results['summary'] = {
            'total_factors': len(self.factors),
            'total_weight': total_weight,
            'categories': len(actual_categories),
            'valid_configuration': validation_results['valid']
        }
        
        return validation_results


# Global factor registry instance
factor_registry = FactorRegistry()