"""
Style Mismatch Amplifier - SECONDARY contrarian factor.

Identifies matchup-specific advantages based on playing style conflicts.
Public bets on team reputation/rankings, not how styles interact.
Success rate differentials and pace mismatches create hidden edges.
"""

from typing import Dict, Any, Tuple, Optional, List
import logging
from factors.base_calculator import BaseFactorCalculator, FactorType, FactorConfidence


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
        self.weight = 0.15
        self.category = "matchup"
        self.description = "Identifies exploitable style mismatches between teams"
        
        # Output range (Phase 3d, 3c.10): ±1.5 = 0.6× the ratified ~2.5-pt HFA (D9). The old ±4.0
        # (1.6× HFA) was the largest single-factor range in the system — a style/efficiency mismatch
        # is a SECONDARY matchup read and must be capped well below home field; ±1.5 sits alongside
        # the physical factors (bye 1.0, travel cap 1.5).
        # RATIFIED (owner, 2026-07-04; CALIBRATION_LOG 3d.3).
        self._min_output = -1.5
        self._max_output = 1.5

        # Hierarchical system configuration
        self.factor_type = FactorType.SECONDARY
        self.activation_threshold = 0.05  # Very low threshold for advanced stats analysis
        self.max_impact = 1.5
        
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

    def calculate(self, home_team: str, away_team: str, context: Optional[Dict[str, Any]] = None) -> float:
        """Style-mismatch factor — DORMANT FOR ALL OF 2026. RATIFIED (owner, 2026-08-03; B-1).

        **TWO INDEPENDENT BLOCKERS. Removing this return alone does NOT restore the factor.**

        1. **This gate.** `calculate()` returns 0.0 unconditionally for 2026.
        2. **The internals are UNRATIFIED and UNMEASURED.** The ~20 branch constants in
           `_calculate_success_rate_mismatch`, `_calculate_explosiveness_mismatch`,
           `_calculate_run_pass_mismatch` and `_calculate_havoc_mismatch` carry **no** magnitude
           argument in `docs/CALIBRATION_LOG.md` — none could honestly be written against a vehicle
           holding `advanced_stats` for **zero** teams. B8's own PROPOSED text flagged them
           ("~20 internal branch thresholds… 3d ratified only the output range, not the pre-clamp
           weighting"); the ratification never returned to it.

        **Clearing (1) without ratifying (2) restores an UNLOGGED CALIBRATION SURFACE** — the exact
        reverse-coverage failure the 2026-07-09 shakedown existed to close. A **third**, separate
        blocker predates both: the pace component is dormant per 3d.2.

        **Precedent — `MarketSentiment` (B9):** `advanced_stats` **is** still collected into every
        weekly snapshot, so 2027 inherits a full season of real inputs and can back-compute this
        factor offline against actual outcomes before ratifying its internals per-number.
        Activation is earned with evidence, not assumed.

        **NOT deleted, deliberately.** Deletion would change the registered factor count and thus
        the weight-normalisation denominator, moving every other factor's normalized weight — and
        therefore every prediction. The implementation is preserved verbatim below as
        `_calculate_2027_reference()`, uncalled, as the basis for that back-computation. Kept
        registered and honestly dormant (dormancy-as-design, binding principle #4).
        """
        return 0.0

    def _calculate_2027_reference(self, home_team: str, away_team: str,
                                  context: Optional[Dict[str, Any]] = None) -> float:
        """The 2026 implementation, PRESERVED AND UNCALLED for the 2027 back-computation.

        This is the former body of `calculate()`, unchanged. It is not wired to anything while the
        factor is dormant (see `calculate()` for both blockers). Do not call it without first
        ratifying the branch constants it depends on.
        """
        if not context:
            self.logger.debug("No context available for style mismatch")
            return 0.0

        # Advanced season stats come from the snapshot via context (SPEC §5.2), not a
        # live CFBD fetch — current-season only, no prior-season fallback.
        advanced_by_team = context.get('advanced_stats', {})

        # Get advanced stats for both teams
        home_stats = self._get_team_advanced_stats(home_team, advanced_by_team)
        away_stats = self._get_team_advanced_stats(away_team, advanced_by_team)
        
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
    
    def _get_team_advanced_stats(self, team: str,
                                 advanced_by_team: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Read one team's advanced stats from the snapshot's `advanced_stats` map."""
        try:
            team_stats = advanced_by_team.get(str(team).upper())

            if not team_stats:
                self.logger.debug(f"No advanced stats found for {team}")
                return None

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
                
                # Pace metrics: REMOVED in Phase 3d (3c.10). The canonical AdvancedStats payload
                # carries only a raw season `plays` total and no games-played count, so the old
                # `plays / max(1, season)` was a /1 fabrication whose home-vs-away difference fires
                # on total-play-count noise (games played, blowouts, OT), not tempo. The pace
                # component is dormant — see `_calculate_pace_mismatch`.

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
        """DORMANT (Phase 3d, 3c.10 resolution — ratified in CALIBRATION_LOG).

        Tempo mismatch needs a **per-game** pace, but the advanced-stats payload this factor
        consumes has only a raw season `plays` total and no games-played count (games-played is not
        in the factor's data contract). The old formula divided by a non-existent `season` count
        (→ /1) and compared raw totals, whose difference tracks games-played/blowouts, not tempo —
        a Bug-#7-adjacent phantom. Neutralized to 0.0 (no signal); the other five style components
        (real rate stats) carry the factor. Revisit with 2026 attribution in 2027 if tempo earns a
        real per-game signal.
        """
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

        if not context or not context.get('advanced_stats'):
            return value, FactorConfidence.NONE, ["No snapshot advanced stats available"]

        # Determine confidence based on mismatch severity. Bands rescaled to the Phase-3d ±1.5
        # range (3c.10) so the factor uses its full range rather than dead >2.0/>3.0 tiers.
        if abs(value) > 1.2:
            confidence = FactorConfidence.VERY_HIGH
            reasoning.append("Extreme style mismatch identified")
        elif abs(value) > 0.9:
            confidence = FactorConfidence.HIGH
            reasoning.append("Significant style conflict detected")
        elif abs(value) > 0.6:
            confidence = FactorConfidence.MEDIUM
            reasoning.append("Moderate style mismatch found")
        elif abs(value) > 0.3:
            confidence = FactorConfidence.LOW
            reasoning.append("Minor style differential present")
        else:
            confidence = FactorConfidence.NONE
            reasoning.append("No exploitable style mismatch")

        # Add specific mismatch type to reasoning
        if abs(value) > 0.6:
            advanced_by_team = context.get('advanced_stats', {})
            home_stats = self._get_team_advanced_stats(home_team, advanced_by_team)
            away_stats = self._get_team_advanced_stats(away_team, advanced_by_team)

            if home_stats and away_stats:
                success_diff = abs(home_stats['success_rate_off'] - away_stats['success_rate_off'])
                if success_diff > 0.05:
                    reasoning.append("Success rate differential detected")

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
        
        impact = "major" if abs(value) > 0.9 else "moderate" if abs(value) > 0.6 else "notable"
        
        # Identify primary mismatch type
        mismatch_type = "style"
        if context:
            advanced_by_team = context.get('advanced_stats', {})
            home_stats = self._get_team_advanced_stats(home_team, advanced_by_team)
            away_stats = self._get_team_advanced_stats(away_team, advanced_by_team)

            if home_stats and away_stats:
                success_diff = abs(home_stats['success_rate_off'] - away_stats['success_rate_off'])
                if success_diff > 0.08:
                    mismatch_type = "success rate"
                else:
                    mismatch_type = "explosiveness"
        
        return (f"{favored_team} has {impact} {mismatch_type} advantage "
                f"({value:+.1f} points)")
    
    def get_required_data(self) -> Dict[str, bool]:
        """Declare required data."""
        return {
            'team_stats': True,        # Reads snapshot `advanced_stats` from context
            'team_info': False,
            'coaching_data': False,
            'schedule_data': False,
            'betting_data': False,
            'historical_data': False
        }