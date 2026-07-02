"""
Integration tests for real-world scenarios in College Football Market Edge Platform.
Tests specific betting situations and edge cases that occur in practice.
"""

import unittest
from unittest.mock import patch, Mock, MagicMock
from datetime import datetime, timedelta
import time

from engine.prediction_engine import prediction_engine
from engine.confidence_calculator import confidence_calculator
from engine.edge_detector import edge_detector, EdgeType
from factors.factor_registry import factor_registry
from data.data_manager import data_manager
from output.formatter import output_formatter
from output.insights_generator import insights_generator
from utils.normalizer import normalizer


class TestRealWorldScenarios(unittest.TestCase):
    """Test real-world betting scenarios and edge cases."""
    
    def setUp(self):
        """Set up test environment."""
        self.maxDiff = None  # Show full diff for complex objects
    
    def test_playoff_elimination_game_scenario(self):
        """Test high-stakes playoff elimination game."""
        # Scenario: Week 13, one team needs win for playoff contention
        with patch('data.odds_client.OddsAPIClient.get_consensus_spread') as mock_odds, \
             patch('data.espn_client.ESPNStatsClient.get_team_info') as mock_espn:
            
            # Mock spread: Georgia slightly favored
            mock_odds.return_value = -2.5
            
            # Mock team data: Both teams good, but Alabama desperate
            mock_espn.side_effect = [
                # Georgia data (home)
                {
                    'info': {'conference': {'name': 'SEC'}},
                    'derived_metrics': {
                        'current_record': {'wins': 10, 'losses': 1, 'win_percentage': 0.909},
                        'venue_performance': {
                            'home_record': {'win_percentage': 0.900},
                            'away_record': {'win_percentage': 0.850}
                        }
                    },
                    'schedule': [
                        {'completed': True, 'date': '2024-11-01', 'team_score': 31, 'opponent_score': 17, 'result': 'W'},
                        {'completed': True, 'date': '2024-11-08', 'team_score': 28, 'opponent_score': 21, 'result': 'W'},
                        {'completed': True, 'date': '2024-11-15', 'team_score': 24, 'opponent_score': 27, 'result': 'L'},
                        {'completed': True, 'date': '2024-11-22', 'team_score': 35, 'opponent_score': 14, 'result': 'W'},
                    ]
                },
                # Alabama data (away) - needs this win
                {
                    'info': {'conference': {'name': 'SEC'}},
                    'derived_metrics': {
                        'current_record': {'wins': 9, 'losses': 2, 'win_percentage': 0.818},
                        'venue_performance': {
                            'home_record': {'win_percentage': 0.800},
                            'away_record': {'win_percentage': 0.750}
                        }
                    },
                    'schedule': [
                        {'completed': True, 'date': '2024-11-01', 'team_score': 42, 'opponent_score': 21, 'result': 'W'},
                        {'completed': True, 'date': '2024-11-08', 'team_score': 17, 'opponent_score': 24, 'result': 'L'},
                        {'completed': True, 'date': '2024-11-15', 'team_score': 21, 'opponent_score': 28, 'result': 'L'},
                        {'completed': True, 'date': '2024-11-22', 'team_score': 38, 'opponent_score': 10, 'result': 'W'},
                    ]
                }
            ]
            
            # Generate prediction for Week 13 desperation game
            result = prediction_engine.generate_prediction("GEORGIA", "ALABAMA", week=13)
            
            # Assertions for playoff elimination scenario
            self.assertFalse(result.get('error'), "Prediction should not fail")
            
            # Should detect some edge due to desperation
            edge_size = result.get('edge_size', 0.0)
            self.assertGreater(edge_size, 0.0, "Should detect some edge from factors")
            
            # Confidence should be reasonable despite high stakes
            confidence = result.get('confidence_score', 0.0)
            self.assertGreater(confidence, 0.4, "Should have reasonable confidence")
            self.assertLess(confidence, 0.9, "Should not be overconfident in high-variance game")
            
            # Should mention desperation in factors
            self.assertIn('factor_breakdown', result)
            if 'DesperationIndex' in result['factor_breakdown']:
                desp_factor = result['factor_breakdown']['DesperationIndex']
                self.assertTrue(desp_factor.get('success', False), "Desperation factor should calculate")
    
    def test_weather_game_scenario(self):
        """Test game with adverse weather conditions."""
        # Scenario: November game in harsh weather
        with patch('data.odds_client.OddsAPIClient.get_consensus_spread') as mock_odds, \
             patch('data.espn_client.ESPNStatsClient.get_team_info') as mock_espn:
            
            mock_odds.return_value = -6.5  # Normal spread
            
            # Mock normal team data
            mock_team_data = {
                'info': {'conference': {'name': 'BIG TEN'}},
                'derived_metrics': {
                    'current_record': {'wins': 7, 'losses': 3, 'win_percentage': 0.7},
                    'venue_performance': {
                        'home_record': {'win_percentage': 0.8},
                        'away_record': {'win_percentage': 0.6}
                    }
                }
            }
            mock_espn.return_value = mock_team_data
            
            # Test late-season northern game (weather implications)
            result = prediction_engine.generate_prediction("MICHIGAN", "OHIO STATE", week=12)
            
            # Weather typically favors ground game and home teams
            self.assertFalse(result.get('error'), "Weather game should not fail")
            
            # Should have some venue performance consideration
            if 'VenuePerformance' in result.get('factor_breakdown', {}):
                venue_factor = result['factor_breakdown']['VenuePerformance']
                self.assertTrue(venue_factor.get('success', False))
    
    def test_rivalry_game_unpredictability(self):
        """Test traditional rivalry game with historical unpredictability."""
        with patch('data.odds_client.OddsAPIClient.get_consensus_spread') as mock_odds, \
             patch('data.espn_client.ESPNStatsClient.get_team_info') as mock_espn:
            
            mock_odds.return_value = -10.5  # Large spread
            
            # Mock data: One team much better on paper
            mock_espn.side_effect = [
                # Michigan (home) - good team
                {
                    'info': {'conference': {'name': 'BIG TEN'}},
                    'derived_metrics': {
                        'current_record': {'wins': 10, 'losses': 1, 'win_percentage': 0.909},
                        'venue_performance': {'home_record': {'win_percentage': 0.950}}
                    }
                },
                # Ohio State (away) - struggling season
                {
                    'info': {'conference': {'name': 'BIG TEN'}},
                    'derived_metrics': {
                        'current_record': {'wins': 6, 'losses': 5, 'win_percentage': 0.545},
                        'venue_performance': {'away_record': {'win_percentage': 0.500}}
                    }
                }
            ]
            
            result = prediction_engine.generate_prediction("MICHIGAN", "OHIO STATE", week=12)
            
            # Rivalry games often have different dynamics
            self.assertFalse(result.get('error'))
            
            # Check if system detects potential for upset/closer game
            if 'RevengeGame' in result.get('factor_breakdown', {}):
                revenge_factor = result['factor_breakdown']['RevengeGame']
                # Revenge factor should activate for known rivals
                self.assertTrue(revenge_factor.get('success', False) or revenge_factor.get('value', 0) != 0)
    
    def test_conference_championship_scenario(self):
        """Test conference championship game scenario."""
        with patch('data.odds_client.OddsAPIClient.get_consensus_spread') as mock_odds, \
             patch('data.espn_client.ESPNStatsClient.get_team_info') as mock_espn:
            
            mock_odds.return_value = -3.0  # Close championship game
            
            # Both teams should be very good (made championship)
            championship_team_data = {
                'info': {'conference': {'name': 'SEC'}},
                'derived_metrics': {
                    'current_record': {'wins': 11, 'losses': 1, 'win_percentage': 0.917},
                    'venue_performance': {
                        'home_record': {'win_percentage': 0.900},
                        'away_record': {'win_percentage': 0.850}
                    }
                }
            }
            mock_espn.return_value = championship_team_data
            
            # Week 14 championship game
            result = prediction_engine.generate_prediction("GEORGIA", "ALABAMA", week=14)
            
            self.assertFalse(result.get('error'))
            
            # Championship games have high stakes
            confidence = result.get('confidence_score', 0.0)
            # Should be cautious with championship game due to high variance
            self.assertLess(confidence, 0.85, "Should be cautious with championship game variance")
    
    def test_unranked_vs_ranked_trap_game(self):
        """Test unranked home team vs ranked away team (classic trap game)."""
        with patch('data.odds_client.OddsAPIClient.get_consensus_spread') as mock_odds, \
             patch('data.espn_client.ESPNStatsClient.get_team_info') as mock_espn:
            
            mock_odds.return_value = 7.5  # Away team heavily favored
            
            mock_espn.side_effect = [
                # Home team (unranked, decent)
                {
                    'info': {'conference': {'name': 'PAC-12'}},
                    'derived_metrics': {
                        'current_record': {'wins': 6, 'losses': 4, 'win_percentage': 0.6},
                        'venue_performance': {'home_record': {'win_percentage': 0.8}}  # Strong at home
                    }
                },
                # Away team (ranked, traveling)
                {
                    'info': {'conference': {'name': 'PAC-12'}},
                    'derived_metrics': {
                        'current_record': {'wins': 9, 'losses': 1, 'win_percentage': 0.9},
                        'venue_performance': {'away_record': {'win_percentage': 0.7}}  # Weaker on road
                    }
                }
            ]
            
            result = prediction_engine.generate_prediction("STANFORD", "USC", week=8)
            
            self.assertFalse(result.get('error'))
            
            # Should detect some value on home team due to venue performance
            if 'VenuePerformance' in result.get('factor_breakdown', {}):
                venue_factor = result['factor_breakdown']['VenuePerformance']
                self.assertTrue(venue_factor.get('success', False))
                # Home team should get some venue boost
                self.assertGreater(venue_factor.get('value', 0), 0)
    
    def test_bowl_eligibility_desperation(self):
        """Test team on bubble for bowl eligibility."""
        with patch('data.odds_client.OddsAPIClient.get_consensus_spread') as mock_odds, \
             patch('data.espn_client.ESPNStatsClient.get_team_info') as mock_espn:
            
            mock_odds.return_value = -1.5  # Close game
            
            mock_espn.side_effect = [
                # Home team (5-6, needs win for bowl)
                {
                    'info': {'conference': {'name': 'ACC'}},
                    'derived_metrics': {
                        'current_record': {'wins': 5, 'losses': 6, 'win_percentage': 0.455},
                        'venue_performance': {'home_record': {'win_percentage': 0.6}}
                    }
                },
                # Away team (7-4, bowl eligible)
                {
                    'info': {'conference': {'name': 'ACC'}},
                    'derived_metrics': {
                        'current_record': {'wins': 7, 'losses': 4, 'win_percentage': 0.636},
                        'venue_performance': {'away_record': {'win_percentage': 0.5}}
                    }
                }
            ]
            
            result = prediction_engine.generate_prediction("FLORIDA STATE", "CLEMSON", week=12)
            
            self.assertFalse(result.get('error'))
            
            # Should detect desperation for home team
            if 'DesperationIndex' in result.get('factor_breakdown', {}):
                desp_factor = result['factor_breakdown']['DesperationIndex']
                if desp_factor.get('success', False):
                    # Home team should have higher desperation
                    self.assertGreater(desp_factor.get('value', 0), -0.5)
    
    def test_lookahead_sandwich_game(self):
        """Test team with big game next week (lookahead concern)."""
        with patch('data.odds_client.OddsAPIClient.get_consensus_spread') as mock_odds, \
             patch('data.espn_client.ESPNStatsClient.get_team_info') as mock_espn:
            
            mock_odds.return_value = -14.0  # Big favorite
            
            # Mock team with easy game this week, big game next week
            mock_espn.side_effect = [
                # Favored team
                {
                    'info': {'conference': {'name': 'SEC'}},
                    'derived_metrics': {
                        'current_record': {'wins': 9, 'losses': 1, 'win_percentage': 0.9},
                        'venue_performance': {'home_record': {'win_percentage': 0.95}}
                    },
                    'schedule': [
                        {'date': '2024-11-08', 'opponent': 'WEAK_TEAM', 'completed': False},
                        {'date': '2024-11-15', 'opponent': 'ALABAMA', 'completed': False}  # Big game next
                    ]
                },
                # Underdog team
                {
                    'info': {'conference': {'name': 'SEC'}},
                    'derived_metrics': {
                        'current_record': {'wins': 3, 'losses': 7, 'win_percentage': 0.3},
                        'venue_performance': {'away_record': {'win_percentage': 0.2}}
                    }
                }
            ]
            
            result = prediction_engine.generate_prediction("GEORGIA", "VANDERBILT", week=11)
            
            self.assertFalse(result.get('error'))
            
            # Check if lookahead factor detected potential distraction
            if 'LookaheadSandwich' in result.get('factor_breakdown', {}):
                lookahead_factor = result['factor_breakdown']['LookaheadSandwich']
                # May or may not trigger depending on schedule data availability
                if lookahead_factor.get('success', False):
                    # If it triggers, should slightly favor underdog
                    self.assertLessEqual(lookahead_factor.get('value', 0), 0.5)
    
    def test_early_season_limited_data(self):
        """Test early season game with limited historical data."""
        with patch('data.odds_client.OddsAPIClient.get_consensus_spread') as mock_odds, \
             patch('data.espn_client.ESPNStatsClient.get_team_info') as mock_espn:
            
            mock_odds.return_value = -6.0
            
            # Limited early season data
            early_season_data = {
                'info': {'conference': {'name': 'BIG TEN'}},
                'derived_metrics': {
                    'current_record': {'wins': 2, 'losses': 0, 'win_percentage': 1.0},
                    'venue_performance': {
                        'home_record': {'win_percentage': 1.0},  # Small sample
                        'away_record': {'win_percentage': 0.0}
                    }
                },
                'schedule': [
                    {'completed': True, 'date': '2024-09-01', 'team_score': 35, 'opponent_score': 10, 'result': 'W'},
                    {'completed': True, 'date': '2024-09-08', 'team_score': 28, 'opponent_score': 21, 'result': 'W'}
                ]
            }
            mock_espn.return_value = early_season_data
            
            result = prediction_engine.generate_prediction("MICHIGAN", "TEXAS", week=3)
            
            self.assertFalse(result.get('error'))
            
            # Confidence should be lower due to limited data
            confidence = result.get('confidence_score', 0.0)
            self.assertLess(confidence, 0.8, "Should have lower confidence with limited early season data")
            
            # Data quality should reflect limited information
            data_quality = result.get('data_quality', 1.0)
            self.assertLess(data_quality, 0.9, "Data quality should reflect early season limitations")
    
    def test_late_season_injury_impact(self):
        """Test late season game with potential injury impact on data quality."""
        with patch('data.odds_client.OddsAPIClient.get_consensus_spread') as mock_odds, \
             patch('data.espn_client.ESPNStatsClient.get_team_info') as mock_espn:
            
            mock_odds.return_value = -4.5
            
            # Mock data that might be stale due to key player injury
            mock_team_data = {
                'info': {'conference': {'name': 'SEC'}},
                'derived_metrics': {
                    'current_record': {'wins': 8, 'losses': 3, 'win_percentage': 0.727},
                    'venue_performance': {'home_record': {'win_percentage': 0.8}}
                }
            }
            mock_espn.return_value = mock_team_data
            
            # Late season game where injury status matters
            result = prediction_engine.generate_prediction("GEORGIA", "TENNESSEE", week=12)
            
            self.assertFalse(result.get('error'))
            
            # System should still generate prediction but may have lower confidence
            # due to potential data staleness
            self.assertIn('confidence_score', result)
            self.assertGreater(result['confidence_score'], 0.15)  # Above minimum
    
    def test_system_resilience_to_api_failures(self):
        """Test system resilience when APIs partially fail."""
        with patch('data.odds_client.OddsAPIClient.get_consensus_spread') as mock_odds, \
             patch('data.espn_client.ESPNStatsClient.get_team_info') as mock_espn:
            
            # Odds API works, ESPN fails
            mock_odds.return_value = -3.5
            mock_espn.side_effect = Exception("ESPN API temporarily unavailable")
            
            result = prediction_engine.generate_prediction("GEORGIA", "ALABAMA", week=8)
            
            # Should gracefully handle partial failure
            # Either succeed with degraded data or fail gracefully
            if result.get('error'):
                # If it fails, should be graceful
                self.assertIn('error', result)
                self.assertEqual(result.get('prediction_type'), 'ERROR')
            else:
                # If it succeeds, should note data quality issues
                self.assertLess(result.get('data_quality', 1.0), 0.8)
                self.assertLess(result.get('confidence_score', 1.0), 0.7)
    
    def test_neutral_site_game_handling(self):
        """Test handling of neutral site games (bowls, championship games)."""
        with patch('data.odds_client.OddsAPIClient.get_consensus_spread') as mock_odds, \
             patch('data.espn_client.ESPNStatsClient.get_team_info') as mock_espn:
            
            mock_odds.return_value = -2.5  # Close neutral site game
            
            neutral_site_data = {
                'info': {'conference': {'name': 'SEC'}},
                'derived_metrics': {
                    'current_record': {'wins': 10, 'losses': 2, 'win_percentage': 0.833},
                    'venue_performance': {
                        'home_record': {'win_percentage': 0.85},
                        'away_record': {'win_percentage': 0.75},
                        'neutral_record': {'win_percentage': 0.80}  # If available
                    }
                }
            }
            mock_espn.return_value = neutral_site_data
            
            # Could be bowl game or championship
            result = prediction_engine.generate_prediction("GEORGIA", "TEXAS", week=15)
            
            self.assertFalse(result.get('error'))
            
            # Venue performance factor should handle neutral sites
            if 'VenuePerformance' in result.get('factor_breakdown', {}):
                venue_factor = result['factor_breakdown']['VenuePerformance']
                # Should not give full home field advantage
                if venue_factor.get('success', False):
                    venue_value = venue_factor.get('value', 0)
                    # Should be less than typical home advantage
                    self.assertLess(abs(venue_value), 1.0)
    
    def test_conference_strength_differential(self):
        """Test games between teams from different strength conferences."""
        with patch('data.odds_client.OddsAPIClient.get_consensus_spread') as mock_odds, \
             patch('data.espn_client.ESPNStatsClient.get_team_info') as mock_espn:
            
            mock_odds.return_value = -7.0
            
            mock_espn.side_effect = [
                # SEC team (traditionally stronger conference)
                {
                    'info': {'conference': {'name': 'SEC'}},
                    'derived_metrics': {
                        'current_record': {'wins': 8, 'losses': 2, 'win_percentage': 0.8},
                        'venue_performance': {'home_record': {'win_percentage': 0.85}}
                    }
                },
                # Group of 5 team
                {
                    'info': {'conference': {'name': 'AMERICAN'}},
                    'derived_metrics': {
                        'current_record': {'wins': 9, 'losses': 1, 'win_percentage': 0.9},
                        'venue_performance': {'away_record': {'win_percentage': 0.7}}
                    }
                }
            ]
            
            result = prediction_engine.generate_prediction("GEORGIA", "CINCINNATI", week=8)
            
            self.assertFalse(result.get('error'))
            
            # System should handle cross-conference games
            # May not have sophisticated conference strength adjustments
            # but should not crash or produce extreme values
            edge_size = result.get('edge_size', 0.0)
            self.assertLess(abs(edge_size), 10.0, "Edge size should be reasonable")


