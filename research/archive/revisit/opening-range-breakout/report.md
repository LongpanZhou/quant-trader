> **Post-test note (2026-11-27):** this file is the pre-registration, not
> the result. The frozen development result is in `../SUMMARY.md`; the
> full 2016-2026 audit, the post-tune variants and the research-validity
> verdicts are in `../WHY_UNDERPERFORM.md`. The published website curve is
> the freeze named in `../SUMMARY.md`.

# Opening-range failed-breakdown reclaim — standalone rebuild

**Status: pre-registered, pending backtest.** Backtests are paused by the lead.
This file contains the hypothesis, exact spec, code, provenance and falsifiers;
it deliberately contains **no strategy results**. `result.json` will be generated
only after the lead authorises the run.

---

## 1. What was extracted, and what is new

The original `agents/opening-range-breakout` strategy was:

> buy the first close **above** the 30-minute opening-range high, stop at the
> range low, then **hold overnight for weeks** while QQQ is above its 165-day
> SMA.

The genuinely new idea in that strategy is the **opening-range interaction**,
not the 165-day overnight base. This rebuild keeps the opening range but
changes the mechanism, direction, asset, holding period, sizing and risk:

| | Original | This rebuild |
|---|---|---|
| Signal | breakout **above** ORH | failed break **below** ORL + reclaim |
| Direction | continuation | reversal (liquidity sweep) |
| Asset | TQQQ | **QQQ** (TQQQ only as sensitivity) |
| Holding | weeks/months, overnight | **intraday only**, flat at the close |
| Gate | QQQ 165-day SMA | **none** |
| Size | 100% TQQQ | **0.5% equity risk at the stop**, cap 100% notional |
| Exit | OR-low stop / regime off | sweep-low stop, ORH target, EOD |

This is not the old overlay with the base stripped. The return driver is a
different effect (intraday reversal after a failed breakdown), the position is
flat overnight, and the risk is defined by the setup's own geometry.

## 2. Why not the other standalone variants I considered

