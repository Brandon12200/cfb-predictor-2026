#!/usr/bin/env python3
"""
Fetch Week 1 results and update the results file.
"""

import json
import sys
import os
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from utils.results_fetcher import results_fetcher
from utils.normalizer import normalizer as team_name_normalizer

def main():
    """Fetch Week 1 results and update the results file."""
    
    # Load predictions to get the games we're tracking
    predictions_file = Path("data/predictions/2025_week_01.json")
    results_file = Path("data/results/2025_week_01_results.json")
    
    with open(predictions_file) as f:
        predictions_data = json.load(f)
    
    # Fetch actual results from APIs
    print("Fetching Week 1 results from ESPN and CFBD APIs...")
    actual_results = results_fetcher.fetch_game_results(week=1, season=2025)
    
    # Create results structure
    results_data = {
        "week": 1,
        "season": 2025,
        "recorded_date": "2025-09-03",
        "results": []
    }
    
    # Match predictions with actual results
    for pred in predictions_data["predictions"]:
        home_team = pred["home_team"]
        away_team = pred["away_team"]
        vegas_spread = pred["vegas_spread"]
        contrarian_spread = pred["contrarian_spread"]
        
        # Find matching result
        game_result = None
        for result in actual_results:
            # Normalize team names for matching
            norm_result_home = team_name_normalizer.normalize(result["home_team"])
            norm_result_away = team_name_normalizer.normalize(result["away_team"])
            norm_pred_home = team_name_normalizer.normalize(home_team)
            norm_pred_away = team_name_normalizer.normalize(away_team)
            
            if (norm_result_home and norm_pred_home and norm_result_away and norm_pred_away and
                norm_result_home.upper() == norm_pred_home.upper() and
                norm_result_away.upper() == norm_pred_away.upper()):
                game_result = result
                break
        
        if game_result:
            home_score = game_result["home_score"]
            away_score = game_result["away_score"]
            actual_spread = home_score - away_score
            
            # Determine if home team covered the spread
            # If vegas_spread is positive, home team is getting points
            # If vegas_spread is negative, home team is giving points
            if vegas_spread > 0:
                # Home team is underdog, getting points
                covered_vegas = actual_spread + vegas_spread > 0
                covered_contrarian = actual_spread + contrarian_spread > 0
            else:
                # Home team is favorite, giving points
                covered_vegas = actual_spread > abs(vegas_spread)
                covered_contrarian = actual_spread > abs(contrarian_spread)
            
            results_data["results"].append({
                "game_id": pred["game_id"],
                "home_team": home_team,
                "away_team": away_team,
                "home_score": home_score,
                "away_score": away_score,
                "actual_spread": actual_spread,
                "vegas_spread": vegas_spread,
                "contrarian_spread": contrarian_spread,
                "home_covered_vegas": covered_vegas,
                "home_covered_contrarian": covered_contrarian,
                "prediction_correct": covered_contrarian if pred["edge_direction"] == "home" else not covered_contrarian,
                "confidence": pred["confidence"],
                "prediction_type": pred["prediction_type"],
                "notes": f"Source: {game_result.get('source', 'Unknown')}"
            })
            
            print(f"✅ {away_team} @ {home_team}: {away_score}-{home_score} (Spread: {actual_spread})")
        else:
            print(f"❌ No result found for {away_team} @ {home_team}")
            results_data["results"].append({
                "game_id": pred["game_id"],
                "home_team": home_team,
                "away_team": away_team,
                "home_score": None,
                "away_score": None,
                "actual_spread": None,
                "vegas_spread": vegas_spread,
                "contrarian_spread": contrarian_spread,
                "home_covered_vegas": None,
                "home_covered_contrarian": None,
                "prediction_correct": None,
                "confidence": pred["confidence"],
                "prediction_type": pred["prediction_type"],
                "notes": "Result not found"
            })
    
    # Calculate summary statistics
    games_with_results = [r for r in results_data["results"] if r["actual_spread"] is not None]
    correct_predictions = [r for r in games_with_results if r["prediction_correct"]]
    
    results_data["summary"] = {
        "total_games": len(results_data["results"]),
        "games_with_results": len(games_with_results),
        "correct_predictions": len(correct_predictions),
        "accuracy": len(correct_predictions) / len(games_with_results) if games_with_results else 0,
        "accuracy_percentage": f"{(len(correct_predictions) / len(games_with_results) * 100):.1f}%" if games_with_results else "N/A"
    }
    
    # Save results
    with open(results_file, 'w') as f:
        json.dump(results_data, f, indent=2)
    
    print(f"\n📊 Summary:")
    print(f"Games tracked: {results_data['summary']['total_games']}")
    print(f"Results found: {results_data['summary']['games_with_results']}")
    print(f"Correct predictions: {results_data['summary']['correct_predictions']}")
    print(f"Accuracy: {results_data['summary']['accuracy_percentage']}")
    print(f"\nResults saved to: {results_file}")

if __name__ == "__main__":
    main()