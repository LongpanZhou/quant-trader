# Intraday realized skew - `family-realized-skew`

**Window:** 2016-01-04 -> 2023-12-29, development only. The 2024-2026
holdout is never loaded.

**Family:** realized skewness / semivariance asymmetry of intraday returns.
The primary object is the skew, not the volatility level.

---

## 1. Mechanism

Realized skew measures the asymmetry of the intraday return distribution. A
negative-skew session has many small up moves and a few large down moves; a
positive-skew session has the opposite. The skewness premium says assets with
negative skew must offer higher expected returns, and the lottery literature
says positive-skew assets are overpriced. The family hypothesis is therefore:

- negative realized skew -> a bounce / higher forward return;
- positive realized skew -> continuation or fragility (lower forward return).

The signal is deliberately built from **5-minute intraday returns**, so the
overnight gap does not enter the skew. The overnight gap is a separate object
(and is already used by the gap families).

The development scan found that the negative-skew bounce is real at the event
level but only in the **mild** negative range. Extreme negative skew (the
crash tail, S10 < -0.15 or -0.20) is followed by *worse* returns, not better
ones: a crash-skew session is a warning, not a buy signal. The primary
threshold is therefore -0.10, the mild-negative region, and the report states
that the extreme-tail version fails.

## 2. Exact rules

### Estimation window and decision clock

```
5-minute closes: 09:34, 09:39, ..., 15:59 ET
r5[j]  = log(close5[j] / close5[j-1])            (77 returns per full session)
RS[d]  = mean(r5^3) / mean(r5^2)^1.5             (per-session realized skew)
S10[d] = mean(RS[d-9..d])                        (trailing 10 sessions)
```

`S10[d]` uses only sessions through the 15:59 close of day d. The overnight
gap is excluded. Sessions with fewer than 10 five-minute returns (half-days,
data holes) are skipped; the 10-day mean uses the available sessions.

### Position rule (known at 15:59 of d; fill at the next 09:30 open)

```
if S10[d] < -0.10:
    TQQQ 1.0 for the next 3 sessions
else:
    BIL 1.0
```

A new signal while holding rolls the 3-session exit forward. The position is
0 or 1; there is no volatility scaling and no volatility filter.

### Execution

`research/bt.py`, 1-minute marks, next-open fills, 2% band, long-only,
weights >= 0, sum <= 1. Headline cost 1 bp; 5 bp and 10 bp also reported. BIL is
the flat asset.

## 3. Pre-registered 8-cell grid

The grid was fixed before the final run. It varies the skew threshold at the
primary 3-session hold, and the hold at the primary threshold.

| # | S10 threshold | hold | role |
|---:|---:|---:|---|
| 1 | **-0.10** | **3** | **primary** |
| 2 | -0.05 | 3 | shallower |
| 3 | -0.15 | 3 | deeper |
| 4 | -0.20 | 3 | extreme tail |
| 5 | -0.10 | 2 | short hold |
| 6 | -0.10 | 4 | longer hold |
| 7 | -0.10 | 5 | longer hold |
| 8 | -0.10 | 6 | longer hold |

## 4. Falsifiers

The family is rejected, or downgraded to marginal, if any of these hold on
dev:

1. Primary 1 bp CAGR <= 36.72% or max drawdown >= 82.29%.
2. Fewer than 5 of the 8 grid cells clear the same bar.
3. 10 bp CAGR <= 36.72%.
4. Shift-placebo p > 0.05.
5. Random-entry placebo p > 0.05.
6. Ex-2020 CAGR <= 25%.
7. Daily-return correlation to any of the nine current winners > 0.85.
8. Fewer than 100 fills or fewer than 30 independent events.
9. Pre-cut max weight difference > 1e-12.
10. The event-forward 3-session return is not significantly positive
    (t <= 1.5), which would mean the skew premium is not present at the event
    level.

## 5. Expected failure modes

- **Extreme-tail failure:** the deepest negative-skew sessions are crash
  sessions; buying them should be worse, not better. The -0.15 and -0.20 grid
  cells are the test.
- **Ex-2020 dependence:** the 2020 crash-recovery should carry a large share
  of the return; ex-2020 is reported.
- **Overlap with short reversal:** negative skew is correlated with down
  days, so the daily correlation to `family-short-reversal` should be
  moderately high (0.5-0.7).
- **Weak placebo:** the event count is large (849) but highly overlapping, so
  the event t-stat overstates the independent evidence. The portfolio placebo
  is the honest test.
- **Cost sensitivity:** 2,500x turnover at 1 bp; the 10 bp case is the stress.

## 6. What this is not

- Not volatility targeting: the position is 0 or 1; the signal is the third
  moment, not the second.
- Not a volatility filter: no VIX, no realized-vol level and no vol regime.
- Not a 20/50/100/150/165/200-day moving-average trend gate.
- Not a drawdown / capitulation event: no peak-to-trough state machine.
- Not a calendar clock, opening-range, VWAP or relative-strength rule.
- Not ML.

## 7. Design provenance

The daily realized skew and the 10-day mean were computed on the development
window only. A coarse scan tested the daily skew, the 5-day mean and the
10-day mean at thresholds from -2.0 to 0.0. The extreme negative thresholds
produced few events and negative forward returns; the mild negative threshold
(-0.10 on the 10-day mean) produced the stable positive event edge. The
threshold/hold grid above was then frozen, and the final run was made once. No
2024-2026 data was loaded at any point. The failure of the extreme tail is
reported as a finding, not hidden.
