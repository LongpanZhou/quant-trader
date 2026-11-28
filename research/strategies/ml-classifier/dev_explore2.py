"""Development-only prototype: ML risk ladder across TQQQ / QQQ / BIL.

PRE-PAUSE EXPLORATORY PROTOTYPE: this is the stripped-base supervised model
wrapped in a three-asset ladder.  It was rejected because it did not stand
alone.  It is not the final strategy; see `strategy.py` for the unsupervised
regime-cluster rebuild.
"""
from __future__ import annotations

import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "research"))
sys.path.insert(0, str(ROOT / "research" / "revisit" / "ml-classifier"))
import bt  # noqa: E402
from dev_explore import build_features, logistic_fit, logistic_predict, standardize_fit  # noqa: E402

DEV_END = "2023-12-29"
TRADE_START = "2017-01-03"


def make_pair_labels(od, cd, h):
    n = len(od)
    ft = np.full(n, np.nan); fq = np.full(n, np.nan); fb = np.full(n, np.nan)
    ft[:-(h + 1)] = np.log(od[h + 1:, 1] / od[1:-h, 1])
    fq[:-(h + 1)] = np.log(od[h + 1:, 0] / od[1:-h, 0])
    fb[:-(h + 1)] = np.log(od[h + 1:, 2] / od[1:-h, 2])
    y_tq = (ft > fq).astype(float)
    y_qb = (fq > fb).astype(float)
    ok = np.isfinite(ft) & np.isfinite(fq) & np.isfinite(fb)
    y_tq[~ok] = np.nan
    y_qb[~ok] = np.nan
    return y_tq, y_qb


def walk_forward(tsd, x, y, horizon, window=750, lam=10.0):
    p = np.full(len(tsd), np.nan)
    for year in range(2017, 2024):
        start = pd.Timestamp(f"{year}-01-01", tz="America/New_York")
        end = pd.Timestamp(f"{year + 1}-01-01", tz="America/New_York")
        test = (tsd >= start) & (tsd < end)
        train = np.where(tsd < start)[0]
        train = train[np.isfinite(y[train])]
        train = train[:-(horizon + 1)]
        if window:
            train = train[-window:]
        if len(train) < 60:
            continue
        coverage = np.isfinite(x[train]).mean(axis=0)
        keep = coverage >= 0.5
        xt = x[:, keep]
        med = np.nanmedian(xt[train], axis=0)
        med = np.where(np.isfinite(med), med, 0.0)
        xf = np.where(np.isfinite(xt), xt, med)
        mu, sd = standardize_fit(xf[train])
        xs = np.clip((xf - mu) / sd, -6, 6)
        w = logistic_fit(xs[train], y[train], lam=lam)
        p[test] = logistic_predict(w, xs[test])
    return p


def rank_series(p):
    return pd.Series(p).rolling(252, min_periods=60).rank(pct=True).to_numpy()


def avg_rank(p_by_h):
    r = np.column_stack([rank_series(p_by_h[h]) for h in (5, 10, 20)])
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        a = np.nanmean(r, axis=1)
    return np.where(np.isfinite(a), a, 0.5)


def weights_from_alloc(tqqq, qqq):
    w = np.zeros((len(tqqq), 3))
    w[:, 0] = qqq
    w[:, 1] = tqqq
    w[:, 2] = np.clip(1.0 - tqqq - qqq, 0.0, 1.0)
    return w


def evaluate(tsd, od, cd, tqqq, qqq, label, slip=1.0):
    w = weights_from_alloc(tqqq, qqq)
    r = bt.run(tsd, od, cd, w, TRADE_START, band=0.02, slippage_bps=slip)
    s = bt.stats(r, 252)
    i0 = bt.start_index(tsd, TRADE_START)
    rets = np.diff(r["equity"]) / r["equity"][:-1]
    print(f"{label:40s} {slip:4.1f}bp CAGR {s['cagr']*100:6.2f}% DD {s['max_drawdown']*100:5.2f}% "
          f"Sharpe {s['sharpe']:4.2f} fills {s['fills']:4d} turn {s['turnover']:6.0f} "
          f"TQ {np.mean(tqqq[i0:]):.2f} Q {np.mean(qqq[i0:]):.2f}", flush=True)
    return r, s, rets


