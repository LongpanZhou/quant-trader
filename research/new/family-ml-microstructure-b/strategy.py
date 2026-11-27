"""ML-microstructure-b: walk-forward intraday price-action allocator for TQQQ.

Development-only specification, frozen in HYPOTHESIS.md:

  features : QQQ gap, first-30m, last-30m, daily range, close location, volume
  target   : TQQQ 15:59-open to next 15:59-open return
  model    : L2 ridge (headline) / L2 logistic, quarterly expanding refit
  signal   : long TQQQ when forecast excess return >= 50 bp, else BIL
  fills    : research/bt.py next-open, 2% band, long-only

Run from the repo root:

    $env:PYTHONPATH = "C:\\Users\\27175\\AppData\\Local\\Temp\\opencode\\pylibs"
    $env:BT_THREADS = "1"
    python research/new/family-ml-microstructure-b/strategy.py

The 1-minute parquet files are read with a hard timestamp filter at
2023-12-30 00:00 UTC; the daily adjustment files are filtered at 2023-12-29.
No 2024-2026 row is loaded, inspected or scored.
"""
from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402

DEV_START = "2016-01-04"
DEV_END = "2023-12-29"
DATA_DIR = ROOT / "data" / "intraday-hf"
OUT_DIR = Path(__file__).resolve().parent
BARS_PER_YEAR = 252 * 390

F6 = ["gap", "first30", "last30", "rng", "clv", "volr"]
F2 = ["clv", "volr"]
F5 = ["gap", "first30", "last30", "clv", "volr"]

HEADLINE_THRESHOLD = 0.0050  # 50 bp predicted excess return
RIDGE_LAMBDA = 30.0
LOGIT_LAMBDA = 5.0
MIN_TRAIN = 100
PURGE_DAYS = 3
REFIT = "QS"
PLACEBO_SEEDS = 20


# --------------------------------------------------------------------------- data
def _load_1m_dev(symbol: str) -> pd.DataFrame:
    """Adjusted 1m bars, read with a parquet filter that excludes 2024+."""
    end_utc = pd.Timestamp(DEV_END, tz="UTC") + pd.Timedelta(days=1)
    df = pd.read_parquet(
        DATA_DIR / f"{symbol}-1m.parquet",
        columns=["ts", "open", "high", "low", "close", "volume"],
        filters=[("ts", "<", end_utc)],
    )
    df["ts"] = pd.to_datetime(df["ts"], utc=True).dt.tz_convert("America/New_York")
    df = df[
        (df["ts"].dt.time >= pd.Timestamp("09:30").time())
        & (df["ts"].dt.time < pd.Timestamp("16:00").time())
    ].copy()
    df["date"] = df["ts"].dt.date

    # NYSE half-days: discard after-hours prints after 13:00, as bt.load_1m does.
    after_close = df["date"].isin(bt.HALF_DAYS) & (
        df["ts"].dt.time > pd.Timestamp("13:00").time()
    )
    df = df.loc[~after_close].copy()

    # BIL is raw in the source and had a 1:2 reverse split on 2017-11-30.
    if symbol == "BIL":
        before = df["date"] < pd.Timestamp("2017-11-30").date()
        for column in ("open", "high", "low", "close"):
            df.loc[before, column] *= 2.0

    daily = pd.read_parquet(
        DATA_DIR / f"{symbol}-1d-yahoo.parquet",
        columns=["date", "close", "adjclose"],
        filters=[("date", "<=", pd.Timestamp(DEV_END).date())],
    )
    daily["date"] = pd.to_datetime(daily["date"]).dt.date
    daily["factor"] = daily["adjclose"].astype(float) / daily["close"].astype(float)
    df = df.merge(daily[["date", "factor"]], on="date", how="left")
    df["factor"] = df["factor"].ffill().bfill()
    for column in ("open", "high", "low", "close"):
        df[column] = df[column] * df["factor"]
    return df[["ts", "date", "open", "high", "low", "close", "volume"]]


