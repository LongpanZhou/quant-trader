# Close location value - `family-close-location`

**Window:** 2016-01-04 -> 2023-12-29, development only. The 2024-2026
holdout is never loaded.

**Family:** close location value (CLV) / where the close sits inside the
session range. The primary object is CLV, not the opening range and not VWAP.

---

## 1. Mechanism

CLV measures where the last price sits inside the session's range:

```
CLV[d] = 2 * (close[d] - low[d]) / (high[d] - low[d]) - 1
```

A close at the session low is -1; a close at the session high is +1. The
family hypothesis allows either continuation (close at the high -> next-session
continuation) or reversal (close at the low -> next-session bounce). The
development scan found the **reversal** side: a close pinned at the session
low is followed by a strong TQQQ bounce over the next week, while a close at
the session high is followed by weak or negative forward returns. The primary
therefore buys the low-CLV event and does not trade the high-CLV event.

The economic story is forced selling / inventory imbalance: when the session
closes at its low, the marginal seller has pushed price to the bottom of the
day's range, and the next sessions mean-revert as that flow finishes. TQQQ is
the long instrument because it gives roughly 3x the QQQ bounce; the cost is 3x
the path risk, which is why the sleeve is flat (BIL) most of the time.

## 2. Exact rules

### Estimation window and decision clock

- `high[d]` and `low[d]` are the maximum and minimum of the **1-minute QQQ
  closes** from 09:30 to 15:59 ET; `close[d]` is the 15:59 ET close. The
  overnight gap is not part of the range.
- CLV is computed once per session at the 15:59 close. It is known at that
  moment and is not revised.
- The target is written on the 15:59 bar and fills at the **09:30 open** of the
  next session.
- No volatility estimate, no moving average, no full-sample normalisation.

Using the range of 1-minute closes rather than the official daily high/low
changes the CLV by a mean absolute 0.033 and gives a 0.997 correlation with the
official daily CLV. The 1-minute-close version is used so that the signal is
derived entirely from the research panel.

### Position rule

```
if CLV[d] < -0.80:
    TQQQ 1.0 for the next 5 sessions
else:
    BIL 1.0
```

A new event while holding rolls the 5-session exit forward. The position is 0
or 1; there is no volatility scaling, stop, profit target or trend filter in
the primary.

### Execution

`research/bt.py`, 1-minute marks, next-open fills, 2% band, long-only,
weights >= 0, sum <= 1. Headline cost 1 bp; 5 bp and 10 bp also reported. BIL is
the flat asset.

## 3. Pre-registered 8-cell grid

The grid was fixed before the final run. It varies the CLV threshold at the
primary 5-session hold, and the hold at the primary threshold.

| # | CLV threshold | hold | role |
|---:|---:|---:|---|
| 1 | -0.60 | 5 | shallow end |
| 2 | -0.70 | 5 | neighbour |
| 3 | **-0.80** | **5** | **primary** |
| 4 | -0.90 | 5 | deep end |
| 5 | -0.80 | 3 | short hold |
| 6 | -0.80 | 4 | short hold |
| 7 | -0.80 | 6 | long hold |
| 8 | -0.80 | 8 | long hold |

## 4. Falsifiers

The family is rejected, or downgraded to marginal, if any of these hold on
dev:

1. Primary 1 bp CAGR <= 36.72% or max drawdown >= 82.29%.
2. Fewer than 5 of the 8 grid cells clear the same bar.
3. 10 bp CAGR <= 36.72%.
4. Shift-placebo p > 0.05.
5. Random-entry placebo p > 0.05.
6. Ex-2020 CAGR <= 25%.
7. Daily-return correlation to `family-short-reversal` > 0.85 (which would
   mean CLV is only a re-parameterised down-day rule).
8. Fewer than 100 fills or fewer than 30 independent events.
9. Pre-cut max weight difference > 1e-12.
10. The event-forward 5-session return is not significantly positive
    (t <= 1.5).

## 5. Expected failure modes

- **2022 bear:** a close at the low keeps firing in a sustained decline, and
  the 5-session hold compounds down. The maximum drawdown should be in 2022,
  not 2020.
- **2020 crash:** the same mechanism in February-March 2020; the rebound
  rescues the year but the peak-to-trough loss is large.
- **Turnover:** 5-session holds with overlapping events produce ~12,900x
  turnover at 1 bp. The 10 bp case is the cost stress.
- **Short-reversal overlap:** CLV is correlated with down days; the daily
  correlation to `family-short-reversal` should be high (0.7-0.8). The CLV
  object must add something beyond the down-day rule, and the report compares
  them directly.
- **Small event count:** ~200 independent events over eight years; the
  bootstrap and the placebo are the honest significance tests.

## 6. What this is not

- Not opening-range breakout: the opening range is not computed.
- Not VWAP or close-flow: no volume-weighted price and no volume data is used.
- Not a 20/50/100/150/165/200-day moving-average trend gate.
- Not volatility targeting: the position is 0 or 1.
- Not a drawdown / capitulation event: no peak-to-trough state machine.
- Not a calendar clock, relative strength or ML.
- Not `family-short-reversal`: that rule is a QQQ down-streak / 3-day return;
  this one is the location of the close inside the intraday range, and it
  fires on days that are not necessarily down streaks.

## 7. Design provenance

The CLV was computed from the 1-minute closes on the development window only.
A coarse scan tested both directions:

- high CLV (close at the high) -> continuation: the forward returns were
  negative at the 1-3 session horizons (CLV > 0.8, h2: -7.6% dev CAGR;
  h3: -1.4%), so the continuation hypothesis was rejected;
- low CLV (close at the low) -> reversal: the forward returns were positive and
  increased with the hold, with a sweet spot at CLV < -0.80 and h5.

The threshold/hold grid above was then frozen, and the final run was made once.
No 2024-2026 data was loaded at any point. The high-CLV failure is reported as
a finding, not hidden.
