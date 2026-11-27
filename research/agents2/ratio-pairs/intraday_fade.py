"""Idea (b): fade extreme intraday TQQQ/QQQ ratio deviations.

Deviation from 2x-implied ratio:  dev_t = log(R_t/R_prevclose) - 2*log(QQQ_t/QQQ_prevclose)
(the deterministic -drag term is smooth; its 5-minute change is ~0).
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bt_lib as L  # noqa: E402


def main():
    ts, opens, closes = L.load_panel()
    dates, first, last = L.day_bounds(ts)
    nd = len(first)
    n = len(ts)
    day_id = np.repeat(np.arange(nd), np.diff(np.r_[first, n]))
    prev_last = np.r_[np.nan, closes[last, 0][:-1]]
    prev_last_t = np.r_[np.nan, closes[last, 1][:-1]]
    q0 = prev_last[day_id]
    t0 = prev_last_t[day_id]
    x = np.log(closes[:, 0] / q0)
    lr = np.log(closes[:, 1] / t0)
    dev = lr - 3.0 * x

    # within-day bar counter
    bar = np.arange(n) - first[day_id]
    print(f"dev at end of day: mean {np.nanmean(dev[last])*100:+.3f}%  "
          f"std {np.nanstd(dev[last])*100:.3f}%  "
          f"p1 {np.nanpercentile(dev[last],1)*100:+.2f}%  p99 {np.nanpercentile(dev[last],99)*100:+.2f}%")

    for k in (1, 5, 15, 30):
        d = np.full(n, np.nan)
        d[k:] = dev[k:] - dev[:-k]
        f = np.full(n, np.nan)
        f[:-k] = dev[k:] - dev[:-k]
        valid = (bar >= k) & (bar < 390 - k) & np.isfinite(d) & np.isfinite(f)
        c = np.corrcoef(d[valid], f[valid])[0, 1]
        # P&L of fading: -sign(d)*f
        fade = -np.sign(d[valid]) * f[valid]
        print(f"k={k:2d}m  n={valid.sum():7d}  corr(d_t, d_t+k) {c:+.3f}  "
              f"E[-sign(d)*fwd] {fade.mean()*1e4:+.2f}bp  "
              f"sd {fade.std()*1e4:.1f}bp")

    print("\nquintiles of 5m deviation change -> forward 5m dev change (bp)")
    k = 5
    d = np.full(n, np.nan)
    d[k:] = dev[k:] - dev[:-k]
    f = np.full(n, np.nan)
    f[:-k] = dev[k:] - dev[:-k]
    valid = (bar >= k) & (bar < 390 - k) & np.isfinite(d) & np.isfinite(f)
    q = pd.qcut(pd.Series(d[valid]), 10, labels=False, duplicates="drop")
    tab = pd.DataFrame({"q": q, "d": d[valid] * 1e4, "f": f[valid] * 1e4})
    print(tab.groupby("q").agg(n=("f", "size"), d_mean=("d", "mean"), f_mean=("f", "mean")).to_string(
        float_format=lambda v: f"{v: .2f}"))

    print("\nthreshold fade, 5m signal, hold 5m, one position at a time, 1bp per fill")
    for thr in (20, 40, 60, 100):
        # signals per minute
        sig = d
        trade_pnl = []
        # simple event study: each occurrence, fade for k minutes
        ev = valid & (np.abs(sig) > thr / 1e4)
        idx = np.flatnonzero(ev)
        # avoid overlapping events
        keep = []
        nxt = -1
        for i in idx:
            if i > nxt:
                keep.append(i)
                nxt = i + k
        keep = np.array(keep)
        pnl = -np.sign(sig[keep]) * f[keep] * 1e4  # bp
        print(f"  |d5|>{thr:3d}bp  events {len(keep):6d}  mean {pnl.mean():+.2f}bp  "
              f"hit {np.mean(pnl>0)*100:4.1f}%  net after 2bp {pnl.mean()-2:+.2f}bp  "
              f"total {pnl.sum()/100:+.1f}%")

    print("\ndaily ratio reversal: does a 1-day ratio drop predict next-day TQQQ-QQQ excess?")
    dly = L.add_ratio_features(L.daily_frame(ts, opens, closes))
    o = opens[first]
    r_tq = np.r_[o[1:, 1] / o[:-1, 1] - 1, np.nan]
    r_qq = np.r_[o[1:, 0] / o[:-1, 0] - 1, np.nan]
    one = dly["logr"].diff()
    for k in (1, 3, 5):
        past = dly["logr"].diff(k).shift(1)
        okm = np.isfinite(past) & np.isfinite(r_tq) & (dly.index >= pd.Timestamp(L.START10))
        q = pd.qcut(past[okm], 10, labels=False, duplicates="drop")
        tab = pd.DataFrame({"q": q, "exc": (r_tq - 3 * r_qq)[okm] * 100,
                            "tq": r_tq[okm] * 100})
        g = tab.groupby("q").agg(n=("tq", "size"), exc=("exc", "mean"), tq=("tq", "mean"),
                                 hit=("tq", lambda v: float((v > 0).mean())))
        print(f"\n  past {k}-day log ratio change (deciles)")
        print(g.to_string(float_format=lambda v: f"{v: .2f}"))


if __name__ == "__main__":
    main()
