> **Post-test note (2026-11-27):** this file is the pre-registration, not
> the result. The frozen development result is in `../SUMMARY.md`; the
> full 2016-2026 audit, the post-tune variants and the research-validity
> verdicts are in `../WHY_UNDERPERFORM.md`. The published website curve is
> the freeze named in `../SUMMARY.md`.

# Revisit: stop-reentry-recovery → leveraged-ETF overshoot recovery

**Status:** `pre_registered` — backtests are paused by the user; no `result.json` yet.
**Development period:** 2016-01-04 → 2023-12-29. **Holdout 2024-2026 not inspected.**
**Original:** `research/agents2/stop-reentry-recovery/` (round-1 winner + gradual
re-entry overlay).

---

## 1. What the original strategy actually was

The original is a re-entry overlay, not a standalone strategy. Its base is the
shared 165-day QQQ SMA regime (TQQQ when QQQ's prior close is above the SMA,
BIL otherwise) plus the round-1 armed 4% TQQQ stop. The genuinely new part is
only what happens *after* the stop:

- if the stopped session closed above its stop level, re-enter 100% next
  session with a 2% stop;
- if it closed below, re-enter 50% and hold that half through the session and
  night, restoring 100% after a clean session.

That overlay improved the shared base (61.03%/39.92% 10y, 51.57%/29.96% 5y at
1 bp on the original 2017–2026 sample), but it is still an overlay: it decides
nothing about when to be in TQQQ in the first place.

## 2. Why stripping the base is not enough (pre-pause screen, dev only)

Before the pause I ran a quick development-only screen of the obvious
"stripped-base" candidates. The results are the evidence for changing direction
rather than just deleting the 165-day gate.

| Stripped-base candidate | Dev CAGR | Dev max DD | Corr vs 165d baseline |
|---|---:|---:|---:|
| 165d baseline (benchmark) | 44.76% | 58.76% | 1.00 |
| Always long TQQQ + 4% stop + gradual re-entry | 58.71% | 62.24% | **0.68** |
| Always long TQQQ + 4% stop (no re-entry) | 57.20% | 60.22% | **0.67** |
| TQQQ > 20d MA + 4% stop + re-entry | 36.68% | 41.76% | 0.55 |
| TQQQ > 20d MA + 4% stop | 40.80% | 37.74% | 0.54 |
| TQQQ > 50d MA + 4% stop | 43.70% | 38.02% | 0.63 |
| Buy 4% TQQQ down days, hold 5d, QQQ > 20d MA filter | 6.51% | 17.32% | 0.20 |
| Buy 4% TQQQ down days, hold 1d, QQQ > 20d MA filter | 0.58% | 14.41% | 0.09 |

The pattern is clear: a stripped trend base keeps the old equity beta
(correlation 0.54–0.68), while a pure dip-buy is genuinely uncorrelated but
does not earn enough to be a strategy. **The re-entry rule by itself is not a
standalone edge.** A new return driver is required.

These numbers are a single pre-pause dev screen (one run, no parameter search
beyond a small grid); they are not the new strategy's results and must not be
quoted as such.

## 3. New idea: post-overshoot recovery in a 3× ETF

The economic effect behind the old stop is not "TQQQ fell 4%"; it is that a
leveraged ETF can **overshoot its underlying** when it is forced to rebalance.
A 3× fund must reset its swap exposure every day. After a large down day its
exposure is too high relative to the new NAV, so it sells into the close; the
mechanical selling can push the fund below 3× the underlying move, and that
temporary pressure can reverse over the next 1–3 sessions. The trade is to buy
the overshoot, not to buy every dip.

This is a complete strategy with its own signal, holding period, sizing and
risk — not the old 165-day base with the stop removed.

### Hypothesis

> When TQQQ falls at least 3% from its session open and underperforms 3× QQQ's
> same-session move by at least 1 percentage point, the underperformance is
> partly a leveraged-ETF rebalancing overshoot. Buying TQQQ at the next open,
> 50% first and 100% only after a recovery close, with a 2% stop and a
> three-session hold, captures the reversal with low correlation to the slow
> 165-day trend base.

The "50% then 100%" rule is the part inherited from the stop-re-entry idea: it
is a *scale-in on confirmation*, not a binary all-in. The 2% stop is the
tighter risk control from the original.

## 4. Universe and data

- **Hold:** TQQQ (long), BIL (cash). **Signal only:** QQQ.
- Data: local adjusted 1-minute QQQ/TQQQ/BIL under `data/intraday-hf/`,
  2016-01-04 → 2023-12-29 for development. No new downloads.
- One position at a time, long-only, max 100% TQQQ, no leverage beyond the ETF,
  no shorts. BIL earns its carry while flat.
- The strategy does **not** use QQQ/TQQQ/SPY/NDX against any 100–250-day moving
  average, and does not call or copy the old base weights.

## 5. Signal

For each session *d* (09:30–15:59 ET), using only that session's open and close:

