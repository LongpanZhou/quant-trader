"""Standalone leverage-decay timing strategy (revisit of ml-crash-overlay-winner).

The original strategy was a walk-forward classifier of a 20-session TQQQ crash
layered on the shared 165-day QQQ/TQQQ base.  This rebuild keeps only the
genuinely new idea -- a walk-forward ML classifier of a future crash/decay
regime -- and gives it its own universe, label, holding period, sizing and risk.

The new thesis is leverage-decay timing.  TQQQ's 3x daily reset makes its return
path-dependent: in a choppy/high-volatility path TQQQ lags 3x QQQ, while in a
smooth/trending path the leverage is favorable.  A walk-forward logistic model
predicts whether the next five sessions will be in the worst quartile of
TQQQ-vs-3xQQQ decay.  The position follows the prediction:

    rank < 0.15          -> TQQQ 100%   (leverage favorable)
    0.15 <= rank < 0.70  -> QQQ 100%    (no decay, keep equity beta)
    rank >= 0.70         -> BIL 100%    (high decay / crash risk)

There is no 100-250 day moving-average gate and no call to, or copy of, the old
base weights.  The 165-day baseline appears only in the correlation benchmark.

BACKTESTS ARE PAUSED (2026-11-26).  This file is the implementation of the spec
in report.md; it has not been run.  When the lead authorises the test, run:

    $env:PYTHONPATH = "C:\\Users\\27175\\AppData\\Local\\Temp\\opencode\\pylibs"
    python research/strategies/ml-crash-overlay-winner/strategy.py            # dev only
    python research/strategies/ml-crash-overlay-winner/strategy.py --full     # lead only
    python research/strategies/ml-crash-overlay-winner/strategy.py --neighbourhood
"""
from __future__ import annotations

import argparse
import json
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402
from minute_marks import to_minutes  # noqa: E402

DEV_START, DEV_END = "2016-01-04", "2023-12-29"
FULL_START, FULL_END = "2017-01-03", "2026-10-23"
HOLD_START = "2024-01-02"
BARS_1M = 252 * 390
SYMS = ("QQQ", "TQQQ", "BIL")

Q_TQQQ = 0.15
Q_BIL = 0.70
MIN_HOLD = 5
LABEL_Q = 0.25
HORIZON = 5
WINDOW = 750
LAM = 10.0
RANK_WINDOW = 252
OUT = Path(__file__).resolve().parent

# 37 features, all causal through the decision close, all windows <= 120 days.
# There is no 100-250 day price moving average anywhere in this list.
FEATURES = [
    "r1", "r2", "r5", "r10", "r20", "r60",
    "rv1", "rv5", "rv20", "rv60", "rv_ratio", "rv_pct",
    "skew1", "skew20", "dvol", "dvol20",
    "vwap_dist", "dd_high", "first30", "last30", "close_loc",
    "gap", "gap20", "intraday", "up20", "dd20", "dd60", "sma20",
    "rsi14", "decay5", "decay20", "bil5", "dow",
    "range", "range20", "vol_ratio", "vol_z20",
]


# ---------------------------------------------------------------------------
# Causal daily features from 1-minute bars
# ---------------------------------------------------------------------------
def daily_from_1m(ts, o, c, v):
    dates = bt.session_dates(ts)
    bounds = np.flatnonzero(np.r_[True, dates[1:] != dates[:-1]])
    bounds = np.r_[bounds, len(dates)]
    rows = []
    for j in range(len(bounds) - 1):
        a, b = bounds[j], bounds[j + 1]
        qo, qc, qv = o[a:b, 0], c[a:b, 0], v[a:b, 0]
        lr = np.diff(np.log(qc))
        vwap = float(np.sum(qc * qv) / max(np.sum(qv), 1e-9))
        mu = lr.mean() if len(lr) else 0.0
        sd = lr.std(ddof=0) if len(lr) else 0.0
        sk = float(np.mean(((lr - mu) / sd) ** 3)) if sd > 0 else 0.0
        k30 = min(30, len(qc) - 1)
        rows.append({
            "date": dates[a], "qo": qo[0], "qc": qc[-1], "qh": qc.max(), "ql": qc.min(),
            "qv": float(qv.sum()), "rv1": float(sd), "skew1": sk,
            "dvol": float(np.sqrt(np.mean(np.minimum(lr, 0.0) ** 2))) if len(lr) else 0.0,
            "vwap": vwap, "dd_high": float(qc[-1] / qc.max() - 1.0),
            "first30": float(qc[k30] / qo[0] - 1.0) if len(qc) > 1 else 0.0,
            "last30": float(qc[-1] / qc[max(0, len(qc) - 31)] - 1.0),
            "close_loc": float((qc[-1] - qc.min()) / max(qc.max() - qc.min(), 1e-9)),
        })
    return pd.DataFrame(rows).set_index("date")


