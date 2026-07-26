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
        self.weight = 0.06  # 10% of total (25% of coaching edge's 40%)
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

        # Honest-missing (binding principle #4): coaching experience must come from real data.
        # `.get(key)` (no default) so a missing OR explicitly-None value stays None — the old
        # `.get(key, 5)` neutral-filled missing coaches to 5 years AND still crashed on a
        # present-None (`min(None, 15)`, the preseason norm). If any of the four inputs is
        # absent/None, the differential is not computable: return 0.0 (no signal), never a
        # fabricated default.
        home_exp = home_coaching.get('head_coach_experience')
        away_exp = away_coaching.get('head_coach_experience')
        home_tenure = home_coaching.get('tenure_years')
        away_tenure = away_coaching.get('tenure_years')
        if None in (home_exp, away_exp, home_tenure, away_tenure):
            return 0.0

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
        
        home_exp = home_coaching.get('head_coach_experience')
        away_exp = away_coaching.get('head_coach_experience')
        if home_exp is None or away_exp is None:
            # Matches calculate()'s honest-missing gate — no fabricated confidence on absent data.
            return value, FactorConfidence.NONE, ["Coaching experience data unavailable"]
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
        self.weight = 0.06  # 10% of total (25% of coaching edge's 40%)
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
        """Coaching-pressure factor — DORMANT. RATIFIED (owner, 2026-07-04; CALIBRATION_LOG 3c.2).

        This factor was almost entirely fabricated: an MD5-hash-of-team-name base pressure,
        a hardcoded ``popular_teams`` list, and a home-field term that double-counted the
        pricer's HFA (binding #2/#4 violations, Bug-#7-class phantom). There is no real
        "coaching pressure" data source in 2026 core, and the honest residue (win%-, week-,
        and spread-based heuristics) overlaps DesperationIndex (record-based motivation) and
        the market factors without earning an independent reasoned coefficient. Rather than
        keep a thin, double-counting heuristic, the factor is dormant — it returns 0.0 (no
        signal, never fabricated) until a genuine coaching-pressure signal exists. Ratified as
        dormant in CALIBRATION_LOG 3c.2 (owner, 2026-07-04); revisit with 2026 attribution in 2027.
        """
        return 0.0
    
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
        self.weight = 0.06  # 10% of total (25% of coaching edge's 40%)
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