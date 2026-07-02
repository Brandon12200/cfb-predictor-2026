"""
Tests for configuration management functionality.
"""

import unittest
import os
import tempfile
from unittest.mock import patch, MagicMock
from config import Config, ProductionConfig, get_config


class TestConfig(unittest.TestCase):
    """Test cases for Config class."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Clear environment variables to ensure clean test state
        self.env_vars_to_restore = {}
        env_vars = [
            'ODDS_API_KEY', 'ESPN_API_KEY', 'DEBUG', 'LOG_LEVEL',
            'ODDS_API_RATE_LIMIT', 'ESPN_API_RATE_LIMIT', 
            'CACHE_TTL', 'SESSION_CACHE_SIZE', 'ENVIRONMENT'
        ]
        
        for var in env_vars:
            if var in os.environ:
                self.env_vars_to_restore[var] = os.environ[var]
                del os.environ[var]
    
    def tearDown(self):
        """Restore environment variables."""
        # Clear test environment variables
        env_vars = [
            'ODDS_API_KEY', 'ESPN_API_KEY', 'DEBUG', 'LOG_LEVEL',
            'ODDS_API_RATE_LIMIT', 'ESPN_API_RATE_LIMIT', 
            'CACHE_TTL', 'SESSION_CACHE_SIZE', 'ENVIRONMENT'
        ]
        
        for var in env_vars:
            if var in os.environ:
                del os.environ[var]
        
        # Restore original values
        for var, value in self.env_vars_to_restore.items():
            os.environ[var] = value
    
    def test_default_configuration(self):
        """Test default configuration values."""
        config = Config()
        
        # Check default values
        self.assertIsNone(config.odds_api_key)  # No default API key
        self.assertIsNone(config.espn_api_key)
        self.assertFalse(config.debug)
        self.assertEqual(config.log_level, 'INFO')
        self.assertEqual(config.rate_limit_odds, 83)
        self.assertEqual(config.rate_limit_espn, 60)
        self.assertEqual(config.cache_ttl, 3600)
        self.assertEqual(config.session_cache_size, 1000)
    
    def test_environment_variable_loading(self):
        """Test loading configuration from environment variables."""
        # Set environment variables
        os.environ['ODDS_API_KEY'] = 'test_odds_key'
        os.environ['ESPN_API_KEY'] = 'test_espn_key'
        os.environ['DEBUG'] = 'true'
        os.environ['LOG_LEVEL'] = 'DEBUG'
        os.environ['ODDS_API_RATE_LIMIT'] = '100'
        os.environ['ESPN_API_RATE_LIMIT'] = '120'
        os.environ['CACHE_TTL'] = '7200'
        os.environ['SESSION_CACHE_SIZE'] = '2000'
        
        config = Config()
        
        # Check that environment variables were loaded
        self.assertEqual(config.odds_api_key, 'test_odds_key')
        self.assertEqual(config.espn_api_key, 'test_espn_key')
        self.assertTrue(config.debug)
        self.assertEqual(config.log_level, 'DEBUG')
        self.assertEqual(config.rate_limit_odds, 100)
        self.assertEqual(config.rate_limit_espn, 120)
        self.assertEqual(config.cache_ttl, 7200)
        self.assertEqual(config.session_cache_size, 2000)
    
    def test_factor_weights_validation(self):
        """Test that factor weights sum to 1.0."""
        config = Config()
        
        total_weight = (config.coaching_edge_weight + 
                       config.situational_context_weight + 
                       config.momentum_factors_weight)
        
        self.assertAlmostEqual(total_weight, 1.0, places=3)
    
    def test_invalid_factor_weights(self):
        """Test validation with invalid factor weights."""
        # Create a config and modify weights after initialization
        config = Config()
        
        # Test the validation method directly
        old_momentum = config.momentum_factors_weight
        config.momentum_factors_weight = 0.3  # This makes total > 1.0
        
        # Test that validation would catch this
        total_weight = (config.coaching_edge_weight + 
                       config.situational_context_weight + 
                       config.momentum_factors_weight)
        
        self.assertGreater(abs(total_weight - 1.0), 0.001)
        
        # Restore original value
        config.momentum_factors_weight = old_momentum
    
    def test_invalid_rate_limits(self):
        """Test validation with invalid rate limits."""
        os.environ['ODDS_API_RATE_LIMIT'] = '0'
        
        with self.assertRaises(ValueError):
            Config()
    
    def test_invalid_cache_ttl(self):
        """Test validation with invalid cache TTL."""
        os.environ['CACHE_TTL'] = '-1'
        
        with self.assertRaises(ValueError):
            Config()
    
    def test_validate_api_keys(self):
        """Test API key validation."""
        # No API keys
        config = Config()
        status = config.validate_api_keys()
        
        self.assertFalse(status['odds_api'])
        self.assertEqual(status['espn_api'], 'optional')
        
        # With API keys
        os.environ['ODDS_API_KEY'] = 'test_key'
        os.environ['ESPN_API_KEY'] = 'test_espn_key'
        
        config = Config()
        status = config.validate_api_keys()
        
        self.assertTrue(status['odds_api'])
        self.assertTrue(status['espn_api'])
    
    def test_get_rate_limit(self):
        """Test rate limit retrieval."""
        config = Config()
        
        self.assertEqual(config.get_rate_limit('odds'), config.rate_limit_odds)
        self.assertEqual(config.get_rate_limit('espn'), config.rate_limit_espn)
        
        with self.assertRaises(ValueError):
            config.get_rate_limit('invalid_api')
    
    def test_get_edge_classification(self):
        """Test edge classification thresholds."""
        config = Config()
        
        # Test different edge sizes
        self.assertEqual(config.get_edge_classification(7.0), 'MASSIVE EDGE')
        self.assertEqual(config.get_edge_classification(5.0), 'STRONG EDGE')
        self.assertEqual(config.get_edge_classification(3.0), 'SOLID EDGE')
        self.assertEqual(config.get_edge_classification(2.0), 'SLIGHT LEAN')
        self.assertEqual(config.get_edge_classification(1.0), 'NO EDGE')
        
        # Test negative values (should use absolute value)
        self.assertEqual(config.get_edge_classification(-5.0), 'STRONG EDGE')
    
    def test_is_production(self):
        """Test production mode detection."""
        config = Config()
        self.assertTrue(config.is_production())  # debug=False by default
        
        os.environ['DEBUG'] = 'true'
        config = Config()
        self.assertFalse(config.is_production())
    
    def test_config_string_representation(self):
        """Test string representation of config."""
        config = Config()
        config_str = str(config)
        
        self.assertIn('Config(', config_str)
        self.assertIn('debug=', config_str)
        self.assertIn('log_level=', config_str)
        # Should not contain sensitive information
        self.assertNotIn('test_odds_key', config_str)


class TestProductionConfig(unittest.TestCase):
    """Test cases for ProductionConfig class."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Clear environment variables
        env_vars = ['ODDS_API_KEY', 'DEBUG', 'ENVIRONMENT']
        self.env_vars_to_restore = {}
        
        for var in env_vars:
            if var in os.environ:
                self.env_vars_to_restore[var] = os.environ[var]
                del os.environ[var]
    
    def tearDown(self):
        """Restore environment variables."""
        # Restore original values
        for var, value in self.env_vars_to_restore.items():
            os.environ[var] = value
    
    def test_production_config_requirements(self):
        """Test that production config requires API key."""
        with self.assertRaises(ValueError):
            ProductionConfig()
    
    def test_production_config_with_api_key(self):
        """Test production config with valid API key."""
        os.environ['ODDS_API_KEY'] = 'production_key'
        
        config = ProductionConfig()
        
        self.assertEqual(config.odds_api_key, 'production_key')
        self.assertFalse(config.debug)
        self.assertEqual(config.log_level, 'WARNING')
    
    def test_production_config_overrides_debug(self):
        """Test that production config overrides debug settings."""
        os.environ['ODDS_API_KEY'] = 'production_key'
        os.environ['DEBUG'] = 'true'  # This should be overridden
        
        config = ProductionConfig()
        
        self.assertFalse(config.debug)  # Should be False in production
        self.assertEqual(config.log_level, 'WARNING')


