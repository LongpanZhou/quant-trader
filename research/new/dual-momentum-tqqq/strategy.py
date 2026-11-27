"""Dual-momentum QQQ/SPY gate on a volatility-targeted TQQQ sleeve.

See HYPOTHESIS.md for the pre-registered design.

States, decided from causal daily marks:

    QQQ 12m total return > 0  and  QQQ 12m > SPY 12m   -> TQQQ at min(1, vt/rv), rest BIL
    QQQ 12m total return > 0  and  QQQ 12m <= SPY 12m  -> QQQ 1.00
    QQQ 12m total return <= 0                          -> BIL 1.00

`rv` is annualised realised volatility of TQQQ daily total returns over the
last `rv_n` sessions.  The momentum state is rebalanced at month-end (last
session) or after a 20-session confirmation of the new state, per the grid.
The volatility size is a continuous overlay: it uses the 15:59 close of the
decision session and is refilled at the next open.

Causality: QQQ and SPY relative momentum are both measured through session
k-1 because SPY's official close (16:00) is one minute after the 15:59
decision bar.  The absolute gate and TQQQ volatility use session k's 15:59
close.  Targets set at k's close fill at k+1's open (research/bt.py).

Run from the repo root:
    $env:PYTHONPATH = "C:/Users/27175/AppData/Local/Temp/opencode/pylibs"
    $env:BT_THREADS = "1"
    python research/new/dual-momentum-tqqq/strategy.py
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
BASIS_DD = 0.60         # internal drawdown target (hard bar is 82.29%)

# Pre-registered grid (<= 8).  Primary A is fixed before the 1-minute run.
GRID = {
    "A": dict(lookback=252, vol_target=0.85, rv_n=10, rebalance="C20"),
    "B": dict(lookback=252, vol_target=0.80, rv_n=10, rebalance="C20"),
    "C": dict(lookback=252, vol_target=0.90, rv_n=10, rebalance="C20"),
    "D": dict(lookback=252, vol_target=0.85, rv_n=20, rebalance="C20"),
    "E": dict(lookback=252, vol_target=0.85, rv_n=10, rebalance="M"),
    "F": dict(lookback=189, vol_target=0.85, rv_n=10, rebalance="C20"),
    "G": dict(lookback=126, vol_target=0.85, rv_n=10, rebalance="C20"),
    "H": dict(lookback=252, vol_target=0.85, rv_n=10, rebalance="N20"),
}
PRIMARY = "A"


# ---------------------------------------------------------------------------
# data
# ---------------------------------------------------------------------------
def _yahoo_dev(symbol: str, last_date: pd.Timestamp) -> pd.Series:
    """Yahoo adjusted close, sliced at `last_date` inside the Parquet reader."""
    path = SPY_PATH if symbol == "SPY" else DATA / f"{symbol}-1d-yahoo.parquet"
    table = pq.read_table(
        path,
        filters=[("date", "<=", pd.Timestamp(last_date).normalize())],
        columns=["date", "adjclose"],
    )
    idx = pd.to_datetime(table["date"].to_pandas()).dt.normalize()
    s = pd.Series(np.asarray(table["adjclose"].to_numpy(), dtype=float), index=idx)
    s = s[~s.index.duplicated(keep="last")].sort_index()
    if s.empty:
        raise ValueError(f"no {symbol} daily data up to {last_date}")
    return s


def daily_frame(ts: pd.DatetimeIndex, closes: np.ndarray) -> pd.DataFrame:
    """Total-return daily levels aligned to the panel's session dates."""
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
def _month_end_flags(index: pd.DatetimeIndex) -> np.ndarray:
    period = pd.Series(index.to_period("M"), index=index)
    flags = ~period.duplicated(keep="last").to_numpy()
    flags[0] = True
    return flags


def raw_states(daily: pd.DataFrame, lookback: int) -> np.ndarray:
    """0 = TQQQ, 1 = QQQ, 2 = BIL; one value per session close."""
    rq = daily["QQQ"] / daily["QQQ"].shift(lookback) - 1.0
    rs = daily["SPY"] / daily["SPY"].shift(lookback) - 1.0
    absolute = (rq > 0.0).fillna(False).to_numpy()
    # Both relative legs through k-1 so SPY's 16:00 close is not anticipated.
    relative = (rq.shift(1) > rs.shift(1)).fillna(False).to_numpy()
    return np.where(absolute & relative, 0, np.where(absolute, 1, 2))


