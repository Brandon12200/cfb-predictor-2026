"""
Unit tests for error handler module.
Tests graceful error handling and recovery mechanisms.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
import time

from utils.error_handler import (
    ErrorHandler, error_handler, ErrorSeverity, ErrorCategory
)


class TestErrorHandler(unittest.TestCase):
    """Test the error handler functionality."""
    
    def setUp(self):
        """Set up test environment."""
        self.handler = ErrorHandler()
        # Clear any existing state
        self.handler.reset_error_tracking()
    
    def test_initialization(self):
        """Test error handler initialization."""
        handler = ErrorHandler()
        
        self.assertEqual(len(handler.error_counts), 0)
        self.assertEqual(len(handler.error_history), 0)
        self.assertEqual(len(handler.circuit_breakers), 0)
        self.assertIsNotNone(handler.fallback_values)
        
        # Check fallback values are configured
        self.assertIn('vegas_spread', handler.fallback_values)
        self.assertIn('team_data', handler.fallback_values)
        self.assertIn('factor_value', handler.fallback_values)
    
    def test_handle_error_basic(self):
        """Test basic error handling."""
        error = ValueError("Test error")
        context = {
            'component': 'test_component',
            'operation': 'test_operation'
        }
        
        response = self.handler.handle_error(
            error, context, 
            ErrorCategory.DATA_ERROR,
            ErrorSeverity.MEDIUM
        )
        
        self.assertFalse(response['success'])
        self.assertEqual(response['error'], "Test error")
        self.assertEqual(response['error_category'], 'data_error')
        self.assertEqual(response['error_severity'], 'medium')
        self.assertIn('timestamp', response)
        
        # Check error was tracked
        self.assertEqual(len(self.handler.error_history), 1)
        self.assertIn('data_error:ValueError', self.handler.error_counts)
    
    def test_handle_error_with_fallback(self):
        """Test error handling with fallback value."""
        error = Exception("API failure")
        context = {'component': 'odds_client'}
        fallback = -3.5
        
        response = self.handler.handle_error(
            error, context,
            ErrorCategory.API_ERROR,
            ErrorSeverity.HIGH,
            fallback_value=fallback
        )
        
        self.assertTrue(response['fallback_used'])
        self.assertEqual(response['data'], -3.5)
    
    def test_automatic_fallback_values(self):
        """Test automatic fallback value selection."""
        # Test different components
        test_cases = [
            ('odds_client', None),  # Should return None
            ('espn_client', dict),  # Should return team data dict
            ('factor_calculator', 0.0),  # Should return 0.0
            ('confidence_calculator', 0.15),  # Should return minimum confidence
        ]
        
        for component, expected in test_cases:
            error = Exception("Test error")
            context = {'component': component}
            
            response = self.handler.handle_error(
                error, context,
                ErrorCategory.SYSTEM_ERROR,
                ErrorSeverity.LOW
            )
            
            if expected is None:
                self.assertIsNone(response.get('data'))
            elif expected == dict:
                self.assertIsInstance(response['data'], dict)
                self.assertIn('info', response['data'])
            else:
                self.assertEqual(response['data'], expected)
    
    def test_error_tracking(self):
        """Test error tracking functionality."""
        # Generate multiple errors
        for i in range(5):
            error = ValueError(f"Error {i}")
            context = {'test': i}
            self.handler.handle_error(error, context)
        
        # Check tracking
        self.assertEqual(len(self.handler.error_history), 5)
        self.assertEqual(self.handler.error_counts['system_error:ValueError'], 5)
        
        # Test history limit (should keep only last 100)
        for i in range(100):
            self.handler.handle_error(Exception("Bulk error"), {})
        
        self.assertEqual(len(self.handler.error_history), 100)
    
    def test_safe_execute_success(self):
        """Test safe execute with successful function."""
        def test_func(x, y):
            return x + y
        
        result = self.handler.safe_execute(test_func, 2, 3)
        self.assertEqual(result, 5)
        
        # No errors should be tracked
        self.assertEqual(len(self.handler.error_history), 0)
    
    def test_safe_execute_with_error(self):
        """Test safe execute with error and fallback."""
        def failing_func():
            raise ValueError("Function failed")
        
        result = self.handler.safe_execute(
            failing_func,
            category=ErrorCategory.CALCULATION_ERROR,
            severity=ErrorSeverity.LOW,
            fallback_value=42
        )
        
        self.assertEqual(result, 42)
        self.assertEqual(len(self.handler.error_history), 1)
    
    def test_safe_execute_no_fallback(self):
        """Test safe execute with error and no fallback."""
        def failing_func():
            raise ValueError("Function failed")
        
        with self.assertRaises(ValueError):
            self.handler.safe_execute(failing_func)
    
    def test_circuit_breaker_closed_state(self):
        """Test circuit breaker in closed state."""
        @self.handler.circuit_breaker('test_service', failure_threshold=3)
        def test_service():
            return "success"
        
        # Should work normally
        result = test_service()
        self.assertEqual(result, "success")
        
        # Check breaker state
        breaker = self.handler.circuit_breakers.get('test_service', {})
        self.assertEqual(breaker.get('state'), 'closed')
    
    def test_circuit_breaker_opening(self):
        """Test circuit breaker opening after failures."""
        call_count = 0
        
        @self.handler.circuit_breaker('failing_service', failure_threshold=3)
        def failing_service():
            nonlocal call_count
            call_count += 1
            raise Exception("Service failure")
        
        # First 2 failures should pass through
        for i in range(2):
            with self.assertRaises(Exception):
                failing_service()
        
        self.assertEqual(call_count, 2)
        
        # Third failure should open the circuit
        with self.assertRaises(Exception):
            failing_service()
        
        self.assertEqual(call_count, 3)
        
        # Circuit should be open now
        breaker = self.handler.circuit_breakers['failing_service']
        self.assertEqual(breaker['state'], 'open')
        
        # Further calls should fail immediately
        with self.assertRaisesRegex(Exception, "Circuit breaker open"):
            failing_service()
        
        # Call count should not increase
        self.assertEqual(call_count, 3)
    
    def test_circuit_breaker_reset(self):
        """Test circuit breaker reset after timeout."""
        @self.handler.circuit_breaker('reset_service', failure_threshold=2, reset_timeout=1)
        def reset_service(should_fail=True):
            if should_fail:
                raise Exception("Service failure")
            return "success"
        
        # Open the circuit
        for i in range(2):
            with self.assertRaises(Exception):
                reset_service()
        
        # Circuit should be open
        self.assertEqual(self.handler.circuit_breakers['reset_service']['state'], 'open')
        
        # Manually set last_failure to past time to simulate timeout
        from datetime import datetime, timedelta
        self.handler.circuit_breakers['reset_service']['last_failure'] = datetime.now() - timedelta(seconds=2)
        
        # Should reset and succeed
        result = reset_service(should_fail=False)
        self.assertEqual(result, "success")
        
        # Circuit should be closed again
        self.assertEqual(self.handler.circuit_breakers['reset_service']['state'], 'closed')
    
    def test_get_error_summary(self):
        """Test error summary generation."""
        # Generate various errors
        self.handler.handle_error(ValueError("Data error"), {'component': 'test'}, 
                                ErrorCategory.DATA_ERROR)
        self.handler.handle_error(Exception("API error"), {'component': 'api'}, 
                                ErrorCategory.API_ERROR)
        self.handler.handle_error(ValueError("Another data error"), {'component': 'test'}, 
                                ErrorCategory.DATA_ERROR)
        
        summary = self.handler.get_error_summary()
        
        self.assertEqual(summary['total_errors'], 3)
        self.assertIn('data_error:ValueError', summary['error_counts_by_type'])
        self.assertEqual(len(summary['recent_errors']), 3)
        self.assertIsInstance(summary['most_common_errors'], list)
        self.assertIn('trend', summary['error_trends'])
    
    def test_error_trends_analysis(self):
        """Test error trend analysis."""
        # Not enough data
        trends = self.handler._analyze_error_trends()
        self.assertEqual(trends['trend'], 'insufficient_data')
        
        # Generate errors for trend analysis
        for i in range(25):
            self.handler.handle_error(Exception(f"Error {i}"), {})
        
        trends = self.handler._analyze_error_trends()
        self.assertIn('trend', trends)
        self.assertIn(trends['trend'], ['new_system', 'stable', 'increasing', 'decreasing'])
    
    def test_create_safe_prediction_context(self):
        """Test safe prediction context creation."""
        context = self.handler.create_safe_prediction_context()
        
        self.assertIsNone(context['vegas_spread'])
        self.assertEqual(context['data_quality'], 0.0)
        self.assertIsInstance(context['data_sources'], list)
        self.assertIn('home_team_data', context)
        self.assertIn('away_team_data', context)
        self.assertIn('coaching_comparison', context)
        
        # Check nested structure
        self.assertIn('info', context['home_team_data'])
        self.assertIn('derived_metrics', context['home_team_data'])
    
    def test_recovery_mode_prediction(self):
        """Test recovery mode prediction generation."""
        result = self.handler.recovery_mode_prediction('Georgia', 'Alabama')
        
        self.assertEqual(result['prediction_type'], 'RECOVERY_MODE')
        self.assertFalse(result['has_edge'])
        self.assertEqual(result['confidence_score'], 0.0)
        self.assertIn('recovery mode', result['recommendation'])
        self.assertIn('error_details', result)
    
    def test_recovery_mode_with_normalization_failure(self):
        """Test recovery mode when normalization fails."""
        with patch('normalizer.normalizer') as mock_normalizer:
            mock_normalizer.normalize.side_effect = Exception("Normalization failed")
            
            result = self.handler.recovery_mode_prediction('Invalid Team', 'Another Invalid')
        
        self.assertEqual(result['prediction_type'], 'CRITICAL_ERROR')
        self.assertIn('Critical system failure', result['error'])
        self.assertEqual(result['home_team'], 'Invalid Team')  # Original names preserved
    
    def test_auto_recovery_check_normal(self):
        """Test auto recovery check with no recent errors."""
        recovery = self.handler.auto_recovery_check()
        
        self.assertTrue(recovery['can_recover'])
        self.assertEqual(recovery['recovery_action'], 'none_needed')
        self.assertIn('normally', recovery['message'])
    
    def test_auto_recovery_check_api_errors(self):
        """Test auto recovery check with API errors."""
        # Generate recent API errors
        for i in range(3):
            error_info = {
                'timestamp': datetime.now().isoformat(),
                'category': 'api_error',
                'error_message': 'API timeout'
            }
            self.handler.error_history.append(error_info)
        
        recovery = self.handler.auto_recovery_check()
        
        self.assertTrue(recovery['can_recover'])
        self.assertEqual(recovery['recovery_action'], 'wait_and_retry')
        self.assertEqual(recovery['wait_seconds'], 60)
    
    def test_auto_recovery_check_too_many_errors(self):
        """Test auto recovery check with too many errors."""
        # Generate many recent errors
        for i in range(10):
            error_info = {
                'timestamp': datetime.now().isoformat(),
                'category': 'system_error',
                'error_message': 'System failure'
            }
            self.handler.error_history.append(error_info)
        
        recovery = self.handler.auto_recovery_check()
        
        self.assertFalse(recovery['can_recover'])
        self.assertEqual(recovery['recovery_action'], 'manual_intervention')
    
    def test_validate_prediction_inputs(self):
        """Test prediction input validation."""
        # Valid inputs
        result = self.handler.validate_prediction_inputs('Georgia', 'Alabama', week=8)
        self.assertTrue(result['valid'])
        self.assertEqual(len(result['errors']), 0)
        
        # Invalid home team
        result = self.handler.validate_prediction_inputs('', 'Alabama')
        self.assertFalse(result['valid'])
        self.assertIn("Invalid home team name", result['errors'])
        
        # Same teams
        result = self.handler.validate_prediction_inputs('Georgia', 'Georgia')
        self.assertFalse(result['valid'])
        self.assertIn("cannot be the same", result['errors'][0])
        
        # Invalid week
        result = self.handler.validate_prediction_inputs('Georgia', 'Alabama', week=20)
        self.assertTrue(result['valid'])  # Still valid, just warning
        self.assertTrue(any("Invalid week number" in warning for warning in result['warnings']))
    
    def test_error_severity_logging(self):
        """Test different error severity levels are logged correctly."""
        with patch.object(self.handler.logger, 'critical') as mock_critical, \
             patch.object(self.handler.logger, 'error') as mock_error, \
             patch.object(self.handler.logger, 'warning') as mock_warning, \
             patch.object(self.handler.logger, 'info') as mock_info:
            
            # Critical error
            self.handler.handle_error(
                Exception("Critical"), {}, 
                ErrorCategory.SYSTEM_ERROR, ErrorSeverity.CRITICAL
            )
            mock_critical.assert_called_once()
            
            # High severity
            self.handler.handle_error(
                Exception("High"), {}, 
                ErrorCategory.API_ERROR, ErrorSeverity.HIGH
            )
            mock_error.assert_called_once()
            
            # Medium severity
            self.handler.handle_error(
                Exception("Medium"), {}, 
                ErrorCategory.DATA_ERROR, ErrorSeverity.MEDIUM
            )
            mock_warning.assert_called_once()
            
            # Low severity
            self.handler.handle_error(
                Exception("Low"), {}, 
                ErrorCategory.VALIDATION_ERROR, ErrorSeverity.LOW
            )
            mock_info.assert_called_once()
    
    def test_reset_error_tracking(self):
        """Test error tracking reset."""
        # Generate some errors
        for i in range(5):
            self.handler.handle_error(Exception(f"Error {i}"), {})
        
        # Set up circuit breaker
        self.handler.circuit_breakers['test'] = {'state': 'open'}
        
        # Reset
        self.handler.reset_error_tracking()
        
        self.assertEqual(len(self.handler.error_counts), 0)
        self.assertEqual(len(self.handler.error_history), 0)
        self.assertEqual(len(self.handler.circuit_breakers), 0)
    
    def test_most_common_errors(self):
        """Test most common errors identification."""
        # Generate errors with different frequencies
        for i in range(5):
            self.handler.handle_error(ValueError("Common"), {})
        for i in range(3):
            self.handler.handle_error(TypeError("Less common"), {})
        self.handler.handle_error(RuntimeError("Rare"), {})
        
        most_common = self.handler._get_most_common_errors()
        
        self.assertEqual(len(most_common), 3)
        self.assertEqual(most_common[0]['error_type'], 'system_error:ValueError')
        self.assertEqual(most_common[0]['count'], 5)
    
    def test_global_error_handler_instance(self):
        """Test global error handler instance."""
        from utils.error_handler import error_handler
        
        self.assertIsInstance(error_handler, ErrorHandler)
        self.assertIsNotNone(error_handler.fallback_values)


if __name__ == '__main__':
    unittest.main()