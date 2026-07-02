"""
Output formatter for College Football Market Edge Platform.
Handles clean CLI presentation with emojis, tables, and structured output.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
import textwrap

from engine.edge_detector import EdgeType


class OutputFormatter:
    """
    Formats prediction results for clean CLI presentation.
    
    Features:
    - Clean terminal output with emojis
    - Structured tables and sections
    - Color-coded results (optional)
    - Responsive formatting for different terminal widths
    - Export capabilities
    """
    
    def __init__(self, terminal_width: int = 80, use_emojis: bool = True):
        """Initialize output formatter."""
        self.terminal_width = terminal_width
        self.use_emojis = use_emojis
        
        # Emoji mappings
        self.emojis = {
            'strong_buy': '🎯',
            'moderate_buy': '📈',
            'slight_buy': '📊',
            'consensus': '🤝',
            'no_edge': '⚪',
            'avoid': '❌',
            'high_confidence': '🔥',
            'medium_confidence': '⚡',
            'low_confidence': '⚠️',
            'data_quality': '📊',
            'performance': '⚡',
            'warning': '⚠️',
            'success': '✅',
            'error': '❌',
            'info': 'ℹ️',
            'money': '💰',
            'trophy': '🏆',
            'clock': '⏱️',
            'home': '🏠',
            'away': '✈️'
        }
        
        # Color codes (for terminals that support them)
        self.colors = {
            'green': '\033[92m',
            'red': '\033[91m',
            'yellow': '\033[93m',
            'blue': '\033[94m',
            'cyan': '\033[96m',
            'white': '\033[97m',
            'bold': '\033[1m',
            'end': '\033[0m'
        }
        
        # Logging
        self.logger = logging.getLogger(__name__)
        
        self.logger.debug("Output formatter initialized")
    
    def format_prediction_output(self, prediction_result: Dict[str, Any],
                               confidence_assessment: Dict[str, Any],
                               edge_classification: Any,
                               insights: Dict[str, Any],
                               show_details: bool = False,
                               show_factors: bool = False) -> str:
        """
        Format complete prediction output for CLI display.
        
        Args:
            prediction_result: Prediction engine results
            confidence_assessment: Confidence analysis
            edge_classification: Edge classification object
            insights: Generated insights
            show_details: Show detailed analysis
            show_factors: Show factor breakdown
            
        Returns:
            Formatted output string
        """
        sections = []
        
        # Header
        sections.append(self._format_header(prediction_result, insights))
        
        # Summary
        sections.append(self._format_summary(prediction_result, confidence_assessment, edge_classification))
        
        # Edge Analysis
        sections.append(self._format_edge_analysis(edge_classification, insights))
        
        # Factor Breakdown (if requested)
        if show_factors:
            sections.append(self._format_factor_breakdown(prediction_result, insights))
        
        # Detailed Insights (if requested)
        if show_details:
            sections.append(self._format_detailed_insights(insights))
        
        # Key Takeaways
        sections.append(self._format_key_takeaways(insights))
        
        # Footer
        sections.append(self._format_footer(prediction_result))
        
        return '\n\n'.join(sections)
    
    def _format_header(self, prediction_result: Dict[str, Any], insights: Dict[str, Any]) -> str:
        """Format the output header."""
        home_team = prediction_result.get('home_team', 'Home')
        away_team = prediction_result.get('away_team', 'Away')
        week = prediction_result.get('week')
        
        header_lines = []
        
        # Title
        title = f"College Football Market Edge Platform - {away_team} @ {home_team}"
        if week:
            title += f" (Week {week})"
        
        header_lines.append(self._center_text(title))
        header_lines.append("=" * self.terminal_width)
        
        # Summary headline
        summary = insights.get('summary', {})
        headline = summary.get('headline', 'Analysis Complete')
        
        if self.use_emojis:
            edge_emoji = self._get_edge_emoji(insights)
            headline = f"{edge_emoji} {headline}"
        
        header_lines.append(self._center_text(headline))
        header_lines.append("-" * self.terminal_width)
        
        return '\n'.join(header_lines)
    
    def _format_summary(self, prediction_result: Dict[str, Any],
                       confidence_assessment: Dict[str, Any],
                       edge_classification: Any) -> str:
        """Format the prediction summary."""
        summary_lines = []
        summary_lines.append(f"{self._emoji('info')} PREDICTION SUMMARY")
        
        # Spread information
        vegas_spread = prediction_result.get('vegas_spread')
        contrarian_spread = prediction_result.get('contrarian_spread')
        edge_size = edge_classification.edge_size
        
        if vegas_spread is not None:
            home_team = prediction_result.get('home_team', 'Home')
            summary_lines.append(f"  {self._emoji('money')} Vegas Line: {home_team} {vegas_spread:+.1f}")
            
            if contrarian_spread is not None:
                summary_lines.append(f"  {self._emoji('trophy')} Contrarian Line: {home_team} {contrarian_spread:+.1f}")
                summary_lines.append(f"  📏 Edge Size: {edge_size:.2f} points")
        else:
            summary_lines.append(f"  {self._emoji('warning')} No betting line available")
        
        # Confidence
        confidence_level = confidence_assessment.get('confidence_level', 'Unknown')
        confidence_emoji = self._get_confidence_emoji(confidence_level)
        summary_lines.append(f"  {confidence_emoji} Confidence: {confidence_level}")
        
        # Recommendation
        recommendation = edge_classification.recommended_action
        summary_lines.append(f"  🎯 Recommendation: {recommendation}")
        
        return '\n'.join(summary_lines)
    
    def _format_edge_analysis(self, edge_classification: Any, insights: Dict[str, Any]) -> str:
        """Format edge analysis section."""
        edge_lines = []
        edge_lines.append(f"{self._emoji('trophy')} EDGE ANALYSIS")
        
        edge_insights = insights.get('edge_analysis', {})
        
        # Edge classification
        edge_class = edge_insights.get('edge_classification', 'Unknown')
        edge_lines.append(f"  📊 Classification: {edge_class}")
        
        # Edge magnitude
        magnitude = edge_insights.get('edge_magnitude', 'Unknown')
        edge_lines.append(f"  📏 Magnitude: {magnitude}")
        
        # Significance
        significance = edge_insights.get('edge_significance', '')
        if significance:
            wrapped_significance = textwrap.fill(significance, width=self.terminal_width-4, 
                                               initial_indent="  💡 ", subsequent_indent="     ")
            edge_lines.append(wrapped_significance)
        
        # Market implications
        market_implications = edge_insights.get('market_implications', '')
        if market_implications:
            wrapped_implications = textwrap.fill(market_implications, width=self.terminal_width-4,
                                              initial_indent="  🏪 ", subsequent_indent="     ")
            edge_lines.append(wrapped_implications)
        
        return '\n'.join(edge_lines)
    
    def _format_factor_breakdown(self, prediction_result: Dict[str, Any], insights: Dict[str, Any]) -> str:
        """Format factor breakdown section."""
        factor_lines = []
        factor_lines.append(f"{self._emoji('performance')} FACTOR BREAKDOWN")
        
        factor_insights = insights.get('factor_insights', [])
        category_adjustments = prediction_result.get('category_adjustments', {})
        
        # Category summary
        if category_adjustments:
            factor_lines.append("  Category Summary:")
            for category, adjustment in category_adjustments.items():
                category_name = category.replace('_', ' ').title()
                sign = "+" if adjustment >= 0 else ""
                factor_lines.append(f"    {category_name}: {sign}{adjustment:.3f} points")
        
        factor_lines.append("")
        
        # Individual factors
        if factor_insights:
            factor_lines.append("  Key Contributing Factors:")
            for factor_insight in factor_insights[:5]:  # Top 5 factors
                factor_name = factor_insight['factor']
                value = factor_insight['value']
                weighted = factor_insight['weighted_contribution']
                impact = factor_insight['impact_level']
                explanation = factor_insight['explanation']
                
                sign = "+" if value >= 0 else ""
                factor_lines.append(f"    {factor_name}: {sign}{value:.3f} (weighted: {sign}{weighted:.3f})")
                factor_lines.append(f"      Impact: {impact}")
                
                if explanation:
                    wrapped_explanation = textwrap.fill(explanation, width=self.terminal_width-8,
                                                      initial_indent="      → ", subsequent_indent="        ")
                    factor_lines.append(wrapped_explanation)
                
                factor_lines.append("")
        
        return '\n'.join(factor_lines)
    
    def _format_detailed_insights(self, insights: Dict[str, Any]) -> str:
        """Format detailed insights section."""
        detail_lines = []
        detail_lines.append(f"{self._emoji('info')} DETAILED ANALYSIS")
        
        # Strategic insights
        strategic_insights = insights.get('strategic_insights', [])
        if strategic_insights:
            detail_lines.append("  Strategic Considerations:")
            for insight in strategic_insights:
                wrapped_insight = textwrap.fill(insight, width=self.terminal_width-4,
                                             initial_indent="    • ", subsequent_indent="      ")
                detail_lines.append(wrapped_insight)
        
        detail_lines.append("")
        
        # Risk assessment
        risk_assessment = insights.get('risk_assessment', {})
        if risk_assessment:
            risk_level = risk_assessment.get('risk_level', 'Unknown')
            risk_emoji = self._get_risk_emoji(risk_level)
            detail_lines.append(f"  {risk_emoji} Risk Assessment: {risk_level}")
            
            risk_factors = risk_assessment.get('risk_factors', [])
            if risk_factors:
                detail_lines.append("    Risk Factors:")
                for factor in risk_factors:
                    detail_lines.append(f"      • {factor}")
            
            kelly_estimate = risk_assessment.get('kelly_criterion_estimate', '')
            if kelly_estimate:
                detail_lines.append(f"    Kelly Estimate: {kelly_estimate}")
        
        detail_lines.append("")
        
        # Confidence breakdown
        confidence_insights = insights.get('confidence_insights', {})
        if confidence_insights:
            detail_lines.append("  Confidence Analysis:")
            
            strongest = confidence_insights.get('strongest_factor', {})
            if strongest:
                detail_lines.append(f"    Strongest: {strongest.get('component', 'Unknown')} ({strongest.get('score', 0):.1%})")
            
            weakest = confidence_insights.get('weakest_factor', {})
            if weakest:
                detail_lines.append(f"    Weakest: {weakest.get('component', 'Unknown')} ({weakest.get('score', 0):.1%})")
            
            suggestions = confidence_insights.get('improvement_suggestions', [])
            if suggestions:
                detail_lines.append("    Improvements:")
                for suggestion in suggestions:
                    wrapped_suggestion = textwrap.fill(suggestion, width=self.terminal_width-8,
                                                     initial_indent="      • ", subsequent_indent="        ")
                    detail_lines.append(wrapped_suggestion)
        
        return '\n'.join(detail_lines)
    
    def _format_key_takeaways(self, insights: Dict[str, Any]) -> str:
        """Format key takeaways section."""
        takeaway_lines = []
        takeaway_lines.append(f"{self._emoji('trophy')} KEY TAKEAWAYS")
        
        key_takeaways = insights.get('key_takeaways', [])
        if key_takeaways:
            for i, takeaway in enumerate(key_takeaways, 1):
                wrapped_takeaway = textwrap.fill(takeaway, width=self.terminal_width-6,
                                              initial_indent=f"  {i}. ", subsequent_indent="     ")
                takeaway_lines.append(wrapped_takeaway)
        else:
            takeaway_lines.append("  No specific takeaways identified")
        
        return '\n'.join(takeaway_lines)
    
    def _format_footer(self, prediction_result: Dict[str, Any]) -> str:
        """Format output footer."""
        footer_lines = []
        footer_lines.append("-" * self.terminal_width)
        
        # Timestamp
        timestamp = prediction_result.get('timestamp', datetime.now().isoformat())
        try:
            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            formatted_time = dt.strftime("%Y-%m-%d %H:%M:%S")
        except:
            formatted_time = timestamp
        
        footer_lines.append(f"{self._emoji('clock')} Generated: {formatted_time}")
        
        # Data sources
        data_sources = prediction_result.get('data_sources', [])
        if data_sources:
            sources_str = ", ".join(data_sources)
            footer_lines.append(f"📊 Data Sources: {sources_str}")
        
        # Data quality
        data_quality = prediction_result.get('data_quality', 0.0)
        quality_emoji = self._get_quality_emoji(data_quality)
        footer_lines.append(f"{quality_emoji} Data Quality: {data_quality:.1%}")
        
        return '\n'.join(footer_lines)
    
    def format_error_output(self, error_message: str, context: Dict[str, Any] = None) -> str:
        """Format error output."""
        error_lines = []
        error_lines.append(f"{self._emoji('error')} PREDICTION ERROR")
        error_lines.append("=" * self.terminal_width)
        
        # Error message
        wrapped_error = textwrap.fill(error_message, width=self.terminal_width-4,
                                   initial_indent="  ", subsequent_indent="  ")
        error_lines.append(wrapped_error)
        
        # Context (if available)
        if context:
            error_lines.append("")
            error_lines.append("Context:")
            for key, value in context.items():
                error_lines.append(f"  {key}: {value}")
        
        # Suggestion
        error_lines.append("")
        error_lines.append("💡 Suggestion: Check team names and try again, or use --help for usage info")
        
        return '\n'.join(error_lines)
    
    def format_weekly_summary(self, weekly_results: List[Dict[str, Any]], 
                             week: int, min_edge: float = 0.0) -> str:
        """Format weekly analysis summary."""
        summary_lines = []
        summary_lines.append(f"{self._emoji('trophy')} WEEKLY ANALYSIS - WEEK {week}")
        summary_lines.append("=" * self.terminal_width)
        
        # Filter results by minimum edge
        significant_edges = [r for r in weekly_results if r.get('edge_size', 0.0) >= min_edge]
        
        summary_lines.append(f"📊 Total Games Analyzed: {len(weekly_results)}")
        summary_lines.append(f"🎯 Games with {min_edge}+ Point Edges: {len(significant_edges)}")
        summary_lines.append("")
        
        if significant_edges:
            # Sort by edge size
            significant_edges.sort(key=lambda x: x.get('edge_size', 0.0), reverse=True)
            
            summary_lines.append("TOP OPPORTUNITIES:")
            for i, result in enumerate(significant_edges[:5], 1):
                home_team = result.get('home_team', 'Home')
                away_team = result.get('away_team', 'Away')
                edge_size = result.get('edge_size', 0.0)
                confidence = result.get('confidence', 0.0)
                recommendation = result.get('recommendation', 'Unknown')
                
                edge_emoji = self._get_edge_size_emoji(edge_size)
                conf_emoji = self._get_confidence_emoji_from_score(confidence)
                
                summary_lines.append(f"  {i}. {edge_emoji} {away_team} @ {home_team}")
                summary_lines.append(f"     Edge: {edge_size:.1f} pts | Conf: {conf_emoji} | {recommendation}")
                summary_lines.append("")
        else:
            summary_lines.append(f"No games found with edges >= {min_edge} points")
        
        return '\n'.join(summary_lines)
    
    def _emoji(self, key: str) -> str:
        """Get emoji for key, with fallback."""
        if not self.use_emojis:
            return ""
        return self.emojis.get(key, "")
    
    def _get_edge_emoji(self, insights: Dict[str, Any]) -> str:
        """Get appropriate emoji for edge type."""
        edge_analysis = insights.get('edge_analysis', {})
        edge_class = edge_analysis.get('edge_classification', '').lower()
        
        if 'strong' in edge_class:
            return self._emoji('strong_buy')
        elif 'moderate' in edge_class:
            return self._emoji('moderate_buy')
        elif 'slight' in edge_class:
            return self._emoji('slight_buy')
        elif 'consensus' in edge_class:
            return self._emoji('consensus')
        elif 'no' in edge_class or 'none' in edge_class:
            return self._emoji('no_edge')
        else:
            return self._emoji('avoid')
    
    def _get_confidence_emoji(self, confidence_level: str) -> str:
        """Get emoji for confidence level."""
        level = confidence_level.lower()
        if 'high' in level or 'very high' in level:
            return self._emoji('high_confidence')
        elif 'medium' in level or 'moderate' in level:
            return self._emoji('medium_confidence')
        else:
            return self._emoji('low_confidence')
    
    def _get_confidence_emoji_from_score(self, confidence_score: float) -> str:
        """Get emoji for confidence score."""
        if confidence_score > 0.7:
            return self._emoji('high_confidence')
        elif confidence_score > 0.5:
            return self._emoji('medium_confidence')
        else:
            return self._emoji('low_confidence')
    
    def _get_risk_emoji(self, risk_level: str) -> str:
        """Get emoji for risk level."""
        level = risk_level.lower()
        if 'high' in level:
            return self._emoji('error')
        elif 'medium' in level:
            return self._emoji('warning')
        else:
            return self._emoji('success')
    
    def _get_quality_emoji(self, quality_score: float) -> str:
        """Get emoji for data quality score."""
        if quality_score > 0.7:
            return self._emoji('success')
        elif quality_score > 0.4:
            return self._emoji('warning')
        else:
            return self._emoji('error')
    
    def _get_edge_size_emoji(self, edge_size: float) -> str:
        """Get emoji for edge size."""
        if edge_size >= 3.0:
            return self._emoji('strong_buy')
        elif edge_size >= 2.0:
            return self._emoji('moderate_buy')
        elif edge_size >= 1.0:
            return self._emoji('slight_buy')
        else:
            return self._emoji('no_edge')
    
    def _center_text(self, text: str) -> str:
        """Center text within terminal width."""
        # Remove emojis for length calculation
        text_length = len(text)
        if text_length >= self.terminal_width:
            return text
        
        padding = (self.terminal_width - text_length) // 2
        return " " * padding + text
    
    def export_to_csv(self, results: List[Dict[str, Any]], filename: str = None) -> str:
        """Export results to CSV format."""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"cfb_predictions_{timestamp}.csv"
        
        # CSV headers
        headers = [
            "timestamp", "home_team", "away_team", "week", "vegas_spread",
            "contrarian_spread", "edge_size", "edge_type", "confidence_score",
            "recommendation", "data_quality"
        ]
        
        csv_lines = [",".join(headers)]
        
        for result in results:
            row = [
                result.get('timestamp', ''),
                result.get('home_team', ''),
                result.get('away_team', ''),
                str(result.get('week', '')),
                str(result.get('vegas_spread', '')),
                str(result.get('contrarian_spread', '')),
                str(result.get('edge_size', '')),
                result.get('edge_classification', ''),
                str(result.get('confidence', '')),
                result.get('recommendation', ''),
                str(result.get('data_quality', ''))
            ]
            csv_lines.append(",".join(f'"{item}"' for item in row))
        
        return '\n'.join(csv_lines)


# Global output formatter instance
output_formatter = OutputFormatter()