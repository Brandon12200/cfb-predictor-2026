"""
Error handler utility for College Football Market Edge Platform.
Provides graceful error handling and recovery mechanisms.
"""

import logging
import traceback
from typing import Dict, Any, Optional, Callable, List
from enum import Enum
from datetime import datetime
import functools


class ErrorSeverity(Enum):
    """Error severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ErrorCategory(Enum):
    """Error category types."""
    API_ERROR = "api_error"
    DATA_ERROR = "data_error"
    CALCULATION_ERROR = "calculation_error"
    VALIDATION_ERROR = "validation_error"
    SYSTEM_ERROR = "system_error"
    NETWORK_ERROR = "network_error"
    CONFIGURATION_ERROR = "configuration_error"


class ErrorHandler:
    """
    Centralized error handling for the prediction system.
    
    Features:
    - Graceful error recovery
    - Error categorization and severity
    - Fallback value generation
    - Error tracking and reporting
    - Circuit breaker patterns
    """
    
    def __init__(self):
        """Initialize error handler."""
        self.error_counts = {}
        self.error_history = []
        self.circuit_breakers = {}
        self.fallback_values = {}
        
        # Logging
        self.logger = logging.getLogger(__name__)
        
        # Configure fallback values
        self._configure_fallbacks()
        
        self.logger.debug("Error handler initialized")
    
    def _configure_fallbacks(self):
        """Configure fallback values for different data types."""
        self.fallback_values = {
            'vegas_spread': None,
            'team_data': {
                'info': {'conference': {'name': 'Unknown'}},
                'derived_metrics': {
                    'current_record': {'wins': 0, 'losses': 0, 'win_percentage': 0.5},
                    'venue_performance': {
                        'home_record': {'win_percentage': 0.5},
                        'away_record': {'win_percentage': 0.5}
                    }
                }
            },
            'coaching_data': {
                'head_coach_experience': 5,
                'tenure_years': 3,
                'head_to_head_record': {'total_games': 0}
            },
            'factor_value': 0.0,
            'confidence_score': 0.15,  # Minimum confidence
            'data_quality': 0.0
        }
    
    def handle_error(self, error: Exception, context: Dict[str, Any], 
                    category: ErrorCategory = ErrorCategory.SYSTEM_ERROR,
                    severity: ErrorSeverity = ErrorSeverity.MEDIUM,
                    fallback_value: Any = None) -> Dict[str, Any]:
        """
        Handle an error with appropriate response.
        
        Args:
            error: The exception that occurred
            context: Context information about the error
            category: Error category
            severity: Error severity level
            fallback_value: Optional fallback value to return
            
        Returns:
            Error response with fallback data
        """
        error_info = self._create_error_info(error, context, category, severity)
        
        # Log the error
        self._log_error(error_info)
        
        # Track the error
        self._track_error(error_info)
        
        # Generate response
        return self._generate_error_response(error_info, fallback_value)
    
    def _create_error_info(self, error: Exception, context: Dict[str, Any],
                          category: ErrorCategory, severity: ErrorSeverity) -> Dict[str, Any]:
        """Create comprehensive error information."""
        return {
            'timestamp': datetime.now().isoformat(),
            'error_type': type(error).__name__,
            'error_message': str(error),
            'category': category.value,
            'severity': severity.value,
            'context': context,
            'traceback': traceback.format_exc(),
            'component': context.get('component', 'unknown'),
            'operation': context.get('operation', 'unknown')
        }
    
    def _log_error(self, error_info: Dict[str, Any]):
        """Log error with appropriate level."""
        severity = error_info['severity']
        message = f"{error_info['category']}: {error_info['error_message']}"
        
        if severity == ErrorSeverity.CRITICAL.value:
            self.logger.critical(message, extra=error_info)
        elif severity == ErrorSeverity.HIGH.value:
            self.logger.error(message, extra=error_info)
        elif severity == ErrorSeverity.MEDIUM.value:
            self.logger.warning(message, extra=error_info)
        else:
            self.logger.info(message, extra=error_info)
    
    def _track_error(self, error_info: Dict[str, Any]):
        """Track error for analysis."""
        error_key = f"{error_info['category']}:{error_info['error_type']}"
        
        if error_key not in self.error_counts:
            self.error_counts[error_key] = 0
        
        self.error_counts[error_key] += 1
        self.error_history.append(error_info)
        
        # Keep only last 100 errors
        if len(self.error_history) > 100:
            self.error_history.pop(0)
    
    def _generate_error_response(self, error_info: Dict[str, Any], 
                               fallback_value: Any = None) -> Dict[str, Any]:
        """Generate appropriate error response."""
        response = {
            'success': False,
            'error': error_info['error_message'],
            'error_category': error_info['category'],
            'error_severity': error_info['severity'],
            'timestamp': error_info['timestamp'],
            'fallback_used': fallback_value is not None
        }
        
        if fallback_value is not None:
            response['data'] = fallback_value
        else:
            # Try to provide appropriate fallback
            component = error_info.get('component', '')
            operation = error_info.get('operation', '')
            
            fallback = self._get_fallback_value(component, operation)
            if fallback is not None:
                response['data'] = fallback
                response['fallback_used'] = True
        
        return response
    
    def _get_fallback_value(self, component: str, operation: str) -> Any:
        """Get appropriate fallback value based on component and operation."""
        # Map components to fallback values
        fallback_map = {
            'odds_client': self.fallback_values['vegas_spread'],
            'espn_client': self.fallback_values['team_data'],
            'factor_calculator': self.fallback_values['factor_value'],
            'confidence_calculator': self.fallback_values['confidence_score'],
            'data_manager': self.fallback_values['team_data']
        }
        
        return fallback_map.get(component)
    
    def safe_execute(self, func: Callable, *args, 
                    category: ErrorCategory = ErrorCategory.SYSTEM_ERROR,
                    severity: ErrorSeverity = ErrorSeverity.MEDIUM,
                    fallback_value: Any = None,
                    context: Optional[Dict[str, Any]] = None,
                    **kwargs) -> Any:
        """
        Safely execute a function with error handling.
        
        Args:
            func: Function to execute
            *args: Function arguments
            category: Error category
            severity: Error severity
            fallback_value: Fallback value on error
            context: Additional context
            **kwargs: Function keyword arguments
            
        Returns:
            Function result or fallback value
        """
        if context is None:
            context = {'function': func.__name__}
        
        try:
            return func(*args, **kwargs)
        except Exception as e:
            error_response = self.handle_error(e, context, category, severity, fallback_value)
            
            if error_response['fallback_used']:
                return error_response['data']
            else:
                raise e
    
    def circuit_breaker(self, service_name: str, failure_threshold: int = 5,
                       reset_timeout: int = 60):
        """
        Implement circuit breaker pattern for services.
        
        Args:
            service_name: Name of the service
            failure_threshold: Number of failures before opening circuit
            reset_timeout: Seconds before attempting to reset circuit
        """
        def decorator(func):
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                breaker = self.circuit_breakers.get(service_name, {
                    'failures': 0,
                    'last_failure': None,
                    'state': 'closed'  # closed, open, half-open
                })
                
                # Check circuit state
                if breaker['state'] == 'open':
                    if (datetime.now() - breaker['last_failure']).seconds > reset_timeout:
                        breaker['state'] = 'half-open'
                        self.logger.info(f"Circuit breaker for {service_name} half-open")
                    else:
                        raise Exception(f"Circuit breaker open for {service_name}")
                
                try:
                    result = func(*args, **kwargs)
                    
                    # Reset on success
                    if breaker['state'] == 'half-open':
                        breaker['failures'] = 0
                        breaker['state'] = 'closed'
                        self.logger.info(f"Circuit breaker for {service_name} reset to closed")
                    
                    self.circuit_breakers[service_name] = breaker
                    return result
                    
                except Exception as e:
                    breaker['failures'] += 1
                    breaker['last_failure'] = datetime.now()
                    
                    if breaker['failures'] >= failure_threshold:
                        breaker['state'] = 'open'
                        self.logger.warning(f"Circuit breaker for {service_name} opened")
                    
                    self.circuit_breakers[service_name] = breaker
                    raise e
            
            return wrapper
        return decorator
    
    def get_error_summary(self) -> Dict[str, Any]:
        """Get summary of errors encountered."""
        return {
            'total_errors': len(self.error_history),
            'error_counts_by_type': self.error_counts.copy(),
            'recent_errors': self.error_history[-10:],  # Last 10 errors
            'circuit_breaker_status': self.circuit_breakers.copy(),
            'most_common_errors': self._get_most_common_errors(),
            'error_trends': self._analyze_error_trends()
        }
    
    def _get_most_common_errors(self) -> List[Dict[str, Any]]:
        """Get most common error types."""
        sorted_errors = sorted(self.error_counts.items(), key=lambda x: x[1], reverse=True)
        
        return [
            {'error_type': error_type, 'count': count}
            for error_type, count in sorted_errors[:5]
        ]
    
    def _analyze_error_trends(self) -> Dict[str, Any]:
        """Analyze error trends over time."""
        if len(self.error_history) < 10:
            return {'trend': 'insufficient_data'}
        
        recent_errors = self.error_history[-10:]
        older_errors = self.error_history[-20:-10] if len(self.error_history) >= 20 else []
        
        recent_count = len(recent_errors)
        older_count = len(older_errors)
        
        if older_count == 0:
            trend = 'new_system'
        elif recent_count > older_count * 1.5:
            trend = 'increasing'
        elif recent_count < older_count * 0.5:
            trend = 'decreasing'
        else:
            trend = 'stable'
        
        return {
            'trend': trend,
            'recent_error_rate': recent_count,
            'comparison_error_rate': older_count
        }
    
    def create_safe_prediction_context(self) -> Dict[str, Any]:
        """Create a safe context for predictions with fallback values."""
        return {
            'vegas_spread': None,
            'data_quality': 0.0,
            'data_sources': [],
            'home_team_data': self.fallback_values['team_data'].copy(),
            'away_team_data': self.fallback_values['team_data'].copy(),
            'coaching_comparison': {
                'home_coaching': self.fallback_values['coaching_data'].copy(),
                'away_coaching': self.fallback_values['coaching_data'].copy(),
                'head_to_head_record': {'total_games': 0}
            }
        }
    
    def recovery_mode_prediction(self, home_team: str, away_team: str) -> Dict[str, Any]:
        """
        Generate a minimal prediction in recovery mode when normal prediction fails.
        
        Args:
            home_team: Home team name
            away_team: Away team name
            
        Returns:
            dict: Minimal prediction result
        """
        try:
            from utils.normalizer import normalizer
            
            # Try to normalize team names
            home_normalized = normalizer.normalize(home_team)
            away_normalized = normalizer.normalize(away_team)
            
            if not home_normalized or not away_normalized:
                raise ValueError("Could not normalize team names")
            
            # Create minimal prediction
            return {
                'home_team': home_normalized,
                'away_team': away_normalized,
                'timestamp': datetime.now().isoformat(),
                'prediction_type': 'RECOVERY_MODE',
                'vegas_spread': None,
                'contrarian_spread': None,
                'edge_size': 0.0,
                'has_edge': False,
                'confidence_score': 0.0,
                'recommendation': 'System in recovery mode - no prediction available',
                'data_quality': 0.0,
                'error_details': 'Prediction generated in recovery mode due to system issues'
            }
            
        except Exception as e:
            # Ultimate fallback
            return {
                'home_team': home_team,
                'away_team': away_team,
                'timestamp': datetime.now().isoformat(),
                'prediction_type': 'CRITICAL_ERROR',
                'error': f'Critical system failure: {str(e)}',
                'has_edge': False,
                'confidence_score': 0.0,
                'recommendation': 'System unavailable - please try again later'
            }
    
    def auto_recovery_check(self) -> Dict[str, Any]:
        """
        Check if system can recover from recent errors automatically.
        
        Returns:
            dict: Recovery assessment and recommendations
        """
        from datetime import timedelta
        recent_errors = [
            error for error in self.error_history
            if datetime.fromisoformat(error['timestamp']) > 
               datetime.now() - timedelta(minutes=10)
        ]
        
        if not recent_errors:
            return {
                'can_recover': True,
                'recovery_action': 'none_needed',
                'message': 'System operating normally'
            }
        
        # Analyze error patterns
        error_types = [error['category'] for error in recent_errors]
        most_common_error = max(set(error_types), key=error_types.count) if error_types else None
        
        # Recovery strategies
        if most_common_error == 'api_error':
            return {
                'can_recover': True,
                'recovery_action': 'wait_and_retry',
                'message': 'API errors detected - recommend waiting 60 seconds before retry',
                'wait_seconds': 60
            }
        elif most_common_error == 'data_error':
            return {
                'can_recover': True,
                'recovery_action': 'use_fallback_data',
                'message': 'Data issues detected - using fallback values'
            }
        elif len(recent_errors) > 5:
            return {
                'can_recover': False,
                'recovery_action': 'manual_intervention',
                'message': 'Too many recent errors - manual intervention required'
            }
        else:
            return {
                'can_recover': True,
                'recovery_action': 'continue_with_caution',
                'message': 'Some errors detected but system should continue'
            }
    
    def reset_error_tracking(self):
        """Reset error tracking for fresh start."""
        self.error_counts.clear()
        self.error_history.clear()
        self.circuit_breakers.clear()
        self.logger.info("Error tracking reset")
    
    def validate_prediction_inputs(self, home_team: str, away_team: str, 
                                 week: Optional[int] = None) -> Dict[str, Any]:
        """Validate prediction inputs and return validation result."""
        validation_result = {
            'valid': True,
            'errors': [],
            'warnings': []
        }
        
        # Team validation
        if not home_team or not isinstance(home_team, str):
            validation_result['valid'] = False
            validation_result['errors'].append("Invalid home team name")
        
        if not away_team or not isinstance(away_team, str):
            validation_result['valid'] = False
            validation_result['errors'].append("Invalid away team name")
        
        if home_team == away_team:
            validation_result['valid'] = False
            validation_result['errors'].append("Home and away teams cannot be the same")
        
        # Week validation
        if week is not None:
            if not isinstance(week, int) or week < 1 or week > 17:
                validation_result['warnings'].append("Invalid week number, using current week")
        
        return validation_result


# Global error handler instance
error_handler = ErrorHandler()