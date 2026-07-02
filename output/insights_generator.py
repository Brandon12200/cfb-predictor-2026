"""
Insights generator for College Football Market Edge Platform.
Creates human-readable explanations and actionable insights from predictions.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from engine.edge_detector import EdgeType


class InsightsGenerator:
    """
    Generates human-readable insights and explanations from prediction results.
    
    Features:
    - Factor-by-factor breakdowns
    - Strategic betting insights
    - Risk assessments
    - Confidence explanations
    - Market context analysis
    """
    
    def __init__(self):
        """Initialize insights generator."""
        # Insight templates
        self.edge_templates = {
            EdgeType.STRONG_CONTRARIAN: {
                'headline': "🎯 STRONG CONTRARIAN OPPORTUNITY",
                'description': "Significant edge detected with high confidence",
                'action_level': "Consider strong position"
            },
            EdgeType.MODERATE_CONTRARIAN: {
                'headline': "📈 MODERATE CONTRARIAN EDGE",
                'description': "Good contrarian opportunity with reasonable confidence",
                'action_level': "Consider moderate position"
            },
            EdgeType.SLIGHT_CONTRARIAN: {
                'headline': "📊 SLIGHT CONTRARIAN LEAN",
                'description': "Minor edge detected, proceed with caution",
                'action_level': "Consider small position or pass"
            },
            EdgeType.CONSENSUS_PLAY: {
                'headline': "🤝 CONSENSUS ALIGNMENT",
                'description': "Analysis aligns with market consensus",
                'action_level': "Follow market or pass"
            },
            EdgeType.NO_EDGE: {
                'headline': "⚪ NO CLEAR EDGE",
                'description': "No meaningful contrarian opportunity",
                'action_level': "Pass on this game"
            },
            EdgeType.INSUFFICIENT_DATA: {
                'headline': "❌ INSUFFICIENT DATA",
                'description': "Not enough reliable data for analysis",
                'action_level': "Avoid - data quality too low"
            }
        }
        
        # Factor descriptions
        self.factor_descriptions = {
            'ExperienceDifferential': "Coaching experience and tenure comparison",
            'PressureSituation': "Performance under high-stakes scenarios",
            'VenuePerformance': "Home field advantage and travel factors",
            'HeadToHeadRecord': "Historical coaching matchup results",
            'DesperationIndex': "Bowl/playoff eligibility motivation",
            'RevengeGame': "Revenge narratives and coaching connections",
            'LookaheadSandwich': "Schedule position and distraction factors",
            'StatementOpportunity': "Opportunity to make statement vs expectations",
            'ATSRecentForm': "Recent against-the-spread performance",
            'PointDifferentialTrends': "Scoring margin trends vs season averages",
            'CloseGamePerformance': "Performance in clutch/close game situations"
        }
        
        # Logging
        self.logger = logging.getLogger(__name__)
        
        self.logger.debug("Insights generator initialized")
    
    def generate_prediction_insights(self, prediction_result: Dict[str, Any], 
                                   confidence_assessment: Dict[str, Any],
                                   edge_classification: Any,
                                   context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate comprehensive insights for a prediction.
        
        Args:
            prediction_result: Results from prediction engine
            confidence_assessment: Confidence analysis
            edge_classification: Edge classification object
            context: Game context data
            
        Returns:
            Dictionary with structured insights
        """
        insights = {
            'summary': self._generate_summary_insight(
                prediction_result, confidence_assessment, edge_classification
            ),
            'edge_analysis': self._generate_edge_insights(
                prediction_result, edge_classification
            ),
            'factor_insights': self._generate_factor_insights(
                prediction_result, context
            ),
            'confidence_insights': self._generate_confidence_insights(
                confidence_assessment
            ),
            'strategic_insights': self._generate_strategic_insights(
                prediction_result, confidence_assessment, edge_classification, context
            ),
            'risk_assessment': self._generate_risk_assessment(
                prediction_result, confidence_assessment, context
            ),
            'key_takeaways': self._generate_key_takeaways(
                prediction_result, confidence_assessment, edge_classification
            )
        }
        
        return insights
    
    def _generate_summary_insight(self, prediction_result: Dict[str, Any],
                                confidence_assessment: Dict[str, Any],
                                edge_classification: Any) -> Dict[str, Any]:
        """Generate high-level summary insight."""
        home_team = prediction_result.get('home_team', 'Home')
        away_team = prediction_result.get('away_team', 'Away')
        vegas_spread = prediction_result.get('vegas_spread')
        contrarian_spread = prediction_result.get('contrarian_spread')
        edge_size = prediction_result.get('edge_size', 0.0)
        
        edge_info = self.edge_templates.get(edge_classification.edge_type, {})
        
        summary = {
            'headline': edge_info.get('headline', 'Analysis Complete'),
            'matchup': f"{away_team} @ {home_team}",
            'edge_size': edge_size,
            'confidence_level': confidence_assessment.get('confidence_level', 'Unknown'),
            'recommendation': edge_classification.recommended_action,
            'quick_summary': edge_info.get('description', ''),
            'action_level': edge_info.get('action_level', '')
        }
        
        # Add spread comparison if available
        if vegas_spread is not None and contrarian_spread is not None:
            summary['spread_comparison'] = {
                'vegas_line': f"{home_team} {vegas_spread:+.1f}",
                'contrarian_line': f"{home_team} {contrarian_spread:+.1f}",
                'difference': f"{edge_size:+.1f} points"
            }
        
        return summary
    
    def _generate_edge_insights(self, prediction_result: Dict[str, Any],
                              edge_classification: Any) -> Dict[str, Any]:
        """Generate detailed edge analysis insights."""
        edge_type = edge_classification.edge_type
        edge_size = edge_classification.edge_size
        
        insights = {
            'edge_classification': edge_type.value.replace('_', ' ').title(),
            'edge_magnitude': self._classify_edge_magnitude(edge_size),
            'edge_significance': self._explain_edge_significance(edge_size),
            'historical_context': self._provide_historical_context(edge_size),
            'market_implications': self._explain_market_implications(edge_type, edge_size)
        }
        
        return insights
    
    def _generate_factor_insights(self, prediction_result: Dict[str, Any],
                                context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate insights for each contributing factor."""
        factor_insights = []
        
        factor_breakdown = prediction_result.get('factor_breakdown', {})
        category_adjustments = prediction_result.get('category_adjustments', {})
        
        # Identify most impactful factors
        significant_factors = []
        for factor_name, factor_result in factor_breakdown.items():
            if factor_result.get('success', False):
                weighted_value = abs(factor_result.get('weighted_value', 0.0))
                if weighted_value > 0.02:  # Threshold for significance
                    significant_factors.append((factor_name, factor_result, weighted_value))
        
        # Sort by impact
        significant_factors.sort(key=lambda x: x[2], reverse=True)
        
        # Generate insights for top factors
        for factor_name, factor_result, impact in significant_factors[:5]:
            insight = {
                'factor': factor_name,
                'description': self.factor_descriptions.get(factor_name, factor_name),
                'value': factor_result.get('value', 0.0),
                'weighted_contribution': factor_result.get('weighted_value', 0.0),
                'impact_level': self._classify_impact_level(impact),
                'explanation': factor_result.get('explanation', ''),
                'reliability': self._assess_factor_reliability(factor_name, factor_result, context)
            }
            factor_insights.append(insight)
        
        return factor_insights
    
    def _generate_confidence_insights(self, confidence_assessment: Dict[str, Any]) -> Dict[str, Any]:
        """Generate confidence analysis insights."""
        confidence_score = confidence_assessment.get('confidence_score', 0.0)
        confidence_level = confidence_assessment.get('confidence_level', 'Unknown')
        components = confidence_assessment.get('components', {})
        
        # Find strongest and weakest components
        strongest_component = max(components.items(), key=lambda x: x[1]) if components else ('unknown', 0.5)
        weakest_component = min(components.items(), key=lambda x: x[1]) if components else ('unknown', 0.5)
        
        insights = {
            'overall_confidence': confidence_level,
            'confidence_score': confidence_score,
            'confidence_explanation': self._explain_confidence_level(confidence_score),
            'strongest_factor': {
                'component': strongest_component[0].replace('_', ' ').title(),
                'score': strongest_component[1],
                'explanation': self._explain_confidence_component(strongest_component[0], strongest_component[1])
            },
            'weakest_factor': {
                'component': weakest_component[0].replace('_', ' ').title(),
                'score': weakest_component[1],
                'explanation': self._explain_confidence_component(weakest_component[0], weakest_component[1])
            },
            'improvement_suggestions': self._suggest_confidence_improvements(components)
        }
        
        return insights
    
    def _generate_strategic_insights(self, prediction_result: Dict[str, Any],
                                   confidence_assessment: Dict[str, Any],
                                   edge_classification: Any,
                                   context: Dict[str, Any]) -> List[str]:
        """Generate strategic betting insights."""
        insights = []
        
        edge_type = edge_classification.edge_type
        edge_size = edge_classification.edge_size
        confidence_score = confidence_assessment.get('confidence_score', 0.0)
        
        # Position sizing suggestions
        if edge_type in [EdgeType.STRONG_CONTRARIAN, EdgeType.MODERATE_CONTRARIAN]:
            if confidence_score > 0.7:
                insights.append("High confidence supports standard position sizing")
            elif confidence_score > 0.5:
                insights.append("Moderate confidence suggests reduced position size")
            else:
                insights.append("Low confidence warrants minimal position or pass")
        
        # Timing insights
        week = context.get('week')
        if week:
            if week <= 3:
                insights.append("Early season: Markets less efficient, edges may be more reliable")
            elif week >= 12:
                insights.append("Late season: Stakes higher, emotional factors amplified")
            else:
                insights.append("Mid-season: Most predictable period for factor analysis")
        
        # Data quality insights
        data_quality = context.get('data_quality', 0.0)
        if data_quality < 0.5:
            insights.append("Limited data quality reduces prediction reliability")
        elif data_quality > 0.8:
            insights.append("High data quality supports prediction confidence")
        
        # Market context
        vegas_spread = prediction_result.get('vegas_spread')
        if vegas_spread is not None:
            if abs(vegas_spread) > 14:
                insights.append("Large spread: Consider totals or alternative markets")
            elif abs(vegas_spread) < 3:
                insights.append("Close line: Factor analysis more critical for edge detection")
        
        return insights
    
    def _generate_risk_assessment(self, prediction_result: Dict[str, Any],
                                confidence_assessment: Dict[str, Any],
                                context: Dict[str, Any]) -> Dict[str, Any]:
        """Generate risk assessment insights."""
        confidence_score = confidence_assessment.get('confidence_score', 0.0)
        edge_size = prediction_result.get('edge_size', 0.0)
        data_quality = context.get('data_quality', 0.0)
        
        # Calculate overall risk level
        risk_factors = []
        
        if confidence_score < 0.4:
            risk_factors.append("Low prediction confidence")
        
        if edge_size < 1.0:
            risk_factors.append("Small edge size")
        
        if data_quality < 0.3:
            risk_factors.append("Poor data quality")
        
        # Determine risk level
        if len(risk_factors) >= 3:
            risk_level = "High"
        elif len(risk_factors) >= 2:
            risk_level = "Medium"
        elif len(risk_factors) >= 1:
            risk_level = "Low-Medium"
        else:
            risk_level = "Low"
        
        return {
            'risk_level': risk_level,
            'risk_factors': risk_factors,
            'risk_mitigation': self._suggest_risk_mitigation(risk_factors),
            'kelly_criterion_estimate': self._estimate_kelly_percentage(confidence_score, edge_size),
            'volatility_assessment': self._assess_volatility(prediction_result, context)
        }
    
    def _generate_key_takeaways(self, prediction_result: Dict[str, Any],
                              confidence_assessment: Dict[str, Any],
                              edge_classification: Any) -> List[str]:
        """Generate key takeaways from the analysis."""
        takeaways = []
        
        edge_type = edge_classification.edge_type
        edge_size = edge_classification.edge_size
        confidence_score = confidence_assessment.get('confidence_score', 0.0)
        
        # Primary takeaway based on edge
        if edge_type == EdgeType.STRONG_CONTRARIAN:
            takeaways.append(f"Strong {edge_size:.1f} point contrarian edge identified")
        elif edge_type == EdgeType.MODERATE_CONTRARIAN:
            takeaways.append(f"Moderate {edge_size:.1f} point contrarian opportunity present")
        elif edge_type == EdgeType.SLIGHT_CONTRARIAN:
            takeaways.append(f"Slight {edge_size:.1f} point edge, proceed with caution")
        else:
            takeaways.append("No significant contrarian edge detected")
        
        # Confidence takeaway
        if confidence_score > 0.7:
            takeaways.append("High confidence in prediction methodology")
        elif confidence_score < 0.4:
            takeaways.append("Low confidence due to data limitations")
        
        # Factor-specific takeaway
        factor_breakdown = prediction_result.get('factor_breakdown', {})
        category_adjustments = prediction_result.get('category_adjustments', {})
        
        if category_adjustments:
            dominant_category = max(category_adjustments.items(), key=lambda x: abs(x[1]))
            category_name = dominant_category[0].replace('_', ' ').title()
            takeaways.append(f"Primary edge source: {category_name} factors")
        
        return takeaways
    
    def _classify_edge_magnitude(self, edge_size: float) -> str:
        """Classify the magnitude of an edge."""
        if edge_size >= 5.0:
            return "Extremely Large"
        elif edge_size >= 3.0:
            return "Large"
        elif edge_size >= 2.0:
            return "Moderate"
        elif edge_size >= 1.0:
            return "Small"
        elif edge_size >= 0.5:
            return "Minimal"
        else:
            return "Negligible"
    
    def _explain_edge_significance(self, edge_size: float) -> str:
        """Explain the significance of an edge size."""
        if edge_size >= 3.0:
            return "This represents a significant market inefficiency that warrants attention"
        elif edge_size >= 2.0:
            return "A meaningful edge that could provide value over time"
        elif edge_size >= 1.0:
            return "A modest edge that may offer slight value"
        else:
            return "Minimal edge that may not overcome market friction"
    
    def _provide_historical_context(self, edge_size: float) -> str:
        """Provide historical context for edge size."""
        if edge_size >= 3.0:
            return "Edges of this size are rare and typically occur 5-10% of the time"
        elif edge_size >= 2.0:
            return "Moderate edges like this occur approximately 15-20% of the time"
        elif edge_size >= 1.0:
            return "Small edges are more common, occurring 25-30% of the time"
        else:
            return "Minimal edges occur frequently but may not be actionable"
    
    def _explain_market_implications(self, edge_type: EdgeType, edge_size: float) -> str:
        """Explain market implications of the detected edge."""
        if edge_type == EdgeType.STRONG_CONTRARIAN:
            return "Market may be missing key factors or overreacting to public sentiment"
        elif edge_type == EdgeType.MODERATE_CONTRARIAN:
            return "Possible market inefficiency due to incomplete information incorporation"
        elif edge_type == EdgeType.SLIGHT_CONTRARIAN:
            return "Minor market mispricing, possibly due to recency bias or media narrative"
        else:
            return "Market appears to be efficiently pricing this matchup"
    
    def _classify_impact_level(self, weighted_value: float) -> str:
        """Classify the impact level of a factor."""
        abs_value = abs(weighted_value)
        if abs_value >= 0.15:
            return "High Impact"
        elif abs_value >= 0.05:
            return "Medium Impact"
        elif abs_value >= 0.02:
            return "Low Impact"
        else:
            return "Minimal Impact"
    
    def _assess_factor_reliability(self, factor_name: str, factor_result: Dict, context: Dict) -> str:
        """Assess the reliability of a factor calculation."""
        success = factor_result.get('success', False)
        
        if not success:
            return "Unreliable - Calculation failed"
        
        # Factor-specific reliability assessment
        reliability_map = {
            'VenuePerformance': "High - Home field advantage is well-established",
            'ExperienceDifferential': "Medium - Experience data may be incomplete",
            'DesperationIndex': "Medium - Motivation factors can be unpredictable",
            'ATSRecentForm': "Low - Limited historical data available",
            'RevengeGame': "Low - Narrative factors are subjective"
        }
        
        return reliability_map.get(factor_name, "Medium - Standard factor reliability")
    
    def _explain_confidence_level(self, confidence_score: float) -> str:
        """Explain what a confidence level means."""
        if confidence_score > 0.8:
            return "Very high confidence with strong data support and factor agreement"
        elif confidence_score > 0.6:
            return "Good confidence with adequate data and reasonable factor consensus"
        elif confidence_score > 0.4:
            return "Moderate confidence with some data limitations or factor disagreement"
        else:
            return "Low confidence due to poor data quality or significant uncertainty"
    
    def _explain_confidence_component(self, component: str, score: float) -> str:
        """Explain what a confidence component score means."""
        explanations = {
            'data_quality': "Quality and completeness of underlying data",
            'factor_consensus': "Agreement between different analytical factors",
            'edge_significance': "Size and statistical significance of detected edge",
            'market_context': "Market efficiency and timing considerations",
            'historical_performance': "Track record of similar predictions",
            'situational_factors': "Special circumstances affecting prediction"
        }
        
        base_explanation = explanations.get(component, component.replace('_', ' '))
        
        if score > 0.7:
            return f"{base_explanation} - Strong"
        elif score > 0.5:
            return f"{base_explanation} - Adequate"
        elif score > 0.3:
            return f"{base_explanation} - Weak"
        else:
            return f"{base_explanation} - Poor"
    
    def _suggest_confidence_improvements(self, components: Dict[str, float]) -> List[str]:
        """Suggest ways to improve prediction confidence."""
        suggestions = []
        
        for component, score in components.items():
            if score < 0.4:
                if component == 'data_quality':
                    suggestions.append("Improve data quality by waiting for more complete information")
                elif component == 'factor_consensus':
                    suggestions.append("Factors disagree - consider additional analysis or pass")
                elif component == 'edge_significance':
                    suggestions.append("Edge size is small - consider larger edges for better confidence")
        
        if not suggestions:
            suggestions.append("Confidence is adequate for current analysis")
        
        return suggestions
    
    def _suggest_risk_mitigation(self, risk_factors: List[str]) -> List[str]:
        """Suggest risk mitigation strategies."""
        mitigations = []
        
        for risk_factor in risk_factors:
            if "confidence" in risk_factor.lower():
                mitigations.append("Reduce position size due to confidence concerns")
            elif "edge" in risk_factor.lower():
                mitigations.append("Consider alternative markets or pass entirely")
            elif "data" in risk_factor.lower():
                mitigations.append("Wait for better data or seek additional sources")
        
        return mitigations
    
    def _estimate_kelly_percentage(self, confidence_score: float, edge_size: float) -> str:
        """Provide rough Kelly criterion estimate."""
        if edge_size < 0.5:
            return "0% - No meaningful edge"
        
        # Simplified Kelly approximation
        estimated_edge_percentage = min(edge_size / 20.0, 0.15)  # Max 15%
        confidence_adjusted = estimated_edge_percentage * confidence_score
        
        if confidence_adjusted < 0.01:
            return "0-1% - Minimal edge"
        elif confidence_adjusted < 0.03:
            return "1-3% - Small position"
        elif confidence_adjusted < 0.05:
            return "3-5% - Moderate position"
        else:
            return "5%+ - Large position (with caution)"
    
    def _assess_volatility(self, prediction_result: Dict[str, Any], context: Dict[str, Any]) -> str:
        """Assess the volatility/variance of the prediction."""
        factor_breakdown = prediction_result.get('factor_breakdown', {})
        
        # Look for factors that increase volatility
        volatile_factors = ['DesperationIndex', 'RevengeGame', 'StatementOpportunity']
        volatility_contributors = []
        
        for factor_name, factor_result in factor_breakdown.items():
            if factor_name in volatile_factors and factor_result.get('success', False):
                value = abs(factor_result.get('value', 0.0))
                if value > 0.5:
                    volatility_contributors.append(factor_name)
        
        if len(volatility_contributors) >= 2:
            return "High - Multiple emotional/situational factors present"
        elif len(volatility_contributors) == 1:
            return "Medium - Some situational volatility expected"
        else:
            return "Low - Primarily analytical factors involved"


# Global insights generator instance
insights_generator = InsightsGenerator()