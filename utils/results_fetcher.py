"""
Game results fetching utilities for College Football Market Edge Platform.

Handles fetching completed game results from various data sources.
"""

import requests
import time
from typing import Dict, List, Optional, Tuple
from datetime import datetime

from data.espn_client import ESPNStatsClient
from data.cfbd_client import CFBDataClient
from utils.normalizer import normalizer as team_name_normalizer


class ResultsFetcher:
    """Fetches completed game results from multiple data sources."""
    
    def __init__(self):
        self.espn_client = ESPNStatsClient()
        self.cfbd_client = CFBDataClient()
    
    def fetch_game_results(self, week: int, season: int = 2025) -> List[Dict]:
        """
        Fetch all completed games for a given week.
        
        Args:
            week: Week number (1-15, excluding 0)
            season: Season year
            
        Returns:
            List of game result dictionaries
        """
        if week == 0:
            return []  # Skip week 0 as requested
        
        print(f"Fetching results for Week {week}, {season}...")
        
        results = []
        
        # Try ESPN first (primary source)
        try:
            espn_results = self._fetch_espn_results(week, season)
            results.extend(espn_results)
            print(f"✅ ESPN: Found {len(espn_results)} completed games")
        except Exception as e:
            print(f"⚠️  ESPN fetch failed: {e}")
        
        # Try CFBD as backup/supplement
        try:
            cfbd_results = self._fetch_cfbd_results(week, season)
            # Merge results, avoiding duplicates
            new_results = self._merge_results(results, cfbd_results)
            results.extend(new_results)
            print(f"✅ CFBD: Added {len(new_results)} additional games")
        except Exception as e:
            print(f"⚠️  CFBD fetch failed: {e}")
        
        print(f"📊 Total completed games found: {len(results)}")
        return results
    
    def _fetch_espn_results(self, week: int, season: int) -> List[Dict]:
        """
        Fetch results from ESPN API.
        
        Args:
            week: Week number
            season: Season year
            
        Returns:
            List of game result dictionaries
        """
        results = []
        
        # ESPN's API structure for getting completed games
        # This is a simplified version - ESPN's actual API is more complex
        
        # Get games for the week
        url = f"https://site.api.espn.com/apis/site/v2/sports/football/college-football/scoreboard"
        params = {
            'groups': '80',  # FBS games
            'week': week,
            'year': season,
            'seasontype': 2  # Regular season
        }
        
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            events = data.get('events', [])
            
            for event in events:
                # Only process completed games
                status = event.get('status', {})
                if status.get('type', {}).get('name') != 'STATUS_FINAL':
                    continue
                
                competitions = event.get('competitions', [])
                if not competitions:
                    continue
                
                competition = competitions[0]
                competitors = competition.get('competitors', [])
                
                if len(competitors) != 2:
                    continue
                
                # Extract team info and scores
                home_team = None
                away_team = None
                home_score = 0
                away_score = 0
                
                for competitor in competitors:
                    team_info = competitor.get('team', {})
                    team_name = team_info.get('displayName', '')
                    score = int(competitor.get('score', 0))
                    is_home = competitor.get('homeAway') == 'home'
                    
                    if is_home:
                        home_team = team_name
                        home_score = score
                    else:
                        away_team = team_name
                        away_score = score
                
                if home_team and away_team:
                    game_date = event.get('date', '')
                    game_id = event.get('id', '')
                    
                    result = {
                        'game_id': f"espn_{game_id}",
                        'home_team': home_team,
                        'away_team': away_team,
                        'home_score': home_score,
                        'away_score': away_score,
                        'actual_margin': home_score - away_score,
                        'game_date': game_date,
                        'week': week,
                        'season': season,
                        'status': 'final',
                        'source': 'ESPN'
                    }
                    
                    results.append(result)
            
            time.sleep(0.1)  # Rate limiting
            
        except Exception as e:
            raise Exception(f"ESPN API error: {e}")
        
        return results
    
    def _fetch_cfbd_results(self, week: int, season: int) -> List[Dict]:
        """
        Fetch results from CFBD API.
        
        Args:
            week: Week number
            season: Season year
            
        Returns:
            List of game result dictionaries
        """
        results = []
        
        try:
            # Use existing CFBD client's get_games method
            games_data = self.cfbd_client.get_games(
                year=season,
                week=week,
                season_type='regular'
            )
            
            for game in games_data:
                # Only process completed games
                if not game.get('completed', False):
                    continue
                
                home_team = game.get('home_team', '')
                away_team = game.get('away_team', '')
                home_points = game.get('home_points', 0)
                away_points = game.get('away_points', 0)
                
                if home_team and away_team and (home_points > 0 or away_points > 0):
                    result = {
                        'game_id': f"cfbd_{game.get('id', '')}",
                        'home_team': home_team,
                        'away_team': away_team,
                        'home_score': int(home_points) if home_points else 0,
                        'away_score': int(away_points) if away_points else 0,
                        'actual_margin': int(home_points or 0) - int(away_points or 0),
                        'game_date': game.get('start_date', ''),
                        'week': week,
                        'season': season,
                        'status': 'final',
                        'source': 'CFBD'
                    }
                    
                    results.append(result)
        
        except Exception as e:
            raise Exception(f"CFBD API error: {e}")
        
        return results
    
    def _merge_results(self, existing_results: List[Dict], new_results: List[Dict]) -> List[Dict]:
        """
        Merge new results with existing, avoiding duplicates.
        
        Args:
            existing_results: Already fetched results
            new_results: New results to merge
            
        Returns:
            List of non-duplicate results to add
        """
        # Create a set of existing game matchups for quick lookup
        existing_matchups = set()
        
        for result in existing_results:
            home = self._normalize_team_for_matching(result['home_team'])
            away = self._normalize_team_for_matching(result['away_team'])
            matchup = (home, away, result['week'], result['season'])
            existing_matchups.add(matchup)
        
        # Filter out duplicates from new results
        unique_results = []
        
        for result in new_results:
            home = self._normalize_team_for_matching(result['home_team'])
            away = self._normalize_team_for_matching(result['away_team'])
            matchup = (home, away, result['week'], result['season'])
            
            if matchup not in existing_matchups:
                unique_results.append(result)
                existing_matchups.add(matchup)
        
        return unique_results
    
    def _normalize_team_for_matching(self, team_name: str) -> str:
        """
        Normalize team name for duplicate detection.
        
        Args:
            team_name: Raw team name
            
        Returns:
            Normalized team name
        """
        # Use the existing normalizer but make it more aggressive
        normalized = team_name_normalizer.normalize(team_name)
        return normalized.upper().strip()
    
    def find_game_result(self, home_team: str, away_team: str, week: int, season: int = 2025) -> Optional[Dict]:
        """
        Find the result for a specific game.
        
        Args:
            home_team: Home team name
            away_team: Away team name
            week: Week number
            season: Season year
            
        Returns:
            Game result dictionary or None if not found
        """
        if week == 0:
            return None  # Skip week 0
        
        # First try to find in a cached weekly results file
        # This would be more efficient than fetching all results
        
        # For now, fetch all results and search
        all_results = self.fetch_game_results(week, season)
        
        # Normalize team names for matching
        target_home = self._normalize_team_for_matching(home_team)
        target_away = self._normalize_team_for_matching(away_team)
        
        for result in all_results:
            result_home = self._normalize_team_for_matching(result['home_team'])
            result_away = self._normalize_team_for_matching(result['away_team'])
            
            if result_home == target_home and result_away == target_away:
                return result
        
        return None
    
    def get_team_record(self, team: str, through_week: int, season: int = 2025) -> Dict:
        """
        Get a team's win-loss record through a specific week.
        
        Args:
            team: Team name
            through_week: Week number to calculate through
            season: Season year
            
        Returns:
            Dictionary with wins, losses, and record
        """
        wins = 0
        losses = 0
        
        # Fetch results for all weeks up to through_week
        for week in range(1, through_week + 1):  # Start from 1, skip week 0
            try:
                week_results = self.fetch_game_results(week, season)
                
                normalized_team = self._normalize_team_for_matching(team)
                
                for result in week_results:
                    home_team = self._normalize_team_for_matching(result['home_team'])
                    away_team = self._normalize_team_for_matching(result['away_team'])
                    
                    if normalized_team == home_team:
                        # Team played at home
                        if result['home_score'] > result['away_score']:
                            wins += 1
                        else:
                            losses += 1
                    elif normalized_team == away_team:
                        # Team played away
                        if result['away_score'] > result['home_score']:
                            wins += 1
                        else:
                            losses += 1
            except Exception:
                continue  # Skip weeks with errors
        
        return {
            'wins': wins,
            'losses': losses,
            'record': f"{wins}-{losses}",
            'win_percentage': wins / max(wins + losses, 1)
        }


# Convenience instance for easy importing
results_fetcher = ResultsFetcher()