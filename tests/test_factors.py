"""
Unit tests for factor calculators in College Football Market Edge Platform.
Tests all factor implementations for correctness and edge cases.
"""

import unittest
from unittest.mock import Mock, patch
from typing import Dict, Any

from factors.base_calculator import BaseFactorCalculator
from factors.coaching_edge import (
    ExperienceDifferentialCalculator,
    PressureSituationCalculator,
    HeadToHeadRecordCalculator
)
from factors.situational_context import (
    DesperationIndexCalculator,
    RevengeGameCalculator,
    LookaheadSandwichCalculator
)
from factors.momentum_factors import (
    PointDifferentialTrendsCalculator,
    CloseGamePerformanceCalculator
)


class TestBaseFactorCalculator(unittest.TestCase):
    """Test the base factor calculator abstract class."""
    
    def setUp(self):
        """Create a concrete implementation for testing."""
        class TestCalculator(BaseFactorCalculator):
            def __init__(self):
                super().__init__()
                self.weight = 0.1
                self.category = "test"
                self._min_output = -2.0
                self._max_output = 2.0
            
            def calculate(self, home_team, away_team, context=None):
                return 1.0
            
            def get_output_range(self):
                return (self._min_output, self._max_output)
        
        self.calculator = TestCalculator()
    
    def test_validate_teams(self):
        """Test team validation logic."""
        # Valid teams
        self.calculator.validate_teams("GEORGIA", "ALABAMA")
        
        # Empty teams
        with self.assertRaises(ValueError):
            self.calculator.validate_teams("", "ALABAMA")
        
        # Same teams
        with self.assertRaises(ValueError):
            self.calculator.validate_teams("GEORGIA", "GEORGIA")
        
        # Non-string teams
        with self.assertRaises(ValueError):
            self.calculator.validate_teams(123, "ALABAMA")
    
    def test_validate_output(self):
        """Test output validation and clamping."""
        # Within range
        self.assertEqual(self.calculator.validate_output(1.0), 1.0)
        
        # Above maximum
        self.assertEqual(self.calculator.validate_output(3.0), 2.0)
        
        # Below minimum
        self.assertEqual(self.calculator.validate_output(-3.0), -2.0)
        
        # Non-numeric
        self.assertEqual(self.calculator.validate_output("invalid"), 0.0)
    
    def test_safe_calculate(self):
        """Test safe calculation with error handling."""
        result = self.calculator.safe_calculate("GEORGIA", "ALABAMA")
        
        self.assertTrue(result['success'])
        self.assertEqual(result['value'], 1.0)
        self.assertEqual(result['weighted_value'], 0.1)  # 1.0 * 0.1 weight
        self.assertEqual(result['home_team'], "GEORGIA")
        self.assertEqual(result['away_team'], "ALABAMA")


class TestCoachingEdgeFactors(unittest.TestCase):
    """Test coaching edge factor calculators."""
    
    def setUp(self):
        """Set up test data and calculators."""
        self.experience_calc = ExperienceDifferentialCalculator()
        self.pressure_calc = PressureSituationCalculator()
        self.venue_calc = VenuePerformanceCalculator()
        self.h2h_calc = HeadToHeadRecordCalculator()
        
        # Mock context data
        self.context = {
            'coaching_comparison': {
                'home_coaching': {
                    'head_coach_experience': 10,
                    'tenure_years': 5
                },
                'away_coaching': {
                    'head_coach_experience': 5,
                    'tenure_years': 2
                },
                'head_to_head_record': {
                    'home_wins': 3,
                    'away_wins': 1,
                    'total_games': 4
                }
            },
            'home_team_data': {
                'derived_metrics': {
                    'current_record': {'win_percentage': 0.7},
                    'venue_performance': {
                        'home_record': {'win_percentage': 0.8}
                    }
                }
            },
            'away_team_data': {
                'derived_metrics': {
                    'current_record': {'win_percentage': 0.5},
                    'venue_performance': {
                        'away_record': {'win_percentage': 0.4}
                    }
                }
            }
        }
    
    def test_experience_differential(self):
        """Test experience differential calculation."""
        # More experienced home coach
        result = self.experience_calc.calculate("GEORGIA", "ALABAMA", self.context)
        self.assertGreater(result, 0)  # Should favor home team
        self.assertLessEqual(abs(result), 2.0)  # Within bounds
        
        # Reverse experience (swap teams)
        swapped_context = {
            'coaching_comparison': {
                'home_coaching': self.context['coaching_comparison']['away_coaching'],
                'away_coaching': self.context['coaching_comparison']['home_coaching']
            }
        }
        result_swapped = self.experience_calc.calculate("GEORGIA", "ALABAMA", swapped_context)
        self.assertLess(result_swapped, 0)  # Should favor away team
        
        # No context
        result_no_context = self.experience_calc.calculate("GEORGIA", "ALABAMA", None)
        self.assertEqual(result_no_context, 0.0)
    
    def test_pressure_situation(self):
        """Test pressure situation calculation."""
        result = self.pressure_calc.calculate("GEORGIA", "ALABAMA", self.context)
        self.assertGreaterEqual(result, -2.0)
        self.assertLessEqual(result, 2.0)
        
        # Late season pressure
        late_season_context = dict(self.context)
        late_season_context['week'] = 13
        result_late = self.pressure_calc.calculate("GEORGIA", "ALABAMA", late_season_context)
        self.assertIsInstance(result_late, float)
    
    def test_venue_performance(self):
        """Test venue performance calculation."""
        result = self.venue_calc.calculate("GEORGIA", "ALABAMA", self.context)
        self.assertGreater(result, 0)  # Home team has better home record
        self.assertLessEqual(result, 1.5)  # Within max range
        
        # No venue data
        no_venue_context = {
            'home_team_data': {},
            'away_team_data': {}
        }
        result_no_data = self.venue_calc.calculate("GEORGIA", "ALABAMA", no_venue_context)
        self.assertEqual(result_no_data, 0.3)  # Base home field advantage
    
    def test_head_to_head_record(self):
        """Test head-to-head record calculation."""
        result = self.h2h_calc.calculate("GEORGIA", "ALABAMA", self.context)
        self.assertGreater(result, 0)  # Home team has winning record
        
        # Insufficient games
        few_games_context = {
            'coaching_comparison': {
                'head_to_head_record': {
                    'home_wins': 1,
                    'away_wins': 0,
                    'total_games': 1
                }
            }
        }
        result_few = self.h2h_calc.calculate("GEORGIA", "ALABAMA", few_games_context)
        self.assertEqual(result_few, 0.0)  # Not enough data


