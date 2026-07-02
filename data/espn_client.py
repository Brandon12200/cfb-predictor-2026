"""
ESPN API client for College Football Market Edge Platform.
Fetches team information, coaching data, statistics, and schedules.
"""

import requests
import logging
import time
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta
import json

from config import config
from utils.rate_limiter import rate_limiter_manager, setup_api_rate_limiters
from data.cache_manager import cache_manager
from utils.normalizer import normalizer


class ESPNStatsClient:
    """
    Client for ESPN API to fetch college football team data.
    
    Features:
    - Team information and statistics
    - Coaching data and tenure information
    - Game schedules and results
    - Venue performance data
    - Rate limiting compliance
    - Comprehensive caching
    """
    
    def __init__(self):
        """Initialize ESPN API client."""
        self.base_url = "https://site.api.espn.com/apis/site/v2/sports/football/college-football"
        
        # Setup rate limiter
        if not rate_limiter_manager.get_limiter('espn_api'):
            setup_api_rate_limiters(
                odds_limit=config.rate_limit_odds,
                espn_limit=config.rate_limit_espn
            )
        
        self.rate_limiter = rate_limiter_manager.get_limiter('espn_api')
        
        # Cache manager
        self.cache = cache_manager
        
        # Session for connection pooling
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'CFB-Contrarian-Predictor/2.0',
            'Accept': 'application/json'
        })
        
        # Team ID cache (ESPN uses numeric IDs) - pre-populate with known IDs
        self.team_id_cache = {
            'OHIO STATE': 194,
            'MICHIGAN': 130,
            'TEXAS': 251,
            'ALABAMA': 333,
            'GEORGIA': 61,
            'FLORIDA': 57,
            'LSU': 99,
            'CLEMSON': 228,
            'NOTRE DAME': 87,
            'USC': 30,
            'PENN STATE': 213,
            'OKLAHOMA': 201,
            'TENNESSEE': 2633,
            'AUBURN': 2,
            'WISCONSIN': 275,
            'IOWA': 2294,
            'NEBRASKA': 158,
            'OREGON': 2483,
            'WASHINGTON': 264,
            'MICHIGAN STATE': 127,
            'FLORIDA STATE': 52,
            'MIAMI': 2390,
            'VIRGINIA TECH': 259,
            'NORTH CAROLINA': 153,
            'NC STATE': 152,
            'STANFORD': 24,
            'UCLA': 26,
            'ARIZONA': 12,
            'ARIZONA STATE': 9,
            'COLORADO': 38,
            'UTAH': 254,
            'WEST VIRGINIA': 277,
            'TEXAS A&M': 245,
            'ARKANSAS': 8,
            'MISSISSIPPI': 145,
            'MISSISSIPPI STATE': 344,
            'KENTUCKY': 96,
            'SOUTH CAROLINA': 2579,
            'VANDERBILT': 238,
            'MISSOURI': 142,
            'KANSAS': 2305,
            'KANSAS STATE': 2306,
            'IOWA STATE': 66,
            'OKLAHOMA STATE': 197,
            'TCU': 2628,
            'TEXAS TECH': 2641,
            'BAYLOR': 239,
            'MINNESOTA': 135,
            'ILLINOIS': 356,
            'INDIANA': 84,
            'PURDUE': 2509,
            'NORTHWESTERN': 77,
            'MARYLAND': 120,
            'RUTGERS': 164,
            'BOSTON COLLEGE': 103,
            'SYRACUSE': 183,
            'PITTSBURGH': 221,
            'DUKE': 150,
            'WAKE FOREST': 154,
            'GEORGIA TECH': 59,
            'LOUISVILLE': 97,
            'VIRGINIA': 258,
            'OREGON STATE': 204,
            'WASHINGTON STATE': 265,
            'CALIFORNIA': 25,
            'CINCINNATI': 2132,
            'HOUSTON': 248,
            'SMU': 2567,
            'MEMPHIS': 235,
            'TULANE': 2655,
            'UCF': 2116,
            'SOUTH FLORIDA': 58,
            'TEMPLE': 218,
            'EAST CAROLINA': 151,
            'NAVY': 2426,
            'ARMY': 349,
            'AIR FORCE': 2005
        }
        
        # Logging
        self.logger = logging.getLogger(__name__)
        
        self.logger.info("ESPN API client initialized")
    
    def get_team_info(self, team_name: str) -> Dict[str, Any]:
        """
        Get comprehensive team information including basic stats and info.
        
        Args:
            team_name: Normalized team name
            
        Returns:
            Dictionary with team information
        """
        # Check cache first
        cached_data = self.cache.get_team_data(team_name, 'info')
        if cached_data:
            self.logger.debug(f"Using cached team info for {team_name}")
            return cached_data
        
        try:
            # Get team ID first
            team_id = self.find_team_id(team_name)
            if not team_id:
                return self._get_neutral_team_data(team_name, 'info')
            
            # Rate limiting
            self.rate_limiter.wait_if_needed()
            
            # Fetch team data
            url = f"{self.base_url}/teams/{team_id}"
            response = self.session.get(url, timeout=30)
            
            if response.status_code != 200:
                self.logger.warning(f"ESPN API returned {response.status_code} for team {team_name}")
                return self._get_neutral_team_data(team_name, 'info')
            
            data = response.json()
            
            # Process team data
            team_info = self._process_team_info(data, team_name)
            
            # Cache the result
            self.cache.cache_team_data(team_name, team_info, 'info', ttl=3600)  # 1 hour cache
            
            self.logger.debug(f"Retrieved team info for {team_name}")
            return team_info
            
        except Exception as e:
            self.logger.error(f"Error fetching team info for {team_name}: {e}")
            return self._get_neutral_team_data(team_name, 'info')
    
    def get_team_schedule(self, team_name: str, year: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get team schedule and game results.
        
        Args:
            team_name: Normalized team name
            year: Season year (default: most recent completed season)
            
        Returns:
            List of games with results and details
        """
        if year is None:
            # Use most recent completed season (usually previous year during off-season)
            current_year = datetime.now().year
            current_month = datetime.now().month
            
            # If it's before August, use previous year's data (off-season)
            if current_month < 8:
                year = current_year - 1
            else:
                year = current_year
        
        # Check cache
        cache_key = f"schedule_{year}"
        cached_data = self.cache.get_team_data(team_name, cache_key)
        if cached_data:
            self.logger.debug(f"Using cached schedule for {team_name} {year}")
            return cached_data
        
        try:
            team_id = self.find_team_id(team_name)
            if not team_id:
                return []
            
            # Rate limiting
            self.rate_limiter.wait_if_needed()
            
            # Fetch schedule
            url = f"{self.base_url}/teams/{team_id}/schedule"
            params = {'season': year}
            
            response = self.session.get(url, params=params, timeout=30)
            
            if response.status_code != 200:
                self.logger.warning(f"ESPN API returned {response.status_code} for {team_name} schedule")
                return []
            
            data = response.json()
            
            # Process schedule data
            schedule = self._process_schedule_data(data, team_name)
            
            # Cache the result
            self.cache.cache_team_data(team_name, schedule, cache_key, ttl=1800)  # 30 min cache
            
            self.logger.debug(f"Retrieved schedule for {team_name} {year}: {len(schedule)} games")
            return schedule
            
        except Exception as e:
            self.logger.error(f"Error fetching schedule for {team_name}: {e}")
            return []
    
    def get_coaching_data(self, team_name: str) -> Dict[str, Any]:
        """
        Get coaching staff information and tenure data.
        
        Args:
            team_name: Normalized team name
            
        Returns:
            Dictionary with coaching information
        """
        # Check cache
        cached_data = self.cache.get_team_data(team_name, 'coaching')
        if cached_data:
            self.logger.debug(f"Using cached coaching data for {team_name}")
            return cached_data
        
        try:
            team_id = self.find_team_id(team_name)
            if not team_id:
                return self._get_neutral_coaching_data(team_name)
            
            # Rate limiting
            self.rate_limiter.wait_if_needed()
            
            # Fetch team roster/staff (coaching info sometimes included)
            url = f"{self.base_url}/teams/{team_id}/roster"
            response = self.session.get(url, timeout=30)
            
            coaching_data = self._get_neutral_coaching_data(team_name)
            
            if response.status_code == 200:
                data = response.json()
                coaching_data.update(self._extract_coaching_info(data, team_name))
            
            # Try alternative endpoint for coaching staff
            self.rate_limiter.wait_if_needed()
            
            url = f"{self.base_url}/teams/{team_id}"
            response = self.session.get(url, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                coaching_data.update(self._extract_coaching_from_team_data(data, team_name))
            
            # Cache the result
            self.cache.cache_team_data(team_name, coaching_data, 'coaching', ttl=7200)  # 2 hour cache
            
            self.logger.debug(f"Retrieved coaching data for {team_name}")
            return coaching_data
            
        except Exception as e:
            self.logger.error(f"Error fetching coaching data for {team_name}: {e}")
            return self._get_neutral_coaching_data(team_name)
    
    def get_team_stats(self, team_name: str, year: Optional[int] = None) -> Dict[str, Any]:
        """
        Get team statistics for the season.
        
        Args:
            team_name: Normalized team name
            year: Season year (default: most recent available season)
            
        Returns:
            Dictionary with team statistics
        """
        if year is None:
            # Use current season based on month
            current_year = datetime.now().year
            current_month = datetime.now().month
            
            # If we're in early months (Jan-July), use previous year
            # If we're in Aug+, use current year (season has started)
            if current_month < 8:
                year = current_year - 1
            else:
                year = current_year
        
        # Check cache
        cache_key = f"stats_{year}"
        cached_data = self.cache.get_team_data(team_name, cache_key)
        if cached_data:
            self.logger.debug(f"Using cached stats for {team_name} {year}")
            return cached_data
        
        try:
            team_id = self.find_team_id(team_name)
            if not team_id:
                return self._get_neutral_stats_data(team_name)
            
            # Rate limiting
            self.rate_limiter.wait_if_needed()
            
            # Fetch team statistics
            url = f"{self.base_url}/teams/{team_id}/statistics"
            params = {'season': year}
            
            response = self.session.get(url, params=params, timeout=30)
            
            if response.status_code != 200:
                self.logger.warning(f"ESPN API returned {response.status_code} for {team_name} stats")
                return self._get_neutral_stats_data(team_name)
            
            data = response.json()
            
            # Process statistics
            stats = self._process_team_stats(data, team_name)
            
            # Cache the result
            self.cache.cache_team_data(team_name, stats, cache_key, ttl=1800)  # 30 min cache
            
            self.logger.debug(f"Retrieved stats for {team_name} {year}")
            return stats
            
        except Exception as e:
            self.logger.error(f"Error fetching stats for {team_name}: {e}")
            return self._get_neutral_stats_data(team_name)
    
    def find_team_id(self, team_name: str) -> Optional[int]:
        """
        Find ESPN team ID for a given team name.
        
        Args:
            team_name: Normalized team name
            
        Returns:
            ESPN team ID or None if not found
        """
        # Check cache first
        if team_name in self.team_id_cache:
            return self.team_id_cache[team_name]
        
        # Check if we have cached team list
        cached_teams = self.cache.get_team_data('_all_teams', 'espn_ids')
        if cached_teams and team_name in cached_teams:
            team_id = cached_teams[team_name]
            self.team_id_cache[team_name] = team_id
            return team_id
        
        # Try direct team lookup first (most reliable)
        team_id = self._try_direct_team_lookup(team_name)
        if team_id:
            self.team_id_cache[team_name] = team_id
            return team_id
        
        try:
            # Rate limiting
            self.rate_limiter.wait_if_needed()
            
            # Fetch all teams
            url = f"{self.base_url}/teams"
            response = self.session.get(url, timeout=30)
            
            if response.status_code != 200:
                self.logger.warning(f"ESPN API returned {response.status_code} for teams list")
                return None
            
            data = response.json()
            
            # Build team ID mapping
            team_mapping = {}
            
            for conference in data.get('sports', [{}])[0].get('leagues', [{}])[0].get('children', []):
                for team in conference.get('teams', []):
                    team_info = team.get('team', {})
                    espn_name = team_info.get('displayName', '')
                    espn_short_name = team_info.get('shortDisplayName', '')
                    espn_abbrev = team_info.get('abbreviation', '')
                    team_id = team_info.get('id')
                    
                    if team_id:
                        # Try to normalize ESPN names to our format
                        normalized_names = []
                        for name in [espn_name, espn_short_name, espn_abbrev]:
                            if name:
                                normalized = normalizer.normalize(name)
                                if normalized:
                                    normalized_names.append(normalized)
                        
                        # Map all variants to this team ID
                        for norm_name in normalized_names:
                            team_mapping[norm_name] = int(team_id)
            
            # Cache the full mapping
            self.cache.cache_team_data('_all_teams', team_mapping, 'espn_ids', ttl=86400)  # 24 hour cache
            
            # Update local cache
            self.team_id_cache.update(team_mapping)
            
            # Return the requested team ID
            team_id = team_mapping.get(team_name)
            self.logger.debug(f"Found ESPN team ID for {team_name}: {team_id}")
            
            return team_id
            
        except Exception as e:
            self.logger.error(f"Error finding team ID for {team_name}: {e}")
            return None
    
    def _try_direct_team_lookup(self, team_name: str) -> Optional[int]:
        """
        Try direct team lookup using ESPN's team endpoint.
        This is more reliable than the teams list endpoint.
        
        Args:
            team_name: Normalized team name
            
        Returns:
            ESPN team ID or None if not found
        """
        # Generate possible ESPN team slugs from the normalized name
        possible_slugs = self._generate_team_slugs(team_name)
        
        for slug in possible_slugs:
            try:
                # Rate limiting
                self.rate_limiter.wait_if_needed()
                
                # Try direct lookup
                url = f"{self.base_url}/teams/{slug}"
                response = self.session.get(url, timeout=10)
                
                if response.status_code == 200:
                    data = response.json()
                    team_info = data.get('team', {})
                    team_id = team_info.get('id')
                    
                    if team_id:
                        self.logger.debug(f"Found {team_name} via direct lookup: {slug} -> ID {team_id}")
                        return int(team_id)
                        
            except Exception as e:
                self.logger.debug(f"Direct lookup failed for {slug}: {e}")
                continue
        
        return None
    
    def _generate_team_slugs(self, team_name: str) -> List[str]:
        """Generate possible ESPN team slugs for a normalized team name."""
        slugs = []
        
        # Common mappings for ESPN slugs
        slug_mappings = {
            'CLEMSON': ['clemson'],
            'LSU': ['lsu'],
            'ALABAMA': ['alabama'],
            'GEORGIA': ['georgia'],
            'OHIO STATE': ['ohio-state'],
            'MICHIGAN': ['michigan'],
            'TEXAS': ['texas'],
            'OKLAHOMA': ['oklahoma'],
            'FLORIDA': ['florida'],
            'PENN STATE': ['penn-state'],
            'NOTRE DAME': ['notre-dame'],
            'USC': ['usc'],
            'UCLA': ['ucla'],
            'OREGON': ['oregon'],
            'WASHINGTON': ['washington'],
            'WISCONSIN': ['wisconsin'],
            'IOWA': ['iowa'],
            'NEBRASKA': ['nebraska'],
            'MINNESOTA': ['minnesota'],
            'ILLINOIS': ['illinois'],
            'INDIANA': ['indiana'],
            'MARYLAND': ['maryland'],
            'MICHIGAN STATE': ['michigan-state'],
            'NORTHWESTERN': ['northwestern'],
            'PURDUE': ['purdue'],
            'RUTGERS': ['rutgers'],
            'FLORIDA STATE': ['florida-state'],
            'MIAMI': ['miami'],
            'VIRGINIA TECH': ['virginia-tech'],
            'NORTH CAROLINA': ['north-carolina'],
            'NC STATE': ['nc-state'],
            'DUKE': ['duke'],
            'WAKE FOREST': ['wake-forest'],
            'VIRGINIA': ['virginia'],
            'PITTSBURGH': ['pittsburgh'],
            'SYRACUSE': ['syracuse'],
            'BOSTON COLLEGE': ['boston-college'],
            'LOUISVILLE': ['louisville'],
            'GEORGIA TECH': ['georgia-tech'],
            'TEXAS A&M': ['texas-am'],
            'AUBURN': ['auburn'],
            'ARKANSAS': ['arkansas'],
            'KENTUCKY': ['kentucky'],
            'MISSISSIPPI': ['ole-miss'],
            'MISSISSIPPI STATE': ['mississippi-state'],
            'MISSOURI': ['missouri'],
            'SOUTH CAROLINA': ['south-carolina'],
            'TENNESSEE': ['tennessee'],
            'VANDERBILT': ['vanderbilt'],
            'TEXAS TECH': ['texas-tech'],
            'BAYLOR': ['baylor'],
            'TCU': ['tcu'],
            'OKLAHOMA STATE': ['oklahoma-state'],
            'KANSAS': ['kansas'],
            'KANSAS STATE': ['kansas-state'],
            'IOWA STATE': ['iowa-state'],
            'WEST VIRGINIA': ['west-virginia'],
            'UTAH': ['utah'],
            'COLORADO': ['colorado'],
            'ARIZONA': ['arizona'],
            'ARIZONA STATE': ['arizona-state'],
            'WASHINGTON STATE': ['washington-state'],
            'OREGON STATE': ['oregon-state'],
            'CAL': ['california'],
            'STANFORD': ['stanford']
        }
        
        # Get mapped slugs
        if team_name in slug_mappings:
            slugs.extend(slug_mappings[team_name])
        
        # Generate fallback slugs
        fallback_slug = team_name.lower().replace(' ', '-').replace('&', '')
        if fallback_slug not in slugs:
            slugs.append(fallback_slug)
        
        return slugs
    
    def _process_team_info(self, data: Dict, team_name: str) -> Dict[str, Any]:
        """Process raw team info response."""
        team_data = data.get('team', {})
        
        return {
            'team_name': team_name,
            'espn_id': team_data.get('id'),
            'display_name': team_data.get('displayName', team_name),
            'short_name': team_data.get('shortDisplayName', team_name),
            'abbreviation': team_data.get('abbreviation', ''),
            'color': team_data.get('color', '#000000'),
            'alternate_color': team_data.get('alternateColor', '#FFFFFF'),
            'logo': team_data.get('logos', [{}])[0].get('href', ''),
            'venue': self._extract_venue_info(team_data.get('venue', {})),
            'conference': self._extract_conference_info(team_data.get('groups', {})),
            'record': self._extract_record_info(team_data.get('record', {})),
            'last_updated': datetime.now().isoformat()
        }
    
    def _process_schedule_data(self, data: Dict, team_name: str) -> List[Dict[str, Any]]:
        """Process schedule/results data."""
        events = data.get('events', [])
        games = []
        
        for event in events:
            try:
                game_info = self._extract_game_info(event, team_name)
                if game_info:
                    games.append(game_info)
            except Exception as e:
                self.logger.warning(f"Error processing game event: {e}")
                continue
        
        return games
    
    def _process_team_stats(self, data: Dict, team_name: str) -> Dict[str, Any]:
        """Process team statistics data."""
        stats_data = {
            'team_name': team_name,
            'season_stats': {},
            'last_updated': datetime.now().isoformat()
        }
        
        # Extract various statistical categories
        for category in data.get('statistics', []):
            category_name = category.get('name', 'unknown')
            category_stats = {}
            
            for stat in category.get('stats', []):
                stat_name = stat.get('name', '')
                stat_value = stat.get('value', 0)
                category_stats[stat_name] = stat_value
            
            stats_data['season_stats'][category_name] = category_stats
        
        return stats_data
    
    def _extract_coaching_info(self, data: Dict, team_name: str) -> Dict[str, Any]:
        """Extract coaching information from roster data."""
        coaching_info = {}
        
        # Check if there's direct coaching data in the response
        coaches = data.get('coach', [])
        if coaches and isinstance(coaches, list) and len(coaches) > 0:
            head_coach = coaches[0]  # First coach is typically head coach
            first_name = head_coach.get('firstName', '')
            last_name = head_coach.get('lastName', '')
            coach_name = f"{first_name} {last_name}".strip() or 'Unknown'
            experience = head_coach.get('experience', 5)
            
            coaching_info.update({
                'head_coach_name': coach_name,
                'head_coach_experience': experience,
                'tenure_years': experience,  # Use ESPN experience directly
            })
            return coaching_info
        
        # Look for coaching staff in roster athletes
        athletes = data.get('athletes', [])
        
        for athlete_group in athletes:
            # Check if this is a coaching position group
            group_position = athlete_group.get('position', '').lower()
            if 'coach' in group_position:
                items = athlete_group.get('items', [])
                for athlete in items:
                    position_data = athlete.get('position', {})
                    if isinstance(position_data, dict):
                        position_name = position_data.get('name', '').lower()
                    else:
                        position_name = str(position_data).lower()
                    
                    if 'head coach' in position_name or 'coach' in position_name:
                        coaching_info.update({
                            'head_coach_name': athlete.get('displayName', 'Unknown'),
                            'head_coach_experience': self._estimate_coaching_experience(athlete),
                        })
                        return coaching_info
        
        return coaching_info
    
    def _extract_coaching_from_team_data(self, data: Dict, team_name: str) -> Dict[str, Any]:
        """Extract coaching info from general team data."""
        # ESPN sometimes includes coaching info in team details
        return {}  # Placeholder - ESPN API structure varies
    
    def _extract_venue_info(self, venue_data: Dict) -> Dict[str, Any]:
        """Extract venue information."""
        return {
            'name': venue_data.get('fullName', ''),
            'capacity': venue_data.get('capacity', 0),
            'grass': venue_data.get('grass', False),
            'city': venue_data.get('address', {}).get('city', ''),
            'state': venue_data.get('address', {}).get('state', '')
        }
    
    def _extract_conference_info(self, groups_data: Dict) -> Dict[str, Any]:
        """Extract conference information."""
        if isinstance(groups_data, dict):
            return {
                'name': groups_data.get('shortDisplayName', ''),
                'full_name': groups_data.get('name', '')
            }
        return {'name': '', 'full_name': ''}
    
    def _extract_record_info(self, record_data: Dict) -> Dict[str, Any]:
        """Extract win-loss record information."""
        return {
            'wins': record_data.get('wins', 0),
            'losses': record_data.get('losses', 0),
            'ties': record_data.get('ties', 0),
            'win_percentage': record_data.get('winPercentage', 0.0)
        }
    
    def _extract_game_info(self, event: Dict, team_name: str) -> Optional[Dict[str, Any]]:
        """Extract information from a single game event."""
        competitions = event.get('competitions', [])
        if not competitions:
            return None
        
        competition = competitions[0]
        competitors = competition.get('competitors', [])
        
        # Find home/away teams
        home_team = None
        away_team = None
        team_score = None
        opponent_score = None
        is_home_game = False
        
        for competitor in competitors:
            comp_team_name = competitor.get('team', {}).get('displayName', '')
            normalized_comp_name = normalizer.normalize(comp_team_name)
            
            if normalized_comp_name == team_name:
                score_data = competitor.get('score', {})
                team_score = score_data.get('value', 0) if isinstance(score_data, dict) else score_data
                is_home_game = competitor.get('homeAway') == 'home'
                if is_home_game:
                    home_team = team_name
                else:
                    away_team = team_name
            else:
                score_data = competitor.get('score', {})
                opponent_score = score_data.get('value', 0) if isinstance(score_data, dict) else score_data
                if competitor.get('homeAway') == 'home':
                    home_team = normalized_comp_name
                else:
                    away_team = normalized_comp_name
        
        # Determine game result
        result = None
        if team_score is not None and opponent_score is not None:
            if team_score > opponent_score:
                result = 'W'
            elif team_score < opponent_score:
                result = 'L'
            else:
                result = 'T'
        
        return {
            'date': event.get('date'),
            'home_team': home_team,
            'away_team': away_team,
            'team_score': team_score,
            'opponent_score': opponent_score,
            'is_home_game': is_home_game,
            'result': result,
            'venue': competition.get('venue', {}).get('fullName', ''),
            'neutral_site': competition.get('neutralSite', False),
            'conference_game': competition.get('conferenceCompetition', False),
            'completed': event.get('status', {}).get('type', {}).get('completed', False)
        }
    
    def _estimate_coaching_experience(self, coach_data: Dict) -> int:
        """Estimate coaching experience from available data."""
        # This is a placeholder - ESPN doesn't always provide experience data
        # In practice, this would need external data sources or manual curation
        return 5  # Default estimate
    
    def _get_neutral_team_data(self, team_name: str, data_type: str) -> Dict[str, Any]:
        """Return neutral/fallback team data."""
        return {
            'team_name': team_name,
            'data_type': data_type,
            'status': 'neutral_fallback',
            'last_updated': datetime.now().isoformat()
        }
    
    def _get_neutral_coaching_data(self, team_name: str) -> Dict[str, Any]:
        """Return neutral coaching data when real data unavailable."""
        return {
            'team_name': team_name,
            'head_coach_name': 'Unknown',
            'head_coach_experience': 5,  # Neutral estimate
            'tenure_years': 3,  # Neutral estimate
            'overall_record': {'wins': 30, 'losses': 25},  # Neutral record
            'status': 'neutral_fallback',
            'last_updated': datetime.now().isoformat()
        }
    
    def _get_neutral_stats_data(self, team_name: str) -> Dict[str, Any]:
        """Return neutral statistics when real data unavailable."""
        return {
            'team_name': team_name,
            'season_stats': {
                'offense': {
                    'points_per_game': 25.0,
                    'yards_per_game': 350.0
                },
                'defense': {
                    'points_allowed_per_game': 25.0,
                    'yards_allowed_per_game': 350.0
                }
            },
            'status': 'neutral_fallback',
            'last_updated': datetime.now().isoformat()
        }
    
    def get_week_boundaries(self, week: int) -> Optional[Dict[str, datetime]]:
        """
        Get date boundaries for a specific CFB week from ESPN schedule data.
        
        Args:
            week: Week number (1-17)
            
        Returns:
            Dictionary with 'start_date' and 'end_date' datetime objects, or None if not found
        """
        try:
            # Rate limiting
            self.rate_limiter.wait_if_needed()
            
            # Fetch current season schedule/scoreboard to determine week boundaries
            current_year = datetime.now().year
            url = f"{self.base_url}/scoreboard"
            
            # Try to get schedule data for the current season
            params = {
                'seasontype': 2,  # Regular season
                'week': week,
                'year': current_year
            }
            
            response = self.session.get(url, params=params, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                events = data.get('events', [])
                
                if events:
                    # Extract game dates from this week's events
                    game_dates = []
                    for event in events:
                        event_date = event.get('date')
                        if event_date:
                            try:
                                # Parse ESPN date format
                                game_date = datetime.fromisoformat(event_date.replace('Z', '+00:00'))
                                game_dates.append(game_date)
                            except Exception as e:
                                self.logger.debug(f"Error parsing date {event_date}: {e}")
                                continue
                    
                    if game_dates:
                        # Calculate week boundaries
                        earliest_game = min(game_dates)
                        latest_game = max(game_dates)
                        
                        # Week typically starts on Tuesday and ends on Monday
                        # But we'll use the actual game dates with some buffer
                        start_date = earliest_game - timedelta(days=2)  # Start 2 days before first game
                        end_date = latest_game + timedelta(hours=6)     # End 6 hours after last game
                        
                        # Handle Week 0 + Week 1 grouping
                        if week == 1:
                            # For Week 1, also include Week 0 games
                            week0_data = self.get_week_boundaries(0)
                            if week0_data:
                                start_date = min(start_date, week0_data['start_date'])
                        
                        self.logger.debug(f"Found ESPN week {week} boundaries: {start_date} to {end_date}")
                        return {
                            'start_date': start_date,
                            'end_date': end_date
                        }
            
            # Fallback: Try Week 0 if Week 1 request failed
            if week == 1:
                params['week'] = 0
                response = self.session.get(url, params=params, timeout=30)
                
                if response.status_code == 200:
                    data = response.json()
                    events = data.get('events', [])
                    
                    if events:
                        game_dates = []
                        for event in events:
                            event_date = event.get('date')
                            if event_date:
                                try:
                                    game_date = datetime.fromisoformat(event_date.replace('Z', '+00:00'))
                                    game_dates.append(game_date)
                                except Exception:
                                    continue
                        
                        if game_dates:
                            earliest_game = min(game_dates)
                            latest_game = max(game_dates)
                            
                            # Extend to cover both Week 0 and Week 1
                            start_date = earliest_game - timedelta(days=2)
                            
                            # Try to get Week 1 end date
                            self.rate_limiter.wait_if_needed()
                            params['week'] = 1
                            week1_response = self.session.get(url, params=params, timeout=30)
                            
                            if week1_response.status_code == 200:
                                week1_data = week1_response.json()
                                week1_events = week1_data.get('events', [])
                                
                                week1_dates = []
                                for event in week1_events:
                                    event_date = event.get('date')
                                    if event_date:
                                        try:
                                            game_date = datetime.fromisoformat(event_date.replace('Z', '+00:00'))
                                            week1_dates.append(game_date)
                                        except Exception:
                                            continue
                                
                                if week1_dates:
                                    end_date = max(week1_dates) + timedelta(hours=6)
                                else:
                                    end_date = latest_game + timedelta(hours=6)
                            else:
                                end_date = latest_game + timedelta(hours=6)
                            
                            self.logger.debug(f"Found ESPN Week 0+1 boundaries: {start_date} to {end_date}")
                            return {
                                'start_date': start_date,
                                'end_date': end_date
                            }
            
            self.logger.warning(f"Could not find ESPN schedule data for week {week}")
            return None
            
        except Exception as e:
            self.logger.error(f"Error fetching ESPN week boundaries for week {week}: {e}")
            return None

    def test_connection(self) -> bool:
        """
        Test ESPN API connection.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            self.rate_limiter.wait_if_needed()
            
            url = f"{self.base_url}/teams"
            response = self.session.get(url, timeout=10)
            
            if response.status_code == 200:
                self.logger.info("ESPN API connection test successful")
                return True
            else:
                self.logger.error(f"ESPN API connection test failed: {response.status_code}")
                return False
                
        except Exception as e:
            self.logger.error(f"ESPN API connection test error: {e}")
            return False
    
    def __del__(self):
        """Cleanup session on destruction."""
        if hasattr(self, 'session'):
            self.session.close()