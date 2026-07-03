# Performance Tracking System - Implementation Plan

## Overview

A two-script system to automatically track the real-world performance of contrarian betting predictions, providing quantifiable success metrics for the platform.

## System Architecture

### Components

1. **Tuesday Prediction Script** (`scripts/weekly_predictions.py`)
2. **Monday Results Script** (`scripts/check_results.py`) 
3. **Performance Database** (`data/performance_tracker.json`)
4. **Weekly Data Storage** (`data/predictions/`, `data/results/`)

### Data Flow

```
Tuesday: Generate Predictions → Store in predictions/2025_week_XX.json
    ↓ (Wait for games to be played)
Monday: Fetch Results → Store in results/2025_week_XX.json
    ↓
Update performance_tracker.json → Calculate running metrics
```

## File Structure

```
data/
├── predictions/
│   ├── 2025_week_01.json    # Weekly prediction outputs
│   ├── 2025_week_02.json
│   └── ...
├── results/
│   ├── 2025_week_01.json    # Actual game results
│   ├── 2025_week_02.json
│   └── ...
└── performance_tracker.json # Master performance database
```

## Data Schemas

### Prediction File Format (`predictions/2025_week_XX.json`)

```json
{
  "week": 1,
  "season": 2025,
  "generated_date": "2025-09-03T10:30:00Z",
  "prediction_count": 3,
  "predictions": [
    {
      "game_id": "ohio-state-vs-michigan-week1",
      "home_team": "Ohio State",
      "away_team": "Michigan", 
      "vegas_spread": "Ohio State -7.5",
      "predicted_edge": 1.8,
      "confidence": 72.4,
      "recommendation": "Michigan +7.5",
      "bet_rationale": "Market overvaluing Ohio State due to public bias",
      "factor_breakdown": {
        "market_sentiment": 0.39,
        "style_mismatch": 0.19,
        "scheduling_fatigue": -0.12
      },
      "data_quality": 85.0
    }
  ],
  "system_stats": {
    "total_games_analyzed": 25,
    "games_with_edges": 3,
    "hit_rate": 0.12,
    "average_confidence": 71.2
  }
}
```

### Results File Format (`results/2025_week_XX.json`)

```json
{
  "week": 1,
  "season": 2025,
  "processed_date": "2025-09-09T09:15:00Z",
  "results": [
    {
      "game_id": "ohio-state-vs-michigan-week1",
      "home_team": "Ohio State",
      "away_team": "Michigan",
      "home_score": 24,
      "away_score": 21,
      "actual_margin": -3,
      "vegas_spread": -7.5,
      "game_date": "2025-09-07",
      "status": "final"
    }
  ]
}
```

### Performance Tracker (`performance_tracker.json`)

```json
{
  "last_updated": "2025-09-09T09:30:00Z",
  "tracking_start_date": "2025-09-03",
  "weeks_tracked": 1,
  
  "overall_performance": {
    "total_predictions": 3,
    "correct_predictions": 2, 
    "win_rate": 0.667,
    "total_games_analyzed": 25,
    "prediction_rate": 0.12,
    "average_edge_size": 1.6,
    "average_confidence": 71.8
  },
  
  "weekly_breakdown": {
    "2025_week_01": {
      "predictions": 3,
      "wins": 2,
      "losses": 1,
      "win_rate": 0.667,
      "average_confidence": 71.8,
      "largest_edge": 2.1,
      "best_call": "Michigan +7.5 (Won by 4.5)"
    }
  },
  
  "confidence_analysis": {
    "80_plus": {"predictions": 0, "wins": 0, "win_rate": null},
    "70_79": {"predictions": 2, "wins": 2, "win_rate": 1.000},
    "60_69": {"predictions": 1, "wins": 0, "win_rate": 0.000},
    "below_60": {"predictions": 0, "wins": 0, "win_rate": null}
  },
  
  "factor_performance": {
    "market_sentiment": {"avg_impact": 0.38, "success_rate": 0.75},
    "style_mismatch": {"avg_impact": 0.21, "success_rate": 0.60}
  },
  
  "notable_results": [
    {
      "week": 1,
      "game": "Michigan +7.5",
      "result": "WIN",
      "edge_found": 1.8,
      "actual_edge": 4.5,
      "confidence": 72.4
    }
  ]
}
```

