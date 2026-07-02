#!/usr/bin/env python3
"""
Analyze Week 1 prediction accuracy and performance.
"""

import json
from pathlib import Path
from typing import Dict, List

def analyze_results():
    """Analyze the accuracy of Week 1 predictions."""
    
    # Load results
    results_file = Path("data/results/2025_week_01_results.json")
    with open(results_file) as f:
        results_data = json.load(f)
    
    results = results_data["results"]
    
    # Overall accuracy
    total = len(results)
    correct = sum(1 for r in results if r["prediction_correct"])
    accuracy = (correct / total) * 100 if total > 0 else 0
    
    print("=" * 60)
    print("WEEK 1 PREDICTION PERFORMANCE ANALYSIS")
    print("=" * 60)
    print(f"\n📊 OVERALL ACCURACY: {correct}/{total} = {accuracy:.1f}%\n")
    
    # Break down by prediction type
    by_type = {}
    for result in results:
        pred_type = result["prediction_type"]
        if pred_type not in by_type:
            by_type[pred_type] = {"correct": 0, "total": 0, "games": []}
        by_type[pred_type]["total"] += 1
        if result["prediction_correct"]:
            by_type[pred_type]["correct"] += 1
        by_type[pred_type]["games"].append(result)
    
    print("ACCURACY BY PREDICTION TYPE:")
    print("-" * 40)
    for pred_type, stats in by_type.items():
        type_accuracy = (stats["correct"] / stats["total"]) * 100 if stats["total"] > 0 else 0
        print(f"{pred_type}: {stats['correct']}/{stats['total']} = {type_accuracy:.1f}%")
    
    # Detailed game-by-game analysis
    print("\n" + "=" * 60)
    print("GAME-BY-GAME RESULTS:")
    print("=" * 60)
    
    for result in results:
        status = "✅ CORRECT" if result["prediction_correct"] else "❌ INCORRECT"
        
        print(f"\n{result['away_team']} @ {result['home_team']}")
        print(f"  Final Score: {result['away_score']}-{result['home_score']}")
        print(f"  Actual Spread: {result['actual_spread']}")
        print(f"  Vegas Spread: {result['vegas_spread']}")
        print(f"  Contrarian Spread: {result['contrarian_spread']}")
        print(f"  Confidence: {result['confidence']:.1f}%")
        print(f"  Prediction Type: {result['prediction_type']}")
        print(f"  Result: {status}")
        
        # Analyze the miss if incorrect
        if not result["prediction_correct"]:
            spread_diff = abs(result['actual_spread'] - result['vegas_spread'])
            print(f"  ⚠️  Missed by {spread_diff:.1f} points vs Vegas")
    
    # Biggest surprises (games that went opposite of prediction)
    print("\n" + "=" * 60)
    print("BIGGEST SURPRISES (Incorrect Predictions):")
    print("=" * 60)
    
    incorrect = [r for r in results if not r["prediction_correct"]]
    incorrect.sort(key=lambda x: x["confidence"], reverse=True)
    
    for result in incorrect[:5]:  # Top 5 surprises
        spread_miss = abs(result['actual_spread'] - result['contrarian_spread'])
        print(f"\n{result['away_team']} @ {result['home_team']}")
        print(f"  Confidence: {result['confidence']:.1f}%")
        print(f"  Expected Spread: {result['contrarian_spread']}")
        print(f"  Actual Spread: {result['actual_spread']}")
        print(f"  Missed by: {spread_miss:.1f} points")
    
    # Best predictions
    print("\n" + "=" * 60)
    print("BEST PREDICTIONS (Correct with High Confidence):")
    print("=" * 60)
    
    correct_preds = [r for r in results if r["prediction_correct"]]
    correct_preds.sort(key=lambda x: x["confidence"], reverse=True)
    
    for result in correct_preds:
        print(f"\n{result['away_team']} @ {result['home_team']}")
        print(f"  Confidence: {result['confidence']:.1f}%")
        print(f"  Contrarian Spread: {result['contrarian_spread']}")
        print(f"  Actual Spread: {result['actual_spread']}")
        print(f"  Type: {result['prediction_type']}")
    
    # Statistical summary
    print("\n" + "=" * 60)
    print("STATISTICAL SUMMARY:")
    print("=" * 60)
    
    avg_confidence_correct = sum(r["confidence"] for r in results if r["prediction_correct"]) / max(correct, 1)
    avg_confidence_incorrect = sum(r["confidence"] for r in results if not r["prediction_correct"]) / max(total - correct, 1)
    
    print(f"\nAverage Confidence (Correct): {avg_confidence_correct:.1f}%")
    print(f"Average Confidence (Incorrect): {avg_confidence_incorrect:.1f}%")
    
    # Check if contrarian picks performed better
    contrarian_games = [r for r in results if "CONTRARIAN" in r["prediction_type"]]
    consensus_games = [r for r in results if "CONSENSUS" in r["prediction_type"]]
    
    contrarian_correct = sum(1 for r in contrarian_games if r["prediction_correct"])
    consensus_correct = sum(1 for r in consensus_games if r["prediction_correct"])
    
    if contrarian_games:
        contrarian_accuracy = (contrarian_correct / len(contrarian_games)) * 100
        print(f"\nContrarian Picks: {contrarian_correct}/{len(contrarian_games)} = {contrarian_accuracy:.1f}%")
    
    if consensus_games:
        consensus_accuracy = (consensus_correct / len(consensus_games)) * 100
        print(f"Consensus Picks: {consensus_correct}/{len(consensus_games)} = {consensus_accuracy:.1f}%")
    
    print("\n" + "=" * 60)

if __name__ == "__main__":
    analyze_results()