"""
Game Quality Filter for College Football Market Edge Platform.
Filters out high-variance and low-quality betting opportunities.
"""

import logging
from typing import Dict, Any, List, Optional, Set
from datetime import datetime

from config import config
from utils.normalizer import normalizer


class GameQualityFilter:
    """
    Filters games based on quality and predictability criteria.
    
    Features:
    - Spread variance filtering (avoid extreme spreads)
    - FCS opponent filtering
    - Data quality requirements
    - Conference classification
    - Primetime/TV slot consideration
    - Weather impact assessment
    - Injury/suspension alerts
    """
    
    def __init__(self):
        """Initialize game quality filter."""
        self.logger = logging.getLogger(__name__)
        
        # Filter thresholds
        self.filter_criteria = {
            'max_spread': 30.0,          # Avoid spreads > 30 points
            'min_spread': 0.5,           # Avoid pick'em games < 0.5
            'min_data_quality': 0.6,     # Require 60% data completeness
            'max_weather_impact': 20,    # Wind speed in mph
            'required_tv_coverage': False # Don't require TV but prefer it
        }
        
        # FCS schools (partial list - would be comprehensive in production)
        self.fcs_schools = {
            'CHATTANOOGA', 'FURMAN', 'WOFFORD', 'CITADEL', 'VMI',
            'JACKSON STATE', 'FLORIDA A&M', 'BETHUNE-COOKMAN',
            'NORTH DAKOTA STATE', 'SOUTH DAKOTA STATE', 'MONTANA',
            'JAMES MADISON', 'DELAWARE', 'NEW HAMPSHIRE', 'MAINE',
            'FORDHAM', 'COLGATE', 'HOLY CROSS', 'BUCKNELL',
            'RICHMOND', 'WILLIAM & MARY', 'VILLANOVA', 'RHODE ISLAND'
        }
        
        # Power conferences for quality classification
        self.power_conferences = {
            'SEC', 'BIG TEN', 'BIG 12', 'ACC', 'PAC-12', 
            'BIG TEN CONFERENCE', 'SOUTHEASTERN CONFERENCE',
            'ATLANTIC COAST CONFERENCE', 'PAC-12 CONFERENCE'
        }
        
        # Group of 5 conferences
        self.group_of_5 = {
            'AMERICAN', 'AAC', 'MOUNTAIN WEST', 'MAC', 'SUN BELT', 'CONFERENCE USA',
            'AMERICAN ATHLETIC CONFERENCE', 'MID-AMERICAN CONFERENCE'
        }
        
        self.logger.info("Game Quality Filter initialized")
    
    def evaluate_game_quality(self, game_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Comprehensive game quality evaluation.
        
        Args:
            game_data: Complete game information
            
        Returns:
            Quality assessment with recommendations
        """
        try:
            quality_assessment = {
                'overall_quality': 'UNKNOWN',
                'quality_score': 0.0,
                'filter_results': {},
                'recommendations': [],
                'warnings': [],
                'should_analyze': True
            }
            
            # Run all quality filters
            spread_filter = self._evaluate_spread_quality(game_data)
            quality_assessment['filter_results']['spread'] = spread_filter
            
            opponent_filter = self._evaluate_opponent_quality(game_data)
            quality_assessment['filter_results']['opponents'] = opponent_filter
            
            data_filter = self._evaluate_data_quality(game_data)
            quality_assessment['filter_results']['data'] = data_filter
            
            conference_filter = self._evaluate_conference_quality(game_data)
            quality_assessment['filter_results']['conference'] = conference_filter
            
            timing_filter = self._evaluate_timing_quality(game_data)
            quality_assessment['filter_results']['timing'] = timing_filter
            
            weather_filter = self._evaluate_weather_impact(game_data)
            quality_assessment['filter_results']['weather'] = weather_filter
            
            # Calculate overall quality score
            quality_score = self._calculate_quality_score(quality_assessment['filter_results'])
            quality_assessment['quality_score'] = quality_score
            
            # Determine overall quality classification
            if quality_score >= 0.8:
                quality_assessment['overall_quality'] = 'PREMIUM'
                quality_assessment['recommendations'].append('HIGH_CONFIDENCE_ANALYSIS')
            elif quality_score >= 0.6:
                quality_assessment['overall_quality'] = 'GOOD'
                quality_assessment['recommendations'].append('STANDARD_ANALYSIS')
            elif quality_score >= 0.4:
                quality_assessment['overall_quality'] = 'FAIR'
                quality_assessment['recommendations'].append('REDUCED_CONFIDENCE')
            else:
                quality_assessment['overall_quality'] = 'POOR'
                quality_assessment['recommendations'].append('SKIP_ANALYSIS')
                quality_assessment['should_analyze'] = False
            
            # Add specific warnings
            quality_assessment['warnings'] = self._generate_quality_warnings(
                quality_assessment['filter_results']
            )
            
            return quality_assessment
            
        except Exception as e:
            self.logger.error(f"Error evaluating game quality: {e}")
            return {
                'overall_quality': 'ERROR',
                'quality_score': 0.0,
                'should_analyze': False,
                'error': str(e)
            }
    
    def _evaluate_spread_quality(self, game_data: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate spread quality and variance."""
        spread_eval = {
            'quality': 'GOOD',
            'score': 1.0,
            'issues': []
        }
        
        spread = game_data.get('vegas_spread')
        if spread is None:
            spread_eval['quality'] = 'POOR'
            spread_eval['score'] = 0.0
            spread_eval['issues'].append('NO_SPREAD_DATA')
            return spread_eval
        
        abs_spread = abs(spread)
        
        # Check for extreme spreads
        if abs_spread > self.filter_criteria['max_spread']:
            spread_eval['quality'] = 'POOR'
            spread_eval['score'] = 0.2
            spread_eval['issues'].append(f'EXTREME_SPREAD_{abs_spread}')
        elif abs_spread > 21:
            spread_eval['quality'] = 'FAIR'
            spread_eval['score'] = 0.6
            spread_eval['issues'].append('HIGH_SPREAD')
        elif abs_spread < self.filter_criteria['min_spread']:
            spread_eval['quality'] = 'FAIR'
            spread_eval['score'] = 0.7
            spread_eval['issues'].append('PICK_EM_GAME')
        
        # Check for suspicious line movement
        opening_spread = game_data.get('opening_spread')
        if opening_spread is not None:
            movement = abs(spread - opening_spread)
            if movement > 7:
                spread_eval['issues'].append('MAJOR_LINE_MOVEMENT')
                spread_eval['score'] *= 0.8
            elif movement > 3:
                spread_eval['issues'].append('SIGNIFICANT_MOVEMENT')
                spread_eval['score'] *= 0.9
        
        return spread_eval
    
    def _evaluate_opponent_quality(self, game_data: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate opponent quality and classification."""
        opponent_eval = {
            'quality': 'GOOD',
            'score': 1.0,
            'classification': 'P5_VS_P5',
            'issues': []
        }
        
        home_team = game_data.get('home_team', '').upper()
        away_team = game_data.get('away_team', '').upper()
        
        # Check for FCS opponents
        home_is_fcs = self._is_fcs_team(home_team)
        away_is_fcs = self._is_fcs_team(away_team)
        
        if home_is_fcs or away_is_fcs:
            opponent_eval['quality'] = 'POOR'
            opponent_eval['score'] = 0.3
            opponent_eval['classification'] = 'FCS_GAME'
            opponent_eval['issues'].append('FCS_OPPONENT')
            return opponent_eval
        
        # Classify by conference
        home_conf_tier = self._get_conference_tier(game_data.get('home_team_data', {}))
        away_conf_tier = self._get_conference_tier(game_data.get('away_team_data', {}))
        
        if home_conf_tier == 'POWER' and away_conf_tier == 'POWER':
            opponent_eval['classification'] = 'P5_VS_P5'
            opponent_eval['score'] = 1.0
        elif home_conf_tier == 'GROUP_5' and away_conf_tier == 'GROUP_5':
            opponent_eval['classification'] = 'G5_VS_G5'
            opponent_eval['score'] = 0.8
        elif (home_conf_tier == 'POWER') != (away_conf_tier == 'POWER'):
            opponent_eval['classification'] = 'P5_VS_G5'
            opponent_eval['score'] = 0.9
        else:
            opponent_eval['classification'] = 'OTHER'
            opponent_eval['quality'] = 'FAIR'
            opponent_eval['score'] = 0.6
            opponent_eval['issues'].append('LOWER_TIER_MATCHUP')
        
        return opponent_eval
    
    def _evaluate_data_quality(self, game_data: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate completeness and quality of available data."""
        data_eval = {
            'quality': 'GOOD',
            'score': 1.0,
            'completeness': 0.0,
            'missing_data': []
        }
        
        # Check for essential data fields
        essential_fields = [
            'home_team', 'away_team', 'vegas_spread', 'week'
        ]
        
        optional_fields = [
            'home_team_data', 'away_team_data', 'weather', 'tv_coverage'
        ]
        
        # Count available data
        total_fields = len(essential_fields) + len(optional_fields)
        available_fields = 0
        
        for field in essential_fields:
            if game_data.get(field) is not None:
                available_fields += 1
            else:
                data_eval['missing_data'].append(field)
        
        for field in optional_fields:
            if game_data.get(field) is not None:
                available_fields += 1
        
        # Calculate completeness
        data_eval['completeness'] = available_fields / total_fields
        
        # Assess data quality
        if data_eval['missing_data']:
            data_eval['quality'] = 'POOR'
            data_eval['score'] = 0.3
        elif data_eval['completeness'] >= 0.8:
            data_eval['quality'] = 'EXCELLENT'
            data_eval['score'] = 1.0
        elif data_eval['completeness'] >= 0.6:
            data_eval['quality'] = 'GOOD'
            data_eval['score'] = 0.85
        else:
            data_eval['quality'] = 'FAIR'
            data_eval['score'] = 0.6
        
        return data_eval
    
    def _evaluate_conference_quality(self, game_data: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate conference quality and matchup significance."""
        conf_eval = {
            'quality': 'GOOD',
            'score': 1.0,
            'significance': 'CONFERENCE',
            'factors': []
        }
        
        home_data = game_data.get('home_team_data', {})
        away_data = game_data.get('away_team_data', {})
        
        home_conf = self._get_conference_name(home_data)
        away_conf = self._get_conference_name(away_data)
        
        # Conference game bonus
        if home_conf == away_conf and home_conf:
            conf_eval['significance'] = 'CONFERENCE'
            conf_eval['factors'].append('CONFERENCE_GAME')
            conf_eval['score'] *= 1.1
        
        # Rivalry game detection (basic)
        if self._is_rivalry_game(game_data):
            conf_eval['significance'] = 'RIVALRY'
            conf_eval['factors'].append('RIVALRY')
            conf_eval['score'] *= 0.9  # More unpredictable
        
        # Power conference boost
        home_tier = self._get_conference_tier(home_data)
        away_tier = self._get_conference_tier(away_data)
        
        if home_tier == 'POWER' and away_tier == 'POWER':
            conf_eval['factors'].append('POWER_MATCHUP')
            conf_eval['score'] *= 1.05
        
        return conf_eval
    
    def _evaluate_timing_quality(self, game_data: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate game timing factors."""
        timing_eval = {
            'quality': 'GOOD',
            'score': 1.0,
            'factors': []
        }
        
        week = game_data.get('week', 4)
        
        # Early season adjustment
        if week <= 2:
            timing_eval['factors'].append('EARLY_SEASON')
            timing_eval['score'] *= 0.8
        elif week <= 3:
            timing_eval['factors'].append('EARLY_SEASON_MINOR')
            timing_eval['score'] *= 0.9
        
        # Late season/playoff implications
        if week >= 12:
            timing_eval['factors'].append('LATE_SEASON')
            timing_eval['score'] *= 1.05
        
        # Check for bye week impacts
        if self._has_bye_week_impact(game_data):
            timing_eval['factors'].append('BYE_WEEK_IMPACT')
            timing_eval['score'] *= 1.1
        
        # TV coverage boost (more scrutinized lines)
        if game_data.get('tv_coverage') or game_data.get('is_primetime'):
            timing_eval['factors'].append('TV_COVERAGE')
            timing_eval['score'] *= 1.05
        
        return timing_eval
    
    def _evaluate_weather_impact(self, game_data: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate weather impact on game quality."""
        weather_eval = {
            'quality': 'GOOD',
            'score': 1.0,
            'impact': 'MINIMAL',
            'factors': []
        }
        
        weather = game_data.get('weather', {})
        if not weather:
            return weather_eval
        
        # Wind impact
        wind_speed = weather.get('wind_speed', 0)
        if wind_speed > self.filter_criteria['max_weather_impact']:
            weather_eval['quality'] = 'POOR'
            weather_eval['score'] = 0.6
            weather_eval['impact'] = 'HIGH'
            weather_eval['factors'].append(f'HIGH_WIND_{wind_speed}')
        elif wind_speed > 15:
            weather_eval['quality'] = 'FAIR'
            weather_eval['score'] = 0.8
            weather_eval['impact'] = 'MODERATE'
            weather_eval['factors'].append('MODERATE_WIND')
        
        # Precipitation
        precipitation = weather.get('precipitation_probability', 0)
        if precipitation > 70:
            weather_eval['factors'].append('HIGH_PRECIP')
            weather_eval['score'] *= 0.9
        
        # Temperature extremes
        temp = weather.get('temperature')
        if temp is not None:
            if temp < 20 or temp > 100:
                weather_eval['factors'].append('EXTREME_TEMP')
                weather_eval['score'] *= 0.9
        
        return weather_eval
    
    def _calculate_quality_score(self, filter_results: Dict) -> float:
        """Calculate overall quality score from all filters."""
        weights = {
            'spread': 0.25,
            'opponents': 0.25,
            'data': 0.20,
            'conference': 0.15,
            'timing': 0.10,
            'weather': 0.05
        }
        
        total_score = 0.0
        
        for filter_name, weight in weights.items():
            filter_result = filter_results.get(filter_name, {})
            filter_score = filter_result.get('score', 0.5)
            total_score += filter_score * weight
        
        return min(1.0, max(0.0, total_score))
    
    def _generate_quality_warnings(self, filter_results: Dict) -> List[str]:
        """Generate warnings based on filter results."""
        warnings = []
        
        for filter_name, result in filter_results.items():
            issues = result.get('issues', [])
            for issue in issues:
                if issue not in warnings:
                    warnings.append(f"{filter_name.upper()}_{issue}")
        
        return warnings
    
    def _is_fcs_team(self, team_name: str) -> bool:
        """Check if team is FCS level."""
        normalized_name = normalizer.normalize(team_name).upper()
        return any(fcs in normalized_name for fcs in self.fcs_schools)
    
    def _get_conference_tier(self, team_data: Dict) -> str:
        """Get conference tier (POWER, GROUP_5, FCS, OTHER)."""
        if not team_data:
            return 'OTHER'
        
        conference_info = team_data.get('info', {}).get('conference', {})
        if not conference_info:
            return 'OTHER'
        
        conf_name = conference_info.get('name', '').upper()
        
        if any(power in conf_name for power in self.power_conferences):
            return 'POWER'
        elif any(g5 in conf_name for g5 in self.group_of_5):
            return 'GROUP_5'
        else:
            return 'OTHER'
    
    def _get_conference_name(self, team_data: Dict) -> str:
        """Extract conference name from team data."""
        if not team_data:
            return ''
        
        return team_data.get('info', {}).get('conference', {}).get('name', '')
    
    def _is_rivalry_game(self, game_data: Dict) -> bool:
        """Detect rivalry games (basic implementation)."""
        # Would need comprehensive rivalry database
        home_team = game_data.get('home_team', '').upper()
        away_team = game_data.get('away_team', '').upper()
        
        # Basic rivalry pairs (partial list)
        rivalries = [
            ('ALABAMA', 'AUBURN'), ('OHIO STATE', 'MICHIGAN'),
            ('TEXAS', 'OKLAHOMA'), ('USC', 'UCLA'),
            ('FLORIDA', 'GEORGIA'), ('CLEMSON', 'SOUTH CAROLINA')
        ]
        
        for team1, team2 in rivalries:
            if (team1 in home_team and team2 in away_team) or \
               (team2 in home_team and team1 in away_team):
                return True
        
        return False
    
    def _has_bye_week_impact(self, game_data: Dict) -> bool:
        """Check for bye week advantages."""
        # Would need schedule data to determine bye weeks
        return False
    
    def get_recommended_games(self, games: List[Dict]) -> List[Dict]:
        """Filter and rank games by quality for analysis."""
        quality_games = []
        
        for game in games:
            quality_assessment = self.evaluate_game_quality(game)
            
            if quality_assessment['should_analyze']:
                game_copy = game.copy()
                game_copy['quality_assessment'] = quality_assessment
                quality_games.append(game_copy)
        
        # Sort by quality score (highest first)
        quality_games.sort(key=lambda g: g['quality_assessment']['quality_score'], reverse=True)
        
        return quality_games


# Global instance
game_quality_filter = GameQualityFilter()