Before choosing the reversal, I tested the opening-range idea's own forward
returns on the development period (pre-pause exploration, 2016-01-04 ..
2023-12-29; these are **not** the final strategy's results):

| Signal after the 30-min opening range | n | next overnight mean | next-day close-to-close | verdict |
|---|---:|---:|---:|---|
| close **above** ORH (classic breakout) | 805 | +0.006% | −0.043% | no overnight edge; classic breakout is weak |
| first 30-min candle **up** | 1,061 | **+0.235%** (t = 3.10) | +0.115% | real overnight edge, but **rejected** (see below) |
| close **below** ORL | 614 | +0.082% | +0.200% | weak, not enough alone |

The first-30-min direction has a strong overnight edge, but using it would
make the new strategy long TQQQ on ~53% of nights — the same return driver as
the old base, which is long TQQQ on ~80% of nights. A rough overlap
calculation (both earn the same TQQQ overnight return on overlapping nights)
gives an expected correlation of **0.65–0.75**, above the 0.60 limit. It is
therefore rejected as the standalone base; the pre-pause scratch scripts
`dev_evidence.py` / `dev_overnight.py` document that line of research.

The classic breakout-close signal is also rejected: on dev it has essentially
no overnight edge and a negative next-day return, consistent with the new
pre-registered futures study that finds ORB does not survive costs
(SSRN 7428398). The remaining opening-range mechanism with a distinct return
driver is the **failed-breakdown reclaim**.

## 3. Hypothesis

A brief break below the 30-minute opening-range low that is quickly reclaimed
is a **liquidity sweep**: stop-loss sellers and breakout shorts are filled,
then the price recovers into the range. The trapped sellers cover and the
reversal continues toward the opposite side of the range (ORH) before the
close. The effect is intraday, so it is structurally separate from the
overnight TQQQ drift that drives the old base.

**What would prove it wrong:** the reclaim is just intraday beta; a
random-entry control with the same time-of-day and holding period produces the
same result, or the mean R is ≤ 0 after costs. See §9.

## 4. Universe and data constraints

- **Primary:** QQQ (signal and execution), BIL (flat). Long-only.
- **Sensitivity:** TQQQ execution with the same risk budget (3× volatility,
  so the notional is smaller for the same dollar risk). Not the base.
- **Development period:** 2016-01-04 → 2023-12-29. Holdout 2024-01-02 →
  2026-10-23 is **not inspected**; the lead runs it once.
- **Data available for dev:** adjusted 1-minute QQQ/TQQQ/BIL in
  `data/intraday-hf/`. SPY 1-minute exists only for 2026-08..2026-10 in
  `data/cache/dukascopy/`, so it cannot support a 2016–2023 opening-range
  study. SPY daily exists in `data/round3/yahoo/`, but a daily bar has no
  opening range. No sector/bond/gold/volatility 1-minute data covers dev.
- **Consequence:** a multi-asset ORB is not possible on the current dev data.
  If the lead wants a sector/bond/gold ORB, the data subagent must first fetch
  1-minute history into `data/round3/<source>/` with a `SOURCE.md`.

## 5. Exact rules (primary)

All times US/Eastern, regular session. Signals use data through the signal
bar's close; fills are the next bar's open.

1. **Opening range:** first 30 minutes, 09:30–09:59. `ORH = max high`,
   `ORL = min low`, `ORM = (ORH+ORL)/2`.
2. **Breakdown:** after 10:00, the first bar whose **low < ORL × (1 − 5 bp)**.
   Record the breakdown bar and the running **sweep low** (minimum low from
   the breakdown onward).
3. **Reclaim:** within **30 bars** of the breakdown, a bar whose **close >
   ORL × (1 + 5 bp)**, before the last 30 minutes of the session. That close
   is the entry signal.
4. **Entry:** next bar's open, long QQQ.
5. **Stop:** the sweep low. Checked on every subsequent bar's **low**; a
   breach exits at the next bar's open.
6. **Target:** ORH. Checked on every subsequent bar's **high**; a hit exits at
   the next bar's open. If the target is hit, no more trades that day.
7. **Reward filter:** require `ORH − entry ≥ 1.0 × (entry − sweep low)`;
   otherwise skip the day.
8. **End of day:** force exit at the second-to-last bar of the session (fills
   at the last bar's open). No overnight exposure; BIL when flat.
9. **One trade per session.** No re-entry after a stop or an EOD exit.
10. **Costs:** 1 bp headline; 5 bp and 10 bp reported.

The EOD exit uses the session's own second-to-last bar, so half days (13:00
close) are handled without a fixed clock time. Sessions with fewer than
`or_min + 10` bars are skipped.

## 6. Sizing and risk

- Risk budget **0.50% of equity per trade**, measured from the entry to the
  sweep-low stop:
  `size = min(1.0, 0.005 × entry / (entry − stop))`.
- The remainder sits in BIL; no leverage, no overnight gap risk, no shorting.
- This is deliberately different from the old 100% TQQQ base. The dollar risk
  is constant across setups; wide sweeps get a smaller notional.
- One position at a time, one trade per day.

## 7. Why this is not the old base

- **No 165-day (or any 100–250-day) QQQ/TQQQ/SPY/NDX moving-average gate.**
  The strategy has no moving-average gate at all.
- **No reused positions or code.** `build_weights` is a fresh state machine;
  it does not call or copy the old `build_weights` or the old weights.
- **Different return driver.** The old base earns TQQQ's overnight drift
  while a slow trend filter is on. This strategy earns an intraday reversal
  after a failed breakdown and is flat every night.
- **Different holding period.** Hours, not weeks.
- **Different risk.** Fixed fractional risk at the sweep low, not 100% TQQQ.

## 8. Expected correlation with the old base

**Expected: 0.10–0.40** (to be measured on dev daily returns).

Argument: the old base's daily return is mostly the TQQQ overnight gap; this
strategy is flat overnight and holds QQQ only for a few hours after a morning
breakdown/reclaim. The holding windows are disjoint, and the strategy often
buys after a morning selloff, which can be a day the old base is long or flat.
The only shared component is same-day QQQ beta during the holding window, and
the old base's daytime beta is a small part of its daily return.

If the measured dev correlation is **≥ 0.60**, the design fails the brief and
must be changed (e.g., a different intraday asset or a different reversal
window), not reported as passing.

## 9. Falsifiers (pre-registered)

The strategy is rejected if any of these is true on dev 2016–2023:

1. Mean R per trade ≤ 0 at 1 bp, or CAGR ≤ 0.
2. Profit factor < 1.1 at 1 bp, or the edge is gone at 5 bp.
3. Both sub-periods 2016–19 and 2022–23 are ≤ 0 (the result is a single-episode
   artifact, e.g. 2020 only).
4. A random-entry placebo with the same time-of-day and holding period
   matches or beats the strategy's CAGR and mean R.
5. Fewer than 100 events and a bootstrap p-value > 0.10 for mean R.
6. Dev correlation with the 165-day baseline ≥ 0.60.
7. The ±1-step neighbourhood flips sign: OR 15 or 45 minutes, break buffer 0
   or 10 bp, reclaim window 15 or 60 bars, target ORM or EOD, min reward
   0.75R or 1.25R, risk 0.25% or 1.0% — if the neighbouring values are
   negative, there is no plateau.
8. The edge depends on the 5 bp buffers or the ORH target specifically;
   neighbouring buffers/targets are negative.

A negative result is acceptable and will be reported as
`retired_overlay_only` or `rejected` with the evidence.

## 10. Overfitting controls (planned)

- **Variants tried:** one-at-a-time neighbourhood, pre-registered:
  OR window 15 / **30** / 45; break buffer 0 / **5** / 10 bp; reclaim buffer
  0 / **5** / 10 bp; reclaim window 15 / **30** / 60 bars; target **ORH** /
  ORM / EOD; min reward 0.75 / **1.0** / 1.25R; risk 0.25% / **0.5%** / 1.0%;
  asset QQQ / TQQQ. That is 15 one-step variants plus the primary, not a grid.
- **Sub-periods:** 2016–19, 2020–21, 2022–23, each reported separately.
- **Placebo:** random entry bar between 10:00 and 14:00, same asset, same
  risk budget, hold to EOD; 500 draws, report the distribution and percentile
  of the real strategy.
- **Event count / bootstrap:** number of breakdown-reclaim events and a
  10,000-draw bootstrap p-value for mean R.
- **Parameter plateau:** report the full neighbourhood table, not just the
  best cell.
- **Data:** dev only; no holdout inspection.

## 11. Provenance

| Idea / claim | Source | URL | Type | Role | Confidence |
|---|---|---|---|---|---|
| Fade a false breakout: price breaks ORH then reverses back inside; trapped breakout longs create the reversal. The long-side mirror is a break below ORL that reclaims it. | Bergstrom, D., *Opening Range Breakout: Complete Guide*, Build Alpha, 2026, Setup 2 | https://www.buildalpha.com/opening-range-breakout/ | blog / practitioner guide | inspired the rule | medium |
| Force EOD exit; limit trades per day; OR/ATR size filters; most ORB variants are overfit. | Same Build Alpha guide | https://www.buildalpha.com/opening-range-breakout/ | blog | supports execution/risk choices | medium |
| ORB does not survive realistic costs: median gross edge −0.01 ticks, 155/225 cells within two ticks of zero, 5-min range worst, largest surviving cell fails a random-anchor control. | Fetna, M., *Opening-Range Breakout Does Not Survive Trading Costs: A Pre-Registered 225-Cell Study on Sixteen Years of Futures Data*, SSRN 7428398 | https://papers.ssrn.com/sol3/papers.cfm?abstract_id=7428398 | paper | supports rejecting a plain breakout rebuild; motivates a different mechanism | high |
| Post-breakout sequence / retest in QQQ at 1-minute resolution; the interaction after the break matters, not just the break. | Pineda, M., *Anatomy of the Retest in the QQQ Opening Range Breakout*, SSRN 6745958 | https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6745958 | paper (exploratory) | supports studying the reclaim, not the initial break | medium (abstract only; full text 403) |
| ORB origin: 5-minute first-candle direction, stop at the first candle's low, 10R target/EOD; TQQQ variant. | Zarattini, C. & Aziz, A., *Can Day Trading Really Be Profitable?*, SSRN 4416622 | https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4416622 | paper | area starting point; not the new rule | high |
| ORB profitability is conditional on the return distribution / volatility conditions; unconditional ORB is weak. | Holmberg, U., Lönnbark, C. & Lundström, C., *Assessing the profitability of intraday opening range breakout strategies*, Umeå Economic Studies 845, 2012 | https://ideas.repec.org/p/hhs/umnees/0845.html | paper | supports conditioning/filtering the setup | medium |
| Dev evidence: the classic breakout close has ~zero overnight edge; the first-30-min direction has a strong overnight edge but would share the old base's driver. | Own pre-pause test, 2016-01-04..2023-12-29 | local: `dev_evidence.py` | data | rejected alternative designs | high (own data) |
| Exact parameters (30 min, 5 bp buffers, 30-bar reclaim, 1R filter, 0.5% risk) and the failed-breakdown reclaim state machine. | Own design / no external source | — | — | the rebuild itself | — |

The old paper and the old local strategy are the **starting point**, not the
source of the new rule. The new rule is the long-side mirror of Build Alpha's
"fade the false breakout", adapted to a long-only intraday QQQ implementation
with a sweep-low stop and ORH target.

## 12. Results (pending)

> Backtests are paused. No strategy results have been generated. The following
> placeholders will be filled by the authorised run.

| Window | 1 bp CAGR / max DD / Sharpe | 5 bp | 10 bp | Fills |
|---|---:|---:|---:|---:|
| Dev 2016-01-04..2023-12-29 | pending | pending | pending | pending |
| 10y (overlaps holdout) | lead only | lead only | — | — |
| 5y (overlaps holdout) | lead only | lead only | — | — |
| Holdout 2024-01-02..2026-10-23 | lead only | lead only | — | — |

Other pending tables: yearly returns; sub-periods 2016–19 / 2020–21 / 2022–23;
±1-step neighbourhood; placebo distribution; event count and bootstrap p-value;
correlation vs the 165-day baseline; correlation vs other rebuilds.

## 13. Status and next step

- **Current status:** pre-registered, pending test. Not passed, not rejected.
- **Next step:** when the lead authorises backtests, run `strategy.py`
  (dev only) and fill §12 and `result.json`; then the lead runs the frozen
  strategy once on the holdout.
- **Data request (optional):** if a multi-asset ORB is wanted later, fetch
  1-minute history for sector/bond/gold/vol ETFs into `data/round3/` with a
  `SOURCE.md`; the current dev data only supports QQQ/TQQQ/BIL.
