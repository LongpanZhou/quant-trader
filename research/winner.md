# Winner: daily 165-day QQQ regime + armed 4% minute stop

Status: **verified winner** across all 10 research agents. Not yet committed.

> **Round-2 update:** the TQQQ/QQQ ratio-froth overlay (Agent 21) now leads:
> 69.50% / 39.11% (10y) and 63.74% / 26.85% (5y) at 1 bp, with 27/27 rolling
> 3-year windows beating TQQQ on both return and drawdown. See
> `research/agents2/LEADER.md`. This file remains the round-1 winner record and
> the strict two-window baseline.

## Objective

Beat TQQQ buy-and-hold on **both** return and maximum drawdown, on both the
10-year and 5-year windows, using minute data with no look-ahead and next-bar
fills.

| Benchmark | 10y CAGR | 10y max DD | 5y CAGR | 5y max DD |
|---|---:|---:|---:|---:|
| TQQQ buy & hold | 39.28% | 81.68% | 13.47% | 81.68% |
| Daily QQQ 165d SMA baseline | 45.31% | 58.71% | 34.61% | 36.86% |

## Rules

1. **Regime (daily):** if QQQ's prior daily close is above its 165-day SMA,
   the next session is risk-on; otherwise hold 100% BIL.
2. **Risk-on:** hold 100% TQQQ, including overnight.
3. **Arm the stop:** on a risk-on day, arm a 4% stop from the session open only
   when QQQ's first-minute close is below its prior 20-day SMA times 1.01.
4. **Stop:** while armed, if TQQQ closes 4% below the session open, sell at the
   next minute's open and stay in BIL for the rest of the session **and the
   following night**. Re-enter at the next session's open if the regime is
   still risk-on.
5. Long-only, one position at a time, no leverage beyond 100% TQQQ.

The stop is the only minute decision. It fires rarely (160 events over the full
2016–2026 sample), so costs are low and the overnight drift is preserved.

## Results (independently replicated)

`research/verification/verify_agent1.py` re-implements the rules from scratch,
loads the same 1-minute panel, and checks causality by truncating all data after
2022-01-03 and confirming every prior weight is unchanged.

```text
causality: truncation at 2022-01-03 leaves prior weights unchanged = True

10y  1bp  CAGR 58.80%  DD 44.56%  Sharpe 1.24  fills 657
10y  5bp  CAGR 54.60%  DD 47.08%  Sharpe 1.18  fills 657
10y 10bp  CAGR 49.50%  DD 50.06%  Sharpe 1.11  fills 657

5y   1bp  CAGR 49.88%  DD 33.49%  Sharpe 1.16  fills 337
5y   5bp  CAGR 45.89%  DD 34.13%  Sharpe 1.09  fills 337
5y  10bp  CAGR 41.05%  DD 34.93%  Sharpe 1.01  fills 337
```

Pass/fail:

| Test | 10y | 5y |
|---|---|---|
| CAGR > TQQQ | 58.80% > 39.28% | 49.88% > 13.47% |
| Max DD < TQQQ | 44.56% < 81.68% | 33.49% < 81.68% |
| CAGR > daily baseline | 58.80% > 45.31% | 49.88% > 34.61% |
| Max DD < daily baseline | 44.56% < 58.71% | 33.49% < 36.86% |
| Passes at 10bp | yes | yes |

## Year-by-year consistency

Return and within-year max drawdown, strategy vs TQQQ:

| Year | Strategy return | Strategy DD | TQQQ return | TQQQ DD | Return | DD |
|---|---:|---:|---:|---:|---|---|
| 2017 | +118.76% | 17.07% | +114.54% | 15.97% | win | slightly higher |
| 2018 | +0.47% | 41.05% | −20.76% | 59.36% | win | lower |
| 2019 | +47.94% | 32.01% | +148.23% | 31.96% | lag | flat |
| 2020 | +183.91% | 39.32% | +104.14% | 72.74% | win | lower |
| 2021 | +60.61% | 41.50% | +81.05% | 32.84% | lag | higher |
| 2022 | −17.99% | 21.79% | −79.39% | 81.10% | win | lower |
| 2023 | +149.04% | 26.64% | +192.05% | 34.93% | lag | lower |
| 2024 | +67.96% | 29.43% | +62.43% | 42.17% | win | lower |
| 2025 | +43.29% | 24.06% | +32.10% | 61.23% | win | lower |
| 2026 | +16.76% | 33.49% | +22.62% | 35.46% | lag | lower |

