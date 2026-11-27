# Failed-breakdown spring — standalone revisit of `drawdown-stop-overlay`

**Status: SPEC / PAUSED. No `result.json` yet. Backtests are paused by the
user; this file is the hypothesis, spec, provenance and report skeleton.**

Agent: `drawdown-stop-overlay` (revisit)
Original: `research/agents/drawdown-stop-overlay`
Development window: **2016-01-04 → 2023-12-29** (holdout 2024-2026 untouched)

---

## 1. What was actually new in the original — and why stripping the base fails

The original strategy is the daily 165-day QQQ→TQQQ base plus an overlay:

1. Hold TQQQ while QQQ's close is above its 165-day SMA.
2. Exit intraday when QQQ trades through the exact 165-day SMA threshold
   `T_t = mean(C_{t-164..t-1})`, at `0.995 × T_t`.
3. After a stop, re-enter on the next regime cross, or on a new 10-day TQQQ
   high if the regime never went bearish.

The genuinely new part is the **exact threshold stop + 10-day-high re-entry**;
the position itself comes from the 165-day base. The corrected original result
is 10y 43.27% CAGR / 45.23% DD and 5y 29.46% / 42.96% — it cuts the baseline's
10y DD but does **not** beat the baseline's 10y CAGR (45.31%). It is a risk
overlay, not a standalone return source.

**Pre-pause exploratory evidence (dev 2016-2023, 1 bp, 1-minute marks).** I
already tested the two obvious "strip the base" rebuilds before the pause:
always-long TQQQ with a fixed-percentage peak stop, and always-long TQQQ with
an N-day exact SMA-threshold stop, both with the 10-day-high re-entry. These
are exploratory, not the final strategy, but they are the evidence that the
stop alone does not stand up:

| Standalone stop attempt | CAGR | Max DD | Sharpe | Corr vs 165d base |
|---|---:|---:|---:|---:|
| TQQQ buy & hold (dev) | 35.98% | 81.68% | 0.80 | — |
| QQQ buy & hold (dev) | 18.86% | 35.11% | 0.87 | — |
| 165-day baseline (dev, daily / 1m) | 43.63% / 43.62% | 58.71% / 59.64% | 1.01 | 1.00 |
| Peak stop 8% + 10-day high | 33.16% | 44.19% | 1.03 | 0.527 |
| Peak stop 10% + 10-day high | 33.56% | 47.62% | 0.99 | 0.563 |
| Peak stop 12% + 10-day high | 36.79% | 63.97% | 1.01 | **0.606** |
| Peak stop 15% + 10-day high | 25.82% | 71.42% | 0.76 | 0.616 |
| 10-day SMA threshold + 10-day high | 18.05% | 52.84% | 0.66 | 0.473 |
| 20-day SMA threshold + 10-day high | 31.72% | 55.53% | 0.91 | 0.544 |
| 30-day SMA threshold + 10-day high | 19.42% | 66.28% | 0.65 | 0.563 |

The pure stop is **not robust**:

- 8/10/15% peak stops have a lower CAGR than TQQQ buy-and-hold.
- 12% is the lone point that beats TQQQ on both axes, but its correlation
  (0.606) is above the 0.60 diversity limit and the neighbourhood is
  non-monotone (33.16, 33.56, 36.79, 25.82%).
- The 10/20/30-day SMA-threshold stops all have a lower CAGR than TQQQ; the
  20-day version is the best (31.72% / 55.53%) but still below TQQQ's 35.98%.
- No version is a complete, independent return source; they are all TQQQ
  risk overlays.

**Conclusion from the pre-pause work:** the original overlay is
`overlay-only`. The revisit must not be another stop on TQQQ; it needs a
different return driver. That is the failed-breakdown event below.

---

## 2. The standalone idea: failed-breakdown spring

**Hypothesis.** When QQQ undercuts its prior 20-session low intraday but closes
back above that low, the breakdown was a stop run / liquidity sweep: stop-loss
and breakout sellers were absorbed, and the forced selling is exhausted. The
next few days tend to rebound. A complete strategy can trade that event
directly, with no 165-day regime and no old base weights.

This is the *inverse* of the original stop overlay: the original sells when a
trend threshold breaks; this strategy buys when a support break **fails** and
reclaims. The return driver is short-horizon liquidity/mean reversion, not
slow trend following.

**Universe.** `QQQ` (signal), `TQQQ` (long execution), `BIL` (cash). This is
the only full-history 1-minute universe in the repo. `SPY` exists only as 60
daily `.bi5` files in `data/cache/dukascopy/SPY` (2026-08-31..2026-11-20), and
there is no local sector/bond/gold/vol history for 2016-2023. A broader
universe would need new data, which is out of scope while tests are paused.

**Signal (all at the 15:59 close, known before the next open):**