```
r_t   = TQQQ_close[d] / TQQQ_open[d] - 1
r_q   = QQQ_close[d]  / QQQ_open[d]  - 1
excess = r_t - 3 * r_q

overshoot[d] = (r_t <= -0.03) and (excess <= -0.01)
```

- The `-3%` floor keeps ordinary noisy days out; the `-1 pp` excess is the
  actual overshoot condition (TQQQ fell at least 1 pp more than 3× QQQ).
- Primary thresholds: drop 3.0%, excess 1.0 pp. Neighbourhood: 2.5/3.5% drop,
  0.75/1.25 pp excess.
- Robustness alternative: compute the same excess on close-to-close returns
  (`TQQQ_close[d]/TQQQ_close[d-1] - 1` minus 3× the QQQ analogue), which
  captures the full-day rebalancing signal including the overnight gap. The
  intraday version is primary because it matches the session-open reference of
  the original stop and the into-the-close rebalancing pressure.
- No signal is taken while a position or its holding period is active.

## 6. Position, sizing, holding period, risk

1. **Entry.** At the next session *d+1*, buy 50% TQQQ at the 09:31 open (weight
   set at the 09:30 close, filled at 09:31).
2. **Add-on.** If the entry session closes above its own open (a recovery
   session), add the remaining 50% at the next session's 09:31 (*d+2*), reaching
   100%. If the entry session closes at or below its open, keep 50% for the rest
   of the holding period; do not add.
3. **Exit.** Hold three sessions (*d+1*, *d+2*, *d+3*). Exit at the close of
   *d+3* (sell at the 15:59 open).
4. **Stop.** 2% from the initial entry price (the 09:31 open of *d+1*). If any
   close from the entry session onward is below `entry_px × 0.98`, sell at the
   next bar's open and stay BIL for the rest of the holding period. The stop is
   checked from the first entry bar's close. If the add-on is at a different
   price, the stop stays anchored to the initial entry price (conservative when
   the add-on is higher, tighter when lower).
5. **No re-entry after a stop.** A stopped event is finished; the next event
   needs a new overshoot signal.
6. **Size cap.** 50% then 100% of equity; BIL for the remainder. No pyramiding
   beyond 100%.

Neighbourhood tested after authorization: hold 1/3/5 sessions, stop 1.5/2.0/
2.5%, initial size 0/50%, add-on rule on/off, gap-cancel on/off.

## 7. Expected correlation and hard bars

- **Expected daily-return correlation vs the 165-day baseline: 0.3–0.5.**
  The strategy is in BIL most sessions and long TQQQ only in short
  post-overshoot windows, so it should not inherit the slow trend beta. The hard
  bar is **< 0.60** on the development period.
- If the correlation lands at 0.55–0.60, the close-to-close signal variant is the
  fallback; if it is ≥ 0.60, the strategy is not distinct enough and will be
  re-specified or retired.
- **Max correlation vs other rebuilds < 0.70.** This cannot be computed until
  the other rebuilds exist; the lead must recompute it. The closest existing
  ideas are `ratio-pairs` (slow TQQQ/QQQ ratio froth) and
  `letf-rebalance-flow` (late-day flow overlay); this strategy is a short-horizon
  *downside* overshoot recovery, not a slow ratio or a late-day entry.
- Benchmark bars: beat BIL (~1.4% dev CAGR) and do not exceed the 165-day
  baseline's dev max drawdown (58.76%). A strategy that cannot clear BIL is not
  a strategy.

## 8. Falsifiers — what would prove it wrong

The idea is falsified if any of these holds on the development period:

1. **No forward edge:** mean three-session return after an overshoot, measured
   from the 09:31 entry fill to the exit, is ≤ 0; or the hit rate is below 50%
   with no positive tail.
2. **No risk compensation:** dev CAGR ≤ BIL's ~1.4%, or dev max drawdown ≥ the
   165-day baseline's 58.76%.
3. **Still the old beta:** daily-return correlation with the 165-day baseline
   ≥ 0.60.
4. **One-episode wonder:** 2016–19 and 2021–23 both have non-positive CAGR, or
   removing the top three events kills the edge (the result is March 2020 only).
5. **No plateau:** a ±1-step change in drop or excess flips the sign of the
   CAGR, or cuts it by more than half. A single best grid point is not a
   strategy.
6. **Not enough evidence:** fewer than 100 events and a bootstrap p-value
   > 0.10 on the event returns.
7. **The scale-in is not additive:** 100% entry with a 4% stop matches or beats
   the 50%→100% / 2% version on CAGR and drawdown, meaning the "gradual
   re-entry" component is decoration.
8. **The add-on is the whole edge:** the 50%-only version has the same return
   with lower risk, so the second 50% is not justified.

## 9. Test plan (dev only; paused until authorized)

- Dev window 2016-01-04 → 2023-12-29, 1-minute marks, next-open fills, 2% band,
  1 bp headline plus 5 bp and 10 bp.
