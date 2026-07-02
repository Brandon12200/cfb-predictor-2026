"""
The Odds API client for College Football Market Edge Platform.
Fetches betting lines and consensus spreads from multiple bookmakers.
"""

import requests
import logging
import time
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
import json

from config import config
from utils.rate_limiter import rate_limiter_manager, setup_api_rate_limiters
from data.cache_manager import cache_manager
from utils.normalizer import normalizer


class OddsAPIClient:
    """
    Client for The Odds API to fetch college football betting data.
    
    Features:
    - Rate limiting compliance (83 calls/day)
    - Automatic caching to reduce API usage
    - Consensus spread calculation from multiple bookmakers
    - Team name normalization integration
    - Comprehensive error handling
    """
    
    def __init__(self, api_key: str):
        """
        Initialize Odds API client.
        
        Args:
            api_key: The Odds API key
        """
        self.api_key = api_key
        self.base_url = "https://api.the-odds-api.com/v4"
        self.sport = "americanfootball_ncaaf"  # College Football
        
        # Setup rate limiter
        if not rate_limiter_manager.get_limiter('odds_api'):
            setup_api_rate_limiters(
                odds_limit=config.rate_limit_odds,
                espn_limit=config.rate_limit_espn
            )
        
        self.rate_limiter = rate_limiter_manager.get_limiter('odds_api')
        
        # Cache manager
        self.cache = cache_manager
        
        # Session for connection pooling
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'CFB-Contrarian-Predictor/2.0'
        })
        
        # Logging
        self.logger = logging.getLogger(__name__)
        
        # Markets and bookmakers we're interested in
        self.markets = ['spreads', 'totals']  # Point spreads and over/under
        self.regions = ['us']  # US bookmakers
        
        # Bookmaker preferences (in order of reliability)
        self.preferred_bookmakers = [
            'fanduel', 'draftkings', 'pointsbet_us', 'betmgm', 'caesars',
            'barstool', 'unibet_us', 'betrivers', 'sugarhouse'
        ]
        
        self.logger.info(f"Odds API client initialized with key: ...{api_key[-4:] if api_key else 'None'}")
    
    def get_weekly_spreads(self, week: Optional[int] = None) -> Dict[str, Any]:
        """
        Get all college football spreads for current or specified week.
        
        Args:
            week: Week number (1-17), None for current week
            
        Returns:
            Dict containing all games with spreads and metadata
        """
        cache_key = f"weekly_spreads_week_{week}" if week else "weekly_spreads_current"
        
        # Check cache first
        cached_data = self.cache.get_odds_data('cfb', week)
        if cached_data:
            self.logger.debug(f"Using cached weekly spreads for week {week}")
            return cached_data
        
        # Rate limiting
        self.rate_limiter.wait_if_needed()
        
        try:
            # Build request parameters
            params = {
                'apiKey': self.api_key,
                'regions': ','.join(self.regions),
                'markets': ','.join(self.markets),
                'oddsFormat': 'american',
                'dateFormat': 'iso'
            }
            
            # Add commence time filter for specific week if provided
            if week:
                start_date, end_date = self._get_week_date_range(week)
                params['commenceTimeFrom'] = start_date.strftime('%Y-%m-%dT%H:%M:%SZ')
                params['commenceTimeTo'] = end_date.strftime('%Y-%m-%dT%H:%M:%SZ')
            
            url = f"{self.base_url}/sports/{self.sport}/odds"
            
            self.logger.info(f"Fetching odds data for week {week if week else 'current'}")
            response = self.session.get(url, params=params, timeout=30)
            
            # Check response
            if response.status_code == 401:
                raise ValueError("Invalid API key")
            elif response.status_code == 429:
                raise ValueError("Rate limit exceeded")
            elif response.status_code != 200:
                raise ValueError(f"API request failed: {response.status_code} - {response.text}")
            
            data = response.json()
            
            # Process and normalize the data
            processed_data = self._process_odds_response(data)
            
            # Cache the results
            self.cache.cache_odds_data(processed_data, 'cfb', week, ttl=1800)  # 30 minute cache
            
            self.logger.info(f"Retrieved {len(processed_data.get('games', []))} games for week {week if week else 'current'}")
            
            return processed_data
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Network error fetching odds: {e}")
            raise ValueError(f"Network error: {e}")
        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON response: {e}")
            raise ValueError(f"Invalid API response: {e}")
        except Exception as e:
            self.logger.error(f"Unexpected error fetching odds: {e}")
            raise
    
    def get_consensus_spread(self, home_team: str, away_team: str, week: Optional[int] = None) -> Optional[float]:
        """
        Get consensus spread for a specific matchup.
        
        Args:
            home_team: Normalized home team name
            away_team: Normalized away team name
            week: Week number (optional)
            
        Returns:
            Float spread (positive = home team favored) or None if not found
        """
        # Get weekly data
        weekly_data = self.get_weekly_spreads(week)
        
        # Find the specific game
        for game in weekly_data.get('games', []):
            if (game['home_team'] == home_team and game['away_team'] == away_team):
                spread = game.get('consensus_spread')
                self.logger.debug(f"Found consensus spread for {away_team} @ {home_team}: {spread}")
                return spread
        
        self.logger.warning(f"No spread found for {away_team} @ {home_team}")
        return None
    
    def get_game_odds(self, date: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get odds for games on a specific date.
        
        Args:
            date: Date string in YYYY-MM-DD format (default: today)
            
        Returns:
            List of games with odds data
        """
        if date is None:
            date = datetime.now().strftime('%Y-%m-%d')
        
        # Use weekly spreads and filter by date
        weekly_data = self.get_weekly_spreads()
        games = []
        
        for game in weekly_data.get('games', []):
            game_date = game.get('commence_time', '')[:10]  # Extract date part
            if game_date == date:
                games.append(game)
        
        return games
    
    def _process_odds_response(self, raw_data: List[Dict]) -> Dict[str, Any]:
        """
        Process raw odds API response into normalized format.
        
        Args:
            raw_data: Raw response from Odds API
            
        Returns:
            Processed data with consensus calculations
        """
        processed_games = []
        
        for game_data in raw_data:
            try:
                processed_game = self._process_single_game(game_data)
                if processed_game:
                    processed_games.append(processed_game)
            except Exception as e:
                self.logger.warning(f"Error processing game data: {e}")
                continue
        
        return {
            'games': processed_games,
            'timestamp': datetime.now().isoformat(),
            'source': 'the_odds_api',
            'total_games': len(processed_games)
        }
    
    def _process_single_game(self, game_data: Dict) -> Optional[Dict[str, Any]]:
        """
        Process a single game from the odds response.
        
        Args:
            game_data: Single game data from API
            
        Returns:
            Processed game data or None if processing fails
        """
        # Extract basic game info
        home_team_raw = game_data.get('home_team', '')
        away_team_raw = game_data.get('away_team', '')
        
        # Check for FCS teams first (before normalization)
        if normalizer.is_fbs_vs_fcs_matchup(home_team_raw, away_team_raw):
            self.logger.debug(f"Filtering out FCS matchup: {away_team_raw} @ {home_team_raw}")
            return None
        
        # Normalize team names
        home_team = normalizer.normalize(home_team_raw)
        away_team = normalizer.normalize(away_team_raw)
        
        if not home_team or not away_team:
            # Second check - might be an FCS team we couldn't normalize
            if normalizer.is_fcs_team(home_team_raw) or normalizer.is_fcs_team(away_team_raw):
                self.logger.debug(f"Filtering out potential FCS team: {away_team_raw} @ {home_team_raw}")
                return None
            self.logger.warning(f"Could not normalize teams: {home_team_raw} vs {away_team_raw}")
            return None
        
        # Extract bookmaker data
        bookmakers = game_data.get('bookmakers', [])
        spreads = self._extract_spreads(bookmakers, home_team, away_team)
        totals = self._extract_totals(bookmakers)
        
        # Calculate consensus
        consensus_spread = self._calculate_consensus_spread(spreads)
        consensus_total = self._calculate_consensus_total(totals)
        
        return {
            'id': game_data.get('id'),
            'commence_time': game_data.get('commence_time'),
            'home_team': home_team,
            'away_team': away_team,
            'home_team_raw': home_team_raw,
            'away_team_raw': away_team_raw,
            'consensus_spread': consensus_spread,
            'consensus_total': consensus_total,
            'spreads': spreads,
            'totals': totals,
            'bookmaker_count': len(bookmakers),
            'spread_count': len(spreads),
            'last_updated': datetime.now().isoformat()
        }
    
    def _extract_spreads(self, bookmakers: List[Dict], home_team: str, away_team: str) -> List[Dict[str, Any]]:
        """Extract spread data from bookmakers."""
        spreads = []
        
        for bookmaker in bookmakers:
            bookmaker_key = bookmaker.get('key', '')
            
            for market in bookmaker.get('markets', []):
                if market.get('key') == 'spreads':
                    for outcome in market.get('outcomes', []):
                        team_name = normalizer.normalize(outcome.get('name', ''))
                        
                        if team_name == home_team:
                            # Home team spread (negative = favored)
                            spread = {
                                'bookmaker': bookmaker_key,
                                'team': home_team,
                                'point': float(outcome.get('point', 0)),
                                'price': outcome.get('price'),
                                'last_update': market.get('last_update')
                            }
                            spreads.append(spread)
                            break
        
        return spreads
    
    def _extract_totals(self, bookmakers: List[Dict]) -> List[Dict[str, Any]]:
        """Extract totals (over/under) data from bookmakers."""
        totals = []
        
        for bookmaker in bookmakers:
            bookmaker_key = bookmaker.get('key', '')
            
            for market in bookmaker.get('markets', []):
                if market.get('key') == 'totals':
                    over_under = {}
                    
                    for outcome in market.get('outcomes', []):
                        name = outcome.get('name', '').lower()
                        if name in ['over', 'under']:
                            over_under[name] = {
                                'point': float(outcome.get('point', 0)),
                                'price': outcome.get('price')
                            }
                    
                    if 'over' in over_under and 'under' in over_under:
                        total = {
                            'bookmaker': bookmaker_key,
                            'total': over_under['over']['point'],  # Total line
                            'over_price': over_under['over']['price'],
                            'under_price': over_under['under']['price'],
                            'last_update': market.get('last_update')
                        }
                        totals.append(total)
        
        return totals
    
    def _calculate_consensus_spread(self, spreads: List[Dict]) -> Optional[float]:
        """
        Calculate consensus spread from multiple bookmakers.
        
        Args:
            spreads: List of spread data from bookmakers
            
        Returns:
            Consensus spread or None if insufficient data
        """
        if not spreads:
            return None
        
        # Weight bookmakers by preference
        weighted_spreads = []
        
        for spread in spreads:
            bookmaker = spread['bookmaker']
            point = spread['point']
            
            # Get weight based on preference order
            try:
                weight = 1.0 / (self.preferred_bookmakers.index(bookmaker) + 1)
            except ValueError:
                weight = 0.1  # Low weight for unknown bookmakers
            
            weighted_spreads.append((point, weight))
        
        if not weighted_spreads:
            return None
        
        # Calculate weighted average
        total_weighted = sum(point * weight for point, weight in weighted_spreads)
        total_weight = sum(weight for _, weight in weighted_spreads)
        
        consensus = total_weighted / total_weight
        
        # Round to nearest 0.5 (common spread increment)
        consensus = round(consensus * 2) / 2
        
        return consensus
    
    def _calculate_consensus_total(self, totals: List[Dict]) -> Optional[float]:
        """Calculate consensus total from multiple bookmakers."""
        if not totals:
            return None
        
        total_points = [total['total'] for total in totals]
        
        if not total_points:
            return None
        
        # Simple average for totals
        consensus = sum(total_points) / len(total_points)
        
        # Round to nearest 0.5
        consensus = round(consensus * 2) / 2
        
        return consensus
    
    def _get_week_date_range(self, week: int) -> Tuple[datetime, datetime]:
        """
        Get date range for a specific college football week by querying actual schedule data.
        
        Args:
            week: Week number (1-17)
            
        Returns:
            Tuple of (start_date, end_date)
        """
        # Try to get week boundaries from ESPN schedule API
        try:
            from data.espn_client import ESPNStatsClient
            espn_client = ESPNStatsClient()
            
            # Get week boundaries from ESPN schedule data
            week_boundaries = espn_client.get_week_boundaries(week)
            if week_boundaries:
                return week_boundaries['start_date'], week_boundaries['end_date']
                
        except Exception as e:
            self.logger.warning(f"Could not get week boundaries from ESPN: {e}")
        
        # Fallback: Use current games to infer week boundaries
        try:
            # Get all current games without date filter
            all_games = self._fetch_all_current_games()
            if all_games:
                # Group games by week and find the date range for requested week
                week_games = self._group_games_by_week(all_games)
                if week in week_games and week_games[week]:
                    game_dates = [game['commence_time'] for game in week_games[week]]
                    start_date = min(game_dates)
                    end_date = max(game_dates) + timedelta(hours=6)  # Add buffer for late games
                    return start_date, end_date
        except Exception as e:
            self.logger.warning(f"Could not infer week boundaries from games: {e}")
        
        # Ultimate fallback: Return a wide date range
        current_year = datetime.now().year
        season_start = datetime(current_year, 8, 15)  # Conservative early start
        season_end = datetime(current_year + 1, 1, 31)  # Through bowl season
        return season_start, season_end
    
    def _fetch_all_current_games(self) -> List[Dict]:
        """Fetch all current games without date filtering to infer week boundaries."""
        try:
            params = {
                'apiKey': self.api_key,
                'regions': ','.join(self.regions),
                'markets': ','.join(self.markets),
                'oddsFormat': 'american',
                'dateFormat': 'iso'
            }
            
            url = f"{self.base_url}/sports/{self.sport}/odds"
            response = self.session.get(url, params=params, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                return data if isinstance(data, list) else []
            else:
                return []
        except Exception as e:
            self.logger.warning(f"Error fetching current games: {e}")
            return []
    
    def _group_games_by_week(self, games: List[Dict]) -> Dict[int, List[Dict]]:
        """Group games by CFB week based on commence times."""
        week_games = {}
        
        for game in games:
            try:
                commence_time_str = game.get('commence_time')
                if not commence_time_str:
                    continue
                    
                commence_time = datetime.fromisoformat(commence_time_str.replace('Z', '+00:00'))
                
                # Determine CFB week based on date
                # This is a simplified approach - games are typically grouped by Saturday
                # Week boundaries are roughly Saturday to Friday
                week_num = self._determine_cfb_week_from_date(commence_time)
                
                if week_num not in week_games:
                    week_games[week_num] = []
                
                game_copy = game.copy()
                game_copy['commence_time'] = commence_time
                week_games[week_num].append(game_copy)
                
            except Exception as e:
                self.logger.debug(f"Error processing game for week grouping: {e}")
                continue
        
        return week_games
    
    def _determine_cfb_week_from_date(self, game_date: datetime) -> int:
        """Determine CFB week number from game date."""
        # Find the first Saturday of the CFB season from current games
        # This is dynamic and based on actual data
        current_year = game_date.year
        
        # Start looking from mid-August for the first CFB games
        search_start = datetime(current_year, 8, 15)
        
        # Count weeks from the earliest games we can find
        days_since_season_start = (game_date.date() - search_start.date()).days
        week_num = max(1, (days_since_season_start // 7) + 1)
        
        # Cap at 17 weeks (including bowl season)
        return min(week_num, 17)
    
    def get_api_usage(self) -> Dict[str, Any]:
        """
        Get current API usage information.
        
        Returns:
            Dictionary with usage statistics
        """
        remaining_calls = self.rate_limiter.get_remaining_calls()
        
        return {
            'remaining_calls_minute': remaining_calls['minute'],
            'remaining_calls_day': remaining_calls['day'],
            'can_make_call': self.rate_limiter.can_make_call(),
            'rate_limiter_status': str(self.rate_limiter)
        }
    
    def test_connection(self) -> bool:
        """
        Test API connection and key validity.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            # Make a minimal API call to test connection
            self.rate_limiter.wait_if_needed()
            
            params = {
                'apiKey': self.api_key,
                'regions': 'us',
                'markets': 'spreads'
            }
            
            url = f"{self.base_url}/sports/{self.sport}/odds"
            response = self.session.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                self.logger.info("Odds API connection test successful")
                return True
            elif response.status_code == 401:
                self.logger.error("Odds API key invalid")
                return False
            else:
                self.logger.error(f"Odds API connection test failed: {response.status_code}")
                return False
                
        except Exception as e:
            self.logger.error(f"Odds API connection test error: {e}")
            return False
    
    def __del__(self):
        """Cleanup session on destruction."""
        if hasattr(self, 'session'):
            self.session.close()