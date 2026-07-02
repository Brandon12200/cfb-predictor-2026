"""
Tests for API client functionality.
Includes both unit tests with mocks and integration tests with live APIs.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import json
from datetime import datetime

from data.odds_client import OddsAPIClient
from data.espn_client import ESPNStatsClient
from data.data_manager import DataManager
from config import config


class TestOddsAPIClient(unittest.TestCase):
    """Test cases for OddsAPIClient class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.api_key = "test_api_key"
        self.client = OddsAPIClient(self.api_key)
    
    def test_client_initialization(self):
        """Test client initialization."""
        self.assertEqual(self.client.api_key, self.api_key)
        self.assertEqual(self.client.sport, "americanfootball_ncaaf")
        self.assertIsNotNone(self.client.rate_limiter)
        self.assertIsNotNone(self.client.session)
    
    @patch('data.odds_client.requests.Session')
    def test_get_weekly_spreads_success(self, mock_session_class):
        """Test successful weekly spreads retrieval."""
        # Mock response data
        mock_response_data = [
            {
                'id': 'game123',
                'home_team': 'Georgia',
                'away_team': 'Alabama',
                'commence_time': '2024-09-07T19:00:00Z',
                'bookmakers': [
                    {
                        'key': 'fanduel',
                        'markets': [
                            {
                                'key': 'spreads',
                                'outcomes': [
                                    {
                                        'name': 'Georgia',
                                        'point': -3.5,
                                        'price': -110
                                    },
                                    {
                                        'name': 'Alabama',
                                        'point': 3.5,
                                        'price': -110
                                    }
                                ]
                            }
                        ]
                    }
                ]
            }
        ]
        
        # Mock session and response
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_response_data
        mock_session.get.return_value = mock_response
        
        # Reset client with mocked session
        client = OddsAPIClient(self.api_key)
        client.session = mock_session
        
        # Test the method
        result = client.get_weekly_spreads()
        
        # Verify results
        self.assertIn('games', result)
        self.assertGreater(len(result['games']), 0)
        
        game = result['games'][0]
        self.assertEqual(game['home_team'], 'GEORGIA')
        self.assertEqual(game['away_team'], 'ALABAMA')
        self.assertIsNotNone(game['consensus_spread'])
    
    @patch('data.odds_client.requests.Session')
    def test_get_weekly_spreads_api_error(self, mock_session_class):
        """Test handling of API errors."""
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session
        
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"
        mock_session.get.return_value = mock_response
        
        client = OddsAPIClient(self.api_key)
        client.session = mock_session
        
        with self.assertRaises(ValueError) as context:
            client.get_weekly_spreads()
        
        self.assertIn("Invalid API key", str(context.exception))
    
    def test_consensus_spread_calculation(self):
        """Test consensus spread calculation logic."""
        spreads = [
            {'bookmaker': 'fanduel', 'point': -3.5},
            {'bookmaker': 'draftkings', 'point': -3.0},
            {'bookmaker': 'pointsbet_us', 'point': -4.0},
        ]
        
        consensus = self.client._calculate_consensus_spread(spreads)
        
        # Should be a weighted average rounded to nearest 0.5
        self.assertIsInstance(consensus, float)
        self.assertTrue(-5.0 <= consensus <= -2.0)  # Reasonable range
    
    def test_consensus_spread_no_data(self):
        """Test consensus spread calculation with no data."""
        consensus = self.client._calculate_consensus_spread([])
        self.assertIsNone(consensus)
    
    def test_team_normalization_in_processing(self):
        """Test that team names are properly normalized."""
        game_data = {
            'id': 'test_game',
            'home_team': 'Georgia Bulldogs',
            'away_team': 'Alabama Crimson Tide',
            'commence_time': '2024-09-07T19:00:00Z',
            'bookmakers': []
        }
        
        processed_game = self.client._process_single_game(game_data)
        
        self.assertEqual(processed_game['home_team'], 'GEORGIA')
        self.assertEqual(processed_game['away_team'], 'ALABAMA')
    
    def test_invalid_team_names(self):
        """Test handling of invalid team names."""
        game_data = {
            'id': 'test_game',
            'home_team': 'Invalid Team Name',
            'away_team': 'Another Invalid Team',
            'commence_time': '2024-09-07T19:00:00Z',
            'bookmakers': []
        }
        
        processed_game = self.client._process_single_game(game_data)
        self.assertIsNone(processed_game)


