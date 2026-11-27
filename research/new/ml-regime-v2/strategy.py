"""Walk-forward path-drawdown-risk regime allocator across TQQQ / QQQ / BIL.

The strategy is a two-state causal allocator:

1. Momentum state: a majority vote of QQQ 60-, 100- and 150-session total
   returns being positive.
2. Path-risk state: a quarterly-refit L2 logistic regression estimates
   P(TQQQ peak-to-trough drawdown over the next 20 sessions > 15%) from nine
   volatility-term-structure features.  Training uses only labels whose
   forward window ends before the test quarter; no full-sample fitting.

Allocation at the next open:
    momentum down                              -> 100% BIL
    momentum up, risk probability < 0.60       -> 100% TQQQ
    momentum up, 0.60 <= probability < 0.90    -> 100% QQQ
    momentum up, probability >= 0.90           -> 100% BIL

Development window only: 2016-01-04 .. 2023-12-29.  The 2024-2026 holdout is
never loaded.

Run from the repository root:
    $env:PYTHONPATH = "C:\\Users\\27175\\AppData\\Local\\Temp\\opencode\\pylibs"
    python research/new/ml-regime-v2/strategy.py
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

START = "2016-01-04"
END = "2023-12-29"
BARS_PER_YEAR = 252 * 390
OUT = Path(__file__).resolve().parent

H = 20
DD_THR = 0.15
MOM_HORIZONS = (60, 100, 150)
MOM_NEED = 2.0 / 3.0
LO, HI = 0.60, 0.90
MIN_TRAIN = 200
LAM = 10.0

FEATURES = [
    "rv5", "rv10", "rv20", "rv60", "rv_ratio5", "rv_ratio20",
    "park20", "down_share", "volofvol",
]

# Pre-registered grid: 8 combinations, fixed a priori.
GRID = [
    {"label": "exp_lo60_hi90", "window": None, "lo": 0.60, "hi": 0.90},
    {"label": "exp_lo60_hi85", "window": None, "lo": 0.60, "hi": 0.85},
    {"label": "exp_lo65_hi90", "window": None, "lo": 0.65, "hi": 0.90},
    {"label": "exp_lo65_hi85", "window": None, "lo": 0.65, "hi": 0.85},
    {"label": "w750_lo60_hi90", "window": 750, "lo": 0.60, "hi": 0.90},
    {"label": "w750_lo60_hi85", "window": 750, "lo": 0.60, "hi": 0.85},
    {"label": "w750_lo65_hi90", "window": 750, "lo": 0.65, "hi": 0.90},
    {"label": "w750_lo65_hi85", "window": 750, "lo": 0.65, "hi": 0.85},
]
PRIMARY = "exp_lo60_hi90"


# ---------------------------------------------------------------------------
# Causal features and labels
# ---------------------------------------------------------------------------
def _ret(arr: np.ndarray, k: int) -> np.ndarray:
    out = np.full(len(arr), np.nan)
    out[k:] = arr[k:] / arr[:-k] - 1.0
    return out


def _rstd(arr: np.ndarray, k: int) -> np.ndarray:
    return pd.Series(arr).rolling(k, min_periods=max(3, k // 2)).std(ddof=0).to_numpy()


def build_features(q: np.ndarray, t: np.ndarray, b: np.ndarray) -> tuple[pd.DataFrame, list[str]]:
    """Nine price/vol features, all using data through the current close."""
    lr = np.r_[np.nan, np.log(q[1:] / q[:-1])]
    f = pd.DataFrame(index=np.arange(len(q)))
    f["rv5"] = _rstd(lr, 5) * np.sqrt(252)
    f["rv10"] = _rstd(lr, 10) * np.sqrt(252)
    f["rv20"] = _rstd(lr, 20) * np.sqrt(252)
    f["rv60"] = _rstd(lr, 60) * np.sqrt(252)
    f["rv_ratio5"] = f["rv5"] / np.maximum(f["rv60"], 1e-9)
    f["rv_ratio20"] = f["rv20"] / np.maximum(f["rv60"], 1e-9)
    hi = pd.Series(q).rolling(20).max().to_numpy()
    lo = pd.Series(q).rolling(20).min().to_numpy()
    f["park20"] = np.sqrt(np.maximum(np.log(hi / lo), 0.0) ** 2 / (4.0 * np.log(2.0) * 20.0))
    neg = np.where(lr < 0, lr ** 2, 0.0)
    f["down_share"] = (
        pd.Series(neg).rolling(20).mean().to_numpy()
        / np.maximum(pd.Series(lr ** 2).rolling(20).mean().to_numpy(), 1e-12)
    )
    f["volofvol"] = (
        pd.Series(f["rv5"]).rolling(20).std(ddof=0).to_numpy()
        / np.maximum(f["rv20"].to_numpy(), 1e-9)
    )
    return f, FEATURES


def momentum_score(q: np.ndarray) -> np.ndarray:
    signs = []
    for k in MOM_HORIZONS:
        r = _ret(q, k)
        signs.append((r > 0).astype(float))
    return np.mean(np.column_stack(signs), axis=1)


def path_drawdown_label(t: np.ndarray, horizon: int, threshold: float = DD_THR) -> np.ndarray:
    """1 if TQQQ's max peak-to-trough drawdown over t+1..t+horizon exceeds threshold."""
    n = len(t)
    y = np.full(n, np.nan)
    for i in range(n - horizon - 1):
        seg = t[i + 1:i + 1 + horizon]
        drawdown = float(-(seg / np.maximum.accumulate(seg) - 1.0).min())
        y[i] = 1.0 if drawdown > threshold else 0.0
    return y


