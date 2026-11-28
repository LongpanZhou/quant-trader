"""Eleventh exploration: is the 13:00 acceleration effect a volatility proxy?

Also: hysteresis deadband variants and winner correlations (fixed index types).
"""
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

    j = 210  # 13:00
    acc = np.full(n, np.nan); vwd = np.full(n, np.nan); rop = np.full(n, np.nan)
    rv = np.full(n, np.nan); overnight = np.full(n, np.nan); intraday = np.full(n, np.nan)
    for k in range(20, n - 1):
        m = min(int(last[k]) - int(first[k]) + 1, 390)
        if j >= m - 1:
            continue
        fk = int(first[k]); cl = c[fk:fk + m, 0]; v = V[k, :m]
        w0 = j - 29
        hist = [V[kk, w0:j + 1].sum() for kk in range(k - 20, k)]
        med = np.median(hist)
        if med > 0:
            acc[k] = v[w0:j + 1].sum() / med
        vw = np.sum(v[:j + 1] * cl[:j + 1]) / max(v[:j + 1].sum(), 1)
        vwd[k] = cl[j] / vw - 1.0
        rop[k] = cl[j] / o[fk, 0] - 1.0
        rr = np.diff(np.log(cl[:j + 1]))
        rv[k] = np.std(rr, ddof=0) * np.sqrt(390)  # per-session vol scale
        fn, lk = int(first[k + 1]), int(last[k])
        overnight[k] = o[fn, 1] / c[lk, 1] - 1.0
        intraday[k] = c[lk, 1] / c[fk + j, 1] - 1.0

    d = pd.DataFrame(dict(k=np.arange(n), acc=acc, vwd=vwd, rop=rop, rv=rv,
                          overnight=overnight, intraday=intraday)).dropna()
    print(f"n={len(d)}")
    print(f"corr(accel, log rv)={d.acc.corr(np.log(d.rv)):.3f}")
    print(f"corr(accel, abs r_open)={d.acc.corr(d.rop.abs()):.3f}")
    print(f"corr(accel, vwd)={d.acc.corr(d.vwd):.3f}")

    print("\n--- accel quintiles: overnight / intraday / rv / |r_open| ---")
    d["aq"] = pd.qcut(d.acc, 5, labels=False)
    g = d.groupby("aq").agg(n=("acc", "size"), acc=("acc", "mean"),
                            on_bp=("overnight", lambda x: x.mean()*1e4),
                            id_bp=("intraday", lambda x: x.mean()*1e4),
                            rv=("rv", "mean"), absrop=("rop", lambda x: x.abs().mean()*1e4))
    print(g.round(4))

    print("\n--- rv quintiles: overnight ---")
    d["vq"] = pd.qcut(np.log(d.rv), 5, labels=False)
    g2 = d.groupby("vq").agg(n=("rv", "size"), rv=("rv", "mean"),
                             on_bp=("overnight", lambda x: x.mean()*1e4),
                             t=("overnight", lambda x: x.mean()/(x.std(ddof=1)/np.sqrt(len(x)))))
    print(g2.round(3))

    print("\n--- double sort: accel low/high x rv low/high ---")
    d["a_lo"] = d.acc < d.acc.median()
    d["v_lo"] = np.log(d.rv) < np.log(d.rv).median()
    for a in (True, False):
        for vv in (True, False):
            x = d.loc[(d.a_lo == a) & (d.v_lo == vv), "overnight"]
            print(f"  accel{'low ' if a else 'high'} rv{'low ' if vv else 'high'}: "
                  f"n={len(x):4d} mean {x.mean()*1e4:7.2f}bp "
                  f"t={x.mean()/(x.std(ddof=1)/np.sqrt(len(x))):5.2f}")

    # OLS: overnight ~ const + accel + log rv + |r_open|
    X = np.column_stack([np.ones(len(d)), d.acc, np.log(d.rv), d.rop.abs()])
    y = d.overnight.to_numpy()
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ beta
    s2 = resid @ resid / (len(d) - X.shape[1])
    cov = s2 * np.linalg.inv(X.T @ X)
    se = np.sqrt(np.diag(cov))
    print("\n--- OLS overnight (bp) on accel, log rv, |r_open| ---")
    for name, b, s in zip(("const", "accel", "log_rv", "abs_r_open"), beta, se):
        print(f"  {name:12s} {b*1e4:9.3f} bp  t={b/s:6.2f}")

    # add interaction: low accel dummy x low rv dummy
    X2 = np.column_stack([np.ones(len(d)), (d.acc < 0.8).astype(float),
                          np.log(d.rv), d.rop.abs()])
    beta2, *_ = np.linalg.lstsq(X2, y, rcond=None)
    resid2 = y - X2 @ beta2
    s22 = resid2 @ resid2 / (len(d) - X2.shape[1])
    se2 = np.sqrt(np.diag(s22 * np.linalg.inv(X2.T @ X2)))
    print("\n--- OLS with accel<0.8 dummy ---")
    for name, b, s in zip(("const", "accel<0.8", "log_rv", "abs_r_open"), beta2, se2):
        print(f"  {name:12s} {b*1e4:9.3f} bp  t={b/s:6.2f}")

    # worst overnight days by accel bucket
    print("\n--- worst 10 overnight returns: accel, rv, date ---")
    worst = d.nsmallest(10, "overnight")
    for _, r in worst.iterrows():
        k = int(r.k)
        print(f"  {dates[first[k]]} on {r.overnight*100:7.2f}% accel {r.acc:5.2f} rv {r.rv:.4f}")

    # hysteresis state machines
    print("\n=== hysteresis around 13:00 ===")
    def w_state(enter, exit_, j):
        w = np.zeros((len(ts), 3))
        state = 0
        for k in range(n - 1):
            m = min(int(last[k]) - int(first[k]) + 1, 390)
            if j >= m - 1:
                continue
            if state == 0 and enter[k]:
                state = 1
            elif state == 1 and exit_[k]:
                state = 0
            if state:
                fk, lk = int(first[k]), int(last[k])
                w[fk + j, 1] = 1.0
                w[fk + j + 1:lk + 1, 1] = 1.0
                w[lk, 1] = 0.0
        w[-1] = w[-2]
        return w

    def ev(w, slip):
        r = bt.run(ts, o, c, w, DEV_START, band=0.02, slippage_bps=slip)
        return bt.stats(r, BPY), r

    def show(label, w):
        s1, _ = ev(w, 1.0); s5, _ = ev(w, 5.0); s10, _ = ev(w, 10.0)
        print(f"  {label:40s} 1bp {s1['cagr']*100:6.2f}/{s1['max_drawdown']*100:5.1f}/"
              f"{s1['sharpe']:4.2f} 5bp {s5['cagr']*100:6.2f} 10bp {s10['cagr']*100:6.2f} "
              f"fills {s1['fills']:5d} TQ {np.mean(w[:,1]>0)*100:4.1f}%")

    for ent, ext, name in [
        (0.75, 0.85, "enter<0.75 exit>0.85"),
        (0.75, 0.90, "enter<0.75 exit>0.90"),
        (0.80, 0.90, "enter<0.80 exit>0.90"),
        (0.80, 1.00, "enter<0.80 exit>1.00"),
        (0.70, 0.90, "enter<0.70 exit>0.90"),
    ]:
        e = np.nan_to_num(acc < ent, nan=False).astype(bool)
        x = np.nan_to_num(acc > ext, nan=False).astype(bool)
        show(name, w_state(e, x, 210))

    # correlations with winners
    print("\n=== correlations with winners ===")
    w = np.zeros((len(ts), 3))
    enter = np.nan_to_num(acc < 0.8, nan=False).astype(bool)
    for k in range(n - 1):
        if not enter[k]:
            continue
        fk, lk = int(first[k]), int(last[k])
        w[fk + 210, 1] = 1.0
        w[fk + 211:lk + 1, 1] = 1.0
        w[lk, 1] = 0.0
    w[-1] = w[-2]
    s, r = ev(w, 1.0)
    eq = pd.Series(r["equity"], index=pd.to_datetime(r["ts"]))
    dr = eq.groupby(eq.index.normalize()).last().pct_change().dropna()
    dr.index = pd.DatetimeIndex(dr.index).normalize()
    for win in WINNERS:
        d = json.loads((ROOT / "research" / "new" / "curves" / f"{win}.json").read_text())
        wr = pd.Series(d["values"], index=pd.to_datetime(d["dates"]))
        wr.index = pd.DatetimeIndex(wr.index).normalize()
        wr = wr.pct_change().dropna()
        jj = dr.index.intersection(wr.index)
        print(f"  {win:38s} corr {dr.loc[jj].corr(wr.loc[jj]):+.3f}  n={len(jj)}")


if __name__ == "__main__":
    main()
