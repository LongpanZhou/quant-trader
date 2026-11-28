# Failed gap-up fade, repaired — `gap-fill-fade-v2`

**Status:** pre-registered development test. Window **2016-01-04 .. 2023-12-29**
only. The 2024-2026 holdout has not been loaded or inspected.
**Original:** `research/revisit/gap-fill-fade` (rebuild of
`research/agents2/gap-fill-fade`).
**Direction:** **short QQQ** on event days; BIL otherwise; flat overnight.
**Harness:** `research/bt.py`, 1-minute marks, next-open fills, 2% band,
long-only engine with a synthetic inverse asset for the short, 1 bp headline
with 5/10 bp sensitivity.

---

## 1. What the old rebuild did, and why it was economically tiny

The old rebuild shorts QQQ only when a small gap-up (+0.10% to +0.75%) occurs
in a weak, stressed tape, the first 30 minutes confirm the failure (QQQ below
the open and negative on the day), and price is still above the prior close at
10:00. It enters at 10:01, targets the prior close (full gap fill), stops at
the opening-range high (0.2-1.5% above entry), times out at 11:30, and sizes at
`clip(10% / 20-day vol, 10%, 100%)`.

The dev result was **25 events / 101 fills, +1.43% CAGR, 0.48% max DD, 0.94
Sharpe at 1 bp** and +0.80% CAGR at 10 bp. The average short notional was only
about **0.04% of equity** across all minutes (about 0.45x on the 25 event
days), and the strategy was in the market for roughly **0.05% of minutes**.

### 1.1 The 1.43% was BIL carry, not short alpha

Running 100% BIL over the same window returns **+1.39% CAGR**. The old
strategy's short overlay contributed roughly **+0.04%/yr** before costs. The
headline CAGR is almost entirely the T-bill yield on the idle cash.

### 1.2 The event edge was not significant

The old event study reported 25 events, mean **+0.056%** gross per event,
t = 1.01, bootstrap p = 0.15, 76% win rate. The 95% bootstrap interval
included zero. The "confirmation" filter selected the 25 events with the
smallest remaining gap; the first 30 minutes had already absorbed most of the
move.

### 1.3 Raw gap-fade diagnostics (all sessions, 2016-2023)

Short QQQ from the 09:31 open to the close, by gap bucket and tape:

| gap bucket | n | weak+stress short return 09:31→close | t |
|---|---:|---:|---:|
| +0.10-0.25% | 17 | -0.00% | -0.03 |
| +0.20-0.45% | 43 | +0.13% | 1.89 |
| +0.25-0.50% | 38 | +0.18% | 2.42 |
| +0.30-0.55% | 37 | +0.11% | 1.24 |
| +0.35-0.60% | 39 | +0.13% | 1.17 |
| +0.20-0.60% | 66 | +0.09% | 1.26 |
| +0.10-0.75% | 95 | +0.05% | 0.68 |

The low end of the old band is negative; the positive region is about
**0.20-0.60%**. The old 10:00 confirmation is a late, adverse-selection filter:
it keeps the events where the first 30 minutes have already moved, which is
exactly where the remaining target is smallest.

---

## 2. Repair hypothesis

Keep the mechanism — fade a small gap-up in a weak, stressed tape — and change
the implementation:

1. **Drop the 10:00 confirmation.** Enter at the **09:31 open**, one minute
   after the gap is known. The gap and the tape filters are known before the
   open; no future information is used. Skipping the 30-minute wait keeps the
   part of the gap-fill that is still there.
2. **Tighten the gap band to +0.20% to +0.60%.** The old 0.10-0.75% band mixes
   a negative low bucket with a weak high bucket. The 0.20-0.60% region is the
   positive plateau; +0.25-0.50% is the in-sample peak.
3. **Size larger.** Use a fixed **2x short QQQ notional** on event days via
   short TQQQ (0.667 weight of the 3x inverse), instead of a 10% vol target
   that leaves the short at ~0.45x. The rest is BIL.
4. **Keep the risk controls.** Stop at +1.5% on QQQ (a 4.5% loss on the 3x
   inverse at 0.667 weight), target the prior close, time exit at 15:58 so the
   position is flat overnight. One short at a time.
5. **Report the short clearly.** Direction: short QQQ. Size: 2.0x gross short
   notional on event days, 0.667 weight in the synthetic inverse TQQQ asset;
   average across all minutes is under 1% of equity because the strategy is
   flat most of the time. Borrow is charged at 0.5%/yr, prorated to the
   intraday holding period.

The 1x QQQ-inverse version is the size neighbour; the 3x TQQQ-inverse version
is the aggressive neighbour. The original is the direct comparison.

---

## 3. What would falsify the repair