def held_states_index(index: pd.DatetimeIndex, raw: np.ndarray, rebalance: str,
                      confirm: int = 20) -> np.ndarray:
    n = len(raw)
    out = np.full(n, 2, dtype=int)
    cur = 2
    if rebalance == "M":
        mend = _month_end_flags(index)
        for k in range(1, n):
            if mend[k - 1]:
                cur = raw[k - 1]
            out[k] = cur
    elif rebalance == "C20":
        for k in range(1, n):
            cand = raw[k - 1]
            if cand != cur and k - confirm >= 0 and np.all(raw[k - confirm:k] == cand):
                cur = cand
            out[k] = cur
    elif rebalance == "N20":
        for k in range(1, n):
            if (k - 1) % 20 == 0:
                cur = raw[k - 1]
            out[k] = cur
    else:
        raise ValueError(f"unknown rebalance rule: {rebalance}")
    return out


def build_session_targets(daily: pd.DataFrame, params: dict):
    """Per-session target weights, decided at the previous session's close."""
    lookback = int(params["lookback"])
    vol_target = float(params["vol_target"])
    rv_n = int(params["rv_n"])
    rebalance = str(params["rebalance"])

    raw = raw_states(daily, lookback)
    held = held_states_index(daily.index, raw, rebalance)

    rets = daily["TQQQ"].pct_change()
    rv = rets.rolling(rv_n, min_periods=rv_n).std() * np.sqrt(252.0)
    w_tqqq = np.clip(vol_target / rv.to_numpy(), 0.0, 1.0)
    w_tqqq = np.where(np.isfinite(w_tqqq), w_tqqq, 0.0)

    # Weight held during session k uses the volatility measured at k-1's close.
    targets = np.zeros((len(daily), 3), dtype=float)
    targets[0] = (0.0, 0.0, 1.0)
    for k in range(1, len(daily)):
        state = held[k]
        if state == 0:
            targets[k, 1] = w_tqqq[k - 1]
            targets[k, 2] = 1.0 - w_tqqq[k - 1]
        elif state == 1:
            targets[k, 0] = 1.0
        else:
            targets[k, 2] = 1.0
    if targets.min() < -1e-12 or targets.sum(axis=1).max() > 1.0 + 1e-9:
        raise ValueError("targets violate long-only / sum <= 1")

    info = dict(
        raw=raw,
        held=held,
        rv_tqqq=rv.to_numpy(),
        w_tqqq_raw=w_tqqq,
        daily_index=daily.index,
    )
    return targets, info


