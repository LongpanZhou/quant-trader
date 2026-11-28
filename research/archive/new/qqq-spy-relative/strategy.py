"""QQQ/SPY relative-strength leverage ladder on TQQQ / QQQ / BIL.

Pre-registered design: see HYPOTHESIS.md.  Four risk states from a QQQ-vs-SPY
relative-momentum gate and QQQ's own slow trend, mapped to a 3x / 2x / 1x / 0x
Nasdaq exposure ladder:

    relative +   absolute +   TQQQ 1.00                  (3x)
    relative -   absolute +   TQQQ 0.50 + QQQ 0.50       (2x)
    relative +   absolute -   QQQ 1.00                   (1x)
    relative -   absolute -   BIL 1.00                   (0x)

The TQQQ sleeve is capped by 0.70 / rv20(TQQQ); freed weight goes to QQQ when
the absolute gate is on, else BIL.

Causality: the relative gate uses both legs through session k-1 because SPY's
official close (16:00) is one minute after the 15:59 decision bar; aligning both
legs through k-1 avoids a one-day endpoint mismatch.  The absolute gate and the
volatility cap use the 15:59 close at session k.  Targets are set at k's close
and filled at k+1's open by research/bt.py.  Long-only, weights >= 0, sum <= 1.

Run from the repo root:
    $env:PYTHONPATH = "C:/Users/27175/AppData/Local/Temp/opencode/pylibs"
    $env:BT_THREADS = "1"
    python research/new/qqq-spy-relative/strategy.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402

HERE = Path(__file__).resolve().parent
DATA = ROOT / "data" / "intraday-hf"
SPY_PATH = ROOT / "data" / "round3" / "yahoo" / "SPY-1d-yahoo.parquet"

START = "2016-01-04"
END = "2023-12-29"
DEV_END = pd.Timestamp("2023-12-29")
BAND = 0.02
BARS_PER_YEAR = 252 * 390
SYMS = ("QQQ", "TQQQ", "BIL")
BASIS = 0.3672          # TQQQ development CAGR bar
BASIS_DD = 0.60         # internal drawdown target (bar is 82.29%)
VOL_N = 20

GRID = {
    "A": dict(rel_lookback=126, sma=150, vol_cap=0.70, qqq_state_tqqq=0.50),
    "B": dict(rel_lookback=126, sma=150, vol_cap=0.60, qqq_state_tqqq=0.50),
    "C": dict(rel_lookback=126, sma=150, vol_cap=0.80, qqq_state_tqqq=0.50),
    "D": dict(rel_lookback=105, sma=150, vol_cap=0.70, qqq_state_tqqq=0.50),
    "E": dict(rel_lookback=147, sma=150, vol_cap=0.70, qqq_state_tqqq=0.50),
    "F": dict(rel_lookback=126, sma=180, vol_cap=0.70, qqq_state_tqqq=0.50),
    "G": dict(rel_lookback=126, sma=200, vol_cap=0.70, qqq_state_tqqq=0.50),
    "H": dict(rel_lookback=126, sma=150, vol_cap=None, qqq_state_tqqq=0.50),
}
PRIMARY = "A"


# ---------------------------------------------------------------------------
# data
# ---------------------------------------------------------------------------
def _yahoo_dev(symbol: str, last_date: pd.Timestamp) -> pd.Series:
    """Yahoo adjusted close, sliced at `last_date` inside the Parquet reader.

    Reading with a filter keeps the 2024-2026 holdout rows out of the process.
    """
    path = SPY_PATH if symbol == "SPY" else DATA / f"{symbol}-1d-yahoo.parquet"
    table = pq.read_table(
        path,
        filters=[("date", "<=", pd.Timestamp(last_date))],
        columns=["date", "adjclose"],
    )
    idx = pd.to_datetime(table["date"].to_pandas()).dt.normalize()
    s = pd.Series(np.asarray(table["adjclose"].to_numpy(), dtype=float), index=idx)
    s = s[~s.index.duplicated(keep="last")].sort_index()
    if s.empty:
        raise ValueError(f"no {symbol} daily data up to {last_date}")
    return s


def daily_frame(ts: pd.DatetimeIndex, closes: np.ndarray) -> pd.DataFrame:
    """Daily total-return levels aligned to the panel's session dates."""
    if len(ts) == 0:
        raise ValueError("empty panel")
    last_date = pd.Timestamp(ts[-1]).tz_localize(None).normalize()
    if last_date > DEV_END:
        raise ValueError(f"panel extends past the development window: {last_date}")

    dates, _, last = bt.day_bounds(ts)
    sess = pd.to_datetime(dates[last])
    panel = pd.DataFrame(closes[last], index=sess, columns=list(SYMS))

    levels = {}
    for symbol in SYMS:
        y = _yahoo_dev(symbol, last_date)
        p = panel[symbol]
        common = p.index.intersection(y.index)
        if len(common) == 0:
            raise ValueError(f"{symbol}: no overlap between panel and Yahoo")
        k = float(p.loc[common[0]] / y.loc[common[0]])
        pre = y[y.index < p.index[0]] * k
        levels[symbol] = pd.concat([pre, p]).sort_index()

    idx = levels["QQQ"].index
    spy = _yahoo_dev("SPY", last_date).reindex(idx).ffill()
    if spy.isna().any():
        raise ValueError("SPY daily series has gaps inside the QQQ calendar")

    daily = pd.DataFrame(
        {"QQQ": levels["QQQ"], "TQQQ": levels["TQQQ"], "BIL": levels["BIL"], "SPY": spy},
        index=idx,
    )
    if daily.isna().any().any():
        raise ValueError("daily signal frame contains NaN")
    if daily.index.min() > pd.Timestamp("2015-01-02"):
        raise ValueError("daily signal frame starts too late for warm-up")
    return daily


