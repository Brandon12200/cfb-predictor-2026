#!/usr/bin/env python3
"""
Results Checking Script for College Football Market Edge Platform.

Fetches completed game results and evaluates the success of previous predictions.
Updates the performance tracking database with accuracy metrics.

Usage:
    python scripts/check_results.py [options]

Examples:
    python scripts/check_results.py                    # Check last week
    python scripts/check_results.py --week 5           # Check specific week
    python scripts/check_results.py --detailed-report  # Generate detailed report
"""

import sys
import json
import argparse
from pathlib import Path
from datetime import datetime, timedelta

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from utils.prediction_storage import prediction_storage
from utils.results_fetcher import results_fetcher
from utils.bet_evaluator import bet_evaluator


def get_last_week() -> int:
    """
    Get the most recent completed week.
    
    This is a simple implementation - could be improved with
    more sophisticated date-based logic.
    
    Returns:
        Most recent week number
    """
    # Get current week and subtract 1
    now = datetime.now()
    
    if now.month < 8:  # Before season starts
        return 1
    elif now.month >= 12:  # After regular season
        return 15
    
    # Rough approximation
    if now.month == 8:
        return 1
    elif now.month == 9:
        week_of_month = (now.day - 1) // 7 + 1
        current_week = min(week_of_month + 1, 5)
        return max(current_week - 1, 1)
    elif now.month == 10:
        week_of_month = (now.day - 1) // 7 + 1
        current_week = min(week_of_month + 5, 9)
        return max(current_week - 1, 1)
    elif now.month == 11:
        week_of_month = (now.day - 1) // 7 + 1
        current_week = min(week_of_month + 9, 13)
        return max(current_week - 1, 1)
    else:
        return 13


def check_week_results(week: int, season: int = 2025) -> dict:
    """
    Check results for a specific week.
    
    Args:
        week: Week number to check
        season: Season year
        
    Returns:
        Dictionary with week results and evaluation
    """
    if week == 0:
        print("⚠️  Skipping Week 0 as requested")
        return {"week": week, "predictions": [], "results": [], "evaluations": []}
    
    print(f"Checking results for Week {week}, {season}...")
    
    # Load predictions for this week
    prediction_data = prediction_storage.load_weekly_predictions(week, season)
    
    if not prediction_data:
        print(f"❌ No predictions found for Week {week}")
        return {"week": week, "predictions": [], "results": [], "evaluations": []}
    
    predictions = prediction_data.get('predictions', [])
    print(f"📋 Found {len(predictions)} predictions to evaluate")
    
    if not predictions:
        print("❌ No predictions in file")
        return {"week": week, "predictions": [], "results": [], "evaluations": []}
    
    # Fetch game results for this week
    try:
        game_results = results_fetcher.fetch_game_results(week, season)
        print(f"📊 Found {len(game_results)} completed games")
    except Exception as e:
        print(f"❌ Error fetching results: {e}")
        return {"week": week, "predictions": predictions, "results": [], "evaluations": []}
    
    # Save results to file
    if game_results:
        results_filepath = prediction_storage.save_weekly_results(game_results, week, season)
        print(f"💾 Results saved to: {results_filepath}")
    
    # Evaluate each prediction
    evaluations = []
    
    print("\\nEvaluating predictions...")
    print("-" * 40)
    
    for i, prediction in enumerate(predictions, 1):
        try:
            # Find matching game result
            home_team = prediction['home_team']
            away_team = prediction['away_team']
            
            # Look for matching result
            matching_result = None
            for result in game_results:
                if (results_fetcher._normalize_team_for_matching(result['home_team']) == 
                    results_fetcher._normalize_team_for_matching(home_team) and
                    results_fetcher._normalize_team_for_matching(result['away_team']) == 
                    results_fetcher._normalize_team_for_matching(away_team)):
                    matching_result = result
                    break
            
            if not matching_result:
                print(f"{i}. ❓ {away_team} @ {home_team} - Game not found or incomplete")
                evaluation = {
                    "prediction": prediction,
                    "game_result": None,
                    "bet_evaluation": {"error": "Game result not found"},
                    "found_result": False
                }
                evaluations.append(evaluation)
                continue
            
            # Evaluate the bet
            bet_result = bet_evaluator.evaluate_bet(prediction, matching_result)
            
            # Create evaluation entry
            evaluation = {
                "prediction": prediction,
                "game_result": matching_result,
                "bet_evaluation": bet_result,
                "found_result": True
            }
            evaluations.append(evaluation)
            
            # Display result
            summary = bet_evaluator.generate_bet_summary(prediction, bet_result)
            print(f"{i}. {summary}")
            
        except Exception as e:
            print(f"{i}. 🚨 Error evaluating {away_team} @ {home_team}: {e}")
            evaluation = {
                "prediction": prediction,
                "game_result": None,
                "bet_evaluation": {"error": str(e)},
                "found_result": False
            }
            evaluations.append(evaluation)
    
    return {
        "week": week,
        "season": season,
        "predictions": predictions,
        "results": game_results,
        "evaluations": evaluations
    }


