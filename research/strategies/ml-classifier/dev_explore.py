"""Development-only exploration for the standalone ML risk model.

PRE-PAUSE EXPLORATORY PROTOTYPE: this is the stripped-base TQQQ/BIL approach.
It was rejected because it did not stand alone.  It is not the final strategy;
see `strategy.py` for the regime-cluster rebuild.

No data after 2023-12-29 is loaded or inspected.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402

DEV_END = "2023-12-29"
TRADE_START = "2017-01-03"


def minute_daily(ts5, o5, c5):
    q = c5[:, 0]
    lr = np.zeros(len(ts5))
    lr[1:] = np.log(q[1:] / q[:-1])
    d = pd.DataFrame({
        "date": ts5.date, "o": o5[:, 0], "q": q,
        "hi": np.maximum(o5[:, 0], q), "lo": np.minimum(o5[:, 0], q),
        "lr": lr, "pv": (o5[:, 0] + q) / 2.0,
    })
    g = d.groupby("date", sort=True)
    out = pd.DataFrame({
        "day_open": g["o"].first(),
        "day_close": g["q"].last(),
        "day_high": g["hi"].max(),
        "day_low": g["lo"].min(),
        "rv5": g["lr"].std(ddof=0),
        "first30": g.apply(lambda x: x["q"].iloc[min(5, len(x) - 1)] / x["o"].iloc[0] - 1.0,
                           include_groups=False),
        "last30": g.apply(lambda x: x["q"].iloc[-1] / x["q"].iloc[max(0, len(x) - 7)] - 1.0,
                          include_groups=False),
        "vwap": g.apply(lambda x: x["pv"].mean(), include_groups=False),
        "close_loc": g.apply(
            lambda x: (x["q"].iloc[-1] - x["lo"].min()) / max(x["hi"].max() - x["lo"].min(), 1e-9),
            include_groups=False),
    })
    out["vwap_dist"] = out["day_close"] / out["vwap"] - 1.0
    out["gap"] = out["day_open"] / out["day_close"].shift(1) - 1.0
    out["intraday"] = out["day_close"] / out["day_open"] - 1.0
    return out


def build_features(ts5, o5, c5, tsd, od, cd):
    q, t, b = cd[:, 0], cd[:, 1], cd[:, 2]
    md = minute_daily(ts5, o5, c5)
    md = md.reindex(pd.Index([x.date() for x in tsd])).ffill()
    d = pd.DataFrame({"q": q, "t": t, "b": b})
    lrq = np.log(d.q / d.q.shift(1))

    def ret(s, k):
        return np.log(s / s.shift(k))

    def rstd(k):
        return lrq.rolling(k, min_periods=max(5, k // 3)).std(ddof=0)

    f = pd.DataFrame(index=d.index)
    for k in (1, 2, 5, 10, 20, 60):
        f[f"q_r{k}"] = ret(d.q, k)
    for k in (5, 20, 60):
        f[f"t_r{k}"] = ret(d.t, k)
    for k in (5, 10, 20, 60):
        f[f"rv{k}"] = rstd(k)
    f["rv_ratio_5_60"] = f["rv5"] / f["rv60"]
    f["rv_ratio_20_60"] = f["rv20"] / f["rv60"]
    f["rv_pct"] = f["rv20"].rolling(252, min_periods=100).rank(pct=True)
    delta = d.q.diff()
    up = delta.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
    dn = (-delta).clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
    f["rsi14"] = (100 - 100 / (1 + up / dn.clip(lower=1e-12))) / 100 - 0.5
    f["dd20"] = d.q / d.q.rolling(20, min_periods=10).max() - 1.0
    f["dd60"] = d.q / d.q.rolling(60, min_periods=20).max() - 1.0
    for k in (10, 20, 50):
        f[f"ema{k}_dist"] = d.q / d.q.ewm(span=k, adjust=False).mean() - 1.0
    f["gap"] = md["gap"].to_numpy()
    f["intraday"] = md["intraday"].to_numpy()
    f["first30"] = md["first30"].to_numpy()
    f["last30"] = md["last30"].to_numpy()
    f["vwap_dist"] = md["vwap_dist"].to_numpy()
    f["close_loc"] = md["close_loc"].to_numpy()
    f["overnight20"] = md["gap"].rolling(20, min_periods=10).mean().to_numpy()
    f["intraday20"] = md["intraday"].rolling(20, min_periods=10).mean().to_numpy()
    f["rv5_20"] = md["rv5"].rolling(20, min_periods=10).mean().to_numpy()
    f["decay20"] = f["t_r20"] - 3.0 * f["q_r20"]
    f["decay60"] = f["t_r60"] - 3.0 * f["q_r60"]
    f["bil_r20"] = ret(d.b, 20)
    f["skew20"] = lrq.rolling(20, min_periods=10).skew()
    f["kurt20"] = lrq.rolling(20, min_periods=10).kurt()
    f["accel"] = f["q_r20"] - f["q_r60"]
    f["short_vs_med"] = f["q_r5"] - f["q_r20"]
    f["vol_change"] = f["rv20"] - f["rv60"]
    f["dow"] = pd.Series(tsd.day_of_week, index=d.index).astype(float) / 4.0 - 0.5
    return f


def standardize_fit(x):
    mu = np.nanmean(x, axis=0)
    sd = np.nanstd(x, axis=0)
    mu = np.where(np.isfinite(mu), mu, 0.0)
    sd = np.where(np.isfinite(sd) & (sd > 1e-12), sd, 1.0)
    return mu, sd


def logistic_fit(x, y, lam=10.0, iters=30):
    n, d = x.shape
    xb = np.column_stack([np.ones(n), x])
    w = np.zeros(d + 1)
    reg = np.full(d + 1, lam); reg[0] = 0.0
    for _ in range(iters):
        z = xb @ w
        p = 1.0 / (1.0 + np.exp(-np.clip(z, -35, 35)))
        g = xb.T @ (p - y) + reg * w
        s = np.maximum(p * (1 - p), 1e-6)
        h = xb.T @ (xb * s[:, None]) + np.diag(reg + 1e-9)
        step = np.linalg.solve(h, g)
        w -= step
        if np.max(np.abs(step)) < 1e-7:
            break
    return w


def logistic_predict(w, x):
    xb = np.column_stack([np.ones(len(x)), x])
    return 1.0 / (1.0 + np.exp(-np.clip(xb @ w, -35, 35)))


def make_labels(od, h):
    n = len(od)
    ft = np.full(n, np.nan); fb = np.full(n, np.nan)
    ft[:-(h + 1)] = np.log(od[h + 1:, 1] / od[1:-h, 1])
    fb[:-(h + 1)] = np.log(od[h + 1:, 2] / od[1:-h, 2])
    y = (ft > fb).astype(float)
    y[~np.isfinite(ft) | ~np.isfinite(fb)] = np.nan
    return y


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


def weights_from_tqqq(pos):
    w = np.zeros((len(pos), 3))
    w[:, 1] = pos.astype(float)
    w[:, 2] = 1.0 - w[:, 1]
    return w


def evaluate(ts, o, c, pos, label, slip=1.0):
    w = weights_from_tqqq(pos)
    r = bt.run(ts, o, c, w, TRADE_START, band=0.02, slippage_bps=slip)
    s = bt.stats(r, 252)
    print(f"{label:34s} {slip:4.1f}bp CAGR {s['cagr']*100:6.2f}% DD {s['max_drawdown']*100:5.2f}% "
          f"Sharpe {s['sharpe']:4.2f} fills {s['fills']:4d} turn {s['turnover']:6.0f} "
          f"exp {np.mean(pos):.2f}", flush=True)
    return r, s


def main():
    ts5, o5, c5 = bt.panel(("QQQ", "TQQQ", "BIL"), "2016-01-04", DEV_END, "5min")
    tsd, od, cd = bt.panel(("QQQ", "TQQQ", "BIL"), "2016-01-04", DEV_END, "1D")
    f = build_features(ts5, o5, c5, tsd, od, cd)
    x = f.to_numpy()
    print("features", x.shape, "dates", tsd[0], tsd[-1], flush=True)
    ps = {}
    for h in (5, 10, 20):
        y = make_labels(od, h)
        ps[h] = walk_forward(tsd, x, y, h)
        print(f"h={h} finite p {np.isfinite(ps[h]).sum()}", flush=True)
    ranks = np.column_stack([rank_series(ps[h]) for h in (5, 10, 20)])
    with np.errstate(invalid="ignore"):
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            avg = np.nanmean(ranks, axis=1)
    avg = np.where(np.isfinite(avg), avg, 1.0)

    # benchmarks
    i0 = bt.start_index(tsd, TRADE_START)
    for name, col in (("TQQQ", 1), ("QQQ", 0), ("BIL", 2)):
        b = bt.benchmark(cd[i0:, col], tsd[i0:], 252)
        print(f"bench {name}: CAGR {b['cagr']*100:6.2f}% DD {b['max_drawdown']*100:5.2f}% "
              f"Sharpe {b['sharpe']:4.2f}", flush=True)

    q = cd[:, 0]
    sma = pd.Series(q).rolling(165, min_periods=100).mean().to_numpy()
    base_pos = q > sma
    evaluate(tsd, od, cd, base_pos, "165d baseline (benchmark)")

    print("\n--- binary rank threshold ---", flush=True)
    for thr in (0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8):
        evaluate(tsd, od, cd, avg >= thr, f"rank>={thr}")

    print("\n--- continuous rank sizing ---", flush=True)
    for lo, hi in ((0.2, 0.8), (0.3, 0.7), (0.4, 0.8), (0.5, 0.9), (0.6, 0.9)):
        w = np.clip((avg - lo) / (hi - lo), 0.0, 1.0)
        evaluate(tsd, od, cd, w, f"w=clip((r-{lo})/{hi - lo})")

    print("\n--- old ML-only reference (rank>=0.2) ---", flush=True)
    evaluate(tsd, od, cd, avg >= 0.2, "rank>=0.2 old style")

    # subperiods for a couple of candidates
    print("\n--- subperiods ---", flush=True)
    for thr in (0.4, 0.5, 0.6):
        pos = avg >= thr
        for label, start, end in (("2017-19", "2017-01-03", "2019-12-31"),
                                  ("2020-21", "2020-01-02", "2021-12-31"),
                                  ("2022-23", "2022-01-03", "2023-12-29")):
            w = weights_from_tqqq(pos)
            r = bt.run(tsd, o, c, w, start, band=0.02, slippage_bps=1.0)
            # slice to end
            j = bt.start_index(tsd, end)
            k = bt.start_index(tsd, start)
            rr = bt.simulate(tsd[k:j + 1], od[k:j + 1], cd[k:j + 1], w[k:j + 1],
                             band=0.02, slippage_bps=1.0)
            s = bt.stats(rr, 252)
            print(f"thr{thr} {label}: CAGR {s['cagr']*100:7.2f}% DD {s['max_drawdown']*100:6.2f}%", flush=True)


if __name__ == "__main__":
    main()
