"""Cross-asset multi-horizon dual momentum: QQQ / SPY signal, TQQQ / QQQ / BIL book.

Final design is Revision 2 in HYPOTHESIS.md.  Revision 1 (single 126-day
absolute lookback) is kept as a reproducible reference because it was the
pre-registered first attempt and it failed.

Revision 2 rules
----------------
1. Daily total-return levels for QQQ, TQQQ and BIL are the 15:59 ET session
   closes from the 1-minute panel, spliced to Yahoo adjusted daily closes
   before 2016-01-04 so 21/42/84/105/126-day lookbacks have warm-up from 2015.
   SPY is Yahoo adjusted daily closes, used as a signal only; there is no SPY
   1-minute history for the development period, so SPY is never held.
2. Absolute momentum has two gates:
       short  = M21(QQQ) > M21(BIL)  OR  M42(QQQ) > M42(BIL)
       medium = at least 2 of M84, M105, M126 for QQQ > BIL
       absolute = short AND medium
   where M_L = P(t)/P(t-L) - 1.
3. Relative momentum: M126(QQQ, t-1) > M126(SPY, t-1).  SPY is lagged one
   session because its official close is 16:00, after the 15:59 decision bar.
4. State 2 (absolute and relative): TQQQ.  State 1 (absolute only): QQQ.
   State 0: BIL.
5. Volatility target: w_risky = min(1, target_vol / sigma_20d), where sigma_20d
   is the annualized 20-session realized vol of the asset held; remainder BIL.
6. Rebalance weekly (last session of the ISO week) or monthly (last session of
   the month), plus an initial decision at the first session.  Decisions fill
   at the next session's open.  2% band.
7. Long-only, weights >= 0, row sum <= 1.  Costs 1 bp headline, 5 bp and 10 bp
   sensitivity.  Equity marked on every 1-minute bar.

Run from the repo root:
    $env:PYTHONPATH = "C:/Users/27175/AppData/Local/Temp/opencode/pylibs"
    $env:BT_THREADS = "1"
    python research/new/cross-asset-momentum/strategy.py
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

HERE = Path(__file__).resolve().parent
DATA = ROOT / "data" / "intraday-hf"
SPY_PATH = ROOT / "data" / "round3" / "yahoo" / "SPY-1d-yahoo.parquet"

START = "2016-01-04"
END = "2023-12-29"
DEV_END = pd.Timestamp("2023-12-29")
BAND = 0.02
BARS_PER_YEAR = 252 * 390
SYMS = ("QQQ", "TQQQ", "BIL")

SHORT_LOOKS = (21, 42)
MEDIUM_LOOKS = (84, 105, 126)

# Revision 2 grid.  A is the primary and was fixed before the final run.
GRID = {
    "A": dict(vol_target=1.00, rel_lookback=126, rebalance="W"),
    "B": dict(vol_target=0.90, rel_lookback=126, rebalance="W"),
    "C": dict(vol_target=0.80, rel_lookback=126, rebalance="W"),
    "D": dict(vol_target=1.00, rel_lookback=252, rebalance="W"),
    "E": dict(vol_target=0.90, rel_lookback=252, rebalance="W"),
    "F": dict(vol_target=0.80, rel_lookback=252, rebalance="W"),
    "G": dict(vol_target=0.90, rel_lookback=126, rebalance="M"),
    "H": dict(vol_target=1.00, rel_lookback=126, rebalance="M"),
}
PRIMARY = "A"

# Revision 1 primary, kept for the record (single 126-day absolute lookback).
REV1_PRIMARY = dict(rev=1, lookback=126, vol_target=0.65, rebalance="W")
REV1_GRID = {
    "A": dict(rev=1, lookback=126, vol_target=0.65, rebalance="W"),
    "B": dict(rev=1, lookback=126, vol_target=0.65, rebalance="M"),
    "C": dict(rev=1, lookback=126, vol_target=0.50, rebalance="W"),
    "D": dict(rev=1, lookback=126, vol_target=0.50, rebalance="M"),
    "E": dict(rev=1, lookback=252, vol_target=0.65, rebalance="W"),
    "F": dict(rev=1, lookback=252, vol_target=0.65, rebalance="M"),
    "G": dict(rev=1, lookback=252, vol_target=0.50, rebalance="W"),
    "H": dict(rev=1, lookback=252, vol_target=0.50, rebalance="M"),
}

VOL_N = 20
MIN_VOL_OBS = 20


# ---------------------------------------------------------------------------
# data
# ---------------------------------------------------------------------------
def _yahoo_adj(symbol: str, last_date: pd.Timestamp) -> pd.Series:
    path = SPY_PATH if symbol == "SPY" else DATA / f"{symbol}-1d-yahoo.parquet"
    df = pd.read_parquet(path)
    s = pd.Series(
        df["adjclose"].to_numpy(dtype=float),
        index=pd.to_datetime(df["date"]).dt.normalize(),
    )
    s = s[~s.index.duplicated(keep="last")].sort_index()
    s = s[s.index <= last_date]
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

    dates, first, last = bt.day_bounds(ts)
    sess_dates = pd.to_datetime(dates[last])
    panel = pd.DataFrame(closes[last], index=sess_dates, columns=list(SYMS))

    levels = {}
    for symbol in SYMS:
        y = _yahoo_adj(symbol, last_date)
        p = panel[symbol]
        common = p.index.intersection(y.index)
        if len(common) == 0:
            raise ValueError(f"{symbol}: no overlap between panel and Yahoo")
        k = float(p.loc[common[0]] / y.loc[common[0]])
        pre = y[y.index < p.index[0]] * k
        levels[symbol] = pd.concat([pre, p]).sort_index()

    idx = levels["QQQ"].index
    spy = _yahoo_adj("SPY", last_date).reindex(idx).ffill()
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
    if freq == "W":
        iso = index.isocalendar()
        key = pd.Series(
            list(zip(iso["year"].to_numpy(), iso["week"].to_numpy())), index=index
        )
    elif freq == "M":
        key = pd.Series(index.to_period("M"), index=index)
    else:
        raise ValueError(f"unknown rebalance frequency: {freq}")
    flags = ~key.duplicated(keep="last").to_numpy()
    flags[0] = True
    return flags


def _vote(daily: pd.DataFrame, looks: tuple[int, ...], rule: str) -> np.ndarray:
    votes = []
    for L in looks:
        votes.append(
            (daily["QQQ"] / daily["QQQ"].shift(L) - 1.0)
            > (daily["BIL"] / daily["BIL"].shift(L) - 1.0)
        )
    v = np.vstack([x.to_numpy() for x in votes])
    if rule == "or":
        return v.any(axis=0)
    if rule == "and":
        return v.all(axis=0)
    if rule == "majority":
        return v.sum(axis=0) >= (len(looks) + 1) // 2
    raise ValueError(f"unknown vote rule: {rule}")


def build_session_targets(daily: pd.DataFrame, params: dict):
    """Per-session target weights, decided at that session's close.

    `targets[k]` is the weight held during session k, i.e. it was decided at
    session k-1's close.  The target set at session k's close is `targets[k+1]`.
    """
    rev = int(params.get("rev", 2))
    target_vol = float(params["vol_target"])
    freq = str(params["rebalance"])

    if rev == 1:
        L = int(params["lookback"])
        mq = daily["QQQ"] / daily["QQQ"].shift(L) - 1.0
        mb = daily["BIL"] / daily["BIL"].shift(L) - 1.0
        ms = daily["SPY"] / daily["SPY"].shift(L) - 1.0
        abs_on = (mq > mb).to_numpy()
        rel_on = (mq.shift(1) > ms.shift(1)).to_numpy()
        short_on = abs_on.copy()
        med_on = abs_on.copy()
    else:
        short_rule = str(params.get("short_rule", "or"))
        medium_rule = str(params.get("medium_rule", "majority"))
        short_looks = tuple(params.get("short_looks", SHORT_LOOKS))
        medium_looks = tuple(params.get("medium_looks", MEDIUM_LOOKS))
        short_on = _vote(daily, short_looks, short_rule)
        med_on = _vote(daily, medium_looks, medium_rule)
        abs_on = short_on & med_on
        relL = int(params["rel_lookback"])
        rq = daily["QQQ"] / daily["QQQ"].shift(relL) - 1.0
        rs = daily["SPY"] / daily["SPY"].shift(relL) - 1.0
        rel_on = (rq.shift(1) > rs.shift(1)).to_numpy()
        if params.get("abs_only", False):
            rel_on = np.ones(len(daily), dtype=bool)

    state = np.where(abs_on & rel_on, 2, np.where(abs_on, 1, 0)).astype(int)

    rets = daily[["QQQ", "TQQQ", "BIL"]].pct_change()
    rv = rets.rolling(VOL_N, min_periods=MIN_VOL_OBS).std() * np.sqrt(252.0)
    w_tqqq = np.clip(target_vol / rv["TQQQ"].to_numpy(), 0.0, 1.0)
    w_qqq = np.clip(target_vol / rv["QQQ"].to_numpy(), 0.0, 1.0)
    w_tqqq = np.where(np.isfinite(w_tqqq), w_tqqq, 0.0)
    w_qqq = np.where(np.isfinite(w_qqq), w_qqq, 0.0)

    desired = np.zeros((len(daily), 3))
    desired[state == 2, 1] = w_tqqq[state == 2]
    desired[state == 2, 2] = 1.0 - w_tqqq[state == 2]
    desired[state == 1, 0] = w_qqq[state == 1]
    desired[state == 1, 2] = 1.0 - w_qqq[state == 1]
    desired[state == 0, 2] = 1.0

    flags = _rebalance_flags(daily.index, freq)
    targets = np.zeros((len(daily), 3))
    targets[0] = (0.0, 0.0, 1.0)
    for k in range(1, len(daily)):
        targets[k] = desired[k - 1] if flags[k - 1] else targets[k - 1]

    info = dict(
        state=state,
        desired=desired,
        targets=targets,
        flags=flags,
        short_on=short_on,
        med_on=med_on,
        abs_on=abs_on,
        rel_on=rel_on,
        w_tqqq=w_tqqq,
        w_qqq=w_qqq,
        rv_tqqq=rv["TQQQ"].to_numpy(),
        rv_qqq=rv["QQQ"].to_numpy(),
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
        if isinstance(value, np.ndarray) and len(value) == len(daily):
            info[key] = value[pos]
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
    s = bt.daily_last(values, ts)
    return s.pct_change().dropna()


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


def _summary(result: dict, bench_tqqq: np.ndarray) -> dict:
    s = bt.stats(result, BARS_PER_YEAR)
    ret_s = _daily_returns(result["ts"], result["equity"])
    ret_b = _daily_returns(result["ts"], bench_tqqq)
    eq = result["equity"]
    peak = np.maximum.accumulate(eq)
    dd = eq / peak - 1.0
    trough_i = int(np.argmin(dd))
    peak_i = int(np.argmax(eq[: trough_i + 1]))
    return {
        "cagr": float(s["cagr"]),
        "max_drawdown": float(s["max_drawdown"]),
        "max_drawdown_peak": str(result["ts"][peak_i]),
        "max_drawdown_trough": str(result["ts"][trough_i]),
        "max_drawdown_days": float(
            (result["ts"][trough_i] - result["ts"][peak_i]).total_seconds() / 86400.0
        ),
        "sharpe": float(s["sharpe"]),
        "sortino": float(s["sortino"]),
        "volatility": float(s["volatility"]),
        "exposure_invested": float(s["exposure"]),
        "fills": int(s["fills"]),
        "turnover": float(s["turnover"]),
        "turnover_per_year": float(s["turnover"] / s["years"]),
        "corr_tqqq_daily": _corr(ret_s, ret_b),
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
    }


def _state_share(state: np.ndarray) -> dict:
    return {
        "tqqq": float(np.mean(state == 2)),
        "qqq": float(np.mean(state == 1)),
        "bil": float(np.mean(state == 0)),
        "switches": int(np.sum(state[1:] != state[:-1])),
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

    This preserves the exact state sequence, exposure distribution, vol
    targeting and turnover, but destroys its alignment with market returns.
    """
    d = len(targets)
    rng = np.random.default_rng(seed)
    cagrs = []
    dds = []
    for _ in range(n_draws):
        shift = int(rng.integers(20, d - 20))
        shifted = np.roll(targets, shift, axis=0)
        w = expand_to_bars(ts, shifted)
        res = bt.run(ts, o, c, w, start=START, band=BAND, slippage_bps=1.0)
        s = bt.stats(res, BARS_PER_YEAR)
        cagrs.append(float(s["cagr"]))
        dds.append(float(s["max_drawdown"]))
    cagrs = np.asarray(cagrs)
    dds = np.asarray(dds)
    return {
        "draws": n_draws,
        "seed": seed,
        "cagr_median": float(np.median(cagrs)),
        "cagr_p05": float(np.percentile(cagrs, 5)),
        "cagr_p95": float(np.percentile(cagrs, 95)),
        "max_drawdown_median": float(np.median(dds)),
        "max_drawdown_p05": float(np.percentile(dds, 5)),
        "max_drawdown_p95": float(np.percentile(dds, 95)),
        "share_beating_strategy": None,
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

    # Revision 1 primary and grid, for the record.
    w1, _ = weights_from_daily(ts, daily, REV1_PRIMARY)
    res1 = bt.run(ts, o, c, w1, start=START, band=BAND, slippage_bps=1.0)
    rev1_grid = {}
    for vid, params in REV1_GRID.items():
        w, _ = weights_from_daily(ts, daily, params)
        res = bt.run(ts, o, c, w, start=START, band=BAND, slippage_bps=1.0)
        rev1_grid[vid] = {"params": dict(params), "1bp": _summary(res, bench_tqqq)}
    rev1_pass = [
        v for v, e in rev1_grid.items()
        if e["1bp"]["cagr"] > 0.3672 and e["1bp"]["max_drawdown"] < 0.60
    ]
    rev1 = {
        "params": dict(REV1_PRIMARY),
        "1bp": _summary(res1, bench_tqqq),
        "yearly": _yearly(res1, bench_tqqq),
        "grid": rev1_grid,
        "passed": bool(len(rev1_pass) > 0),
        "passing_points": rev1_pass,
    }

    grid_out = {}
    primary_w = None
    primary_info = None
    primary_res = None
    for vid, params in GRID.items():
        w, info = weights_from_daily(ts, daily, params)
        entry = {"params": dict(params)}
        for slip in (1.0, 5.0, 10.0):
            res = bt.run(ts, o, c, w, start=START, band=BAND, slippage_bps=slip)
            entry[f"{int(slip)}bp"] = _summary(res, bench_tqqq)
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
    spy = _yahoo_adj("SPY", DEV_END)
    spy = spy[(spy.index >= pd.Timestamp(START)) & (spy.index <= DEV_END)]
    spy_ts = pd.DatetimeIndex(spy.index).tz_localize("America/New_York")
    b_spy = bt.benchmark(spy.to_numpy(), spy_ts, 252.0)

    ret_s = _daily_returns(primary_res["ts"], primary_res["equity"])
    ret_t = _daily_returns(primary_res["ts"], bench_tqqq)
    ret_q = _daily_returns(primary_res["ts"], bench_qqq)
    corr_t = _corr(ret_s, ret_t)
    corr_q = _corr(ret_s, ret_q)

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

    # Neighbour table: horizon and gate perturbations around A.  Descriptive,
    # not candidates for substitution.
    neighbours = {}
    neighbour_specs = {
        "short21_only": dict(vol_target=1.0, rel_lookback=126, rebalance="W",
                             short_looks=(21,), short_rule="or"),
        "short42_only": dict(vol_target=1.0, rel_lookback=126, rebalance="W",
                             short_looks=(42,), short_rule="or"),
        "short63_only": dict(vol_target=1.0, rel_lookback=126, rebalance="W",
                             short_looks=(63,), short_rule="or"),
        "short21_42_and": dict(vol_target=1.0, rel_lookback=126, rebalance="W",
                               short_looks=(21, 42), short_rule="and"),
        "short21_42_63_maj": dict(vol_target=1.0, rel_lookback=126, rebalance="W",
                                  short_looks=(21, 42, 63), short_rule="majority"),
        "medium63_84_105": dict(vol_target=1.0, rel_lookback=126, rebalance="W",
                                medium_looks=(63, 84, 105)),
        "medium105_126_147": dict(vol_target=1.0, rel_lookback=126, rebalance="W",
                                  medium_looks=(105, 126, 147)),
        "medium84_126_168": dict(vol_target=1.0, rel_lookback=126, rebalance="W",
                                 medium_looks=(84, 126, 168)),
        "abs_only": dict(vol_target=1.0, rel_lookback=126, rebalance="W", abs_only=True),
    }
    for name, params in neighbour_specs.items():
        w, info = weights_from_daily(ts, daily, params)
        res = bt.run(ts, o, c, w, start=START, band=BAND, slippage_bps=1.0)
        neighbours[name] = {"params": params, **_summary(res, bench_tqqq)}

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

    avg_w = _avg_weights(primary_info["targets"])
    state_share = _state_share(primary_info["state"])

    weekly_ids = ["A", "B", "C", "D", "E", "F"]
    weekly_pass = [
        v for v in weekly_ids
        if grid_out[v]["1bp"]["cagr"] > 0.3672
        and grid_out[v]["1bp"]["max_drawdown"] < 0.60
    ]
    passed = bool(
        prim["cagr"] > 0.3672
        and prim["max_drawdown"] < 0.60
        and len(weekly_pass) >= 3
    )

    # Concentration: replace one year's strategy return with TQQQ's and
    # recompute the CAGR.  This shows whether the pass depends on one year.
    yy = sorted(yearly)
    s_rets = np.array([yearly[y]["strategy"] for y in yy])
    t_rets = np.array([yearly[y]["tqqq"] for y in yy])
    years_total = float(prim["years"])

    def _cagr(rets):
        return float(np.prod(1.0 + rets) ** (1.0 / years_total) - 1.0)

    replace_year = {}
    for i, y in enumerate(yy):
        r = s_rets.copy()
        r[i] = t_rets[i]
        replace_year[y] = _cagr(r)

    falsifiers = {
        "headline_cagr": bool(prim["cagr"] > 0.3672),
        "headline_drawdown": bool(prim["max_drawdown"] < 0.60),
        "weekly_plateau": bool(len(weekly_pass) >= 3),
        "placebo_at_most_5pct": bool(placebo["share_beating_strategy"] <= 0.05),
        "cut_test": bool(all(c["pass"] for c in cuts)),
        "cost_10bp": bool(grid_out[PRIMARY]["10bp"]["cagr"] > 0.3672),
        "tqqq_weight_below_90pct": bool(avg_w["TQQQ"] < 0.90),
        "short_gate_21_and_63_both_work": bool(
            neighbours["short21_only"]["cagr"] > 0.3672
            and neighbours["short63_only"]["cagr"] > 0.3672
        ),
        "replace_any_year_with_tqqq_still_passes": bool(
            min(replace_year.values()) > 0.3672
        ),
    }
    robustness_failures = [k for k, ok in falsifiers.items() if not ok]
    robustness_status = "fragile" if robustness_failures else "robust"

    out = {
        "agent": "cross-asset-momentum",
        "status": "passed" if passed else "negative_result",
        "exploratory": True,
        "exploratory_reason": (
            "Revision 2 was designed after the pre-registered Revision 1 failed; "
            "the short-horizon ensemble was informed by diagnostics on the same "
            "development window. It is not a clean out-of-sample pass."
        ),
        "hypothesis": (
            "A multi-horizon cross-asset dual-momentum gate (short 21/42 OR, "
            "medium 84/105/126 majority, QQQ vs SPY relative) with a "
            "volatility-targeted TQQQ sleeve should beat TQQQ's 36.72% "
            "development CAGR with a materially lower drawdown."
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
        "year_concentration": {
            "replace_year_with_tqqq_cagr": replace_year,
            "note": "Replace one year's strategy return with TQQQ's and recompute CAGR; shows one-year dependence.",
        },
        "weekly_pass": weekly_pass,
        "grid": grid_out,
        "revision_1": rev1,
        "benchmarks": {
            "tqqq": {k: float(v) for k, v in b_tqqq.items()},
            "qqq": {k: float(v) for k, v in b_qqq.items()},
            "spy_daily": {k: float(v) for k, v in b_spy.items()},
            "spy_note": "daily close marks only; no SPY 1-minute history for dev",
        },
        "corr_tqqq_daily": corr_t,
        "corr_qqq_daily": corr_q,
        "yearly": yearly,
        "subperiods": sub,
        "avg_target_weights": avg_w,
        "risky_exposure": avg_w["risky"],
        "state_session_share": state_share,
        "placebo": placebo,
        "cut_tests": cuts,
        "neighbours": neighbours,
        "variants_tried": len(GRID) + len(neighbours) + len(REV1_GRID) + 1,
        "diagnostic_variants_approx": 200,
        "variants_tried_note": (
            "26 formal grid/neighbour/placebo runs are counted here; roughly 200 "
            "diagnostic backtests across lookbacks, vol targets, stops and state "
            "rules preceded Revision 2. See report.md section 1."
        ),
        "notes": [
            "SPY is a signal only: no SPY 1-minute history exists for 2016-2023.",
            "SPY relative momentum is lagged one session to respect the 15:59 decision bar.",
            "Signals use 15:59 panel closes for QQQ/TQQQ/BIL and Yahoo adjclose for SPY.",
            "The holdout (2024-2026) was not loaded or inspected.",
            "Equity is marked on every 1-minute bar; costs 1/5/10 bp.",
            "Revision 1 (single 126-day absolute lookback) failed at 31.04% CAGR / 54.86% DD.",
            "Revision 2 is exploratory: designed after Revision 1 failed, on the same dev window.",
        ],
    }

    with open(HERE / "result.json", "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, indent=2, allow_nan=False)

    print(f"primary {PRIMARY} {GRID[PRIMARY]}")
    print(
        f"  dev 1bp: CAGR {prim['cagr']*100:.2f}%  DD {prim['max_drawdown']*100:.2f}%  "
        f"Sharpe {prim['sharpe']:.2f}  risky exposure {avg_w['risky']*100:.1f}%  "
        f"corr(TQQQ) {corr_t:.2f}"
    )
    print(f"  status: {out['status']}  weekly pass: {weekly_pass}")
    print(f"  robustness: {robustness_status}  failures: {robustness_failures}")
    print(f"  placebo share beating: {placebo['share_beating_strategy']:.3f}")
    print("grid 1bp:")
    for vid, e in grid_out.items():
        s = e["1bp"]
        print(
            f"  {vid}: {e['params']['vol_target']*100:.0f}%/rel{e['params']['rel_lookback']}/"
            f"{e['params']['rebalance']}  CAGR {s['cagr']*100:6.2f}%  "
            f"DD {s['max_drawdown']*100:5.2f}%  Sharpe {s['sharpe']:.2f}  "
            f"corr {s['corr_tqqq_daily']:.2f}"
        )
    print(f"wrote {HERE / 'result.json'}")


if __name__ == "__main__":
    main()
