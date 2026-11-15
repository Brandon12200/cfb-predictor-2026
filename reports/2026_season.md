# 2026 Season Report — to date

_270/270 games graded across 11 week(s)._

_Capture cadence changed at **week 04** (D44). Close-age and timeliness figures below are reported per era and never blended across it._

### Games of interest, by lean side (D27 — read this before the blended numbers)

_250 of 270 games carry a gradable lean (172 home / 78 away, 2.21:1)._

_**These are hypothetical leans, not placed bets.** All 250 graded games were NO_BET — this is what the model would have done had it bet, which is how selectivity gets measured (3c.5). No wager was recommended._

| lean | leans | graded | W-L-P | ATS win% | Wilson 95% | avg CLV |
|---|---|---|---|---|---|---|
| home | 172 | 172 | 98-74-0 | 57.0% | [50%–64%] | +0.16 pts (beat close 47.7%, n=172) |
| away | 78 | 78 | 52-25-1 | 67.5% | [56%–77%] | +0.04 pts (beat close 47.4%, n=78) |
| _naive: always lean home_ | 250 | 250 | 123-126-1 | 49.4% | [43%–56%] | +0.10 pts (beat close 47.6%, n=250) |

_Model 60.2% vs naive baseline 49.4% on the same games: **+10.8%** — **above** always taking the home team._

_20 neutral games: no side taken — CLV is defined from the bet side's perspective, so it is null rather than 0.0 (D22 f3). Their own selectivity bucket, never win-rated._

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
| NO_BET (hypothetical lean) | 250 | 60.2% |
| NO_BET (neutral, no lean) | 20 | — (no side) |

_Entire slate NO_BET — selectivity working as designed (dormancy-as-design, 3c.9), not breakage._

### Per-factor attribution (converts `reasoned` → `measured` for 2027)

| factor | fired | ATS (W-L) | ATS win% | avg CLV |
|---|---|---|---|---|
| Altitude | 13 | 11-2 | 84.6% | +0.35 |
| ByeAdvantage | 67 | 43-24 | 64.2% | -0.13 |
| CloseGamePerformance | 62 | 39-23 | 62.9% | -0.15 |
| ConsecutiveRoad | 56 | 36-20 | 64.3% | +0.09 |
| DesperationIndex | 1 | 0-1 | 0.0% | +2.10 |
| PointDifferentialTrends | 83 | 48-34 | 58.5% | +0.12 |
| Sandwich | 121 | 70-51 | 57.9% | +0.08 |
| ShortWeek | 37 | 22-15 | 59.5% | +0.18 |
| TravelBurden | 145 | 89-56 | 61.4% | +0.19 |

_read the Wilson intervals — first-season per-factor cells are small_

### CLV by close age (D44)

_Close age is kickoff − `close_as_of`: how stale the last pre-kickoff observation was when the market closed for that game. Derived from the committed line store, so weeks before the cadence change bucket correctly with no relabel of any append-only file._

**Weeks 01–03 — pre-D44 cadence**

| close age | games with CLV | avg CLV | beat the close |
|---|---|---|---|
| ≤3 h | 23 | +0.13 | 47.8% |
| 3–12 h | 2 | -0.15 | 50.0% |
| >12 h | 8 | +0.01 | 50.0% |

_12 further graded game(s) are not counted here: a neutral lean takes no side, so it has no CLV to age (D22 f3) — the close itself may well have been fresh._

**Week 04 onward — D44 cadence**

| close age | games with CLV | avg CLV | beat the close |
|---|---|---|---|
| ≤3 h | 216 | +0.13 | 47.7% |
| 3–12 h | 1 | -0.70 | 0.0% |
| >12 h | 0 | — | — |

_8 further graded game(s) are not counted here: a neutral lean takes no side, so it has no CLV to age (D22 f3) — the close itself may well have been fresh._

_The two eras are reported separately and never summed: weeks 1–3 ran one capture wave per kickoff window, week 4 onward runs D44's guarantee + best-effort pair. A single season row would average a fixed cadence with the one that replaced it (D44 §(4))._


### Capture timeliness (D44 tier 3)

| week | guarantee slots | landed before their window | missed |
|---|---|---|---|
| 04 | 8 | 8 | 0 |
| 05 | 8 | 8 | 0 |
| 06 | 8 | 8 | 0 |
| 07 | 8 | 8 | 0 |
| 08 | 8 | 7 | 1 |
| 09 | 8 | 8 | 0 |
| 10 | 8 | 8 | 0 |
| 11 | 8 | 8 | 0 |

_A guarantee slot is judged by the capture run it produced — the earliest observation at or after its scheduled time — and counts as covered when that run landed before the kickoff window it precedes. Best-effort slots are designed to miss and are not counted (D44 implementation ruling 1)._
_Week 08: the Tue 12:50 ET slot before the 19:00 ET window was served by Tue 10-20 21:39 ET._

_D44 tier 4 (escalation at a guarantee miss in 2 or more weeks of any 3): not triggered._

