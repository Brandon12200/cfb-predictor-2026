# 2026 Season Report — to date

_178/178 games graded across 8 week(s)._

_Capture cadence changed at **week 04** (D44). Close-age and timeliness figures below are reported per era and never blended across it._

### Games of interest, by lean side (D27 — read this before the blended numbers)

_160 of 178 games carry a gradable lean (111 home / 49 away, 2.27:1)._

_**These are hypothetical leans, not placed bets.** All 160 graded games were NO_BET — this is what the model would have done had it bet, which is how selectivity gets measured (3c.5). No wager was recommended._

| lean | leans | graded | W-L-P | ATS win% | Wilson 95% | avg CLV |
|---|---|---|---|---|---|---|
| home | 111 | 111 | 66-45-0 | 59.5% | [50%–68%] | -0.02 pts (beat close 40.5%, n=111) |
| away | 49 | 49 | 34-14-1 | 70.8% | [57%–82%] | -0.05 pts (beat close 49.0%, n=49) |
| _naive: always lean home_ | 160 | 160 | 80-79-1 | 50.3% | [43%–58%] | +0.00 pts (beat close 42.5%, n=160) |

_Model 62.9% vs naive baseline 50.3% on the same games: **+12.6%** — **above** always taking the home team._

_The away cell is thin (n=48 graded). Its Wilson interval, not its point estimate, is the honest reading._

_18 neutral games: no side taken — CLV is defined from the bet side's perspective, so it is null rather than 0.0 (D22 f3). Their own selectivity bucket, never win-rated._

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
| NO_BET (hypothetical lean) | 160 | 62.9% |
| NO_BET (neutral, no lean) | 18 | — (no side) |

_Entire slate NO_BET — selectivity working as designed (dormancy-as-design, 3c.9), not breakage._

### Per-factor attribution (converts `reasoned` → `measured` for 2027)

| factor | fired | ATS (W-L) | ATS win% | avg CLV |
|---|---|---|---|---|
| Altitude | 8 | 7-1 | 87.5% | -0.41 |
| ByeAdvantage | 53 | 34-19 | 64.1% | -0.05 |
| CloseGamePerformance | 31 | 18-13 | 58.1% | -0.40 |
| ConsecutiveRoad | 31 | 19-12 | 61.3% | +0.19 |
| PointDifferentialTrends | 36 | 23-12 | 65.7% | -0.17 |
| Sandwich | 71 | 46-25 | 64.8% | -0.02 |
| ShortWeek | 23 | 16-7 | 69.6% | -0.22 |
| TravelBurden | 99 | 65-34 | 65.7% | +0.00 |

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
| ≤3 h | 126 | -0.05 | 42.1% |
| 3–12 h | 1 | -0.70 | 0.0% |
| >12 h | 0 | — | — |

_6 further graded game(s) are not counted here: a neutral lean takes no side, so it has no CLV to age (D22 f3) — the close itself may well have been fresh._

_The two eras are reported separately and never summed: weeks 1–3 ran one capture wave per kickoff window, week 4 onward runs D44's guarantee + best-effort pair. A single season row would average a fixed cadence with the one that replaced it (D44 §(4))._


### Capture timeliness (D44 tier 3)

| week | guarantee slots | landed before their window | missed |
|---|---|---|---|
| 04 | 8 | 8 | 0 |
| 05 | 8 | 8 | 0 |
| 06 | 8 | 8 | 0 |
| 07 | 8 | 8 | 0 |
| 08 | 8 | 7 | 1 |

_A guarantee slot is judged by the capture run it produced — the earliest observation at or after its scheduled time — and counts as covered when that run landed before the kickoff window it precedes. Best-effort slots are designed to miss and are not counted (D44 implementation ruling 1)._
_Week 08: the Tue 12:50 ET slot before the 19:00 ET window was served by Tue 10-20 21:39 ET._

_D44 tier 4 (escalation at a guarantee miss in 2 or more weeks of any 3): not triggered._

