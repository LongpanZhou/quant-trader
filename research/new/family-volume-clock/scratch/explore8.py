"""Eighth exploration: focused plateau/cost/state-machine tests."""
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

    def feats(j):
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
        return acc, vwd, vwr, rop

    def w_fixed(enter, j, hold="overnight"):
        w = np.zeros((len(ts), 3))
        for k in range(n - 1):
            if not enter[k]:
                continue
            m = min(int(last[k]) - int(first[k]) + 1, 390)
            if j >= m - 1:
                continue
            fk, lk = int(first[k]), int(last[k])
            w[fk + j, 1] = 1.0
            if hold == "overnight":
                w[fk + j + 1:lk + 1, 1] = 1.0
                w[lk, 1] = 0.0
            elif hold == "intraday":
                w[fk + j + 1:lk, 1] = 1.0
                w[lk - 1, 1] = 0.0
            elif hold == "next_close":
                fn, ln = int(first[k + 1]), int(last[k + 1])
                w[fk + j + 1:ln, 1] = 1.0
                w[ln - 1, 1] = 0.0
        w[-1] = w[-2]
        return w

    def ev(w, slip=1.0):
        r = bt.run(ts, o, c, w, DEV_START, band=0.02, slippage_bps=slip)
        return bt.stats(r, BPY), r

    def show(label, enter, j, hold="overnight"):
        w = w_fixed(enter, j, hold)
        row = []
        for slip in (1.0, 5.0, 10.0):
            s, _ = ev(w, slip)
            row.append((s, slip))
        s1 = row[0][0]
        print(f"  {label:44s} 1bp {s1['cagr']*100:6.2f}%/{s1['max_drawdown']*100:5.1f}%/"
              f"{s1['sharpe']:4.2f}  5bp {row[1][0]['cagr']*100:6.2f}%  "
              f"10bp {row[2][0]['cagr']*100:6.2f}%  fills {s1['fills']:5d}  "
              f"TQ {np.mean(w[:,1]>0)*100:4.1f}%")
        return s1, row

    print("=== 13:00 accel<0.8 plateau / cost ===")
    for j in (135, 150, 165):
        acc, vwd, vwr, rop = feats(j)
        for th in (0.6, 0.7, 0.8, 0.9, 1.0):
            enter = np.nan_to_num(acc < th, nan=False).astype(bool)
            show(f"{(9+(30+j)//60):02d}:{(30+j)%60:02d} accel<{th:.1f}", enter, j)
        print()

    print("=== 14:30 accel & vwd plateau / cost ===")
    j = 300
    acc, vwd, vwr, rop = feats(j)
    for th in (0.8, 0.9, 1.0, 1.1, 1.2, 1.3):
        for dv in (0.0, -0.001):
            enter = np.nan_to_num((acc < th) & (vwd > dv), nan=False).astype(bool)
            show(f"14:30 accel<{th:.1f} vwd>{dv*1e4:+.0f}bp", enter, j)
    print()
    for hold in ("intraday", "overnight", "next_close"):
        enter = np.nan_to_num((acc < 1.0) & (vwd > 0), nan=False).astype(bool)
        show(f"14:30 accel<1.0 vwd>0 {hold}", enter, j, hold)

    print("\n=== state machine (14:30): hysteresis with deadband ===")
    # states: 1 = TQQQ overnight, 0 = BIL
    def state_w(enter_sig, exit_sig, j):
        w = np.zeros((len(ts), 3))
        state = 0
        for k in range(n - 1):
            m = min(int(last[k]) - int(first[k]) + 1, 390)
            if j >= m - 1:
                continue
            if state == 0 and enter_sig[k]:
                state = 1
            elif state == 1 and exit_sig[k]:
                state = 0
            if state:
                fk, lk = int(first[k]), int(last[k])
                w[fk + j, 1] = 1.0
                w[fk + j + 1:lk + 1, 1] = 1.0
                w[lk, 1] = 0.0
        w[-1] = w[-2]
        return w

    for name, ent, ext in [
        ("enter accel<1.0&vwd>0, exit accel>1.5|vwd<-20bp",
         (acc < 1.0) & (vwd > 0), (acc > 1.5) | (vwd < -0.002)),
        ("enter accel<1.0&vwd>0, exit accel>1.3|vwd<-10bp",
         (acc < 1.0) & (vwd > 0), (acc > 1.3) | (vwd < -0.001)),
        ("enter accel<1.2&vwd>0, exit accel>1.6|vwd<-20bp",
         (acc < 1.2) & (vwd > 0), (acc > 1.6) | (vwd < -0.002)),
        ("enter accel<1.0&vwd>-5bp, exit accel>1.5|vwd<-25bp",
         (acc < 1.0) & (vwd > -0.0005), (acc > 1.5) | (vwd < -0.0025)),
    ]:
        ent = np.nan_to_num(ent, nan=False).astype(bool)
        ext = np.nan_to_num(ext, nan=False).astype(bool)
        w = state_w(ent, ext, j)
        s1, _ = ev(w, 1.0); s5, _ = ev(w, 5.0); s10, _ = ev(w, 10.0)
        print(f"  {name:58s} 1bp {s1['cagr']*100:6.2f}%/{s1['max_drawdown']*100:5.1f}%/"
              f"{s1['sharpe']:4.2f} 5bp {s5['cagr']*100:6.2f}% 10bp {s10['cagr']*100:6.2f}% "
              f"fills {s1['fills']:5d} TQ {np.mean(w[:,1]>0)*100:4.1f}%")

    # subperiods of the two main cells
    print("\n=== subperiods / yearly for selected cells ===")
    def subperiod(tsx, eq, lo, hi):
        m = (tsx >= pd.Timestamp(lo, tz="America/New_York")) & (tsx < pd.Timestamp(hi, tz="America/New_York") + pd.Timedelta(days=1))
        x, tt = eq[m], tsx[m]
        if len(x) < 2:
            return None
        years = (tt[-1] - tt[0]).total_seconds() / (365.25 * 86400)
        peak = np.maximum.accumulate(x)
        return dict(cagr=float((x[-1] / x[0]) ** (1 / years) - 1),
                    dd=float(-(x / peak - 1).min()))
    for name, jj, cm, hold in [
        ("13:00 accel<0.8", 150, (feats(150)[0] < 0.8), "overnight"),
        ("14:30 accel<1.0&vwd>0", 300, (feats(300)[0] < 1.0) & (feats(300)[1] > 0), "overnight"),
        ("14:30 accel<1.0&vwd>0 nextclose", 300, (feats(300)[0] < 1.0) & (feats(300)[1] > 0), "next_close"),
    ]:
        enter = np.nan_to_num(cm, nan=False).astype(bool)
        w = w_fixed(enter, jj, hold)
        s, r = ev(w, 1.0)
        print(f"\n{name}: CAGR {s['cagr']*100:.2f}% DD {s['max_drawdown']*100:.1f}% Sh {s['sharpe']:.2f} fills {s['fills']}")
        for lo, hi in (("2016-01-04", "2019-12-31"), ("2020-01-02", "2021-12-31"), ("2022-01-03", "2023-12-29")):
            print("  ", lo, hi, subperiod(r["ts"], r["equity"], lo, hi))
        yr = bt.yearly(r["ts"], r["equity"], c[bt.start_index(ts, DEV_START):, 1])
        print("  yearly", {k: round(v["strategy"]*100, 1) for k, v in yr.items()})


if __name__ == "__main__":
    main()
