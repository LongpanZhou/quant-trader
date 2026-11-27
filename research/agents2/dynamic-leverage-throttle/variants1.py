"""First pass: vol-target / drawdown / trend / Kelly throttles on the winner.

Usage: python variants1.py [batch]
Batches: vol, dd, trend, kelly, all
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402

HERE = Path(__file__).resolve().parent
START10, START5, END = "2017-01-03", "2021-10-25", "2026-10-23"
BARS_PER_YEAR = 252 * 390
STOP, SMA_N, MA_FAST, ARM_BUF = 0.04, 165, 20, 0.01
G = {}


def load_panel():
    z = np.load(HERE / "panel.npz")
    ts = (pd.DatetimeIndex(z["ts"].astype("int64"))
          .tz_localize("UTC").tz_convert("America/New_York"))
    return ts, z["opens"].astype(float), z["closes"].astype(float)


def day_bounds(dates):
    first = np.flatnonzero(np.r_[True, dates[1:] != dates[:-1]])
    last = np.r_[first[1:] - 1, len(dates) - 1]
    return first, last


def roll_sma(x, n):
    return pd.Series(x).rolling(n).mean().to_numpy()


def prev(a):
    return np.r_[np.nan, a[:-1]]


def build_minute_weights(day_tq, day_qq, ts, opens, closes):
    first, last = G["first"], G["last"]
    qc, tc = closes[:, 0], closes[:, 1]
    n = len(ts)
    w = np.zeros((n, 3))
    stops = 0
    for k in range(len(first)):
        f, l = first[k], last[k]
        wt, wq = day_tq[k], day_qq[k]
        if wt <= 0 and wq <= 0:
            w[f:l + 1, 2] = 1.0
            continue
        armed = G["arm"][k]
        if not armed:
            w[f:l + 1, 0] = wq
            w[f:l + 1, 1] = wt
            w[f:l + 1, 2] = 1.0 - wt - wq
            continue
        base = opens[f, 1]
        state = True
        for i in range(f, l + 1):
            if state and tc[i] < base * (1.0 - STOP):
                state = False
                stops += 1
            if state:
                w[i, 0] = wq
                w[i, 1] = wt
                w[i, 2] = 1.0 - wt - wq
            else:
                w[i, 2] = 1.0
    return w, stops


def main():
    batch = sys.argv[1] if len(sys.argv) > 1 else "all"
    t0 = time.time()
    ts, opens, closes = load_panel()
    dates = np.array([t.date() for t in ts])
    first, last = day_bounds(dates)
    n_days = len(first)
    G["first"], G["last"] = first, last
    dq, dt, db = closes[last, 0], closes[last, 1], closes[last, 2]
    ma20 = roll_sma(dq, MA_FAST)
    G["arm"] = closes[first, 0] < prev(ma20) * (1.0 + ARM_BUF)
    sma165 = roll_sma(dq, SMA_N)
    risk_on = np.zeros(n_days, bool)
    risk_on[1:] = dq[:-1] > prev(sma165)[1:]

    ret_t = np.r_[np.nan, np.log(dt[1:] / dt[:-1])]
    ret_q = np.r_[np.nan, np.log(dq[1:] / dq[:-1])]
    vol20 = prev(pd.Series(ret_t).rolling(20).std().to_numpy() * np.sqrt(252))
    vol10 = prev(pd.Series(ret_t).rolling(10).std().to_numpy() * np.sqrt(252))
    vol60 = prev(pd.Series(ret_t).rolling(60).std().to_numpy() * np.sqrt(252))
    vol20q = prev(pd.Series(ret_q).rolling(20).std().to_numpy() * np.sqrt(252))
    dd60 = prev((dq / pd.Series(dq).rolling(60).max() - 1.0).to_numpy())
    dd120 = prev((dq / pd.Series(dq).rolling(120).max() - 1.0).to_numpy())
    dd252 = prev((dq / pd.Series(dq).rolling(252).max() - 1.0).to_numpy())
    trend_p = prev(dq / sma165 - 1.0)
    mu60 = prev(pd.Series(ret_t).rolling(60).mean().to_numpy())
    var60 = prev(pd.Series(ret_t).rolling(60).var().to_numpy())
    mu120 = prev(pd.Series(ret_t).rolling(120).mean().to_numpy())
    var120 = prev(pd.Series(ret_t).rolling(120).var().to_numpy())

    print(f"loaded {len(ts):,} bars, {n_days} sessions, {time.time()-t0:.0f}s; "
          f"armed days {int(G['arm'].sum())}", flush=True)
    print("vol20 TQQQ pct", np.round(np.nanpercentile(vol20, [5, 25, 50, 75, 95]), 3), flush=True)
    print("vol60 TQQQ pct", np.round(np.nanpercentile(vol60, [5, 25, 50, 75, 95]), 3), flush=True)
    print("vol20 QQQ pct", np.round(np.nanpercentile(vol20q, [5, 25, 50, 75, 95]), 3), flush=True)
    print("trend pct", np.round(np.nanpercentile(trend_p, [5, 25, 50, 75, 95]), 3), flush=True)

    def report(name, day_tq, day_qq=None):
        if day_qq is None:
            day_qq = np.zeros(n_days)
        day_tq = np.where(risk_on, np.clip(day_tq, 0, 1), 0.0)
        day_qq = np.where(risk_on, np.clip(day_qq, 0, 1), 0.0)
        tot = day_tq + day_qq
        over = tot > 1.0
        if over.any():
            day_tq[over] /= tot[over]
            day_qq[over] /= tot[over]
        w, ns = build_minute_weights(day_tq, day_qq, ts, opens, closes)
        vals = []
        for start in (START10, START5):
            r = bt.run(ts, opens, closes, w, start, band=0.02, slippage_bps=1.0)
            s = bt.stats(r, BARS_PER_YEAR)
            vals.append((s["cagr"], s["max_drawdown"], s["sharpe"],
                         s["cagr"] / s["max_drawdown"]))
        a, b = vals
        print(f"{name:40s} stops {ns:4d} | "
              f"10y {a[0]*100:6.2f}/{a[1]*100:5.2f} Sh {a[2]:.2f} Cal {a[3]:.2f} | "
              f"5y {b[0]*100:6.2f}/{b[1]*100:5.2f} Sh {b[2]:.2f} Cal {b[3]:.2f}",
              flush=True)
        return w

    if batch in ("vol", "all"):
        report("winner 100% TQQQ", np.ones(n_days))
        print("-- vol target (TQQQ, residual BIL, daily-close vol) --", flush=True)
        for tv in (0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70, 0.80):
            report(f"voltarget20 {tv:.2f}", np.minimum(1.0, tv / vol20))
        for tv in (0.45, 0.55, 0.65):
            report(f"voltarget60 {tv:.2f}", np.minimum(1.0, tv / vol60))

    if batch in ("dd", "all"):
        print("-- drawdown throttle (QQQ dd from high, w=1-k*|dd|) --", flush=True)
        for win, dd in (("60d", dd60), ("120d", dd120), ("252d", dd252)):
            for k in (0.5, 1.0, 2.0):
                wgt = np.clip(1.0 - k * np.maximum(-dd, 0.0), 0.25, 1.0)
                report(f"dd{win} k={k:.1f}", wgt)

    if batch in ("trend", "all"):
        print("-- trend strength (qqq/sma165-1) --", flush=True)
        for band in (0.02, 0.04, 0.06):
            for floor in (0.3, 0.5):
                wgt = np.clip(floor + (1 - floor) * trend_p / band, floor, 1.0)
                report(f"trend band={band:.2f} floor={floor:.1f}", wgt)

    if batch in ("neighbors", "all"):
        print("-- neighbours: pure vol target and core blends --", flush=True)
        for tv in (0.58, 0.60, 0.62, 0.65, 0.68, 0.72):
            report(f"vt{tv:.2f} pure", np.minimum(1.0, tv / vol20))
        for core in (0.2, 0.3, 0.4):
            wgt = core + (1.0 - core) * np.minimum(1.0, 0.65 / vol20)
            report(f"vt65 core={core:.1f}", wgt)
        core = 0.3
        wgt = core + (1.0 - core) * np.minimum(1.0, 0.65 / vol20)
        report("vt65 core0.3 + qqq-res", wgt, 1.0 - wgt)
        vol30 = prev(pd.Series(ret_t).rolling(30).std().to_numpy() * np.sqrt(252))
        report("vt65 vol30", np.minimum(1.0, 0.65 / vol30))

    if batch in ("extra", "all"):
        print("-- extra neighbours --", flush=True)
        vol30 = prev(pd.Series(ret_t).rolling(30).std().to_numpy() * np.sqrt(252))
        for tv, vv, core in ((0.65, vol30, 0.3), (0.70, vol20, 0.3),
                             (0.60, vol20, 0.3), (0.65, vol30, 0.5),
                             (0.70, vol30, 0.3)):
            wgt = core + (1.0 - core) * np.minimum(1.0, tv / vv)
            tag = "vol30" if vv is vol30 else "vol20"
            report(f"vt{tv:.2f} {tag} core={core:.1f}", wgt)
        wgt = 0.3 + 0.7 * np.minimum(1.0, 0.65 / vol20)
        report("vt65 core0.3 qqq10", wgt, 0.1 * (1.0 - wgt))

    if batch in ("kelly", "all"):
        print("-- fractional Kelly (TQQQ daily mu/var) --", flush=True)
        for win, mu, var in (("60d", mu60, var60), ("120d", mu120, var120)):
            for frac in (0.25, 0.5, 1.0):
                f = frac * np.maximum(mu, 0) / var
                report(f"kelly {win} frac={frac:.2f}", np.clip(f, 0.0, 1.0))

    if batch in ("combo", "all"):
        print("-- vol target + QQQ residual / partial / dd --", flush=True)
        for tv in (0.55, 0.65, 0.70):
            wt = np.minimum(1.0, tv / vol20)
            report(f"vt{tv:.2f} qqq-residual", wt, 1.0 - wt)
        wt65 = np.minimum(1.0, 0.65 / vol20)
        report("vt65 qqq-half", wt65, 0.5 * (1.0 - wt65))
        for lam in (0.5, 0.7):
            wgt = 1.0 - lam * (1.0 - np.minimum(1.0, 0.65 / vol20))
            report(f"vt65 partial lam={lam:.1f}", wgt)
        report("vt70 dd60 k=0.5",
               np.minimum(1.0, 0.70 / vol20)
               * np.clip(1.0 - 0.5 * np.maximum(-dd60, 0.0), 0.25, 1.0))
        report("vt65 vol10", np.minimum(1.0, 0.65 / vol10))
        report("vt65 trend-gate>5%",
               np.where(trend_p > 0.05, 1.0, np.minimum(1.0, 0.65 / vol20)))

    print(f"done {time.time()-t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