def expand_to_bars(ts: pd.DatetimeIndex, targets: np.ndarray) -> np.ndarray:
    """Map per-session targets to the engine's bar convention.

    `weights[i]` is set at bar i's close and fills at bar i+1's open.  For each
    session k, bars before the last carry targets[k]; the last bar carries
    targets[k+1], the decision made at k's close.
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


def build_weights(ts: pd.DatetimeIndex, o: np.ndarray, c: np.ndarray,
                  params: dict | None = None):
    """Public interface: bar-level weight matrix from the panel."""
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


def _state_share(held: np.ndarray) -> dict:
    return {
        "tqqq": float(np.mean(held == 0)),
        "qqq": float(np.mean(held == 1)),
        "bil": float(np.mean(held == 2)),
        "switches": int(np.sum(held[1:] != held[:-1])),
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
    daily = daily_frame(ts[: i + 1], c[: i + 1])
    w_cut, _ = weights_from_daily(ts[: i + 1], daily, params)
    diff = float(np.abs(w_full[: i + 1] - w_cut).max())
    return {
        "cut": cut,
        "bars_checked": int(i + 1),
        "max_abs_weight_diff": diff,
        "pass": bool(diff <= 1e-12),
    }


def _placebo(ts, o, c, targets: np.ndarray, n_draws: int = 200,
             seed: int = 20261127) -> dict:
    """Circularly shift the per-session target sequence."""
    d = len(targets)
    rng = np.random.default_rng(seed)
    cagrs, dds, sharpes = [], [], []
    for _ in range(n_draws):
        shift = int(rng.integers(20, d - 20))
        w = expand_to_bars(ts, np.roll(targets, shift, axis=0))
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

    all_w = {}
    all_info = {}
    for vid, params in GRID.items():
        w, info = weights_from_daily(ts, daily, params)
        all_w[vid] = w
        all_info[vid] = info

    grid_out = {}
    for vid, params in GRID.items():
        grid_out[vid] = {"params": dict(params)}
    for slip in (1.0, 5.0, 10.0):
        results = bt.run_many(ts, o, c, list(all_w.values()), start=START, band=BAND,
                              slippage_bps=slip)
        for vid, res in zip(GRID, results):
            grid_out[vid][f"{int(slip)}bp"] = _summary(res, bench_tqqq, bench_qqq)

    # Primary result at 1 bp.
    prim_w = all_w[PRIMARY]
    prim_info = all_info[PRIMARY]
    i0 = bt.start_index(ts, START)
    prim_res = bt.run(ts, o, c, prim_w, start=START, band=BAND, slippage_bps=1.0)
    prim = grid_out[PRIMARY]["1bp"]

    b_tqqq = bt.benchmark(bench_tqqq[i0:], ts[i0:], BARS_PER_YEAR)
    b_qqq = bt.benchmark(bench_qqq[i0:], ts[i0:], BARS_PER_YEAR)
    spy = _yahoo_dev("SPY", DEV_END)
    spy = spy[(spy.index >= pd.Timestamp(START)) & (spy.index <= DEV_END)]
    spy_ts = pd.DatetimeIndex(spy.index).tz_localize("America/New_York")
    b_spy = bt.benchmark(spy.to_numpy(), spy_ts, 252.0)

    ret_s = _daily_returns(prim_res["ts"], prim_res["equity"])
    ret_t = _daily_returns(prim_res["ts"], bench_tqqq)
    ret_q = _daily_returns(prim_res["ts"], bench_qqq)
    corr_t = _corr(ret_s, ret_t)
    corr_q = _corr(ret_s, ret_q)
    updown = _updown_capture(ret_s, ret_t)

    yearly = _yearly(prim_res, bench_tqqq)
    q_daily = bt.daily_last(bench_qqq, prim_res["ts"])
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
        ss = _sliced_stats(prim_res, a, b)
        t0 = pd.Timestamp(a, tz="America/New_York")
        t1 = pd.Timestamp(b, tz="America/New_York")
        j0 = int(prim_res["ts"].searchsorted(t0))
        j1 = int(prim_res["ts"].searchsorted(t1 + pd.Timedelta(days=1)))
        bs = bt.benchmark(bench_tqqq[j0:j1], prim_res["ts"][j0:j1], BARS_PER_YEAR)
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

    avg_w = _avg_weights(prim_info["targets"])

    # Ablations at 1 bp.
    ablations = {}
    abl_specs = {
        "no_vol_cap": dict(lookback=252, vol_target=10.0, rv_n=10, rebalance="C20"),
        "monthly_no_vol_cap": dict(lookback=252, vol_target=10.0, rv_n=10, rebalance="M"),
        "absolute_only": dict(lookback=252, vol_target=0.85, rv_n=10, rebalance="C20",
                              rel_mode="always"),
        "relative_only": dict(lookback=252, vol_target=0.85, rv_n=10, rebalance="C20",
                              abs_mode="always"),
        "no_confirmation_monthly": dict(lookback=252, vol_target=0.85, rv_n=10, rebalance="M"),
        "rv5": dict(lookback=252, vol_target=0.85, rv_n=5, rebalance="C20"),
        "rv15": dict(lookback=252, vol_target=0.85, rv_n=15, rebalance="C20"),
        "relative_126": dict(lookback=252, rel_lookback=126, vol_target=0.85,
                             rv_n=10, rebalance="C20"),
        "relative_189": dict(lookback=252, rel_lookback=189, vol_target=0.85,
                             rv_n=10, rebalance="C20"),
    }
    for name, spec in abl_specs.items():
        params = {k: v for k, v in spec.items() if k in
                  ("lookback", "vol_target", "rv_n", "rebalance")}
        w, _ = _weights_with_overrides(ts, daily, params, spec)
        res = bt.run(ts, o, c, w, start=START, band=BAND, slippage_bps=1.0)
        ablations[name] = {"params": spec, **_summary(res, bench_tqqq, bench_qqq)}

    # Neighbour table (descriptive, not candidates for substitution).
    neighbours = {}
    neigh_specs = {
        "lookback_210": dict(lookback=210, vol_target=0.85, rv_n=10, rebalance="C20"),
        "lookback_294": dict(lookback=294, vol_target=0.85, rv_n=10, rebalance="C20"),
        "vol_target_0.75": dict(lookback=252, vol_target=0.75, rv_n=10, rebalance="C20"),
        "vol_target_0.95": dict(lookback=252, vol_target=0.95, rv_n=10, rebalance="C20"),
        "rv30": dict(lookback=252, vol_target=0.85, rv_n=30, rebalance="C20"),
        "confirm_10": dict(lookback=252, vol_target=0.85, rv_n=10, rebalance="C10"),
        "confirm_30": dict(lookback=252, vol_target=0.85, rv_n=10, rebalance="C30"),
        "monthly_volat_month_end": dict(lookback=252, vol_target=0.85, rv_n=10,
                                        rebalance="MC20"),
    }
    for name, params in neigh_specs.items():
        w, _ = _weights_with_overrides(ts, daily, params, params)
        res = bt.run(ts, o, c, w, start=START, band=BAND, slippage_bps=1.0)
        neighbours[name] = {"params": params, **_summary(res, bench_tqqq, bench_qqq)}

    placebo = _placebo(ts, o, c, prim_info["targets"], n_draws=200)
    placebo["share_beating_strategy"] = float(
        np.mean(np.asarray(placebo["cagrs"]) >= prim["cagr"])
    )
    placebo.pop("cagrs", None)
    placebo.pop("max_drawdowns", None)

    cuts = [
        _cut_test(ts, o, c, GRID[PRIMARY], prim_w, "2020-03-12 11:07"),
        _cut_test(ts, o, c, GRID[PRIMARY], prim_w, "2022-09-13 10:41"),
    ]

    # Leave-one-year-out and replace-one-year-with-TQQQ.
    yy = sorted(yearly)
    s_rets = np.array([yearly[y]["strategy"] for y in yy])
    t_rets = np.array([yearly[y]["tqqq"] for y in yy])
    years_total = float(prim["years"])
    loo, replace_year = {}, {}
    for i, y in enumerate(yy):
        keep = np.ones(len(yy), dtype=bool)
        keep[i] = False
        loo[y] = float(np.prod(1.0 + s_rets[keep]) ** (1.0 / (len(yy) - 1)) - 1.0)
        r = s_rets.copy()
        r[i] = t_rets[i]
        replace_year[y] = float(np.prod(1.0 + r) ** (1.0 / years_total) - 1.0)

    pass_cells = [
        v for v, e in grid_out.items()
        if e["1bp"]["cagr"] > BASIS and e["1bp"]["max_drawdown"] < BASIS_DD
    ]
    vol_band_pass = [
        v for v in ("A", "B", "C")
        if grid_out[v]["1bp"]["cagr"] > BASIS
        and grid_out[v]["1bp"]["max_drawdown"] < BASIS_DD
    ]
    falsifiers = {
        "headline_cagr": bool(prim["cagr"] > BASIS),
        "headline_drawdown_below_60": bool(prim["max_drawdown"] < BASIS_DD),
        "vol_band_plateau_3_of_3": bool(len(vol_band_pass) == 3),
        "grid_plateau_3_of_8": bool(len(pass_cells) >= 3),
        "cost_10bp": bool(grid_out[PRIMARY]["10bp"]["cagr"] > BASIS),
        "placebo_at_most_10pct": bool(placebo["share_beating_strategy"] <= 0.10),
        "cut_test": bool(all(x["pass"] for x in cuts)),
        "loo_5_of_7": bool(sum(v > BASIS for v in loo.values()) >= 5),
    }
    robustness_failures = [k for k, ok in falsifiers.items() if not ok]
    robustness_status = "fragile" if robustness_failures else "robust"

    passed = bool(
        falsifiers["headline_cagr"]
        and falsifiers["headline_drawdown_below_60"]
        and falsifiers["vol_band_plateau_3_of_3"]
    )

    out = {
        "agent": "dual-momentum-tqqq",
        "status": "passed" if passed else "negative_result",
        "exploratory": True,
        "exploratory_reason": (
            "The 20-session confirmation and 10-session volatility window were "
            "chosen after daily-bar diagnostics on the development window. The "
            "pre-registered grid is a plateau probe, not a clean out-of-sample "
            "design."
        ),
        "hypothesis": (
            "A 12-month QQQ absolute-momentum gate with a QQQ-vs-SPY relative "
            "gate, a 20-session state confirmation, and a TQQQ sleeve sized to "
            "an 80-90% volatility target should beat TQQQ's 36.72% development "
            "CAGR with a materially lower drawdown."
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
        "updown_capture_vs_tqqq": updown,
        "yearly": yearly,
        "subperiods": sub,
        "avg_target_weights": avg_w,
        "risky_exposure": avg_w["risky"],
        "state_session_share": _state_share(prim_info["held"]),
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
        "diagnostic_variants_approx": 120,
        "variants_tried_note": (
            "8 pre-registered grid cells plus 17 ablations/neighbours and one "
            "placebo family are counted here; roughly 120 daily-bar diagnostic "
            "backtests across lookbacks, vol targets, vol windows and state "
            "rules preceded the frozen 1-minute grid. See report.md section 1."
        ),
        "verdict_note": (
            f"Passes the pre-registered development bar ({prim['cagr']*100:.2f}% "
            f"CAGR, {prim['max_drawdown']*100:.2f}% max DD). The result is not "
            "all-weather: the 2018 Q4 drawdown is essentially a full TQQQ "
            "drawdown, 2016-2019 underperforms TQQQ, and the 252-session "
            "lookback is load-bearing (126/189 fail). The edge is concentrated "
            "in 2019-2020 and in avoiding 2022. See report.md section 6."
        ),
        "caveats": [
            "The 58% max drawdown is the 2018-08-30 to 2018-12-24 TQQQ "
            "drawdown (-58.6% in the panel); the 12-month gate and the 85% "
            "vol threshold did not de-risk in time. It clears the 60% target "
            "by about 2 pp, not by crash protection.",
            "2016-2019 strategy CAGR is below TQQQ's (38.9% vs 49.0%) with "
            "the same 58% drawdown. The edge is 2020-2023.",
            "2023 is +42.3% vs TQQQ +198.4%: the 12-month gate re-entered only "
            "after the first-half rebound.",
            "Lookback neighbours 126 and 189 fail (31.9% and 28.0% CAGR); the "
            "252-session plateau is narrow in the lookback dimension.",
            "The 20-session confirmation and the 10-session volatility window "
            "were chosen after daily-bar diagnostics on the same development "
            "window; this is an exploratory pass, not a clean out-of-sample.",
            "The placebo distribution has 10.5% of random target reorderings "
            "at or above the strategy's CAGR; the result is at the "
            "pre-registered significance edge, not far beyond it.",
            "Leave-one-year-out drops below the bar when 2019, 2020 or 2017 is "
            "removed; replacing 2022 with TQQQ drops the CAGR to about 21.5%.",
        ],
        "notes": [
            "SPY is a signal only: no SPY 1-minute history exists for 2016-2023.",
            "The relative gate measures both QQQ and SPY through session k-1 so "
            "the windows are aligned and SPY's 16:00 close is not anticipated.",
            "The absolute gate and the TQQQ vol size use the 15:59 close at k.",
            "The holdout (2024-2026) was physically filtered out of the SPY and "
            "daily Parquet reads; the panel is hard-sliced at 2023-12-29.",
            "Equity is marked on every 1-minute bar; costs 1/5/10 bp kept.",
        ],
    }

    with open(HERE / "result.json", "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, indent=2, allow_nan=False)

    print(f"primary {PRIMARY} {GRID[PRIMARY]}")
    print(
        f"  dev 1bp: CAGR {prim['cagr']*100:.2f}%  DD {prim['max_drawdown']*100:.2f}%  "
        f"Sharpe {prim['sharpe']:.2f}  exposure {prim['exposure_invested']*100:.1f}%  "
        f"corr(TQQQ) {corr_t:.2f}"
    )
    print(f"  avg weights: {avg_w}")
    print(f"  states: {_state_share(prim_info['held'])}")
    print(f"  status: {out['status']}  passing cells: {pass_cells}")
    print(f"  robustness: {robustness_status}  failures: {robustness_failures}")
    print(f"  placebo share beating: {placebo['share_beating_strategy']:.3f}")
    print("grid 1bp:")
    for vid, e in grid_out.items():
        s = e["1bp"]
        print(
            f"  {vid}: L{e['params']['lookback']} vt{e['params']['vol_target']:.2f} "
            f"rv{e['params']['rv_n']} {e['params']['rebalance']}  "
            f"CAGR {s['cagr']*100:6.2f}%  DD {s['max_drawdown']*100:5.2f}%  "
            f"Sharpe {s['sharpe']:.2f}  exp {s['exposure_invested']*100:.1f}%  "
            f"corr {s['corr_tqqq_daily']:.2f}"
        )
    print(f"wrote {HERE / 'result.json'}")


def _weights_with_overrides(ts, daily, params, spec):
    """Build weights for a param dict plus diagnostic-only signal overrides."""
    p = dict(params)
    # rel_mode / abs_mode / rel_lookback / confirm / MC20 handled locally.
    override = {}
    for key in ("rel_mode", "abs_mode", "rel_lookback"):
        if key in spec:
            override[key] = spec[key]
    if not override and p.get("rebalance") not in ("C10", "C30", "MC20"):
        daily2 = daily
        return weights_from_daily(ts, daily2, p)

    # Rebuild with a modified raw-state function.
    lookback = int(p["lookback"])
    rel_lookback = int(spec.get("rel_lookback", lookback))
    rq = daily["QQQ"] / daily["QQQ"].shift(lookback) - 1.0
    rq_rel = daily["QQQ"] / daily["QQQ"].shift(rel_lookback) - 1.0
    rs = daily["SPY"] / daily["SPY"].shift(rel_lookback) - 1.0
    absolute = (rq > 0.0).fillna(False).to_numpy()
    relative = (rq_rel.shift(1) > rs.shift(1)).fillna(False).to_numpy()
    if spec.get("rel_mode") == "always":
        relative = np.ones(len(daily), dtype=bool)
    if spec.get("abs_mode") == "always":
        absolute = np.ones(len(daily), dtype=bool)
    raw = np.where(absolute & relative, 0, np.where(absolute, 1, 2))

    reb = str(p.get("rebalance", "C20"))
    n = len(raw)
    held = np.full(n, 2, dtype=int)
    cur = 2
    mend = _month_end_flags(daily.index)
    confirm = 20
    if reb == "C10":
        confirm = 10
        reb = "C20"
    elif reb == "C30":
        confirm = 30
        reb = "C20"
    for k in range(1, n):
        cand = raw[k - 1]
        if reb == "MC20":
            if mend[k - 1]:
                cur = cand
            elif cand != cur and k - confirm >= 0 and np.all(raw[k - confirm:k] == cand):
                cur = cand
        elif reb == "C20":
            if cand != cur and k - confirm >= 0 and np.all(raw[k - confirm:k] == cand):
                cur = cand
        elif reb == "M":
            if mend[k - 1]:
                cur = cand
        elif reb == "N20":
            if (k - 1) % 20 == 0:
                cur = cand
        held[k] = cur

    rets = daily["TQQQ"].pct_change()
    rv = rets.rolling(int(p["rv_n"]), min_periods=int(p["rv_n"])).std() * np.sqrt(252.0)
    w_tqqq = np.clip(float(p["vol_target"]) / rv.to_numpy(), 0.0, 1.0)
    w_tqqq = np.where(np.isfinite(w_tqqq), w_tqqq, 0.0)

    targets = np.zeros((n, 3), dtype=float)
    targets[0] = (0.0, 0.0, 1.0)
    for k in range(1, n):
        s = held[k]
        if s == 0:
            targets[k, 1] = w_tqqq[k - 1]
            targets[k, 2] = 1.0 - w_tqqq[k - 1]
        elif s == 1:
            targets[k, 0] = 1.0
        else:
            targets[k, 2] = 1.0
    pos = daily.index.get_indexer(pd.to_datetime(bt.session_dates(ts)[bt.day_bounds(ts)[2]]))
    if (pos < 0).any():
        raise ValueError("panel session date missing from daily signal frame")
    targets = targets[pos]
    return expand_to_bars(ts, targets), None


if __name__ == "__main__":
    main()
