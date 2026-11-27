# Hypothesis: opening-drive continuation + weak-close overnight reversal

**Family:** intraday-microstructure
**Window:** 2016-01-04 -> 2023-12-29 (development only; no 2024+ data)
**Bar:** TQQQ dev 36.72% CAGR / 82.29% max DD / 0.82 Sharpe. Pass if
CAGR > 36.72% and DD < 82.29% (target DD < 60%).

## 1. Hypothesis

TQQQ's 3x leverage produces two distinct intraday price-action effects that
can be traded long-only on minute bars:

1. **Opening-drive continuation.** When TQQQ gaps up and the first five
   minutes extend the gap, the rest of the session tends to continue in the
   same direction. The effect is stronger than the unconditional intraday
   drift and survives a 30-minute confirmation window.
2. **Weak-close overnight reversal.** When the session closes weak (a down
   day), the overnight return is positive on average. This is the
   liquidity-provision / inventory-reversal component of the overnight
   risk premium, and it is strongest after an intraday decline.

A close-based trailing stop is added as a disclosed risk overlay: it lets the
right tail run while cutting the left tail on reversal days. It is not a
volatility or drawdown regime signal; it is a price-based exit.

No daily trend SMA, no volatility/drawdown regime, no relative strength, and
no drawdown recovery are used. The only non-price input is the session clock.

## 2. Why this is not the old opening-range breakout

`research/new/orb-tqqq-volume/` traded a 30-minute opening-range breakout
with volume/ATR filters, entered at a median 10:15, used an ATR stop, and
held to the close. It earned 17.89% dev CAGR and failed the bar. This
strategy is materially different:

- The day entry is a **first-5-minute / first-30-minute momentum** signal,
  not a break of a 30-minute range. It enters at 09:35 or 10:00, earlier
  than the old ORB's median entry.
- The exit is a **close-based trailing stop** (8% below the highest close
  since entry), not a fixed ATR stop. The stop is the load-bearing risk
  control.
- A **weak-close overnight sleeve** is added. It is the opposite of the old
  ORB's flat-every-night rule and captures part of TQQQ's overnight drift,
  which the old report identified as the structural reason a flat-overnight
  intraday strategy cannot reach the bar.
- The old ORB's volume and range-width filters are not used.

## 3. Exact rules

Universe: QQQ (calendar only), TQQQ (position), BIL (flat asset in the
headline; cash variant reported). Long-only, weights >= 0, sum <= 1. All
fills are at the next 1-minute bar's open; 2% band; 1 bp headline plus 5 and
10 bp.

Let `a` be the first bar of a session (09:30) and `b` the last bar (15:59 on
a full day, 13:00 on a half day).

```
gap   = open(09:30) / close(prior session last bar) - 1
r5    = close(09:34) / open(09:30) - 1
r30   = close(09:59) / open(09:30) - 1
dayret= close(15:58) / open(09:30) - 1

# Day sleeve (flat overnight by default)
if gap > +0.25% and r5 > 0:      buy at 09:35 open
elif r30 > +0.50%:               buy at 10:00 open
trailing stop: exit at the next bar's open if any 1-minute close is
               8% below the highest close since entry
otherwise:                      exit at the 15:59 open (second-to-last bar)

# Night sleeve (weak-close overnight reversal)
if dayret < -1.0%:              buy at the 15:59 open
                                 exit at the next 09:31 open
```

The day sleeve and the night sleeve can chain: if a day position is still on
at 15:58 and the night signal is true, it is held through the last bar and
overnight; otherwise it exits at the 15:59 open. A night position that is
still on at 09:30 the next day is exited at the 09:31 open unless the day
sleeve enters later that morning (the entry is at 09:35 or 10:00, so the
09:31-09:34 gap is flat).

Half-days use their own last bar. The trailing stop uses closes only, so it
does not need intrabar highs or lows and has no same-bar high/low ambiguity.

## 4. Pre-registered 8-cell grid

The grid varies the stop, the night threshold, the gap threshold and the
30-minute threshold around the base. The base is the centre of the stop
plateau, not the best cell.

| # | Cell | night | gap | r30 | trail |
|---|---|---|---|---|---|
| 1 | base | -1.0% | +0.25% | +0.50% | 8% |
| 2 | trail6 | -1.0% | +0.25% | +0.50% | 6% |
| 3 | trail10 | -1.0% | +0.25% | +0.50% | 10% |
| 4 | trail4 | -1.0% | +0.25% | +0.50% | 4% |
| 5 | night_dr15 | -1.5% | +0.25% | +0.50% | 8% |
| 6 | night_dr05 | -0.5% | +0.25% | +0.50% | 8% |
| 7 | gap0 | -1.0% | 0.0% | +0.50% | 8% |
| 8 | r30_065 | -1.0% | +0.25% | +0.65% | 8% |

The grid is deliberately small and covers the four free parameters. It is
not a search over entry times or holding periods; those are fixed by the
mechanism (09:35/10:00 entries, 15:58 day exit, 09:31 night exit).

## 5. Falsifiers

The hypothesis is rejected if any of the following holds:

- **F1.** The base dev CAGR is <= 36.72% or the max DD is >= 82.29%.
- **F2.** Fewer than 6 of the 8 grid cells clear the CAGR bar at 1 bp.
- **F3.** A random-entry placebo with the same holding/stop mechanics
  matches or beats the base (p > 0.10).
- **F4.** Removing 2020 or 2022 drops the CAGR below 36.72%.
- **F5.** Removing the best 20 days drops the CAGR below 36.72%.
- **F6.** The 5 bp CAGR is below 36.72% under the mandated BIL flat asset.
- **F7.** The strategy is not causal (pre-cut weight difference > 0).

## 6. Expected effect

- The day sleeve alone should clear the 1 bp bar on the strength of the
  opening-drive continuation; the night sleeve should add a small,
  low-drawdown overnight return.
- The trailing stop should cut the 2020 COVID drawdown from the 80%+
  buy-and-hold level to roughly 40-50%, at the cost of some upside.
- The strategy should be cost-sensitive: 1,300-1,500 round trips over eight
  years, with the BIL leg roughly doubling the fill count.
- The result should be positive in most calendar years but concentrated in
  the high-volatility years (2020, 2022), because 3x intraday momentum pays
  best when dispersion is high.

## 7. Data and integrity

- Data: adjusted 1-minute QQQ/TQQQ/BIL under `data/intraday-hf/`, regular
  session only, truncated at 2023-12-29 before any statistic is computed.
- No full-sample normalization; every threshold is fixed ex ante. The
  session features use only bars up to the decision bar.
- Truncation test: building weights on a panel cut at 2020-03-12 11:07
  leaves all weights before the cut session identical (max difference 0.0).
- The grid was frozen in `strategy.py` before the final `result.json` run.
  Earlier exploratory screens used the development window only; no holdout
  was loaded.
