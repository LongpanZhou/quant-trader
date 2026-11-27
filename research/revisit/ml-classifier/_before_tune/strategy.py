"""Standalone causal regime-cluster allocator (QQQ / TQQQ / BIL).

This is a rebuild of the `ml-classifier` research area, not a stripped version of
the old 165-day-SMA overlay.  The old idea was a supervised direction classifier
used as a risk-off filter on a trend base.  This strategy uses unsupervised
machine learning to identify the current market regime and then allocates across
three assets by the regimes' own historical forward returns.

Universe: QQQ (middle risk), TQQQ (aggressive), BIL (defensive).  Long-only.
Signal:   causal k-means clustering of short-horizon market-state features.
Holding:  daily decisions, positions persist until the cluster changes (weeks).
Sizing:   100% in the asset mapped to the current cluster; BIL otherwise.
Risk:     no leverage beyond 100% TQQQ, no shorts, no stop overlay, no 165-day
          QQQ/TQQQ/SPY/NDX moving-average gate.

Backtests are intentionally paused by the user/lead.  `main()` is complete and
will write `result.json` only when it is run; importing this module has no side
effects.

Run from the repo root (only when authorized):

    $env:PYTHONPATH = "C:\\Users\\27175\\AppData\\Local\\Temp\\opencode\\pylibs"
    python research/revisit/ml-classifier/strategy.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402
from minute_marks import to_minutes  # noqa: E402

SYMBOLS = ("QQQ", "TQQQ", "BIL")
DEV_START = "2016-01-04"
DEV_END = "2023-12-29"
TRADE_START = "2017-01-03"
BARS_1M = 252 * 390

# Primary specification (chosen before any backtest; see report.md).
K = 3
TRAIN_WINDOW = 750
MIN_TRAIN = 150
HORIZON = 20          # forward-return horizon used to rank clusters
BAND = 0.02
CONFIRM_DAYS = 2      # a new regime must persist this many days before switching
CONFIDENCE_Q = None   # primary: no confidence filter; variant: 0.95


# ---------------------------------------------------------------------------
# Features: all backward-looking, no 100-250 day price moving average
# ---------------------------------------------------------------------------
def minute_daily(ts5: pd.DatetimeIndex, o5: np.ndarray, c5: np.ndarray) -> pd.DataFrame:
    """Causal daily aggregates of the 5-minute bars (same-day information only)."""
    q = c5[:, 0]
    lr = np.zeros(len(ts5))
    lr[1:] = np.log(q[1:] / q[:-1])
    d = pd.DataFrame({
        "date": ts5.date,
        "o": o5[:, 0],
        "q": q,
        "hi": np.maximum(o5[:, 0], q),
        "lo": np.minimum(o5[:, 0], q),
        "lr": lr,
        "pv": (o5[:, 0] + q) / 2.0,
    })
    g = d.groupby("date", sort=True)
    out = pd.DataFrame({
        "day_open": g["o"].first(),
        "day_close": g["q"].last(),
        "day_high": g["hi"].max(),
        "day_low": g["lo"].min(),
        "rv5": g["lr"].std(ddof=0),
        "first30": g.apply(
            lambda x: x["q"].iloc[min(5, len(x) - 1)] / x["o"].iloc[0] - 1.0,
            include_groups=False,
        ),
        "last30": g.apply(
            lambda x: x["q"].iloc[-1] / x["q"].iloc[max(0, len(x) - 7)] - 1.0,
            include_groups=False,
        ),
        "vwap": g.apply(lambda x: x["pv"].mean(), include_groups=False),
        "close_loc": g.apply(
            lambda x: (x["q"].iloc[-1] - x["lo"].min()) /
            max(x["hi"].max() - x["lo"].min(), 1e-9),
            include_groups=False,
        ),
    })
    out["vwap_dist"] = out["day_close"] / out["vwap"] - 1.0
    out["gap"] = out["day_open"] / out["day_close"].shift(1) - 1.0
    out["intraday"] = out["day_close"] / out["day_open"] - 1.0
    return out


def build_features(ts5, o5, c5, tsd, od, cd) -> pd.DataFrame:
    """23 short-horizon state features.  No 100-250 day price MA is used."""
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
    f["q_r1"] = ret(d.q, 1)
    f["q_r5"] = ret(d.q, 5)
    f["q_r20"] = ret(d.q, 20)
    f["q_r60"] = ret(d.q, 60)
    f["rv5"] = rstd(5)
    f["rv20"] = rstd(20)
    f["rv60"] = rstd(60)
    f["rv_ratio_20_60"] = f["rv20"] / f["rv60"]
    f["vol_change"] = f["rv20"] - f["rv60"]
    delta = d.q.diff()
    up = delta.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
    dn = (-delta).clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
    f["rsi14"] = (100 - 100 / (1 + up / dn.clip(lower=1e-12))) / 100 - 0.5
    f["dd20"] = d.q / d.q.rolling(20, min_periods=10).max() - 1.0
    f["dd60"] = d.q / d.q.rolling(60, min_periods=20).max() - 1.0
    for k in (10, 20, 50):
        f[f"ema{k}_dist"] = d.q / d.q.ewm(span=k, adjust=False).mean() - 1.0
    f["overnight20"] = md["gap"].rolling(20, min_periods=10).mean().to_numpy()
    f["intraday20"] = md["intraday"].rolling(20, min_periods=10).mean().to_numpy()
    f["rv5_20"] = md["rv5"].rolling(20, min_periods=10).mean().to_numpy()
    f["decay20"] = ret(d.t, 20) - 3.0 * f["q_r20"]
    f["bil_r20"] = ret(d.b, 20)
    f["skew20"] = lrq.rolling(20, min_periods=10).skew()
    f["short_vs_med"] = f["q_r5"] - f["q_r20"]
    f["dow"] = pd.Series(tsd.day_of_week, index=d.index).astype(float) / 4.0 - 0.5
    return f


# ---------------------------------------------------------------------------
# Causal k-means
# ---------------------------------------------------------------------------
def _assign(x: np.ndarray, centroids: np.ndarray):
    d2 = ((x[:, None, :] - centroids[None, :, :]) ** 2).sum(axis=2)
    labels = d2.argmin(axis=1)
    return labels, np.sqrt(d2[np.arange(len(x)), labels])


def kmeans_fit(x: np.ndarray, k: int, seed: int = 7, n_init: int = 8, iters: int = 60):
    """Deterministic k-means++ (fixed seed), with empty-cluster protection."""
    rng = np.random.default_rng(seed)
    best_inertia = np.inf
    best_centroids = None
    n = len(x)
    for _ in range(n_init):
        centroids = [x[rng.integers(n)]]
        for _ in range(1, k):
            dist2 = np.min(
                ((x[:, None, :] - np.array(centroids)[None, :, :]) ** 2).sum(axis=2),
                axis=1,
            )
            total = dist2.sum()
            if total <= 0:
                centroids.append(x[rng.integers(n)])
            else:
                centroids.append(x[rng.choice(n, p=dist2 / total)])
        centroids = np.array(centroids, dtype=float)
        for _ in range(iters):
            labels, _ = _assign(x, centroids)
            new = centroids.copy()
            for j in range(k):
                members = x[labels == j]
                if len(members):
                    new[j] = members.mean(axis=0)
            if np.allclose(new, centroids):
                break
            centroids = new
        labels, _ = _assign(x, centroids)
        inertia = float(((x - centroids[labels]) ** 2).sum())
        if inertia < best_inertia:
            best_inertia = inertia
            best_centroids = centroids
    return best_centroids


# ---------------------------------------------------------------------------
# Walk-forward regime mapping
# ---------------------------------------------------------------------------
def _forward_returns(od: np.ndarray, rows: np.ndarray, horizon: int):
    """Open i+1 -> open i+1+horizon, for each training row i."""
    ft = np.log(od[rows + 1 + horizon, 1] / od[rows + 1, 1])
    fq = np.log(od[rows + 1 + horizon, 0] / od[rows + 1, 0])
    fb = np.log(od[rows + 1 + horizon, 2] / od[rows + 1, 2])
    return ft, fq, fb


def _map_clusters(ft, fq, labels, k, min_members=20):
    """Rank clusters by historical forward TQQQ return and map to assets.

    Best cluster -> TQQQ if its forward TQQQ return is positive, else BIL.
    Second cluster -> QQQ if k >= 3 and its forward QQQ return is positive, else BIL.
    Remaining clusters -> BIL.
    """
    stats = []
    for j in range(k):
        m = labels == j
        if m.sum() < min_members:
            stats.append((j, -np.inf, -np.inf, int(m.sum())))
        else:
            stats.append((j, float(np.nanmean(ft[m])), float(np.nanmean(fq[m])), int(m.sum())))
    stats.sort(key=lambda s: s[1], reverse=True)
    mapping = {}
    best = stats[0]
    mapping[best[0]] = 1 if best[1] > 0 else 2          # TQQQ or BIL
    if k >= 3:
        second = stats[1]
        mapping[second[0]] = 0 if second[2] > 0 else 2  # QQQ or BIL
    for s in stats[(2 if k >= 3 else 1):]:
        mapping[s[0]] = 2                                # BIL
    return mapping, stats


def build_weights(tsd: pd.DatetimeIndex, features: pd.DataFrame, od: np.ndarray,
                  cd: np.ndarray, k: int = K, train_window: int = TRAIN_WINDOW,
                  min_train: int = MIN_TRAIN, horizon: int = HORIZON,
                  confirm_days: int = CONFIRM_DAYS,
                  confidence_q: float | None = CONFIDENCE_Q):
    """Daily target weights (TQQQ, QQQ, BIL), set at each close, filled next open.

    The model is refit on the first trading day of each month using only data
    through the prior trading day.  Training rows whose forward label would
    extend beyond that prior day are removed, so the regime map cannot peek into
    the month in which it is used.
    """
    x = features.to_numpy(dtype=float)
    n = len(tsd)
    w = np.zeros((n, 3))
    w[:, 2] = 1.0  # BIL until the first valid fit
    info = {"refits": [], "switches": 0, "assets": []}

    # First trading day of each month, 2017-01 through 2023-12.
    month_starts = pd.date_range("2017-01-01", "2023-12-01", freq="MS",
                                 tz="America/New_York")
    refit_idx = []
    for m in month_starts:
        j = int(tsd.searchsorted(m))
        if j < n and (not refit_idx or j > refit_idx[-1]):
            refit_idx.append(j)
    refit_idx.append(n)  # sentinel end

    current_asset = 2          # start in BIL
    pending_asset = None
    pending_count = 0

    for r in range(len(refit_idx) - 1):
        j0, j1 = refit_idx[r], refit_idx[r + 1]
        train_end = j0 - 1
        mapping = {c: 2 for c in range(k)}
        centroids = None
        mu = sd = None
        conf_thr = None
        if train_end >= min_train:
            lo = max(0, train_end - train_window + 1)
            rows = np.arange(lo, train_end + 1)
            rows = rows[np.isfinite(x[rows]).all(axis=1)]
            # Purge by index distance, not by row count: a training row's
            # 20-day forward label must end on or before train_end.  This is
            # robust to missing rows in the middle of the window.
            rows = rows[rows <= train_end - horizon - 1]
            if len(rows) >= min_train:
                mu = np.nanmean(x[rows], axis=0)
                sd = np.nanstd(x[rows], axis=0)
                mu = np.where(np.isfinite(mu), mu, 0.0)
                sd = np.where(np.isfinite(sd) & (sd > 1e-12), sd, 1.0)
                xs = np.clip((x[rows] - mu) / sd, -6, 6)
                centroids = kmeans_fit(xs, k)
                labels, dist = _assign(xs, centroids)
                ft, fq, _fb = _forward_returns(od, rows, horizon)
                mapping, stats = _map_clusters(ft, fq, labels, k)
                if confidence_q is not None:
                    conf_thr = float(np.quantile(dist, confidence_q))
                info["refits"].append({
                    "date": str(tsd[j0].date()),
                    "train_rows": int(len(rows)),
                    "mapping": {int(c): int(a) for c, a in mapping.items()},
                    "cluster_fwd_tqqq": {int(s[0]): float(s[1]) for s in stats},
                })
        for i in range(j0, j1):
            if centroids is None or not np.isfinite(x[i]).all():
                asset_new = 2
            else:
                z = np.clip((x[i] - mu) / sd, -6, 6)
                lab, dist = _assign(z[None, :], centroids)
                asset_new = mapping.get(int(lab[0]), 2)
                if conf_thr is not None and dist[0] > conf_thr:
                    asset_new = 2
            # Persistence filter: a new asset must be confirmed for
            # `confirm_days` consecutive sessions before the book switches.
            if asset_new == current_asset:
                pending_asset = None
                pending_count = 0
            elif asset_new == pending_asset:
                pending_count += 1
                if pending_count >= confirm_days:
                    current_asset = asset_new
                    pending_asset = None
                    pending_count = 0
            else:
                pending_asset = asset_new
                pending_count = 1
            w[i, :] = 0.0
            w[i, current_asset] = 1.0
            if i > 0:
                prev = int(np.argmax(w[i - 1]))
                if prev != current_asset:
                    info["switches"] += 1
            info["assets"].append(int(current_asset))

    # The final row's target is never filled by the simulator; harmless.
    return w, info


# ---------------------------------------------------------------------------
# Benchmarks / evaluation
# ---------------------------------------------------------------------------
def correlation_benchmark_weights(tsd, cd):
    """The old 165-day baseline, used ONLY for the required correlation test.

    This function is deliberately outside `build_weights`; the strategy never
    uses this gate or these weights for trading.
    """
    q = cd[:, 0]
    sma = pd.Series(q).rolling(165, min_periods=100).mean().to_numpy()
    on = q > sma
    w = np.zeros((len(tsd), 3))
    w[:, 1] = on.astype(float)
    w[:, 2] = 1.0 - w[:, 1]
    return w


def session_returns(ts: pd.DatetimeIndex, equity: np.ndarray) -> pd.Series:
    s = pd.Series(equity, index=ts)
    last = s.groupby(s.index.normalize()).last()
    return last.pct_change().dropna()


def _window_stats(ts1, o1, c1, w1, start, end, bars, slip):
    i0 = bt.start_index(ts1, start)
    # Include the whole end session (searchsorted alone would stop at its 09:30 bar).
    i1 = int(ts1.searchsorted(
        pd.Timestamp(end, tz="America/New_York") + pd.Timedelta(days=1)
    ))
    r = bt.simulate(ts1[i0:i1], o1[i0:i1], c1[i0:i1], w1[i0:i1],
                    band=BAND, slippage_bps=slip)
    s = bt.stats(r, bars)
    return r, s


def main():
    # Load only development data.  The holdout is never touched here.
    ts5, o5, c5 = bt.panel(SYMBOLS, DEV_START, DEV_END, "5min")
    tsd, od, cd = bt.panel(SYMBOLS, DEV_START, DEV_END, "1D")
    ts1, o1, c1 = bt.panel(SYMBOLS, DEV_START, DEV_END, "1min")

    feats = build_features(ts5, o5, c5, tsd, od, cd)
    w, info = build_weights(tsd, feats, od, cd)
    w1 = to_minutes(tsd, w, ts1, "1D")
    wb = correlation_benchmark_weights(tsd, cd)
    wb1 = to_minutes(tsd, wb, ts1, "1D")

    out = {
        "agent": "ml-classifier",
        "original": "research/agents/ml-classifier",
        "status": "pending_test",
        "idea": "Unsupervised regime clustering allocates TQQQ/QQQ/BIL by each cluster's past forward returns.",
        "hypothesis": "A causal k-means fit on short-horizon market-state features identifies persistent regimes; the historically strongest regime deserves TQQQ, the second QQQ, the rest BIL.",
        "universe": ["QQQ", "TQQQ", "BIL"],
        "frozen_commit": None,
        "variants_tried": 0,
        "corr_vs_165d_baseline": None,
        "max_corr_vs_other_rebuilds": None,
        "windows": {"dev": {}, "holdout": None, "10y": None, "5y": None},
        "marks": "1m",
        "benchmarks": {},
    }

    print(f"refits={len(info['refits'])} switches={info['switches']}", flush=True)
    for slip_label, slip in (("1bp", 1.0), ("5bp", 5.0), ("10bp", 10.0)):
        r, s = _window_stats(ts1, o1, c1, w1, TRADE_START, DEV_END, BARS_1M, slip)
        out["windows"]["dev"][slip_label] = {
            "cagr": float(s["cagr"]),
            "max_drawdown": float(s["max_drawdown"]),
            "sharpe": float(s["sharpe"]),
            "fills": int(s["fills"]),
            "turnover": float(s["turnover"]),
            "exposure": float(s["exposure"]),
        }
        print(f"dev {slip_label}: CAGR {s['cagr']*100:6.2f}% DD {s['max_drawdown']*100:5.2f}% "
              f"Sharpe {s['sharpe']:4.2f} fills {s['fills']}", flush=True)

    # Daily-return correlation with the old 165-day baseline on the same minutes.
    rb = bt.run(ts1, o1, c1, wb1, TRADE_START, band=BAND, slippage_bps=1.0)
    rs = bt.run(ts1, o1, c1, w1, TRADE_START, band=BAND, slippage_bps=1.0)
    a = session_returns(rs["ts"], rs["equity"])
    b = session_returns(rb["ts"], rb["equity"])
    joined = pd.concat([a.rename("s"), b.rename("b")], axis=1).dropna()
    out["corr_vs_165d_baseline"] = float(joined["s"].corr(joined["b"]))
    print(f"corr vs 165d baseline: {out['corr_vs_165d_baseline']:.3f}", flush=True)

    # Daily benchmarks for context (daily marks).
    i0 = bt.start_index(tsd, TRADE_START)
    for name, col in (("tqqq", 1), ("qqq", 0), ("bil", 2)):
        bm = bt.benchmark(cd[i0:, col], tsd[i0:], 252)
        out["benchmarks"][name] = {
            "cagr": float(bm["cagr"]),
            "max_drawdown": float(bm["max_drawdown"]),
            "sharpe": float(bm["sharpe"]),
        }

    path = ROOT / "research" / "revisit" / "ml-classifier" / "result.json"
    path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print("wrote", path)


if __name__ == "__main__":
    main()
