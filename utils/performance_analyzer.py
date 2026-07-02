"""
Advanced performance analysis utilities for College Football Market Edge Platform.

Provides detailed analytics on prediction accuracy, confidence calibration,
and factor performance over time.
"""

import json
import statistics
from typing import Dict, List, Tuple, Optional
from datetime import datetime
from collections import defaultdict

from utils.prediction_storage import prediction_storage


class PerformanceAnalyzer:
    """Advanced analytics for prediction performance."""
    
    def __init__(self):
        self.performance_data = prediction_storage.load_performance_tracker()
    
    def analyze_confidence_calibration(self) -> Dict:
        """
        Analyze how well confidence scores match actual success rates.
        
        Returns:
            Detailed confidence calibration analysis
        """
        calibration_data = {
            "overall_calibration": None,
            "by_confidence_bucket": {},
            "calibration_score": None,
            "is_well_calibrated": False,
            "recommendations": []
        }
        
        # Get all predictions and their outcomes
        all_predictions = []
        all_outcomes = []
        
        # Load all weekly data
        weeks = prediction_storage.get_all_prediction_weeks()
        
        for week in weeks:
            if week == 0:  # Skip week 0
                continue
                
            prediction_data = prediction_storage.load_weekly_predictions(week)
            results_data = prediction_storage.load_weekly_results(week)
            
            if not prediction_data or not results_data:
                continue
            
            predictions = prediction_data.get('predictions', [])
            results = results_data.get('results', [])
            
            # Match predictions to results
            for pred in predictions:
                # Find matching result
                matching_result = self._find_matching_result(pred, results)
                if matching_result:
                    from utils.bet_evaluator import bet_evaluator
                    bet_eval = bet_evaluator.evaluate_bet(pred, matching_result)
                    
                    all_predictions.append(pred)
                    all_outcomes.append(bet_eval.get('bet_won', False))
        
        if not all_predictions:
            return calibration_data
        
        # Analyze by confidence buckets
        confidence_buckets = {
            "90_plus": {"predictions": [], "outcomes": []},
            "80_89": {"predictions": [], "outcomes": []},
            "70_79": {"predictions": [], "outcomes": []},
            "60_69": {"predictions": [], "outcomes": []},
            "50_59": {"predictions": [], "outcomes": []},
            "below_50": {"predictions": [], "outcomes": []}
        }
        
        for pred, outcome in zip(all_predictions, all_outcomes):
            confidence = pred.get('confidence', 0)
            
            if confidence >= 90:
                bucket = "90_plus"
            elif confidence >= 80:
                bucket = "80_89"
            elif confidence >= 70:
                bucket = "70_79"
            elif confidence >= 60:
                bucket = "60_69"
            elif confidence >= 50:
                bucket = "50_59"
            else:
                bucket = "below_50"
            
            confidence_buckets[bucket]["predictions"].append(pred)
            confidence_buckets[bucket]["outcomes"].append(outcome)
        
        # Calculate calibration for each bucket
        bucket_analysis = {}
        calibration_errors = []
        
        for bucket_name, bucket_data in confidence_buckets.items():
            if not bucket_data["predictions"]:
                continue
            
            predicted_rate = sum(p.get('confidence', 0) for p in bucket_data["predictions"]) / len(bucket_data["predictions"]) / 100
            actual_rate = sum(bucket_data["outcomes"]) / len(bucket_data["outcomes"])
            calibration_error = abs(predicted_rate - actual_rate)
            
            bucket_analysis[bucket_name] = {
                "count": len(bucket_data["predictions"]),
                "predicted_success_rate": predicted_rate,
                "actual_success_rate": actual_rate,
                "calibration_error": calibration_error,
                "is_overconfident": predicted_rate > actual_rate,
                "avg_confidence": sum(p.get('confidence', 0) for p in bucket_data["predictions"]) / len(bucket_data["predictions"])
            }
            
            calibration_errors.append(calibration_error)
        
        calibration_data["by_confidence_bucket"] = bucket_analysis
        
        # Overall calibration score (lower is better)
        if calibration_errors:
            calibration_data["calibration_score"] = sum(calibration_errors) / len(calibration_errors)
            calibration_data["is_well_calibrated"] = calibration_data["calibration_score"] < 0.1  # Within 10%
        
        # Generate recommendations
        recommendations = []
        
        for bucket_name, analysis in bucket_analysis.items():
            if analysis["count"] < 5:  # Too few samples
                continue
            
            if analysis["calibration_error"] > 0.15:  # More than 15% error
                if analysis["is_overconfident"]:
                    recommendations.append(f"Reduce confidence for {bucket_name.replace('_', '-')} predictions (overconfident by {analysis['calibration_error']:.1%})")
                else:
                    recommendations.append(f"Increase confidence for {bucket_name.replace('_', '-')} predictions (underconfident by {analysis['calibration_error']:.1%})")
        
        if not recommendations:
            recommendations.append("Confidence calibration is well-balanced")
        
        calibration_data["recommendations"] = recommendations
        
        return calibration_data
    
    def analyze_factor_performance(self) -> Dict:
        """
        Analyze individual factor performance over time.
        
        Returns:
            Factor performance analysis
        """
        factor_analysis = {
            "factor_success_rates": {},
            "factor_impact_analysis": {},
            "best_performing_factors": [],
            "worst_performing_factors": [],
            "factor_correlations": {},
            "recommendations": []
        }
        
        # Collect factor data from all weeks
        factor_outcomes = defaultdict(list)  # factor_name -> [(factor_value, bet_won), ...]
        factor_impacts = defaultdict(list)   # factor_name -> [impact_values, ...]
        
        weeks = prediction_storage.get_all_prediction_weeks()
        
        for week in weeks:
            if week == 0:
                continue
                
            prediction_data = prediction_storage.load_weekly_predictions(week)
            results_data = prediction_storage.load_weekly_results(week)
            
            if not prediction_data or not results_data:
                continue
            
            predictions = prediction_data.get('predictions', [])
            results = results_data.get('results', [])
            
            for pred in predictions:
                matching_result = self._find_matching_result(pred, results)
                if not matching_result:
                    continue
                
                from utils.bet_evaluator import bet_evaluator
                bet_eval = bet_evaluator.evaluate_bet(pred, matching_result)
                bet_won = bet_eval.get('bet_won', False)
                
                factor_breakdown = pred.get('factor_breakdown', {})
                
                for factor_name, factor_value in factor_breakdown.items():
                    factor_outcomes[factor_name].append((factor_value, bet_won))
                    factor_impacts[factor_name].append(abs(factor_value))
        
        # Analyze each factor
        for factor_name, outcomes in factor_outcomes.items():
            if len(outcomes) < 3:  # Need minimum samples
                continue
            
            # Calculate success rate when factor is positive vs negative
            positive_outcomes = [won for value, won in outcomes if value > 0.1]
            negative_outcomes = [won for value, won in outcomes if value < -0.1]
            
            positive_rate = sum(positive_outcomes) / len(positive_outcomes) if positive_outcomes else 0
            negative_rate = sum(negative_outcomes) / len(negative_outcomes) if negative_outcomes else 0
            
            # Average impact
            avg_impact = sum(factor_impacts[factor_name]) / len(factor_impacts[factor_name])
            
            # Directional accuracy (does positive factor value correlate with wins?)
            directional_accuracy = self._calculate_directional_accuracy(outcomes)
            
            factor_analysis["factor_success_rates"][factor_name] = {
                "total_occurrences": len(outcomes),
                "positive_impact_rate": positive_rate,
                "negative_impact_rate": negative_rate,
                "average_impact_magnitude": avg_impact,
                "directional_accuracy": directional_accuracy,
                "effectiveness_score": (directional_accuracy * avg_impact)  # Combined metric
            }
        
        # Rank factors by effectiveness
        if factor_analysis["factor_success_rates"]:
            sorted_factors = sorted(
                factor_analysis["factor_success_rates"].items(),
                key=lambda x: x[1]["effectiveness_score"],
                reverse=True
            )
            
            factor_analysis["best_performing_factors"] = [
                {"name": name, "score": data["effectiveness_score"]} 
                for name, data in sorted_factors[:3]
            ]
            
            factor_analysis["worst_performing_factors"] = [
                {"name": name, "score": data["effectiveness_score"]} 
                for name, data in sorted_factors[-3:]
            ]
        
        # Generate recommendations
        recommendations = []
        
        for factor_name, analysis in factor_analysis["factor_success_rates"].items():
            if analysis["directional_accuracy"] < 0.4:  # Poor directional accuracy
                recommendations.append(f"Review {factor_name} logic - low directional accuracy ({analysis['directional_accuracy']:.1%})")
            elif analysis["effectiveness_score"] > 0.3:  # High effectiveness
                recommendations.append(f"Consider increasing weight for {factor_name} - high effectiveness score")
        
        if not recommendations:
            recommendations.append("Factor performance appears balanced")
        
        factor_analysis["recommendations"] = recommendations
        
        return factor_analysis
    
    def generate_performance_trends(self) -> Dict:
        """
        Analyze performance trends over time.
        
        Returns:
            Trend analysis data
        """
        trends = {
            "weekly_performance": [],
            "rolling_averages": {},
            "trend_direction": None,
            "performance_stability": None,
            "seasonal_patterns": {},
            "improvement_rate": None
        }
        
        weeks = sorted(prediction_storage.get_all_prediction_weeks())
        if not weeks or len(weeks) < 2:
            return trends
        
        # Calculate weekly performance
        weekly_data = []
        
        for week in weeks:
            if week == 0:
                continue
                
            prediction_data = prediction_storage.load_weekly_predictions(week)
            results_data = prediction_storage.load_weekly_results(week)
            
            if not prediction_data or not results_data:
                continue
            
            predictions = prediction_data.get('predictions', [])
            results = results_data.get('results', [])
            
            # Calculate week metrics
            week_wins = 0
            week_total = 0
            week_confidences = []
            week_edges = []
            
            for pred in predictions:
                matching_result = self._find_matching_result(pred, results)
                if matching_result:
                    from utils.bet_evaluator import bet_evaluator
                    bet_eval = bet_evaluator.evaluate_bet(pred, matching_result)
                    
                    if bet_eval.get('bet_won', False):
                        week_wins += 1
                    week_total += 1
                    week_confidences.append(pred.get('confidence', 0))
                    week_edges.append(pred.get('predicted_edge', 0))
            
            if week_total > 0:
                weekly_data.append({
                    "week": week,
                    "win_rate": week_wins / week_total,
                    "total_predictions": week_total,
                    "wins": week_wins,
                    "avg_confidence": sum(week_confidences) / len(week_confidences),
                    "avg_edge": sum(week_edges) / len(week_edges)
                })
        
        trends["weekly_performance"] = weekly_data
        
        # Calculate rolling averages
        if len(weekly_data) >= 3:
            rolling_3_week = []
            for i in range(2, len(weekly_data)):
                recent_weeks = weekly_data[i-2:i+1]
                rolling_win_rate = sum(w["win_rate"] for w in recent_weeks) / 3
                rolling_3_week.append({
                    "week": weekly_data[i]["week"],
                    "rolling_win_rate": rolling_win_rate
                })
            
            trends["rolling_averages"]["3_week"] = rolling_3_week
        
        # Determine trend direction
        if len(weekly_data) >= 4:
            recent_avg = sum(w["win_rate"] for w in weekly_data[-3:]) / 3
            early_avg = sum(w["win_rate"] for w in weekly_data[:3]) / 3
            
            if recent_avg > early_avg + 0.1:
                trends["trend_direction"] = "improving"
                trends["improvement_rate"] = (recent_avg - early_avg) / len(weekly_data)
            elif recent_avg < early_avg - 0.1:
                trends["trend_direction"] = "declining"
                trends["improvement_rate"] = (recent_avg - early_avg) / len(weekly_data)
            else:
                trends["trend_direction"] = "stable"
                trends["improvement_rate"] = 0
        
        # Performance stability (coefficient of variation)
        if len(weekly_data) >= 3:
            win_rates = [w["win_rate"] for w in weekly_data]
            if win_rates:
                mean_win_rate = statistics.mean(win_rates)
                if mean_win_rate > 0:
                    cv = statistics.stdev(win_rates) / mean_win_rate
                    trends["performance_stability"] = {
                        "coefficient_of_variation": cv,
                        "is_stable": cv < 0.3,  # Less than 30% variation
                        "stability_rating": "high" if cv < 0.2 else "medium" if cv < 0.4 else "low"
                    }
        
        return trends
    
    def generate_comprehensive_report(self) -> str:
        """
        Generate a comprehensive performance analysis report.
        
        Returns:
            Formatted comprehensive report
        """
        lines = []
        
        lines.append("=" * 80)
        lines.append("COMPREHENSIVE PERFORMANCE ANALYSIS")
        lines.append("College Football Market Edge Platform")
        lines.append("=" * 80)
        lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append()
        
        # Basic stats
        overall = self.performance_data.get('overall_performance', {})
        lines.append("OVERALL PERFORMANCE SUMMARY:")
        lines.append("-" * 40)
        lines.append(f"Total Predictions: {overall.get('total_predictions', 0)}")
        lines.append(f"Correct Predictions: {overall.get('correct_predictions', 0)}")
        if overall.get('win_rate'):
            lines.append(f"Win Rate: {overall['win_rate']:.1%}")
        if overall.get('average_confidence'):
            lines.append(f"Average Confidence: {overall['average_confidence']:.1f}%")
        lines.append(f"Weeks Tracked: {self.performance_data.get('weeks_tracked', 0)}")
        lines.append()
        
        # Confidence calibration
        calibration = self.analyze_confidence_calibration()
        lines.append("CONFIDENCE CALIBRATION ANALYSIS:")
        lines.append("-" * 40)
        
        if calibration.get("calibration_score") is not None:
            lines.append(f"Overall Calibration Score: {calibration['calibration_score']:.3f}")
            lines.append(f"Well Calibrated: {'Yes' if calibration['is_well_calibrated'] else 'No'}")
            lines.append()
            
            for bucket, analysis in calibration.get("by_confidence_bucket", {}).items():
                if analysis["count"] >= 3:  # Only show buckets with enough data
                    lines.append(f"{bucket.replace('_', '-')} Confidence:")
                    lines.append(f"  Predictions: {analysis['count']}")
                    lines.append(f"  Expected Rate: {analysis['predicted_success_rate']:.1%}")
                    lines.append(f"  Actual Rate: {analysis['actual_success_rate']:.1%}")
                    lines.append(f"  Calibration Error: {analysis['calibration_error']:.1%}")
                    lines.append()
        else:
            lines.append("Insufficient data for calibration analysis")
            lines.append()
        
        # Factor performance
        factor_perf = self.analyze_factor_performance()
        lines.append("FACTOR PERFORMANCE ANALYSIS:")
        lines.append("-" * 40)
        
        if factor_perf.get("best_performing_factors"):
            lines.append("Best Performing Factors:")
            for factor in factor_perf["best_performing_factors"]:
                lines.append(f"  • {factor['name']}: {factor['score']:.3f}")
            lines.append()
        
        if factor_perf.get("worst_performing_factors"):
            lines.append("Needs Improvement:")
            for factor in factor_perf["worst_performing_factors"]:
                lines.append(f"  • {factor['name']}: {factor['score']:.3f}")
            lines.append()
        
        # Trends
        trends = self.generate_performance_trends()
        lines.append("PERFORMANCE TRENDS:")
        lines.append("-" * 40)
        
        if trends.get("trend_direction"):
            lines.append(f"Trend Direction: {trends['trend_direction'].title()}")
            if trends.get("improvement_rate"):
                lines.append(f"Improvement Rate: {trends['improvement_rate']:.3f} per week")
        
        if trends.get("performance_stability"):
            stability = trends["performance_stability"]
            lines.append(f"Performance Stability: {stability['stability_rating'].title()}")
            lines.append(f"Coefficient of Variation: {stability['coefficient_of_variation']:.3f}")
        
        lines.append()
        
        # Recent performance
        if trends.get("weekly_performance") and len(trends["weekly_performance"]) >= 3:
            lines.append("RECENT WEEKLY PERFORMANCE:")
            lines.append("-" * 40)
            recent_weeks = trends["weekly_performance"][-5:]  # Last 5 weeks
            
            for week_data in recent_weeks:
                lines.append(f"Week {week_data['week']}: {week_data['wins']}/{week_data['total_predictions']} ({week_data['win_rate']:.1%})")
        
        lines.append()
        
        # Recommendations
        all_recommendations = []
        all_recommendations.extend(calibration.get("recommendations", []))
        all_recommendations.extend(factor_perf.get("recommendations", []))
        
        if all_recommendations:
            lines.append("RECOMMENDATIONS:")
            lines.append("-" * 40)
            for i, rec in enumerate(all_recommendations[:5], 1):  # Top 5 recommendations
                lines.append(f"{i}. {rec}")
        
        lines.append()
        lines.append("=" * 80)
        
        return "\n".join(lines)
    
    def _find_matching_result(self, prediction: Dict, results: List[Dict]) -> Optional[Dict]:
        """Find matching game result for a prediction."""
        from utils.results_fetcher import results_fetcher
        
        pred_home = results_fetcher._normalize_team_for_matching(prediction['home_team'])
        pred_away = results_fetcher._normalize_team_for_matching(prediction['away_team'])
        
        for result in results:
            result_home = results_fetcher._normalize_team_for_matching(result['home_team'])
            result_away = results_fetcher._normalize_team_for_matching(result['away_team'])
            
            if result_home == pred_home and result_away == pred_away:
                return result
        
        return None
    
    def _calculate_directional_accuracy(self, outcomes: List[Tuple[float, bool]]) -> float:
        """Calculate how often factor direction matches bet outcome."""
        if not outcomes:
            return 0.0
        
        correct_directions = 0
        
        for factor_value, bet_won in outcomes:
            # Positive factor should correlate with wins, negative with losses
            if (factor_value > 0 and bet_won) or (factor_value < 0 and not bet_won):
                correct_directions += 1
        
        return correct_directions / len(outcomes)


# Convenience instance
performance_analyzer = PerformanceAnalyzer()