def build_features(ts, o, c, v):
    dd = daily_from_1m(ts, o, c, v)
    q = pd.Series(dd["qc"].to_numpy(), index=pd.DatetimeIndex(dd.index))
    dates = bt.session_dates(ts)
    first = np.flatnonzero(np.r_[True, dates[1:] != dates[:-1]])
    last = np.r_[first[1:] - 1, len(dates) - 1]
    t = pd.Series(c[last, 1], index=q.index)
    b = pd.Series(c[last, 2], index=q.index)
    qo = pd.Series(o[first, 0], index=q.index)

    f = pd.DataFrame(index=q.index)
    lr = np.log(q / q.shift(1))
    for k in (1, 2, 5, 10, 20, 60):
        f[f"r{k}"] = np.log(q / q.shift(k))
    f["rv1"] = dd["rv1"]
    f["rv5"] = dd["rv1"].rolling(5).mean()
    f["rv20"] = dd["rv1"].rolling(20).mean()
    f["rv60"] = dd["rv1"].rolling(60).mean()
    f["rv_ratio"] = f["rv5"] / f["rv60"]
    f["rv_pct"] = f["rv5"].rolling(120, min_periods=40).rank(pct=True)
    f["skew1"] = dd["skew1"]
    f["skew20"] = dd["skew1"].rolling(20).mean()
    f["dvol"] = dd["dvol"]
    f["dvol20"] = dd["dvol"].rolling(20).mean()
    f["vwap_dist"] = q / dd["vwap"] - 1.0
    f["dd_high"] = dd["dd_high"]
    f["first30"] = dd["first30"]
    f["last30"] = dd["last30"]
    f["close_loc"] = dd["close_loc"]
    f["gap"] = qo / q.shift(1) - 1.0
    f["gap20"] = f["gap"].rolling(20).mean()
    f["intraday"] = q / qo - 1.0
    f["up20"] = (lr > 0).rolling(20).mean() - 0.5
    f["dd20"] = q / q.rolling(20).max() - 1.0
    f["dd60"] = q / q.rolling(60).max() - 1.0
    f["sma20"] = q / q.rolling(20).mean() - 1.0
    delta = q.diff()
    up = delta.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
    dn = (-delta).clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
    f["rsi14"] = (100 - 100 / (1 + up / dn.clip(lower=1e-12))) / 100 - 0.5
    f["decay5"] = np.log(t / t.shift(5)) - 3.0 * np.log(q / q.shift(5))
    f["decay20"] = np.log(t / t.shift(20)) - 3.0 * np.log(q / q.shift(20))
    f["bil5"] = np.log(b / b.shift(5))
    f["dow"] = pd.Series(q.index, index=q.index).apply(lambda x: x.weekday()).astype(float) / 4 - 0.5
    f["range"] = dd["qh"] / dd["ql"] - 1.0
    f["range20"] = f["range"].rolling(20).mean()
    f["vol_ratio"] = dd["qv"] / dd["qv"].rolling(20).mean()
    f["vol_z20"] = (dd["qv"] - dd["qv"].rolling(20).mean()) / dd["qv"].rolling(20).std(ddof=0)
    return f


