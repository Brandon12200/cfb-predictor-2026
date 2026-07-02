#!/usr/bin/env python3
"""
Calculate ROI of the CFB Contrarian Predictor engine.

Assumptions:
- Flat $100 bets on every game
- Standard -110 odds (bet $100 to win $90.91)

Formula:
- Win: profit $90.91
- Loss: lose $100
- Total wagered = total_games × $100
- Profit = (wins × 90.91) - (losses × 100)
- ROI = profit / total_wagered
"""

import json
from pathlib import Path

BET_AMOUNT = 100.00
WIN_PROFIT = 90.91


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


def calculate_roi_stats(games: list[dict]) -> dict:
    """Calculate ROI statistics for a set of games."""
    total_games = len(games)
    wins = sum(1 for game in games if calculate_home_covered(game))
    losses = total_games - wins

    total_wagered = total_games * BET_AMOUNT
    profit = (wins * WIN_PROFIT) - (losses * BET_AMOUNT)
    roi = profit / total_wagered if total_wagered > 0 else 0

    return {
        "total_games": total_games,
        "wins": wins,
        "losses": losses,
        "total_wagered": total_wagered,
        "profit": profit,
        "roi": roi,
    }


def calculate_roi(results: list[dict]) -> dict:
    """Calculate overall and per-week ROI."""
    # Overall ROI
    overall = calculate_roi_stats(results)

    # Per-week ROI
    games_by_week = {}
    for game in results:
        week = game["week"]
        if week not in games_by_week:
            games_by_week[week] = []
        games_by_week[week].append(game)

    weekly = {
        week: calculate_roi_stats(games)
        for week, games in sorted(games_by_week.items())
    }

    return {"overall": overall, "weekly": weekly}


def main():
    project_root = Path(__file__).parent.parent
    results_dir = project_root / "data" / "results"

    results = load_results(results_dir)
    roi = calculate_roi(results)

    # Print results
    print("=" * 60)
    print("CFB Contrarian Predictor - ROI Report")
    print("=" * 60)
    print(f"Bet Amount: ${BET_AMOUNT:.2f} | Win Profit: ${WIN_PROFIT:.2f} | Odds: -110")
    print()

    print("OVERALL ROI")
    print("-" * 40)
    print(f"Total Games:   {roi['overall']['total_games']}")
    print(f"Wins:          {roi['overall']['wins']}")
    print(f"Losses:        {roi['overall']['losses']}")
    print(f"Total Wagered: ${roi['overall']['total_wagered']:,.2f}")
    print(f"Profit:        ${roi['overall']['profit']:+,.2f}")
    print(f"ROI:           {roi['overall']['roi']:+.2%}")
    print()

    print("WEEKLY BREAKDOWN")
    print("-" * 60)
    print(f"{'Week':<6} {'W-L':<8} {'Wagered':<12} {'Profit':<12} {'ROI':<10}")
    print("-" * 60)

    for week, stats in roi["weekly"].items():
        wl = f"{stats['wins']}-{stats['losses']}"
        print(
            f"{week:<6} "
            f"{wl:<8} "
            f"${stats['total_wagered']:>8,.2f}   "
            f"${stats['profit']:>+8,.2f}   "
            f"{stats['roi']:>+7.2%}"
        )

    print()


if __name__ == "__main__":
    main()