- Sub-periods: 2016–19, 2020–21, 2022–23.
- Parameter neighbourhood: drop 2.5/3.0/3.5%, excess 0.75/1.0/1.25 pp, hold
  1/3/5 sessions, stop 1.5/2.0/2.5%, size 0/50/100%, add-on on/off.
- Placebo: 1,000 random samples of the same number of sessions (or shuffled
  overshoot labels) with the same holding/stop rules; report the placebo CAGR
  distribution and the percentile of the real strategy.
- Event count and block-bootstrap p-value for the event returns. The relevant
  count is **actual entries**, not raw signals: a signal that arrives while a
  position or its holding period is active is ignored. Use
  `info["entries"]` / `info["entry_dates"]` from `strategy.py`.
- Correlations: vs the 165-day baseline and vs any other rebuilds present.
- Do **not** run or inspect the holdout. The lead runs the frozen strategy on
  2024-2026 exactly once.

## 10. Provenance

### Inspired the rule

- **Strasmore, "Leveraged ETF Rebalancing Into the Close."** Explains the daily
  rebalance: a 3× long fund trades six times the underlying move, buying after
  up days and selling after down days, with the flow concentrated into the
  close. This is the mechanism behind the downside overshoot and the next-day
  reversal. <https://strasmore.com/blog/leveraged-etf-rebalancing-and-the-close>
- **Shum, Hejazi, Haryanto & Rodier, "Intraday Share Price Volatility and
  Leveraged ETF Rebalancing."** Finds larger tracking errors in volatile
  periods, consistent with rebalancing costs. Used to justify measuring the
  *relative* TQQQ/QQQ excess rather than TQQQ's raw drop.
  <https://papers.ssrn.com/sol3/Delivery.cfm?abstractid=2161057&mirid=1>
- **Avellaneda & Zhang (2010), "Path-Dependence of Leveraged ETF Returns."**
  Gives the path-dependence/decay formula for leveraged ETFs; the ratio is a
  decay meter, not a pure beta. Used as background for why the 3× fund can
  deviate from 3× the underlying.
  <https://epubs.siam.org/doi/10.1137/090760805>
  <https://math.nyu.edu/inmemoriam/avellaneda/LETFRISKPROF.pdf>
- **"Preying on Leveraged ETFs" (arXiv 2608.03703).** Models the mandated daily
  rebalance as upward-sloping demand at the close and shows arbitrageurs
  pre-position around it. Supporting evidence for the close/reversal mechanism;
  the paper studies the Korean market, so confidence is medium.
  <https://arxiv.org/html/2608.03703v3>
- **Own round-1 event study (local).** After the old 4% stop, the next session's
  open→close return was +0.726% after a weak close and +0.481% after a recovered
  close (160 events, 2016–2026). This is the seed for the recovery hypothesis,
  but the new strategy uses a different, relative-overshoot signal.
  `research/agents2/stop-reentry-recovery/report.md` and `explore3.py`.

### Tested and rejected (do not reuse)

- **The old 165-day base + gradual re-entry overlay.** It works as an overlay
  (61.03%/39.92% 10y, 51.57%/29.96% 5y on the original sample) but is not a
  standalone strategy and is not used here.
- **Stripped fast-trend bases** (TQQQ > 10/20/50-day MA + old stop/re-entry):
  dev CAGR 23–41%, correlation 0.53–0.68 — either too correlated or too weak
  (Section 2).
- **Pure 4% dip-buy** (buy every 4% down day, hold 1–5 days): correlation
  0.09–0.30 but dev CAGR −3% to +6.5%; not enough return to be a strategy.
- **Same-day VWAP / 5m / 15m EMA / QQQ-MA20 reclaim re-entry** from the original
  report: negative post-reclaim drift and higher drawdown; not used. The VWAP
  practitioner sources (Scanz, Section 32, Tradezella, QuantCore) inspired those
  rejected variants and are not provenance for this rebuild.

### Own tests still to run

- The overshoot event count, forward-return distribution, parameter
  neighbourhood, placebo, and correlations are **not yet measured**. They are
  the authorized next step; no result is claimed in this document.

## 11. Results (pending authorization)

| Window | 1 bp CAGR / DD | 5 bp CAGR / DD | 10 bp CAGR / DD |
|---|---:|---:|---:|
| dev 2016-01-04..2023-12-29 | TBD | TBD | TBD |
| 10y / 5y / holdout | not inspected | not inspected | not inspected |

Correlation vs 165-day baseline: TBD (hard bar < 0.60).
Event count: TBD (if < 100, bootstrap p-value required).
Placebo percentile: TBD.

## 12. Status rule

- If the dev result clears the falsifiers in Section 8 and the correlation bar,
  the strategy is `passed` and frozen for the lead's single holdout run.
- If the signal has no forward edge, or the result is a single-episode artifact,
  or the correlation is ≥ 0.60, it is `retired_overlay_only` (or re-specified
  once, then retired).
- No result.json is generated while tests are paused.
