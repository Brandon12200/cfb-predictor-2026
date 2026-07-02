"""
Integration tests for College Football Market Edge Platform.
Tests the complete prediction pipeline end-to-end.
"""

import unittest
from unittest.mock import Mock, patch
import time
from datetime import datetime

from engine.prediction_engine import prediction_engine
from engine.confidence_calculator import confidence_calculator
from engine.edge_detector import edge_detector, EdgeType
from data.data_manager import data_manager
from utils.normalizer import normalizer


class TestPredictionPipeline(unittest.TestCase):
    """Test the complete prediction pipeline."""
    
    def setUp(self):
        """Set up test environment."""
        # Mock data for consistent testing
        self.mock_context = {
            'vegas_spread': -3.5,
            'data_quality': 0.75,
            'data_sources': ['odds_api', 'espn_api'],
            'week': 8,
            'home_team_data': {
                'info': {'conference': {'name': 'SEC'}},
                'derived_metrics': {
                    'current_record': {'wins': 6, 'losses': 2, 'win_percentage': 0.75},
                    'venue_performance': {
                        'home_record': {'win_percentage': 0.85}
                    }
                }
            },
            'away_team_data': {
                'info': {'conference': {'name': 'SEC'}},
                'derived_metrics': {
                    'current_record': {'wins': 7, 'losses': 1, 'win_percentage': 0.875},
                    'venue_performance': {
                        'away_record': {'win_percentage': 0.60}
                    }
                }
            },
            'coaching_comparison': {
                'home_coaching': {'head_coach_experience': 8, 'tenure_years': 4},
                'away_coaching': {'head_coach_experience': 12, 'tenure_years': 6}
            }
        }
    
    @patch('data.data_manager.DataManager.get_game_context')
    def test_full_prediction_pipeline(self, mock_get_context):
        """Test complete prediction generation."""
        mock_get_context.return_value = self.mock_context
        
        # Generate prediction
        result = prediction_engine.generate_prediction("GEORGIA", "ALABAMA", week=8)
        
        # Verify structure
        self.assertIn('home_team', result)
        self.assertIn('away_team', result)
        self.assertIn('vegas_spread', result)
        self.assertIn('contrarian_spread', result)
        self.assertIn('edge_size', result)
        self.assertIn('confidence_score', result)
        self.assertIn('recommendation', result)
        
        # Verify calculations
        self.assertEqual(result['vegas_spread'], -3.5)
        self.assertIsInstance(result['contrarian_spread'], float)
        self.assertIsInstance(result['edge_size'], float)
        self.assertGreater(result['confidence_score'], 0.15)
        self.assertLess(result['confidence_score'], 0.95)
    
    @patch('data.data_manager.DataManager.get_game_context')
    def test_strong_contrarian_edge_detection(self, mock_get_context):
        """Test detection of strong contrarian opportunity."""
        # Create context with factors that create large edge
        strong_edge_context = dict(self.mock_context)
        strong_edge_context['vegas_spread'] = -7.0
        
        mock_get_context.return_value = strong_edge_context
        
        # Generate prediction with mocked factor results
        with patch('factors.factor_registry.FactorRegistry.calculate_all_factors') as mock_factors:
            mock_factors.return_value = {
                'summary': {
                    'total_adjustment': 4.0,  # Large adjustment creates strong edge
                    'factors_calculated': 11,
                    'factors_successful': 10,
                    'category_adjustments': {
                        'coaching_edge': 2.0,
                        'situational_context': 1.5,
                        'momentum_factors': 0.5
                    }
                },
                'factors': {}
            }
            
            result = prediction_engine.generate_prediction("GEORGIA", "ALABAMA", week=8)
            
            # Verify strong edge detection
            self.assertGreaterEqual(result['edge_size'], 3.0)
            self.assertEqual(result['prediction_type'], 'STRONG_CONTRARIAN')
            self.assertTrue(result['has_edge'])
    
    @patch('data.data_manager.DataManager.get_game_context')
    def test_no_betting_data_handling(self, mock_get_context):
        """Test handling when no Vegas spread available."""
        no_spread_context = dict(self.mock_context)
        no_spread_context['vegas_spread'] = None
        
        mock_get_context.return_value = no_spread_context
        
        result = prediction_engine.generate_prediction("GEORGIA", "ALABAMA", week=8)
        
        # Check if error occurred
        if 'error' in result:
            self.assertEqual(result['prediction_type'], 'ERROR')
            self.assertFalse(result['has_edge'])
        else:
            self.assertIsNone(result.get('contrarian_spread'))
            self.assertIsNone(result.get('edge_size'))
            self.assertEqual(result.get('prediction_type'), 'NO_BETTING_DATA')
            self.assertFalse(result.get('has_edge', False))
    
    def test_confidence_calculation_components(self):
        """Test confidence calculator with various inputs."""
        # High confidence scenario
        high_conf_prediction = {
            'edge_size': 3.5,
            'prediction_type': 'STRONG_CONTRARIAN',
            'vegas_spread': -3.5,
            'contrarian_spread': 0.0
        }
        
        high_conf_factors = {
            'summary': {
                'factors_calculated': 11,
                'factors_successful': 11,
                'category_adjustments': {'coaching_edge': 2.0}
            },
            'factors': {
                'ExperienceDifferential': {'success': True, 'value': 1.5, 'weight': 0.1},
                'DesperationIndex': {'success': True, 'value': 0.5, 'weight': 0.1}
            }
        }
        
        high_conf_context = {
            'data_quality': 0.9,
            'vegas_spread': -3.5,
            'data_sources': ['odds_api', 'espn_api'],
            'week': 7
        }
        
        confidence = confidence_calculator.calculate_confidence(
            high_conf_prediction, high_conf_factors, high_conf_context
        )
        
        self.assertGreater(confidence['confidence_score'], 0.7)
        self.assertEqual(confidence['confidence_level'], 'High')
        
        # Low confidence scenario
        low_conf_context = {
            'data_quality': 0.2,
            'vegas_spread': -3.5,
            'data_sources': ['odds_api'],
            'week': 1
        }
        
        low_conf_factors = {
            'summary': {
                'factors_calculated': 11,
                'factors_successful': 3,
                'category_adjustments': {}
            },
            'factors': {}
        }
        
        confidence_low = confidence_calculator.calculate_confidence(
            high_conf_prediction, low_conf_factors, low_conf_context
        )
        
        self.assertLess(confidence_low['confidence_score'], 0.5)
        self.assertIn(confidence_low['confidence_level'], ['Low', 'Very Low'])
    
    def test_edge_detector_classifications(self):
        """Test edge detector with various scenarios."""
        # Test all edge types
        test_cases = [
            (4.0, 0.8, EdgeType.STRONG_CONTRARIAN),
            (2.5, 0.7, EdgeType.MODERATE_CONTRARIAN),
            (1.5, 0.6, EdgeType.SLIGHT_CONTRARIAN),
            (0.7, 0.5, EdgeType.CONSENSUS_PLAY),
            (0.3, 0.4, EdgeType.NO_EDGE),
        ]
        
        for edge_size, confidence, expected_type in test_cases:
            prediction_result = {
                'edge_size': edge_size,
                'vegas_spread': -3.5,
                'contrarian_spread': -3.5 + edge_size,
                'edge_direction': 'home' if edge_size > 0 else 'away',
                'home_team': 'GEORGIA',
                'away_team': 'ALABAMA'
            }
            
            confidence_assessment = {
                'confidence_score': confidence,
                'confidence_level': 'High' if confidence > 0.7 else 'Medium'
            }
            
            context = {'data_quality': 0.8}
            
            edge_class = edge_detector.detect_edge(
                prediction_result, confidence_assessment, context
            )
            
            self.assertEqual(edge_class.edge_type, expected_type)
            self.assertEqual(edge_class.edge_size, edge_size)
            self.assertEqual(edge_class.confidence, confidence)


