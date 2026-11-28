# Short-horizon dip reversal — `family-short-reversal`

**Window:** 2016-01-04 → 2023-12-29, development only. The 2024-2026
holdout is never loaded.

**Family:** short-horizon mean reversion. Buy TQQQ after a short decline,
exit within five sessions. No trend SMA, no volatility/drawdown regime as the
primary signal, no relative-strength gate, no drawdown-recovery circuit
breaker.

---

## 1. Mechanism

A two- to three-session decline in QQQ is mostly a positioning event: short-term
supply, dealer inventory and stop-loss flow push the price below its recent
path. When the decline is not a single-day information shock, the following
sessions tend to retrace part of it. TQQQ is the instrument because it gives
roughly 3x the QQQ bounce; the cost is 3x the path risk, which is why the
strategy is a **sleeve** (TQQQ when the event is on, BIL otherwise), not a
permanent position.

The signal deliberately has two legs with different jobs:

- **2 consecutive QQQ down days (`q2dn`)** is the broad, frequent leg. On its
  own it is close to TQQQ beta (dev 35.1% CAGR, 57.6% DD); its job is to keep
  the sleeve invested often enough that the strategy can clear the TQQQ CAGR
  bar at all.
- **3-session QQQ return ≤ −1.5% (`q3`)** is the sharper leg. It fires on the
  deeper dips where the reversal edge per unit of exposure is highest, and it
  chains with the broad leg.

The primary is the union. The 3-day-return leg is the only one of the three
mandated trigger families that showed a positive open-to-open forward edge in
the dev event study; down-streak-only and RSI(2)-only triggers were at or below
the unconditional TQQQ drift, and the 5-day-return leg was flat-to-negative.
The 2-day streak is retained because it supplies exposure and because the
mandate explicitly allows it, not because it has a large standalone edge.

**Falling-knife warning.** This is the known failure mode of the family. A
decline cluster in a bear market keeps generating `q2dn` events, the sleeve
stays fully invested, and the 3x fund compounds down. The primary has no
trend or drawdown gate by mandate; a hard stop and vol-target sizing are
tested as overlays but are not part of the primary. The 2020 and 2022 results
in the report are the honest measure of this risk.

## 2. Exact rules

All signals are computed at the **15:59 ET close of session d**; the target is
written on that bar and fills at the **09:30 open of session d+1**.

```
q2dn[d] = QQQ_close[d] < QQQ_close[d-1] AND QQQ_close[d-1] < QQQ_close[d-2]
q3[d]   = QQQ_close[d] / QQQ_close[d-3] - 1
event[d] = q2dn[d] OR (q3[d] <= -1.5%)

entry:  TQQQ weight 1.0 at the next session open
hold:   5 sessions; exit at the open after the fifth held session
chain:  if a new event fires while holding, the exit moves to 5 sessions
        from the latest event (a rolling 5-session hold, never longer than
        the latest event plus five sessions)
flat:   BIL weight 1.0
```

Warm-up: no trades in the first 20 sessions of the panel. This is a data
warm-up only, not a trend filter.

No stop, no profit target and no vol target in the primary. Those are tested as
risk overlays in the report; they lower CAGR and do not lower the maximum
drawdown, so the primary stays simple.

Execution: `research/bt.py`, 1-minute marks, next-open fills, 2% band,
long-only, weights ≥ 0, sum ≤ 1. Headline cost 1 bp; 5 bp and 10 bp reported.
When the sleeve is flat it holds BIL, so the cash return is the T-bill return,
not zero.

## 3. Pre-registered grid (8 cells)

The grid is fixed before the final run. It varies the 3-day-return threshold at
the primary hold of 5 sessions, and the hold at the primary threshold of
−1.5%. The 2-day-streak leg is on in every cell.

| # | 3-day threshold | hold | role |
|---:|---:|---:|---|
| 1 | −0.50% | 5 | shallow end |
| 2 | −0.75% | 5 | shallow end |
| 3 | −1.00% | 5 | neighbour |
| 4 | **−1.50%** | **5** | **primary** |
| 5 | −2.00% | 5 | neighbour |
| 6 | −3.00% | 5 | deep end |
| 7 | −1.50% | 3 | short hold |
| 8 | −1.50% | 4 | short hold |

The 2-day-streak-only variant (no `q3` leg) is reported as a leg attribution,
not as a grid cell.

## 4. Falsifiers

The family claim is rejected, or downgraded to a marginal pass, if any of these
hold on dev:

1. Primary 1 bp CAGR ≤ 36.72%.
2. Primary max drawdown ≥ 82.29%.
3. The threshold row is a single-cell spike: neighbours 5 and 6 fall more than
   2 pp below the primary while the primary clears the bar.
4. The hold row is a single-horizon spike: h3 and h4 fall more than 5 pp below
   h5.
5. Ex-2020 CAGR is below 36.72%.
6. The random-entry placebo p-value is above 0.05.
7. The 10 bp CAGR is below 36.72%.

A pass that survives only at 1 bp and only at one threshold/hold cell is
reported as **marginal**, not as a validated family edge.

## 5. Expected failure modes

- **2022 / 2018 falling knives:** the 2-day-streak leg keeps buying into a
  sustained bear, and 5-session holds overlap into a nearly continuous long
  position. The 2022 loss should be large even if it is smaller than TQQQ's.
- **2020 crash:** the same mechanism produces the maximum drawdown, because the
  sleeve is fully invested into the February-March decline and the rebound is
  not enough to avoid a deep peak-to-trough loss.
- **2020 dependence:** a large share of the dev P&L should come from the
  2020-2021 recovery. If ex-2020 CAGR is below the bar, the pass is one
  episode, not a repeatable premium.
- **High TQQQ correlation:** with ~60% TQQQ exposure, the daily correlation to
  TQQQ should be high (0.85-0.90). This is a timing overlay on leveraged beta,
  not a diversifying alpha.
- **Cost sensitivity:** ~450 fills and ~3,700x turnover; 10 bp costs should
  cost several pp of CAGR.

## 6. What this is not

- Not a 20/50/100/150/165/200-day trend gate: no moving average is used.
- Not a volatility or drawdown regime strategy: the primary has no vol filter,
  no drawdown circuit breaker and no crash cooldown.
- Not relative strength: no QQQ/SPY or TQQQ/QQQ ratio.
- Not drawdown-recovery: no deep-drawdown state machine; the signal is a
  two-to-three-session decline, and the hold is five sessions.
- Not the existing `capitulation-reversal-v2`: that strategy enters at the
  event-day close (15:59) on a 3/10/15-day decline with a volume cap and holds
  one session. This one enters at the **next open**, uses a 2-day streak plus a
  3-day return, holds five sessions and has no volume filter.

## 7. Design provenance

The three mandated trigger families were scanned on the development window
before this file was frozen: 2-4 down days, 3-day and 5-day returns, and
RSI(2). The scan used next-open, open-to-open returns and the union/portfolio
accounting, not the final evaluation metrics. The 3-day-return leg was the only
standalone leg with a positive edge over the unconditional drift; the 5-day leg
and the RSI(2) leg were flat. The 2-day streak was added for exposure. The grid
above was then fixed and run once. No 2024-2026 data was loaded at any point.