- `L20_t = min(QQQ low_{t-20..t-1})` — the prior 20-session low, excluding today.
- Breakdown: `QQQ low_t < L20_t`.
- Reclaim: `QQQ close_t > L20_t`.
- Confirmation: `(close_t - low_t) / (high_t - low_t) >= 0.50` — the close is in
  the upper half of the day's range. If `high == low`, no signal.
- Signal = breakdown & reclaim & confirmation. One position at a time; a signal
  while already long is ignored.

**Entry.** Buy 100% TQQQ at the next session's 09:30 open (the bar after the
15:59 signal). No same-bar fill.

**Holding period.** Maximum **5 trading sessions** (entry session through the
fifth session). Exit earlier on:

- **Recovery:** QQQ closes at or above its prior 10-day high
  (`max(QQQ close_{t-10..t-1})`), i.e. the breakdown is fully repaired; or
- **Hard stop:** TQQQ closes at or below `entry_price × (1 − 8%)`; or
- **Time:** the fifth session closes.

All exits are decided at the close and filled at the next open. The strategy
is in BIL when flat.

**Sizing and risk.** 100% TQQQ per event (headline); a 50% TQQQ / 50% BIL
variant is the sizing neighbour. No pyramiding, no shorts, no leverage beyond
TQQQ. The 8% close-based stop caps the per-event loss (with gap risk), and the
5-session time stop caps exposure.

**Costs/harness.** 1 bp headline, 5 bp and 10 bp sensitivity; 2% band;
1-minute equity marks; `bt.run_many` on the Rust `simcore`; next-open fills.
No holdout, no 10y/5y windows in this rebuild (they overlap 2024-2026; the lead
runs the frozen strategy on the holdout once).

---

## 3. Expected correlation vs the old 165-day base

**Expected: 0.20–0.45.** The old base is long TQQQ through slow uptrends and
out during 2018/2020/2022; this strategy is flat most of the time and long for
5 sessions after a failed breakdown. It often buys after declines, when the
base is out, which lowers correlation. The risk is that most failed breakdowns
occur during bull-market pullbacks when the base is long; in that case the
correlation could reach 0.50–0.60. The hard falsifier is **≥ 0.60**.

This is an estimate, not a measured number. It will be replaced by the dev
daily-return correlation when the test is authorised.

---

## 4. What would falsify the idea

1. **Too few events.** A 20-day low breach + reclaim + upper-half close may
   occur fewer than 100 times in 2016-2023. If so, the event study is
   underpowered; report the count and a bootstrap p-value. Fewer than ~30
   events would make the result anecdotal.
2. **No event edge.** Mean forward 1/3/5/10-day TQQQ return after signals is
   ≤ the unconditional same-horizon return, or ≤ 0, or the bootstrap p-value
   is > 0.10.
3. **No standalone performance.** Dev CAGR ≤ TQQQ buy-and-hold and max DD not
   lower; or Sharpe below the 165-day baseline; or the strategy loses money in
   two of the three sub-periods (2016-19, 2020-21, 2022-23).
4. **High correlation.** Daily-return correlation with the 165-day baseline
   ≥ 0.60.
5. **Event concentration.** Removing 2020 (or 2022) kills the edge; the result
   must not be a single-crash artefact.
6. **Placebo match.** A control that buys after any QQQ −1% day, or random
   entries with the same count/hold, matches or beats the failed-breakdown
   version. Then the 20-day-low reclaim adds nothing.
7. **Parameter instability.** The 10/20/30-day lookback or 3/5/10-session hold
   flips the sign or the neighbourhood is not a plateau.
8. **Costs.** 10 bp costs turn the edge negative (unlikely with low turnover,
   but must be checked).

If (1)-(4) fail, the original overlay is confirmed `overlay-only` and the
rebuild is `rejected`. If the event edge is real but the TQQQ implementation
does not beat TQQQ buy-and-hold, the honest status is still `rejected` as a
standalone strategy, with the event study documented.

---

## 5. Planned tests and overfitting controls (when authorised)

- **Variants:** primary 20-day lookback / 5-session hold / 8% stop / 0.50 range
  / 100% size; one-at-a-time neighbours 10 and 30 days, 3 and 10 sessions, 6%
  and 10% stops, 0.40 and 0.60 range, 50% size. `variants_tried = 11`.
- **Sub-periods:** 2016-2019, 2020-2021, 2022-2023.
- **Event study:** signal count, mean forward 1/3/5/10-day TQQQ returns vs
  unconditional, and a bootstrap p-value (the event count is likely <100).
- **Placebo/control:** buy after any QQQ close-to-close day ≤ −1% with the same
  hold/exit rules; optionally random entries with the same count and hold.
- **Costs:** 1 bp, 5 bp, 10 bp.
- **Benchmarks:** TQQQ, QQQ, 165-day baseline, original `result.json`.
  SPY is unavailable for 2016-2023 (only 60 days in 2026), so it is `null`.
- **No holdout / no 10y / no 5y** in the rebuild; the lead runs the frozen
  strategy on the holdout once after audit.