class TestPerformanceRequirements(unittest.TestCase):
    """Test performance requirements."""
    
    @patch('data.data_manager.DataManager.get_game_context')
    def test_execution_time_under_15_seconds(self, mock_get_context):
        """Test that predictions complete within 15 seconds."""
        # Mock data to avoid actual API calls
        mock_get_context.return_value = {
            'vegas_spread': -3.5,
            'data_quality': 0.5,
            'data_sources': ['mock'],
            'home_team_data': {},
            'away_team_data': {},
            'coaching_comparison': {}
        }
        
        start_time = time.time()
        
        # Generate prediction
        result = prediction_engine.generate_prediction("GEORGIA", "ALABAMA")
        
        execution_time = time.time() - start_time
        
        self.assertLess(execution_time, 15.0, 
                       f"Execution took {execution_time:.2f}s, exceeds 15s limit")
        self.assertIsNotNone(result)
    
    def test_factor_calculation_performance(self):
        """Test that factor calculations are efficient."""
        from factors.factor_registry import factor_registry
        
        context = {
            'home_team_data': {'derived_metrics': {}},
            'away_team_data': {'derived_metrics': {}},
            'coaching_comparison': {}
        }
        
        start_time = time.time()
        
        # Calculate all factors
        results = factor_registry.calculate_all_factors("GEORGIA", "ALABAMA", context)
        
        execution_time = time.time() - start_time
        
        self.assertLess(execution_time, 1.0, 
                       f"Factor calculation took {execution_time:.2f}s, too slow")
        self.assertEqual(results['summary']['factors_calculated'], 11)


