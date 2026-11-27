# Quiet oversold capitulation reversal — revisit

**Slug:** `gap-capitulation-reversal`
**Status:** pre-registered, **not yet run** (backtests paused).
**Original:** `research/agents2/gap-capitulation-reversal` — 165-day QQQ
regime + buy TQQQ at the next open after a QQQ gap-down.
**Dev window:** 2016-01-04 → 2023-12-29. **Holdout:** 2024-01-02 →
2026-10-23 (lead only; not inspected by this agent).

## 1. The idea, and what is genuinely new

The original strategy was an overlay: hold TQQQ while QQQ is above its 165-day
SMA, and buy TQQQ for one day after a QQQ gap-down. Its standalone version made
7.74%/21.22% (10y) and 7.95%/8.20% (5y) at 1 bp, and the base dominated it.

The rebuild keeps the research area — **capitulation reversals** — but changes
the claim and the position:

- **Old:** any large gap-down in a long-term bull regime is a 1-day buy.
- **New:** a large decline that occurs while QQQ is *already short-term
  oversold* and on *below-average volume* is a liquidity/positioning event, not
  an information event. It reverses over **three sessions**. A large decline on
  heavy volume is more likely to be information-driven and is not traded.

The event, its volume condition, its 3-session clock and its own stops own the
position. There is no 165-day (or any 100–250-day) moving-average gate and no
reuse of the old base weights. The 165-day baseline appears only in the
correlation/benchmark table.

## 2. Hypothesis (one sentence)

A QQQ close-to-close decline of at least 2% (or an intraday low at least 3%
below the prior close), on volume at most 1.2x the prior 20-day average, while
QQQ's 20-day return is at most -3%, is followed by a positive 3-session TQQQ
return large enough to beat BIL after 1/5/10 bp costs, with daily-return
correlation below 0.60 to the old 165-day baseline.

## 3. Universe and data constraints

- Tradable: **QQQ, TQQQ, BIL** 1-minute, regular session, `data/intraday-hf/`.
- The local SPY file is **daily only** and its `SOURCE.md` explicitly says it
  must not be used as a tradable asset in a rebuild (there is no SPY intraday
  history for 2016-2023). SPY is used only as a daily benchmark.
- No sector, bond, gold or volatility-product data is local. No new data was
  fetched because the test is paused; the strategy is deliberately built on
  the assets that exist.
- Signals use the event day's close and fill at the next session's open;
  stops use the current minute close and fill at the next minute open; the
  time exit sells at the 15:59 open of the third session.

## 4. Exact rules

```
For each session d (close known):
  qret = QQQ_close[d] / QQQ_close[d-1] - 1
  qdd  = QQQ_low[d]   / QQQ_close[d-1] - 1
  q20  = QQQ_close[d] / QQQ_close[d-20] - 1
  rvol = QQQ_volume[d] / mean(QQQ_volume[d-20 .. d-1])
  vol20 = annualised stdev(QQQ daily returns, last 20 sessions)

  event = (qret <= -2.0% OR qdd <= -3.0%)
          AND rvol <= 1.2
          AND q20 <= -3.0%

  if event:
      buy at next open, 100% of:
          TQQQ if vol20 <= 30%, else QQQ
      hold 3 sessions (entry session + 2)
      exit at the close of the 3rd session,
        OR at the next minute open if QQQ closes below the event-day low,
        OR at the next minute open if the held asset closes 8% below entry
      a new event during the hold restarts the 3-session clock and resets the
        asset, entry price and event-low stop
  else: BIL
```

- No regime exit; no 165-day MA; no old base weights.
- One position at a time; long-only; weights sum to <= 1.
- Base parameters: drop 2.0%, intraday 3.0%, rvol 1.2, oversold -3%, hold 3,
  vol cap 30%, hard stop 8%, event-low stop on.

## 5. Pre-registered evidence (exploratory, 2016-2023 only, before the pause)

These are raw TQQQ forward returns from the next open to the close of the
3rd/5th session. They are the reason for the design, not the final result.

| Event, dev 2016-2023 | n | 3-session mean | t | 5-session mean | t |
|---|---:|---:|---:|---:|---:|
| QQQ close <= -2% (all) | 136 | +1.16% | 1.66 | +1.57% | 1.62 |
| QQQ low <= -3% (all) | 94 | +1.11% | 1.24 | +2.16% | 1.81 |
| QQQ close <= -2% & rvol <= 1.2 | 43 | **+3.97%** | **2.97** | +4.36% | 2.28 |
| QQQ low <= -3% & rvol <= 1.2 | 28 | **+4.32%** | **2.95** | +6.06% | 2.64 |
| QQQ close <= -2% & rvol > 1.2 | 89 | +0.12% | 0.19 | +1.17% | 1.22 |
| QQQ low <= -3% & rvol > 1.2 | 62 | +0.31% | 0.31 | +1.84% | 1.44 |
| QQQ 20-day DD <= -8% & rvol <= 1.2 | 109 | +2.19% | 2.62 | +2.90% | 2.41 |
| QQQ close <= -2% & q20 <= -3% | 78 | +1.55% | 1.48 | +2.64% | 1.89 |
| QQQ low <= -3% & q20 <= -3% | 65 | +2.13% | 1.84 | +3.33% | 2.18 |