class TestSituationalContextFactors(unittest.TestCase):
    """Test situational context factor calculators."""
    
    def setUp(self):
        """Set up test data and calculators."""
        self.desperation_calc = DesperationIndexCalculator()
        self.revenge_calc = RevengeGameCalculator()
        self.lookahead_calc = LookaheadSandwichCalculator()
        self.statement_calc = StatementOpportunityCalculator()
        
        # Mock context data
        self.context = {
            'week': 10,
            'home_team_data': {
                'derived_metrics': {
                    'current_record': {
                        'wins': 5,
                        'losses': 4,
                        'win_percentage': 0.556
                    }
                }
            },
            'away_team_data': {
                'derived_metrics': {
                    'current_record': {
                        'wins': 8,
                        'losses': 1,
                        'win_percentage': 0.889
                    }
                }
            }
        }
    
    def test_desperation_index(self):
        """Test desperation index calculation."""
        result = self.desperation_calc.calculate("GEORGIA", "ALABAMA", self.context)
        # Check that result is within valid range
        self.assertGreaterEqual(result, -2.0)
        self.assertLessEqual(result, 2.0)
        
        # Early season (different desperation dynamics)
        early_context = dict(self.context)
        early_context['week'] = 2
        result_early = self.desperation_calc.calculate("GEORGIA", "ALABAMA", early_context)
        # Both should be valid calculations
        self.assertGreaterEqual(result_early, -2.0)
        self.assertLessEqual(result_early, 2.0)
    
    def test_revenge_game(self):
        """Test revenge game factor calculation."""
        result = self.revenge_calc.calculate("GEORGIA", "ALABAMA", self.context)
        self.assertGreaterEqual(result, -1.5)
        self.assertLessEqual(result, 1.5)
        
        # Known rivalry
        rivalry_result = self.revenge_calc.calculate("MICHIGAN", "OHIO STATE", self.context)
        self.assertIsInstance(rivalry_result, float)
    
    def test_lookahead_sandwich(self):
        """Test lookahead/sandwich game calculation."""
        # This requires schedule data
        schedule_context = dict(self.context)
        schedule_context['home_team_data']['schedule'] = []
        schedule_context['away_team_data']['schedule'] = []
        
        result = self.lookahead_calc.calculate("GEORGIA", "ALABAMA", schedule_context)
        self.assertGreaterEqual(result, -2.0)
        self.assertLessEqual(result, 2.0)
    
    def test_statement_opportunity(self):
        """Test statement opportunity calculation."""
        # Away team is highly ranked, home team average
        result = self.statement_calc.calculate("GEORGIA", "ALABAMA", self.context)
        self.assertGreater(result, 0)  # Home team has statement opportunity
        
        # Equal teams
        equal_context = {
            'home_team_data': self.context['home_team_data'],
            'away_team_data': self.context['home_team_data']  # Same record
        }
        result_equal = self.statement_calc.calculate("GEORGIA", "ALABAMA", equal_context)
        self.assertAlmostEqual(result_equal, 0.0, places=1)


