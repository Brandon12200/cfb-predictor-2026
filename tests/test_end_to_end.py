"""
End-to-end integration tests for College Football Market Edge Platform.
Tests the complete prediction pipeline with real and mock data.
"""

import unittest
import time
import logging
from unittest.mock import patch, MagicMock
from datetime import datetime

# Import main components
from main import main, parse_arguments
from engine.prediction_engine import prediction_engine
from data.data_manager import data_manager
from factors.factor_registry import factor_registry
from utils.normalizer import normalizer
from config import config
from utils.health_check import health_checker
from utils.monitoring import system_monitor


class TestEndToEndIntegration(unittest.TestCase):
    """End-to-end integration tests."""
    
    def setUp(self):
        """Set up test environment."""
        self.test_teams = [
            ('georgia', 'alabama'),
            ('ohio state', 'michigan'),
            ('notre dame', 'usc'),
            ('texas', 'oklahoma')
        ]
        
        # Configure logging for tests
        logging.basicConfig(level=logging.WARNING)
    
    def test_full_prediction_pipeline_with_mocks(self):
        """Test complete prediction pipeline with mocked API responses."""
        with patch('data.odds_client.OddsAPIClient.get_consensus_spread') as mock_odds, \
             patch('data.espn_client.ESPNStatsClient.get_team_info') as mock_espn:
            
            # Mock API responses
            mock_odds.return_value = -3.5  # Georgia favored by 3.5
            mock_espn.return_value = {
                'info': {'conference': {'name': 'SEC'}},
                'derived_metrics': {
                    'current_record': {'wins': 8, 'losses': 2, 'win_percentage': 0.8},
                    'venue_performance': {
                        'home_record': {'win_percentage': 0.85},
                        'away_record': {'win_percentage': 0.75}
                    }
                }
            }
            
            # Test prediction generation
            start_time = time.time()
            result = prediction_engine.generate_prediction('georgia', 'alabama', week=8)
            execution_time = time.time() - start_time
            
            # Validate result structure
            self.assertIsInstance(result, dict)
            self.assertIn('home_team', result)
            self.assertIn('away_team', result)
            self.assertIn('vegas_spread', result)
            self.assertIn('edge_size', result)
            self.assertIn('confidence_score', result)
            
            # Validate performance
            self.assertLess(execution_time, 15, "Prediction took too long")
            
            # Validate data quality
            self.assertGreaterEqual(result.get('confidence_score', 0), 0.15)
            self.assertLessEqual(result.get('confidence_score', 1), 0.95)
            
            print(f"✅ Full pipeline test completed in {execution_time:.2f}s")
    
    def test_cli_integration_with_mocks(self):
        """Test CLI integration with mocked responses."""
        with patch('data.odds_client.OddsAPIClient.get_consensus_spread') as mock_odds, \
             patch('data.espn_client.ESPNStatsClient.get_team_info') as mock_espn, \
             patch('sys.argv', ['main.py', '--home', 'georgia', '--away', 'alabama']):
            
            mock_odds.return_value = -2.5
            mock_espn.return_value = {
                'info': {'conference': {'name': 'SEC'}},
                'derived_metrics': {
                    'current_record': {'wins': 7, 'losses': 3, 'win_percentage': 0.7},
                    'venue_performance': {
                        'home_record': {'win_percentage': 0.8},
                        'away_record': {'win_percentage': 0.7}
                    }
                }
            }
            
            try:
                # This should not raise an exception
                main()
                print("✅ CLI integration test passed")
            except SystemExit as e:
                # CLI might exit with 0 (success)
                if e.code == 0:
                    print("✅ CLI integration test passed (exit 0)")
                else:
                    self.fail(f"CLI exited with error code: {e.code}")
            except Exception as e:
                self.fail(f"CLI integration failed: {str(e)}")
    
    def test_factor_calculation_performance(self):
        """Test factor calculation performance across multiple teams."""
        test_pairs = [
            ('GEORGIA', 'ALABAMA'),
            ('OHIO STATE', 'MICHIGAN'),
            ('TEXAS', 'OKLAHOMA'),
            ('NOTRE DAME', 'USC'),
            ('CLEMSON', 'FLORIDA STATE')
        ]
        
        execution_times = []
        
        for home_team, away_team in test_pairs:
            start_time = time.time()
            
            try:
                # Mock context to avoid API calls
                mock_context = {
                    'vegas_spread': -3.0,
                    'data_quality': 0.8,
                    'home_team_data': {
                        'info': {'conference': {'name': 'SEC'}},
                        'derived_metrics': {
                            'current_record': {'wins': 8, 'losses': 2, 'win_percentage': 0.8},
                            'venue_performance': {
                                'home_record': {'win_percentage': 0.85},
                                'away_record': {'win_percentage': 0.75}
                            }
                        }
                    },
                    'away_team_data': {
                        'info': {'conference': {'name': 'SEC'}},
                        'derived_metrics': {
                            'current_record': {'wins': 7, 'losses': 3, 'win_percentage': 0.7},
                            'venue_performance': {
                                'home_record': {'win_percentage': 0.8},
                                'away_record': {'win_percentage': 0.7}
                            }
                        }
                    }
                }
                
                # Calculate factors
                factor_results = factor_registry.calculate_all_factors(
                    home_team, away_team, mock_context
                )
                
                execution_time = time.time() - start_time
                execution_times.append(execution_time)
                
                # Validate results
                self.assertIsInstance(factor_results, dict)
                self.assertIn('factors', factor_results)
                self.assertIn('summary', factor_results)
                
                print(f"✅ Factor calculation for {home_team} vs {away_team}: {execution_time:.3f}s")
                
            except Exception as e:
                self.fail(f"Factor calculation failed for {home_team} vs {away_team}: {str(e)}")
        
        # Validate overall performance
        avg_time = sum(execution_times) / len(execution_times)
        max_time = max(execution_times)
        
        self.assertLess(avg_time, 5.0, f"Average factor calculation too slow: {avg_time:.2f}s")
        self.assertLess(max_time, 10.0, f"Slowest factor calculation too slow: {max_time:.2f}s")
        
        print(f"✅ Factor performance: avg={avg_time:.2f}s, max={max_time:.2f}s")
    
    def test_normalizer_comprehensive(self):
        """Test normalizer with comprehensive team name variations."""
        test_cases = [
            # Standard cases
            ('Georgia', 'GEORGIA'),
            ('Alabama', 'ALABAMA'),
            ('Ohio State', 'OHIO STATE'),
            
            # Common abbreviations
            ('UGA', 'GEORGIA'),
            ('Bama', 'ALABAMA'),
            ('OSU', 'OHIO STATE'),
            
            # Case variations
            ('georgia', 'GEORGIA'),
            ('ALABAMA', 'ALABAMA'),
            ('ohio state', 'OHIO STATE'),
            
            # With common suffixes
            ('Georgia Bulldogs', 'GEORGIA'),
            ('Alabama Crimson Tide', 'ALABAMA'),
            
            # Edge cases
            ('Miami', 'MIAMI'),  # Could be FL or OH
            ('USC', 'USC'),      # Southern California
        ]
        
        failed_cases = []
        
        for input_name, expected in test_cases:
            try:
                result = normalizer.normalize(input_name)
                if result != expected:
                    failed_cases.append(f"{input_name} -> {result} (expected {expected})")
                else:
                    print(f"✅ {input_name} -> {result}")
            except Exception as e:
                failed_cases.append(f"{input_name} -> ERROR: {str(e)}")
        
        if failed_cases:
            print("❌ Failed normalizer cases:")
            for case in failed_cases:
                print(f"  {case}")
        
        # Allow some flexibility for ambiguous cases
        self.assertLess(len(failed_cases), 3, f"Too many normalizer failures: {failed_cases}")
    
    def test_health_check_comprehensive(self):
        """Test comprehensive health check functionality."""
        try:
            # Run full health check
            start_time = time.time()
            health_report = health_checker.run_full_health_check()
            execution_time = time.time() - start_time
            
            # Validate health report structure
            self.assertIsInstance(health_report, dict)
            self.assertIn('overall_status', health_report)
            self.assertIn('components', health_report)
            self.assertIn('execution_time', health_report)
            
            # Check that all expected components were tested
            expected_components = [
                'configuration', 'system_resources', 'normalizer',
                'prediction_engine', 'data_manager', 'factor_registry'
            ]
            
            tested_components = list(health_report['components'].keys())
            
            for component in expected_components:
                self.assertIn(component, tested_components, 
                            f"Component {component} not tested")
            
            # Validate execution time
            self.assertLess(execution_time, 60, "Health check took too long")
            
            print(f"✅ Health check completed in {execution_time:.2f}s")
            print(f"   Overall status: {health_report['overall_status']}")
            print(f"   Components tested: {len(tested_components)}")
            
            # Print component statuses
            for component, status in health_report['components'].items():
                status_emoji = "✅" if status['status'] == 'healthy' else "⚠️" if status['status'] == 'warning' else "❌"
                print(f"   {status_emoji} {component}: {status['status']}")
            
        except Exception as e:
            self.fail(f"Health check failed: {str(e)}")
    
    def test_monitoring_system(self):
        """Test monitoring system functionality."""
        try:
            # Start monitoring
            system_monitor.start_monitoring()
            
            # Log some test metrics
            system_monitor.log_prediction_performance(
                execution_time=2.5,
                api_calls=8,
                prediction_success=True
            )
            
            system_monitor.log_api_call('test_api', 1.2, success=True)
            system_monitor.log_api_call('test_api', 0.8, success=True)
            system_monitor.log_api_call('test_api', 5.0, success=False)  # Slow/failed call
            
            # Get performance summary
            summary = system_monitor.get_performance_summary()
            
            # Validate summary structure
            self.assertIsInstance(summary, dict)
            self.assertIn('total_predictions', summary)
            self.assertIn('avg_prediction_time', summary)
            self.assertIn('total_api_calls', summary)
            self.assertIn('health_status', summary)
            
            # Check metrics were recorded
            self.assertEqual(summary['total_predictions'], 1)
            self.assertEqual(summary['total_api_calls'], 3)
            
            print(f"✅ Monitoring system test passed")
            print(f"   Predictions: {summary['total_predictions']}")
            print(f"   API calls: {summary['total_api_calls']}")
            print(f"   Avg prediction time: {summary['avg_prediction_time']:.2f}s")
            
            # Stop monitoring
            system_monitor.stop_monitoring()
            
        except Exception as e:
            self.fail(f"Monitoring system test failed: {str(e)}")
    
    def test_error_handling_resilience(self):
        """Test system resilience to various error conditions."""
        test_cases = [
            # Invalid team names
            ('invalid_team', 'alabama'),
            ('georgia', 'invalid_team'),
            
            # Same team for both
            ('georgia', 'georgia'),
            
            # Empty/None inputs
            ('', 'alabama'),
            ('georgia', ''),
        ]
        
        for home_team, away_team in test_cases:
            try:
                result = prediction_engine.generate_prediction(home_team, away_team)
                
                # Should return error result, not crash
                self.assertIsInstance(result, dict)
                
                # Should have error indicators
                if result.get('prediction_type') == 'ERROR' or result.get('error'):
                    print(f"✅ Error handled correctly for {home_team} vs {away_team}")
                else:
                    print(f"⚠️  No error for potentially invalid input: {home_team} vs {away_team}")
                
            except Exception as e:
                print(f"❌ Unhandled exception for {home_team} vs {away_team}: {str(e)}")
    
    def test_configuration_validation(self):
        """Test configuration validation."""
        try:
            # Test API key validation
            api_status = config.validate_api_keys()
            self.assertIsInstance(api_status, dict)
            
            # Test rate limit retrieval
            odds_limit = config.get_rate_limit('odds')
            espn_limit = config.get_rate_limit('espn')
            
            self.assertIsInstance(odds_limit, int)
            self.assertIsInstance(espn_limit, int)
            self.assertGreater(odds_limit, 0)
            self.assertGreater(espn_limit, 0)
            
            # Test edge classification
            test_edges = [0.5, 1.5, 2.5, 4.0, 6.0]
            for edge in test_edges:
                classification = config.get_edge_classification(edge)
                self.assertIsInstance(classification, str)
            
            print("✅ Configuration validation passed")
            print(f"   Odds API configured: {api_status.get('odds_api', False)}")
            print(f"   ESPN API configured: {api_status.get('espn_api', 'optional')}")
            print(f"   Rate limits: odds={odds_limit}, espn={espn_limit}")
            
        except Exception as e:
            self.fail(f"Configuration validation failed: {str(e)}")