# ---------------------------------------------------------------------------
# signal
# ---------------------------------------------------------------------------
def _rebalance_flags(index: pd.DatetimeIndex, freq: str) -> np.ndarray:
    if freq == "D":
        return np.ones(len(index), dtype=bool)
    if freq == "W":
        iso = index.isocalendar()
        key = pd.Series(list(zip(iso["year"].to_numpy(), iso["week"].to_numpy())), index=index)
    elif freq == "M":
        key = pd.Series(index.to_period("M"), index=index)
    else:
        raise ValueError(f"unknown rebalance frequency: {freq}")
    flags = ~key.duplicated(keep="last").to_numpy()
    flags[0] = True
    return flags


def build_session_targets(daily: pd.DataFrame, params: dict):
    """Per-session targets decided at that session's close.

    `targets[k]` is the weight held during session k, i.e. it was decided at
    session k-1's close.  The target set at session k's close is `targets[k+1]`.
    """
    L = int(params["rel_lookback"])
    sma_n = int(params["sma"])
    p = float(params.get("qqq_state_tqqq", 0.50))
    vol_cap = params.get("vol_cap", 0.70)
    rel_in_bear = bool(params.get("rel_in_bear", True))
    qqq_lag = int(params.get("qqq_lag", 1))
    spy_lag = int(params.get("spy_lag", 1))
    freq = str(params.get("rebalance", "D"))
    rel_mode = str(params.get("rel_mode", "mom"))
    abs_mode = str(params.get("abs_mode", "sma"))
    abs_symbol = str(params.get("abs_symbol", "QQQ"))

    # Relative gate.  Positive qqq_lag = measure QQQ through k-1; spy_lag = 1
    # keeps SPY's 16:00 close out of the 15:59 decision.
    if rel_mode == "mom":
        rq = daily["QQQ"] / daily["QQQ"].shift(L) - 1.0
        rs = daily["SPY"] / daily["SPY"].shift(L) - 1.0
        rel = rq.shift(qqq_lag) > rs.shift(spy_lag)
    elif rel_mode == "ratio_sma":
        ratio = daily["QQQ"] / daily["SPY"]
        rel = ratio.shift(qqq_lag) > ratio.rolling(L, min_periods=L).mean().shift(qqq_lag)
    elif rel_mode == "always":
        rel = pd.Series(True, index=daily.index)
    else:
        raise ValueError(f"unknown rel_mode: {rel_mode}")
    rel = rel.fillna(False).astype(bool)

    # Absolute gate.  SPY is lagged because its official close is 16:00.
    abs_lag = 1 if abs_symbol == "SPY" else 0
    if abs_mode == "sma":
        sma = daily[abs_symbol].rolling(sma_n, min_periods=sma_n).mean()
        ab = (daily[abs_symbol].shift(abs_lag) > sma.shift(abs_lag))
    elif abs_mode == "mom":
        aq = daily[abs_symbol] / daily[abs_symbol].shift(sma_n) - 1.0
        abil = daily["BIL"] / daily["BIL"].shift(sma_n) - 1.0
        ab = (aq.shift(abs_lag) > abil.shift(abs_lag))
    elif abs_mode == "always":
        ab = pd.Series(True, index=daily.index)
    else:
        raise ValueError(f"unknown abs_mode: {abs_mode}")
    ab = ab.fillna(False).astype(bool)

    rets = daily[["QQQ", "TQQQ", "BIL"]].pct_change()
    rv = rets["TQQQ"].rolling(VOL_N, min_periods=VOL_N).std() * np.sqrt(252.0)

    # Desired weights at session k's close.
    desired = np.zeros((len(daily), 3), dtype=float)
    qqq = np.zeros(len(daily))
    tqqq = np.zeros(len(daily))
    bil = np.zeros(len(daily))
    tqqq[rel.to_numpy() & ab.to_numpy()] = 1.0
    if rel_in_bear:
        qqq[rel.to_numpy() & ~ab.to_numpy()] = 1.0
    else:
        bil[~ab.to_numpy()] = 1.0
    tqqq[~rel.to_numpy() & ab.to_numpy()] = p
    qqq[~rel.to_numpy() & ab.to_numpy()] = 1.0 - p
    if rel_in_bear:
        bil[~rel.to_numpy() & ~ab.to_numpy()] = 1.0

    if vol_cap is not None:
        scale = np.clip(float(vol_cap) / rv.to_numpy(), 0.0, 1.0)
        scale = np.where(np.isfinite(scale), scale, 0.0)
        raw_tq = tqqq.copy()
        tqqq = raw_tq * scale
        freed = raw_tq - tqqq
        qqq = qqq + np.where(ab.to_numpy(), freed, 0.0)
        bil = bil + np.where(ab.to_numpy(), 0.0, freed)
    raw_tqqq = tqqq.copy()

    desired[:, 0] = qqq
    desired[:, 1] = tqqq
    desired[:, 2] = bil
    if desired.min() < -1e-12 or desired.sum(axis=1).max() > 1.0 + 1e-9:
        raise ValueError("desired weights violate long-only / sum <= 1")

    flags = _rebalance_flags(daily.index, freq)
    targets = np.zeros((len(daily), 3), dtype=float)
    targets[0] = (0.0, 0.0, 1.0)
    for k in range(1, len(daily)):
        targets[k] = desired[k - 1] if flags[k - 1] else targets[k - 1]

    state = np.where(rel.to_numpy() & ab.to_numpy(), 3,
                     np.where(~rel.to_numpy() & ab.to_numpy(), 2,
                              np.where(rel.to_numpy() & ~ab.to_numpy(), 1, 0)))
    info = dict(
        state=state,
        desired=desired,
        targets=targets,
        flags=flags,
        rel=rel.to_numpy(),
        ab=ab.to_numpy(),
        rv_tqqq=rv.to_numpy(),
        w_tqqq_raw=raw_tqqq,
        daily_index=daily.index,
    )
    return targets, info


