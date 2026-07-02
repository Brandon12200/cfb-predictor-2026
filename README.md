# CFB Contrarian Predictor

A rule-based system that adjusts Vegas college football spreads using 11 quantifiable factors. Built to test whether a fixed-weight model could find edges without the overfitting that kills most backtested systems.

The model was frozen on August 25, 2025—three days before Week 1—and run forward with no algorithmic modifications. Predictions committed to git before each week's games, results recorded after. Git history provides the audit trail.

## Results

**2025 Season, Weeks 1–14**

| Metric | Value |
|--------|-------|
| Games | 300 |
| Accuracy (ATS) | 57.0% |
| ROI (at -110) | +8.82% |
| Sharpe Ratio | 0.093 |

300 games puts the 95% confidence interval at roughly 51–63%. Enough signal to validate the approach, not enough to draw strong conclusions.

All predictions and results stored as JSON in `data/predictions/` and `data/results/` with timestamps, Vegas spreads, factor breakdowns, and confidence scores.

## How It Works

Takes the Vegas spread and applies adjustments:

```
Contrarian Spread = (Vegas Spread + Factor Adjustments) × Market Modifier
Edge = |Contrarian Spread - Vegas Spread|
```

### Factor System

11 factors in a fixed-weight hierarchy. Fixed weights were a deliberate choice—learned weights require training data, which means backtesting, which means overfitting risk. This way, if scheduling fatigue should matter more than revenge games, that assumption is explicit before seeing any results. Wrong assumptions get exposed cleanly.

| Category | Weight | Factors |
|----------|--------|---------|
| Primary | 60% | Scheduling Fatigue (±3.5 pts), Head-to-Head Record (±1 pt), Desperation Index (±2 pts) |
| Secondary | 30% | Experience Differential, Pressure Situation, Revenge Game, Lookahead Spot, Point Differential Trends, Close Game Performance, Style Mismatch |
| Modifier | 10% | Market Sentiment (0.5x–1.5x multiplier based on line movement) |

Each factor inherits from `BaseFactorCalculator` and implements `calculate()`, `calculate_with_confidence()`, and `get_output_range()`.

Factors have activation thresholds—signals below threshold get zeroed out. A "minor revenge spot" probably isn't mispriced; markets handle small effects fine. Thresholds accept that not every game has an edge and reduce noise from marginal signals.

### Variance Detection

When factors disagree significantly (scheduling fatigue favors Team A, market sentiment favors Team B), the game receives a reduced confidence score. High-variance games can be filtered out—trading volume for expected accuracy.

## Observations

**Scheduling fatigue was the strongest signal.** Games with significant rest/travel disadvantage showed the highest edge capture. Physical factors appear more reliably underpriced than motivational ones—makes sense, since fatigue is concrete and motivation is speculative.

**Situational factors were noisier than expected.** Revenge games and lookahead spots produced high variance. Sometimes they mattered enormously, sometimes not at all. These probably need higher activation thresholds or confirming factors before firing.

**The confidence scoring worked.** High-confidence predictions outperformed low-confidence ones. The variance detector's "I don't know" signal had real value—filtering to aligned-factor games would have improved accuracy at the cost of volume.

If I rebuilt this, I'd weight physical factors higher, be more selective about activation, and add explicit "no bet" flags. The current version bets too many games where the edge is marginal.

## Data Pipeline

Three external APIs with fallback chain:

| Source | Role | Data |
|--------|------|------|
| The Odds API | Required | Live spreads from FanDuel, DraftKings, BetMGM |
| College Football Data API | Primary | Coaching records, advanced stats, historical lines |
| ESPN API | Fallback | Schedule and team data when CFBD unavailable |

`DataManager` coordinates requests across sources. CFBD failure falls back to ESPN. Both failing uses neutral values and penalizes prediction confidence—the system knows when its data is degraded.

### Caching & Rate Limiting

TTL-based caching: 1h default, 30min for game context data. `RateLimiter` implements sliding window with thread-safe tracking.

## Project Structure

```
├── main.py                     # CLI entry point
├── config.py                   # API keys, factor weights
├── engine/
│   ├── prediction_engine.py    # Factor calculation and aggregation
│   ├── edge_detector.py        # Edge classification
│   ├── variance_detector.py    # Factor agreement analysis
│   └── confidence_calculator.py
├── factors/
│   ├── base_calculator.py      # Abstract base class
│   ├── factor_registry.py      # Dynamic factor loading
│   ├── scheduling_fatigue.py   # Travel, rest, emotional hangover
│   ├── market_sentiment.py     # Line movement analysis
│   ├── coaching_edge.py        # Experience, H2H records
│   ├── situational_context.py  # Desperation, lookahead, revenge
│   ├── momentum_factors.py     # Point differential, close games
│   └── style_mismatch.py       # Pace and efficiency matchups
├── data/
│   ├── data_manager.py         # Multi-source coordinator
│   ├── odds_client.py
│   ├── cfbd_client.py
│   ├── espn_client.py
│   ├── cache_manager.py
│   ├── predictions/            # Pre-game predictions (JSON)
│   └── results/                # Post-game results (JSON)
├── utils/
│   ├── rate_limiter.py
│   └── normalizer.py           # Team name normalization
├── scripts/
│   ├── calculate_accuracy.py
│   ├── calculate_roi.py
│   └── calculate_sharpe.py
└── tests/                      # 305 tests
```

## Setup

```bash
git clone https://github.com/Brandon12200/CFB-Market-Edge-Platform.git
cd CFB-Market-Edge-Platform
pip install -r requirements.txt
```

`.env`:
```
ODDS_API_KEY=your_key      # Required - theoddsapi.com
CFBD_API_KEY=your_key      # Recommended - collegefootballdata.com
```

## Usage

```bash
# Single game
python main.py --home "Ohio State" --away "Michigan" --week 12

# With factor breakdown
python main.py --home "Ohio State" --away "Michigan" --week 12 --show-factors

# List games for a week
python main.py --list-games 10

# Performance analysis
python scripts/calculate_accuracy.py
python scripts/calculate_roi.py
python scripts/calculate_sharpe.py
```

### Sample Output

```
$ python main.py --home "Alabama" --away "Oklahoma" --week 4

Analyzing: OKLAHOMA @ ALABAMA
--------------------------------------------------
Fetching game data...
Data Quality: 100.0%
Vegas Spread: ALABAMA -6.0

Team Information:
ALABAMA: Alabama Crimson Tide
OKLAHOMA: Oklahoma Sooners

Generating Contrarian Prediction...

Prediction Results:
Vegas Spread: ALABAMA -6.0
Contrarian Prediction: ALABAMA -5.0
Factor Adjustment: +0.98 points
Edge Size: 0.98 points

Edge Analysis:
Edge Type: Consensus Play
Confidence: Medium (66.8%)
Recommendation: CONSENSUS - Consider market consensus, minimal contrarian edge

Explanation:
Minimal edge (1.0 points) aligns mostly with market consensus. Prediction
confidence: Medium (66.8%). Primary driver: situational context factors
(+0.98 points). Vegas line: -6.0, Contrarian prediction: -5.0.
```

## License

MIT
