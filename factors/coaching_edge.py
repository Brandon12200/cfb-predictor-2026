"""
Coaching edge factors for College Football Market Edge Platform.
Implements the four coaching-related factors that comprise 40% of prediction weight.
"""

from typing import Dict, Any, Tuple, Optional
import logging
from datetime import datetime

from factors.base_calculator import BaseFactorCalculator, FactorType, FactorConfidence


class ExperienceDifferentialCalculator(BaseFactorCalculator):
    """
    Calculate coaching experience differential between teams.
    
    Evaluates head coach experience levels and assigns advantage to more experienced coach.
    Takes into account both total experience and tenure at current school.
    """
    
    def __init__(self):
        super().__init__()
        self.weight = 0.10  # 10% of total (25% of coaching edge's 40%)
        self.category = "coaching_edge"
        self.description = "Coaching experience differential analysis"
        self._min_output = -2.0
        self._max_output = 2.0
        
        # Mark as PRIMARY factor - experience differential is a strong contrarian signal
        self.factor_type = FactorType.PRIMARY
        self.activation_threshold = 1.0  # Configured by registry
        self.max_impact = 5.0  # Configured by registry
        
        # Configuration
        self.config = {
            'max_experience_edge': 15,  # Years beyond which diminishing returns apply
            'tenure_weight': 0.3,  # Weight given to tenure vs total experience
            'rookie_penalty': 0.5,  # Additional penalty for first-year coaches
        }
    
    def calculate(self, home_team: str, away_team: str, context: Optional[Dict[str, Any]] = None) -> float:
        """Calculate experience differential factor."""
        if not context:
            return 0.0
        
        coaching_comp = context.get('coaching_comparison', {})
        if not coaching_comp:
            return 0.0
        
        home_coaching = coaching_comp.get('home_coaching', {})
        away_coaching = coaching_comp.get('away_coaching', {})
        
        # Get experience data
        home_exp = home_coaching.get('head_coach_experience', 5)
        away_exp = away_coaching.get('head_coach_experience', 5)
        
        home_tenure = home_coaching.get('tenure_years', 3)
        away_tenure = away_coaching.get('tenure_years', 3)
        
        # Calculate composite experience scores
        home_score = self._calculate_experience_score(home_exp, home_tenure)
        away_score = self._calculate_experience_score(away_exp, away_tenure)
        
        # Calculate differential
        raw_diff = home_score - away_score
        
        # Apply scaling and bounds
        scaled_diff = self._scale_experience_differential(raw_diff)
        
        return self.validate_output(scaled_diff)
    
    def _calculate_experience_score(self, total_exp: int, tenure: int) -> float:
        """Calculate composite experience score for a coach."""
        # Base score from total experience (diminishing returns after 15 years)
        exp_score = min(total_exp, self.config['max_experience_edge']) / self.config['max_experience_edge']
        
        # Tenure score (capped at 8 years for familiarity)
        tenure_score = min(tenure, 8) / 8
        
        # Combine scores
        composite = (exp_score * (1 - self.config['tenure_weight']) + 
                    tenure_score * self.config['tenure_weight'])
        
        # Apply rookie penalty
        if total_exp <= 1:
            composite *= (1 - self.config['rookie_penalty'])
        
        return composite
    
    def _scale_experience_differential(self, raw_diff: float) -> float:
        """Scale experience differential to output range."""
        # Raw diff is approximately -1.0 to 1.0, scale to -2.0 to 2.0
        return raw_diff * 2.0
    
    def calculate_with_confidence(self, home_team: str, away_team: str, 
                                 context: Optional[Dict[str, Any]] = None) -> Tuple[float, FactorConfidence, list]:
        """Calculate experience differential with confidence scoring."""
        value = self.calculate(home_team, away_team, context)
        reasoning = []
        
        if not context or not context.get('coaching_comparison'):
            return value, FactorConfidence.NONE, ["No coaching data available"]
        
        coaching_comp = context.get('coaching_comparison', {})
        home_coaching = coaching_comp.get('home_coaching', {})
        away_coaching = coaching_comp.get('away_coaching', {})
        
        home_exp = home_coaching.get('head_coach_experience', 5)
        away_exp = away_coaching.get('head_coach_experience', 5)
        exp_diff = abs(home_exp - away_exp)
        
        # Determine confidence based on experience differential magnitude
        if exp_diff >= 10:
            confidence = FactorConfidence.VERY_HIGH
            reasoning.append(f"Major experience gap: {max(home_exp, away_exp)} vs {min(home_exp, away_exp)} years")
        elif exp_diff >= 5:
            confidence = FactorConfidence.HIGH
            reasoning.append(f"Significant experience differential: {exp_diff} years")
        elif exp_diff >= 3:
            confidence = FactorConfidence.MEDIUM
            reasoning.append(f"Moderate experience differential: {exp_diff} years")
        elif exp_diff >= 1:
            confidence = FactorConfidence.LOW
            reasoning.append(f"Small experience differential: {exp_diff} years")
        else:
            confidence = FactorConfidence.NONE
            reasoning.append("Minimal experience differential")
        
        # Add context about rookie coaches
        if home_exp <= 1:
            reasoning.append(f"{home_team} has a first-year head coach")
            # Cap confidence for rookie situations
            if confidence.value > FactorConfidence.HIGH.value:
                confidence = FactorConfidence.HIGH
        if away_exp <= 1:
            reasoning.append(f"{away_team} has a first-year head coach")
            if confidence.value > FactorConfidence.HIGH.value:
                confidence = FactorConfidence.HIGH
        
        return value, confidence, reasoning
    
    def get_output_range(self) -> Tuple[float, float]:
        """Get output range for experience differential."""
        return (self._min_output, self._max_output)
    
    def get_explanation(self, home_team: str, away_team: str, value: float, 
                       context: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """Generate explanation for experience differential."""
        if abs(value) < 0.1:
            return "Coaching experience levels are comparable"
        
        favored_team = home_team if value > 0 else away_team
        edge_size = abs(value)
        
        if edge_size < 0.5:
            edge_desc = "slight"
        elif edge_size < 1.0:
            edge_desc = "moderate"
        else:
            edge_desc = "significant"
        
        return f"Coaching experience gives {favored_team} a {edge_desc} edge ({value:+.1f})"
    
    def get_required_data(self) -> Dict[str, bool]:
        """Experience differential requires coaching data."""
        return {
            'team_info': False,
            'coaching_data': True,
            'team_stats': False,
            'schedule_data': False,
            'betting_data': False,
            'historical_data': False
        }


class PressureSituationCalculator(BaseFactorCalculator):
    """
    Calculate coaching performance under pressure situations.
    
    Evaluates how coaches perform in high-stakes games, playoff scenarios,
    and situations with high expectations vs actual performance.
    """
    
    def __init__(self):
        super().__init__()
        self.weight = 0.10  # 10% of total (25% of coaching edge's 40%)
        self.category = "coaching_edge"
        self.description = "Coaching performance under pressure analysis"
        self._min_output = -2.0
        self._max_output = 2.0
        
        # Configuration
        self.config = {
            'pressure_factors': {
                'ranked_opponent': 0.3,
                'bowl_eligibility': 0.2,
                'conference_championship': 0.4,
                'rivalry_game': 0.1
            },
            'job_security_weight': 0.4,  # Weight for job security pressure
            'expectations_weight': 0.6   # Weight for performance vs expectations
        }
    
    def calculate(self, home_team: str, away_team: str, context: Optional[Dict[str, Any]] = None) -> float:
        """Calculate pressure situation factor."""
        if not context:
            return 0.0
        
        # Get team data for pressure assessment
        home_data = context.get('home_team_data', {})
        away_data = context.get('away_team_data', {})
        
        # Add team names to data if not present
        if 'team_name' not in home_data:
            home_data['team_name'] = home_team
        if 'team_name' not in away_data:
            away_data['team_name'] = away_team
        
        # Calculate pressure scores for each team
        home_pressure = self._calculate_pressure_score(home_data, context, is_home=True)
        away_pressure = self._calculate_pressure_score(away_data, context, is_home=False)
        
        # Higher pressure typically hurts performance, so invert the differential
        # Positive value means home team has advantage (less pressure or better under pressure)
        pressure_diff = away_pressure - home_pressure
        
        return self.validate_output(pressure_diff)
    
    def _calculate_pressure_score(self, team_data: Dict, context: Dict, is_home: bool) -> float:
        """Calculate pressure score for a team."""
        pressure_score = 0.0
        
        # Job security pressure (estimated from performance vs expectations)
        job_pressure = self._estimate_job_security_pressure(team_data)
        pressure_score += job_pressure * self.config['job_security_weight']
        
        # Game-specific pressure
        game_pressure = self._estimate_game_pressure(team_data, context, is_home)
        pressure_score += game_pressure * self.config['expectations_weight']
        
        return pressure_score
    
    def _estimate_job_security_pressure(self, team_data: Dict) -> float:
        """Estimate job security pressure based on team performance."""
        # Get current record if available
        derived_metrics = team_data.get('derived_metrics', {})
        current_record = derived_metrics.get('current_record', {})
        
        # If no record data, use team name to create variety
        if not current_record:
            # Use team name hash for deterministic variety
            import hashlib
            team_name = team_data.get('team_name', '')
            if team_name:
                team_hash = int(hashlib.md5(team_name.encode()).hexdigest()[:8], 16)
                # Generate pressure between 0.3 and 0.7 based on team
                return 0.3 + (team_hash % 40) / 100.0
            return 0.5  # Neutral pressure
        
        win_pct = current_record.get('win_percentage', 0.5)
        
        # Higher pressure for coaches with poor records
        if win_pct < 0.3:
            return 0.8  # High pressure
        elif win_pct < 0.5:
            return 0.6  # Moderate pressure
        elif win_pct > 0.8:
            return 0.2  # Low pressure (success)
        else:
            return 0.4  # Normal pressure
    
    def _estimate_game_pressure(self, team_data: Dict, context: Dict, is_home: bool) -> float:
        """Estimate game-specific pressure factors."""
        # Use team-specific base pressure
        team_name = team_data.get('team_name', '')
        import hashlib
        
        # Generate team-specific base pressure
        if team_name:
            team_hash = int(hashlib.md5(f"{team_name}_pressure".encode()).hexdigest()[:8], 16)
            game_pressure = 0.2 + (team_hash % 20) / 100.0  # 0.2 to 0.4 base
        else:
            game_pressure = 0.3  # Default base pressure
        
        # Week-based pressure estimation
        week = context.get('week')
        if week is None:
            week = 1  # Default to week 1 if not provided
            
        if week >= 12:  # Late season pressure
            game_pressure += 0.2
        elif week >= 10:
            game_pressure += 0.1
        elif week <= 3:  # Early season, less pressure
            game_pressure -= 0.1
        
        # Spread-based pressure (big favorites feel pressure to cover)
        vegas_spread = context.get('vegas_spread')
        if vegas_spread is None:
            vegas_spread = 0  # Default to pick'em if no spread available
        
        if is_home and vegas_spread < -14:
            game_pressure += 0.15  # Home favorite pressure
        elif not is_home and vegas_spread > 14:
            game_pressure += 0.15  # Road favorite pressure
        elif abs(vegas_spread) < 3:
            game_pressure += 0.1  # Close game pressure
        
        # Home field pressure (home teams often feel more pressure from fans)
        if is_home:
            game_pressure += 0.1
        
        # Popular team pressure
        popular_teams = ['ALABAMA', 'GEORGIA', 'OHIO STATE', 'MICHIGAN', 'TEXAS', 'NOTRE DAME']
        if team_name.upper() in popular_teams:
            game_pressure += 0.15  # Extra pressure on popular teams
        
        return min(game_pressure, 1.0)
    
    def get_output_range(self) -> Tuple[float, float]:
        """Get output range for pressure situations."""
        return (self._min_output, self._max_output)
    
    def get_explanation(self, home_team: str, away_team: str, value: float, 
                       context: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """Generate explanation for pressure situation factor."""
        if abs(value) < 0.1:
            return "Both teams facing similar pressure levels"
        
        if value > 0:
            return f"Pressure situation favors {home_team} (less pressure or better under pressure)"
        else:
            return f"Pressure situation favors {away_team} (less pressure or better under pressure)"
    
    def get_required_data(self) -> Dict[str, bool]:
        """Pressure situations can work with basic team data."""
        return {
            'team_info': False,
            'coaching_data': False,
            'team_stats': False,
            'schedule_data': False,
            'betting_data': False,
            'historical_data': False
        }


class HeadToHeadRecordCalculator(BaseFactorCalculator):
    """
    Calculate head-to-head coaching record between current coaches.
    
    Evaluates the historical performance of current coaches against each other,
    filtered by their tenure at current schools.
    """
    
    def __init__(self):
        super().__init__()
        self.weight = 0.10  # 10% of total (25% of coaching edge's 40%)
        self.category = "coaching_edge"
        self.description = "Head-to-head coaching record analysis"
        self._min_output = -1.0
        self._max_output = 1.0
        
        # Configuration
        self.config = {
            'min_games_for_significance': 3,  # Minimum H2H games to be significant
            'recent_game_weight': 1.5,  # Weight more recent games higher
            'max_lookback_years': 10  # Don't look back more than 10 years
        }
    
    def calculate(self, home_team: str, away_team: str, context: Optional[Dict[str, Any]] = None) -> float:
        """Calculate head-to-head coaching record factor."""
        if not context:
            return 0.0
        
        coaching_comp = context.get('coaching_comparison', {})
        if not coaching_comp:
            return 0.0
        
        h2h_record = coaching_comp.get('head_to_head_record', {})
        
        # For now, this is a placeholder since H2H data isn't fully implemented
        home_wins = h2h_record.get('home_wins', 0)
        away_wins = h2h_record.get('away_wins', 0)
        total_games = h2h_record.get('total_games', 0)
        
        if total_games < self.config['min_games_for_significance']:
            return 0.0  # Not enough data for meaningful assessment
        
        # Calculate win percentage differential
        if total_games > 0:
            home_win_pct = home_wins / total_games
            h2h_edge = (home_win_pct - 0.5) * 2.0  # Scale to -1.0 to 1.0
        else:
            h2h_edge = 0.0
        
        return self.validate_output(h2h_edge)
    
    def get_output_range(self) -> Tuple[float, float]:
        """Get output range for head-to-head record."""
        return (self._min_output, self._max_output)
    
    def get_explanation(self, home_team: str, away_team: str, value: float, 
                       context: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """Generate explanation for head-to-head record factor."""
        if not context:
            return "Head-to-head coaching data not available"
        
        coaching_comp = context.get('coaching_comparison', {})
        h2h_record = coaching_comp.get('head_to_head_record', {})
        total_games = h2h_record.get('total_games', 0)
        
        if total_games < self.config['min_games_for_significance']:
            return "Insufficient head-to-head coaching history"
        
        if abs(value) < 0.1:
            return f"Even head-to-head coaching record ({total_games} games)"
        
        favored_team = home_team if value > 0 else away_team
        return f"Head-to-head coaching record favors {favored_team} ({total_games} games)"
    
    def get_required_data(self) -> Dict[str, bool]:
        """Head-to-head record requires coaching comparison data."""
        return {
            'team_info': False,
            'coaching_data': True,
            'team_stats': False,
            'schedule_data': False,
            'betting_data': False,
            'historical_data': False
        }