def expand_to_bars(ts: pd.DatetimeIndex, targets: np.ndarray) -> np.ndarray:
    """Map per-session targets to the engine's bar convention.

    `weights[i]` is set at bar i's close and fills at bar i+1's open.  For each
    session k, bars before the last carry targets[k]; the last bar carries
    targets[k+1], which is the decision made at k's close.
    """
    dates, first, last = bt.day_bounds(ts)
    n = len(ts)
    d = len(first)
    if len(targets) != d:
        raise ValueError("targets must have one row per session")
    w = np.empty((n, 3), dtype=float)
    for k in range(d):
        f = int(first[k])
        l = int(last[k])
        w[f:l] = targets[k]
        w[l] = targets[k + 1] if k + 1 < d else targets[k]
    if not np.isfinite(w).all():
        raise ValueError("weights contain non-finite values")
    if w.min() < -1e-12 or w.sum(axis=1).max() > 1.0 + 1e-9:
        raise ValueError("weights violate long-only / sum <= 1")
    return w


def weights_from_daily(ts: pd.DatetimeIndex, daily: pd.DataFrame, params: dict):
    targets, info = build_session_targets(daily, params)
    dates, _, last = bt.day_bounds(ts)
    sess = pd.to_datetime(dates[last])
    pos = daily.index.get_indexer(sess)
    if (pos < 0).any():
        raise ValueError("panel session date missing from daily signal frame")
    targets = targets[pos]
    for key, value in list(info.items()):
        if isinstance(value, np.ndarray) and value.ndim == 1 and len(value) == len(daily):
            info[key] = value[pos]
    info["targets"] = targets
    info["daily_index"] = daily.index[pos]
    return expand_to_bars(ts, targets), info


def build_weights(ts: pd.DatetimeIndex, o: np.ndarray, c: np.ndarray, params: dict | None = None):
    """Public interface: build the bar-level weight matrix from the panel."""
    p = dict(GRID[PRIMARY]) if params is None else dict(params)
    daily = daily_frame(ts, c)
    return weights_from_daily(ts, daily, p)


# ---------------------------------------------------------------------------
# evaluation helpers
# ---------------------------------------------------------------------------
def _sliced_stats(result: dict, start: str, end: str) -> dict:
    ts = result["ts"]
    t0 = pd.Timestamp(start, tz="America/New_York")
    t1 = pd.Timestamp(end, tz="America/New_York")
    i0 = int(ts.searchsorted(t0))
    i1 = int(ts.searchsorted(t1 + pd.Timedelta(days=1)))
    if i0 > 0:
        i0 -= 1
    sub = {
        "ts": ts[i0:i1],
        "equity": result["equity"][i0:i1],
        "cash": result["cash"][i0:i1],
        "fills": result["fills"],
        "turnover": result["turnover"],
    }
    return bt.stats(sub, BARS_PER_YEAR)