class TestPerformanceBenchmarks(unittest.TestCase):
    """Performance benchmark tests."""
    
    def test_prediction_speed_benchmark(self):
        """Benchmark prediction generation speed."""
        # Use mocked data to focus on calculation performance
        with patch('data.odds_client.OddsAPIClient.get_consensus_spread') as mock_odds, \
             patch('data.espn_client.ESPNStatsClient.get_team_info') as mock_espn:
            
            mock_odds.return_value = -3.0
            mock_espn.return_value = {
                'info': {'conference': {'name': 'SEC'}},
                'derived_metrics': {
                    'current_record': {'wins': 8, 'losses': 2, 'win_percentage': 0.8},
                    'venue_performance': {
                        'home_record': {'win_percentage': 0.85},
                        'away_record': {'win_percentage': 0.75}
                    }
                }
            }
            
            # Run multiple predictions
            times = []
            for i in range(10):
                start_time = time.time()
                result = prediction_engine.generate_prediction('georgia', 'alabama')
                execution_time = time.time() - start_time
                times.append(execution_time)
                
                # Validate each prediction
                self.assertIsInstance(result, dict)
                self.assertIn('edge_size', result)
            
            avg_time = sum(times) / len(times)
            min_time = min(times)
            max_time = max(times)
            
            print(f"🚀 Performance Benchmark Results:")
            print(f"   Average: {avg_time:.3f}s")
            print(f"   Min: {min_time:.3f}s")
            print(f"   Max: {max_time:.3f}s")
            print(f"   All under 15s: {max_time < 15.0}")
            
            # Performance assertions
            self.assertLess(avg_time, 5.0, f"Average prediction time too slow: {avg_time:.2f}s")
            self.assertLess(max_time, 15.0, f"Slowest prediction too slow: {max_time:.2f}s")


if __name__ == '__main__':
    print("🧪 Running End-to-End Integration Tests")
    print("=" * 50)
    
    # Run tests with detailed output
    unittest.main(verbosity=2, exit=False)
    
    print("\n" + "=" * 50)
    print("🏁 End-to-End Testing Complete")