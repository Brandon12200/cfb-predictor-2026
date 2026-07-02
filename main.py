#!/usr/bin/env python3
"""
College Football Market Edge Platform - Command Line Interface

Main entry point for the college football betting analysis tool.
Identifies contrarian opportunities by layering human factor adjustments 
on top of Vegas market consensus.
"""

import sys
import argparse
import logging
import time
from typing import Optional, Dict, Any

# Heavy imports moved to main() to allow logging setup first
# Global variables for lazy loading
config = None
normalizer = None  
data_manager = None
prediction_engine = None
confidence_calculator = None
edge_detector = None

def _ensure_imports():
    """Ensure all heavy modules are imported."""
    global config, normalizer, data_manager, prediction_engine, confidence_calculator, edge_detector
    if config is None:
        from config import config as _config
        from utils.normalizer import normalizer as _normalizer
        from data.data_manager import data_manager as _data_manager
        from engine.prediction_engine import prediction_engine as _prediction_engine
        from engine.confidence_calculator import confidence_calculator as _confidence_calculator
        from engine.edge_detector import edge_detector as _edge_detector
        
        config = _config
        normalizer = _normalizer
        data_manager = _data_manager
        prediction_engine = _prediction_engine
        confidence_calculator = _confidence_calculator
        edge_detector = _edge_detector


