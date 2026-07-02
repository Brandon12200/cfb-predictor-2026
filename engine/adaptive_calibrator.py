"""
Adaptive Confidence Calibration System for College Football Market Edge Platform.
Self-adjusts confidence scoring based on historical accuracy.
"""

import logging
import json
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
from datetime import datetime
import statistics


class AdaptiveCalibrator:
    """
    Dynamically calibrates confidence scores based on actual performance.
    
    Features:
    - Tracks prediction accuracy by confidence level
    - Adjusts confidence scaling based on results
    - Identifies most predictive factors
    - Self-corrects overconfidence/underconfidence
    - Provides calibration metrics and diagnostics
    """
    
    def __init__(self):
        """Initialize adaptive calibrator."""
        self.logger = logging.getLogger(__name__)
        
        # Paths for data persistence
        self.calibration_file = Path("data/calibration/calibration_state.json")
        self.calibration_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Load or initialize calibration state
        self.calibration_state = self._load_calibration_state()
        
        # Calibration parameters
        self.min_samples_for_adjustment = 10
        self.target_calibration_ratio = 1.0  # Perfect calibration
        self.adjustment_rate = 0.1  # How aggressively to adjust
        
        self.logger.info("Adaptive Calibrator initialized")
    
    def calibrate_confidence(self, raw_confidence: float, 
                            prediction_type: str,
                            edge_size: float,
                            week: int) -> Dict[str, Any]:
        """
        Apply adaptive calibration to raw confidence score.
        
        Args:
            raw_confidence: Original confidence score (0-1)
            prediction_type: Type of prediction being made
            edge_size: Size of the betting edge
            week: Current week number
            
        Returns:
            Calibrated confidence with metadata
        """
        try:
            # Get calibration factors
            calibration_factors = self._get_calibration_factors(
                prediction_type, edge_size, week
            )
            
            # Apply calibration adjustments
            calibrated_confidence = self._apply_calibration(
                raw_confidence, calibration_factors
            )
            
            # Ensure bounds
            calibrated_confidence = max(0.15, min(0.85, calibrated_confidence))
            
            return {
                'raw_confidence': raw_confidence,
                'calibrated_confidence': calibrated_confidence,
                'adjustment_factor': calibration_factors['total_adjustment'],
                'calibration_metrics': {
                    'historical_accuracy': calibration_factors.get('historical_accuracy'),
                    'sample_size': calibration_factors.get('sample_size'),
                    'calibration_quality': self._assess_calibration_quality()
                },
                'explanation': self._generate_calibration_explanation(
                    raw_confidence, calibrated_confidence, calibration_factors
                )
            }
            
        except Exception as e:
            self.logger.error(f"Calibration error: {e}")
            return {
                'raw_confidence': raw_confidence,
                'calibrated_confidence': raw_confidence,
                'adjustment_factor': 1.0,
                'error': str(e)
            }
    
    def update_calibration(self, predictions: List[Dict], 
                          actual_results: List[Dict]) -> Dict[str, Any]:
        """
        Update calibration based on actual results.
        
        Args:
            predictions: List of predictions made
            actual_results: List of actual game results
            
        Returns:
            Calibration update summary
        """
        try:
            update_summary = {
                'predictions_processed': 0,
                'calibration_adjustments': {},
                'factor_performance': {},
                'new_calibration_state': {}
            }
            
            # Match predictions with results
            matched_results = self._match_predictions_to_results(
                predictions, actual_results
            )
            
            # Update accuracy tracking by confidence bucket
            accuracy_by_confidence = self._update_accuracy_tracking(matched_results)
            update_summary['accuracy_by_confidence'] = accuracy_by_confidence
            
            # Calculate calibration adjustments
            adjustments = self._calculate_calibration_adjustments(accuracy_by_confidence)
            update_summary['calibration_adjustments'] = adjustments
            
            # Update factor performance tracking
            factor_performance = self._update_factor_performance(matched_results)
            update_summary['factor_performance'] = factor_performance
            
            # Apply adjustments to calibration state
            self._apply_calibration_updates(adjustments, factor_performance)
            
            # Save updated state
            self._save_calibration_state()
            
            update_summary['predictions_processed'] = len(matched_results)
            update_summary['new_calibration_state'] = self.calibration_state
            
            return update_summary
            
        except Exception as e:
            self.logger.error(f"Error updating calibration: {e}")
            return {'error': str(e)}
    
    def _load_calibration_state(self) -> Dict[str, Any]:
        """Load saved calibration state or initialize new one."""
        if self.calibration_file.exists():
            try:
                with open(self.calibration_file) as f:
                    state = json.load(f)
                    self.logger.info("Loaded existing calibration state")
                    return state
            except Exception as e:
                self.logger.error(f"Error loading calibration state: {e}")
        
        # Initialize new calibration state
        return {
            'version': '2.0',
            'last_updated': datetime.now().isoformat(),
            'total_predictions': 0,
            'confidence_buckets': {
                '0.15-0.25': {'correct': 0, 'total': 0},
                '0.25-0.35': {'correct': 0, 'total': 0},
                '0.35-0.45': {'correct': 0, 'total': 0},
                '0.45-0.55': {'correct': 0, 'total': 0},
                '0.55-0.65': {'correct': 0, 'total': 0},
                '0.65-0.75': {'correct': 0, 'total': 0},
                '0.75-0.85': {'correct': 0, 'total': 0}
            },
            'calibration_factors': {
                'global_adjustment': 1.0,
                'confidence_scaling': 1.0,
                'overconfidence_penalty': 0.0,
                'week_adjustments': {}
            },
            'factor_weights': {
                'coaching_differential': 1.0,
                'situational_context': 1.0,
                'momentum_factors': 1.0,
                'experience_differential': 1.0,
                'desperation_index': 1.0
            },
            'prediction_type_performance': {
                'STRONG_CONTRARIAN': {'correct': 0, 'total': 0},
                'MODERATE_CONTRARIAN': {'correct': 0, 'total': 0},
                'SLIGHT_CONTRARIAN': {'correct': 0, 'total': 0},
                'CONSENSUS_ALIGNMENT': {'correct': 0, 'total': 0}
            }
        }
    
    def _save_calibration_state(self):
        """Save calibration state to disk."""
        try:
            self.calibration_state['last_updated'] = datetime.now().isoformat()
            with open(self.calibration_file, 'w') as f:
                json.dump(self.calibration_state, f, indent=2)
            self.logger.info("Calibration state saved")
        except Exception as e:
            self.logger.error(f"Error saving calibration state: {e}")
    
    def _get_calibration_factors(self, prediction_type: str, 
                                edge_size: float, week: int) -> Dict[str, Any]:
        """Get calibration factors for current prediction."""
        factors = {
            'total_adjustment': 1.0,
            'components': {}
        }
        
        # Global calibration adjustment
        global_adj = self.calibration_state['calibration_factors'].get('global_adjustment', 1.0)
        factors['components']['global'] = global_adj
        factors['total_adjustment'] *= global_adj
        
        # Week-specific adjustment
        week_adj = self.calibration_state['calibration_factors'].get('week_adjustments', {}).get(str(week), 1.0)
        if week_adj != 1.0:
            factors['components']['week'] = week_adj
            factors['total_adjustment'] *= week_adj
        
        # Prediction type performance adjustment
        type_perf = self.calibration_state['prediction_type_performance'].get(prediction_type, {})
        if type_perf.get('total', 0) >= self.min_samples_for_adjustment:
            accuracy = type_perf['correct'] / type_perf['total']
            type_adj = self._calculate_accuracy_adjustment(accuracy)
            factors['components']['prediction_type'] = type_adj
            factors['total_adjustment'] *= type_adj
        
        # Edge size calibration
        if edge_size < 1.0:
            # Small edges have been overconfident
            factors['components']['small_edge'] = 0.9
            factors['total_adjustment'] *= 0.9
        elif edge_size > 4.0:
            # Large edges can maintain confidence
            factors['components']['large_edge'] = 1.05
            factors['total_adjustment'] *= 1.05
        
        # Get historical accuracy for this confidence level
        factors['historical_accuracy'] = self._get_historical_accuracy_rate()
        factors['sample_size'] = self.calibration_state['total_predictions']
        
        return factors
    
    def _apply_calibration(self, raw_confidence: float, 
                          factors: Dict[str, Any]) -> float:
        """Apply calibration adjustments to confidence score."""
        # Apply total adjustment factor
        calibrated = raw_confidence * factors['total_adjustment']
        
        # Apply confidence scaling (compress toward 0.5 if overconfident)
        scaling = self.calibration_state['calibration_factors'].get('confidence_scaling', 1.0)
        if scaling != 1.0:
            # Move confidence toward 0.5 by scaling factor
            calibrated = 0.5 + (calibrated - 0.5) * scaling
        
        # Apply overconfidence penalty
        penalty = self.calibration_state['calibration_factors'].get('overconfidence_penalty', 0.0)
        if penalty > 0 and calibrated > 0.65:
            calibrated -= penalty * (calibrated - 0.65)
        
        return calibrated
    
    def _match_predictions_to_results(self, predictions: List[Dict], 
                                     results: List[Dict]) -> List[Dict]:
        """Match predictions with their actual results."""
        matched = []
        
        for pred in predictions:
            for result in results:
                if self._games_match(pred, result):
                    matched.append({
                        'prediction': pred,
                        'result': result,
                        'correct': self._is_prediction_correct(pred, result)
                    })
                    break
        
        return matched
    
    def _games_match(self, prediction: Dict, result: Dict) -> bool:
        """Check if prediction and result are for the same game."""
        # Simple matching by teams (could be enhanced)
        pred_home = prediction.get('home_team', '').upper()
        pred_away = prediction.get('away_team', '').upper()
        result_home = result.get('home_team', '').upper()
        result_away = result.get('away_team', '').upper()
        
        return pred_home == result_home and pred_away == result_away
    
    def _is_prediction_correct(self, prediction: Dict, result: Dict) -> bool:
        """Determine if prediction was correct."""
        # This depends on the prediction format
        return result.get('prediction_correct', False)
    
    def _update_accuracy_tracking(self, matched_results: List[Dict]) -> Dict[str, Any]:
        """Update accuracy tracking by confidence bucket."""
        accuracy_by_bucket = {}
        
        for match in matched_results:
            confidence = match['prediction'].get('confidence', 50) / 100  # Convert to 0-1
            bucket = self._get_confidence_bucket(confidence)
            
            if bucket not in accuracy_by_bucket:
                accuracy_by_bucket[bucket] = {'correct': 0, 'total': 0}
            
            accuracy_by_bucket[bucket]['total'] += 1
            if match['correct']:
                accuracy_by_bucket[bucket]['correct'] += 1
            
            # Update calibration state
            if bucket in self.calibration_state['confidence_buckets']:
                self.calibration_state['confidence_buckets'][bucket]['total'] += 1
                if match['correct']:
                    self.calibration_state['confidence_buckets'][bucket]['correct'] += 1
        
        self.calibration_state['total_predictions'] += len(matched_results)
        
        return accuracy_by_bucket
    
    def _get_confidence_bucket(self, confidence: float) -> str:
        """Get confidence bucket for given confidence value."""
        if confidence < 0.25:
            return '0.15-0.25'
        elif confidence < 0.35:
            return '0.25-0.35'
        elif confidence < 0.45:
            return '0.35-0.45'
        elif confidence < 0.55:
            return '0.45-0.55'
        elif confidence < 0.65:
            return '0.55-0.65'
        elif confidence < 0.75:
            return '0.65-0.75'
        else:
            return '0.75-0.85'
    
    def _calculate_calibration_adjustments(self, accuracy_by_confidence: Dict) -> Dict:
        """Calculate calibration adjustments based on accuracy patterns."""
        adjustments = {}
        
        # Check for systematic overconfidence/underconfidence
        calibration_errors = []
        
        for bucket, stats in self.calibration_state['confidence_buckets'].items():
            if stats['total'] >= self.min_samples_for_adjustment:
                actual_accuracy = stats['correct'] / stats['total']
                expected_accuracy = self._get_bucket_midpoint(bucket)
                
                calibration_error = actual_accuracy - expected_accuracy
                calibration_errors.append(calibration_error)
                
                if abs(calibration_error) > 0.1:
                    # Significant miscalibration in this bucket
                    adjustments[bucket] = {
                        'expected': expected_accuracy,
                        'actual': actual_accuracy,
                        'adjustment': self._calculate_accuracy_adjustment(actual_accuracy)
                    }
        
        # Global overconfidence check
        if calibration_errors:
            mean_error = statistics.mean(calibration_errors)
            if mean_error < -0.1:  # Systematically overconfident
                adjustments['global'] = {
                    'issue': 'overconfidence',
                    'adjustment': 0.85,
                    'scaling': 0.8  # Compress confidence range
                }
            elif mean_error > 0.1:  # Systematically underconfident
                adjustments['global'] = {
                    'issue': 'underconfidence',
                    'adjustment': 1.15,
                    'scaling': 1.1  # Expand confidence range
                }
        
        return adjustments
    
    def _get_bucket_midpoint(self, bucket: str) -> float:
        """Get midpoint confidence for a bucket."""
        ranges = {
            '0.15-0.25': 0.20,
            '0.25-0.35': 0.30,
            '0.35-0.45': 0.40,
            '0.45-0.55': 0.50,
            '0.55-0.65': 0.60,
            '0.65-0.75': 0.70,
            '0.75-0.85': 0.80
        }
        return ranges.get(bucket, 0.5)
    
    def _calculate_accuracy_adjustment(self, actual_accuracy: float) -> float:
        """Calculate adjustment factor based on actual accuracy."""
        # If accuracy is 40%, we want to reduce confidence
        # If accuracy is 60%, we can increase confidence slightly
        if actual_accuracy < 0.35:
            return 0.75
        elif actual_accuracy < 0.45:
            return 0.85
        elif actual_accuracy < 0.55:
            return 1.0
        elif actual_accuracy < 0.65:
            return 1.1
        else:
            return 1.2
    
    def _update_factor_performance(self, matched_results: List[Dict]) -> Dict:
        """Track which factors are most predictive."""
        factor_performance = {}
        
        for match in matched_results:
            factors = match['prediction'].get('factor_breakdown', {})
            
            for factor_name, factor_value in factors.items():
                if factor_name not in factor_performance:
                    factor_performance[factor_name] = {
                        'correct_sum': 0,
                        'incorrect_sum': 0,
                        'total': 0
                    }
                
                factor_performance[factor_name]['total'] += 1
                
                if match['correct']:
                    factor_performance[factor_name]['correct_sum'] += abs(factor_value)
                else:
                    factor_performance[factor_name]['incorrect_sum'] += abs(factor_value)
        
        # Calculate predictive power for each factor
        for factor_name, perf in factor_performance.items():
            if perf['total'] > 0:
                correct_avg = perf['correct_sum'] / max(perf['total'] / 2, 1)
                incorrect_avg = perf['incorrect_sum'] / max(perf['total'] / 2, 1)
                perf['predictive_power'] = correct_avg - incorrect_avg
        
        return factor_performance
    
    def _apply_calibration_updates(self, adjustments: Dict, 
                                  factor_performance: Dict):
        """Apply calculated adjustments to calibration state."""
        if 'global' in adjustments:
            global_adj = adjustments['global']
            self.calibration_state['calibration_factors']['global_adjustment'] *= global_adj.get('adjustment', 1.0)
            self.calibration_state['calibration_factors']['confidence_scaling'] = global_adj.get('scaling', 1.0)
            
            if global_adj.get('issue') == 'overconfidence':
                self.calibration_state['calibration_factors']['overconfidence_penalty'] = 0.05
        
        # Update factor weights based on performance
        for factor_name, perf in factor_performance.items():
            if perf.get('predictive_power') is not None and perf['total'] >= 10:
                current_weight = self.calibration_state['factor_weights'].get(factor_name, 1.0)
                
                if perf['predictive_power'] > 0.1:
                    # Good predictor, increase weight
                    new_weight = min(1.5, current_weight * 1.1)
                elif perf['predictive_power'] < -0.1:
                    # Poor predictor, decrease weight
                    new_weight = max(0.5, current_weight * 0.9)
                else:
                    new_weight = current_weight
                
                self.calibration_state['factor_weights'][factor_name] = new_weight
    
    def _assess_calibration_quality(self) -> str:
        """Assess overall calibration quality."""
        total_predictions = self.calibration_state['total_predictions']
        
        if total_predictions < 20:
            return 'INSUFFICIENT_DATA'
        
        # Calculate calibration score
        calibration_errors = []
        
        for bucket, stats in self.calibration_state['confidence_buckets'].items():
            if stats['total'] > 5:
                actual = stats['correct'] / stats['total']
                expected = self._get_bucket_midpoint(bucket)
                calibration_errors.append(abs(actual - expected))
        
        if not calibration_errors:
            return 'INSUFFICIENT_DATA'
        
        mean_error = statistics.mean(calibration_errors)
        
        if mean_error < 0.05:
            return 'EXCELLENT'
        elif mean_error < 0.10:
            return 'GOOD'
        elif mean_error < 0.15:
            return 'FAIR'
        else:
            return 'POOR'
    
    def _generate_calibration_explanation(self, raw: float, calibrated: float, 
                                         factors: Dict) -> str:
        """Generate explanation of calibration adjustments."""
        if abs(raw - calibrated) < 0.02:
            return "Minimal calibration adjustment applied."
        
        adjustment = factors['total_adjustment']
        
        if adjustment < 0.9:
            return f"Confidence reduced by {(1-adjustment)*100:.0f}% due to historical overconfidence."
        elif adjustment > 1.1:
            return f"Confidence increased by {(adjustment-1)*100:.0f}% based on strong historical accuracy."
        else:
            return "Standard calibration adjustment applied."
    
    def _get_historical_accuracy_rate(self) -> float:
        """Get overall historical accuracy rate."""
        total_correct = sum(b['correct'] for b in self.calibration_state['confidence_buckets'].values())
        total_predictions = self.calibration_state['total_predictions']
        
        if total_predictions == 0:
            return 0.5
        
        return total_correct / total_predictions
    
    def get_calibration_report(self) -> Dict[str, Any]:
        """Generate comprehensive calibration report."""
        return {
            'total_predictions': self.calibration_state['total_predictions'],
            'overall_accuracy': self._get_historical_accuracy_rate(),
            'calibration_quality': self._assess_calibration_quality(),
            'confidence_buckets': self.calibration_state['confidence_buckets'],
            'current_adjustments': self.calibration_state['calibration_factors'],
            'factor_weights': self.calibration_state['factor_weights'],
            'last_updated': self.calibration_state.get('last_updated')
        }


# Global instance
adaptive_calibrator = AdaptiveCalibrator()