"""CLI argument parsing and validation (extracted from main.py, SPEC §4.7)."""

import argparse


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


