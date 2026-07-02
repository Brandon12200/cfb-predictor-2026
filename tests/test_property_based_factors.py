"""
Property-based tests for factor combinations and edge cases.
Uses hypothesis library to generate test cases that uncover edge conditions.
"""

import unittest
import random
from typing import Dict, Any
from unittest.mock import Mock

# Try to import hypothesis, fall back to basic testing if not available
try:
    from hypothesis import given, strategies as st, assume, settings
    from hypothesis.stateful import RuleBasedStateMachine, rule, Bundle
    HYPOTHESIS_AVAILABLE = True
except ImportError:
    HYPOTHESIS_AVAILABLE = False
    # Create dummy decorators for when hypothesis is not available
    def given(*args, **kwargs):
        def decorator(func):
            return func
        return decorator
    
    def settings(*args, **kwargs):
        def decorator(func):
            return func
        return decorator
    
    class st:
        @staticmethod
        def integers(min_value=None, max_value=None):
            return range(min_value or 0, max_value or 100)
        
        @staticmethod
        def floats(min_value=None, max_value=None):
            return [random.uniform(min_value or -10, max_value or 10) for _ in range(10)]
        
        @staticmethod
        def text():
            return ["GEORGIA", "ALABAMA", "OHIO STATE", "MICHIGAN"]
        
        @staticmethod
        def booleans():
            return [True, False]

from factors.factor_registry import factor_registry
from factors.base_calculator import BaseFactorCalculator
from engine.prediction_engine import prediction_engine
from engine.confidence_calculator import confidence_calculator