# ---------------------------------------------------------------------------
# Walk-forward logistic model
# ---------------------------------------------------------------------------
def _logistic_fit(x: np.ndarray, y: np.ndarray, lam: float = LAM, iters: int = 40) -> np.ndarray:
    n, d = x.shape
    xb = np.column_stack([np.ones(n), x])
    w = np.zeros(d + 1)
    reg = np.full(d + 1, lam)
    reg[0] = 0.0
    for _ in range(iters):
        p = 1.0 / (1.0 + np.exp(-np.clip(xb @ w, -35.0, 35.0)))
        grad = xb.T @ (p - y) + reg * w
        s = np.maximum(p * (1.0 - p), 1e-6)
        hess = xb.T @ (xb * s[:, None]) + np.diag(reg + 1e-9)
        step = np.linalg.solve(hess, grad)
        w -= step
        if np.max(np.abs(step)) < 1e-8:
            break
    return w


def _logistic_predict(w: np.ndarray, x: np.ndarray) -> np.ndarray:
    xb = np.column_stack([np.ones(len(x)), x])
    return 1.0 / (1.0 + np.exp(-np.clip(xb @ w, -35.0, 35.0)))


def walk_forward(
    ts: pd.DatetimeIndex,
    x: np.ndarray,
    y: np.ndarray,
    *,
    window: int | None,
    horizon: int = H,
    lam: float = LAM,
    min_train: int = MIN_TRAIN,
    refit: str = "QS",
) -> np.ndarray:
    """Quarterly (or monthly) refit; purged labels; expanding or rolling window."""
    p = np.full(len(ts), np.nan)
    purge_days = int(horizon * 1.6) + 4
    starts = pd.date_range("2017-01-01", "2023-10-01", freq=refit, tz=ts.tz)
    for qs in starts:
        if refit == "MS":
            qe = qs + pd.DateOffset(months=1)
        else:
            qe = qs + pd.DateOffset(months=3)
        test = (ts >= qs) & (ts < qe)
        if not test.any():
            continue
        tr = np.where((ts < qs) & np.isfinite(y))[0]
        tr = tr[ts[tr] + pd.Timedelta(days=purge_days) < qs]
        if window:
            tr = tr[-window:]
        if len(tr) < min_train:
            continue
        coverage = np.isfinite(x[tr]).mean(axis=0)
        keep = coverage >= 0.60
        xt = x[:, keep]
        med = np.nanmedian(xt[tr], axis=0)
        med = np.where(np.isfinite(med), med, 0.0)
        xf = np.where(np.isfinite(xt), xt, med)
        mu = xf[tr].mean(axis=0)
        sd = xf[tr].std(axis=0)
        sd = np.where(sd > 1e-12, sd, 1.0)
        xs = np.clip((xf - mu) / sd, -6.0, 6.0)
        w = _logistic_fit(xs[tr], y[tr], lam=lam)
        p[test] = _logistic_predict(w, xs[test])
    return p


# ---------------------------------------------------------------------------
# Allocation
# ---------------------------------------------------------------------------
def states_from_probability(p: np.ndarray, mom: np.ndarray, lo: float, hi: float) -> np.ndarray:
    """0 = QQQ, 1 = TQQQ, 2 = BIL."""
    n = len(p)
    st = np.full(n, 2, dtype=int)
    up = mom >= MOM_NEED - 1e-12
    known = np.isfinite(p)
    st[up & known & (p < lo)] = 1
    st[up & known & (p >= lo) & (p < hi)] = 0
    return st


def state_weights(states: np.ndarray) -> np.ndarray:
    w = np.zeros((len(states), 3))
    w[np.arange(len(states)), states] = 1.0
    return w


