"""
Prediction storage utilities for College Football Market Edge Platform.

Handles saving and loading weekly predictions and performance data.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any, Optional


class PredictionStorage:
    """Handles all prediction and performance data storage operations."""
    
    def __init__(self, base_data_dir: str = None):
        """Initialize storage with base data directory."""
        if base_data_dir is None:
            # Default to data/ directory in project root
            project_root = Path(__file__).parent.parent
            base_data_dir = project_root / "data"
        
        self.base_dir = Path(base_data_dir)
        self.predictions_dir = self.base_dir / "predictions"
        self.results_dir = self.base_dir / "results"
        self.performance_file = self.base_dir / "performance_tracker.json"
        
        # Ensure directories exist
        self.predictions_dir.mkdir(parents=True, exist_ok=True)
        self.results_dir.mkdir(parents=True, exist_ok=True)
    
    def save_weekly_predictions(self, predictions: List[Dict], week: int, season: int = 2025) -> str:
        """
        Save weekly predictions to JSON file.
        
        Args:
            predictions: List of prediction dictionaries
            week: Week number
            season: Season year
            
        Returns:
            Path to saved file
        """
        filename = f"{season}_week_{week:02d}.json"
        filepath = self.predictions_dir / filename
        
        # Calculate summary statistics
        total_games = len(predictions) if predictions else 0
        edges_found = len([p for p in predictions if p.get('predicted_edge', 0) > 0])
        avg_confidence = sum(p.get('confidence', 0) for p in predictions) / max(len(predictions), 1)
        avg_edge = sum(p.get('predicted_edge', 0) for p in predictions) / max(len(predictions), 1)
        
        prediction_data = {
            "week": week,
            "season": season,
            "generated_date": datetime.now(timezone.utc).isoformat(),
            "prediction_count": len(predictions),
            "predictions": predictions,
            "system_stats": {
                "total_games_analyzed": total_games,
                "games_with_edges": edges_found,
                "hit_rate": edges_found / max(total_games, 1),
                "average_confidence": round(avg_confidence, 1),
                "average_edge_size": round(avg_edge, 2)
            }
        }
        
        with open(filepath, 'w') as f:
            json.dump(prediction_data, f, indent=2)
        
        return str(filepath)
    
    def load_weekly_predictions(self, week: int, season: int = 2025) -> Optional[Dict]:
        """
        Load weekly predictions from JSON file.
        
        Args:
            week: Week number
            season: Season year
            
        Returns:
            Prediction data dictionary or None if file doesn't exist
        """
        filename = f"{season}_week_{week:02d}.json"
        filepath = self.predictions_dir / filename
        
        if not filepath.exists():
            return None
        
        with open(filepath, 'r') as f:
            return json.load(f)
    
    def save_weekly_results(self, results: List[Dict], week: int, season: int = 2025) -> str:
        """
        Save weekly game results to JSON file.
        
        Args:
            results: List of game result dictionaries
            week: Week number
            season: Season year
            
        Returns:
            Path to saved file
        """
        filename = f"{season}_week_{week:02d}.json"
        filepath = self.results_dir / filename
        
        result_data = {
            "week": week,
            "season": season,
            "processed_date": datetime.now(timezone.utc).isoformat(),
            "results": results
        }
        
        with open(filepath, 'w') as f:
            json.dump(result_data, f, indent=2)
        
        return str(filepath)
    
    def load_weekly_results(self, week: int, season: int = 2025) -> Optional[Dict]:
        """
        Load weekly results from JSON file.
        
        Args:
            week: Week number
            season: Season year
            
        Returns:
            Results data dictionary or None if file doesn't exist
        """
        filename = f"{season}_week_{week:02d}.json"
        filepath = self.results_dir / filename
        
        if not filepath.exists():
            return None
        
        with open(filepath, 'r') as f:
            return json.load(f)
    
    def load_performance_tracker(self) -> Dict:
        """
        Load the master performance tracking data.
        
        Returns:
            Performance tracker dictionary
        """
        if not self.performance_file.exists():
            # Return default structure if file doesn't exist
            return {
                "last_updated": None,
                "tracking_start_date": None,
                "weeks_tracked": 0,
                "overall_performance": {
                    "total_predictions": 0,
                    "correct_predictions": 0,
                    "win_rate": None,
                    "total_games_analyzed": 0,
                    "prediction_rate": None,
                    "average_edge_size": None,
                    "average_confidence": None
                },
                "weekly_breakdown": {},
                "confidence_analysis": {
                    "80_plus": {"predictions": 0, "wins": 0, "win_rate": None},
                    "70_79": {"predictions": 0, "wins": 0, "win_rate": None},
                    "60_69": {"predictions": 0, "wins": 0, "win_rate": None},
                    "below_60": {"predictions": 0, "wins": 0, "win_rate": None}
                },
                "factor_performance": {},
                "notable_results": []
            }
        
        with open(self.performance_file, 'r') as f:
            return json.load(f)
    
    def save_performance_tracker(self, performance_data: Dict) -> str:
        """
        Save updated performance tracking data.
        
        Args:
            performance_data: Updated performance tracker dictionary
            
        Returns:
            Path to saved file
        """
        performance_data["last_updated"] = datetime.now(timezone.utc).isoformat()
        
        with open(self.performance_file, 'w') as f:
            json.dump(performance_data, f, indent=2)
        
        return str(self.performance_file)
    
    def get_all_prediction_weeks(self, season: int = 2025) -> List[int]:
        """
        Get list of all weeks that have prediction files.
        
        Args:
            season: Season year
            
        Returns:
            Sorted list of week numbers
        """
        weeks = []
        pattern = f"{season}_week_*.json"
        
        for filepath in self.predictions_dir.glob(pattern):
            # Extract week number from filename
            week_str = filepath.stem.split('_')[-1]  # Get "01" from "2025_week_01"
            try:
                weeks.append(int(week_str))
            except ValueError:
                continue
        
        return sorted(weeks)
    
    def create_prediction_entry(self, home_team: str, away_team: str, 
                              vegas_spread: str, predicted_edge: float,
                              confidence: float, recommendation: str,
                              factor_breakdown: Dict, data_quality: float,
                              week: int, rationale: str = "") -> Dict:
        """
        Create a properly formatted prediction entry.
        
        Args:
            home_team: Home team name
            away_team: Away team name
            vegas_spread: Vegas spread (e.g. "Ohio State -7.5")
            predicted_edge: Predicted edge in points
            confidence: Confidence percentage
            recommendation: Betting recommendation (e.g. "Michigan +7.5")
            factor_breakdown: Dictionary of factor contributions
            data_quality: Data quality score
            week: Week number
            rationale: Optional explanation of the bet
            
        Returns:
            Formatted prediction dictionary
        """
        game_id = f"{away_team.lower().replace(' ', '-')}-vs-{home_team.lower().replace(' ', '-')}-week{week}"
        
        return {
            "game_id": game_id,
            "home_team": home_team,
            "away_team": away_team,
            "vegas_spread": vegas_spread,
            "predicted_edge": round(predicted_edge, 2),
            "confidence": round(confidence, 1),
            "recommendation": recommendation,
            "bet_rationale": rationale,
            "factor_breakdown": {k: round(v, 3) for k, v in factor_breakdown.items()},
            "data_quality": round(data_quality, 1)
        }
    
    def list_stored_weeks(self, season: int = 2025) -> Dict[str, List[int]]:
        """
        List all weeks that have stored data.
        
        Args:
            season: Season year
            
        Returns:
            Dictionary with 'predictions' and 'results' lists
        """
        prediction_weeks = self.get_all_prediction_weeks(season)
        
        result_weeks = []
        pattern = f"{season}_week_*.json"
        for filepath in self.results_dir.glob(pattern):
            week_str = filepath.stem.split('_')[-1]
            try:
                result_weeks.append(int(week_str))
            except ValueError:
                continue
        
        return {
            "predictions": sorted(prediction_weeks),
            "results": sorted(result_weeks)
        }


# Convenience instance for easy importing
prediction_storage = PredictionStorage()