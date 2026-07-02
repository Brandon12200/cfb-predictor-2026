"""
Rate limiting infrastructure for College Football Market Edge Platform.
Prevents API quota violations and ensures compliance with rate limits.
"""

import time
import threading
from typing import List, Optional
from collections import deque
import logging


class RateLimiter:
    """
    Thread-safe rate limiter for API calls.
    
    Implements a sliding window approach to track calls within time periods.
    Supports both per-minute and per-day rate limiting.
    """
    
    def __init__(self, calls_per_minute: int, calls_per_day: Optional[int] = None):
        """
        Initialize rate limiter with specified limits.
        
        Args:
            calls_per_minute: Maximum calls allowed per minute
            calls_per_day: Maximum calls allowed per day (optional)
        """
        self.calls_per_minute = calls_per_minute
        self.calls_per_day = calls_per_day
        
        # Track call timestamps for sliding window
        self.minute_calls: deque = deque()
        self.day_calls: deque = deque()
        
        # Thread safety
        self._lock = threading.Lock()
        
        # Logging
        self.logger = logging.getLogger(__name__)
        
        self.logger.debug(f"Rate limiter initialized: {calls_per_minute}/min" + 
                         (f", {calls_per_day}/day" if calls_per_day else ""))
    
    def wait_if_needed(self) -> float:
        """
        Wait if necessary to comply with rate limits.
        
        Returns:
            float: Time waited in seconds (0 if no wait was needed)
        """
        with self._lock:
            current_time = time.time()
            wait_time = self._calculate_wait_time(current_time)
            
            if wait_time > 0:
                self.logger.info(f"Rate limit reached, waiting {wait_time:.2f} seconds")
                time.sleep(wait_time)
                current_time = time.time()
            
            # Record the call
            self._record_call(current_time)
            
            return wait_time
    
    def can_make_call(self) -> bool:
        """
        Check if a call can be made without waiting.
        
        Returns:
            bool: True if call can be made immediately
        """
        with self._lock:
            current_time = time.time()
            return self._calculate_wait_time(current_time) == 0
    
    def get_remaining_calls(self) -> dict:
        """
        Get number of remaining calls for current time windows.
        
        Returns:
            dict: Remaining calls per minute and per day
        """
        with self._lock:
            current_time = time.time()
            self._cleanup_old_calls(current_time)
            
            minute_remaining = max(0, self.calls_per_minute - len(self.minute_calls))
            day_remaining = None
            
            if self.calls_per_day:
                day_remaining = max(0, self.calls_per_day - len(self.day_calls))
            
            return {
                'minute': minute_remaining,
                'day': day_remaining
            }
    
    def reset(self) -> None:
        """Reset all call tracking (useful for testing)."""
        with self._lock:
            self.minute_calls.clear()
            self.day_calls.clear()
            self.logger.debug("Rate limiter reset")
    
    def _calculate_wait_time(self, current_time: float) -> float:
        """
        Calculate time to wait before making next call.
        
        Args:
            current_time: Current timestamp
            
        Returns:
            float: Seconds to wait (0 if no wait needed)
        """
        self._cleanup_old_calls(current_time)
        
        wait_times = []
        
        # Check minute limit
        if len(self.minute_calls) >= self.calls_per_minute:
            oldest_call = self.minute_calls[0]
            minute_wait = oldest_call + 60 - current_time
            if minute_wait > 0:
                wait_times.append(minute_wait)
        
        # Check day limit
        if self.calls_per_day and len(self.day_calls) >= self.calls_per_day:
            oldest_call = self.day_calls[0]
            day_wait = oldest_call + 86400 - current_time  # 24 hours
            if day_wait > 0:
                wait_times.append(day_wait)
        
        return max(wait_times) if wait_times else 0
    
    def _cleanup_old_calls(self, current_time: float) -> None:
        """
        Remove call records outside the tracking windows.
        
        Args:
            current_time: Current timestamp
        """
        # Clean up minute calls (older than 60 seconds)
        while self.minute_calls and self.minute_calls[0] <= current_time - 60:
            self.minute_calls.popleft()
        
        # Clean up day calls (older than 24 hours)
        while self.day_calls and self.day_calls[0] <= current_time - 86400:
            self.day_calls.popleft()
    
    def _record_call(self, timestamp: float) -> None:
        """
        Record a new API call.
        
        Args:
            timestamp: Timestamp of the call
        """
        self.minute_calls.append(timestamp)
        
        if self.calls_per_day:
            self.day_calls.append(timestamp)
        
        self.logger.debug(f"Call recorded: {len(self.minute_calls)}/{self.calls_per_minute} per minute" +
                         (f", {len(self.day_calls)}/{self.calls_per_day} per day" if self.calls_per_day else ""))
    
    def __str__(self) -> str:
        """String representation of rate limiter status."""
        remaining = self.get_remaining_calls()
        return (f"RateLimiter({self.calls_per_minute}/min" +
                (f", {self.calls_per_day}/day" if self.calls_per_day else "") +
                f", remaining: {remaining['minute']}/min" +
                (f", {remaining['day']}/day" if remaining['day'] is not None else "") + ")")


