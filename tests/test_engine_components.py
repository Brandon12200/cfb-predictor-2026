"""
Test suite for engine components of the CFB Market Edge Platform.
Tests market efficiency detector, adaptive calibrator, game filter, and dynamic weighter.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import json
import tempfile
from pathlib import Path

from engine.market_efficiency_detector import MarketEfficiencyDetector
from engine.adaptive_calibrator import AdaptiveCalibrator
from engine.game_filter import GameQualityFilter
from engine.dynamic_weighter import DynamicWeighter


class TestMarketEfficiencyDetector(unittest.TestCase):
    """Test market efficiency detection."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.detector = MarketEfficiencyDetector()
        
        self.sample_game_data = {
            'home_team': 'Alabama',
            'away_team': 'Auburn',
            'vegas_spread': -14.5,
            'opening_spread': -13.0,
            'week': 12,
            'is_rivalry': True,
            'public_betting_percentage': 75.0
        }
    
    def test_analyze_market_efficiency_basic(self):
        """Test basic market efficiency analysis."""
        result = self.detector.analyze_market_efficiency(self.sample_game_data)
        
        self.assertIn('efficiency_score', result)
        self.assertIn('market_indicators', result)
        self.assertIn('recommendation', result)
        self.assertIsInstance(result['efficiency_score'], float)
        self.assertGreaterEqual(result['efficiency_score'], 0.0)
        self.assertLessEqual(result['efficiency_score'], 1.0)
    
    def test_line_movement_analysis(self):
        """Test line movement detection."""
        line_movement = self.detector._analyze_line_movement(self.sample_game_data)
        
        self.assertIn('total_movement', line_movement)
        self.assertIn('direction', line_movement)
        self.assertIn('significance', line_movement)
        
        # Should detect 1.5 point movement
        self.assertEqual(line_movement['total_movement'], 1.5)
        self.assertEqual(line_movement['direction'], 'TOWARD_HOME')
    
    def test_sharp_public_split_detection(self):
        """Test sharp vs public money detection."""
        sharp_public = self.detector._detect_sharp_public_split(self.sample_game_data)
        
        self.assertIn('public_percentage', sharp_public)
        self.assertIn('fade_public', sharp_public)
        
        # Should identify public fade opportunity at 75%
        self.assertTrue(sharp_public['fade_public'])
    
    def test_reverse_line_movement(self):
        """Test reverse line movement detection."""
        # Create scenario with RLM
        game_data = self.sample_game_data.copy()
        game_data['public_betting_percentage'] = 80  # Heavy public on favorite
        game_data['vegas_spread'] = -12.0  # Line moved toward dog
        game_data['opening_spread'] = -14.0
        
        rlm = self.detector._detect_reverse_line_movement(game_data)
        
        self.assertTrue(rlm['detected'])
        self.assertEqual(rlm['side'], 'UNDERDOG')
        self.assertGreater(rlm['strength'], 0)
    
    def test_game_efficiency_calculation(self):
        """Test game-specific efficiency calculation."""
        game_efficiency = self.detector._calculate_game_efficiency(self.sample_game_data)
        
        self.assertIn('final_efficiency', game_efficiency)
        self.assertIn('modifiers', game_efficiency)
        
        # Should have rivalry modifier
        modifier_names = [mod[0] for mod in game_efficiency['modifiers']]
        self.assertIn('rivalry', modifier_names)


