# 2026 Season Report — to date

_151/151 games graded across 7 week(s)._

_Capture cadence changed at **week 04** (D44). Close-age and timeliness figures below are reported per era and never blended across it._

### Games of interest, by lean side (D27 — read this before the blended numbers)

_135 of 151 games carry a gradable lean (91 home / 44 away, 2.07:1)._

_**These are hypothetical leans, not placed bets.** All 135 graded games were NO_BET — this is what the model would have done had it bet, which is how selectivity gets measured (3c.5). No wager was recommended._

| lean | leans | graded | W-L-P | ATS win% | Wilson 95% | avg CLV |
|---|---|---|---|---|---|---|
| home | 91 | 91 | 49-42-0 | 53.8% | [44%–64%] | -0.06 pts (beat close 38.5%, n=91) |
| away | 44 | 44 | 30-13-1 | 69.8% | [55%–81%] | -0.01 pts (beat close 50.0%, n=44) |
| _naive: always lean home_ | 135 | 135 | 62-72-1 | 46.3% | [38%–55%] | -0.04 pts (beat close 40.7%, n=135) |

_Model 59.0% vs naive baseline 46.3% on the same games: **+12.7%** — **above** always taking the home team._

_The away cell is thin (n=43 graded). Its Wilson interval, not its point estimate, is the honest reading._

_16 neutral games: no side taken — CLV is defined from the bet side's perspective, so it is null rather than 0.0 (D22 f3). Their own selectivity bucket, never win-rated._

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
| NO_BET (hypothetical lean) | 135 | 59.0% |
| NO_BET (neutral, no lean) | 16 | — (no side) |

_Entire slate NO_BET — selectivity working as designed (dormancy-as-design, 3c.9), not breakage._

### Per-factor attribution (converts `reasoned` → `measured` for 2027)

| factor | fired | ATS (W-L) | ATS win% | avg CLV |
|---|---|---|---|---|
| Altitude | 7 | 6-1 | 85.7% | -0.49 |
| ByeAdvantage | 47 | 29-18 | 61.7% | -0.04 |
| CloseGamePerformance | 21 | 10-11 | 47.6% | -0.62 |
| ConsecutiveRoad | 25 | 14-11 | 56.0% | +0.09 |
| PointDifferentialTrends | 26 | 13-12 | 52.0% | -0.30 |
| Sandwich | 57 | 33-24 | 57.9% | +0.03 |
| ShortWeek | 20 | 13-7 | 65.0% | -0.14 |
| TravelBurden | 85 | 52-33 | 61.2% | -0.03 |

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
| ≤3 h | 101 | -0.08 | 40.6% |
| 3–12 h | 1 | -0.70 | 0.0% |
| >12 h | 0 | — | — |

_4 further graded game(s) are not counted here: a neutral lean takes no side, so it has no CLV to age (D22 f3) — the close itself may well have been fresh._

_The two eras are reported separately and never summed: weeks 1–3 ran one capture wave per kickoff window, week 4 onward runs D44's guarantee + best-effort pair. A single season row would average a fixed cadence with the one that replaced it (D44 §(4))._


### Capture timeliness (D44 tier 3)

| week | guarantee slots | landed before their window | missed |
|---|---|---|---|
| 04 | 8 | 8 | 0 |
| 05 | 8 | 8 | 0 |
| 06 | 8 | 8 | 0 |
| 07 | 8 | 8 | 0 |

_A guarantee slot is judged by the capture run it produced — the earliest observation at or after its scheduled time — and counts as covered when that run landed before the kickoff window it precedes. Best-effort slots are designed to miss and are not counted (D44 implementation ruling 1)._

_D44 tier 4 (escalation at a guarantee miss in 2 or more weeks of any 3): not triggered._