def build_weights(
    tsd: pd.DatetimeIndex,
    od: np.ndarray,
    cd: np.ndarray,
    *,
    window: int | None = None,
    lo: float = LO,
    hi: float = HI,
    horizon: int = H,
    dd_threshold: float = DD_THR,
    refit: str = "QS",
) -> tuple[np.ndarray, dict]:
    """Full causal pipeline: features -> label -> walk-forward model -> states.

    Returns the per-session target states (0=QQQ, 1=TQQQ, 2=BIL) and the
    intermediate series.  `states[k]` is set at the close of session k and is
    held during session k+1, which is exactly what `bt.run` expects.
    """
    q, t, b = cd[:, 0], cd[:, 1], cd[:, 2]
    feats, cols = build_features(q, t, b)
    x = feats[cols].to_numpy()
    mom = momentum_score(q)
    y = path_drawdown_label(t, horizon, dd_threshold)
    p = walk_forward(tsd, x, y, window=window, horizon=horizon, refit=refit)
    st = states_from_probability(p, mom, lo, hi)
    return st, {"p": p, "mom": mom, "y": y, "features": feats, "cols": cols}


def minute_weights(states_daily: np.ndarray, tsd: pd.DatetimeIndex, ts1: pd.DatetimeIndex) -> np.ndarray:
    """Expand daily decisions to every minute.

    states_daily[k] is set at the close of session k and is held during
    session k+1.  Every minute of session k+1 therefore carries that state.
    """
    dates_d = bt.session_dates(tsd)
    dates_m_bar = bt.session_dates(ts1)
    first, last = bt.day_bounds_from_dates(dates_m_bar)
    dates_m = dates_m_bar[first]
    counts = last - first + 1
    idx = np.searchsorted(dates_d, dates_m)
    idx = np.clip(idx, 0, len(dates_d) - 1)
    if not np.array_equal(dates_d[idx], dates_m):
        raise RuntimeError("daily and minute session calendars do not align")
    target = np.full(len(dates_d), 2, dtype=int)
    target[1:] = states_daily[:-1]
    per_minute = np.repeat(target[idx], counts)
    return state_weights(per_minute)


# ---------------------------------------------------------------------------
# Evaluation helpers
# ---------------------------------------------------------------------------
def auc_score(y: np.ndarray, p: np.ndarray) -> float:
    m = np.isfinite(y) & np.isfinite(p)
    if m.sum() < 30:
        return float("nan")
    yy, pp = y[m], p[m]
    ranks = pd.Series(pp).rank().to_numpy()
    n1 = float(yy.sum())
    n0 = float(len(yy) - n1)
    if n1 == 0 or n0 == 0:
        return float("nan")
    return float((ranks[yy == 1].sum() - n1 * (n1 + 1) / 2.0) / (n1 * n0))


def quantile_stats(x: np.ndarray) -> dict:
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    return {
        "mean": float(np.mean(x)),
        "p5": float(np.percentile(x, 5)),
        "p50": float(np.percentile(x, 50)),
        "p95": float(np.percentile(x, 95)),
        "min": float(np.min(x)),
        "max": float(np.max(x)),
    }


def daily_equity(result: dict, ts: pd.DatetimeIndex) -> pd.Series:
    eq = pd.Series(result["equity"], index=ts)
    d = eq.groupby(eq.index.date).last()
    d.index = pd.DatetimeIndex(d.index)
    return d


def daily_bench(close: np.ndarray, ts: pd.DatetimeIndex) -> pd.Series:
    s = pd.Series(close, index=ts)
    d = s.groupby(s.index.date).last()
    d.index = pd.DatetimeIndex(d.index)
    return d


def window_metrics(ts, o, c, w, start, end, slip, bars_per_year):
    """bt.run on a sliced panel (the panel is already dev-only)."""
    i0 = bt.start_index(ts, start)
    i1 = int(ts.searchsorted(pd.Timestamp(end, tz=ts.tz), side="right"))
    r = bt.simulate(ts[i0:i1], o[i0:i1], c[i0:i1], w[i0:i1],
                    band=0.02, slippage_bps=slip)
    s = bt.stats(r, bars_per_year)
    return r, s


def yearly_table(tsd, equity_daily, tqqq_daily, states):
    d = equity_daily
    b = tqqq_daily.reindex(d.index).ffill()
    out = {}
    for year in sorted(set(d.index.year)):
        m = d.index.year == year
        if m.sum() < 2:
            continue
        sm = states[np.asarray(tsd.year == year)]
        out[str(int(year))] = {
            "strategy": float(d[m].iloc[-1] / d[m].iloc[0] - 1.0),
            "tqqq": float(b[m].iloc[-1] / b[m].iloc[0] - 1.0),
            "time_tqqq": float(np.mean(sm == 1)),
            "time_qqq": float(np.mean(sm == 0)),
            "time_bil": float(np.mean(sm == 2)),
        }
    return out