def main():
    ts5, o5, c5 = bt.panel(("QQQ", "TQQQ", "BIL"), "2016-01-04", DEV_END, "5min")
    tsd, od, cd = bt.panel(("QQQ", "TQQQ", "BIL"), "2016-01-04", DEV_END, "1D")
    f = build_features(ts5, o5, c5, tsd, od, cd)
    x = f.to_numpy()
    print("features", x.shape, flush=True)

    p_tq, p_qb = {}, {}
    for h in (5, 10, 20):
        y_tq, y_qb = make_pair_labels(od, cd, h)
        p_tq[h] = walk_forward(tsd, x, y_tq, h)
        p_qb[h] = walk_forward(tsd, x, y_qb, h)
        print(f"h={h} finite {np.isfinite(p_tq[h]).sum()}", flush=True)

    r_tq = avg_rank(p_tq)
    r_qb = avg_rank(p_qb)

    # benchmarks
    i0 = bt.start_index(tsd, TRADE_START)
    for name, col in (("TQQQ", 1), ("QQQ", 0), ("BIL", 2)):
        b = bt.benchmark(cd[i0:, col], tsd[i0:], 252)
        print(f"bench {name}: CAGR {b['cagr']*100:6.2f}% DD {b['max_drawdown']*100:5.2f}% "
              f"Sharpe {b['sharpe']:4.2f}", flush=True)
    q = cd[:, 0]
    sma = pd.Series(q).rolling(165, min_periods=100).mean().to_numpy()
    base_pos = (q > sma)
    evaluate(tsd, od, cd, base_pos.astype(float), np.zeros(len(tsd)), "165d baseline (benchmark)")
    # store baseline returns
    wb = weights_from_alloc(base_pos.astype(float), np.zeros(len(tsd)))
    rb = bt.run(tsd, od, cd, wb, TRADE_START, band=0.02, slippage_bps=1.0)
    base_rets = np.diff(rb["equity"]) / rb["equity"][:-1]

    print("\n--- binary 3-state ---", flush=True)
    for qe in (0.4, 0.5, 0.6):
        for ql in (0.4, 0.5, 0.6):
            eq = r_qb >= qe
            lev = r_tq >= ql
            tqqq = (eq & lev).astype(float)
            qqq = (eq & ~lev).astype(float)
            evaluate(tsd, od, cd, tqqq, qqq, f"eq>={qe} lev>={ql}")

    print("\n--- continuous ladder ---", flush=True)
    for lo, hi in ((0.3, 0.7), (0.4, 0.6), (0.4, 0.8), (0.5, 0.8)):
        eq = np.clip((r_qb - lo) / (hi - lo), 0.0, 1.0)
        lev = np.clip((r_tq - lo) / (hi - lo), 0.0, 1.0)
        evaluate(tsd, od, cd, eq * lev, eq * (1 - lev), f"cont eq/lev {lo}-{hi}")

    print("\n--- equity-only (QQQ/BIL) ---", flush=True)
    for qe in (0.3, 0.4, 0.5, 0.6):
        eq = (r_qb >= qe).astype(float)
        evaluate(tsd, od, cd, np.zeros(len(tsd)), eq, f"QQQ only eq>={qe}")

    print("\n--- leverage-only (TQQQ/QQQ) ---", flush=True)
    for ql in (0.3, 0.4, 0.5, 0.6):
        lev = (r_tq >= ql).astype(float)
        evaluate(tsd, od, cd, lev, 1 - lev, f"TQQQ/QQQ lev>={ql}")

    # correlation of a mid candidate vs baseline
    eq = np.clip((r_qb - 0.4) / 0.4, 0.0, 1.0)
    lev = np.clip((r_tq - 0.4) / 0.4, 0.0, 1.0)
    _, s, rets = evaluate(tsd, od, cd, eq * lev, eq * (1 - lev), "candidate cont 0.4-0.8")
    n = min(len(rets), len(base_rets))
    print("corr candidate vs 165d baseline:", np.corrcoef(rets[-n:], base_rets[-n:])[0, 1].round(3))


if __name__ == "__main__":
    main()
