"""
Scheduling Fatigue Factor - PRIMARY contrarian factor.

Analyzes cumulative travel, rest patterns, and emotional game impacts that
create hidden performance disadvantages not reflected in betting lines.
Public doesn't systematically track these patterns, creating contrarian value.
"""

from typing import Dict, Any, Tuple, Optional, List
from datetime import datetime, timedelta
import logging
from factors.base_calculator import BaseFactorCalculator, FactorType, FactorConfidence
from data.cfbd_client import get_cfbd_client


class SchedulingFatigueCalculator(BaseFactorCalculator):
    """
    Identifies teams facing hidden fatigue from travel and scheduling patterns.
    
    Contrarian insight: Vegas lines don't adequately account for cumulative
    fatigue from multiple road games, short rest, or emotional game hangover.
    """
    
    def __init__(self):
        super().__init__()
        
        # PRIMARY factor: 33% of PRIMARY category's 60% = 20% total weight
        self.weight = 0.33
        self.category = "situational_context"
        self.description = "Analyzes cumulative travel fatigue and rest disadvantages"
        
        # Output range for this factor
        self._min_output = -3.5
        self._max_output = 3.5
        
        # Hierarchical system configuration
        self.factor_type = FactorType.PRIMARY
        self.activation_threshold = 1.0
        self.max_impact = 3.5
        
        # Factor-specific parameters
        self.config = {
            'road_game_weight': 0.8,        # Weight per road game in last 4 weeks
            'short_rest_weight': 1.5,       # Weight for <7 days rest
            'emotional_game_weight': 0.6,   # Weight for rivalry/OT games
            'timezone_weight': 0.4,         # Weight per timezone crossed
            'lookback_weeks': 4,            # How many weeks to analyze
            'min_games_for_analysis': 2     # Minimum games needed for valid analysis
        }
        
        self.cfbd_client = get_cfbd_client()
    
    def calculate(self, home_team: str, away_team: str, context: Optional[Dict[str, Any]] = None) -> float:
        """
        Calculate scheduling fatigue adjustment.
        
        Positive values indicate home team advantage from away team fatigue.
        Negative values indicate away team advantage from home team fatigue.
        """
        if not context or not self.cfbd_client:
            self.logger.debug("No context or CFBD client available for scheduling fatigue")
            return 0.0
        
        week = context.get('week')
        if week is None:
            week = 1  # Default to week 1 if not provided
        year = context.get('year', 2024)
        
        # Calculate fatigue scores for both teams
        home_fatigue = self._calculate_team_fatigue(home_team, week, year)
        away_fatigue = self._calculate_team_fatigue(away_team, week, year)
        
        # Away team fatigue helps home team (positive adjustment)
        # Home team fatigue helps away team (negative adjustment)
        adjustment = (away_fatigue - home_fatigue) * 0.5
        
        # Log significant findings
        if abs(adjustment) > self.activation_threshold:
            self.logger.info(f"Scheduling fatigue factor: {home_team} vs {away_team}")
            self.logger.info(f"  Home fatigue: {home_fatigue:.1f}, Away fatigue: {away_fatigue:.1f}")
            self.logger.info(f"  Adjustment: {adjustment:+.2f}")
        
        return self.validate_output(adjustment)
    
    def _calculate_team_fatigue(self, team: str, current_week: int, year: int) -> float:
        """Calculate cumulative fatigue score for a team."""
        try:
            # Ensure current_week is valid
            if current_week is None or current_week < 1:
                current_week = 1
            
            # Get recent games for the team
            start_week = max(1, current_week - self.config['lookback_weeks'])
            games = self.cfbd_client.get_games(
                year=year,
                team=team,
                seasonType='regular'
            )
            
            if not games:
                return 0.0
            
            # Filter to recent games before current week
            recent_games = [
                g for g in games 
                if g.get('week', 0) >= start_week and g.get('week', 0) < current_week
            ]
            
            if len(recent_games) < self.config['min_games_for_analysis']:
                return 0.0
            
            fatigue_score = 0.0
            
            # Count road games
            road_games = sum(1 for g in recent_games if self._is_road_game(g, team))
            fatigue_score += road_games * self.config['road_game_weight']
            
            # Check for short rest periods
            for i in range(1, len(recent_games)):
                days_rest = self._calculate_rest_days(recent_games[i-1], recent_games[i])
                if days_rest < 7:
                    fatigue_score += self.config['short_rest_weight']
            
            # Check for emotional games (close games, rivalries, OT)
            emotional_games = sum(1 for g in recent_games if self._is_emotional_game(g, team))
            fatigue_score += emotional_games * self.config['emotional_game_weight']
            
            # Check for timezone travel (simplified - would need venue data for accuracy)
            timezone_changes = self._estimate_timezone_changes(recent_games, team)
            fatigue_score += timezone_changes * self.config['timezone_weight']
            
            return fatigue_score
            
        except Exception as e:
            self.logger.error(f"Error calculating fatigue for {team}: {e}")
            return 0.0
    
    def _is_road_game(self, game: Dict, team: str) -> bool:
        """Check if team played on the road."""
        return game.get('awayTeam', '').upper() == team.upper()
    
    def _calculate_rest_days(self, game1: Dict, game2: Dict) -> int:
        """Calculate days between two games."""
        try:
            date1 = datetime.fromisoformat(game1.get('startDate', '').replace('Z', '+00:00'))
            date2 = datetime.fromisoformat(game2.get('startDate', '').replace('Z', '+00:00'))
            return abs((date2 - date1).days)
        except:
            return 7  # Default to normal rest if can't parse dates
    
    def _is_emotional_game(self, game: Dict, team: str) -> bool:
        """Check if game was emotionally draining (close game, rivalry, OT)."""
        home_score = game.get('homePoints', 0)
        away_score = game.get('awayPoints', 0)
        
        if not home_score and not away_score:
            return False
        
        # Close game (decided by 7 or fewer points)
        margin = abs(home_score - away_score)
        if margin <= 7:
            return True
        
        # Overtime game (scores suggest OT - both teams score high)
        if home_score > 40 and away_score > 40:
            return True
        
        return False
    
    def _estimate_timezone_changes(self, games: List[Dict], team: str) -> int:
        """Estimate timezone changes based on home/away pattern."""
        # Simplified: Count transitions between home and away
        transitions = 0
        for i in range(1, len(games)):
            prev_away = self._is_road_game(games[i-1], team)
            curr_away = self._is_road_game(games[i], team)
            if prev_away != curr_away:
                transitions += 1
        return transitions
    
    def calculate_with_confidence(self, home_team: str, away_team: str, 
                                 context: Optional[Dict[str, Any]] = None) -> Tuple[float, FactorConfidence, List[str]]:
        """Calculate with confidence scoring."""
        value = self.calculate(home_team, away_team, context)
        reasoning = []
        
        if not self.cfbd_client:
            return value, FactorConfidence.NONE, ["CFBD client unavailable"]
        
        # Determine confidence based on signal strength
        if abs(value) > 2.5:
            confidence = FactorConfidence.VERY_HIGH
            reasoning.append("Severe scheduling imbalance detected")
        elif abs(value) > 1.5:
            confidence = FactorConfidence.HIGH
            reasoning.append("Significant fatigue differential found")
        elif abs(value) > 0.8:
            confidence = FactorConfidence.MEDIUM
            reasoning.append("Moderate scheduling advantage identified")
        elif abs(value) > 0.3:
            confidence = FactorConfidence.LOW
            reasoning.append("Minor fatigue factor present")
        else:
            confidence = FactorConfidence.NONE
            reasoning.append("No meaningful scheduling fatigue detected")
        
        return value, confidence, reasoning
    
    def get_output_range(self) -> Tuple[float, float]:
        """Return the output range."""
        return (self._min_output, self._max_output)
    
    def get_explanation(self, home_team: str, away_team: str, value: float, 
                       context: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """Generate human-readable explanation."""
        if abs(value) < 0.1:
            return "No significant scheduling fatigue impact"
        
        favored_team = home_team if value > 0 else away_team
        disadvantaged_team = away_team if value > 0 else home_team
        
        impact = "severe" if abs(value) > 2.5 else "significant" if abs(value) > 1.5 else "moderate"
        
        return (f"{disadvantaged_team} facing {impact} scheduling fatigue - "
                f"{favored_team} advantage ({value:+.1f} points)")
    
    def get_required_data(self) -> Dict[str, bool]:
        """Declare required data."""
        return {
            'schedule_data': False,    # Fetched directly via CFBD
            'team_info': False,
            'coaching_data': False,
            'team_stats': False,
            'betting_data': False,
            'historical_data': False
        }