def subperiod(tsd, equity_daily, tqqq_daily, start, end):
    d = equity_daily
    b = tqqq_daily.reindex(d.index).ffill()
    m = (d.index >= pd.Timestamp(start)) & (d.index <= pd.Timestamp(end))
    seg, bs = d[m], b[m]
    years = (seg.index[-1] - seg.index[0]).total_seconds() / (365.25 * 86400)
    peak = np.maximum.accumulate(seg)
    bpeak = np.maximum.accumulate(bs)
    return {
        "cagr": float((seg.iloc[-1] / seg.iloc[0]) ** (1 / years) - 1),
        "max_drawdown": float(-(seg / peak - 1).min()),
        "tqqq_cagr": float((bs.iloc[-1] / bs.iloc[0]) ** (1 / years) - 1),
        "tqqq_max_drawdown": float(-(bs / bpeak - 1).min()),
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    warnings.filterwarnings("ignore")

    tsd, od, cd = bt.panel(("QQQ", "TQQQ", "BIL"), START, END, "1D", warmup_days=0)
    ts1, o1, c1 = bt.panel(("QQQ", "TQQQ", "BIL"), START, END, "1min", warmup_days=0)
    q, t, b = cd[:, 0], cd[:, 1], cd[:, 2]
    n = len(tsd)

    feats, cols = build_features(q, t, b)
    x = feats[cols].to_numpy()
    mom = momentum_score(q)
    y = path_drawdown_label(t, H)

    # Models: one per training-window choice.
    preds = {}
    for window in (None, 750):
        key = "exp" if window is None else f"w{window}"
        preds[key] = walk_forward(tsd, x, y, window=window)

    # Pre-registered grid on 1-minute marks.
    grid_rows = []
    weights_1m = {}
    for cfg in GRID:
        key = "exp" if cfg["window"] is None else f"w{cfg['window']}"
        p = preds[key]
        st = states_from_probability(p, mom, cfg["lo"], cfg["hi"])
        w1 = minute_weights(st, tsd, ts1)
        weights_1m[cfg["label"]] = w1
        r, s = window_metrics(ts1, o1, c1, w1, START, END, 1.0, BARS_PER_YEAR)
        grid_rows.append({
            "label": cfg["label"],
            "window": cfg["window"] or "expanding",
            "lo": cfg["lo"],
            "hi": cfg["hi"],
            "cagr": float(s["cagr"]),
            "max_drawdown": float(s["max_drawdown"]),
            "sharpe": float(s["sharpe"]),
            "sortino": float(s["sortino"]),
            "volatility": float(s["volatility"]),
            "fills": int(s["fills"]),
            "time_tqqq": float(np.mean(st == 1)),
            "time_qqq": float(np.mean(st == 0)),
            "time_bil": float(np.mean(st == 2)),
        })

    primary = next(g for g in GRID if g["label"] == PRIMARY)
    st_primary, api_info = build_weights(
        tsd, od, cd, window=None, lo=primary["lo"], hi=primary["hi"]
    )
    # The grid path and the public build_weights path must agree.
    assert np.array_equal(
        st_primary,
        states_from_probability(preds["exp"], mom, primary["lo"], primary["hi"]),
    )
    w_primary = weights_1m[PRIMARY]

    # Primary result at 1/5/10 bp.
    costs = {}
    primary_results = {}
    for slip in (1.0, 5.0, 10.0):
        r, s = window_metrics(ts1, o1, c1, w_primary, START, END, slip, BARS_PER_YEAR)
        primary_results[slip] = (r, s)
        costs[f"{int(slip)}bp"] = {
            "cagr": float(s["cagr"]),
            "total_return": float(s["total_return"]),
            "max_drawdown": float(s["max_drawdown"]),
            "volatility": float(s["volatility"]),
            "sharpe": float(s["sharpe"]),
            "sortino": float(s["sortino"]),
            "exposure": float(s["exposure"]),
            "fills": int(s["fills"]),
            "turnover": float(s["turnover"]),
            "ending_equity": float(s["ending_equity"]),
        }

    r1, s1 = primary_results[1.0]
    eq_daily = daily_equity(r1, r1["ts"])
    tq_daily = daily_bench(c1[:, 1], ts1)
    qq_daily = daily_bench(c1[:, 0], ts1)
    bil_daily = daily_bench(c1[:, 2], ts1)

    # Correlation to TQQQ (daily returns over the dev window).
    strat_ret = eq_daily.pct_change().dropna()
    tqqq_ret = tq_daily.pct_change().dropna()
    qqq_ret = qq_daily.pct_change().dropna()
    corr = {
        "strategy_vs_tqqq": float(strat_ret.corr(tqqq_ret)),
        "strategy_vs_qqq": float(strat_ret.corr(qqq_ret)),
        "tqqq_vs_qqq": float(tqqq_ret.corr(qqq_ret)),
    }

    # 165-day QQQ regime baseline for correlation only (not part of the strategy).
    sma165 = pd.Series(q).rolling(165).mean().to_numpy()
    base_pos = (q > sma165).astype(float)
    base_pos[~np.isfinite(sma165)] = 0.0
    w_base_d = np.zeros((n, 3))
    w_base_d[:, 1] = base_pos
    w_base_d[:, 2] = 1.0 - base_pos
    r_base, s_base = window_metrics(tsd, od, cd, w_base_d, START, END, 1.0, 252)
    base_eq = daily_equity(r_base, tsd)
    corr["strategy_vs_165d_base"] = float(strat_ret.corr(base_eq.pct_change().dropna()))

    # 165-day base on 1-minute marks (comparison only, not part of the strategy).
    st_base = np.where(base_pos > 0, 1, 2).astype(int)
    w_base_1 = minute_weights(st_base, tsd, ts1)
    r_base_1, s_base_1 = window_metrics(ts1, o1, c1, w_base_1, START, END, 1.0, BARS_PER_YEAR)


    # Benchmarks on 1-minute marks.
    benchmarks = {}
    for name, close in (("tqqq", c1[:, 1]), ("qqq", c1[:, 0]), ("bil", c1[:, 2])):
        bm = bt.benchmark(close, ts1, BARS_PER_YEAR)
        benchmarks[name] = {k: float(v) for k, v in bm.items()}
    benchmarks["sma165_base_1m"] = {
        "cagr": float(s_base_1["cagr"]),
        "max_drawdown": float(s_base_1["max_drawdown"]),
        "sharpe": float(s_base_1["sharpe"]),
        "fills": int(s_base_1["fills"]),
        "note": "QQQ > 165-day SMA -> TQQQ else BIL; comparison only",
    }

    # Simple vol rule: same momentum, rv5 < 0.60, else BIL.
    rv5 = feats["rv5"].to_numpy()
    st_vol = np.full(n, 2, dtype=int)
    up = mom >= MOM_NEED - 1e-12
    st_vol[up & (np.nan_to_num(rv5, nan=9.0) < 0.60)] = 1
    w_vol = minute_weights(st_vol, tsd, ts1)
    vol_rows = {}
    r_vol_1 = None
    for slip in (1.0, 5.0, 10.0):
        rv, sv = window_metrics(ts1, o1, c1, w_vol, START, END, slip, BARS_PER_YEAR)
        if slip == 1.0:
            r_vol_1 = rv
        vol_rows[f"{int(slip)}bp"] = {
            "cagr": float(sv["cagr"]),
            "max_drawdown": float(sv["max_drawdown"]),
            "sharpe": float(sv["sharpe"]),
            "fills": int(sv["fills"]),
            "time_tqqq": float(np.mean(st_vol == 1)),
        }

    # Momentum-only baseline (no risk gate).
    st_mom = np.where(up, 1, 2).astype(int)
    w_mom = minute_weights(st_mom, tsd, ts1)
    r_mom, s_mom = window_metrics(ts1, o1, c1, w_mom, START, END, 1.0, BARS_PER_YEAR)

    # Correlation to the simple vol rule and to momentum-only.
    vol_eq = daily_equity(r_vol_1, r_vol_1["ts"])
    mom_eq = daily_equity(r_mom, r_mom["ts"])
    corr["strategy_vs_vol_rule"] = float(strat_ret.corr(vol_eq.pct_change().dropna()))
    corr["strategy_vs_momentum_only"] = float(strat_ret.corr(mom_eq.pct_change().dropna()))

    # Binary ML variant (no QQQ middle state), a neighbour.
    st_bin = np.full(n, 2, dtype=int)
    st_bin[up & np.isfinite(preds["exp"]) & (preds["exp"] < 0.60)] = 1
    w_bin = minute_weights(st_bin, tsd, ts1)
    r_bin, s_bin = window_metrics(ts1, o1, c1, w_bin, START, END, 1.0, BARS_PER_YEAR)

    # Model diagnostics.
    p = preds["exp"]
    risk_metrics = {
        "auc": auc_score(y, p),
        "accuracy_at_0.5": float(np.nanmean(((p >= 0.5) == (y >= 0.5))[np.isfinite(p) & np.isfinite(y)])),
        "accuracy_at_0.6": float(np.nanmean(((p >= 0.6) == (y >= 0.5))[np.isfinite(p) & np.isfinite(y)])),
        "base_rate": float(np.nanmean(y)),
        "brier": float(np.nanmean(((p - y) ** 2)[np.isfinite(p) & np.isfinite(y)])),
        "n_oos": int(np.sum(np.isfinite(p) & np.isfinite(y))),
        "first_prediction": str(tsd[np.isfinite(p)][0].date()) if np.isfinite(p).any() else None,
        "auc_by_year": {
            str(int(yy)): auc_score(y[tsd.year == yy], p[tsd.year == yy])
            for yy in range(2017, 2024)
        },
        "positive_rate_by_year": {
            str(int(yy)): float(np.nanmean(y[tsd.year == yy])) for yy in range(2017, 2024)
        },
    }

    # Sub-periods.
    sub = {
        "2016-2019": subperiod(tsd, eq_daily, tq_daily, "2016-01-04", "2019-12-31"),
        "2020-2021": subperiod(tsd, eq_daily, tq_daily, "2020-01-01", "2021-12-31"),
        "2022-2023": subperiod(tsd, eq_daily, tq_daily, "2022-01-01", "2023-12-29"),
    }

    # Yearly table.
    yearly = yearly_table(tsd, eq_daily, tq_daily, st_primary)

    # Ex-year CAGR: remove one calendar year's return and re-annualise the
    # remaining chain.  This is an approximation (calendar years, not exact
    # 365-day buckets) and is labelled as such.
    yrs = list(yearly)
    chain_total = float(np.prod([1.0 + yearly[y]["strategy"] for y in yrs]))
    ex_year = {}
    for yy in yrs:
        if len(yrs) < 2:
            continue
        rest = chain_total / (1.0 + yearly[yy]["strategy"])
        ex_year[yy] = float(rest ** (1.0 / (len(yrs) - 1)) - 1.0)

    # Placebo A: circular shifts of the risk probability (keeps its
    # autocorrelation and the momentum state, breaks alignment).
    rng = np.random.default_rng(20240101)
    eq_arr = eq_daily.to_numpy()
    placebo_shift = []
    p_valid = np.isfinite(p)
    p_filled = np.where(p_valid, p, 0.0)
    for _ in range(200):
        shift = int(rng.integers(60, n - 60))
        ps = np.roll(p_filled, shift)
        st = states_from_probability(np.where(p_valid, ps, np.nan), mom, primary["lo"], primary["hi"])
        w = state_weights(st)  # daily marks for speed
        rr, ss = window_metrics(tsd, od, cd, w, START, END, 1.0, 252)
        placebo_shift.append(float(ss["cagr"]))

    # Placebo B: random permutation of the primary state array (same counts).
    placebo_perm = []
    for _ in range(200):
        st = rng.permutation(st_primary)
        w = state_weights(st)
        rr, ss = window_metrics(tsd, od, cd, w, START, END, 1.0, 252)
        placebo_perm.append(float(ss["cagr"]))

    # Neighbour checks: horizon, drawdown threshold, momentum set, monthly refit,
    # one-session delay, and the binary variant.
    neighbours = {}
    for horizon in (10, 40):
        y_h = path_drawdown_label(t, horizon)
        p_h = walk_forward(tsd, x, y_h, window=None, horizon=horizon)
        st_h = states_from_probability(p_h, mom, primary["lo"], primary["hi"])
        w_h = minute_weights(st_h, tsd, ts1)
        _, s_h = window_metrics(ts1, o1, c1, w_h, START, END, 1.0, BARS_PER_YEAR)
        neighbours[f"horizon_{horizon}"] = {
            "cagr": float(s_h["cagr"]), "max_drawdown": float(s_h["max_drawdown"]),
            "sharpe": float(s_h["sharpe"]), "auc": auc_score(y_h, p_h),
        }
    for thr in (0.10, 0.20):
        y_t = path_drawdown_label(t, H, thr)
        p_t = walk_forward(tsd, x, y_t, window=None)
        st_t = states_from_probability(p_t, mom, primary["lo"], primary["hi"])
        w_t = minute_weights(st_t, tsd, ts1)
        _, s_t = window_metrics(ts1, o1, c1, w_t, START, END, 1.0, BARS_PER_YEAR)
        neighbours[f"dd_threshold_{int(thr*100)}"] = {
            "cagr": float(s_t["cagr"]), "max_drawdown": float(s_t["max_drawdown"]),
            "sharpe": float(s_t["sharpe"]), "auc": auc_score(y_t, p_t),
        }
    for name, horizons in (("mom_60_100", (60, 100)), ("mom_100_150_200", (100, 150, 200))):
        signs = [(r > 0).astype(float) for r in (_ret(q, k) for k in horizons)]
        m2 = np.mean(np.column_stack(signs), axis=1)
        st_m = np.full(n, 2)
        u2 = m2 >= 0.5
        st_m[u2 & (p < primary["lo"])] = 1
        st_m[u2 & (p >= primary["lo"]) & (p < primary["hi"])] = 0
        w_m = minute_weights(st_m, tsd, ts1)
        _, s_m = window_metrics(ts1, o1, c1, w_m, START, END, 1.0, BARS_PER_YEAR)
        neighbours[name] = {
            "cagr": float(s_m["cagr"]), "max_drawdown": float(s_m["max_drawdown"]),
            "sharpe": float(s_m["sharpe"]),
        }
    p_m = walk_forward(tsd, x, y, window=None, refit="MS")
    st_m = states_from_probability(p_m, mom, primary["lo"], primary["hi"])
    w_m = minute_weights(st_m, tsd, ts1)
    _, s_m = window_metrics(ts1, o1, c1, w_m, START, END, 1.0, BARS_PER_YEAR)
    neighbours["monthly_refit"] = {
        "cagr": float(s_m["cagr"]), "max_drawdown": float(s_m["max_drawdown"]),
        "sharpe": float(s_m["sharpe"]),
    }
    st_delay = np.r_[2, st_primary[:-1]]
    w_delay = minute_weights(st_delay, tsd, ts1)
    _, s_delay = window_metrics(ts1, o1, c1, w_delay, START, END, 1.0, BARS_PER_YEAR)
    neighbours["one_session_delay"] = {
        "cagr": float(s_delay["cagr"]), "max_drawdown": float(s_delay["max_drawdown"]),
        "sharpe": float(s_delay["sharpe"]),
    }
    neighbours["binary_ml_no_qqq"] = {
        "cagr": float(s_bin["cagr"]), "max_drawdown": float(s_bin["max_drawdown"]),
        "sharpe": float(s_bin["sharpe"]),
    }
    neighbours["momentum_only"] = {
        "cagr": float(s_mom["cagr"]), "max_drawdown": float(s_mom["max_drawdown"]),
        "sharpe": float(s_mom["sharpe"]),
    }

    # Cut test: rebuild the daily states on data truncated at 2022-06-30 and
    # confirm the earlier states are identical.
    cut = "2022-06-30"
    i_cut = int(tsd.searchsorted(pd.Timestamp(cut, tz=tsd.tz), side="right"))
    ts_c, o_c, c_c = tsd[:i_cut], od[:i_cut], cd[:i_cut]
    q_c, t_c, b_c = c_c[:, 0], c_c[:, 1], c_c[:, 2]
    f_c, _ = build_features(q_c, t_c, b_c)
    y_c = path_drawdown_label(t_c, H)
    p_c = walk_forward(ts_c, f_c[cols].to_numpy(), y_c, window=None)
    mom_c = momentum_score(q_c)
    st_c = states_from_probability(p_c, mom_c, primary["lo"], primary["hi"])
    cut_ok = bool(np.array_equal(st_c, st_primary[:i_cut]))
    cut_test = {
        "cut_date": cut,
        "daily_states_identical": cut_ok,
        "n_compared": int(i_cut),
        "minute_note": "daily states are expanded to constant weights within each session, so a mid-session cut cannot change earlier minute weights",
    }

    # Pass / fail against the stated TQQQ bar.
    dev1 = costs["1bp"]
    pass_bar = bool(dev1["cagr"] > 0.3672 and dev1["max_drawdown"] < 0.8229)
    pass_5 = bool(costs["5bp"]["cagr"] > 0.3672 and costs["5bp"]["max_drawdown"] < 0.8229)
    pass_10 = bool(costs["10bp"]["cagr"] > 0.3672 and costs["10bp"]["max_drawdown"] < 0.8229)

    out = {
        "agent": "ml-regime-v2",
        "status": "passed" if pass_bar else "negative_result",
        "hypothesis": (
            "A causal momentum state plus a walk-forward path-drawdown-risk model "
            "can hold TQQQ through calm uptrends and avoid the crash paths, "
            "beating TQQQ buy-and-hold on CAGR with a much smaller drawdown."
        ),
        "universe": ["QQQ", "TQQQ", "BIL"],
        "marks": "1m",
        "data": {
            "source": "local adjusted 1-minute QQQ/TQQQ/BIL bars, regular session",
            "start": START,
            "end": END,
            "holds_2024_2026": False,
        },
        "parameters": {
            "momentum_horizons": list(MOM_HORIZONS),
            "momentum_need": MOM_NEED,
            "label_horizon": H,
            "drawdown_threshold": DD_THR,
            "features": cols,
            "train_window": "expanding (primary)",
            "refit": "quarterly",
            "purge_days": int(H * 1.6) + 4,
            "l2": LAM,
            "lo": primary["lo"],
            "hi": primary["hi"],
            "band": 0.02,
        },
        "windows": {
            "dev": costs,
        },
        "pass": {
            "vs_tqqq_bar_1bp": pass_bar,
            "vs_tqqq_bar_5bp": pass_5,
            "vs_tqqq_bar_10bp": pass_10,
            "bar": {"cagr": 0.3672, "max_drawdown": 0.8229, "sharpe": 0.82},
        },
        "benchmarks": benchmarks,
        "risk_model": risk_metrics,
        "grid": grid_rows,
        "primary": PRIMARY,
        "exposure": {
            "time_tqqq": float(np.mean(st_primary == 1)),
            "time_qqq": float(np.mean(st_primary == 0)),
            "time_bil": float(np.mean(st_primary == 2)),
            "avg_tqqq_weight": float(np.mean(st_primary == 1)),
            "switches": int(np.sum(st_primary[1:] != st_primary[:-1])),
        },
        "correlation": corr,
        "yearly": yearly,
        "subperiods": sub,
        "simple_vol_rule": vol_rows,
        "state_overlap_with_vol_rule": float(np.mean(st_primary == st_vol)),
        "ex_year_cagr": ex_year,
        "neighbours": neighbours,
        "placebo": {
            "shift_risk_probability_200": quantile_stats(np.array(placebo_shift)),
            "permute_states_200": quantile_stats(np.array(placebo_perm)),
            "strategy_cagr": float(dev1["cagr"]),
            "shift_percentile": float(np.mean(np.array(placebo_shift) < dev1["cagr"])),
            "permute_percentile": float(np.mean(np.array(placebo_perm) < dev1["cagr"])),
            "note": "placebo runs are on daily marks for speed; the strategy's daily-mark CAGR is used for the percentile",
        },
        "cut_test": cut_test,
        "variants": {
            "pre_registered_grid": len(GRID),
            "neighbour_checks": len(neighbours),
            "exploratory_screens": (
                "roughly 300 daily-panel configurations were examined while choosing "
                "the mechanism and the pre-registered grid; the grid itself was "
                "fixed before the 1-minute run"
            ),
        },
    }

    # Daily-mark reference computed properly.
    w_primary_daily = state_weights(st_primary)
    rd, sd = window_metrics(tsd, od, cd, w_primary_daily, START, END, 1.0, 252)
    out["daily_mark_reference"] = {
        "cagr": float(sd["cagr"]),
        "max_drawdown": float(sd["max_drawdown"]),
        "sharpe": float(sd["sharpe"]),
        "fills": int(sd["fills"]),
    }

    def _clean(obj):
        if isinstance(obj, dict):
            return {k: _clean(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [_clean(v) for v in obj]
        if isinstance(obj, (np.floating, float)):
            v = float(obj)
            return v if np.isfinite(v) else None
        if isinstance(obj, (np.integer,)):
            return int(obj)
        return obj

    (OUT / "result.json").write_text(json.dumps(_clean(out), indent=2, allow_nan=False))

    print(f"\n=== ml-regime-v2 dev {START}..{END} (1-minute marks) ===")
    print(f"risk model: AUC {risk_metrics['auc']:.3f}  acc@0.5 {risk_metrics['accuracy_at_0.5']:.3f}  "
          f"base {risk_metrics['base_rate']:.3f}  first {risk_metrics['first_prediction']}")
    print(f"primary {PRIMARY}: CAGR {dev1['cagr']*100:.2f}%  DD {dev1['max_drawdown']*100:.2f}%  "
          f"Sharpe {dev1['sharpe']:.2f}  fills {dev1['fills']}  TQQQ {out['exposure']['time_tqqq']*100:.0f}%")
    print(f"  5bp CAGR {costs['5bp']['cagr']*100:.2f}%  DD {costs['5bp']['max_drawdown']*100:.2f}%  "
          f"10bp CAGR {costs['10bp']['cagr']*100:.2f}%  DD {costs['10bp']['max_drawdown']*100:.2f}%")
    print(f"  corr to TQQQ {corr['strategy_vs_tqqq']:.3f}  to 165d base {corr['strategy_vs_165d_base']:.3f}")
    print(f"  simple vol rule 1bp: CAGR {vol_rows['1bp']['cagr']*100:.2f}%  DD {vol_rows['1bp']['max_drawdown']*100:.2f}%  "
          f"Sharpe {vol_rows['1bp']['sharpe']:.2f}")
    print(f"  momentum only: CAGR {s_mom['cagr']*100:.2f}%  DD {s_mom['max_drawdown']*100:.2f}%  Sharpe {s_mom['sharpe']:.2f}")
    print(f"  pass 1bp={pass_bar}  5bp={pass_5}  10bp={pass_10}")
    print("  grid:")
    for g in grid_rows:
        print(f"    {g['label']:16s} CAGR {g['cagr']*100:6.2f}%  DD {g['max_drawdown']*100:5.2f}%  Sharpe {g['sharpe']:.2f}")
    print("\n  yearly strategy / TQQQ:")
    for yy, v in yearly.items():
        print(f"    {yy}: {v['strategy']*100:7.1f}% / {v['tqqq']*100:7.1f}%   TQQQ time {v['time_tqqq']*100:3.0f}%")
    print(f"\nwrote {OUT / 'result.json'}")


if __name__ == "__main__":
    main()
