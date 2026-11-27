"""Walk-forward experiments for the ML classifier agent."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "research"))
sys.path.insert(0, str(ROOT / "research" / "agents" / "ml-classifier"))
import bt  # noqa: E402
from explore import build_features, logistic_fit, logistic_predict, standardize_fit  # noqa: E402


def walk_forward(ts, x, y, horizon, years_test=range(2017, 2027), lam=10.0, verbose=True):
    years = np.asarray([t.year for t in ts])
    p = np.full(len(ts), np.nan)
    models = {}
    for yr in years_test:
        test_start = pd.Timestamp(f"{yr}-01-01", tz="America/New_York")
        test_end = pd.Timestamp(f"{yr + 1}-01-01", tz="America/New_York")
        test = (ts >= test_start) & (ts < test_end)
        # purge the last `horizon` bars before the test start
        train = np.where(ts < test_start)[0]
        if len(train) > horizon:
            train = train[:-horizon]
        train = train[np.isfinite(y[train]) & np.isfinite(x[train]).all(axis=1)]
        if len(train) < 2000:
            continue
        mu, sd = standardize_fit(x[train])
        xs = (x - mu) / sd
        xs = np.clip(xs, -6, 6)
        w = logistic_fit(xs[train], y[train], lam=lam)
        p[test] = logistic_predict(w, xs[test])
        models[yr] = (len(train), w)
        if verbose:
            acc = np.nanmean((p[test] > 0.5) == (y[test] > 0.5))
            print(f"  {yr}: train n={len(train):6d} test n={test.sum():5d} acc={acc:.4f}")
    return p, models


def direct_weights(ts, p, enter=0.55, exit=0.45, min_hold=0):
    n = len(ts)
    w = np.zeros((n, 3))
    w[:, 2] = 1.0
    pos = 0
    held = 10**9
    for i in range(n):
        if not np.isfinite(p[i]):
            pos = 0
            held += 1
        else:
            if pos == 0 and p[i] >= enter and held >= min_hold:
                pos = 1
                held = 0
            elif pos == 1 and p[i] <= exit and held >= min_hold:
                pos = 0
                held = 0
            held += 1
        w[i, 1] = float(pos)
        w[i, 2] = 1.0 - pos
    return w


def daily_weights(ts, o, c, p, kind="mean", enter=0.5, exit=0.5):
    """Daily target from intraday predictions, changed at the 15:50 bar."""
    n = len(ts)
    d = pd.DataFrame({"date": ts.date, "p": p})
    d["bidx"] = d.groupby("date").cumcount()
    d["dsize"] = d.groupby("date")["p"].transform("size")
    sig = d["bidx"] < (d["dsize"] - 1)  # through 15:50 bar (exclude 15:55)
    dd = d[sig].groupby("date")
    if kind == "mean":
        s = dd["p"].mean()
    elif kind == "last":
        s = dd["p"].last()
    elif kind == "last6":
        s = dd["p"].apply(lambda v: v.tail(6).mean())
    elif kind == "frac":
        s = dd["p"].apply(lambda v: (v > 0.5).mean())
    else:
        raise ValueError(kind)
    # target for each date, decided at 15:50 of that date
    target = {}
    pos = 0
    for date, val in s.items():
        if not np.isfinite(val):
            pos = 0
        elif pos == 0 and val >= enter:
            pos = 1
        elif pos == 1 and val <= exit:
            pos = 0
        target[date] = pos
    w = np.zeros((n, 3))
    # only apply today's target from the 15:50 bar onward; the position then
    # persists overnight and through the next day until the next 15:50 signal.
    bidx = d["bidx"].to_numpy()
    dsize = d["dsize"].to_numpy()
    dates = ts.date
    last = 0
    for i in range(n):
        date = dates[i]
        if bidx[i] >= dsize[i] - 2:
            last = target.get(date, 0)
        w[i, 1] = last
        w[i, 2] = 1.0 - last
    return w


def sim(ts, o, c, w, start, slippage=1.0, band=0.02):
    r = bt.run(ts, o, c, w, start, band=band, slippage_bps=slippage)
    s = bt.stats(r, 252 * 78)
    return r, s


def print_stats(label, s, b):
    print(f"  {label:34s} CAGR {s['cagr']*100:6.2f}%  DD {s['max_drawdown']*100:6.2f}%  "
          f"Sharpe {s['sharpe']:5.2f}  fills {s['fills']:6d}  turn {s['turnover']:6.1f}x  exp {s['exposure']*100:5.1f}%  "
          f"bench {b['cagr']*100:5.2f}%/{b['max_drawdown']*100:5.2f}%")


def main():
    ts, o, c = bt.panel(("QQQ", "TQQQ", "BIL"), "2017-01-03", "2026-10-23", "5min")
    x, names = build_features(ts, o, c)
    n = len(ts)
    years = np.asarray([t.year for t in ts])
    for horizon in (6, 12):
        fwd_t = np.zeros(n)
        fwd_t[:-horizon] = np.log(c[horizon:, 1] / c[:-horizon, 1])
        fwd_b = np.zeros(n)
        fwd_b[:-horizon] = np.log(c[horizon:, 2] / c[:-horizon, 2])
        y = np.full(n, np.nan)
        y[:-horizon] = (fwd_t[:-horizon] > fwd_b[:-horizon]).astype(float)
        print(f"\n===== walk-forward horizon {horizon} =====")
        p, models = walk_forward(ts, x, y, horizon)
        np.save(ROOT / "research" / "agents" / "ml-classifier" / f"p_h{horizon}.npy", p)
        # economic value by probability decile (next-horizon excess return, bp)
        ex = fwd_t - fwd_b
        m = np.isfinite(p) & np.isfinite(ex)
        q = pd.qcut(pd.Series(p[m]), 10, labels=False, duplicates="drop")
        tab = pd.DataFrame({"q": q, "ex": ex[m]}).groupby("q")["ex"].agg(["mean", "count"])
        tab["mean_bp"] = tab["mean"] * 1e4
        print("  decile next-excess bp:")
        print(tab[["mean_bp", "count"]].round(2).to_string())
        # daily aggregation diagnostics
        d = pd.DataFrame({"date": ts.date, "p": p, "t": c[:, 1], "q": c[:, 0], "b": c[:, 2]})
        g = d.groupby("date")
        daily = pd.DataFrame({
            "p_mean": g["p"].mean(),
            "p_last": g["p"].last(),
            "t_last": g["t"].last(),
            "b_last": g["b"].last(),
            "q_last": g["q"].last(),
        })
        daily["t_ret_next"] = daily["t_last"].shift(-1) / daily["t_last"] - 1
        dd = daily.dropna()
        print("  daily IC p_mean vs next TQQQ ret:", np.corrcoef(dd.p_mean, dd.t_ret_next)[0, 1].round(4))
        print("  daily IC p_last vs next TQQQ ret:", np.corrcoef(dd.p_last, dd.t_ret_next)[0, 1].round(4))
        q5 = pd.qcut(dd.p_mean, 5, labels=False, duplicates="drop")
        print(dd.groupby(q5)["t_ret_next"].agg(["mean", "count"]).round(5).to_string())
        for yr in range(2017, 2027):
            mm = years == yr
            if mm.sum() == 0:
                continue
            print(f"  {yr}: meanp={np.nanmean(p[mm]):.3f} base={np.nanmean(y[mm]):.3f} acc={np.nanmean((p[mm]>.5)==(y[mm]>.5)):.3f}")

        # Backtests
        print("  --- direct 5m rules ---")
        bench10 = bt.benchmark(c[bt.start_index(ts, "2017-01-03"):, 1], ts[bt.start_index(ts, "2017-01-03"):], 252 * 78)
        for enter, exit_, hold in [(0.5, 0.5, 0), (0.55, 0.45, 0), (0.55, 0.45, 6),
                                   (0.55, 0.45, 12), (0.55, 0.45, 78), (0.60, 0.40, 12),
                                   (0.60, 0.40, 78)]:
            w = direct_weights(ts, p, enter, exit_, hold)
            r, s = sim(ts, o, c, w, "2017-01-03")
            print_stats(f"enter{enter} exit{exit_} hold{hold}", s, bench10)
        print("  --- daily rules ---")
        for kind in ("mean", "last", "last6", "frac"):
            for th in (0.5, 0.52, 0.525, 0.53, 0.54):
                w = daily_weights(ts, o, c, p, kind=kind, enter=th, exit=th - 0.01)
                r, s = sim(ts, o, c, w, "2017-01-03")
                print_stats(f"{kind} enter{th}", s, bench10)




if __name__ == "__main__":
    main()
