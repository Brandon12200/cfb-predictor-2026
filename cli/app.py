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

from data.team_registry import get_conference_map
from cli.args import parse_arguments

# Heavy imports moved to main() to allow logging setup first
# Global variables for lazy loading
config = None
normalizer = None
data_manager = None
prediction_engine = None

def _ensure_imports():
    """Ensure all heavy modules are imported.

    Reverse-audit A2: the standalone `confidence_calculator`/`edge_detector` were dropped here
    with the rest of that cluster — the ratified `prediction_engine` is the only scoring surface.
    """
    global config, normalizer, data_manager, prediction_engine
    if config is None:
        from config import config as _config
        from utils.normalizer import normalizer as _normalizer
        from data.data_manager import data_manager as _data_manager
        from engine.prediction_engine import prediction_engine as _prediction_engine

        config = _config
        normalizer = _normalizer
        data_manager = _data_manager
        prediction_engine = _prediction_engine


def _get_current_week() -> int:
    """Derive the current CFB week from today's date via the season calendar.

    Replaces the old silent week-1 default: the week is echoed on every run and,
    when the date falls outside the season, the run hard-fails (exit code 2)
    instead of guessing. Omitting --week therefore resolves to the same value a
    correct explicit --week would supply.
    """
    from datetime import datetime
    from utils.season_calendar import resolve_week, WeekInferenceError

    today = datetime.now().date()
    try:
        week = resolve_week(None, today=today)
    except WeekInferenceError as exc:
        logging.error(str(exc))
        raise SystemExit(2)
    print(f"Week {week} — inferred from {today.isoformat()}")
    return week


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
    
    # Conference membership comes from the single source (data/conferences.py).
    conferences = get_conference_map()
    
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
    print(f"  Odds API budget: {config.odds_monthly_budget} credits/month (D5); ESPN {config.rate_limit_espn}/min")
    
    # Factor weights, read LIVE from the ratified registry (reverse-audit A5). The old display
    # printed `config.py`'s stale legacy 40/40/20 category constants, which contradicted the
    # ratified 3b.2 shares and fed nothing — the registry is the single source of truth.
    # Shares are shown BOTH raw and as a share of the additive budget: the MODIFIER category
    # (market sentiment) is multiplicative, so the ratified 3b.2 percentages are quoted against
    # the additive subtotal, not the raw total.
    from factors.factor_registry import factor_registry as _registry
    by_category: dict[str, float] = {}
    for _f in _registry.factors.values():
        by_category[_f.category] = by_category.get(_f.category, 0.0) + _f.weight
    total_weight = sum(by_category.values())
    additive = total_weight - by_category.get('market', 0.0)
    print(f"\nFactor Weights (live registry; total: {total_weight:.3f}):")
    for _cat in sorted(by_category, key=lambda c: -by_category[c]):
        _share = f"{by_category[_cat] / additive:.1%} of additive" if _cat != 'market' else "multiplicative modifier"
        print(f"  {_cat}: {by_category[_cat]:.1%}  ({_share})")
    
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
        
        # Power 4 conference membership from the single source (data/conferences.py).
        power4_teams = get_conference_map()
        
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
        
        # Power 4 conference membership from the single source (data/conferences.py).
        power4_teams = get_conference_map()
        
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
                        rationale=reasoning,
                        # Phase 3c L3/L4 pass-through (not silently dropped; full schema is 3d)
                        prediction_type=result.get('prediction_type'),
                        no_bet=result.get('no_bet'),
                        confidence_tier=result.get('confidence_tier')
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
                tier = pred.get('confidence_tier')
                tier_str = f" | Tier {tier}" if tier else (" | NO BET" if pred.get('no_bet') else "")
                print(f"     Edge: {pred['predicted_edge']:.1f} pts | Confidence: {pred['confidence']:.1f}%{tier_str}")
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


def _confidence_label(uncertainty: float) -> str:
    """Qualitative confidence from rating uncertainty (hypothetical output)."""
    if uncertainty >= 0.66:
        return "LOW"
    if uncertainty >= 0.4:
        return "MEDIUM"
    return "HIGH"


