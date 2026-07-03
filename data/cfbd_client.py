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
    
