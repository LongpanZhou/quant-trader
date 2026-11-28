"""Dev-only exploration for a standalone volatility-targeted leverage strategy.

Period: 2016-01-04 .. 2023-12-29. Never touches 2024+.
No 100-250 day moving-average gate on QQQ/TQQQ/SPY/NDX; the position is owned
by volatility/drawdown sizing.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402

HERE = Path(__file__).resolve().parent
START, END = "2016-01-04", "2023-12-29"
BARS = 252 * 390


def load_dev():
    ts, opens, closes = bt.panel(("QQQ", "TQQQ", "BIL"), START, END, "1min")
    return ts, opens, closes


def day_bounds(dates):
    first = np.flatnonzero(np.r_[True, dates[1:] != dates[:-1]])
    last = np.r_[first[1:] - 1, len(dates) - 1]
    return first, last


def prev(a):
    return np.r_[np.nan, a[:-1]]


def signals(ts, closes):
    dates = bt.session_dates(ts)
    first, last = day_bounds(dates)
    dq, dt, db = closes[last, 0], closes[last, 1], closes[last, 2]
    rq = np.r_[np.nan, np.log(dq[1:] / dq[:-1])]
    rt = np.r_[np.nan, np.log(dt[1:] / dt[:-1])]

    def annvol(r, n):
        return prev(pd.Series(r).rolling(n).std().to_numpy() * np.sqrt(252))

    v_t20 = annvol(rt, 20)
    v_t10 = annvol(rt, 10)
    v_t60 = annvol(rt, 60)
    v_q20 = annvol(rq, 20)
    dd60 = prev((dt / pd.Series(dt).rolling(60).max() - 1.0).to_numpy())
    dd120 = prev((dt / pd.Series(dt).rolling(120).max() - 1.0).to_numpy())
    dd252 = prev((dt / pd.Series(dt).rolling(252).max() - 1.0).to_numpy())
    sma165 = pd.Series(dq).rolling(165).mean().to_numpy()
    base_on = np.zeros(len(first), bool)
    base_on[1:] = dq[:-1] > prev(sma165)[1:]
    return dict(dates=dates, first=first, last=last, dq=dq, dt=dt,
                v_t20=v_t20, v_t10=v_t10, v_t60=v_t60, v_q20=v_q20,
                dd60=dd60, dd120=dd120, dd252=dd252, base_on=base_on)


def to_minutes(sig, day_w):
    """day_w: (nd,3) target per session -> (n,3) minutes."""
    n = len(sig["dates"])
    w = np.zeros((n, 3))
    # vectorised assignment by day id
    day_id = np.repeat(np.arange(len(sig["first"])),
                       np.diff(np.r_[sig["first"], n]))
    return day_w[day_id]


def daily_rets(ts, equity):
    s = pd.Series(equity, index=ts)
    e = s.groupby(s.index.date).last()
    return e.pct_change().dropna()


def main():
    ts, opens, closes = load_dev()
    sig = signals(ts, closes)
    nd = len(sig["first"])
    zeros = np.zeros(nd)

    def wt(tqqq, qqq=None):
        qqq = zeros if qqq is None else qqq
        t = np.nan_to_num(np.asarray(tqqq, float), nan=0.0, posinf=0.0, neginf=0.0)
        q = np.nan_to_num(np.asarray(qqq, float), nan=0.0, posinf=0.0, neginf=0.0)
        d = np.column_stack([np.clip(q, 0, 1), np.clip(t, 0, 1), zeros])
        # renormalise if sum > 1
        s = d.sum(axis=1)
        over = s > 1
        d[over, :2] /= s[over, None]
        d[:, 2] = 1.0 - d[:, 0] - d[:, 1]
        return d

    base = wt(sig["base_on"].astype(float))

    cands = {}
    for tv in (0.20, 0.25, 0.30, 0.35, 0.40, 0.50, 0.60):
        cands[f"vt_tqqq_{tv:.2f}"] = wt(np.minimum(1.0, tv / sig["v_t20"]))
    for tv in (0.08, 0.10, 0.12, 0.15, 0.18):
        cands[f"vt_qqq_{tv:.2f}"] = wt(zeros, np.minimum(1.0, tv / sig["v_q20"]))
    for tv in (0.25, 0.30, 0.35, 0.40):
        w = np.minimum(1.0, tv / sig["v_t20"])
        cands[f"vt_tqqq_{tv:.2f}_qqqres"] = wt(w, 1.0 - w)
    for tv in (0.30, 0.35):
        w = np.minimum(1.0, tv / sig["v_t20"])
        cands[f"vt_tqqq_{tv:.2f}_halfres"] = wt(w, 0.5 * (1.0 - w))
    for thr in (0.30, 0.35, 0.40, 0.45, 0.50):
        cands[f"volgate_{thr:.2f}"] = wt((sig["v_t20"] < thr).astype(float))
    for k in (0.6, 1.0, 1.5):
        base_w = np.minimum(1.0, 0.35 / sig["v_t20"])
        scale = np.clip(1.0 - k * np.maximum(-sig["dd60"], 0.0) / 0.20, 0.2, 1.0)
        cands[f"vt35_dd60_k{k:.1f}"] = wt(base_w * scale)
    for k in (0.5, 1.0):
        base_w = np.minimum(1.0, 0.35 / sig["v_t20"])
        ratio = sig["v_t10"] / sig["v_t60"]
        scale = np.clip(1.0 - k * (ratio - 1.0), 0.3, 1.0)
        cands[f"vt35_voltrend_k{k:.1f}"] = wt(base_w * scale)
    for tv in (0.35, 0.45):
        w = np.minimum(1.0, tv / sig["v_t20"])
        # high vol: move residual to QQQ instead of BIL
        q = np.where(sig["v_t20"] > tv, 1.0 - w, 0.0)
        cands[f"vt_tqqq_{tv:.2f}_qqqwhenhigh"] = wt(w, q)

    names = list(cands)
    mats = [to_minutes(sig, base)] + [to_minutes(sig, cands[n]) for n in names]
    print(f"sessions {nd}, bars {len(ts)}, variants {len(names)}", flush=True)
    res = bt.run_many(ts, opens, closes, mats, start=START, band=0.02,
                      slippage_bps=1.0)
    sb = bt.stats(res[0], BARS)
    rb = daily_rets(ts, res[0]["equity"])
    print(f"BASE 165d  cagr {sb['cagr']*100:6.2f}  dd {sb['max_drawdown']*100:5.2f}  "
          f"sh {sb['sharpe']:.2f}  fills {sb['fills']}", flush=True)
    rows = []
    for j, name in enumerate(names, start=1):
        s = bt.stats(res[j], BARS)
        rr = daily_rets(ts, res[j]["equity"])
        idx = rb.index.intersection(rr.index)
        corr = float(np.corrcoef(rb.loc[idx], rr.loc[idx])[0, 1])
        cal = s["cagr"] / s["max_drawdown"] if s["max_drawdown"] > 0 else 0
        rows.append((name, s["cagr"], s["max_drawdown"], s["sharpe"], cal,
                     s["fills"], corr, s["exposure"]))
        print(f"{name:32s} cagr {s['cagr']*100:6.2f} dd {s['max_drawdown']*100:5.2f} "
              f"sh {s['sharpe']:.2f} cal {cal:.2f} corr {corr:.3f} "
              f"fills {s['fills']:5d} exp {s['exposure']*100:.0f}%", flush=True)
    print("done", flush=True)


if __name__ == "__main__":
    main()
