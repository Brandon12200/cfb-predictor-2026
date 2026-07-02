"""
Synthetic backtesting framework for College Football Market Edge Platform.
Creates realistic test scenarios to validate prediction accuracy.
"""

import unittest
import random
import json
from typing import Dict, Any, List, Tuple
from datetime import datetime, timedelta
from unittest.mock import patch, Mock
import statistics

from engine.prediction_engine import prediction_engine
from factors.factor_registry import factor_registry
from utils.normalizer import normalizer


class SyntheticGame:
    """Represents a synthetic game with known outcomes for testing."""
    
    def __init__(self, home_team: str, away_team: str, week: int, 
                 vegas_spread: float, actual_margin: float, 
                 scenario_type: str = "normal"):
        self.home_team = home_team
        self.away_team = away_team
        self.week = week
        self.vegas_spread = vegas_spread
        self.actual_margin = actual_margin  # Actual final margin (home team perspective)
        self.scenario_type = scenario_type
        
        # Calculate actual outcomes
        self.home_covered = actual_margin > vegas_spread
        self.vegas_was_correct = abs(actual_margin - vegas_spread) < 3.0
        
        # Determine if this should be a contrarian opportunity
        self.should_be_contrarian = self._determine_contrarian_opportunity()
    
    def _determine_contrarian_opportunity(self) -> bool:
        """Determine if this game should present a contrarian opportunity."""
        if self.scenario_type == "trap_game":
            # Home team should outperform expectations
            return self.actual_margin > self.vegas_spread + 3.0
        elif self.scenario_type == "desperation":
            # Team needing bowl eligibility should outperform
            return self.actual_margin > self.vegas_spread + 2.0
        elif self.scenario_type == "rivalry":
            # Games should be closer than expected
            return abs(self.actual_margin - self.vegas_spread) > 4.0
        elif self.scenario_type == "weather":
            # Weather games should go under and be lower scoring
            return abs(self.actual_margin) < abs(self.vegas_spread) - 2.0
        else:
            # Normal games - no strong contrarian signal
            return abs(self.actual_margin - self.vegas_spread) > 5.0


