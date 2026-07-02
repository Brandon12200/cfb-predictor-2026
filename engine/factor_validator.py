"""
Factor Validation System for College Football Market Edge Platform.

Tests factors for:
1. Realistic vs uniform outputs
2. Proper value distributions
3. Contextual responsiveness
4. Output range compliance
5. Edge case handling
6. Consistency and determinism
"""

import logging
import statistics
from typing import Dict, Any, List, Tuple, Optional, Set
from collections import defaultdict, Counter
import hashlib
from enum import Enum

from factors.factor_registry import factor_registry


class ValidationResult(Enum):
    """Validation result levels."""
    PASS = "pass"
    WARNING = "warning" 
    FAIL = "fail"
    ERROR = "error"


class FactorValidator:
    """
    Comprehensive validation system for factor quality assurance.
    
    Tests factors against multiple criteria to ensure they produce
    realistic, varied, and contextually appropriate outputs.
    """
    
    def __init__(self):
        """Initialize factor validator."""
        self.logger = logging.getLogger(__name__)
        
        # Validation thresholds
        self.thresholds = {
            'uniformity_max': 0.05,        # Max CV for uniform detection
            'min_unique_values': 5,        # Min unique values across test games
            'range_utilization_min': 0.1,  # Min % of factor range used
            'outlier_max_pct': 0.15,      # Max % of outlier values
            'zero_output_max_pct': 0.3,   # Max % of zero outputs
            'consistency_tolerance': 1e-6  # Tolerance for determinism test
        }
        
        # Test game scenarios for comprehensive testing
        self.test_scenarios = self._generate_test_scenarios()
    
    def validate_all_factors(self) -> Dict[str, Any]:
        """
        Run comprehensive validation on all registered factors.
        
        Returns:
            Dictionary with validation results for each factor
        """
        self.logger.info("Starting comprehensive factor validation...")
        
        validation_results = {}
        
        for factor_name, factor in factor_registry.factors.items():
            self.logger.info(f"Validating factor: {factor_name}")
            
            try:
                result = self.validate_single_factor(factor_name, factor)
                validation_results[factor_name] = result
            except Exception as e:
                self.logger.error(f"Error validating {factor_name}: {e}")
                validation_results[factor_name] = {
                    'overall_result': ValidationResult.ERROR,
                    'error': str(e),
                    'tests_passed': 0,
                    'tests_total': 0
                }
        
        # Generate overall system validation summary
        summary = self._generate_validation_summary(validation_results)
        
        return {
            'individual_factors': validation_results,
            'system_summary': summary,
            'validation_timestamp': self._get_timestamp()
        }
    
    def validate_single_factor(self, factor_name: str, factor) -> Dict[str, Any]:
        """
        Validate a single factor across multiple test criteria.
        
        Args:
            factor_name: Name of the factor
            factor: Factor instance to validate
            
        Returns:
            Dictionary with detailed validation results
        """
        results = {
            'factor_name': factor_name,
            'tests': {},
            'outputs': [],
            'test_scenarios_count': len(self.test_scenarios)
        }
        
        # Step 1: Generate outputs across all test scenarios
        outputs = self._generate_test_outputs(factor, factor_name)
        results['outputs'] = outputs
        
        if not outputs:
            return {
                'overall_result': ValidationResult.FAIL,
                'error': 'No valid outputs generated',
                'tests_passed': 0,
                'tests_total': 0
            }
        
        # Step 2: Run validation tests
        test_methods = [
            ('uniformity_test', self._test_uniformity),
            ('variety_test', self._test_output_variety),
            ('range_compliance_test', self._test_range_compliance),
            ('distribution_test', self._test_output_distribution),
            ('contextual_response_test', self._test_contextual_responsiveness),
            ('consistency_test', self._test_deterministic_consistency),
            ('edge_case_test', self._test_edge_case_handling),
            ('activation_test', self._test_activation_patterns)
        ]
        
        tests_passed = 0
        tests_total = len(test_methods)
        
        for test_name, test_method in test_methods:
            try:
                test_result = test_method(outputs, factor, factor_name)
                results['tests'][test_name] = test_result
                
                if test_result['result'] == ValidationResult.PASS:
                    tests_passed += 1
                
            except Exception as e:
                self.logger.error(f"Error in {test_name} for {factor_name}: {e}")
                results['tests'][test_name] = {
                    'result': ValidationResult.ERROR,
                    'error': str(e)
                }
        
        # Determine overall result
        if tests_passed == tests_total:
            overall_result = ValidationResult.PASS
        elif tests_passed >= tests_total * 0.7:
            overall_result = ValidationResult.WARNING
        else:
            overall_result = ValidationResult.FAIL
        
        results.update({
            'overall_result': overall_result,
            'tests_passed': tests_passed,
            'tests_total': tests_total,
            'pass_rate': tests_passed / tests_total if tests_total > 0 else 0
        })
        
        return results
    
    def _generate_test_scenarios(self) -> List[Dict[str, Any]]:
        """Generate comprehensive test scenarios covering various game types."""
        scenarios = []
        
        # Basic matchup types
        basic_matchups = [
            # Elite vs Weak
            ('Alabama', 'Vanderbilt', {'vegas_spread': -28.0, 'week': 8, 'year': 2024}),
            ('Ohio State', 'Akron', {'vegas_spread': -42.5, 'week': 3, 'year': 2024}),
            
            # Rivalry games
            ('Michigan', 'Ohio State', {'vegas_spread': -3.5, 'week': 13, 'year': 2024}),
            ('Alabama', 'Auburn', {'vegas_spread': -7.0, 'week': 12, 'year': 2024}),
            ('Texas', 'Oklahoma', {'vegas_spread': -4.5, 'week': 10, 'year': 2024}),
            
            # Close games
            ('Georgia', 'Tennessee', {'vegas_spread': -2.5, 'week': 11, 'year': 2024}),
            ('USC', 'UCLA', {'vegas_spread': -1.0, 'week': 12, 'year': 2024}),
            
            # Road favorites
            ('Clemson', 'Duke', {'vegas_spread': 10.5, 'week': 9, 'year': 2024}),
            ('Penn State', 'Maryland', {'vegas_spread': 14.0, 'week': 7, 'year': 2024}),
            
            # Conference championship implications
            ('Michigan', 'Wisconsin', {'vegas_spread': -9.5, 'week': 12, 'year': 2024}),
            ('Oregon', 'Washington', {'vegas_spread': -6.5, 'week': 11, 'year': 2024}),
            
            # Bowl eligibility bubble
            ('Illinois', 'Northwestern', {'vegas_spread': -3.0, 'week': 11, 'year': 2024}),
            ('Minnesota', 'Iowa', {'vegas_spread': 2.5, 'week': 10, 'year': 2024}),
        ]
        
        for home, away, context in basic_matchups:
            scenarios.append({
                'home_team': home,
                'away_team': away,
                'context': context,
                'scenario_type': 'basic_matchup'
            })
        
        # Week variations
        week_variations = [
            ('Notre Dame', 'Navy', {'vegas_spread': -14.0, 'week': 1, 'year': 2024}),  # Week 1
            ('Florida State', 'Miami', {'vegas_spread': -3.5, 'week': 6, 'year': 2024}),  # Mid-season
            ('LSU', 'Texas A&M', {'vegas_spread': -7.0, 'week': 13, 'year': 2024}),  # Late season
        ]
        
        for home, away, context in week_variations:
            scenarios.append({
                'home_team': home,
                'away_team': away,
                'context': context,
                'scenario_type': 'week_variation'
            })
        
        # Spread variations
        spread_variations = [
            ('Kentucky', 'Louisville', {'vegas_spread': 0.0, 'week': 12, 'year': 2024}),  # Pick'em
            ('TCU', 'Baylor', {'vegas_spread': -21.5, 'week': 9, 'year': 2024}),  # Large spread
            ('Virginia', 'Virginia Tech', {'vegas_spread': -35.5, 'week': 12, 'year': 2024}),  # Huge spread
        ]
        
        for home, away, context in spread_variations:
            scenarios.append({
                'home_team': home,
                'away_team': away,
                'context': context,
                'scenario_type': 'spread_variation'
            })
        
        return scenarios
    
    def _generate_test_outputs(self, factor, factor_name: str) -> List[Dict[str, Any]]:
        """Generate factor outputs across all test scenarios."""
        outputs = []
        
        for scenario in self.test_scenarios:
            try:
                # Calculate factor value
                value = factor.calculate(
                    scenario['home_team'],
                    scenario['away_team'],
                    scenario['context']
                )
                
                outputs.append({
                    'home_team': scenario['home_team'],
                    'away_team': scenario['away_team'],
                    'context': scenario['context'],
                    'scenario_type': scenario['scenario_type'],
                    'value': value,
                    'is_zero': abs(value) < 1e-10,
                    'is_activated': abs(value) > getattr(factor, 'activation_threshold', 0.01)
                })
                
            except Exception as e:
                self.logger.debug(f"Error calculating {factor_name} for {scenario['home_team']} vs {scenario['away_team']}: {e}")
                # Continue with other scenarios
        
        return outputs
    
    def _test_uniformity(self, outputs: List[Dict[str, Any]], factor, factor_name: str) -> Dict[str, Any]:
        """Test if factor produces uniform (unrealistic) outputs."""
        values = [o['value'] for o in outputs if not o['is_zero']]
        
        if len(values) < 3:
            return {
                'result': ValidationResult.WARNING,
                'message': 'Insufficient non-zero values for uniformity test',
                'values_tested': len(values)
            }
        
        # Calculate coefficient of variation
        try:
            mean_val = statistics.mean(values)
            if mean_val == 0:
                cv = 0 if all(v == 0 for v in values) else float('inf')
            else:
                std_dev = statistics.stdev(values) if len(values) > 1 else 0
                cv = abs(std_dev / mean_val)
        except:
            cv = 0
        
        # Check for exact uniformity (all values identical)
        unique_values = set(round(v, 6) for v in values)  # Round to avoid floating point issues
        
        if len(unique_values) == 1:
            return {
                'result': ValidationResult.FAIL,
                'message': f'Uniform output detected: all values = {list(unique_values)[0]:.6f}',
                'coefficient_of_variation': cv,
                'unique_values': len(unique_values),
                'total_values': len(values)
            }
        elif cv < self.thresholds['uniformity_max']:
            return {
                'result': ValidationResult.WARNING,
                'message': f'Very low variation detected (CV = {cv:.6f})',
                'coefficient_of_variation': cv,
                'unique_values': len(unique_values),
                'total_values': len(values)
            }
        else:
            return {
                'result': ValidationResult.PASS,
                'message': f'Good variation detected (CV = {cv:.3f})',
                'coefficient_of_variation': cv,
                'unique_values': len(unique_values),
                'total_values': len(values)
            }
    
    def _test_output_variety(self, outputs: List[Dict[str, Any]], factor, factor_name: str) -> Dict[str, Any]:
        """Test if factor produces sufficient variety in outputs."""
        all_values = [round(o['value'], 3) for o in outputs]  # Round for variety counting
        unique_values = len(set(all_values))
        total_values = len(all_values)
        
        variety_ratio = unique_values / total_values if total_values > 0 else 0
        
        if unique_values < self.thresholds['min_unique_values']:
            return {
                'result': ValidationResult.FAIL,
                'message': f'Insufficient variety: only {unique_values} unique values across {total_values} tests',
                'unique_values': unique_values,
                'total_values': total_values,
                'variety_ratio': variety_ratio
            }
        elif variety_ratio < 0.3:
            return {
                'result': ValidationResult.WARNING,
                'message': f'Low variety: {variety_ratio:.1%} unique values',
                'unique_values': unique_values,
                'total_values': total_values,
                'variety_ratio': variety_ratio
            }
        else:
            return {
                'result': ValidationResult.PASS,
                'message': f'Good variety: {unique_values} unique values ({variety_ratio:.1%})',
                'unique_values': unique_values,
                'total_values': total_values,
                'variety_ratio': variety_ratio
            }
    
    def _test_range_compliance(self, outputs: List[Dict[str, Any]], factor, factor_name: str) -> Dict[str, Any]:
        """Test if factor outputs comply with expected ranges."""
        values = [o['value'] for o in outputs]
        
        # Get factor's expected range
        min_expected = getattr(factor, '_min_output', -5.0)
        max_expected = getattr(factor, '_max_output', 5.0)
        
        actual_min = min(values) if values else 0
        actual_max = max(values) if values else 0
        
        # Check for range violations
        violations = [v for v in values if v < min_expected or v > max_expected]
        
        # Calculate range utilization
        expected_range = max_expected - min_expected
        actual_range = actual_max - actual_min
        range_utilization = actual_range / expected_range if expected_range > 0 else 0
        
        if violations:
            return {
                'result': ValidationResult.FAIL,
                'message': f'{len(violations)} values outside expected range [{min_expected}, {max_expected}]',
                'violations': len(violations),
                'violation_examples': violations[:3],
                'expected_range': [min_expected, max_expected],
                'actual_range': [actual_min, actual_max]
            }
        elif range_utilization < self.thresholds['range_utilization_min']:
            return {
                'result': ValidationResult.WARNING,
                'message': f'Low range utilization: {range_utilization:.1%} of expected range',
                'range_utilization': range_utilization,
                'expected_range': [min_expected, max_expected],
                'actual_range': [actual_min, actual_max]
            }
        else:
            return {
                'result': ValidationResult.PASS,
                'message': f'Good range compliance: {range_utilization:.1%} utilization',
                'range_utilization': range_utilization,
                'expected_range': [min_expected, max_expected],
                'actual_range': [actual_min, actual_max]
            }
    
    def _test_output_distribution(self, outputs: List[Dict[str, Any]], factor, factor_name: str) -> Dict[str, Any]:
        """Test the distribution characteristics of factor outputs."""
        values = [o['value'] for o in outputs]
        zero_count = sum(1 for o in outputs if o['is_zero'])
        
        zero_ratio = zero_count / len(outputs) if outputs else 0
        
        # Check for excessive zeros
        if zero_ratio > self.thresholds['zero_output_max_pct']:
            return {
                'result': ValidationResult.FAIL,
                'message': f'Too many zero outputs: {zero_ratio:.1%}',
                'zero_ratio': zero_ratio,
                'zero_count': zero_count,
                'total_outputs': len(outputs)
            }
        
        # Check for outliers (values >2 std devs from mean)
        if len(values) > 2:
            try:
                mean_val = statistics.mean(values)
                std_dev = statistics.stdev(values)
                outliers = [v for v in values if abs(v - mean_val) > 2 * std_dev] if std_dev > 0 else []
                outlier_ratio = len(outliers) / len(values)
                
                if outlier_ratio > self.thresholds['outlier_max_pct']:
                    return {
                        'result': ValidationResult.WARNING,
                        'message': f'High outlier ratio: {outlier_ratio:.1%}',
                        'outlier_ratio': outlier_ratio,
                        'outlier_count': len(outliers),
                        'mean': mean_val,
                        'std_dev': std_dev
                    }
            except:
                pass  # Skip outlier test if statistics fail
        
        return {
            'result': ValidationResult.PASS,
            'message': f'Good distribution: {zero_ratio:.1%} zeros',
            'zero_ratio': zero_ratio,
            'zero_count': zero_count,
            'total_outputs': len(outputs)
        }
    
    def _test_contextual_responsiveness(self, outputs: List[Dict[str, Any]], factor, factor_name: str) -> Dict[str, Any]:
        """Test if factor responds appropriately to different contexts."""
        # Group outputs by scenario type
        by_scenario = defaultdict(list)
        for output in outputs:
            by_scenario[output['scenario_type']].append(output['value'])
        
        scenario_variations = {}
        
        for scenario_type, values in by_scenario.items():
            if len(values) > 1:
                cv = abs(statistics.stdev(values) / statistics.mean(values)) if statistics.mean(values) != 0 else 0
                scenario_variations[scenario_type] = cv
        
        # Check if factor varies across different scenario types
        avg_variation = statistics.mean(scenario_variations.values()) if scenario_variations else 0
        
        if avg_variation < 0.1:
            return {
                'result': ValidationResult.WARNING,
                'message': f'Low contextual responsiveness: avg CV = {avg_variation:.3f}',
                'avg_variation': avg_variation,
                'scenario_variations': scenario_variations
            }
        else:
            return {
                'result': ValidationResult.PASS,
                'message': f'Good contextual responsiveness: avg CV = {avg_variation:.3f}',
                'avg_variation': avg_variation,
                'scenario_variations': scenario_variations
            }
    
    def _test_deterministic_consistency(self, outputs: List[Dict[str, Any]], factor, factor_name: str) -> Dict[str, Any]:
        """Test if factor produces consistent outputs for identical inputs."""
        # Test with a few repeated scenarios
        test_scenarios = self.test_scenarios[:3]  # Test first 3 scenarios
        
        inconsistencies = []
        
        for scenario in test_scenarios:
            try:
                # Calculate same scenario multiple times
                values = []
                for _ in range(3):
                    value = factor.calculate(
                        scenario['home_team'],
                        scenario['away_team'],
                        scenario['context']
                    )
                    values.append(value)
                
                # Check if all values are identical (within tolerance)
                if not all(abs(v - values[0]) < self.thresholds['consistency_tolerance'] for v in values):
                    inconsistencies.append({
                        'scenario': f"{scenario['away_team']} @ {scenario['home_team']}",
                        'values': values
                    })
                    
            except Exception as e:
                inconsistencies.append({
                    'scenario': f"{scenario['away_team']} @ {scenario['home_team']}",
                    'error': str(e)
                })
        
        if inconsistencies:
            return {
                'result': ValidationResult.FAIL,
                'message': f'Deterministic inconsistencies detected in {len(inconsistencies)} scenarios',
                'inconsistencies': inconsistencies
            }
        else:
            return {
                'result': ValidationResult.PASS,
                'message': 'Factor produces consistent outputs for identical inputs',
                'tests_performed': len(test_scenarios)
            }
    
    def _test_edge_case_handling(self, outputs: List[Dict[str, Any]], factor, factor_name: str) -> Dict[str, Any]:
        """Test factor behavior with edge case inputs."""
        edge_cases = [
            # Zero spread
            ('Duke', 'Wake Forest', {'vegas_spread': 0.0, 'week': 8, 'year': 2024}),
            # Huge spread
            ('Georgia', 'Georgia Southern', {'vegas_spread': -49.5, 'week': 2, 'year': 2024}),
            # Week 1
            ('Alabama', 'Miami', {'vegas_spread': -14.0, 'week': 1, 'year': 2024}),
            # Late season
            ('Ohio State', 'Michigan', {'vegas_spread': -7.0, 'week': 14, 'year': 2024}),
        ]
        
        edge_case_errors = []
        edge_case_values = []
        
        for home, away, context in edge_cases:
            try:
                value = factor.calculate(home, away, context)
                edge_case_values.append(value)
            except Exception as e:
                edge_case_errors.append({
                    'scenario': f'{away} @ {home}',
                    'context': context,
                    'error': str(e)
                })
        
        if edge_case_errors:
            return {
                'result': ValidationResult.FAIL,
                'message': f'Errors in {len(edge_case_errors)} edge cases',
                'errors': edge_case_errors
            }
        else:
            return {
                'result': ValidationResult.PASS,
                'message': f'Handled {len(edge_cases)} edge cases successfully',
                'edge_case_values': edge_case_values
            }
    
    def _test_activation_patterns(self, outputs: List[Dict[str, Any]], factor, factor_name: str) -> Dict[str, Any]:
        """Test factor activation patterns."""
        total_outputs = len(outputs)
        activated_outputs = sum(1 for o in outputs if o['is_activated'])
        activation_rate = activated_outputs / total_outputs if total_outputs > 0 else 0
        
        # Factor should activate sometimes but not always
        if activation_rate == 0:
            return {
                'result': ValidationResult.WARNING,
                'message': 'Factor never activates - may need threshold adjustment',
                'activation_rate': activation_rate,
                'activated_count': activated_outputs,
                'total_count': total_outputs
            }
        elif activation_rate == 1.0:
            return {
                'result': ValidationResult.WARNING,
                'message': 'Factor always activates - may need threshold adjustment',
                'activation_rate': activation_rate,
                'activated_count': activated_outputs,
                'total_count': total_outputs
            }
        else:
            return {
                'result': ValidationResult.PASS,
                'message': f'Good activation pattern: {activation_rate:.1%} activation rate',
                'activation_rate': activation_rate,
                'activated_count': activated_outputs,
                'total_count': total_outputs
            }
    
    def _generate_validation_summary(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Generate overall validation summary."""
        factor_results = results
        
        total_factors = len(factor_results)
        passed_factors = sum(1 for r in factor_results.values() 
                           if r.get('overall_result') == ValidationResult.PASS)
        warning_factors = sum(1 for r in factor_results.values() 
                            if r.get('overall_result') == ValidationResult.WARNING)
        failed_factors = sum(1 for r in factor_results.values() 
                           if r.get('overall_result') == ValidationResult.FAIL)
        error_factors = sum(1 for r in factor_results.values() 
                          if r.get('overall_result') == ValidationResult.ERROR)
        
        # Calculate overall system health
        if passed_factors >= total_factors * 0.8:
            system_health = "HEALTHY"
        elif passed_factors >= total_factors * 0.6:
            system_health = "MODERATE"
        else:
            system_health = "POOR"
        
        return {
            'total_factors': total_factors,
            'passed_factors': passed_factors,
            'warning_factors': warning_factors,
            'failed_factors': failed_factors,
            'error_factors': error_factors,
            'pass_rate': passed_factors / total_factors if total_factors > 0 else 0,
            'system_health': system_health,
            'test_scenarios_used': len(self.test_scenarios),
            'recommendations': self._generate_recommendations(factor_results)
        }
    
    def _generate_recommendations(self, factor_results: Dict[str, Any]) -> List[str]:
        """Generate recommendations based on validation results."""
        recommendations = []
        
        # Analyze common issues
        uniform_factors = [name for name, result in factor_results.items()
                          if result.get('tests', {}).get('uniformity_test', {}).get('result') == ValidationResult.FAIL]
        
        if uniform_factors:
            recommendations.append(f"Fix uniform output in factors: {', '.join(uniform_factors)}")
        
        low_variety_factors = [name for name, result in factor_results.items()
                              if result.get('tests', {}).get('variety_test', {}).get('result') == ValidationResult.FAIL]
        
        if low_variety_factors:
            recommendations.append(f"Increase output variety in factors: {', '.join(low_variety_factors)}")
        
        error_factors = [name for name, result in factor_results.items()
                        if result.get('overall_result') == ValidationResult.ERROR]
        
        if error_factors:
            recommendations.append(f"Fix critical errors in factors: {', '.join(error_factors)}")
        
        if not recommendations:
            recommendations.append("All factors are performing well - no critical issues detected")
        
        return recommendations
    
    def _get_timestamp(self) -> str:
        """Get current timestamp for validation results."""
        from datetime import datetime
        return datetime.now().isoformat()


# Singleton instance
factor_validator = FactorValidator()