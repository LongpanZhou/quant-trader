# Sign CUSUM change-point - `family-change-point`

**Window:** 2016-01-04 -> 2023-12-29, development only. The 2024-2026
holdout is never loaded.

**Family:** online change-point detection. The primary object is the CUSUM
break statistic, not a moving average.

---

## 1. Mechanism

A change-point detector asks a different question from a trend filter: has the
*data-generating process* changed, not is price above an average? The CUSUM is
the simplest sequential answer. It accumulates evidence of a shift in the
up/down balance and fires when the evidence crosses a threshold.

The family hypothesis is: a detected break marks a new direction / volatility
state, and the new state persists long enough to trade with a fixed holding
window. The primary uses the **sign** of the daily return as the increment:

```
x[d]  = +1 if QQQ_close[d] > QQQ_close[d-1]
        -1 if QQQ_close[d] < QQQ_close[d-1]
         0 if unchanged
S+[d] = max(0, S+[d-1] + x[d] - k)
S-[d] = max(0, S-[d-1] - x[d] - k)
```

`S+` is the running excess of up days over down days; `S-` is its mirror. A
break is `S+ > h` (up-break) or `S- > h` (down-break); the triggered statistic
resets. k = 0.00, h = 3.0 in the primary. The statistic is bounded and does not
need a volatility estimate.

The alternative - CUSUM on standardized return magnitudes - was tested first
and was weaker: its up-breaks were less reliable and its threshold surface was
more jagged. The sign version is the primary because the break object is
cleaner and the up-break forward edge is stronger. The report gives both the
success and the failure of the direction hypothesis.

## 2. Exact rules

### Estimation window and decision clock

- `x[d]` uses the QQQ 15:59 close and the prior session's 15:59 close.
- `S+`, `S-` are updated once per session at the 15:59 close; the recursion is
  causal and starts after a 20-session data warm-up.
- A break at the close of day d is known at 15:59 and fills at the 09:30 open
  of day d+1.
- No volatility estimate, no moving average and no full-sample scaling is used.

### Position rule

```
up-break   at close d -> TQQQ 1.0 for the next 20 sessions
down-break at close d -> BIL  1.0 for the next 20 sessions
a new break while a window is active replaces the direction and restarts
the 20-session clock
```

The 20-session window is a fixed holding period, not a trend gate. If an
up-break and a down-break occur close together, the later one wins; that is the
whipsaw risk and it is measured in the report.

### Execution

`research/bt.py`, 1-minute marks, next-open fills, 2% band, long-only,
weights >= 0, sum <= 1. Headline cost 1 bp; 5 bp and 10 bp also reported. BIL is
the flat asset.

## 3. Pre-registered 8-cell grid

The grid was fixed before the final run. It varies the threshold `h` and the
drift allowance `k` at the primary 20-session hold, plus one 15-session hold
cell.

| # | k | h | hold | role |
|---:|---:|---:|---:|---|
| 1 | **0.00** | **3.0** | **20** | **primary** |
| 2 | 0.00 | 4.0 | 20 | higher threshold |
| 3 | 0.00 | 5.0 | 20 | higher threshold |
| 4 | 0.00 | 6.0 | 20 | high threshold |
| 5 | 0.10 | 3.0 | 20 | small drift allowance |
| 6 | 0.10 | 5.0 | 20 | drift + higher threshold |
| 7 | 0.20 | 3.0 | 20 | larger drift allowance |
| 8 | 0.10 | 3.0 | 15 | shorter hold |

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
8. Fewer than 100 fills or fewer than 30 independent breaks.
9. Pre-cut max weight difference > 1e-12.
10. The down-break forward 20-session return is significantly positive
    (t > 2): that would mean the "new direction down" leg is false and the
    cash rule is not supported by the event study.

## 5. Expected failure modes

- **Whipsaw:** a down-break immediately after an up-break cancels the long
  window and can lock in a loss. The 2018 Q4 drawdown is the test.
- **Down-break leg false:** if down-breaks are followed by rebounds, the cash
  window is opportunity cost, not protection. The event study measures this
  directly.
- **Threshold sensitivity:** the break count changes quickly with h; the h=4
  cell is the most likely hole in the plateau.
- **2020 dependence:** a large share of the return should come from the
  2020-2021 recovery; ex-2020 is reported.
- **High TQQQ correlation:** with ~64% exposure, the daily correlation should
  be around 0.6.

## 6. What this is not

- Not a 20/50/100/150/165/200-day moving-average trend gate: no moving
  average is used.
- Not volatility targeting: the position is 0 or 1; no vol estimate.
- Not a drawdown / capitulation event: no peak-to-trough state machine.
- Not a calendar clock: no FOMC, OpEx, turn-of-month or session-time rule.
- Not opening-range or close-flow: the only input is the daily close.
- Not relative strength or ML.

## 7. Design provenance

The development scan tested the standardized-return CUSUM first (k = 0.10,
h = 3.0). It produced a weaker primary (42.5% dev CAGR, 57.6% DD), a narrower
threshold surface, and a down-break forward return of +3.9% (t = 1.71) - the
opposite of the direction hypothesis. The sign CUSUM was then fixed as the
primary because it is bounded, has a stronger up-break forward edge (+4.20%,
t = 3.33), and a wider 6/8 grid. The grid above was frozen and the final run
was made once. No 2024-2026 data was loaded at any point.
