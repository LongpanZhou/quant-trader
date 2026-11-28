# HYPOTHESIS — volume-orderflow-v2 (participation exhaustion)

**Status:** pre-registered before the confirmatory grid. Development window only:
2016-01-04 → 2023-12-29. The 2024-2026 holdout is outside the panel and is not inspected.
**Original:** `research/revisit/volume-orderflow/`
**New code:** `strategy.py` in this directory.

---

## 1. Why the original barely traded

The original signal was

```
rvol    = QQQ_volume[d] / mean(QQQ_volume[d-20 .. d-1])
intraday= QQQ_close[d] / QQQ_open[d] - 1
clv     = ((close-low) - (high-close)) / (high-low)      # +1 at high, -1 at low
event   = (rvol >= 1.5) AND (intraday <= -0.8%) AND (clv >= 0)
```

Development-window component counts (2012 sessions):

| Component | Days |
|---|---:|
| `rvol >= 1.5` | 192 |
| `QQQ intraday <= -0.8%` | 342 |
| `clv >= 0` | 1183 |
| all three | **3** |

The close-location condition is not rare in general, but it is nearly
self-contradictory on a down day: conditional on QQQ falling at least 0.8%
intraday, only five sessions close in the upper half of their range. A large
down day normally closes near its low, so `clv >= 0` and `intraday <= -0.8%`
almost never coexist. The conjunction, not any single component, is the
bottleneck.

## 2. The repaired hypothesis

The core idea — participation tells us whether a decline is information —
is kept, but the close-location conjunction is relaxed from "upper half" to
"upper three-quarters of the range", and the volume threshold is relaxed from
1.5× to 1.3× the prior-20-session mean:

```
event = (rvol >= 1.3) AND (QQQ intraday <= -0.8%) AND (clv >= -0.5)
```

`clv >= -0.5` means the close is at least 25% of the range above the low, i.e.
the session did not close on its low. The economic claim is unchanged: a
well-above-normal-volume intraday decline that closes off the low has absorbed
the supply, and TQQQ rises over the next five sessions.

Execution (pre-registered primary, otherwise the same as the original):

1. On an event, buy 100% TQQQ at the next session's open.
2. Hold 5 sessions; exit at the following open.
3. Otherwise 100% BIL. Long-only, no stop, max 100% TQQQ.
4. Overlapping events extend the holding window exactly as in the original.

The relaxation is pre-registered as a **count fix**, not a return fit: the
original fired 3 times in 8 years, and the relaxed rule is the nearest
neighbour that produces a usable sample without changing the direction of the
close-location condition. The report must still show whether volume is doing
any work; a positive headline return with no volume attribution is not evidence
for this hypothesis.

## 3. Pre-registered grid (8 cells)

All cells use a 5-session hold at 100% size unless stated. Costs 1 bp for the
grid; the primary is also run at 5 bp and 10 bp.

| # | rvol min | clv min | hold | size | purpose |
|---:|---:|---:|---:|---:|---|
| 1 | 1.3 | -0.50 | 5 | 100% | **primary** |
| 2 | 1.2 | -0.50 | 5 | 100% | looser volume |
| 3 | 1.5 | -0.50 | 5 | 100% | original volume |
| 4 | 1.3 | -0.25 | 5 | 100% | stricter close |
| 5 | 1.3 | -0.75 | 5 | 100% | looser close |
| 6 | 1.3 | -0.50 | 3 | 100% | shorter hold |
| 7 | 1.3 | -0.50 | 10 | 100% | longer hold |
| 8 | 1.3 | -0.50 | 5 | 50% | half size |

## 4. Falsifiers

The repair is not accepted if any of these holds on the development window:

1. **Too thin:** fewer than 20 events.
2. **No forward edge:** mean 5-session TQQQ return after events ≤ 0, or t < 1.5.
3. **No volume attribution:** the high-volume bucket (`rvol >= 1.3`) is not
   better than the low-volume bucket (`rvol < 1.3`) inside the same
   `QQQ <= -0.8%` and `clv >= -0.5` filter. If volume does not add return,
   the participation-exhaustion mechanism is not supported and the strategy is
   retired as a participation strategy regardless of headline CAGR.
4. **No close-location attribution:** the result is not monotone/plateau in
   `clv`, or the `clv >= -0.5` cell is a single spike between two weak
   neighbours.
5. **One-episode wonder:** the 2020-21 sub-period carries the result while
   2016-19 and 2022-23 are both non-positive.
6. **No risk compensation:** 10 bp CAGR ≤ BIL's development CAGR.
7. **Placebo:** fewer than 95% of same-size random-event placebo runs have a
   lower CAGR than the real signal.

If (3) fails, the honest verdict is **retired as a participation strategy**,
even if (1), (2), (6), (7) pass. A generic down-day close-off-low reversal is a
different strategy and is not claimed here.

## 5. Data and alignment

- `research/bt.py` 1-minute panel, QQQ/TQQQ/BIL, 2016-01-04..2023-12-29.
- QQQ high/low/volume are aligned to the same QQQ-minute grid by
  `load_1m` + reindex, forward-fill prices, zero-fill volume.
- `rvol` uses only the prior 20 sessions (shifted mean). All features are known
  at the session's last bar.
- Event at session *d*'s close; weight is placed on the last bar of *d* and
  filled at the next session's open. Exit is placed on the last bar of
  *d+hold* and filled at the following open.
- Next-open fills, 2% band, 1/5/10 bp slippage, long-only, weights ≥0 and
  sum ≤1.
- No 2024-2026 data is requested, loaded into the analysis, or inspected.
