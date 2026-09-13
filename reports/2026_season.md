# 2026 Season Report — to date

_27/27 games graded across 2 week(s)._

### Games of interest, by lean side (D27 — read this before the blended numbers)

_19 of 27 games carry a gradable lean (15 home / 4 away, 3.75:1)._

_**These are hypothetical leans, not placed bets.** All 19 graded games were NO_BET — this is what the model would have done had it bet, which is how selectivity gets measured (3c.5). No wager was recommended._

| lean | games | W-L-P | ATS win% | Wilson 95% | avg CLV |
|---|---|---|---|---|---|
| home | 15 | 7-8-0 | 46.7% | [25%–70%] | +0.03 pts (beat close 53.3%, n=15) |
| away | 4 | 3-1-0 | 75.0% | [30%–95%] | -0.15 pts (beat close 25.0%, n=4) |
| _naive: always lean home_ | 19 | 8-11-0 | 42.1% | [23%–64%] | +0.06 pts (beat close 57.9%, n=19) |

_Model 52.6% vs naive baseline 42.1% on the same games: **+10.5%** — **above** always taking the home team._

_The away cell is thin (n=4 graded). Its Wilson interval, not its point estimate, is the honest reading._

_8 neutral games: no side taken — CLV is defined from the bet side's perspective, so it is null rather than 0.0 (D22 f3). Their own selectivity bucket, never win-rated._

_Leans are structurally home-skewed: TravelBurden/ConsecutiveRoad only penalise the visitor and Altitude only advantages the host (D27). Read the away cell's Wilson interval before drawing anything from it._

### Placeable strategy — blended (secondary; see the lean split above)

_Blended across both lean sides. Per D27 this is **not** the headline: with a structurally home-skewed lean, a single number here is dominated by how home teams did against the spread._

| metric | value |
|---|---|
| ATS record | 0-0-0 |
| ATS win% | —  — |
| ROI @ -110 | — ($0.00 on 0 bets) |
| Sharpe | — |
| max drawdown | 0.0 units |
| longest losing streak | 0 |
| avg CLV | — (no placed bets) |

_No bets placed — the model declined the slate. Selectivity working as designed (dormancy-as-design, 3c.9), not breakage._

### Calibration by tier

Brier score: **—** (n=0; lower is better, 0.25 = no-skill).

| tier | n | ATS win% | mean conf | Wilson 95% |
|---|---|---|---|---|
| A | 0 | — | — | — |
| B | 0 | — | — | — |
| C | 0 | — | — | — |

_No graded bets in these tiers yet — tier separation unmeasured. An empty breakdown here is the honest state (e.g. an all-NO_BET slate), not a bug._

### Selectivity (was the skip right?)

| bucket | games | ATS win% |
|---|---|---|
| placed bets | 0 | — |
| NO_BET (hypothetical lean) | 19 | 52.6% |
| NO_BET (neutral, no lean) | 8 | — (no side) |

_Entire slate NO_BET — selectivity working as designed (dormancy-as-design, 3c.9), not breakage._

### Per-factor attribution (converts `reasoned` → `measured` for 2027)

| factor | fired | ATS (W-L) | ATS win% | avg CLV |
|---|---|---|---|---|
| Altitude | 2 | 2-0 | 100.0% | -0.25 |
| ByeAdvantage | 8 | 5-3 | 62.5% | +0.12 |
| Sandwich | 6 | 2-4 | 33.3% | +0.28 |
| ShortWeek | 2 | 0-2 | 0.0% | +0.20 |
| TravelBurden | 13 | 6-7 | 46.2% | +0.03 |

_read the Wilson intervals — first-season per-factor cells are small_

