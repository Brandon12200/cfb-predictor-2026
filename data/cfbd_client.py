"""
College Football Data API client for comprehensive CFB statistics.
Provides coaching data, advanced metrics, and team statistics.
"""

import requests
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
import json

from config import config
from utils.rate_limiter import rate_limiter_manager, setup_api_rate_limiters
from data.cache_manager import cache_manager
from utils.normalizer import normalizer


class CFBDataClient:
    """
    Client for College Football Data API (collegefootballdata.com).
    
    Features:
    - Coaching experience and tenure data
    - Advanced team metrics and ratings
    - Historical team statistics
    - Game results and performance data
    - Rate limiting compliance
    - Comprehensive caching
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize CFBD API client."""
        self.api_key = api_key or getattr(config, 'cfbd_api_key', None)
        
        if not self.api_key:
            raise ValueError("CFBD API key is required. Set CFBD_API_KEY in environment or config.")
        
        self.base_url = "https://api.collegefootballdata.com"
        
        # Setup rate limiter (5000 calls/month = ~166/day = ~7/hour for Tier 1)
        if not rate_limiter_manager.get_limiter('cfbd_api'):
            rate_limiter_manager.create_limiter(
                api_name='cfbd_api',
                calls_per_minute=10,  # Reasonable limit for Tier 1
                calls_per_day=150     # Leave headroom for peak usage
            )
        
        self.rate_limiter = rate_limiter_manager.get_limiter('cfbd_api')
        
        # Cache manager
        self.cache = cache_manager
        
        # Session for connection pooling
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {self.api_key}',
            'User-Agent': 'CFB-Contrarian-Predictor/2.0',
            'Accept': 'application/json'
        })
        
        # Logging
        self.logger = logging.getLogger(__name__)
        
        # Team name mapping cache
        self.team_mapping = {}
        
        self.logger.info("CFBD API client initialized")
    
    def get_coaching_data(self, team_name: str, year: int = None) -> Dict[str, Any]:
        """
        Get coaching staff data for a team.
        
        Args:
            team_name: Normalized team name
            year: Season year (defaults to current season)
            
        Returns:
            Dictionary with coaching information including experience
        """
        if year is None:
            # Use current season based on month
            current_year = datetime.now().year
            current_month = datetime.now().month
            year = current_year if current_month >= 8 else current_year - 1
        # Check cache
        cache_key = f"coaching_{year}"
        cached_data = self.cache.get_team_data(team_name, cache_key)
        if cached_data:
            self.logger.debug(f"Using cached CFBD coaching data for {team_name}")
            return cached_data
        
        try:
            # Rate limiting
            self.rate_limiter.wait_if_needed()
            
            # Get coaches for the year
            url = f"{self.base_url}/coaches"
            params = {
                'year': year,
                'team': self._get_cfbd_team_name(team_name)
            }
            
            response = self.session.get(url, params=params, timeout=30)
            
            if response.status_code != 200:
                self.logger.warning(f"CFBD API returned {response.status_code} for {team_name} coaches")
                return self._get_default_coaching_data(team_name)
            
            coaches_data = response.json()
            
            # Process coaching data with full history
            coaching_info = self._process_coaching_data(coaches_data, team_name, year)
            
            # If we got a coach name, fetch their full history for accurate experience
            if coaching_info.get('head_coach_name') and coaching_info['head_coach_name'] != f"{team_name} Head Coach":
                full_experience = self._fetch_coach_full_experience(coaching_info['head_coach_name'])
                if full_experience > coaching_info['head_coach_experience']:
                    coaching_info['head_coach_experience'] = full_experience
            
            # Cache the result
            self.cache.cache_team_data(team_name, coaching_info, cache_key, ttl=86400)  # 24 hour cache
            
            self.logger.debug(f"Retrieved CFBD coaching data for {team_name}")
            return coaching_info
            
        except Exception as e:
            self.logger.error(f"Error fetching CFBD coaching data for {team_name}: {e}")
            return self._get_default_coaching_data(team_name)
    
    def get_team_stats(self, team_name: str, year: int = None) -> Dict[str, Any]:
        """
        Get comprehensive team statistics.
        
        Args:
            team_name: Normalized team name
            year: Season year (defaults to current season)
            
        Returns:
            Dictionary with team statistics
        """
        if year is None:
            # Use current season based on month
            current_year = datetime.now().year
            current_month = datetime.now().month
            year = current_year if current_month >= 8 else current_year - 1
        # Check cache
        cache_key = f"cfbd_stats_{year}"
        cached_data = self.cache.get_team_data(team_name, cache_key)
        if cached_data:
            self.logger.debug(f"Using cached CFBD stats for {team_name}")
            return cached_data
        
        try:
            # Rate limiting
            self.rate_limiter.wait_if_needed()
            
            # Get team season stats
            url = f"{self.base_url}/stats/season"
            params = {
                'year': year,
                'team': self._get_cfbd_team_name(team_name)
            }
            
            response = self.session.get(url, params=params, timeout=30)
            
            if response.status_code != 200:
                self.logger.warning(f"CFBD API returned {response.status_code} for {team_name} stats")
                return self._get_default_stats_data(team_name)
            
            stats_data = response.json()
            
            # Process stats
            processed_stats = self._process_team_stats(stats_data, team_name, year)
            
            # Cache the result
            self.cache.cache_team_data(team_name, processed_stats, cache_key, ttl=3600)  # 1 hour cache
            
            self.logger.debug(f"Retrieved CFBD stats for {team_name}")
            return processed_stats
            
        except Exception as e:
            self.logger.error(f"Error fetching CFBD stats for {team_name}: {e}")
            return self._get_default_stats_data(team_name)
    
    def get_team_ratings(self, team_name: str, year: int = None) -> Dict[str, Any]:
        """
        Get team ratings (SP+, FPI, etc.).
        
        Args:
            team_name: Normalized team name
            year: Season year (defaults to current season)
            
        Returns:
            Dictionary with team ratings
        """
        if year is None:
            # Use current season based on month
            current_year = datetime.now().year
            current_month = datetime.now().month
            year = current_year if current_month >= 8 else current_year - 1
        # Check cache
        cache_key = f"cfbd_ratings_{year}"
        cached_data = self.cache.get_team_data(team_name, cache_key)
        if cached_data:
            self.logger.debug(f"Using cached CFBD ratings for {team_name}")
            return cached_data
        
        try:
            # Rate limiting
            self.rate_limiter.wait_if_needed()
            
            # Get team ratings
            url = f"{self.base_url}/ratings/sp"
            params = {
                'year': year,
                'team': self._get_cfbd_team_name(team_name)
            }
            
            response = self.session.get(url, params=params, timeout=30)
            
            if response.status_code != 200:
                self.logger.warning(f"CFBD API returned {response.status_code} for {team_name} ratings")
                return self._get_default_ratings_data(team_name)
            
            ratings_data = response.json()
            
            # Process ratings
            processed_ratings = self._process_team_ratings(ratings_data, team_name, year)
            
            # Cache the result
            self.cache.cache_team_data(team_name, processed_ratings, cache_key, ttl=3600)  # 1 hour cache
            
            self.logger.debug(f"Retrieved CFBD ratings for {team_name}")
            return processed_ratings
            
        except Exception as e:
            self.logger.error(f"Error fetching CFBD ratings for {team_name}: {e}")
            return self._get_default_ratings_data(team_name)
    
    def _get_cfbd_team_name(self, normalized_name: str) -> str:
        """
        Convert normalized team name to CFBD format.
        
        Args:
            normalized_name: Our normalized team name
            
        Returns:
            CFBD team name format
        """
        # CFBD uses specific team names - map our normalized format to CFBD format
        cfbd_mappings = {
            'TENNESSEE': 'Tennessee',
            'SYRACUSE': 'Syracuse',
            'NC STATE': 'NC State',
            'MISSISSIPPI': 'Ole Miss',
            'MISSISSIPPI STATE': 'Mississippi State',
            'TEXAS A&M': 'Texas A&M',
            'PENN STATE': 'Penn State',
            'OHIO STATE': 'Ohio State',
            'MICHIGAN STATE': 'Michigan State',
            'KANSAS STATE': 'Kansas State',
            'IOWA STATE': 'Iowa State',
            'OKLAHOMA STATE': 'Oklahoma State',
            'TEXAS TECH': 'Texas Tech',
            'WEST VIRGINIA': 'West Virginia',
            'BOSTON COLLEGE': 'Boston College',
            'FLORIDA STATE': 'Florida State',
            'GEORGIA TECH': 'Georgia Tech',
            'NORTH CAROLINA': 'North Carolina',
            'VIRGINIA TECH': 'Virginia Tech',
            'WAKE FOREST': 'Wake Forest',
            'NOTRE DAME': 'Notre Dame',
            'WASHINGTON STATE': 'Washington State',
            'OREGON STATE': 'Oregon State',
            'EAST CAROLINA': 'East Carolina',
            'SOUTH FLORIDA': 'South Florida',
            'NORTH TEXAS': 'North Texas',
            'SOUTHERN MISSISSIPPI': 'Southern Miss',
            'FLORIDA ATLANTIC': 'FAU',
            'FLORIDA INTERNATIONAL': 'FIU',
            'WESTERN KENTUCKY': 'Western Kentucky',
            'MIDDLE TENNESSEE': 'Middle Tennessee',
            'OLD DOMINION': 'Old Dominion',
            'COASTAL CAROLINA': 'Coastal Carolina',
            'GEORGIA STATE': 'Georgia State',
            'GEORGIA SOUTHERN': 'Georgia Southern',
            'TROY': 'Troy',
            'APPALACHIAN STATE': 'Appalachian State',
            'ARKANSAS STATE': 'Arkansas State',
            'LOUISIANA': 'Louisiana',
            'SOUTH ALABAMA': 'South Alabama',
            'TEXAS STATE': 'Texas State',
            'NEW MEXICO STATE': 'New Mexico State',
            'LIBERTY': 'Liberty',
            'ALABAMA': 'Alabama',
            'AUBURN': 'Auburn',
            'ARKANSAS': 'Arkansas',
            'FLORIDA': 'Florida',
            'GEORGIA': 'Georgia',
            'KENTUCKY': 'Kentucky',
            'LSU': 'LSU',
            'MISSOURI': 'Missouri',
            'SOUTH CAROLINA': 'South Carolina',
            'VANDERBILT': 'Vanderbilt',
            'CLEMSON': 'Clemson',
            'DUKE': 'Duke',
            'LOUISVILLE': 'Louisville',
            'MIAMI': 'Miami',
            'PITTSBURGH': 'Pittsburgh',
            'VIRGINIA': 'Virginia'
        }
        
        return cfbd_mappings.get(normalized_name, normalized_name.title())
    
    def _process_coaching_data(self, coaches_data: List[Dict], team_name: str, year: int) -> Dict[str, Any]:
        """Process raw coaching data from CFBD API."""
        if not coaches_data:
            return self._get_default_coaching_data(team_name)
        
        # Use the first coach entry (CFBD returns head coach data even if names are missing)
        head_coach = coaches_data[0]
        
        # Calculate experience based on coaching history
        coach_name = f"{head_coach.get('firstName', '') or ''} {head_coach.get('lastName', '') or ''}".strip()
        
        # If no name is available, use a generic placeholder
        if not coach_name:
            coach_name = f"{team_name} Head Coach"
        
        # Get coaching history to calculate experience
        experience_years = self._calculate_coaching_experience(head_coach, year)
        tenure_years = self._calculate_tenure_years(head_coach, team_name, year)
        
        # If we have meaningful season data, this is valid CFBD data
        seasons = head_coach.get('seasons', [])
        if seasons and any(s.get('year') == year for s in seasons):
            status = 'cfbd_data'
        else:
            status = 'default_fallback'
        
        return {
            'team_name': team_name,
            'head_coach_name': coach_name,
            'head_coach_experience': experience_years,
            'tenure_years': tenure_years,
            'coach_id': head_coach.get('id'),
            'season': year,
            'status': status,
            'last_updated': datetime.now().isoformat()
        }
    
    def _fetch_coach_full_experience(self, coach_name: str) -> int:
        """Fetch full coaching experience by searching coach history."""
        try:
            # Parse coach name
            name_parts = coach_name.split()
            if len(name_parts) < 2:
                return 3  # Default if name parsing fails
            
            first_name = name_parts[0]
            last_name = ' '.join(name_parts[1:])  # Handle names like "Van Der Kamp"
            
            # Rate limiting
            self.rate_limiter.wait_if_needed()
            
            # Search for coach by name to get full history
            url = f"{self.base_url}/coaches"
            params = {
                'firstName': first_name,
                'lastName': last_name
            }
            
            response = self.session.get(url, params=params, timeout=30)
            
            if response.status_code != 200:
                return 3  # Default on API error
            
            coaches_data = response.json()
            if not coaches_data:
                return 3  # Default if no data
            
            # Count all unique years coached
            years = set()
            for coach_record in coaches_data:
                for season in coach_record.get('seasons', []):
                    years.add(season.get('year'))
            
            return len(years) if years else 3
            
        except Exception as e:
            self.logger.warning(f"Error fetching full experience for {coach_name}: {e}")
            return 3  # Default on error
    
    def _calculate_coaching_experience(self, coach_data: Dict, current_year: int) -> int:
        """Calculate total head coaching experience."""
        # CFBD API provides seasons data with coaching records
        seasons = coach_data.get('seasons', [])
        if seasons:
            # Count seasons as head coach experience
            head_coach_seasons = len(seasons)
            
            # Look for earliest season to estimate total experience
            if head_coach_seasons > 0:
                earliest_season = min(season.get('year', current_year) for season in seasons)
                total_experience = current_year - earliest_season + 1
                
                # Use the higher of seasons count or calculated experience
                return max(head_coach_seasons, total_experience)
            
            return head_coach_seasons
        
        # Fallback: estimate based on first year if available
        first_year = coach_data.get('first_year')
        if first_year:
            return current_year - first_year + 1
        
        # Default conservative estimate
        return 3  # More reasonable than 1 year
    
    def _calculate_tenure_years(self, coach_data: Dict, team_name: str, current_year: int) -> int:
        """Calculate years at current school."""
        # Look for seasons data for this specific school
        seasons = coach_data.get('seasons', [])
        if seasons:
            # Filter seasons for this school and count tenure
            school_seasons = [s for s in seasons if s.get('school', '').lower() in [team_name.lower(), self._get_cfbd_team_name(team_name).lower()]]
            if school_seasons:
                earliest_year = min(season.get('year', current_year) for season in school_seasons)
                tenure = current_year - earliest_year + 1
                return max(1, tenure)  # At least 1 year
        
        # Fallback: use first_year if available
        first_year_at_school = coach_data.get('first_year')
        if first_year_at_school:
            return current_year - first_year_at_school + 1
        
        # Default to 2 years if no data (more realistic than 1)
        return 2
    
    def _process_team_stats(self, stats_data: List[Dict], team_name: str, year: int) -> Dict[str, Any]:
        """Process team statistics data."""
        if not stats_data:
            return self._get_default_stats_data(team_name)
        
        # CFBD returns list of stat categories - organize them similar to ESPN structure
        processed_stats = {
            'team_name': team_name,
            'season': year,
            'status': 'cfbd_data',
            'stats': {},  # Raw CFBD stats
            'season_stats': {  # ESPN-compatible structure
                'offense': {},
                'defense': {},
                'special_teams': {}
            },
            'last_updated': datetime.now().isoformat()
        }
        
        # Map CFBD stats to categories
        offensive_stats = ['points', 'totalOffense', 'rushingOffense', 'passingOffense', 'firstDowns']
        defensive_stats = ['pointsAllowed', 'totalDefense', 'rushingDefense', 'passingDefense', 'tacklesForLoss', 'sacks']
        special_teams_stats = ['kickReturns', 'puntReturns', 'fieldGoals']
        
        for stat in stats_data:
            category = stat.get('statName', 'unknown')
            value = stat.get('statValue', 0)
            
            # Store raw stat
            processed_stats['stats'][category] = value
            
            # Map to ESPN-compatible categories
            if category in offensive_stats:
                processed_stats['season_stats']['offense'][category] = value
                # Common ESPN mappings
                if category == 'points':
                    processed_stats['season_stats']['offense']['points_per_game'] = value
                elif category == 'totalOffense':
                    processed_stats['season_stats']['offense']['yards_per_game'] = value
            elif category in defensive_stats:
                processed_stats['season_stats']['defense'][category] = value
                # Common ESPN mappings
                if category == 'pointsAllowed':
                    processed_stats['season_stats']['defense']['points_allowed_per_game'] = value
                elif category == 'totalDefense':
                    processed_stats['season_stats']['defense']['yards_allowed_per_game'] = value
            elif category in special_teams_stats:
                processed_stats['season_stats']['special_teams'][category] = value
        
        return processed_stats
    
    def _process_team_ratings(self, ratings_data: List[Dict], team_name: str, year: int) -> Dict[str, Any]:
        """Process team ratings data."""
        if not ratings_data:
            return self._get_default_ratings_data(team_name)
        
        # CFBD returns list of ratings
        processed_ratings = {
            'team_name': team_name,
            'season': year,
            'status': 'cfbd_data',
            'ratings': {},
            'last_updated': datetime.now().isoformat()
        }
        
        for rating in ratings_data:
            rating_name = rating.get('rating', 'unknown')
            rating_value = rating.get('rating_value', 0)
            processed_ratings['ratings'][rating_name] = rating_value
        
        return processed_ratings
    
    def _get_default_coaching_data(self, team_name: str) -> Dict[str, Any]:
        """Get default coaching data when API fails."""
        return {
            'team_name': team_name,
            'head_coach_name': 'Unknown Coach',
            'head_coach_experience': 3,  # Reasonable default
            'tenure_years': 2,
            'status': 'default_fallback',
            'last_updated': datetime.now().isoformat()
        }
    
    def _get_default_stats_data(self, team_name: str) -> Dict[str, Any]:
        """Get default stats data when API fails."""
        return {
            'team_name': team_name,
            'stats': {},
            'season_stats': {
                'offense': {
                    'points_per_game': 25.0,
                    'yards_per_game': 350.0
                },
                'defense': {
                    'points_allowed_per_game': 25.0,
                    'yards_allowed_per_game': 350.0
                },
                'special_teams': {}
            },
            'status': 'default_fallback',
            'last_updated': datetime.now().isoformat()
        }
    
    def _get_default_ratings_data(self, team_name: str) -> Dict[str, Any]:
        """Get default ratings data when API fails."""
        return {
            'team_name': team_name,
            'ratings': {},
            'status': 'default_fallback',
            'last_updated': datetime.now().isoformat()
        }
    
    def test_connection(self) -> bool:
        """Test connection to CFBD API."""
        try:
            self.rate_limiter.wait_if_needed()
            
            url = f"{self.base_url}/teams"
            params = {'year': 2024}
            
            response = self.session.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                self.logger.info("CFBD API connection successful")
                return True
            else:
                self.logger.warning(f"CFBD API test returned {response.status_code}")
                return False
                
        except Exception as e:
            self.logger.error(f"CFBD API connection test failed: {e}")
            return False

    def get_games(self, year: int = 2024, week: Optional[int] = None, 
                  team: Optional[str] = None, **kwargs) -> List[Dict[str, Any]]:
        """
        Get games from CFBD API for scheduling fatigue analysis.
        
        Args:
            year: Season year
            week: Specific week (optional) 
            team: Specific team name (optional)
            **kwargs: Additional query parameters
            
        Returns:
            List of game dictionaries with scheduling data
        """
        params = {'year': year}
        
        if week:
            params['week'] = week
        if team:
            # Normalize team name for API consistency
            params['team'] = normalizer.normalize(team)
        
        # Add any additional parameters
        params.update(kwargs)
        
        try:
            # Rate limiting
            self.rate_limiter.wait_if_needed()
            
            url = f"{self.base_url}/games"
            response = self.session.get(url, params=params, timeout=30)
            
            if response.status_code != 200:
                self.logger.warning(f"CFBD API returned {response.status_code} for games")
                return []
            
            data = response.json()
            self.logger.info(f"Retrieved {len(data)} games from CFBD API")
            return data
            
        except Exception as e:
            self.logger.error(f"Error fetching CFBD games data: {e}")
            return []

    def get_betting_lines(self, game_id: Optional[int] = None, year: int = 2024, 
                         week: Optional[int] = None, **kwargs) -> List[Dict[str, Any]]:
        """
        Get betting lines from CFBD API for market sentiment analysis.
        
        Args:
            game_id: Specific game ID (optional)
            year: Season year 
            week: Specific week (optional)
            **kwargs: Additional query parameters
            
        Returns:
            List of betting line dictionaries
        """
        params = {'year': year}
        
        if game_id:
            params['gameId'] = game_id
        if week:
            params['week'] = week
            
        # Add any additional parameters  
        params.update(kwargs)
        
        try:
            # Rate limiting
            self.rate_limiter.wait_if_needed()
            
            url = f"{self.base_url}/lines"
            response = self.session.get(url, params=params, timeout=30)
            
            if response.status_code != 200:
                self.logger.warning(f"CFBD API returned {response.status_code} for betting lines")
                return []
            
            data = response.json()
            self.logger.info(f"Retrieved {len(data)} betting lines from CFBD API")
            return data
            
        except Exception as e:
            self.logger.error(f"Error fetching CFBD betting lines: {e}")
            return []

    def get_advanced_stats(self, year: int = 2024, team: Optional[str] = None, 
                          **kwargs) -> List[Dict[str, Any]]:
        """
        Get advanced team statistics from CFBD API for StyleMismatch analysis.
        
        Args:
            year: Season year
            team: Specific team name (optional)
            **kwargs: Additional query parameters
            
        Returns:
            List of advanced stats dictionaries with EPA, success rates, explosiveness
        """
        params = {'year': year}
        
        if team:
            # Normalize team name for API consistency
            params['team'] = normalizer.normalize(team)
        
        # Add any additional parameters
        params.update(kwargs)
        
        try:
            # Rate limiting
            self.rate_limiter.wait_if_needed()
            
            url = f"{self.base_url}/stats/season/advanced"
            response = self.session.get(url, params=params, timeout=30)
            
            if response.status_code != 200:
                self.logger.warning(f"CFBD API returned {response.status_code} for advanced stats")
                return []
            
            data = response.json()
            self.logger.info(f"Retrieved {len(data)} advanced stats records from CFBD API")
            return data
            
        except Exception as e:
            self.logger.error(f"Error fetching CFBD advanced stats: {e}")
            return []


# Global CFBD client instance
cfbd_client = None

def get_cfbd_client() -> Optional[CFBDataClient]:
    """Get global CFBD client instance."""
    global cfbd_client
    
    if cfbd_client is None:
        try:
            cfbd_client = CFBDataClient()
        except ValueError as e:
            logging.getLogger(__name__).warning(f"CFBD client not available: {e}")
            return None
    
    return cfbd_client