## Script Implementation Details

### Tuesday Prediction Script (`scripts/weekly_predictions.py`)

**Purpose:** Generate weekly predictions and store them for later validation

**Key Functions:**
```python
def generate_weekly_predictions(week, min_edge=1.0, min_confidence=65):
    """Generate predictions for all games in specified week"""
    
def save_predictions(predictions, week, season):
    """Save predictions to JSON file"""
    
def analyze_prediction_patterns(predictions):
    """Generate metadata about this week's predictions"""
```

**Command Line Interface:**
```bash
# Generate predictions for current week
python scripts/weekly_predictions.py

# Specific week with filters
python scripts/weekly_predictions.py --week 5 --min-edge 1.5 --min-confidence 70

# Dry run mode
python scripts/weekly_predictions.py --dry-run
```

**Output:**
```
College Football Market Edge Platform - Weekly Predictions
========================================================
Analyzing Week 5 games...

Games with contrarian opportunities:
  ✅ Georgia +3.5 vs Alabama (Edge: 2.1, Confidence: 74%)
  ✅ Michigan +7 vs Ohio State (Edge: 1.8, Confidence: 68%)  
  ✅ Texas +1 vs Oklahoma (Edge: 1.2, Confidence: 71%)

Summary:
  Games analyzed: 28
  Edges found: 3 (10.7%)
  Average confidence: 71.0%
  
Predictions saved to: data/predictions/2025_week_05.json
```

### Monday Results Script (`scripts/check_results.py`)

**Purpose:** Fetch game results and calculate prediction accuracy

**Key Functions:**
```python
def fetch_game_results(week, season):
    """Fetch actual game results from ESPN API"""
    
def evaluate_prediction_accuracy(prediction, result):
    """Determine if our recommended bet was successful"""
    
def update_performance_tracker(weekly_results):
    """Update master performance database"""
    
def generate_weekly_report(week_results):
    """Create human-readable performance report"""
```

**Bet Evaluation Logic:**
```python
def check_bet_success(prediction, actual_result):
    """
    Determine if recommended bet was successful
    
    Args:
        prediction: Our recommendation (e.g. "Michigan +7.5")
        actual_result: Game outcome with scores
        
    Returns:
        dict: {
            "bet_won": bool,
            "bet_margin": float,  # How much we won/lost by
            "actual_spread": float,
            "vegas_spread": float
        }
    """
    recommended_bet = prediction['recommendation']
    home_score = actual_result['home_score'] 
    away_score = actual_result['away_score']
    actual_margin = home_score - away_score  # Positive = home team won
    
    # Parse recommendation: "Michigan +7.5" or "Ohio State -3"
    if "+" in recommended_bet:
        # We bet the underdog
        team, spread = parse_underdog_bet(recommended_bet)  # ("Michigan", 7.5)
        
        if team == actual_result['away_team']:
            # Away underdog: did away_score + spread > home_score?
            bet_won = (away_score + spread) > home_score
            bet_margin = (away_score + spread) - home_score
        else:
            # Home underdog: did home_score + spread > away_score?
            bet_won = (home_score + spread) > away_score  
            bet_margin = (home_score + spread) - away_score
            
    else:  # "-" bet (favorite)
        team, spread = parse_favorite_bet(recommended_bet)  # ("Ohio State", 3)
        
        if team == actual_result['home_team']:
            # Home favorite: did home_score - spread > away_score?
            bet_won = (home_score - spread) > away_score
            bet_margin = (home_score - spread) - away_score
        else:
            # Away favorite: did away_score - spread > home_score?
            bet_won = (away_score - spread) > home_score
            bet_margin = (away_score - spread) - home_score
    
    return {
        "bet_won": bet_won,
        "bet_margin": bet_margin,
        "actual_margin": actual_margin,
        "vegas_spread": prediction['vegas_spread']
    }
```

