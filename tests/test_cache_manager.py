"""
Tests for cache manager functionality.
"""

import unittest
import time
import threading
from data.cache_manager import DataCache, CacheKeyGenerator, CacheManager, CacheEntry


class TestCacheEntry(unittest.TestCase):
    """Test cases for CacheEntry class."""
    
    def test_cache_entry_creation(self):
        """Test cache entry creation and properties."""
        data = {'test': 'data'}
        timestamp = time.time()
        ttl = 3600
        
        entry = CacheEntry(data, timestamp, ttl)
        
        self.assertEqual(entry.data, data)
        self.assertEqual(entry.timestamp, timestamp)
        self.assertEqual(entry.ttl, ttl)
        self.assertEqual(entry.access_count, 0)
        self.assertEqual(entry.last_accessed, 0)
    
    def test_cache_entry_expiration(self):
        """Test cache entry expiration logic."""
        timestamp = time.time()
        entry = CacheEntry({'test': 'data'}, timestamp, 10)  # 10 second TTL
        
        # Should not be expired immediately
        self.assertFalse(entry.is_expired(timestamp))
        
        # Should be expired after TTL
        self.assertTrue(entry.is_expired(timestamp + 11))
        
        # Test with current time
        entry = CacheEntry({'test': 'data'}, time.time() - 11, 10)
        self.assertTrue(entry.is_expired())
    
    def test_cache_entry_access_tracking(self):
        """Test access count tracking."""
        entry = CacheEntry({'test': 'data'}, time.time(), 3600)
        
        # Initial state
        self.assertEqual(entry.access_count, 0)
        self.assertEqual(entry.last_accessed, 0)
        
        # After access
        entry.access()
        self.assertEqual(entry.access_count, 1)
        self.assertGreater(entry.last_accessed, 0)
        
        # Multiple accesses
        entry.access()
        entry.access()
        self.assertEqual(entry.access_count, 3)


