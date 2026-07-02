#!/usr/bin/env python3
"""
Calculate accuracy of the CFB Contrarian Predictor engine.

Accuracy Definition:
- actual_spread = home_score - away_score
- home_covered = actual_spread > -contrarian_spread
- accuracy = games_where_home_covered / total_games
"""

import json
from pathlib import Path


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


def calculate_accuracy(results: list[dict]) -> dict:
    """Calculate overall and per-week accuracy."""
    # Overall accuracy
    total_games = len(results)
    games_covered = sum(1 for game in results if calculate_home_covered(game))
    overall_accuracy = games_covered / total_games if total_games > 0 else 0

    # Per-week accuracy
    weekly_stats = {}
    for game in results:
        week = game["week"]
        if week not in weekly_stats:
            weekly_stats[week] = {"total": 0, "covered": 0}
        weekly_stats[week]["total"] += 1
        if calculate_home_covered(game):
            weekly_stats[week]["covered"] += 1

    weekly_accuracy = {
        week: stats["covered"] / stats["total"]
        for week, stats in sorted(weekly_stats.items())
    }

    return {
        "overall": {
            "total_games": total_games,
            "games_covered": games_covered,
            "accuracy": overall_accuracy,
        },
        "weekly": {
            week: {
                "total_games": weekly_stats[week]["total"],
                "games_covered": weekly_stats[week]["covered"],
                "accuracy": acc,
            }
            for week, acc in weekly_accuracy.items()
        },
    }


def main():
    project_root = Path(__file__).parent.parent
    results_dir = project_root / "data" / "results"

    results = load_results(results_dir)
    accuracy = calculate_accuracy(results)

    # Print results
    print("=" * 50)
    print("CFB Contrarian Predictor - Accuracy Report")
    print("=" * 50)
    print()

    print("OVERALL ACCURACY")
    print("-" * 30)
    print(f"Total Games:   {accuracy['overall']['total_games']}")
    print(f"Games Covered: {accuracy['overall']['games_covered']}")
    print(f"Accuracy:      {accuracy['overall']['accuracy']:.1%}")
    print()

    print("WEEKLY BREAKDOWN")
    print("-" * 30)
    print(f"{'Week':<6} {'Games':<8} {'Covered':<10} {'Accuracy':<10}")
    print("-" * 30)

    for week, stats in accuracy["weekly"].items():
        print(f"{week:<6} {stats['total_games']:<8} {stats['games_covered']:<10} {stats['accuracy']:.1%}")

    print()


if __name__ == "__main__":
    main()
