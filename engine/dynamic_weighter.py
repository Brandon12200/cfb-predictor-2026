"""
Dynamic Factor Weighting System for College Football Market Edge Platform.
Automatically adjusts factor weights based on performance and seasonal patterns.
"""

import logging
import json
from typing import Dict, Any, List, Optional
from pathlib import Path
from datetime import datetime
import statistics


class DynamicWeighter:
    """
    Dynamically adjusts factor weights based on actual performance.
    
    Features:
    - Performance-based weight adjustment
    - Seasonal adaptation (early vs late season)
    - Conference-specific optimizations
    - Prediction type specialization
    - Continuous learning and improvement
    """
    
    def __init__(self):
        """Initialize dynamic weighter."""
        self.logger = logging.getLogger(__name__)
        
        # Paths for weight persistence
        self.weights_file = Path("data/calibration/dynamic_weights.json")
        self.weights_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Load or initialize weights
        self.weight_state = self._load_weight_state()
        
        # Weight adjustment parameters
        self.learning_rate = 0.05  # How fast to adjust weights
        self.min_samples_for_adjustment = 15  # Minimum games before adjusting
        self.stability_threshold = 0.1  # Don't adjust if change < 10%
        
        # Factor categories for specialized weighting
        self.factor_categories = {
            'primary': ['coaching_differential', 'experience_differential', 'situational_context'],
            'secondary': ['momentum_factors', 'desperation_index', 'revenge_game'],
            'market': ['market_efficiency', 'line_movement', 'public_sentiment'],
            'temporal': ['week_factor', 'rest_advantage', 'travel_distance']
        }
        
        self.logger.info("Dynamic Weighter initialized")
    
    def get_optimized_weights(self, context: Dict[str, Any]) -> Dict[str, float]:
        """
        Get optimized factor weights for current context.
        
        Args:
            context: Game and prediction context
            
        Returns:
            Optimized factor weights
        """
        try:
            # Start with base weights
            weights = self._get_base_weights()
            
            # Apply seasonal adjustments
            seasonal_weights = self._apply_seasonal_adjustments(weights, context)
            
            # Apply conference-specific adjustments
            conf_weights = self._apply_conference_adjustments(seasonal_weights, context)
            
            # Apply prediction type adjustments
            type_weights = self._apply_prediction_type_adjustments(conf_weights, context)
            
            # Apply recent performance adjustments
            performance_weights = self._apply_performance_adjustments(type_weights, context)
            
            # Normalize weights to maintain total
            final_weights = self._normalize_weights(performance_weights)
            
            self.logger.debug(f"Optimized weights for context: {final_weights}")
            
            return final_weights
            
        except Exception as e:
            self.logger.error(f"Error getting optimized weights: {e}")
            return self._get_base_weights()
    
    def update_weights_from_results(self, predictions: List[Dict], 
                                   results: List[Dict]) -> Dict[str, Any]:
        """
        Update weights based on prediction results.
        
        Args:
            predictions: List of predictions made
            results: List of actual results
            
        Returns:
            Update summary
        """
        try:
            update_summary = {
                'predictions_processed': 0,
                'weight_changes': {},
                'performance_metrics': {},
                'adjustment_applied': False
            }
            
            # Match predictions with results
            matched_data = self._match_predictions_with_results(predictions, results)
            update_summary['predictions_processed'] = len(matched_data)
            
            if len(matched_data) < self.min_samples_for_adjustment:
                update_summary['message'] = f"Need {self.min_samples_for_adjustment} samples, got {len(matched_data)}"
                return update_summary
            
            # Analyze factor performance
            factor_performance = self._analyze_factor_performance(matched_data)
            update_summary['performance_metrics'] = factor_performance
            
            # Calculate weight adjustments
            weight_adjustments = self._calculate_weight_adjustments(factor_performance)
            update_summary['weight_changes'] = weight_adjustments
            
            # Apply significant adjustments
            if self._should_apply_adjustments(weight_adjustments):
                self._apply_weight_adjustments(weight_adjustments)
                self._save_weight_state()
                update_summary['adjustment_applied'] = True
                self.logger.info("Applied dynamic weight adjustments")
            else:
                update_summary['message'] = "Weight changes below significance threshold"
            
            return update_summary
            
        except Exception as e:
            self.logger.error(f"Error updating weights from results: {e}")
            return {'error': str(e)}
    
    def _load_weight_state(self) -> Dict[str, Any]:
        """Load saved weight state or initialize new one."""
        if self.weights_file.exists():
            try:
                with open(self.weights_file) as f:
                    state = json.load(f)
                    self.logger.info("Loaded existing weight state")
                    return state
            except Exception as e:
                self.logger.error(f"Error loading weight state: {e}")
        
        # Initialize new weight state
        return {
            'version': '2.0',
            'last_updated': datetime.now().isoformat(),
            'base_weights': {
                'coaching_differential': 0.25,
                'experience_differential': 0.20,
                'situational_context': 0.20,
                'momentum_factors': 0.15,
                'desperation_index': 0.10,
                'revenge_game': 0.05,
                'market_efficiency': 0.05
            },
            'seasonal_adjustments': {
                'early_season': {  # Weeks 1-3
                    'coaching_differential': 0.9,  # Less reliable early
                    'momentum_factors': 0.7,      # No prior games
                    'market_efficiency': 1.2      # Markets less efficient
                },
                'mid_season': {  # Weeks 4-11
                    'coaching_differential': 1.0,
                    'momentum_factors': 1.1,
                    'situational_context': 1.0
                },
                'late_season': {  # Weeks 12+
                    'desperation_index': 1.3,    # More important
                    'situational_context': 1.2,  # Playoff implications
                    'coaching_differential': 1.1  # Experience shows
                }
            },
            'conference_adjustments': {
                'SEC': {'coaching_differential': 1.1, 'experience_differential': 1.1},
                'BIG_TEN': {'situational_context': 1.1, 'momentum_factors': 1.0},
                'BIG_12': {'market_efficiency': 0.9, 'desperation_index': 1.1},
                'ACC': {'coaching_differential': 1.0, 'situational_context': 1.0},
                'PAC_12': {'market_efficiency': 0.95, 'momentum_factors': 1.05}
            },
            'prediction_type_weights': {
                'STRONG_CONTRARIAN': {
                    'market_efficiency': 1.3,
                    'coaching_differential': 1.1
                },
                'MODERATE_CONTRARIAN': {
                    'market_efficiency': 1.2,
                    'situational_context': 1.1
                },
                'SLIGHT_CONTRARIAN': {
                    'market_efficiency': 1.1,
                    'momentum_factors': 1.1
                },
                'CONSENSUS_ALIGNMENT': {
                    'coaching_differential': 1.1,
                    'experience_differential': 1.1
                }
            },
            'performance_tracking': {},
            'total_predictions': 0
        }
    
    def _save_weight_state(self):
        """Save weight state to disk."""
        try:
            self.weight_state['last_updated'] = datetime.now().isoformat()
            with open(self.weights_file, 'w') as f:
                json.dump(self.weight_state, f, indent=2)
            self.logger.info("Weight state saved")
        except Exception as e:
            self.logger.error(f"Error saving weight state: {e}")
    
    def _get_base_weights(self) -> Dict[str, float]:
        """Get current base weights."""
        return self.weight_state['base_weights'].copy()
    
    def _apply_seasonal_adjustments(self, weights: Dict[str, float], 
                                   context: Dict[str, Any]) -> Dict[str, float]:
        """Apply seasonal weight adjustments."""
        week = context.get('week', 4)
        
        if week <= 3:
            season_key = 'early_season'
        elif week >= 12:
            season_key = 'late_season'
        else:
            season_key = 'mid_season'
        
        adjustments = self.weight_state['seasonal_adjustments'].get(season_key, {})
        
        adjusted_weights = weights.copy()
        for factor, multiplier in adjustments.items():
            if factor in adjusted_weights:
                adjusted_weights[factor] *= multiplier
        
        return adjusted_weights
    
    def _apply_conference_adjustments(self, weights: Dict[str, float], 
                                     context: Dict[str, Any]) -> Dict[str, float]:
        """Apply conference-specific adjustments."""
        # Determine primary conference
        home_conf = self._extract_conference(context.get('home_team_data', {}))
        away_conf = self._extract_conference(context.get('away_team_data', {}))
        
        # Use home team's conference as primary
        primary_conf = home_conf or away_conf
        
        if not primary_conf:
            return weights
        
        adjustments = self.weight_state['conference_adjustments'].get(primary_conf, {})
        
        adjusted_weights = weights.copy()
        for factor, multiplier in adjustments.items():
            if factor in adjusted_weights:
                adjusted_weights[factor] *= multiplier
        
        return adjusted_weights
    
    def _apply_prediction_type_adjustments(self, weights: Dict[str, float], 
                                          context: Dict[str, Any]) -> Dict[str, float]:
        """Apply prediction type specific adjustments."""
        prediction_type = context.get('prediction_type', 'CONSENSUS_ALIGNMENT')
        
        adjustments = self.weight_state['prediction_type_weights'].get(prediction_type, {})
        
        adjusted_weights = weights.copy()
        for factor, multiplier in adjustments.items():
            if factor in adjusted_weights:
                adjusted_weights[factor] *= multiplier
        
        return adjusted_weights
    
    def _apply_performance_adjustments(self, weights: Dict[str, float], 
                                      context: Dict[str, Any]) -> Dict[str, float]:
        """Apply recent performance-based adjustments."""
        performance_data = self.weight_state.get('performance_tracking', {})
        
        if not performance_data:
            return weights
        
        adjusted_weights = weights.copy()
        
        for factor, weight in weights.items():
            factor_perf = performance_data.get(factor, {})
            
            if factor_perf.get('sample_size', 0) >= 10:
                accuracy = factor_perf.get('accuracy', 0.5)
                predictive_power = factor_perf.get('predictive_power', 0.0)
                
                # Adjust based on accuracy
                if accuracy > 0.6:
                    multiplier = 1 + (accuracy - 0.5) * 0.4  # Up to 1.4x for 90% accuracy
                elif accuracy < 0.4:
                    multiplier = 0.7 + accuracy * 0.6  # Down to 0.7x for 10% accuracy
                else:
                    multiplier = 1.0
                
                # Further adjust based on predictive power
                multiplier *= (1 + predictive_power * 0.2)
                
                adjusted_weights[factor] *= multiplier
        
        return adjusted_weights
    
    def _normalize_weights(self, weights: Dict[str, float]) -> Dict[str, float]:
        """Normalize weights to maintain total weight sum."""
        total_weight = sum(weights.values())
        
        if total_weight <= 0:
            # Fallback to equal weights
            equal_weight = 1.0 / len(weights)
            return {factor: equal_weight for factor in weights}
        
        # Normalize to original sum (typically 1.0)
        normalization_factor = 1.0 / total_weight
        
        return {factor: weight * normalization_factor 
                for factor, weight in weights.items()}
    
    def _match_predictions_with_results(self, predictions: List[Dict], 
                                       results: List[Dict]) -> List[Dict]:
        """Match predictions with their results."""
        matched = []
        
        for pred in predictions:
            for result in results:
                if self._predictions_match(pred, result):
                    matched.append({
                        'prediction': pred,
                        'result': result,
                        'correct': result.get('prediction_correct', False),
                        'factors': pred.get('factor_breakdown', {})
                    })
                    break
        
        return matched
    
    def _predictions_match(self, prediction: Dict, result: Dict) -> bool:
        """Check if prediction and result match."""
        pred_home = prediction.get('home_team', '').upper()
        pred_away = prediction.get('away_team', '').upper()
        result_home = result.get('home_team', '').upper()
        result_away = result.get('away_team', '').upper()
        
        return pred_home == result_home and pred_away == result_away
    
    def _analyze_factor_performance(self, matched_data: List[Dict]) -> Dict[str, Any]:
        """Analyze how each factor performed."""
        factor_stats = {}
        
        for match in matched_data:
            factors = match.get('factors', {})
            correct = match['correct']
            
            for factor_name, factor_value in factors.items():
                if factor_name not in factor_stats:
                    factor_stats[factor_name] = {
                        'correct_predictions': 0,
                        'total_predictions': 0,
                        'correct_factor_sum': 0.0,
                        'incorrect_factor_sum': 0.0,
                        'factor_values': []
                    }
                
                stats = factor_stats[factor_name]
                stats['total_predictions'] += 1
                stats['factor_values'].append(abs(factor_value))
                
                if correct:
                    stats['correct_predictions'] += 1
                    stats['correct_factor_sum'] += abs(factor_value)
                else:
                    stats['incorrect_factor_sum'] += abs(factor_value)
        
        # Calculate performance metrics
        performance_metrics = {}
        
        for factor_name, stats in factor_stats.items():
            total = stats['total_predictions']
            correct = stats['correct_predictions']
            
            accuracy = correct / total if total > 0 else 0.5
            
            # Calculate predictive power (higher absolute values when correct)
            avg_correct_value = stats['correct_factor_sum'] / max(correct, 1)
            avg_incorrect_value = stats['incorrect_factor_sum'] / max(total - correct, 1)
            predictive_power = (avg_correct_value - avg_incorrect_value) / max(avg_correct_value + avg_incorrect_value, 1)
            
            performance_metrics[factor_name] = {
                'accuracy': accuracy,
                'predictive_power': predictive_power,
                'sample_size': total,
                'avg_factor_magnitude': statistics.mean(stats['factor_values']) if stats['factor_values'] else 0
            }
        
        return performance_metrics
    
    def _calculate_weight_adjustments(self, performance_metrics: Dict) -> Dict[str, float]:
        """Calculate weight adjustments based on performance."""
        adjustments = {}
        
        for factor_name, metrics in performance_metrics.items():
            current_weight = self.weight_state['base_weights'].get(factor_name, 0.1)
            
            accuracy = metrics['accuracy']
            predictive_power = metrics['predictive_power']
            sample_size = metrics['sample_size']
            
            # Calculate adjustment based on performance
            if sample_size >= self.min_samples_for_adjustment:
                # Base adjustment on accuracy vs 50%
                accuracy_adjustment = (accuracy - 0.5) * 2  # -1 to 1 range
                
                # Adjust based on predictive power
                power_adjustment = predictive_power * 0.5
                
                # Combine adjustments
                total_adjustment = (accuracy_adjustment + power_adjustment) * self.learning_rate
                
                # Apply to current weight
                new_weight = current_weight * (1 + total_adjustment)
                
                # Ensure reasonable bounds
                new_weight = max(0.01, min(0.5, new_weight))
                
                # Only include if change is significant
                if abs(new_weight - current_weight) > current_weight * self.stability_threshold:
                    adjustments[factor_name] = new_weight
        
        return adjustments
    
    def _should_apply_adjustments(self, adjustments: Dict) -> bool:
        """Determine if adjustments are significant enough to apply."""
        if not adjustments:
            return False
        
        # Apply if we have adjustments for at least 3 factors
        return len(adjustments) >= 3
    
    def _apply_weight_adjustments(self, adjustments: Dict):
        """Apply weight adjustments to the base weights."""
        for factor_name, new_weight in adjustments.items():
            old_weight = self.weight_state['base_weights'].get(factor_name, 0.1)
            self.weight_state['base_weights'][factor_name] = new_weight
            
            self.logger.info(f"Adjusted {factor_name} weight: {old_weight:.3f} -> {new_weight:.3f}")
        
        # Normalize weights
        self.weight_state['base_weights'] = self._normalize_weights(
            self.weight_state['base_weights']
        )
    
    def _extract_conference(self, team_data: Dict) -> Optional[str]:
        """Extract conference from team data."""
        if not team_data:
            return None
        
        conf_info = team_data.get('info', {}).get('conference', {})
        conf_name = conf_info.get('name', '').upper()
        
        # Map to standard conference names
        if 'SEC' in conf_name:
            return 'SEC'
        elif 'BIG TEN' in conf_name or 'BIG 10' in conf_name:
            return 'BIG_TEN'
        elif 'BIG 12' in conf_name:
            return 'BIG_12'
        elif 'ACC' in conf_name:
            return 'ACC'
        elif 'PAC' in conf_name:
            return 'PAC_12'
        else:
            return 'OTHER'
    
    def get_weight_analysis_report(self) -> Dict[str, Any]:
        """Generate comprehensive weight analysis report."""
        return {
            'current_base_weights': self.weight_state['base_weights'],
            'seasonal_adjustments': self.weight_state['seasonal_adjustments'],
            'conference_adjustments': self.weight_state['conference_adjustments'],
            'prediction_type_weights': self.weight_state['prediction_type_weights'],
            'performance_tracking': self.weight_state.get('performance_tracking', {}),
            'total_predictions': self.weight_state.get('total_predictions', 0),
            'last_updated': self.weight_state.get('last_updated')
        }


# Global instance
dynamic_weighter = DynamicWeighter()