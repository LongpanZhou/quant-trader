"""Weekly close-location / participation state model for TQQQ.

Frozen primary
--------------
id        ridge5_ms_clv5_vol5_f25
features  clv5, volr5
label     y5 = entry(d+5) / entry(d) - 1
model     ridge, L2=30, expanding training, monthly refit
hurdle    0.25 * training mean of y5
sizing    clip(0.45 / sigma20, 0, 1), sigma20 from entry returns through d-1
decision  every 5 sessions, at the 15:58 signal bar
fill      next bar open (15:59)
hold      5 sessions

The session-shape features are built from adjusted 1-minute bars:
  CLV  = 2*(C-L)/(H-L) - 1, through the 15:58 bar
  VOLR = log(V / trailing 20-session mean volume), through the 15:58 bar
  clv5, volr5 = 5-day trailing means

Development window only: 2016-01-04 .. 2023-12-29. The 2024-2026 holdout is
never loaded.

Run from the repository root:
    $env:PYTHONPATH = "C:\\Users\\27175\\AppData\\Local\\Temp\\opencode\\pylibs"
    $env:BT_THREADS = "1"
    python research/new/family-ml-microstructure/strategy.py
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

BLOCK = 5
LAM = 30.0
VT = 0.45
MIN_TRAIN = 60
PURGE_DAYS = 9
WARMUP_WEIGHT = 1.0
FIRST_REFIT = "2016-07-01"

# Pre-registered 8-cell grid, centred on the frozen primary.
GRID = [
    {"id": "clv5_vol5_m_f25", "features": ["clv5", "volr5"], "refit": "MS",
     "hurdle": 0.25, "primary": True},
    {"id": "clv5_vol5_m_f50", "features": ["clv5", "volr5"], "refit": "MS",
     "hurdle": 0.50, "primary": False},
    {"id": "clv5_vol5_m_f75", "features": ["clv5", "volr5"], "refit": "MS",
     "hurdle": 0.75, "primary": False},
    {"id": "clv5_vol5_q_f25", "features": ["clv5", "volr5"], "refit": "QS",
     "hurdle": 0.25, "primary": False},
    {"id": "clv5_m_f25", "features": ["clv5"], "refit": "MS",
     "hurdle": 0.25, "primary": False},
    {"id": "clv5_m_f50", "features": ["clv5"], "refit": "MS",
     "hurdle": 0.50, "primary": False},
    {"id": "volr5_m_f25", "features": ["volr5"], "refit": "MS",
     "hurdle": 0.25, "primary": False},
    {"id": "clv5_vol5_last5_m_f25", "features": ["clv5", "volr5", "last30_5"],
     "refit": "MS", "hurdle": 0.25, "primary": False},
]
PRIMARY = "clv5_vol5_m_f25"


# ---------------------------------------------------------------------------
# Session-shape features from 1-minute bars
# ---------------------------------------------------------------------------
def _session_features(symbol: str, end: str = END) -> pd.DataFrame:
    """Daily session shape through the second-to-last 1-minute bar.

    The signal bar is `last - 1` (15:58 on a normal session); the entry bar is
    `last` (15:59). Highs, lows, close and volume use the signal bar, so the
    feature timestamp is strictly before the fill.
    """
    df = bt.load_1m(symbol)
    end_ts = pd.Timestamp(end, tz="America/New_York").normalize() + pd.Timedelta(days=1)
    df = df[
        (df["ts"] >= pd.Timestamp(START, tz="America/New_York"))
        & (df["ts"] < end_ts)
    ].reset_index(drop=True)
    dates = bt.session_dates(pd.DatetimeIndex(df["ts"]))
    first, last = bt.day_bounds_from_dates(dates)
    o, h, l, c, v = (df[k].to_numpy() for k in ("open", "high", "low", "close", "volume"))
    sig = last - 1
    i30 = np.minimum(first + 29, sig)
    j30 = np.maximum(sig - 29, first)
    hi = np.array([h[a:b + 1].max() for a, b in zip(first, sig)])
    lo = np.array([l[a:b + 1].min() for a, b in zip(first, sig)])
    vol = np.array([v[a:b + 1].sum() for a, b in zip(first, sig)])
    return pd.DataFrame({
        "date": pd.to_datetime(dates[first]),
        "open": o[first],
        "high": hi,
        "low": lo,
        "close": c[sig],
        "volume": vol,
        "c30": c[i30],
        "o30": o[j30],
        "entry": o[last],
        "n_bars": last - first + 1,
    })


def build_feature_panel(end: str = END) -> pd.DataFrame:
    """QQQ/TQQQ session features, 5-day means, and the 5-session label."""
    q = _session_features("QQQ", end)
    t = _session_features("TQQQ", end)
    m = q.merge(t, on="date", suffixes=("_q", "_t"))
    if not (len(m) == len(q) == len(t)):
        raise RuntimeError("QQQ/TQQQ session calendars do not align")

    oq, hq, lq, cq, vq = (m[k + "_q"].to_numpy() for k in ("open", "high", "low", "close", "volume"))
    ot, ht, lt, ct, vt = (m[k + "_t"].to_numpy() for k in ("open", "high", "low", "close", "volume"))
    c30q = m["c30_q"].to_numpy()
    o30q = m["o30_q"].to_numpy()
    entry = m["entry_t"].to_numpy(float)

    f = pd.DataFrame({"date": m["date"], "entry": entry})
    f["gap"] = oq / np.r_[np.nan, cq[:-1]] - 1.0
    f["first30"] = c30q / oq - 1.0
    f["mid"] = o30q / c30q - 1.0
    f["last30"] = cq / o30q - 1.0
    f["day"] = cq / oq - 1.0
    f["rng"] = (hq - lq) / cq
    f["clv"] = 2.0 * (cq - lq) / np.maximum(hq - lq, 1e-12) - 1.0
    vprev = pd.Series(vq).shift(1).rolling(20, min_periods=15).mean().to_numpy()
    f["volr"] = np.log(np.maximum(vq / np.maximum(vprev, 1.0), 1e-3))
    vtprev = pd.Series(vt).shift(1).rolling(20, min_periods=15).mean().to_numpy()
    f["tvolr"] = np.log(np.maximum(vt / np.maximum(vtprev, 1.0), 1e-3))

    # label: entry-to-entry return over the 5-session holding block
    f["y5"] = np.nan
    f.loc[: len(f) - 6, "y5"] = entry[5:] / entry[:-5] - 1.0

    # 5-day trailing means of the session-shape features
    names5 = {
        "gap": "gap5", "first30": "first30_5", "mid": "mid5",
        "last30": "last30_5", "day": "day5", "clv": "clv5",
        "volr": "volr5", "tvolr": "tvolr5", "rng": "rng5",
    }
    for col, name in names5.items():
        f[name] = pd.Series(f[col]).rolling(5, min_periods=4).mean().to_numpy()
    return f


# ---------------------------------------------------------------------------
# Walk-forward ridge on 5-session blocks
# ---------------------------------------------------------------------------
def _ridge_fit(x: np.ndarray, y: np.ndarray, lam: float = LAM) -> np.ndarray:
    xb = np.column_stack([np.ones(len(x)), x])
    reg = np.full(x.shape[1] + 1, lam)
    reg[0] = 0.0
    return np.linalg.solve(xb.T @ xb + np.diag(reg), xb.T @ y)


def _standardize(xt: np.ndarray, xte: np.ndarray):
    med = np.nanmedian(xt, axis=0)
    xf = np.where(np.isfinite(xt), xt, med)
    mu = xf.mean(axis=0)
    sd = xf.std(axis=0)
    sd = np.where(sd > 1e-12, sd, 1.0)
    xs = np.clip((xf - mu) / sd, -5.0, 5.0)
    xes = np.clip((np.where(np.isfinite(xte), xte, med) - mu) / sd, -5.0, 5.0)
    return xs, xes


def walk_weekly(
    feat: pd.DataFrame,
    ts: pd.DatetimeIndex,
    features: list[str],
    *,
    refit: str = "MS",
    hurdle: float = 0.25,
    lam: float = LAM,
    min_train: int = MIN_TRAIN,
    purge_days: int = PURGE_DAYS,
    label: str = "y5",
    label_shuffle: int | None = None,
    feature_shuffle: int | None = None,
    feature_shift: int = 0,
    refit_end: str | None = None,
):
    """Expanding, purged walk-forward ridge on every 5th session.

    Returns the per-session prediction (only on block starts; NaN elsewhere),
    the training mean used for the hurdle, and the refit count.  Refits run
    from FIRST_REFIT to the last month in `ts` (or `refit_end`), so extending
    `ts` extends the walk-forward automatically (holdout-ready).
    """
    n = len(feat)
    blocks = np.arange(0, n, BLOCK)
    x = feat[features].to_numpy(float)
    if feature_shift:
        xs_all = np.full_like(x, np.nan)
        xs_all[feature_shift:] = x[:-feature_shift]
        x = xs_all
    lab = feat[label].to_numpy(float)
    pred = np.full(n, np.nan)
    base = np.full(n, np.nan)
    n_refit = 0

    if len(ts) == 0:
        return pred, base, 0
    end = (pd.Timestamp(refit_end, tz=ts.tz) if refit_end is not None
           else ts[-1].normalize())
    starts = pd.date_range(
        pd.Timestamp(FIRST_REFIT, tz=ts.tz), end, freq=refit
    )
    for qs in starts:
        qe = qs + (pd.DateOffset(months=1) if refit == "MS" else pd.DateOffset(months=3))
        test = (ts >= qs) & (ts < qe)
        if not test.any():
            continue
        tb = blocks[test[blocks]]
        if len(tb) == 0:
            continue
        tr = blocks[
            (ts[blocks] < qs - pd.Timedelta(days=purge_days))
            & np.isfinite(lab[blocks])
        ]
        if len(tr) < min_train:
            continue
        xt = x[tr].copy()
        yy = lab[tr].copy()
        if label_shuffle is not None:
            rng = np.random.default_rng(1000 + label_shuffle * 97 + int(qs.value % 100000))
            yy = rng.permutation(yy)
        if feature_shuffle is not None:
            rng = np.random.default_rng(2000 + feature_shuffle * 89 + int(qs.value % 100000))
            xt = xt[rng.permutation(len(xt))]
        xs, xes = _standardize(xt, x[tb])
        ym, ys = yy.mean(), yy.std()
        if not np.isfinite(ys) or ys <= 0:
            continue
        w = _ridge_fit(xs, (yy - ym) / ys, lam)
        z = np.column_stack([np.ones(len(xes)), xes]) @ w
        pred[tb] = z * ys + ym
        base[tb] = ym
        n_refit += 1
    return pred, base, n_refit


def vol_target(feat: pd.DataFrame, c: np.ndarray | None = None) -> np.ndarray:
    """45% volatility budget, using entry returns through session d-1."""
    px = feat["entry"].to_numpy(float) if "entry" in feat else np.asarray(c)[:, 1]
    lr = np.r_[np.nan, np.log(px[1:] / px[:-1])]
    sigma = pd.Series(lr).rolling(20, min_periods=15).std(ddof=0).to_numpy() * np.sqrt(252)
    sigma = pd.Series(sigma).shift(1).to_numpy()
    sigma = np.where(np.isfinite(sigma), sigma, np.nanmedian(sigma))
    return np.clip(VT / np.maximum(sigma, 1e-9), 0.0, 1.0)


def expand_weekly(wb: np.ndarray) -> np.ndarray:
    """Hold each block-start weight for 5 sessions."""
    out = np.full(len(wb), np.nan)
    for b in range(0, len(wb), BLOCK):
        out[b:min(b + BLOCK, len(wb))] = wb[b]
    return out


def build_weights(
    ts: pd.DatetimeIndex,
    o: np.ndarray,
    c: np.ndarray,
    *,
    features: pd.DataFrame | None = None,
    cell: dict | None = None,
    label_shuffle: int | None = None,
    feature_shuffle: int | None = None,
    feature_shift: int = 0,
    refit_end: str | None = None,
):
    """Causal daily target weights for the frozen model / a grid cell.

    `ts, o, c` are the daily panel (open/close per symbol).  The session-shape
    features are read from `features`, or rebuilt from 1-minute bars if not
    supplied.  Nothing after `ts[-1]` is used.  The walk-forward refits only on
    labels realised before each test month, with a 9-day purge.  `refit_end`
    is a reproducibility hook for the pre-freeze calendar; the default runs to
    the last month in `ts` (holdout-ready).
    """
    if cell is None:
        cell = GRID[0]
    if features is None:
        features = build_feature_panel()
    if len(features) != len(ts):
        raise ValueError("feature panel and daily panel lengths differ")
    fdates = pd.DatetimeIndex(pd.to_datetime(features["date"]).dt.tz_localize(ts.tz))
    if not np.array_equal(fdates, pd.DatetimeIndex(ts)):
        raise ValueError("feature panel and daily panel dates differ")

    pred, base, n_refit = walk_weekly(
        features, ts, cell["features"], refit=cell["refit"], hurdle=cell["hurdle"],
        label_shuffle=label_shuffle, feature_shuffle=feature_shuffle,
        feature_shift=feature_shift, refit_end=refit_end,
    )
    vt = vol_target(features, c)
    wb = np.where(
        np.isfinite(pred),
        vt * (pred >= cell["hurdle"] * base).astype(float),
        WARMUP_WEIGHT,
    )
    wb = np.clip(wb, 0.0, 1.0)
    w_daily = expand_weekly(wb)
    info = {
        "pred": pred,
        "base": base,
        "wb": wb,
        "vt": vt,
        "n_refit": n_refit,
    }
    return w_daily, info


# ---------------------------------------------------------------------------
# 1-minute execution
# ---------------------------------------------------------------------------
def minute_weights(w_daily: np.ndarray, ts1: pd.DatetimeIndex) -> np.ndarray:
    """Expand a daily target to every minute bar.

    w_daily[d] is set at the 15:58 signal bar of session d and filled at the
    15:59 open, so from that signal bar through the next session's signal bar
    it is the active target.
    """
    dates_m = bt.session_dates(ts1)
    first, last = bt.day_bounds_from_dates(dates_m)
    sig = last - 1
    day_id = bt.day_ids(ts1)
    prev = np.r_[WARMUP_WEIGHT, w_daily[:-1]]
    w = np.where(np.arange(len(ts1)) >= sig[day_id], w_daily[day_id], prev[day_id])
    return np.clip(np.where(np.isfinite(w), w, WARMUP_WEIGHT), 0.0, 1.0)


def simulate_minute(ts1, o1, c1, w_daily, slip=1.0):
    wm = minute_weights(w_daily, ts1)
    ww = np.zeros((len(ts1), 3))
    ww[:, 1] = wm
    ww[:, 2] = 1.0 - wm
    r = bt.simulate(ts1, o1, c1, ww, band=0.02, slippage_bps=slip)
    return r, bt.stats(r, BARS_PER_YEAR)


# ---------------------------------------------------------------------------
# Reporting helpers
# ---------------------------------------------------------------------------
def daily_series(values, ts):
    s = pd.Series(values, index=ts)
    d = s.groupby(s.index.date).last()
    d.index = pd.DatetimeIndex(d.index)
    return d


def yearly_table(ts1, equity, tqqq):
    eq = daily_series(equity, ts1)
    bq = daily_series(tqqq, ts1)
    out = {}
    for year in sorted(set(eq.index.year)):
        m = np.asarray([d.year == year for d in eq.index])
        if m.sum() < 2:
            continue
        out[str(int(year))] = {
            "strategy": float(eq[m].iloc[-1] / eq[m].iloc[0] - 1.0),
            "tqqq": float(bq[m].iloc[-1] / bq[m].iloc[0] - 1.0),
        }
    return out


def subperiod(ts1, equity, tqqq, start, end):
    eq = daily_series(equity, ts1)
    tq = daily_series(tqqq, ts1)
    m = np.asarray([(d >= pd.Timestamp(start)) and (d <= pd.Timestamp(end)) for d in eq.index])
    seg, bs = eq[m], tq[m]
    if len(seg) < 2:
        return None
    years = (seg.index[-1] - seg.index[0]).days / 365.25
    peak = np.maximum.accumulate(seg)
    bpeak = np.maximum.accumulate(bs)
    return {
        "cagr": float((seg.iloc[-1] / seg.iloc[0]) ** (1 / years) - 1),
        "max_drawdown": float(-(seg / peak - 1).min()),
        "tqqq_cagr": float((bs.iloc[-1] / bs.iloc[0]) ** (1 / years) - 1),
        "tqqq_max_drawdown": float(-(bs / bpeak - 1).min()),
    }


def max_dd_window(ts1, equity):
    s = daily_series(equity, ts1)
    peak = np.maximum.accumulate(s.to_numpy())
    dd = s.to_numpy() / peak - 1.0
    trough = int(np.argmin(dd))
    peak_i = int(np.argmax(s.to_numpy()[:trough + 1]))
    return {
        "peak": str(s.index[peak_i]),
        "trough": str(s.index[trough]),
        "drawdown": float(-dd[trough]),
    }


def quantile_stats(x):
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    return {
        "mean": float(np.mean(x)),
        "p5": float(np.percentile(x, 5)),
        "p50": float(np.percentile(x, 50)),
        "p95": float(np.percentile(x, 95)),
        "min": float(np.min(x)),
        "max": float(np.max(x)),
    }


def clean(obj):
    if isinstance(obj, dict):
        return {k: clean(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [clean(v) for v in obj]
    if isinstance(obj, (np.floating, float)):
        v = float(obj)
        return v if np.isfinite(v) else None
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, np.bool_):
        return bool(obj)
    return obj


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    warnings.filterwarnings("ignore")

    tsd, od, cd = bt.panel(("QQQ", "TQQQ", "BIL"), START, END, "1D", warmup_days=0)
    ts1, o1, c1 = bt.panel(("QQQ", "TQQQ", "BIL"), START, END, "1min", warmup_days=0)
    feat = build_feature_panel()
    if len(feat) != len(tsd):
        raise RuntimeError("feature panel / daily panel length mismatch")

    q, t, b = cd[:, 0], cd[:, 1], cd[:, 2]
    n = len(tsd)

    # --- grid -------------------------------------------------------------
    grid_rows = []
    preds = {}
    for cell in GRID:
        w_daily, info = build_weights(tsd, od, cd, features=feat, cell=cell)
        r, s = simulate_minute(ts1, o1, c1, w_daily, 1.0)
        preds[cell["id"]] = (w_daily, info, r, s)
        first_pred = tsd[np.isfinite(info["pred"])][0] if np.isfinite(info["pred"]).any() else None
        grid_rows.append({
            "id": cell["id"],
            "features": cell["features"],
            "refit": cell["refit"],
            "hurdle": cell["hurdle"],
            "primary": bool(cell.get("primary", False)),
            "cagr": float(s["cagr"]),
            "max_drawdown": float(s["max_drawdown"]),
            "sharpe": float(s["sharpe"]),
            "sortino": float(s["sortino"]),
            "volatility": float(s["volatility"]),
            "avg_tqqq_weight": float(np.mean(w_daily)),
            "fills": int(s["fills"]),
            "turnover": float(s["turnover"]),
            "first_prediction": str(first_pred.date()) if first_pred is not None else None,
            "pass_bar_1bp": bool(s["cagr"] > 0.3672 and s["max_drawdown"] < 0.8229),
        })

    primary_cell = next(c for c in GRID if c["id"] == PRIMARY)
    w_primary, info_primary, r_primary, s_primary = preds[PRIMARY]

    # --- cost ladder ------------------------------------------------------
    costs = {}
    primary_results = {}
    for slip in (1.0, 5.0, 10.0):
        r, s = simulate_minute(ts1, o1, c1, w_primary, slip)
        primary_results[slip] = (r, s)
        costs[f"{int(slip)}bp"] = {
            "cagr": float(s["cagr"]),
            "total_return": float(s["total_return"]),
            "max_drawdown": float(s["max_drawdown"]),
            "sharpe": float(s["sharpe"]),
            "sortino": float(s["sortino"]),
            "volatility": float(s["volatility"]),
            "exposure": float(s["exposure"]),
            "avg_tqqq_weight": float(np.mean(w_primary)),
            "fills": int(s["fills"]),
            "turnover": float(s["turnover"]),
            "ending_equity": float(s["ending_equity"]),
        }

    r1, s1 = primary_results[1.0]
    eq_daily = daily_series(r1["equity"], ts1)
    tq_daily = daily_series(c1[:, 1], ts1)
    qq_daily = daily_series(c1[:, 0], ts1)
    bil_daily = daily_series(c1[:, 2], ts1)

    # --- benchmarks -------------------------------------------------------
    benchmarks = {}
    for name, close in (("tqqq", c1[:, 1]), ("qqq", c1[:, 0]), ("bil", c1[:, 2])):
        bm = bt.benchmark(close, ts1, BARS_PER_YEAR)
        benchmarks[name] = {k: float(v) for k, v in bm.items()}

    # vol-target-only control
    vt_only = vol_target(feat, cd)
    r_vt, s_vt = simulate_minute(ts1, o1, c1, vt_only, 1.0)
    benchmarks["vol_target_only_1bp"] = {
        "cagr": float(s_vt["cagr"]),
        "max_drawdown": float(s_vt["max_drawdown"]),
        "sharpe": float(s_vt["sharpe"]),
        "avg_tqqq_weight": float(np.mean(vt_only)),
        "fills": int(s_vt["fills"]),
    }

    # --- correlations -----------------------------------------------------
    strat_ret = eq_daily.pct_change().dropna()
    corr = {
        "strategy_vs_tqqq": float(strat_ret.corr(tq_daily.pct_change().dropna())),
        "strategy_vs_qqq": float(strat_ret.corr(qq_daily.pct_change().dropna())),
        "tqqq_vs_qqq": float(tq_daily.pct_change().corr(qq_daily.pct_change().dropna())),
    }

    # --- exposures / drawdown / yearly -----------------------------------
    exposure = {
        "avg_tqqq_weight": float(np.mean(w_primary)),
        "time_full": float(np.mean(w_primary > 0.98)),
        "time_zero": float(np.mean(w_primary < 0.02)),
        "switches": int(np.sum(np.abs(np.diff(w_primary)) > 0.02)),
        "first_prediction": str(tsd[np.isfinite(info_primary["pred"])][0].date()),
        "n_refits": int(info_primary["n_refit"]),
    }
    dd_window = max_dd_window(ts1, r1["equity"])
    yearly = yearly_table(ts1, r1["equity"], c1[:, 1])
    sub = {
        "2016-2019": subperiod(ts1, r1["equity"], c1[:, 1], "2016-01-04", "2019-12-31"),
        "2020-2021": subperiod(ts1, r1["equity"], c1[:, 1], "2020-01-01", "2021-12-31"),
        "2022-2023": subperiod(ts1, r1["equity"], c1[:, 1], "2022-01-01", "2023-12-29"),
    }
    # model-only period (after the first prediction)
    first_pred_date = tsd[np.isfinite(info_primary["pred"])][0]
    model_period = subperiod(ts1, r1["equity"], c1[:, 1],
                             str(first_pred_date.date()), END)

    # --- simple-rule controls --------------------------------------------
    def rule_weights_weekly(sig, thr):
        wb = np.where(np.isfinite(sig), vt_only * (sig <= thr).astype(float), WARMUP_WEIGHT)
        return expand_weekly(wb)

    controls = {}
    clv5 = feat["clv5"].to_numpy(float)
    volr5 = feat["volr5"].to_numpy(float)
    volr = feat["volr"].to_numpy(float)
    control_weights = {
        "clv5<=0.25_weekly_xVT": rule_weights_weekly(clv5, 0.25),
        "clv5<=0.5_weekly_xVT": rule_weights_weekly(clv5, 0.5),
        "volr5<=0.25_weekly_xVT": rule_weights_weekly(volr5, 0.25),
        "volr<=0.25_daily_xVT": np.clip(np.where(np.isfinite(volr), (volr <= 0.25) * vt_only, WARMUP_WEIGHT), 0, 1),
        "vol_target_only": vt_only,
        "tqqq_buyhold": np.ones(n),
    }
    for name, w in control_weights.items():
        r_c, s_c = simulate_minute(ts1, o1, c1, w, 1.0)
        controls[name] = {
            "cagr": float(s_c["cagr"]),
            "max_drawdown": float(s_c["max_drawdown"]),
            "sharpe": float(s_c["sharpe"]),
            "avg_tqqq_weight": float(np.mean(w)),
            "fills": int(s_c["fills"]),
        }

    # cost ladder for the two key simple-rule controls
    control_costs = {}
    for name in ("clv5<=0.25_weekly_xVT", "volr<=0.25_daily_xVT"):
        w = control_weights[name]
        row = {}
        for slip in (1.0, 5.0, 10.0):
            _, s_c = simulate_minute(ts1, o1, c1, w, slip)
            row[f"{int(slip)}bp"] = {
                "cagr": float(s_c["cagr"]),
                "max_drawdown": float(s_c["max_drawdown"]),
                "sharpe": float(s_c["sharpe"]),
            }
        control_costs[name] = row

    # provenance check: the pre-freeze calendar ended at 2023-10-01 and left
    # Nov-Dec 2023 on the 1.0 warm-up weight.  The primary above uses the full
    # calendar (holdout-ready).  Record the old-calendar number for the report.
    w_old, _ = build_weights(tsd, od, cd, features=feat, cell=primary_cell,
                             refit_end="2023-10-01")
    _, s_old = simulate_minute(ts1, o1, c1, w_old, 1.0)
    frozen_calendar = {
        "refit_end": "2023-10-01",
        "cagr": float(s_old["cagr"]),
        "max_drawdown": float(s_old["max_drawdown"]),
        "sharpe": float(s_old["sharpe"]),
        "avg_tqqq_weight": float(np.mean(w_old)),
        "fills": int(s_old["fills"]),
        "note": "reproduces the pre-freeze scratch number exactly; Nov-Dec 2023 "
                "are held at the 1.0 warm-up weight because the old refit calendar "
                "stopped at 2023-10-01.  The primary headline uses the full calendar.",
    }

    # --- ablations (outside the grid) ------------------------------------
    ablations = {}
    ablation_sets = {
        "clv5_volr5": ["clv5", "volr5"],
        "clv5_only": ["clv5"],
        "volr5_only": ["volr5"],
        "last30_5_only": ["last30_5"],
        "gap5_first30_5_mid5": ["gap5", "first30_5", "mid5"],
        "full_shape": ["gap5", "first30_5", "mid5", "last30_5", "clv5", "volr5"],
    }
    for name, feats in ablation_sets.items():
        cell = {"id": name, "features": feats, "refit": "MS", "hurdle": 0.25}
        w_a, info_a = build_weights(tsd, od, cd, features=feat, cell=cell)
        r_a, s_a = simulate_minute(ts1, o1, c1, w_a, 1.0)
        ablations[name] = {
            "features": feats,
            "cagr": float(s_a["cagr"]),
            "max_drawdown": float(s_a["max_drawdown"]),
            "sharpe": float(s_a["sharpe"]),
            "avg_tqqq_weight": float(np.mean(w_a)),
            "fills": int(s_a["fills"]),
        }

    # --- placebo: shuffled labels and shuffled training features ----------
    n_placebo = 20
    placebo_label = []
    placebo_feat = []
    for seed in range(n_placebo):
        w_l, _ = build_weights(tsd, od, cd, features=feat, cell=primary_cell,
                               label_shuffle=seed)
        _, s_l = simulate_minute(ts1, o1, c1, w_l, 1.0)
        placebo_label.append(float(s_l["cagr"]))

        w_f, _ = build_weights(tsd, od, cd, features=feat, cell=primary_cell,
                               feature_shuffle=seed)
        _, s_f = simulate_minute(ts1, o1, c1, w_f, 1.0)
        placebo_feat.append(float(s_f["cagr"]))

    # timing placebo: features shifted by one block
    w_shift, _ = build_weights(tsd, od, cd, features=feat, cell=primary_cell,
                               feature_shift=BLOCK)
    _, s_shift = simulate_minute(ts1, o1, c1, w_shift, 1.0)

    placebo = {
        "shuffled_labels_20": quantile_stats(placebo_label),
        "shuffled_training_features_20": quantile_stats(placebo_feat),
        "shifted_features_5_sessions": {
            "cagr": float(s_shift["cagr"]),
            "max_drawdown": float(s_shift["max_drawdown"]),
            "sharpe": float(s_shift["sharpe"]),
        },
        "real_cagr": float(costs["1bp"]["cagr"]),
        "label_percentile": float(np.mean(np.array(placebo_label) < costs["1bp"]["cagr"])),
        "feature_percentile": float(np.mean(np.array(placebo_feat) < costs["1bp"]["cagr"])),
        "note": "placebos use the same model, hurdle and cost; labels/features are "
                "permuted within each monthly training window, or the features are "
                "shifted one 5-session block for the timing test",
    }

    # --- cut tests --------------------------------------------------------
    def cut_test(cut_date):
        idx = int(tsd.searchsorted(pd.Timestamp(cut_date, tz=tsd.tz), side="right"))
        idx = (idx // BLOCK) * BLOCK
        if idx <= 0 or idx >= n:
            return {"cut": cut_date, "skipped": True}
        ts_c, o_c, c_c = tsd[:idx], od[:idx], cd[:idx]
        feat_c = feat.iloc[:idx].reset_index(drop=True)
        w_c, _ = build_weights(ts_c, o_c, c_c, features=feat_c, cell=primary_cell)
        diff = np.abs(w_c - w_primary[:idx])
        return {
            "cut": cut_date,
            "cut_index": int(idx),
            "cut_session": str(tsd[idx - 1].date()),
            "n_compared": int(idx),
            "max_abs_weight_diff": float(np.max(diff)),
            "n_changed_gt_1e-12": int(np.sum(diff > 1e-12)),
        }

    cut_tests = [cut_test("2020-06-30"), cut_test("2022-06-30")]

    # --- pass / fail ------------------------------------------------------
    dev1 = costs["1bp"]
    pass_1 = bool(dev1["cagr"] > 0.3672 and dev1["max_drawdown"] < 0.8229)
    pass_5 = bool(costs["5bp"]["cagr"] > 0.3672 and costs["5bp"]["max_drawdown"] < 0.8229)
    pass_10 = bool(costs["10bp"]["cagr"] > 0.3672 and costs["10bp"]["max_drawdown"] < 0.8229)
    dd_target = bool(dev1["max_drawdown"] < 0.60)

    # --- result -----------------------------------------------------------
    out = {
        "agent": "family-ml-microstructure",
        "strategy": "Weekly close-location / participation ridge state model",
        "status": "passed" if (pass_1 and pass_5 and pass_10) else "negative_result",
        "hypothesis": (
            "5-day mean close location and volume participation predict the next "
            "5-session TQQQ return; a walk-forward ridge model holds TQQQ when the "
            "predicted return is above a fraction of the training mean, with a 45% "
            "volatility budget for risk control."
        ),
        "universe": ["QQQ", "TQQQ", "BIL"],
        "marks": "1m",
        "data": {
            "source": "local adjusted 1-minute QQQ/TQQQ/BIL bars, regular session",
            "start": START,
            "end": END,
            "holds_2024_2026": False,
            "feature_timestamp": "15:58 ET signal bar; fill at the 15:59 open",
        },
        "primary": PRIMARY,
        "parameters": {
            "features": ["clv5", "volr5"],
            "clv_definition": "2*(C-L)/(H-L)-1 through the 15:58 bar",
            "volr_definition": "log(V / trailing 20-session mean volume) through the 15:58 bar",
            "feature_average": "5-session trailing mean",
            "label": "entry(d+5)/entry(d)-1",
            "model": "ridge",
            "l2": LAM,
            "refit": "monthly (MS), expanding",
            "min_train_blocks": MIN_TRAIN,
            "purge_days": PURGE_DAYS,
            "blocks": "every 5 sessions",
            "hurdle": 0.25,
            "vol_target": VT,
            "warmup_weight": WARMUP_WEIGHT,
            "band": 0.02,
        },
        "windows": {"dev": costs},
        "pass": {
            "bar": {"cagr": 0.3672, "max_drawdown": 0.8229, "sharpe": 0.82},
            "at_1bp": pass_1,
            "at_5bp": pass_5,
            "at_10bp": pass_10,
            "dd_under_60": dd_target,
        },
        "benchmarks": benchmarks,
        "grid": grid_rows,
        "ablations": ablations,
        "exposure": exposure,
        "drawdown_window": dd_window,
        "correlation": corr,
        "yearly": yearly,
        "subperiods": sub,
        "model_period": model_period,
        "simple_rule_controls": controls,
        "simple_rule_control_costs": control_costs,
        "frozen_calendar_diagnostic": frozen_calendar,
        "placebo": placebo,
        "cut_tests": cut_tests,
        "family_purity": {
            "primary_features": ["clv5", "volr5"],
            "source": "intraday 1-minute session shape (close location and volume participation)",
            "excluded": [
                "daily realised volatility / drawdown / trend SMA / relative strength",
                "intraday range (rng) is excluded from the primary and the grid; an "
                "exploratory screen showed it acts as a volatility proxy",
            ],
            "vol_target_role": "risk control only, not a predictor",
        },
        "variants": {
            "pre_registered_grid": len(GRID),
            "primary_frozen": PRIMARY,
            "exploratory_screens_disclosed": (
                "next-open classifiers/regressions, shallow CART trees with/without rng, "
                "daily clv/volume gates, a 1-session-label weekly variant, and the "
                "weekly ridge feature/hurdle/refit surface"
            ),
        },
    }
    (OUT / "result.json").write_text(json.dumps(clean(out), indent=2, allow_nan=False))

    # --- console ----------------------------------------------------------
    print(f"\n=== {PRIMARY} dev {START}..{END} (1-minute marks) ===")
    print(f"first prediction {exposure['first_prediction']}  refits {exposure['n_refits']}  "
          f"avg TQQQ weight {exposure['avg_tqqq_weight']*100:.1f}%")
    print(f"1bp : CAGR {dev1['cagr']*100:6.2f}%  DD {dev1['max_drawdown']*100:5.2f}%  "
          f"Sharpe {dev1['sharpe']:4.2f}  fills {dev1['fills']}  turnover {dev1['turnover']:.0f}x")
    print(f"5bp : CAGR {costs['5bp']['cagr']*100:6.2f}%  DD {costs['5bp']['max_drawdown']*100:5.2f}%  "
          f"Sharpe {costs['5bp']['sharpe']:4.2f}")
    print(f"10bp: CAGR {costs['10bp']['cagr']*100:6.2f}%  DD {costs['10bp']['max_drawdown']*100:5.2f}%  "
          f"Sharpe {costs['10bp']['sharpe']:4.2f}")
    print(f"TQQQ : CAGR {benchmarks['tqqq']['cagr']*100:6.2f}%  DD {benchmarks['tqqq']['max_drawdown']*100:5.2f}%  "
          f"Sharpe {benchmarks['tqqq']['sharpe']:4.2f}")
    print(f"pass 1bp={pass_1} 5bp={pass_5} 10bp={pass_10}  dd<60={dd_target}")
    print(f"corr to TQQQ {corr['strategy_vs_tqqq']:.3f}  to QQQ {corr['strategy_vs_qqq']:.3f}")
    print(f"placebo label p95 {placebo['shuffled_labels_20']['p95']*100:.2f}%  "
          f"feature p95 {placebo['shuffled_training_features_20']['p95']*100:.2f}%  "
          f"real {dev1['cagr']*100:.2f}%")
    print("\ngrid:")
    for g in grid_rows:
        print(f"  {g['id']:28s} CAGR {g['cagr']*100:6.2f}%  DD {g['max_drawdown']*100:5.2f}%  "
              f"Sharpe {g['sharpe']:4.2f}  wt {g['avg_tqqq_weight']*100:5.1f}%  pass={g['pass_bar_1bp']}")
    print("\nyearly (strategy / TQQQ):")
    for yy, v in yearly.items():
        print(f"  {yy}: {v['strategy']*100:7.1f}% / {v['tqqq']*100:7.1f}%")
    print("\nsimple controls:")
    for k, v in controls.items():
        print(f"  {k:28s} CAGR {v['cagr']*100:6.2f}%  DD {v['max_drawdown']*100:5.2f}%  Sharpe {v['sharpe']:4.2f}")
    print("\ncut tests:")
    for c in cut_tests:
        print(f"  {c}")
    print(f"\nwrote {OUT / 'result.json'}")


if __name__ == "__main__":
    main()
