"""
Unit tests for insights generator module.
Tests human-readable explanations and actionable insights generation.
"""

import unittest
from unittest.mock import Mock
from datetime import datetime

from output.insights_generator import InsightsGenerator, insights_generator
from engine.edge_detector import EdgeType


class TestInsightsGenerator(unittest.TestCase):
    """Test the insights generator functionality."""
    
    def setUp(self):
        """Set up test environment."""
        self.generator = InsightsGenerator()
        
        # Sample prediction result
        self.prediction_result = {
            'home_team': 'GEORGIA',
            'away_team': 'ALABAMA',
            'vegas_spread': -3.5,
            'contrarian_spread': -0.5,
            'edge_size': 3.0,
            'week': 8,
            'data_quality': 0.85,
            'category_adjustments': {
                'coaching_edge': 1.5,
                'situational_context': 1.0,
                'momentum_factors': 0.5
            },
            'factor_breakdown': {
                'ExperienceDifferential': {
                    'success': True,
                    'value': 1.2,
                    'weighted_value': 0.12,
                    'explanation': 'Home coach has 5 more years experience'
                },
                'DesperationIndex': {
                    'success': True,
                    'value': 0.8,
                    'weighted_value': 0.08,
                    'explanation': 'Home team needs win for bowl eligibility'
                },
                'ATSRecentForm': {
                    'success': True,
                    'value': 0.5,
                    'weighted_value': 0.05,
                    'explanation': 'Home team 3-1 ATS in last 4'
                },
                'VenuePerformance': {
                    'success': True,
                    'value': 0.3,
                    'weighted_value': 0.03,
                    'explanation': 'Strong home field advantage'
                },
                'RevengeGame': {
                    'success': False,
                    'value': 0.0,
                    'weighted_value': 0.0,
                    'explanation': ''
                }
            }
        }
        
        # Sample confidence assessment
        self.confidence_assessment = {
            'confidence_score': 0.75,
            'confidence_level': 'High',
            'components': {
                'data_quality': 0.85,
                'factor_consensus': 0.80,
                'edge_significance': 0.70,
                'market_context': 0.65,
                'historical_performance': 0.75,
                'situational_factors': 0.70
            }
        }
        
        # Mock edge classification
        self.edge_classification = Mock()
        self.edge_classification.edge_type = EdgeType.STRONG_CONTRARIAN
        self.edge_classification.edge_size = 3.0
        self.edge_classification.confidence = 0.75
        self.edge_classification.recommended_action = "Strong play on home team +3.5"
        
        # Sample context
        self.context = {
            'vegas_spread': -3.5,
            'data_quality': 0.85,
            'week': 8,
            'home_team_data': {'info': {'conference': {'name': 'SEC'}}},
            'away_team_data': {'info': {'conference': {'name': 'SEC'}}}
        }
    
    def test_initialization(self):
        """Test generator initialization."""
        generator = InsightsGenerator()
        
        # Check templates are loaded
        self.assertIsNotNone(generator.edge_templates)
        self.assertIn(EdgeType.STRONG_CONTRARIAN, generator.edge_templates)
        self.assertIn(EdgeType.NO_EDGE, generator.edge_templates)
        
        # Check factor descriptions
        self.assertIsNotNone(generator.factor_descriptions)
        self.assertIn('ExperienceDifferential', generator.factor_descriptions)
        self.assertIn('DesperationIndex', generator.factor_descriptions)
    
    def test_generate_prediction_insights_complete(self):
        """Test complete insights generation."""
        insights = self.generator.generate_prediction_insights(
            self.prediction_result,
            self.confidence_assessment,
            self.edge_classification,
            self.context
        )
        
        # Check all sections are present
        expected_sections = [
            'summary', 'edge_analysis', 'factor_insights',
            'confidence_insights', 'strategic_insights',
            'risk_assessment', 'key_takeaways'
        ]
        
        for section in expected_sections:
            self.assertIn(section, insights)
            self.assertIsNotNone(insights[section])
    
    def test_generate_summary_insight(self):
        """Test summary insight generation."""
        summary = self.generator._generate_summary_insight(
            self.prediction_result,
            self.confidence_assessment,
            self.edge_classification
        )
        
        self.assertEqual(summary['headline'], "🎯 STRONG CONTRARIAN OPPORTUNITY")
        self.assertEqual(summary['matchup'], "ALABAMA @ GEORGIA")
        self.assertEqual(summary['edge_size'], 3.0)
        self.assertEqual(summary['confidence_level'], 'High')
        self.assertIn('spread_comparison', summary)
        self.assertEqual(summary['spread_comparison']['vegas_line'], "GEORGIA -3.5")
        self.assertEqual(summary['spread_comparison']['contrarian_line'], "GEORGIA -0.5")
    
    def test_edge_insights_generation(self):
        """Test edge analysis insights."""
        edge_insights = self.generator._generate_edge_insights(
            self.prediction_result,
            self.edge_classification
        )
        
        self.assertEqual(edge_insights['edge_classification'], 'Strong Contrarian')
        self.assertEqual(edge_insights['edge_magnitude'], 'Large')
        self.assertIn('significant market inefficiency', edge_insights['edge_significance'])
        self.assertIn('rare', edge_insights['historical_context'])
        self.assertIn('Market may be missing key factors', edge_insights['market_implications'])
    
    def test_factor_insights_generation(self):
        """Test factor insights generation."""
        factor_insights = self.generator._generate_factor_insights(
            self.prediction_result,
            self.context
        )
        
        # Should return list of factor insights
        self.assertIsInstance(factor_insights, list)
        self.assertGreater(len(factor_insights), 0)
        
        # Check first factor (should be ExperienceDifferential - highest impact)
        first_factor = factor_insights[0]
        self.assertEqual(first_factor['factor'], 'ExperienceDifferential')
        self.assertEqual(first_factor['value'], 1.2)
        self.assertEqual(first_factor['weighted_contribution'], 0.12)
        self.assertEqual(first_factor['impact_level'], 'Medium Impact')
        self.assertIn('experience', first_factor['explanation'])
        
        # Should not include failed factors
        factor_names = [f['factor'] for f in factor_insights]
        self.assertNotIn('RevengeGame', factor_names)
    
    def test_confidence_insights_generation(self):
        """Test confidence insights generation."""
        confidence_insights = self.generator._generate_confidence_insights(
            self.confidence_assessment
        )
        
        self.assertEqual(confidence_insights['overall_confidence'], 'High')
        self.assertEqual(confidence_insights['confidence_score'], 0.75)
        self.assertIn('Good confidence', confidence_insights['confidence_explanation'])
        
        # Check strongest/weakest factors
        self.assertEqual(confidence_insights['strongest_factor']['component'], 'Data Quality')
        self.assertEqual(confidence_insights['strongest_factor']['score'], 0.85)
        self.assertEqual(confidence_insights['weakest_factor']['component'], 'Market Context')
        self.assertEqual(confidence_insights['weakest_factor']['score'], 0.65)
        
        # Check improvement suggestions
        self.assertIsInstance(confidence_insights['improvement_suggestions'], list)
    
    def test_strategic_insights_generation(self):
        """Test strategic insights generation."""
        strategic_insights = self.generator._generate_strategic_insights(
            self.prediction_result,
            self.confidence_assessment,
            self.edge_classification,
            self.context
        )
        
        self.assertIsInstance(strategic_insights, list)
        self.assertGreater(len(strategic_insights), 0)
        
        # Should mention position sizing given high confidence
        position_insight = next((i for i in strategic_insights if 'position' in i.lower()), None)
        self.assertIsNotNone(position_insight)
        self.assertIn('standard position', position_insight)
        
        # Should mention mid-season timing
        timing_insight = next((i for i in strategic_insights if 'season' in i.lower()), None)
        self.assertIsNotNone(timing_insight)
        
        # Should mention data quality
        data_insight = next((i for i in strategic_insights if 'data quality' in i.lower()), None)
        self.assertIsNotNone(data_insight)
        self.assertIn('High data quality', data_insight)
    
    def test_risk_assessment_generation(self):
        """Test risk assessment generation."""
        risk_assessment = self.generator._generate_risk_assessment(
            self.prediction_result,
            self.confidence_assessment,
            self.context
        )
        
        self.assertIn('risk_level', risk_assessment)
        self.assertIn('risk_factors', risk_assessment)
        self.assertIn('risk_mitigation', risk_assessment)
        self.assertIn('kelly_criterion_estimate', risk_assessment)
        self.assertIn('volatility_assessment', risk_assessment)
        
        # With high confidence and good edge, risk should be low
        self.assertEqual(risk_assessment['risk_level'], 'Low')
        
        # Kelly estimate should be reasonable
        self.assertIn('%', risk_assessment['kelly_criterion_estimate'])
        self.assertNotIn('0%', risk_assessment['kelly_criterion_estimate'])
    
    def test_key_takeaways_generation(self):
        """Test key takeaways generation."""
        takeaways = self.generator._generate_key_takeaways(
            self.prediction_result,
            self.confidence_assessment,
            self.edge_classification
        )
        
        self.assertIsInstance(takeaways, list)
        self.assertGreater(len(takeaways), 0)
        
        # Should mention edge size
        edge_takeaway = next((t for t in takeaways if '3.0 point' in t), None)
        self.assertIsNotNone(edge_takeaway)
        
        # Should mention confidence
        confidence_takeaway = next((t for t in takeaways if 'confidence' in t.lower()), None)
        self.assertIsNotNone(confidence_takeaway)
        
        # Should mention primary factor category
        factor_takeaway = next((t for t in takeaways if 'Coaching Edge' in t), None)
        self.assertIsNotNone(factor_takeaway)
    
    def test_edge_magnitude_classification(self):
        """Test edge magnitude classification."""
        test_cases = [
            (6.0, "Extremely Large"),
            (3.5, "Large"),
            (2.5, "Moderate"),
            (1.5, "Small"),
            (0.7, "Minimal"),
            (0.3, "Negligible")
        ]
        
        for edge_size, expected in test_cases:
            result = self.generator._classify_edge_magnitude(edge_size)
            self.assertEqual(result, expected)
    
    def test_impact_level_classification(self):
        """Test impact level classification."""
        test_cases = [
            (0.20, "High Impact"),
            (0.08, "Medium Impact"),
            (0.03, "Low Impact"),
            (0.01, "Minimal Impact")
        ]
        
        for value, expected in test_cases:
            result = self.generator._classify_impact_level(value)
            self.assertEqual(result, expected)
    
    def test_confidence_explanation(self):
        """Test confidence level explanation."""
        test_cases = [
            (0.85, "Very high confidence"),
            (0.65, "Good confidence"),
            (0.45, "Moderate confidence"),
            (0.25, "Low confidence")
        ]
        
        for score, expected_phrase in test_cases:
            explanation = self.generator._explain_confidence_level(score)
            self.assertIn(expected_phrase, explanation)
    
    def test_kelly_estimation(self):
        """Test Kelly criterion estimation."""
        test_cases = [
            (0.8, 3.0, "5%+"),   # High confidence, good edge -> large position
            (0.4, 1.5, "3-5%"),  # Moderate confidence, moderate edge -> moderate position 
            (0.3, 1.0, "1-3%"),  # Low confidence, small edge -> actually returns 1-3%
            (0.8, 0.3, "0%"),    # High confidence, no edge
        ]
        
        for confidence, edge, expected in test_cases:
            estimate = self.generator._estimate_kelly_percentage(confidence, edge)
            self.assertIn(expected, estimate)
    
    def test_volatility_assessment(self):
        """Test volatility assessment."""
        # High volatility scenario
        volatile_result = dict(self.prediction_result)
        volatile_result['factor_breakdown'] = {
            'DesperationIndex': {'success': True, 'value': 1.5},
            'RevengeGame': {'success': True, 'value': 1.0},
            'StatementOpportunity': {'success': True, 'value': 0.8}
        }
        
        volatility = self.generator._assess_volatility(volatile_result, self.context)
        self.assertIn("High", volatility)
        
        # Low volatility scenario
        stable_result = dict(self.prediction_result)
        stable_result['factor_breakdown'] = {
            'ExperienceDifferential': {'success': True, 'value': 0.5},
            'VenuePerformance': {'success': True, 'value': 0.3}
        }
        
        volatility_low = self.generator._assess_volatility(stable_result, self.context)
        self.assertIn("Low", volatility_low)
    
    def test_low_confidence_scenario(self):
        """Test insights for low confidence scenario."""
        low_conf_assessment = {
            'confidence_score': 0.35,
            'confidence_level': 'Low',
            'components': {
                'data_quality': 0.3,
                'factor_consensus': 0.4,
                'edge_significance': 0.35
            }
        }
        
        # Test with low confidence
        insights = self.generator.generate_prediction_insights(
            self.prediction_result,
            low_conf_assessment,
            self.edge_classification,
            self.context
        )
        
        # Should suggest caution
        strategic = insights['strategic_insights']
        caution_insight = next((i for i in strategic if 'minimal position or pass' in i), None)
        self.assertIsNotNone(caution_insight)
        
        # Risk should be higher
        risk = insights['risk_assessment']
        self.assertIn(risk['risk_level'], ['Medium', 'High', 'Low-Medium'])
    
    def test_no_edge_scenario(self):
        """Test insights for no edge scenario."""
        no_edge_classification = Mock()
        no_edge_classification.edge_type = EdgeType.NO_EDGE
        no_edge_classification.edge_size = 0.2
        no_edge_classification.recommended_action = "Pass"
        
        no_edge_result = dict(self.prediction_result)
        no_edge_result['edge_size'] = 0.2
        
        insights = self.generator.generate_prediction_insights(
            no_edge_result,
            self.confidence_assessment,
            no_edge_classification,
            self.context
        )
        
        # Summary should indicate no edge
        self.assertIn("NO CLEAR EDGE", insights['summary']['headline'])
        
        # Takeaways should mention no edge
        takeaway = next((t for t in insights['key_takeaways'] if 'No significant' in t), None)
        self.assertIsNotNone(takeaway)
    
    def test_missing_data_handling(self):
        """Test handling of missing data."""
        # Minimal prediction result
        minimal_result = {
            'home_team': 'GEORGIA',
            'away_team': 'ALABAMA'
        }
        
        # Minimal confidence
        minimal_confidence = {
            'confidence_score': 0.5,
            'confidence_level': 'Medium'
        }
        
        # Should not crash
        insights = self.generator.generate_prediction_insights(
            minimal_result,
            minimal_confidence,
            self.edge_classification,
            {}
        )
        
        self.assertIsNotNone(insights)
        self.assertIn('summary', insights)
        self.assertIn('ALABAMA @ GEORGIA', insights['summary']['matchup'])
    
    def test_factor_reliability_assessment(self):
        """Test factor reliability assessment."""
        # Test successful factor
        venue_result = {'success': True, 'value': 0.5}
        reliability = self.generator._assess_factor_reliability(
            'VenuePerformance', venue_result, self.context
        )
        self.assertIn("High", reliability)
        
        # Test failed factor
        failed_result = {'success': False, 'value': 0.0}
        reliability = self.generator._assess_factor_reliability(
            'ATSRecentForm', failed_result, self.context
        )
        self.assertIn("Unreliable", reliability)
    
    def test_risk_mitigation_suggestions(self):
        """Test risk mitigation suggestions."""
        risk_factors = [
            "Low prediction confidence",
            "Small edge size",
            "Poor data quality"
        ]
        
        mitigations = self.generator._suggest_risk_mitigation(risk_factors)
        
        self.assertIsInstance(mitigations, list)
        self.assertEqual(len(mitigations), 3)
        
        # Check specific suggestions
        self.assertTrue(any('position size' in m for m in mitigations))
        self.assertTrue(any('alternative markets' in m for m in mitigations))
        self.assertTrue(any('Wait for better data' in m for m in mitigations))
    
    def test_confidence_improvement_suggestions(self):
        """Test confidence improvement suggestions."""
        low_components = {
            'data_quality': 0.3,
            'factor_consensus': 0.35,
            'edge_significance': 0.25
        }
        
        suggestions = self.generator._suggest_confidence_improvements(low_components)
        
        self.assertIsInstance(suggestions, list)
        self.assertGreater(len(suggestions), 0)
        
        # Should suggest improvements for low scores
        self.assertTrue(any('data quality' in s for s in suggestions))
        self.assertTrue(any('Factors disagree' in s for s in suggestions))
        self.assertTrue(any('Edge size is small' in s for s in suggestions))
    
    def test_edge_templates_coverage(self):
        """Test all edge types have templates."""
        for edge_type in EdgeType:
            self.assertIn(edge_type, self.generator.edge_templates)
            
            template = self.generator.edge_templates[edge_type]
            self.assertIn('headline', template)
            self.assertIn('description', template)
            self.assertIn('action_level', template)
    
    def test_global_generator_instance(self):
        """Test global generator instance."""
        from output.insights_generator import insights_generator
        
        self.assertIsInstance(insights_generator, InsightsGenerator)
        self.assertIsNotNone(insights_generator.edge_templates)
        self.assertIsNotNone(insights_generator.factor_descriptions)


if __name__ == '__main__':
    unittest.main()