- Beats TQQQ on return in **6 of 10** years.
- Has a lower within-year drawdown in **7 of 10** years.
- The three return lags are strong bull years (2019, 2021, 2023); the strategy
  gives up upside in melt-ups to cut crash risk.
- 2020 is the largest return contribution (+184% vs +104%). Excluding 2020 the
  edge is smaller, so treat the point estimate as high-40s to low-50s CAGR, not
  a guaranteed 58.8%.

## Sub-periods (from the agent report)

| Period | CAGR | Max DD |
|---|---:|---:|
| 2017–2021 | 73.4% | 44.6% |
| 2022–2026 | 45.2% | 33.5% |
| 2017–2019 | +2 pp over the no-overlay control | — |
| 2023–2026 | +14 pp over the no-overlay control | — |

The improvement is present in both halves, not only 2020, though 2020–2022 is
the strongest stretch.

## Robustness (independent)

`research/verification/robustness_agent1.py` re-runs the rules across a small
parameter grid and with an extra bar of execution delay.

| Variant | 10y CAGR / DD | 5y CAGR / DD |
|---|---:|---:|
| Base: 4% stop, MA20 arm, SMA165 | 58.80% / 44.56% | 49.88% / 33.49% |
| Stop 2.5% | 53.75% / 43.02% | 44.60% / 43.02% |
| Stop 3% | 54.05% / 48.43% | 44.36% / 37.66% |
| Stop 5% | 50.15% / 43.03% | 41.46% / 42.31% |
| Stop 6% | 47.07% / 47.25% | 42.17% / 41.12% |
| Arm gate MA50 | 53.58% / 42.34% | 49.42% / 30.88% |
| Regime SMA150 | 57.38% / 41.50% | 43.04% / 36.62% |
| Regime SMA180 | 58.36% / 46.97% | 48.14% / 33.49% |
| Base + 1 extra bar delay | 56.69% / 45.24% | 50.91% / 33.06% |

**Every variant still beats TQQQ on both windows** (CAGR > 39.28%/13.47%,
DD < 81.68%). The result is a plateau, not a single lucky parameter.

Rolling 3-year windows, quarterly starts from 2017-04 to 2023-10 (27 windows):

- **Drawdown lower than TQQQ in 27/27 windows.**
- **Return higher than TQQQ in 23/27 windows.**
- Both conditions in 23/27 windows.
- The four return lags are 2018-04, 2018-07, 2019-01 and 2023-01, all strong
  bull-market stretches where giving up upside is the cost of crash protection.

This is the strongest evidence for “consistently”: the drawdown advantage is
present in every rolling window tested, and the return advantage in 85% of them.

## Why it works

TQQQ's drift is overwhelmingly overnight: the agent measured **+1,354.8%
overnight vs +81.2% intraday** over 2017–2026. Intraday-only designs are
therefore structurally disadvantaged. This strategy stays invested overnight
and uses minute data only to avoid a handful of crash days. The 4% stop is a
cheap crash hedge, not a continuous trading edge:

- 160 stop events over the full sample, median event ≈ 0, mean ≈ −0.30%.
- The average masks a few gap nights: 2020-03-11 −21.6%, 2024-08-02 −13.8%.
- Robust across 2.5–6% stop levels and MA20/MA50 arm gates (agent report).
- The same daily regime **without** the minute stop is 46.63% / 58.76% (10y)
  and 36.14% / 42.17% (5y); the stop adds roughly 12 pp of CAGR and cuts the
  10y drawdown by about 14 pp.

