"""Dev-only exploration 2: volatility as the position owner, not a small tilt.

Goal: keep the volatility-sizing idea but earn a daily-return correlation with
the 165-day baseline below 0.60.  Period 2016-01-04..2023-12-29 only.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402

START, END = "2016-01-04", "2023-12-29"
BARS = 252 * 390


def day_bounds(dates):
    first = np.flatnonzero(np.r_[True, dates[1:] != dates[:-1]])
    last = np.r_[first[1:] - 1, len(dates) - 1]
    return first, last


def prev(a):
    return np.r_[np.nan, a[:-1]]


def signals(ts, closes):
    dates = bt.session_dates(ts)
    first, last = day_bounds(dates)
    dq, dt = closes[last, 0], closes[last, 1]
    rq = np.r_[np.nan, np.log(dq[1:] / dq[:-1])]
    rt = np.r_[np.nan, np.log(dt[1:] / dt[:-1])]

    def annvol(r, n):
        return prev(pd.Series(r).rolling(n).std().to_numpy() * np.sqrt(252))

    v20 = annvol(rt, 20)
    v60 = annvol(rt, 60)
    vq20 = annvol(rq, 20)
    # trailing percentile of v20 (uses only past values)
    pct = np.full(len(v20), np.nan)
    for i in range(252, len(v20)):
        h = v20[i - 252:i]
        h = h[np.isfinite(h)]
        if len(h) > 100 and np.isfinite(v20[i]):
            pct[i] = (h < v20[i]).mean()
    sma165 = pd.Series(dq).rolling(165).mean().to_numpy()
    base_on = np.zeros(len(first), bool)
    base_on[1:] = dq[:-1] > prev(sma165)[1:]
    dd252 = prev((dt / pd.Series(dt).rolling(252).max() - 1.0).to_numpy())
    return dict(dates=dates, first=first, last=last, v20=v20, v60=v60,
                vq20=vq20, pct=pct, base_on=base_on, dd252=dd252)


def to_minutes(sig, day_w):
    n = len(sig["dates"])
    day_id = np.repeat(np.arange(len(sig["first"])),
                       np.diff(np.r_[sig["first"], n]))
    return day_w[day_id]


def daily_rets(ts, equity):
    s = pd.Series(equity, index=ts)
    e = s.groupby(s.index.date).last()
    return e.pct_change().dropna()


def main():
    ts, opens, closes = bt.panel(("QQQ", "TQQQ", "BIL"), START, END, "1min")
    sig = signals(ts, closes)
    nd = len(sig["first"])
    z = np.zeros(nd)

    def wt(t, q=None):
        q = z if q is None else q
        t = np.nan_to_num(np.asarray(t, float), nan=0.0)
        q = np.nan_to_num(np.asarray(q, float), nan=0.0)
        d = np.column_stack([np.clip(q, 0, 1), np.clip(t, 0, 1), z])
        s = d.sum(axis=1)
        over = s > 1
        d[over, :2] /= s[over, None]
        d[:, 2] = 1 - d[:, 0] - d[:, 1]
        return d

    base = wt(sig["base_on"].astype(float))
    cands = {}
    # binary vol gate, BIL in the high-vol state
    for thr in (0.45, 0.48, 0.50, 0.52, 0.55, 0.58, 0.60, 0.65):
        cands[f"gate_bil_{thr:.2f}"] = wt((sig["v20"] < thr).astype(float))
    # binary vol gate, QQQ in the high-vol state
    for thr in (0.40, 0.45, 0.48, 0.50, 0.52, 0.55, 0.58, 0.60):
        on = sig["v20"] < thr
        cands[f"gate_qqq_{thr:.2f}"] = wt(on.astype(float), (~on).astype(float))
    # half QQQ in the high-vol state
    for thr in (0.45, 0.50, 0.52, 0.55):
        on = sig["v20"] < thr
        cands[f"gate_halfqqq_{thr:.2f}"] = wt(on.astype(float),
                                              0.5 * (~on).astype(float))
    # continuous TQQQ -> QQQ rotation
    for lo, hi in ((0.30, 0.70), (0.35, 0.75), (0.40, 0.80), (0.35, 0.85),
                   (0.30, 0.60), (0.40, 0.70)):
        x = np.clip((sig["v20"] - lo) / (hi - lo), 0, 1)
        cands[f"rot_{lo:.2f}_{hi:.2f}"] = wt(1 - x, x)
    # vol target with a hard ceiling (sizing, but zero above the ceiling)
    for tv, thr in ((0.25, 0.55), (0.30, 0.55), (0.35, 0.55),
                    (0.30, 0.60), (0.35, 0.60), (0.40, 0.60),
                    (0.30, 0.65), (0.35, 0.65)):
        w = np.where(sig["v20"] < thr, np.minimum(1.0, tv / sig["v20"]), 0.0)
        cands[f"vt{tv:.2f}_ceil{thr:.2f}"] = wt(w)
    # vol-target QQQ in the high-vol state
    for thr, tq in ((0.50, 0.15), (0.55, 0.15), (0.55, 0.18), (0.60, 0.15)):
        on = sig["v20"] < thr
        wq = np.where(~on, np.minimum(1.0, tq / sig["vq20"]), 0.0)
        cands[f"gate_vtqqq_{thr:.2f}_{tq:.2f}"] = wt(on.astype(float), wq)
    # hysteresis gate
    for lo, hi in ((0.45, 0.55), (0.48, 0.58), (0.50, 0.60), (0.52, 0.62)):
        state = np.zeros(nd)
        on = False
        for i in range(nd):
            v = sig["v20"][i]
            if np.isfinite(v):
                if not on and v < lo:
                    on = True
                elif on and v > hi:
                    on = False
            state[i] = 1.0 if on else 0.0
        cands[f"hyst_{lo:.2f}_{hi:.2f}"] = wt(state)
    # trailing-percentile gate
    for p in (0.50, 0.60, 0.70, 0.80):
        on = np.isfinite(sig["pct"]) & (sig["pct"] < p)
        cands[f"pctile_{p:.2f}_bil"] = wt(on.astype(float))
        cands[f"pctile_{p:.2f}_qqq"] = wt(on.astype(float), (~on).astype(float))
    # drawdown gate (comparison; still no price MA)
    for dd in (-0.10, -0.15, -0.20):
        on = sig["dd252"] > dd
        cands[f"ddgate_{dd:.2f}"] = wt(on.astype(float))
    # short tail overlay on the 0.55 gate (borrow cost applied in final if used)
    for thr, sw in ((0.55, 0.2), (0.50, 0.2), (0.55, 0.3)):
        on = sig["v20"] < thr
        t = on.astype(float) - np.where(sig["v20"] > 0.90, sw, 0.0)
        cands[f"gate_{thr:.2f}_short{sw:.1f}"] = wt(t)

    names = list(cands)
    mats = [to_minutes(sig, base)] + [to_minutes(sig, cands[n]) for n in names]
    print(f"variants {len(names)}", flush=True)
    res = bt.run_many(ts, opens, closes, mats, start=START, band=0.02,
                      slippage_bps=1.0)
    sb = bt.stats(res[0], BARS)
    rb = daily_rets(ts, res[0]["equity"])
    print(f"BASE  cagr {sb['cagr']*100:6.2f} dd {sb['max_drawdown']*100:5.2f} "
          f"sh {sb['sharpe']:.2f}", flush=True)
    rows = []
    for j, name in enumerate(names, start=1):
        s = bt.stats(res[j], BARS)
        rr = daily_rets(ts, res[j]["equity"])
        idx = rb.index.intersection(rr.index)
        corr = float(np.corrcoef(rb.loc[idx], rr.loc[idx])[0, 1])
        cal = s["cagr"] / s["max_drawdown"] if s["max_drawdown"] > 0 else 0
        rows.append((name, s["cagr"], s["max_drawdown"], s["sharpe"], cal, corr))
        print(f"{name:30s} cagr {s['cagr']*100:6.2f} dd {s['max_drawdown']*100:5.2f} "
              f"sh {s['sharpe']:.2f} cal {cal:.2f} corr {corr:.3f} "
              f"fills {s['fills']:4d}", flush=True)
    print("done", flush=True)


if __name__ == "__main__":
    main()
