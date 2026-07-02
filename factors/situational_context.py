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
        
        # Add team names for simulation
        home_data['team_name'] = home_team
        away_data['team_name'] = away_team
        
        # Calculate desperation scores for each team
        home_desperation = self._calculate_team_desperation(home_data, week)
        away_desperation = self._calculate_team_desperation(away_data, week)
        
        # Desperation differential (positive = home team more desperate)
        desperation_diff = home_desperation - away_desperation
        
        # Scale the differential
        scaled_diff = self._scale_desperation_differential(desperation_diff)
        
        return self.validate_output(scaled_diff)
    
    def _calculate_team_desperation(self, team_data: Dict, week: Optional[int]) -> float:
        """Calculate desperation score for a team."""
        if week is None:
            week = 8  # Default mid-season
        
        # Get current record
        derived_metrics = team_data.get('derived_metrics', {})
        current_record = derived_metrics.get('current_record', {})
        
        if not current_record:
            # Simulate desperation based on team and week
            return self._simulate_desperation(team_data.get('team_name', ''), week)
        
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
    
    def _simulate_desperation(self, team_name: str, week: int) -> float:
        """Simulate desperation score based on team and week."""
        import hashlib
        
        if not team_name:
            return 0.5
        
        # Generate team-specific desperation pattern
        team_hash = hashlib.md5(f"{team_name}_desperation_{week}".encode()).hexdigest()
        base_desperation = 0.5  # Neutral base
        
        # Week-based desperation increases
        if week >= 10:
            base_desperation += 0.2  # Late season pressure
        elif week >= 8:
            base_desperation += 0.1
        elif week <= 3:
            base_desperation -= 0.1  # Early season, less desperation
        
        # Team-specific patterns
        # Teams typically fighting for bowl eligibility
        bubble_teams = ['ILLINOIS', 'MARYLAND', 'PURDUE', 'VIRGINIA', 'BOSTON COLLEGE',
                       'DUKE', 'WAKE FOREST', 'KANSAS', 'ARIZONA STATE', 'COLORADO']
        
        # Elite teams with playoff aspirations
        playoff_teams = ['GEORGIA', 'ALABAMA', 'OHIO STATE', 'MICHIGAN', 'TEXAS',
                         'PENN STATE', 'OREGON', 'WASHINGTON', 'FLORIDA STATE']
        
        # Struggling programs
        struggling_teams = ['VANDERBILT', 'KENT STATE', 'UMASS', 'NEW MEXICO STATE',
                           'CONNECTICUT', 'AKRON', 'TEMPLE']
        
        if team_name.upper() in bubble_teams:
            # Bowl bubble teams have high desperation weeks 8-11
            if 8 <= week <= 11:
                base_desperation += 0.3
            else:
                base_desperation += 0.1
        elif team_name.upper() in playoff_teams:
            # Playoff teams have desperation for perfect seasons
            hash_val = int(team_hash[:2], 16)
            if hash_val < 128:  # Simulate undefeated ~50% of time
                base_desperation += 0.25  # Pressure to stay undefeated
            else:
                base_desperation += 0.15  # One-loss pressure
        elif team_name.upper() in struggling_teams:
            # Struggling teams have low desperation (playing for pride)
            base_desperation -= 0.2
        
        # Add team-specific variation
        team_var = (int(team_hash[2:4], 16) % 40 - 20) / 100.0
        
        return min(max(base_desperation + team_var, 0.0), 1.0)
    
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
        """Estimate revenge factor from recent losses."""
        # Placeholder implementation - would need historical game data
        # For now, assign random revenge factors based on team matchups
        
        # Common revenge scenarios (hardcoded examples)
        revenge_scenarios = {
            ('GEORGIA', 'ALABAMA'): 0.3,  # Georgia seeking revenge vs Alabama
            ('ALABAMA', 'GEORGIA'): 0.2,
            ('MICHIGAN', 'OHIO STATE'): 0.4,
            ('OHIO STATE', 'MICHIGAN'): 0.3,
            ('TEXAS', 'OKLAHOMA'): 0.3,
            ('OKLAHOMA', 'TEXAS'): 0.3
        }
        
        return revenge_scenarios.get((team, opponent), 0.0)
    
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