def calculate_week_summary(week_data: dict) -> dict:
    """
    Calculate summary statistics for a week.
    
    Args:
        week_data: Week results data
        
    Returns:
        Summary statistics dictionary
    """
    evaluations = week_data.get('evaluations', [])
    valid_evaluations = [e for e in evaluations if e.get('found_result', False)]
    
    if not valid_evaluations:
        return {
            "predictions": 0,
            "wins": 0,
            "losses": 0,
            "pushes": 0,
            "win_rate": None,
            "average_confidence": None,
            "average_edge": None,
            "largest_edge": None,
            "best_call": None,
            "worst_call": None
        }
    
    wins = 0
    losses = 0
    pushes = 0
    confidence_scores = []
    edge_sizes = []
    best_call = None
    worst_call = None
    best_margin = -float('inf')
    worst_margin = float('inf')
    
    for evaluation in valid_evaluations:
        bet_eval = evaluation.get('bet_evaluation', {})
        prediction = evaluation.get('prediction', {})
        
        if bet_eval.get('bet_won', False):
            wins += 1
            margin = bet_eval.get('bet_margin', 0)
            if margin > best_margin:
                best_margin = margin
                best_call = bet_evaluator.generate_bet_summary(prediction, bet_eval)
        elif bet_eval.get('is_push', False):
            pushes += 1
        else:
            losses += 1
            margin = bet_eval.get('bet_margin', 0)
            if margin < worst_margin:
                worst_margin = margin
                worst_call = bet_evaluator.generate_bet_summary(prediction, bet_eval)
        
        confidence_scores.append(prediction.get('confidence', 0))
        edge_sizes.append(prediction.get('predicted_edge', 0))
    
    return {
        "predictions": len(valid_evaluations),
        "wins": wins,
        "losses": losses,
        "pushes": pushes,
        "win_rate": wins / len(valid_evaluations) if valid_evaluations else None,
        "average_confidence": sum(confidence_scores) / len(confidence_scores) if confidence_scores else None,
        "average_edge": sum(edge_sizes) / len(edge_sizes) if edge_sizes else None,
        "largest_edge": max(edge_sizes) if edge_sizes else None,
        "best_call": best_call,
        "worst_call": worst_call
    }