def forward_decay(od, cd, horizon=HORIZON):
    """Tradable open-to-open decay: entry at the next open, exit h sessions later.

    Row t is known at the open of t+1+h, hence the h+1-session purge below.
    """
    n = len(od)
    out = np.full(n, np.nan)
    for t in range(n - horizon - 1):
        out[t] = (np.log(od[t + 1 + horizon, 1] / od[t + 1, 1])
                  - 3.0 * np.log(od[t + 1 + horizon, 0] / od[t + 1, 0]))
    return out


# ---------------------------------------------------------------------------
# Walk-forward logistic model
# ---------------------------------------------------------------------------
def logistic_fit(x, y, lam=LAM, iters=30):
    n, d = x.shape
    xb = np.column_stack([np.ones(n), x])
    w = np.zeros(d + 1)
    reg = np.full(d + 1, lam)
    reg[0] = 0.0
    for _ in range(iters):
        p = 1.0 / (1.0 + np.exp(-np.clip(xb @ w, -35, 35)))
        g = xb.T @ (p - y) + reg * w
        s = np.maximum(p * (1 - p), 1e-6)
        h = xb.T @ (xb * s[:, None]) + np.diag(reg + 1e-9)
        step = np.linalg.solve(h, g)
        w -= step
        if np.max(np.abs(step)) < 1e-7:
            break
    return w


def walk_forward_decay(dts, x, decay, horizon=HORIZON, window=WINDOW, lam=LAM,
                       label_q=LABEL_Q, first_year=2016, last_year=2023):
    """Annual walk-forward probabilities and test labels.

    The threshold is the label_q quantile of the training labels only.  The
    last horizon+1 training rows are purged so no training label overlaps the
    test year.  Returns (p, y_test, threshold).
    """
    decay = np.asarray(decay, dtype=float)
    p = np.full(len(dts), np.nan)
    y_test = np.full(len(dts), np.nan)
    thresholds = np.full(len(dts), np.nan)
    tz = getattr(dts, "tz", None)
    for year in range(first_year, last_year + 1):
        start = pd.Timestamp(f"{year}-01-01", tz=tz)
        end = pd.Timestamp(f"{year + 1}-01-01", tz=tz)
        test = (dts >= start) & (dts < end)
        tr = np.where(dts < start)[0]
        tr = tr[np.isfinite(decay[tr])]
        tr = tr[:-(horizon + 1)]
        if window:
            tr = tr[-window:]
        if len(tr) < 60:
            continue
        thr = float(np.nanquantile(decay[tr], label_q))
        ytr = (decay[tr] < thr).astype(float)
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
        w = logistic_fit(xs[tr], ytr, lam=lam)
        xb = np.column_stack([np.ones(test.sum()), xs[test]])
        p[test] = 1.0 / (1.0 + np.exp(-np.clip(xb @ w, -35, 35)))
        y_test[test] = (decay[test] < thr).astype(float)
        thresholds[test] = thr
    return p, y_test, thresholds


# ---------------------------------------------------------------------------
# Position rule
# ---------------------------------------------------------------------------
def state_weights(rank, q_tqqq=Q_TQQQ, q_bil=Q_BIL, min_hold=MIN_HOLD):
    """Three-state long-only map: 0=QQQ, 1=TQQQ, 2=BIL.

    A state is held for at least `min_hold` sessions before a normal switch.
    A crossing into the high-risk BIL state exits immediately (crash exit).
    """
    n = len(rank)
    state = np.zeros(n, dtype=np.int64)
    cur = 0
    held = 0
    for i in range(n):
        r = rank[i]
        if not np.isfinite(r):
            target = 0
        elif r < q_tqqq:
            target = 1
        elif r >= q_bil:
            target = 2
        else:
            target = 0
        if target == 2 and cur != 2:
            cur = 2
            held = 0
        elif target != cur and held >= min_hold:
            cur = target
            held = 0
        held += 1
        state[i] = cur
    w = np.zeros((n, 3))
    w[state == 0, 0] = 1.0
    w[state == 1, 1] = 1.0
    w[state == 2, 2] = 1.0
    return w, state