class TestMomentumFactors(unittest.TestCase):
    """Test momentum factor calculators."""
    
    def setUp(self):
        """Set up test data and calculators."""
        self.ats_calc = ATSRecentFormCalculator()
        self.differential_calc = PointDifferentialTrendsCalculator()
        self.close_game_calc = CloseGamePerformanceCalculator()
        
        # Mock schedule data
        self.context = {
            'home_team_data': {
                'schedule': [
                    {'completed': True, 'date': '2024-09-01', 'team_score': 35, 'opponent_score': 14, 
                     'is_home_game': True, 'result': 'W'},
                    {'completed': True, 'date': '2024-09-08', 'team_score': 28, 'opponent_score': 21, 
                     'is_home_game': False, 'result': 'W'},
                    {'completed': True, 'date': '2024-09-15', 'team_score': 17, 'opponent_score': 20, 
                     'is_home_game': True, 'result': 'L'},
                    {'completed': True, 'date': '2024-09-22', 'team_score': 31, 'opponent_score': 24, 
                     'is_home_game': True, 'result': 'W'},
                ]
            },
            'away_team_data': {
                'schedule': [
                    {'completed': True, 'date': '2024-09-01', 'team_score': 42, 'opponent_score': 10, 
                     'is_home_game': True, 'result': 'W'},
                    {'completed': True, 'date': '2024-09-08', 'team_score': 38, 'opponent_score': 14, 
                     'is_home_game': True, 'result': 'W'},
                    {'completed': True, 'date': '2024-09-15', 'team_score': 45, 'opponent_score': 17, 
                     'is_home_game': False, 'result': 'W'},
                    {'completed': True, 'date': '2024-09-22', 'team_score': 35, 'opponent_score': 21, 
                     'is_home_game': True, 'result': 'W'},
                ]
            }
        }
    
    def test_ats_recent_form(self):
        """Test ATS recent form calculation."""
        result = self.ats_calc.calculate("GEORGIA", "ALABAMA", self.context)
        self.assertGreaterEqual(result, -2.0)
        self.assertLessEqual(result, 2.0)
        
        # No schedule data
        no_schedule = {'home_team_data': {}, 'away_team_data': {}}
        result_no_data = self.ats_calc.calculate("GEORGIA", "ALABAMA", no_schedule)
        self.assertEqual(result_no_data, 0.0)
    
    def test_point_differential_trends(self):
        """Test point differential trends calculation."""
        result = self.differential_calc.calculate("GEORGIA", "ALABAMA", self.context)
        # Away team has better point differentials
        self.assertLess(result, 0)  # Should favor away team
        
        # Consistent performance check
        # Home team has mix of blowout and close games
        # Away team has consistent blowouts
        self.assertIsInstance(result, float)
    
    def test_close_game_performance(self):
        """Test close game performance calculation."""
        result = self.close_game_calc.calculate("GEORGIA", "ALABAMA", self.context)
        self.assertGreaterEqual(result, -1.5)
        self.assertLessEqual(result, 1.5)
        
        # Add more close games
        close_game_context = dict(self.context)
        close_game_context['home_team_data']['schedule'].extend([
            {'completed': True, 'date': '2024-09-29', 'team_score': 24, 'opponent_score': 21, 
             'is_home_game': True, 'result': 'W'},
            {'completed': True, 'date': '2024-10-06', 'team_score': 20, 'opponent_score': 23, 
             'is_home_game': False, 'result': 'L'},
        ])
        
        result_close = self.close_game_calc.calculate("GEORGIA", "ALABAMA", close_game_context)
        self.assertNotEqual(result_close, 0.0)  # Should have clutch factor


class TestFactorIntegration(unittest.TestCase):
    """Test factor integration and edge cases."""
    
    def test_all_factors_have_correct_weights(self):
        """Test that all factor weights sum to 1.0."""
        from factors.factor_registry import factor_registry
        
        total_weight = sum(f.weight for f in factor_registry.factors.values())
        self.assertAlmostEqual(total_weight, 1.0, places=3)
    
    def test_all_factors_have_valid_ranges(self):
        """Test that all factors have valid output ranges."""
        from factors.factor_registry import factor_registry
        
        for name, factor in factor_registry.factors.items():
            min_val, max_val = factor.get_output_range()
            self.assertLess(min_val, max_val, f"{name} has invalid range")
            self.assertGreaterEqual(min_val, -5.0, f"{name} min too low")
            self.assertLessEqual(max_val, 5.0, f"{name} max too high")
    
    def test_factor_categories_are_valid(self):
        """Test that all factors belong to valid categories."""
        from factors.factor_registry import factor_registry
        
        valid_categories = {'coaching_edge', 'situational_context', 'momentum_factors'}
        
        for name, factor in factor_registry.factors.items():
            self.assertIn(factor.category, valid_categories, 
                         f"{name} has invalid category: {factor.category}")
    
    def test_factors_handle_missing_data_gracefully(self):
        """Test that all factors handle missing data without crashing."""
        from factors.factor_registry import factor_registry
        
        # Test with various levels of missing data
        test_contexts = [
            None,  # No context
            {},    # Empty context
            {'home_team_data': {}, 'away_team_data': {}},  # Empty team data
            {'week': 7},  # Only week data
        ]
        
        for context in test_contexts:
            results = factor_registry.calculate_all_factors("GEORGIA", "ALABAMA", context)
            
            # Should complete without crashing
            self.assertIn('factors', results)
            self.assertIn('summary', results)
            self.assertGreaterEqual(results['summary']['factors_calculated'], 0)


if __name__ == '__main__':
    unittest.main()