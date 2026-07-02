"""
Tests for rate limiter functionality.
"""

import unittest
import time
import threading
from unittest.mock import patch
from utils.rate_limiter import RateLimiter, APIRateLimiterManager, setup_api_rate_limiters


class TestRateLimiter(unittest.TestCase):
    """Test cases for RateLimiter class."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Use fast limits for testing
        self.limiter = RateLimiter(calls_per_minute=6, calls_per_day=100)  # 6/min for easy testing
    
    def test_initial_state(self):
        """Test rate limiter initial state."""
        remaining = self.limiter.get_remaining_calls()
        
        self.assertEqual(remaining['minute'], 6)
        self.assertEqual(remaining['day'], 100)
        self.assertTrue(self.limiter.can_make_call())
    
    def test_single_call(self):
        """Test making a single call."""
        wait_time = self.limiter.wait_if_needed()
        
        # First call should not require waiting
        self.assertEqual(wait_time, 0)
        
        # Check remaining calls
        remaining = self.limiter.get_remaining_calls()
        self.assertEqual(remaining['minute'], 5)
        self.assertEqual(remaining['day'], 99)
    
    def test_multiple_calls_within_limit(self):
        """Test multiple calls within rate limit."""
        # Make 5 calls (should all be immediate)
        total_wait = 0
        for i in range(5):
            wait_time = self.limiter.wait_if_needed()
            total_wait += wait_time
        
        # No waiting should be required
        self.assertEqual(total_wait, 0)
        
        # Check remaining calls
        remaining = self.limiter.get_remaining_calls()
        self.assertEqual(remaining['minute'], 1)
        self.assertEqual(remaining['day'], 95)
    
    def test_rate_limit_enforcement(self):
        """Test that rate limit is enforced."""
        # Exhaust minute limit
        for i in range(6):
            self.limiter.wait_if_needed()
        
        # Next call should require waiting
        self.assertFalse(self.limiter.can_make_call())
        
        # Verify remaining calls
        remaining = self.limiter.get_remaining_calls()
        self.assertEqual(remaining['minute'], 0)
    
    def test_sliding_window(self):
        """Test sliding window behavior."""
        # Make calls rapidly to fill the window
        for i in range(6):
            self.limiter.wait_if_needed()
        
        # Should not be able to make another call immediately
        self.assertFalse(self.limiter.can_make_call())
        
        # Wait for sliding window to allow new calls (need to wait > 10 seconds for 6/min)
        # For testing, we'll simulate time passage
        with patch('time.time') as mock_time:
            # Set initial time
            base_time = 1000.0
            mock_time.return_value = base_time
            
            # Reset limiter with mocked time
            limiter = RateLimiter(calls_per_minute=6)
            
            # Fill the limit
            for i in range(6):
                mock_time.return_value = base_time + i
                limiter.wait_if_needed()
            
            # Should be at limit
            self.assertFalse(limiter.can_make_call())
            
            # Advance time by 61 seconds
            mock_time.return_value = base_time + 61
            
            # Should be able to make calls again
            self.assertTrue(limiter.can_make_call())
    
    def test_day_limit_only(self):
        """Test rate limiter with only day limit."""
        limiter = RateLimiter(calls_per_minute=1000, calls_per_day=5)  # High minute limit, low day limit
        
        # Make calls up to day limit
        for i in range(5):
            wait_time = limiter.wait_if_needed()
            self.assertEqual(wait_time, 0)
        
        # Next call should be blocked by day limit
        self.assertFalse(limiter.can_make_call())
        
        remaining = limiter.get_remaining_calls()
        self.assertEqual(remaining['day'], 0)
        self.assertGreater(remaining['minute'], 0)  # Minute limit should still have capacity
    
    def test_no_day_limit(self):
        """Test rate limiter without day limit."""
        limiter = RateLimiter(calls_per_minute=60)  # No day limit
        
        remaining = limiter.get_remaining_calls()
        self.assertIsNone(remaining['day'])
        self.assertEqual(remaining['minute'], 60)
    
    def test_reset_functionality(self):
        """Test rate limiter reset."""
        # Make some calls
        for i in range(3):
            self.limiter.wait_if_needed()
        
        remaining_before = self.limiter.get_remaining_calls()
        self.assertEqual(remaining_before['minute'], 3)
        
        # Reset
        self.limiter.reset()
        
        # Should be back to initial state
        remaining_after = self.limiter.get_remaining_calls()
        self.assertEqual(remaining_after['minute'], 6)
        self.assertEqual(remaining_after['day'], 100)
    
    def test_thread_safety(self):
        """Test rate limiter thread safety."""
        call_count = [0]  # Use list for mutable counter
        errors = []
        
        def worker():
            try:
                for i in range(5):
                    self.limiter.wait_if_needed()
                    call_count[0] += 1
                    time.sleep(0.01)  # Small delay
            except Exception as e:
                errors.append(e)
        
        # Start multiple threads
        threads = []
        for i in range(3):
            thread = threading.Thread(target=worker)
            threads.append(thread)
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        # Check for errors
        self.assertEqual(len(errors), 0, f"Errors occurred: {errors}")
        
        # All calls should have been made
        self.assertEqual(call_count[0], 15)
    
    def test_string_representation(self):
        """Test string representation of rate limiter."""
        limiter_str = str(self.limiter)
        
        self.assertIn('RateLimiter', limiter_str)
        self.assertIn('/min', limiter_str)
        self.assertIn('/day', limiter_str)
        self.assertIn('remaining', limiter_str)


class TestAPIRateLimiterManager(unittest.TestCase):
    """Test cases for APIRateLimiterManager class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.manager = APIRateLimiterManager()
    
    def test_create_limiter(self):
        """Test creating rate limiters."""
        limiter = self.manager.create_limiter('test_api', 60, 1000)
        
        self.assertIsInstance(limiter, RateLimiter)
        self.assertEqual(limiter.calls_per_minute, 60)
        self.assertEqual(limiter.calls_per_day, 1000)
        
        # Should be able to retrieve it
        retrieved = self.manager.get_limiter('test_api')
        self.assertIs(retrieved, limiter)
    
    def test_get_nonexistent_limiter(self):
        """Test getting non-existent rate limiter."""
        result = self.manager.get_limiter('nonexistent')
        self.assertIsNone(result)
    
    def test_wait_for_api(self):
        """Test waiting for specific API."""
        # Create limiter
        self.manager.create_limiter('test_api', 60)
        
        # Should not wait for first call
        wait_time = self.manager.wait_for_api('test_api')
        self.assertEqual(wait_time, 0)
    
    def test_wait_for_nonexistent_api(self):
        """Test waiting for non-existent API raises error."""
        with self.assertRaises(ValueError):
            self.manager.wait_for_api('nonexistent')
    
    def test_get_status(self):
        """Test getting status of all limiters."""
        # Create some limiters
        self.manager.create_limiter('api1', 60, 1000)
        self.manager.create_limiter('api2', 30)
        
        status = self.manager.get_status()
        
        self.assertIn('api1', status)
        self.assertIn('api2', status)
        
        # Check structure
        api1_status = status['api1']
        self.assertIn('limiter', api1_status)
        self.assertIn('remaining_calls', api1_status)
        self.assertIn('can_make_call', api1_status)
        
        # Check remaining calls structure
        remaining = api1_status['remaining_calls']
        self.assertIn('minute', remaining)
        self.assertIn('day', remaining)
    
    def test_reset_all(self):
        """Test resetting all rate limiters."""
        # Create limiters and make some calls
        limiter1 = self.manager.create_limiter('api1', 60)
        limiter2 = self.manager.create_limiter('api2', 30)
        
        # Make some calls
        limiter1.wait_if_needed()
        limiter2.wait_if_needed()
        
        # Check they have been used
        self.assertEqual(limiter1.get_remaining_calls()['minute'], 59)
        self.assertEqual(limiter2.get_remaining_calls()['minute'], 29)
        
        # Reset all
        self.manager.reset_all()
        
        # Check they are back to initial state
        self.assertEqual(limiter1.get_remaining_calls()['minute'], 60)
        self.assertEqual(limiter2.get_remaining_calls()['minute'], 30)


