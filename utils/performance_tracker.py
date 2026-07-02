"""
Performance tracker for College Football Market Edge Platform.
Monitors execution times, API calls, and system performance.
"""

import time
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from collections import defaultdict, deque
import threading
import statistics


class PerformanceTracker:
    """
    Tracks performance metrics for the prediction system.
    
    Features:
    - Execution time monitoring
    - API call tracking
    - Memory usage estimation
    - Performance history
    - Real-time metrics
    """
    
    def __init__(self, max_history: int = 1000):
        """Initialize performance tracker."""
        self.max_history = max_history
        
        # Execution time tracking
        self.execution_times = deque(maxlen=max_history)
        self.component_times = defaultdict(lambda: deque(maxlen=max_history))
        
        # API tracking
        self.api_calls = defaultdict(int)
        self.api_response_times = defaultdict(lambda: deque(maxlen=max_history))
        self.api_failures = defaultdict(int)
        
        # System metrics
        self.prediction_count = 0
        self.success_count = 0
        self.error_count = 0
        
        # Current session tracking
        self.session_start = datetime.now()
        self.active_timers = {}
        
        # Thread safety
        self.lock = threading.Lock()
        
        # Logging
        self.logger = logging.getLogger(__name__)
        
        self.logger.debug("Performance tracker initialized")
    
    def start_timer(self, operation: str) -> str:
        """Start timing an operation."""
        timer_id = f"{operation}_{int(time.time() * 1000000)}"
        
        with self.lock:
            self.active_timers[timer_id] = {
                'operation': operation,
                'start_time': time.time(),
                'timestamp': datetime.now()
            }
        
        return timer_id
    
    def stop_timer(self, timer_id: str) -> float:
        """Stop timing and record the duration."""
        if timer_id not in self.active_timers:
            self.logger.warning(f"Timer {timer_id} not found")
            return 0.0
        
        end_time = time.time()
        
        with self.lock:
            timer_info = self.active_timers.pop(timer_id)
            duration = end_time - timer_info['start_time']
            operation = timer_info['operation']
            
            # Record the timing
            self.component_times[operation].append(duration)
            
            # Log slow operations
            if duration > 5.0:
                self.logger.warning(f"Slow operation: {operation} took {duration:.2f}s")
            
        return duration
    
    def record_prediction(self, execution_time: float, success: bool = True):
        """Record a prediction execution."""
        with self.lock:
            self.execution_times.append(execution_time)
            self.prediction_count += 1
            
            if success:
                self.success_count += 1
            else:
                self.error_count += 1
    
    def record_api_call(self, api_name: str, response_time: float, success: bool = True):
        """Record an API call."""
        with self.lock:
            self.api_calls[api_name] += 1
            self.api_response_times[api_name].append(response_time)
            
            if not success:
                self.api_failures[api_name] += 1
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get comprehensive performance summary."""
        with self.lock:
            summary = {
                'session_info': self._get_session_info(),
                'execution_metrics': self._get_execution_metrics(),
                'api_metrics': self._get_api_metrics(),
                'component_metrics': self._get_component_metrics(),
                'performance_alerts': self._get_performance_alerts()
            }
        
        return summary
    
    def _get_session_info(self) -> Dict[str, Any]:
        """Get session information."""
        session_duration = datetime.now() - self.session_start
        
        return {
            'session_start': self.session_start.isoformat(),
            'session_duration_seconds': session_duration.total_seconds(),
            'session_duration_formatted': str(session_duration),
            'total_predictions': self.prediction_count,
            'success_rate': self.success_count / max(self.prediction_count, 1),
            'error_rate': self.error_count / max(self.prediction_count, 1),
            'predictions_per_minute': self.prediction_count / max(session_duration.total_seconds() / 60, 1)
        }
    
    def _get_execution_metrics(self) -> Dict[str, Any]:
        """Get execution time metrics."""
        if not self.execution_times:
            return {
                'avg_execution_time': 0.0,
                'min_execution_time': 0.0,
                'max_execution_time': 0.0,
                'median_execution_time': 0.0,
                'p95_execution_time': 0.0,
                'total_predictions': 0,
                'under_15s_rate': 1.0
            }
        
        times = list(self.execution_times)
        
        return {
            'avg_execution_time': statistics.mean(times),
            'min_execution_time': min(times),
            'max_execution_time': max(times),
            'median_execution_time': statistics.median(times),
            'p95_execution_time': self._percentile(times, 95),
            'total_predictions': len(times),
            'under_15s_rate': sum(1 for t in times if t < 15.0) / len(times),
            'under_5s_rate': sum(1 for t in times if t < 5.0) / len(times)
        }
    
    def _get_api_metrics(self) -> Dict[str, Any]:
        """Get API performance metrics."""
        api_metrics = {}
        
        for api_name in self.api_calls:
            calls = self.api_calls[api_name]
            failures = self.api_failures[api_name]
            response_times = list(self.api_response_times[api_name])
            
            if response_times:
                api_metrics[api_name] = {
                    'total_calls': calls,
                    'total_failures': failures,
                    'success_rate': (calls - failures) / calls,
                    'avg_response_time': statistics.mean(response_times),
                    'min_response_time': min(response_times),
                    'max_response_time': max(response_times),
                    'p95_response_time': self._percentile(response_times, 95)
                }
            else:
                api_metrics[api_name] = {
                    'total_calls': calls,
                    'total_failures': failures,
                    'success_rate': (calls - failures) / calls if calls > 0 else 1.0,
                    'avg_response_time': 0.0
                }
        
        return api_metrics
    
    def _get_component_metrics(self) -> Dict[str, Any]:
        """Get component-specific performance metrics."""
        component_metrics = {}
        
        for component, times in self.component_times.items():
            if times:
                times_list = list(times)
                component_metrics[component] = {
                    'avg_time': statistics.mean(times_list),
                    'min_time': min(times_list),
                    'max_time': max(times_list),
                    'total_calls': len(times_list),
                    'p95_time': self._percentile(times_list, 95)
                }
        
        return component_metrics
    
    def _get_performance_alerts(self) -> List[str]:
        """Get performance alerts and warnings."""
        alerts = []
        
        # Execution time alerts
        if self.execution_times:
            avg_time = statistics.mean(self.execution_times)
            max_time = max(self.execution_times)
            
            if avg_time > 10.0:
                alerts.append(f"High average execution time: {avg_time:.1f}s")
            
            if max_time > 30.0:
                alerts.append(f"Very slow prediction detected: {max_time:.1f}s")
            
            under_15s_rate = sum(1 for t in self.execution_times if t < 15.0) / len(self.execution_times)
            if under_15s_rate < 0.9:
                alerts.append(f"Only {under_15s_rate:.1%} of predictions under 15s target")
        
        # API alerts
        for api_name, failures in self.api_failures.items():
            total_calls = self.api_calls[api_name]
            if total_calls > 0:
                failure_rate = failures / total_calls
                if failure_rate > 0.1:
                    alerts.append(f"High {api_name} API failure rate: {failure_rate:.1%}")
        
        # Component alerts
        for component, times in self.component_times.items():
            if times and len(times) > 5:
                avg_time = statistics.mean(times)
                if component == 'factor_calculation' and avg_time > 2.0:
                    alerts.append(f"Slow factor calculations: {avg_time:.1f}s average")
                elif component == 'api_calls' and avg_time > 3.0:
                    alerts.append(f"Slow API responses: {avg_time:.1f}s average")
        
        return alerts
    
    def _percentile(self, data: List[float], percentile: int) -> float:
        """Calculate percentile of data."""
        if not data:
            return 0.0
        
        sorted_data = sorted(data)
        index = (percentile / 100) * (len(sorted_data) - 1)
        
        if index.is_integer():
            return sorted_data[int(index)]
        else:
            lower = sorted_data[int(index)]
            upper = sorted_data[int(index) + 1]
            return lower + (upper - lower) * (index - int(index))
    
    def optimize_recommendations(self) -> List[str]:
        """Generate optimization recommendations."""
        recommendations = []
        
        # Execution time optimization
        if self.execution_times:
            avg_time = statistics.mean(self.execution_times)
            
            if avg_time > 8.0:
                recommendations.append("Consider caching team data to reduce API calls")
                recommendations.append("Implement parallel factor calculations")
            
            if avg_time > 12.0:
                recommendations.append("Review factor complexity - some may be too computationally expensive")
                recommendations.append("Consider reducing API timeout values")
        
        # API optimization
        total_api_calls = sum(self.api_calls.values())
        if total_api_calls / max(self.prediction_count, 1) > 10:
            recommendations.append("Too many API calls per prediction - implement better caching")
        
        # Component optimization
        for component, times in self.component_times.items():
            if times and len(times) > 3:
                avg_time = statistics.mean(times)
                max_time = max(times)
                
                if component == 'factor_calculation' and avg_time > 1.0:
                    recommendations.append("Factor calculations are slow - optimize algorithms")
                
                if component == 'data_fetching' and max_time > 5.0:
                    recommendations.append("Data fetching is slow - check network and API performance")
        
        return recommendations
    
    def reset_metrics(self):
        """Reset all performance metrics."""
        with self.lock:
            self.execution_times.clear()
            self.component_times.clear()
            self.api_calls.clear()
            self.api_response_times.clear()
            self.api_failures.clear()
            
            self.prediction_count = 0
            self.success_count = 0
            self.error_count = 0
            
            self.session_start = datetime.now()
            
        self.logger.info("Performance metrics reset")
    
    def get_realtime_status(self) -> Dict[str, Any]:
        """Get real-time performance status."""
        with self.lock:
            recent_times = list(self.execution_times)[-10:]  # Last 10 predictions
            
            if recent_times:
                recent_avg = statistics.mean(recent_times)
                trend = "stable"
                
                if len(recent_times) >= 5:
                    first_half = recent_times[:len(recent_times)//2]
                    second_half = recent_times[len(recent_times)//2:]
                    
                    if statistics.mean(second_half) > statistics.mean(first_half) * 1.2:
                        trend = "slowing"
                    elif statistics.mean(second_half) < statistics.mean(first_half) * 0.8:
                        trend = "improving"
            else:
                recent_avg = 0.0
                trend = "no_data"
            
            return {
                'recent_avg_time': recent_avg,
                'trend': trend,
                'active_timers': len(self.active_timers),
                'session_predictions': self.prediction_count,
                'last_prediction_time': self.execution_times[-1] if self.execution_times else None,
                'performance_score': self._calculate_performance_score()
            }
    
    def _calculate_performance_score(self) -> float:
        """Calculate overall performance score (0-100)."""
        if not self.execution_times:
            return 100.0
        
        score = 100.0
        
        # Execution time penalty
        avg_time = statistics.mean(self.execution_times)
        if avg_time > 15.0:
            score -= 50.0
        elif avg_time > 10.0:
            score -= 30.0
        elif avg_time > 5.0:
            score -= 15.0
        
        # Success rate bonus/penalty
        success_rate = self.success_count / max(self.prediction_count, 1)
        score *= success_rate
        
        # API failure penalty
        total_api_calls = sum(self.api_calls.values())
        total_api_failures = sum(self.api_failures.values())
        
        if total_api_calls > 0:
            api_success_rate = (total_api_calls - total_api_failures) / total_api_calls
            score *= api_success_rate
        
        return max(0.0, min(100.0, score))


# Global performance tracker instance
performance_tracker = PerformanceTracker()