def run_hypothetical(argv: list) -> int:
    """`main.py hypothetical` (SPEC §6.4): price any matchup with the in-house power
    rating — model spread, factor breakdown, confidence, caveats. No Vegas line needed.
    Prices off the freshest built snapshot (reads ONLY the snapshot, offline)."""
    import json
    from datetime import date as _date

    parser = argparse.ArgumentParser(
        prog="main.py hypothetical",
        description="Price a hypothetical matchup with the in-house power rating.")
    parser.add_argument("--home", required=True)
    parser.add_argument("--away", required=True)
    parser.add_argument("--neutral-site", action="store_true")
    parser.add_argument("--venue", help="Venue team key (e.g. a neutral host); defaults to home.")
    parser.add_argument("--date", help="Game date YYYY-MM-DD (schedule-intel + week inference).")
    parser.add_argument("--week", type=int, help="Override the snapshot week to price from.")
    parser.add_argument("--show-factors", action="store_true")
    parser.add_argument("--format", choices=["table", "json"], default="table")
    parser.add_argument("--year", type=int, default=2026)
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    setup_logging(args.debug, args.quiet)
    _ensure_imports()

    from data.snapshot.store import (
        SnapshotNotFoundError,
        latest_snapshot_week,
        load_snapshot,
    )
    from engine.matchup_pricer import compute_ratings_for_snapshot, price
    from utils.season_calendar import resolve_week

    home = normalizer.normalize(args.home)
    away = normalizer.normalize(args.away)
    if not home:
        print(f"Could not resolve home team '{args.home}'. Check spelling.")
        return 1
    if not away:
        print(f"Could not resolve away team '{args.away}'. Check spelling.")
        return 1
    if home == away:
        print("Home and away teams cannot be the same.")
        return 1

    # Resolve which snapshot to price from: explicit --week, else infer from --date/today,
    # then use the freshest built snapshot at or before that week.
    game_date = None
    if args.date:
        try:
            game_date = _date.fromisoformat(args.date)
        except ValueError:
            print(f"Invalid --date '{args.date}' (expected YYYY-MM-DD).")
            return 1
    try:
        target_week = resolve_week(args.week, game_date)
    except Exception:  # noqa: BLE001 — date outside the season is not fatal here
        target_week = None
    week = latest_snapshot_week(args.year, not_after=target_week)
    if week is None:
        week = latest_snapshot_week(args.year)
    if week is None:
        print(f"No snapshot built for {args.year}. Run `python scripts/build_snapshot.py --week N`.")
        return 1

    try:
        snap = load_snapshot(week, args.year)
    except SnapshotNotFoundError as exc:
        print(str(exc))
        return 1
    data = snap["data"]
    ratings = compute_ratings_for_snapshot(snap)
    priced = price(
        home, away, ratings=ratings, season_games=data.get("games", []),
        venues=data.get("venues", {}), sp_ratings=data.get("sp_ratings", {}),
        returning_production=data.get("returning_production", {}),
        week=snap["meta"].get("week"), game_date=args.date,
        neutral_site=args.neutral_site, venue=args.venue)

    if args.format == "json":
        payload = priced.to_dict()
        payload["snapshot_id"] = snap["meta"].get("snapshot_id")
        payload["snapshot_week"] = week
        payload["confidence"] = _confidence_label(priced.rating_uncertainty)
        print(json.dumps(payload, indent=2, default=str))
        return 0

    _print_hypothetical(priced, snap, week, args.show_factors)
    return 0


def _print_hypothetical(p, snap: dict, week: int, show_factors: bool) -> None:
    """Readable hypothetical output, mirroring the real-game format (spread, factors,
    confidence, caveats)."""
    site = "neutral site" if p.neutral_site else f"@ {p.home_team}"
    fav, by = (p.home_team, -p.model_spread) if p.model_spread < 0 else (p.away_team, p.model_spread)
    print(f"\nHypothetical: {p.away_team} {site} — priced from {snap['meta'].get('year')} "
          f"week {week} snapshot ({snap['meta'].get('snapshot_id', '')[:12]})")
    print(f"  Model spread : {p.home_team} {p.model_spread:+.1f}")
    if abs(p.model_spread) < 1e-9:
        print("  Pick'em (no model edge)")
    else:
        print(f"  Model favors : {fav} by {by:.1f}")
    print(f"  Components    : rating {p.rating_component:+.1f} (weight "
          f"{p.rating_signal_weight:.0%}, uncertainty {p.rating_uncertainty:.2f}) | "
          f"home field {p.breakdown['hfa_points']:+.1f} | schedule {p.schedule_component:+.1f}")
    print(f"  Ratings       : {p.home_team} {p.home_rating:.0f} ({p.home_prior_source}) | "
          f"{p.away_team} {p.away_rating:.0f} ({p.away_prior_source})")
    print(f"  Confidence    : {_confidence_label(p.rating_uncertainty)}")
    if p.caveats:
        print("  Caveats:")
        for c in p.caveats:
            print(f"    - {c}")
    if show_factors:
        print("  Schedule factors (points, + favors home):")
        for k, v in (p.breakdown.get("schedule") or {}).items():
            print(f"    {k:12s}: {v:+.2f}")
        if not p.breakdown.get("schedule"):
            print("    (none active)")
        print(f"  home intel: {p.breakdown.get('home_intel')}")
        print(f"  away intel: {p.breakdown.get('away_intel')}")


