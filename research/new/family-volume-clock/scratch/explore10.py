"""Tenth exploration: attribution of acceleration vs sign, and winner correlations."""
from __future__ import annotations

import json
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
WINNERS = ["ratio-froth", "vol-scaled-crash-stop", "relative-value-tqqq",
           "fomc-opex-window", "family-session-timing", "family-short-reversal",
           "family-rebalance-flow", "family-intraday-microstructure-day",
           "family-ml-microstructure"]


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

    FC = {}
    def feats(j):
        if j in FC:
            return FC[j]
        acc = np.full(n, np.nan); vwd = np.full(n, np.nan)
        rop = np.full(n, np.nan)
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
            rop[k] = cl[j] / o[fk, 0] - 1.0
        FC[j] = (acc, vwd, rop)
        return FC[j]

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

    def ev(w, slip=1.0):
        r = bt.run(ts, o, c, w, DEV_START, band=0.02, slippage_bps=slip)
        return bt.stats(r, BPY), r

    def line(label, enter, j):
        w = w_fixed(np.nan_to_num(enter, nan=False).astype(bool), j)
        s1, _ = ev(w, 1.0); s5, _ = ev(w, 5.0); s10, _ = ev(w, 10.0)
        print(f"  {label:44s} 1bp {s1['cagr']*100:6.2f}/{s1['max_drawdown']*100:5.1f}/"
              f"{s1['sharpe']:4.2f}  5bp {s5['cagr']*100:6.2f}  10bp {s10['cagr']*100:6.2f}  "
              f"fills {s1['fills']:5d}  TQ {np.mean(w[:,1]>0)*100:4.1f}%")
        return s1

    print("=== 13:00 attribution ===")
    acc, vwd, rop = feats(210)
    line("all sessions", np.ones(n, bool), 210)
    line("accel<0.8 only", acc < 0.8, 210)
    line("vwd>0 only", vwd > 0, 210)
    line("vwd>-10bp only", vwd > -0.001, 210)
    line("rop>0 only", rop > 0, 210)
    line("rop>-20bp only", rop > -0.002, 210)
    line("accel<0.8 & vwd>0", (acc < 0.8) & (vwd > 0), 210)
    line("accel<0.8 & vwd>-10bp", (acc < 0.8) & (vwd > -0.001), 210)
    line("accel<0.8 & rop>-20bp", (acc < 0.8) & (rop > -0.002), 210)
    line("accel>=0.8 only", acc >= 0.8, 210)
    line("accel<0.8 & vwd<0", (acc < 0.8) & (vwd < 0), 210)

    print("\n=== 14:30 attribution ===")
    acc, vwd, rop = feats(300)
    line("all sessions", np.ones(n, bool), 300)
    line("accel<1.3 only", acc < 1.3, 300)
    line("accel<1.4 only", acc < 1.4, 300)
    line("vwd>-10bp only", vwd > -0.001, 300)
    line("vwd>0 only", vwd > 0, 300)
    line("rop>-20bp only", rop > -0.002, 300)
    line("rop>0 only", rop > 0, 300)
    line("accel<1.3 & vwd>-10bp", (acc < 1.3) & (vwd > -0.001), 300)
    line("accel<1.3 & vwd>0", (acc < 1.3) & (vwd > 0), 300)
    line("accel<1.3 & rop>-20bp", (acc < 1.3) & (rop > -0.002), 300)
    line("accel<1.4 & vwd>-10bp", (acc < 1.4) & (vwd > -0.001), 300)
    line("accel<1.0 & vwd>0", (acc < 1.0) & (vwd > 0), 300)

    # correlations of the two main candidates with winners
    print("\n=== correlations with winners ===")
    cands = {}
    acc210, vwd210, rop210 = feats(210)
    cands["vc13_accel080"] = w_fixed(np.nan_to_num(acc210 < 0.8, nan=False).astype(bool), 210)
    acc300, vwd300, rop300 = feats(300)
    cands["vc1430_accel130_vwd10"] = w_fixed(
        np.nan_to_num((acc300 < 1.3) & (vwd300 > -0.001), nan=False).astype(bool), 300)
    cands["vc1430_accel100_vwd0"] = w_fixed(
        np.nan_to_num((acc300 < 1.0) & (vwd300 > 0), nan=False).astype(bool), 300)
    cands["vc1430_rop20"] = w_fixed(np.nan_to_num(rop300 > -0.002, nan=False).astype(bool), 300)

    for name, w in cands.items():
        s, r = ev(w, 1.0)
        eq = pd.Series(r["equity"], index=pd.to_datetime(r["ts"]))
        dr = eq.groupby(eq.index.date).last().pct_change().dropna()
        corrs = {}
        for win in WINNERS:
            p = ROOT / "research" / "new" / "curves" / f"{win}.json"
            d = json.loads(p.read_text())
            ws = pd.Series(d["values"], index=pd.to_datetime(d["dates"]))
            wr = ws.pct_change().dropna()
            j = dr.index.intersection(wr.index)
            corrs[win] = float(dr.loc[j].corr(wr.loc[j]))
        print(f"\n{name}: CAGR {s['cagr']*100:.2f}% DD {s['max_drawdown']*100:.1f}% "
              f"Sh {s['sharpe']:.2f} fills {s['fills']}")
        for k, v in sorted(corrs.items(), key=lambda x: -abs(x[1])):
            print(f"    {k:38s} {v:+.3f}")


if __name__ == "__main__":
    main()