# ---------------------------------------------------------------------------
# Build the strategy
# ---------------------------------------------------------------------------
def build_weights(ts1, o1, c1, tsd, od, cd, last_year=2023):
    vol = bt.load_1m("QQQ").set_index("ts")["volume"].reindex(ts1).fillna(0.0).to_numpy()
    f = build_features(ts1, o1, c1, np.column_stack([vol, vol, vol]))

    dts = pd.DatetimeIndex(tsd).tz_localize(None)
    f.index = pd.DatetimeIndex(f.index)
    f = f.reindex(dts).ffill()
    x = f[FEATURES].to_numpy()
    decay = forward_decay(od, cd, HORIZON)

    p, y_test, thresholds = walk_forward_decay(dts, x, decay, last_year=last_year)
    rank = pd.Series(p).rolling(RANK_WINDOW, min_periods=60).rank(pct=True).to_numpy()
    w_daily, state = state_weights(rank)

    info = {
        "features": FEATURES,
        "n_features": len(FEATURES),
        "last_year": last_year,
        "state_days": {},
        "state_share": {},
        "n_switches": 0,
        "mean_threshold": float(np.nanmean(thresholds)),
        "auc_by_year": {},
        "mean_decay_by_state": {},
    }
    dev = np.asarray(dts >= pd.Timestamp(DEV_START))
    for k in (0, 1, 2):
        info["state_days"][str(k)] = int(((state == k) & dev).sum())
        info["state_share"][str(k)] = float(((state == k) & dev).sum() / max(dev.sum(), 1))
    info["n_switches"] = int(np.sum((state[1:] != state[:-1]) & dev[1:]))
    for year in range(2016, last_year + 1):
        m = (dts.year == year) & np.isfinite(p) & np.isfinite(y_test)
        if m.sum() < 40:
            continue
        pp, yy = p[m], y_test[m]
        pos, neg = pp[yy == 1], pp[yy == 0]
        if len(pos) and len(neg):
            auc = (np.sum(pos[:, None] > neg[None, :])
                   + 0.5 * np.sum(pos[:, None] == neg[None, :])) / (len(pos) * len(neg))
        else:
            auc = np.nan
        info["auc_by_year"][str(year)] = float(auc)
    for k in (0, 1, 2):
        m = (state == k) & dev & np.isfinite(decay)
        info["mean_decay_by_state"][str(k)] = float(np.nanmean(decay[m])) if m.sum() else np.nan

    w1 = to_minutes(tsd, w_daily, ts1, "1D")
    return w1, w_daily, state, p, y_test, rank, decay, info


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------
def daily_returns(result):
    eq = pd.Series(result["equity"], index=result["ts"])
    d = eq.groupby(eq.index.date).last()
    d.index = pd.DatetimeIndex(d.index)
    return d.pct_change().dropna()


def baseline_weights(tsd, cd):
    """The old 165-day baseline, used ONLY as a correlation benchmark."""
    q = pd.Series(cd[:, 0], index=pd.DatetimeIndex(tsd))
    on = (q > q.rolling(165, min_periods=100).mean()).to_numpy().copy()
    on[:1] = False
    w = np.zeros((len(cd), 3))
    w[:, 1] = on
    w[:, 2] = 1.0 - on
    return w


def window_metrics(ts1, o1, c1, w1, start, slip):
    r = bt.run(ts1, o1, c1, w1, start, band=0.02, slippage_bps=slip)
    s = bt.stats(r, BARS_1M)
    return r, {k: float(v) for k, v in s.items() if k != "years"}


def corr_vs_baseline(ts1, o1, c1, tsd, od, cd, w1, start):
    r = bt.run(ts1, o1, c1, w1, start, band=0.02, slippage_bps=1.0)
    sr = daily_returns(r)
    wb = baseline_weights(tsd, cd)
    wb1 = to_minutes(tsd, wb, ts1, "1D")
    rb = bt.run(ts1, o1, c1, wb1, start, band=0.02, slippage_bps=1.0)
    br = daily_returns(rb)
    idx = sr.index.intersection(br.index)
    return float(np.corrcoef(sr.loc[idx].to_numpy(), br.loc[idx].to_numpy())[0, 1])


