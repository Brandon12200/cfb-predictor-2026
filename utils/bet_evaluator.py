"""
Bet evaluation utilities for College Football Market Edge Platform.

Handles logic for determining whether betting predictions were successful.
"""

import re
from typing import Dict, Tuple, Optional


class BetEvaluator:
    """Evaluates betting prediction success against actual game results."""
    
    @staticmethod
    def parse_betting_line(betting_line: str) -> Tuple[str, float, str]:
        """
        Parse a betting line into team, spread, and bet type.
        
        Args:
            betting_line: Line like "Michigan +7.5" or "Ohio State -3"
            
        Returns:
            Tuple of (team_name, spread_value, bet_type)
            bet_type is either "underdog" (+) or "favorite" (-)
        """
        # Handle common formats: "Michigan +7.5", "Ohio State -3", "MICHIGAN +7.5"
        line = betting_line.strip()
        
        # Look for + or - followed by number
        match = re.match(r'^(.+?)\s*([\+\-])(\d+(?:\.\d+)?)$', line)
        
        if not match:
            raise ValueError(f"Could not parse betting line: {betting_line}")
        
        team_name = match.group(1).strip()
        sign = match.group(2)
        spread_value = float(match.group(3))
        
        bet_type = "underdog" if sign == "+" else "favorite"
        
        return team_name, spread_value, bet_type
    
    @staticmethod
    def evaluate_bet(prediction: Dict, game_result: Dict) -> Dict:
        """
        Evaluate whether a betting prediction was successful.
        
        Args:
            prediction: Prediction dictionary with 'recommendation' key
            game_result: Game result with home/away scores and teams
            
        Returns:
            Dictionary with bet evaluation results
        """
        try:
            recommendation = prediction['recommendation']
            home_team = game_result['home_team']
            away_team = game_result['away_team']
            home_score = game_result['home_score']
            away_score = game_result['away_score']
            
            # Parse the recommendation
            bet_team, spread, bet_type = BetEvaluator.parse_betting_line(recommendation)
            
            # Calculate actual margin (positive = home team won)
            actual_margin = home_score - away_score
            
            # Determine if this team is home or away
            is_home_bet = BetEvaluator._normalize_team_name(bet_team) == BetEvaluator._normalize_team_name(home_team)
            is_away_bet = BetEvaluator._normalize_team_name(bet_team) == BetEvaluator._normalize_team_name(away_team)
            
            if not (is_home_bet or is_away_bet):
                raise ValueError(f"Bet team '{bet_team}' doesn't match game teams: {home_team} vs {away_team}")
            
            # Calculate bet result
            if bet_type == "underdog":  # + spread
                if is_home_bet:
                    # Home underdog: home_score + spread > away_score
                    adjusted_score = home_score + spread
                    bet_won = adjusted_score > away_score
                    bet_margin = adjusted_score - away_score
                else:
                    # Away underdog: away_score + spread > home_score
                    adjusted_score = away_score + spread
                    bet_won = adjusted_score > home_score
                    bet_margin = adjusted_score - home_score
            
            else:  # favorite (- spread)
                if is_home_bet:
                    # Home favorite: home_score - spread > away_score
                    adjusted_score = home_score - spread
                    bet_won = adjusted_score > away_score
                    bet_margin = adjusted_score - away_score
                else:
                    # Away favorite: away_score - spread > home_score
                    adjusted_score = away_score - spread
                    bet_won = adjusted_score > home_score
                    bet_margin = adjusted_score - home_score
            
            # Handle pushes (exact ties)
            is_push = abs(bet_margin) < 0.001  # Handle floating point precision
            
            return {
                "bet_won": bet_won and not is_push,
                "is_push": is_push,
                "bet_margin": round(bet_margin, 1),
                "actual_margin": actual_margin,
                "vegas_spread": prediction.get('vegas_spread', 'Unknown'),
                "recommendation": recommendation,
                "game_summary": f"{away_team} {away_score}, {home_team} {home_score}",
                "bet_team": bet_team,
                "spread": spread,
                "bet_type": bet_type
            }
            
        except Exception as e:
            return {
                "bet_won": False,
                "is_push": False,
                "bet_margin": 0.0,
                "actual_margin": 0.0,
                "error": str(e),
                "recommendation": prediction.get('recommendation', 'Unknown'),
                "game_summary": f"Error evaluating bet: {e}"
            }
    
    @staticmethod
    def _normalize_team_name(team_name: str) -> str:
        """
        Normalize team name for comparison.
        
        Args:
            team_name: Team name to normalize
            
        Returns:
            Normalized team name (uppercase, common abbreviations)
        """
        name = team_name.upper().strip()
        
        # Common normalizations
        normalizations = {
            "OHIO ST": "OHIO STATE",
            "OSU": "OHIO STATE",
            "BUCKEYES": "OHIO STATE",
            "MICHIGAN": "MICHIGAN",
            "WOLVERINES": "MICHIGAN",
            "U OF M": "MICHIGAN",
            "BAMA": "ALABAMA",
            "CRIMSON TIDE": "ALABAMA",
            "TIDE": "ALABAMA",
            "TEXAS": "TEXAS",
            "LONGHORNS": "TEXAS",
            "UT": "TEXAS",
            "GEORGIA": "GEORGIA",
            "BULLDOGS": "GEORGIA",
            "UGA": "GEORGIA",
            "CLEMSON": "CLEMSON",
            "TIGERS": "CLEMSON",
            "LSU": "LSU",
            "NOTRE DAME": "NOTRE DAME",
            "ND": "NOTRE DAME",
            "FIGHTING IRISH": "NOTRE DAME"
        }
        
        return normalizations.get(name, name)
    
    @staticmethod
    def calculate_confidence_calibration(predictions: list, results: list) -> Dict:
        """
        Calculate how well confidence scores match actual success rates.
        
        Args:
            predictions: List of prediction dictionaries
            results: List of corresponding bet evaluation results
            
        Returns:
            Dictionary with calibration analysis
        """
        if len(predictions) != len(results):
            raise ValueError("Predictions and results lists must have same length")
        
        confidence_buckets = {
            "80_plus": {"predictions": 0, "wins": 0, "pushes": 0},
            "70_79": {"predictions": 0, "wins": 0, "pushes": 0},
            "60_69": {"predictions": 0, "wins": 0, "pushes": 0},
            "below_60": {"predictions": 0, "wins": 0, "pushes": 0}
        }
        
        for pred, result in zip(predictions, results):
            confidence = pred.get('confidence', 0)
            
            # Determine bucket
            if confidence >= 80:
                bucket = "80_plus"
            elif confidence >= 70:
                bucket = "70_79"
            elif confidence >= 60:
                bucket = "60_69"
            else:
                bucket = "below_60"
            
            confidence_buckets[bucket]["predictions"] += 1
            
            if result.get('bet_won', False):
                confidence_buckets[bucket]["wins"] += 1
            elif result.get('is_push', False):
                confidence_buckets[bucket]["pushes"] += 1
        
        # Calculate win rates
        for bucket_data in confidence_buckets.values():
            total_preds = bucket_data["predictions"]
            if total_preds > 0:
                bucket_data["win_rate"] = bucket_data["wins"] / total_preds
            else:
                bucket_data["win_rate"] = None
        
        return confidence_buckets
    
    @staticmethod
    def generate_bet_summary(prediction: Dict, result: Dict) -> str:
        """
        Generate a human-readable summary of a bet result.
        
        Args:
            prediction: Original prediction
            result: Bet evaluation result
            
        Returns:
            Formatted summary string
        """
        if result.get('error'):
            return f"❌ ERROR: {result['error']}"
        
        status_icon = "✅" if result['bet_won'] else "🟡" if result['is_push'] else "❌"
        recommendation = result['recommendation']
        game_summary = result['game_summary']
        
        if result['is_push']:
            return f"{status_icon} {recommendation} (PUSH: {game_summary})"
        elif result['bet_won']:
            margin = result['bet_margin']
            return f"{status_icon} {recommendation} (Won by {margin}: {game_summary})"
        else:
            margin = abs(result['bet_margin'])
            return f"{status_icon} {recommendation} (Lost by {margin}: {game_summary})"


# Convenience instance for easy importing
bet_evaluator = BetEvaluator()