class LookaheadSandwichCalculator(BaseFactorCalculator):
    """
    Calculate lookahead/sandwich game factor based on schedule position.
    
    Teams may overlook current opponent if they have a big game coming up,
    or may be emotionally/physically drained from a recent big game.
    """
    
    def __init__(self):
        super().__init__()
        self.weight = 0.10  # 10% of total (25% of situational context's 40%)
        self.category = "situational_context"
        self.description = "Lookahead and sandwich game analysis"
        self._min_output = -2.0
        self._max_output = 2.0
        
        # Configuration
        self.config = {
            'big_game_thresholds': {
                'rivalry': 2.0,
                'ranked_opponent': 1.5,
                'conference_championship': 2.5,
                'bowl_game': 1.8
            },
            'lookahead_weeks': 2,  # How many weeks ahead to look
            'letdown_weeks': 1,    # How many weeks back to check for letdown
            'opponent_strength_multiplier': 1.2
        }
    
    def calculate(self, home_team: str, away_team: str, context: Optional[Dict[str, Any]] = None) -> float:
        """Calculate lookahead/sandwich factor."""
        if not context:
            return 0.0
        
        home_data = context.get('home_team_data', {})
        away_data = context.get('away_team_data', {})
        week = context.get('week')
        
        # Calculate lookahead/letdown for each team
        home_distraction = self._calculate_team_distraction(home_data, week)
        away_distraction = self._calculate_team_distraction(away_data, week)
        
        # Distraction differential (positive means home team less distracted)
        distraction_diff = away_distraction - home_distraction
        
        return self.validate_output(distraction_diff)
    
    def _calculate_team_distraction(self, team_data: Dict, week: Optional[int]) -> float:
        """Calculate distraction score for a team."""
        if week is None:
            return 0.0
        
        distraction_score = 0.0
        
        # Lookahead distraction (upcoming big games)
        lookahead_score = self._calculate_lookahead_distraction(team_data, week)
        distraction_score += lookahead_score * 0.6
        
        # Letdown distraction (coming off big games)
        letdown_score = self._calculate_letdown_factor(team_data, week)
        distraction_score += letdown_score * 0.4
        
        return distraction_score
    
    def _calculate_lookahead_distraction(self, team_data: Dict, week: int) -> float:
        """Calculate lookahead distraction from upcoming games."""
        # Check for significant upcoming games
        upcoming_games = self._get_upcoming_games(team_data, week)
        
        max_lookahead = 0.0
        for game in upcoming_games:
            game_importance = self._assess_game_importance(game)
            weeks_ahead = game.get('weeks_ahead', 1)
            
            # Closer games have more lookahead effect
            lookahead_effect = game_importance / weeks_ahead
            max_lookahead = max(max_lookahead, lookahead_effect)
        
        return min(max_lookahead, 1.0)
    
    def _calculate_letdown_factor(self, team_data: Dict, week: int) -> float:
        """Calculate letdown factor from recent big games."""
        # Check for recent significant games
        recent_games = self._get_recent_games(team_data, week)
        
        max_letdown = 0.0
        for game in recent_games:
            if game.get('weeks_ago', 2) <= self.config['letdown_weeks']:
                game_importance = self._assess_game_importance(game)
                max_letdown = max(max_letdown, game_importance * 0.7)
        
        return min(max_letdown, 1.0)
    
    def _get_upcoming_games(self, team_data: Dict, current_week: int) -> List[Dict]:
        """Get upcoming games for lookahead analysis."""
        # This would parse the team's schedule for upcoming games
        # For now, return empty list (placeholder)
        return []
    
    def _get_recent_games(self, team_data: Dict, current_week: int) -> List[Dict]:
        """Get recent games for letdown analysis."""
        # This would parse the team's schedule for recent games
        # For now, return empty list (placeholder)
        return []
    
    def _assess_game_importance(self, game: Dict) -> float:
        """Assess the importance/significance of a game."""
        importance = 0.5  # Base importance
        
        # Check for rivalry games, ranked opponents, etc.
        # This would need more sophisticated opponent analysis
        
        return importance
    
    def get_output_range(self) -> Tuple[float, float]:
        """Get output range for lookahead/sandwich factor."""
        return (self._min_output, self._max_output)
    
    def get_explanation(self, home_team: str, away_team: str, value: float, 
                       context: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """Generate explanation for lookahead/sandwich factor."""
        if abs(value) < 0.2:
            return "No significant lookahead or letdown factors"
        
        if value > 0:
            return f"Schedule positioning favors {home_team} (opponent more distracted)"
        else:
            return f"Schedule positioning favors {away_team} (opponent more distracted)"
    
    def get_required_data(self) -> Dict[str, bool]:
        """Lookahead/sandwich analysis benefits from schedule data."""
        return {
            'team_info': False,
            'coaching_data': False,
            'team_stats': False,
            'schedule_data': True,  # Required for schedule analysis
            'betting_data': False,
            'historical_data': False
        }

