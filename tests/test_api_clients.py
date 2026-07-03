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
        self.assertIsInstance(self.client.team_id_cache, dict)  # pre-seeded team->id cache
    
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
    
    @patch('data.espn_client.requests.Session')
    def test_api_error_raises_not_fabricates(self, mock_session_class):
        """On an API error, get_team_info RAISES (Phase 1b) rather than returning a
        neutral-fabricated structure — absence is honest (SPEC §5.2)."""
        from data.espn_client import ESPNError
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_session.get.return_value = mock_response

        client = ESPNStatsClient()
        client.session = mock_session

        with self.assertRaises(ESPNError):
            client.get_team_info('GEORGIA')


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
    
    def _snapshot(self, home_coaching, away_coaching, stats_status="cfbd", vegas=-3.5):
        """Minimal in-memory snapshot bundle for get_game_context(snapshot=...)."""
        def team(name):
            return {"team_name": name, "info": {"status": "cfbd", "conference": {"name": "SEC"}},
                    "coaching": home_coaching if name == "GEORGIA" else away_coaching,
                    "stats": {"status": stats_status}, "schedule": [],
                    "derived_metrics": {}, "is_home": False}
        return {"meta": {"snapshot_id": "s1", "built_at": "2026-09-01T00:00:00+00:00"},
                "data": {"teams": {"GEORGIA": team("GEORGIA"), "ALABAMA": team("ALABAMA")},
                         "games": [], "advanced_stats": {},
                         "betting_lines": {"ALABAMA@GEORGIA": {"vegas_spread": vegas, "lines": []}}}}

    def test_get_game_context_from_snapshot(self):
        """get_game_context assembles the factor-facing context from a snapshot, and
        coaching_comparison computes the experience differential."""
        snap = self._snapshot({"head_coach_experience": 9, "tenure_years": 4, "status": "cfbd"},
                              {"head_coach_experience": 6, "tenure_years": 2, "status": "cfbd"})
        ctx = self.data_manager.get_game_context("GEORGIA", "ALABAMA", week=1, snapshot=snap)
        self.assertEqual(ctx["vegas_spread"], -3.5)
        self.assertTrue(ctx["has_betting_data"])
        self.assertEqual(ctx["snapshot_id"], "s1")
        self.assertTrue(ctx["home_team_data"]["is_home"])
        self.assertEqual(ctx["coaching_comparison"]["experience_differential"], 3)  # 9 - 6

    def test_missing_fields_lower_quality_not_fabricated(self):
        """D4: missing coaching/stats stay None and lower data_quality honestly — the
        neutral-fill that used to report full quality is gone (SPEC §5.2)."""
        snap = self._snapshot({"status": None}, {"status": None}, stats_status=None)
        ctx = self.data_manager.get_game_context("GEORGIA", "ALABAMA", week=1, snapshot=snap)
        report = ctx["data_quality_report"]
        self.assertIn("home_coaching", report["missing_fields"])
        self.assertIn("home_stats", report["missing_fields"])
        self.assertLess(ctx["data_quality"], 0.8)  # betting+info present, rest missing
        self.assertIsNone(ctx["home_team_data"]["coaching"].get("head_coach_experience"))

    def test_no_betting_line_gate(self):
        """No vegas spread → has_betting_data False (engine skips), not fabricated."""
        snap = self._snapshot({"status": "cfbd"}, {"status": "cfbd"}, vegas=None)
        ctx = self.data_manager.get_game_context("GEORGIA", "ALABAMA", week=1, snapshot=snap)
        self.assertIsNone(ctx["vegas_spread"])
        self.assertFalse(ctx["has_betting_data"])
    
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
    @unittest.skip("Live API integration test; requires network + real key (excluded from offline suite)")
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
    
    @unittest.skip("Live ESPN integration (network); get_team_info now raises rather "
                   "than neutral-filling, so it cannot run in the offline suite.")
    def test_real_espn_api_call(self):
        """Test real ESPN API call."""
        team_info = self.data_manager.espn_client.get_team_info('GEORGIA')
        self.assertEqual(team_info['team_name'], 'GEORGIA')
    
    def test_end_to_end_data_flow(self):
        """Test complete data flow from input to output."""
        try:
            # Game context is assembled from a snapshot bundle (Phase 1b); inject a
            # minimal in-memory one rather than fetching live.
            snapshot = {
                "meta": {"snapshot_id": "e2e", "built_at": "2026-09-01T00:00:00+00:00"},
                "data": {
                    "teams": {
                        "GEORGIA": {"team_name": "GEORGIA", "info": {"status": "cfbd", "conference": {"name": "SEC"}},
                                    "coaching": {"status": "cfbd", "head_coach_experience": 9}, "stats": {"status": "cfbd"},
                                    "schedule": [], "derived_metrics": {}, "is_home": False},
                        "ALABAMA": {"team_name": "ALABAMA", "info": {"status": "cfbd", "conference": {"name": "SEC"}},
                                    "coaching": {"status": "cfbd", "head_coach_experience": 7}, "stats": {"status": "cfbd"},
                                    "schedule": [], "derived_metrics": {}, "is_home": False},
                    },
                    "games": [], "advanced_stats": {},
                    "betting_lines": {"ALABAMA@GEORGIA": {"vegas_spread": -3.5, "lines": []}},
                },
            }
            context = self.data_manager.get_game_context('GEORGIA', 'ALABAMA', week=1, snapshot=snapshot)

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