"""
Unified data manager for College Football Market Edge Platform.
Coordinates data access across multiple APIs with fallback and error handling.
"""

import logging
from typing import Dict, List, Optional, Any, Callable, Union
from functools import wraps
from datetime import datetime

from config import config
from data.odds_client import OddsAPIClient
from data.espn_client import ESPNStatsClient
from data.cfbd_client import get_cfbd_client
from data.cache_manager import cache_manager
from utils.normalizer import normalizer


def safe_api_call(fallback_value=None):
    """
    Decorator for safe API calls with fallback handling.
    
    Args:
        fallback_value: Value to return on failure
    """
    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            try:
                return func(self, *args, **kwargs)
            except Exception as e:
                self.logger.warning(f"API call failed in {func.__name__}: {e}")
                if fallback_value is not None:
                    return fallback_value
                return self._get_neutral_fallback(func.__name__, args, kwargs)
        return wrapper
    return decorator


class DataManager:
    """
    Unified data manager that coordinates access to multiple data sources.
    
    Features:
    - Safe data fetching with graceful degradation
    - Automatic fallback to neutral values on API failures
    - Comprehensive error handling and logging
    - Data validation and consistency checks
    - Unified interface for all data access
    """
    
    def __init__(self, config_obj=None):
        """
        Initialize data manager with API clients.
        
        Args:
            config_obj: Configuration object (uses global if None)
        """
        self.config = config_obj or config
        
        # Initialize API clients (CFBD primary, ESPN fallback)
        self.odds_client = None
        self.cfbd_client = None
        self.espn_client = ESPNStatsClient()
        
        # Initialize odds client only if API key is available
        if self.config.odds_api_key:
            try:
                self.odds_client = OddsAPIClient(self.config.odds_api_key)
            except Exception as e:
                logging.warning(f"Failed to initialize Odds API client: {e}")
        
        # Initialize CFBD client as primary data source
        if self.config.cfbd_api_key:
            try:
                self.cfbd_client = get_cfbd_client()
            except Exception as e:
                logging.warning(f"Failed to initialize CFBD API client: {e}")
        else:
            logging.warning("CFBD API key not configured - primary data source unavailable")
        
        # Cache manager
        self.cache = cache_manager
        
        # Normalizer
        self.normalizer = normalizer
        
        # Logging
        self.logger = logging.getLogger(__name__)
        
        # Fallback data structures
        self._fallback_data = self._initialize_fallback_data()
        
        self.logger.info(f"Data manager initialized - CFBD API (Primary): {'✓' if self.cfbd_client else '✗'}, ESPN API (Fallback): ✓, Odds API: {'✓' if self.odds_client else '✗'}")
    
    @safe_api_call(fallback_value={})
    def get_game_context(self, home_team: str, away_team: str, week: Optional[int] = None) -> Dict[str, Any]:
        """
        Get comprehensive context for a specific game matchup.
        
        Args:
            home_team: Normalized home team name
            away_team: Normalized away team name
            week: Week number (optional)
            
        Returns:
            Dictionary with game context including spread, team data, etc.
        """
        self.logger.info(f"Fetching game context: {away_team} @ {home_team} (Week {week})")
        
        # Check cache first
        cached_context = self.cache.get_game_data(home_team, away_team, week)
        if cached_context:
            self.logger.debug("Using cached game context")
            return cached_context
        
        # Fetch data from multiple sources
        context = {
            'home_team': home_team,
            'away_team': away_team,
            'week': week,
            'year': datetime.now().year,  # Add current year for factors
            'timestamp': datetime.now().isoformat(),
            'data_sources': []
        }
        
        # Get betting data
        if self.odds_client:
            try:
                spread = self.odds_client.get_consensus_spread(home_team, away_team, week)
                context['vegas_spread'] = spread
                context['has_betting_data'] = spread is not None
                context['data_sources'].append('odds_api')
                
                if spread is not None:
                    self.logger.info(f"Retrieved spread: {away_team} @ {home_team} = {spread}")
            except Exception as e:
                self.logger.warning(f"Failed to get betting data: {e}")
                context['vegas_spread'] = None
                context['has_betting_data'] = False
        else:
            context['vegas_spread'] = None
            context['has_betting_data'] = False
        
        # PRODUCTION: If no betting line, return minimal context - don't fetch expensive data
        if context['vegas_spread'] is None:
            self.logger.info(f"No betting line available for {away_team} @ {home_team} - returning minimal context")
            context['home_team_data'] = {}
            context['away_team_data'] = {}
            context['coaching_comparison'] = {}
            context['data_quality'] = 0.0
            return context
        
        # Get team data for both teams (only if we have a betting line)
        context['home_team_data'] = self.get_team_data(home_team)
        context['away_team_data'] = self.get_team_data(away_team)
        
        # Determine primary data source used
        if self.cfbd_client:
            context['data_sources'].append('cfbd_api_primary')
        context['data_sources'].append('espn_api_fallback')
        
        # Get coaching comparison
        context['coaching_comparison'] = self.get_coaching_comparison(home_team, away_team)
        
        # Calculate data quality score
        context['data_quality'] = self._assess_data_quality(context)
        
        # Cache the result
        self.cache.cache_game_data(home_team, away_team, context, week, ttl=1800)  # 30 min cache
        
        self.logger.debug(f"Game context compiled with quality score: {context['data_quality']}")
        return context
    
    @safe_api_call(fallback_value={})
    def get_team_data(self, team_name: str, data_types: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Get comprehensive team data from multiple sources.
        
        Args:
            team_name: Normalized team name
            data_types: List of specific data types to fetch (default: all)
            
        Returns:
            Dictionary with all available team data
        """
        if data_types is None:
            data_types = ['info', 'coaching', 'stats', 'schedule']
        
        # Check for cached comprehensive data
        cached_data = self.cache.get_team_data(team_name, 'comprehensive')
        if cached_data and all(dt in cached_data for dt in data_types):
            self.logger.debug(f"Using cached comprehensive data for {team_name}")
            return cached_data
        
        team_data = {
            'team_name': team_name,
            'last_updated': datetime.now().isoformat(),
            'data_sources': []
        }
        
        # Fetch each data type (CFBD primary, ESPN fallback)
        for data_type in data_types:
            try:
                if data_type == 'info':
                    # ESPN is still primary for basic team info
                    team_data['info'] = self.espn_client.get_team_info(team_name)
                    team_data['data_sources'].append('espn_info')
                elif data_type == 'coaching':
                    # Use CFBD first for coaching data
                    if self.cfbd_client:
                        team_data['coaching'] = self.cfbd_client.get_coaching_data(team_name)
                        if team_data['coaching'].get('status') == 'cfbd_data':
                            team_data['data_sources'].append('cfbd_coaching')
                        else:
                            # Fallback to ESPN if CFBD failed
                            team_data['coaching'] = self.espn_client.get_coaching_data(team_name)
                            team_data['data_sources'].append('espn_coaching_fallback')
                    else:
                        team_data['coaching'] = self.espn_client.get_coaching_data(team_name)
                        team_data['data_sources'].append('espn_coaching')
                elif data_type == 'stats':
                    # Use CFBD first for team stats
                    if self.cfbd_client:
                        team_data['stats'] = self.cfbd_client.get_team_stats(team_name)
                        if team_data['stats'].get('status') == 'cfbd_data':
                            team_data['data_sources'].append('cfbd_stats')
                        else:
                            # Fallback to ESPN if CFBD failed
                            team_data['stats'] = self.espn_client.get_team_stats(team_name)
                            team_data['data_sources'].append('espn_stats_fallback')
                    else:
                        team_data['stats'] = self.espn_client.get_team_stats(team_name)
                        team_data['data_sources'].append('espn_stats')
                elif data_type == 'schedule':
                    # ESPN is still primary for schedule data
                    team_data['schedule'] = self.espn_client.get_team_schedule(team_name)
                    team_data['data_sources'].append('espn_schedule')
                
                self.logger.debug(f"Retrieved {data_type} data for {team_name}")
                
            except Exception as e:
                self.logger.warning(f"Failed to get {data_type} data for {team_name}: {e}")
                team_data[data_type] = self._get_neutral_data_structure(data_type, team_name)
        
        # Add derived metrics
        team_data['derived_metrics'] = self._calculate_derived_metrics(team_data)
        
        # Cache comprehensive data
        self.cache.cache_team_data(team_name, team_data, 'comprehensive', ttl=3600)  # 1 hour cache
        
        return team_data
    
    @safe_api_call(fallback_value={})
    def get_coaching_comparison(self, home_team: str, away_team: str) -> Dict[str, Any]:
        """
        Get coaching comparison between two teams.
        Uses CFBD API as primary source with ESPN fallback.
        
        Args:
            home_team: Normalized home team name
            away_team: Normalized away team name
            
        Returns:
            Dictionary with coaching comparison data
        """
        # Try CFBD first as primary source
        home_coaching = None
        away_coaching = None
        
        if self.cfbd_client:
            try:
                self.logger.debug(f"Using CFBD primary for {home_team} coaching data")
                home_coaching = self.cfbd_client.get_coaching_data(home_team)
                
                self.logger.debug(f"Using CFBD primary for {away_team} coaching data")
                away_coaching = self.cfbd_client.get_coaching_data(away_team)
                
            except Exception as e:
                self.logger.warning(f"CFBD coaching data failed: {e}")
        
        # Fallback to ESPN for any missing or failed data
        home_needs_espn_fallback = (
            home_coaching is None or 
            home_coaching.get('status') == 'default_fallback' or 
            home_coaching.get('head_coach_experience', 0) <= 1
        )
        away_needs_espn_fallback = (
            away_coaching is None or 
            away_coaching.get('status') == 'default_fallback' or 
            away_coaching.get('head_coach_experience', 0) <= 1
        )
        
        if home_needs_espn_fallback:
            self.logger.debug(f"Using ESPN fallback for {home_team} coaching data")
            espn_home_coaching = self.espn_client.get_coaching_data(home_team)
            if espn_home_coaching.get('status') != 'neutral_fallback':
                home_coaching = espn_home_coaching
            elif home_coaching is None:
                home_coaching = espn_home_coaching  # Use even neutral fallback if no CFBD data
        
        if away_needs_espn_fallback:
            self.logger.debug(f"Using ESPN fallback for {away_team} coaching data")
            espn_away_coaching = self.espn_client.get_coaching_data(away_team)
            if espn_away_coaching.get('status') != 'neutral_fallback':
                away_coaching = espn_away_coaching
            elif away_coaching is None:
                away_coaching = espn_away_coaching  # Use even neutral fallback if no CFBD data
        
        # Ensure we have data (fallback to neutral if both failed)
        if home_coaching is None:
            home_coaching = self._get_neutral_data_structure('coaching', home_team)
        if away_coaching is None:
            away_coaching = self._get_neutral_data_structure('coaching', away_team)
        
        comparison = {
            'home_team': home_team,
            'away_team': away_team,
            'home_coaching': home_coaching,
            'away_coaching': away_coaching,
            'experience_differential': self._calculate_experience_differential(home_coaching, away_coaching),
            'head_to_head_record': self._get_head_to_head_coaching_record(home_team, away_team),
            'data_sources': [],
            'last_updated': datetime.now().isoformat()
        }
        
        # Track data sources used
        if home_coaching.get('status') == 'cfbd_data':
            comparison['data_sources'].append('cfbd_home_coaching')
        elif home_coaching.get('status') != 'neutral_fallback':
            comparison['data_sources'].append('espn_home_coaching')
            
        if away_coaching.get('status') == 'cfbd_data':
            comparison['data_sources'].append('cfbd_away_coaching')
        elif away_coaching.get('status') != 'neutral_fallback':
            comparison['data_sources'].append('espn_away_coaching')
        
        return comparison
    
    def safe_data_fetch(self, fetch_function: Callable, *args, **kwargs) -> Any:
        """
        Safely execute a data fetch function with error handling.
        
        Args:
            fetch_function: Function to execute
            *args: Arguments to pass to function
            **kwargs: Keyword arguments to pass to function
            
        Returns:
            Function result or fallback value on error
        """
        try:
            return fetch_function(*args, **kwargs)
        except Exception as e:
            self.logger.warning(f"Safe data fetch failed for {fetch_function.__name__}: {e}")
            return self._get_neutral_fallback(fetch_function.__name__, args, kwargs)
    
    def validate_data_availability(self, home_team: str, away_team: str) -> Dict[str, bool]:
        """
        Check what data is available for a matchup.
        
        Args:
            home_team: Normalized home team name
            away_team: Normalized away team name
            
        Returns:
            Dictionary showing data availability
        """
        availability = {
            'teams_normalized': True,  # If we get here, teams are normalized
            'odds_api_available': self.odds_client is not None,
            'espn_api_available': True,  # ESPN is always available
            'home_team_data': False,
            'away_team_data': False,
            'betting_data': False
        }
        
        # Test team data availability
        try:
            home_data = self.espn_client.get_team_info(home_team)
            availability['home_team_data'] = home_data.get('status') != 'neutral_fallback'
        except:
            pass
        
        try:
            away_data = self.espn_client.get_team_info(away_team)
            availability['away_team_data'] = away_data.get('status') != 'neutral_fallback'
        except:
            pass
        
        # Test betting data availability
        if self.odds_client:
            try:
                spread = self.odds_client.get_consensus_spread(home_team, away_team)
                availability['betting_data'] = spread is not None
            except:
                pass
        
        return availability
    
    def get_data_quality_report(self, home_team: str, away_team: str) -> Dict[str, Any]:
        """
        Generate a data quality report for a matchup.
        
        Args:
            home_team: Normalized home team name
            away_team: Normalized away team name
            
        Returns:
            Dictionary with data quality assessment
        """
        availability = self.validate_data_availability(home_team, away_team)
        
        # Calculate quality score
        total_sources = 5  # teams_normalized, odds_api, espn_api, home_data, away_data
        available_sources = sum(availability.values())
        quality_score = available_sources / total_sources
        
        # Determine quality level
        if quality_score >= 0.8:
            quality_level = 'HIGH'
        elif quality_score >= 0.6:
            quality_level = 'MEDIUM'
        elif quality_score >= 0.4:
            quality_level = 'LOW'
        else:
            quality_level = 'POOR'
        
        return {
            'quality_score': quality_score,
            'quality_level': quality_level,
            'availability': availability,
            'recommendations': self._get_quality_recommendations(availability),
            'timestamp': datetime.now().isoformat()
        }
    
    def _calculate_experience_differential(self, home_coaching: Dict, away_coaching: Dict) -> float:
        """Calculate coaching experience differential."""
        home_exp = home_coaching.get('head_coach_experience', 5)
        away_exp = away_coaching.get('head_coach_experience', 5)
        
        return home_exp - away_exp
    
    def _get_head_to_head_coaching_record(self, home_team: str, away_team: str) -> Dict[str, Any]:
        """Get head-to-head coaching record (placeholder for now)."""
        return {
            'home_wins': 0,
            'away_wins': 0,
            'total_games': 0,
            'note': 'Historical coaching H2H data not yet implemented'
        }
    
    def _calculate_derived_metrics(self, team_data: Dict) -> Dict[str, Any]:
        """Calculate derived metrics from raw team data."""
        metrics = {}
        
        # Extract schedule performance if available
        schedule = team_data.get('schedule', [])
        if schedule:
            completed_games = [g for g in schedule if g.get('completed', False)]
            
            if completed_games:
                wins = len([g for g in completed_games if g.get('result') == 'W'])
                losses = len([g for g in completed_games if g.get('result') == 'L'])
                
                metrics['current_record'] = {
                    'wins': wins,
                    'losses': losses,
                    'win_percentage': wins / (wins + losses) if (wins + losses) > 0 else 0.0
                }
                
                # Home/away performance
                home_games = [g for g in completed_games if g.get('is_home_game', False)]
                away_games = [g for g in completed_games if not g.get('is_home_game', False)]
                
                metrics['venue_performance'] = {
                    'home_record': self._calculate_record(home_games),
                    'away_record': self._calculate_record(away_games)
                }
        
        return metrics
    
    def _calculate_record(self, games: List[Dict]) -> Dict[str, Any]:
        """Calculate win-loss record from games list."""
        wins = len([g for g in games if g.get('result') == 'W'])
        losses = len([g for g in games if g.get('result') == 'L'])
        total = len(games)
        
        return {
            'wins': wins,
            'losses': losses,
            'total_games': total,
            'win_percentage': wins / total if total > 0 else 0.0
        }
    
    def _assess_data_quality(self, context: Dict) -> float:
        """Assess overall data quality for a game context."""
        score = 0.0
        max_score = 5.0
        
        # Betting data availability
        if context.get('has_betting_data', False):
            score += 1.5
        
        # Home team data quality
        home_data = context.get('home_team_data', {})
        if home_data and home_data.get('info', {}).get('status') != 'neutral_fallback':
            score += 1.0
        
        # Away team data quality
        away_data = context.get('away_team_data', {})
        if away_data and away_data.get('info', {}).get('status') != 'neutral_fallback':
            score += 1.0
        
        # Coaching data availability
        if context.get('coaching_comparison', {}).get('home_coaching', {}).get('status') != 'neutral_fallback':
            score += 0.75
        
        if context.get('coaching_comparison', {}).get('away_coaching', {}).get('status') != 'neutral_fallback':
            score += 0.75
        
        return score / max_score
    
    def _get_quality_recommendations(self, availability: Dict[str, bool]) -> List[str]:
        """Get recommendations for improving data quality."""
        recommendations = []
        
        if not availability.get('odds_api_available', False):
            recommendations.append("Configure Odds API key for betting line data")
        
        if not availability.get('betting_data', False):
            recommendations.append("Game may not have betting lines available yet")
        
        if not availability.get('home_team_data', False):
            recommendations.append("Home team data may be limited - check team name normalization")
        
        if not availability.get('away_team_data', False):
            recommendations.append("Away team data may be limited - check team name normalization")
        
        if not recommendations:
            recommendations.append("Data quality is optimal for analysis")
        
        return recommendations
    
    def _get_neutral_data_structure(self, data_type: str, team_name: str) -> Dict[str, Any]:
        """Get neutral data structure for fallback scenarios."""
        base_structure = {
            'team_name': team_name,
            'status': 'neutral_fallback',
            'last_updated': datetime.now().isoformat()
        }
        
        if data_type == 'info':
            base_structure.update({
                'display_name': team_name,
                'conference': {'name': 'Unknown'},
                'venue': {'name': 'Unknown', 'capacity': 50000}
            })
        elif data_type == 'coaching':
            base_structure.update({
                'head_coach_name': 'Unknown',
                'head_coach_experience': 5,
                'tenure_years': 3
            })
        elif data_type == 'stats':
            base_structure.update({
                'season_stats': {
                    'offense': {'points_per_game': 25.0},
                    'defense': {'points_allowed_per_game': 25.0}
                }
            })
        elif data_type == 'schedule':
            base_structure = []  # Empty schedule
        
        return base_structure
    
    def _get_neutral_fallback(self, function_name: str, args: tuple, kwargs: dict) -> Any:
        """Get appropriate fallback value based on function context."""
        self.logger.debug(f"Providing neutral fallback for {function_name}")
        
        if 'team' in function_name.lower():
            return self._get_neutral_data_structure('info', args[0] if args else 'Unknown')
        elif 'coaching' in function_name.lower():
            return self._get_neutral_data_structure('coaching', args[0] if args else 'Unknown')
        elif 'spread' in function_name.lower():
            return None  # No fallback spread
        else:
            return {}
    
    def _initialize_fallback_data(self) -> Dict[str, Any]:
        """Initialize fallback data structures."""
        return {
            'neutral_spread': None,
            'neutral_team_data': self._get_neutral_data_structure('info', 'Unknown'),
            'neutral_coaching_data': self._get_neutral_data_structure('coaching', 'Unknown'),
            'neutral_stats_data': self._get_neutral_data_structure('stats', 'Unknown')
        }
    
    def test_all_connections(self) -> Dict[str, bool]:
        """
        Test connections to all data sources.
        
        Returns:
            Dictionary with connection test results
        """
        results = {}
        
        # Test CFBD API (primary)
        if self.cfbd_client:
            try:
                results['cfbd_api'] = self.cfbd_client.test_connection()
            except Exception as e:
                self.logger.error(f"CFBD API test failed: {e}")
                results['cfbd_api'] = False
        else:
            results['cfbd_api'] = False
        
        # Test ESPN API (fallback)
        try:
            results['espn_api'] = self.espn_client.test_connection()
        except Exception as e:
            self.logger.error(f"ESPN API test failed: {e}")
            results['espn_api'] = False
        
        # Test Odds API
        if self.odds_client:
            try:
                results['odds_api'] = self.odds_client.test_connection()
            except Exception as e:
                self.logger.error(f"Odds API test failed: {e}")
                results['odds_api'] = False
        else:
            results['odds_api'] = False
        
        return results
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return self.cache.get_stats()
    
    def clear_all_caches(self) -> None:
        """Clear all cached data."""
        self.cache.clear_all()
        self.logger.info("All caches cleared")


# Global data manager instance
data_manager = DataManager()