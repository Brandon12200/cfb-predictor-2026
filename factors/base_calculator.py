"""
Base factor calculator abstract class for College Football Market Edge Platform.
All factor calculators must inherit from this class to ensure consistent interface.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Tuple, Optional, List
from enum import Enum
import logging


class FactorType(Enum):
    """Factor type classification for hierarchical system."""
    PRIMARY = "primary"      # Strong contrarian signals (high weight)
    SECONDARY = "secondary"  # Supporting factors (medium weight)
    TRIGGER = "trigger"      # Conditional factors that only apply in specific situations
    MODIFIER = "modifier"    # Multiplicative factors that enhance other signals


class FactorConfidence(Enum):
    """Confidence levels for factor signals."""
    VERY_HIGH = 0.9   # Extremely confident contrarian signal
    HIGH = 0.75       # Strong signal
    MEDIUM = 0.5      # Moderate signal
    LOW = 0.25        # Weak signal
    NONE = 0.0        # No confidence/neutral


class BaseFactorCalculator(ABC):
    """
    Abstract base class for all factor calculators.
    
    All factor implementations must inherit from this class and implement
    the required methods. This ensures consistent interface and behavior
    across all factors in the prediction engine.
    """
    
    def __init__(self):
        """Initialize base calculator with common properties."""
        self.weight = 0.0  # Default weight, overridden by subclasses
        self.category = "unknown"  # Factor category (coaching, situational, momentum)
        self.description = "Base factor calculator"  # Human-readable description
        self.name = self.__class__.__name__.replace('Calculator', '').replace('Factor', '')
        
        # Enhanced properties for dynamic weighting
        self.factor_type = FactorType.SECONDARY  # Default to secondary
        self.activation_threshold = 0.5  # Minimum absolute value to activate
        self.max_impact = 5.0  # Maximum adjustment this factor can make
        self.is_multiplicative = False  # Whether this factor multiplies vs adds
        
        # Logging
        self.logger = logging.getLogger(f"factors.{self.name.lower()}")
        
        # Output range - subclasses should override
        self._min_output = -5.0
        self._max_output = 5.0
        
        # Factor-specific configuration
        self.config = {}
        
        self.logger.debug(f"Initialized {self.name} factor calculator")
    
    @abstractmethod
    def calculate(self, home_team: str, away_team: str, context: Optional[Dict[str, Any]] = None) -> float:
        """
        Calculate the factor adjustment for a given matchup.
        
        Args:
            home_team: Normalized home team name
            away_team: Normalized away team name
            context: Optional context data (game data, week info, etc.)
            
        Returns:
            Float adjustment value within the factor's output range
            Positive values favor the home team
            Negative values favor the away team
            
        Raises:
            ValueError: If teams are invalid or calculation fails
        """
        pass
    
    @abstractmethod
    def get_output_range(self) -> Tuple[float, float]:
        """
        Get the minimum and maximum possible output values for this factor.
        
        Returns:
            Tuple of (min_value, max_value)
        """
        pass
    
    def calculate_with_confidence(self, home_team: str, away_team: str, 
                                 context: Optional[Dict[str, Any]] = None) -> Tuple[float, FactorConfidence, List[str]]:
        """
        Calculate factor with confidence score and reasoning.
        Default implementation for backward compatibility.
        
        Args:
            home_team: Normalized home team name
            away_team: Normalized away team name
            context: Game context data
            
        Returns:
            Tuple of (adjustment_value, confidence, reasoning_list)
        """
        # Default implementation uses standard calculate and returns medium confidence
        value = self.calculate(home_team, away_team, context)
        
        # Determine confidence based on value magnitude
        abs_value = abs(value)
        if abs_value >= 3.0:
            confidence = FactorConfidence.HIGH
        elif abs_value >= 1.5:
            confidence = FactorConfidence.MEDIUM
        elif abs_value >= 0.5:
            confidence = FactorConfidence.LOW
        else:
            confidence = FactorConfidence.NONE
        
        reasoning = [f"Factor value: {value:.2f}"]
        return value, confidence, reasoning
    
    def get_factor_info(self) -> Dict[str, Any]:
        """
        Get comprehensive information about this factor.
        
        Returns:
            Dictionary with factor metadata
        """
        min_val, max_val = self.get_output_range()
        
        return {
            'name': self.name,
            'weight': self.weight,
            'category': self.category,
            'description': self.description,
            'output_range': {
                'min': min_val,
                'max': max_val
            },
            'class_name': self.__class__.__name__,
            'config': self.config
        }
    
    def validate_teams(self, home_team: str, away_team: str) -> None:
        """
        Validate team inputs for factor calculation.
        
        Args:
            home_team: Normalized home team name
            away_team: Normalized away team name
            
        Raises:
            ValueError: If teams are invalid
        """
        if not home_team or not away_team:
            raise ValueError("Both home and away teams must be provided")
        
        if home_team == away_team:
            raise ValueError("Home and away teams cannot be the same")
        
        if not isinstance(home_team, str) or not isinstance(away_team, str):
            raise ValueError("Team names must be strings")
    
    def validate_output(self, value: float) -> float:
        """
        Validate and clamp output value to acceptable range.
        
        Args:
            value: Calculated factor value
            
        Returns:
            Validated and clamped value
        """
        if not isinstance(value, (int, float)):
            self.logger.warning(f"Factor {self.name} returned non-numeric value: {value}")
            return 0.0
        
        min_val, max_val = self.get_output_range()
        
        if value < min_val:
            self.logger.warning(f"Factor {self.name} output {value} below minimum {min_val}, clamping")
            return min_val
        elif value > max_val:
            self.logger.warning(f"Factor {self.name} output {value} above maximum {max_val}, clamping")
            return max_val
        
        return float(value)
    
    def apply_threshold(self, value: float) -> float:
        """
        Apply activation threshold to factor value.
        
        If absolute value is below threshold, return 0.
        """
        if abs(value) < self.activation_threshold:
            self.logger.debug(f"Factor {self.name} below threshold: {abs(value):.3f} < {self.activation_threshold}")
            return 0.0
        return value
    
    def get_dynamic_weight(self, confidence: FactorConfidence) -> float:
        """
        Calculate dynamic weight based on confidence level.
        
        Higher confidence = higher weight contribution.
        """
        if self.factor_type == FactorType.PRIMARY:
            # Primary factors maintain higher weights even with lower confidence
            return self.weight * max(confidence.value, 0.5)
        elif self.factor_type == FactorType.SECONDARY:
            # Secondary factors scale more with confidence
            return self.weight * confidence.value
        elif self.factor_type == FactorType.TRIGGER:
            # Trigger factors use full weight when activated
            return self.weight if confidence != FactorConfidence.NONE else 0.0
        else:  # MODIFIER
            # Modifiers return their multiplier effect
            return 1.0
    
    def safe_calculate(self, home_team: str, away_team: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Safely calculate factor with comprehensive error handling.
        Enhanced with confidence scoring and dynamic weighting.
        
        Args:
            home_team: Normalized home team name
            away_team: Normalized away team name
            context: Optional context data
            
        Returns:
            Dictionary with calculation results and metadata
        """
        result = {
            'factor_name': self.name,
            'factor_type': self.factor_type.value,
            'home_team': home_team,
            'away_team': away_team,
            'value': 0.0,
            'raw_value': 0.0,
            'confidence': FactorConfidence.NONE,
            'success': False,
            'error': None,
            'weight': self.weight,
            'dynamic_weight': 0.0,
            'weighted_value': 0.0,
            'explanation': None,
            'reasoning': [],
            'is_multiplicative': self.is_multiplicative,
            'activated': False
        }
        
        try:
            # Validate inputs
            self.validate_teams(home_team, away_team)
            
            # Calculate factor value with confidence
            raw_value, confidence, reasoning = self.calculate_with_confidence(home_team, away_team, context)
            
            # Store raw value before threshold
            result['raw_value'] = raw_value
            
            # Apply threshold
            threshold_value = self.apply_threshold(raw_value)
            
            # Check if factor activated after threshold
            if threshold_value == 0.0 and raw_value != 0.0:
                result['reasoning'] = [f"Below activation threshold ({self.activation_threshold})"]
                result['success'] = True
                return result
            
            # Validate and clamp output
            validated_value = self.validate_output(threshold_value)
            
            # Calculate dynamic weight based on confidence
            dynamic_weight = self.get_dynamic_weight(confidence)
            
            # Calculate weighted contribution
            if self.is_multiplicative:
                # For multiplicative factors, store as multiplier
                weighted_value = 1.0 + (validated_value * dynamic_weight / self.max_impact)
            else:
                weighted_value = validated_value * dynamic_weight
            
            # Generate explanation if available
            explanation = self.get_explanation(home_team, away_team, validated_value, context)
            
            result.update({
                'value': validated_value,
                'confidence': confidence,
                'success': True,
                'dynamic_weight': dynamic_weight,
                'weighted_value': weighted_value,
                'explanation': explanation,
                'reasoning': reasoning,
                'activated': True
            })
            
            self.logger.debug(
                f"Factor {self.name}: {away_team} @ {home_team} = {validated_value:.3f} "
                f"(confidence: {confidence.name}, weight: {dynamic_weight:.3f})"
            )
            
        except Exception as e:
            self.logger.error(f"Error calculating factor {self.name}: {e}")
            result['error'] = str(e)
        
        return result
    
    def get_explanation(self, home_team: str, away_team: str, value: float, 
                       context: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """
        Generate human-readable explanation for the factor calculation.
        
        This is optional - subclasses can override to provide detailed explanations.
        
        Args:
            home_team: Normalized home team name
            away_team: Normalized away team name
            value: Calculated factor value
            context: Optional context data
            
        Returns:
            Human-readable explanation string or None
        """
        if abs(value) < 0.1:
            return f"{self.name}: Neutral impact"
        elif value > 0:
            return f"{self.name}: Favors {home_team} (+{value:.1f})"
        else:
            return f"{self.name}: Favors {away_team} ({value:.1f})"
    
    def get_required_data(self) -> Dict[str, bool]:
        """
        Get information about what data this factor requires.
        
        Returns:
            Dictionary mapping data types to whether they're required (True) or optional (False)
        """
        return {
            'team_info': False,
            'coaching_data': False,
            'team_stats': False,
            'schedule_data': False,
            'betting_data': False,
            'historical_data': False
        }
    
    def can_calculate(self, context: Optional[Dict[str, Any]] = None) -> Tuple[bool, str]:
        """
        Check if this factor can be calculated with available data.
        
        Args:
            context: Game context with available data
            
        Returns:
            Tuple of (can_calculate, reason_if_not)
        """
        if not context:
            return False, "No context data provided"
        
        required_data = self.get_required_data()
        
        for data_type, is_required in required_data.items():
            if is_required and not self._has_data(context, data_type):
                return False, f"Missing required data: {data_type}"
        
        return True, "All requirements met"
    
    def _has_data(self, context: Dict[str, Any], data_type: str) -> bool:
        """Check if specific data type is available in context."""
        data_mappings = {
            'team_info': lambda ctx: bool(ctx.get('home_team_data', {}).get('info')) and bool(ctx.get('away_team_data', {}).get('info')),
            'coaching_data': lambda ctx: bool(ctx.get('coaching_comparison')),
            'team_stats': lambda ctx: bool(ctx.get('home_team_data', {}).get('stats')) and bool(ctx.get('away_team_data', {}).get('stats')),
            'schedule_data': lambda ctx: bool(ctx.get('home_team_data', {}).get('schedule')) and bool(ctx.get('away_team_data', {}).get('schedule')),
            'betting_data': lambda ctx: ctx.get('vegas_spread') is not None,
            'historical_data': lambda ctx: False  # Not implemented yet
        }
        
        check_function = data_mappings.get(data_type, lambda ctx: True)
        return check_function(context)
    
    def __str__(self) -> str:
        """String representation of the factor."""
        return f"{self.name}Factor(weight={self.weight:.3f}, category={self.category})"
    
    def __repr__(self) -> str:
        """Detailed string representation."""
        min_val, max_val = self.get_output_range()
        return f"{self.__class__.__name__}(weight={self.weight}, range=[{min_val}, {max_val}])"