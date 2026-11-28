"""Exploration for the standalone drawdown/underwater rebuild (development only).

Period: 2016-01-04 .. 2023-12-29. No holdout inspection.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402

DEV_START, DEV_END = "2016-01-04", "2023-12-29"
BPY = 252 * 390
SYMS = ("QQQ", "TQQQ", "BIL")


def day_index(ts):
    dates = bt.session_dates(ts)
    first = np.flatnonzero(np.r_[True, dates[1:] != dates[:-1]])
    last = np.r_[first[1:] - 1, len(dates) - 1]
    day_id = np.repeat(np.arange(len(first)), np.diff(np.r_[first, len(dates)]))
    return dates, first, last, day_id


def daily_qqq_long():
    """QQQ adjusted daily closes from 2015 (for warmup) through dev end."""
    d = pd.read_parquet(ROOT / "data" / "intraday-hf" / "QQQ-1d-yahoo.parquet")
    d["date"] = pd.to_datetime(d["date"]).dt.date
    d = d[d["date"] <= pd.Timestamp(DEV_END).date()].sort_values("date")
    return d["date"].to_numpy(), d["adjclose"].to_numpy(float)


def dd_series(dates, close, window=252, min_periods=200):
    """Trailing-high drawdown known at the prior close, and underwater length."""
    s = pd.Series(close, index=pd.to_datetime(dates))
    hi = s.rolling(window, min_periods=min_periods).max()
    dd = (s / hi - 1.0).to_numpy()
    dd_prev = np.r_[np.nan, dd[:-1]]
    sma = s.rolling(165, min_periods=165).mean().to_numpy()
    reg = np.r_[False, close[:-1] > sma[:-1]]
    uw = np.zeros(len(s), int)
    run = 0
    for k in range(1, len(s)):
        if close[k - 1] >= hi.iloc[k] * (1 - 1e-12):
            run = 0
        else:
            run += 1
        uw[k] = run
    return dd_prev, uw, reg


def weights_from_day(on):
    w = np.zeros((len(on) * 0 + 0, 3))
    return w


def main():
    ts, opens, closes = bt.panel(SYMS, DEV_START, DEV_END, "1min", warmup_days=500)
    dates_bar, first, last, day_id = day_index(ts)
    dates = dates_bar[last]          # one entry per session
    n_days = len(first)
    print(f"bars {len(ts):,} days {n_days} {ts[0]} .. {ts[-1]}", flush=True)

    ddates, dcl = daily_qqq_long()
    dd_prev_d, uw_d, reg_d = dd_series(ddates, dcl)
    by_day = {d: (dd_prev_d[i], uw_d[i], reg_d[i]) for i, d in enumerate(ddates)}
    missing = [d for d in dates if d not in by_day]
    print("missing daily dates:", len(missing), missing[:5])
    dd_prev = np.array([by_day[d][0] for d in dates])
    uw = np.array([by_day[d][1] for d in dates])
    reg_base = np.array([by_day[d][2] for d in dates])
    print("dd nan", int(np.isnan(dd_prev).sum()), "reg on", f"{reg_base.mean()*100:.1f}%")
    print("dd quantiles", np.nanpercentile(dd_prev, [1, 5, 25, 50, 75, 95]).round(4))

    # sanity: panel daily close vs parquet adjclose at a few dates
    dclose = closes[last, 0]
    for k in (0, 500, 1500, n_days - 1):
        i = int(np.searchsorted(ddates, dates[k]))
        print(f"  {dates[k]} panel {dclose[k]:.4f} parquet {dcl[i]:.4f} dd {dd_prev[k]*100:6.2f}%")

    # ---- unconditional forward returns, TQQQ, by drawdown bucket (dev days)
    tq = closes[last, 1]
    print("\nunconditional fwd TQQQ by QQQ drawdown bucket (dev 2016-2023)")
    print(f"{'bucket':>12} {'days':>5} {'fwd5':>8} {'hit':>5} {'fwd20':>8} {'hit':>5} {'fwd60':>8} {'hit':>5}")
    edges = [(0.0, -0.03), (-0.03, -0.05), (-0.05, -0.08), (-0.08, -0.12),
             (-0.12, -0.20), (-0.20, -1.0)]
    for lo, hi in edges:
        m = np.isfinite(dd_prev) & (dd_prev <= lo) & (dd_prev > hi)
        idx = np.flatnonzero(m)
        f5 = np.array([tq[k + 5] / tq[k] - 1 for k in idx if k + 5 < n_days])
        f20 = np.array([tq[k + 20] / tq[k] - 1 for k in idx if k + 20 < n_days])
        f60 = np.array([tq[k + 60] / tq[k] - 1 for k in idx if k + 60 < n_days])
        print(f"{lo*100:6.1f}..{hi*100:6.1f} {len(idx):5d} {f5.mean()*100:7.2f}% "
              f"{(f5>0).mean()*100:4.0f}% {f20.mean()*100:7.2f}% {(f20>0).mean()*100:4.0f}% "
              f"{f60.mean()*100:7.2f}% {(f60>0).mean()*100:4.0f}%")

    print("\ntime spent by bucket (dev days)")
    for lo, hi in edges:
        m = np.isfinite(dd_prev) & (dd_prev <= lo) & (dd_prev > hi)
        print(f"  {lo*100:6.1f}..{hi*100:6.1f}: {m.sum():5d} days ({m.mean()*100:4.1f}%)")
    print("\nunderwater duration quantiles (dev days):",
          np.percentile(uw[np.isfinite(dd_prev)], [50, 75, 90, 95, 99]).round(1))

    # ---- baseline 165d (with 2015 warmup) on dev
    wb = np.zeros((len(ts), 3))
    wb[:, 1] = reg_base[day_id].astype(float)
    wb[:, 2] = 1 - wb[:, 1]
    r = bt.run(ts, opens, closes, wb, DEV_START, band=0.02, slippage_bps=1.0)
    s = bt.stats(r, BPY)
    base_daily = pd.Series(r["equity"], index=r["ts"]).resample("1D").last().pct_change().dropna()
    print(f"\n165d baseline dev: CAGR {s['cagr']*100:.2f} DD {s['max_drawdown']*100:.2f} "
          f"Sharpe {s['sharpe']:.2f} fills {s['fills']} exposure {s['exposure']*100:.0f}%")

    # ---- simple binary drawdown gate
    def gate_weights(x, y):
        on = np.zeros(n_days, bool)
        state = True
        for k in range(n_days):
            if not np.isfinite(dd_prev[k]):
                state = True
            elif state and dd_prev[k] <= -x:
                state = False
            elif (not state) and dd_prev[k] >= -y:
                state = True
            on[k] = state
        w = np.zeros((len(ts), 3))
        w[:, 1] = on[day_id].astype(float)
        w[:, 2] = 1 - w[:, 1]
        return w

    print("\nbinary gate: TQQQ when dd > -X, exit at <= -X, re-enter at >= -Y")
    ws, labels = [], []
    for x in (0.05, 0.08, 0.10, 0.12, 0.15, 0.20):
        for y in (0.02, 0.05):
            if y >= x:
                continue
            ws.append(gate_weights(x, y))
            labels.append(f"X{x*100:.0f} Y{y*100:.0f}")
    rs = bt.run_many(ts, opens, closes, ws, start=DEV_START, band=0.02, slippage_bps=1.0)
    for lab, rr in zip(labels, rs):
        st = bt.stats(rr, BPY)
        d = pd.Series(rr["equity"], index=rr["ts"]).resample("1D").last().pct_change().dropna()
        corr = float(pd.concat([d, base_daily], axis=1, join="inner").dropna().corr().iloc[0, 1])
        print(f"{lab:12s} CAGR {st['cagr']*100:6.2f} DD {st['max_drawdown']*100:5.2f} "
              f"Sharpe {st['sharpe']:5.2f} fills {st['fills']:4d} exp {st['exposure']*100:5.1f}% corr {corr:.3f}")


if __name__ == "__main__":
    main()
