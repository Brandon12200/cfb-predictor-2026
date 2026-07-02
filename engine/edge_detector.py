"""
Edge detector for College Football Market Edge Platform.
Identifies and classifies contrarian betting opportunities.
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from enum import Enum

from config import config


class EdgeType(Enum):
    """Types of contrarian edges."""
    STRONG_CONTRARIAN = "strong_contrarian"
    MODERATE_CONTRARIAN = "moderate_contrarian"
    SLIGHT_CONTRARIAN = "slight_contrarian"
    CONSENSUS_PLAY = "consensus_play"
    NO_EDGE = "no_edge"
    INSUFFICIENT_DATA = "insufficient_data"


class EdgeClassification:
    """Classification of a detected edge."""
    
    def __init__(self, edge_type: EdgeType, edge_size: float, confidence: float,
                 explanation: str, recommended_action: str):
        self.edge_type = edge_type
        self.edge_size = edge_size
        self.confidence = confidence
        self.explanation = explanation
        self.recommended_action = recommended_action


class EdgeDetector:
    """
    Detects and classifies contrarian betting opportunities.
    
    The detector analyzes prediction results to identify situations where
    our contrarian analysis suggests a meaningful edge over market consensus.
    """
    
    def __init__(self):
        """Initialize edge detector."""
        # Edge detection thresholds
        self.edge_thresholds = {
            'strong_contrarian': 3.0,      # 3+ point edge
            'moderate_contrarian': 2.0,    # 2-3 point edge
            'slight_contrarian': 1.0,      # 1-2 point edge
            'minimal_edge': 0.5            # 0.5-1 point edge
        }
        
        # Confidence thresholds for recommendations
        self.confidence_thresholds = {
            'high_confidence': 0.75,
            'medium_confidence': 0.60,
            'low_confidence': 0.45
        }
        
        # Risk management parameters
        self.risk_parameters = {
            'max_recommended_edge': 5.0,   # Don't recommend edges > 5 points (likely data error)
            'min_confidence_for_action': 0.40,  # Minimum confidence to recommend action
            'data_quality_threshold': 0.30      # Minimum data quality for recommendations
        }
        
        # Logging
        self.logger = logging.getLogger(__name__)
        
        self.logger.debug("Edge detector initialized")
    
    def detect_edge(self, prediction_result: Dict[str, Any], 
                   confidence_assessment: Dict[str, Any],
                   context: Dict[str, Any]) -> EdgeClassification:
        """
        Detect and classify contrarian edges from prediction results.
        
        Args:
            prediction_result: Results from prediction engine
            confidence_assessment: Confidence analysis results
            context: Game context and data
            
        Returns:
            EdgeClassification with detected edge information
        """
        # Extract key metrics
        edge_size = prediction_result.get('edge_size', 0.0)
        # Handle None edge size
        if edge_size is None:
            edge_size = 0.0
        vegas_spread = prediction_result.get('vegas_spread')
        contrarian_spread = prediction_result.get('contrarian_spread')
        prediction_type = prediction_result.get('prediction_type', 'UNKNOWN')
        
        confidence_score = confidence_assessment.get('confidence_score', 0.0)
        # Handle None confidence score
        if confidence_score is None:
            confidence_score = 0.0
        data_quality = context.get('data_quality', 0.0)
        
        # Perform edge detection
        edge_classification = self._classify_edge_size(edge_size)
        
        # Validate edge with risk management checks
        validated_edge = self._validate_edge(
            edge_classification, edge_size, confidence_score, 
            data_quality, vegas_spread, contrarian_spread
        )
        
        # Generate recommendation
        recommendation = self._generate_recommendation(
            validated_edge, edge_size, confidence_score, 
            prediction_result, confidence_assessment
        )
        
        # Create detailed explanation
        explanation = self._generate_explanation(
            validated_edge, edge_size, confidence_score, 
            prediction_result, confidence_assessment, context
        )
        
        self.logger.debug(f"Edge detected: {validated_edge.name} ({edge_size:.2f} points, {confidence_score:.1%} confidence)")
        
        return EdgeClassification(
            edge_type=validated_edge,
            edge_size=edge_size,
            confidence=confidence_score,
            explanation=explanation,
            recommended_action=recommendation
        )
    
    def _classify_edge_size(self, edge_size: float) -> EdgeType:
        """Classify edge based on size thresholds."""
        # Handle None or invalid edge size
        if edge_size is None or not isinstance(edge_size, (int, float)):
            return EdgeType.INSUFFICIENT_DATA
            
        edge_size = abs(edge_size)  # Use absolute value for classification
        
        if edge_size >= self.edge_thresholds['strong_contrarian']:
            return EdgeType.STRONG_CONTRARIAN
        elif edge_size >= self.edge_thresholds['moderate_contrarian']:
            return EdgeType.MODERATE_CONTRARIAN
        elif edge_size >= self.edge_thresholds['slight_contrarian']:
            return EdgeType.SLIGHT_CONTRARIAN
        elif edge_size >= self.edge_thresholds['minimal_edge']:
            return EdgeType.CONSENSUS_PLAY
        else:
            return EdgeType.NO_EDGE
    
    def _validate_edge(self, initial_classification: EdgeType, edge_size: float,
                      confidence_score: float, data_quality: float,
                      vegas_spread: Optional[float], contrarian_spread: Optional[float]) -> EdgeType:
        """Validate edge classification with risk management checks."""
        
        # Check for insufficient data
        if vegas_spread is None or contrarian_spread is None:
            return EdgeType.INSUFFICIENT_DATA
        
        if data_quality < self.risk_parameters['data_quality_threshold']:
            return EdgeType.INSUFFICIENT_DATA
        
        # Check for suspiciously large edges (likely data errors)
        if edge_size > self.risk_parameters['max_recommended_edge']:
            self.logger.warning(f"Suspiciously large edge detected: {edge_size:.2f} points")
            return EdgeType.INSUFFICIENT_DATA
        
        # Downgrade edge classification based on confidence
        if confidence_score < self.confidence_thresholds['low_confidence']:
            if initial_classification in [EdgeType.STRONG_CONTRARIAN, EdgeType.MODERATE_CONTRARIAN]:
                return EdgeType.SLIGHT_CONTRARIAN
            elif initial_classification == EdgeType.SLIGHT_CONTRARIAN:
                return EdgeType.CONSENSUS_PLAY
        
        elif confidence_score < self.confidence_thresholds['medium_confidence']:
            if initial_classification == EdgeType.STRONG_CONTRARIAN:
                return EdgeType.MODERATE_CONTRARIAN
        
        return initial_classification
    
    def _generate_recommendation(self, edge_type: EdgeType, edge_size: float,
                               confidence_score: float, prediction_result: Dict[str, Any],
                               confidence_assessment: Dict[str, Any]) -> str:
        """Generate betting recommendation based on edge classification."""
        
        if edge_type == EdgeType.INSUFFICIENT_DATA:
            return "AVOID - Insufficient data for reliable prediction"
        
        if confidence_score < self.risk_parameters['min_confidence_for_action']:
            return "AVOID - Confidence too low for recommended action"
        
        edge_direction = prediction_result.get('edge_direction', 'neutral')
        home_team = prediction_result.get('home_team', 'Home')
        away_team = prediction_result.get('away_team', 'Away')
        
        # Determine favored team
        if edge_direction == 'home':
            favored_team = home_team
            side = "home"
        elif edge_direction == 'away':
            favored_team = away_team
            side = "away"
        else:
            return "NEUTRAL - No clear contrarian advantage identified"
        
        # Generate recommendation based on edge strength
        if edge_type == EdgeType.STRONG_CONTRARIAN:
            if confidence_score >= self.confidence_thresholds['high_confidence']:
                return f"STRONG BUY - {favored_team} ({side}) - {edge_size:.1f} point edge with high confidence"
            else:
                return f"BUY - {favored_team} ({side}) - {edge_size:.1f} point edge with medium confidence"
        
        elif edge_type == EdgeType.MODERATE_CONTRARIAN:
            if confidence_score >= self.confidence_thresholds['medium_confidence']:
                return f"BUY - {favored_team} ({side}) - {edge_size:.1f} point edge"
            else:
                return f"LEAN - {favored_team} ({side}) - {edge_size:.1f} point edge, moderate confidence"
        
        elif edge_type == EdgeType.SLIGHT_CONTRARIAN:
            return f"LEAN - {favored_team} ({side}) - {edge_size:.1f} point slight edge"
        
        elif edge_type == EdgeType.CONSENSUS_PLAY:
            return "CONSENSUS - Consider market consensus, minimal contrarian edge"
        
        else:
            return "PASS - No meaningful contrarian opportunity"
    
    def _generate_explanation(self, edge_type: EdgeType, edge_size: float,
                            confidence_score: float, prediction_result: Dict[str, Any],
                            confidence_assessment: Dict[str, Any], context: Dict[str, Any]) -> str:
        """Generate detailed explanation of the edge detection."""
        
        explanation_parts = []
        
        # Edge classification explanation
        if edge_type == EdgeType.STRONG_CONTRARIAN:
            explanation_parts.append(f"Strong contrarian opportunity identified with {edge_size:.1f} point edge.")
        elif edge_type == EdgeType.MODERATE_CONTRARIAN:
            explanation_parts.append(f"Moderate contrarian opportunity with {edge_size:.1f} point edge.")
        elif edge_type == EdgeType.SLIGHT_CONTRARIAN:
            explanation_parts.append(f"Slight contrarian edge of {edge_size:.1f} points detected.")
        elif edge_type == EdgeType.CONSENSUS_PLAY:
            explanation_parts.append(f"Minimal edge ({edge_size:.1f} points) aligns mostly with market consensus.")
        elif edge_type == EdgeType.NO_EDGE:
            explanation_parts.append("No meaningful contrarian edge identified.")
        else:
            explanation_parts.append("Insufficient data quality for reliable edge detection.")
        
        # Confidence explanation
        confidence_level = confidence_assessment.get('confidence_level', 'Unknown')
        explanation_parts.append(f"Prediction confidence: {confidence_level} ({confidence_score:.1%}).")
        
        # Key factors contributing to edge
        category_adjustments = prediction_result.get('category_adjustments', {})
        if category_adjustments:
            # Filter out None values and get dominant category
            valid_adjustments = {k: v for k, v in category_adjustments.items() if v is not None}
            if valid_adjustments:
                dominant_category = max(valid_adjustments.items(), key=lambda x: abs(x[1]))
                if abs(dominant_category[1]) > 0.1:
                    explanation_parts.append(f"Primary driver: {dominant_category[0].replace('_', ' ')} factors ({dominant_category[1]:+.2f} points).")
        
        # Data quality context
        data_quality = context.get('data_quality', 0.0)
        if data_quality < 0.5:
            explanation_parts.append(f"Note: Limited data quality ({data_quality:.1%}) affects prediction reliability.")
        
        # Market context
        vegas_spread = prediction_result.get('vegas_spread')
        contrarian_spread = prediction_result.get('contrarian_spread')
        if vegas_spread is not None and contrarian_spread is not None:
            explanation_parts.append(f"Vegas line: {vegas_spread:+.1f}, Contrarian prediction: {contrarian_spread:+.1f}.")
        elif vegas_spread is not None:
            explanation_parts.append(f"Vegas line: {vegas_spread:+.1f}, but contrarian prediction unavailable.")
        else:
            explanation_parts.append("No betting line available for comparison.")
        
        return " ".join(explanation_parts)
    
    def analyze_edge_opportunities(self, prediction_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analyze multiple predictions to identify the best edge opportunities.
        
        Args:
            prediction_results: List of prediction results with edge classifications
            
        Returns:
            Summary analysis of edge opportunities
        """
        if not prediction_results:
            return {
                'total_games': 0,
                'edge_opportunities': 0,
                'strong_edges': 0,
                'moderate_edges': 0,
                'slight_edges': 0,
                'recommendations': []
            }
        
        # Categorize edges
        edge_counts = {edge_type: 0 for edge_type in EdgeType}
        recommendations = []
        
        for result in prediction_results:
            edge_classification = result.get('edge_classification')
            if edge_classification:
                edge_counts[edge_classification.edge_type] += 1
                
                # Collect actionable recommendations
                if edge_classification.edge_type in [EdgeType.STRONG_CONTRARIAN, EdgeType.MODERATE_CONTRARIAN]:
                    recommendations.append({
                        'game': f"{result.get('away_team', '')} @ {result.get('home_team', '')}",
                        'edge_type': edge_classification.edge_type.value,
                        'edge_size': edge_classification.edge_size,
                        'confidence': edge_classification.confidence,
                        'recommendation': edge_classification.recommended_action
                    })
        
        # Sort recommendations by edge size and confidence
        recommendations.sort(key=lambda x: (x['edge_size'], x['confidence']), reverse=True)
        
        total_edges = (edge_counts[EdgeType.STRONG_CONTRARIAN] + 
                      edge_counts[EdgeType.MODERATE_CONTRARIAN] + 
                      edge_counts[EdgeType.SLIGHT_CONTRARIAN])
        
        return {
            'total_games': len(prediction_results),
            'edge_opportunities': total_edges,
            'strong_edges': edge_counts[EdgeType.STRONG_CONTRARIAN],
            'moderate_edges': edge_counts[EdgeType.MODERATE_CONTRARIAN],
            'slight_edges': edge_counts[EdgeType.SLIGHT_CONTRARIAN],
            'consensus_plays': edge_counts[EdgeType.CONSENSUS_PLAY],
            'no_edge_games': edge_counts[EdgeType.NO_EDGE],
            'insufficient_data': edge_counts[EdgeType.INSUFFICIENT_DATA],
            'recommendations': recommendations[:5],  # Top 5 recommendations
            'edge_rate': total_edges / len(prediction_results) if prediction_results else 0
        }
    
    def get_edge_detection_stats(self) -> Dict[str, Any]:
        """Get edge detection configuration and statistics."""
        return {
            'edge_thresholds': self.edge_thresholds,
            'confidence_thresholds': self.confidence_thresholds,
            'risk_parameters': self.risk_parameters,
            'edge_types': [edge_type.value for edge_type in EdgeType]
        }


# Global edge detector instance
edge_detector = EdgeDetector()