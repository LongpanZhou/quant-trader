# Rolling Hurst / variance ratio - `family-hurst-persistence`

**Window:** 2016-01-04 -> 2023-12-29, development only. The 2024-2026
holdout is never loaded.

**Family:** persistence / mean-reversion regime estimated from the Hurst
exponent. The primary object is the Hurst estimate, not a moving average.

---

## 1. Mechanism

The Hurst exponent summarises how quickly the variance of a return series
scales with the horizon. For a random walk H = 0.5. H > 0.5 means increments
are positively autocorrelated (persistence / trend), H < 0.5 means they are
negatively autocorrelated (mean reversion).

The family hypothesis is:

- H > 0.5: trend continuation is favoured -> hold the long sleeve.
- H < 0.5: mean reversion is favoured -> buy declines.
- H ~ 0.5: no edge -> cash.

QQQ daily returns are negatively autocorrelated over 2016-2023. The rolling
estimate never reaches 0.5 in this sample: the full-dev mean is **0.433**, the
minimum **0.287**, the maximum **0.511**, and only one day is above 0.50. The
absolute version of the hypothesis therefore cannot be tested as written; the
test has to be whether the *relative* Hurst state separates forward returns.

A coarse development scan found that the low-H side is the risk-on side and
the high-H side is the risk-off side. The high-H state is not a trend-
continuation state in QQQ; it is disproportionately a persistent-downside /
high-volatility state. The primary rule keeps the low-H (mean-reversion) leg
and the neutral-band drift leg, and stands aside in the high-H state. This is
the inverse of the naive "persistent -> trend" reading, and the report states
it plainly rather than pretending the original sign worked.

## 2. Exact rules

### Estimation window

```
r[d]   = QQQ_close[d] / QQQ_close[d-1] - 1          (15:59 ET closes)
VR(q)  = Var(sum of q consecutive r) / (q * Var(r))  over the last W returns
H[d]   = 0.5 + log(VR(q)) / (2 * log(q))
W = 252, q = 5
```

`H[d]` uses only returns through the 15:59 close of day d. The thresholds are
the expanding 30th and 70th percentiles of the H estimates over a rolling
window of at most **1,260** observations (including the current estimate),
with a minimum of **60** estimates. The minimum is what lets the strategy start
in March 2017 rather than January 2018; it is causal and uses no future
observations.

The first H estimate needs 252 daily returns, so the first valid H is
**2017-01-03**. The first quantile threshold needs 60 H estimates, so the first
trade is **2017-03-29**. 2016 is therefore a structural cash year. That is a
real cost of a one-year estimator, not an intentional filter.

### Position rule (known at the 15:59 close of d; fill at the next 09:30 open)

```
if H[d] <= q30[d]:
    TQQQ 1.0                       # strong mean reversion: stay long
elif q30[d] < H[d] < q70[d] and QQQ_5d_return[d] > 0:
    TQQQ 1.0                       # neutral band, short-term drift up
else:
    BIL 1.0                        # high-H persistent state, or neutral-down
```

The 5-day return is only the direction selector inside the neutral band. It is
not a moving average, and it is not the regime variable.

### Execution

`research/bt.py`, 1-minute marks, next-open fills, 2% band, long-only,
weights >= 0, row sum <= 1. Headline cost 1 bp; 5 bp and 10 bp also reported.
BIL is the flat asset, so the cash return is the T-bill return.

## 3. Pre-registered 8-cell grid

The grid was fixed before the final run. It varies the estimator window, the
variance-ratio horizon and the quantile band; the rule is unchanged.

| # | W | q | band | role |
|---:|---:|---:|---|---|
| 1 | **252** | **5** | **30/70** | **primary** |
| 2 | 252 | 2 | 30/70 | short VR horizon |
| 3 | 252 | 10 | 30/70 | long VR horizon |
| 4 | 126 | 5 | 30/70 | half-year window |
| 5 | 126 | 2 | 30/70 | half-year, short VR |
| 6 | 126 | 10 | 30/70 | half-year, long VR |
| 7 | 252 | 5 | 25/75 | wider tails |
| 8 | 252 | 5 | 35/65 | narrower core |

## 4. Falsifiers

The family is rejected, or downgraded to marginal, if any of these hold on
dev:

1. Primary 1 bp CAGR <= 36.72% or max drawdown >= 82.29%.
2. Fewer than 5 of the 8 grid cells clear the same bar.
3. 10 bp CAGR <= 36.72%.
4. Shift-placebo p > 0.05.
5. Shuffle-placebo p > 0.05.
6. Ex-2020 CAGR <= 25%.
7. Daily-return correlation to any of the nine current winners > 0.85.
8. Fewer than 100 fills or fewer than 30 independent entries.
9. Pre-cut max weight difference > 1e-12.

## 5. Expected failure modes

- **2020 crash:** the low-H state is exactly the high-volatility crash state,
  so the strategy is nearly fully invested into February-March 2020. The
  largest drawdown should be there, not in 2022.
- **2016-2017 cash drag:** the estimator needs a year of returns and three
  months of H history. The first two calendar years should be poor.
- **Right-skewed episode distribution:** a handful of low-H entries in 2020
  and 2021 carry a large share of the compounded return. The median episode
  should be much smaller than the mean.
- **High TQQQ correlation:** roughly half the time in TQQQ gives a daily
  correlation around 0.65-0.70. This is a timing overlay on leveraged Nasdaq
  beta, not a diversifying alpha.
- **Parameter sensitivity:** the 126-day/q=10 cell should be weak; the
  one-year/q=5 cell is the economic prior.

## 6. What this is not

- Not a 20/50/100/150/165/200-day moving-average trend gate: no moving
  average is computed.
- Not volatility targeting: the position is 0 or 1; there is no vol estimate
  in the sizing.
- Not a drawdown / capitulation event: no peak-to-trough state machine.
- Not a calendar clock: no FOMC, OpEx, turn-of-month or session-time rule.
- Not relative strength: no QQQ/SPY or TQQQ/QQQ ratio.
- Not opening-range or close-flow: the only intraday input is the 15:59 close.

## 7. Design provenance

The Hurst estimate and the quantile thresholds were computed on the
development window only. A coarse scan first tested the literal hypothesis
(high H -> long trend, low H -> fade), and the high-H long leg lost money
(always-long in the top H tercile: -8.8% dev CAGR; high-H + 5-day-up: -11.8%).
The low-H state was the profitable side. The rule above and the 8-cell grid
were then frozen, and the final run was made once. No 2024-2026 data was
loaded at any point. The inversion is reported as a finding, not hidden.
