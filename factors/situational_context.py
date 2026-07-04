"""
Situational context factors for College Football Market Edge Platform.
Implements the four situation-based factors that comprise 40% of prediction weight.
"""

from typing import Dict, Any, Tuple, Optional, List
import logging
from datetime import datetime

from factors.base_calculator import BaseFactorCalculator


class DesperationIndexCalculator(BaseFactorCalculator):
    """
    Calculate desperation index based on playoff/bowl eligibility stakes.
    
    Teams fighting for bowl eligibility, conference championships, or playoff spots
    often perform differently than their season averages suggest.
    """
    
    def __init__(self):
        super().__init__()
        self.weight = 0.10  # 10% of total (25% of situational context's 40%)
        self.category = "situational_context"
        self.description = "Desperation index for bowl/playoff eligibility"
        self._min_output = -2.0
        self._max_output = 2.0
        
        # Configuration
        self.config = {
            'bowl_eligibility_threshold': 6,  # Wins needed for bowl eligibility
            'playoff_contender_threshold': 1,  # Max losses to be playoff contender
            'conference_championship_weeks': [13, 14],  # Weeks for conference championships
            'desperation_multipliers': {
                'elimination_game': 2.0,
                'must_win': 1.5,
                'helpful_win': 1.0,
                'meaningless': 0.3
            }
        }
    
    def calculate(self, home_team: str, away_team: str, context: Optional[Dict[str, Any]] = None) -> float:
        """Calculate desperation index factor."""
        if not context:
            return 0.0
        
        home_data = context.get('home_team_data', {})
        away_data = context.get('away_team_data', {})
        week = context.get('week')

        # Calculate desperation scores for each team from their real W-L record.
        home_desperation = self._calculate_team_desperation(home_data, week)
        away_desperation = self._calculate_team_desperation(away_data, week)

        # Honest-missing (binding principle #4): desperation is a function of a real
        # W-L record. Preseason — and any week whose results aren't yet in the snapshot —
        # has no record, so the differential is not computable. Return 0.0 (no signal),
        # NEVER a fabricated value. The factor is dormant until real records arrive; it is
        # measured for real by Phase-4 attribution in 2026.
        if home_desperation is None or away_desperation is None:
            return 0.0

        # Desperation differential (positive = home team more desperate)
        desperation_diff = home_desperation - away_desperation

        # Scale the differential
        scaled_diff = self._scale_desperation_differential(desperation_diff)

        return self.validate_output(scaled_diff)
    
    def _calculate_team_desperation(self, team_data: Dict, week: Optional[int]) -> Optional[float]:
        """Calculate a team's desperation score from its real W-L record.

        Returns None (honest-missing) when no current record exists — the caller then
        emits no signal. There is deliberately no fabricated fallback (the old MD5-hash /
        hardcoded-team-list simulation was removed in Phase 3c as a binding #2/#4 violation
        and a Bug-#7-class phantom).
        """
        if week is None:
            week = 8  # Default mid-season

        # Get current record
        derived_metrics = team_data.get('derived_metrics', {})
        current_record = derived_metrics.get('current_record', {})

        if not current_record:
            return None

        wins = current_record.get('wins', 0)
        losses = current_record.get('losses', 0)
        games_remaining = max(0, 12 - (wins + losses))  # Estimate games remaining
        
        # Calculate desperation based on different scenarios
        desperation_score = 0.5  # Base neutral score
        
        # Bowl eligibility desperation
        bowl_desperation = self._calculate_bowl_eligibility_desperation(wins, losses, games_remaining, week)
        desperation_score += bowl_desperation * 0.4
        
        # Playoff contender desperation
        playoff_desperation = self._calculate_playoff_desperation(wins, losses, week)
        desperation_score += playoff_desperation * 0.3
        
        # Late season pressure
        late_season_desperation = self._calculate_late_season_pressure(week)
        desperation_score += late_season_desperation * 0.3
        
        return min(max(desperation_score, 0.0), 1.0)
    
    def _calculate_bowl_eligibility_desperation(self, wins: int, losses: int, games_remaining: int, week: int) -> float:
        """Calculate desperation related to bowl eligibility."""
        wins_needed = max(0, self.config['bowl_eligibility_threshold'] - wins)
        
        if wins >= self.config['bowl_eligibility_threshold']:
            return 0.0  # Already bowl eligible
        
        if wins_needed > games_remaining:
            return -0.3  # Eliminated from bowl eligibility
        
        if wins_needed == games_remaining:
            return 0.6  # Must win every remaining game
        
        if wins_needed == 1:
            return 0.4  # Need one more win
        
        return 0.2  # Still in decent shape
    
    def _calculate_playoff_desperation(self, wins: int, losses: int, week: int) -> float:
        """Calculate desperation related to playoff contention."""
        if losses > self.config['playoff_contender_threshold']:
            return 0.0  # Likely out of playoff contention
        
        if week >= 10 and losses == 0:
            return 0.5  # Undefeated, high stakes
        
        if week >= 10 and losses == 1:
            return 0.3  # One loss, still viable
        
        return 0.1  # Early season or not in contention
    
    def _calculate_late_season_pressure(self, week: int) -> float:
        """Calculate late season pressure effects."""
        if week >= 13:
            return 0.4  # Championship week pressure
        elif week >= 11:
            return 0.3  # Late season stakes
        elif week >= 9:
            return 0.2  # Mid-late season
        else:
            return 0.0  # Early season
    
    def _scale_desperation_differential(self, diff: float) -> float:
        """Scale desperation differential to output range."""
        # diff is approximately -0.5 to 0.5, scale to -2.0 to 2.0
        return diff * 4.0
    
    def get_output_range(self) -> Tuple[float, float]:
        """Get output range for desperation index."""
        return (self._min_output, self._max_output)
    
    def get_explanation(self, home_team: str, away_team: str, value: float, 
                       context: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """Generate explanation for desperation index."""
        if abs(value) < 0.2:
            return "Similar desperation levels for both teams"
        
        more_desperate = home_team if value > 0 else away_team
        less_desperate = away_team if value > 0 else home_team
        
        intensity = "slightly" if abs(value) < 1.0 else "significantly"
        
        return f"{more_desperate} is {intensity} more desperate than {less_desperate}"
    
    def get_required_data(self) -> Dict[str, bool]:
        """Desperation index uses team records and week information."""
        return {
            'team_info': False,
            'coaching_data': False,
            'team_stats': False,
            'schedule_data': False,  # Optional for better accuracy
            'betting_data': False,
            'historical_data': False
        }


class RevengeGameCalculator(BaseFactorCalculator):
    """
    Calculate revenge game factor based on previous losses and coaching connections.
    
    Teams often perform differently when facing opponents that beat them recently
    or when there are coaching staff connections/revenge narratives.
    """
    
    def __init__(self):
        super().__init__()
        self.weight = 0.10  # 10% of total (25% of situational context's 40%)
        self.category = "situational_context"
        self.description = "Revenge game and narrative factor analysis"
        self._min_output = -1.5
        self._max_output = 1.5
        
        # Configuration
        self.config = {
            'revenge_timeframes': {
                'last_year': 1.0,
                'two_years_ago': 0.6,
                'three_years_ago': 0.3
            },
            'coaching_connection_weight': 0.7,
            'margin_of_defeat_weight': 0.3,
            'rivalry_amplifier': 1.2
        }
    
    def calculate(self, home_team: str, away_team: str, context: Optional[Dict[str, Any]] = None) -> float:
        """Calculate revenge game factor."""
        if not context:
            return 0.0
        
        # Calculate revenge factors for both teams
        home_revenge = self._calculate_team_revenge_factor(
            home_team, away_team, context, is_home=True
        )
        away_revenge = self._calculate_team_revenge_factor(
            away_team, home_team, context, is_home=False
        )
        
        # Net revenge factor (positive favors home team)
        revenge_differential = home_revenge - away_revenge
        
        return self.validate_output(revenge_differential)
    
    def _calculate_team_revenge_factor(self, team: str, opponent: str, context: Dict, is_home: bool) -> float:
        """Calculate revenge factor for a specific team."""
        revenge_score = 0.0
        
        # Recent loss revenge (placeholder - would need historical data)
        recent_loss_revenge = self._estimate_recent_loss_revenge(team, opponent)
        revenge_score += recent_loss_revenge * 0.5
        
        # Coaching connection revenge
        coaching_revenge = self._estimate_coaching_connections(team, opponent, context)
        revenge_score += coaching_revenge * 0.3
        
        # Narrative/media revenge storylines (estimated)
        narrative_revenge = self._estimate_narrative_revenge(team, opponent, context)
        revenge_score += narrative_revenge * 0.2
        
        return revenge_score
    
    def _estimate_recent_loss_revenge(self, team: str, opponent: str) -> float:
        """Revenge from a recent loss to this opponent.

        Requires real prior-meeting results, which have no data source in 2026 core
        (deferred). Honest-missing (binding #4): 0.0 until that data exists — the old
        hardcoded rivalry table (binding #2 violation, a Bug-#7-class phantom) was
        removed in Phase 3c. With the other sub-signals also unsourced, RevengeGame is
        dormant (0.0) until real prior-meeting data arrives; measured in 2026 (Phase 4).
        """
        return 0.0
    
    def _estimate_coaching_connections(self, team: str, opponent: str, context: Dict) -> float:
        """Estimate revenge factor from coaching connections."""
        # This would analyze if coaches have history at opponent schools,
        # former assistant coaches facing former head coaches, etc.
        
        coaching_comp = context.get('coaching_comparison', {})
        if not coaching_comp:
            return 0.0
        
        # Placeholder for coaching connection analysis
        # Would need database of coaching histories
        return 0.0
    
    def _estimate_narrative_revenge(self, team: str, opponent: str, context: Dict) -> float:
        """Estimate media/narrative revenge storylines."""
        # This could analyze news articles, social media, etc. for revenge narratives
        # For now, just return neutral
        return 0.0
    
    def get_output_range(self) -> Tuple[float, float]:
        """Get output range for revenge game factor."""
        return (self._min_output, self._max_output)
    
    def get_explanation(self, home_team: str, away_team: str, value: float, 
                       context: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """Generate explanation for revenge game factor."""
        if abs(value) < 0.1:
            return "No significant revenge storylines identified"
        
        if value > 0:
            return f"Revenge narrative favors {home_team}"
        else:
            return f"Revenge narrative favors {away_team}"
    
    def get_required_data(self) -> Dict[str, bool]:
        """Revenge games would benefit from historical data."""
        return {
            'team_info': False,
            'coaching_data': False,
            'team_stats': False,
            'schedule_data': False,
            'betting_data': False,
            'historical_data': False  # Would be helpful but not required
        }
