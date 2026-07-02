"""
System monitoring and performance tracking for College Football Market Edge Platform.
Provides comprehensive monitoring, logging, and performance metrics.
"""

import logging
import time
import psutil
import threading
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, timedelta
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum
import json
import os


class AlertLevel(Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class PerformanceMetric:
    """Performance metric data structure."""
    name: str
    value: float
    timestamp: datetime
    unit: str = ""
    tags: Dict[str, str] = field(default_factory=dict)


@dataclass
class SystemAlert:
    """System alert data structure."""
    level: AlertLevel
    message: str
    timestamp: datetime
    component: str
    metric_value: Optional[float] = None
    threshold: Optional[float] = None


class SystemMonitor:
    """
    Comprehensive system monitoring for the CFB Predictor.
    
    Features:
    - Performance metrics tracking
    - Resource utilization monitoring
    - API usage tracking
    - Error rate monitoring
    - Health checks
    - Alerting system
    """
    
    def __init__(self, config=None):
        """Initialize system monitor."""
        self.config = config
        self.start_time = datetime.now()
        
        # Performance tracking
        self.prediction_times = deque(maxlen=1000)
        self.api_call_counts = defaultdict(int)
        self.api_response_times = defaultdict(list)
        self.error_counts = defaultdict(int)
        
        # Resource monitoring
        self.cpu_usage_history = deque(maxlen=100)
        self.memory_usage_history = deque(maxlen=100)
        
        # Metrics storage
        self.metrics = defaultdict(list)
        self.alerts = []
        
        # Health check status
        self.health_status = {
            'overall': 'unknown',
            'api_connectivity': 'unknown',
            'system_resources': 'unknown',
            'prediction_engine': 'unknown'
        }
        
        # Threading for background monitoring
        self.monitoring_active = False
        self.monitor_thread = None
        
        # Logging
        self.logger = logging.getLogger(__name__)
        
        # Thresholds (can be overridden by config)
        self.thresholds = {
            'max_prediction_time': 15.0,  # seconds
            'max_cpu_usage': 80.0,  # percent
            'max_memory_usage': 200.0,  # MB
            'max_error_rate': 10.0,  # percent
            'api_timeout': 30.0,  # seconds
            'max_consecutive_failures': 3
        }
        
        if config:
            health_config = getattr(config, 'get_system_health_check_config', lambda: {})()
            self.thresholds.update(health_config)
        
        self.logger.info("System monitor initialized")
    
    def start_monitoring(self):
        """Start background monitoring thread."""
        if not self.monitoring_active:
            self.monitoring_active = True
            self.monitor_thread = threading.Thread(target=self._background_monitoring, daemon=True)
            self.monitor_thread.start()
            self.logger.info("Background monitoring started")
    
    def stop_monitoring(self):
        """Stop background monitoring thread."""
        self.monitoring_active = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        self.logger.info("Background monitoring stopped")
    
    def _background_monitoring(self):
        """Background monitoring loop."""
        while self.monitoring_active:
            try:
                self._collect_system_metrics()
                self._check_thresholds()
                time.sleep(60)  # Monitor every minute
            except Exception as e:
                self.logger.error(f"Error in background monitoring: {e}")
                time.sleep(60)
    
    def _collect_system_metrics(self):
        """Collect system resource metrics."""
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            self.cpu_usage_history.append(cpu_percent)
            self.record_metric("system.cpu_usage", cpu_percent, unit="percent")
            
            # Memory usage
            process = psutil.Process()
            memory_mb = process.memory_info().rss / 1024 / 1024
            self.memory_usage_history.append(memory_mb)
            self.record_metric("system.memory_usage", memory_mb, unit="MB")
            
            # Disk usage (optional)
            disk_usage = psutil.disk_usage('/').percent
            self.record_metric("system.disk_usage", disk_usage, unit="percent")
            
        except Exception as e:
            self.logger.error(f"Error collecting system metrics: {e}")
    
    def _check_thresholds(self):
        """Check metrics against thresholds and generate alerts."""
        # Check CPU usage
        if self.cpu_usage_history and self.cpu_usage_history[-1] > self.thresholds['max_cpu_usage']:
            self.create_alert(
                AlertLevel.WARNING,
                f"High CPU usage: {self.cpu_usage_history[-1]:.1f}%",
                "system",
                self.cpu_usage_history[-1],
                self.thresholds['max_cpu_usage']
            )
        
        # Check memory usage
        if self.memory_usage_history and self.memory_usage_history[-1] > self.thresholds['max_memory_usage']:
            self.create_alert(
                AlertLevel.WARNING,
                f"High memory usage: {self.memory_usage_history[-1]:.1f}MB",
                "system",
                self.memory_usage_history[-1],
                self.thresholds['max_memory_usage']
            )
        
        # Check prediction times
        if self.prediction_times:
            avg_time = sum(self.prediction_times) / len(self.prediction_times)
            if avg_time > self.thresholds['max_prediction_time']:
                self.create_alert(
                    AlertLevel.ERROR,
                    f"Slow prediction times: {avg_time:.1f}s average",
                    "prediction_engine",
                    avg_time,
                    self.thresholds['max_prediction_time']
                )
    
    def log_prediction_performance(self, execution_time: float, api_calls: int, 
                                 prediction_success: bool = True):
        """
        Log prediction performance metrics.
        
        Args:
            execution_time: Total execution time in seconds
            api_calls: Number of API calls made
            prediction_success: Whether prediction was successful
        """
        self.prediction_times.append(execution_time)
        
        # Record metrics
        self.record_metric("prediction.execution_time", execution_time, unit="seconds")
        self.record_metric("prediction.api_calls", api_calls, unit="count")
        
        # Track success/failure
        outcome = "success" if prediction_success else "failure"
        self.record_metric(f"prediction.{outcome}", 1, unit="count")
        
        # Check for performance issues
        if execution_time > self.thresholds['max_prediction_time']:
            self.create_alert(
                AlertLevel.WARNING,
                f"Slow prediction: {execution_time:.1f}s",
                "prediction_engine",
                execution_time,
                self.thresholds['max_prediction_time']
            )
        
        self.logger.info(f"Prediction completed in {execution_time:.2f}s with {api_calls} API calls")
    
    def log_api_call(self, api_name: str, response_time: float, success: bool = True):
        """
        Log API call metrics.
        
        Args:
            api_name: Name of the API (e.g., 'odds_api', 'espn_api')
            response_time: Response time in seconds
            success: Whether the call was successful
        """
        self.api_call_counts[api_name] += 1
        self.api_response_times[api_name].append(response_time)
        
        # Keep only recent response times
        if len(self.api_response_times[api_name]) > 100:
            self.api_response_times[api_name] = self.api_response_times[api_name][-100:]
        
        # Record metrics
        self.record_metric(f"api.{api_name}.response_time", response_time, unit="seconds")
        self.record_metric(f"api.{api_name}.calls", 1, unit="count")
        
        if not success:
            self.error_counts[f"api_{api_name}"] += 1
            self.record_metric(f"api.{api_name}.errors", 1, unit="count")
        
        # Check for slow API calls
        if response_time > self.thresholds['api_timeout']:
            self.create_alert(
                AlertLevel.WARNING,
                f"Slow API response from {api_name}: {response_time:.1f}s",
                f"api_{api_name}",
                response_time,
                self.thresholds['api_timeout']
            )
        
        self.logger.debug(f"API call to {api_name}: {response_time:.2f}s, success={success}")
    
    def log_error(self, error_type: str, error_message: str, component: str = "unknown"):
        """
        Log error occurrence.
        
        Args:
            error_type: Type of error
            error_message: Error message
            component: Component where error occurred
        """
        self.error_counts[error_type] += 1
        self.record_metric(f"error.{error_type}", 1, unit="count")
        
        self.create_alert(
            AlertLevel.ERROR,
            f"{error_type}: {error_message}",
            component
        )
        
        self.logger.error(f"Error in {component}: {error_type} - {error_message}")
    
    def record_metric(self, name: str, value: float, unit: str = "", tags: Dict[str, str] = None):
        """
        Record a performance metric.
        
        Args:
            name: Metric name
            value: Metric value
            unit: Unit of measurement
            tags: Additional tags
        """
        metric = PerformanceMetric(
            name=name,
            value=value,
            timestamp=datetime.now(),
            unit=unit,
            tags=tags or {}
        )
        
        self.metrics[name].append(metric)
        
        # Keep only recent metrics (last 1000 per metric)
        if len(self.metrics[name]) > 1000:
            self.metrics[name] = self.metrics[name][-1000:]
    
    def create_alert(self, level: AlertLevel, message: str, component: str,
                    metric_value: Optional[float] = None, threshold: Optional[float] = None):
        """
        Create a system alert.
        
        Args:
            level: Alert severity level
            message: Alert message
            component: Component that triggered the alert
            metric_value: Current metric value
            threshold: Threshold that was exceeded
        """
        alert = SystemAlert(
            level=level,
            message=message,
            timestamp=datetime.now(),
            component=component,
            metric_value=metric_value,
            threshold=threshold
        )
        
        self.alerts.append(alert)
        
        # Keep only recent alerts (last 100)
        if len(self.alerts) > 100:
            self.alerts = self.alerts[-100:]
        
        # Log the alert
        log_level = {
            AlertLevel.INFO: logging.INFO,
            AlertLevel.WARNING: logging.WARNING,
            AlertLevel.ERROR: logging.ERROR,
            AlertLevel.CRITICAL: logging.CRITICAL
        }[level]
        
        self.logger.log(log_level, f"ALERT [{level.value.upper()}] {component}: {message}")
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """
        Get comprehensive performance summary.
        
        Returns:
            dict: Performance summary
        """
        summary = {
            'uptime': str(datetime.now() - self.start_time),
            'total_predictions': len(self.prediction_times),
            'avg_prediction_time': sum(self.prediction_times) / len(self.prediction_times) if self.prediction_times else 0,
            'total_api_calls': sum(self.api_call_counts.values()),
            'total_errors': sum(self.error_counts.values()),
            'current_cpu_usage': self.cpu_usage_history[-1] if self.cpu_usage_history else 0,
            'current_memory_usage': self.memory_usage_history[-1] if self.memory_usage_history else 0,
            'recent_alerts': len([a for a in self.alerts if a.timestamp > datetime.now() - timedelta(hours=1)]),
            'health_status': self.health_status.copy()
        }
        
        # API breakdown
        summary['api_breakdown'] = {}
        for api_name, call_count in self.api_call_counts.items():
            avg_response_time = (
                sum(self.api_response_times[api_name]) / len(self.api_response_times[api_name])
                if self.api_response_times[api_name] else 0
            )
            summary['api_breakdown'][api_name] = {
                'total_calls': call_count,
                'avg_response_time': avg_response_time,
                'recent_calls': len([t for t in self.api_response_times[api_name] 
                                   if t > time.time() - 3600])  # Last hour
            }
        
        return summary
    
    def get_recent_alerts(self, hours: int = 24) -> List[SystemAlert]:
        """
        Get recent alerts within specified timeframe.
        
        Args:
            hours: Number of hours to look back
            
        Returns:
            list: Recent alerts
        """
        cutoff = datetime.now() - timedelta(hours=hours)
        return [alert for alert in self.alerts if alert.timestamp > cutoff]
    
    def get_metric_history(self, metric_name: str, hours: int = 24) -> List[PerformanceMetric]:
        """
        Get metric history for specified timeframe.
        
        Args:
            metric_name: Name of the metric
            hours: Number of hours to look back
            
        Returns:
            list: Metric history
        """
        cutoff = datetime.now() - timedelta(hours=hours)
        return [
            metric for metric in self.metrics.get(metric_name, [])
            if metric.timestamp > cutoff
        ]
    
    def export_metrics(self, filepath: Optional[str] = None) -> str:
        """
        Export metrics to JSON file.
        
        Args:
            filepath: Optional file path, defaults to timestamped file
            
        Returns:
            str: Path to exported file
        """
        if not filepath:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filepath = f"cfb_predictor_metrics_{timestamp}.json"
        
        export_data = {
            'export_timestamp': datetime.now().isoformat(),
            'summary': self.get_performance_summary(),
            'recent_alerts': [
                {
                    'level': alert.level.value,
                    'message': alert.message,
                    'timestamp': alert.timestamp.isoformat(),
                    'component': alert.component,
                    'metric_value': alert.metric_value,
                    'threshold': alert.threshold
                }
                for alert in self.get_recent_alerts(24)
            ],
            'metrics': {
                name: [
                    {
                        'value': metric.value,
                        'timestamp': metric.timestamp.isoformat(),
                        'unit': metric.unit,
                        'tags': metric.tags
                    }
                    for metric in metrics[-100:]  # Last 100 values per metric
                ]
                for name, metrics in self.metrics.items()
            }
        }
        
        try:
            with open(filepath, 'w') as f:
                json.dump(export_data, f, indent=2)
            self.logger.info(f"Metrics exported to {filepath}")
            return filepath
        except Exception as e:
            self.logger.error(f"Error exporting metrics: {e}")
            raise
    
    def run_health_check(self) -> Dict[str, Any]:
        """
        Run comprehensive health check.
        
        Returns:
            dict: Health check results
        """
        health_results = {
            'timestamp': datetime.now().isoformat(),
            'overall_status': 'healthy',
            'checks': {}
        }
        
        try:
            # System resources check
            cpu_usage = psutil.cpu_percent(interval=1)
            memory_usage = psutil.Process().memory_info().rss / 1024 / 1024
            
            health_results['checks']['system_resources'] = {
                'status': 'healthy',
                'cpu_usage': cpu_usage,
                'memory_usage': memory_usage,
                'details': f"CPU: {cpu_usage:.1f}%, Memory: {memory_usage:.1f}MB"
            }
            
            if cpu_usage > self.thresholds['max_cpu_usage'] or memory_usage > self.thresholds['max_memory_usage']:
                health_results['checks']['system_resources']['status'] = 'warning'
                health_results['overall_status'] = 'warning'
            
            # Performance check
            if self.prediction_times:
                avg_prediction_time = sum(self.prediction_times) / len(self.prediction_times)
                health_results['checks']['performance'] = {
                    'status': 'healthy',
                    'avg_prediction_time': avg_prediction_time,
                    'total_predictions': len(self.prediction_times),
                    'details': f"Average prediction time: {avg_prediction_time:.2f}s"
                }
                
                if avg_prediction_time > self.thresholds['max_prediction_time']:
                    health_results['checks']['performance']['status'] = 'warning'
                    health_results['overall_status'] = 'warning'
            
            # Error rate check
            total_operations = len(self.prediction_times) + sum(self.api_call_counts.values())
            total_errors = sum(self.error_counts.values())
            error_rate = (total_errors / total_operations * 100) if total_operations > 0 else 0
            
            health_results['checks']['error_rate'] = {
                'status': 'healthy',
                'error_rate': error_rate,
                'total_errors': total_errors,
                'total_operations': total_operations,
                'details': f"Error rate: {error_rate:.2f}%"
            }
            
            if error_rate > self.thresholds['max_error_rate']:
                health_results['checks']['error_rate']['status'] = 'critical'
                health_results['overall_status'] = 'critical'
            
        except Exception as e:
            health_results['overall_status'] = 'error'
            health_results['error'] = str(e)
            self.logger.error(f"Error running health check: {e}")
        
        # Update internal health status
        self.health_status['overall'] = health_results['overall_status']
        
        return health_results


# Global monitor instance
system_monitor = SystemMonitor()