class TestRateLimiterSetup(unittest.TestCase):
    """Test cases for rate limiter setup functionality."""
    
    def test_setup_api_rate_limiters(self):
        """Test setting up API rate limiters."""
        # Clear any existing limiters
        from utils.rate_limiter import rate_limiter_manager
        rate_limiter_manager.limiters.clear()
        
        # Setup limiters
        setup_api_rate_limiters(odds_limit=100, espn_limit=120)
        
        # Check that limiters were created
        odds_limiter = rate_limiter_manager.get_limiter('odds_api')
        espn_limiter = rate_limiter_manager.get_limiter('espn_api')
        
        self.assertIsNotNone(odds_limiter)
        self.assertIsNotNone(espn_limiter)
        
        # Check ESPN limiter
        self.assertEqual(espn_limiter.calls_per_minute, 120)
        self.assertIsNone(espn_limiter.calls_per_day)
        
        # Check Odds limiter
        self.assertIsNotNone(odds_limiter.calls_per_day)
        self.assertEqual(odds_limiter.calls_per_day, 100)
    
    def test_setup_with_default_limits(self):
        """Test setup with default rate limits."""
        from utils.rate_limiter import rate_limiter_manager
        rate_limiter_manager.limiters.clear()
        
        # Setup with defaults
        setup_api_rate_limiters()
        
        # Check that limiters exist
        odds_limiter = rate_limiter_manager.get_limiter('odds_api')
        espn_limiter = rate_limiter_manager.get_limiter('espn_api')
        
        self.assertIsNotNone(odds_limiter)
        self.assertIsNotNone(espn_limiter)
        
        # Check default values
        self.assertEqual(espn_limiter.calls_per_minute, 60)
        self.assertEqual(odds_limiter.calls_per_day, 83)


