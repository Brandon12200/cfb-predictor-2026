"""
Unit tests for performance tracker module.
Tests execution time monitoring, API call tracking, and system performance.
"""

import unittest
from unittest.mock import patch, MagicMock
import time
from datetime import datetime, timedelta
import threading
import statistics

from utils.performance_tracker import PerformanceTracker, performance_tracker


class TestPerformanceTracker(unittest.TestCase):
    """Test the performance tracker functionality."""
    
    def setUp(self):
        """Set up test environment."""
        self.tracker = PerformanceTracker(max_history=100)
        self.tracker.reset_metrics()  # Start with clean slate
    
    def test_initialization(self):
        """Test tracker initialization."""
        tracker = PerformanceTracker(max_history=50)
        
        self.assertEqual(tracker.max_history, 50)
        self.assertEqual(len(tracker.execution_times), 0)
        self.assertEqual(len(tracker.component_times), 0)
        self.assertEqual(len(tracker.api_calls), 0)
        self.assertEqual(tracker.prediction_count, 0)
        self.assertEqual(tracker.success_count, 0)
        self.assertEqual(tracker.error_count, 0)
        self.assertIsNotNone(tracker.session_start)
    
    def test_timer_operations(self):
        """Test timer start and stop operations."""
        # Start timer
        timer_id = self.tracker.start_timer('test_operation')
        self.assertIsNotNone(timer_id)
        self.assertIn('test_operation', timer_id)
        self.assertIn(timer_id, self.tracker.active_timers)
        
        # Brief pause
        time.sleep(0.1)
        
        # Stop timer
        duration = self.tracker.stop_timer(timer_id)
        self.assertGreater(duration, 0.05)  # Should be at least 50ms
        self.assertNotIn(timer_id, self.tracker.active_timers)
        
        # Check component timing was recorded
        self.assertEqual(len(self.tracker.component_times['test_operation']), 1)
        self.assertAlmostEqual(
            self.tracker.component_times['test_operation'][0], 
            duration, 
            places=3
        )
    
    def test_timer_not_found(self):
        """Test stopping non-existent timer."""
        duration = self.tracker.stop_timer('non_existent_timer')
        self.assertEqual(duration, 0.0)
    
    def test_record_prediction(self):
        """Test prediction recording."""
        # Record successful predictions
        self.tracker.record_prediction(1.5, success=True)
        self.tracker.record_prediction(2.0, success=True)
        self.tracker.record_prediction(3.5, success=False)
        
        self.assertEqual(self.tracker.prediction_count, 3)
        self.assertEqual(self.tracker.success_count, 2)
        self.assertEqual(self.tracker.error_count, 1)
        self.assertEqual(len(self.tracker.execution_times), 3)
        self.assertEqual(list(self.tracker.execution_times), [1.5, 2.0, 3.5])
    
    def test_record_api_call(self):
        """Test API call recording."""
        # Record successful API calls
        self.tracker.record_api_call('odds_api', 1.2, success=True)
        self.tracker.record_api_call('odds_api', 0.8, success=True)
        self.tracker.record_api_call('espn_api', 2.5, success=False)
        
        self.assertEqual(self.tracker.api_calls['odds_api'], 2)
        self.assertEqual(self.tracker.api_calls['espn_api'], 1)
        self.assertEqual(self.tracker.api_failures['odds_api'], 0)
        self.assertEqual(self.tracker.api_failures['espn_api'], 1)
        
        # Check response times
        odds_times = list(self.tracker.api_response_times['odds_api'])
        self.assertEqual(odds_times, [1.2, 0.8])
    
    def test_session_info(self):
        """Test session information generation."""
        # Record some data
        self.tracker.record_prediction(1.0, success=True)
        self.tracker.record_prediction(2.0, success=True)
        self.tracker.record_prediction(3.0, success=False)
        
        session_info = self.tracker._get_session_info()
        
        self.assertIn('session_start', session_info)
        self.assertIn('session_duration_seconds', session_info)
        self.assertEqual(session_info['total_predictions'], 3)
        self.assertAlmostEqual(session_info['success_rate'], 2/3, places=2)
        self.assertAlmostEqual(session_info['error_rate'], 1/3, places=2)
        self.assertGreater(session_info['session_duration_seconds'], 0)
    
    def test_execution_metrics(self):
        """Test execution metrics calculation."""
        # No data case
        metrics = self.tracker._get_execution_metrics()
        self.assertEqual(metrics['avg_execution_time'], 0.0)
        self.assertEqual(metrics['total_predictions'], 0)
        
        # With data
        times = [1.0, 2.0, 3.0, 4.0, 5.0, 10.0, 15.0, 20.0]
        for t in times:
            self.tracker.record_prediction(t)
        
        metrics = self.tracker._get_execution_metrics()
        
        self.assertEqual(metrics['avg_execution_time'], statistics.mean(times))
        self.assertEqual(metrics['min_execution_time'], 1.0)
        self.assertEqual(metrics['max_execution_time'], 20.0)
        self.assertEqual(metrics['median_execution_time'], statistics.median(times))
        self.assertEqual(metrics['total_predictions'], 8)
        
        # Test under 15s rate
        under_15s = sum(1 for t in times if t < 15.0)
        expected_rate = under_15s / len(times)
        self.assertEqual(metrics['under_15s_rate'], expected_rate)
    
    def test_api_metrics(self):
        """Test API metrics calculation."""
        # Record API calls
        self.tracker.record_api_call('test_api', 1.0, success=True)
        self.tracker.record_api_call('test_api', 2.0, success=True)
        self.tracker.record_api_call('test_api', 3.0, success=False)
        
        metrics = self.tracker._get_api_metrics()
        
        self.assertIn('test_api', metrics)
        api_metric = metrics['test_api']
        
        self.assertEqual(api_metric['total_calls'], 3)
        self.assertEqual(api_metric['total_failures'], 1)
        self.assertAlmostEqual(api_metric['success_rate'], 2/3, places=2)
        self.assertEqual(api_metric['avg_response_time'], 2.0)  # (1+2+3)/3
        self.assertEqual(api_metric['min_response_time'], 1.0)
        self.assertEqual(api_metric['max_response_time'], 3.0)
    
    def test_component_metrics(self):
        """Test component metrics calculation."""
        # Record component timings
        timer1 = self.tracker.start_timer('factor_calculation')
        time.sleep(0.1)
        self.tracker.stop_timer(timer1)
        
        timer2 = self.tracker.start_timer('factor_calculation')
        time.sleep(0.05)
        self.tracker.stop_timer(timer2)
        
        metrics = self.tracker._get_component_metrics()
        
        self.assertIn('factor_calculation', metrics)
        component_metric = metrics['factor_calculation']
        
        self.assertEqual(component_metric['total_calls'], 2)
        self.assertGreater(component_metric['avg_time'], 0.05)
        self.assertLess(component_metric['avg_time'], 0.2)
        self.assertGreater(component_metric['max_time'], 0.08)
    
    def test_percentile_calculation(self):
        """Test percentile calculation."""
        data = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        
        # Test various percentiles
        self.assertEqual(self.tracker._percentile(data, 50), 5.5)  # Median
        self.assertEqual(self.tracker._percentile(data, 90), 9.1)
        self.assertAlmostEqual(self.tracker._percentile(data, 95), 9.55, places=1)
        self.assertEqual(self.tracker._percentile(data, 100), 10)
        
        # Edge cases
        self.assertEqual(self.tracker._percentile([], 50), 0.0)
        self.assertEqual(self.tracker._percentile([5], 50), 5)
    
    def test_performance_alerts(self):
        """Test performance alert generation."""
        # No alerts initially
        alerts = self.tracker._get_performance_alerts()
        self.assertEqual(len(alerts), 0)
        
        # Create slow execution times
        for _ in range(10):
            self.tracker.record_prediction(12.0)  # High average
        
        alerts = self.tracker._get_performance_alerts()
        self.assertTrue(any('High average execution time' in alert for alert in alerts))
        
        # Add very slow prediction
        self.tracker.record_prediction(35.0)
        alerts = self.tracker._get_performance_alerts()
        self.assertTrue(any('Very slow prediction' in alert for alert in alerts))
        
        # Test API failure alerts
        for _ in range(10):
            self.tracker.record_api_call('failing_api', 1.0, success=False)
        
        alerts = self.tracker._get_performance_alerts()
        self.assertTrue(any('High failing_api API failure rate' in alert for alert in alerts))
    
    def test_optimization_recommendations(self):
        """Test optimization recommendations."""
        # Initially no recommendations
        recommendations = self.tracker.optimize_recommendations()
        self.assertEqual(len(recommendations), 0)
        
        # Create slow execution scenario
        for _ in range(5):
            self.tracker.record_prediction(10.0)
        
        recommendations = self.tracker.optimize_recommendations()
        self.assertTrue(any('caching' in rec.lower() for rec in recommendations))
        
        # Create very slow scenario
        for _ in range(5):
            self.tracker.record_prediction(15.0)
        
        recommendations = self.tracker.optimize_recommendations()
        self.assertTrue(any('factor complexity' in rec.lower() for rec in recommendations))
        
        # Test API call recommendations
        self.tracker.prediction_count = 1
        for _ in range(15):  # More than 10 calls per prediction
            self.tracker.record_api_call('test_api', 1.0)
        
        recommendations = self.tracker.optimize_recommendations()
        self.assertTrue(any('Too many API calls' in rec for rec in recommendations))
    
    def test_realtime_status(self):
        """Test real-time status calculation."""
        # No data case
        status = self.tracker.get_realtime_status()
        self.assertEqual(status['recent_avg_time'], 0.0)
        self.assertEqual(status['trend'], 'no_data')
        self.assertEqual(status['session_predictions'], 0)
        
        # With data - stable trend
        times = [2.0, 2.1, 1.9, 2.0, 2.1]
        for t in times:
            self.tracker.record_prediction(t)
        
        status = self.tracker.get_realtime_status()
        self.assertAlmostEqual(status['recent_avg_time'], 2.02, places=1)
        self.assertEqual(status['trend'], 'stable')
        self.assertEqual(status['session_predictions'], 5)
        self.assertAlmostEqual(status['last_prediction_time'], 2.1, places=1)
        
        # Test slowing trend
        self.tracker.reset_metrics()
        for t in [1.0, 1.1, 2.8, 2.9, 3.0]:  # Gets slower
            self.tracker.record_prediction(t)
        
        status = self.tracker.get_realtime_status()
        self.assertEqual(status['trend'], 'slowing')
        
        # Test improving trend
        self.tracker.reset_metrics()
        for t in [3.0, 2.9, 1.1, 1.0, 0.9]:  # Gets faster
            self.tracker.record_prediction(t)
        
        status = self.tracker.get_realtime_status()
        self.assertEqual(status['trend'], 'improving')
    
    def test_performance_score_calculation(self):
        """Test performance score calculation."""
        # Perfect score initially
        score = self.tracker._calculate_performance_score()
        self.assertEqual(score, 100.0)
        
        # Good performance (fast execution, all success)
        for _ in range(5):
            self.tracker.record_prediction(3.0, success=True)
        
        score = self.tracker._calculate_performance_score()
        self.assertEqual(score, 100.0)  # No penalty for 3s execution (<=5s threshold)
        
        # Poor performance (slow execution)
        self.tracker.reset_metrics()
        for _ in range(5):
            self.tracker.record_prediction(20.0, success=True)
        
        score = self.tracker._calculate_performance_score()
        self.assertEqual(score, 50.0)  # 100 - 50 for >15s execution
        
        # With failures
        self.tracker.reset_metrics()
        self.tracker.record_prediction(3.0, success=True)
        self.tracker.record_prediction(3.0, success=False)
        
        score = self.tracker._calculate_performance_score()
        expected = 100.0 * 0.5  # No execution penalty for 3s, just success rate penalty
        self.assertEqual(score, expected)
    
    def test_comprehensive_performance_summary(self):
        """Test comprehensive performance summary."""
        # Record various metrics
        self.tracker.record_prediction(2.5, success=True)
        self.tracker.record_prediction(3.0, success=True)
        self.tracker.record_api_call('test_api', 1.0, success=True)
        
        timer_id = self.tracker.start_timer('test_component')
        time.sleep(0.05)
        self.tracker.stop_timer(timer_id)
        
        summary = self.tracker.get_performance_summary()
        
        # Check all sections exist
        self.assertIn('session_info', summary)
        self.assertIn('execution_metrics', summary)
        self.assertIn('api_metrics', summary)
        self.assertIn('component_metrics', summary)
        self.assertIn('performance_alerts', summary)
        
        # Verify data
        self.assertEqual(summary['session_info']['total_predictions'], 2)
        self.assertEqual(summary['execution_metrics']['total_predictions'], 2)
        self.assertIn('test_api', summary['api_metrics'])
        self.assertIn('test_component', summary['component_metrics'])
    
    def test_reset_metrics(self):
        """Test metrics reset functionality."""
        # Generate some data
        self.tracker.record_prediction(1.0)
        self.tracker.record_api_call('test_api', 1.0)
        timer_id = self.tracker.start_timer('test')
        self.tracker.stop_timer(timer_id)
        
        # Verify data exists
        self.assertGreater(len(self.tracker.execution_times), 0)
        self.assertGreater(len(self.tracker.api_calls), 0)
        self.assertGreater(len(self.tracker.component_times), 0)
        
        # Reset
        old_start = self.tracker.session_start
        self.tracker.reset_metrics()
        
        # Verify reset
        self.assertEqual(len(self.tracker.execution_times), 0)
        self.assertEqual(len(self.tracker.api_calls), 0)
        self.assertEqual(len(self.tracker.component_times), 0)
        self.assertEqual(self.tracker.prediction_count, 0)
        self.assertEqual(self.tracker.success_count, 0)
        self.assertEqual(self.tracker.error_count, 0)
        self.assertGreater(self.tracker.session_start, old_start)
    
    def test_thread_safety(self):
        """Test thread safety of tracker operations."""
        def record_predictions():
            for i in range(50):
                self.tracker.record_prediction(1.0 + i * 0.1)
        
        def record_api_calls():
            for i in range(50):
                self.tracker.record_api_call('test_api', 0.5 + i * 0.1)
        
        # Run concurrent operations
        thread1 = threading.Thread(target=record_predictions)
        thread2 = threading.Thread(target=record_api_calls)
        
        thread1.start()
        thread2.start()
        
        thread1.join()
        thread2.join()
        
        # Verify all data was recorded
        self.assertEqual(len(self.tracker.execution_times), 50)
        self.assertEqual(self.tracker.api_calls['test_api'], 50)
        self.assertEqual(len(self.tracker.api_response_times['test_api']), 50)
    
    def test_max_history_limit(self):
        """Test that history respects max limit."""
        tracker = PerformanceTracker(max_history=5)
        
        # Add more than max history
        for i in range(10):
            tracker.record_prediction(float(i))
            tracker.record_api_call('test_api', float(i))
        
        # Should only keep last 5
        self.assertEqual(len(tracker.execution_times), 5)
        self.assertEqual(len(tracker.api_response_times['test_api']), 5)
        
        # Check correct values are kept (last 5)
        self.assertEqual(list(tracker.execution_times), [5.0, 6.0, 7.0, 8.0, 9.0])
    
    def test_slow_operation_logging(self):
        """Test slow operation logging."""
        with patch.object(self.tracker.logger, 'warning') as mock_warning:
            # Start and stop timer with long operation
            timer_id = self.tracker.start_timer('slow_operation')
            
            # Mock a slow operation by manipulating start time
            self.tracker.active_timers[timer_id]['start_time'] = time.time() - 6.0
            
            duration = self.tracker.stop_timer(timer_id)
            
            # Should log warning for slow operation
            mock_warning.assert_called_once()
            self.assertIn('Slow operation', mock_warning.call_args[0][0])
    
    def test_edge_cases(self):
        """Test various edge cases."""
        # Test with zero division scenarios
        summary = self.tracker.get_performance_summary()
        self.assertEqual(summary['session_info']['success_rate'], 0.0)
        
        # Test percentile with single value
        self.tracker.record_prediction(5.0)
        metrics = self.tracker._get_execution_metrics()
        self.assertEqual(metrics['p95_execution_time'], 5.0)
        
        # Test API metrics with no response times
        self.tracker.api_calls['empty_api'] = 5
        self.tracker.api_failures['empty_api'] = 1
        api_metrics = self.tracker._get_api_metrics()
        self.assertEqual(api_metrics['empty_api']['avg_response_time'], 0.0)
    
    def test_global_tracker_instance(self):
        """Test global tracker instance."""
        from utils.performance_tracker import performance_tracker
        
        self.assertIsInstance(performance_tracker, PerformanceTracker)
        self.assertEqual(performance_tracker.max_history, 1000)
        
        # Test it works
        performance_tracker.record_prediction(1.0)
        self.assertGreater(performance_tracker.prediction_count, 0)


if __name__ == '__main__':
    unittest.main()