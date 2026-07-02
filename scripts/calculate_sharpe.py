#!/usr/bin/env python3
"""
Calculate Sharpe ratio for the CFB Contrarian Predictor engine.

Approach:
- Calculate return for each bet: +0.909 for win, -1.0 for loss
- Sharpe ratio = mean(returns) / std(returns)
"""

import json
import statistics
from pathlib import Path

WIN_RETURN = 0.909  # Win $90.91 on $100 bet
LOSS_RETURN = -1.0  # Lose $100 on $100 bet


def load_results(results_dir: Path) -> list[dict]:
    """Load all results files and return flattened list of game results."""
    all_results = []

    for results_file in sorted(results_dir.glob("*_results.json")):
        with open(results_file) as f:
            data = json.load(f)
            week = data["week"]
            for game in data["results"]:
                game["week"] = week
                all_results.append(game)

    return all_results


def calculate_home_covered(game: dict) -> bool:
    """Determine if home team covered the contrarian spread."""
    actual_spread = game["home_score"] - game["away_score"]
    return actual_spread > -game["contrarian_spread"]


def get_bet_return(game: dict) -> float:
    """Get the return for a single bet."""
    return WIN_RETURN if calculate_home_covered(game) else LOSS_RETURN


def calculate_sharpe_stats(games: list[dict]) -> dict:
    """Calculate Sharpe ratio statistics for a set of games."""
    if len(games) < 2:
        return {
            "total_games": len(games),
            "mean_return": None,
            "std_return": None,
            "sharpe_ratio": None,
        }

    returns = [get_bet_return(game) for game in games]
    mean_return = statistics.mean(returns)
    std_return = statistics.stdev(returns)
    sharpe_ratio = mean_return / std_return if std_return > 0 else None

    return {
        "total_games": len(games),
        "mean_return": mean_return,
        "std_return": std_return,
        "sharpe_ratio": sharpe_ratio,
    }


def calculate_sharpe(results: list[dict]) -> dict:
    """Calculate overall and per-week Sharpe ratio."""
    # Overall Sharpe
    overall = calculate_sharpe_stats(results)

    # Per-week Sharpe
    games_by_week = {}
    for game in results:
        week = game["week"]
        if week not in games_by_week:
            games_by_week[week] = []
        games_by_week[week].append(game)

    weekly = {
        week: calculate_sharpe_stats(games)
        for week, games in sorted(games_by_week.items())
    }

    return {"overall": overall, "weekly": weekly}


def format_value(value, fmt: str) -> str:
    """Format a value, handling None."""
    return "N/A" if value is None else fmt.format(value)


def main():
    project_root = Path(__file__).parent.parent
    results_dir = project_root / "data" / "results"

    results = load_results(results_dir)
    sharpe = calculate_sharpe(results)

    # Print results
    print("=" * 60)
    print("CFB Contrarian Predictor - Sharpe Ratio Report")
    print("=" * 60)
    print(f"Win Return: +{WIN_RETURN:.3f} | Loss Return: {LOSS_RETURN:.3f}")
    print()

    print("OVERALL SHARPE RATIO")
    print("-" * 40)
    print(f"Total Games:  {sharpe['overall']['total_games']}")
    print(f"Mean Return:  {format_value(sharpe['overall']['mean_return'], '{:+.4f}')}")
    print(f"Std Dev:      {format_value(sharpe['overall']['std_return'], '{:.4f}')}")
    print(f"Sharpe Ratio: {format_value(sharpe['overall']['sharpe_ratio'], '{:+.4f}')}")
    print()

    print("WEEKLY BREAKDOWN")
    print("-" * 60)
    print(f"{'Week':<6} {'Games':<8} {'Mean':<10} {'Std':<10} {'Sharpe':<10}")
    print("-" * 60)

    for week, stats in sharpe["weekly"].items():
        print(
            f"{week:<6} "
            f"{stats['total_games']:<8} "
            f"{format_value(stats['mean_return'], '{:+.4f}'):<10} "
            f"{format_value(stats['std_return'], '{:.4f}'):<10} "
            f"{format_value(stats['sharpe_ratio'], '{:+.4f}'):<10}"
        )

    print()


if __name__ == "__main__":
    main()