class TestRateLimiterEdgeCases(unittest.TestCase):
    """Test edge cases and error conditions."""
    
    def test_zero_limits(self):
        """Test rate limiter with zero limits."""
        limiter = RateLimiter(calls_per_minute=0, calls_per_day=0)
        
        # Should not be able to make any calls
        self.assertFalse(limiter.can_make_call())
        
        remaining = limiter.get_remaining_calls()
        self.assertEqual(remaining['minute'], 0)
        self.assertEqual(remaining['day'], 0)
    
    def test_very_high_limits(self):
        """Test rate limiter with very high limits."""
        limiter = RateLimiter(calls_per_minute=10000, calls_per_day=1000000)
        
        # Should be able to make many calls without waiting
        for i in range(100):
            wait_time = limiter.wait_if_needed()
            self.assertEqual(wait_time, 0)
        
        self.assertTrue(limiter.can_make_call())
    
    def test_cleanup_old_calls(self):
        """Test internal cleanup of old call records."""
        with patch('time.time') as mock_time:
            base_time = 1000.0
            mock_time.return_value = base_time
            
            limiter = RateLimiter(calls_per_minute=60)
            
            # Make some calls
            for i in range(5):
                mock_time.return_value = base_time + i
                limiter.wait_if_needed()
            
            # Advance time significantly
            mock_time.return_value = base_time + 3600  # 1 hour later
            
            # Cleanup should occur during next operation
            limiter._cleanup_old_calls(mock_time.return_value)
            
            # Old calls should be cleaned up
            self.assertEqual(len(limiter.minute_calls), 0)
            self.assertEqual(len(limiter.day_calls), 0)
    
    def test_concurrent_access_different_apis(self):
        """Test concurrent access to different API limiters."""
        manager = APIRateLimiterManager()
        
        # Create limiters for different APIs
        manager.create_limiter('api1', 60)
        manager.create_limiter('api2', 30)
        
        results = []
        
        def worker(api_name, iterations):
            for i in range(iterations):
                wait_time = manager.wait_for_api(api_name)
                results.append((api_name, wait_time))
        
        # Start threads for different APIs
        threads = []
        threads.append(threading.Thread(target=worker, args=('api1', 10)))
        threads.append(threading.Thread(target=worker, args=('api2', 5)))
        
        for thread in threads:
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # All operations should complete
        self.assertEqual(len(results), 15)
        
        # Check that we have results for both APIs
        api1_results = [r for r in results if r[0] == 'api1']
        api2_results = [r for r in results if r[0] == 'api2']
        
        self.assertEqual(len(api1_results), 10)
        self.assertEqual(len(api2_results), 5)


if __name__ == '__main__':
    unittest.main()