def load_panel():
    """QQQ/TQQQ/BIL 1m panel and QQQ high/low/volume, all development-only."""
    frames = {symbol: _load_1m_dev(symbol) for symbol in ("QQQ", "TQQQ", "BIL")}
    base = pd.DatetimeIndex(frames["QQQ"]["ts"])
    assert base.is_monotonic_increasing and not base.has_duplicates
    assert base[-1] <= pd.Timestamp(DEV_END + " 15:59", tz="America/New_York")

    opens, closes = [], []
    highs = lows = volumes = None
    for symbol in ("QQQ", "TQQQ", "BIL"):
        frame = frames[symbol].set_index("ts").reindex(base).ffill().bfill()
        opens.append(frame["open"].to_numpy(float))
        closes.append(frame["close"].to_numpy(float))
        if symbol == "QQQ":
            highs = frame["high"].to_numpy(float)
            lows = frame["low"].to_numpy(float)
            volumes = frame["volume"].to_numpy(float)
    return (
        base,
        np.column_stack(opens),
        np.column_stack(closes),
        highs,
        lows,
        volumes,
    )


def build_features(ts, opens, closes, highs, lows, volumes) -> pd.DataFrame:
    """Daily QQQ intraday-shape features and the tradable TQQQ label."""
    dates = bt.session_dates(ts)
    first, last = bt.day_bounds_from_dates(dates)
    sig = last - 1  # 15:58 bar; its close is the 15:59 print

    q_o = opens[first, 0]
    q_c = closes[sig, 0]
    q_h = np.array([highs[a:b + 1].max() for a, b in zip(first, sig)])
    q_l = np.array([lows[a:b + 1].min() for a, b in zip(first, sig)])
    q_v = np.array([volumes[a:b + 1].sum() for a, b in zip(first, sig)])

    i30 = np.minimum(first + 29, sig)   # 10:00 close
    j30 = np.maximum(sig - 29, first)   # 15:29 open
    q_c30 = closes[i30, 0]
    q_o30 = opens[j30, 0]
    entry = opens[last, 1]              # TQQQ 15:59 open, next-open fill

    prev_c = np.r_[np.nan, q_c[:-1]]
    vol_prev = pd.Series(q_v).shift(1).rolling(20, min_periods=15).mean().to_numpy()
    hl = np.maximum(q_h - q_l, 1e-12)

    frame = pd.DataFrame({"date": pd.to_datetime(dates[first])})
    frame["gap"] = q_o / prev_c - 1.0
    frame["first30"] = q_c30 / q_o - 1.0
    frame["last30"] = q_c / q_o30 - 1.0
    frame["rng"] = (q_h - q_l) / np.maximum(q_c, 1e-12)
    frame["clv"] = 2.0 * (q_c - q_l) / hl - 1.0
    frame["volr"] = np.log(np.maximum(q_v / np.maximum(vol_prev, 1.0), 1e-3))
    frame["entry"] = entry
    frame["y"] = np.r_[entry[1:] / entry[:-1] - 1.0, np.nan]

    assert len(frame) == len(first)
    assert frame["date"].iloc[0] == pd.Timestamp(DEV_START)
    assert frame["date"].iloc[-1] == pd.Timestamp(DEV_END)
    assert np.isfinite(frame["y"].iloc[:-1]).all()
    return frame


# --------------------------------------------------------------------------- model
def _prep_train_test(xt: np.ndarray, xte: np.ndarray):
    """Training-only imputation and scaling; never touches full-sample stats."""
    med = np.nanmedian(xt, axis=0)
    xt_filled = np.where(np.isfinite(xt), xt, med)
    mu = xt_filled.mean(axis=0)
    sd = xt_filled.std(axis=0)
    sd = np.where(sd > 1e-12, sd, 1.0)
    xte_filled = np.where(np.isfinite(xte), xte, med)
    return (
        np.clip((xt_filled - mu) / sd, -5.0, 5.0),
        np.clip((xte_filled - mu) / sd, -5.0, 5.0),
    )