def update_performance_tracker(week_data: dict, week_summary: dict):
    """
    Update the master performance tracker with new week data.
    
    Args:
        week_data: Week results data
        week_summary: Week summary statistics
    """
    # Load current performance data
    performance_data = prediction_storage.load_performance_tracker()
    
    week = week_data['week']
    season = week_data['season']
    week_key = f"{season}_week_{week:02d}"
    
    # Add this week's data
    performance_data['weekly_breakdown'][week_key] = week_summary
    performance_data['weeks_tracked'] = len(performance_data['weekly_breakdown'])
    
    # Update overall statistics
    all_weeks = list(performance_data['weekly_breakdown'].values())
    valid_weeks = [w for w in all_weeks if w.get('predictions', 0) > 0]
    
    if valid_weeks:
        total_predictions = sum(w['predictions'] for w in valid_weeks)
        total_wins = sum(w['wins'] for w in valid_weeks)
        total_games_analyzed = sum(len(wd.get('predictions', [])) for wd in [week_data] if 'predictions' in wd)
        
        # Get all confidence scores for average
        all_confidences = []
        all_edges = []
        for evaluation in week_data.get('evaluations', []):
            if evaluation.get('found_result'):
                pred = evaluation.get('prediction', {})
                all_confidences.append(pred.get('confidence', 0))
                all_edges.append(pred.get('predicted_edge', 0))
        
        # Update overall performance
        performance_data['overall_performance'].update({
            "total_predictions": total_predictions,
            "correct_predictions": total_wins,
            "win_rate": total_wins / total_predictions if total_predictions > 0 else None,
            "total_games_analyzed": total_games_analyzed,
            "prediction_rate": total_predictions / total_games_analyzed if total_games_analyzed > 0 else None,
            "average_edge_size": sum(all_edges) / len(all_edges) if all_edges else None,
            "average_confidence": sum(all_confidences) / len(all_confidences) if all_confidences else None
        })
        
        # Update confidence analysis
        if week_data.get('evaluations'):
            confidence_cal = bet_evaluator.calculate_confidence_calibration(
                [e['prediction'] for e in week_data['evaluations'] if e.get('found_result')],
                [e['bet_evaluation'] for e in week_data['evaluations'] if e.get('found_result')]
            )
            performance_data['confidence_analysis'] = confidence_cal
        
        # Set tracking start date if first week
        if performance_data['tracking_start_date'] is None:
            performance_data['tracking_start_date'] = datetime.now().strftime('%Y-%m-%d')
    
    # Save updated performance data
    prediction_storage.save_performance_tracker(performance_data)
    print(f"📈 Performance tracker updated")


def generate_detailed_report(week_data: dict, week_summary: dict) -> str:
    """
    Generate a detailed report for the week.
    
    Args:
        week_data: Week results data
        week_summary: Week summary statistics
        
    Returns:
        Formatted report string
    """
    lines = []
    week = week_data['week']
    season = week_data['season']
    
    lines.append("=" * 60)
    lines.append(f"DETAILED RESULTS REPORT - WEEK {week}, {season}")
    lines.append("=" * 60)
    lines.append()
    
    # Week summary
    lines.append("WEEK SUMMARY:")
    lines.append(f"  Predictions Made: {week_summary['predictions']}")
    if week_summary['predictions'] > 0:
        lines.append(f"  Wins: {week_summary['wins']}")
        lines.append(f"  Losses: {week_summary['losses']}")
        lines.append(f"  Pushes: {week_summary['pushes']}")
        lines.append(f"  Win Rate: {week_summary['win_rate']:.1%}" if week_summary['win_rate'] else "  Win Rate: N/A")
        lines.append(f"  Average Confidence: {week_summary['average_confidence']:.1f}%" if week_summary['average_confidence'] else "  Average Confidence: N/A")
        lines.append(f"  Average Edge: {week_summary['average_edge']:.1f} pts" if week_summary['average_edge'] else "  Average Edge: N/A")
    lines.append()
    
    # Individual results
    if week_data.get('evaluations'):
        lines.append("INDIVIDUAL RESULTS:")
        lines.append("-" * 40)
        
        for i, evaluation in enumerate(week_data['evaluations'], 1):
            if evaluation.get('found_result'):
                prediction = evaluation['prediction']
                bet_eval = evaluation['bet_evaluation']
                summary = bet_evaluator.generate_bet_summary(prediction, bet_eval)
                
                lines.append(f"{i}. {summary}")
                lines.append(f"   Confidence: {prediction.get('confidence', 0):.1f}%")
                lines.append(f"   Predicted Edge: {prediction.get('predicted_edge', 0):.1f} pts")
                if prediction.get('bet_rationale'):
                    lines.append(f"   Rationale: {prediction['bet_rationale']}")
                lines.append()
        
        # Best/worst calls
        if week_summary.get('best_call'):
            lines.append("NOTABLE CALLS:")
            lines.append(f"  Best Call: {week_summary['best_call']}")
            if week_summary.get('worst_call'):
                lines.append(f"  Worst Call: {week_summary['worst_call']}")
            lines.append()
    
    # Overall performance (if available)
    performance_data = prediction_storage.load_performance_tracker()
    overall = performance_data.get('overall_performance', {})
    
    if overall.get('total_predictions', 0) > 0:
        lines.append("OVERALL PERFORMANCE TO DATE:")
        lines.append(f"  Total Predictions: {overall['total_predictions']}")
        lines.append(f"  Overall Win Rate: {overall['win_rate']:.1%}" if overall['win_rate'] else "  Overall Win Rate: N/A")
        lines.append(f"  Weeks Tracked: {performance_data.get('weeks_tracked', 0)}")
        lines.append(f"  Average Confidence: {overall['average_confidence']:.1f}%" if overall['average_confidence'] else "  Average Confidence: N/A")
        lines.append()
    
    lines.append("=" * 60)
    
    return "\\n".join(lines)