class APIRateLimiterManager:
    """
    Manages rate limiters for different APIs.
    
    Provides centralized rate limiting for the application.
    """
    
    def __init__(self):
        """Initialize rate limiter manager."""
        self.limiters = {}
        self.logger = logging.getLogger(__name__)
    
    def create_limiter(self, api_name: str, calls_per_minute: int, 
                      calls_per_day: Optional[int] = None) -> RateLimiter:
        """
        Create and register a rate limiter for an API.
        
        Args:
            api_name: Name of the API
            calls_per_minute: Calls per minute limit
            calls_per_day: Calls per day limit (optional)
            
        Returns:
            RateLimiter: Created rate limiter
        """
        limiter = RateLimiter(calls_per_minute, calls_per_day)
        self.limiters[api_name] = limiter
        
        self.logger.info(f"Created rate limiter for {api_name}: {limiter}")
        
        return limiter
    
    def get_limiter(self, api_name: str) -> Optional[RateLimiter]:
        """
        Get rate limiter for specified API.
        
        Args:
            api_name: Name of the API
            
        Returns:
            RateLimiter: Rate limiter or None if not found
        """
        return self.limiters.get(api_name)
    
    def wait_for_api(self, api_name: str) -> float:
        """
        Wait if necessary for the specified API.
        
        Args:
            api_name: Name of the API
            
        Returns:
            float: Time waited in seconds
            
        Raises:
            ValueError: If API limiter not found
        """
        limiter = self.get_limiter(api_name)
        if not limiter:
            raise ValueError(f"No rate limiter found for API: {api_name}")
        
        return limiter.wait_if_needed()
    
    def get_status(self) -> dict:
        """
        Get status of all rate limiters.
        
        Returns:
            dict: Status information for all APIs
        """
        status = {}
        for api_name, limiter in self.limiters.items():
            remaining = limiter.get_remaining_calls()
            status[api_name] = {
                'limiter': str(limiter),
                'remaining_calls': remaining,
                'can_make_call': limiter.can_make_call()
            }
        
        return status
    
    def reset_all(self) -> None:
        """Reset all rate limiters."""
        for limiter in self.limiters.values():
            limiter.reset()
        
        self.logger.info("All rate limiters reset")


# Global rate limiter manager instance
rate_limiter_manager = APIRateLimiterManager()


def setup_api_rate_limiters(odds_limit: int = 83, espn_limit: int = 60) -> None:
    """
    Setup rate limiters for all APIs used by the application.
    
    Args:
        odds_limit: Odds API daily limit (default: 83 calls/day)
        espn_limit: ESPN API minute limit (default: 60 calls/minute)
    """
    # Use reasonable per-minute limit for Odds API
    # Allow burst usage during active periods while respecting daily limit
    odds_per_minute = min(15, odds_limit // 4)  # Allow 15/min but respect daily budget
    
    # Create rate limiters
    rate_limiter_manager.create_limiter('odds_api', odds_per_minute, odds_limit)
    rate_limiter_manager.create_limiter('espn_api', espn_limit)
    
    logging.info(f"Rate limiters configured: Odds API {odds_per_minute}/min ({odds_limit}/day), ESPN {espn_limit}/min")