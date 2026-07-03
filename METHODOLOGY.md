# Prediction Methodology

## Overview

This document outlines the methodology for the College Football Market Edge Platform's contrarian prediction system, developed as a forward-testing experiment in market efficiency and quantitative sports betting analysis.

## Model Development Timeline

### Pre-Season Development (July - August 2025)
- **July 16, 2025**: Initial commit - project foundation
- **August 4-7, 2025**: Data integration and factor framework
- **August 25, 2025**: **FINAL MODEL LOCK** - Last modification to core prediction engine
- **August 28, 2025**: Season start - First predictions generated (Week 1)

### In-Season Operation (August 28 - Present)
**Zero modifications to prediction algorithm.** All commits since model lock have been:
1. Data collection (weekly predictions and results)
2. Bug fixes for data fetching (API issues causing missed games)
3. Infrastructure additions (testing/validation tools not used in production)

## Factor Weights and Point Adjustments

| Category | Weight | Factors | Typical Adjustment |
|----------|--------|---------|-------------------|
| Primary | 60% | Scheduling Fatigue | ±3.5 pts max |
| Primary | 60% | Head-to-Head Record | ±2.0 pts max |
| Primary | 60% | Desperation Index | ±2.5 pts max |
| Secondary | 30% | Experience Differential | ±1.5 pts max |
| Secondary | 30% | Pressure Situation | ±1.5 pts max |
| Secondary | 30% | Revenge Game | ±1.0 pts max |
| Secondary | 30% | Lookahead Spot | ±1.5 pts max |
| Secondary | 30% | Point Differential Trends | ±1.0 pts max |
| Secondary | 30% | Close Game Performance | ±1.0 pts max |
| Secondary | 30% | Style Mismatch | ±1.5 pts max |
| Modifier | 10% | Market Sentiment | 0.5x–1.5x multiplier |

Activation thresholds vary by factor. Signals below threshold are zeroed out to avoid noise from weak signals.

## Core Algorithm

**Location**: `engine/prediction_engine.py`
**Last Modified**: August 25, 2025 (commit `38c5a74`)
**Status**: Locked for entire 2025 season

### Verification Command
```bash
# Verify no changes to core prediction logic since lock
git diff 38c5a74..HEAD -- engine/prediction_engine.py
# Expected output: (empty - no changes)
```

## Prediction Approach

### Philosophy
The system generates **contrarian predictions** by layering human factor adjustments onto Vegas market consensus. Rather than building spreads from scratch, it identifies where the market may be mispricing games based on:
- Situational context
- Coaching advantages
- Momentum factors

### Process Flow
1. Fetch Vegas consensus spread (market baseline)
2. Calculate factor adjustments across multiple dimensions
3. Apply adjustments to generate contrarian spread
4. Measure edge size (difference from market)
5. Assess confidence and generate recommendation

### Prediction Categories
- **SLIGHT_CONTRARIAN**: 0.5-1.5 point edge
- **MODERATE_CONTRARIAN**: 1.5-3.0 point edge
- **STRONG_CONTRARIAN**: 3.0+ point edge
- **CONSENSUS_ALIGNMENT**: <0.5 point edge (follow market)

## Data Quality Standards

### Scope
- **Games analyzed**: Power 4 conference matchups only
- **Betting lines**: Consensus spreads from multiple sportsbooks
- **Historical data**: Team performance, coaching records, situational factors

### Exclusion Criteria
- FCS vs FBS matchups (outside scope)
- Games without available betting lines (no baseline for contrarian analysis)
- Extreme blowouts (>14 point spreads) when appropriate for edge probability

## Post-Lock Modifications

### Allowed Changes
- **Data collection**: Adding weekly prediction files and results
- **Bug fixes**: Correcting data fetching to capture all P4 games
- **Documentation**: README updates, performance tracking
- **Infrastructure**: Test files, validation scripts (not used in predictions)

### Prohibited Changes
- **Algorithm modifications**: Any changes to prediction logic
- **Weight adjustments**: Factor weights locked Aug 25
- **Threshold tuning**: Edge detection thresholds unchanged
- **In-sample optimization**: No parameter tuning based on results

### Notable Bug Fixes (Post-Lock)
All bug fixes addressed data collection issues only:
- **Week 2**: Fixed game normalization for proper team matching
- **Week 5**: Added missing Oregon @ Penn State game to analysis
- **Week 6**: Added missing Boston College @ Pittsburgh game to analysis

**Impact**: These fixes ensured complete game coverage but did not alter prediction logic.

## Results Tracking

### Performance Metrics
Tracked weekly in `data/results/` directory:
- Prediction accuracy (correct vs incorrect)
- Return on investment (ROI) at standard -110 odds
- Contrarian pick performance vs consensus picks
- Weekly variance analysis

### Statistical Significance
- **Sample size**: 300 games (Weeks 1–14)
- **95% confidence interval**: 51–63% true accuracy

### Key Performance Indicators (Through Week 14)
- **Overall accuracy**: 57.0% (171/300)
- **ROI**: +8.82% at -110 odds
- **Sharpe ratio**: 0.093

## Research vs Production Code

### Production System
Code actually used to generate predictions:
- `engine/prediction_engine.py` (locked Aug 25)
- `factors/` directory (factor calculations)
- `data/data_manager.py` (data fetching)
- `config.py` (configuration)

### Research Code (Not Used in Predictions)
Added post-lock for exploration only:
- `engine/adaptive_calibrator.py` (Sept 2)
- `engine/dynamic_weighter.py` (Sept 2)
- `engine/market_efficiency_detector.py` (Sept 2)
- `engine/game_filter.py` (Sept 2)
- `validate_performance_metrics.py` (Sept 2)

**Note**: Research code exists alongside production but is not imported or called during prediction generation.

## Intellectual Honesty

### Out-of-Sample Testing
This project represents **pure forward testing**:
- Model finalized before season started
- No optimization on observed results
- No cherry-picking of games or weeks
- Complete transparency on all predictions made

### Limitations Acknowledged
- Small sample size early in season (statistical power limited)
- High week-to-week variance (36% to 75% accuracy range)
- Market efficiency varies by game type and conference
- Real-world constraints (vig, limits, line movement) not fully modeled

## Verification for Third Parties

### Git History Verification
```bash
# Show core algorithm unchanged since lock
git log --format="%h %ai %s" -- engine/prediction_engine.py
# Last change: Aug 25, 2025

# Show first prediction generated after lock
git log --format="%h %ai %s" -- data/predictions/2025_week_01.json
# Generated: Aug 28, 2025

# Show all commits since season start
git log --oneline --since="2025-08-28"
# Review: Only data additions and bug fixes
```

### Reproducibility
All predictions are:
- Timestamped with generation date
- Stored in versioned JSON files
- Committed to git before games occur
- Traceable to specific git commits

## Conclusion

This methodology demonstrates a disciplined approach to quantitative sports betting research:
1. **Model development and lock** before data collection
2. **Pure out-of-sample testing** with no in-sample optimization
3. **Complete transparency** on all predictions and results
4. **Statistical rigor** in evaluating performance

The separation between model lock (Aug 25) and season start (Aug 28) provides clear evidence that all predictions represent genuine forward tests of the algorithm's edge-finding capability.

---

**Model Version**: 1.0
**Lock Date**: August 25, 2025
**Lock Commit**: `38c5a74`
**Status**: Active (2025 Season)
**Last Updated**: December 13, 2025
