"""
Configuration management for College Football Market Edge Platform.
Handles API keys, rate limits, and application settings.
"""

import os
import logging
from typing import Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Config:
    """Application configuration with environment variable loading and validation."""
    
    def __init__(self):
        """Initialize configuration with environment variables and defaults."""
        # API Configuration
        self.odds_api_key = os.getenv('ODDS_API_KEY')
        self.espn_api_key = os.getenv('ESPN_API_KEY', None)  # Optional
        self.cfbd_api_key = os.getenv('CFBD_API_KEY', None)  # College Football Data API
        
        # Application Settings
        self.debug = os.getenv('DEBUG', 'false').lower() == 'true'
        self.log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
        
        # Rate Limiting (calls per time period)
        self.rate_limit_odds = int(os.getenv('ODDS_API_RATE_LIMIT', '83'))  # calls per day
        self.rate_limit_espn = int(os.getenv('ESPN_API_RATE_LIMIT', '60'))  # calls per minute
        self.rate_limit_cfbd = int(os.getenv('CFBD_API_RATE_LIMIT', '150'))  # calls per day (Tier 1)
        
        # Cache Configuration
        self.cache_ttl = int(os.getenv('CACHE_TTL', '3600'))  # 1 hour default
        self.session_cache_size = int(os.getenv('SESSION_CACHE_SIZE', '1000'))
        
        # API Endpoints
        self.odds_api_base_url = "https://api.the-odds-api.com/v4"
        self.espn_api_base_url = "https://site.api.espn.com/apis/site/v2/sports/football/college-football"
        
        # Application Constants
        self.max_execution_time = 15  # seconds
        self.max_api_calls_per_prediction = 20
        self.min_confidence_threshold = 15  # percent
        self.max_confidence_threshold = 95  # percent
        
        # Factor Weights (should sum to 1.0)
        # New contrarian factor structure: PRIMARY/SECONDARY/MODIFIER
        self.primary_factors_weight = float(os.getenv('PRIMARY_FACTORS_WEIGHT', 0.60))
        self.secondary_factors_weight = float(os.getenv('SECONDARY_FACTORS_WEIGHT', 0.30))
        self.modifier_factors_weight = float(os.getenv('MODIFIER_FACTORS_WEIGHT', 0.10))
        
        # Legacy weights (deprecated but kept for backward compatibility)
        self.coaching_edge_weight = 0.40
        self.situational_context_weight = 0.40
        self.momentum_factors_weight = 0.20
        
        # Edge Classification Thresholds
        self.edge_thresholds = {
            'massive': 6.0,
            'strong': 4.0,
            'solid': 2.5,
            'slight': 1.5
        }
        
        # Validate configuration
        self._validate_config()
        
        # Setup logging
        self._setup_logging()
    
    def _validate_config(self) -> None:
        """Validate required configuration values."""
        if not self.odds_api_key:
            logging.warning("ODDS_API_KEY not found in environment variables")
        
        # Validate rate limits are positive
        if self.rate_limit_odds <= 0 or self.rate_limit_espn <= 0:
            raise ValueError("Rate limits must be positive integers")
        
        # Validate cache TTL
        if self.cache_ttl <= 0:
            raise ValueError("Cache TTL must be positive")
        
        # Validate new contrarian factor weights sum to 1.0
        new_total_weight = (self.primary_factors_weight + 
                           self.secondary_factors_weight + 
                           self.modifier_factors_weight)
        if abs(new_total_weight - 1.0) > 0.001:  # Allow for float precision
            raise ValueError(f"Contrarian factor weights must sum to 1.0, got {new_total_weight}")
        
        # Also validate legacy weights for backward compatibility
        legacy_total_weight = (self.coaching_edge_weight + 
                              self.situational_context_weight + 
                              self.momentum_factors_weight)
        if abs(legacy_total_weight - 1.0) > 0.001:
            raise ValueError(f"Legacy factor weights must sum to 1.0, got {legacy_total_weight}")
    
    def _setup_logging(self) -> None:
        """Configure logging based on configuration settings."""
        # Only set up logging if it hasn't been configured yet
        if not logging.getLogger().handlers:
            logging.basicConfig(
                level=getattr(logging, self.log_level),
                format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
        
        if self.debug:
            logging.getLogger().setLevel(logging.DEBUG)
    
    def validate_api_keys(self) -> dict:
        """
        Validate API keys and return status.
        
        Returns:
            dict: Status of each API key with primary/fallback indicators
        """
        status = {
            'cfbd_api': {
                'configured': bool(self.cfbd_api_key),
                'role': 'primary',
                'description': 'College Football Data API - Primary source for coaching/stats data'
            },
            'espn_api': {
                'configured': True,  # Always available as fallback
                'role': 'fallback', 
                'description': 'ESPN API - Fallback for team data and schedule info'
            },
            'odds_api': {
                'configured': bool(self.odds_api_key),
                'role': 'required',
                'description': 'Odds API - Required for betting lines and spreads'
            }
        }
        return status
    
    def get_rate_limit(self, api_name: str) -> int:
        """
        Get rate limit for specified API.
        
        Args:
            api_name: Name of the API ('odds', 'espn', or 'cfbd')
            
        Returns:
            int: Rate limit for the API
        """
        if api_name.lower() == 'odds':
            return self.rate_limit_odds
        elif api_name.lower() == 'espn':
            return self.rate_limit_espn
        elif api_name.lower() == 'cfbd':
            return self.rate_limit_cfbd
        else:
            raise ValueError(f"Unknown API name: {api_name}")
    
    def get_edge_classification(self, edge_size: float) -> str:
        """
        Classify edge size into categories.
        
        Args:
            edge_size: Size of the edge in points
            
        Returns:
            str: Edge classification
        """
        # Handle None or invalid edge size
        if edge_size is None or not isinstance(edge_size, (int, float)):
            return 'NO DATA'
            
        abs_edge = abs(edge_size)
        
        if abs_edge >= self.edge_thresholds['massive']:
            return 'MASSIVE EDGE'
        elif abs_edge >= self.edge_thresholds['strong']:
            return 'STRONG EDGE'
        elif abs_edge >= self.edge_thresholds['solid']:
            return 'SOLID EDGE'
        elif abs_edge >= self.edge_thresholds['slight']:
            return 'SLIGHT LEAN'
        else:
            return 'NO EDGE'
    
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return not self.debug
    
    def __str__(self) -> str:
        """String representation of configuration (without sensitive data)."""
        return f"""Config(
    debug={self.debug},
    log_level={self.log_level},
    cfbd_api_configured={bool(self.cfbd_api_key)} (Primary),
    espn_api_configured={bool(self.espn_api_key)} (Fallback),
    odds_api_configured={bool(self.odds_api_key)},
    cache_ttl={self.cache_ttl}s,
    rate_limits=(cfbd:{self.rate_limit_cfbd}/day, espn:{self.rate_limit_espn}/min, odds:{self.rate_limit_odds}/day)
)"""


class ProductionConfig(Config):
    """Production-specific configuration with enhanced validation."""
    
    def __init__(self):
        super().__init__()
        # Override debug settings for production
        self.debug = False
        self.log_level = 'WARNING'
        
        # Production performance settings
        self.max_execution_time = 12  # Stricter for production
        self.max_api_calls_per_prediction = 15  # More conservative
        
        # Enhanced caching for production
        self.cache_ttl = 7200  # 2 hours for production
        self.session_cache_size = 2000  # Larger cache
        
        # Stricter validation for production
        self._validate_production_requirements()
        self._setup_production_logging()
    
    def _validate_production_requirements(self) -> None:
        """Validate production-specific requirements."""
        if not self.odds_api_key:
            raise ValueError("ODDS_API_KEY is required for production")
        
        # Ensure conservative rate limits for production
        if self.rate_limit_odds > 100:  # Conservative limit for daily quota
            logging.warning(f"High rate limit for odds API: {self.rate_limit_odds}")
        
        # Validate critical thresholds
        if self.max_execution_time > 15:
            logging.warning("Execution time limit may be too high for production")
    
    def _setup_production_logging(self) -> None:
        """Setup production-specific logging configuration."""
        import logging.handlers
        
        # Create logs directory if it doesn't exist
        log_dir = os.path.join(os.path.dirname(__file__), 'logs')
        os.makedirs(log_dir, exist_ok=True)
        
        # Setup file logging for production
        log_file = os.path.join(log_dir, 'cfb_predictor.log')
        file_handler = logging.handlers.RotatingFileHandler(
            log_file, maxBytes=10*1024*1024, backupCount=5  # 10MB files, 5 backups
        )
        file_handler.setLevel(logging.WARNING)
        
        # Setup error log file
        error_log_file = os.path.join(log_dir, 'cfb_predictor_errors.log')
        error_handler = logging.handlers.RotatingFileHandler(
            error_log_file, maxBytes=5*1024*1024, backupCount=3  # 5MB files, 3 backups
        )
        error_handler.setLevel(logging.ERROR)
        
        # Add handlers to root logger
        root_logger = logging.getLogger()
        root_logger.addHandler(file_handler)
        root_logger.addHandler(error_handler)
    
    def get_system_health_check_config(self) -> dict:
        """Get configuration for system health checks."""
        return {
            'api_timeout_seconds': 30,
            'max_consecutive_failures': 3,
            'health_check_interval': 300,  # 5 minutes
            'performance_alert_threshold': 20,  # seconds
            'memory_alert_threshold': 200  # MB
        }


# Factory function for getting appropriate config
def get_config() -> Config:
    """
    Factory function to get appropriate configuration.
    
    Returns:
        Config: Configuration instance based on environment
    """
    if os.getenv('ENVIRONMENT', '').lower() == 'production':
        return ProductionConfig()
    else:
        return Config()


# Global config instance
config = get_config()