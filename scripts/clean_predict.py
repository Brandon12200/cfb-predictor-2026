#!/usr/bin/env python3
"""
Clean prediction interface without all the logging noise.
"""

import sys
import os
import logging
import warnings

# Add parent directory to path so we can import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Suppress all warnings and info logs
warnings.filterwarnings('ignore')
logging.getLogger().setLevel(logging.CRITICAL)
logging.getLogger('root').setLevel(logging.CRITICAL)

# Disable all logging before imports
logging.disable(logging.CRITICAL)

from engine.prediction_engine import prediction_engine
from utils.normalizer import normalizer
from engine.edge_detector import edge_detector
from engine.confidence_calculator import confidence_calculator


def clean_predict(home_team: str, away_team: str):
    """Run a clean prediction without logging noise."""
    
    # Normalize team names
    home_normalized = normalizer.normalize(home_team)
    away_normalized = normalizer.normalize(away_team)
    
    if not home_normalized or not away_normalized:
        print(f"❌ Could not recognize team names: {home_team} or {away_team}")
        return
    
    print(f"\n🏈 CFB CONTRARIAN PREDICTOR")
    print(f"{'='*50}")
    print(f"📍 {away_normalized} @ {home_normalized}")
    print(f"{'='*50}")
    
    # Generate prediction
    result = prediction_engine.generate_prediction(home_normalized, away_normalized)
    
    if 'error' in result:
        print(f"\n❌ Error: {result['error']}")
        return
    
    # Display results
    vegas_spread = result.get('vegas_spread')
    contrarian_spread = result.get('contrarian_spread')
    edge_size = result.get('edge_size', 0)
    confidence = result.get('confidence_score', 0)
    
    print(f"\n📊 BETTING LINES:")
    if vegas_spread is not None:
        print(f"   Vegas Line: {home_normalized} {vegas_spread:+.1f}")
        if contrarian_spread is not None:
            print(f"   Our Pick: {home_normalized} {contrarian_spread:+.1f}")
            print(f"   Edge Size: {edge_size:.1f} points")
    else:
        print(f"   No betting line available")
    
    print(f"\n🎯 RECOMMENDATION:")
    print(f"   {result.get('recommendation', 'No recommendation available')}")
    print(f"   Confidence: {confidence:.1%}")
    
    # Show key factors if significant edge
    if edge_size and edge_size >= 1.0:
        print(f"\n💡 KEY FACTORS:")
        category_adj = result.get('category_adjustments', {})
        if category_adj:
            for category, adjustment in category_adj.items():
                if abs(adjustment) > 0.1:
                    category_name = category.replace('_', ' ').title()
                    direction = "favors " + (home_normalized if adjustment > 0 else away_normalized)
                    print(f"   • {category_name}: {direction} ({adjustment:+.2f})")
    
    # Data quality warning if low
    data_quality = result.get('data_quality', 0)
    if data_quality < 0.6:
        print(f"\n⚠️  Note: Limited data availability ({data_quality:.0%}) may affect accuracy")
    
    print(f"\n{'='*50}\n")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python clean_predict.py <home_team> <away_team>")
        print("Example: python clean_predict.py Alabama Auburn")
        sys.exit(1)
    
    clean_predict(sys.argv[1], sys.argv[2])