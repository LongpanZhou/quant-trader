"""Standalone stop-only controls, sub-periods, neighbourhoods and placebos.

Development only: 2016-01-04 .. 2023-12-29.
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
    ma20 = s.rolling(20).mean().to_numpy()
    ma20_prev = np.r_[np.nan, ma20[:-1]]
    sma = s.rolling(165, min_periods=165).mean().to_numpy()
    reg = np.r_[False, close[:-1] > sma[:-1]]
    return dd_prev, ma20_prev, reg


def weights_from(on_days, day_id, n_bars, col=1):
    w = np.zeros((n_bars, 3))
    w[:, col] = on_days[day_id].astype(float)
    w[:, 2] = 1.0 - w[:, 1] - w[:, 0]
    return w


def state_gate(dd, x, y):
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


def state_trough(dd, x, r):
    n = len(dd)
    on = np.zeros(n, bool)
    state = True
    dmin = 0.0
    for k in range(n):
        d = dd[k]
        if not np.isfinite(d):
            state, dmin = True, 0.0
        elif state:
            dmin = min(dmin, d)
            if d <= -x:
                state, dmin = False, d
        else:
            dmin = min(dmin, d)
            if d >= dmin + r:
                state = True
        on[k] = state
    return on


def stop_weights(ts, opens, closes, first, last, day_id, dd, arm_ma20,
                 base_stop=0.04, dd_thr=None, dd_stop=None, arm_buf=0.01,
                 always_in=False):
    """Intraday stop with no 165-day regime. Position is always TQQQ unless
    stopped; `always_in=True` disables the MA20 arming."""
    n = len(ts)
    hold = np.zeros(n)
    qqq, tqqq = closes[:, 0], closes[:, 1]
    for k, (f, l) in enumerate(zip(first, last)):
        stop = base_stop
        if dd_thr is not None and dd[k] <= -dd_thr:
            stop = dd_stop
        armed = always_in or (np.isfinite(arm_ma20[k]) and qqq[f] < arm_ma20[k] * (1 + arm_buf))
        base = opens[f, 1]
        on = True
        for i in range(f, l + 1):
            if on and armed and tqqq[i] < base * (1 - stop):
                on = False
            hold[i] = 1.0 if on else 0.0
    w = np.zeros((n, 3))
    w[:, 1] = hold
    w[:, 2] = 1 - hold
    return w


def dev_stats(rr):
    s = bt.stats(rr, BPY)
    return s


def corr_with(rr, base_daily):
    d = pd.Series(rr["equity"], index=rr["ts"]).resample("1D").last().pct_change().dropna()
    j = pd.concat([d, base_daily], axis=1, join="inner").dropna()
    return float(j.corr().iloc[0, 1])


def subperiod(rr, a, b):
    ts = rr["ts"]
    m = (ts >= pd.Timestamp(a, tz="America/New_York")) & (ts <= pd.Timestamp(b, tz="America/New_York"))
    eq = rr["equity"][m]
    t = ts[m]
    years = (t[-1] - t[0]).total_seconds() / (365.25 * 86400)
    peak = np.maximum.accumulate(eq)
    return ((eq[-1] / eq[0]) ** (1 / years) - 1, float(-(eq / peak - 1).min()))


def main():
    ts, opens, closes = bt.panel(SYMS, DEV_START, DEV_END, "1min", warmup_days=500)
    dates_bar, first, last, day_id = day_index(ts)
    dates = dates_bar[last]
    n_days, n_bars = len(first), len(ts)
    ddates, dcl = daily_qqq_long()
    dd_d, ma20_d, reg_d = dd_signals(ddates, dcl)
    mp = {d: (dd_d[i], ma20_d[i], reg_d[i]) for i, d in enumerate(ddates)}
    dd = np.array([mp[d][0] for d in dates])
    ma20 = np.array([mp[d][1] for d in dates])
    reg = np.array([mp[d][2] for d in dates])
    print(f"days {n_days}", flush=True)

    wb = weights_from(reg, day_id, n_bars)
    rb = bt.run(ts, opens, closes, wb, DEV_START, band=0.02, slippage_bps=1.0)
    sb = dev_stats(rb)
    base_daily = pd.Series(rb["equity"], index=rb["ts"]).resample("1D").last().pct_change().dropna()
    print(f"baseline {sb['cagr']*100:.2f}/{sb['max_drawdown']*100:.2f} Sharpe {sb['sharpe']:.2f}", flush=True)

    # ---- stop-only controls: always long TQQQ, no regime
    ws, labels = [], []
    for name, kw in [
        ("no stop (B&H)", None),
        ("4% armed MA20", dict(base_stop=0.04)),
        ("4% always armed", dict(base_stop=0.04, always_in=True)),
        ("2% armed MA20", dict(base_stop=0.02)),
        ("dd2@8 + 4% MA20", dict(base_stop=0.04, dd_thr=0.08, dd_stop=0.02)),
        ("dd2@8 always", dict(base_stop=0.04, dd_thr=0.08, dd_stop=0.02, always_in=True)),
        ("dd2@5 + 4% MA20", dict(base_stop=0.04, dd_thr=0.05, dd_stop=0.02)),
    ]:
        if kw is None:
            w = np.zeros((n_bars, 3)); w[:, 1] = 1.0
        else:
            w = stop_weights(ts, opens, closes, first, last, day_id, dd, ma20, **kw)
        ws.append(w); labels.append(name)
    rs = bt.run_many(ts, opens, closes, ws, start=DEV_START, band=0.02, slippage_bps=1.0)
    print("\nstop-only, always long TQQQ (no regime gate)")
    for lab, rr in zip(labels, rs):
        st = dev_stats(rr)
        print(f"{lab:20s} CAGR {st['cagr']*100:6.2f} DD {st['max_drawdown']*100:5.2f} "
              f"Sharpe {st['sharpe']:5.2f} fills {st['fills']:4d} corr {corr_with(rr, base_daily):.3f}")

    # ---- sub-periods for key drawdown variants
    key = {}
    key["gate X12/Y5"] = weights_from(state_gate(dd, 0.12, 0.05), day_id, n_bars)
    key["trough X15/R5"] = weights_from(state_trough(dd, 0.15, 0.05), day_id, n_bars)
    key["gate X8/Y2"] = weights_from(state_gate(dd, 0.08, 0.02), day_id, n_bars)
    rr_key = bt.run_many(ts, opens, closes, [key[k] for k in key], start=DEV_START,
                         band=0.02, slippage_bps=1.0)
    print("\nsub-periods (CAGR/DD)")
    print(f"{'variant':18s} {'2016-19':>16s} {'2020-21':>16s} {'2022-23':>16s}")
    for (lab, rr) in zip(key, rr_key):
        a = subperiod(rr, "2016-01-04", "2019-12-31")
        b = subperiod(rr, "2020-01-01", "2021-12-31")
        c = subperiod(rr, "2022-01-01", "2023-12-29")
        print(f"{lab:18s} {a[0]*100:7.1f}/{a[1]*100:5.1f} {b[0]*100:7.1f}/{b[1]*100:5.1f} "
              f"{c[0]*100:7.1f}/{c[1]*100:5.1f}")

    # ---- neighbourhood for trough X/R
    print("\ntrough-gate neighbourhood (CAGR/DD)")
    print(f"{'R\\X':>6} " + " ".join(f"{x*100:>13.0f}" for x in (0.10, 0.12, 0.15, 0.20)))
    ws2, labs2 = [], []
    for r in (0.03, 0.04, 0.05, 0.06):
        for x in (0.10, 0.12, 0.15, 0.20):
            ws2.append(weights_from(state_trough(dd, x, r), day_id, n_bars))
            labs2.append((r, x))
    rs2 = bt.run_many(ts, opens, closes, ws2, start=DEV_START, band=0.02, slippage_bps=1.0)
    st2 = {(r, x): dev_stats(rr) for (r, x), rr in zip(labs2, rs2)}
    for r in (0.03, 0.04, 0.05, 0.06):
        row = f"{r*100:5.0f}% "
        for x in (0.10, 0.12, 0.15, 0.20):
            s = st2[(r, x)]
            row += f" {s['cagr']*100:6.1f}/{s['max_drawdown']*100:5.1f}"
        print(row)

    # ---- placebo: circular shifts of the X12/Y5 signal
    print("\nplacebo: circular shifts of the gate X12/Y5 on/off signal")
    on = state_gate(dd, 0.12, 0.05)
    for shift in (21, 42, 63, 126, 189, 252):
        sh = np.roll(on, shift)
        w = weights_from(sh, day_id, n_bars)
        rr = bt.run(ts, opens, closes, w, DEV_START, band=0.02, slippage_bps=1.0)
        s = dev_stats(rr)
        print(f"  shift {shift:4d}: CAGR {s['cagr']*100:6.2f} DD {s['max_drawdown']*100:5.2f} "
              f"Sharpe {s['sharpe']:5.2f} fills {s['fills']:3d}")

    # ---- exposure overlap stats for key variants
    print("\nexposure overlap with baseline")
    base_on = reg.astype(bool)
    for lab, w in key.items():
        on_d = np.zeros(n_days, bool)
        for k in range(n_days):
            on_d[k] = w[first[k], 1] > 0.5
        both = (on_d & base_on).sum()
        print(f"  {lab:18s} on {on_d.mean()*100:5.1f}%  overlap with base {both/n_days*100:5.1f}%  "
              f"joint/sqrt {both/np.sqrt(max(on_d.sum()*base_on.sum(),1)):.3f}")


if __name__ == "__main__":
    main()