1. **No event edge.** The repaired event mean is ≤ 0 after 1 bp, t < 1.5, or
   the bootstrap 95% interval includes zero.
2. **No economic size.** 5 bp CAGR is below the BIL-only CAGR, or 10 bp CAGR is
   below BIL. The repair must beat the old +1.39% BIL carry, not just the old
   headline.
3. **No plateau.** The 0.25-0.50% cell is positive only because of one gap
   bucket; the 0.20-0.45/0.30-0.55/0.35-0.60 neighbours are negative.
4. **Sub-period concentration.** The result is positive only in 2020, or only
   in 2018/2022, and vanishes in the rest.
5. **Confirmation helps.** If the 10:00-confirmed version at the same size
   beats the 09:31 version, the original confirmation was not the problem.
6. **Costs.** 10 bp costs turn the CAGR below BIL.
7. **Correlation.** Daily correlation with the 165-day base ≥ 0.60 (very
   unlikely for a short, but must be checked).

If (1) or (2) fails, the idea is retired. If the edge is real but only at 1 bp
and in one band, it is a research candidate, not a promoted satellite.

---

## 4. Pre-registered grid (8 variants, one at a time)

All variants: QQQ signal; weak tape = prior close < 10-day SMA and prior 5-day
return < 0; stress = 20-day realised vol > trailing 1-year median; target =
prior close; borrow 0.5%/yr; flat overnight; one short at a time.

| # | name | gap band | confirmation | entry | size / asset | stop | time |
|---|---|---|---:|---|---:|---|---:|
| 1 | `orig` | 0.10-0.75% | 10:00 r30<0 | 10:01 | 10% vol target / QQQ inv | OR high | 11:30 |
| 2 | `orig_size1` | 0.10-0.75% | 10:00 r30<0 | 10:01 | 1.0x / QQQ inv | OR high | 11:30 |
| 3 | `all_nc_1x` | 0.10-0.75% | none | 09:31 | 1.0x / QQQ inv | 1.5% | 15:58 |
| 4 | `b20_60_1x` | 0.20-0.60% | none | 09:31 | 1.0x / QQQ inv | 1.5% | 15:58 |
| 5 | `b20_60_2x` | 0.20-0.60% | none | 09:31 | 0.667 / TQQQ inv (2x) | 1.5% | 15:58 |
| 6 | `b20_60_3x` | 0.20-0.60% | none | 09:31 | 1.0x / TQQQ inv (3x) | 1.5% | 15:58 |
| 7 | **`b25_50_2x`** | **0.25-0.50%** | **none** | **09:31** | **0.667 / TQQQ inv (2x)** | **1.5%** | **15:58** |
| 8 | `b20_60_conf_2x` | 0.20-0.60% | 10:00 r30<0 | 10:01 | 0.667 / TQQQ inv (2x) | OR high | 11:30 |

`variants_tried = 8`. The primary is #7. #3-#6 are the size/band/plateau
neighbours; #8 is the confirmation control; #1-#2 are the old rebuild.

The plateau is read across the gap band (0.20-0.45, 0.25-0.50, 0.30-0.55,
0.35-0.60, 0.20-0.60) and across size (1x, 2x, 3x). No holdout, no 10y/5y.

---

## 5. Rules and accounting

- **Gap:** `QQQ open / prior close - 1` in the band, known at 09:30.
- **Weak tape:** prior close < 10-day SMA and prior 5-day return < 0.
- **Stress:** prior 20-day realised vol > trailing 1-year median.
- **Entry:** short QQQ at the 09:31 open (variant #1/#2/#8: 10:01 open).
- **Exit:** target prior close, stop at +1.5% (variant #1/#2/#8: OR high,
  floored at +0.2%, capped at +1.5%), time at 15:58 (variant #1/#2/#8: 11:30).
  All fills are next-open 1-minute fills; the 15:58 time exit fills at the
  15:59 open and is flat overnight.
- **Sizing:** fixed short notional. The 2x version holds 0.667 of the synthetic
  inverse TQQQ asset and 0.333 BIL; this is 2.0x gross short QQQ on event days.
- **Borrow:** 0.5%/yr on the short notional, prorated per minute.
- **Costs:** 1 bp headline; 5 and 10 bp reported for every variant.

---

## 6. Expected result (stated before the confirmatory run)

The repair should lift the event count from ~25 to ~35-65, raise the average
short notional from ~0.04% to ~0.4-1.0% of equity, and produce a **positive
CAGR above the 1.39% BIL carry** at 1 bp with a Sharpe around 0.8-1.2 and a
drawdown under 8%. The honest bar is not the old 1.43% headline; it is BIL
plus a positive, cost-robust short alpha. If the 10 bp CAGR is below 1.39%,
the repair is a research candidate only.
