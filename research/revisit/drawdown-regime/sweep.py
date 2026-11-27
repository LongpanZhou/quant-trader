"""Standalone drawdown/underwater variants, development only (2016-2023)."""
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


def daily_qqq_long(end=DEV_END):
    d = pd.read_parquet(ROOT / "data" / "intraday-hf" / "QQQ-1d-yahoo.parquet")
    d["date"] = pd.to_datetime(d["date"]).dt.date
    d = d[d["date"] <= pd.Timestamp(end).date()].sort_values("date")
    return d["date"].to_numpy(), d["adjclose"].to_numpy(float)


def dd_signals(dates, close, window=252, min_periods=200):
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


def weights_for(on_days, day_id, n_bars, col=1):
    w = np.zeros((n_bars, 3))
    w[:, col] = on_days[day_id].astype(float)
    w[:, 2] = 1.0 - w[:, 1] - w[:, 0]
    return w


def state_gate(dd, x, y):
    """exit at dd <= -x, re-enter at dd >= -y."""
    n = len(dd)
    on = np.zeros(n, bool)
    state = True
    for k in range(n):
        if not np.isfinite(dd[k]):
            state = True
        elif state and dd[k] <= -x:
            state = False
        elif (not state) and dd[k] >= -y:
            state = True
        on[k] = state
    return on


def state_contrarian(dd, x, y):
    n = len(dd)
    on = np.zeros(n, bool)   # default out
    state = False
    for k in range(n):
        if not np.isfinite(dd[k]):
            state = False
        elif (not state) and dd[k] <= -x:
            state = True
        elif state and dd[k] >= -y:
            state = False
        on[k] = state
    return on


def state_trough(dd, x, r):
    """exit at -x; re-enter after the drawdown recovers r pp from its trough."""
    n = len(dd)
    on = np.zeros(n, bool)
    state = True
    dmin = 0.0
    for k in range(n):
        d = dd[k]
        if not np.isfinite(d):
            state, dmin = True, 0.0
        else:
            if state:
                dmin = min(dmin, d)
                if d <= -x:
                    state = False
                    dmin = d
            else:
                dmin = min(dmin, d)
                if d >= dmin + r:
                    state = True
        on[k] = state
    return on


def main():
    ts, opens, closes = bt.panel(SYMS, DEV_START, DEV_END, "1min", warmup_days=500)
    dates_bar, first, last, day_id = day_index(ts)
    dates = dates_bar[last]
    n_days, n_bars = len(first), len(ts)
    print(f"bars {n_bars:,} days {n_days}", flush=True)

    ddates, dcl = daily_qqq_long()
    dd_d, uw_d, reg_d = dd_signals(ddates, dcl)
    mp = {d: (dd_d[i], uw_d[i], reg_d[i]) for i, d in enumerate(ddates)}
    dd = np.array([mp[d][0] for d in dates])
    uw = np.array([mp[d][1] for d in dates])
    reg = np.array([mp[d][2] for d in dates])

    wb = weights_for(reg, day_id, n_bars)
    r = bt.run(ts, opens, closes, wb, DEV_START, band=0.02, slippage_bps=1.0)
    sb = bt.stats(r, BPY)
    base_daily = pd.Series(r["equity"], index=r["ts"]).resample("1D").last().pct_change().dropna()
    print(f"baseline 165d: CAGR {sb['cagr']*100:.2f} DD {sb['max_drawdown']*100:.2f} "
          f"Sharpe {sb['sharpe']:.2f}", flush=True)

    ws, labels, kinds = [], [], []

    def add(lab, w, kind):
        ws.append(w); labels.append(lab); kinds.append(kind)

    add("baseline", wb, "baseline")

    for x in (0.05, 0.08, 0.10, 0.12, 0.15, 0.20):
        for y in (0.02, 0.05):
            if y < x:
                add(f"gate X{x*100:.0f}/Y{y*100:.0f}", weights_for(state_gate(dd, x, y), day_id, n_bars), "gate")

    for a, b in ((5, 10), (8, 15), (5, 15), (10, 20), (5, 8)):
        frac = np.ones(n_days)
        frac[dd <= -a / 100] = 0.5
        frac[dd <= -b / 100] = 0.0
        add(f"ladder {a}/{b}", weights_for(frac, day_id, n_bars), "ladder")

    for a, b in ((5, 10), (8, 15), (10, 20)):
        w = np.zeros((n_bars, 3))
        q = np.zeros(n_days); t = np.zeros(n_days)
        q[dd <= -a / 100] = 1.0
        q[dd <= -b / 100] = 0.0
        t[dd > -a / 100] = 1.0
        w[:, 0] = q[day_id]; w[:, 1] = t[day_id]
        w[:, 2] = 1 - w[:, 0] - w[:, 1]
        add(f"delever {a}/{b}", w, "delever")

    for n in (60, 120, 180, 250):
        add(f"uw<{n}", weights_for((uw < n).astype(float), day_id, n_bars), "uw")

    for dmax in (10, 15, 20, 30):
        frac = np.clip(1.0 - np.abs(np.minimum(dd, 0)) / (dmax / 100), 0, 1)
        add(f"scale D{dmax}", weights_for(frac, day_id, n_bars), "scale")

    for x in (0.08, 0.10, 0.15):
        for rr in (0.02, 0.03, 0.05):
            add(f"trough X{x*100:.0f}/R{rr*100:.0f}", weights_for(state_trough(dd, x, rr), day_id, n_bars), "trough")

    for x in (0.10, 0.15, 0.20):
        for y in (0.02, 0.05):
            add(f"contra X{x*100:.0f}/Y{y*100:.0f}", weights_for(state_contrarian(dd, x, y), day_id, n_bars), "contra")

    # QQQ instead of TQQQ for the best-looking gate family
    for x, y in ((0.08, 0.02), (0.10, 0.05), (0.12, 0.05)):
        add(f"QQQ gate X{x*100:.0f}/Y{y*100:.0f}", weights_for(state_gate(dd, x, y), day_id, n_bars, col=0), "qqqgate")

    rs = bt.run_many(ts, opens, closes, ws, start=DEV_START, band=0.02, slippage_bps=1.0)
    rows = []
    for lab, rr, kind in zip(labels, rs, kinds):
        st = bt.stats(rr, BPY)
        d = pd.Series(rr["equity"], index=rr["ts"]).resample("1D").last().pct_change().dropna()
        corr = float(pd.concat([d, base_daily], axis=1, join="inner").dropna().corr().iloc[0, 1])
        rows.append((lab, kind, st, corr))
        print(f"{lab:24s} {kind:9s} CAGR {st['cagr']*100:6.2f} DD {st['max_drawdown']*100:5.2f} "
              f"Sharpe {st['sharpe']:5.2f} fills {st['fills']:4d} exp {st['exposure']*100:5.1f}% "
              f"corr {corr:.3f}", flush=True)

    print("\nbest by CAGR with corr<0.60:")
    cand = [x for x in rows if x[3] < 0.60 and x[1] != "baseline"]
    for lab, kind, st, corr in sorted(cand, key=lambda z: -z[2]["cagr"])[:5]:
        print(f"  {lab:24s} CAGR {st['cagr']*100:6.2f} DD {st['max_drawdown']*100:5.2f} corr {corr:.3f}")


if __name__ == "__main__":
    main()
