"""Sixth exploration: attribution and volume-acceleration variants.

Key questions:
 1. Does the volume-clock decision time beat a fixed-time filter?
 2. Is the edge just "do not hold overnight after a down day"?
 3. Does volume acceleration at the clock crossing add information?
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402

DEV_START, DEV_END = "2016-01-04", "2023-12-29"
BPY = 252 * 390


def load_all():
    ts, o, c = bt.panel(("QQQ", "TQQQ", "BIL"), DEV_START, DEV_END, "1min", warmup_days=60)
    lo, hi = pd.Timestamp(ts[0]), pd.Timestamp(ts[-1])
    df = bt.load_1m("QQQ")
    df = df[(df["ts"] >= lo) & (df["ts"] <= hi)].set_index("ts").reindex(ts)
    vol = np.nan_to_num(df["volume"].to_numpy(dtype=float), nan=0.0)
    return ts, o, c, vol


def prep(ts, o, c, vol):
    dates, first, last = bt.day_bounds(ts)
    n = len(first)
    V = np.zeros((n, 390))
    for k in range(n):
        f, l = int(first[k]), int(last[k])
        m = min(l - f + 1, 390)
        V[k, :m] = vol[f:f + m]
    CUM = np.cumsum(V, axis=1)
    dayvol = V.sum(axis=1)
    med_day = np.full(n, np.nan)
    for k in range(n):
        if k >= 20:
            med_day[k] = np.median(dayvol[k - 20:k])
    return dates, np.asarray(first), np.asarray(last), V, CUM, dayvol, med_day


def main():
    ts, o, c, vol = load_all()
    dates, first, last, V, CUM, dayvol, med_day = prep(ts, o, c, vol)
    n = len(first)
    o = np.asarray(o, float); c = np.asarray(c, float)

    def tol(x):
        arr = np.full(n, np.nan)
        for k in range(n):
            m = min(int(last[k]) - int(first[k]) + 1, 390)
            tgt = x * med_day[k] if np.isfinite(med_day[k]) else np.nan
            if np.isfinite(tgt) and tgt > 0:
                j = int(np.searchsorted(CUM[k, :m], tgt))
                if 0 < j < m - 1:
                    arr[k] = j
        return arr

    J = {x: tol(x) for x in (0.50, 0.60, 0.75, 1.00)}

    def eval_w(w, label, slip=1.0):
        r = bt.run(ts, o, c, w, DEV_START, band=0.02, slippage_bps=slip)
        s = bt.stats(r, BPY)
        print(f"  {label:52s} CAGR {s['cagr']*100:6.2f}% DD {s['max_drawdown']*100:5.1f}% "
              f"Sh {s['sharpe']:4.2f} fills {s['fills']:5d} turnover {s['turnover']:7.0f} "
              f"TQQQbars {np.mean(w[:,1]>0)*100:4.1f}%")
        return s

    def overnight_mask(enter, label):
        """enter[k] -> buy at session k decision, hold through close, sell next open."""
        w = np.zeros((len(ts), 3))
        for k in range(n - 1):
            if not enter[k]:
                continue
            j = int(J[0.75][k]) if np.isfinite(J[0.75][k]) else -1
            # placeholder, replaced by caller-specific J
        return w

    def overnight_at(enter, jarr, label, col=1):
        w = np.zeros((len(ts), 3))
        for k in range(n - 1):
            if not enter[k]:
                continue
            j = int(jarr[k]) if np.isfinite(jarr[k]) else -1
            if j <= 0:
                continue
            fk, lk = int(first[k]), int(last[k])
            w[fk + j, col] = 1.0
            w[fk + j + 1:lk + 1, col] = 1.0
            w[lk, col] = 0.0
        w[-1] = w[-2]
        return eval_w(w, label)

    print("=== attribution: fixed-time vs volume-clock, r_open > -20bp ===")
    for jfix in (150, 180, 210, 240, 270, 285, 300):
        enter = np.zeros(n, bool)
        for k in range(n):
            fk, lk = int(first[k]), int(last[k])
            m = min(lk - fk + 1, 390)
            if jfix >= m - 1:
                continue
            enter[k] = c[fk + jfix, 0] / o[fk, 0] - 1.0 > -0.002
        jarr = np.full(n, jfix)
        overnight_at(enter, jarr, f"fixed {9+(30+jfix)//60:02d}:{(30+jfix)%60:02d} r_open>-20bp")
    for x in (0.50, 0.60, 0.75, 1.00):
        enter = np.zeros(n, bool)
        for k in range(n):
            j = J[x][k]
            if not np.isfinite(j):
                continue
            fk = int(first[k])
            enter[k] = c[fk + int(j), 0] / o[fk, 0] - 1.0 > -0.002
        overnight_at(enter, J[x], f"x{x:.2f} r_open>-20bp")

    print("\n=== attribution: day-return / close-position filters ===")
    # r_day > threshold at close, enter at last bar open
    for th in (-0.005, -0.002, 0.0, 0.002):
        enter = np.zeros(n, bool)
        for k in range(n):
            fk, lk = int(first[k]), int(last[k])
            enter[k] = c[lk, 0] / o[fk, 0] - 1.0 > th
        jarr = np.full(n, 388)
        overnight_at(enter, jarr, f"close r_day>{th*100:+.1f}%")

    print("\n=== volume acceleration at the clock crossing ===")
    # build accel for each x
    ACC = {}
    for x in (0.50, 0.60, 0.75):
        a = np.full(n, np.nan)
        for k in range(20, n):
            j = J[x][k]
            if not np.isfinite(j):
                continue
            j = int(j)
            w0 = max(0, j - 29)
            hist = [V[kk, w0:j + 1].sum() for kk in range(k - 20, k)]
            med = np.median(hist)
            if med > 0:
                a[k] = V[k, w0:j + 1].sum() / med
        ACC[x] = a
        print(f"x{x:.2f} accel quantiles: "
              f"{np.nanpercentile(a,[5,20,50,80,95]).round(2)}")

    # long if accel < th, or skip if accel > th
    for x in (0.50, 0.60, 0.75):
        for th in (0.8, 1.0, 1.2, 1.5, 2.0):
            enter = np.zeros(n, bool)
            for k in range(n):
                if np.isfinite(ACC[x][k]):
                    enter[k] = ACC[x][k] < th
            overnight_at(enter, J[x], f"x{x:.2f} accel<{th:.1f}")
        for th in (1.2, 1.5, 2.0):
            enter = np.zeros(n, bool)
            for k in range(n):
                enter[k] = not (np.isfinite(ACC[x][k]) and ACC[x][k] > th)
            overnight_at(enter, J[x], f"x{x:.2f} skip accel>{th:.1f}")

    print("\n=== accel x r_open interaction at x0.75 ===")
    a = ACC[0.75]
    for alab, am in (("accel<1.0", a < 1.0), ("accel 1-1.5", (a >= 1.0) & (a < 1.5)),
                     ("accel>=1.5", a >= 1.5)):
        for rlab, rm in (("r>-20bp", np.zeros(n, bool)), ("r<=-20bp", np.zeros(n, bool))):
            pass
    # simple table
    rec = []
    for k in range(20, n - 1):
        j = J[0.75][k]
        if not np.isfinite(j) or not np.isfinite(a[k]):
            continue
        fk, lk = int(first[k]), int(last[k])
        fn = int(first[k + 1])
        rec.append((a[k], c[fk + int(j), 0] / o[fk, 0] - 1.0,
                    o[fn, 1] / c[fk + int(j), 1] - 1.0))
    R = np.array(rec)
    for alo, ahi in ((0, 1.0), (1.0, 1.5), (1.5, 99)):
        for rlo, rhi in ((-9, -0.002), (-0.002, 9)):
            m = (R[:, 0] >= alo) & (R[:, 0] < ahi) & (R[:, 1] >= rlo) & (R[:, 1] < rhi)
            x = R[m, 2]
            print(f"  accel[{alo},{ahi}) r_open[{rlo},{rhi}): n={len(x):4d} "
                  f"mean {x.mean()*1e4:7.2f}bp t={x.mean()/(x.std(ddof=1)/np.sqrt(len(x))):5.2f}")


if __name__ == "__main__":
    main()