class TestESPNStatsClient(unittest.TestCase):
    """Test cases for ESPNStatsClient class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.client = ESPNStatsClient()
    
    def test_client_initialization(self):
        """Test client initialization."""
        self.assertIsNotNone(self.client.rate_limiter)
        self.assertIsNotNone(self.client.session)
        self.assertEqual(self.client.team_id_cache, {})
    
    @patch('data.espn_client.requests.Session')
    def test_find_team_id_success(self, mock_session_class):
        """Test successful team ID lookup."""
        mock_teams_response = {
            'sports': [{
                'leagues': [{
                    'children': [{
                        'teams': [{
                            'team': {
                                'id': '61',
                                'displayName': 'Georgia Bulldogs',
                                'shortDisplayName': 'Georgia',
                                'abbreviation': 'UGA'
                            }
                        }]
                    }]
                }]
            }]
        }
        
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_teams_response
        mock_session.get.return_value = mock_response
        
        client = ESPNStatsClient()
        client.session = mock_session
        
        team_id = client.find_team_id('GEORGIA')
        
        self.assertEqual(team_id, 61)
        self.assertIn('GEORGIA', client.team_id_cache)
    
    @patch('data.espn_client.requests.Session')
    def test_get_team_info_success(self, mock_session_class):
        """Test successful team info retrieval."""
        # Mock team ID lookup
        mock_teams_response = {
            'sports': [{
                'leagues': [{
                    'children': [{
                        'teams': [{
                            'team': {
                                'id': '61',
                                'displayName': 'Georgia Bulldogs',
                                'shortDisplayName': 'Georgia',
                                'abbreviation': 'UGA'
                            }
                        }]
                    }]
                }]
            }]
        }
        
        # Mock team info response
        mock_team_info_response = {
            'team': {
                'id': '61',
                'displayName': 'Georgia Bulldogs',
                'shortDisplayName': 'Georgia',
                'abbreviation': 'UGA',
                'color': '#CC0000',
                'alternateColor': '#000000',
                'logos': [{'href': 'https://example.com/logo.png'}],
                'venue': {
                    'fullName': 'Sanford Stadium',
                    'capacity': 92746
                }
            }
        }
        
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session
        
        # Set up different responses for different URLs
        def mock_get_side_effect(url, **kwargs):
            mock_response = MagicMock()
            mock_response.status_code = 200
            
            if 'teams/' in url and url.endswith('/61'):
                mock_response.json.return_value = mock_team_info_response
            else:  # teams list
                mock_response.json.return_value = mock_teams_response
            
            return mock_response
        
        mock_session.get.side_effect = mock_get_side_effect
        
        client = ESPNStatsClient()
        client.session = mock_session
        
        team_info = client.get_team_info('GEORGIA')
        
        self.assertEqual(team_info['team_name'], 'GEORGIA')
        self.assertEqual(team_info['display_name'], 'Georgia Bulldogs')
        self.assertEqual(team_info['espn_id'], '61')
        self.assertIn('venue', team_info)
    
    def test_neutral_fallback_data(self):
        """Test neutral fallback data generation."""
        neutral_coaching = self.client._get_neutral_coaching_data('GEORGIA')
        
        self.assertEqual(neutral_coaching['team_name'], 'GEORGIA')
        self.assertEqual(neutral_coaching['status'], 'neutral_fallback')
        self.assertIsInstance(neutral_coaching['head_coach_experience'], int)
        
        neutral_stats = self.client._get_neutral_stats_data('GEORGIA')
        
        self.assertEqual(neutral_stats['team_name'], 'GEORGIA')
        self.assertEqual(neutral_stats['status'], 'neutral_fallback')
        self.assertIn('season_stats', neutral_stats)
    
    @patch('data.espn_client.requests.Session')
    def test_api_error_handling(self, mock_session_class):
        """Test handling of ESPN API errors."""
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session
        
        # Mock failed response
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_session.get.return_value = mock_response
        
        client = ESPNStatsClient()
        client.session = mock_session
        
        # Should return neutral data, not raise exception
        team_info = client.get_team_info('GEORGIA')
        
        self.assertIn('status', team_info)
        # Should get fallback data, not crash


class TestDataManager(unittest.TestCase):
    """Test cases for DataManager class."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Mock configuration without real API key
        self.mock_config = Mock()
        self.mock_config.odds_api_key = None
        self.mock_config.rate_limit_odds = 83
        self.mock_config.rate_limit_espn = 60
        
        self.data_manager = DataManager(self.mock_config)
    
    def test_data_manager_initialization(self):
        """Test data manager initialization."""
        self.assertIsNotNone(self.data_manager.espn_client)
        self.assertIsNone(self.data_manager.odds_client)  # No API key provided
        self.assertIsNotNone(self.data_manager.cache)
        self.assertIsNotNone(self.data_manager.normalizer)
    
    def test_safe_api_call_decorator(self):
        """Test safe API call decorator functionality."""
        @self.data_manager.safe_api_call(fallback_value={'fallback': True})
        def test_function():
            raise Exception("Test error")
        
        # Temporarily add method to data manager
        self.data_manager.test_function = test_function
        
        result = self.data_manager.test_function()
        self.assertEqual(result, {'fallback': True})
    
    def test_validate_data_availability(self):
        """Test data availability validation."""
        availability = self.data_manager.validate_data_availability('GEORGIA', 'ALABAMA')
        
        self.assertIn('teams_normalized', availability)
        self.assertIn('odds_api_available', availability)
        self.assertIn('espn_api_available', availability)
        self.assertIn('home_team_data', availability)
        self.assertIn('away_team_data', availability)
        
        # Should have normalized teams
        self.assertTrue(availability['teams_normalized'])
        
        # Should not have odds API (no key configured)
        self.assertFalse(availability['odds_api_available'])
        
        # Should have ESPN API
        self.assertTrue(availability['espn_api_available'])
    
    def test_data_quality_report(self):
        """Test data quality report generation."""
        report = self.data_manager.get_data_quality_report('GEORGIA', 'ALABAMA')
        
        self.assertIn('quality_score', report)
        self.assertIn('quality_level', report)
        self.assertIn('availability', report)
        self.assertIn('recommendations', report)
        
        # Quality score should be between 0 and 1
        self.assertTrue(0 <= report['quality_score'] <= 1)
        
        # Quality level should be valid
        self.assertIn(report['quality_level'], ['HIGH', 'MEDIUM', 'LOW', 'POOR'])
        
        # Should have recommendations
        self.assertIsInstance(report['recommendations'], list)
    
    def test_neutral_data_structures(self):
        """Test neutral data structure generation."""
        # Test different data types
        info_structure = self.data_manager._get_neutral_data_structure('info', 'GEORGIA')
        self.assertEqual(info_structure['team_name'], 'GEORGIA')
        self.assertEqual(info_structure['status'], 'neutral_fallback')
        self.assertIn('display_name', info_structure)
        
        coaching_structure = self.data_manager._get_neutral_data_structure('coaching', 'GEORGIA')
        self.assertEqual(coaching_structure['team_name'], 'GEORGIA')
        self.assertIn('head_coach_name', coaching_structure)
        self.assertIn('head_coach_experience', coaching_structure)
        
        stats_structure = self.data_manager._get_neutral_data_structure('stats', 'GEORGIA')
        self.assertEqual(stats_structure['team_name'], 'GEORGIA')
        self.assertIn('season_stats', stats_structure)
        
        schedule_structure = self.data_manager._get_neutral_data_structure('schedule', 'GEORGIA')
        self.assertEqual(schedule_structure, [])  # Empty list for schedule
    
    def test_derived_metrics_calculation(self):
        """Test derived metrics calculation."""
        # Mock team data with schedule
        team_data = {
            'schedule': [
                {'completed': True, 'result': 'W', 'is_home_game': True},
                {'completed': True, 'result': 'L', 'is_home_game': False},
                {'completed': True, 'result': 'W', 'is_home_game': True},
                {'completed': False, 'result': None, 'is_home_game': True}
            ]
        }
        
        metrics = self.data_manager._calculate_derived_metrics(team_data)
        
        self.assertIn('current_record', metrics)
        self.assertIn('venue_performance', metrics)
        
        # Check current record calculation
        record = metrics['current_record']
        self.assertEqual(record['wins'], 2)
        self.assertEqual(record['losses'], 1)
        self.assertAlmostEqual(record['win_percentage'], 2/3, places=2)
        
        # Check venue performance
        venue_perf = metrics['venue_performance']
        self.assertIn('home_record', venue_perf)
        self.assertIn('away_record', venue_perf)
    
    def test_experience_differential_calculation(self):
        """Test coaching experience differential calculation."""
        home_coaching = {'head_coach_experience': 10}
        away_coaching = {'head_coach_experience': 5}
        
        diff = self.data_manager._calculate_experience_differential(home_coaching, away_coaching)
        self.assertEqual(diff, 5)
        
        # Test with missing data (should use defaults)
        home_coaching_empty = {}
        away_coaching_empty = {}
        
        diff = self.data_manager._calculate_experience_differential(home_coaching_empty, away_coaching_empty)
        self.assertEqual(diff, 0)  # Both default to 5, so diff is 0
    
    def test_cache_integration(self):
        """Test cache integration."""
        # Test cache stats retrieval
        cache_stats = self.data_manager.get_cache_stats()
        self.assertIsInstance(cache_stats, dict)
        
        # Test cache clearing
        self.data_manager.clear_all_caches()  # Should not raise exception


