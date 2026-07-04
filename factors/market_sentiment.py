"""
Market Sentiment Divergence - MODIFIER contrarian factor.

Detects when sharp money moves against public betting patterns.
Reverse line movement and steam moves indicate informed betting
that contradicts recreational money flow.
"""

from typing import Dict, Any, Tuple, Optional, List
from datetime import datetime, timedelta
import logging
from factors.base_calculator import BaseFactorCalculator, FactorType, FactorConfidence
# from data.odds_client import get_odds_client  # TODO: Add when odds client has get_odds_client function


class MarketSentimentCalculator(BaseFactorCalculator):
    """
    Identifies sharp vs public money divergence in betting markets.
    
    Contrarian insight: When line movement opposes public betting percentages,
    sharp money is taking a position against recreational bettors. This creates
    opportunities to fade the public and follow professional money.
    """
    
    def __init__(self):
        super().__init__()
        
        # MODIFIER factor: 100% of MODIFIER category's 10% = 10% total weight
        self.weight = 0.10
        self.category = "market"
        self.description = "Detects sharp money moving against public sentiment"
        
        # Multiplicative modifier: its value IS the multiplier applied to total_adjustment
        # (D19). MODIFIER weights are inert by design — the calibration is the RANGE, not a weight.
        self.is_multiplicative = True
        # Output range (the dormant cap for slice 1.5). Ratified 2026-07-03: a fabrication-history
        # factor with mostly-missing inputs gets a tight cap; widen in 2027 with attribution.
        self._min_output = 0.85  # Can dampen the model edge by 15%
        self._max_output = 1.15  # Can amplify the model edge by 15%

        # Hierarchical system configuration
        self.factor_type = FactorType.MODIFIER
        self.activation_threshold = 0.1  # Low threshold for modifiers
        self.max_impact = 2.5  # Maximum points impact after multiplication
        
        # Factor-specific parameters
        self.config = {
            'reverse_movement_threshold': 0.7,    # 70% public on one side
            'line_move_threshold': 0.5,          # Half point line movement
            'steam_move_threshold': 1.0,         # 1 point rapid movement
            'steam_time_window': 6,              # Hours for steam move detection
            'sharp_indicator_weight': 0.4,       # Weight for sharp indicators
            'public_fade_weight': 0.3,           # Weight for fading public
            'line_freeze_signal': 0.2            # Weight for suspicious line freezes
        }
        # Public-betting % has no free data source; the heuristic proxy below is
        # gated on this staying None (no live odds client in the factor).
        self.odds_client = None

    def _game_book_lines(self, home_team: str, away_team: str,
                         context: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """This game's per-book lines from the snapshot's `betting_lines` (via context).

        Each entry has `spread` (current, from the Odds API) and `spread_open`. Line-
        movement history is deferred to slice 1.5 (D6/SCHEMA §4): `spread_open` is
        absent in core Phase 1, so movement detectors below find no movement and
        return 0.0 — an honest `missing`, distinct from a real movement of 0. That
        missing-movement state also lowers this factor's confidence (see
        `calculate_with_confidence`); it is never fabricated.
        """
        if not context:
            return []
        key = f"{str(away_team).upper()}@{str(home_team).upper()}"
        # The snapshot's betting_lines hold the frozen prediction-time observation (1c);
        # the full as-of-T series lives in the append-only data/lines/ store.
        entry = context.get('betting_lines', {}).get(key, {})
        observation = entry.get('observation') or {}
        return observation.get('lines', [])

    def _has_line_movement(self, home_team: str, away_team: str,
                           context: Optional[Dict[str, Any]]) -> bool:
        """True only if a book carries an opening spread (movement is computable)."""
        return any(ln.get('spread_open') is not None
                   for ln in self._game_book_lines(home_team, away_team, context))
    
    def calculate(self, home_team: str, away_team: str, context: Optional[Dict[str, Any]] = None) -> float:
        """
        Calculate market sentiment modifier.
        
        Returns a multiplier (0.5 to 1.5) that modifies other adjustments.
        1.0 = neutral, >1.0 amplifies contrarian signal, <1.0 reduces it.
        """
        if not context:
            return 1.0  # Neutral modifier if no context
        
        # Get current vegas spread from context
        vegas_spread = context.get('vegas_spread')
        
        # If no spread available, try to get it from CFBD line data
        if vegas_spread is None:
            cfbd_spread = self._get_cfbd_current_spread(home_team, away_team, context)
            if cfbd_spread:
                vegas_spread = cfbd_spread
            else:
                return 1.0  # Can't analyze without any spread data

        # Honest gate (D19, binding principle #4): real market sentiment needs line-movement
        # history, which is deferred to slice 1.5 (D6/SCHEMA §4). Absent it, the factor is
        # DORMANT — a neutral 1.0 (no effect on the model edge), NEVER a signal manufactured
        # from a team-name hash or spread/week heuristics. The multiplier activates only once
        # real movement data exists; the tightened range is its cap for that day.
        if not self._has_line_movement(home_team, away_team, context):
            return 1.0

        sentiment_score = self._analyze_game_sentiment(home_team, away_team, vegas_spread, context)

        # Map the [-1, 1] real-movement sentiment into the ratified [0.85, 1.15] multiplier cap.
        modifier = 1.0 + (sentiment_score * (self._max_output - 1.0))

        if abs(modifier - 1.0) > 0.05:
            sentiment_type = "amplifies" if modifier > 1.0 else "dampens"
            self.logger.debug(f"Market sentiment {sentiment_type} the model edge for {home_team} vs {away_team} (×{modifier:.2f})")

        return max(self._min_output, min(self._max_output, modifier))
    
    def _analyze_game_sentiment(self, home_team: str, away_team: str,
                               vegas_spread: float, context: Dict) -> float:
        """
        Sentiment score from REAL market signals only: -1.0 to +1.0
        (positive = amplify the model edge, negative = dampen it).

        Only reached once real line-movement data exists (``calculate`` gates on it). No
        game-characteristic heuristics and no team-name hash — those manufactured signal from
        nothing and are removed (D19, binding principle #4).
        """
        sentiment_factors = []

        line_movement_signal = self._detect_actual_line_movement(home_team, away_team, context)
        if line_movement_signal != 0.0:
            sentiment_factors.append(line_movement_signal)
            self.logger.debug(f"Line movement signal: {line_movement_signal:.2f} for {away_team} @ {home_team}")

        trap_signal = self._detect_line_freeze(home_team, away_team, context)
        if trap_signal > 0.0:
            sentiment_factors.append(trap_signal * 0.8)  # Strong contrarian signal
            self.logger.debug(f"Trap game signal: {trap_signal:.2f} for {away_team} @ {home_team}")

        if not sentiment_factors:
            return 0.0
        return max(-1.0, min(1.0, sum(sentiment_factors) / len(sentiment_factors)))
    
    def _detect_actual_line_movement(self, home_team: str, away_team: str, context: Dict) -> float:
        """
        Detect actual line movement using CFBD betting lines data.
        
        Returns:
            -1.0 to +1.0 based on line movement patterns
            Positive = line moved toward underdog (contrarian signal)
            Negative = line moved toward favorite (public money)
        """
        try:
            # Book lines come from the snapshot via context, not a live fetch.
            game_lines = self._game_book_lines(home_team, away_team, context)
            if not game_lines:
                return 0.0

            # Analyze line movement across multiple books. In core Phase 1 no book
            # carries an opening spread (movement history deferred, D6), so this yields
            # no signal — honest missing, not a fabricated 0.
            movement_signals = []

            for book_line in game_lines:
                current_spread = book_line.get('spread')
                opening_spread = book_line.get('spread_open')
                
                if current_spread is not None and opening_spread is not None:
                    movement = current_spread - opening_spread
                    
                    # Convert movement to sentiment signal
                    movement_signal = self._interpret_line_movement(movement, current_spread)
                    movement_signals.append(movement_signal)
                    
                    provider = book_line.get('provider', 'Unknown')
                    self.logger.debug(f"{provider}: {opening_spread} → {current_spread} (movement: {movement:+.1f})")
            
            if not movement_signals:
                return 0.0
            
            # Average across all available books
            avg_movement_signal = sum(movement_signals) / len(movement_signals)
            
            # Log significant line movement
            if abs(avg_movement_signal) > 0.3:
                direction = "toward underdog" if avg_movement_signal > 0 else "toward favorite"
                self.logger.info(f"Significant line movement {direction} detected: {away_team} @ {home_team}")
            
            return avg_movement_signal
            
        except Exception as e:
            self.logger.error(f"Error detecting line movement for {away_team} @ {home_team}: {e}")
            return 0.0
    
    def _interpret_line_movement(self, movement: float, current_spread: float) -> float:
        """
        Interpret line movement magnitude and direction.
        
        Args:
            movement: Points moved (positive = line moved toward favorite)
            current_spread: Current spread for context
            
        Returns:
            Sentiment signal (-1.0 to +1.0)
        """
        # Determine movement magnitude categories
        abs_movement = abs(movement)
        
        if abs_movement < 0.5:
            return 0.0  # No significant movement
        
        # Calculate base signal strength
        if abs_movement >= 2.0:
            signal_strength = 1.0      # Strong movement
        elif abs_movement >= 1.0:
            signal_strength = 0.7      # Moderate movement  
        else:
            signal_strength = 0.4      # Slight movement
        
        # Interpret direction (contrarian perspective)
        if movement > 0:
            # Line moved toward favorite (public money pushed it)
            # This creates contrarian value on the underdog
            return signal_strength
        else:
            # Line moved toward underdog (sharp money)
            # Market is becoming more efficient, less contrarian value
            return -signal_strength * 0.5  # Reduced penalty for sharp action
    
    def _get_cfbd_current_spread(self, home_team: str, away_team: str, context: Dict) -> Optional[float]:
        """
        Get current spread from CFBD betting lines when main odds API unavailable.
        
        Returns the current spread (positive = away team favored)
        """
        try:
            game_lines = self._game_book_lines(home_team, away_team, context)
            for book_line in game_lines:
                current_spread = book_line.get('spread')
                if current_spread is not None:
                    self.logger.debug(f"Using snapshot spread: {current_spread} for {away_team} @ {home_team}")
                    return current_spread
            return None
        except Exception as e:
            self.logger.error(f"Error reading snapshot spread for {away_team} @ {home_team}: {e}")
            return None
    
    def _detect_steam_moves(self, home_team: str, away_team: str, context: Dict) -> float:
        """
        Detect rapid line movement indicating sharp action.
        Steam moves show professional money hitting a number hard.
        """
        try:
            # Cross-book spread dispersion is a proxy for steam; it uses only current
            # book spreads (no movement history), so it works from the snapshot.
            game_lines = self._game_book_lines(home_team, away_team, context)
            if not game_lines:
                return 0.0

            spreads = [ln.get('spread') for ln in game_lines if ln.get('spread') is not None]
            if len(spreads) > 1:
                spread_range = max(spreads) - min(spreads)
                if spread_range > self.config['steam_move_threshold']:
                    return 1.0  # Steam move detected
                elif spread_range > self.config['steam_move_threshold'] * 0.5:
                    return 0.5  # Moderate movement

            return 0.0

        except Exception as e:
            self.logger.error(f"Error detecting steam moves: {e}")
            return 0.0
    
    def _detect_line_freeze(self, home_team: str, away_team: str, context: Dict) -> float:
        """Detect suspicious line freezes / trap games.

        This needs BOTH line-movement history and public-betting share. Neither has a
        data source in core Phase 1 (movement deferred, D6; public-betting % has no free
        feed), so the signal is honestly UNAVAILABLE and returns 0.0 (missing) — never a
        simulated value. The prior implementation fabricated public-betting % from
        hardcoded team-popularity/rivalry lists + random noise; that is removed
        (SPEC §5.2, SCHEMA §4, binding principles #2 and #4).
        """
        return 0.0
    
    def _get_line_movement_magnitude(self, home_team: str, away_team: str, context: Dict) -> float:
        """
        Calculate the magnitude of line movement from open to current.
        
        Returns:
            Float representing points moved (positive = toward favorite)
        """
        try:
            # Open→current movement from the snapshot's book lines. Opening spreads
            # are absent in core Phase 1 (movement history deferred, D6), so this is
            # 0.0 (missing) — never simulated/fabricated, which is why the old
            # `_simulate_line_movement` fallback was removed (SPEC §5.2, SCHEMA §4).
            game_lines = self._game_book_lines(home_team, away_team, context)
            total_movement = 0.0
            movement_count = 0
            for line in game_lines:
                opening = line.get('spread_open')
                current = line.get('spread')
                if opening is not None and current is not None:
                    total_movement += current - opening
                    movement_count += 1
            return total_movement / movement_count if movement_count else 0.0
        except Exception as e:
            self.logger.debug(f"Error reading line movement: {e}")
            return 0.0

    def calculate_with_confidence(self, home_team: str, away_team: str, 
                                 context: Optional[Dict[str, Any]] = None) -> Tuple[float, FactorConfidence, List[str]]:
        """Calculate with confidence scoring."""
        value = self.calculate(home_team, away_team, context)
        reasoning = []
        
        if not context:
            return value, FactorConfidence.NONE, ["No market data available"]
        
        # For modifiers, confidence based on deviation from 1.0
        deviation = abs(value - 1.0)
        
        if deviation > 0.4:
            confidence = FactorConfidence.VERY_HIGH
            reasoning.append("Strong market sentiment divergence detected")
        elif deviation > 0.25:
            confidence = FactorConfidence.HIGH
            reasoning.append("Clear sharp vs public split identified")
        elif deviation > 0.15:
            confidence = FactorConfidence.MEDIUM
            reasoning.append("Moderate betting pattern divergence")
        elif deviation > 0.05:
            confidence = FactorConfidence.LOW
            reasoning.append("Slight market sentiment signal")
        else:
            confidence = FactorConfidence.NONE
            reasoning.append("No significant market sentiment")
        
        # Add specific signals to reasoning
        if value > 1.2:
            reasoning.append("Sharp money aligned with contrarian position")
        elif value < 0.8:
            reasoning.append("Market sentiment suggests caution")

        # SCHEMA §4 (D6): line-movement history is deferred to slice 1.5. When no book
        # carries an opening spread, movement is *missing* (not a real 0) — honestly
        # reduce confidence rather than over-trust the characteristic heuristics.
        if not self._has_line_movement(home_team, away_team, context):
            reasoning.append("Line-movement history unavailable (deferred) — reduced confidence")
            if confidence > FactorConfidence.MEDIUM:
                confidence = FactorConfidence.MEDIUM

        return value, confidence, reasoning
    
    def get_output_range(self) -> Tuple[float, float]:
        """Return the output range (multiplicative)."""
        return (self._min_output, self._max_output)
    
    def get_explanation(self, home_team: str, away_team: str, value: float, 
                       context: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """Generate human-readable explanation."""
        if abs(value - 1.0) < 0.05:
            return "No significant market sentiment signal"
        
        if value > 1.0:
            strength = "strong" if value > 1.3 else "moderate" if value > 1.15 else "slight"
            return f"Market sentiment shows {strength} sharp money support (×{value:.2f} modifier)"
        else:
            strength = "strong" if value < 0.7 else "moderate" if value < 0.85 else "slight"
            return f"Market sentiment suggests {strength} caution (×{value:.2f} modifier)"
    
    def get_required_data(self) -> Dict[str, bool]:
        """Declare required data."""
        return {
            'betting_data': True,      # Reads snapshot `betting_lines` from context
            'team_info': False,
            'coaching_data': False,
            'team_stats': False,
            'schedule_data': False,
            'historical_data': False
        }