The volume split is the core empirical fact and also the most dangerous one:
the academic literature (Campbell-Grossman-Wang 1993; Conrad-Hameed-Niden 1994)
finds the **opposite** sign for individual stocks — high-volume declines are
the ones that reverse. The rebuild therefore treats the low-volume sign as a
falsifiable hypothesis, not a fact. If the quiet subset does not beat the
heavy subset in the final event study, the volume condition is dropped and the
strategy is re-specified or retired.

## 6. Results

**Not run yet.** The table is fixed before the authorised run.

| Window | Costs | CAGR | Max DD | Sharpe | Fills | Exposure | Corr vs 165d |
|---|---|---:|---:|---:|---:|---:|---:|
| dev 2016-2023 | 1 bp | TBD | TBD | TBD | TBD | TBD | TBD |
| dev 2016-2023 | 5 bp | TBD | TBD | TBD | TBD | TBD | — |
| dev 2016-2023 | 10 bp | TBD | TBD | TBD | TBD | TBD | — |
| 10y (overlap) | 1 bp | TBD | TBD | TBD | TBD | TBD | — |
| 5y (overlap) | 1 bp | TBD | TBD | TBD | TBD | TBD | — |
| holdout | 1 bp | lead only | lead only | lead only | lead only | lead only | — |

Expected shape: 30-50 events over 8 years, about 5-7% bar exposure, mid-single
digit CAGR before BIL carry, low-to-mid-teens drawdown, correlation with the
165-day baseline around 0.05-0.25. If so, the strategy is a low-CAGR
diversifier and may be retired by the lead; it is not a TQQQ competitor.

## 7. Overfitting controls (pre-registered)

- Variants tried: 23 (base + one-at-a-time neighbours + 7 ablations).
- Neighbourhood: drop 1.5/2.0/2.5%; intraday 2.5/3.0/3.5%; rvol 1.0/1.2/1.5;
  oversold 0/-3/-5%; hold 1/3/5; vol cap 25/30/35%; hard stop 6/8/10%;
  event-low stop on/off. Every row is reported.
- Sub-periods: 2016-2019, 2020-2021, 2022-2023.
- Placebo: random event days with the same count and hold, 1,000 draws;
  report the percentile of the real CAGR.
- Bootstrap: 10,000 resamples of the event 3-session returns; p-value for
  mean <= 0 (required because the event count is below 100).
- All parameters were fixed before the rebuild run; no post-hoc selection.

## 8. What would falsify it

1. The quiet event's 3-session mean is <= 0, or its bootstrap p-value is > 0.10.
2. The quiet subset does not beat the heavy-volume subset (`rvol > 1.2`) within
   the same oversold bucket; the volume condition is then dropped.
3. The edge is one episode: 2016-2019, 2020-2021 or 2022-2023 has a negative
   mean 3-session return, or 2020 accounts for more than half the P&L.
4. Dev CAGR < 3%, Sharpe < 0.30, or max drawdown > 25% at 1 bp.
5. Correlation with the 165-day baseline >= 0.60, or with another rebuild
   >= 0.70.
6. Removing the event-low or hard stop improves CAGR by more than 2 pp.
7. The placebo CAGR is inside the 90% band of the real strategy.
8. The 10 bp CAGR is below 2%, or the 5 bp/10 bp drawdown is more than 5 pp
   worse than the 1 bp drawdown.

## 9. Provenance

See `PROVENANCE.md` for the full table. The main sources are Cox & Peterson
(1994) on large-decline reversals; Campbell-Grossman-Wang (1993),
Conrad-Hameed-Niden (1994) and Llorente et al. (2002) on volume and reversal
(the first two are counter-evidence to the low-volume sign); Lou-Polk-Skouras
(2019) and Cliff-Cooper-Gulen (2008) on the overnight/next-open entry;
Moreira-Muir (2017) on volatility-managed sizing; Kaminski-Lo (2014) on stops;
and the local QQQ/TQQQ data and prior reports.

## 10. Files and next step

- `HYPOTHESIS.md` — idea, mechanism, falsifiers, pre-registered choices.
- `SPEC.md` — exact rules, parameters, timing, evaluation.
- `strategy.py` — `build_weights(...)` and `main()`; `main()` is not to be run
  until the lead/user authorises the test.
- `PROVENANCE.md` — source provenance and what each source supports.
- `result.json` — **not created yet** (backtests paused).

Next step: the lead authorises the dev run; `main()` produces `result.json`
with dev 1/5/10 bp metrics, the event study (quiet vs heavy vs no-volume), the
bootstrap p-value, and the 165-day correlation. The lead then runs the frozen
strategy on the 10y/5y (labelled overlap) and the holdout once.
