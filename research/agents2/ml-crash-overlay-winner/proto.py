"""Prototype walk-forward crash overlay on the winner (close-decision variant)."""
from __future__ import annotations

import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402

sys.path.insert(0, str(Path(__file__).parent))
from analyze2 import winner_daily  # noqa: E402

START, END = "2017-01-03", "2026-10-23"
BARS = 252 * 390
WINDOW = 750
STARTS = {"10y": "2017-01-03", "5y": "2021-10-25"}


def logistic_fit(x, y, lam=10.0, iters=30):
    n, d = x.shape
    xb = np.column_stack([np.ones(n), x])
    w = np.zeros(d + 1)
    reg = np.full(d + 1, lam)
    reg[0] = 0.0
    for _ in range(iters):
        z = np.clip(xb @ w, -35, 35)
        p = 1.0 / (1.0 + np.exp(-z))
        g = xb.T @ (p - y) + reg * w
        s = np.maximum(p * (1 - p), 1e-6)
        h = xb.T @ (xb * s[:, None]) + np.diag(reg + 1e-9)
        step = np.linalg.solve(h, g)
        w -= step
        if np.max(np.abs(step)) < 1e-7:
            break
    return w


def walk_forward(dts, x, y, horizon, window=WINDOW, lam=10.0):
    y = np.asarray(y, dtype=float)
    p = np.full(len(dts), np.nan)
    for year in range(2017, 2027):
        start = pd.Timestamp(f"{year}-01-01")
        end = pd.Timestamp(f"{year + 1}-01-01")
        test = (dts >= start) & (dts < end)
        tr = np.where(dts < start)[0]
        tr = tr[np.isfinite(y[tr])]
        tr = tr[:-(horizon + 1)]
        if window:
            tr = tr[-window:]
        if len(tr) < 60:
            continue
        coverage = np.isfinite(x[tr]).mean(axis=0)
        keep = coverage >= 0.5
        xt = x[:, keep]
        med = np.nanmedian(xt[tr], axis=0)
        med = np.where(np.isfinite(med), med, 0.0)
        xf = np.where(np.isfinite(xt), xt, med)
        mu = np.nanmean(xf[tr], axis=0)
        sd = np.nanstd(xf[tr], axis=0)
        sd = np.where(np.isfinite(sd) & (sd > 1e-12), sd, 1.0)
        xs = np.clip((xf - mu) / sd, -6, 6)
        w = logistic_fit(xs[tr], y[tr], lam=lam)
        p[test] = 1.0 / (1.0 + np.exp(-np.clip(
            np.column_stack([np.ones(test.sum()), xs[test]]) @ w, -35, 35)))
    return p


def apply_override(w_win, rflag, mode, held, day_of_bar):
    """Override only sessions that the winner would hold in TQQQ at the open."""
    w = w_win.copy()
    fb = (rflag & held)[day_of_bar]
    if mode == "bil":
        w[fb, 1] = 0.0
        w[fb, 2] = 1.0
    elif mode == "qqq":
        w[fb, 1] = 0.0
        w[fb, 2] = 0.0
        w[fb, 0] = 1.0
    elif mode == "half":
        w[fb, 1] = 0.5
        w[fb, 2] = 0.5
    elif mode == "tq":
        w[fb, 1] = 0.5
        w[fb, 2] = 0.0
        w[fb, 0] = 0.5
    return w


def evaluate(ts, o, c, w, start, slip=1.0):
    r = bt.run(ts, o, c, w, start, band=0.02, slippage_bps=slip)
    return bt.stats(r, BARS)


def main():
    ts, o, c = bt.panel(("QQQ", "TQQQ", "BIL"), START, END, "1min")
    w_win, opened, stopped, last, first = winner_daily(ts, o, c)
    dates = np.array([t.date() for t in ts])
    dts = pd.DatetimeIndex([pd.Timestamp(x) for x in dates[last]])
    day_of_bar = pd.Index(dates).map({d: k for k, d in enumerate(dts.date)}).to_numpy()
    f = pd.read_pickle(Path(__file__).parent / "features.pkl")
    f.index = pd.to_datetime(f.index)
    f = f.reindex(dts).ffill()

    tqc = pd.Series(c[last, 1], index=dts)
    tot = tqc.pct_change().shift(-1)
    bilr = pd.Series(c[last, 2], index=dts).pct_change().shift(-1)
    ex = tot - bilr
    labels = {}
    for nm, thr in (("c2", -0.02), ("c3", -0.03), ("c4", -0.045)):
        y = (tot < thr).astype(float)
        y[~np.isfinite(tot)] = np.nan
        labels[nm] = (y, 1)
    yu = (ex < 0).astype(float)
    yu[~np.isfinite(ex)] = np.nan
    labels["under"] = (yu, 1)

    feats = ["rv1", "rv5", "rv20", "rv60", "rv_ratio", "rv_pct", "skew1", "skew20",
             "dvol", "dvol20", "vwap_dist", "dd_high", "first30", "last30", "close_loc",
             "gap", "gap20", "intraday", "up20", "dd20", "dd252", "sma20", "sma165",
             "rsi14", "decay5", "decay20", "bil5", "dow", "range", "range20",
             "vol_ratio", "vol_z20", "rv_x_trend", "skew_x_dd"]
    x = f[feats].to_numpy()

    print("base winner:", end=" ")
    for lab, st in STARTS.items():
        s = evaluate(ts, o, c, w_win, st)
        print(f"{lab} {s['cagr']*100:.2f}/{s['max_drawdown']*100:.2f}/{s['sharpe']:.2f}", end="  ")
    print()

    rows = []
    for yname, (y, h) in labels.items():
        p = walk_forward(dts, x, y, h)
        rank = pd.Series(p).rolling(252, min_periods=60).rank(pct=True).to_numpy()
        oos = np.isfinite(p) & (dts >= pd.Timestamp("2017-01-03"))
        yy = y[oos & np.isfinite(y)]
        pp = p[oos & np.isfinite(y)]
        print(f"\n{yname}: base={np.nanmean(yy):.3f} corr={np.corrcoef(pp, yy)[0,1]:.3f}")
        for q in (0.80, 0.90, 0.95):
            flag = np.isfinite(rank) & (rank >= q)
            for mode in ("bil", "qqq", "half", "tq"):
                w = apply_override(w_win, flag, mode, opened, day_of_bar)
                out = []
                for lab, st in STARTS.items():
                    s = evaluate(ts, o, c, w, st)
                    out.append((lab, s))
                line = f"  q{q:.2f} {mode:4s} " + "  ".join(
                    f"{lab} {s['cagr']*100:5.1f}/{s['max_drawdown']*100:5.1f}/{s['sharpe']:.2f}"
                    for lab, s in out)
                print(line)
                rows.append((yname, q, mode, out))

    pd.to_pickle(rows, Path(__file__).parent / "proto_rows.pkl")


if __name__ == "__main__":
    warnings.filterwarnings("ignore")
    main()
