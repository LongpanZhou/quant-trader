"""Ninth exploration: exact plateau/cost/subperiod map for the two candidates."""
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

    FCACHE = {}

    def feats(j):
        if j in FCACHE:
            return FCACHE[j]
        acc = np.full(n, np.nan); vwd = np.full(n, np.nan)
        vwr = np.full(n, np.nan); rop = np.full(n, np.nan)
        for k in range(20, n):
            m = min(int(last[k]) - int(first[k]) + 1, 390)
            if j >= m - 1:
                continue
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
            rop[k] = cl[j] / o[fk, 0] - 1.0
        FCACHE[j] = (acc, vwd, vwr, rop)
        return FCACHE[j]

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

    def metrics(w, slip):
        r = bt.run(ts, o, c, w, DEV_START, band=0.02, slippage_bps=slip)
        return bt.stats(r, BPY), r

    def line(label, w, sub=False):
        s1, r1 = metrics(w, 1.0); s5, _ = metrics(w, 5.0); s10, _ = metrics(w, 10.0)
        print(f"  {label:40s} 1bp {s1['cagr']*100:6.2f}/{s1['max_drawdown']*100:5.1f}/"
              f"{s1['sharpe']:4.2f}  5bp {s5['cagr']*100:6.2f}  10bp {s10['cagr']*100:6.2f}  "
              f"fills {s1['fills']:5d}  TQ {np.mean(w[:,1]>0)*100:4.1f}%")
        if sub:
            for lo, hi in (("2016-01-04", "2019-12-31"), ("2020-01-02", "2021-12-31"),
                           ("2022-01-03", "2023-12-29")):
                m = (r1["ts"] >= pd.Timestamp(lo, tz="America/New_York")) & (
                    r1["ts"] < pd.Timestamp(hi, tz="America/New_York") + pd.Timedelta(days=1))
                x = r1["equity"][m]; tt = r1["ts"][m]
                years = (tt[-1] - tt[0]).total_seconds() / (365.25 * 86400)
                peak = np.maximum.accumulate(x)
                print(f"      {lo[:7]}-{hi[:7]}: CAGR {((x[-1]/x[0])**(1/years)-1)*100:6.2f}%  "
                      f"DD {(-(x/peak-1).min())*100:5.1f}%")
        return s1

    print("=== 13:00 (offset 210) accel plateau ===")
    for j in (195, 210, 225):
        acc, vwd, vwr, rop = feats(j)
        print(f"-- {9+(30+j)//60:02d}:{(30+j)%60:02d} --")
        for th in (0.7, 0.75, 0.8, 0.85, 0.9):
            enter = np.nan_to_num(acc < th, nan=False).astype(bool)
            line(f"accel<{th:.2f}", w_fixed(enter, j))
    print("\nsubperiods of 13:00 accel<0.8:")
    acc, vwd, vwr, rop = feats(210)
    line("13:00 accel<0.8", w_fixed(np.nan_to_num(acc < 0.8, nan=False).astype(bool), 210), sub=True)

    print("\n=== 14:30 (offset 300) accel x vwd plateau ===")
    for j in (285, 300, 315):
        acc, vwd, vwr, rop = feats(j)
        print(f"-- {9+(30+j)//60:02d}:{(30+j)%60:02d} --")
        for th in (1.0, 1.1, 1.2, 1.3, 1.4):
            for dv in (-0.001, 0.0):
                enter = np.nan_to_num((acc < th) & (vwd > dv), nan=False).astype(bool)
                line(f"accel<{th:.1f} vwd>{dv*1e4:+.0f}bp", w_fixed(enter, j))
    print("\nsubperiods of 14:30 accel<1.3 vwd>-10bp:")
    acc, vwd, vwr, rop = feats(300)
    line("14:30 accel<1.3 vwd>-10bp",
         w_fixed(np.nan_to_num((acc < 1.3) & (vwd > -0.001), nan=False).astype(bool), 300), sub=True)
    print("\nsubperiods of 14:30 accel<1.0 vwd>0:")
    line("14:30 accel<1.0 vwd>0",
         w_fixed(np.nan_to_num((acc < 1.0) & (vwd > 0), nan=False).astype(bool), 300), sub=True)

    # yearly for the selected cell
    w = w_fixed(np.nan_to_num((acc < 1.3) & (vwd > -0.001), nan=False).astype(bool), 300)
    s, r = metrics(w, 1.0)
    i0 = bt.start_index(ts, DEV_START)
    yr = bt.yearly(r["ts"], r["equity"], c[i0:, 1])
    print("yearly 14:30 accel<1.3 vwd>-10bp:",
          {k: round(v["strategy"]*100, 1) for k, v in yr.items()})


if __name__ == "__main__":
    main()