class TestErrorHandling(unittest.TestCase):
    """Test error handling and edge cases."""
    
    def test_invalid_team_names(self):
        """Test handling of invalid team names."""
        result = prediction_engine.generate_prediction("INVALID_TEAM_XYZ", "ANOTHER_FAKE", week=8)
        
        self.assertIn('error', result)
        self.assertEqual(result['prediction_type'], 'ERROR')
        self.assertFalse(result['has_edge'])
        self.assertEqual(result['confidence_score'], 0.0)
    
    @patch('data.data_manager.DataManager.get_game_context')
    def test_api_failure_handling(self, mock_get_context):
        """Test handling when APIs fail."""
        mock_get_context.side_effect = Exception("API connection failed")
        
        result = prediction_engine.generate_prediction("GEORGIA", "ALABAMA", week=8)
        
        self.assertIn('error', result)
        self.assertIn('Prediction failed', result['recommendation'])
    
    def test_partial_data_handling(self):
        """Test handling of partial data scenarios."""
        partial_contexts = [
            {},  # Empty context
            {'vegas_spread': -3.5},  # Only spread
            {'home_team_data': {}, 'away_team_data': {}},  # Empty team data
            {'data_quality': 0.1, 'data_sources': []}  # Low quality
        ]
        
        for context in partial_contexts:
            with patch('data.data_manager.DataManager.get_game_context') as mock_get:
                mock_get.return_value = context
                
                result = prediction_engine.generate_prediction("GEORGIA", "ALABAMA")
                
                # Should not crash
                self.assertIsNotNone(result)
                self.assertIn('confidence_score', result)
    
    def test_extreme_values_handling(self):
        """Test handling of extreme factor values."""
        with patch('factors.factor_registry.FactorRegistry.calculate_all_factors') as mock_factors:
            # Extreme adjustment that would be suspicious
            mock_factors.return_value = {
                'summary': {
                    'total_adjustment': 10.0,  # Unrealistic adjustment
                    'factors_calculated': 11,
                    'factors_successful': 11,
                    'category_adjustments': {}
                },
                'factors': {}
            }
            
            with patch('data.data_manager.DataManager.get_game_context') as mock_context:
                mock_context.return_value = {
                    'vegas_spread': -3.5,
                    'data_quality': 0.8,
                    'data_sources': ['test']
                }
                
                result = prediction_engine.generate_prediction("GEORGIA", "ALABAMA")
                
                # Edge detector should flag this as suspicious
                confidence_assessment = {'confidence_score': 0.8, 'confidence_level': 'High'}
                edge_class = edge_detector.detect_edge(
                    result, confidence_assessment, {'data_quality': 0.8}
                )
                
                # Should downgrade or reject suspicious edges
                self.assertIn(edge_class.edge_type, 
                            [EdgeType.INSUFFICIENT_DATA, EdgeType.MODERATE_CONTRARIAN])


class TestSystemIntegration(unittest.TestCase):
    """Test full system integration."""
    
    def test_normalizer_integration(self):
        """Test that normalizer works throughout pipeline."""
        test_names = [
            ("georgia", "alabama"),
            ("UGA", "BAMA"),
            ("Georgia Bulldogs", "Alabama Crimson Tide"),
            ("GEORGIA", "ALABAMA")
        ]
        
        for home, away in test_names:
            # All should normalize to same internal format
            home_norm = normalizer.normalize(home)
            away_norm = normalizer.normalize(away)
            
            self.assertEqual(home_norm, "GEORGIA")
            self.assertEqual(away_norm, "ALABAMA")
    
    def test_weekly_analysis_integration(self):
        """Test weekly analysis functionality."""
        # Test that normalizer works with prediction engine
        with patch('data.data_manager.DataManager.get_game_context') as mock_context:
            mock_context.return_value = {
                'vegas_spread': -3.5,
                'data_quality': 0.5,
                'data_sources': ['test']
            }
            
            result = prediction_engine.generate_prediction("uga", "bama")
            
            # Should normalize to internal format
            self.assertEqual(result['home_team'], 'GEORGIA')
            self.assertEqual(result['away_team'], 'ALABAMA')


if __name__ == '__main__':
    unittest.main()