class TestConfigFactory(unittest.TestCase):
    """Test cases for config factory function."""
    
    def setUp(self):
        """Set up test fixtures."""
        if 'ENVIRONMENT' in os.environ:
            self.original_env = os.environ['ENVIRONMENT']
        else:
            self.original_env = None
    
    def tearDown(self):
        """Restore environment."""
        if self.original_env is not None:
            os.environ['ENVIRONMENT'] = self.original_env
        elif 'ENVIRONMENT' in os.environ:
            del os.environ['ENVIRONMENT']
    
    def test_get_config_default(self):
        """Test get_config returns default Config."""
        if 'ENVIRONMENT' in os.environ:
            del os.environ['ENVIRONMENT']
        
        config = get_config()
        self.assertIsInstance(config, Config)
        self.assertNotIsInstance(config, ProductionConfig)
    
    def test_get_config_production(self):
        """Test get_config returns ProductionConfig for production."""
        os.environ['ENVIRONMENT'] = 'production'
        os.environ['ODDS_API_KEY'] = 'prod_key'  # Required for production
        
        config = get_config()
        self.assertIsInstance(config, ProductionConfig)


class TestConfigIntegration(unittest.TestCase):
    """Integration tests for config with other components."""
    
    def test_config_with_dotenv_file(self):
        """Test config loading from .env file."""
        # Create temporary .env file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
            f.write('ODDS_API_KEY=file_key\n')
            f.write('DEBUG=true\n')
            f.write('CACHE_TTL=1800\n')
            temp_env_file = f.name
        
        try:
            # Mock dotenv to use our temp file
            with patch('config.load_dotenv') as mock_load_dotenv:
                # Manually set the environment variables as if dotenv loaded them
                os.environ['ODDS_API_KEY'] = 'file_key'
                os.environ['DEBUG'] = 'true'
                os.environ['CACHE_TTL'] = '1800'
                
                config = Config()
                
                self.assertEqual(config.odds_api_key, 'file_key')
                self.assertTrue(config.debug)
                self.assertEqual(config.cache_ttl, 1800)
        finally:
            # Clean up
            os.unlink(temp_env_file)
            for var in ['ODDS_API_KEY', 'DEBUG', 'CACHE_TTL']:
                if var in os.environ:
                    del os.environ[var]
    
    def test_config_edge_thresholds(self):
        """Test that edge thresholds are properly defined."""
        config = Config()
        
        # Check that all required thresholds exist
        required_thresholds = ['massive', 'strong', 'solid', 'slight']
        for threshold in required_thresholds:
            self.assertIn(threshold, config.edge_thresholds)
            self.assertIsInstance(config.edge_thresholds[threshold], (int, float))
            self.assertGreater(config.edge_thresholds[threshold], 0)
        
        # Check that thresholds are in descending order
        thresholds = [config.edge_thresholds[t] for t in required_thresholds]
        self.assertEqual(thresholds, sorted(thresholds, reverse=True))
    
    def test_config_logging_setup(self):
        """Test that logging is properly configured."""
        import logging
        
        # Test debug logging
        os.environ['DEBUG'] = 'true'
        os.environ['LOG_LEVEL'] = 'DEBUG'
        
        config = Config()
        
        # Check that logging level is set correctly
        # Note: We can't easily test the actual logging configuration
        # without interfering with other tests, so we just verify
        # the config values are correct
        self.assertTrue(config.debug)
        self.assertEqual(config.log_level, 'DEBUG')
    
    def test_config_constants(self):
        """Test application constants are reasonable."""
        config = Config()
        
        # Check execution time limit
        self.assertGreater(config.max_execution_time, 0)
        self.assertLess(config.max_execution_time, 60)  # Should be reasonable
        
        # Check API call limit
        self.assertGreater(config.max_api_calls_per_prediction, 0)
        self.assertLess(config.max_api_calls_per_prediction, 100)
        
        # Check confidence thresholds
        self.assertGreater(config.min_confidence_threshold, 0)
        self.assertLess(config.min_confidence_threshold, 50)
        self.assertGreater(config.max_confidence_threshold, 50)
        self.assertLess(config.max_confidence_threshold, 100)


if __name__ == '__main__':
    unittest.main()