**Command Line Interface:**
```bash
# Check results for last week
python scripts/check_results.py

# Specific week
python scripts/check_results.py --week 4

# Generate detailed report
python scripts/check_results.py --week 4 --detailed-report
```

**Output:**
```
College Football Market Edge Platform - Results Check
===================================================
Checking Week 5 results...

Prediction Results:
  ❌ Georgia +3.5 vs Alabama (L 28-35, Lost by 3.5)
  ✅ Michigan +7 vs Ohio State (L 24-28, Won by 3)  
  ✅ Texas +1 vs Oklahoma (W 31-28, Won by 4)

Week 5 Performance:
  Predictions: 3
  Wins: 2  
  Win Rate: 66.7%
  Average Confidence: 71.0%

Overall Performance (5 weeks):
  Total Predictions: 14
  Total Wins: 10
  Overall Win Rate: 71.4%
  High Confidence (70+): 8/10 (80.0%)
```

## Automation Options

### Cron Jobs (Recommended)

```bash
# Tuesday 8 AM: Generate weekly predictions
0 8 * * 2 cd /path/to/project && python scripts/weekly_predictions.py

# Monday 9 AM: Check previous week results  
0 9 * * 1 cd /path/to/project && python scripts/check_results.py
```

### Manual Execution

```bash
# Every Tuesday
python scripts/weekly_predictions.py

# Every Monday
python scripts/check_results.py --week previous
```

## Success Metrics to Track

### Primary Metrics
- **Win Rate**: Percentage of recommended bets that were successful
- **Prediction Rate**: Percentage of games where we found edges
- **Average Confidence**: Mean confidence score of our predictions
- **Confidence Calibration**: Do 70% confidence bets win 70% of the time?

### Secondary Metrics
- **Edge Accuracy**: How close were our predicted edges to actual edges?
- **Factor Performance**: Which factors contribute most to successful predictions?
- **Best/Worst Calls**: Highlight standout predictions
- **Trap Game Detection**: Did we successfully avoid trap games?

### Resume-Ready Stats (After 8+ weeks)
- *"Achieved 68% accuracy on 45 live college football betting predictions"*
- *"Identified profitable opportunities in 12% of analyzed games"*
- *"High-confidence predictions (70%+) achieved 78% success rate"*
- *"System correctly predicted contrarian value in 8 of 12 major upsets"*

## Implementation Timeline

### Phase 1: Core Infrastructure (Weekend 1)
- [ ] Create data directory structure
- [ ] Build prediction storage system
- [ ] Implement basic bet evaluation logic
- [ ] Create weekly_predictions.py skeleton

### Phase 2: Results Processing (Weekend 2) 
- [ ] Build ESPN results fetching
- [ ] Implement check_results.py
- [ ] Create performance_tracker.json updates
- [ ] Add basic reporting

### Phase 3: Refinement (Ongoing)
- [ ] Add confidence calibration analysis
- [ ] Implement factor performance tracking
- [ ] Create detailed reporting features
- [ ] Add automation scripts

## Error Handling Considerations

### Data Issues
- Games postponed/cancelled
- Betting lines not available at prediction time
- ESPN API timeouts
- Malformed prediction files

### Edge Cases
- Pushes (exact ties with spread)
- Line movements between prediction and game time
- Games that don't finish (weather, etc.)
- FCS vs FBS matchups

### Recovery Strategies
- Graceful degradation when APIs fail
- Manual result entry for missing data
- Data validation checks
- Backup data sources

## Future Enhancements

### Advanced Analytics
- ROI calculation (assuming unit betting)
- Kelly criterion bet sizing recommendations
- Market movement analysis
- Seasonal performance trends

### Visualization
- Performance dashboard
- Win rate charts by confidence level
- Factor impact heatmaps
- Weekly prediction summaries

### Integration
- Slack/Discord notifications for predictions
- Email weekly summaries
- Web dashboard for live tracking
- Integration with betting platforms (legal considerations)

---

*This system will provide quantifiable evidence of the platform's real-world performance, essential for demonstrating practical value in fintech applications.*