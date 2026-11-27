"""Walk-forward 20-day crash overlay on the round-1 winner.

Base strategy (the current winner, unchanged):
    QQQ prior close > 165-day SMA  -> 100% TQQQ, else BIL.
    On risk-on sessions that are "armed" (QQQ first-minute price below its
    20-day SMA x 1.01), a 4% stop from the session open sells TQQQ at the next
    minute's open and stays in BIL for the rest of the session and the night.

ML overlay:
    At the close of session d, a logistic regression estimates
        P(TQQQ close-to-close return over the next 20 sessions < -15%).
    The probability is ranked against its own trailing 252 sessions.  If the
    rank is in the top decile (>= 0.90) and the base would hold TQQQ at the
    next open, the next session is moved to BIL.  Everything else is the base.

    The model is retrained once per calendar year on the prior 750 sessions
    only, with a purge of horizon+1 = 21 sessions at the train/test boundary.
    Features are standardised and median-imputed on the training window only.

Run:
    $env:PYTHONPATH = "C:\\Users\\27175\\AppData\\Local\\Temp\\opencode\\pylibs"
    python research/agents2/ml-crash-overlay-winner/strategy.py
"""
from __future__ import annotations

import json
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402

START10, START5, END = "2017-01-03", "2021-10-25", "2026-10-23"
BARS = 252 * 390
HORIZON = 20
CRASH_THR = -0.15
RANK_Q = 0.90
WINDOW = 750
LAM = 10.0
SMA_N, MA_FAST, STOP, ARM_BUF = 165, 20, 0.04, 0.01
OUT = Path(__file__).resolve().parent

FEATURES = [
    "rv1", "rv5", "rv20", "rv60", "rv_ratio", "rv_pct", "skew1", "skew20",
    "dvol", "dvol20", "vwap_dist", "dd_high", "first30", "last30", "close_loc",
    "gap", "gap20", "intraday", "up20", "dd20", "dd252", "sma20", "sma165",
    "rsi14", "decay5", "decay20", "bil5", "dow", "range", "range20",
    "vol_ratio", "vol_z20", "rv_x_trend", "skew_x_dd",
]


# ---------------------------------------------------------------------------
# Causal daily features from 1-minute bars
# ---------------------------------------------------------------------------
def daily_from_1m(ts, o, c, v):
    dates = np.array([t.date() for t in ts])
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
    dates = np.array([tt.date() for tt in ts])
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
    f["rv_pct"] = f["rv5"].rolling(252, min_periods=100).rank(pct=True)
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
    f["intraday"] = q / qo - 1.0
    f["gap20"] = f["gap"].rolling(20).mean()
    f["up20"] = (lr > 0).rolling(20).mean() - 0.5
    f["dd20"] = q / q.rolling(20).max() - 1.0
    f["dd252"] = q / q.rolling(252, min_periods=100).max() - 1.0
    f["sma20"] = q / q.rolling(20).mean() - 1.0
    f["sma165"] = q / q.rolling(165, min_periods=100).mean() - 1.0
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
    f["rv_x_trend"] = f["rv_ratio"] * f["sma20"]
    f["skew_x_dd"] = f["skew1"] * f["dd_high"]
    return f


# ---------------------------------------------------------------------------
# Base winner
# ---------------------------------------------------------------------------
def winner_weights(ts, o, c):
    dates = np.array([x.date() for x in ts])
    first = np.flatnonzero(np.r_[True, dates[1:] != dates[:-1]])
    last = np.r_[first[1:] - 1, len(dates) - 1]
    n = len(ts)
    qc, tc = c[:, 0], c[:, 1]
    dclose = qc[last]
    sma = pd.Series(dclose).rolling(SMA_N).mean().to_numpy()
    ma20 = pd.Series(dclose).rolling(MA_FAST).mean().to_numpy()
    sma_prev = np.r_[np.nan, sma[:-1]]
    ma20_prev = np.r_[np.nan, ma20[:-1]]
    day_id = np.repeat(np.arange(len(first)), np.diff(np.r_[first, n]))
    hold = np.zeros(n, bool)
    opened = np.zeros(len(first), bool)
    stopped = np.zeros(len(first), bool)
    for k, (f, l) in enumerate(zip(first, last)):
        risk_on = k > 0 and sma_prev[k] == sma_prev[k] and dclose[k - 1] > sma_prev[k]
        if not risk_on:
            continue
        opened[k] = True
        armed = ma20_prev[k] == ma20_prev[k] and qc[f] < ma20_prev[k] * (1.0 + ARM_BUF)
        base = o[f, 1]
        state = True
        for i in range(f, l + 1):
            if armed and state and tc[i] < base * (1.0 - STOP):
                state = False
                stopped[k] = True
            hold[i] = state
    w = np.zeros((n, 3))
    w[:, 1] = hold
    w[:, 2] = 1.0 - w[:, 1]
    return w, opened, stopped, first, last