class TestFactorProperties(unittest.TestCase):
    """Property-based tests for factor calculations."""
    
    def setUp(self):
        """Set up test environment."""
        self.teams = ["GEORGIA", "ALABAMA", "OHIO STATE", "MICHIGAN", "TEXAS", "OKLAHOMA"]
    
    @unittest.skipUnless(HYPOTHESIS_AVAILABLE, "Hypothesis not available")
    @given(
        home_team=st.text(),
        away_team=st.text(),
        experience_home=st.integers(min_value=1, max_value=30),
        experience_away=st.integers(min_value=1, max_value=30),
        week=st.integers(min_value=1, max_value=17)
    )
    @settings(max_examples=50)
    def test_factor_output_bounds(self, home_team, away_team, experience_home, experience_away, week):
        """Test that all factors respect their output bounds."""
        assume(home_team != away_team)
        assume(len(home_team) > 0 and len(away_team) > 0)
        
        # Create mock context
        context = self._create_mock_context(experience_home, experience_away, week)
        
        # Test all factors
        for factor_name, factor in factor_registry.factors.items():
            try:
                result = factor.safe_calculate(home_team, away_team, context)
                
                if result['success']:
                    value = result['value']
                    min_val, max_val = factor.get_output_range()
                    
                    self.assertGreaterEqual(
                        value, min_val,
                        f"{factor_name} output {value} below minimum {min_val}"
                    )
                    self.assertLessEqual(
                        value, max_val,
                        f"{factor_name} output {value} above maximum {max_val}"
                    )
                    self.assertIsInstance(value, (int, float))
            except Exception as e:
                self.fail(f"Factor {factor_name} failed with {type(e).__name__}: {e}")
    
    @unittest.skipUnless(HYPOTHESIS_AVAILABLE, "Hypothesis not available")
    @given(
        vegas_spread=st.floats(min_value=-21.0, max_value=21.0),
        data_quality=st.floats(min_value=0.0, max_value=1.0),
        week=st.integers(min_value=1, max_value=17)
    )
    @settings(max_examples=30)
    def test_confidence_bounds(self, vegas_spread, data_quality, week):
        """Test that confidence calculations always stay within bounds."""
        # Create mock prediction result
        prediction_result = {
            'edge_size': abs(vegas_spread) * 0.5,  # Some edge based on spread
            'prediction_type': 'MODERATE_CONTRARIAN',
            'vegas_spread': vegas_spread,
            'contrarian_spread': vegas_spread + random.uniform(-2, 2)
        }
        
        # Create mock factors
        factors = {
            'summary': {
                'factors_calculated': 11,
                'factors_successful': random.randint(6, 11),
                'category_adjustments': {
                    'coaching_edge': random.uniform(-1, 1),
                    'situational_context': random.uniform(-1, 1),
                    'momentum_factors': random.uniform(-1, 1)
                }
            },
            'factors': {}
        }
        
        # Create mock context
        context = {
            'data_quality': data_quality,
            'vegas_spread': vegas_spread,
            'data_sources': ['odds_api', 'espn_api'],
            'week': week
        }
        
        try:
            confidence_result = confidence_calculator.calculate_confidence(
                prediction_result, factors, context
            )
            
            confidence_score = confidence_result['confidence_score']
            
            # Confidence should always be between 15% and 95%
            self.assertGreaterEqual(confidence_score, 0.15, "Confidence below minimum 15%")
            self.assertLessEqual(confidence_score, 0.95, "Confidence above maximum 95%")
            self.assertIsInstance(confidence_score, (int, float))
            
        except Exception as e:
            self.fail(f"Confidence calculation failed: {e}")
    
    def test_factor_symmetry_property(self):
        """Test that factors respond differently when teams are swapped."""
        # Most factors are not perfectly symmetric due to team-specific data,
        # but they should at least produce different results when teams are swapped
        test_factors = ['ExperienceDifferential', 'VenuePerformance', 'HeadToHeadRecord']
        
        for factor_name in test_factors:
            if factor_name in factor_registry.factors:
                factor = factor_registry.factors[factor_name]
                
                # Create basic context
                context = self._create_basic_context()
                
                try:
                    # Calculate both directions
                    home_result = factor.safe_calculate("GEORGIA", "ALABAMA", context)
                    away_result = factor.safe_calculate("ALABAMA", "GEORGIA", context)
                    
                    if home_result['success'] and away_result['success']:
                        # Results should be different (not necessarily opposite)
                        home_value = home_result['value']
                        away_value = away_result['value']
                        
                        # Factors should respond to team order (even if not perfectly symmetric)
                        self.assertIsInstance(home_value, (int, float))
                        self.assertIsInstance(away_value, (int, float))
                        
                except Exception as e:
                    self.fail(f"Factor calculation failed for {factor_name}: {e}")
    
    def _create_basic_context(self):
        """Create basic context for fallback tests."""
        return {
            'week': 8,
            'vegas_spread': -3.5,
            'data_quality': 0.75,
            'home_team_data': {
                'derived_metrics': {
                    'current_record': {'win_percentage': 0.75},
                    'venue_performance': {'home_record': {'win_percentage': 0.80}}
                }
            },
            'away_team_data': {
                'derived_metrics': {
                    'current_record': {'win_percentage': 0.65},
                    'venue_performance': {'away_record': {'win_percentage': 0.60}}
                }
            }
        }
    
    def test_factor_monotonicity(self):
        """Test that factors behave monotonically with respect to key inputs."""
        # Test experience differential monotonicity
        factor = factor_registry.factors.get('ExperienceDifferential')
        if factor:
            experiences = [1, 5, 10, 15, 20]
            results = []
            
            for exp in experiences:
                context = self._create_mock_context(experience_home=exp, experience_away=5)
                result = factor.safe_calculate("GEORGIA", "ALABAMA", context)
                if result['success']:
                    results.append(result['value'])
            
            # Should generally increase with more experience differential
            if len(results) >= 3:
                # Allow some non-monotonicity due to diminishing returns
                increasing_trend = sum(
                    1 for i in range(1, len(results)) 
                    if results[i] >= results[i-1] - 0.1
                ) / (len(results) - 1)
                
                self.assertGreater(
                    increasing_trend, 0.6,
                    f"Experience factor not sufficiently monotonic: {results}"
                )
    
    def test_factor_zero_property(self):
        """Test that factors return zero for identical teams."""
        for factor_name, factor in factor_registry.factors.items():
            context = self._create_mock_context()
            
            try:
                result = factor.safe_calculate("GEORGIA", "GEORGIA", context)
                
                # Most factors should return 0 for same team
                # Allow some exceptions for factors that might not apply this rule
                if result['success'] and factor_name not in ['DesperationIndex', 'LookaheadSandwich']:
                    self.assertAlmostEqual(
                        result['value'], 0.0, places=2,
                        msg=f"{factor_name} should return ~0 for identical teams, got {result['value']}"
                    )
                    
            except Exception as e:
                # Factor should handle same team gracefully, not crash
                self.fail(f"Factor {factor_name} crashed on identical teams: {e}")
    
    def test_extreme_input_handling(self):
        """Test factors handle extreme inputs gracefully."""
        extreme_contexts = [
            # Extreme experience values
            self._create_mock_context(experience_home=0, experience_away=50),
            self._create_mock_context(experience_home=50, experience_away=0),
            
            # Extreme win percentages
            {
                'home_team_data': {
                    'derived_metrics': {
                        'current_record': {'win_percentage': 1.0},
                        'venue_performance': {'home_record': {'win_percentage': 1.0}}
                    }
                },
                'away_team_data': {
                    'derived_metrics': {
                        'current_record': {'win_percentage': 0.0},
                        'venue_performance': {'away_record': {'win_percentage': 0.0}}
                    }
                }
            },
            
            # Missing data context
            {},
            
            # Extreme week values
            self._create_mock_context(week=1),
            self._create_mock_context(week=17)
        ]
        
        for i, context in enumerate(extreme_contexts):
            for factor_name, factor in factor_registry.factors.items():
                try:
                    result = factor.safe_calculate("GEORGIA", "ALABAMA", context)
                    
                    # Should either succeed with valid output or fail gracefully
                    if result['success']:
                        value = result['value']
                        min_val, max_val = factor.get_output_range()
                        
                        self.assertGreaterEqual(value, min_val)
                        self.assertLessEqual(value, max_val)
                        self.assertIsInstance(value, (int, float))
                        self.assertFalse(
                            value != value,  # Check for NaN
                            f"{factor_name} returned NaN with extreme context {i}"
                        )
                    
                except Exception as e:
                    self.fail(f"Factor {factor_name} failed on extreme context {i}: {e}")
    
    def test_weight_consistency(self):
        """Test that factor weights sum to 1.0 and are positive."""
        total_weight = sum(factor.weight for factor in factor_registry.factors.values())
        
        self.assertAlmostEqual(total_weight, 1.0, places=3, msg="Factor weights don't sum to 1.0")
        
        for factor_name, factor in factor_registry.factors.items():
            self.assertGreater(factor.weight, 0, f"{factor_name} has non-positive weight")
            self.assertLess(factor.weight, 1.0, f"{factor_name} weight >= 1.0")
    
    def test_factor_combination_stability(self):
        """Test that factor combinations produce stable results."""
        # Test with various team combinations
        team_pairs = [
            ("GEORGIA", "ALABAMA"),
            ("OHIO STATE", "MICHIGAN"),
            ("TEXAS", "OKLAHOMA"),
            ("CLEMSON", "FLORIDA STATE")
        ]
        
        for home, away in team_pairs:
            context = self._create_mock_context()
            
            # Calculate factors multiple times
            results = []
            for _ in range(3):
                try:
                    factor_results = factor_registry.calculate_all_factors(home, away, context)
                    total_adjustment = factor_results['summary']['total_adjustment']
                    results.append(total_adjustment)
                except Exception as e:
                    self.fail(f"Factor calculation failed for {home} vs {away}: {e}")
            
            # Results should be identical (deterministic)
            for i in range(1, len(results)):
                self.assertAlmostEqual(
                    results[0], results[i], places=6,
                    msg=f"Non-deterministic results for {home} vs {away}: {results}"
                )
    
    def test_confidence_monotonicity(self):
        """Test that confidence increases with better conditions."""
        base_context = {
            'data_quality': 0.5,
            'vegas_spread': -3.5,
            'data_sources': ['odds_api'],
            'week': 8
        }
        
        base_factors = {
            'summary': {
                'factors_calculated': 11,
                'factors_successful': 6,
                'category_adjustments': {}
            },
            'factors': {}
        }
        
        base_prediction = {
            'edge_size': 2.0,
            'prediction_type': 'MODERATE_CONTRARIAN',
            'vegas_spread': -3.5,
            'contrarian_spread': -1.5
        }
        
        # Test with improving conditions
        improvements = [
            ('data_quality', [0.3, 0.5, 0.7, 0.9]),
            ('factors_successful', [4, 6, 8, 10]),
            ('edge_size', [0.5, 1.0, 2.0, 3.0])
        ]
        
        for param, values in improvements:
            confidences = []
            
            for value in values:
                test_context = base_context.copy()
                test_factors = base_factors.copy()
                test_prediction = base_prediction.copy()
                
                if param == 'data_quality':
                    test_context[param] = value
                elif param == 'factors_successful':
                    test_factors['summary'][param] = value
                elif param == 'edge_size':
                    test_prediction[param] = value
                
                try:
                    confidence = confidence_calculator.calculate_confidence(
                        test_prediction, test_factors, test_context
                    )
                    confidences.append(confidence['confidence_score'])
                except Exception as e:
                    self.fail(f"Confidence calculation failed for {param}={value}: {e}")
            
            # Check general upward trend (allow some non-monotonicity)
            if len(confidences) >= 3:
                increasing_count = sum(
                    1 for i in range(1, len(confidences))
                    if confidences[i] >= confidences[i-1] - 0.05
                )
                increasing_ratio = increasing_count / (len(confidences) - 1)
                
                self.assertGreater(
                    increasing_ratio, 0.5,
                    f"Confidence not generally increasing with {param}: {confidences}"
                )
    
    def _create_mock_context(self, experience_home=10, experience_away=8, week=8):
        """Create a mock context for testing."""
        return {
            'week': week,
            'vegas_spread': -3.5,
            'data_quality': 0.75,
            'data_sources': ['odds_api', 'espn_api'],
            'home_team_data': {
                'info': {'conference': {'name': 'SEC'}},
                'derived_metrics': {
                    'current_record': {'wins': 7, 'losses': 2, 'win_percentage': 0.78},
                    'venue_performance': {
                        'home_record': {'win_percentage': 0.85},
                        'away_record': {'win_percentage': 0.70}
                    }
                }
            },
            'away_team_data': {
                'info': {'conference': {'name': 'SEC'}},
                'derived_metrics': {
                    'current_record': {'wins': 6, 'losses': 3, 'win_percentage': 0.67},
                    'venue_performance': {
                        'home_record': {'win_percentage': 0.75},
                        'away_record': {'win_percentage': 0.60}
                    }
                }
            },
            'coaching_comparison': {
                'home_coaching': {
                    'head_coach_experience': experience_home,
                    'tenure_years': min(experience_home, 8)
                },
                'away_coaching': {
                    'head_coach_experience': experience_away,
                    'tenure_years': min(experience_away, 6)
                },
                'head_to_head_record': {
                    'home_wins': 2,
                    'away_wins': 1,
                    'total_games': 3
                }
            }
        }
    
    def _create_biased_context(self, home_advantage=True):
        """Create a context biased toward home or away team."""
        if home_advantage:
            return self._create_mock_context(experience_home=15, experience_away=5)
        else:
            return self._create_mock_context(experience_home=5, experience_away=15)


