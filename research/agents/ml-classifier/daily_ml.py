"""Daily walk-forward ML classifier using daily + minute-derived features."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "research"))
sys.path.insert(0, str(ROOT / "research" / "agents" / "ml-classifier"))
import bt  # noqa: E402
from explore import logistic_fit, logistic_predict, standardize_fit  # noqa: E402


def minute_daily(ts5, o5, c5):
    """Aggregate 5-minute QQQ/TQQQ bars into causal daily features."""
    q, t = c5[:, 0], c5[:, 1]
    d = pd.DataFrame({
        "date": ts5.date, "o": o5[:, 0], "q": q, "t": t,
        "hi": np.maximum(o5[:, 0], q), "lo": np.minimum(o5[:, 0], q),
        "bar": pd.Series(ts5.date).groupby(pd.Series(ts5.date)).cumcount().to_numpy(),
    })
    # intraday 5m log returns for realized vol / vwap
    lr = np.zeros(len(ts5))
    lr[1:] = np.log(q[1:] / q[:-1])
    d["lr"] = lr
    d["pv"] = (o5[:, 0] + q) / 2.0
    g = d.groupby("date", sort=True)
    out = pd.DataFrame({
        "day_open": g["o"].first(),
        "day_close": g["q"].last(),
        "day_high": g["hi"].max(),
        "day_low": g["lo"].min(),
        "rv5": g["lr"].std(ddof=0),
        "first30": g.apply(lambda x: x["q"].iloc[min(5, len(x) - 1)] / x["o"].iloc[0] - 1.0, include_groups=False),
        "last30": g.apply(lambda x: x["q"].iloc[-1] / x["q"].iloc[max(0, len(x) - 7)] - 1.0, include_groups=False),
        "vwap": g.apply(lambda x: x["pv"].mean(), include_groups=False),
        "close_loc": g.apply(lambda x: (x["q"].iloc[-1] - x["lo"].min()) / max(x["hi"].max() - x["lo"].min(), 1e-9), include_groups=False),
        "t_close": g["t"].last(),
    })
    out["vwap_dist"] = out["day_close"] / out["vwap"] - 1.0
    out["gap"] = out["day_open"] / out["day_close"].shift(1) - 1.0
    out["intraday"] = out["day_close"] / out["day_open"] - 1.0
    return out


def build_daily_features(ts5, o5, c5, tsd, od, cd):
    q, t, b = cd[:, 0], cd[:, 1], cd[:, 2]
    md = minute_daily(ts5, o5, c5)
    md = md.reindex(pd.Index([x.date() for x in tsd])).ffill()

    d = pd.DataFrame({"q": q, "t": t, "b": b, "o": od[:, 0]})
    lrq = np.log(d.q / d.q.shift(1))
    lrt = np.log(d.t / d.t.shift(1))
    lrb = np.log(d.b / d.b.shift(1))

    def ret(s, k):
        return np.log(s / s.shift(k))

    def rstd(s, k):
        return s.rolling(k, min_periods=max(5, k // 3)).std(ddof=0)

    feat = pd.DataFrame(index=d.index)
    for k in (1, 2, 5, 10, 20, 60, 120, 250):
        feat[f"q_r{k}"] = ret(d.q, k)
    for k in (10, 20, 60):
        feat[f"rv{k}"] = rstd(lrq, k)
    feat["rv_ratio"] = feat["rv10"] / feat["rv60"]
    feat["rv_pct"] = feat["rv20"].rolling(252, min_periods=100).rank(pct=True)
    delta = d.q.diff()
    up = delta.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
    dn = (-delta).clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
    feat["rsi14"] = (100 - 100 / (1 + up / dn.clip(lower=1e-12))) / 100 - 0.5
    for k in (20, 50, 100, 165, 200):
        feat[f"sma{k}"] = d.q / d.q.rolling(k, min_periods=max(20, k // 2)).mean() - 1.0
    feat["ema20"] = d.q / d.q.ewm(span=20, adjust=False).mean() - 1.0
    feat["ema50"] = d.q / d.q.ewm(span=50, adjust=False).mean() - 1.0
    feat["dd252"] = d.q / d.q.rolling(252, min_periods=100).max() - 1.0
    feat["dd20"] = d.q / d.q.rolling(20, min_periods=10).max() - 1.0
    feat["up20"] = (lrq > 0).rolling(20, min_periods=10).mean() - 0.5
    feat["t_r20"] = ret(d.t, 20)
    feat["t_r60"] = ret(d.t, 60)
    feat["decay60"] = feat["t_r60"] - 3.0 * feat["q_r60"]
    feat["bil_r20"] = ret(d.b, 20)
    feat["overnight20"] = md["gap"].rolling(20, min_periods=10).mean().to_numpy()
    feat["intraday20"] = md["intraday"].rolling(20, min_periods=10).mean().to_numpy()
    feat["rv5_20"] = md["rv5"].rolling(20, min_periods=10).mean().to_numpy()
    feat["gap"] = md["gap"].to_numpy()
    feat["intraday"] = md["intraday"].to_numpy()
    feat["first30"] = md["first30"].to_numpy()
    feat["last30"] = md["last30"].to_numpy()
    feat["vwap_dist"] = md["vwap_dist"].to_numpy()
    feat["close_loc"] = md["close_loc"].to_numpy()
    feat["dow"] = pd.Series(tsd.dayofweek, index=d.index).astype(float) / 4.0 - 0.5
    return feat


def auc(y, p):
    y = np.asarray(y)
    p = np.asarray(p)
    order = np.argsort(p)
    ranks = np.empty(len(p))
    ranks[order] = np.arange(1, len(p) + 1)
    # average ranks for ties
    s = pd.Series(p)
    ranks = s.rank().to_numpy()
    n1 = y.sum()
    n0 = len(y) - n1
    if n0 == 0 or n1 == 0:
        return np.nan
    return (ranks[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)


def walk_forward_daily(tsd, x, y, years_test=range(2017, 2027), lam=10.0, window=None, verbose=True, purge=2):
    years = np.asarray([t.year for t in tsd])
    p = np.full(len(tsd), np.nan)
    for yr in years_test:
        test_start = pd.Timestamp(f"{yr}-01-01", tz="America/New_York")
        test_end = pd.Timestamp(f"{yr + 1}-01-01", tz="America/New_York")
        test = (tsd >= test_start) & (tsd < test_end)
        train = np.where(tsd < test_start)[0]
        train = train[np.isfinite(y[train])]
        train = train[:-purge]  # purge label days that peek into the test
        if window:
            train = train[-window:]
        if len(train) < 60:
            continue
        med = np.nanmedian(x[train], axis=0)
        med = np.where(np.isfinite(med), med, 0.0)
        xf = np.where(np.isfinite(x), x, med)
        mu, sd = standardize_fit(xf[train])
        xs = np.clip((xf - mu) / sd, -6, 6)
        w = logistic_fit(xs[train], y[train], lam=lam, iters=30)
        p[test] = logistic_predict(w, xs[test])
        if verbose:
            a = auc(y[test], p[test])
            acc = np.nanmean((p[test] > 0.5) == (y[test] > 0.5))
            print(f"  {yr}: train n={len(train):4d} test n={test.sum():3d} auc={a:.3f} acc={acc:.3f} base={np.nanmean(y[test]):.3f}")
    return p


def main():
    ts5, o5, c5 = bt.panel(("QQQ", "TQQQ", "BIL"), "2017-01-03", "2026-10-23", "5min")
    tsd, od, cd = bt.panel(("QQQ", "TQQQ", "BIL"), "2017-01-03", "2026-10-23", "1D")
    feat = build_daily_features(ts5, o5, c5, tsd, od, cd)
    x = feat.to_numpy()
    names = list(feat.columns)
    print("features", x.shape, "dates", tsd[0], tsd[-1])
    print("nan share", np.isnan(x).mean().round(3))

    # Label: exact holding-period return if the weight is set at close i and
    # rebalanced after h trading days -> open i+1 to open i+1+h (TQQQ vs BIL).
    n = len(tsd)
    for h in (1, 5, 10, 20):
        fwd_t = np.full(n, np.nan)
        fwd_b = np.full(n, np.nan)
        fwd_t[:-(h + 1)] = np.log(od[h + 1:, 1] / od[1:-(h), 1])
        fwd_b[:-(h + 1)] = np.log(od[h + 1:, 2] / od[1:-(h), 2])
        y = (fwd_t > fwd_b).astype(float)
        y[~np.isfinite(fwd_t) | ~np.isfinite(fwd_b)] = np.nan
        print(f"\n########## horizon {h}d  base={np.nanmean(y):.3f} ##########")
        for window in (None, 750):
            print(f"=== daily WF h={h} window={window} ===")
            p = walk_forward_daily(tsd, x, y, window=window, purge=h + 1)
            np.save(ROOT / "research" / "agents" / "ml-classifier" / f"pd_h{h}_w{window}.npy", p)
            aucs = []
            for yr in range(2017, 2027):
                mm = (np.asarray([t.year for t in tsd]) == yr) & np.isfinite(p) & np.isfinite(y)
                if mm.sum() == 0:
                    continue
                a = auc(y[mm], p[mm])
                aucs.append(a)
                print(f"  {yr}: auc={a:.3f} acc={np.nanmean((p[mm]>.5)==(y[mm]>.5)):.3f} "
                      f"base={np.nanmean(y[mm]):.3f} meanp={np.nanmean(p[mm]):.3f}")
            print(f"  mean AUC {np.nanmean(aucs):.3f}")
            pos = (p > 0.5)
            print("  position days", np.nanmean(pos), "switches", np.nansum(pos[1:] != pos[:-1]))


if __name__ == "__main__":
    main()