def _ridge_fit(x: np.ndarray, y: np.ndarray, lam: float) -> np.ndarray:
    xb = np.column_stack([np.ones(len(x)), x])
    reg = np.full(xb.shape[1], lam)
    reg[0] = 0.0
    return np.linalg.solve(xb.T @ xb + np.diag(reg), xb.T @ y)


def _logit_fit(x: np.ndarray, y: np.ndarray, lam: float, iters: int = 60) -> np.ndarray:
    xb = np.column_stack([np.ones(len(x)), x])
    w = np.zeros(xb.shape[1])
    reg = np.full(xb.shape[1], lam)
    reg[0] = 0.0
    for _ in range(iters):
        p = 1.0 / (1.0 + np.exp(-np.clip(xb @ w, -30.0, 30.0)))
        grad = xb.T @ (p - y) + reg * w
        curv = np.maximum(p * (1.0 - p), 1e-6)
        hess = xb.T @ (xb * curv[:, None]) + np.diag(reg + 1e-10)
        step = np.linalg.solve(hess, grad)
        w -= step
        if np.max(np.abs(step)) < 1e-9:
            break
    return w


def walk_forward(frame: pd.DataFrame, features: list[str], kind: str,
                 lam: float, shuffle_seed: int | None = None):
    """Expanding, quarterly-refit predictions. No full-sample statistics."""
    tsd = pd.DatetimeIndex(frame["date"]).tz_localize("America/New_York")
    x = frame[features].to_numpy(float)
    y = frame["y"].to_numpy(float)
    n = len(frame)
    pred = np.full(n, np.nan)
    base = np.full(n, np.nan)
    coefs = []
    rng = np.random.default_rng(shuffle_seed) if shuffle_seed is not None else None

    for qs in pd.date_range("2016-07-01", "2023-10-01", freq=REFIT, tz=tsd.tz):
        qe = qs + pd.DateOffset(months=3)
        test = (tsd >= qs) & (tsd < qe)
        if not test.any():
            continue
        train = np.where(
            (tsd < qs - pd.Timedelta(days=PURGE_DAYS)) & np.isfinite(y)
        )[0]
        if len(train) < MIN_TRAIN:
            continue

        xt, xte = _prep_train_test(x[train], x[test])
        if kind == "ridge":
            yy = y[train].copy()
            if shuffle_seed is not None:
                yy = rng.permutation(yy)  # within-training shuffled-label placebo
            mu, sd = float(yy.mean()), float(yy.std())
            if sd <= 1e-12:
                sd = 1.0
            w = _ridge_fit(xt, (yy - mu) / sd, lam)
            pred[test] = (np.column_stack([np.ones(len(xte)), xte]) @ w) * sd + mu
            base[test] = mu
            coefs.append(w[1:])
        elif kind == "logit":
            yy = (y[train] > 0).astype(float)
            if shuffle_seed is not None:
                yy = rng.permutation(yy)
            w = _logit_fit(xt, yy, lam)
            pred[test] = 1.0 / (
                1.0 + np.exp(-np.clip(np.column_stack([np.ones(len(xte)), xte]) @ w,
                                      -30.0, 30.0))
            )
            base[test] = float(yy.mean())
            coefs.append(w[1:])
        else:
            raise ValueError(kind)

    return pred, base, (np.array(coefs) if coefs else np.empty((0, len(features))))


# --------------------------------------------------------------------------- simulation
def weight_schedule(w_daily: np.ndarray, ts, sig, day_id) -> np.ndarray:
    """Daily target -> 1m target. Signal at 15:58 executes at 15:59 open."""
    w = np.clip(np.where(np.isfinite(w_daily), w_daily, 0.0), 0.0, 1.0)
    prev = np.r_[0.0, w[:-1]]
    return np.where(np.arange(len(ts)) >= sig[day_id], w[day_id], prev[day_id])


