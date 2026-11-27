"""Realized-vol term-structure timing on TQQQ - standalone strategy.

Development window ONLY: 2016-01-04 .. 2023-12-29.  The 1-minute panel is
requested with ``end=2023-12-29`` and every daily parquet read is filtered with
``date <= 2023-12-29``; no 2024+ bar is loaded or inspected.

Rule (see HYPOTHESIS.md):
    RV_n(t) = sqrt(mean(r_{t-n+1..t}^2)) * sqrt(252),  r = QQQ daily log return
    trend_t = QQQ close > SMA_165
    calm_t  = RV_20/RV_60 < 0.95
    spike_t = RV_5/RV_60 > 1.80
    w_t     = 0 if spike_t else 0.5*trend_t + 0.5*calm_t
Weight w_t is the TQQQ target for session t+1, filled at the next open with a
2% band.  Idle weight is cash at 0%.

Run from the repo root:
    $env:PYTHONPATH = "C:\\Users\\27175\\AppData\\Local\\Temp\\opencode\\pylibs"
    $env:BT_THREADS = "1"
    python research/new/vol-term-structure/strategy.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402

START = "2016-01-04"
END = "2023-12-29"
SYMBOLS = ("QQQ", "TQQQ", "BIL")
COL_Q, COL_T, COL_B = 0, 1, 2
BARS_1M = 252 * 390
BAND = 0.02
HEADLINE_COST = 1.0
COSTS = (1.0, 5.0, 10.0)

# Primary parameters, frozen in HYPOTHESIS.md before the final run.
PRIMARY = dict(
    trend_n=165,
    rv_short=20,
    rv_long=60,
    theta=0.95,
    spike=1.80,
    trend_w=0.50,
    signal_symbol="QQQ",
)

# Pre-registered 8-cell grid: one parameter at a time around the centre.
GRID = [
    ("primary", {}),
    ("theta_092", {"theta": 0.92}),
    ("theta_098", {"theta": 0.98}),
    ("sma150", {"trend_n": 150}),
    ("sma180", {"trend_n": 180}),
    ("spike_1.6", {"spike": 1.60}),
    ("spike_2.0", {"spike": 2.00}),
    ("blend_40_60", {"trend_w": 0.40}),
]


# --------------------------------------------------------------------------- #
# signals
# --------------------------------------------------------------------------- #
def _read_daily_adjclose(symbol: str) -> pd.Series:
    """Adjusted daily close, physically filtered to the development window."""
    path = bt.DATA_DIR / f"{symbol}-1d-yahoo.parquet"
    d = pd.read_parquet(
        path,
        columns=["date", "adjclose"],
        filters=[("date", "<=", pd.Timestamp(END).date())],
    )
    d["date"] = pd.to_datetime(d["date"])
    s = d.drop_duplicates("date").set_index("date")["adjclose"].astype(float).sort_index()
    if len(s) == 0 or s.index.max() > pd.Timestamp(END):
        raise RuntimeError("daily read crossed the development boundary")
    return s


def _daily_signals(session_dates: pd.DatetimeIndex, params: dict):
    """Causal daily state and target weight for each session.

    ``session_dates`` is the ordered list of trading sessions in the panel.
    The returned ``w`` has one value per session; the value at index d is the
    target for session d+1.
    """
    p = dict(PRIMARY)
    p.update(params or {})
    q = _read_daily_adjclose(p["signal_symbol"])
    idx = q.index.union(pd.DatetimeIndex(session_dates))
    q = q.reindex(idx).ffill().loc[: session_dates[-1]]
    r = np.log(q).diff()

    def rv(n: int) -> pd.Series:
        return np.sqrt(r.pow(2).rolling(n, min_periods=n).mean()) * np.sqrt(252.0)

    rv_s = rv(int(p["rv_short"]))
    rv_l = rv(int(p["rv_long"]))
    rv_f = rv(5)
    sma = q.rolling(int(p["trend_n"]), min_periods=int(p["trend_n"])).mean()

    qq = q.reindex(session_dates)
    trend = (qq > sma.reindex(session_dates)).astype(float).fillna(0.0).to_numpy()
    ratio = (rv_s / rv_l).reindex(session_dates).to_numpy(dtype=float)
    spike_ratio = (rv_f / rv_l).reindex(session_dates).to_numpy(dtype=float)
    rv_long = rv_l.reindex(session_dates).to_numpy(dtype=float)
    rv_short = rv_s.reindex(session_dates).to_numpy(dtype=float)

    calm = np.isfinite(ratio) & (ratio < float(p["theta"]))
    calm = calm.astype(float)
    raw = float(p["trend_w"]) * trend + (1.0 - float(p["trend_w"])) * calm
    spike = np.isfinite(spike_ratio) & (spike_ratio > float(p["spike"]))
    w = np.where(spike, 0.0, raw)
    w = np.clip(np.nan_to_num(w, nan=0.0), 0.0, 1.0)
    parts = dict(
        trend=trend,
        calm=calm,
        ratio=ratio,
        spike_ratio=spike_ratio,
        spike=spike.astype(float),
        rv_short=rv_short,
        rv_long=rv_long,
    )
    return w, parts


def _expand_to_bars(ts: pd.DatetimeIndex, w_daily: np.ndarray) -> np.ndarray:
    """Map one target per session to one target per bar.

    The target set at the close of session d is executed at the open of d+1,
    so bars of session d carry w[d-1] and the 15:59 bar carries w[d].
    """
    nd = len(w_daily)
    if nd != len(bt.day_bounds(ts)[1]):
        raise ValueError("session count mismatch")
    if len(ts) == nd:  # already a daily panel
        return np.asarray(w_daily, dtype=float).copy()
    sid = bt.day_ids(ts)
    _, _, last = bt.day_bounds(ts)
    out = np.zeros(len(ts), dtype=float)
    shifted = np.r_[0.0, np.asarray(w_daily, dtype=float)[:-1]]
    out[:] = shifted[sid]
    out[last] = w_daily
    return out


def _check_dev_boundary(ts) -> None:
    """Refuse a panel that extends past the current development end.

    The lead's one-shot holdout runner catches this RuntimeError, sets
    ``END`` to the full-window end and retries.  The signal and weight logic
    are unchanged; this only lets the same code read the holdout daily closes
    when the lead explicitly authorizes it.  A normal development run never
    reaches the raise.
    """
    if len(ts) == 0:
        return
    last = pd.Timestamp(ts[-1])
    if last.tzinfo is None:
        last = last.tz_localize("America/New_York")
    limit = (pd.Timestamp(END, tz="America/New_York").normalize()
             + pd.Timedelta(days=1))
    if last >= limit:
        raise RuntimeError(
            "panel extends past the development window; "
            "the holdout runner may lift END and retry"
        )


def build_weights(ts, o, c, params=None, return_parts=False):
    """Return (n, 3) TQQQ/cash target weights for the harness.

    ``ts`` may be a 1-minute or a daily panel.  The columns of the returned
    matrix follow ``SYMBOLS`` (QQQ, TQQQ, BIL); only TQQQ is used.
    """
    _check_dev_boundary(ts)
    dates, first, _ = bt.day_bounds(ts)
    session_dates = pd.DatetimeIndex(dates[first])
    w_daily, parts = _daily_signals(session_dates, params or {})
    w = _expand_to_bars(ts, w_daily)
    W = np.zeros((len(ts), len(SYMBOLS)), dtype=float)
    W[:, COL_T] = w
    if return_parts:
        return W, w_daily, parts, session_dates
    return W


# --------------------------------------------------------------------------- #
# simulation / metrics
# --------------------------------------------------------------------------- #
def _benchmark(ts, c):
    return bt.benchmark(c[:, COL_T], ts, BARS_1M)


def _metrics(ts, o, c, W, cost: float = HEADLINE_COST, start: str = START,
             bars_per_year: float = BARS_1M, end: str | None = None):
    if end is not None:
        j = int(ts.searchsorted(pd.Timestamp(end, tz="America/New_York"), side="right"))
        ts, o, c, W = ts[:j], o[:j], c[:j], W[:j]
    i0 = bt.start_index(ts, start)
    r = bt.run(ts, o, c, W, start, band=BAND, slippage_bps=cost)
    s = bt.stats(r, bars_per_year)
    eq = r["equity"]
    b = c[i0:, COL_T]
    eq_d = bt.daily_last(eq, r["ts"])
    b_d = bt.daily_last(b, r["ts"])
    rets = np.diff(eq_d.to_numpy()) / eq_d.to_numpy()[:-1]
    bret = np.diff(b_d.to_numpy()) / b_d.to_numpy()[:-1]
    corr = float(np.corrcoef(rets, bret)[0, 1]) if len(rets) > 2 else float("nan")
    s["corr_tqqq"] = corr
    s["cagr"] = float(s["cagr"])
    s["max_drawdown"] = float(s["max_drawdown"])
    s["sharpe"] = float(s["sharpe"])
    s["exposure"] = float(s["exposure"])
    s["turnover"] = float(s["turnover"])
    s["fills"] = int(s["fills"])
    return s, r, eq_d, b_d


def _metrics_daily(ts_d, o_d, c_d, W, cost: float = HEADLINE_COST):
    return _metrics(ts_d, o_d, c_d, W, cost=cost, bars_per_year=252)


def _round(obj):
    if isinstance(obj, dict):
        return {k: _round(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_round(v) for v in obj]
    if isinstance(obj, (np.floating, float)):
        return round(float(obj), 6)
    if isinstance(obj, (np.integer, int)):
        return int(obj)
    return obj


def _summary(s):
    return {
        "cagr": s["cagr"],
        "max_drawdown": s["max_drawdown"],
        "sharpe": s["sharpe"],
        "sortino": s.get("sortino"),
        "volatility": s["volatility"],
        "exposure": s.get("exposure"),
        "corr_tqqq": s.get("corr_tqqq"),
        "fills": s.get("fills"),
        "turnover": s.get("turnover"),
        "years": s["years"],
        "ending_equity": s["ending_equity"],
    }


def _yearly(ts, eq, bench):
    return {str(y): {"strategy": v["strategy"], "benchmark": v["benchmark"]}
            for y, v in bt.yearly(ts, eq, bench).items()}


def _yearly_exposure(ts, r):
    eq = r["equity"]
    expo = (eq - r["cash"]) / eq
    out = {}
    for y in sorted(set(ts.year)):
        m = ts.year == y
        out[str(int(y))] = float(np.mean(expo[m]))
    return out


def _binarize(a):
    return (np.asarray(a, dtype=float) > 0.5).astype(float)


# --------------------------------------------------------------------------- #
# robustness
# --------------------------------------------------------------------------- #
def _cagr_from_returns(dr: np.ndarray, periods_per_year: float = 252.0) -> float:
    if len(dr) == 0:
        return float("nan")
    return float(np.prod(1.0 + dr) ** (periods_per_year / len(dr)) - 1.0)


def _drop_year_cut(dr: pd.Series, bret: pd.Series, year: int) -> dict:
    keep = dr.index.year != year
    d = dr[keep].to_numpy()
    b = bret[keep].to_numpy()
    return {
        "strategy": _cagr_from_returns(d),
        "benchmark": _cagr_from_returns(b),
        "days": int(len(d)),
    }


def _drop_best_days(dr: pd.Series, bret: pd.Series, n: int = 10) -> dict:
    idx = np.argsort(dr.to_numpy())[-n:]
    d = dr.to_numpy().copy()
    d[idx] = 0.0
    b = bret.to_numpy().copy()
    # also remove the same calendar days from the benchmark for comparability
    b[idx] = 0.0
    return {"strategy": _cagr_from_returns(d), "benchmark": _cagr_from_returns(b),
            "n_days": int(n)}


def _block_shuffle(w: np.ndarray, nd: int, block: int = 20,
                   draws: int = 200, seed: int = 7) -> np.ndarray:
    rng = np.random.default_rng(seed)
    out = np.empty((draws, nd), dtype=float)
    for j in range(draws):
        nblocks = int(np.ceil(nd / block))
        starts = rng.integers(0, nd, nblocks)
        idx = np.concatenate([(np.arange(s, s + block) % nd) for s in starts])[:nd]
        out[j] = w[idx]
    return out


def _shift_placebo(parts: dict, params: dict, nd: int, draws: int = 200,
                   seed: int = 11) -> np.ndarray:
    """Circularly shift the term-structure component, keep the trend sleeve."""
    rng = np.random.default_rng(seed)
    trend = parts["trend"]
    calm = parts["calm"]
    spike = _binarize(parts["spike"])
    tw = float(params["trend_w"])
    out = np.empty((draws, nd), dtype=float)
    for j in range(draws):
        k = int(rng.integers(20, nd - 20))
        raw = tw * trend + (1.0 - tw) * np.roll(calm, k)
        out[j] = np.where(np.roll(spike, k) > 0.5, 0.0, raw)
    return np.clip(out, 0.0, 1.0)


def _placebo_stats(ts_d, o_d, c_d, weights, cost=HEADLINE_COST):
    Ws = []
    for w in weights:
        W = np.zeros((len(ts_d), len(SYMBOLS)), dtype=float)
        W[:, COL_T] = np.clip(np.nan_to_num(w, nan=0.0), 0.0, 1.0)
        Ws.append(W)
    results = bt.simulate_many(ts_d, o_d, c_d, Ws, band=BAND,
                               slippage_bps=cost, threads=1)
    return [bt.stats(r, 252) for r in results]


def _pct_rank(dist, value):
    d = np.asarray(dist, dtype=float)
    return float((np.sum(d < value) + 0.5 * np.sum(d == value)) / len(d))


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def main() -> dict:
    print("loading 1-minute panel (development window only) ...", flush=True)
    ts, o, c = bt.panel(SYMBOLS, START, END, "1min", warmup_days=0)
    if ts[-1] >= pd.Timestamp("2024-01-01", tz="America/New_York"):
        raise RuntimeError("panel crossed the development boundary")
    i0 = bt.start_index(ts, START)
    print(f"  {len(ts):,} bars  {ts[0]} .. {ts[-1]}", flush=True)

    bench = _benchmark(ts[i0:], c[i0:])
    print(f"  TQQQ buy&hold: CAGR {bench['cagr']*100:.2f}%  DD "
          f"{bench['max_drawdown']*100:.2f}%  Sharpe {bench['sharpe']:.2f}", flush=True)

    # ---- primary at three cost levels -------------------------------------
    print("primary ...", flush=True)
    W_primary, w_daily_1m, parts_1m, sdates_1m = build_weights(
        ts, o, c, PRIMARY, return_parts=True)
    headline = {}
    prim_runs = {}
    for cost in COSTS:
        s, r, eq_d, b_d = _metrics(ts, o, c, W_primary, cost=cost)
        headline[f"{cost:g}bp"] = _summary(s)
        prim_runs[cost] = (s, r, eq_d, b_d)
        print(f"  {cost:4.1f} bp: CAGR {s['cagr']*100:6.2f}%  DD "
              f"{s['max_drawdown']*100:5.2f}%  Sharpe {s['sharpe']:4.2f}  "
              f"expo {s['exposure']*100:5.1f}%  corr {s['corr_tqqq']:4.2f}  "
              f"fills {s['fills']}", flush=True)

    s1, r1, eq_d, b_d = prim_runs[HEADLINE_COST]
    yearly = _yearly(r1["ts"], r1["equity"], c[i0:, COL_T])
    yearly_expo = _yearly_exposure(r1["ts"], r1)

    # ---- pre-registered grid ---------------------------------------------
    print("grid ...", flush=True)
    grid = []
    for name, over in GRID:
        p = dict(PRIMARY); p.update(over)
        W = build_weights(ts, o, c, p)
        s, _, _, _ = _metrics(ts, o, c, W, cost=HEADLINE_COST)
        row = {"cell": name, "params": p, **_summary(s)}
        grid.append(row)
        print(f"  {name:14s} CAGR {s['cagr']*100:6.2f}%  DD "
              f"{s['max_drawdown']*100:5.2f}%  Sharpe {s['sharpe']:4.2f}  "
              f"expo {s['exposure']*100:5.1f}%", flush=True)

    # ---- structural ablations --------------------------------------------
    print("ablations ...", flush=True)
    ablations = {}
    ablation_specs = [
        ("primary", {}),
        ("no_spike", {"spike": 1e9}),
        ("no_trend", {"trend_w": 0.0}),
        ("trend_only", {"trend_w": 1.0, "spike": 1e9}),
        ("ts_only", {"trend_w": 0.0, "spike": 1e9}),
        ("trend_plus_spike", {"trend_w": 1.0}),
        ("ts_plus_spike", {"trend_w": 0.0}),
        ("blend_60_40", {"trend_w": 0.60}),
        ("sma120", {"trend_n": 120}),
        ("sma200", {"trend_n": 200}),
        ("rv_10_60", {"rv_short": 10}),
        ("rv_20_90", {"rv_long": 90}),
        ("rv_30_60", {"rv_short": 30}),
        ("tqqq_signal", {"signal_symbol": "TQQQ"}),
    ]
    for name, over in ablation_specs:
        p = dict(PRIMARY); p.update(over)
        W = build_weights(ts, o, c, p)
        s, _, _, _ = _metrics(ts, o, c, W, cost=HEADLINE_COST)
        ablations[name] = {"params": p, **_summary(s)}
        print(f"  {name:18s} CAGR {s['cagr']*100:6.2f}%  DD "
              f"{s['max_drawdown']*100:5.2f}%  Sharpe {s['sharpe']:4.2f}  "
              f"expo {s['exposure']*100:5.1f}%", flush=True)

    # ---- simple-rule comparisons (the honest "does it add?" test) --------
    print("simple rules ...", flush=True)
    rv20 = parts_1m["rv_short"]
    rv60 = parts_1m["rv_long"]
    trend = parts_1m["trend"]
    calm = parts_1m["calm"]
    spike = _binarize(parts_1m["spike"])
    simple = {}

    def _run_w(name, w_daily):
        w = np.clip(np.nan_to_num(w_daily, nan=0.0), 0.0, 1.0)
        W = np.zeros((len(ts), len(SYMBOLS)), dtype=float)
        W[:, COL_T] = _expand_to_bars(ts, w)
        s, _, _, _ = _metrics(ts, o, c, W, cost=HEADLINE_COST)
        simple[name] = _summary(s)
        print(f"  {name:26s} CAGR {s['cagr']*100:6.2f}%  DD "
              f"{s['max_drawdown']*100:5.2f}%  Sharpe {s['sharpe']:4.2f}  "
              f"expo {s['exposure']*100:5.1f}%", flush=True)

    _run_w("vol_target_12", np.minimum(1.0, 0.12 / np.maximum(rv20, 1e-9)))
    _run_w("vol_target_14", np.minimum(1.0, 0.14 / np.maximum(rv20, 1e-9)))
    _run_w("vol_target_16", np.minimum(1.0, 0.16 / np.maximum(rv20, 1e-9)))
    _run_w("vol_level_rv20_lt_20", (rv20 < 0.20).astype(float))
    _run_w("vol_level_rv20_lt_22", (rv20 < 0.22).astype(float))
    _run_w("vol_level_rv60_lt_25", (rv60 < 0.25).astype(float))
    _run_w("trend165", trend)
    _run_w("ts_gate_only", calm * (1.0 - spike))
    _run_w("blend_with_vol_level",
           0.5 * trend + 0.5 * (rv20 < 0.22).astype(float))
    _run_w("blend_with_vol_level_spike",
           (0.5 * trend + 0.5 * (rv20 < 0.22).astype(float)) * (1.0 - spike))

    # BIL idle sleeve (TQQQ + BIL, no cash drag)
    W_bil = W_primary.copy()
    W_bil[:, COL_B] = 1.0 - W_bil[:, COL_T]
    s_bil, _, _, _ = _metrics(ts, o, c, W_bil, cost=HEADLINE_COST)
    bil_idle = _summary(s_bil)
    print(f"  {'BIL idle':26s} CAGR {s_bil['cagr']*100:6.2f}%  DD "
          f"{s_bil['max_drawdown']*100:5.2f}%  Sharpe {s_bil['sharpe']:4.2f}", flush=True)

    # ---- subperiods and cut tests ----------------------------------------
    print("cuts ...", flush=True)
    subperiods = {}
    for name, a, b in (("2016_2019", START, "2019-12-31"),
                       ("2020_2023", "2020-01-02", END),
                       ("2016_2020", START, "2020-12-31"),
                       ("2021_2023", "2021-01-04", END)):
        s, _, _, _ = _metrics(ts, o, c, W_primary, cost=HEADLINE_COST, start=a, end=b)
        subperiods[name] = _summary(s)
        print(f"  {name:12s} CAGR {s['cagr']*100:6.2f}%  DD "
              f"{s['max_drawdown']*100:5.2f}%  Sharpe {s['sharpe']:4.2f}", flush=True)

    dr = eq_d.pct_change().dropna()
    bret = b_d.pct_change().dropna()
    cuts = {}
    for y in range(2016, 2024):
        cuts[f"drop_{y}"] = _drop_year_cut(dr, bret, y)
    cuts["drop_best_10_days"] = _drop_best_days(dr, bret, 10)
    cuts["drop_best_20_days"] = _drop_best_days(dr, bret, 20)

    # ---- placebo ---------------------------------------------------------
    print("placebo (daily marks) ...", flush=True)
    ts_d, o_d, c_d = bt.panel(SYMBOLS, START, END, "1D", warmup_days=0)
    W_d, w_daily_d, parts_d, _ = build_weights(ts_d, o_d, c_d, PRIMARY,
                                               return_parts=True)
    s_act, _, _, _ = _metrics_daily(ts_d, o_d, c_d, W_d, cost=HEADLINE_COST)
    nd = len(w_daily_d)
    nd_d = len(ts_d)
    print(f"  actual daily-mark CAGR {s_act['cagr']*100:.2f}%  "
          f"DD {s_act['max_drawdown']*100:.2f}%", flush=True)

    # Execution-delay diagnostic: an extra k sessions of delay, daily marks.
    # This is a fragility check, not a tradable variant.
    lag_diag = {}
    for k in (0, 1, 2, 3, 5):
        wk = (w_daily_d.copy() if k == 0
              else np.r_[np.zeros(k), w_daily_d[:-k]])
        Wk = np.zeros((len(ts_d), len(SYMBOLS)), dtype=float)
        Wk[:, COL_T] = wk
        sk, _, _, _ = _metrics_daily(ts_d, o_d, c_d, Wk, cost=HEADLINE_COST)
        lag_diag[f"lag_{k}"] = _summary(sk)
        print(f"  lag {k}: CAGR {sk['cagr']*100:6.2f}%  DD "
              f"{sk['max_drawdown']*100:5.2f}%  Sharpe {sk['sharpe']:4.2f}", flush=True)

    block_draws = _block_shuffle(w_daily_d, nd_d, block=20, draws=200)
    block_stats = _placebo_stats(ts_d, o_d, c_d, block_draws)
    block_cagr = np.array([s["cagr"] for s in block_stats])
    block_dd = np.array([s["max_drawdown"] for s in block_stats])
    block_sharpe = np.array([s["sharpe"] for s in block_stats])
    block_expo = np.array([s["exposure"] for s in block_stats])

    shift_draws = _shift_placebo(parts_d, PRIMARY, nd_d, draws=200)
    shift_stats = _placebo_stats(ts_d, o_d, c_d, shift_draws)
    shift_cagr = np.array([s["cagr"] for s in shift_stats])
    shift_dd = np.array([s["max_drawdown"] for s in shift_stats])
    shift_sharpe = np.array([s["sharpe"] for s in shift_stats])

    placebo = {
        "block_shuffle_20d": {
            "draws": 200,
            "actual_cagr": float(s_act["cagr"]),
            "actual_dd": float(s_act["max_drawdown"]),
            "actual_sharpe": float(s_act["sharpe"]),
            "actual_exposure": float(s_act["exposure"]),
            "cagr_pct_rank": _pct_rank(block_cagr, s_act["cagr"]),
            "cagr_mean": float(np.mean(block_cagr)),
            "cagr_p05": float(np.percentile(block_cagr, 5)),
            "cagr_p50": float(np.percentile(block_cagr, 50)),
            "cagr_p95": float(np.percentile(block_cagr, 95)),
            "dd_median": float(np.median(block_dd)),
            "sharpe_median": float(np.median(block_sharpe)),
            "exposure_mean": float(np.mean(block_expo)),
        },
        "ts_component_shift": {
            "draws": 200,
            "actual_cagr": float(s_act["cagr"]),
            "cagr_pct_rank": _pct_rank(shift_cagr, s_act["cagr"]),
            "cagr_mean": float(np.mean(shift_cagr)),
            "cagr_p05": float(np.percentile(shift_cagr, 5)),
            "cagr_p50": float(np.percentile(shift_cagr, 50)),
            "cagr_p95": float(np.percentile(shift_cagr, 95)),
            "dd_median": float(np.median(shift_dd)),
            "sharpe_median": float(np.median(shift_sharpe)),
        },
    }
    print(f"  block-shuffle rank {placebo['block_shuffle_20d']['cagr_pct_rank']:.3f}  "
          f"(actual {s_act['cagr']*100:.2f}% vs median "
          f"{np.median(block_cagr)*100:.2f}%)", flush=True)
    print(f"  TS-shift rank      {placebo['ts_component_shift']['cagr_pct_rank']:.3f}  "
          f"(median {np.median(shift_cagr)*100:.2f}%)", flush=True)

    # ---- concentration diagnostics --------------------------------------
    top10 = np.sort(dr.to_numpy())[-10:]
    top10_sum = float(np.sum(np.log1p(top10)))
    total_log = float(np.sum(np.log1p(dr.to_numpy())))
    concentration = {
        "top10_log_share_of_total": top10_sum / total_log if total_log != 0 else None,
        "best_day": float(top10[-1]),
        "worst_day": float(np.min(dr.to_numpy())),
        "positive_day_fraction": float(np.mean(dr.to_numpy() > 0)),
    }

    result = {
        "meta": {
            "slug": "vol-term-structure",
            "window": {"start": START, "end": END},
            "bar": {"cagr": 0.3672, "max_drawdown": 0.8229, "sharpe": 0.82,
                    "source": "lead-provided TQQQ 1-minute-mark development bar"},
            "harness_benchmark": _summary(bench),
            "primary_params": PRIMARY,
            "band": BAND,
            "headline_cost_bp": HEADLINE_COST,
            "costs_bp": list(COSTS),
            "bars_per_year": BARS_1M,
            "grid": [name for name, _ in GRID],
            "notes": "Development window only; no 2024+ data loaded. "
                     "Signals use QQQ adjusted daily closes through the prior "
                     "session close; fills at the next session open.",
        },
        "benchmark": _summary(bench),
        "headline": headline,
        "yearly": yearly,
        "yearly_exposure": yearly_expo,
        "grid": grid,
        "ablations": ablations,
        "simple_rules": simple,
        "bil_idle": bil_idle,
        "subperiods": subperiods,
        "cuts": cuts,
        "placebo": placebo,
        "lag_diagnostic": lag_diag,
        "concentration": concentration,
    }
    result = _round(result)
    out_path = HERE / "result.json"
    with open(out_path, "w") as fh:
        json.dump(result, fh, indent=2, sort_keys=False)
    print(f"wrote {out_path}", flush=True)
    return result


if __name__ == "__main__":
    main()