class SyntheticBacktester:
    """Framework for synthetic backtesting of predictions."""
    
    def __init__(self):
        self.test_teams = [
            "GEORGIA", "ALABAMA", "OHIO STATE", "MICHIGAN", "TEXAS", "OKLAHOMA",
            "CLEMSON", "FLORIDA STATE", "NOTRE DAME", "USC", "PENN STATE", "WISCONSIN"
        ]
        
        self.conferences = {
            "SEC": ["GEORGIA", "ALABAMA", "TEXAS", "OKLAHOMA"],
            "BIG TEN": ["OHIO STATE", "MICHIGAN", "PENN STATE", "WISCONSIN"],
            "ACC": ["CLEMSON", "FLORIDA STATE", "NOTRE DAME"],
            "PAC-12": ["USC"]
        }
        
        self.synthetic_games = []
        self.prediction_results = []
    
    def generate_synthetic_season(self, num_games: int = 50) -> List[SyntheticGame]:
        """Generate a synthetic season of games with realistic scenarios."""
        games = []
        
        # Generate different types of scenarios
        scenario_distribution = {
            "normal": 0.60,
            "trap_game": 0.15,
            "desperation": 0.10,
            "rivalry": 0.10,
            "weather": 0.05
        }
        
        for i in range(num_games):
            # Select scenario type
            scenario_type = self._select_scenario(scenario_distribution)
            
            # Generate game based on scenario
            game = self._generate_game_for_scenario(scenario_type, i % 17 + 1)
            games.append(game)
        
        self.synthetic_games = games
        return games
    
    def _select_scenario(self, distribution: Dict[str, float]) -> str:
        """Select scenario type based on distribution."""
        rand = random.random()
        cumulative = 0.0
        
        for scenario, prob in distribution.items():
            cumulative += prob
            if rand <= cumulative:
                return scenario
        
        return "normal"
    
    def _generate_game_for_scenario(self, scenario_type: str, week: int) -> SyntheticGame:
        """Generate a game for a specific scenario type."""
        home_team = random.choice(self.test_teams)
        away_team = random.choice([t for t in self.test_teams if t != home_team])
        
        if scenario_type == "normal":
            vegas_spread = random.uniform(-14.0, 14.0)
            actual_margin = vegas_spread + random.normalvariate(0, 8.0)
            
        elif scenario_type == "trap_game":
            # Unranked home team vs ranked away team
            vegas_spread = random.uniform(3.0, 10.0)  # Away team favored
            # Home team often covers/wins in trap games
            actual_margin = vegas_spread + random.uniform(3.0, 14.0)
            
        elif scenario_type == "desperation":
            # Team needing bowl eligibility
            vegas_spread = random.uniform(-7.0, 7.0)
            # Desperate team performs better
            desperation_boost = random.uniform(2.0, 8.0)
            actual_margin = vegas_spread + desperation_boost
            
        elif scenario_type == "rivalry":
            # Traditional rivals
            vegas_spread = random.uniform(-10.0, 10.0)
            # Rivalry games are unpredictable
            rivalry_variance = random.normalvariate(0, 12.0)
            actual_margin = vegas_spread + rivalry_variance
            
        elif scenario_type == "weather":
            # Bad weather game
            vegas_spread = random.uniform(-7.0, 7.0)
            # Weather makes games lower scoring, closer
            weather_effect = random.uniform(-3.0, 3.0)
            actual_margin = vegas_spread + weather_effect
            
        else:
            # Default case
            vegas_spread = random.uniform(-14.0, 14.0)
            actual_margin = vegas_spread + random.normalvariate(0, 7.0)
        
        return SyntheticGame(home_team, away_team, week, vegas_spread, actual_margin, scenario_type)
    
    def run_backtest(self, games: List[SyntheticGame]) -> Dict[str, Any]:
        """Run predictions on synthetic games and measure accuracy."""
        results = {
            'total_games': len(games),
            'predictions': [],
            'accuracy_metrics': {},
            'scenario_performance': {},
            'edge_performance': {}
        }
        
        for game in games:
            prediction_result = self._predict_game(game)
            results['predictions'].append(prediction_result)
        
        # Calculate accuracy metrics
        results['accuracy_metrics'] = self._calculate_accuracy_metrics(results['predictions'])
        results['scenario_performance'] = self._analyze_scenario_performance(results['predictions'])
        results['edge_performance'] = self._analyze_edge_performance(results['predictions'])
        
        return results
    
    def _predict_game(self, game: SyntheticGame) -> Dict[str, Any]:
        """Generate prediction for a synthetic game."""
        # Create synthetic context for the game
        context = self._create_game_context(game)
        
        try:
            with patch('data.odds_client.OddsAPIClient.get_consensus_spread') as mock_odds, \
                 patch('data.espn_client.ESPNStatsClient.get_team_info') as mock_espn:
                
                # Mock API responses
                mock_odds.return_value = game.vegas_spread
                mock_espn.return_value = self._create_mock_team_data(game.scenario_type)
                
                # Generate prediction
                prediction = prediction_engine.generate_prediction(
                    game.home_team, game.away_team, week=game.week
                )
                
                # Add game information and actual outcome
                prediction_result = {
                    'game': game,
                    'prediction': prediction,
                    'actual_margin': game.actual_margin,
                    'home_covered': game.home_covered,
                    'vegas_was_correct': game.vegas_was_correct,
                    'scenario_type': game.scenario_type,
                    'should_be_contrarian': game.should_be_contrarian
                }
                
                # Evaluate prediction accuracy
                prediction_result.update(self._evaluate_prediction(prediction, game))
                
                return prediction_result
                
        except Exception as e:
            return {
                'game': game,
                'prediction': {'error': str(e)},
                'prediction_failed': True,
                'scenario_type': game.scenario_type
            }
    
    def _create_game_context(self, game: SyntheticGame) -> Dict[str, Any]:
        """Create realistic context for a synthetic game."""
        # Simulate different data qualities based on scenario
        data_quality_map = {
            "normal": random.uniform(0.7, 0.9),
            "trap_game": random.uniform(0.6, 0.8),
            "desperation": random.uniform(0.5, 0.8),
            "rivalry": random.uniform(0.7, 0.9),
            "weather": random.uniform(0.4, 0.7)
        }
        
        return {
            'vegas_spread': game.vegas_spread,
            'data_quality': data_quality_map.get(game.scenario_type, 0.75),
            'week': game.week,
            'scenario_indicators': {
                'is_rivalry': game.scenario_type == "rivalry",
                'weather_concern': game.scenario_type == "weather",
                'desperation_game': game.scenario_type == "desperation",
                'trap_game_potential': game.scenario_type == "trap_game"
            }
        }
    
    def _create_mock_team_data(self, scenario_type: str) -> Dict[str, Any]:
        """Create mock team data influenced by scenario type."""
        base_data = {
            'info': {'conference': {'name': random.choice(list(self.conferences.keys()))}},
            'derived_metrics': {
                'current_record': {
                    'wins': random.randint(4, 9),
                    'losses': random.randint(1, 6),
                    'win_percentage': random.uniform(0.4, 0.8)
                },
                'venue_performance': {
                    'home_record': {'win_percentage': random.uniform(0.5, 0.9)},
                    'away_record': {'win_percentage': random.uniform(0.3, 0.7)}
                }
            }
        }
        
        # Adjust based on scenario
        if scenario_type == "desperation":
            # Team on bubble for bowl eligibility
            base_data['derived_metrics']['current_record']['wins'] = random.randint(5, 6)
            base_data['derived_metrics']['current_record']['win_percentage'] = random.uniform(0.45, 0.55)
        elif scenario_type == "trap_game":
            # Unranked team vs ranked team
            base_data['derived_metrics']['current_record']['win_percentage'] = random.uniform(0.6, 0.8)
            base_data['derived_metrics']['venue_performance']['home_record']['win_percentage'] = random.uniform(0.7, 0.9)
        
        return base_data
    
    def _evaluate_prediction(self, prediction: Dict[str, Any], game: SyntheticGame) -> Dict[str, Any]:
        """Evaluate how well the prediction performed."""
        evaluation = {
            'prediction_failed': 'error' in prediction,
            'detected_edge': False,
            'edge_correct': False,
            'confidence_appropriate': False,
            'beat_vegas': False
        }
        
        if evaluation['prediction_failed']:
            return evaluation
        
        # Check if edge was detected
        edge_size = prediction.get('edge_size', 0.0)
        evaluation['detected_edge'] = edge_size >= 1.0
        
        # Check if edge detection was correct
        if evaluation['detected_edge']:
            contrarian_spread = prediction.get('contrarian_spread', game.vegas_spread)
            contrarian_covered = game.actual_margin > contrarian_spread
            evaluation['edge_correct'] = contrarian_covered
            evaluation['beat_vegas'] = evaluation['edge_correct'] and not game.vegas_was_correct
        
        # Check confidence appropriateness
        confidence = prediction.get('confidence_score', 0.5)
        if game.should_be_contrarian:
            evaluation['confidence_appropriate'] = confidence > 0.6
        else:
            evaluation['confidence_appropriate'] = confidence < 0.7
        
        return evaluation
    
    def _calculate_accuracy_metrics(self, predictions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate overall accuracy metrics."""
        successful_predictions = [p for p in predictions if not p.get('prediction_failed', False)]
        
        if not successful_predictions:
            return {'error': 'No successful predictions'}
        
        # Edge detection accuracy
        edge_predictions = [p for p in successful_predictions if p.get('detected_edge', False)]
        correct_edges = [p for p in edge_predictions if p.get('edge_correct', False)]
        
        # Confidence calibration
        high_conf_predictions = [p for p in successful_predictions 
                               if p['prediction'].get('confidence_score', 0) > 0.7]
        high_conf_correct = [p for p in high_conf_predictions if p.get('edge_correct', False)]
        
        # Beat Vegas rate
        beat_vegas_count = sum(1 for p in successful_predictions if p.get('beat_vegas', False))
        
        return {
            'total_successful': len(successful_predictions),
            'edge_detection_rate': len(edge_predictions) / len(successful_predictions),
            'edge_accuracy_rate': len(correct_edges) / max(len(edge_predictions), 1),
            'high_confidence_rate': len(high_conf_predictions) / len(successful_predictions),
            'high_confidence_accuracy': len(high_conf_correct) / max(len(high_conf_predictions), 1),
            'beat_vegas_rate': beat_vegas_count / len(successful_predictions),
            'confidence_calibration': self._calculate_confidence_calibration(successful_predictions)
        }
    
    def _calculate_confidence_calibration(self, predictions: List[Dict[str, Any]]) -> Dict[str, float]:
        """Calculate confidence calibration metrics."""
        confidence_buckets = {
            'low': (0.0, 0.4),
            'medium': (0.4, 0.7),
            'high': (0.7, 1.0)
        }
        
        calibration = {}
        
        for bucket_name, (min_conf, max_conf) in confidence_buckets.items():
            bucket_predictions = [
                p for p in predictions
                if min_conf <= p['prediction'].get('confidence_score', 0.5) < max_conf
            ]
            
            if bucket_predictions:
                correct_count = sum(1 for p in bucket_predictions if p.get('edge_correct', False))
                calibration[f'{bucket_name}_accuracy'] = correct_count / len(bucket_predictions)
                calibration[f'{bucket_name}_count'] = len(bucket_predictions)
            else:
                calibration[f'{bucket_name}_accuracy'] = 0.0
                calibration[f'{bucket_name}_count'] = 0
        
        return calibration
    
    def _analyze_scenario_performance(self, predictions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze performance by scenario type."""
        scenario_performance = {}
        
        for scenario in ["normal", "trap_game", "desperation", "rivalry", "weather"]:
            scenario_predictions = [p for p in predictions if p.get('scenario_type') == scenario]
            
            if scenario_predictions:
                successful = [p for p in scenario_predictions if not p.get('prediction_failed', False)]
                edges_detected = [p for p in successful if p.get('detected_edge', False)]
                correct_edges = [p for p in edges_detected if p.get('edge_correct', False)]
                
                scenario_performance[scenario] = {
                    'total_games': len(scenario_predictions),
                    'successful_predictions': len(successful),
                    'edges_detected': len(edges_detected),
                    'correct_edges': len(correct_edges),
                    'edge_accuracy': len(correct_edges) / max(len(edges_detected), 1),
                    'should_detect_rate': sum(1 for p in scenario_predictions 
                                            if p.get('should_be_contrarian', False)) / len(scenario_predictions)
                }
        
        return scenario_performance
    
    def _analyze_edge_performance(self, predictions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze performance by edge size."""
        edge_buckets = {
            'small': (1.0, 2.0),
            'medium': (2.0, 3.0),
            'large': (3.0, float('inf'))
        }
        
        edge_performance = {}
        
        for bucket_name, (min_edge, max_edge) in edge_buckets.items():
            bucket_predictions = [
                p for p in predictions
                if not p.get('prediction_failed', False) and 
                min_edge <= p['prediction'].get('edge_size', 0.0) < max_edge
            ]
            
            if bucket_predictions:
                correct_count = sum(1 for p in bucket_predictions if p.get('edge_correct', False))
                edge_performance[bucket_name] = {
                    'count': len(bucket_predictions),
                    'accuracy': correct_count / len(bucket_predictions),
                    'avg_confidence': statistics.mean(
                        p['prediction'].get('confidence_score', 0.5) for p in bucket_predictions
                    )
                }
        
        return edge_performance


class TestSyntheticBacktesting(unittest.TestCase):
    """Test the synthetic backtesting framework."""
    
    def setUp(self):
        """Set up test environment."""
        self.backtester = SyntheticBacktester()
        random.seed(42)  # For reproducible tests
    
    def test_synthetic_game_creation(self):
        """Test synthetic game creation."""
        game = SyntheticGame(
            "GEORGIA", "ALABAMA", 8, -3.5, -1.0, "trap_game"
        )
        
        self.assertEqual(game.home_team, "GEORGIA")
        self.assertEqual(game.away_team, "ALABAMA")
        self.assertEqual(game.week, 8)
        self.assertEqual(game.vegas_spread, -3.5)
        self.assertEqual(game.actual_margin, -1.0)
        self.assertTrue(game.home_covered)  # -1.0 > -3.5
        self.assertTrue(game.vegas_was_correct)  # |(-1.0) - (-3.5)| = 2.5 < 3.0
    
    def test_synthetic_season_generation(self):
        """Test synthetic season generation."""
        games = self.backtester.generate_synthetic_season(num_games=20)
        
        self.assertEqual(len(games), 20)
        
        # Check variety of scenarios
        scenario_types = set(game.scenario_type for game in games)
        self.assertGreater(len(scenario_types), 1, "Should have multiple scenario types")
        
        # Check all games have required fields
        for game in games:
            self.assertIsInstance(game.home_team, str)
            self.assertIsInstance(game.away_team, str)
            self.assertNotEqual(game.home_team, game.away_team)
            self.assertIsInstance(game.vegas_spread, float)
            self.assertIsInstance(game.actual_margin, float)
            self.assertIn(game.week, range(1, 18))
    
    def test_scenario_distribution(self):
        """Test that scenario distribution is reasonable."""
        games = self.backtester.generate_synthetic_season(num_games=100)
        scenario_counts = {}
        
        for game in games:
            scenario_counts[game.scenario_type] = scenario_counts.get(game.scenario_type, 0) + 1
        
        # Normal games should be most common
        self.assertGreater(scenario_counts.get('normal', 0), 40)
        
        # Other scenarios should be present but less common
        for scenario in ['trap_game', 'desperation', 'rivalry']:
            self.assertGreater(scenario_counts.get(scenario, 0), 0)
            self.assertLess(scenario_counts.get(scenario, 0), 30)
    
    def test_backtest_execution(self):
        """Test backtest execution."""
        # Generate small test season
        games = self.backtester.generate_synthetic_season(num_games=5)
        
        # Run backtest
        results = self.backtester.run_backtest(games)
        
        # Check results structure
        self.assertEqual(results['total_games'], 5)
        self.assertIn('predictions', results)
        self.assertIn('accuracy_metrics', results)
        self.assertIn('scenario_performance', results)
        self.assertIn('edge_performance', results)
        
        # Check predictions
        self.assertEqual(len(results['predictions']), 5)
        
        for prediction_result in results['predictions']:
            self.assertIn('game', prediction_result)
            self.assertIn('prediction', prediction_result)
            self.assertIn('scenario_type', prediction_result)
    
    def test_prediction_evaluation(self):
        """Test prediction evaluation logic."""
        # Create a game where contrarian edge should win
        game = SyntheticGame("GEORGIA", "ALABAMA", 8, -7.0, -2.0, "trap_game")
        
        # Mock prediction that detects edge correctly
        mock_prediction = {
            'vegas_spread': -7.0,
            'contrarian_spread': -3.0,  # Better line for home team
            'edge_size': 4.0,
            'confidence_score': 0.8
        }
        
        evaluation = self.backtester._evaluate_prediction(mock_prediction, game)
        
        self.assertFalse(evaluation['prediction_failed'])
        self.assertTrue(evaluation['detected_edge'])  # Edge size >= 1.0
        self.assertTrue(evaluation['edge_correct'])   # Home team covered contrarian spread
        # Note: beat_vegas depends on whether Vegas was also wrong
    
    def test_confidence_calibration(self):
        """Test confidence calibration calculation."""
        # Create test predictions with known confidence levels
        test_predictions = [
            {'prediction': {'confidence_score': 0.3}, 'edge_correct': False},  # Low confidence, wrong
            {'prediction': {'confidence_score': 0.3}, 'edge_correct': False},  # Low confidence, wrong
            {'prediction': {'confidence_score': 0.5}, 'edge_correct': True},   # Medium confidence, right
            {'prediction': {'confidence_score': 0.6}, 'edge_correct': False},  # Medium confidence, wrong
            {'prediction': {'confidence_score': 0.8}, 'edge_correct': True},   # High confidence, right
            {'prediction': {'confidence_score': 0.8}, 'edge_correct': True},   # High confidence, right
        ]
        
        calibration = self.backtester._calculate_confidence_calibration(test_predictions)
        
        # Low confidence should have low accuracy
        self.assertEqual(calibration['low_accuracy'], 0.0)
        self.assertEqual(calibration['low_count'], 2)
        
        # Medium confidence should have medium accuracy
        self.assertEqual(calibration['medium_accuracy'], 0.5)
        self.assertEqual(calibration['medium_count'], 2)
        
        # High confidence should have high accuracy
        self.assertEqual(calibration['high_accuracy'], 1.0)
        self.assertEqual(calibration['high_count'], 2)
    
    def test_scenario_performance_analysis(self):
        """Test scenario performance analysis."""
        # Create mock prediction results
        mock_predictions = [
            {
                'scenario_type': 'trap_game',
                'prediction_failed': False,
                'detected_edge': True,
                'edge_correct': True,
                'should_be_contrarian': True
            },
            {
                'scenario_type': 'trap_game',
                'prediction_failed': False,
                'detected_edge': True,
                'edge_correct': False,
                'should_be_contrarian': True
            },
            {
                'scenario_type': 'normal',
                'prediction_failed': False,
                'detected_edge': False,
                'edge_correct': False,
                'should_be_contrarian': False
            }
        ]
        
        scenario_perf = self.backtester._analyze_scenario_performance(mock_predictions)
        
        # Check trap game performance
        trap_perf = scenario_perf['trap_game']
        self.assertEqual(trap_perf['total_games'], 2)
        self.assertEqual(trap_perf['successful_predictions'], 2)
        self.assertEqual(trap_perf['edges_detected'], 2)
        self.assertEqual(trap_perf['correct_edges'], 1)
        self.assertEqual(trap_perf['edge_accuracy'], 0.5)
        self.assertEqual(trap_perf['should_detect_rate'], 1.0)
        
        # Check normal game performance
        normal_perf = scenario_perf['normal']
        self.assertEqual(normal_perf['total_games'], 1)
        self.assertEqual(normal_perf['edges_detected'], 0)
        self.assertEqual(normal_perf['should_detect_rate'], 0.0)
    
    def test_comprehensive_backtest(self):
        """Test a comprehensive backtest run."""
        # Generate reasonable-sized test season
        games = self.backtester.generate_synthetic_season(num_games=10)
        
        # Run full backtest
        results = self.backtester.run_backtest(games)
        
        # Validate comprehensive results
        self.assertIsInstance(results['accuracy_metrics'], dict)
        self.assertIn('edge_detection_rate', results['accuracy_metrics'])
        self.assertIn('beat_vegas_rate', results['accuracy_metrics'])
        
        # Check scenario performance exists for each scenario type
        scenario_types = set(game.scenario_type for game in games)
        for scenario_type in scenario_types:
            self.assertIn(scenario_type, results['scenario_performance'])
        
        # Validate edge performance buckets
        if results['edge_performance']:
            for bucket in ['small', 'medium', 'large']:
                if bucket in results['edge_performance']:
                    bucket_data = results['edge_performance'][bucket]
                    self.assertIn('count', bucket_data)
                    self.assertIn('accuracy', bucket_data)
                    self.assertGreaterEqual(bucket_data['accuracy'], 0.0)
                    self.assertLessEqual(bucket_data['accuracy'], 1.0)
    
    def test_mock_team_data_generation(self):
        """Test mock team data generation."""
        for scenario in ["normal", "trap_game", "desperation", "rivalry", "weather"]:
            team_data = self.backtester._create_mock_team_data(scenario)
            
            self.assertIn('info', team_data)
            self.assertIn('derived_metrics', team_data)
            self.assertIn('current_record', team_data['derived_metrics'])
            self.assertIn('venue_performance', team_data['derived_metrics'])
            
            win_pct = team_data['derived_metrics']['current_record']['win_percentage']
            self.assertGreaterEqual(win_pct, 0.0)
            self.assertLessEqual(win_pct, 1.0)


if __name__ == '__main__':
    print("Running synthetic backtesting tests...")
    unittest.main()