def simulate(w_daily: np.ndarray, ts, opens, closes, sig, day_id,
             slippage_bps: float = 1.0):
    w = weight_schedule(w_daily, ts, sig, day_id)
    ww = np.zeros((len(ts), 3))
    ww[:, 1] = w          # TQQQ
    ww[:, 2] = 1.0 - w    # BIL
    result = bt.simulate(ts, opens, closes, ww, band=0.02, slippage_bps=slippage_bps)
    return result, bt.stats(result, BARS_PER_YEAR)


def daily_metrics(result, stats, frame, closes, last, w_daily) -> dict:
    eq_day = result["equity"][last]
    tq_day = closes[last, 1]
    idx = pd.DatetimeIndex(frame["date"])
    rets = np.diff(eq_day) / eq_day[:-1]
    tq_rets = np.diff(tq_day) / tq_day[:-1]
    corr = float(np.corrcoef(rets, tq_rets)[0, 1]) if len(rets) > 2 else float("nan")

    eq_series = pd.Series(eq_day, index=idx)
    peak = eq_series.cummax()
    dd = eq_series / peak - 1.0
    trough = dd.idxmin()
    peak_date = eq_series.loc[:trough].idxmax()

    yearly = {}
    for year in range(2016, 2024):
        mask = np.asarray(idx.year == year)
        de = eq_day[mask]
        db = tq_day[mask]
        if len(de) < 2:
            continue
        yearly[int(year)] = {
            "strategy": float(de[-1] / de[0] - 1.0),
            "tqqq": float(db[-1] / db[0] - 1.0),
        }

    # Concentration and ex-2020 diagnostics (not selection criteria).
    daily_rets = np.r_[np.nan, rets]
    finite = np.isfinite(daily_rets)
    log_growth = float(np.log(eq_day[-1] / eq_day[0]))
    top10 = np.sort(daily_rets[finite])[-10:]
    top10_share = float(np.log1p(top10).sum() / log_growth) if log_growth > 0 else float("nan")
    non2020 = np.asarray(idx.year != 2020)
    mult_no2020 = float(np.prod(1.0 + daily_rets[non2020 & finite]))
    ex2020_cagr = mult_no2020 ** (1.0 / 7.0) - 1.0
    long_mask = np.asarray(w_daily) > 0.5
    entries = int(np.sum(long_mask[1:] & ~long_mask[:-1]))
    avg_hold = float(long_mask.sum() / entries) if entries else float(long_mask.sum())

    return {
        "cagr": float(stats["cagr"]),
        "total_return": float(stats["total_return"]),
        "max_drawdown": float(stats["max_drawdown"]),
        "sharpe": float(stats["sharpe"]),
        "sortino": float(stats["sortino"]),
        "volatility": float(stats["volatility"]),
        "ending_equity": float(stats["ending_equity"]),
        "fills": int(stats["fills"]),
        "bt_turnover_x_start_equity": float(stats["turnover"]),
        "exposure_tqqq": float(np.mean(np.clip(w_daily, 0.0, 1.0))),
        "long_days": int(long_mask.sum()),
        "entries": entries,
        "avg_holding_days": avg_hold,
        "corr_tqqq_daily": corr,
        "top10_log_growth_share": top10_share,
        "ex_2020_cagr_7y": float(ex2020_cagr),
        "max_dd_peak": str(peak_date.date()),
        "max_dd_trough": str(trough.date()),
        "yearly": yearly,
    }


