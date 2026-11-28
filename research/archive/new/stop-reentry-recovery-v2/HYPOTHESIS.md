# HYPOTHESIS — stop-reentry-recovery-v2 (LETF overshoot recovery)

**Status:** pre-registered before the confirmatory grid. Development window only:
2016-01-04 → 2023-12-29. The 2024-2026 holdout is outside the panel and is not inspected.
**Original:** `research/revisit/stop-reentry-recovery/`
**New code:** `strategy.py` in this directory.

---

## 1. Why the original barely traded

The original signal was

```
r_t    = TQQQ_close[d] / TQQQ_open[d] - 1
r_q    = QQQ_close[d]  / QQQ_open[d]  - 1
signal = (r_t <= -3%) AND (r_t - 3*r_q <= -1pp)
```

Development-window component counts (2012 sessions):

| Component | Days |
|---|---:|
| `r_t <= -3%` | 282 |
| `r_t - 3*r_q <= -1pp` | 3 |
| both | **1** |

The intraday tracking residual `r_t - 3*r_q` has a standard deviation of only
**0.121 pp**. A 1 pp underperformance is therefore about **8.3 standard
deviations** — not a tradeable filter, a data-availability accident. The single
event was 2020-03-12; the 2020-03-13 entry was stopped the same session. Five
fills in eight years is the entire sample.

The relative-excess condition is also not supported by forward returns. On the
three days with `r_t - 3*r_q <= -1pp`, the forward TQQQ excess return (subtract
3× QQQ) is negative over 1, 3 and 5 sessions. Conditioning a dip-buy on a large
negative tracking residual makes the forward return *worse*, not better. The
idea that the relative tracking-error overshoot reverses is falsified in this
sample.

## 2. The repaired hypothesis

A large TQQQ down day that is unusually large **relative to TQQQ's own recent
volatility** is a forced-selling / short-term-liquidity overshoot. The next
session tends to reverse. The relevant normalization is the one that is
actually measurable: the drop's z-score against its trailing 20-session
standard deviation, not the tiny QQQ tracking residual.

Primary signal at the close of session *d* (all inputs known at that close):

```
r_t   = TQQQ_close[d] / TQQQ_open[d] - 1
sd20  = std(r_t[d-20 .. d-1])                  # prior 20 sessions, shifted
z     = r_t / max(sd20, 0.5pp)                 # 0.5pp floor for quiet periods
event = (r_t <= -5.0%) AND (z <= -2.0)
```

Economic claim: the event is a volatility-normalized downside overshoot; the
next session's open-to-close TQQQ return is positive on average. This is a
narrower claim than the original relative-overshoot story, and the report says
so: the original *relative-to-QQQ* mechanism did not survive diagnosis.

Execution (pre-registered primary):

1. Enter 100% TQQQ at the next session's 09:31 open (weight set at the 09:30
   close, filled at 09:31 under `research/bt.py`).
2. Exit at the same session's 15:59 open (sell at the close). One-session hold.
3. No stop: a stop cannot act before a one-session clock exit. The original
   2% minute-close stop is retained only in the structural comparison; it is
   far too tight for a multi-day hold (TQQQ intraday σ ≈ 2.5%, so 2% is less
   than one sigma).
4. Otherwise 100% BIL. Long-only, one position at a time, max 100% TQQQ.

Why one session instead of the original three: the event study shows the
reversal is concentrated in the first session. Correctly aligned mean returns
from the next open are +1.98% (h1), +2.62% (h3) and +5.15% (h5) for the primary
5%/2σ signal; the per-session return and the risk-adjusted result are best at
h1. The original 3-session 50%→100% scale-in with a 4% daily-close stop is
retained as a grid cell, so the comparison is explicit rather than assumed.
(The old 2% minute-close stop is not used: it is less than one daily sigma and
stops out a large fraction of the repaired sample.)

## 3. Pre-registered grid (8 cells)

All cells use the same one-session execution unless stated. Costs 1 bp for the
grid; the primary is also run at 5 bp and 10 bp.

| # | drop | z max | hold | size | stop | purpose |
|---:|---:|---:|---:|---:|---:|---|
| 1 | 5.0% | -2.00 | 1 | 100% | none | **primary** |
| 2 | 4.0% | -2.00 | 1 | 100% | none | smaller drop |
| 3 | 4.5% | -2.00 | 1 | 100% | none | drop neighbour |
| 4 | 6.0% | -2.00 | 1 | 100% | none | larger drop |
| 5 | 5.0% | -1.75 | 1 | 100% | none | looser z |
| 6 | 5.0% | -2.25 | 1 | 100% | none | tighter z |
| 7 | 5.0% | -2.00 | 1 | 50% | none | half size |
| 8 | 5.0% | -2.00 | 3 | 50%→100% | 4% daily close | original structure |

Cell 8 is the closest reconstruction of the old scale-in/stop design: 50% first
tranche, add the second 50% if the entry session closes above its open, a 4%
daily-close stop, and a 3-session hold. (The old 2% minute-close stop is not
used because it stops out a large fraction of the repaired sample.)

## 4. Falsifiers

The repair is not accepted if any of these holds on the development window:

1. **Too thin again:** fewer than 20 entries.
2. **No forward edge:** h1 event mean ≤ 0, or one-sided bootstrap p > 0.10.
3. **One-episode wonder:** mean h1 return excluding the five best events ≤ 0,
   or two of the three sub-periods (2016-19, 2020-21, 2022-23) have negative
   CAGR.
4. **No risk compensation:** 10 bp CAGR ≤ BIL's development CAGR.
5. **Cost fragility:** the sign of the 10 bp CAGR is negative, or the 10 bp
   CAGR is less than half the 1 bp CAGR.
6. **Not a plateau:** the sign of the CAGR flips inside the drop/z grid, or the
   primary is the only profitable cell.
7. **Placebo:** fewer than 95% of same-size random-event placebo runs have a
   lower CAGR than the real signal.

If 1-7 pass, the signal repair is honest but the strategy remains a
low-exposure event strategy; the report must state the low exposure and the
top-event concentration rather than present the CAGR as a broad equity beta.

## 5. Data and alignment

- `research/bt.py` 1-minute panel, QQQ/TQQQ/BIL, 2016-01-04..2023-12-29.
- Next-open fills, 2% band, 1/5/10 bp slippage, long-only, weights ≥0 and sum ≤1.
- Signal is computed from session *d*'s open and close and placed on the last
  bar of *d*; the fill is the next bar (09:31 of *d+1*). The exit is placed on
  the 15:58 bar, filled at the 15:59 open.
- No 2024-2026 data is requested, loaded into the analysis, or inspected.
