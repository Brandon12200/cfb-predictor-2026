"""
Style Mismatch Amplifier - SECONDARY contrarian factor.

Identifies matchup-specific advantages based on playing style conflicts.
Public bets on team reputation/rankings, not how styles interact.
Success rate differentials and pace mismatches create hidden edges.
"""

from typing import Dict, Any, Tuple, Optional, List
import logging
from factors.base_calculator import BaseFactorCalculator, FactorType, FactorConfidence
from data.cfbd_client import get_cfbd_client


class StyleMismatchCalculator(BaseFactorCalculator):
    """
    Analyzes style conflicts that create advantages not reflected in spreads.
    
    Contrarian insight: Public focuses on overall team quality, not how
    specific strengths/weaknesses interact. Pace and explosiveness mismatches
    create scoring variance that favors underdogs.
    """
    
    def __init__(self):
        super().__init__()
        
        # SECONDARY factor: 50% of SECONDARY category's 30% = 15% total weight
        self.weight = 0.50
        self.category = "situational_context"
        self.description = "Identifies exploitable style mismatches between teams"
        
        # Output range for this factor
        self._min_output = -4.0
        self._max_output = 4.0
        
        # Hierarchical system configuration
        self.factor_type = FactorType.SECONDARY
        self.activation_threshold = 0.05  # Very low threshold for advanced stats analysis
        self.max_impact = 4.0
        
        # Factor-specific parameters
        self.config = {
            'success_rate_weight': 2.0,      # Most predictive metric
            'explosiveness_weight': 1.5,     # Big play differential
            'pace_mismatch_weight': 1.2,     # Tempo conflicts
            'redzone_weight': 1.0,           # Scoring efficiency
            'havoc_weight': 0.8,             # Chaos generation
            'min_success_diff': 0.05,       # 5% success rate difference threshold
            'pace_advantage_slower': 0.3     # Slower team advantage in mismatches
        }
        
        self.cfbd_client = get_cfbd_client()
    
    def calculate(self, home_team: str, away_team: str, context: Optional[Dict[str, Any]] = None) -> float:
        """
        Calculate style mismatch adjustment.
        
        Positive values indicate home team style advantage.
        Negative values indicate away team style advantage.
        """
        if not context or not self.cfbd_client:
            self.logger.debug("No context or CFBD client available for style mismatch")
            return 0.0
        
        year = context.get('year', 2024)
        
        # For 2025 data, fall back to 2024 for advanced stats analysis
        if year >= 2025:
            year = 2024
        
        # Get advanced stats for both teams
        home_stats = self._get_team_advanced_stats(home_team, year)
        away_stats = self._get_team_advanced_stats(away_team, year)
        
        if not home_stats or not away_stats:
            self.logger.debug(f"Insufficient advanced stats for {home_team} vs {away_team}")
            return 0.0
        
        # Calculate individual mismatch components
        success_mismatch = self._calculate_success_rate_mismatch(home_stats, away_stats)
        explosiveness_mismatch = self._calculate_explosiveness_mismatch(home_stats, away_stats)
        pace_mismatch = self._calculate_pace_mismatch(home_stats, away_stats)
        style_mismatch = self._calculate_run_pass_mismatch(home_stats, away_stats)
        havoc_mismatch = self._calculate_havoc_mismatch(home_stats, away_stats)
        
        # Weighted combination (updated weights for better analysis)
        adjustment = (
            success_mismatch * self.config['success_rate_weight'] +
            explosiveness_mismatch * self.config['explosiveness_weight'] +
            pace_mismatch * self.config['pace_mismatch_weight'] +
            style_mismatch * 1.0 +  # New style mismatch component
            havoc_mismatch * self.config['havoc_weight']
        ) / 6.0  # Normalize by total weights
        
        # Log significant findings
        if abs(adjustment) > self.activation_threshold:
            self.logger.info(f"Style mismatch detected: {home_team} vs {away_team}")
            self.logger.info(f"  Success: {success_mismatch:+.2f}, Explosive: {explosiveness_mismatch:+.2f}")
            self.logger.info(f"  Pace: {pace_mismatch:+.2f}, Style: {style_mismatch:+.2f}, Havoc: {havoc_mismatch:+.2f}")
            self.logger.info(f"  Total adjustment: {adjustment:+.2f}")
        
        return self.validate_output(adjustment)
    
    def _get_team_advanced_stats(self, team: str, year: int) -> Optional[Dict[str, Any]]:
        """Fetch advanced statistics for a team using real CFBD data."""
        try:
            # Get advanced stats from CFBD API
            advanced_stats = self.cfbd_client.get_advanced_stats(year=year, team=team)
            
            if not advanced_stats:
                self.logger.debug(f"No advanced stats found for {team} in {year}")
                return None
            
            # Extract the team's stats (first record should be the team we requested)
            team_stats = advanced_stats[0]
            offense = team_stats.get('offense', {})
            defense = team_stats.get('defense', {})
            
            # Extract the key metrics for style mismatch analysis
            advanced_metrics = {
                # Overall success rates (most predictive)
                'success_rate_off': offense.get('successRate', 0.40),
                'success_rate_def': defense.get('successRate', 0.40),
                
                # Explosiveness (big play rates)
                'explosiveness_off': offense.get('explosiveness', 1.0),
                'explosiveness_def': defense.get('explosiveness', 1.0),
                
                # PPA (Points Per Attempt) - efficiency metric
                'ppa_off': offense.get('ppa', 0.0),
                'ppa_def': defense.get('ppa', 0.0),
                
                # Pace metrics
                'plays_per_game': offense.get('plays', 70) / max(1, team_stats.get('season', 1)),  # Estimate PPG
                
                # Havoc rate (chaos generation)
                'havoc_rate': defense.get('havoc', {}).get('total', 0.15),
                
                # Situational metrics
                'standard_downs_success_off': offense.get('standardDowns', {}).get('successRate', 0.45),
                'passing_downs_success_off': offense.get('passingDowns', {}).get('successRate', 0.25),
                'standard_downs_success_def': defense.get('standardDowns', {}).get('successRate', 0.45),
                'passing_downs_success_def': defense.get('passingDowns', {}).get('successRate', 0.25),
                
                # Rushing vs Passing efficiency
                'rushing_success_off': offense.get('rushingPlays', {}).get('successRate', 0.40),
                'passing_success_off': offense.get('passingPlays', {}).get('successRate', 0.50),
                'rushing_success_def': defense.get('rushingPlays', {}).get('successRate', 0.40),
                'passing_success_def': defense.get('passingPlays', {}).get('successRate', 0.50),
                
                # Power/Stuff rates for short yardage
                'power_success_off': offense.get('powerSuccess', 0.70),
                'stuff_rate_def': defense.get('stuffRate', 0.15)
            }
            
            self.logger.debug(f"Retrieved advanced stats for {team}: Success Rate {advanced_metrics['success_rate_off']:.3f} off, {advanced_metrics['success_rate_def']:.3f} def")
            
            return advanced_metrics
            
        except Exception as e:
            self.logger.error(f"Error fetching advanced stats for {team}: {e}")
            return None
    
    def _calculate_success_rate_mismatch(self, home_stats: Dict, away_stats: Dict) -> float:
        """
        Success rate differential is the most predictive advanced metric.
        Analyze overall success rates plus situational breakdowns.
        """
        mismatches = []
        
        # Overall success rate matchup
        home_off_advantage = home_stats['success_rate_off'] - away_stats['success_rate_def']
        away_off_advantage = away_stats['success_rate_off'] - home_stats['success_rate_def']
        overall_advantage = home_off_advantage - away_off_advantage
        
        if abs(overall_advantage) > self.config['min_success_diff']:
            mismatches.append(('overall', overall_advantage * 8))  # Primary weight
        
        # Standard downs success rate (early down efficiency)
        home_std_advantage = home_stats['standard_downs_success_off'] - away_stats['standard_downs_success_def']
        away_std_advantage = away_stats['standard_downs_success_off'] - home_stats['standard_downs_success_def']
        std_advantage = home_std_advantage - away_std_advantage
        
        if abs(std_advantage) > 0.05:  # 5% threshold for situational stats
            mismatches.append(('standard_downs', std_advantage * 4))
        
        # Passing downs success rate (3rd downs, clutch situations)
        home_pass_advantage = home_stats['passing_downs_success_off'] - away_stats['passing_downs_success_def']
        away_pass_advantage = away_stats['passing_downs_success_off'] - home_stats['passing_downs_success_def']
        pass_advantage = home_pass_advantage - away_pass_advantage
        
        if abs(pass_advantage) > 0.05:
            mismatches.append(('passing_downs', pass_advantage * 6))  # More weight for clutch situations
        
        # Log significant mismatches
        if mismatches:
            self.logger.debug(f"Success rate mismatches detected: {[f'{name}: {val:+.2f}' for name, val in mismatches]}")
        
        # Return weighted average of mismatches
        if mismatches:
            return sum(val for _, val in mismatches) / len(mismatches)
        return 0.0
    
    def _calculate_explosiveness_mismatch(self, home_stats: Dict, away_stats: Dict) -> float:
        """
        Explosiveness mismatches create high variance, which helps underdogs.
        Analyze explosive play differential and PPA efficiency.
        """
        mismatches = []
        
        # Explosive play rate differential
        home_exp_advantage = home_stats['explosiveness_off'] - away_stats['explosiveness_def']
        away_exp_advantage = away_stats['explosiveness_off'] - home_stats['explosiveness_def']
        exp_differential = home_exp_advantage - away_exp_advantage
        
        if abs(exp_differential) > 0.5:  # Significant explosiveness gap
            mismatches.append(('explosiveness', exp_differential * 1.5))
        
        # PPA (Points Per Attempt) efficiency differential
        home_ppa_advantage = home_stats['ppa_off'] - away_stats['ppa_def']
        away_ppa_advantage = away_stats['ppa_off'] - home_stats['ppa_def']
        ppa_differential = home_ppa_advantage - away_ppa_advantage
        
        if abs(ppa_differential) > 0.1:  # PPA differences matter
            mismatches.append(('ppa_efficiency', ppa_differential * 3))
        
        # High variance bonus (helps underdogs in chaotic games)
        total_explosiveness = home_stats['explosiveness_off'] + away_stats['explosiveness_off']
        if total_explosiveness > 3.0:  # Both teams explosive
            # Slight underdog advantage in high-variance games
            variance_bonus = -0.3 if exp_differential > 0 else 0.3
            mismatches.append(('variance_bonus', variance_bonus))
        
        # Log significant mismatches
        if mismatches:
            self.logger.debug(f"Explosiveness mismatches: {[f'{name}: {val:+.2f}' for name, val in mismatches]}")
        
        if mismatches:
            return sum(val for _, val in mismatches) / len(mismatches)
        return 0.0
    
    def _calculate_pace_mismatch(self, home_stats: Dict, away_stats: Dict) -> float:
        """
        Pace mismatches favor slower teams (more control, less variance).
        Fast vs slow creates opportunities for time management.
        """
        home_pace = home_stats['plays_per_game']
        away_pace = away_stats['plays_per_game']
        
        pace_diff = abs(home_pace - away_pace)
        
        # Significant pace mismatch (>10 plays per game difference)
        if pace_diff > 10:
            # Slower team gets advantage
            if home_pace < away_pace:
                return self.config['pace_advantage_slower']
            else:
                return -self.config['pace_advantage_slower']
        
        return 0.0
    
    def _calculate_run_pass_mismatch(self, home_stats: Dict, away_stats: Dict) -> float:
        """
        Analyze rushing vs passing style mismatches.
        Some teams are built to stop the run but weak vs pass and vice versa.
        """
        mismatches = []
        
        # Rushing attack vs run defense
        home_run_advantage = home_stats['rushing_success_off'] - away_stats['rushing_success_def']
        away_run_advantage = away_stats['rushing_success_off'] - home_stats['rushing_success_def']
        run_differential = home_run_advantage - away_run_advantage
        
        if abs(run_differential) > 0.08:  # 8% rushing success rate gap
            mismatches.append(('rushing_mismatch', run_differential * 4))
        
        # Passing attack vs pass defense
        home_pass_advantage = home_stats['passing_success_off'] - away_stats['passing_success_def']
        away_pass_advantage = away_stats['passing_success_off'] - home_stats['passing_success_def']
        pass_differential = home_pass_advantage - away_pass_advantage
        
        if abs(pass_differential) > 0.08:  # 8% passing success rate gap
            mismatches.append(('passing_mismatch', pass_differential * 4))
        
        # Power success vs stuff rate (short yardage situations)
        home_power_advantage = home_stats['power_success_off'] - (away_stats['stuff_rate_def'] * 2)  # Convert stuff rate to power resistance
        away_power_advantage = away_stats['power_success_off'] - (home_stats['stuff_rate_def'] * 2)
        power_differential = home_power_advantage - away_power_advantage
        
        if abs(power_differential) > 0.15:  # 15% power differential
            mismatches.append(('power_mismatch', power_differential * 2))
        
        # Log significant style mismatches
        if mismatches:
            self.logger.debug(f"Run/Pass style mismatches: {[f'{name}: {val:+.2f}' for name, val in mismatches]}")
        
        if mismatches:
            return sum(val for _, val in mismatches) / len(mismatches)
        return 0.0
    
    
    def _calculate_havoc_mismatch(self, home_stats: Dict, away_stats: Dict) -> float:
        """
        Havoc rate (TFL, sacks, turnovers) creates chaos that helps underdogs.
        High havoc games have more variance.
        """
        home_havoc = home_stats['havoc_rate']
        away_havoc = away_stats['havoc_rate']
        
        # Combined havoc rate
        total_havoc = (home_havoc + away_havoc) / 2
        
        # High havoc games favor underdogs
        if total_havoc > 0.20:  # Top quartile havoc
            # Slight underdog advantage (typically away)
            return -0.3
        elif home_havoc > away_havoc * 1.3:
            return 0.5
        elif away_havoc > home_havoc * 1.3:
            return -0.5
        
        return 0.0
    
    def calculate_with_confidence(self, home_team: str, away_team: str, 
                                 context: Optional[Dict[str, Any]] = None) -> Tuple[float, FactorConfidence, List[str]]:
        """Calculate with confidence scoring."""
        value = self.calculate(home_team, away_team, context)
        reasoning = []
        
        if not self.cfbd_client:
            return value, FactorConfidence.NONE, ["CFBD client unavailable"]
        
        # Determine confidence based on mismatch severity
        if abs(value) > 3.0:
            confidence = FactorConfidence.VERY_HIGH
            reasoning.append("Extreme style mismatch identified")
        elif abs(value) > 2.0:
            confidence = FactorConfidence.HIGH
            reasoning.append("Significant style conflict detected")
        elif abs(value) > 1.0:
            confidence = FactorConfidence.MEDIUM
            reasoning.append("Moderate style mismatch found")
        elif abs(value) > 0.5:
            confidence = FactorConfidence.LOW
            reasoning.append("Minor style differential present")
        else:
            confidence = FactorConfidence.NONE
            reasoning.append("No exploitable style mismatch")
        
        # Add specific mismatch type to reasoning
        if abs(value) > 1.0:
            year = context.get('year', 2024) if context else 2024
            home_stats = self._get_team_advanced_stats(home_team, year)
            away_stats = self._get_team_advanced_stats(away_team, year)
            
            if home_stats and away_stats:
                success_diff = abs(home_stats['success_rate_off'] - away_stats['success_rate_off'])
                if success_diff > 0.05:
                    reasoning.append("Success rate differential detected")
                
                pace_diff = abs(home_stats['plays_per_game'] - away_stats['plays_per_game'])
                if pace_diff > 10:
                    reasoning.append("Pace mismatch advantage")
        
        return value, confidence, reasoning
    
    def get_output_range(self) -> Tuple[float, float]:
        """Return the output range."""
        return (self._min_output, self._max_output)
    
    def get_explanation(self, home_team: str, away_team: str, value: float, 
                       context: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """Generate human-readable explanation."""
        if abs(value) < 0.1:
            return "No significant style mismatch impact"
        
        favored_team = home_team if value > 0 else away_team
        
        impact = "extreme" if abs(value) > 3.0 else "major" if abs(value) > 2.0 else "notable"
        
        # Identify primary mismatch type
        mismatch_type = "style"
        if context:
            year = context.get('year', 2024)
            home_stats = self._get_team_advanced_stats(home_team, year)
            away_stats = self._get_team_advanced_stats(away_team, year)
            
            if home_stats and away_stats:
                success_diff = abs(home_stats['success_rate_off'] - away_stats['success_rate_off'])
                pace_diff = abs(home_stats['plays_per_game'] - away_stats['plays_per_game'])
                
                if success_diff > 0.08:
                    mismatch_type = "success rate"
                elif pace_diff > 15:
                    mismatch_type = "pace"
                else:
                    mismatch_type = "explosiveness"
        
        return (f"{favored_team} has {impact} {mismatch_type} advantage "
                f"({value:+.1f} points)")
    
    def get_required_data(self) -> Dict[str, bool]:
        """Declare required data."""
        return {
            'team_stats': False,       # Fetched directly via CFBD advanced stats
            'team_info': False,
            'coaching_data': False,
            'schedule_data': False,
            'betting_data': False,
            'historical_data': False
        }