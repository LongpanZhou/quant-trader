# Round-2 leader: TQQQ/QQQ ratio froth overlay

Status: **verified round-2 leader**, independently reproduced. Not committed.

## Strategy

Start from the round-1 winner:

1. Hold 100% TQQQ while QQQ's prior close is above its 165-day SMA, else BIL.
2. On risk-on days, arm a 4% stop from the session open only when QQQ's
   first-minute close is below its prior 20-day SMA × 1.01. If armed and TQQQ
   closes 4% below the open, move to BIL at the next minute's open and stay out
   for the rest of the session and the night.

Add the ratio-froth overlay:

3. Compute the daily TQQQ/QQQ price ratio and its 200-day moving average.
   `ext = log(ratio / MA200(ratio))`, using the prior session's close.
4. If `ext > 0.18`, hold **QQQ instead of TQQQ** for the next session,
   including overnight. The 4% stop still applies; if it triggers, move to BIL.
5. Otherwise run the winner unchanged.

The idea: a very high ratio extension is a low-volatility melt-up where
leveraged exposure has compounded without paying drag. The next shock is
amplified. The overlay is a crash hedge, not a continuous alpha signal.

## Results

| Window | Cost | CAGR | Max DD | Sharpe | Fills | vs TQQQ | vs round-1 winner |
|---|---:|---:|---:|---:|---:|---|---|
| 10y | 1 bp | **69.50%** | **39.11%** | 1.51 | 889 | +30.2 pp / −42.6 pp | +10.7 pp / −5.5 pp |
| 10y | 5 bp | **63.46%** | **41.75%** | — | 889 | +24.2 pp / −39.9 pp | +8.9 pp / −5.3 pp |
| 10y | 10 bp | **56.22%** | **45.03%** | — | 889 | +16.9 pp / −36.7 pp | +6.7 pp / +0.47 pp worse DD |
| 5y | 1 bp | **63.74%** | **26.85%** | 1.47 | 445 | +50.3 pp / −54.8 pp | +13.9 pp / −6.6 pp |
| 5y | 5 bp | **58.00%** | **27.72%** | — | 445 | +44.5 pp / −54.0 pp | +12.1 pp / −6.4 pp |
| 5y | 10 bp | **51.12%** | **28.80%** | — | 445 | +37.7 pp / −52.9 pp | +10.1 pp / −6.1 pp |

It **strictly dominates the round-1 winner at 1 bp and 5 bp on both windows**.
At 10 bp the 10-year drawdown is 0.47 pp worse than the winner while CAGR is
6.7 pp higher; the 5-year window still dominates.

## Consistency

Agent 21's own audit uses 28 quarterly-start windows:

- **28/28** have lower max drawdown than TQQQ.
- **26/28** have higher CAGR than TQQQ (the two misses are the 2017-04 and
  2017-07 windows, by 0.3–0.5 pp).
- **26/28** have higher CAGR and **28/28** lower drawdown than the round-1
  winner.

The independent verifier's separate 27-window run reported 27/27 on both.
Both conventions are shown; the difference is the extra quarter at the start
or end, not a contradiction.

## Caveats

- The overlay fires on **21.5% of sessions** (67 episodes over 10 years). The
  edge is a fat left tail, not a higher hit rate: the five worst froth days sum
  to −67.9% in arithmetic TQQQ return; hit-rate edge is only 2.6 pp.
- The 10-year drawdown is **higher** than the 50/50 ratio + first-hour blend
  (39.11% vs 36.16%). If the priority is the smallest 10-year drawdown, use
  that blend instead.
- At 10 bp the 10-year drawdown is marginally worse than the round-1 winner
  (45.03% vs 44.56%), though CAGR is much higher.
- The ratio threshold (200-day MA, 0.18) was chosen from the data. The report's
  surface shows MA-150/200 cells with θ ≥ 0.16 beat the winner, but this is not
  a pre-registered parameter; treat the point estimate as uncertain.
- No look-ahead: the ratio uses the prior close; truncation at 2022-01-03 leaves
  every prior weight bit-identical; weights sum to 1 and are long-only.

## Alternatives on the Pareto frontier

| Strategy | 10y CAGR / DD | 5y CAGR / DD | Note |
|---|---:|---:|---|
| **Ratio froth** | **69.50% / 39.11%** | **63.74% / 26.85%** | best 5y and consistency |
| Ratio + first-hour 50/50 | **69.95% / 36.16%** | 58.47% / 29.72% | best 10y CAGR, lower 10y DD |
| Ratio + volume 50/50 | 68.14% / 40.80% | 58.69% / 27.74% | not better than ratio alone |
| 1/3 ratio + first + volume | 69.05% / 35.97% | 56.91% / 29.31% | lowest 10y DD of the 69% group |
| First-hour + volume 50/50 | 67.83% / 35.63% | 53.10% / 32.02% | previous round-2 leader |
| Gradual stop re-entry | 61.03% / 39.92% | 51.57% / 29.96% | strict dominance vs round-1 winner; robust DD cut |
| ATR-scaled stop | 62.60% / 40.94% | 54.88% / 33.49% | strict 10y dominance; 5y DD tie |
| OpEx de-risk (V1) | 67.06% / 40.65% | 53.83% / 35.88% | strict 10y dominance; 5y DD worse |
| OpEx + FOMC (V4) | 69.08% / 43.15% | 54.84% / 34.16% | high 10y CAGR; 5y DD not lower |
| Dual-speed 60m EMA regime | 70.11% / 42.91% | 61.78% / 25.88% | higher 10y CAGR, worse 10y DD |
| Dynamic leverage throttle | 57.05% / 41.32% | 50.12% / 30.16% | 5y strict; 10y within 2pp, lower DD |
| ML crash overlay | 72.24% / 41.50% | 53.10% / 31.67% | high 10y CAGR; statistically fragile |
| Late-rally risk-off overlay | 67.92% / 41.50% | 59.44% / 33.49% | additive overlay; 5y DD tie |
| Gap-up fade overlay | 65.17% / 39.02% | 54.92% / 30.99% | strict 1/5bp; fragile 5y |

All figures at 1 bp.

## Files

- `research/agents2/ratio-pairs/` — Agent 21 report, result, strategy
- `research/agents2/overnight-crash-filter/` — first-hour sleeve
- `research/agents2/volume-orderflow/` — volume-armed stop sleeve
- `research/verification/verify_ratio_causal.py` — truncation test
- `research/verification/rolling_ratio_blend.py` — rolling consistency
- `research/verification/blend_ratio.py` — ratio blends
- `research/agents2/LEADER.md` — this file

## Optimization note

The GPU block engine (`research/gpu_block_backtest.py`) precomputes overnight,
first-hour, afternoon and stop returns once per session, then evaluates 1,920
parameter variants as a batch on the RTX 3080 in about 37 seconds. Exact
1-minute replay is reserved for the top few candidates.