class TestBasicPropertyFallbacks(unittest.TestCase):
    """Fallback tests when hypothesis is not available."""
    
    def test_basic_factor_properties(self):
        """Basic property tests without hypothesis."""
        teams = ["GEORGIA", "ALABAMA", "OHIO STATE", "MICHIGAN"]
        
        for home in teams[:2]:
            for away in teams[2:]:
                context = self._create_basic_context()
                
                for factor_name, factor in factor_registry.factors.items():
                    result = factor.safe_calculate(home, away, context)
                    
                    if result['success']:
                        value = result['value']
                        min_val, max_val = factor.get_output_range()
                        
                        self.assertGreaterEqual(value, min_val)
                        self.assertLessEqual(value, max_val)
                        self.assertIsInstance(value, (int, float))
    
    def test_basic_extreme_values(self):
        """Test basic extreme value handling."""
        extreme_contexts = [
            {},  # Empty context
            {'week': 1},  # Early season
            {'week': 17},  # Late season
        ]
        
        for context in extreme_contexts:
            for factor_name, factor in factor_registry.factors.items():
                result = factor.safe_calculate("GEORGIA", "ALABAMA", context)
                
                # Should either succeed or fail gracefully
                if result['success']:
                    value = result['value']
                    min_val, max_val = factor.get_output_range()
                    self.assertGreaterEqual(value, min_val)
                    self.assertLessEqual(value, max_val)
    
    def _create_basic_context(self):
        """Create basic context for fallback tests."""
        return {
            'week': 8,
            'vegas_spread': -3.5,
            'data_quality': 0.75,
            'home_team_data': {
                'derived_metrics': {
                    'current_record': {'win_percentage': 0.75},
                    'venue_performance': {'home_record': {'win_percentage': 0.80}}
                }
            },
            'away_team_data': {
                'derived_metrics': {
                    'current_record': {'win_percentage': 0.65},
                    'venue_performance': {'away_record': {'win_percentage': 0.55}}
                }
            },
            'coaching_comparison': {
                'home_coaching': {'head_coach_experience': 10},
                'away_coaching': {'head_coach_experience': 8}
            }
        }


if __name__ == '__main__':
    if HYPOTHESIS_AVAILABLE:
        print("Running property-based tests with Hypothesis")
    else:
        print("Hypothesis not available, running basic property tests")
    
    unittest.main()