def _daily_returns(ts: pd.DatetimeIndex, values: np.ndarray) -> pd.Series:
    return bt.daily_last(values, ts).pct_change().dropna()


def _corr(a: pd.Series, b: pd.Series) -> float:
    j = pd.concat([a, b], axis=1, join="inner").dropna()
    if len(j) < 10:
        return float("nan")
    return float(j.iloc[:, 0].corr(j.iloc[:, 1]))


def _beta(a: pd.Series, b: pd.Series) -> float:
    j = pd.concat([a, b], axis=1, join="inner").dropna()
    if len(j) < 10:
        return float("nan")
    var = float(j.iloc[:, 1].var(ddof=0))
    if var <= 0:
        return float("nan")
    return float(j.iloc[:, 0].cov(j.iloc[:, 1], ddof=0) / var)


def _yearly(result: dict, bench: np.ndarray) -> dict:
    eq = bt.daily_last(result["equity"], result["ts"])
    bq = bt.daily_last(bench, result["ts"])
    out = {}
    for year in range(2016, 2024):
        e_this = eq[eq.index.year == year]
        b_this = bq[bq.index.year == year]
        if len(e_this) == 0:
            continue
        e_prev = eq[eq.index.year < year]
        b_prev = bq[bq.index.year < year]
        e0 = e_prev.iloc[-1] if len(e_prev) else e_this.iloc[0]
        b0 = b_prev.iloc[-1] if len(b_prev) else b_this.iloc[0]
        out[str(year)] = {
            "strategy": float(e_this.iloc[-1] / e0 - 1.0),
            "tqqq": float(b_this.iloc[-1] / b0 - 1.0),
        }
    return out


def _summary(result: dict, bench_tqqq: np.ndarray, bench_qqq: np.ndarray) -> dict:
    s = bt.stats(result, BARS_PER_YEAR)
    ret_s = _daily_returns(result["ts"], result["equity"])
    ret_t = _daily_returns(result["ts"], bench_tqqq)
    ret_q = _daily_returns(result["ts"], bench_qqq)
    eq = result["equity"]
    peak = np.maximum.accumulate(eq)
    dd = eq / peak - 1.0
    trough_i = int(np.argmin(dd))
    peak_i = int(np.argmax(eq[: trough_i + 1]))
    # Recovery after the trough.
    after = eq[trough_i:]
    rec_i = int(np.argmax(after >= peak[trough_i])) if len(after) else 0
    recovered = bool(after[rec_i] >= peak[trough_i]) if len(after) else False
    return {
        "cagr": float(s["cagr"]),
        "max_drawdown": float(s["max_drawdown"]),
        "max_drawdown_peak": str(result["ts"][peak_i]),
        "max_drawdown_trough": str(result["ts"][trough_i]),
        "max_drawdown_days": float(
            (result["ts"][trough_i] - result["ts"][peak_i]).total_seconds() / 86400.0
        ),
        "max_drawdown_recovered": recovered,
        "max_drawdown_recovery_date": str(result["ts"][trough_i + rec_i]) if recovered else None,
        "sharpe": float(s["sharpe"]),
        "sortino": float(s["sortino"]),
        "volatility": float(s["volatility"]),
        "exposure_invested": float(s["exposure"]),
        "fills": int(s["fills"]),
        "turnover": float(s["turnover"]),
        "turnover_per_year": float(s["turnover"] / s["years"]),
        "corr_tqqq_daily": _corr(ret_s, ret_t),
        "corr_qqq_daily": _corr(ret_s, ret_q),
        "beta_tqqq_daily": _beta(ret_s, ret_t),
        "beta_qqq_daily": _beta(ret_s, ret_q),
        "years": float(s["years"]),
        "ending_equity": float(s["ending_equity"]),
    }


def _avg_weights(targets: np.ndarray) -> dict:
    a = targets.mean(axis=0)
    return {
        "QQQ": float(a[0]),
        "TQQQ": float(a[1]),
        "BIL": float(a[2]),
        "risky": float(a[0] + a[1]),
        "effective_nasdaq_beta": float(a[0] + 3.0 * a[1]),
    }


def _state_share(state: np.ndarray) -> dict:
    return {
        "both_positive_tqqq": float(np.mean(state == 3)),
        "absolute_only_2x": float(np.mean(state == 2)),
        "relative_only_qqq": float(np.mean(state == 1)),
        "neither_bil": float(np.mean(state == 0)),
        "switches": int(np.sum(state[1:] != state[:-1])),
    }