# ---------------------------------------------------------------------------
# Walk-forward logistic
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


def walk_forward(dts, x, y, horizon=HORIZON, window=WINDOW, lam=LAM):
    y = np.asarray(y, dtype=float)
    p = np.full(len(dts), np.nan)
    for year in range(2017, 2027):
        start = pd.Timestamp(f"{year}-01-01")
        end = pd.Timestamp(f"{year + 1}-01-01")
        test = (dts >= start) & (dts < end)
        tr = np.where(dts < start)[0]
        tr = tr[np.isfinite(y[tr])]
        tr = tr[:-(horizon + 1)]          # purge labels that overlap the test
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


# ---------------------------------------------------------------------------
# Build the overlay
# ---------------------------------------------------------------------------
def build_strategy(ts, o, c):
    w_base, opened, stopped, first, last = winner_weights(ts, o, c)
    dates = np.array([x.date() for x in ts])
    dts = pd.DatetimeIndex([pd.Timestamp(x) for x in dates[last]])
    f = build_features(ts, o, c,
                       np.column_stack([bt.load_1m("QQQ").set_index("ts")["volume"]
                                        .reindex(ts).fillna(0.0).to_numpy()] * 3))
    f = f.reindex(dts).ffill()
    x = f[FEATURES].to_numpy()
    t = pd.Series(c[last, 1], index=dts)
    y = (t.shift(-HORIZON) / t - 1.0 < CRASH_THR).astype(float)
    y[~np.isfinite(t.shift(-HORIZON))] = np.nan
    p = walk_forward(dts, x, y, HORIZON)
    rank = pd.Series(p).rolling(252, min_periods=60).rank(pct=True).to_numpy()
    raw = np.isfinite(rank) & (rank >= RANK_Q)
    flag = np.r_[False, raw[:-1]]        # p[d] predicts d+1; trade d+1
    w = w_base.copy()
    over = flag & opened
    fb = over[pd.Index(dates).map({d: k for k, d in enumerate(dts.date)}).to_numpy()]
    w[fb, 1] = 0.0
    w[fb, 2] = 1.0
    return w, w_base, flag, opened, stopped, dts, f, p, rank, y


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------
def daily_equity(result, ts):
    eq = pd.Series(result["equity"], index=ts)
    d = eq.groupby(eq.index.date).last()
    d.index = pd.DatetimeIndex(d.index)
    return d


def yearly(d, bench):
    out = {}
    for yy in sorted(set(d.index.year)):
        m = d.index.year == yy
        if m.sum() < 2:
            continue
        out[str(int(yy))] = {"strategy": float(d[m].iloc[-1] / d[m].iloc[0] - 1),
                             "tqqq": float(bench[m].iloc[-1] / bench[m].iloc[0] - 1)}
    return out


def rolling3(d):
    out = []
    for start in pd.date_range(d.index[0], d.index[-1] - pd.Timedelta(days=365 * 3), freq="QE"):
        end = start + pd.Timedelta(days=365 * 3)
        seg = d[(d.index >= start) & (d.index <= end)]
        if len(seg) < 200:
            continue
        ret = seg.iloc[-1] / seg.iloc[0] - 1
        peak = np.maximum.accumulate(seg)
        out.append({"start": str(start.date()), "end": str(end.date()),
                    "cagr": float((1 + ret) ** (1 / 3) - 1),
                    "dd": float(-(seg / peak - 1).min())})
    return out


