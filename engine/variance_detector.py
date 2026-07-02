"""
Variance Detection System for College Football Market Edge Platform.

Identifies games where factors strongly disagree, indicating:
1. High uncertainty / unpredictable games
2. Potential value opportunities when consensus is wrong
3. Games to avoid due to conflicting signals
4. Games where specific factor categories diverge
"""

import logging
from typing import Dict, Any, List, Tuple, Optional
import statistics
from enum import Enum


class VarianceLevel(Enum):
    """Variance levels for factor disagreement."""
    CONSENSUS = "consensus"          # Factors agree (low variance)
    MILD_DISAGREEMENT = "mild"       # Some disagreement
    MODERATE_DISAGREEMENT = "moderate"  # Notable disagreement
    STRONG_DISAGREEMENT = "strong"   # Significant disagreement
    EXTREME_DISAGREEMENT = "extreme" # Factors completely split


class VarianceDetector:
    """
    Analyzes factor variance to identify games with high disagreement.
    
    High variance can indicate:
    - Market inefficiency (opportunity)
    - High uncertainty (risk)
    - Conflicting narratives (avoid or smaller bet)
    """
    
    def __init__(self):
        """Initialize variance detector."""
        self.logger = logging.getLogger(__name__)
        
        # Variance thresholds
        self.thresholds = {
            'consensus': 0.15,         # Below this = consensus
            'mild': 0.30,              # Mild disagreement
            'moderate': 0.50,          # Moderate disagreement  
            'strong': 0.75,            # Strong disagreement
            'extreme': 1.0             # Above this = extreme split
        }
        
        # Category groupings for analysis
        self.factor_categories = {
            'market': ['MarketSentiment'],
            'statistical': ['StyleMismatch', 'PointDifferentialTrends', 'CloseGamePerformance'],
            'situational': ['DesperationIndex', 'RevengeGame', 'LookaheadSandwich', 'SchedulingFatigue'],
            'coaching': ['ExperienceDifferential', 'PressureSituation', 'HeadToHeadRecord']
        }
    
    def analyze_factor_variance(self, factor_results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze variance across all factors for a game.
        
        Args:
            factor_results: Dictionary of factor calculation results
            
        Returns:
            Dictionary with variance analysis
        """
        # Extract active factor values
        active_factors = self._extract_active_factors(factor_results)
        
        if len(active_factors) < 3:
            return self._create_insufficient_data_result()
        
        # Calculate overall variance metrics
        values = [f['value'] for f in active_factors]
        overall_variance = self._calculate_variance_metrics(values)
        
        # Analyze directional agreement
        directional_analysis = self._analyze_directional_agreement(active_factors)
        
        # Category-level variance
        category_variance = self._analyze_category_variance(active_factors)
        
        # Identify outlier factors
        outlier_factors = self._identify_outlier_factors(active_factors, overall_variance)
        
        # Determine variance level and implications
        variance_level = self._determine_variance_level(overall_variance['coefficient_of_variation'])
        implications = self._interpret_variance_implications(
            variance_level, directional_analysis, category_variance
        )
        
        return {
            'variance_level': variance_level.value,
            'overall_metrics': overall_variance,
            'directional_agreement': directional_analysis,
            'category_variance': category_variance,
            'outlier_factors': outlier_factors,
            'implications': implications,
            'factors_analyzed': len(active_factors),
            'recommendation': self._generate_recommendation(variance_level, directional_analysis)
        }
    
    def _extract_active_factors(self, factor_results: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract successfully calculated and activated factors."""
        active_factors = []
        
        factors_dict = factor_results.get('factors', {})
        
        for factor_name, factor_data in factors_dict.items():
            if (factor_data.get('success') and 
                factor_data.get('activated') and 
                factor_data.get('value') is not None):
                
                active_factors.append({
                    'name': factor_name,
                    'value': factor_data['value'],
                    'weight': factor_data.get('weight', 0.0),
                    'weighted_value': factor_data.get('weighted_value', 0.0),
                    'confidence': factor_data.get('confidence', 'NONE'),
                    'category': self._get_factor_category(factor_name),
                    'is_primary': factor_data.get('factor_type') == 'PRIMARY'
                })
        
        return active_factors
    
    def _calculate_variance_metrics(self, values: List[float]) -> Dict[str, float]:
        """Calculate variance metrics for factor values."""
        if not values:
            return {'mean': 0, 'std_dev': 0, 'variance': 0, 'coefficient_of_variation': 0, 'range': 0}
        
        mean_val = statistics.mean(values)
        
        # Handle edge case where all values are zero
        if all(v == 0 for v in values):
            return {'mean': 0, 'std_dev': 0, 'variance': 0, 'coefficient_of_variation': 0, 'range': 0}
        
        if len(values) > 1:
            std_dev = statistics.stdev(values)
            variance = statistics.variance(values)
        else:
            std_dev = 0
            variance = 0
        
        # Coefficient of variation (normalized measure)
        # Use absolute mean to handle negative values properly
        if mean_val != 0:
            cv = abs(std_dev / mean_val)
        else:
            cv = std_dev  # If mean is 0, use std_dev directly
        
        value_range = max(values) - min(values)
        
        return {
            'mean': mean_val,
            'std_dev': std_dev,
            'variance': variance,
            'coefficient_of_variation': cv,
            'range': value_range
        }
    
    def _analyze_directional_agreement(self, factors: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze whether factors agree on direction (positive/negative)."""
        positive = [f for f in factors if f['value'] > 0]
        negative = [f for f in factors if f['value'] < 0]
        neutral = [f for f in factors if f['value'] == 0]
        
        total = len(factors)
        
        # Calculate directional consensus
        if len(positive) >= total * 0.7:
            direction_consensus = 'strong_positive'
        elif len(negative) >= total * 0.7:
            direction_consensus = 'strong_negative'
        elif len(positive) >= total * 0.5:
            direction_consensus = 'lean_positive'
        elif len(negative) >= total * 0.5:
            direction_consensus = 'lean_negative'
        else:
            direction_consensus = 'mixed'
        
        # Check for complete disagreement (primary factors opposing)
        primary_factors = [f for f in factors if f['is_primary']]
        primary_disagreement = False
        
        if len(primary_factors) >= 2:
            primary_pos = [f for f in primary_factors if f['value'] > 0]
            primary_neg = [f for f in primary_factors if f['value'] < 0]
            if primary_pos and primary_neg:
                primary_disagreement = True
        
        return {
            'positive_count': len(positive),
            'negative_count': len(negative),
            'neutral_count': len(neutral),
            'consensus': direction_consensus,
            'primary_disagreement': primary_disagreement,
            'agreement_ratio': max(len(positive), len(negative)) / total if total > 0 else 0
        }
    
    def _analyze_category_variance(self, factors: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze variance within factor categories."""
        category_analysis = {}
        
        for category_name, category_factors in self.factor_categories.items():
            cat_factors = [f for f in factors if f['name'] in category_factors]
            
            if cat_factors:
                cat_values = [f['value'] for f in cat_factors]
                cat_metrics = self._calculate_variance_metrics(cat_values)
                
                category_analysis[category_name] = {
                    'factor_count': len(cat_factors),
                    'mean': cat_metrics['mean'],
                    'std_dev': cat_metrics['std_dev'],
                    'consensus': cat_metrics['coefficient_of_variation'] < 0.3
                }
        
        # Check for inter-category disagreement
        if len(category_analysis) >= 2:
            category_means = [v['mean'] for v in category_analysis.values()]
            inter_category_variance = self._calculate_variance_metrics(category_means)
            category_analysis['inter_category_variance'] = inter_category_variance['coefficient_of_variation']
        
        return category_analysis
    
    def _identify_outlier_factors(self, factors: List[Dict[str, Any]], 
                                  overall_metrics: Dict[str, float]) -> List[Dict[str, Any]]:
        """Identify factors that significantly deviate from consensus."""
        outliers = []
        
        mean = overall_metrics['mean']
        std_dev = overall_metrics['std_dev']
        
        if std_dev == 0:
            return []  # No outliers if no variance
        
        for factor in factors:
            # Calculate z-score
            z_score = (factor['value'] - mean) / std_dev if std_dev > 0 else 0
            
            # Consider outlier if |z-score| > 1.5
            if abs(z_score) > 1.5:
                outliers.append({
                    'name': factor['name'],
                    'value': factor['value'],
                    'z_score': z_score,
                    'deviation': factor['value'] - mean,
                    'category': factor['category']
                })
        
        # Sort by absolute z-score
        outliers.sort(key=lambda x: abs(x['z_score']), reverse=True)
        
        return outliers
    
    def _determine_variance_level(self, cv: float) -> VarianceLevel:
        """Determine variance level based on coefficient of variation."""
        if cv < self.thresholds['consensus']:
            return VarianceLevel.CONSENSUS
        elif cv < self.thresholds['mild']:
            return VarianceLevel.MILD_DISAGREEMENT
        elif cv < self.thresholds['moderate']:
            return VarianceLevel.MODERATE_DISAGREEMENT
        elif cv < self.thresholds['strong']:
            return VarianceLevel.STRONG_DISAGREEMENT
        else:
            return VarianceLevel.EXTREME_DISAGREEMENT
    
    def _interpret_variance_implications(self, variance_level: VarianceLevel,
                                        directional: Dict[str, Any],
                                        category: Dict[str, Any]) -> List[str]:
        """Interpret what the variance means for betting decisions."""
        implications = []
        
        # Variance level implications
        if variance_level == VarianceLevel.CONSENSUS:
            implications.append("Strong factor agreement - high confidence signal")
        elif variance_level == VarianceLevel.MILD_DISAGREEMENT:
            implications.append("Mild factor disagreement - proceed with standard confidence")
        elif variance_level == VarianceLevel.MODERATE_DISAGREEMENT:
            implications.append("Moderate disagreement - consider reducing bet size")
        elif variance_level == VarianceLevel.STRONG_DISAGREEMENT:
            implications.append("Strong disagreement - high uncertainty, reduce exposure")
        else:  # EXTREME
            implications.append("Extreme disagreement - avoid or minimum bet only")
        
        # Directional implications
        if directional['primary_disagreement']:
            implications.append("Primary factors disagree - fundamental conflict in analysis")
        
        if directional['consensus'] == 'mixed':
            implications.append("No directional consensus - factors pulling both ways")
        elif directional['consensus'] in ['strong_positive', 'strong_negative']:
            implications.append(f"Strong directional agreement ({directional['consensus']})")
        
        # Category implications
        inter_cat_var = category.get('inter_category_variance', 0)
        if inter_cat_var > 0.5:
            implications.append("Categories disagree - different analytical methods conflict")
        
        # Check for specific category patterns
        if 'market' in category and category['market'].get('consensus', False):
            if 'statistical' in category and not category['statistical'].get('consensus', True):
                implications.append("Market factors agree but stats disagree - potential trap")
        
        return implications
    
    def _generate_recommendation(self, variance_level: VarianceLevel,
                                directional: Dict[str, Any]) -> Dict[str, Any]:
        """Generate betting recommendation based on variance analysis."""
        
        # Base recommendations on variance level
        if variance_level == VarianceLevel.CONSENSUS:
            confidence = "HIGH"
            bet_adjustment = 1.0  # Full bet
            action = "PROCEED"
        elif variance_level == VarianceLevel.MILD_DISAGREEMENT:
            confidence = "MEDIUM"
            bet_adjustment = 0.9
            action = "PROCEED"
        elif variance_level == VarianceLevel.MODERATE_DISAGREEMENT:
            confidence = "LOW"
            bet_adjustment = 0.7
            action = "PROCEED_CAUTIOUSLY"
        elif variance_level == VarianceLevel.STRONG_DISAGREEMENT:
            confidence = "VERY_LOW"
            bet_adjustment = 0.5
            action = "REDUCE_EXPOSURE"
        else:  # EXTREME
            confidence = "NO_CONFIDENCE"
            bet_adjustment = 0.25
            action = "AVOID_OR_MINIMUM"
        
        # Adjust for directional agreement
        if directional['primary_disagreement']:
            bet_adjustment *= 0.7
            confidence = "VERY_LOW"
        elif directional['agreement_ratio'] > 0.8:
            bet_adjustment = min(1.0, bet_adjustment * 1.1)
        
        return {
            'action': action,
            'confidence': confidence,
            'bet_size_adjustment': bet_adjustment,
            'reasoning': self._explain_recommendation(variance_level, directional)
        }
    
    def _explain_recommendation(self, variance_level: VarianceLevel,
                               directional: Dict[str, Any]) -> str:
        """Explain the recommendation in plain language."""
        if variance_level == VarianceLevel.CONSENSUS:
            return "Factors strongly agree, indicating a high-confidence opportunity"
        elif variance_level == VarianceLevel.EXTREME_DISAGREEMENT:
            return "Extreme factor disagreement suggests avoiding this game"
        elif directional['primary_disagreement']:
            return "Primary factors disagree, indicating fundamental uncertainty"
        elif variance_level == VarianceLevel.MODERATE_DISAGREEMENT:
            return "Moderate disagreement suggests reducing bet size for risk management"
        else:
            return f"Factor variance at {variance_level.value} level"
    
    def _get_factor_category(self, factor_name: str) -> str:
        """Determine which category a factor belongs to."""
        for category, factors in self.factor_categories.items():
            if factor_name in factors:
                return category
        return 'other'
    
    def _create_insufficient_data_result(self) -> Dict[str, Any]:
        """Create result when insufficient factors for variance analysis."""
        return {
            'variance_level': 'insufficient_data',
            'overall_metrics': None,
            'directional_agreement': None,
            'category_variance': None,
            'outlier_factors': [],
            'implications': ["Insufficient active factors for variance analysis"],
            'factors_analyzed': 0,
            'recommendation': {
                'action': 'INSUFFICIENT_DATA',
                'confidence': 'NONE',
                'bet_size_adjustment': 0.5,
                'reasoning': 'Not enough factors activated for variance analysis'
            }
        }


# Singleton instance
variance_detector = VarianceDetector()