class TestAPIIntegration(unittest.TestCase):
    """Integration tests with real API calls (when available)."""
    
    def setUp(self):
        """Set up integration test fixtures."""
        # Only run integration tests if API keys are available
        self.has_odds_api = bool(config.odds_api_key)
        self.data_manager = DataManager()
    
    def test_connection_tests(self):
        """Test connection to all APIs."""
        connections = self.data_manager.test_all_connections()
        
        self.assertIn('espn_api', connections)
        self.assertIn('odds_api', connections)
        
        # ESPN should always be available
        self.assertIsInstance(connections['espn_api'], bool)
        
        # Odds API depends on configuration
        if self.has_odds_api:
            self.assertIsInstance(connections['odds_api'], bool)
        else:
            self.assertFalse(connections['odds_api'])
    
    @unittest.skipUnless(config.odds_api_key, "Odds API key required for integration test")
    def test_real_odds_api_call(self):
        """Test real Odds API call (requires API key)."""
        if not self.has_odds_api:
            self.skipTest("No Odds API key configured")
        
        try:
            # Test getting weekly spreads
            weekly_data = self.data_manager.odds_client.get_weekly_spreads()
            
            self.assertIn('games', weekly_data)
            self.assertIn('timestamp', weekly_data)
            self.assertIn('source', weekly_data)
            
            # If there are games, test the structure
            if weekly_data['games']:
                game = weekly_data['games'][0]
                self.assertIn('home_team', game)
                self.assertIn('away_team', game)
                self.assertIn('consensus_spread', game)
        
        except Exception as e:
            self.fail(f"Real Odds API call failed: {e}")
    
    def test_real_espn_api_call(self):
        """Test real ESPN API call."""
        try:
            # Test getting team info for a known team
            team_info = self.data_manager.espn_client.get_team_info('GEORGIA')
            
            self.assertIn('team_name', team_info)
            self.assertEqual(team_info['team_name'], 'GEORGIA')
            
            # Should have basic structure even if it's fallback data
            self.assertIn('last_updated', team_info)
        
        except Exception as e:
            self.fail(f"Real ESPN API call failed: {e}")
    
    def test_end_to_end_data_flow(self):
        """Test complete data flow from input to output."""
        try:
            # Test getting game context for a common matchup
            context = self.data_manager.get_game_context('GEORGIA', 'ALABAMA')
            
            # Should have basic structure
            self.assertIn('home_team', context)
            self.assertIn('away_team', context)
            self.assertIn('data_sources', context)
            self.assertIn('data_quality', context)
            
            # Teams should be normalized
            self.assertEqual(context['home_team'], 'GEORGIA')
            self.assertEqual(context['away_team'], 'ALABAMA')
            
            # Should have team data
            self.assertIn('home_team_data', context)
            self.assertIn('away_team_data', context)
            
            # Data quality should be reasonable
            self.assertTrue(0 <= context['data_quality'] <= 1)
        
        except Exception as e:
            self.fail(f"End-to-end data flow test failed: {e}")


if __name__ == '__main__':
    # Run tests with different verbosity levels
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == '--integration':
        # Run only integration tests
        suite = unittest.TestLoader().loadTestsFromTestCase(TestAPIIntegration)
    else:
        # Run all tests
        suite = unittest.TestLoader().loadTestsFromModule(sys.modules[__name__])
    
    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(suite)