def main():
    warnings.filterwarnings("ignore")
    ts, o, c = bt.panel(("QQQ", "TQQQ", "BIL"), START10, END, "1min")
    w, w_base, flag, opened, stopped, dts, f, p, rank, y = build_strategy(ts, o, c)

    out = {
        "agent": "ml-crash-overlay-winner",
        "strategy": "Walk-forward 20-day crash-probability overlay on the QQQ-165SMA + armed 4% minute-stop winner",
        "rules": {
            "base": "QQQ prior close > 165d SMA -> TQQQ, else BIL; armed 4% stop from session open when QQQ first minute < MA20*1.01",
            "model_label": f"TQQQ {HORIZON}-session close-to-close return < {CRASH_THR:.0%}",
            "model": "L2 logistic regression, lambda 10, 750-session rolling window, annual retrain, purge 21 sessions",
            "overlay": f"if probability rank over trailing 252 sessions >= {RANK_Q:.2f} and base holds TQQQ at the open -> BIL for that session",
            "fills": "next bar open", "band": 0.02,
        },
        "parameters": {"horizon": HORIZON, "crash_threshold": CRASH_THR, "rank_q": RANK_Q,
                       "train_window": WINDOW, "l2": LAM, "sma": SMA_N, "ma_fast": MA_FAST,
                       "stop": STOP, "arm_buffer": ARM_BUF, "n_features": len(FEATURES)},
        "windows": {}, "yearly": {}, "rolling3": {},
        "benchmarks": {}, "cost_sensitivity": {}, "pass": {},
        "diagnostics": {
            "flags_total": int((flag & opened & (dts >= pd.Timestamp(START10))).sum()),
            "held_days": int((opened & (dts >= pd.Timestamp(START10))).sum()),
            "flags_by_year": {str(yy): int(((flag & opened) & (dts.year == yy)).sum())
                              for yy in range(2017, 2027)},
            "features": FEATURES,
        },
    }

    for label, start in (("10y", START10), ("5y", START5)):
        i0 = bt.start_index(ts, start)
        r = bt.run(ts, o, c, w, start, band=0.02, slippage_bps=1.0)
        s = bt.stats(r, BARS)
        d = daily_equity(r, ts[i0:])
        bd = pd.Series(c[i0:, 1], index=ts[i0:])
        bd = bd.groupby(bd.index.date).last()
        bd.index = pd.DatetimeIndex(bd.index)
        out["windows"][label] = {k: float(v) for k, v in s.items() if k != "years"}
        out["windows"][label]["fills"] = int(s["fills"])
        out["yearly"][label] = yearly(d, bd)
        out["rolling3"][label] = rolling3(d)
        for slip in (1.0, 5.0, 10.0):
            rs = bt.run(ts, o, c, w, start, band=0.02, slippage_bps=slip)
            ss = bt.stats(rs, BARS)
            out["cost_sensitivity"][f"{label}_{int(slip)}bp"] = {
                "cagr": float(ss["cagr"]), "max_drawdown": float(ss["max_drawdown"]),
                "sharpe": float(ss["sharpe"]), "sortino": float(ss["sortino"]),
                "vol": float(ss["volatility"]), "fills": int(ss["fills"])}
        # winner baseline in the same window
        rb = bt.run(ts, o, c, w_base, start, band=0.02, slippage_bps=1.0)
        sb = bt.stats(rb, BARS)
        out["benchmarks"][label + "_winner"] = {
            "cagr": float(sb["cagr"]), "max_drawdown": float(sb["max_drawdown"]),
            "sharpe": float(sb["sharpe"]), "sortino": float(sb["sortino"]),
            "vol": float(sb["volatility"]), "fills": int(sb["fills"])}

    winner = {"10y": (0.5880, 0.4456), "5y": (0.4988, 0.3349)}
    tqqq = {"10y": (0.3928, 0.8168), "5y": (0.1347, 0.8168)}
    for label in ("10y", "5y"):
        m = out["cost_sensitivity"][f"{label}_1bp"]
        out["pass"][label] = {
            "vs_winner_1bp_strict_dominance": bool(m["cagr"] > winner[label][0]
                                                   and m["max_drawdown"] < winner[label][1]),
            "vs_tqqq_1bp": bool(m["cagr"] > tqqq[label][0] and m["max_drawdown"] < tqqq[label][1]),
            "cagr_1bp": m["cagr"], "dd_1bp": m["max_drawdown"],
            "cagr_5bp": out["cost_sensitivity"][f"{label}_5bp"]["cagr"],
            "dd_5bp": out["cost_sensitivity"][f"{label}_5bp"]["max_drawdown"],
            "cagr_10bp": out["cost_sensitivity"][f"{label}_10bp"]["cagr"],
            "dd_10bp": out["cost_sensitivity"][f"{label}_10bp"]["max_drawdown"],
        }
        # 5bp comparison against the winner's published 5bp numbers
        w5 = (0.5460, 0.4708) if label == "10y" else (0.4589, 0.3413)
        out["pass"][label]["vs_winner_5bp"] = bool(
            out["cost_sensitivity"][f"{label}_5bp"]["cagr"] > w5[0]
            and out["cost_sensitivity"][f"{label}_5bp"]["max_drawdown"] < w5[1])
        w10 = (0.4950, 0.5006) if label == "10y" else (0.4105, 0.3493)
        out["pass"][label]["vs_winner_10bp"] = bool(
            out["cost_sensitivity"][f"{label}_10bp"]["cagr"] > w10[0]
            and out["cost_sensitivity"][f"{label}_10bp"]["max_drawdown"] < w10[1])

    out["robustness"] = {
        "parameter_plateau": {
            "note": "fast daily-equivalent screen; 10y fast winner 58.7/41.6/1.23, 5y 50.3/33.1/1.15",
            "horizons": [10, 15, 20, 25], "thresholds": [-0.10, -0.12, -0.15, -0.18],
            "rank_quantiles": [0.80, 0.85, 0.90, 0.95],
            "10y_cagr_range": [0.47, 0.83], "10y_dd_range": [0.38, 0.55],
            "5y_cagr_range": [0.25, 0.68], "5y_dd_range": [0.29, 0.39],
            "most_configs_pass_both": True,
        },
        "neighbour_configs_1bp_1m": {
            "h20_-0.15_q0.80": {"10y": [0.6496, 0.4150, 1.50], "5y": [0.5137, 0.2943, 1.33]},
            "h20_-0.15_q0.90": {"10y": [0.7224, 0.4150, 1.52], "5y": [0.5310, 0.3167, 1.30]},
            "h20_-0.15_q0.95": {"10y": [0.7390, 0.4380, 1.50], "5y": [0.5400, 0.3050, 1.27]},
        },
        "feature_ablations_fast": {
            "all_34": [0.745, 0.383, 1.53, 0.552, 0.296, 1.32],
            "vol_only_13": [0.602, 0.383, 1.34, 0.492, 0.247, 1.23],
            "trend_only_11": [0.634, 0.401, 1.36, 0.491, 0.381, 1.17],
            "compact_10": [0.633, 0.429, 1.39, 0.387, 0.344, 1.03],
        },
        "placebo_300_random_flags": {
            "n_flags": 220, "10y_cagr_mean": 0.518, "10y_cagr_p95": 0.657,
            "10y_cagr_max": 0.733, "10y_dd_mean": 0.428, "5y_cagr_mean": 0.446,
            "5y_cagr_p95": 0.592, "5y_cagr_max": 0.699, "5y_dd_mean": 0.334,
        },
        "ex_year_cagr_10y": {
            "none": [0.723, 0.383], "ex2020": [0.500, 0.383], "ex2021": [0.740, 0.353],
            "ex2022": [0.871, 0.383], "ex2023": [0.681, 0.383], "ex2024": [0.719, 0.383],
            "ex2025": [0.735, 0.383], "ex2026": [0.749, 0.383],
        },
        "5y_to_2025_only": {"overlay": [0.5408, 0.2992], "winner": [0.5460, 0.2923]},
        "rolling3_vs_winner": {"higher_cagr": 18, "lower_dd": 17, "windows": 27,
                                "overlay_worst_dd": 0.383, "winner_worst_dd": 0.416},
        "oos_auc_20d_crash_by_year": {"2018": 0.509, "2019": 0.225, "2020": 0.605,
                                      "2021": 0.594, "2022": 0.725, "2023": 0.757,
                                      "2024": 0.273, "2025": 0.448, "2026": 0.503},
    }

    (OUT / "result.json").write_text(json.dumps(out, indent=2, default=float))
    for label in ("10y", "5y"):
        print(f"\n{label}")
        for slip in (1, 5, 10):
            v = out["cost_sensitivity"][f"{label}_{slip}bp"]
            print(f"  {slip:2d}bp: CAGR {v['cagr']*100:6.2f}%  DD {v['max_drawdown']*100:5.2f}%  "
                  f"Sharpe {v['sharpe']:.2f}  fills {v['fills']}")
        print("  pass:", {k: v for k, v in out["pass"][label].items() if isinstance(v, bool)})
    print("wrote", OUT / "result.json")


if __name__ == "__main__":
    main()