def _updown_capture(ret_s: pd.Series, ret_b: pd.Series) -> dict:
    j = pd.concat([ret_s, ret_b], axis=1, join="inner").dropna()
    j.columns = ["s", "b"]
    up = j[j["b"] > 0]
    dn = j[j["b"] < 0]
    return {
        "up_capture": float(up["s"].mean() / up["b"].mean()) if len(up) else float("nan"),
        "down_capture": float(dn["s"].mean() / dn["b"].mean()) if len(dn) else float("nan"),
        "up_days": int(len(up)),
        "down_days": int(len(dn)),
    }


# ---------------------------------------------------------------------------
# robustness
# ---------------------------------------------------------------------------
def _cut_test(ts, o, c, params: dict, w_full: np.ndarray, cut: str) -> dict:
    cut_ts = pd.Timestamp(cut, tz="America/New_York")
    i = int(ts.searchsorted(cut_ts))
    if i >= len(ts):
        raise ValueError(f"cut {cut} is outside the panel")
    w_cut, _ = build_weights(ts[: i + 1], o[: i + 1], c[: i + 1], params)
    diff = float(np.abs(w_full[: i + 1] - w_cut).max())
    return {
        "cut": cut,
        "bars_checked": int(i + 1),
        "max_abs_weight_diff": diff,
        "pass": bool(diff <= 1e-12),
    }


def _placebo(ts, o, c, targets: np.ndarray, n_draws: int = 200, seed: int = 20261127) -> dict:
    """Circularly shift the per-session target sequence.

    This preserves the exact state sequence, exposure distribution, vol cap and
    turnover, but destroys its alignment with market returns.
    """
    d = len(targets)
    rng = np.random.default_rng(seed)
    cagrs = []
    dds = []
    sharpes = []
    for _ in range(n_draws):
        shift = int(rng.integers(20, d - 20))
        shifted = np.roll(targets, shift, axis=0)
        w = expand_to_bars(ts, shifted)
        res = bt.run(ts, o, c, w, start=START, band=BAND, slippage_bps=1.0)
        s = bt.stats(res, BARS_PER_YEAR)
        cagrs.append(float(s["cagr"]))
        dds.append(float(s["max_drawdown"]))
        sharpes.append(float(s["sharpe"]))
    cagrs = np.asarray(cagrs)
    dds = np.asarray(dds)
    sharpes = np.asarray(sharpes)
    return {
        "draws": n_draws,
        "seed": seed,
        "cagr_median": float(np.median(cagrs)),
        "cagr_p05": float(np.percentile(cagrs, 5)),
        "cagr_p95": float(np.percentile(cagrs, 95)),
        "max_drawdown_median": float(np.median(dds)),
        "max_drawdown_p05": float(np.percentile(dds, 5)),
        "max_drawdown_p95": float(np.percentile(dds, 95)),
        "sharpe_median": float(np.median(sharpes)),
        "cagrs": cagrs.tolist(),
        "max_drawdowns": dds.tolist(),
    }