# --------------------------------------------------------------------------- #
# `main.py project` — experimental season projections + belief drift (SPEC §6.5)
# --------------------------------------------------------------------------- #
def _projections_dir():
    from pathlib import Path
    return Path(__file__).resolve().parent.parent / "data" / "projections"


def _projection_weeks(year: int) -> list:
    weeks = []
    for p in _projections_dir().glob(f"{year}_week_*.json"):
        try:
            weeks.append(int(p.stem.split("_week_")[1]))
        except (ValueError, IndexError):
            continue
    return sorted(weeks)


def _load_projection(year: int, week: int) -> dict:
    import json
    return json.loads((_projections_dir() / f"{year}_week_{week:02d}.json").read_text())


def _proj_wins(projection: dict, team: str):
    """Defensive across schema evolution: tolerate older files missing a team/field."""
    return (projection.get("teams", {}).get(team) or {}).get("projected_wins")


def run_project(argv: list) -> int:
    """`main.py project` (SPEC §6.5): render experimental season win-total projections +
    week-over-week belief drift from the committed `data/projections/` files (offline; build
    them with `scripts/build_projections.py`). Experimental — never drives bet recommendations."""
    import json

    parser = argparse.ArgumentParser(
        prog="main.py project",
        description="Experimental season win-total projections + belief drift (never drives bets).")
    parser.add_argument("--team", help="One team's per-game breakdown + drift history.")
    parser.add_argument("--history", action="store_true", help="Week-by-week projected wins.")
    parser.add_argument("--week", type=int, help="As-of week (default: latest available file).")
    parser.add_argument("--format", choices=["table", "json"], default="table")
    parser.add_argument("--year", type=int, default=2026)
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)
    setup_logging(args.debug, args.quiet)

    weeks = _projection_weeks(args.year)
    if not weeks:
        print(f"No projections for {args.year}. Run `python scripts/build_projections.py --week N`.")
        return 1
    week = args.week if args.week is not None else weeks[-1]
    if week not in weeks:
        print(f"No projection file for {args.year} week {week}. Available: {weeks}")
        return 1

    latest = _load_projection(args.year, week)
    prior_weeks = [w for w in weeks if w < week]
    prev = _load_projection(args.year, prior_weeks[-1]) if prior_weeks else None
    preseason = _load_projection(args.year, weeks[0]) if weeks[0] < week else None

    if args.team:
        _ensure_imports()
        team = normalizer.normalize(args.team)
        if not team or team not in latest.get("teams", {}):
            print(f"No projection for team '{args.team}'"
                  + (f" (resolved '{team}')" if team else "") + ".")
            return 1
        return _project_team(args, team, latest, week, weeks)

    # Slate view: team | rating | proj wins | Δwk | Δpre, sorted by projected wins.
    rows = []
    for t, r in latest.get("teams", {}).items():
        pw = r.get("projected_wins")
        dw = (pw - _proj_wins(prev, t)) if prev and _proj_wins(prev, t) is not None and pw is not None else None
        dp = (pw - _proj_wins(preseason, t)) if preseason and _proj_wins(preseason, t) is not None and pw is not None else None
        rows.append({"team": t, "rating": r.get("rating"), "projected_wins": pw,
                     "delta_week": None if dw is None else round(dw, 2),
                     "delta_preseason": None if dp is None else round(dp, 2)})
    rows.sort(key=lambda x: (x["projected_wins"] is None, -(x["projected_wins"] or 0)))

    if args.format == "json":
        print(json.dumps({"year": args.year, "week": week,
                          "experimental": latest.get("meta", {}).get("experimental", True),
                          "has_drift": prev is not None, "teams": rows}, indent=2))
        return 0
    if args.history:
        return _project_history(args, weeks, latest)
    _print_projection_table(rows, week, latest, prev is not None)
    return 0


