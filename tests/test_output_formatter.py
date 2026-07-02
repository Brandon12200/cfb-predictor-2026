"""
Unit tests for output formatter module.
Tests clean CLI presentation with emojis, tables, and structured output.
"""

import unittest
from unittest.mock import Mock, patch
from datetime import datetime
from io import StringIO

from output.formatter import OutputFormatter, output_formatter
from engine.edge_detector import EdgeType


class TestOutputFormatter(unittest.TestCase):
    """Test the output formatter functionality."""
    
    def setUp(self):
        """Set up test environment."""
        self.formatter = OutputFormatter(terminal_width=80, use_emojis=True)
        self.formatter_no_emoji = OutputFormatter(terminal_width=80, use_emojis=False)
        
        # Sample prediction result
        self.prediction_result = {
            'home_team': 'GEORGIA',
            'away_team': 'ALABAMA',
            'vegas_spread': -3.5,
            'contrarian_spread': -1.0,
            'edge_size': 2.5,
            'week': 8,
            'timestamp': '2024-10-15T14:30:00',
            'data_sources': ['odds_api', 'espn_api'],
            'data_quality': 0.85,
            'category_adjustments': {
                'coaching_edge': 1.2,
                'situational_context': 0.8,
                'momentum_factors': 0.5
            }
        }
        
        # Sample confidence assessment
        self.confidence_assessment = {
            'confidence_score': 0.75,
            'confidence_level': 'High'
        }
        
        # Mock edge classification
        self.edge_classification = Mock()
        self.edge_classification.edge_type = EdgeType.MODERATE_CONTRARIAN
        self.edge_classification.edge_size = 2.5
        self.edge_classification.confidence = 0.75
        self.edge_classification.recommended_action = "Consider home team +1.0"
        
        # Sample insights
        self.insights = {
            'summary': {
                'headline': 'Moderate contrarian opportunity identified'
            },
            'edge_analysis': {
                'edge_classification': 'Moderate Contrarian',
                'edge_magnitude': '2.5 points',
                'edge_significance': 'Market appears to be overweighting recent performances',
                'market_implications': 'Value exists on the home team'
            },
            'factor_insights': [
                {
                    'factor': 'Experience Differential',
                    'value': 1.2,
                    'weighted_contribution': 0.12,
                    'impact_level': 'High',
                    'explanation': 'Home coach has significant experience advantage'
                },
                {
                    'factor': 'Desperation Index',
                    'value': 0.8,
                    'weighted_contribution': 0.08,
                    'impact_level': 'Medium',
                    'explanation': 'Home team needs win for bowl eligibility'
                }
            ],
            'key_takeaways': [
                'Strong coaching edge favors home team',
                'Situational factors suggest home motivation',
                'Consider home team with the points'
            ],
            'strategic_insights': [
                'Home team has covered in 4 of last 5 home games',
                'Away team may be looking ahead to rivalry game next week'
            ],
            'risk_assessment': {
                'risk_level': 'Medium',
                'risk_factors': ['Weather conditions uncertain', 'Key player questionable'],
                'kelly_criterion_estimate': '2-3% of bankroll'
            },
            'confidence_insights': {
                'strongest_factor': {'component': 'Factor alignment', 'score': 0.9},
                'weakest_factor': {'component': 'Data freshness', 'score': 0.6},
                'improvement_suggestions': ['Get injury report updates', 'Monitor weather forecast']
            }
        }
    
    def test_initialization(self):
        """Test formatter initialization."""
        # With emojis
        formatter = OutputFormatter(terminal_width=120, use_emojis=True)
        self.assertEqual(formatter.terminal_width, 120)
        self.assertTrue(formatter.use_emojis)
        self.assertIsNotNone(formatter.emojis)
        self.assertIsNotNone(formatter.colors)
        
        # Without emojis
        formatter_no_emoji = OutputFormatter(terminal_width=80, use_emojis=False)
        self.assertEqual(formatter_no_emoji.terminal_width, 80)
        self.assertFalse(formatter_no_emoji.use_emojis)
    
    def test_format_prediction_output_basic(self):
        """Test basic prediction output formatting."""
        output = self.formatter.format_prediction_output(
            self.prediction_result,
            self.confidence_assessment,
            self.edge_classification,
            self.insights,
            show_details=False,
            show_factors=False
        )
        
        # Check key sections exist
        self.assertIn('College Football Market Edge Platform', output)
        self.assertIn('ALABAMA @ GEORGIA', output)
        self.assertIn('Week 8', output)
        self.assertIn('PREDICTION SUMMARY', output)
        self.assertIn('Vegas Line', output)
        self.assertIn('Contrarian Line', output)
        self.assertIn('Edge Size: 2.50 points', output)
        self.assertIn('Confidence: High', output)
        self.assertIn('EDGE ANALYSIS', output)
        self.assertIn('KEY TAKEAWAYS', output)
        
        # Check emojis are present
        self.assertIn('🎯', output)
        self.assertIn('💰', output)
        self.assertIn('🔥', output)
    
    def test_format_prediction_output_no_emojis(self):
        """Test output formatting without emojis."""
        output = self.formatter_no_emoji.format_prediction_output(
            self.prediction_result,
            self.confidence_assessment,
            self.edge_classification,
            self.insights,
            show_details=False,
            show_factors=False
        )
        
        # Check content exists but fewer emojis (some might still appear in insights)
        self.assertIn('PREDICTION SUMMARY', output)
        # No emoji formatter should have significantly fewer emojis
        emoji_count_no_emoji = sum(1 for char in output if ord(char) > 127)
        
        output_with_emoji = self.formatter.format_prediction_output(
            self.prediction_result,
            self.confidence_assessment,
            self.edge_classification,
            self.insights,
            show_details=False,
            show_factors=False
        )
        emoji_count_with_emoji = sum(1 for char in output_with_emoji if ord(char) > 127)
        
        # Should have fewer emojis when disabled
        self.assertLess(emoji_count_no_emoji, emoji_count_with_emoji)
    
    def test_format_with_factor_breakdown(self):
        """Test output with factor breakdown."""
        output = self.formatter.format_prediction_output(
            self.prediction_result,
            self.confidence_assessment,
            self.edge_classification,
            self.insights,
            show_details=False,
            show_factors=True
        )
        
        # Check factor section
        self.assertIn('FACTOR BREAKDOWN', output)
        self.assertIn('Category Summary:', output)
        self.assertIn('Coaching Edge: +1.200 points', output)
        self.assertIn('Situational Context: +0.800 points', output)
        self.assertIn('Momentum Factors: +0.500 points', output)
        self.assertIn('Key Contributing Factors:', output)
        self.assertIn('Experience Differential', output)
        self.assertIn('Desperation Index', output)
    
    def test_format_with_detailed_insights(self):
        """Test output with detailed insights."""
        output = self.formatter.format_prediction_output(
            self.prediction_result,
            self.confidence_assessment,
            self.edge_classification,
            self.insights,
            show_details=True,
            show_factors=False
        )
        
        # Check detailed sections
        self.assertIn('DETAILED ANALYSIS', output)
        self.assertIn('Strategic Considerations:', output)
        self.assertIn('Risk Assessment: Medium', output)
        self.assertIn('Risk Factors:', output)
        self.assertIn('Kelly Estimate:', output)
        self.assertIn('Confidence Analysis:', output)
        self.assertIn('Strongest:', output)
        self.assertIn('Weakest:', output)
    
    def test_format_error_output(self):
        """Test error output formatting."""
        error_msg = "Unable to find team: INVALID_TEAM"
        context = {
            'requested_home': 'INVALID_TEAM',
            'requested_away': 'ALABAMA',
            'api_status': 'OK'
        }
        
        output = self.formatter.format_error_output(error_msg, context)
        
        self.assertIn('PREDICTION ERROR', output)
        self.assertIn(error_msg, output)
        self.assertIn('Context:', output)
        self.assertIn('requested_home: INVALID_TEAM', output)
        self.assertIn('Suggestion:', output)
        self.assertIn('❌', output)  # Error emoji
    
    def test_format_weekly_summary(self):
        """Test weekly summary formatting."""
        weekly_results = [
            {
                'home_team': 'GEORGIA',
                'away_team': 'ALABAMA',
                'edge_size': 3.5,
                'confidence': 0.82,
                'recommendation': 'Strong contrarian play on home team'
            },
            {
                'home_team': 'OHIO STATE',
                'away_team': 'MICHIGAN',
                'edge_size': 2.1,
                'confidence': 0.65,
                'recommendation': 'Moderate edge on away team'
            },
            {
                'home_team': 'TEXAS',
                'away_team': 'OKLAHOMA',
                'edge_size': 0.5,
                'confidence': 0.45,
                'recommendation': 'No significant edge'
            }
        ]
        
        output = self.formatter.format_weekly_summary(weekly_results, week=8, min_edge=2.0)
        
        self.assertIn('WEEKLY ANALYSIS - WEEK 8', output)
        self.assertIn('Total Games Analyzed: 3', output)
        self.assertIn('Games with 2.0+ Point Edges: 2', output)
        self.assertIn('TOP OPPORTUNITIES:', output)
        self.assertIn('ALABAMA @ GEORGIA', output)
        self.assertIn('Edge: 3.5 pts', output)
        self.assertIn('MICHIGAN @ OHIO STATE', output)
        
        # Should not include low edge game
        self.assertNotIn('OKLAHOMA @ TEXAS', output)
    
    def test_edge_emoji_selection(self):
        """Test correct emoji selection for edge types."""
        test_cases = [
            ('strong contrarian', 'strong_buy'),
            ('moderate edge', 'moderate_buy'),
            ('slight opportunity', 'slight_buy'),
            ('consensus play', 'consensus'),
            ('no edge', 'no_edge'),
            ('avoid', 'avoid')
        ]
        
        for edge_class, expected_key in test_cases:
            insights = {'edge_analysis': {'edge_classification': edge_class}}
            emoji = self.formatter._get_edge_emoji(insights)
            expected_emoji = self.formatter.emojis[expected_key]
            self.assertEqual(emoji, expected_emoji)
    
    def test_confidence_emoji_selection(self):
        """Test confidence emoji selection."""
        # By level
        self.assertEqual(
            self.formatter._get_confidence_emoji('Very High'),
            self.formatter.emojis['high_confidence']
        )
        self.assertEqual(
            self.formatter._get_confidence_emoji('Medium'),
            self.formatter.emojis['medium_confidence']
        )
        self.assertEqual(
            self.formatter._get_confidence_emoji('Low'),
            self.formatter.emojis['low_confidence']
        )
        
        # By score
        self.assertEqual(
            self.formatter._get_confidence_emoji_from_score(0.85),
            self.formatter.emojis['high_confidence']
        )
        self.assertEqual(
            self.formatter._get_confidence_emoji_from_score(0.60),
            self.formatter.emojis['medium_confidence']
        )
        self.assertEqual(
            self.formatter._get_confidence_emoji_from_score(0.35),
            self.formatter.emojis['low_confidence']
        )
    
    def test_text_wrapping(self):
        """Test long text wrapping."""
        long_text = "This is a very long explanation that should be wrapped properly to fit within the terminal width without breaking words awkwardly or creating unreadable output"
        
        insights = {
            'summary': {'headline': 'Test'},
            'edge_analysis': {
                'edge_classification': 'Test',
                'edge_magnitude': 'Test',
                'edge_significance': long_text
            },
            'key_takeaways': []
        }
        
        output = self.formatter.format_prediction_output(
            self.prediction_result,
            self.confidence_assessment,
            self.edge_classification,
            insights,
            show_details=False,
            show_factors=False
        )
        
        # Check that no line exceeds terminal width
        lines = output.split('\n')
        for line in lines:
            # Account for emoji width (emojis may display as 2 chars)
            self.assertLessEqual(len(line.encode('utf-8')), self.formatter.terminal_width * 2)
    
    def test_center_text(self):
        """Test text centering."""
        text = "Centered Text"
        centered = self.formatter._center_text(text)
        
        # Should have padding on left
        self.assertTrue(centered.startswith(' '))
        self.assertIn(text, centered)
        
        # Very long text should not be centered
        long_text = "A" * 100
        not_centered = self.formatter._center_text(long_text)
        self.assertEqual(not_centered, long_text)
    
    def test_export_to_csv(self):
        """Test CSV export functionality."""
        results = [
            {
                'timestamp': '2024-10-15T14:30:00',
                'home_team': 'GEORGIA',
                'away_team': 'ALABAMA',
                'week': 8,
                'vegas_spread': -3.5,
                'contrarian_spread': -1.0,
                'edge_size': 2.5,
                'edge_classification': 'Moderate Contrarian',
                'confidence': 0.75,
                'recommendation': 'Consider home team',
                'data_quality': 0.85
            },
            {
                'timestamp': '2024-10-15T14:35:00',
                'home_team': 'OHIO STATE',
                'away_team': 'MICHIGAN',
                'week': 8,
                'vegas_spread': -7.0,
                'contrarian_spread': -4.5,
                'edge_size': 2.5,
                'edge_classification': 'Moderate Contrarian',
                'confidence': 0.68,
                'recommendation': 'Consider home team',
                'data_quality': 0.80
            }
        ]
        
        csv_output = self.formatter.export_to_csv(results)
        
        # Check headers
        self.assertIn('timestamp,home_team,away_team,week', csv_output)
        
        # Check data rows
        self.assertIn('"GEORGIA"', csv_output)
        self.assertIn('"ALABAMA"', csv_output)
        self.assertIn('"-3.5"', csv_output)
        self.assertIn('"0.75"', csv_output)
        
        # Check proper CSV formatting
        lines = csv_output.split('\n')
        self.assertEqual(len(lines), 3)  # Header + 2 data rows
        
        # Check all rows have same number of columns
        header_cols = len(lines[0].split(','))
        for line in lines[1:]:
            # Count commas outside quotes
            col_count = line.count('","') + 1
            self.assertEqual(col_count, header_cols)
    
    def test_missing_data_handling(self):
        """Test handling of missing data in formatting."""
        # Minimal prediction result
        minimal_result = {
            'home_team': 'GEORGIA',
            'away_team': 'ALABAMA'
        }
        
        # Minimal insights
        minimal_insights = {
            'summary': {},
            'edge_analysis': {},
            'key_takeaways': []
        }
        
        # Should not crash with missing data
        output = self.formatter.format_prediction_output(
            minimal_result,
            {},
            self.edge_classification,
            minimal_insights,
            show_details=False,
            show_factors=False
        )
        
        self.assertIn('GEORGIA', output)
        self.assertIn('ALABAMA', output)
        self.assertIn('No betting line available', output)
        self.assertIn('No specific takeaways identified', output)
    
    def test_timestamp_formatting(self):
        """Test timestamp formatting in footer."""
        # ISO format timestamp
        result_iso = dict(self.prediction_result)
        result_iso['timestamp'] = '2024-10-15T14:30:00'
        
        output = self.formatter.format_prediction_output(
            result_iso,
            self.confidence_assessment,
            self.edge_classification,
            self.insights,
            show_details=False,
            show_factors=False
        )
        
        self.assertIn('Generated: 2024-10-15 14:30:00', output)
        
        # Invalid timestamp should not crash
        result_bad = dict(self.prediction_result)
        result_bad['timestamp'] = 'invalid-timestamp'
        
        output_bad = self.formatter.format_prediction_output(
            result_bad,
            self.confidence_assessment,
            self.edge_classification,
            self.insights,
            show_details=False,
            show_factors=False
        )
        
        self.assertIn('Generated: invalid-timestamp', output_bad)
    
    def test_quality_emoji_thresholds(self):
        """Test data quality emoji thresholds."""
        test_cases = [
            (0.85, 'success'),
            (0.55, 'warning'),
            (0.25, 'error')
        ]
        
        for quality, expected_key in test_cases:
            emoji = self.formatter._get_quality_emoji(quality)
            expected_emoji = self.formatter.emojis[expected_key]
            self.assertEqual(emoji, expected_emoji)
    
    def test_risk_emoji_selection(self):
        """Test risk level emoji selection."""
        test_cases = [
            ('High Risk', 'error'),
            ('Medium Risk', 'warning'),
            ('Low Risk', 'success')
        ]
        
        for risk_level, expected_key in test_cases:
            emoji = self.formatter._get_risk_emoji(risk_level)
            expected_emoji = self.formatter.emojis[expected_key]
            self.assertEqual(emoji, expected_emoji)
    
    def test_edge_size_emoji_thresholds(self):
        """Test edge size emoji thresholds."""
        test_cases = [
            (4.0, 'strong_buy'),
            (2.5, 'moderate_buy'),
            (1.5, 'slight_buy'),
            (0.5, 'no_edge')
        ]
        
        for edge_size, expected_key in test_cases:
            emoji = self.formatter._get_edge_size_emoji(edge_size)
            expected_emoji = self.formatter.emojis[expected_key]
            self.assertEqual(emoji, expected_emoji)
    
    def test_global_formatter_instance(self):
        """Test global formatter instance."""
        from output.formatter import output_formatter
        
        self.assertIsInstance(output_formatter, OutputFormatter)
        self.assertEqual(output_formatter.terminal_width, 80)
        self.assertTrue(output_formatter.use_emojis)


if __name__ == '__main__':
    unittest.main()