class TestSystemIntegrationFlow(unittest.TestCase):
    """Test complete system integration flow from input to output."""
    
    def test_complete_prediction_to_output_flow(self):
        """Test complete flow from prediction through formatting."""
        with patch('data.odds_client.OddsAPIClient.get_consensus_spread') as mock_odds, \
             patch('data.espn_client.ESPNStatsClient.get_team_info') as mock_espn:
            
            mock_odds.return_value = -3.5
            mock_espn.return_value = {
                'info': {'conference': {'name': 'SEC'}},
                'derived_metrics': {
                    'current_record': {'wins': 8, 'losses': 2, 'win_percentage': 0.8},
                    'venue_performance': {'home_record': {'win_percentage': 0.85}}
                }
            }
            
            # Generate prediction
            prediction = prediction_engine.generate_prediction("GEORGIA", "ALABAMA", week=8)
            
            self.assertFalse(prediction.get('error'))
            
            # Generate confidence assessment
            if 'factor_breakdown' in prediction:
                factors = {
                    'summary': {
                        'factors_calculated': len(prediction.get('factor_breakdown', {})),
                        'factors_successful': sum(1 for f in prediction.get('factor_breakdown', {}).values() 
                                                if f.get('success', False)),
                        'category_adjustments': prediction.get('category_adjustments', {})
                    },
                    'factors': prediction.get('factor_breakdown', {})
                }
                
                context = {
                    'data_quality': prediction.get('data_quality', 0.75),
                    'vegas_spread': prediction.get('vegas_spread'),
                    'week': 8
                }
                
                confidence_assessment = confidence_calculator.calculate_confidence(
                    prediction, factors, context
                )
                
                # Generate edge classification
                edge_classification = edge_detector.detect_edge(
                    prediction, confidence_assessment, context
                )
                
                # Generate insights
                insights = insights_generator.generate_prediction_insights(
                    prediction, confidence_assessment, edge_classification, context
                )
                
                # Format output
                formatted_output = output_formatter.format_prediction_output(
                    prediction, confidence_assessment, edge_classification, insights,
                    show_details=True, show_factors=True
                )
                
                # Validate complete output
                self.assertIsInstance(formatted_output, str)
                self.assertIn('College Football Market Edge Platform', formatted_output)
                self.assertIn('GEORGIA', formatted_output)
                self.assertIn('ALABAMA', formatted_output)
                self.assertIn('PREDICTION SUMMARY', formatted_output)
                self.assertIn('EDGE ANALYSIS', formatted_output)
    
    def test_error_handling_integration_flow(self):
        """Test error handling through complete integration flow."""
        with patch('data.odds_client.OddsAPIClient.get_consensus_spread') as mock_odds:
            
            # Simulate complete API failure
            mock_odds.side_effect = Exception("Network error")
            
            # Should handle gracefully
            prediction = prediction_engine.generate_prediction("GEORGIA", "ALABAMA", week=8)
            
            # Should either recover or fail gracefully
            if prediction.get('error'):
                self.assertEqual(prediction.get('prediction_type'), 'ERROR')
                self.assertFalse(prediction.get('has_edge', True))
                
                # Error output should be formattable
                error_output = output_formatter.format_error_output(
                    prediction['error'], 
                    {'requested_home': 'GEORGIA', 'requested_away': 'ALABAMA'}
                )
                
                self.assertIsInstance(error_output, str)
                self.assertIn('PREDICTION ERROR', error_output)
    
    def test_performance_under_load(self):
        """Test system performance with multiple rapid requests."""
        with patch('data.odds_client.OddsAPIClient.get_consensus_spread') as mock_odds, \
             patch('data.espn_client.ESPNStatsClient.get_team_info') as mock_espn:
            
            mock_odds.return_value = -3.5
            mock_espn.return_value = {
                'info': {'conference': {'name': 'SEC'}},
                'derived_metrics': {
                    'current_record': {'wins': 8, 'losses': 2, 'win_percentage': 0.8},
                    'venue_performance': {'home_record': {'win_percentage': 0.85}}
                }
            }
            
            # Generate multiple predictions rapidly
            start_time = time.time()
            
            for i in range(5):
                prediction = prediction_engine.generate_prediction("GEORGIA", "ALABAMA", week=8)
                self.assertFalse(prediction.get('error'), f"Prediction {i} failed")
            
            total_time = time.time() - start_time
            
            # Should complete reasonably quickly
            self.assertLess(total_time, 30.0, "5 predictions took too long")
            
            # Average should be under target
            avg_time = total_time / 5
            self.assertLess(avg_time, 15.0, f"Average prediction time {avg_time:.1f}s exceeds 15s target")


if __name__ == '__main__':
    print("Running real-world scenario integration tests...")
    unittest.main()