def benchmark_1m(ts1, c1, col, start):
    i = bt.start_index(ts1, start)
    return bt.benchmark(c1[i:, col], ts1[i:], BARS_1M)


# ---------------------------------------------------------------------------
# Optional ±1-step neighbourhood (uses bt.run_many in batches)
# ---------------------------------------------------------------------------
def run_neighbourhood(ts1, o1, c1, tsd, od, cd, last_year=2023, slip=1.0):
    vol = bt.load_1m("QQQ").set_index("ts")["volume"].reindex(ts1).fillna(0.0).to_numpy()
    f = build_features(ts1, o1, c1, np.column_stack([vol, vol, vol]))
    dts = pd.DatetimeIndex(tsd).tz_localize(None)
    f.index = pd.DatetimeIndex(f.index)
    f = f.reindex(dts).ffill()
    x = f[FEATURES].to_numpy()
    decay = forward_decay(od, cd, HORIZON)

    rows = []
    for label_q in (0.20, 0.25, 0.30):
        p, _, _ = walk_forward_decay(dts, x, decay, label_q=label_q, last_year=last_year)
        for rank_window in (120, 252):
            rank = (pd.Series(p).rolling(rank_window,
                                         min_periods=(60 if rank_window >= 252 else 40))
                    .rank(pct=True).to_numpy())
            combos = [(qt, qb, mh) for qt in (0.10, 0.15, 0.20)
                      for qb in (0.65, 0.70, 0.75) for mh in (3, 5, 10)]
            for a in range(0, len(combos), 9):
                batch = combos[a:a + 9]
                mats = []
                for qt, qb, mh in batch:
                    wd, _ = state_weights(rank, qt, qb, mh)
                    mats.append(to_minutes(tsd, wd, ts1, "1D"))
                results = bt.run_many(ts1, o1, c1, mats, start=DEV_START,
                                      band=0.02, slippage_bps=slip)
                for (qt, qb, mh), r in zip(batch, results):
                    s = bt.stats(r, BARS_1M)
                    rows.append({"label_q": label_q, "rank_window": rank_window,
                                 "q_tqqq": qt, "q_bil": qb,
                                 "min_hold": mh, "cagr": float(s["cagr"]),
                                 "max_drawdown": float(s["max_drawdown"]),
                                 "sharpe": float(s["sharpe"]), "fills": int(s["fills"])})
    return rows


