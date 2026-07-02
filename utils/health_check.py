"""
Health check system for College Football Market Edge Platform.
Provides comprehensive system health monitoring and API connectivity checks.
"""

import logging
import time
import asyncio
import requests
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass
import concurrent.futures

from config import config
from data.odds_client import OddsAPIClient
from data.espn_client import ESPNStatsClient
from utils.normalizer import normalizer
from utils.rate_limiter import RateLimiter


class HealthStatus(Enum):
    """Health check status levels."""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


@dataclass
class HealthCheckResult:
    """Result of a health check."""
    component: str
    status: HealthStatus
    message: str
    details: Dict[str, Any]
    timestamp: datetime
    response_time: Optional[float] = None


class HealthChecker:
    """
    Comprehensive health check system for all system components.
    
    Features:
    - API connectivity checks
    - System resource monitoring
    - Configuration validation
    - Component functionality tests
    - Performance benchmarking
    """
    
    def __init__(self, config_obj=None):
        """Initialize health checker."""
        self.config = config_obj or config
        self.logger = logging.getLogger(__name__)
        
        # Initialize API clients for testing
        self.odds_client = None
        self.espn_client = None
        
        # Health check history
        self.check_history = {}
        
        # Timeout settings
        self.api_timeout = 30
        self.component_timeout = 10
        
        self.logger.debug("Health checker initialized")
    
    def run_full_health_check(self) -> Dict[str, Any]:
        """
        Run comprehensive health check of all system components.
        
        Returns:
            dict: Complete health check results
        """
        start_time = time.time()
        results = {}
        overall_status = HealthStatus.HEALTHY
        
        self.logger.info("Starting full system health check")
        
        # Run all health checks
        check_methods = [
            self._check_configuration,
            self._check_system_resources,
            self._check_normalizer,
            self._check_odds_api,
            self._check_espn_api,
            self._check_prediction_engine,
            self._check_data_manager,
            self._check_factor_registry
        ]
        
        # Execute checks with timeout
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            future_to_check = {executor.submit(check): check.__name__ for check in check_methods}
            
            for future in concurrent.futures.as_completed(future_to_check, timeout=60):
                check_name = future_to_check[future]
                try:
                    result = future.result(timeout=self.component_timeout)
                    results[result.component] = result
                    
                    # Update overall status
                    if result.status == HealthStatus.CRITICAL:
                        overall_status = HealthStatus.CRITICAL
                    elif result.status == HealthStatus.WARNING and overall_status != HealthStatus.CRITICAL:
                        overall_status = HealthStatus.WARNING
                        
                except concurrent.futures.TimeoutError:
                    results[check_name] = HealthCheckResult(
                        component=check_name,
                        status=HealthStatus.CRITICAL,
                        message="Health check timed out",
                        details={'timeout': True},
                        timestamp=datetime.now()
                    )
                    overall_status = HealthStatus.CRITICAL
                except Exception as e:
                    results[check_name] = HealthCheckResult(
                        component=check_name,
                        status=HealthStatus.CRITICAL,
                        message=f"Health check failed: {str(e)}",
                        details={'error': str(e)},
                        timestamp=datetime.now()
                    )
                    overall_status = HealthStatus.CRITICAL
        
        execution_time = time.time() - start_time
        
        # Compile final results
        health_report = {
            'timestamp': datetime.now().isoformat(),
            'overall_status': overall_status.value,
            'execution_time': execution_time,
            'components': {
                result.component: {
                    'status': result.status.value,
                    'message': result.message,
                    'details': result.details,
                    'response_time': result.response_time,
                    'timestamp': result.timestamp.isoformat()
                }
                for result in results.values()
            },
            'summary': self._generate_health_summary(results, overall_status)
        }
        
        # Store in history
        self.check_history[datetime.now()] = health_report
        
        self.logger.info(f"Health check completed in {execution_time:.2f}s - Status: {overall_status.value}")
        
        return health_report
    
    def _check_configuration(self) -> HealthCheckResult:
        """Check system configuration."""
        start_time = time.time()
        details = {}
        
        try:
            # Check API keys
            api_status = self.config.validate_api_keys()
            details['api_keys'] = api_status
            
            # Check required settings
            required_settings = ['odds_api_key', 'rate_limit_odds', 'rate_limit_espn']
            missing_settings = []
            
            for setting in required_settings:
                if not hasattr(self.config, setting) or getattr(self.config, setting) is None:
                    missing_settings.append(setting)
            
            details['missing_settings'] = missing_settings
            
            # Check factor weights
            total_weight = (self.config.coaching_edge_weight + 
                          self.config.situational_context_weight + 
                          self.config.momentum_factors_weight)
            details['factor_weights_sum'] = total_weight
            details['factor_weights_valid'] = abs(total_weight - 1.0) < 0.001
            
            # Determine status
            if missing_settings or not details['factor_weights_valid']:
                status = HealthStatus.CRITICAL
                message = f"Configuration issues: {', '.join(missing_settings) if missing_settings else 'Invalid factor weights'}"
            elif not api_status.get('odds_api', False):
                status = HealthStatus.WARNING
                message = "Odds API key not configured"
            else:
                status = HealthStatus.HEALTHY
                message = "Configuration valid"
                
        except Exception as e:
            status = HealthStatus.CRITICAL
            message = f"Configuration check failed: {str(e)}"
            details['error'] = str(e)
        
        return HealthCheckResult(
            component="configuration",
            status=status,
            message=message,
            details=details,
            timestamp=datetime.now(),
            response_time=time.time() - start_time
        )
    
    def _check_system_resources(self) -> HealthCheckResult:
        """Check system resource availability."""
        start_time = time.time()
        details = {}
        
        try:
            import psutil
            
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            details['cpu_usage'] = cpu_percent
            
            # Memory usage
            memory = psutil.virtual_memory()
            details['memory_usage'] = {
                'percent': memory.percent,
                'available_gb': memory.available / (1024**3),
                'used_gb': memory.used / (1024**3)
            }
            
            # Disk usage
            disk = psutil.disk_usage('/')
            details['disk_usage'] = {
                'percent': (disk.used / disk.total) * 100,
                'free_gb': disk.free / (1024**3)
            }
            
            # Process info
            process = psutil.Process()
            details['process'] = {
                'memory_mb': process.memory_info().rss / (1024**2),
                'cpu_percent': process.cpu_percent(),
                'num_threads': process.num_threads()
            }
            
            # Determine status
            if cpu_percent > 90 or memory.percent > 90:
                status = HealthStatus.CRITICAL
                message = "System resources critically low"
            elif cpu_percent > 70 or memory.percent > 80:
                status = HealthStatus.WARNING
                message = "System resources running high"
            else:
                status = HealthStatus.HEALTHY
                message = "System resources normal"
                
        except Exception as e:
            status = HealthStatus.WARNING
            message = f"Could not check system resources: {str(e)}"
            details['error'] = str(e)
        
        return HealthCheckResult(
            component="system_resources",
            status=status,
            message=message,
            details=details,
            timestamp=datetime.now(),
            response_time=time.time() - start_time
        )
    
    def _check_normalizer(self) -> HealthCheckResult:
        """Check team name normalizer functionality."""
        start_time = time.time()
        details = {}
        
        try:
            # Test known team names
            test_teams = [
                ('georgia', 'GEORGIA'),
                ('alabama', 'ALABAMA'),
                ('uga', 'GEORGIA'),
                ('bama', 'ALABAMA'),
                ('Ohio State', 'OHIO STATE')
            ]
            
            normalization_results = {}
            for input_name, expected in test_teams:
                try:
                    result = normalizer.normalize(input_name)
                    normalization_results[input_name] = {
                        'result': result,
                        'expected': expected,
                        'correct': result == expected
                    }
                except Exception as e:
                    normalization_results[input_name] = {
                        'error': str(e),
                        'correct': False
                    }
            
            details['test_results'] = normalization_results
            
            # Check if all teams are loaded
            all_teams = normalizer.get_all_teams()
            details['total_teams'] = len(all_teams)
            details['sample_teams'] = list(all_teams)[:10]  # First 10 teams
            
            # Determine status
            failed_tests = [name for name, result in normalization_results.items() 
                          if not result.get('correct', False)]
            
            if failed_tests:
                status = HealthStatus.WARNING
                message = f"Normalizer failed for: {', '.join(failed_tests)}"
            elif len(all_teams) < 100:  # Should have at least 100 FBS teams
                status = HealthStatus.WARNING
                message = f"Only {len(all_teams)} teams loaded, expected more"
            else:
                status = HealthStatus.HEALTHY
                message = f"Normalizer working correctly with {len(all_teams)} teams"
                
        except Exception as e:
            status = HealthStatus.CRITICAL
            message = f"Normalizer check failed: {str(e)}"
            details['error'] = str(e)
        
        return HealthCheckResult(
            component="normalizer",
            status=status,
            message=message,
            details=details,
            timestamp=datetime.now(),
            response_time=time.time() - start_time
        )
    
    def _check_odds_api(self) -> HealthCheckResult:
        """Check Odds API connectivity and functionality."""
        start_time = time.time()
        details = {}
        
        try:
            if not self.config.odds_api_key:
                return HealthCheckResult(
                    component="odds_api",
                    status=HealthStatus.WARNING,
                    message="Odds API key not configured",
                    details={'configured': False},
                    timestamp=datetime.now(),
                    response_time=time.time() - start_time
                )
            
            # Initialize client if needed
            if not self.odds_client:
                self.odds_client = OddsAPIClient(self.config.odds_api_key)
            
            # Test API connectivity
            test_url = f"{self.config.odds_api_base_url}/sports"
            response = requests.get(
                test_url,
                params={'apiKey': self.config.odds_api_key},
                timeout=self.api_timeout
            )
            
            details['api_response'] = {
                'status_code': response.status_code,
                'response_time': response.elapsed.total_seconds(),
                'headers': dict(response.headers)
            }
            
            # Check response
            if response.status_code == 200:
                try:
                    data = response.json()
                    details['sports_available'] = len(data) if isinstance(data, list) else 'unknown'
                    
                    # Look for college football
                    cfb_found = any(sport.get('key') == 'americanfootball_ncaaf' 
                                  for sport in data if isinstance(sport, dict))
                    details['college_football_available'] = cfb_found
                    
                    if cfb_found:
                        status = HealthStatus.HEALTHY
                        message = "Odds API accessible and college football available"
                    else:
                        status = HealthStatus.WARNING
                        message = "Odds API accessible but college football not found"
                        
                except Exception as e:
                    status = HealthStatus.WARNING
                    message = f"Odds API response parsing failed: {str(e)}"
                    details['parse_error'] = str(e)
                    
            elif response.status_code == 401:
                status = HealthStatus.CRITICAL
                message = "Odds API authentication failed - check API key"
            elif response.status_code == 429:
                status = HealthStatus.WARNING
                message = "Odds API rate limit exceeded"
            else:
                status = HealthStatus.WARNING
                message = f"Odds API returned status {response.status_code}"
                
        except requests.exceptions.Timeout:
            status = HealthStatus.CRITICAL
            message = "Odds API request timed out"
            details['timeout'] = True
        except requests.exceptions.ConnectionError:
            status = HealthStatus.CRITICAL
            message = "Could not connect to Odds API"
            details['connection_error'] = True
        except Exception as e:
            status = HealthStatus.CRITICAL
            message = f"Odds API check failed: {str(e)}"
            details['error'] = str(e)
        
        return HealthCheckResult(
            component="odds_api",
            status=status,
            message=message,
            details=details,
            timestamp=datetime.now(),
            response_time=time.time() - start_time
        )
    
    def _check_espn_api(self) -> HealthCheckResult:
        """Check ESPN API connectivity and functionality."""
        start_time = time.time()
        details = {}
        
        try:
            # Initialize client if needed
            if not self.espn_client:
                self.espn_client = ESPNStatsClient()
            
            # Test API connectivity with a simple request
            test_url = f"{self.config.espn_api_base_url}/teams"
            response = requests.get(test_url, timeout=self.api_timeout)
            
            details['api_response'] = {
                'status_code': response.status_code,
                'response_time': response.elapsed.total_seconds(),
                'content_length': len(response.content)
            }
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    
                    # Check if we got team data
                    if 'sports' in data and len(data['sports']) > 0:
                        sport = data['sports'][0]
                        if 'leagues' in sport and len(sport['leagues']) > 0:
                            league = sport['leagues'][0]
                            if 'teams' in league:
                                teams_count = len(league['teams'])
                                details['teams_available'] = teams_count
                                
                                if teams_count > 50:  # Should have many college teams
                                    status = HealthStatus.HEALTHY
                                    message = f"ESPN API accessible with {teams_count} teams"
                                else:
                                    status = HealthStatus.WARNING
                                    message = f"ESPN API accessible but only {teams_count} teams found"
                            else:
                                status = HealthStatus.WARNING
                                message = "ESPN API accessible but no team data structure"
                        else:
                            status = HealthStatus.WARNING
                            message = "ESPN API accessible but no league data"
                    else:
                        status = HealthStatus.WARNING
                        message = "ESPN API accessible but no sports data"
                        
                except Exception as e:
                    status = HealthStatus.WARNING
                    message = f"ESPN API response parsing failed: {str(e)}"
                    details['parse_error'] = str(e)
            else:
                status = HealthStatus.WARNING
                message = f"ESPN API returned status {response.status_code}"
                
        except requests.exceptions.Timeout:
            status = HealthStatus.CRITICAL
            message = "ESPN API request timed out"
            details['timeout'] = True
        except requests.exceptions.ConnectionError:
            status = HealthStatus.CRITICAL
            message = "Could not connect to ESPN API"
            details['connection_error'] = True
        except Exception as e:
            status = HealthStatus.WARNING
            message = f"ESPN API check failed: {str(e)}"
            details['error'] = str(e)
        
        return HealthCheckResult(
            component="espn_api",
            status=status,
            message=message,
            details=details,
            timestamp=datetime.now(),
            response_time=time.time() - start_time
        )
    
    def _check_prediction_engine(self) -> HealthCheckResult:
        """Check prediction engine functionality."""
        start_time = time.time()
        details = {}
        
        try:
            from engine.prediction_engine import prediction_engine
            
            # Test engine initialization
            details['engine_initialized'] = hasattr(prediction_engine, 'factor_registry')
            
            # Test validation method
            validation_result = prediction_engine.validate_prediction_setup()
            details['validation_result'] = validation_result
            
            # Get engine statistics
            stats = prediction_engine.get_prediction_stats()
            details['engine_stats'] = stats
            
            # Determine status based on validation
            if validation_result.get('valid', False):
                status = HealthStatus.HEALTHY
                message = "Prediction engine operational"
            else:
                errors = validation_result.get('errors', [])
                if errors:
                    status = HealthStatus.CRITICAL
                    message = f"Prediction engine has errors: {', '.join(errors[:2])}"
                else:
                    status = HealthStatus.WARNING
                    message = "Prediction engine validation incomplete"
                    
        except ImportError:
            status = HealthStatus.CRITICAL
            message = "Prediction engine not importable"
            details['import_error'] = True
        except Exception as e:
            status = HealthStatus.CRITICAL
            message = f"Prediction engine check failed: {str(e)}"
            details['error'] = str(e)
        
        return HealthCheckResult(
            component="prediction_engine",
            status=status,
            message=message,
            details=details,
            timestamp=datetime.now(),
            response_time=time.time() - start_time
        )
    
    def _check_data_manager(self) -> HealthCheckResult:
        """Check data manager functionality."""
        start_time = time.time()
        details = {}
        
        try:
            from data.data_manager import data_manager
            
            # Test connections
            connections = data_manager.test_all_connections()
            details['connections'] = connections
            
            # Test safe data fetch mechanism
            def test_function():
                return "test_successful"
            
            result = data_manager.safe_data_fetch(test_function)
            details['safe_fetch_working'] = result == "test_successful"
            
            # Check if all required components are available
            required_components = ['odds_client', 'espn_client', 'normalizer']
            available_components = []
            
            for component in required_components:
                if hasattr(data_manager, component):
                    available_components.append(component)
            
            details['available_components'] = available_components
            details['missing_components'] = [c for c in required_components if c not in available_components]
            
            # Determine status
            if len(available_components) == len(required_components):
                if all(conn.get('status') == 'ok' for conn in connections.values()):
                    status = HealthStatus.HEALTHY
                    message = "Data manager fully operational"
                else:
                    status = HealthStatus.WARNING
                    message = "Data manager operational but some connections have issues"
            else:
                status = HealthStatus.CRITICAL
                message = f"Data manager missing components: {', '.join(details['missing_components'])}"
                
        except ImportError:
            status = HealthStatus.CRITICAL
            message = "Data manager not importable"
            details['import_error'] = True
        except Exception as e:
            status = HealthStatus.CRITICAL
            message = f"Data manager check failed: {str(e)}"
            details['error'] = str(e)
        
        return HealthCheckResult(
            component="data_manager",
            status=status,
            message=message,
            details=details,
            timestamp=datetime.now(),
            response_time=time.time() - start_time
        )
    
    def _check_factor_registry(self) -> HealthCheckResult:
        """Check factor registry functionality."""
        start_time = time.time()
        details = {}
        
        try:
            from factors.factor_registry import factor_registry
            
            # Test factor loading
            validation = factor_registry.validate_factor_configuration()
            details['validation'] = validation
            
            # Get factor statistics
            stats = factor_registry.get_execution_stats()
            details['execution_stats'] = stats
            
            # Check weight distribution
            if hasattr(factor_registry, 'get_weight_distribution'):
                weights = factor_registry.get_weight_distribution()
                details['weight_distribution'] = weights
                
                total_weight = sum(weights.values())
                details['total_weight'] = total_weight
                details['weight_balanced'] = abs(total_weight - 1.0) < 0.001
            
            # Count loaded factors
            loaded_factors = len(factor_registry.factors) if hasattr(factor_registry, 'factors') else 0
            details['loaded_factors'] = loaded_factors
            
            # Determine status
            if validation.get('valid', False) and loaded_factors >= 10:
                status = HealthStatus.HEALTHY
                message = f"Factor registry operational with {loaded_factors} factors"
            elif loaded_factors > 0:
                status = HealthStatus.WARNING
                message = f"Factor registry partially operational ({loaded_factors} factors)"
            else:
                status = HealthStatus.CRITICAL
                message = "Factor registry not operational"
                
        except ImportError:
            status = HealthStatus.CRITICAL
            message = "Factor registry not importable"
            details['import_error'] = True
        except Exception as e:
            status = HealthStatus.CRITICAL
            message = f"Factor registry check failed: {str(e)}"
            details['error'] = str(e)
        
        return HealthCheckResult(
            component="factor_registry",
            status=status,
            message=message,
            details=details,
            timestamp=datetime.now(),
            response_time=time.time() - start_time
        )
    
    def _generate_health_summary(self, results: Dict[str, HealthCheckResult], 
                               overall_status: HealthStatus) -> Dict[str, Any]:
        """Generate health check summary."""
        summary = {
            'overall_status': overall_status.value,
            'total_components': len(results),
            'healthy_components': len([r for r in results.values() if r.status == HealthStatus.HEALTHY]),
            'warning_components': len([r for r in results.values() if r.status == HealthStatus.WARNING]),
            'critical_components': len([r for r in results.values() if r.status == HealthStatus.CRITICAL]),
            'recommendations': []
        }
        
        # Generate recommendations based on results
        critical_components = [r.component for r in results.values() if r.status == HealthStatus.CRITICAL]
        warning_components = [r.component for r in results.values() if r.status == HealthStatus.WARNING]
        
        if critical_components:
            summary['recommendations'].append(f"CRITICAL: Fix issues with {', '.join(critical_components)}")
        
        if warning_components:
            summary['recommendations'].append(f"WARNING: Monitor {', '.join(warning_components)}")
        
        if overall_status == HealthStatus.HEALTHY:
            summary['recommendations'].append("All systems operational")
        
        return summary
    
    def get_health_history(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Get health check history for specified timeframe."""
        cutoff = datetime.now() - timedelta(hours=hours)
        return [
            report for timestamp, report in self.check_history.items()
            if timestamp > cutoff
        ]
    
    def quick_health_check(self) -> Dict[str, str]:
        """Run a quick health check of critical components only."""
        results = {}
        
        # Quick API checks
        try:
            if self.config.odds_api_key:
                response = requests.get(
                    f"{self.config.odds_api_base_url}/sports",
                    params={'apiKey': self.config.odds_api_key},
                    timeout=5
                )
                results['odds_api'] = 'healthy' if response.status_code == 200 else 'warning'
            else:
                results['odds_api'] = 'not_configured'
        except:
            results['odds_api'] = 'error'
        
        # Quick ESPN check
        try:
            response = requests.get(f"{self.config.espn_api_base_url}/teams", timeout=5)
            results['espn_api'] = 'healthy' if response.status_code == 200 else 'warning'
        except:
            results['espn_api'] = 'error'
        
        # Quick normalizer check
        try:
            test_result = normalizer.normalize('georgia')
            results['normalizer'] = 'healthy' if test_result == 'GEORGIA' else 'warning'
        except:
            results['normalizer'] = 'error'
        
        return results


# Global health checker instance
health_checker = HealthChecker(config)