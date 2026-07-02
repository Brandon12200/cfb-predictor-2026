"""
Core prediction engine for College Football Market Edge Platform.
Orchestrates factor calculations and generates contrarian predictions.
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

from config import config
from data.data_manager import data_manager
from factors.factor_registry import factor_registry
from utils.normalizer import normalizer
from engine.variance_detector import variance_detector


class PredictionEngine:
    """
    Core prediction engine that orchestrates the contrarian prediction process.
    
    The engine follows this flow:
    1. Fetch Vegas consensus spread
    2. Calculate all factor adjustments
    3. Apply adjustments to create contrarian prediction
    4. Assess edge size and confidence
    5. Generate insights and recommendations
    """
    
    def __init__(self):
        """Initialize prediction engine."""
        self.data_manager = data_manager
        self.factor_registry = factor_registry
        self.normalizer = normalizer
        
        # Performance tracking
        self.prediction_stats = {
            'total_predictions': 0,
            'successful_predictions': 0,
            'failed_predictions': 0,
            'avg_execution_time': 0.0
        }
        
        # Logging
        self.logger = logging.getLogger(__name__)
        
        self.logger.info("Prediction engine initialized")
    
    def generate_prediction(self, home_team: str, away_team: str, 
                          week: Optional[int] = None) -> Dict[str, Any]:
        """
        Generate a contrarian prediction for a given matchup.
        
        Args:
            home_team: Home team name (will be normalized)
            away_team: Away team name (will be normalized)
            week: Week number (optional)
            
        Returns:
            Dictionary with complete prediction results
        """
        start_time = datetime.now()
        
        try:
            # Normalize team names
            home_normalized = self.normalizer.normalize(home_team)
            away_normalized = self.normalizer.normalize(away_team)
            
            if not home_normalized or not away_normalized:
                return self._create_error_result(
                    home_team, away_team, week,
                    "Invalid team names - could not normalize"
                )
            
            if home_normalized == away_normalized:
                return self._create_error_result(
                    home_team, away_team, week,
                    "Home and away teams cannot be the same"
                )
            
            self.logger.info(f"Generating prediction: {away_normalized} @ {home_normalized} (Week {week})")
            
            # Step 1: Fetch comprehensive game context
            context = self.data_manager.get_game_context(home_normalized, away_normalized, week)
            
            # Step 2: Get Vegas consensus spread
            vegas_spread = context.get('vegas_spread')
            
            # CRITICAL: Cannot generate contrarian prediction without betting line
            if vegas_spread is None:
                self.logger.warning(f"No betting line available for {away_normalized} @ {home_normalized}")
                return self._create_error_result(
                    home_normalized, away_normalized, week,
                    "No betting line available - cannot calculate contrarian prediction"
                )
            
            # Step 3: Calculate all factor adjustments
            factor_results = self.factor_registry.calculate_all_factors(
                home_normalized, away_normalized, context
            )
            
            # Step 4: Generate contrarian prediction
            prediction_result = self._calculate_contrarian_prediction(
                vegas_spread, factor_results, context
            )
            
            # Step 4.5: Analyze factor variance for disagreement detection
            variance_analysis = variance_detector.analyze_factor_variance(factor_results)
            
            # Step 5: Build comprehensive result
            result = self._build_prediction_result(
                home_normalized, away_normalized, week,
                vegas_spread, factor_results, prediction_result, context, variance_analysis
            )
            
            # Track successful prediction
            self.prediction_stats['successful_predictions'] += 1
            execution_time = (datetime.now() - start_time).total_seconds()
            self._update_execution_stats(execution_time)
            
            self.logger.info(f"Prediction completed successfully in {execution_time:.2f}s")
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error generating prediction: {e}")
            self.prediction_stats['failed_predictions'] += 1
            
            return self._create_error_result(
                home_team, away_team, week,
                f"Prediction failed: {str(e)}"
            )
        
        finally:
            self.prediction_stats['total_predictions'] += 1
    
    def _calculate_contrarian_prediction(self, vegas_spread: Optional[float], 
                                       factor_results: Dict[str, Any], 
                                       context: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate the contrarian prediction using factor adjustments."""
        # Get both additive and multiplicative adjustments
        total_adjustment = factor_results['summary']['total_adjustment']
        multiplicative_adjustment = factor_results['summary'].get('multiplicative_adjustment', 1.0)
        
        # If no Vegas spread available, can't make a contrarian prediction
        if vegas_spread is None:
            return {
                'contrarian_spread': None,
                'edge_size': None,
                'edge_direction': None,
                'has_edge': False,
                'prediction_type': 'NO_BETTING_DATA',
                'explanation': 'No betting line available for contrarian analysis'
            }
        
        # Apply factor adjustments to Vegas spread
        # First apply additive, then multiplicative
        contrarian_spread = (vegas_spread + total_adjustment) * multiplicative_adjustment
        
        # Calculate edge size (difference between Vegas and our prediction)
        edge_size = abs(contrarian_spread - vegas_spread)
        
        # Determine edge direction
        adjustment_diff = contrarian_spread - vegas_spread
        if adjustment_diff > 0:
            edge_direction = 'home'  # Our prediction favors home team more than Vegas
        elif adjustment_diff < 0:
            edge_direction = 'away'  # Our prediction favors away team more than Vegas
        else:
            edge_direction = 'neutral'
        
        # Adjust thresholds based on confidence and primary signals
        avg_confidence = factor_results['summary'].get('avg_confidence', 0.5)
        primary_signals = factor_results['summary'].get('primary_signals', 0)
        
        # Dynamic edge threshold based on confidence
        if primary_signals >= 2 and avg_confidence >= 0.7:
            min_edge_threshold = 0.75  # Lower threshold for high-confidence primary signals
        elif primary_signals >= 1 or avg_confidence >= 0.6:
            min_edge_threshold = 1.0  # Standard threshold
        else:
            min_edge_threshold = 1.5  # Higher threshold for low-confidence signals
        
        has_edge = edge_size >= min_edge_threshold
        
        # Classify prediction type with confidence-based adjustments
        if primary_signals >= 2 and edge_size >= 2.5:
            prediction_type = 'VERY_STRONG_CONTRARIAN'
        elif edge_size >= 3.0 or (edge_size >= 2.0 and avg_confidence >= 0.7):
            prediction_type = 'STRONG_CONTRARIAN'
        elif edge_size >= 1.5 or (edge_size >= 1.0 and avg_confidence >= 0.6):
            prediction_type = 'MODERATE_CONTRARIAN'
        elif edge_size >= 0.5:
            prediction_type = 'SLIGHT_CONTRARIAN'
        else:
            prediction_type = 'CONSENSUS_ALIGNMENT'
        
        return {
            'contrarian_spread': contrarian_spread,
            'edge_size': edge_size,
            'adjustment_diff': adjustment_diff,
            'multiplicative_effect': multiplicative_adjustment,
            'edge_direction': edge_direction,
            'has_edge': has_edge,
            'prediction_type': prediction_type,
            'total_adjustment': total_adjustment,
            'min_edge_threshold': min_edge_threshold
        }
    
    def _build_prediction_result(self, home_team: str, away_team: str, week: Optional[int],
                               vegas_spread: Optional[float], factor_results: Dict[str, Any],
                               prediction_result: Dict[str, Any], context: Dict[str, Any],
                               variance_analysis: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Build comprehensive prediction result."""
        
        return {
            # Basic game info
            'home_team': home_team,
            'away_team': away_team,
            'week': week,
            'timestamp': datetime.now().isoformat(),
            
            # Market data
            'vegas_spread': vegas_spread,
            'contrarian_spread': prediction_result.get('contrarian_spread'),
            
            # Edge analysis
            'edge_size': prediction_result.get('edge_size'),
            'edge_direction': prediction_result.get('edge_direction'),
            'has_edge': prediction_result.get('has_edge', False),
            'prediction_type': prediction_result.get('prediction_type', 'UNKNOWN'),
            
            # Factor analysis
            'total_adjustment': prediction_result.get('total_adjustment', 0.0),
            'factor_breakdown': factor_results.get('factors', {}),
            'category_adjustments': factor_results.get('summary', {}).get('category_adjustments', {}),
            
            # Data quality
            'data_quality': context.get('data_quality', 0.0),
            'data_sources': context.get('data_sources', []),
            'factors_calculated': factor_results.get('summary', {}).get('factors_calculated', 0),
            'factors_successful': factor_results.get('summary', {}).get('factors_successful', 0),
            
            # Variance Analysis
            'variance_analysis': variance_analysis,
            
            # Recommendation (now incorporates variance)
            'recommendation': self._generate_recommendation(prediction_result, factor_results, variance_analysis),
            'confidence_score': self._calculate_confidence_score(prediction_result, factor_results, context, variance_analysis),
            
            # Context data
            'context': {
                'home_team_data': context.get('home_team_data', {}),
                'away_team_data': context.get('away_team_data', {}),
                'coaching_comparison': context.get('coaching_comparison', {})
            }
        }
    
    def _generate_recommendation(self, prediction_result: Dict[str, Any], 
                               factor_results: Dict[str, Any],
                               variance_analysis: Optional[Dict[str, Any]] = None) -> str:
        """Generate betting recommendation based on prediction results."""
        prediction_type = prediction_result.get('prediction_type', 'UNKNOWN')
        edge_direction = prediction_result.get('edge_direction', 'neutral')
        edge_size = prediction_result.get('edge_size', 0.0)
        
        if prediction_type == 'NO_BETTING_DATA':
            return "Cannot provide recommendation - no betting line available"
        
        if prediction_type == 'CONSENSUS_ALIGNMENT':
            return "No contrarian opportunity identified - align with market consensus"
        
        # Generate contrarian recommendation
        if edge_direction == 'home':
            favored_team = factor_results.get('home_team', 'Home team')
            recommendation = f"CONTRARIAN OPPORTUNITY: Consider {favored_team}"
        elif edge_direction == 'away':
            favored_team = factor_results.get('away_team', 'Away team')
            recommendation = f"CONTRARIAN OPPORTUNITY: Consider {favored_team}"
        else:
            recommendation = "Neutral prediction - no clear contrarian edge"
        
        # Add edge size context
        if edge_size >= 3.0:
            recommendation += f" (Strong {edge_size:.1f} point edge)"
        elif edge_size >= 1.5:
            recommendation += f" (Moderate {edge_size:.1f} point edge)"
        else:
            recommendation += f" (Slight {edge_size:.1f} point edge)"
        
        # Add variance analysis warnings/confirmations
        if variance_analysis:
            variance_level = variance_analysis.get('variance_level', '')
            var_recommendation = variance_analysis.get('recommendation', {})
            var_action = var_recommendation.get('action', '')
            
            if variance_level == 'extreme':
                recommendation += " ⚠️ EXTREME FACTOR DISAGREEMENT - AVOID"
            elif variance_level == 'strong':
                recommendation += " ⚠️ High uncertainty - reduce bet size"
            elif variance_level == 'moderate':
                recommendation += " ⚠️ Some factor disagreement - proceed cautiously"
            elif variance_level == 'consensus':
                recommendation += " ✓ Factors align - high confidence"
            
            # Override recommendation if variance suggests avoiding
            if var_action in ['AVOID_OR_MINIMUM', 'REDUCE_EXPOSURE']:
                recommendation = f"VARIANCE WARNING: {recommendation.split('(')[0].strip()}"
                recommendation += f" - Factors disagree ({variance_level} variance)"
        
        return recommendation
    
    def _calculate_confidence_score(self, prediction_result: Dict[str, Any], 
                                  factor_results: Dict[str, Any], 
                                  context: Dict[str, Any],
                                  variance_analysis: Optional[Dict[str, Any]] = None) -> float:
        """Calculate confidence score for the prediction (0.0 to 1.0)."""
        confidence_factors = []
        
        # Data quality factor (0-40% of confidence)
        data_quality = context.get('data_quality', 0.0)
        confidence_factors.append(data_quality * 0.4)
        
        # Factor success rate (0-30% of confidence)
        factor_summary = factor_results.get('summary', {})
        factors_calculated = factor_summary.get('factors_calculated', 1)
        factors_successful = factor_summary.get('factors_successful', 0)
        success_rate = factors_successful / max(factors_calculated, 1)  # Prevent division by zero
        confidence_factors.append(success_rate * 0.3)
        
        # Edge size factor (0-20% of confidence)
        edge_size = prediction_result.get('edge_size', 0.0)
        if edge_size is not None:
            edge_confidence = min(edge_size / 5.0, 1.0)  # Scale edge to 0-1
            confidence_factors.append(edge_confidence * 0.2)
        else:
            confidence_factors.append(0.0)  # No edge data available
        
        # Betting data availability (0-10% of confidence)
        has_betting_data = prediction_result.get('contrarian_spread') is not None
        confidence_factors.append(0.1 if has_betting_data else 0.0)
        
        # Factor variance adjustment (affects confidence by ±0.3)
        variance_adjustment = 0.0
        if variance_analysis:
            variance_level = variance_analysis.get('variance_level', '')
            if variance_level == 'consensus':
                variance_adjustment = 0.25  # High confidence bonus
            elif variance_level == 'mild':
                variance_adjustment = 0.1   # Mild confidence bonus
            elif variance_level == 'moderate':
                variance_adjustment = -0.1  # Mild confidence penalty
            elif variance_level == 'strong':
                variance_adjustment = -0.2  # Strong confidence penalty
            elif variance_level == 'extreme':
                variance_adjustment = -0.3  # Maximum confidence penalty
        
        # Total confidence score
        total_confidence = sum(confidence_factors) + variance_adjustment
        
        # Ensure confidence is between 0.15 and 0.95 (never completely certain/uncertain)
        return max(0.15, min(0.95, total_confidence))
    
    def _create_error_result(self, home_team: str, away_team: str, 
                           week: Optional[int], error_message: str) -> Dict[str, Any]:
        """Create error result structure."""
        return {
            'home_team': home_team,
            'away_team': away_team,
            'week': week,
            'timestamp': datetime.now().isoformat(),
            'error': error_message,
            'prediction_type': 'ERROR',
            'has_edge': False,
            'recommendation': f"Prediction failed: {error_message}",
            'confidence_score': 0.0
        }
    
    def _update_execution_stats(self, execution_time: float) -> None:
        """Update execution time statistics."""
        total_predictions = self.prediction_stats['total_predictions']
        current_avg = self.prediction_stats['avg_execution_time']
        
        # Update running average
        new_avg = (current_avg * total_predictions + execution_time) / (total_predictions + 1)
        self.prediction_stats['avg_execution_time'] = new_avg
    
    def get_prediction_stats(self) -> Dict[str, Any]:
        """Get prediction engine statistics."""
        total = self.prediction_stats['total_predictions']
        
        return {
            'total_predictions': total,
            'successful_predictions': self.prediction_stats['successful_predictions'],
            'failed_predictions': self.prediction_stats['failed_predictions'],
            'success_rate': self.prediction_stats['successful_predictions'] / max(total, 1),
            'failure_rate': self.prediction_stats['failed_predictions'] / max(total, 1),
            'avg_execution_time': self.prediction_stats['avg_execution_time'],
            'factor_registry_stats': self.factor_registry.get_execution_stats()
        }
    
    def validate_prediction_setup(self) -> Dict[str, Any]:
        """Validate that the prediction engine is properly configured."""
        validation_results = {
            'valid': True,
            'warnings': [],
            'errors': [],
            'components': {}
        }
        
        # Check data manager
        try:
            connections = self.data_manager.test_all_connections()
            validation_results['components']['data_manager'] = {
                'status': 'operational',
                'connections': connections
            }
        except Exception as e:
            validation_results['errors'].append(f"Data manager error: {e}")
            validation_results['valid'] = False
        
        # Check factor registry
        try:
            factor_validation = self.factor_registry.validate_factor_configuration()
            validation_results['components']['factor_registry'] = factor_validation
            
            if not factor_validation['valid']:
                validation_results['errors'].extend(factor_validation['errors'])
                validation_results['valid'] = False
                
            validation_results['warnings'].extend(factor_validation['warnings'])
        except Exception as e:
            validation_results['errors'].append(f"Factor registry error: {e}")
            validation_results['valid'] = False
        
        # Check normalizer
        try:
            all_teams = self.normalizer.get_all_teams()
            validation_results['components']['normalizer'] = {
                'status': 'operational',
                'teams_count': len(all_teams)
            }
        except Exception as e:
            validation_results['errors'].append(f"Normalizer error: {e}")
            validation_results['valid'] = False
        
        return validation_results


# Global prediction engine instance
prediction_engine = PredictionEngine()