# ---------------------------------------------------------------------------
def main():
    warnings.filterwarnings("ignore")
    parser = argparse.ArgumentParser()
    parser.add_argument("--full", action="store_true",
                        help="also produce 10y/5y/holdout windows (lead only)")
    parser.add_argument("--neighbourhood", action="store_true",
                        help="run the 81-point +/-1-step neighbourhood on dev")
    args = parser.parse_args()

    end = FULL_END if args.full else DEV_END
    # Start at DEV_START so the 2015 warm-up is available for the 2016 fold.
    ts1, o1, c1 = bt.panel(SYMS, DEV_START, end, "1min")
    tsd, od, cd = bt.panel(SYMS, DEV_START, end, "1D")
    last_year = 2026 if args.full else 2023

    w1, wd, state, p, y_test, rank, decay, info = build_weights(
        ts1, o1, c1, tsd, od, cd, last_year=last_year)

    out = {
        "agent": "ml-crash-overlay-winner",
        "original": "research/agents2/ml-crash-overlay-winner",
        "status": "pending",
        "idea": ("TQQQ's 3x daily reset makes leverage favorable only when the path is "
                 "smooth; a walk-forward ML classifier of 5-session TQQQ-vs-3xQQQ decay "
                 "rotates between TQQQ, QQQ and BIL."),
        "hypothesis": ("A causal classifier of the worst-quartile 5-session decay can time "
                       "when to use TQQQ instead of QQQ, and when to hold BIL, with a lower "
                       "drawdown than the old 165-day TQQQ base and correlation < 0.60."),
        "universe": ["QQQ", "TQQQ", "BIL"],
        "frozen_commit": None,
        "variants_tried": 0,
        "corr_vs_165d_baseline": None,
        "max_corr_vs_other_rebuilds": None,
        "windows": {"dev": {}, "holdout": None, "10y": None, "5y": None},
        "marks": "1m",
        "benchmarks": {},
        "diagnostics": info,
        "rules": {
            "label": "5-session open-to-open TQQQ-vs-3xQQQ decay < training-window 25th percentile",
            "model": "L2 logistic, lambda 10, 750-session rolling window, annual retrain, 6-session purge",
            "rank": "trailing 252-session percentile of the probability, min 60",
            "states": "rank<0.15 TQQQ; 0.15<=rank<0.70 QQQ; rank>=0.70 BIL",
            "holding": "minimum 5 sessions; immediate BIL exit on a high-risk crossing",
            "sizing": "100% one asset, long-only, no leverage, no shorts",
            "fills": "next bar open, 2% band",
        },
    }

    for slip in (1.0, 5.0, 10.0):
        _, s = window_metrics(ts1, o1, c1, w1, DEV_START, slip)
        out["windows"]["dev"][f"{int(slip)}bp"] = {
            "cagr": s["cagr"], "max_drawdown": s["max_drawdown"],
            "sharpe": s["sharpe"], "sortino": s["sortino"], "vol": s["volatility"],
            "fills": int(s["fills"]), "exposure": s["exposure"], "turnover": s["turnover"],
        }
    out["corr_vs_165d_baseline"] = corr_vs_baseline(
        ts1, o1, c1, tsd, od, cd, w1, DEV_START)
    out["benchmarks"]["tqqq"] = benchmark_1m(ts1, c1, 1, DEV_START)
    out["benchmarks"]["qqq"] = benchmark_1m(ts1, c1, 0, DEV_START)
    out["benchmarks"]["spy"] = None  # historical 1m SPY is not local

    orig = ROOT / "research" / "agents2" / "ml-crash-overlay-winner" / "result.json"
    if orig.exists():
        o = json.loads(orig.read_text(encoding="utf-8"))
        out["benchmarks"]["original"] = {
            "10y_1bp": o.get("windows", {}).get("10y", {}),
            "5y_1bp": o.get("windows", {}).get("5y", {}),
        }

    if args.full:
        for label, start in (("10y", FULL_START), ("5y", "2021-10-25"), ("holdout", HOLD_START)):
            out["windows"][label] = {}
            for slip in (1.0, 5.0, 10.0):
                _, s = window_metrics(ts1, o1, c1, w1, start, slip)
                out["windows"][label][f"{int(slip)}bp"] = {
                    "cagr": s["cagr"], "max_drawdown": s["max_drawdown"],
                    "sharpe": s["sharpe"], "sortino": s["sortino"],
                    "vol": s["volatility"], "fills": int(s["fills"]),
                    "exposure": s["exposure"],
                }

    if args.neighbourhood:
        out["neighbourhood"] = run_neighbourhood(
            ts1, o1, c1, tsd, od, cd, last_year=last_year, slip=1.0)
        out["variants_tried"] = len(out["neighbourhood"])

    (OUT / "result.json").write_text(json.dumps(out, indent=2, default=float),
                                     encoding="utf-8")
    print(f"dev 1bp: CAGR {out['windows']['dev']['1bp']['cagr']*100:.2f}%  "
          f"DD {out['windows']['dev']['1bp']['max_drawdown']*100:.2f}%  "
          f"Sharpe {out['windows']['dev']['1bp']['sharpe']:.2f}  "
          f"corr {out['corr_vs_165d_baseline']:.2f}")
    print("wrote", OUT / "result.json")


if __name__ == "__main__":
    main()