## Verified leaderboard

Only strategies that pass both windows vs TQQQ are listed.

| Agent / strategy | 10y CAGR | 10y DD | 5y CAGR | 5y DD | Minute decision? |
|---|---:|---:|---:|---:|---|
| ML risk-off overlay | 74.95% | 40.48% | 51.29% | 33.20% | No — daily |
| **Daily regime + armed 4% minute stop** | **58.80%** | **44.56%** | **49.88%** | **33.49%** | **Yes — 1m stop** |
| Intraday momentum + first-hour filter | 55.63% | 44.89% | 46.36% | 32.64% | Yes — 1m signal |
| Ensemble: trend + vol budget + 1m crash vote | 54.73% | 39.91% | 40.79% | 34.93% | Yes — 1m crash vote |
| Intraday mean reversion / 3% QQQ stop | 50.96% | 44.83% | 35.50% | 36.29% | Yes — 5m stop |
| Time-of-day overnight + first 30m (V2) | 49.23% | 42.66% | 28.89% | 34.54% | Yes — 2 fills/day, fails 5bp |
| Opening-range breakout, 30m swing | 48.98% | 48.55% | 34.08% | 42.17% | Yes — 1m ORB entry |
| Volatility ladder + crash throttle | 47.53% | 45.32% | 34.59% | 36.29% | Partial — 1m RV, daily |
| Drawdown threshold stop + 10d re-entry | 46.89% | 45.32% | 32.40% | 42.96% | Yes — 1m stop |
| 5-minute Donchian entry | 46.36% | 59.79% | 37.46% | 40.82% | Yes — 5m entry |

The ML strategy has the highest headline return but its 30/60-minute classifier
failed out of sample; the passing version makes daily decisions, so it does not
satisfy the minute-trading requirement. The winner is the best strategy whose
edge survives as a genuine minute-execution rule.

### Winner vs the closest runner-up

The ensemble (Agent 8) is the closest alternative: it has a lower 10-year
drawdown (39.91% vs 44.56%) and fewer fills (225 vs 657), but lower return and
Sharpe in both windows, and weaker rolling-window consistency.

| Test | Agent 1 winner | Agent 8 ensemble |
|---|---:|---:|
| 10y CAGR / DD | **58.80% / 44.56%** | 54.73% / **39.91%** |
| 5y CAGR / DD | **49.88% / 33.49%** | 40.79% / 34.93% |
| 10y Sharpe | **1.24** | 1.19 |
| 5y Sharpe | **1.16** | 0.99 |
| 5bp 10y CAGR / DD | **54.60% / 47.08%** | 53.32% / **40.48%** |
| 5bp 5y CAGR / DD | **45.89% / 34.13%** | 39.79% / 34.93% |
| Rolling 3y return wins | **23/27** | 19/27 |
| Rolling 3y DD wins | 27/27 | 27/27 |

Agent 1 is selected because it has the higher return in both headline windows,
the higher Sharpe in both, and the better rolling return consistency. Agent 8
is the better choice if the priority is the smallest 10-year drawdown and the
lowest turnover rather than maximum return.

## Caveats

- 1-minute data starts in 2016; the free sample cannot test 2000/2008. A 26-year
  1-minute test needs paid QQQ/TQQQ history (Kibot ~$145, MarketParquet ~$79).
- The stop's return contribution is crash-episode dependent, not statistically
  significant in isolation; the drawdown cut is the structural part.
- Drawdown is still 44.6% over 10 years. This is not a low-risk strategy; it is
  a lower-risk way to hold a 3x ETF.
- The 5-year window starts near the 2021 top, which flatters trend strategies
  relative to TQQQ. The 10-year result is the more representative one.

## Reproduction

```powershell
cd C:\Users\27175\Desktop\quant-trader-research
$env:PYTHONPATH = "C:\Users\27175\AppData\Local\Temp\opencode\pylibs"
python research/agents/daily-regime-minute-entry/strategy.py
python research/verification/verify_agent1.py
python research/compare_agents.py
```
