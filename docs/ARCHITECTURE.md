# College Football Market Edge Platform - System Architecture

> **⚠ SUPERSEDED (pre-2026-rebuild overview — do not trust the specifics).** This file predates the
> Phase 0–3 rebuild and is kept only for its high-level shape. It is **wrong** on: the factor roster
> (`SchedulingFatigue` and `LookaheadSandwich` were **retired** in 3b, replaced by six physical factors
> Bye/ShortWeek/Travel/Altitude/ConsecutiveRoad/Sandwich; `MarketSentiment` is a **dormant modifier**,
> not ~39%), the weight distribution (see the real shares in `docs/CALIBRATION_LOG.md` Phase 3b/3c), and
> the "Error Handling → **Return Neutral Values**" flow (that neutral-fill **fabrication was removed** in
> Phase 1 — binding principle #4; missing data is recorded `missing`, never neutral-filled). Authoritative
> current sources: **`docs/CALIBRATION_LOG.md`** (factor roster + weights + evidence), **`docs/CODE_AUDIT.md`**
> (module map, per-phase changes), **`docs/SCHEMA.md`** (data flow + reproducibility). Not on the
> keep-current list in `CLAUDE.md`.

## High-Level Data Flow

```
┌─────────────┐
│   CLI/User  │
└─────┬───────┘
      │
      ▼
┌─────────────────────────────────────────────────┐
│            main.py (Entry Point)                │
│  - Argument parsing                             │
│  - Team name normalization                      │
│  - Output formatting                            │
└─────────────┬───────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────┐
│       PredictionEngine (Orchestrator)           │
│  - Coordinates entire prediction process        │
│  - Handles error recovery                       │
│  - Calculates confidence scores                 │
└─────────────┬───────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────┐
│          DataManager (Data Layer)               │
│  - Manages all API calls                        │
│  - Implements fallback chain                    │
│  - Handles caching                              │
└──┬──────────┬──────────┬───────────────────────┘
   │          │          │
   ▼          ▼          ▼
┌──────┐  ┌──────┐  ┌────────┐
│ CFBD │  │ ESPN │  │ Odds   │
│ API  │  │ API  │  │ API    │
└──────┘  └──────┘  └────────┘
```

## Factor Calculation Pipeline

```
Game Context (home_team, away_team, week)
           │
           ▼
    ┌──────────────┐
    │ Factor       │
    │ Registry     │
    └──────┬───────┘
           │
           ├─── Parallel Factor Execution ───┐
           │                                 │
    ┌──────▼────────┐                ┌──────▼────────┐
    │ Market        │                │ Coaching      │
    │ Factors       │                │ Factors       │
    │               │                │               │
    │ • MarketSent. │                │ • Experience  │
    │ • StyleMatch  │                │ • H2H Record  │
    │ • Schedule    │                │ • Pressure    │
    └──────┬────────┘                └──────┬────────┘
           │                                 │
    ┌──────▼────────┐                ┌──────▼────────┐
    │ Momentum      │                │ Situational   │
    │ Factors       │                │ Factors       │
    │               │                │               │
    │ • CloseGame   │                │ • Desperation │
    │ • PointDiff   │                │ • Revenge     │
    │               │                │ • Lookahead   │
    └──────┬────────┘                └──────┬────────┘
           │                                 │
           └────────────┬────────────────────┘
                        │
                        ▼
                ┌───────────────┐
                │ Weight        │
                │ Normalization │
                │ (Sum = 1.0)   │
                └───────┬───────┘
                        │
                        ▼
                ┌───────────────┐
                │ Variance      │
                │ Detection     │
                └───────┬───────┘
                        │
                        ▼
                ┌───────────────┐
                │ Final Edge    │
                │ Calculation   │
                └───────────────┘
```

## Data Source Hierarchy

```
Required Data Item
        │
        ▼
┌─────────────────┐
│ Check Cache     │──── HIT ──→ Return Cached Data
│ (TTL-based)     │
└────────┬────────┘
         │ MISS
         ▼
┌─────────────────┐
│ Try CFBD API    │──── SUCCESS ──→ Cache & Return
│ (Primary)       │
└────────┬────────┘
         │ FAIL
         ▼
┌─────────────────┐
│ Try ESPN API    │──── SUCCESS ──→ Cache & Return
│ (Fallback)      │
└────────┬────────┘
         │ FAIL
         ▼
┌─────────────────┐
│ Return Default  │
│ (Neutral values)│
└─────────────────┘
```

## Cache Strategy

```
┌──────────────────────────────────────────┐
│             Cache Manager                │
├──────────────────────────────────────────┤
│ Type         │ TTL      │ Invalidation   │
├──────────────┼──────────┼────────────────┤
│ Team Info    │ 7 days   │ Manual         │
│ Coaching     │ 24 hours │ Weekly         │
│ Game Context │ 1 hour   │ Game time      │
│ Stats        │ 30 mins  │ After games    │
│ Odds         │ 5 mins   │ Line movement  │
└──────────────────────────────────────────┘
```

## Factor Weight Distribution (Post-Normalization)

```
MarketSentiment     ████████████████████ 39.1%
StyleMismatch       ██████████           19.5%
SchedulingFatigue   ██████               12.9%
ExperienceDiff      ██                    3.9%
HeadToHeadRecord    ██                    3.9%
PressureSituation   ██                    3.9%
DesperationIndex    ██                    3.9%
LookaheadSandwich   ██                    3.9%
RevengeGame         ██                    3.9%
PointDiffTrends     █                     2.7%
CloseGamePerf       █                     2.3%
                    ─────────────────────
                    Total:              100.0%
```

## Error Handling Flow

```
API Call Attempted
        │
        ├─── Success ──→ Process & Cache
        │
        └─── Failure
                │
                ├─── Timeout ──→ Try Fallback API
                │
                ├─── Rate Limit ──→ Wait & Retry
                │
                ├─── Auth Error ──→ Use Fallback
                │
                └─── Other ──→ Return Neutral Values
                              (System continues)
```

## Class Hierarchy

```
BaseFactorCalculator (Abstract)
    │
    ├── MarketSentiment
    ├── StyleMismatch
    ├── SchedulingFatigue
    │
    ├── ExperienceDifferential ─┐
    ├── HeadToHeadRecord        ├── Coaching Factors
    ├── PressureSituation      ─┘
    │
    ├── CloseGamePerformance ─┐
    ├── PointDiffTrends      ─┴── Momentum Factors
    │
    └── DesperationIndex     ─┐
        LookaheadSandwich     ├── Situational Factors
        RevengeGame          ─┘
```

## Key Design Decisions

### Why This Architecture?

1. **Parallel Factor Processing**: Each factor calculates independently, allowing for parallel execution and graceful degradation if one fails.

2. **Multi-Source Fallback**: Three-tier data sourcing (CFBD → ESPN → Default) ensures the system never crashes due to API issues.

3. **Automatic Weight Normalization**: Instead of manually maintaining weights that sum to 1.0, the system auto-normalizes, making it maintainable.

4. **Variance Detection**: Identifies when factors disagree strongly, which is a signal to avoid the bet rather than force a prediction.

5. **Cache-First Design**: Every API call checks cache first. With 70-80% hit rates, this dramatically reduces API usage and improves speed.

## Performance Characteristics

```
Single Game Analysis
├── Cold Start (no cache): 3-5 seconds
│   ├── API calls: 8-10
│   └── Cache writes: 4-6
│
└── Warm Cache: <1 second
    ├── API calls: 1-2 (odds only)
    └── Cache reads: 8-10

Bulk Analysis (10 games)
├── Sequential: 30-40 seconds
└── Potential Async: 5-8 seconds (not implemented)
```

## File Structure

```
college-football-market-edge/
├── main.py                 # Entry point & CLI
├── engine/
│   ├── prediction_engine.py # Core orchestration
│   ├── factor_validator.py  # Factor testing
│   └── variance_detector.py # Disagreement analysis
├── factors/
│   ├── base_calculator.py   # Abstract base class
│   ├── factor_registry.py   # Auto-discovery & weighting
│   └── [11 factor files]    # Individual factors
├── data/
│   ├── data_manager.py      # API orchestration
│   ├── cfbd_client.py       # CFBD API wrapper
│   ├── espn_client.py       # ESPN API wrapper
│   ├── odds_client.py       # Odds API wrapper
│   └── cache_manager.py     # Caching layer
└── utils/
    ├── normalizer.py        # Team name normalization
    └── rate_limiter.py      # API throttling
```