class TestDataCache(unittest.TestCase):
    """Test cases for DataCache class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.cache = DataCache(default_ttl=60, max_entries=10)
    
    def test_cache_set_and_get(self):
        """Test basic cache set and get operations."""
        key = 'test_key'
        data = {'team': 'alabama', 'score': 35}
        
        # Set data
        self.cache.set(key, data)
        
        # Get data
        result = self.cache.get(key)
        self.assertEqual(result, data)
    
    def test_cache_miss(self):
        """Test cache miss scenarios."""
        # Non-existent key
        result = self.cache.get('nonexistent')
        self.assertIsNone(result)
        
        # Check statistics
        stats = self.cache.get_statistics()
        self.assertEqual(stats['misses'], 1)
        self.assertEqual(stats['hits'], 0)
    
    def test_cache_expiration(self):
        """Test cache entry expiration."""
        key = 'test_key'
        data = {'test': 'data'}
        
        # Set with short TTL
        self.cache.set(key, data, ttl=1)
        
        # Should be available immediately
        result = self.cache.get(key)
        self.assertEqual(result, data)
        
        # Wait for expiration
        time.sleep(1.1)
        
        # Should be expired
        result = self.cache.get(key)
        self.assertIsNone(result)
    
    def test_cache_ttl_override(self):
        """Test TTL override functionality."""
        key = 'test_key'
        data = {'test': 'data'}
        
        # Set with custom TTL
        self.cache.set(key, data, ttl=2)
        
        # Verify entry has correct TTL
        entry = self.cache._cache[key]
        self.assertEqual(entry.ttl, 2)
    
    def test_cache_delete(self):
        """Test cache entry deletion."""
        key = 'test_key'
        data = {'test': 'data'}
        
        # Set data
        self.cache.set(key, data)
        self.assertIsNotNone(self.cache.get(key))
        
        # Delete
        result = self.cache.delete(key)
        self.assertTrue(result)
        self.assertIsNone(self.cache.get(key))
        
        # Delete non-existent key
        result = self.cache.delete('nonexistent')
        self.assertFalse(result)
    
    def test_cache_clear(self):
        """Test cache clearing."""
        # Add some entries
        for i in range(5):
            self.cache.set(f'key_{i}', {'data': i})
        
        self.assertEqual(len(self.cache), 5)
        
        # Clear cache
        self.cache.clear()
        self.assertEqual(len(self.cache), 0)
    
    def test_cache_cleanup_expired(self):
        """Test cleanup of expired entries."""
        # Add entries with different TTLs
        self.cache.set('short_ttl', {'data': 1}, ttl=1)
        self.cache.set('long_ttl', {'data': 2}, ttl=10)
        
        # Wait for short TTL to expire
        time.sleep(1.1)
        
        # Cleanup
        removed_count = self.cache.cleanup_expired()
        self.assertEqual(removed_count, 1)
        
        # Verify correct entry was removed
        self.assertIsNone(self.cache.get('short_ttl'))
        self.assertIsNotNone(self.cache.get('long_ttl'))
    
    def test_cache_statistics(self):
        """Test cache statistics tracking."""
        # Initial state
        stats = self.cache.get_statistics()
        self.assertEqual(stats['hits'], 0)
        self.assertEqual(stats['misses'], 0)
        self.assertEqual(stats['entries'], 0)
        
        # Add entry and access it
        self.cache.set('key1', {'data': 1})
        self.cache.get('key1')  # Hit
        self.cache.get('key2')  # Miss
        
        stats = self.cache.get_statistics()
        self.assertEqual(stats['hits'], 1)
        self.assertEqual(stats['misses'], 1)
        self.assertEqual(stats['entries'], 1)
        self.assertEqual(stats['hit_rate'], 0.5)
    
    def test_cache_eviction(self):
        """Test cache eviction when max entries reached."""
        # Fill cache to capacity
        for i in range(self.cache.max_entries):
            self.cache.set(f'key_{i}', {'data': i})
        
        self.assertEqual(len(self.cache), self.cache.max_entries)
        
        # Add one more entry (should trigger eviction)
        self.cache.set('overflow_key', {'data': 'overflow'})
        
        # Cache should not exceed max entries
        self.assertLessEqual(len(self.cache), self.cache.max_entries)
        
        # New entry should be present
        self.assertIsNotNone(self.cache.get('overflow_key'))
    
    def test_cache_thread_safety(self):
        """Test cache thread safety."""
        num_threads = 5
        entries_per_thread = 10
        
        def worker(thread_id):
            for i in range(entries_per_thread):
                key = f'thread_{thread_id}_key_{i}'
                data = {'thread': thread_id, 'data': i}
                self.cache.set(key, data)
                
                # Read back immediately
                result = self.cache.get(key)
                self.assertEqual(result, data)
        
        # Start multiple threads
        threads = []
        for i in range(num_threads):
            thread = threading.Thread(target=worker, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Verify expected number of entries
        expected_entries = min(num_threads * entries_per_thread, self.cache.max_entries)
        self.assertLessEqual(len(self.cache), expected_entries)
    
    def test_cache_contains(self):
        """Test cache __contains__ method."""
        key = 'test_key'
        data = {'test': 'data'}
        
        # Key not in cache
        self.assertNotIn(key, self.cache)
        
        # Add key
        self.cache.set(key, data)
        self.assertIn(key, self.cache)
        
        # Expired key should not be contained
        self.cache.set('expired_key', data, ttl=1)
        time.sleep(1.1)
        self.assertNotIn('expired_key', self.cache)


class TestCacheKeyGenerator(unittest.TestCase):
    """Test cases for CacheKeyGenerator class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.key_gen = CacheKeyGenerator()
    
    def test_generate_key_basic(self):
        """Test basic key generation."""
        key = self.key_gen.generate_key('arg1', 'arg2', param1='value1')
        
        # Should return a string
        self.assertIsInstance(key, str)
        
        # Should be consistent
        key2 = self.key_gen.generate_key('arg1', 'arg2', param1='value1')
        self.assertEqual(key, key2)
    
    def test_generate_key_order_independence(self):
        """Test that keyword argument order doesn't affect key."""
        key1 = self.key_gen.generate_key(param1='value1', param2='value2')
        key2 = self.key_gen.generate_key(param2='value2', param1='value1')
        
        self.assertEqual(key1, key2)
    
    def test_generate_key_different_inputs(self):
        """Test that different inputs generate different keys."""
        key1 = self.key_gen.generate_key('arg1', param1='value1')
        key2 = self.key_gen.generate_key('arg2', param1='value1')
        key3 = self.key_gen.generate_key('arg1', param1='value2')
        
        # All keys should be different
        self.assertNotEqual(key1, key2)
        self.assertNotEqual(key1, key3)
        self.assertNotEqual(key2, key3)
    
    def test_team_data_key(self):
        """Test team data key generation."""
        key = self.key_gen.team_data_key('ALABAMA', 'stats')
        
        self.assertIsInstance(key, str)
        self.assertIn('team_data', key)
        self.assertIn('ALABAMA', key)
        self.assertIn('stats', key)
    
    def test_game_data_key(self):
        """Test game data key generation."""
        key = self.key_gen.game_data_key('ALABAMA', 'GEORGIA', 8)
        
        self.assertIsInstance(key, str)
        self.assertIn('game_data', key)
        self.assertIn('ALABAMA', key)
        self.assertIn('GEORGIA', key)
        self.assertIn('week_8', key)
        
        # Test without week
        key_no_week = self.key_gen.game_data_key('ALABAMA', 'GEORGIA')
        self.assertNotEqual(key, key_no_week)
    
    def test_odds_data_key(self):
        """Test odds data key generation."""
        key = self.key_gen.odds_data_key('cfb', 8)
        
        self.assertIsInstance(key, str)
        self.assertIn('odds_data', key)
        self.assertIn('cfb', key)
        self.assertIn('week_8', key)
    
    def test_factor_result_key(self):
        """Test factor result key generation."""
        key = self.key_gen.factor_result_key('coaching_edge', 'ALABAMA', 'GEORGIA')
        
        self.assertIsInstance(key, str)
        self.assertIn('factor', key)
        self.assertIn('coaching_edge', key)
        self.assertIn('ALABAMA', key)
        self.assertIn('GEORGIA', key)


