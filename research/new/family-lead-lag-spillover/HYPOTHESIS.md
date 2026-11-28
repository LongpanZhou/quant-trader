# HYPOTHESIS — cross-market spillover / lead-lag

**Status:** pre-registration written before the final grid/placebo run; the sign
and the intraday decomposition were fixed from the dev-window event study
described below. Development window only: **2016-01-04 .. 2023-12-29**. The
2024-2026 holdout is not loaded or inspected.

**Directory:** `research/new/family-lead-lag-spillover/`

---

## 1. Mechanism

SPY and QQQ share a common market factor, but they are not the same asset. SPY
is broader, less volatile, and more heavily used for macro hedging; QQQ is
concentrated in long-duration technology. A cash-session selloff in SPY can be
driven by flow/liquidity that QQQ has not fully priced. If SPY sells off more
than its rolling beta to QQQ implies, the next QQQ session should bounce as the
common factor mean-reverts.

The hypothesis has two layers:

1. **Weak (tradable):** SPY's prior-session return negatively predicts QQQ's
   next-session return, i.e. the common factor exhibits short-horizon reversal.
2. **Strong (novel):** the predictive content survives orthogonalising SPY's
   move to QQQ's contemporaneous move. If it does, the effect is a genuine
   cross-market spillover, not just QQQ's own reversal seen through a proxy.

Layer 2 is the reason to call this a *new* family. Layer 1 alone would overlap
with the existing short-reversal family and the forbidden "short reversal"
space.

A second decomposition matters: SPY's close-to-close return = overnight gap +
intraday move. With next-open fills the overnight gap into session `d+1` is not
tradable. Therefore the primary signal uses **SPY's intraday return,
open-to-close**, and the overnight component is tested only as a diagnostic.

## 2. Exact rules (primary)

All inputs are known at the **16:00 ET close of session `d`**. SPY and QQQ
close at the same time. Fills are at the **next session's 09:30 open**.

```
spy_open_adj[d] = SPY open[d] * SPY adjclose[d] / SPY close[d]
s_id[d]         = SPY adjclose[d] / spy_open_adj[d] - 1          # intraday
z[d]            = s_id[d] / stdev(s_id[d-20 .. d-1], ddof=1)

event           : z[d] <= -0.50
entry           : TQQQ 1.0 at the open of session d+1
exit            : TQQQ 0.0 at the 15:59 open of session d+1
                  (the sell fills on the 15:59 bar, i.e. one minute before close)
idle            : BIL 1.0
```

A run of consecutive events keeps the position open (the next session's entry
replaces the exit); the minimum holding period is one session. `hold=2`
extends the exit to the 15:59 open of session `d+2`.

No 100-250 day moving-average trend gate, no volatility targeting, no
drawdown/capitulation event, no calendar window, no opening-range or close-flow
signal, no ML classifier, and no QQQ/SPY ratio-momentum or relative-strength
gate. The residual `res_id` is a one-day orthogonalised return, not a ratio
level or a trend signal.

## 3. Data and alignment

- QQQ/TQQQ/BIL 1-minute adjusted bars: `data/intraday-hf/*-1m.parquet`, loaded
  through `research/bt.py`.
- QQQ daily adjusted closes: `data/intraday-hf/QQQ-1d-yahoo.parquet`.
- SPY daily: `data/round3/yahoo/SPY-1d-yahoo.parquet`. The file is truncated at
  `2023-12-29` immediately after reading; no later row is used.
- QQQ's 1-minute calendar is the base. Every dev session has a SPY and QQQ
  daily row (asserted at load). The first ~20 sessions are warm-up for the
  20-day stdev and produce no signal.
- `spy_open_adj` applies the same-day `adjclose/close` factor so the
  overnight/intraday split is dividend-consistent. The residual uses a rolling
  60-session beta of SPY intraday on QQQ intraday, estimated strictly through
  `d-1`.
- Headline engine: `bt.run(..., band=0.02, slippage_bps=1.0)`. 5 bp and 10 bp
  are reported. Headline metrics use the repo's `bt.stats(..., 252*390)`
  convention; a daily-return Sharpe is reported alongside for comparison.
- `bt` fills a target written on bar `i` at bar `i+1`'s open. The entry target
  is written on the 15:59 bar of session `d` and fills at session `d+1`'s
  09:30 open, after the 16:00 signal is known. The 15:59 write is bookkeeping,
  not an earlier decision.

## 4. Parameter grid and plateau

Primary cell: `signal=spy_intraday, vol_window=20, thr=0.50, hold=1`.

The plateau is checked over:

- `thr ∈ {0.25, 0.50, 0.75, 1.00}` × `hold ∈ {1, 2}` for
  `spy_intraday`, `spy_cc`, and `qqq_intraday` (24 cells);
- local neighbours `thr ∈ {0.40, 0.45, 0.50, 0.55, 0.60}` × `hold ∈ {1, 2}`;
- `vol_window ∈ {10, 20, 40, 60}` at the primary cell.

The centre is not chosen by the best backtest cell. 0.50 is a round-number
half-sigma deadband chosen for a meaningful move and a stable neighbourhood
(0.40-0.60 Sharpe 0.86-0.96); the grid is reported in full so the lead can see
the shape, including the 2-session cells that do better.

## 5. Falsifiers / kill criteria

The family is killed if any of the following holds:

1. **Activity:** fewer than 100 full-window fills, or fewer than 30 episodes.
2. **Stand-alone:** 1 bp Sharpe < 0.82 or CAGR < 20%.
3. **Cost:** non-positive CAGR at 10 bp.
4. **Stability:** any subperiod with negative CAGR, or 2022-2023 daily Sharpe
   <= 0.2.
5. **Placebo:** circular-shift p-value > 0.10 (24 shifts), or random-event
   p-value > 0.10 (1,000 draws).
6. **Strong hypothesis (novelty):** the orthogonalised residual `rz_id` must
   predict the **tradable** next-session QQQ open-to-close return with
   t <= -1.5; and QQQ's own intraday signal must not match or beat the SPY
   signal. If either fails, the "cross-market beyond QQQ" claim is false even
   if the stand-alone strategy makes money. (The close-to-close residual is a
   diagnostic only; it includes the untradable overnight gap.)
7. **Redundancy:** daily-return correlation with any current winner > 0.70.

## 6. What would make it a pass

A pass requires all of:

- >= 100 fills and >= 30 episodes;
- 1 bp CAGR >= 36.72%, max DD <= 82.29%, Sharpe >= 0.82 (the brief's TQQQ bar);
- positive CAGR at 10 bp;
- all three subperiods positive, with 2022-2023 daily Sharpe > 0.2;
- circular-shift p <= 0.10 and random-event p <= 0.10;
- residual t <= -1.5 and SPY not dominated by QQQ's own signal;
- max winner correlation <= 0.70.

The last two are the important ones. A strategy can clear the return bar and
still fail the family test if the return is just common-factor reversal or
overnight drift.