def _static_blend(ts, o, c, avg: dict) -> dict:
    w_asset = np.array([avg["QQQ"], avg["TQQQ"], avg["BIL"]], dtype=float)
    w = np.tile(w_asset, (len(ts), 1))
    res = bt.run(ts, o, c, w, start=START, band=BAND, slippage_bps=1.0)
    return res


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
def main() -> None:
    ts, o, c = bt.panel(SYMS, START, END, "1min", warmup_days=0)
    if pd.Timestamp(ts[-1]).tz_localize(None).normalize() > DEV_END:
        raise RuntimeError("panel extends past the development window")
    daily = daily_frame(ts, c)

    bench_tqqq = c[:, 1]
    bench_qqq = c[:, 0]

    grid_out = {}
    primary_w = None
    primary_info = None
    primary_res = None
    for vid, params in GRID.items():
        w, info = weights_from_daily(ts, daily, params)
        entry = {"params": dict(params)}
        for slip in (1.0, 5.0, 10.0):
            res = bt.run(ts, o, c, w, start=START, band=BAND, slippage_bps=slip)
            entry[f"{int(slip)}bp"] = _summary(res, bench_tqqq, bench_qqq)
            if vid == PRIMARY and slip == 1.0:
                primary_w = w
                primary_info = info
                primary_res = res
        grid_out[vid] = entry

    prim = grid_out[PRIMARY]["1bp"]

    # Benchmarks on the same dev window.
    i0 = bt.start_index(ts, START)
    b_tqqq = bt.benchmark(bench_tqqq[i0:], ts[i0:], BARS_PER_YEAR)
    b_qqq = bt.benchmark(bench_qqq[i0:], ts[i0:], BARS_PER_YEAR)
    spy = _yahoo_dev("SPY", DEV_END)
    spy = spy[(spy.index >= pd.Timestamp(START)) & (spy.index <= DEV_END)]
    spy_ts = pd.DatetimeIndex(spy.index).tz_localize("America/New_York")
    b_spy = bt.benchmark(spy.to_numpy(), spy_ts, 252.0)

    ret_s = _daily_returns(primary_res["ts"], primary_res["equity"])
    ret_t = _daily_returns(primary_res["ts"], bench_tqqq)
    ret_q = _daily_returns(primary_res["ts"], bench_qqq)
    corr_t = _corr(ret_s, ret_t)
    corr_q = _corr(ret_s, ret_q)
    beta_t = _beta(ret_s, ret_t)
    beta_q = _beta(ret_s, ret_q)
    updown = _updown_capture(ret_s, ret_t)

    yearly = _yearly(primary_res, bench_tqqq)
    q_daily = bt.daily_last(bench_qqq, primary_res["ts"])
    for year, row in yearly.items():
        qy = q_daily[q_daily.index.year == int(year)]
        qprev = q_daily[q_daily.index.year < int(year)]
        q0 = qprev.iloc[-1] if len(qprev) else qy.iloc[0]
        row["qqq"] = float(qy.iloc[-1] / q0 - 1.0)

    sub = {}
    for name, (a, b) in {
        "2016-2019": ("2016-01-04", "2019-12-31"),
        "2020-2021": ("2020-01-02", "2021-12-31"),
        "2022-2023": ("2022-01-03", "2023-12-29"),
    }.items():
        ss = _sliced_stats(primary_res, a, b)
        t0 = pd.Timestamp(a, tz="America/New_York")
        t1 = pd.Timestamp(b, tz="America/New_York")
        j0 = int(primary_res["ts"].searchsorted(t0))
        j1 = int(primary_res["ts"].searchsorted(t1 + pd.Timedelta(days=1)))
        bs = bt.benchmark(bench_tqqq[j0:j1], primary_res["ts"][j0:j1], BARS_PER_YEAR)
        sub[name] = {
            "strategy": {
                "cagr": float(ss["cagr"]),
                "max_drawdown": float(ss["max_drawdown"]),
                "sharpe": float(ss["sharpe"]),
                "exposure_invested": float(ss["exposure"]),
            },
            "tqqq": {
                "cagr": float(bs["cagr"]),
                "max_drawdown": float(bs["max_drawdown"]),
                "sharpe": float(bs["sharpe"]),
            },
        }

    # Static blend at the strategy's own average weights.
    avg_w = _avg_weights(primary_info["targets"])
    static_res = _static_blend(ts, o, c, avg_w)
    static_stats = _summary(static_res, bench_tqqq, bench_qqq)

    # Ablations.  All 1 bp, same panel.
    ablations = {}
    abl_specs = {
        "no_vol_cap": dict(rel_lookback=126, sma=150, vol_cap=None, qqq_state_tqqq=0.50),
        "qqq_state_full_qqq_p0": dict(rel_lookback=126, sma=150, vol_cap=0.70, qqq_state_tqqq=0.00),
        "qqq_state_full_tqqq_p1": dict(rel_lookback=126, sma=150, vol_cap=0.70, qqq_state_tqqq=1.00),
        "absolute_only_rel_always": dict(rel_lookback=126, sma=150, vol_cap=0.70,
                                         qqq_state_tqqq=0.50, rel_mode="always"),
        "relative_only_abs_always": dict(rel_lookback=126, sma=150, vol_cap=0.70,
                                         qqq_state_tqqq=0.50, abs_mode="always"),
        "drop_1x_rung_all_bear_to_bil": dict(rel_lookback=126, sma=150, vol_cap=0.70,
                                             qqq_state_tqqq=0.50, rel_in_bear=False),
        "weekly_rebalance": dict(rel_lookback=126, sma=150, vol_cap=0.70,
                                 qqq_state_tqqq=0.50, rebalance="W"),
        "relative_gate_qqq_fresh_spy_lagged": dict(rel_lookback=126, sma=150,
                                                   vol_cap=0.70, qqq_state_tqqq=0.50,
                                                   qqq_lag=0, spy_lag=1),
        "relative_gate_same_day_one_minute_lookahead": dict(
            rel_lookback=126, sma=150, vol_cap=0.70, qqq_state_tqqq=0.50,
            qqq_lag=0, spy_lag=0,
        ),
        "relative_gate_one_session_lookahead_diagnostic": dict(
            rel_lookback=126, sma=150, vol_cap=0.70, qqq_state_tqqq=0.50,
            qqq_lag=-1, spy_lag=1,
        ),
        "relative_strength_ratio_vs_sma": dict(rel_lookback=126, sma=150, vol_cap=0.70,
                                               qqq_state_tqqq=0.50, rel_mode="ratio_sma"),
        "absolute_momentum_126_vs_bil": dict(rel_lookback=126, sma=126, vol_cap=0.70,
                                             qqq_state_tqqq=0.50, abs_mode="mom"),
        "absolute_trend_on_spy_150": dict(rel_lookback=126, sma=150, vol_cap=0.70,
                                          qqq_state_tqqq=0.50, abs_symbol="SPY"),
    }
    for name, params in abl_specs.items():
        w, _ = weights_from_daily(ts, daily, params)
        res = bt.run(ts, o, c, w, start=START, band=BAND, slippage_bps=1.0)
        ablations[name] = {"params": params, **_summary(res, bench_tqqq, bench_qqq)}

    # Neighbour table: descriptive, not candidates for substitution.
    neighbours = {}
    neigh_specs = {}
    for L in (63, 84, 105, 147, 189, 252):
        neigh_specs[f"rel_{L}"] = dict(rel_lookback=L, sma=150, vol_cap=0.70, qqq_state_tqqq=0.50)
    for sma_n in (120, 140, 160, 180, 200):
        neigh_specs[f"sma_{sma_n}"] = dict(rel_lookback=126, sma=sma_n, vol_cap=0.70,
                                           qqq_state_tqqq=0.50)
    for vc in (0.55, 0.60, 0.80, None):
        key = f"volcap_{vc}" if vc is not None else "volcap_none"
        neigh_specs[key] = dict(rel_lookback=126, sma=150, vol_cap=vc, qqq_state_tqqq=0.50)
    for p in (0.40, 0.60):
        neigh_specs[f"p_{p:.2f}"] = dict(rel_lookback=126, sma=150, vol_cap=0.70,
                                         qqq_state_tqqq=p)
    for name, params in neigh_specs.items():
        w, _ = weights_from_daily(ts, daily, params)
        res = bt.run(ts, o, c, w, start=START, band=BAND, slippage_bps=1.0)
        neighbours[name] = {"params": params, **_summary(res, bench_tqqq, bench_qqq)}

    placebo = _placebo(ts, o, c, primary_info["targets"], n_draws=200)
    placebo["share_beating_strategy"] = float(
        np.mean(np.asarray(placebo["cagrs"]) >= prim["cagr"])
    )
    placebo.pop("cagrs", None)
    placebo.pop("max_drawdowns", None)

    cuts = [
        _cut_test(ts, o, c, GRID[PRIMARY], primary_w, "2020-03-12 11:07"),
        _cut_test(ts, o, c, GRID[PRIMARY], primary_w, "2022-09-13 10:41"),
    ]

    # Leave-one-year-out and replace-one-year-with-TQQQ.
    yy = sorted(yearly)
    s_rets = np.array([yearly[y]["strategy"] for y in yy])
    t_rets = np.array([yearly[y]["tqqq"] for y in yy])
    years_total = float(prim["years"])

    loo = {}
    replace_year = {}
    for i, y in enumerate(yy):
        keep = np.ones(len(yy), dtype=bool)
        keep[i] = False
        loo[y] = float(np.prod(1.0 + s_rets[keep]) ** (1.0 / (len(yy) - 1)) - 1.0)
        r = s_rets.copy()
        r[i] = t_rets[i]
        replace_year[y] = float(np.prod(1.0 + r) ** (1.0 / years_total) - 1.0)

    # Falsifiers fixed in HYPOTHESIS.md.
    pass_cells = [
        v for v, e in grid_out.items()
        if e["1bp"]["cagr"] > BASIS and e["1bp"]["max_drawdown"] < BASIS_DD
    ]
    abs_only_sharpe = ablations["absolute_only_rel_always"]["sharpe"]
    falsifiers = {
        "headline_cagr": bool(prim["cagr"] > BASIS),
        "headline_drawdown_below_60": bool(prim["max_drawdown"] < BASIS_DD),
        "plateau_5_of_8": bool(len(pass_cells) >= 5),
        "cost_10bp": bool(grid_out[PRIMARY]["10bp"]["cagr"] > BASIS),
        "placebo_at_most_10pct": bool(placebo["share_beating_strategy"] <= 0.10),
        "cut_test": bool(all(x["pass"] for x in cuts)),
        "relative_gate_adds_sharpe_0.02": bool(prim["sharpe"] >= abs_only_sharpe + 0.02),
        "loo_5_of_7": bool(sum(v > BASIS for v in loo.values()) >= 5),
    }
    robustness_failures = [k for k, ok in falsifiers.items() if not ok]
    robustness_status = "fragile" if robustness_failures else "robust"

    passed = bool(
        falsifiers["headline_cagr"]
        and falsifiers["headline_drawdown_below_60"]
        and falsifiers["plateau_5_of_8"]
    )

    out = {
        "agent": "qqq-spy-relative",
        "status": "passed" if passed else "negative_result",
        "exploratory": True,
        "exploratory_reason": (
            "The state family and grid centre were chosen after daily-bar "
            "diagnostics on the development window. The pre-registered grid "
            "is a plateau probe, not a clean out-of-sample design."
        ),
        "hypothesis": (
            "A four-state leverage ladder driven by QQQ-vs-SPY relative "
            "momentum and QQQ's own 150-session trend, with a 70% TQQQ "
            "volatility cap, should beat TQQQ's 36.72% development CAGR with "
            "a materially lower drawdown."
        ),
        "universe": ["QQQ", "TQQQ", "BIL", "SPY (signal only, never held)"],
        "window": {"start": START, "end": END, "marks": "1m"},
        "primary": {
            "id": PRIMARY,
            "params": GRID[PRIMARY],
            "dev": {
                "1bp": grid_out[PRIMARY]["1bp"],
                "5bp": grid_out[PRIMARY]["5bp"],
                "10bp": grid_out[PRIMARY]["10bp"],
            },
        },
        "passed": passed,
        "headline_pass": passed,
        "robustness_status": robustness_status,
        "robustness_failures": robustness_failures,
        "falsifiers": falsifiers,
        "passing_cells": pass_cells,
        "grid": grid_out,
        "benchmarks": {
            "tqqq": {k: float(v) for k, v in b_tqqq.items()},
            "qqq": {k: float(v) for k, v in b_qqq.items()},
            "spy_daily": {k: float(v) for k, v in b_spy.items()},
            "spy_note": "daily close marks only; no SPY 1-minute history for dev",
        },
        "corr_tqqq_daily": corr_t,
        "corr_qqq_daily": corr_q,
        "beta_tqqq_daily": beta_t,
        "beta_qqq_daily": beta_q,
        "updown_capture_vs_tqqq": updown,
        "yearly": yearly,
        "subperiods": sub,
        "avg_target_weights": avg_w,
        "risky_exposure": avg_w["risky"],
        "state_session_share": _state_share(primary_info["state"]),
        "static_blend_same_avg": static_stats,
        "ablations": ablations,
        "neighbours": neighbours,
        "placebo": placebo,
        "cut_tests": cuts,
        "leave_one_year_out": loo,
        "year_concentration": {
            "replace_year_with_tqqq_cagr": replace_year,
            "note": (
                "Replace one year's strategy return with TQQQ's and recompute "
                "the 8-year CAGR; shows one-year dependence."
            ),
        },
        "variants_tried": len(GRID) + len(abl_specs) + len(neigh_specs) + 1,
        "notes": [
            "SPY is a signal only: no SPY 1-minute history exists for 2016-2023.",
            "The relative gate measures both QQQ and SPY through session k-1 so "
            "the windows are aligned and SPY's 16:00 close is not anticipated.",
            "The absolute gate and the TQQQ vol cap use the 15:59 close at k.",
            "The holdout (2024-2026) was physically filtered out of the SPY and "
            "daily Parquet reads; the panel is hard-sliced at 2023-12-29.",
            "Equity is marked on every 1-minute bar; costs 1/5/10 bp.",
            "The strategy is a leverage ladder (3x/2x/1x/0x), not a "
            "market-neutral spread. Its relative gate is highly correlated "
            "with Nasdaq beta; see the ablations and static blend.",
        ],
    }

    with open(HERE / "result.json", "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, indent=2, allow_nan=False)

    print(f"primary {PRIMARY} {GRID[PRIMARY]}")
    print(
        f"  dev 1bp: CAGR {prim['cagr']*100:.2f}%  DD {prim['max_drawdown']*100:.2f}%  "
        f"Sharpe {prim['sharpe']:.2f}  exposure {prim['exposure_invested']*100:.1f}%  "
        f"corr(TQQQ) {corr_t:.2f}  beta {beta_t:.2f}"
    )
    print(f"  avg weights: {avg_w}")
    print(f"  status: {out['status']}  passing cells: {pass_cells}")
    print(f"  robustness: {robustness_status}  failures: {robustness_failures}")
    print(f"  placebo share beating: {placebo['share_beating_strategy']:.3f}")
    print("grid 1bp:")
    for vid, e in grid_out.items():
        s = e["1bp"]
        print(
            f"  {vid}: rel{e['params']['rel_lookback']}/sma{e['params']['sma']}/"
            f"vc{e['params']['vol_cap']}  CAGR {s['cagr']*100:6.2f}%  "
            f"DD {s['max_drawdown']*100:5.2f}%  Sharpe {s['sharpe']:.2f}  "
            f"exp {s['exposure_invested']*100:.1f}%  corr {s['corr_tqqq_daily']:.2f}"
        )
    print(f"wrote {HERE / 'result.json'}")


if __name__ == "__main__":
    main()