def _print_projection_table(rows: list, week: int, latest: dict, has_drift: bool) -> None:
    print(f"\nSeason projections — {latest['meta'].get('year')} as of week {week} "
          f"(EXPERIMENTAL — never drives bets; SPEC §6.5)")
    if not has_drift:
        print("  (only one week of projections so far — drift begins once week 2 exists.)")
    print(f"  {'TEAM':<20} {'RATING':>7} {'PROJ W':>7} {'ΔWK':>6} {'ΔPRE':>6}")
    for r in rows:
        dw = "  —" if r["delta_week"] is None else f"{r['delta_week']:+.2f}"
        dp = "  —" if r["delta_preseason"] is None else f"{r['delta_preseason']:+.2f}"
        pw = "—" if r["projected_wins"] is None else f"{r['projected_wins']:.2f}"
        print(f"  {r['team']:<20} {r['rating']:>7.0f} {pw:>7} {dw:>6} {dp:>6}")
    movers = [r for r in rows if r["delta_week"] is not None]
    if movers:
        risers = sorted(movers, key=lambda x: -x["delta_week"])[:5]
        fallers = sorted(movers, key=lambda x: x["delta_week"])[:5]
        print("\n  Biggest risers (Δ vs last week): "
              + ", ".join(f"{r['team']} {r['delta_week']:+.2f}" for r in risers if r["delta_week"] > 0))
        print("  Biggest fallers: "
              + ", ".join(f"{r['team']} {r['delta_week']:+.2f}" for r in fallers if r["delta_week"] < 0))
    cov = latest.get("meta", {}).get("coverage", {})
    unscheduled = cov.get("unscheduled") or []
    if unscheduled:
        print(f"\n  Coverage: {cov.get('scheduled')}/{cov.get('fbs_total')} FBS teams projected. "
              f"No schedule data (shown as —): {', '.join(unscheduled)} "
              f"(known snapshot gap; see docs/PHASE2_NOTES.md).")


def _project_team(args, team: str, latest: dict, week: int, weeks: list) -> int:
    import json
    # Defensive across schema evolution: an older week's file may predate a field, so use
    # `.get` with defaults everywhere (matches the slate/history reader; SPEC §6.5 2b).
    rec = latest["teams"].get(team, {})
    history = [(w, _proj_wins(_load_projection(args.year, w), team)) for w in weeks]
    if args.format == "json":
        print(json.dumps({"team": team, "week": week, "record": rec,
                          "history": [{"week": w, "projected_wins": pw} for w, pw in history]},
                         indent=2))
        return 0
    print(f"\n{team} — {latest['meta'].get('year')} projection as of week {week} (EXPERIMENTAL)")
    if rec.get("schedule_missing"):
        print("  No schedule data for this team in the snapshot — cannot project win total "
              "(known coverage gap; see docs/PHASE2_NOTES.md).")
        return 0
    pw, pl = rec.get("projected_wins"), rec.get("projected_losses")
    pw_s = "—" if pw is None else f"{pw:.2f}"
    pl_s = "—" if pl is None else f"{pl:.2f}"
    unc = rec.get("rating_uncertainty")
    unc_s = "—" if unc is None else f"{unc:.2f}"
    print(f"  rating {rec.get('rating', 0):.0f} (uncertainty {unc_s}) | "
          f"record {rec.get('wins_so_far', 0)}-{rec.get('losses_so_far', 0)} | "
          f"remaining {rec.get('remaining', 0)} | projected {pw_s}-{pl_s}")
    drift = " ".join(f"wk{w}:{p:.2f}" for w, p in history if p is not None)
    print(f"  drift: {drift}")
    print(f"  {'WK':>3} {'OPP':<20} {'SITE':<8} {'SPREAD':>7} {'WIN%':>6}  RESULT")
    for g in rec.get("games", []):
        site = "neutral" if g.get("neutral_site") else ("home" if g.get("is_home") else "away")
        spread = "—" if g.get("model_spread") is None else f"{g['model_spread']:+.1f}"
        res = "" if not g.get("completed") else ("W" if g.get("won") else "L")
        wp = g.get("win_prob")
        wp_s = "  — " if wp is None else f"{wp * 100:>4.0f}%"
        print(f"  {g.get('week', ''):>3} {g.get('opponent', ''):<20} {site:<8} {spread:>7} "
              f"{wp_s:>6}  {res}")
    return 0


def _project_history(args, weeks: list, latest: dict) -> int:
    teams = sorted(latest.get("teams", {}), key=lambda t: -(_proj_wins(latest, t) or 0))
    by_week = {w: _load_projection(args.year, w) for w in weeks}
    print(f"\nProjected wins by week — {latest['meta'].get('year')} (EXPERIMENTAL)")
    print(f"  {'TEAM':<20} " + " ".join(f"wk{w:>2}" for w in weeks))
    for t in teams:
        cells = []
        for w in weeks:
            pw = _proj_wins(by_week[w], t)
            cells.append("  —  " if pw is None else f"{pw:>5.2f}")
        print(f"  {t:<20} " + " ".join(cells))
    return 0