class TestCacheManager(unittest.TestCase):
    """Test cases for CacheManager class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.cache_manager = CacheManager(default_ttl=60, max_entries=100)
    
    def test_cache_team_data(self):
        """Test team data caching."""
        team_name = 'ALABAMA'
        data = {'coach': 'Nick Saban', 'wins': 10}
        
        # Cache data
        self.cache_manager.cache_team_data(team_name, data, 'coaching')
        
        # Retrieve data
        result = self.cache_manager.get_team_data(team_name, 'coaching')
        self.assertEqual(result, data)
        
        # Different data type should return None
        result = self.cache_manager.get_team_data(team_name, 'stats')
        self.assertIsNone(result)
    
    def test_cache_game_data(self):
        """Test game data caching."""
        home_team = 'ALABAMA'
        away_team = 'GEORGIA'
        week = 8
        data = {'spread': -7.5, 'total': 55.5}
        
        # Cache data
        self.cache_manager.cache_game_data(home_team, away_team, data, week)
        
        # Retrieve data
        result = self.cache_manager.get_game_data(home_team, away_team, week)
        self.assertEqual(result, data)
        
        # Different week should return None
        result = self.cache_manager.get_game_data(home_team, away_team, 9)
        self.assertIsNone(result)
    
    def test_cache_odds_data(self):
        """Test odds data caching."""
        data = {'games': [{'home': 'ALABAMA', 'away': 'GEORGIA', 'spread': -7.5}]}
        
        # Cache data
        self.cache_manager.cache_odds_data(data, 'cfb', 8)
        
        # Retrieve data
        result = self.cache_manager.get_odds_data('cfb', 8)
        self.assertEqual(result, data)
        
        # Different week should return None
        result = self.cache_manager.get_odds_data('cfb', 9)
        self.assertIsNone(result)
    
    def test_cache_factor_result(self):
        """Test factor result caching."""
        factor_name = 'coaching_edge'
        home_team = 'ALABAMA'
        away_team = 'GEORGIA'
        result_value = 2.5
        
        # Cache result
        self.cache_manager.cache_factor_result(factor_name, home_team, away_team, result_value)
        
        # Retrieve result
        result = self.cache_manager.get_factor_result(factor_name, home_team, away_team)
        self.assertEqual(result, result_value)
        
        # Different factor should return None
        result = self.cache_manager.get_factor_result('momentum', home_team, away_team)
        self.assertIsNone(result)
    
    def test_cache_manager_cleanup(self):
        """Test cache manager cleanup."""
        # Add some data with short TTL
        self.cache_manager.cache_team_data('ALABAMA', {'test': 'data'}, ttl=1)
        
        # Wait for expiration
        time.sleep(1.1)
        
        # Cleanup
        removed_count = self.cache_manager.cleanup()
        self.assertGreater(removed_count, 0)
    
    def test_cache_manager_stats(self):
        """Test cache manager statistics."""
        # Add some data
        self.cache_manager.cache_team_data('ALABAMA', {'test': 'data'})
        self.cache_manager.get_team_data('ALABAMA')  # Hit
        self.cache_manager.get_team_data('GEORGIA')  # Miss
        
        stats = self.cache_manager.get_stats()
        
        self.assertIn('hits', stats)
        self.assertIn('misses', stats)
        self.assertIn('entries', stats)
        self.assertIn('hit_rate', stats)
    
    def test_cache_manager_clear_all(self):
        """Test cache manager clear all."""
        # Add some data
        self.cache_manager.cache_team_data('ALABAMA', {'test': 'data'})
        self.cache_manager.cache_game_data('ALABAMA', 'GEORGIA', {'test': 'game'})
        
        # Verify data exists
        self.assertIsNotNone(self.cache_manager.get_team_data('ALABAMA'))
        
        # Clear all
        self.cache_manager.clear_all()
        
        # Verify data is gone
        self.assertIsNone(self.cache_manager.get_team_data('ALABAMA'))
        self.assertIsNone(self.cache_manager.get_game_data('ALABAMA', 'GEORGIA'))


class TestCacheIntegration(unittest.TestCase):
    """Integration tests for cache components."""
    
    def test_cache_with_normalizer(self):
        """Test cache integration with team name normalizer."""
        from utils.normalizer import normalizer
        
        cache_manager = CacheManager()
        
        # Cache data with normalized team name
        normalized_name = normalizer.normalize('alabama')
        cache_manager.cache_team_data(normalized_name, {'test': 'data'})
        
        # Should be able to retrieve with normalized name
        result = cache_manager.get_team_data(normalized_name)
        self.assertIsNotNone(result)
        
        # Different input for same team should use same cache key after normalization
        normalized_name2 = normalizer.normalize('bama')
        self.assertEqual(normalized_name, normalized_name2)
    
    def test_cache_performance(self):
        """Test cache performance with many operations."""
        cache = DataCache(max_entries=1000)
        
        # Time cache operations
        start_time = time.time()
        
        # Add many entries
        for i in range(500):
            cache.set(f'key_{i}', {'data': i})
        
        # Read many entries
        for i in range(500):
            cache.get(f'key_{i}')
        
        end_time = time.time()
        
        # Operations should be fast
        self.assertLess(end_time - start_time, 1.0)  # Should complete in less than 1 second
        
        # Verify statistics
        stats = cache.get_statistics()
        self.assertEqual(stats['hits'], 500)
        self.assertEqual(stats['entries'], 500)


if __name__ == '__main__':
    unittest.main()