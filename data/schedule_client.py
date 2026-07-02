"""
CFB Schedule API client for comprehensive game listings.
Fetches weekly schedules with complete P4 game information.
"""

import requests
import logging
import time
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
import json

from config import config
from utils.rate_limiter import rate_limiter_manager
from data.cache_manager import cache_manager
from utils.normalizer import normalizer


class CFBScheduleClient:
    """
    Client for fetching comprehensive CFB weekly schedules.
    
    Features:
    - Week-by-week game listings
    - P4 conference filtering
    - Game time and venue information
    - Integration with existing odds data
    - Comprehensive caching
    """
    
    def __init__(self):
        """Initialize CFB Schedule API client."""
        self.base_url = "https://site.api.espn.com/apis/site/v2/sports/football/college-football"

        # Use ESPN rate limiter - initialize if not exists
        self.rate_limiter = rate_limiter_manager.get_limiter('espn_api')
        if not self.rate_limiter:
            # Create a simple rate limiter if none exists
            from utils.rate_limiter import setup_api_rate_limiters
            setup_api_rate_limiters(odds_limit=10, espn_limit=20)
            self.rate_limiter = rate_limiter_manager.get_limiter('espn_api')

        # Cache manager
        self.cache = cache_manager

        # Initialize CFBD client for more complete schedule data
        try:
            from data.cfbd_client import CFBDataClient
            self.cfbd_client = CFBDataClient()
            self.logger = logging.getLogger(__name__)
            self.logger.info("CFBD client initialized for schedule data")
        except Exception as e:
            self.logger = logging.getLogger(__name__)
            self.logger.warning(f"CFBD client not available: {e}")
            self.cfbd_client = None

        # Session for connection pooling
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'CFB-Contrarian-Predictor/2.0',
            'Accept': 'application/json'
        })

        # P4 Conference definitions
        self.p4_conferences = {
            'SEC', 'BIG TEN', 'BIG 12', 'ACC', 'PAC-12', 'PACIFIC-12'
        }

        # Logging
        self.logger.info("CFB Schedule API client initialized")
    
    def get_week_schedule(self, week: int, year: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get all games for a specific week.

        Args:
            week: Week number (1-17 for regular season)
            year: Season year (default: most recent completed season)

        Returns:
            List of games with team names, times, venues
        """
        if year is None:
            # During offseason (July), use previous year's completed season
            current_year = datetime.now().year
            current_month = datetime.now().month

            if current_month < 8:  # Before August, use previous year
                year = current_year - 1
            else:
                year = current_year

        # Check cache first
        cache_key = f"week_schedule_{year}_{week}"
        cached_data = self.cache.get_team_data('_schedule', cache_key)
        if cached_data:
            self.logger.debug(f"Using cached schedule for Week {week} {year}")
            return cached_data

        # Try CFBD first for more complete schedule data
        if self.cfbd_client:
            try:
                cfbd_games = self.cfbd_client.get_games(year=year, week=week)
                if cfbd_games:
                    self.logger.info(f"CFBD API returned {len(cfbd_games)} games for Week {week} {year}")
                    games = self._process_cfbd_schedule(cfbd_games, week, year)

                    # Cache the result
                    self.cache.cache_team_data('_schedule', games, cache_key, ttl=3600)  # 1 hour cache

                    self.logger.info(f"Processed {len(games)} games from CFBD for Week {week} {year}")
                    return games
            except Exception as e:
                self.logger.warning(f"CFBD schedule fetch failed, falling back to ESPN: {e}")

        # Fallback to ESPN API
        try:
            # Rate limiting
            self.rate_limiter.wait_if_needed()

            # Fetch week schedule from ESPN
            url = f"{self.base_url}/scoreboard"
            params = {
                'season': year,
                'seasontype': 2,  # Regular season
                'week': week
            }

            response = self.session.get(url, params=params, timeout=30)

            if response.status_code != 200:
                self.logger.warning(f"ESPN API returned {response.status_code} for week {week} schedule")
                # Try without week parameter for current/recent data
                self.logger.info(f"Attempting fallback request without week parameter")
                response = self.session.get(f"{self.base_url}/scoreboard", timeout=30)

                if response.status_code != 200:
                    self.logger.error(f"ESPN API fallback also failed: {response.status_code}")
                    return []

            data = response.json()

            # Debug: Log the structure we get back
            self.logger.debug(f"ESPN API response structure: {list(data.keys())}")
            events = data.get('events', [])
            self.logger.info(f"ESPN API returned {len(events)} events for Week {week} {year}")

            # Process schedule data
            games = self._process_week_schedule(data, week, year)

            # Cache the result
            self.cache.cache_team_data('_schedule', games, cache_key, ttl=3600)  # 1 hour cache

            self.logger.info(f"Retrieved {len(games)} total games, processed {len(games)} for Week {week} {year}")
            return games

        except Exception as e:
            self.logger.error(f"Error fetching schedule for Week {week}: {e}")
            return []
    
    def get_p4_games(self, week: int, year: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get only P4 conference games for a specific week.
        
        Args:
            week: Week number
            year: Season year (default: current year)
            
        Returns:
            List of P4 games filtered from full schedule
        """
        all_games = self.get_week_schedule(week, year)
        
        p4_games = []
        for game in all_games:
            home_conf = game.get('home_conference', '').upper()
            away_conf = game.get('away_conference', '').upper()
            
            self.logger.debug(f"Game: {game.get('away_team_short', 'N/A')} @ {game.get('home_team_short', 'N/A')} - Conferences: {away_conf} vs {home_conf}")
            
            # Include game if either team is P4
            if home_conf in self.p4_conferences or away_conf in self.p4_conferences:
                p4_games.append(game)
        
        self.logger.debug(f"Filtered to {len(p4_games)} P4 games from {len(all_games)} total")
        return p4_games
    
    def get_game_matchups(self, week: int, year: Optional[int] = None) -> List[Tuple[str, str]]:
        """
        Get list of team matchups for easy testing.
        
        Args:
            week: Week number
            year: Season year
            
        Returns:
            List of (home_team, away_team) tuples
        """
        games = self.get_p4_games(week, year)
        
        matchups = []
        for game in games:
            home_team = game.get('home_team_normalized')
            away_team = game.get('away_team_normalized')
            
            if home_team and away_team:
                matchups.append((home_team, away_team))
        
        return matchups
    
    def _process_cfbd_schedule(self, cfbd_games: List[Dict], week: int, year: int) -> List[Dict[str, Any]]:
        """Process CFBD API games response into standardized game list."""
        games = []

        for game in cfbd_games:
            try:
                game_info = self._extract_game_from_cfbd(game, week, year)
                if game_info:
                    games.append(game_info)
            except Exception as e:
                self.logger.warning(f"Error processing CFBD game: {e}")
                continue

        return games

    def _extract_game_from_cfbd(self, game: Dict, week: int, year: int) -> Optional[Dict[str, Any]]:
        """Extract game information from CFBD API response."""
        home_team = game.get('homeTeam', '')
        away_team = game.get('awayTeam', '')

        if not home_team or not away_team:
            return None

        # Get conference info
        home_conf = game.get('homeConference', '').upper()
        away_conf = game.get('awayConference', '').upper()

        return {
            'week': week,
            'year': year,
            'game_id': str(game.get('id', '')),
            'date': game.get('startDate', ''),
            'name': f"{away_team} at {home_team}",
            'short_name': f"{away_team} @ {home_team}",

            # Home team info
            'home_team': home_team,
            'home_team_short': home_team,
            'home_team_abbrev': home_team[:4].upper(),
            'home_team_normalized': normalizer.normalize(home_team),
            'home_conference': home_conf,
            'home_ranking': None,  # CFBD doesn't provide rankings in games endpoint
            'home_record': '',

            # Away team info
            'away_team': away_team,
            'away_team_short': away_team,
            'away_team_abbrev': away_team[:4].upper(),
            'away_team_normalized': normalizer.normalize(away_team),
            'away_conference': away_conf,
            'away_ranking': None,
            'away_record': '',

            # Game details
            'venue_name': game.get('venue', ''),
            'venue_city': '',
            'venue_state': '',
            'neutral_site': game.get('neutralSite', False),
            'conference_game': game.get('conferenceGame', False),

            # Status
            'status': 'scheduled',
            'completed': game.get('completed', False),
            'started': game.get('completed', False)
        }

    def _process_week_schedule(self, data: Dict, week: int, year: int) -> List[Dict[str, Any]]:
        """Process raw ESPN scoreboard response into game list."""
        events = data.get('events', [])
        games = []

        for event in events:
            try:
                game_info = self._extract_game_from_event(event, week, year)
                if game_info:
                    games.append(game_info)
            except Exception as e:
                self.logger.warning(f"Error processing game event: {e}")
                continue

        return games
    
    def _extract_game_from_event(self, event: Dict, week: int, year: int) -> Optional[Dict[str, Any]]:
        """Extract game information from ESPN event."""
        competitions = event.get('competitions', [])
        if not competitions:
            return None
        
        competition = competitions[0]
        competitors = competition.get('competitors', [])
        
        if len(competitors) != 2:
            return None
        
        # Extract team information
        home_team = None
        away_team = None
        
        for competitor in competitors:
            team_data = competitor.get('team', {})
            is_home = competitor.get('homeAway') == 'home'
            
            team_info = {
                'display_name': team_data.get('displayName', ''),
                'short_name': team_data.get('shortDisplayName', ''),
                'abbreviation': team_data.get('abbreviation', ''),
                'conference': self._extract_conference_name(team_data, competitor),
                'ranking': self._extract_ranking(competitor),
                'record': self._extract_team_record(competitor),
                'normalized_name': normalizer.normalize(team_data.get('displayName', ''))
            }
            
            if is_home:
                home_team = team_info
            else:
                away_team = team_info
        
        if not home_team or not away_team:
            return None
        
        # Extract game details
        venue_data = competition.get('venue', {})
        status_data = event.get('status', {})
        
        return {
            'week': week,
            'year': year,
            'game_id': event.get('id'),
            'date': event.get('date'),
            'name': event.get('name', ''),
            'short_name': event.get('shortName', ''),
            
            # Home team info
            'home_team': home_team['display_name'],
            'home_team_short': home_team['short_name'],
            'home_team_abbrev': home_team['abbreviation'],
            'home_team_normalized': home_team['normalized_name'],
            'home_conference': home_team['conference'],
            'home_ranking': home_team['ranking'],
            'home_record': home_team['record'],
            
            # Away team info
            'away_team': away_team['display_name'],
            'away_team_short': away_team['short_name'],
            'away_team_abbrev': away_team['abbreviation'],
            'away_team_normalized': away_team['normalized_name'],
            'away_conference': away_team['conference'],
            'away_ranking': away_team['ranking'],
            'away_record': away_team['record'],
            
            # Game details
            'venue_name': venue_data.get('fullName', ''),
            'venue_city': venue_data.get('address', {}).get('city', ''),
            'venue_state': venue_data.get('address', {}).get('state', ''),
            'neutral_site': competition.get('neutralSite', False),
            'conference_game': competition.get('conferenceCompetition', False),
            
            # Status
            'status': status_data.get('type', {}).get('name', ''),
            'completed': status_data.get('type', {}).get('completed', False),
            'started': status_data.get('type', {}).get('state') != 'pre'
        }
    
    def _extract_conference_name(self, team_data: Dict, competitor: Dict) -> str:
        """Extract conference name from team data or competitor data."""
        # First check team data for conference info
        for conf_field in ['conference', 'group', 'division']:
            if conf_field in team_data:
                conf_data = team_data[conf_field]
                if isinstance(conf_data, dict):
                    conf_name = conf_data.get('shortDisplayName', conf_data.get('name', ''))
                    if conf_name:
                        self.logger.debug(f"Found conference in team_data: {conf_name}")
                        return conf_name
                else:
                    conf_name = str(conf_data)
                    if conf_name:
                        self.logger.debug(f"Found conference in team_data: {conf_name}")
                        return conf_name
        
        # Check competitor data for conference info
        for conf_field in ['conference', 'group', 'division']:
            if conf_field in competitor:
                conf_data = competitor[conf_field]
                if isinstance(conf_data, dict):
                    conf_name = conf_data.get('shortDisplayName', conf_data.get('name', ''))
                    if conf_name:
                        self.logger.debug(f"Found conference in competitor: {conf_name}")
                        return conf_name
        
        # Hardcode P4 teams based on team name if ESPN data is missing
        team_name = team_data.get('displayName', '').upper()
        hardcoded_conf = self._get_hardcoded_conference(team_name)
        if hardcoded_conf:
            self.logger.debug(f"Using hardcoded conference for {team_name}: {hardcoded_conf}")
            return hardcoded_conf
        
        self.logger.debug(f"No conference found for {team_name}, using Independent")
        return 'Independent'
    
    def _get_hardcoded_conference(self, team_name: str) -> Optional[str]:
        """Get conference for known P4 teams when ESPN data is missing."""
        p4_teams = {
            # SEC
            'ALABAMA': 'SEC', 'ARKANSAS': 'SEC', 'AUBURN': 'SEC', 'FLORIDA': 'SEC',
            'GEORGIA': 'SEC', 'KENTUCKY': 'SEC', 'LSU': 'SEC', 'MISSISSIPPI': 'SEC',
            'MISSISSIPPI STATE': 'SEC', 'MISSOURI': 'SEC', 'SOUTH CAROLINA': 'SEC',
            'TENNESSEE': 'SEC', 'TEXAS': 'SEC', 'TEXAS A&M': 'SEC', 'VANDERBILT': 'SEC',
            'OKLAHOMA': 'SEC',
            
            # BIG TEN
            'ILLINOIS': 'BIG TEN', 'INDIANA': 'BIG TEN', 'IOWA': 'BIG TEN', 'MARYLAND': 'BIG TEN',
            'MICHIGAN': 'BIG TEN', 'MICHIGAN STATE': 'BIG TEN', 'MINNESOTA': 'BIG TEN',
            'NEBRASKA': 'BIG TEN', 'NORTHWESTERN': 'BIG TEN', 'OHIO STATE': 'BIG TEN',
            'PENN STATE': 'BIG TEN', 'PURDUE': 'BIG TEN', 'RUTGERS': 'BIG TEN',
            'WISCONSIN': 'BIG TEN', 'OREGON': 'BIG TEN', 'WASHINGTON': 'BIG TEN',
            'UCLA': 'BIG TEN', 'USC': 'BIG TEN',
            
            # BIG 12
            'BAYLOR': 'BIG 12', 'IOWA STATE': 'BIG 12', 'KANSAS': 'BIG 12',
            'KANSAS STATE': 'BIG 12', 'OKLAHOMA STATE': 'BIG 12', 'TCU': 'BIG 12',
            'TEXAS TECH': 'BIG 12', 'WEST VIRGINIA': 'BIG 12', 'CINCINNATI': 'BIG 12',
            'HOUSTON': 'BIG 12', 'UCF': 'BIG 12', 'BYU': 'BIG 12', 'COLORADO': 'BIG 12',
            'UTAH': 'BIG 12', 'ARIZONA': 'BIG 12', 'ARIZONA STATE': 'BIG 12',
            
            # ACC
            'BOSTON COLLEGE': 'ACC', 'CLEMSON': 'ACC', 'DUKE': 'ACC', 'FLORIDA STATE': 'ACC',
            'GEORGIA TECH': 'ACC', 'LOUISVILLE': 'ACC', 'MIAMI': 'ACC', 'NC STATE': 'ACC',
            'NORTH CAROLINA': 'ACC', 'PITTSBURGH': 'ACC', 'SYRACUSE': 'ACC',
            'VIRGINIA': 'ACC', 'VIRGINIA TECH': 'ACC', 'WAKE FOREST': 'ACC',
            'NOTRE DAME': 'ACC'
        }
        
        # Try exact match first
        if team_name in p4_teams:
            return p4_teams[team_name]
        
        # Try partial matches for common variations
        for p4_team, conf in p4_teams.items():
            if p4_team in team_name or any(word in team_name for word in p4_team.split()):
                return conf
        
        return None
    
    def _extract_ranking(self, competitor: Dict) -> Optional[int]:
        """Extract AP/CFP ranking if available."""
        rankings = competitor.get('rankings', [])
        if rankings:
            # Look for AP or CFP ranking
            for ranking in rankings:
                if ranking.get('type') in ['ap', 'cfp']:
                    return ranking.get('current')
        
        return None
    
    def _extract_team_record(self, competitor: Dict) -> str:
        """Extract team's current record."""
        record_data = competitor.get('record', {})
        wins = record_data.get('wins', 0)
        losses = record_data.get('losses', 0)
        ties = record_data.get('ties', 0)
        
        if ties > 0:
            return f"{wins}-{losses}-{ties}"
        else:
            return f"{wins}-{losses}"
    
    def format_games_list(self, games: List[Dict[str, Any]], show_odds: bool = False) -> str:
        """
        Format games list for command line display.
        
        Args:
            games: List of game dictionaries
            show_odds: Whether to attempt to show betting odds
            
        Returns:
            Formatted string for display
        """
        if not games:
            return "No games found for the specified week."
        
        output = []
        output.append(f"CFB Week {games[0]['week']} Schedule - {len(games)} Games")
        output.append("=" * 60)
        
        for i, game in enumerate(games, 1):
            # Basic game info
            away_team = game['away_team_short']
            home_team = game['home_team_short']
            venue = game['venue_name']
            
            # Add rankings if available
            away_display = away_team
            if game['away_ranking']:
                away_display = f"#{game['away_ranking']} {away_team}"
            
            home_display = home_team
            if game['home_ranking']:
                home_display = f"#{game['home_ranking']} {home_team}"
            
            # Format game line
            game_line = f"{i:2d}. {away_display:20} @ {home_display:20}"
            
            # Add venue if not home team's venue
            if game['neutral_site']:
                game_line += f" (Neutral: {venue})"
            
            output.append(game_line)
            
            # Add normalized names for easy copy-paste
            normalized_line = f"    Normalized: {game['away_team_normalized']} @ {game['home_team_normalized']}"
            output.append(normalized_line)
            
            output.append("")  # Blank line between games
        
        return "\n".join(output)
    
    def test_connection(self) -> bool:
        """
        Test ESPN Schedule API connection.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            self.rate_limiter.wait_if_needed()
            
            # Test with current week
            url = f"{self.base_url}/scoreboard"
            response = self.session.get(url, timeout=10)
            
            if response.status_code == 200:
                self.logger.info("ESPN Schedule API connection test successful")
                return True
            else:
                self.logger.error(f"ESPN Schedule API connection test failed: {response.status_code}")
                return False
                
        except Exception as e:
            self.logger.error(f"ESPN Schedule API connection test error: {e}")
            return False
    
    def __del__(self):
        """Cleanup session on destruction."""
        if hasattr(self, 'session'):
            self.session.close()