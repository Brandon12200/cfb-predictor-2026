"""
Confidence calculator for College Football Market Edge Platform.
Assesses the confidence level of predictions based on multiple factors.
"""

import logging
from typing import Dict, Any, List, Optional
import statistics
from datetime import datetime

from config import config


class ConfidenceCalculator:
    """
    Calculates confidence scores for predictions based on multiple dimensions.
    
    Confidence is assessed across several dimensions:
    1. Data quality and completeness
    2. Factor consensus and agreement
    3. Historical accuracy of similar predictions
    4. Edge size and significance
    5. Market efficiency indicators
    """
    
    def __init__(self):
        """Initialize confidence calculator."""
        # Confidence weights for different components
        self.confidence_weights = {
            'data_quality': 0.25,       # How complete and reliable is the data
            'factor_consensus': 0.20,   # How much do factors agree
            'edge_significance': 0.20,  # How significant is the edge
            'market_context': 0.15,     # Market conditions and efficiency
            'historical_performance': 0.10,  # Track record of similar predictions
            'situational_factors': 0.10     # Special circumstances
        }
        
        # Confidence thresholds
        self.confidence_levels = {
            'very_high': 0.85,
            'high': 0.70,
            'medium': 0.55,
            'low': 0.40,
            'very_low': 0.25
        }
        
        # Logging
        self.logger = logging.getLogger(__name__)
        
        self.logger.debug("Confidence calculator initialized")
    
    def calculate_confidence(self, prediction_result: Dict[str, Any], 
                           factor_results: Dict[str, Any],
                           context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate comprehensive confidence assessment for a prediction.
        
        Args:
            prediction_result: Results from prediction engine
            factor_results: Results from factor calculations
            context: Game context and data
            
        Returns:
            Dictionary with confidence score and breakdown
        """
        confidence_components = {}
        
        # 1. Data quality assessment
        confidence_components['data_quality'] = self._assess_data_quality(context, factor_results)
        
        # 2. Factor consensus assessment
        confidence_components['factor_consensus'] = self._assess_factor_consensus(factor_results)
        
        # 3. Edge significance assessment
        confidence_components['edge_significance'] = self._assess_edge_significance(prediction_result)
        
        # 4. Market context assessment
        confidence_components['market_context'] = self._assess_market_context(prediction_result, context)
        
        # 5. Historical performance assessment (placeholder)
        confidence_components['historical_performance'] = self._assess_historical_performance(prediction_result)
        
        # 6. Situational factors assessment
        confidence_components['situational_factors'] = self._assess_situational_factors(context, factor_results)
        
        # Calculate weighted confidence score
        total_confidence = sum(
            score * self.confidence_weights[component]
            for component, score in confidence_components.items()
        )
        
        # Apply early season volatility dampener (Weeks 1-3)
        week = context.get('week', 4)
        if week <= 3:
            # Reduce confidence by 10-15% for early season games
            early_season_multiplier = 0.85 if week == 1 else (0.87 if week == 2 else 0.90)
            total_confidence *= early_season_multiplier
            self.logger.debug(f"Applied early season dampener for Week {week}: {early_season_multiplier}")
        
        # Ensure confidence is within reasonable bounds (15% to 85% max for better calibration)
        final_confidence = max(0.15, min(0.85, total_confidence))
        
        # Determine confidence level
        confidence_level = self._determine_confidence_level(final_confidence)
        
        return {
            'confidence_score': final_confidence,
            'confidence_level': confidence_level,
            'confidence_percentage': f"{final_confidence:.1%}",
            'components': confidence_components,
            'weights': self.confidence_weights,
            'explanation': self._generate_confidence_explanation(final_confidence, confidence_components)
        }
    
    def _assess_data_quality(self, context: Dict[str, Any], factor_results: Dict[str, Any]) -> float:
        """Assess data quality and completeness."""
        quality_score = 0.0
        
        # Base data quality from context
        base_quality = context.get('data_quality', 0.0)
        quality_score += base_quality * 0.4
        
        # Factor success rate
        factor_summary = factor_results.get('summary', {})
        factors_calculated = factor_summary.get('factors_calculated', 1)
        factors_successful = factor_summary.get('factors_successful', 0)
        success_rate = factors_successful / factors_calculated
        quality_score += success_rate * 0.3
        
        # Data source diversity
        data_sources = context.get('data_sources', [])
        source_diversity = min(len(data_sources) / 3, 1.0)  # Normalize to 3 sources
        quality_score += source_diversity * 0.2
        
        # Betting data availability
        has_betting_data = context.get('vegas_spread') is not None
        quality_score += 0.1 if has_betting_data else 0.0
        
        return min(quality_score, 1.0)
    
    def _assess_factor_consensus(self, factor_results: Dict[str, Any]) -> float:
        """Assess how much the factors agree with each other."""
        factors = factor_results.get('factors', {})
        if not factors:
            return 0.5  # Neutral if no factors
        
        # Get factor values and weights
        factor_values = []
        factor_weights = []
        
        for factor_name, factor_result in factors.items():
            if factor_result.get('success', False):
                value = factor_result.get('value', 0.0)
                weight = factor_result.get('weight', 0.0)
                factor_values.append(value)
                factor_weights.append(weight)
        
        if len(factor_values) < 2:
            return 0.5  # Need at least 2 factors for consensus
        
        # Calculate consensus metrics
        consensus_score = 0.0
        
        # 1. Direction agreement (how many factors agree on direction)
        positive_factors = sum(1 for v in factor_values if v > 0.1)
        negative_factors = sum(1 for v in factor_values if v < -0.1)
        neutral_factors = len(factor_values) - positive_factors - negative_factors
        
        # Consensus is higher when factors agree on direction
        max_direction = max(positive_factors, negative_factors, neutral_factors)
        direction_consensus = max_direction / len(factor_values)
        consensus_score += direction_consensus * 0.5
        
        # 2. Magnitude consistency (low standard deviation = high consensus)
        if len(factor_values) > 1:
            std_dev = statistics.stdev(factor_values)
            # Lower std dev = higher consensus (invert and normalize)
            magnitude_consensus = max(0, 1 - (std_dev / 2.0))  # Assume std dev > 2 is low consensus
            consensus_score += magnitude_consensus * 0.3
        
        # 3. Weight-adjusted agreement
        if factor_weights and sum(factor_weights) > 0:
            weighted_avg = sum(v * w for v, w in zip(factor_values, factor_weights)) / sum(factor_weights)
            weight_consensus = 1 - abs(weighted_avg) / max(abs(max(factor_values)), abs(min(factor_values)), 1.0)
            consensus_score += weight_consensus * 0.2
        else:
            consensus_score += 0.1  # Neutral if no weights
        
        return min(consensus_score, 1.0)
    
    def _assess_edge_significance(self, prediction_result: Dict[str, Any]) -> float:
        """Assess the significance of the identified edge with recalibrated scoring."""
        edge_size = prediction_result.get('edge_size', 0.0)
        prediction_type = prediction_result.get('prediction_type', 'CONSENSUS_ALIGNMENT')
        
        # Handle None edge size
        if edge_size is None:
            edge_size = 0.0
        
        # Recalibrated edge significance based on Week 1 performance
        # More conservative scoring to avoid overconfidence
        if edge_size >= 6.0:
            base_significance = 0.9  # Massive edge (rare)
        elif edge_size >= 4.0:
            base_significance = 0.75  # Strong edge
        elif edge_size >= 2.5:
            base_significance = 0.65  # Solid edge
        elif edge_size >= 1.5:
            base_significance = 0.55  # Moderate edge
        elif edge_size >= 1.0:
            base_significance = 0.45  # Slight edge
        elif edge_size >= 0.5:
            base_significance = 0.35  # Minimal edge
        else:
            base_significance = 0.25  # No meaningful edge
        
        # Adjust based on prediction type (reduced multipliers)
        type_adjustments = {
            'STRONG_CONTRARIAN': 0.9,
            'MODERATE_CONTRARIAN': 0.75,
            'SLIGHT_CONTRARIAN': 0.6,
            'CONSENSUS_ALIGNMENT': 0.5,  # Increased from 0.3
            'NO_BETTING_DATA': 0.3,
            'ERROR': 0.0
        }
        
        type_multiplier = type_adjustments.get(prediction_type, 0.5)
        
        return base_significance * type_multiplier
    
    def _assess_market_context(self, prediction_result: Dict[str, Any], context: Dict[str, Any]) -> float:
        """Assess market context and efficiency indicators."""
        market_score = 0.5  # Start with neutral
        
        # Betting line availability suggests efficient market
        has_betting_data = context.get('vegas_spread') is not None
        if has_betting_data:
            market_score += 0.2
        else:
            market_score -= 0.1  # Less efficient market without betting lines
        
        # Game timing (earlier in season = less efficient markets)
        week = context.get('week')
        if week:
            if week <= 3:
                market_score += 0.1  # Early season inefficiencies
            elif week >= 12:
                market_score -= 0.1  # Late season markets more efficient
        
        # Conference and team visibility (placeholder)
        # Major conference games have more efficient markets
        home_team_data = context.get('home_team_data', {})
        away_team_data = context.get('away_team_data', {})
        
        # Estimate market efficiency based on team info
        if self._is_major_conference_game(home_team_data, away_team_data):
            market_score -= 0.1  # More efficient market
        else:
            market_score += 0.1  # Potentially less efficient
        
        return max(0.0, min(1.0, market_score))
    
    def _assess_historical_performance(self, prediction_result: Dict[str, Any]) -> float:
        """Assess historical performance of similar predictions (placeholder)."""
        # This would track accuracy of previous predictions with similar characteristics
        # For now, return neutral score
        return 0.5
    
    def _assess_situational_factors(self, context: Dict[str, Any], factor_results: Dict[str, Any]) -> float:
        """Assess special situational factors that affect confidence."""
        situation_score = 0.5  # Start neutral
        
        # Check for high-variance situational factors
        factors = factor_results.get('factors', {})
        
        # Desperation and revenge factors can be less predictable
        desperation_factor = factors.get('DesperationIndex', {})
        if desperation_factor.get('success') and abs(desperation_factor.get('value', 0)) > 1.0:
            situation_score -= 0.1  # High desperation = higher variance
        
        revenge_factor = factors.get('RevengeGame', {})
        if revenge_factor.get('success') and abs(revenge_factor.get('value', 0)) > 0.5:
            situation_score -= 0.05  # Revenge narratives can be unpredictable
        
        # Coaching experience provides stability
        experience_factor = factors.get('ExperienceDifferential', {})
        if experience_factor.get('success') and abs(experience_factor.get('value', 0)) > 0.5:
            situation_score += 0.1  # Coaching experience is more predictable
        
        # Week timing
        week = context.get('week')
        if week:
            if 4 <= week <= 11:  # Mid-season is most predictable
                situation_score += 0.1
            elif week <= 2 or week >= 14:  # Early season and championship time less predictable
                situation_score -= 0.1
        
        return max(0.0, min(1.0, situation_score))
    
    def _is_major_conference_game(self, home_team_data: Dict, away_team_data: Dict) -> bool:
        """Check if this is a major conference game (more efficient markets)."""
        major_conferences = {'SEC', 'BIG TEN', 'BIG 12', 'ACC', 'PAC-12'}
        
        home_conf = home_team_data.get('info', {}).get('conference', {}).get('name', '')
        away_conf = away_team_data.get('info', {}).get('conference', {}).get('name', '')
        
        return any(conf in home_conf.upper() for conf in major_conferences) or \
               any(conf in away_conf.upper() for conf in major_conferences)
    
    def _determine_confidence_level(self, confidence_score: float) -> str:
        """Determine confidence level based on score."""
        if confidence_score >= self.confidence_levels['very_high']:
            return 'Very High'
        elif confidence_score >= self.confidence_levels['high']:
            return 'High'
        elif confidence_score >= self.confidence_levels['medium']:
            return 'Medium'
        elif confidence_score >= self.confidence_levels['low']:
            return 'Low'
        else:
            return 'Very Low'
    
    def _generate_confidence_explanation(self, confidence_score: float, 
                                       components: Dict[str, float]) -> str:
        """Generate human-readable explanation of confidence assessment."""
        level = self._determine_confidence_level(confidence_score)
        
        # Find strongest and weakest components
        strongest_component = max(components.items(), key=lambda x: x[1])
        weakest_component = min(components.items(), key=lambda x: x[1])
        
        explanation = f"{level} confidence ({confidence_score:.1%}). "
        explanation += f"Strongest factor: {strongest_component[0].replace('_', ' ')} ({strongest_component[1]:.1%}). "
        explanation += f"Weakest factor: {weakest_component[0].replace('_', ' ')} ({weakest_component[1]:.1%})."
        
        return explanation


# Global confidence calculator instance
confidence_calculator = ConfidenceCalculator()