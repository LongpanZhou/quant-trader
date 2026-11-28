"""Seventh exploration: fixed-time volume acceleration + sign, and state machines."""
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
    return dates, np.asarray(first), np.asarray(last), V


def main():
    ts, o, c, vol = load_all()
    dates, first, last, V = prep(ts, o, c, vol)
    n = len(first)
    o = np.asarray(o, float); c = np.asarray(c, float)

    def eval_w(w, label, slip=1.0, quiet=False):
        r = bt.run(ts, o, c, w, DEV_START, band=0.02, slippage_bps=slip)
        s = bt.stats(r, BPY)
        if not quiet:
            print(f"  {label:58s} CAGR {s['cagr']*100:6.2f}% DD {s['max_drawdown']*100:5.1f}% "
                  f"Sh {s['sharpe']:4.2f} fills {s['fills']:5d} TO {s['turnover']:7.0f} "
                  f"TQ {np.mean(w[:,1]>0)*100:4.1f}%")
        return s

    # feature table at each fixed time
    def features(j):
        acc = np.full(n, np.nan); vwd = np.full(n, np.nan)
        vwr = np.full(n, np.nan); rop = np.full(n, np.nan)
        for k in range(20, n):
            m = min(int(last[k]) - int(first[k]) + 1, 390)
            if j >= m - 1:
                continue
            fk = int(first[k])
            cl = c[fk:fk + m, 0]
            v = V[k, :m]
            w0 = max(0, j - 29)
            hist = [V[kk, w0:j + 1].sum() for kk in range(k - 20, k)]
            med = np.median(hist)
            if med > 0:
                acc[k] = v[w0:j + 1].sum() / med
            vw = np.sum(v[:j + 1] * cl[:j + 1]) / max(v[:j + 1].sum(), 1)
            vwd[k] = cl[j] / vw - 1.0
            rr = np.diff(np.log(cl[w0:j + 1]))
            vv = v[w0 + 1:j + 1]
            vwr[k] = float(np.sum(rr * vv) / max(vv.sum(), 1)) if len(vv) else 0.0
            rop[k] = cl[j] / o[fk, 0] - 1.0
        return acc, vwd, vwr, rop

    def w_fixed(enter, j):
        w = np.zeros((len(ts), 3))
        for k in range(n - 1):
            if not enter[k]:
                continue
            m = min(int(last[k]) - int(first[k]) + 1, 390)
            if j >= m - 1:
                continue
            fk, lk = int(first[k]), int(last[k])
            w[fk + j, 1] = 1.0
            w[fk + j + 1:lk + 1, 1] = 1.0
            w[lk, 1] = 0.0
        w[-1] = w[-2]
        return w

    print("=== fixed-time acceleration + sign, overnight hold (1bp) ===")
    times = (150, 180, 210, 240, 270, 300)
    for j in times:
        acc, vwd, vwr, rop = features(j)
        lab = f"{9+(30+j)//60:02d}:{(30+j)%60:02d}"
        print(f"\n-- {lab} --")
        for th in (0.8, 1.0, 1.2, 1.5):
            for sname, sm in (("accel<th", acc < th), ("accel>th", acc > th)):
                enter = np.nan_to_num(sm, nan=False).astype(bool)
                eval_w(w_fixed(enter, j), f"{sname} {th:.1f}")
            for sname, sm in (("accel<th & vwd>0", (acc < th) & (vwd > 0)),
                              ("accel>th & vwd>0", (acc > th) & (vwd > 0)),
                              ("accel<th & vwr>0", (acc < th) & (vwr > 0)),
                              ("accel>th & vwr>0", (acc > th) & (vwr > 0))):
                enter = np.nan_to_num(sm, nan=False).astype(bool)
                eval_w(w_fixed(enter, j), f"{sname} {th:.1f}")

    # best-looking: 14:30 accel<1.2, plus sign variants.  Print 5bp/10bp.
    print("\n=== cost sensitivity of selected fixed-time cells ===")
    j = 300
    acc, vwd, vwr, rop = features(j)
    cells = {
        "accel<1.2": acc < 1.2,
        "accel<1.2 & vwd>0": (acc < 1.2) & (vwd > 0),
        "accel<1.2 & vwr>0": (acc < 1.2) & (vwr > 0),
        "accel<1.0 & vwd>0": (acc < 1.0) & (vwd > 0),
        "accel<1.2 & rop>-20bp": (acc < 1.2) & (rop > -0.002),
        "accel>1.2 & vwd>0": (acc > 1.2) & (vwd > 0),
    }
    for name, cm in cells.items():
        enter = np.nan_to_num(cm, nan=False).astype(bool)
        w = w_fixed(enter, j)
        for slip in (1.0, 5.0, 10.0):
            eval_w(w, f"14:30 {name} @{slip:.0f}bp", slip=slip)

    # clock-crossing accel<1.2 and sign, for comparison
    print("\n=== clock-crossing accel (x0.75) + sign, overnight ===")
    def tol(x):
        arr = np.full(n, np.nan)
        CUM = np.cumsum(V, axis=1)
        dayvol = V.sum(axis=1)
        med = np.full(n, np.nan)
        for k in range(20, n):
            med[k] = np.median(dayvol[k - 20:k])
        for k in range(n):
            m = min(int(last[k]) - int(first[k]) + 1, 390)
            tgt = x * med[k] if np.isfinite(med[k]) else np.nan
            if np.isfinite(tgt) and tgt > 0:
                jj = int(np.searchsorted(CUM[k, :m], tgt))
                if 0 < jj < m - 1:
                    arr[k] = jj
        return arr
    J = tol(0.75)
    acc = np.full(n, np.nan); vwd = np.full(n, np.nan); vwr = np.full(n, np.nan)
    for k in range(20, n):
        j = J[k]
        if not np.isfinite(j):
            continue
        j = int(j); m = min(int(last[k]) - int(first[k]) + 1, 390)
        fk = int(first[k]); cl = c[fk:fk + m, 0]; v = V[k, :m]
        w0 = max(0, j - 29)
        hist = [V[kk, w0:j + 1].sum() for kk in range(k - 20, k)]
        med = np.median(hist)
        if med > 0:
            acc[k] = v[w0:j + 1].sum() / med
        vw = np.sum(v[:j + 1] * cl[:j + 1]) / max(v[:j + 1].sum(), 1)
        vwd[k] = cl[j] / vw - 1.0
        rr = np.diff(np.log(cl[w0:j + 1])); vv = v[w0 + 1:j + 1]
        vwr[k] = float(np.sum(rr * vv) / max(vv.sum(), 1)) if len(vv) else 0.0

    def w_clock(enter):
        w = np.zeros((len(ts), 3))
        for k in range(n - 1):
            if not enter[k] or not np.isfinite(J[k]):
                continue
            j = int(J[k]); fk, lk = int(first[k]), int(last[k])
            w[fk + j, 1] = 1.0
            w[fk + j + 1:lk + 1, 1] = 1.0
            w[lk, 1] = 0.0
        w[-1] = w[-2]
        return w
    for name, cm in {
        "accel<1.2": acc < 1.2,
        "accel<1.2 & vwd>0": (acc < 1.2) & (vwd > 0),
        "accel<1.2 & vwr>0": (acc < 1.2) & (vwr > 0),
        "accel<1.2 & vwd>-10bp": (acc < 1.2) & (vwd > -0.001),
    }.items():
        enter = np.nan_to_num(cm, nan=False).astype(bool)
        for slip in (1.0, 5.0, 10.0):
            eval_w(w_clock(enter), f"x0.75 {name} @{slip:.0f}bp", slip=slip)


if __name__ == "__main__":
    main()