class TestAdaptiveCalibrator(unittest.TestCase):
    """Test adaptive confidence calibration."""
    
    def setUp(self):
        """Set up test fixtures."""
        with tempfile.TemporaryDirectory() as temp_dir:
            self.temp_path = Path(temp_dir)
            
        # Mock the calibration file path
        with patch.object(AdaptiveCalibrator, '__init__', lambda x: None):
            self.calibrator = AdaptiveCalibrator()
            self.calibrator.calibration_file = self.temp_path / "test_calibration.json"
            self.calibrator.calibration_file.parent.mkdir(parents=True, exist_ok=True)
            self.calibrator.min_samples_for_adjustment = 5
            self.calibrator.adjustment_rate = 0.1
            self.calibrator.target_calibration_ratio = 1.0
            self.calibrator.logger = Mock()
            
        # Initialize with test state
        self.calibrator.calibration_state = self.calibrator._load_calibration_state()
    
    def test_calibrate_confidence_basic(self):
        """Test basic confidence calibration."""
        result = self.calibrator.calibrate_confidence(
            raw_confidence=0.7,
            prediction_type='SLIGHT_CONTRARIAN',
            edge_size=2.5,
            week=1
        )
        
        self.assertIn('calibrated_confidence', result)
        self.assertIn('adjustment_factor', result)
        self.assertIn('calibration_metrics', result)
        self.assertIsInstance(result['calibrated_confidence'], float)
        self.assertGreaterEqual(result['calibrated_confidence'], 0.15)
        self.assertLessEqual(result['calibrated_confidence'], 0.85)
    
    def test_early_season_dampener(self):
        """Test early season confidence dampening."""
        week_1_result = self.calibrator.calibrate_confidence(0.8, 'CONSENSUS_ALIGNMENT', 1.5, 1)
        week_5_result = self.calibrator.calibrate_confidence(0.8, 'CONSENSUS_ALIGNMENT', 1.5, 5)
        
        # Week 1 should have lower confidence due to dampener
        self.assertLess(week_1_result['calibrated_confidence'], week_5_result['calibrated_confidence'])
    
    def test_confidence_bucket_assignment(self):
        """Test confidence bucket classification."""
        bucket_30 = self.calibrator._get_confidence_bucket(0.3)
        bucket_70 = self.calibrator._get_confidence_bucket(0.7)
        
        self.assertEqual(bucket_30, '0.25-0.35')
        self.assertEqual(bucket_70, '0.65-0.75')
    
    def test_calibration_adjustment_calculation(self):
        """Test calibration adjustment calculation."""
        # Mock some accuracy data
        accuracy_data = {
            '0.65-0.75': {'correct': 4, 'total': 10}  # 40% accuracy in 70% bucket = overconfident
        }
        
        adjustments = self.calibrator._calculate_calibration_adjustments(accuracy_data)
        
        # Should detect overconfidence and suggest global adjustment
        self.assertIn('global', adjustments)
        self.assertEqual(adjustments['global']['issue'], 'overconfidence')
    
    def test_update_calibration(self):
        """Test calibration update from results."""
        predictions = [
            {'home_team': 'Alabama', 'away_team': 'Auburn', 'confidence': 70, 'factor_breakdown': {'coaching': 0.5}}
        ]
        results = [
            {'home_team': 'Alabama', 'away_team': 'Auburn', 'prediction_correct': True}
        ]
        
        # Need minimum samples, so add more
        for i in range(10):
            predictions.append({
                'home_team': f'Team{i}A', 'away_team': f'Team{i}B', 
                'confidence': 60, 'factor_breakdown': {'coaching': 0.3}
            })
            results.append({
                'home_team': f'Team{i}A', 'away_team': f'Team{i}B', 
                'prediction_correct': i % 2 == 0  # 50% accuracy
            })
        
        update_result = self.calibrator.update_calibration(predictions, results)
        
        self.assertIn('predictions_processed', update_result)
        self.assertGreater(update_result['predictions_processed'], 0)