- **Audit:** look-ahead cuts at 2020-03-12 11:07, 2022-09-13 10:41 and
  2022-06-30; spec-vs-code; clean reproduction; correlation recomputation.

---

## 6. Provenance

### The original idea / starting point

- `research/agents/drawdown-stop-overlay/report.md` and `result.json` — the
  corrected 165-day-threshold stop + 10-day-high re-entry, 10y 43.27% / 45.23%,
  5y 29.46% / 42.96%. Used only as the starting point and as a benchmark; no
  code or weights are reused.
- FinLab, *TQQQ 200-Day Moving Average Strategy: 7 Leveraged ETF Rules*
  (2026-10): <https://finlab.finance/en/blog/leveraged-etf-timing-backtest>.
  The old base's whipsaw diagnosis; not used in the new signal.
- Faber (2007), *A Quantitative Approach to Tactical Asset Allocation*:
  <https://papers.ssrn.com/sol3/papers.cfm?abstract_id=962461>. The old base's
  10-month SMA; not used in the new signal.

### The failed-breakdown / spring effect

- Richard D. Wyckoff, *The Richard D. Wyckoff Method of Trading and Investing
  in Stocks* (1931) — the "spring": a false breakdown below support that
  reclaims the range, trapping sellers. Secondary explanation:
  <https://chartschool.stockcharts.com/table-of-contents/market-analysis/wyckoff-analysis-articles/wyckoff-market-analysis>.
- Wyckoff Stock Market Institute, *Test of Springs*:
  <https://wyckoffsmi.com/test-of-springs>. A failed test / spring is the
  pattern the signal is built around.
- StratMill, *Liquidity-Sweep Failed-Breakout Reversal*:
  <https://stratmill.com/research/en/strategies/d0368560-059a-4ebf-b102-ad73818434c7>.
  Practitioner description of the exact pattern (wick beyond a 20-bar extreme,
  close back inside); low-confidence, not an academic result.
- Journali, *Failed Breakout / Breakdown Trading Strategy*:
  <https://journali.io/strategies/failed-breakout>. Practitioner review of the
  pattern's context (range-bound/post-news conditions); low confidence.
- International Trading Institute, *After the Liquidity Sweep*:
  <https://internationaltradinginstitute.com/blog/after-the-liquidity-sweep-confirm-reversal-continuation-or-no-trade>.
  Notes that many sweeps continue rather than reverse; this is exactly why the
  close confirmation and the falsifiers are needed.

### Why a stop is not a standalone edge

- Kaminski & Lo (2014), *When do stop-loss rules stop losses?*, Journal of
  Financial Markets 18, 234-254:
  <https://www.sciencedirect.com/science/article/pii/S138641811300030X>.
  Stop-loss rules add value only in non-random-walk / momentum regimes; in a
  random walk they do not. This is the theoretical reason the original stop
  could only be an overlay on a trend base.
- Lo & Remorov (2017), *Stop-loss strategies with serially correlated
  returns* — extends the above; cited via the Kaminski-Lo line of work. Not
  used directly.

### Short-horizon reversal / liquidity provision

- Nagel (2012), *Evaporating Liquidity*, Review of Financial Studies 25(7),
  2005-2039: <https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1988706>.
  Short-term reversal returns can be interpreted as compensation for liquidity
  provision; expected reversal returns are time-varying with VIX. This supports
  the "forced selling then rebound" mechanism and warns that the edge is
  regime-dependent.
- Campbell, Grossman & Wang (1993), *Trading Volume and Serial Correlation in
  Stock Returns*, Quarterly Journal of Economics 108(4), 905-939:
  <https://doi.org/10.2307/2118454>. Price pressure from non-informational
  selling is followed by reversal; the basis for buying a forced-seller
  breakdown.
- Brunnermeier & Pedersen (2009), *Market Liquidity and Funding Liquidity*,
  Review of Financial Studies 22(6), 2201-2238:
  <https://doi.org/10.1093/rfs/hhn098>. Liquidity spirals and forced selling;
  the mechanism behind stop cascades.

### Own test / no external source

- The exact 20-session lookback, 5-session hold, 8% stop, 0.50 range
  confirmation and 100% size are own choices, tested only in the pre-pause
  exploratory work and to be re-tested as the new strategy. No external source
  specifies these values.
- `research/revisit/BRIEF.md` — the revisit rules (dev window, no shared base,
  correlation thresholds, minute marks, costs, overfitting controls).

---

## 7. Status and next step

- **Current status:** SPEC / PAUSED. `strategy.py` is complete; `result.json`
  has not been generated. No backtest was run after the pause.
- **When authorised:** run `strategy.py` on dev only, then audit look-ahead,
  spec-vs-code, reproduction, harness, correlation and the event study. If it
  passes, the lead runs the frozen strategy on the 2024-2026 holdout once.
- **If it fails the event study or the TQQQ comparison:** mark the original
  overlay `overlay-only` (the pre-pause evidence already points there) and mark
  this rebuild `rejected`; do not force it.
