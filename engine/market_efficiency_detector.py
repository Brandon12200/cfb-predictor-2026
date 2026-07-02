"""
Market Efficiency Detector for College Football Market Edge Platform.
Identifies betting market inefficiencies and sharp money movements.
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
import statistics

from config import config


class MarketEfficiencyDetector:
    """
    Analyzes betting market efficiency to identify value opportunities.
    
    Features:
    - Line movement tracking and analysis
    - Sharp vs public money identification
    - Market consensus divergence detection
    - Efficiency scoring by game type
    - Historical market accuracy tracking
    """
    
    def __init__(self):
        """Initialize market efficiency detector."""
        self.logger = logging.getLogger(__name__)
        
        # Market efficiency thresholds
        self.efficiency_thresholds = {
            'line_movement': 2.5,  # Points of line movement considered significant
            'sharp_threshold': 0.7,  # Confidence threshold for sharp money
            'public_fade_threshold': 75,  # % of public on one side to consider fading
            'reverse_line_movement': True  # Track when line moves against public %
        }
        
        # Game type efficiency multipliers
        self.game_type_efficiency = {
            'primetime': 1.2,  # More efficient (national TV)
            'conference': 1.0,  # Standard efficiency
            'non_conference': 0.9,  # Less efficient
            'rivalry': 0.85,  # Emotional betting, less efficient
            'week_1_3': 0.8,  # Early season less efficient
            'bowl_game': 1.1,  # More scrutinized
            'fcs_opponent': 0.6  # Very inefficient
        }
        
        self.logger.info("Market Efficiency Detector initialized")
    
    def analyze_market_efficiency(self, game_data: Dict[str, Any], 
                                 historical_data: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Comprehensive market efficiency analysis.
        
        Args:
            game_data: Current game information including lines
            historical_data: Optional historical market performance
            
        Returns:
            Market efficiency analysis with recommendations
        """
        try:
            efficiency_analysis = {
                'efficiency_score': 0.0,
                'market_indicators': {},
                'inefficiency_signals': [],
                'confidence': 0.0,
                'recommendation': None
            }
            
            # Analyze line movement
            line_movement = self._analyze_line_movement(game_data)
            efficiency_analysis['market_indicators']['line_movement'] = line_movement
            
            # Detect sharp vs public money
            sharp_public = self._detect_sharp_public_split(game_data)
            efficiency_analysis['market_indicators']['sharp_public'] = sharp_public
            
            # Check for reverse line movement (strong sharp indicator)
            rlm = self._detect_reverse_line_movement(game_data)
            if rlm['detected']:
                efficiency_analysis['inefficiency_signals'].append('REVERSE_LINE_MOVEMENT')
            efficiency_analysis['market_indicators']['reverse_line_movement'] = rlm
            
            # Analyze market consensus
            consensus = self._analyze_market_consensus(game_data)
            efficiency_analysis['market_indicators']['consensus'] = consensus
            
            # Calculate game-specific efficiency
            game_efficiency = self._calculate_game_efficiency(game_data)
            efficiency_analysis['game_efficiency'] = game_efficiency
            
            # Generate overall efficiency score
            efficiency_score = self._calculate_efficiency_score(
                line_movement, sharp_public, rlm, consensus, game_efficiency
            )
            efficiency_analysis['efficiency_score'] = efficiency_score
            
            # Identify inefficiency opportunities
            if efficiency_score < 0.5:  # Low efficiency = opportunity
                efficiency_analysis['inefficiency_signals'].append('HIGH_OPPORTUNITY')
                efficiency_analysis['confidence'] = 0.75
            elif efficiency_score < 0.7:
                efficiency_analysis['inefficiency_signals'].append('MODERATE_OPPORTUNITY')
                efficiency_analysis['confidence'] = 0.60
            else:
                efficiency_analysis['confidence'] = 0.45
            
            # Generate recommendation
            efficiency_analysis['recommendation'] = self._generate_recommendation(
                efficiency_analysis, game_data
            )
            
            # Add historical context if available
            if historical_data:
                efficiency_analysis['historical_context'] = self._add_historical_context(
                    historical_data, game_data
                )
            
            return efficiency_analysis
            
        except Exception as e:
            self.logger.error(f"Error analyzing market efficiency: {e}")
            return {
                'efficiency_score': 0.5,
                'error': str(e),
                'confidence': 0.0
            }
    
    def _analyze_line_movement(self, game_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze betting line movement patterns."""
        movement_analysis = {
            'total_movement': 0.0,
            'direction': 'STABLE',
            'significance': 'LOW',
            'pattern': None
        }
        
        # Get opening and current lines
        opening_line = game_data.get('opening_spread')
        current_line = game_data.get('vegas_spread')
        
        if opening_line is None or current_line is None:
            return movement_analysis
        
        # Calculate movement
        total_movement = abs(current_line - opening_line)
        movement_analysis['total_movement'] = total_movement
        
        # Determine direction
        if current_line > opening_line:
            movement_analysis['direction'] = 'TOWARD_HOME'
        elif current_line < opening_line:
            movement_analysis['direction'] = 'TOWARD_AWAY'
        
        # Assess significance
        if total_movement >= self.efficiency_thresholds['line_movement']:
            movement_analysis['significance'] = 'HIGH'
            movement_analysis['pattern'] = 'SHARP_MOVE'
        elif total_movement >= self.efficiency_thresholds['line_movement'] / 2:
            movement_analysis['significance'] = 'MODERATE'
            movement_analysis['pattern'] = 'STEADY_DRIFT'
        else:
            movement_analysis['pattern'] = 'STABLE'
        
        return movement_analysis
    
    def _detect_sharp_public_split(self, game_data: Dict[str, Any]) -> Dict[str, Any]:
        """Detect sharp vs public money indicators."""
        sharp_public = {
            'public_percentage': None,
            'money_percentage': None,
            'sharp_side': None,
            'fade_public': False
        }
        
        # Get betting percentages if available
        public_pct = game_data.get('public_betting_percentage')
        money_pct = game_data.get('money_percentage')
        
        if public_pct is None:
            # Estimate based on line movement and other factors
            return self._estimate_sharp_indicators(game_data)
        
        sharp_public['public_percentage'] = public_pct
        sharp_public['money_percentage'] = money_pct
        
        # Detect sharp money
        if money_pct and public_pct:
            # Sharp money is when money % significantly differs from ticket %
            if money_pct > public_pct + 15:
                sharp_public['sharp_side'] = 'FAVORITE'
            elif money_pct < public_pct - 15:
                sharp_public['sharp_side'] = 'UNDERDOG'
        
        # Check for public fade opportunity
        if public_pct >= self.efficiency_thresholds['public_fade_threshold']:
            sharp_public['fade_public'] = True
        
        return sharp_public
    
    def _detect_reverse_line_movement(self, game_data: Dict[str, Any]) -> Dict[str, Any]:
        """Detect reverse line movement (line moves against public betting)."""
        rlm = {
            'detected': False,
            'strength': 0.0,
            'side': None
        }
        
        public_pct = game_data.get('public_betting_percentage')
        opening_line = game_data.get('opening_spread')
        current_line = game_data.get('vegas_spread')
        
        if not all([public_pct, opening_line is not None, current_line is not None]):
            return rlm
        
        line_movement = current_line - opening_line
        
        # RLM: Line moves toward team getting less than 40% of bets
        if public_pct > 65 and line_movement > 0.5:
            # Public on favorite but line moving toward dog
            rlm['detected'] = True
            rlm['strength'] = min(line_movement / 3.0, 1.0)
            rlm['side'] = 'UNDERDOG'
        elif public_pct < 35 and line_movement < -0.5:
            # Public on dog but line moving toward favorite
            rlm['detected'] = True
            rlm['strength'] = min(abs(line_movement) / 3.0, 1.0)
            rlm['side'] = 'FAVORITE'
        
        return rlm
    
    def _analyze_market_consensus(self, game_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze consensus across multiple sportsbooks."""
        consensus = {
            'spread_variance': 0.0,
            'total_variance': 0.0,
            'consensus_level': 'HIGH',
            'outlier_books': []
        }
        
        # Get spreads from multiple books if available
        spreads = game_data.get('all_spreads', [game_data.get('vegas_spread')])
        spreads = [s for s in spreads if s is not None]
        
        if len(spreads) > 1:
            # Calculate variance
            mean_spread = statistics.mean(spreads)
            spread_variance = statistics.stdev(spreads) if len(spreads) > 1 else 0
            consensus['spread_variance'] = spread_variance
            
            # Determine consensus level
            if spread_variance > 1.5:
                consensus['consensus_level'] = 'LOW'
            elif spread_variance > 0.5:
                consensus['consensus_level'] = 'MODERATE'
            else:
                consensus['consensus_level'] = 'HIGH'
            
            # Identify outliers
            for i, spread in enumerate(spreads):
                if abs(spread - mean_spread) > 1.5:
                    consensus['outlier_books'].append({
                        'book_index': i,
                        'spread': spread,
                        'deviation': spread - mean_spread
                    })
        
        return consensus
    
    def _calculate_game_efficiency(self, game_data: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate game-specific market efficiency."""
        efficiency = {
            'base_efficiency': 1.0,
            'modifiers': [],
            'final_efficiency': 1.0
        }
        
        week = game_data.get('week', 4)
        
        # Early season modifier
        if week <= 3:
            efficiency['modifiers'].append(('early_season', 0.8))
            efficiency['base_efficiency'] *= 0.8
        
        # Check for FCS opponent
        if self._is_fcs_game(game_data):
            efficiency['modifiers'].append(('fcs_opponent', 0.6))
            efficiency['base_efficiency'] *= 0.6
        
        # Primetime game (more efficient)
        if game_data.get('is_primetime', False):
            efficiency['modifiers'].append(('primetime', 1.2))
            efficiency['base_efficiency'] *= 1.2
        
        # Rivalry game (less efficient, emotional betting)
        if game_data.get('is_rivalry', False):
            efficiency['modifiers'].append(('rivalry', 0.85))
            efficiency['base_efficiency'] *= 0.85
        
        # Conference game
        if game_data.get('is_conference', False):
            efficiency['modifiers'].append(('conference', 1.0))
        
        efficiency['final_efficiency'] = max(0.3, min(1.5, efficiency['base_efficiency']))
        
        return efficiency
    
    def _calculate_efficiency_score(self, line_movement: Dict, sharp_public: Dict,
                                   rlm: Dict, consensus: Dict, 
                                   game_efficiency: Dict) -> float:
        """Calculate overall market efficiency score (0=inefficient, 1=efficient)."""
        score = 0.5  # Start neutral
        
        # Line movement factor
        if line_movement['significance'] == 'HIGH':
            score -= 0.15  # Significant movement = less efficient
        elif line_movement['significance'] == 'LOW':
            score += 0.1   # Stable line = more efficient
        
        # Sharp/public split factor
        if sharp_public.get('sharp_side'):
            score -= 0.2   # Sharp money identified = inefficiency
        if sharp_public.get('fade_public'):
            score -= 0.15  # Public heavily on one side = inefficiency
        
        # Reverse line movement (strong inefficiency signal)
        if rlm['detected']:
            score -= 0.25 * rlm['strength']
        
        # Consensus factor
        if consensus['consensus_level'] == 'LOW':
            score -= 0.15  # Disagreement = inefficiency
        elif consensus['consensus_level'] == 'HIGH':
            score += 0.1   # Agreement = efficiency
        
        # Apply game-specific efficiency
        score *= game_efficiency['final_efficiency']
        
        return max(0.0, min(1.0, score))
    
    def _generate_recommendation(self, analysis: Dict, game_data: Dict) -> str:
        """Generate actionable recommendation based on efficiency analysis."""
        score = analysis['efficiency_score']
        signals = analysis['inefficiency_signals']
        indicators = analysis['market_indicators']
        
        if 'REVERSE_LINE_MOVEMENT' in signals:
            side = indicators['reverse_line_movement']['side']
            return f"STRONG OPPORTUNITY: Reverse line movement detected. Consider {side}."
        
        if score < 0.4:
            sharp_side = indicators['sharp_public'].get('sharp_side')
            if sharp_side:
                return f"HIGH VALUE: Market inefficiency detected. Sharp money on {sharp_side}."
            return "HIGH VALUE: Significant market inefficiency detected."
        
        if score < 0.6:
            if indicators['sharp_public'].get('fade_public'):
                return "MODERATE VALUE: Consider fading heavy public side."
            return "MODERATE VALUE: Some market inefficiency present."
        
        return "EFFICIENT MARKET: Limited contrarian value detected."
    
    def _estimate_sharp_indicators(self, game_data: Dict) -> Dict[str, Any]:
        """Estimate sharp money indicators when direct data unavailable."""
        # Use line movement and other factors to estimate
        return {
            'public_percentage': None,
            'money_percentage': None,
            'sharp_side': None,
            'fade_public': False,
            'estimated': True
        }
    
    def _is_fcs_game(self, game_data: Dict) -> bool:
        """Check if game involves FCS opponent."""
        # Would need team classification data
        home_team = game_data.get('home_team', '').upper()
        away_team = game_data.get('away_team', '').upper()
        
        fcs_keywords = ['STATE', 'SOUTHERN', 'EASTERN', 'WESTERN', 'NORTHERN', 
                       'A&M', 'A&T', 'PRAIRIE', 'VALLEY']
        
        # Simple heuristic (would be better with actual conference data)
        return any(keyword in home_team for keyword in fcs_keywords) or \
               any(keyword in away_team for keyword in fcs_keywords)
    
    def _add_historical_context(self, historical_data: Dict, 
                               game_data: Dict) -> Dict[str, Any]:
        """Add historical market performance context."""
        return {
            'similar_games_efficiency': 0.0,
            'historical_accuracy': 0.0,
            'trend': 'STABLE'
        }


# Global instance
market_efficiency_detector = MarketEfficiencyDetector()