def _serialise(obj):
    if isinstance(obj, dict):
        return {str(k): _serialise(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_serialise(v) for v in obj]
    if isinstance(obj, (np.floating, np.integer)):
        return obj.item()
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if isinstance(obj, (pd.Timestamp, dt.date)):
        return str(obj)
    return obj


# --------------------------------------------------------------------------- main
def main() -> None:
    ts, opens, closes, highs, lows, volumes = load_panel()
    frame = build_features(ts, opens, closes, highs, lows, volumes)
    dates = bt.session_dates(ts)
    first, last = bt.day_bounds_from_dates(dates)
    sig = last - 1
    day_id = bt.day_ids(ts)
    n_days = len(frame)

    print("data audit")
    print(f"  first bar {ts[0]}  last bar {ts[-1]}")
    print(f"  sessions {n_days}  bars {len(ts):,}  last feature date {frame['date'].iloc[-1].date()}")
    print("  features coverage:", frame[F6].notna().mean().round(3).to_dict())

    # ---------------------------------------------------------------- controls
    def eval_weights(w_daily, slip=1.0, vt=None):
        w_eff = np.clip(w_daily, 0.0, 1.0)
        if vt is not None:
            w_eff = w_eff * np.clip(vt, 0.0, 1.0)
        result, stats = simulate(w_eff, ts, opens, closes, sig, day_id, slip)
        return daily_metrics(result, stats, frame, closes, last, w_eff)

    tqqq_bh = eval_weights(np.ones(n_days))
    bil_bh = eval_weights(np.zeros(n_days))
    print("\ncontrols")
    for label, m in (("TQQQ buyhold", tqqq_bh), ("BIL buyhold", bil_bh)):
        print("  %-14s CAGR %6.2f%%  DD %5.2f%%  Sharpe %4.2f" % (
            label, m["cagr"] * 100, m["max_drawdown"] * 100, m["sharpe"]))

    # ---------------------------------------------------------------- fits
    print("\nfitting walk-forward models (expanding window, quarterly refit)")
    p6, b6, coef6 = walk_forward(frame, F6, "ridge", RIDGE_LAMBDA)
    p2, b2, coef2 = walk_forward(frame, F2, "ridge", RIDGE_LAMBDA)
    pl6, bl6, coefl6 = walk_forward(frame, F6, "logit", LOGIT_LAMBDA)
    print("  predicted days:", int(np.isfinite(p6).sum()),
          "first", frame.loc[np.isfinite(p6), "date"].iloc[0].date(),
          "last", frame.loc[np.isfinite(p6), "date"].iloc[-1].date())
    print("  mean ridge coefs (standardised):",
          {name: round(float(coef6[:, i].mean()), 4) for i, name in enumerate(F6)})

    # ---------------------------------------------------------------- 8 cells
    cells = [
        ("ridge6_50bp", "ridge", F6, 0.0050, p6, b6),
        ("ridge6_0bp", "ridge", F6, 0.0000, p6, b6),
        ("ridge6_10bp", "ridge", F6, 0.0010, p6, b6),
        ("ridge6_20bp", "ridge", F6, 0.0020, p6, b6),
        ("ridge6_30bp", "ridge", F6, 0.0030, p6, b6),
        ("ridge2_0bp", "ridge", F2, 0.0000, p2, b2),
        ("ridge2_10bp", "ridge", F2, 0.0010, p2, b2),
        ("logit6_58", "logit", F6, 0.5800, pl6, bl6),
    ]
    cell_results = []
    print("\npre-registered cells (1 bp / 5 bp)")
    for name, kind, feats, threshold, pred, base in cells:
        if kind == "ridge":
            w = (pred >= base + threshold).astype(float)
        else:
            w = (pred >= threshold).astype(float)
        m1 = eval_weights(w, 1.0)
        m5 = eval_weights(w, 5.0)
        row = {
            "cell": name,
            "model": kind,
            "features": feats,
            "threshold": threshold,
            "threshold_bp": threshold * 1e4 if kind == "ridge" else None,
            "metrics_1bp": m1,
            "metrics_5bp": m5,
        }
        if name == "ridge6_50bp":
            row["metrics_10bp"] = eval_weights(w, 10.0)
        cell_results.append(row)
        print("  %-13s 1bp CAGR %6.2f%% DD %5.2f%% Sh %4.2f wt %4.1f%% | "
              "5bp CAGR %6.2f%% DD %5.2f%% Sh %4.2f" % (
                  name, m1["cagr"] * 100, m1["max_drawdown"] * 100, m1["sharpe"],
                  m1["exposure_tqqq"] * 100, m5["cagr"] * 100,
                  m5["max_drawdown"] * 100, m5["sharpe"]))

    headline = cell_results[0]
    w_head = (p6 >= b6 + HEADLINE_THRESHOLD).astype(float)

    # ---------------------------------------------------------------- plateau
    print("\nthreshold plateau, ridge 6f (diagnostic)")
    plateau = []
    for bp in (0, 5, 10, 20, 30, 40, 50, 60, 75, 100):
        w = (p6 >= b6 + bp / 1e4).astype(float)
        m1 = eval_weights(w, 1.0)
        m5 = eval_weights(w, 5.0)
        plateau.append({"threshold_bp": bp, "metrics_1bp": m1, "metrics_5bp": m5})
        print("  %4dbp wt %4.1f%%  1bp CAGR %6.2f%% DD %5.2f%% Sh %4.2f | "
              "5bp CAGR %6.2f%% DD %5.2f%%" % (
                  bp, m1["exposure_tqqq"] * 100, m1["cagr"] * 100,
                  m1["max_drawdown"] * 100, m1["sharpe"],
                  m5["cagr"] * 100, m5["max_drawdown"] * 100))

    # ---------------------------------------------------------------- ablation
    print("\nfeature ablation at 50 bp")
    ablation = []
    subsets = [(f"drop_{drop}", [f for f in F6 if f != drop]) for drop in F6]
    subsets += [("only_clv_volr", F2), ("five_no_rng", F5),
                ("only_clv", ["clv"]), ("only_volr", ["volr"])]
    for name, feats in subsets:
        pred, base, _ = walk_forward(frame, feats, "ridge", RIDGE_LAMBDA)
        w = (pred >= base + HEADLINE_THRESHOLD).astype(float)
        m1 = eval_weights(w, 1.0)
        ablation.append({"variant": name, "features": feats, "metrics_1bp": m1})
        print("  %-16s CAGR %6.2f%% DD %5.2f%% Sh %4.2f wt %4.1f%%" % (
            name, m1["cagr"] * 100, m1["max_drawdown"] * 100,
            m1["sharpe"], m1["exposure_tqqq"] * 100))

    # ---------------------------------------------------------------- placebo
    print("\nshuffled-label placebo, 20 seeds (within-quarter training shuffle)")
    placebo = []
    for seed in range(PLACEBO_SEEDS):
        pred, base, _ = walk_forward(frame, F6, "ridge", RIDGE_LAMBDA,
                                     shuffle_seed=seed)
        w = (pred >= base + HEADLINE_THRESHOLD).astype(float)
        m1 = eval_weights(w, 1.0)
        placebo.append({"seed": seed, "cagr": m1["cagr"],
                        "max_drawdown": m1["max_drawdown"],
                        "sharpe": m1["sharpe"],
                        "exposure_tqqq": m1["exposure_tqqq"]})
        print("  seed %2d  CAGR %6.2f%%  DD %5.2f%%  Sh %4.2f  wt %4.1f%%" % (
            seed, m1["cagr"] * 100, m1["max_drawdown"] * 100,
            m1["sharpe"], m1["exposure_tqqq"] * 100))

    placebo_cagr = np.array([r["cagr"] for r in placebo])
    real_cagr = headline["metrics_1bp"]["cagr"]
    placebo_summary = {
        "seeds": PLACEBO_SEEDS,
        "mean_cagr": float(placebo_cagr.mean()),
        "sd_cagr": float(placebo_cagr.std(ddof=0)),
        "p5_cagr": float(np.percentile(placebo_cagr, 5)),
        "median_cagr": float(np.percentile(placebo_cagr, 50)),
        "p95_cagr": float(np.percentile(placebo_cagr, 95)),
        "real_cagr": float(real_cagr),
        "fraction_below_real": float(np.mean(placebo_cagr < real_cagr)),
        "runs": placebo,
    }
    print("  placebo mean %.2f%%  p5/p50/p95 %.2f/%.2f/%.2f%%  real percentile %.2f" % (
        placebo_summary["mean_cagr"] * 100, placebo_summary["p5_cagr"] * 100,
        placebo_summary["median_cagr"] * 100, placebo_summary["p95_cagr"] * 100,
        placebo_summary["fraction_below_real"]))

    # Exposure-matched placebo: force each shuffled model to be long on the
    # same fraction of *predicted* days as the real headline (top quantile).
    # The 2016 H1 burn-in has no predictions and stays in BIL for both.
    pred_days = np.isfinite(p6)
    target_frac_pred = float(np.sum((w_head > 0.5) & pred_days) / np.sum(pred_days))
    target_frac_overall = float(np.mean(w_head > 0.5))
    print("\nexposure-matched shuffled-label placebo (target %.1f%% of predicted days, "
          "%.1f%% overall)" % (target_frac_pred * 100, target_frac_overall * 100))
    placebo_matched = []
    for seed in range(PLACEBO_SEEDS):
        pred, base, _ = walk_forward(frame, F6, "ridge", RIDGE_LAMBDA,
                                     shuffle_seed=seed)
        excess = pred - base
        valid = np.isfinite(excess)
        threshold = float(np.quantile(excess[valid], 1.0 - target_frac_pred))
        w = (excess >= threshold).astype(float)
        m1 = eval_weights(w, 1.0)
        placebo_matched.append({"seed": seed, "cagr": m1["cagr"],
                                "max_drawdown": m1["max_drawdown"],
                                "sharpe": m1["sharpe"],
                                "exposure_tqqq": m1["exposure_tqqq"]})
    matched_cagr = np.array([r["cagr"] for r in placebo_matched])
    matched_summary = {
        "seeds": PLACEBO_SEEDS,
        "target_exposure_overall": target_frac_overall,
        "target_exposure_predicted_days": target_frac_pred,
        "realized_exposure": float(np.mean([r["exposure_tqqq"] for r in placebo_matched])),
        "mean_cagr": float(matched_cagr.mean()),
        "sd_cagr": float(matched_cagr.std(ddof=0)),
        "p5_cagr": float(np.percentile(matched_cagr, 5)),
        "median_cagr": float(np.percentile(matched_cagr, 50)),
        "p95_cagr": float(np.percentile(matched_cagr, 95)),
        "real_cagr": float(real_cagr),
        "fraction_below_real": float(np.mean(matched_cagr < real_cagr)),
        "runs": placebo_matched,
    }
    print("  matched placebo mean %.2f%%  p5/p50/p95 %.2f/%.2f/%.2f%%  real percentile %.2f" % (
        matched_summary["mean_cagr"] * 100, matched_summary["p5_cagr"] * 100,
        matched_summary["median_cagr"] * 100, matched_summary["p95_cagr"] * 100,
        matched_summary["fraction_below_real"]))

    # ---------------------------------------------------------------- vol target
    print("\nvol-target risk-control diagnostic (45% annualised)")
    entry = frame["entry"].to_numpy(float)
    log_ret = np.r_[np.nan, np.log(entry[1:] / entry[:-1])]
    sigma20 = pd.Series(log_ret).rolling(20, min_periods=15).std(ddof=0).to_numpy()
    sigma20 = pd.Series(sigma20 * np.sqrt(252)).shift(1).to_numpy()
    sigma20 = np.where(np.isfinite(sigma20), sigma20, np.nanmedian(sigma20))
    vt45 = np.clip(0.45 / np.maximum(sigma20, 1e-9), 0.0, 1.0)
    vt_metrics = eval_weights(w_head, 1.0, vt45)
    print("  headline x VT45   CAGR %6.2f%%  DD %5.2f%%  Sharpe %4.2f  wt %4.1f%%" % (
        vt_metrics["cagr"] * 100, vt_metrics["max_drawdown"] * 100,
        vt_metrics["sharpe"], float(np.mean(w_head * vt45)) * 100))

    # ---------------------------------------------------------------- headline detail
    print("\nheadline detail")
    print("  CAGR %.2f%%  DD %.2f%%  Sharpe %.2f  exposure %.1f%%  fills %d  corr %.3f" % (
        headline["metrics_1bp"]["cagr"] * 100,
        headline["metrics_1bp"]["max_drawdown"] * 100,
        headline["metrics_1bp"]["sharpe"],
        headline["metrics_1bp"]["exposure_tqqq"] * 100,
        headline["metrics_1bp"]["fills"],
        headline["metrics_1bp"]["corr_tqqq_daily"]))
    print("  yearly:")
    for year, row in headline["metrics_1bp"]["yearly"].items():
        print("    %s  strategy %+7.3f  tqqq %+7.3f" % (
            year, row["strategy"], row["tqqq"]))
    print("  max DD %s -> %s" % (
        headline["metrics_1bp"]["max_dd_peak"],
        headline["metrics_1bp"]["max_dd_trough"]))

    # ---------------------------------------------------------------- write json
    output = {
        "strategy": "family-ml-microstructure-b",
        "family": "ml-microstructure",
        "dev_window": {"start": DEV_START, "end": DEV_END},
        "data_audit": {
            "first_bar": str(ts[0]),
            "last_bar": str(ts[-1]),
            "sessions": int(n_days),
            "bars": int(len(ts)),
            "last_feature_date": str(frame["date"].iloc[-1].date()),
            "holdout_loaded": False,
            "parquet_filter": "ts < 2023-12-30T00:00Z; daily date <= 2023-12-29",
        },
        "bar": {"cagr": 0.3672, "max_drawdown": 0.8229, "sharpe": 0.82,
                "source": "programme bar; 1-minute panel"},
        "benchmark_tqqq": tqqq_bh,
        "benchmark_bil": bil_bh,
        "headline": headline,
        "headline_detail": {
            "mean_standardised_coefs": {
                name: float(coef6[:, i].mean()) for i, name in enumerate(F6)
            },
            "predicted_days": int(np.isfinite(p6).sum()),
            "long_days": int((w_head > 0.5).sum()),
            "mean_y_long_bps": float(np.nanmean(frame["y"].to_numpy()[w_head > 0.5]) * 1e4),
            "mean_y_all_bps": float(np.nanmean(frame["y"].to_numpy()) * 1e4),
            "vol_target_45": vt_metrics,
        },
        "cells": cell_results,
        "plateau": plateau,
        "ablation": ablation,
        "placebo": placebo_summary,
        "placebo_exposure_matched": matched_summary,
        "notes": [
            "Signals use QQQ bars through 15:58; fills at the 15:59 one-minute open.",
            "Target is the TQQQ 15:59-open to next 15:59-open return, the return actually captured.",
            "Ridge target is demeaned by the training mean; threshold is excess over that mean.",
            "Expanding window, quarterly refit, training-only scaling, 3-day purge.",
            "2016 H1 is BIL burn-in because at least 100 training rows are required.",
            "No 2024-2026 data is loaded or scored.",
        ],
    }
    with open(OUT_DIR / "result.json", "w", encoding="utf-8") as handle:
        json.dump(_serialise(output), handle, indent=2)
    print("\nwrote", OUT_DIR / "result.json")


if __name__ == "__main__":
    main()