def main():
    """Main script execution."""
    parser = argparse.ArgumentParser(
        description='Check results of previous week predictions',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                        Check most recent week
  %(prog)s --week 5               Check specific week
  %(prog)s --detailed-report      Generate detailed report
  %(prog)s --save-report FILE     Save report to file
        """
    )
    
    parser.add_argument('--week', type=int,
                       help='Week number to check (default: last week)')
    parser.add_argument('--season', type=int, default=2025,
                       help='Season year (default: 2025)')
    parser.add_argument('--detailed-report', action='store_true',
                       help='Generate detailed report')
    parser.add_argument('--save-report', type=str,
                       help='Save detailed report to file')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Verbose output')
    
    args = parser.parse_args()
    
    # Determine week
    week = args.week if args.week else get_last_week()
    
    if week == 0:
        print("❌ Week 0 is excluded from analysis")
        return 1
    
    print("=" * 60)
    print("College Football Market Edge Platform - Results Check")
    print("=" * 60)
    print(f"Checking Week: {week}")
    print(f"Season: {args.season}")
    print()
    
    try:
        # Check results for the week
        week_data = check_week_results(week, args.season)
        
        # Calculate summary
        week_summary = calculate_week_summary(week_data)
        
        # Update performance tracker
        if week_summary['predictions'] > 0:
            update_performance_tracker(week_data, week_summary)
        
        # Display basic results
        print("\\n" + "=" * 60)
        print("WEEK RESULTS SUMMARY")
        print("=" * 60)
        
        if week_summary['predictions'] == 0:
            print("❌ No predictions found for this week")
        else:
            print(f"Predictions: {week_summary['predictions']}")
            print(f"Wins: {week_summary['wins']}")
            print(f"Losses: {week_summary['losses']}")
            if week_summary['pushes'] > 0:
                print(f"Pushes: {week_summary['pushes']}")
            
            if week_summary['win_rate'] is not None:
                print(f"Win Rate: {week_summary['win_rate']:.1%}")
            
            if week_summary['average_confidence'] is not None:
                print(f"Average Confidence: {week_summary['average_confidence']:.1f}%")
        
        # Generate detailed report if requested
        if args.detailed_report or args.save_report:
            report = generate_detailed_report(week_data, week_summary)
            
            if args.save_report:
                with open(args.save_report, 'w') as f:
                    f.write(report)
                print(f"\\n📄 Detailed report saved to: {args.save_report}")
            else:
                print("\\n" + report)
        
        return 0
        
    except KeyboardInterrupt:
        print("\\n❌ Interrupted by user")
        return 1
    except Exception as e:
        print(f"❌ Error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == '__main__':
    exit(main())