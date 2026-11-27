"""Rolling 3-year comparison of the vol-target candidates vs winner and TQQQ."""
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
BARS = 252 * 390
STOP, SMA_N, MA_FAST, ARM_BUF = 0.04, 165, 20, 0.01


def load_panel():
    z = np.load(HERE / "panel.npz")
    ts = (pd.DatetimeIndex(z["ts"].astype("int64"))
          .tz_localize("UTC").tz_convert("America/New_York"))
    return ts, z["opens"].astype(float), z["closes"].astype(float)


def prev(a):
    return np.r_[np.nan, a[:-1]]


def build(day_tq, day_qq, ts, opens, closes, first, last, arm):
    qc, tc = closes[:, 0], closes[:, 1]
    w = np.zeros((len(ts), 3))
    for k in range(len(first)):
        f, l = first[k], last[k]
        wt, wq = day_tq[k], day_qq[k]
        if wt <= 0 and wq <= 0:
            w[f:l + 1, 2] = 1.0
            continue
        if not arm[k]:
            w[f:l + 1, 0] = wq
            w[f:l + 1, 1] = wt
            w[f:l + 1, 2] = 1.0 - wt - wq
            continue
        base = opens[f, 1]
        state = True
        for i in range(f, l + 1):
            if state and tc[i] < base * (1.0 - STOP):
                state = False
            if state:
                w[i, 0] = wq
                w[i, 1] = wt
                w[i, 2] = 1.0 - wt - wq
            else:
                w[i, 2] = 1.0
    return w


def main():
    t0 = time.time()
    ts, opens, closes = load_panel()
    dates = np.array([t.date() for t in ts])
    first = np.flatnonzero(np.r_[True, dates[1:] != dates[:-1]])
    last = np.r_[first[1:] - 1, len(ts) - 1]
    nd = len(first)
    dq, dt = closes[last, 0], closes[last, 1]
    ma20 = pd.Series(dq).rolling(MA_FAST).mean().to_numpy()
    sma = pd.Series(dq).rolling(SMA_N).mean().to_numpy()
    arm = closes[first, 0] < prev(ma20) * (1.0 + ARM_BUF)
    risk_on = np.zeros(nd, bool)
    risk_on[1:] = dq[:-1] > prev(sma)[1:]
    ret = np.r_[np.nan, np.log(dt[1:] / dt[:-1])]
    vol20 = prev(pd.Series(ret).rolling(20).std().to_numpy() * np.sqrt(252))
    vol30 = prev(pd.Series(ret).rolling(30).std().to_numpy() * np.sqrt(252))
    z0 = np.zeros(nd)

    def variant(wt):
        wt = np.where(risk_on, np.clip(wt, 0, 1), 0.0)
        return build(wt, z0, ts, opens, closes, first, last, arm)

    cands = {
        "winner": variant(np.ones(nd)),
        "vt65": variant(np.minimum(1.0, 0.65 / vol20)),
        "vt65_core30": variant(0.3 + 0.7 * np.minimum(1.0, 0.65 / vol20)),
        "vt65_core30_v30": variant(0.3 + 0.7 * np.minimum(1.0, 0.65 / vol30)),
        "vt55": variant(np.minimum(1.0, 0.55 / vol20)),
    }
    starts = []
    for y in range(2017, 2024):
        for m in (1, 4, 7, 10):
            s = pd.Timestamp(y, m, 1)
            if pd.Timestamp("2017-04-01") <= s <= pd.Timestamp("2023-10-01"):
                starts.append(s)
    print("windows", len(starts), flush=True)

    rows = {k: [] for k in cands}
    tq_rows = []
    for s in starts:
        i0 = int(ts.searchsorted(s.tz_localize("America/New_York")))
        e = s + pd.DateOffset(years=3)
        i1 = int(ts.searchsorted(e.tz_localize("America/New_York")))
        b = bt.benchmark(closes[i0:i1, 1], ts[i0:i1], BARS)
        tq_rows.append((b["cagr"], b["max_drawdown"]))
        for name, w in cands.items():
            r = bt.simulate(ts[i0:i1], opens[i0:i1], closes[i0:i1], w[i0:i1],
                            band=0.02, slippage_bps=1.0)
            st = bt.stats(r, BARS)
            rows[name].append((st["cagr"], st["max_drawdown"]))
        print(".", end="", flush=True)
    print(flush=True)

    tq = np.array(tq_rows)
    print(f"{'variant':20s} {'ret>TQ':>7s} {'dd<TQ':>6s} {'ret>W':>6s} {'dd<W':>6s} "
          f"{'both>W':>7s} {'calmar>W':>9s}  medCAGR medDD")
    wc = np.array(rows["winner"])
    for name, arr in rows.items():
        a = np.array(arr)
        rt = (a[:, 0] > tq[:, 0]).sum()
        dt_ = (a[:, 1] < tq[:, 1]).sum()
        rw = (a[:, 0] > wc[:, 0]).sum()
        dw = (a[:, 1] < wc[:, 1]).sum()
        both = ((a[:, 0] > wc[:, 0]) & (a[:, 1] < wc[:, 1])).sum()
        cal = ((a[:, 0] / a[:, 1]) > (wc[:, 0] / wc[:, 1])).sum()
        print(f"{name:20s} {rt:7d} {dt_:6d} {rw:6d} {dw:6d} {both:7d} {cal:9d}  "
              f"{np.median(a[:,0])*100:6.1f} {np.median(a[:,1])*100:5.1f}", flush=True)
    print(f"\ndone {time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