def _get_current_week() -> int:
    """Get the current CFB week based on date."""
    from datetime import datetime
    
    # For August 2025, we're at the start of the season
    # Let's default to week 1 for current testing
    now = datetime.now()
    
    if now.month == 8:  # August - pre-season/early season
        return 1  # Week 1
    elif now.month >= 9:  # September-December
        # Rough approximation: Week 1 starts Sept 1, each week is 7 days
        week = ((now.day - 1) // 7) + 1
        if now.month == 9:
            return min(week, 4)  # Sept has weeks 1-4
        elif now.month == 10:
            return min(week + 4, 8)  # Oct has weeks 5-8
        elif now.month == 11:
            return min(week + 8, 12)  # Nov has weeks 9-12
        else:  # December
            return min(week + 12, 16)  # Dec has weeks 13-16
    elif now.month == 1:  # January - bowl season
        return 17  # Bowl week
    else:
        return 1  # Default to week 1


def parse_arguments() -> argparse.Namespace:
    """
    Parse command line arguments for the College Football Market Edge Platform.
    
    Returns:
        argparse.Namespace: Parsed command line arguments
    """
    parser = argparse.ArgumentParser(
        description='College Football Market Edge Platform - Find contrarian college football betting opportunities',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --home georgia --away alabama
  %(prog)s --home uga --away bama --verbose --show-factors
  %(prog)s --home "Georgia Bulldogs" --away "Alabama Crimson Tide" --week 8
  %(prog)s --analyze-week 8 --min-edge 3.0
  %(prog)s --list-teams
        """
    )
    
    # Primary prediction arguments
    prediction_group = parser.add_argument_group('Prediction Options')
    prediction_group.add_argument(
        '--home',
        type=str,
        help='Home team (e.g., "georgia", "uga", "Georgia Bulldogs")'
    )
    prediction_group.add_argument(
        '--away', 
        type=str,
        help='Away team (e.g., "alabama", "bama", "Alabama Crimson Tide")'
    )
    prediction_group.add_argument(
        '--week',
        type=int,
        metavar='N',
        help='College football week number (1-17)'
    )
    
    # Batch analysis
    batch_group = parser.add_argument_group('Batch Analysis')
    batch_group.add_argument(
        '--analyze-week',
        type=int,
        metavar='N',
        nargs='?',
        const=0,
        help='Analyze all games for specified week (defaults to current week if no number provided)'
    )
    batch_group.add_argument(
        '--analyze-week-p4',
        type=int,
        metavar='N',
        nargs='?',
        const=0,
        help='Generate contrarian predictions for all P4 games for specified week (defaults to current week)'
    )
    batch_group.add_argument(
        '--min-edge',
        type=float,
        default=3.0,
        metavar='POINTS',
        help='Minimum edge size to display (default: 3.0 points)'
    )
    batch_group.add_argument(
        '--min-confidence',
        type=float,
        default=60.0,
        metavar='PERCENT',
        help='Minimum confidence percentage to display (default: 60.0%%)'
    )
    batch_group.add_argument(
        '--delay',
        type=float,
        default=3.0,
        metavar='MINUTES',
        help='Minutes to wait between analyzing games (default: 3.0 minutes)'
    )
    
    # Output control
    output_group = parser.add_argument_group('Output Options')
    output_group.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose output with detailed explanations'
    )
    output_group.add_argument(
        '--show-factors',
        action='store_true',
        help='Display factor-by-factor breakdown'
    )
    output_group.add_argument(
        '--quiet', '-q',
        action='store_true',
        help='Suppress non-essential output'
    )
    output_group.add_argument(
        '--format',
        choices=['table', 'json', 'csv'],
        default='table',
        help='Output format (default: table)'
    )
    
    # Utility options
    utility_group = parser.add_argument_group('Utility Options')
    utility_group.add_argument(
        '--list-teams',
        action='store_true',
        help='List all supported team names and aliases'
    )
    utility_group.add_argument(
        '--list-games',
        type=int,
        metavar='WEEK',
        help='List all P4 games for specified week with normalized team names'
    )
    utility_group.add_argument(
        '--validate-team',
        type=str,
        metavar='TEAM',
        help='Check if team name can be normalized'
    )
    utility_group.add_argument(
        '--check-config',
        action='store_true',
        help='Validate configuration and API keys'
    )
    utility_group.add_argument(
        '--version',
        action='version',
        version='College Football Market Edge Platform v2.0'
    )
    
    # Debug options
    debug_group = parser.add_argument_group('Debug Options')
    debug_group.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug logging'
    )
    debug_group.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be done without making API calls'
    )
    debug_group.add_argument(
        '--cache-clear',
        action='store_true',
        help='Clear all cached data before running'
    )
    
    args = parser.parse_args()
    
    # Validate argument combinations
    _validate_arguments(args, parser)
    
    return args


def _validate_arguments(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    """
    Validate argument combinations and requirements.
    
    Args:
        args: Parsed arguments
        parser: Argument parser for error reporting
    """
    # Check for prediction requirements
    if not any([args.home, args.analyze_week is not None, args.analyze_week_p4 is not None, 
                args.list_teams, args.list_games, args.validate_team, args.check_config]):
        parser.error("Must specify prediction teams (--home/--away) or use utility options")
    
    # Both home and away required for single prediction
    if (args.home and not args.away) or (args.away and not args.home):
        parser.error("Both --home and --away are required for single game prediction")
    
    # Week validation
    if args.week and not (1 <= args.week <= 17):
        parser.error("Week must be between 1 and 17")
    
    if args.analyze_week and args.analyze_week != 0 and not (1 <= args.analyze_week <= 17):
        parser.error("Analyze week must be between 1 and 17")
    
    if args.analyze_week_p4 and args.analyze_week_p4 != 0 and not (1 <= args.analyze_week_p4 <= 17):
        parser.error("Analyze week P4 must be between 1 and 17")
    
    # Edge threshold validation
    if args.min_edge < 0:
        parser.error("Minimum edge must be non-negative")
    
    # Conflicting options
    if args.verbose and args.quiet:
        parser.error("Cannot use --verbose and --quiet together")


def setup_logging(debug: bool = False, quiet: bool = False) -> None:
    """
    Configure logging based on command line options.
    
    Args:
        debug: Enable debug logging
        quiet: Suppress non-essential output
    """
    import os
    from logging.handlers import RotatingFileHandler
    
    # Create logs directory if it doesn't exist
    log_dir = os.path.join(os.path.dirname(__file__), 'logs')
    os.makedirs(log_dir, exist_ok=True)
    
    # Clear any existing handlers
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    if debug:
        level = logging.DEBUG
    elif quiet:
        level = logging.ERROR  # Only show errors on console
    else:
        level = logging.ERROR  # Default: only errors on console
    
    # Always log everything to file
    file_handler = RotatingFileHandler(
        os.path.join(log_dir, 'cfb_predictor.log'),
        maxBytes=10*1024*1024,  # 10MB
        backupCount=3
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    ))
    root_logger.addHandler(file_handler)
    
    # Console handler - only errors unless debug mode
    if not quiet:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(level)
        if debug:
            console_handler.setFormatter(logging.Formatter(
                '%(levelname)s: %(message)s'
            ))
        else:
            # For normal operation, only show errors
            console_handler.setFormatter(logging.Formatter('%(message)s'))
        root_logger.addHandler(console_handler)
    
    # Set root logger level
    root_logger.setLevel(logging.DEBUG if debug else logging.INFO)
    
    # Suppress warnings in normal mode
    if not debug:
        import warnings
        warnings.filterwarnings('ignore')


def validate_teams(home_team: str, away_team: str) -> tuple[Optional[str], Optional[str]]:
    """
    Validate and normalize team names.
    
    Args:
        home_team: Home team input
        away_team: Away team input
        
    Returns:
        tuple: (normalized_home, normalized_away) or (None, None) if invalid
    """
    _ensure_imports()
    
    # Check for FCS teams first
    if normalizer.is_fcs_team(home_team):
        print(f"Error: '{home_team}' is an FCS team. This tool only analyzes FBS (Power 4) matchups.")
        return None, None
    
    if normalizer.is_fcs_team(away_team):
        print(f"Error: '{away_team}' is an FCS team. This tool only analyzes FBS (Power 4) matchups.")
        return None, None
    
    normalized_home = normalizer.normalize(home_team)
    normalized_away = normalizer.normalize(away_team)
    
    if not normalized_home:
        # Check if it might be FCS
        if normalizer.is_fcs_team(home_team):
            print(f"Error: '{home_team}' appears to be an FCS team.")
        else:
            print(f"Error: Unknown home team '{home_team}'")
        print("Use --list-teams to see supported team names")
        return None, None
    
    if not normalized_away:
        # Check if it might be FCS
        if normalizer.is_fcs_team(away_team):
            print(f"Error: '{away_team}' appears to be an FCS team.")
        else:
            print(f"Error: Unknown away team '{away_team}'")
        print("Use --list-teams to see supported team names")
        return None, None
    
    if normalized_home == normalized_away:
        print("Error: Home and away teams cannot be the same")
        return None, None
    
    return normalized_home, normalized_away


def list_teams() -> None:
    """Display all supported team names and aliases."""
    _ensure_imports()
    print("College Football Market Edge Platform - Supported Teams")
    print("=" * 50)
    print()
    
    all_teams = sorted(normalizer.get_all_teams())
    
    # Group by conference (simplified)
    conferences = {
        'SEC': ['ALABAMA', 'ARKANSAS', 'AUBURN', 'FLORIDA', 'GEORGIA', 'KENTUCKY',
                'LSU', 'MISSISSIPPI', 'MISSISSIPPI STATE', 'MISSOURI', 'SOUTH CAROLINA',
                'TENNESSEE', 'TEXAS', 'TEXAS A&M', 'VANDERBILT', 'OKLAHOMA'],
        'BIG TEN': ['ILLINOIS', 'INDIANA', 'IOWA', 'MARYLAND', 'MICHIGAN', 'MICHIGAN STATE',
                    'MINNESOTA', 'NEBRASKA', 'NORTHWESTERN', 'OHIO STATE', 'PENN STATE',
                    'PURDUE', 'RUTGERS', 'WISCONSIN', 'OREGON', 'WASHINGTON', 'UCLA', 'USC'],
        'BIG 12': ['BAYLOR', 'IOWA STATE', 'KANSAS', 'KANSAS STATE', 'OKLAHOMA STATE',
                   'TCU', 'TEXAS TECH', 'WEST VIRGINIA', 'CINCINNATI', 'HOUSTON',
                   'UCF', 'BYU', 'COLORADO', 'UTAH', 'ARIZONA', 'ARIZONA STATE'],
        'ACC': ['BOSTON COLLEGE', 'CLEMSON', 'DUKE', 'FLORIDA STATE', 'GEORGIA TECH',
                'LOUISVILLE', 'MIAMI', 'NC STATE', 'NORTH CAROLINA', 'PITTSBURGH',
                'SYRACUSE', 'VIRGINIA', 'VIRGINIA TECH', 'WAKE FOREST'],
        'INDEPENDENT': ['NOTRE DAME']
    }
    
    for conf_name, teams in conferences.items():
        print(f"{conf_name}:")
        for team in teams:
            if team in all_teams:
                aliases = normalizer.get_all_aliases(team)
                alias_str = ', '.join([a for a in aliases if a != team][:3])  # Show first 3 aliases
                if alias_str:
                    print(f"  {team:<20} (aliases: {alias_str})")
                else:
                    print(f"  {team}")
        print()
    
    print("Examples:")
    print("  --home georgia --away alabama")
    print("  --home uga --away bama")
    print("  --home 'Georgia Bulldogs' --away 'Alabama Crimson Tide'")


def validate_team_name(team_name: str) -> None:
    """Validate a single team name and show normalization."""
    _ensure_imports()
    normalized = normalizer.normalize(team_name)

    if normalized:
        print(f"'{team_name}' normalizes to: {normalized}")

        aliases = normalizer.get_all_aliases(normalized)
        print(f"  Known aliases: {', '.join(aliases)}")

        espn_format = normalizer.to_espn_format(normalized)
        if espn_format:
            print(f"  ESPN format: {espn_format}")

        odds_format = normalizer.to_odds_format(normalized)
        if odds_format:
            print(f"  Odds API format: {odds_format}")
    else:
        print(f"'{team_name}' not recognized")
        print("Use --list-teams to see supported team names")


def list_games(week: int) -> None:
    """List all P4 games for a specific week with normalized team names."""
    _ensure_imports()
    print(f"CFB Week {week} Schedule - P4 Games")
    print("=" * 60)

    try:
        # Initialize schedule client
        from data.schedule_client import CFBScheduleClient
        schedule_client = CFBScheduleClient()

        # Test connection first
        if not schedule_client.test_connection():
            print("Cannot connect to ESPN Schedule API")
            print("   Check your internet connection and try again")
            return

        print(f"Fetching Week {week} schedule...")

        # Get P4 games for the week
        p4_games = schedule_client.get_p4_games(week)

        if not p4_games:
            print(f"No P4 games found for Week {week}")
            print("   This may be an off-season week or the data isn't available yet")
            return

        print(f"Found {len(p4_games)} P4 games for Week {week}")
        print("-" * 80)
        
        # Display each game in single-line format
        for i, game in enumerate(p4_games, 1):
            away_team = game['away_team_short']
            home_team = game['home_team_short']
            venue = game['venue_name']
            
            # Add rankings if available
            away_display = away_team
            if game['away_ranking']:
                away_display = f"#{game['away_ranking']} {away_team}"
            
            home_display = home_team
            if game['home_ranking']:
                home_display = f"#{game['home_ranking']} {home_team}"
            
            # Compact matchup display (fixed width for alignment)
            matchup = f"{away_display:18} @ {home_display:18}"
            
            # Show normalized names for commands
            away_norm = game['away_team_normalized']
            home_norm = game['home_team_normalized']
            
            # Venue info (compact)
            venue_info = ""
            if game['neutral_site']:
                venue_info = f"[Neutral: {venue[:15]}]"
            
            # Command for easy copy/paste
            if away_norm and home_norm:
                cmd = f"--home {home_norm.lower().replace(' ', '-')} --away {away_norm.lower().replace(' ', '-')}"
                print(f"{i:2d}. {matchup} {venue_info} | {cmd}")
            else:
                print(f"{i:2d}. {matchup} {venue_info} | [Normalization incomplete]")
        
        print("=" * 60)
        print("Tips:")
        print("   - Use the Command lines above to test individual games")
        print("   - Add --verbose --show-factors for detailed analysis")
        print(f"   - Try: python main.py --analyze-week {week} for batch analysis")

    except Exception as e:
        print(f"Error fetching Week {week} schedule: {e}")
        print("   Check your configuration and try again")


def check_configuration() -> bool:
    """
    Check configuration and API key status.
    
    Returns:
        bool: True if configuration is valid
    """
    _ensure_imports()
    print("College Football Market Edge Platform - Configuration Check")
    print("=" * 50)
    
    # Check API keys
    api_status = config.validate_api_keys()
    print(f"Odds API Key: {'Configured' if api_status['odds_api'] else 'Missing'}")
    print(f"ESPN API Key: {'Configured' if api_status['espn_api'] == True else 'Optional' if api_status['espn_api'] == 'optional' else 'Missing'}")

    # Test API connections
    print(f"\nAPI Connection Tests:")
    try:
        connections = data_manager.test_all_connections()
        print(f"  Odds API: {'Connected' if connections.get('odds_api', False) else 'Failed'}")
        print(f"  ESPN API: {'Connected' if connections.get('espn_api', False) else 'Failed'}")
    except Exception as e:
        print(f"  Connection test failed: {e}")
    
    # Check configuration
    print(f"\nConfiguration:")
    print(f"  Debug mode: {config.debug}")
    print(f"  Log level: {config.log_level}")
    print(f"  Cache TTL: {config.cache_ttl}s")
    print(f"  Rate limits: Odds API {config.rate_limit_odds}/day, ESPN {config.rate_limit_espn}/min")
    
    # Check factor weights
    total_weight = config.coaching_edge_weight + config.situational_context_weight + config.momentum_factors_weight
    print(f"\nFactor Weights (total: {total_weight:.3f}):")
    print(f"  Coaching Edge: {config.coaching_edge_weight:.1%}")
    print(f"  Situational Context: {config.situational_context_weight:.1%}")
    print(f"  Momentum Factors: {config.momentum_factors_weight:.1%}")
    
    # Show cache statistics
    try:
        cache_stats = data_manager.get_cache_stats()
        print(f"\nCache Statistics:")
        print(f"  Entries: {cache_stats.get('entries', 0)}")
        print(f"  Hit rate: {cache_stats.get('hit_rate', 0):.1%}")
        print(f"  Utilization: {cache_stats.get('utilization', 0):.1%}")
    except Exception as e:
        print(f"  Cache stats unavailable: {e}")
    
    # Validation
    is_valid = api_status['odds_api'] and abs(total_weight - 1.0) < 0.001

    if is_valid:
        print("\nConfiguration valid and ready for use")
    else:
        print("\nConfiguration issues detected:")
        if not api_status['odds_api']:
            print("  - Odds API key required")
        if abs(total_weight - 1.0) >= 0.001:
            print(f"  - Factor weights don't sum to 1.0 (got {total_weight})")

    return is_valid


def run_single_prediction(home_team: str, away_team: str, week: Optional[int] = None,
                         verbose: bool = False, show_factors: bool = False) -> Dict[str, Any]:
    """
    Run prediction for a single game.
    
    Args:
        home_team: Normalized home team name
        away_team: Normalized away team name
        week: Week number (optional)
        verbose: Enable verbose output
        show_factors: Show factor breakdown
        
    Returns:
        dict: Prediction results
    """
    _ensure_imports()
    print(f"\nAnalyzing: {away_team} @ {home_team}")
    if week:
        print(f"Week: {week}")
    print("-" * 50)
    
    try:
        # Get comprehensive game context
        print("Fetching game data...")
        context = data_manager.get_game_context(home_team, away_team, week)

        # Display data quality
        quality = context.get('data_quality', 0)
        quality_str = f"{quality:.1%}"
        print(f"Data Quality: {quality_str}")

        # Get betting line
        vegas_spread = context.get('vegas_spread')
        if vegas_spread is not None:
            print(f"Vegas Spread: {home_team} {vegas_spread:+.1f}")
        else:
            print("Vegas Spread: Not available")
        
        # Show data availability if verbose
        if verbose:
            print(f"\nData Sources: {', '.join(context.get('data_sources', []))}")

            availability = data_manager.validate_data_availability(home_team, away_team)
            print("Data Availability:")
            for source, available in availability.items():
                status = "Yes" if available else "No"
                print(f"   {source}: {status}")
        
        # Show team information
        home_data = context.get('home_team_data', {})
        away_data = context.get('away_team_data', {})

        print(f"\nTeam Information:")

        # Home team info
        home_info = home_data.get('info', {})
        home_display = home_info.get('display_name', home_team)
        print(f"{home_team}: {home_display}")

        # Away team info
        away_info = away_data.get('info', {})
        away_display = away_info.get('display_name', away_team)
        print(f"{away_team}: {away_display}")
        
        # Show coaching comparison
        coaching_comp = context.get('coaching_comparison', {})
        if coaching_comp and show_factors:
            print(f"\nCoaching Comparison:")

            home_coach = coaching_comp.get('home_coaching', {})
            away_coach = coaching_comp.get('away_coaching', {})

            home_coach_name = home_coach.get('head_coach_name', 'Unknown')
            away_coach_name = away_coach.get('head_coach_name', 'Unknown')

            home_exp = home_coach.get('head_coach_experience', 0)
            away_exp = away_coach.get('head_coach_experience', 0)

            print(f"   {home_team}: {home_coach_name} ({home_exp} years)")
            print(f"   {away_team}: {away_coach_name} ({away_exp} years)")

            exp_diff = coaching_comp.get('experience_differential', 0)
            if exp_diff > 0:
                print(f"   Experience Edge: {home_team} +{exp_diff} years")
            elif exp_diff < 0:
                print(f"   Experience Edge: {away_team} +{abs(exp_diff)} years")
            else:
                print(f"   Experience Edge: Even")
        
        # Generate contrarian prediction using the prediction engine
        print(f"\nGenerating Contrarian Prediction...")
        prediction_result = prediction_engine.generate_prediction(home_team, away_team, week)
        
        # Calculate confidence assessment
        context_for_confidence = {
            'data_quality': quality,
            'vegas_spread': vegas_spread,
            'data_sources': context.get('data_sources', [])
        }
        
        # Get factor results for confidence calculation
        from factors.factor_registry import factor_registry
        factor_results = factor_registry.calculate_all_factors(home_team, away_team, context)
        
        confidence_assessment = confidence_calculator.calculate_confidence(
            prediction_result, factor_results, context_for_confidence
        )
        
        # Detect contrarian edges
        edge_classification = edge_detector.detect_edge(
            prediction_result, confidence_assessment, context_for_confidence
        )
        
        # Display prediction results
        print(f"\nPrediction Results:")
        print(f"Vegas Spread: {home_team} {vegas_spread:+.1f}" if vegas_spread is not None else "Vegas Spread: Not available")
        
        if prediction_result.get('contrarian_spread') is not None:
            contrarian_spread = prediction_result['contrarian_spread']
            total_adjustment = prediction_result.get('total_adjustment', 0.0)
            edge_size = prediction_result.get('edge_size', 0.0)

            # Handle None values
            if contrarian_spread is None:
                contrarian_spread = 0.0
            if total_adjustment is None:
                total_adjustment = 0.0
            if edge_size is None:
                edge_size = 0.0

            print(f"Contrarian Prediction: {home_team} {contrarian_spread:+.1f}")
            print(f"Factor Adjustment: {total_adjustment:+.2f} points")
            print(f"Edge Size: {edge_size:.2f} points")
        else:
            print("Contrarian Prediction: Cannot calculate without betting line")
        
        print(f"\nEdge Analysis:")
        print(f"Edge Type: {edge_classification.edge_type.value.replace('_', ' ').title()}")
        print(f"Confidence: {confidence_assessment['confidence_level']} ({confidence_assessment['confidence_percentage']})")
        print(f"Recommendation: {edge_classification.recommended_action}")
        
        if show_factors:
            print(f"\nFactor Breakdown:")
            for factor_name, factor_result in factor_results['factors'].items():
                if factor_result['success']:
                    value = factor_result.get('value', 0.0)
                    weighted_value = factor_result.get('weighted_value', 0.0)
                    # Handle None values
                    if value is None:
                        value = 0.0
                    if weighted_value is None:
                        weighted_value = 0.0
                    print(f"   {factor_name}: {value:+.3f} (weighted: {weighted_value:+.3f})")
                    if factor_result.get('explanation'):
                        print(f"      -> {factor_result['explanation']}")
                else:
                    print(f"   {factor_name}: FAILED - {factor_result.get('error', 'Unknown error')}")

            print(f"\nCategory Summary:")
            for category, adjustment in factor_results['summary'].get('category_adjustments', {}).items():
                # Handle None adjustment values
                if adjustment is None:
                    adjustment = 0.0
                print(f"   {category.replace('_', ' ').title()}: {adjustment:+.3f} points")
        
        print(f"\nExplanation:")
        print(f"{edge_classification.explanation}")
        
        # Build result structure with prediction engine results
        result = {
            'home_team': home_team,
            'away_team': away_team,
            'week': week,
            'vegas_spread': vegas_spread,
            'contrarian_prediction': prediction_result.get('contrarian_spread'),
            'edge_size': prediction_result.get('edge_size'),
            'confidence': confidence_assessment.get('confidence_score'),
            'edge_classification': edge_classification.edge_type.value,
            'data_quality': quality,
            'data_sources': context.get('data_sources', []),
            'team_data': {
                'home': home_data,
                'away': away_data
            },
            'coaching_comparison': coaching_comp,
            'recommendation': edge_classification.recommended_action,
            'timestamp': context.get('timestamp'),
            'prediction_result': prediction_result,
            'confidence_assessment': confidence_assessment,
            'edge_classification_obj': edge_classification
        }
        
        return result
        
    except Exception as e:
        print(f"Error analyzing game: {e}")

        # Return error result
        return {
            'home_team': home_team,
            'away_team': away_team,
            'week': week,
            'error': str(e),
            'edge_classification': 'ERROR',
            'recommendation': 'Analysis failed - check configuration'
        }


def run_weekly_analysis(week: int, min_edge: float = 3.0) -> None:
    """
    Analyze all games for a specified week, focusing on Power 4 conferences.
    
    Args:
        week: Week number to analyze
        min_edge: Minimum edge size to display
    """
    _ensure_imports()
    print(f"\nWeek {week} Power 4 vs Power 4 Games")
    print("=" * 60)
    
    try:
        # Get all games from multiple sources
        all_games = []
        games_with_lines = {}
        
        # Try to get games with betting lines first
        if data_manager.odds_client:
            try:
                weekly_data = data_manager.odds_client.get_weekly_spreads(week)
                betting_games = weekly_data.get('games', [])

                for game in betting_games:
                    home = game.get('home_team')
                    away = game.get('away_team')
                    if home and away:
                        key = f"{away.upper()}@{home.upper()}"
                        games_with_lines[key] = game.get('consensus_spread')
                        all_games.append({
                            'home_team': home,
                            'away_team': away,
                            'spread': game.get('consensus_spread'),
                            'has_line': True
                        })
            except Exception as e:
                print(f"Could not fetch odds data: {e}")
        
        # Also get games from schedule API to ensure we have all P4 games
        try:
            from data.schedule_client import CFBScheduleClient
            from datetime import datetime
            schedule_client = CFBScheduleClient()
            # Use current year (2025 for September 2025)
            current_year = datetime.now().year
            schedule_games = schedule_client.get_p4_games(week, current_year)

            # Add schedule games that aren't already in our list
            for game in schedule_games:
                home = game.get('home_team')
                away = game.get('away_team')
                if home and away:
                    # Normalize names for deduplication check
                    home_norm = normalizer.normalize(home)
                    away_norm = normalizer.normalize(away)

                    if home_norm and away_norm:
                        home_norm_upper = home_norm.upper()
                        away_norm_upper = away_norm.upper()
                        key = f"{away_norm_upper}@{home_norm_upper}"
                        # Only add if not already included from odds API
                        if key not in games_with_lines:
                            all_games.append({
                                'home_team': home,
                                'away_team': away,
                                'spread': None,
                                'has_line': False
                            })
        except Exception as e:
            print(f"Could not fetch schedule data: {e}")
        
        # Power 4 conference teams (accurate as of 2024 season)
        power4_teams = {
            'SEC': ['ALABAMA', 'ARKANSAS', 'AUBURN', 'FLORIDA', 'GEORGIA', 'KENTUCKY', 
                   'LSU', 'MISSISSIPPI', 'MISSISSIPPI STATE', 'MISSOURI', 'SOUTH CAROLINA', 
                   'TENNESSEE', 'TEXAS', 'TEXAS A&M', 'VANDERBILT', 'OKLAHOMA'],
            'BIG TEN': ['ILLINOIS', 'INDIANA', 'IOWA', 'MARYLAND', 'MICHIGAN', 'MICHIGAN STATE',
                       'MINNESOTA', 'NEBRASKA', 'NORTHWESTERN', 'OHIO STATE', 'PENN STATE',
                       'PURDUE', 'RUTGERS', 'WISCONSIN', 'UCLA', 'USC', 'OREGON', 'WASHINGTON'],
            'BIG 12': ['ARIZONA', 'ARIZONA STATE', 'BAYLOR', 'CINCINNATI', 'COLORADO', 'HOUSTON',
                      'IOWA STATE', 'KANSAS', 'KANSAS STATE', 'OKLAHOMA STATE', 'TCU', 'TEXAS TECH',
                      'UCF', 'UTAH', 'WEST VIRGINIA', 'BYU'],
            'ACC': ['BOSTON COLLEGE', 'CLEMSON', 'DUKE', 'FLORIDA STATE', 'GEORGIA TECH', 'LOUISVILLE',
                   'MIAMI', 'NC STATE', 'NORTH CAROLINA', 'PITTSBURGH', 'SYRACUSE',
                   'VIRGINIA', 'VIRGINIA TECH', 'WAKE FOREST', 'CALIFORNIA', 'STANFORD', 'SMU'],
            'INDEPENDENT': ['NOTRE DAME']  # Football independents that we track
        }
        
        # Filter to Power 4 games only
        power4_games = []
        all_power4_teams = set()
        for conf_teams in power4_teams.values():
            all_power4_teams.update(conf_teams)
        
        for game in all_games:
            # Normalize team names to remove mascots and get consistent format
            home_raw = game.get('home_team', '')
            away_raw = game.get('away_team', '')

            # Use normalizer to get clean team names
            home_normalized = normalizer.normalize(home_raw)
            away_normalized = normalizer.normalize(away_raw)

            # Skip if normalization failed
            if not home_normalized or not away_normalized:
                continue

            home = home_normalized.upper() if isinstance(home_normalized, str) else home_normalized
            away = away_normalized.upper() if isinstance(away_normalized, str) else away_normalized

            # Skip invalid games where team plays itself (data error)
            if home == away:
                continue

            # Filter out FCS teams first
            if normalizer.is_fcs_team(home) or normalizer.is_fcs_team(away):
                continue

            # Check if BOTH teams are Power 4 (includes independents like Notre Dame)
            if home in all_power4_teams and away in all_power4_teams:
                # Update game with normalized team names for consistent display
                game['home_team'] = normalizer.normalize(home_raw)
                game['away_team'] = normalizer.normalize(away_raw)

                # Determine conference matchup type
                home_conf = None
                away_conf = None
                for conf, teams in power4_teams.items():
                    if home in teams:
                        home_conf = conf
                    if away in teams:
                        away_conf = conf

                game['home_conf'] = home_conf
                game['away_conf'] = away_conf

                # Conference game only if both teams are in the same actual conference
                # (Independent teams can never play "conference" games)
                is_conference_game = (home_conf == away_conf and
                                    home_conf is not None and
                                    home_conf != 'INDEPENDENT')

                game['matchup_type'] = 'Conference' if is_conference_game else 'Non-Conference'
                power4_games.append(game)
        
        if not power4_games:
            print("No Power 4 vs Power 4 games found for this week")
            print("   Only games where BOTH teams are from Power 4 conferences are shown")
            print("   This might be early season (mostly non-conference games) or an off-week")
            return
        
        # Sort games by conference matchup type, then by spread size
        power4_games.sort(key=lambda x: (
            x['matchup_type'] != 'Conference',  # Conference games first
            x['home_conf'] or 'ZZZ',  # Then by home team conference
            -(abs(x['spread']) if x['spread'] is not None else 0)  # Then by spread size
        ))
        
        # Display games in simple list format
        _display_games_simple(power4_games)
        
        # Summary
        print("-" * 60)

        conf_games = [g for g in power4_games if g['matchup_type'] == 'Conference']
        non_conf_games = [g for g in power4_games if g['matchup_type'] == 'Non-Conference']
        games_with_lines = [g for g in power4_games if g['spread'] is not None]

        print(f"Summary: {len(power4_games)} Power 4 vs Power 4 games this week")
        print(f"   - {len(conf_games)} conference games")
        print(f"   - {len(non_conf_games)} non-conference Power 4 matchups")

        if games_with_lines:
            print(f"\nAnalyze individual games:")
            for game in games_with_lines[:2]:  # Show first 2 examples
                print(f"   python main.py --home \"{game['home_team']}\" --away \"{game['away_team']}\"")
            if len(games_with_lines) > 2:
                print(f"   (... {len(games_with_lines) - 2} more games available)")

    except Exception as e:
        print(f"Error in weekly analysis: {e}")
        print("   Check your API configuration and try again")


def _display_games_simple(games):
    """Display games in a simple, terminal-friendly format."""
    print("\nPower 4 vs Power 4 Games:")
    print("-" * 80)
    
    for i, game in enumerate(games, 1):
        away_team = game['away_team']
        home_team = game['home_team']
        
        # Create matchup string (fixed width for alignment)
        matchup = f"{away_team:15} @ {home_team:15}"
        
        # Format spread
        if game['spread'] is not None:
            if game['spread'] < 0:
                # Negative spread = home team favored
                line = f"{home_team[:10]} {game['spread']:.1f}"
            elif game['spread'] > 0:
                # Positive spread = away team favored  
                line = f"{away_team[:10]} -{game['spread']:.1f}"
            else:
                line = "Pick'em"
        else:
            line = "No line"
        
        # Format type (compact)
        if game.get('matchup_type') == 'Conference':
            conf = game.get('home_conf', 'Unknown')[:8]
            type_str = f"[{conf}]"
        else:
            if game.get('home_conf') == 'INDEPENDENT' or game.get('away_conf') == 'INDEPENDENT':
                type_str = "[IND]"
            else:
                type_str = "[Non-Conf]"
        
        # Single line output
        print(f"{i:2d}. {matchup} | {line:15} {type_str}")


def run_p4_predictions(week: int, min_edge: float = 1.0, min_confidence: float = 60.0, max_spread: float = 14.0, delay_minutes: float = 3.0) -> list:
    """
    Run contrarian predictions for all P4 games in a specified week.
    
    Args:
        week: Week number to analyze
        min_edge: Minimum edge size to include in results
        min_confidence: Minimum confidence percentage to include in results
        max_spread: Maximum spread to analyze (skip blowouts)
        delay_minutes: Minutes to wait between analyzing games (prevents rate limiting)
        
    Returns:
        List of predictions that meet the minimum thresholds
    """
    _ensure_imports()
    
    print(f"Generating contrarian predictions for Week {week} P4 games...")
    print("=" * 70)
    print(f"Filters: Edge ≥ {min_edge:.1f} points, Confidence ≥ {min_confidence:.1f}%")
    print()
    
    try:
        # Get all P4 games (reusing logic from run_weekly_analysis)
        all_games = []
        
        # Try to get games with betting lines first
        if data_manager.odds_client:
            weekly_data = data_manager.odds_client.get_weekly_spreads(week)
            betting_games = weekly_data.get('games', [])
            
            for game in betting_games:
                all_games.append({
                    'home_team': game.get('home_team'),
                    'away_team': game.get('away_team'),
                    'spread': game.get('consensus_spread'),
                    'has_line': True
                })
        
        # Power 4 conference teams
        power4_teams = {
            'SEC': ['ALABAMA', 'ARKANSAS', 'AUBURN', 'FLORIDA', 'GEORGIA', 'KENTUCKY', 
                   'LSU', 'MISSISSIPPI', 'MISSISSIPPI STATE', 'MISSOURI', 'SOUTH CAROLINA', 
                   'TENNESSEE', 'TEXAS', 'TEXAS A&M', 'VANDERBILT', 'OKLAHOMA'],
            'BIG TEN': ['ILLINOIS', 'INDIANA', 'IOWA', 'MARYLAND', 'MICHIGAN', 'MICHIGAN STATE',
                       'MINNESOTA', 'NEBRASKA', 'NORTHWESTERN', 'OHIO STATE', 'PENN STATE',
                       'PURDUE', 'RUTGERS', 'WISCONSIN', 'UCLA', 'USC', 'OREGON', 'WASHINGTON'],
            'BIG 12': ['ARIZONA', 'ARIZONA STATE', 'BAYLOR', 'CINCINNATI', 'COLORADO', 'HOUSTON',
                      'IOWA STATE', 'KANSAS', 'KANSAS STATE', 'OKLAHOMA STATE', 'TCU', 'TEXAS TECH',
                      'UCF', 'UTAH', 'WEST VIRGINIA', 'BYU'],
            'ACC': ['BOSTON COLLEGE', 'CLEMSON', 'DUKE', 'FLORIDA STATE', 'GEORGIA TECH', 'LOUISVILLE',
                   'MIAMI', 'NC STATE', 'NORTH CAROLINA', 'PITTSBURGH', 'SYRACUSE',
                   'VIRGINIA', 'VIRGINIA TECH', 'WAKE FOREST', 'CALIFORNIA', 'STANFORD', 'SMU'],
            'INDEPENDENT': ['NOTRE DAME']
        }
        
        # Filter to P4 games only
        power4_games = []
        all_power4_teams = set()
        for conf_teams in power4_teams.values():
            all_power4_teams.update(conf_teams)
        
        for game in all_games:
            home = game.get('home_team', '').upper()
            away = game.get('away_team', '').upper()
            
            # Filter out FCS teams
            if normalizer.is_fcs_team(home) or normalizer.is_fcs_team(away):
                continue
            
            # Must have both teams as P4 for full P4 analysis
            if home in all_power4_teams and away in all_power4_teams:
                power4_games.append(game)
        
        if not power4_games:
            print("No P4 vs P4 games found for this week")
            return []

        print(f"Found {len(power4_games)} P4 vs P4 games with betting lines")
        
        # Smart filtering: Focus on games with higher edge probability
        # Games with massive spreads rarely have contrarian value
        MAX_SPREAD_FOR_ANALYSIS = max_spread  # Use parameter value
        HIGH_PRIORITY_SPREAD = 7.5           # One-score games have highest edge potential
        MAX_GAMES_TO_ANALYZE = 20            # Increased limit since we have delays now
        
        games_to_analyze = []
        games_skipped = []
        
        for game in power4_games:
            spread = game.get('spread')
            if spread is None:
                continue
                
            spread_abs = abs(spread)
            
            # Categorize games by edge probability
            if spread_abs <= HIGH_PRIORITY_SPREAD:
                # High priority: close games where edges are most likely
                game['priority'] = 'HIGH'
                game['spread_abs'] = spread_abs
                games_to_analyze.append(game)
            elif spread_abs <= MAX_SPREAD_FOR_ANALYSIS:
                # Medium priority: still worth checking but less likely
                game['priority'] = 'MEDIUM'
                game['spread_abs'] = spread_abs
                games_to_analyze.append(game)
            else:
                # Skip: very unlikely to find edges in blowouts
                games_skipped.append(game)
        
        # Sort by spread size (closest games first)
        games_to_analyze.sort(key=lambda x: x['spread_abs'])
        
        # Limit games if needed
        if len(games_to_analyze) > MAX_GAMES_TO_ANALYZE:
            print(f"Limiting analysis to {MAX_GAMES_TO_ANALYZE} closest games")
            games_to_analyze = games_to_analyze[:MAX_GAMES_TO_ANALYZE]

        print(f"Smart filtering: Analyzing {len(games_to_analyze)} games (skipping {len(games_skipped)} blowouts)")

        # Calculate estimated runtime
        from datetime import datetime, timedelta
        import time
        total_minutes = len(games_to_analyze) * delay_minutes
        estimated_completion = datetime.now() + timedelta(minutes=total_minutes)

        print(f"Estimated runtime: {total_minutes:.1f} minutes ({delay_minutes} min delay between games)")
        print(f"   Expected completion: {estimated_completion.strftime('%I:%M %p')}")
        
        if games_skipped:
            print(f"   Skipped games with spreads > {MAX_SPREAD_FOR_ANALYSIS}:")
            for game in games_skipped[:3]:  # Show first 3
                print(f"     - {game['away_team']} @ {game['home_team']} ({game['spread']:+.1f})")
            if len(games_skipped) > 3:
                print(f"     - ... and {len(games_skipped) - 3} more")
        
        print()
        
        # Run predictions for filtered games
        predictions = []
        successful_predictions = 0
        
        for i, game in enumerate(games_to_analyze, 1):
            home_team = game['home_team']
            away_team = game['away_team']

            priority_tag = "[HIGH]" if game['priority'] == 'HIGH' else "[MED]"
            print(f"[{i}/{len(games_to_analyze)}] {priority_tag} {away_team} @ {home_team} ({game['spread']:+.1f})", end=" -> ")
            
            try:
                # Generate prediction
                result = prediction_engine.generate_prediction(home_team, away_team, week=week)
                
                # Extract metrics
                edge_size = result.get('edge_size', 0)
                confidence = result.get('confidence_score', 0) * 100
                
                print(f"Edge: {edge_size:.1f}, Conf: {confidence:.0f}%", end="")
                
                # Check if this meets our thresholds
                if edge_size >= min_edge and confidence >= min_confidence:
                    # Extract prediction details
                    vegas_spread = result.get('vegas_spread', 'Unknown')
                    recommendation = result.get('recommendation', 'No recommendation')
                    data_quality = result.get('data_quality', 0)
                    factor_breakdown = result.get('factor_breakdown', {})
                    reasoning = result.get('reasoning', '')
                    
                    # Create prediction entry
                    from utils.prediction_storage import prediction_storage
                    prediction = prediction_storage.create_prediction_entry(
                        home_team=home_team,
                        away_team=away_team,
                        vegas_spread=vegas_spread,
                        predicted_edge=edge_size,
                        confidence=confidence,
                        recommendation=recommendation,
                        factor_breakdown=factor_breakdown,
                        data_quality=data_quality,
                        week=week,
                        rationale=reasoning
                    )
                    
                    predictions.append(prediction)
                    successful_predictions += 1
                    print(f" EDGE FOUND!")
                else:
                    print(f" -")

                # Delay between games to prevent rate limiting
                if i < len(games_to_analyze) and delay_minutes > 0:
                    next_game_time = datetime.now() + timedelta(minutes=delay_minutes)
                    print(f"   Waiting {delay_minutes} minutes before next game... (resumes at {next_game_time.strftime('%I:%M %p')})")
                    time.sleep(delay_minutes * 60)  # Convert to seconds

            except Exception as e:
                print(f" ERROR")
                continue
        
        # Summary
        print("=" * 70)
        print("PREDICTION RESULTS")
        print("=" * 70)

        if predictions:
            print(f"Found {successful_predictions} contrarian opportunities:")
            print()

            for i, pred in enumerate(predictions, 1):
                print(f"{i:2d}. {pred['recommendation']}")
                print(f"     Game: {pred['away_team']} @ {pred['home_team']}")
                print(f"     Edge: {pred['predicted_edge']:.1f} pts | Confidence: {pred['confidence']:.1f}%")
                if pred.get('bet_rationale'):
                    print(f"     Rationale: {pred['bet_rationale']}")
                print()
        else:
            print(f"No contrarian opportunities found")
            print(f"   Analyzed {len(games_to_analyze)} games (skipped {len(games_skipped)} blowouts)")
            print(f"   Try lowering --min-edge (current: {min_edge:.1f}) or --min-confidence (current: {min_confidence:.1f}%)")

        return predictions

    except Exception as e:
        print(f"Error in P4 predictions: {e}")
        return []


def main() -> int:
    """
    Main entry point for the College Football Market Edge Platform CLI.
    
    Returns:
        int: Exit code (0 for success, 1 for error)
    """
    try:
        # Parse arguments
        args = parse_arguments()
        
        # Setup logging FIRST
        setup_logging(args.debug, args.quiet)
        
        # Import heavy modules after logging is configured
        _ensure_imports()
        from data.schedule_client import CFBScheduleClient
        
        if args.debug:
            logging.debug(f"Arguments: {args}")
            logging.debug(f"Configuration: {config}")
        
        # Handle utility commands
        if args.list_teams:
            list_teams()
            return 0
        
        if args.list_games:
            list_games(args.list_games)
            return 0
        
        if args.validate_team:
            validate_team_name(args.validate_team)
            return 0
        
        if args.check_config:
            is_valid = check_configuration()
            return 0 if is_valid else 1
        
        # Validate configuration for prediction commands
        if not config.odds_api_key and not args.dry_run:
            logging.error("Odds API key required for predictions")
            logging.error("Set ODDS_API_KEY in environment or .env file")
            return 1
        
        start_time = time.time()
        
        # Handle prediction commands
        if args.home and args.away:
            # Validate teams
            home_normalized, away_normalized = validate_teams(args.home, args.away)
            if not home_normalized or not away_normalized:
                return 1
            
            # Run single prediction
            result = run_single_prediction(
                home_normalized, 
                away_normalized, 
                args.week,
                args.verbose, 
                args.show_factors
            )
            
            if args.format == 'json':
                import json
                # Convert EdgeClassification object to serializable format
                json_result = result.copy()
                if 'edge_classification_obj' in json_result:
                    edge_obj = json_result['edge_classification_obj']
                    json_result['edge_classification_obj'] = {
                        'edge_type': edge_obj.edge_type.value if hasattr(edge_obj.edge_type, 'value') else str(edge_obj.edge_type),
                        'recommended_action': edge_obj.recommended_action,
                        'explanation': edge_obj.explanation
                    }
                print(json.dumps(json_result, indent=2, default=str))
        
        elif args.analyze_week is not None:
            # Run weekly analysis - if week is 0, use current week logic
            week_to_analyze = args.analyze_week if args.analyze_week != 0 else _get_current_week()
            run_weekly_analysis(week_to_analyze, args.min_edge)
        
        elif args.analyze_week_p4 is not None:
            # Run P4 predictions - if week is 0, use current week logic
            week_to_analyze = args.analyze_week_p4 if args.analyze_week_p4 != 0 else _get_current_week()
            predictions = run_p4_predictions(week_to_analyze, args.min_edge, args.min_confidence, 
                                           max_spread=14.0, delay_minutes=args.delay)
            
            # Save predictions if any were found
            if predictions:
                from utils.prediction_storage import prediction_storage
                filepath = prediction_storage.save_weekly_predictions(predictions, week_to_analyze)
                print(f"Predictions saved to: {filepath}")
            else:
                print("No predictions to save (no edges found)")
        
        # Performance timing
        execution_time = time.time() - start_time
        if args.debug:
            logging.debug(f"Execution time: {execution_time:.2f} seconds")
        
        return 0
        
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
        return 1
    except Exception as e:
        if args.debug if 'args' in locals() else False:
            logging.exception("Unexpected error occurred")
        else:
            logging.error(f"Error: {e}")
        return 1


if __name__ == '__main__':
    sys.exit(main())