class TestGameQualityFilter(unittest.TestCase):
    """Test game quality filtering."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.filter = GameQualityFilter()
        
        self.high_quality_game = {
            'home_team': 'Alabama',
            'away_team': 'Georgia',
            'vegas_spread': -7.5,
            'week': 6,
            'home_team_data': {'info': {'conference': {'name': 'SEC'}}},
            'away_team_data': {'info': {'conference': {'name': 'SEC'}}},
            'tv_coverage': True
        }
        
        self.poor_quality_game = {
            'home_team': 'Alabama',
            'away_team': 'Chattanooga',  # FCS school
            'vegas_spread': -45.0,  # Extreme spread
            'week': 2
        }
    
    def test_evaluate_high_quality_game(self):
        """Test evaluation of high quality game."""
        result = self.filter.evaluate_game_quality(self.high_quality_game)
        
        self.assertIn('overall_quality', result)
        self.assertIn('quality_score', result)
        self.assertTrue(result['should_analyze'])
        self.assertGreaterEqual(result['quality_score'], 0.6)
    
    def test_evaluate_poor_quality_game(self):
        """Test evaluation of poor quality game."""
        result = self.filter.evaluate_game_quality(self.poor_quality_game)
        
        self.assertEqual(result['overall_quality'], 'POOR')
        self.assertFalse(result['should_analyze'])
        self.assertLess(result['quality_score'], 0.5)
    
    def test_spread_quality_evaluation(self):
        """Test spread quality evaluation."""
        # Normal spread
        normal_game = {'vegas_spread': -7.5}
        normal_result = self.filter._evaluate_spread_quality(normal_game)
        self.assertEqual(normal_result['quality'], 'GOOD')
        
        # Extreme spread
        extreme_game = {'vegas_spread': -35.0}
        extreme_result = self.filter._evaluate_spread_quality(extreme_game)
        self.assertEqual(extreme_result['quality'], 'POOR')
        self.assertIn('EXTREME_SPREAD_35.0', extreme_result['issues'])
    
    def test_fcs_team_detection(self):
        """Test FCS team detection."""
        self.assertTrue(self.filter._is_fcs_team('Chattanooga'))
        self.assertTrue(self.filter._is_fcs_team('North Dakota State'))
        self.assertFalse(self.filter._is_fcs_team('Alabama'))
        self.assertFalse(self.filter._is_fcs_team('Ohio State'))
    
    def test_conference_tier_classification(self):
        """Test conference tier classification."""
        sec_data = {'info': {'conference': {'name': 'Southeastern Conference'}}}
        aac_data = {'info': {'conference': {'name': 'American Athletic Conference'}}}
        
        self.assertEqual(self.filter._get_conference_tier(sec_data), 'POWER')
        self.assertEqual(self.filter._get_conference_tier(aac_data), 'GROUP_5')
    
    def test_recommended_games_filtering(self):
        """Test recommended games filtering and ranking."""
        games = [self.high_quality_game, self.poor_quality_game]
        
        recommended = self.filter.get_recommended_games(games)
        
        # Should only recommend the high quality game
        self.assertEqual(len(recommended), 1)
        self.assertEqual(recommended[0]['home_team'], 'Alabama')
        self.assertEqual(recommended[0]['away_team'], 'Georgia')


class TestDynamicWeighter(unittest.TestCase):
    """Test dynamic factor weighting."""
    
    def setUp(self):
        """Set up test fixtures."""
        with tempfile.TemporaryDirectory() as temp_dir:
            self.temp_path = Path(temp_dir)
            
        # Mock the weights file path
        with patch.object(DynamicWeighter, '__init__', lambda x: None):
            self.weighter = DynamicWeighter()
            self.weighter.weights_file = self.temp_path / "test_weights.json"
            self.weighter.weights_file.parent.mkdir(parents=True, exist_ok=True)
            self.weighter.learning_rate = 0.05
            self.weighter.min_samples_for_adjustment = 5
            self.weighter.stability_threshold = 0.1
            self.weighter.logger = Mock()
            
        # Initialize with test state
        self.weighter.weight_state = self.weighter._load_weight_state()
        
        self.sample_context = {
            'week': 6,
            'home_team_data': {'info': {'conference': {'name': 'SEC'}}},
            'away_team_data': {'info': {'conference': {'name': 'SEC'}}},
            'prediction_type': 'SLIGHT_CONTRARIAN'
        }
    
    def test_get_optimized_weights(self):
        """Test optimized weight calculation."""
        weights = self.weighter.get_optimized_weights(self.sample_context)
        
        self.assertIsInstance(weights, dict)
        self.assertGreater(len(weights), 0)
        
        # Check that weights sum to approximately 1.0
        total_weight = sum(weights.values())
        self.assertAlmostEqual(total_weight, 1.0, places=2)
    
    def test_seasonal_adjustments(self):
        """Test seasonal weight adjustments."""
        base_weights = {'coaching_differential': 0.25, 'momentum_factors': 0.15}
        
        # Early season should reduce coaching weight, momentum weight
        early_context = {'week': 2}
        early_weights = self.weighter._apply_seasonal_adjustments(base_weights, early_context)
        
        self.assertLess(early_weights['coaching_differential'], base_weights['coaching_differential'])
        self.assertLess(early_weights['momentum_factors'], base_weights['momentum_factors'])
        
        # Late season should increase desperation weight
        late_context = {'week': 13}
        late_weights = self.weighter._apply_seasonal_adjustments(base_weights, late_context)
        # Would need desperation_index in base_weights to test this properly
    
    def test_conference_adjustments(self):
        """Test conference-specific adjustments."""
        base_weights = {'coaching_differential': 0.25, 'experience_differential': 0.2}
        
        sec_context = {'home_team_data': {'info': {'conference': {'name': 'SEC'}}}}
        sec_weights = self.weighter._apply_conference_adjustments(base_weights, sec_context)
        
        # SEC should boost coaching and experience weights
        self.assertGreaterEqual(sec_weights['coaching_differential'], base_weights['coaching_differential'])
    
    def test_weight_normalization(self):
        """Test weight normalization."""
        unnormalized_weights = {
            'factor1': 0.5,
            'factor2': 0.3,
            'factor3': 0.8  # Total = 1.6
        }
        
        normalized = self.weighter._normalize_weights(unnormalized_weights)
        total = sum(normalized.values())
        
        self.assertAlmostEqual(total, 1.0, places=5)
    
    def test_factor_performance_analysis(self):
        """Test factor performance analysis."""
        matched_data = [
            {
                'correct': True,
                'factors': {'coaching_differential': 0.5, 'momentum_factors': 0.3}
            },
            {
                'correct': False,
                'factors': {'coaching_differential': 0.2, 'momentum_factors': 0.8}
            },
            {
                'correct': True,
                'factors': {'coaching_differential': 0.7, 'momentum_factors': 0.1}
            }
        ]
        
        performance = self.weighter._analyze_factor_performance(matched_data)
        
        self.assertIn('coaching_differential', performance)
        self.assertIn('momentum_factors', performance)
        
        # Coaching should have better predictive power (higher values when correct)
        coaching_perf = performance['coaching_differential']
        self.assertGreater(coaching_perf['accuracy'], 0.5)  # 2/3 correct


if __name__ == '__main__':
    unittest.main()