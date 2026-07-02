"""
Caching system for College Football Market Edge Platform.
Implements session-level caching with TTL to reduce API calls and improve performance.
"""

import time
import json
import hashlib
import threading
from typing import Dict, Any, Optional, Union
import logging
from dataclasses import dataclass, asdict


@dataclass
class CacheEntry:
    """Represents a cached data entry with metadata."""
    data: Any
    timestamp: float
    ttl: int
    access_count: int = 0
    last_accessed: float = 0
    
    def is_expired(self, current_time: Optional[float] = None) -> bool:
        """Check if cache entry has expired."""
        if current_time is None:
            current_time = time.time()
        return (current_time - self.timestamp) > self.ttl
    
    def access(self) -> None:
        """Record access to this cache entry."""
        self.access_count += 1
        self.last_accessed = time.time()


class DataCache:
    """
    Thread-safe cache with TTL support and automatic cleanup.
    
    Features:
    - Session-level caching with configurable TTL
    - Thread-safe operations
    - Automatic cleanup of expired entries
    - Cache statistics and monitoring
    - Memory management with size limits
    """
    
    def __init__(self, default_ttl: int = 3600, max_entries: int = 1000):
        """
        Initialize cache with configuration.
        
        Args:
            default_ttl: Default time-to-live in seconds (1 hour)
            max_entries: Maximum number of cache entries
        """
        self.default_ttl = default_ttl
        self.max_entries = max_entries
        
        # Cache storage
        self._cache: Dict[str, CacheEntry] = {}
        
        # Thread safety
        self._lock = threading.RLock()
        
        # Statistics
        self._hits = 0
        self._misses = 0
        self._evictions = 0
        
        # Logging
        self.logger = logging.getLogger(__name__)
        
        self.logger.debug(f"Cache initialized: TTL={default_ttl}s, max_entries={max_entries}")
    
    def get(self, key: str) -> Optional[Any]:
        """
        Retrieve data from cache.
        
        Args:
            key: Cache key
            
        Returns:
            Cached data or None if not found/expired
        """
        with self._lock:
            if key not in self._cache:
                self._misses += 1
                return None
            
            entry = self._cache[key]
            
            if entry.is_expired():
                self.logger.debug(f"Cache entry expired: {key}")
                del self._cache[key]
                self._misses += 1
                return None
            
            entry.access()
            self._hits += 1
            
            self.logger.debug(f"Cache hit: {key}")
            return entry.data
    
    def set(self, key: str, data: Any, ttl: Optional[int] = None) -> None:
        """
        Store data in cache.
        
        Args:
            key: Cache key
            data: Data to cache
            ttl: Time-to-live override (uses default if None)
        """
        if ttl is None:
            ttl = self.default_ttl
        
        with self._lock:
            # Check if we need to evict entries
            if len(self._cache) >= self.max_entries and key not in self._cache:
                self._evict_entries()
            
            current_time = time.time()
            entry = CacheEntry(
                data=data,
                timestamp=current_time,
                ttl=ttl,
                last_accessed=current_time
            )
            
            self._cache[key] = entry
            
            self.logger.debug(f"Cache set: {key} (TTL={ttl}s)")
    
    def delete(self, key: str) -> bool:
        """
        Delete entry from cache.
        
        Args:
            key: Cache key
            
        Returns:
            True if entry was deleted, False if not found
        """
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                self.logger.debug(f"Cache entry deleted: {key}")
                return True
            return False
    
    def clear(self) -> None:
        """Clear all cache entries."""
        with self._lock:
            entry_count = len(self._cache)
            self._cache.clear()
            self.logger.info(f"Cache cleared: {entry_count} entries removed")
    
    def cleanup_expired(self) -> int:
        """
        Remove expired entries from cache.
        
        Returns:
            Number of entries removed
        """
        with self._lock:
            current_time = time.time()
            expired_keys = [
                key for key, entry in self._cache.items()
                if entry.is_expired(current_time)
            ]
            
            for key in expired_keys:
                del self._cache[key]
            
            if expired_keys:
                self.logger.debug(f"Cleaned up {len(expired_keys)} expired cache entries")
            
            return len(expired_keys)
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Dictionary with cache statistics
        """
        with self._lock:
            total_requests = self._hits + self._misses
            hit_rate = (self._hits / total_requests) if total_requests > 0 else 0
            
            return {
                'entries': len(self._cache),
                'max_entries': self.max_entries,
                'hits': self._hits,
                'misses': self._misses,
                'evictions': self._evictions,
                'hit_rate': hit_rate,
                'utilization': len(self._cache) / self.max_entries
            }
    
    def get_cache_info(self) -> Dict[str, Any]:
        """
        Get detailed cache information.
        
        Returns:
            Detailed cache information including entry details
        """
        with self._lock:
            current_time = time.time()
            entries_info = []
            
            for key, entry in self._cache.items():
                age = current_time - entry.timestamp
                remaining_ttl = max(0, entry.ttl - age)
                
                entries_info.append({
                    'key': key,
                    'age_seconds': age,
                    'remaining_ttl': remaining_ttl,
                    'access_count': entry.access_count,
                    'last_accessed': entry.last_accessed,
                    'is_expired': entry.is_expired(current_time)
                })
            
            # Sort by most recently accessed
            entries_info.sort(key=lambda x: x['last_accessed'], reverse=True)
            
            stats = self.get_statistics()
            
            return {
                'statistics': stats,
                'entries': entries_info[:20]  # Show top 20 most recent
            }
    
    def _evict_entries(self) -> None:
        """Evict least recently used entries to make room."""
        # Calculate how many entries to evict (10% of max)
        evict_count = max(1, self.max_entries // 10)
        
        # Sort entries by last accessed time
        sorted_entries = sorted(
            self._cache.items(),
            key=lambda x: x[1].last_accessed
        )
        
        # Remove oldest entries
        for i in range(min(evict_count, len(sorted_entries))):
            key = sorted_entries[i][0]
            del self._cache[key]
            self._evictions += 1
        
        self.logger.debug(f"Evicted {evict_count} cache entries")
    
    def __len__(self) -> int:
        """Return number of cache entries."""
        return len(self._cache)
    
    def __contains__(self, key: str) -> bool:
        """Check if key exists in cache (and is not expired)."""
        return self.get(key) is not None


class CacheKeyGenerator:
    """Utility class for generating consistent cache keys."""
    
    @staticmethod
    def generate_key(*args, **kwargs) -> str:
        """
        Generate a cache key from arguments.
        
        Args:
            *args: Positional arguments
            **kwargs: Keyword arguments
            
        Returns:
            String cache key
        """
        # Convert all arguments to a consistent string representation
        key_parts = []
        
        # Add positional args
        for arg in args:
            key_parts.append(str(arg))
        
        # Add keyword args (sorted for consistency)
        for key, value in sorted(kwargs.items()):
            key_parts.append(f"{key}={value}")
        
        # Create key string and hash it for consistent length
        key_string = "|".join(key_parts)
        return hashlib.md5(key_string.encode()).hexdigest()
    
    @staticmethod
    def team_data_key(team_name: str, data_type: str = "general") -> str:
        """Generate cache key for team data."""
        return f"team_data:{team_name}:{data_type}"
    
    @staticmethod
    def game_data_key(home_team: str, away_team: str, week: Optional[int] = None) -> str:
        """Generate cache key for game data."""
        week_str = f":week_{week}" if week else ""
        return f"game_data:{home_team}_vs_{away_team}{week_str}"
    
    @staticmethod
    def odds_data_key(sport: str = "cfb", week: Optional[int] = None) -> str:
        """Generate cache key for odds data."""
        week_str = f":week_{week}" if week else ""
        return f"odds_data:{sport}{week_str}"
    
    @staticmethod
    def factor_result_key(factor_name: str, home_team: str, away_team: str) -> str:
        """Generate cache key for factor calculation results."""
        return f"factor:{factor_name}:{home_team}_vs_{away_team}"


class CacheManager:
    """
    High-level cache manager for the application.
    
    Provides easy-to-use caching interface with semantic methods.
    """
    
    def __init__(self, default_ttl: int = 3600, max_entries: int = 1000):
        """
        Initialize cache manager.
        
        Args:
            default_ttl: Default cache TTL in seconds
            max_entries: Maximum cache entries
        """
        self.cache = DataCache(default_ttl, max_entries)
        self.key_gen = CacheKeyGenerator()
        self.logger = logging.getLogger(__name__)
    
    def cache_team_data(self, team_name: str, data: Dict[str, Any], 
                       data_type: str = "general", ttl: Optional[int] = None) -> None:
        """
        Cache team-specific data.
        
        Args:
            team_name: Normalized team name
            data: Team data to cache
            data_type: Type of data (e.g., 'stats', 'coaching', 'schedule')
            ttl: Cache TTL override
        """
        key = self.key_gen.team_data_key(team_name, data_type)
        self.cache.set(key, data, ttl)
    
    def get_team_data(self, team_name: str, data_type: str = "general") -> Optional[Dict[str, Any]]:
        """
        Retrieve cached team data.
        
        Args:
            team_name: Normalized team name
            data_type: Type of data to retrieve
            
        Returns:
            Cached team data or None
        """
        key = self.key_gen.team_data_key(team_name, data_type)
        return self.cache.get(key)
    
    def cache_game_data(self, home_team: str, away_team: str, data: Dict[str, Any],
                       week: Optional[int] = None, ttl: Optional[int] = None) -> None:
        """
        Cache game-specific data.
        
        Args:
            home_team: Home team name
            away_team: Away team name
            data: Game data to cache
            week: Week number
            ttl: Cache TTL override
        """
        key = self.key_gen.game_data_key(home_team, away_team, week)
        self.cache.set(key, data, ttl)
    
    def get_game_data(self, home_team: str, away_team: str, 
                     week: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """
        Retrieve cached game data.
        
        Args:
            home_team: Home team name
            away_team: Away team name
            week: Week number
            
        Returns:
            Cached game data or None
        """
        key = self.key_gen.game_data_key(home_team, away_team, week)
        return self.cache.get(key)
    
    def cache_odds_data(self, data: Dict[str, Any], sport: str = "cfb",
                       week: Optional[int] = None, ttl: Optional[int] = None) -> None:
        """
        Cache odds/betting data.
        
        Args:
            data: Odds data to cache
            sport: Sport identifier
            week: Week number
            ttl: Cache TTL override
        """
        key = self.key_gen.odds_data_key(sport, week)
        self.cache.set(key, data, ttl)
    
    def get_odds_data(self, sport: str = "cfb", week: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """
        Retrieve cached odds data.
        
        Args:
            sport: Sport identifier
            week: Week number
            
        Returns:
            Cached odds data or None
        """
        key = self.key_gen.odds_data_key(sport, week)
        return self.cache.get(key)
    
    def cache_factor_result(self, factor_name: str, home_team: str, away_team: str,
                           result: float, ttl: Optional[int] = None) -> None:
        """
        Cache factor calculation result.
        
        Args:
            factor_name: Name of the factor
            home_team: Home team name
            away_team: Away team name
            result: Factor calculation result
            ttl: Cache TTL override
        """
        key = self.key_gen.factor_result_key(factor_name, home_team, away_team)
        self.cache.set(key, result, ttl)
    
    def get_factor_result(self, factor_name: str, home_team: str, away_team: str) -> Optional[float]:
        """
        Retrieve cached factor result.
        
        Args:
            factor_name: Name of the factor
            home_team: Home team name
            away_team: Away team name
            
        Returns:
            Cached factor result or None
        """
        key = self.key_gen.factor_result_key(factor_name, home_team, away_team)
        return self.cache.get(key)
    
    def cleanup(self) -> int:
        """
        Clean up expired cache entries.
        
        Returns:
            Number of entries cleaned up
        """
        return self.cache.cleanup_expired()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return self.cache.get_statistics()
    
    def clear_all(self) -> None:
        """Clear all cached data."""
        self.cache.clear()


# Global cache manager instance
cache_manager = CacheManager()