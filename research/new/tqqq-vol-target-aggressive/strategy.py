r"""Aggressive always-long TQQQ volatility target with a fast crash brake.

Development-window strategy (2016-01-04 .. 2023-12-29).  The 2024-2026
holdout is not loaded, inspected or used for selection.

    base_t  = clip(target_vol / sigma_t, 0, 1)        # high nominal target
    dd15_t  = 1 - C_t / max(C_{t-14..t})              # fast drawdown state
    brake_t = clip(1 - (dd15_t - 0.06)/(0.12 - 0.06), 0.25, 1)
    w_t     = EMA_3(base_t * brake_t)                 # causal, span 3
    BIL     = 1 - w_t

The weight is set from the close of session t and filled at the open of t+1.
There is no slow trend gate, no moving-average regime and no shorting.

Run from the repo root:
    $env:PYTHONPATH = "C:\Users\27175\AppData\Local\Temp\opencode\pylibs"
    $env:BT_THREADS = "1"
    python research/new/tqqq-vol-target-aggressive/strategy.py
"""
from __future__ import annotations

import json
import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402

DEV_START, DEV_END = "2016-01-04", "2023-12-29"
SYMS = ("QQQ", "TQQQ", "BIL")
BAND = 0.02
BARS_1M = 252 * 390
BARS_1D = 252
TZ = "America/New_York"
DATA = ROOT / "data" / "intraday-hf"

BAR_CAGR = 0.3672
BAR_DD = 0.8229
BAR_SHARPE = 0.82
FULL_BAR_CAGR = 0.3754
FULL_BAR_DD = 0.8168
FULL_START = "2016-01-04"
FULL_END = "2026-10-23"
HOLD_START = "2024-01-02"

# Fixed fast crash brake used by every cell of the pre-registered grid.
BRAKE = dict(dd_window=15, dd_start=0.06, dd_end=0.12, dd_floor=0.25)
SMOOTH = 3

GRID = {
    "rv20_t080": dict(estimator="rv", window=20, target=0.80, smooth=SMOOTH, **BRAKE),
    "rv20_t090": dict(estimator="rv", window=20, target=0.90, smooth=SMOOTH, **BRAKE),
    "rv20_t100": dict(estimator="rv", window=20, target=1.00, smooth=SMOOTH, **BRAKE),
    "rv10_t080": dict(estimator="rv", window=10, target=0.80, smooth=SMOOTH, **BRAKE),
    "rv60_t080": dict(estimator="rv", window=60, target=0.80, smooth=SMOOTH, **BRAKE),
    "park20_t080": dict(estimator="park", window=20, target=0.80, smooth=SMOOTH, **BRAKE),
    "ewma_t080": dict(estimator="ewma", window=20, target=0.80, smooth=SMOOTH, **BRAKE),
    "rv20_t080_nocut": dict(estimator="rv", window=20, target=0.80, smooth=SMOOTH,
                            dd_window=15, dd_start=0.06, dd_end=0.12,
                            dd_floor=0.25, cut=False),
}
PRIMARY = "rv20_t080"
CANDIDATE = PRIMARY
BASE = dict(GRID[CANDIDATE])

# Out-of-grid diagnostics; never used to choose the primary.
TARGET_SWEEP = {
    "rv20_t070": dict(estimator="rv", window=20, target=0.70, smooth=SMOOTH, **BRAKE),
    "rv20_t075": dict(estimator="rv", window=20, target=0.75, smooth=SMOOTH, **BRAKE),
    "rv20_t085": dict(estimator="rv", window=20, target=0.85, smooth=SMOOTH, **BRAKE),
    "rv20_t095": dict(estimator="rv", window=20, target=0.95, smooth=SMOOTH, **BRAKE),
}
ESTIMATOR_SWEEP = {
    "rv5_t080": dict(estimator="rv", window=5, target=0.80, smooth=SMOOTH, **BRAKE),
    "rv120_t080": dict(estimator="rv", window=120, target=0.80, smooth=SMOOTH, **BRAKE),
    "park10_t080": dict(estimator="park", window=10, target=0.80, smooth=SMOOTH, **BRAKE),
    "park60_t080": dict(estimator="park", window=60, target=0.80, smooth=SMOOTH, **BRAKE),
    "blend_t080": dict(estimator="blend", window=20, target=0.80, smooth=SMOOTH, **BRAKE),
}
BRAKE_SWEEP = {
    "h10": dict(estimator="rv", window=20, target=0.80, smooth=SMOOTH,
                dd_window=10, dd_start=0.06, dd_end=0.12, dd_floor=0.25),
    "h20": dict(estimator="rv", window=20, target=0.80, smooth=SMOOTH,
                dd_window=20, dd_start=0.06, dd_end=0.12, dd_floor=0.25),
    "h30": dict(estimator="rv", window=20, target=0.80, smooth=SMOOTH,
                dd_window=30, dd_start=0.06, dd_end=0.12, dd_floor=0.25),
    "s05f20": dict(estimator="rv", window=20, target=0.80, smooth=SMOOTH,
                   dd_window=15, dd_start=0.05, dd_end=0.12, dd_floor=0.20),
    "s06e15f25": dict(estimator="rv", window=20, target=0.80, smooth=SMOOTH,
                      dd_window=15, dd_start=0.06, dd_end=0.15, dd_floor=0.25),
    "s08f30": dict(estimator="rv", window=20, target=0.80, smooth=SMOOTH,
                   dd_window=15, dd_start=0.08, dd_end=0.12, dd_floor=0.30),
    "s04f10": dict(estimator="rv", window=20, target=0.80, smooth=SMOOTH,
                   dd_window=15, dd_start=0.04, dd_end=0.12, dd_floor=0.10),
    "s10f40": dict(estimator="rv", window=20, target=0.80, smooth=SMOOTH,
                   dd_window=15, dd_start=0.10, dd_end=0.20, dd_floor=0.40),
}
SMOOTH_SWEEP = {
    "raw_no_ema": dict(estimator="rv", window=20, target=0.80, smooth=0, **BRAKE),
    "ema2": dict(estimator="rv", window=20, target=0.80, smooth=2, **BRAKE),
    "ema5": dict(estimator="rv", window=20, target=0.80, smooth=5, **BRAKE),
}
BLENDS = (0.60, 0.70, 0.75, 0.80, 0.85, 0.90, 0.95, 1.00)
CUTS = ("2018-12-31", "2020-03-12", "2021-12-31", "2022-09-13")
CUT_TS = ("2018-12-31 15:59", "2020-03-12 11:07", "2021-12-31 15:59",
          "2022-09-13 15:59")
EPISODES = (
    ("2018Q4", "2018-09-20", "2018-12-24"),
    ("covid_crash", "2020-02-19", "2020-03-23"),
    ("covid_recovery", "2020-03-23", "2021-11-19"),
    ("2022_bear", "2022-01-03", "2022-12-28"),
    ("2023_recovery", "2023-01-03", "2023-12-29"),
)

_DAILY_CACHE: dict = {}


def _f(x):
    if x is None:
        return None
    x = float(x)
    return x if np.isfinite(x) else None


def _ts(x: str) -> pd.Timestamp:
    return pd.Timestamp(x, tz=TZ)


# --------------------------------------------------------------------------- #
# Daily signal data
# --------------------------------------------------------------------------- #
def load_daily(end: str | pd.Timestamp | date = DEV_END) -> pd.DataFrame:
    """Adjusted TQQQ daily OHLC, read only through `end` (inclusive)."""
    end_day = pd.Timestamp(end).date()
    key = end_day
    if key in _DAILY_CACHE:
        return _DAILY_CACHE[key]
    read_to = end_day + timedelta(days=1)
    df = pd.read_parquet(
        DATA / "TQQQ-1d-yahoo.parquet",
        columns=["date", "open", "high", "low", "close", "adjclose"],
        filters=[("date", "<", read_to)],
    )
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").drop_duplicates("date").reset_index(drop=True)
    factor = (df["adjclose"] / df["close"]).to_numpy(float)
    for col in ("open", "high", "low", "close"):
        df[col] = df[col].to_numpy(float) * factor
    df = df.set_index("date")[["open", "high", "low", "close"]]
    df = df.loc[df.index <= pd.Timestamp(end_day)]
    _DAILY_CACHE[key] = df
    return df


def estimate_vol(df: pd.DataFrame, kind: str, window: int) -> pd.Series:
    """Causal annualised volatility, all data through each row's close."""
    lr = np.log(df["close"]).diff()
    if kind == "rv":
        return lr.rolling(window, min_periods=window).std(ddof=1) * np.sqrt(252.0)
    if kind == "park":
        hl2 = np.log(df["high"] / df["low"]) ** 2
        var = hl2.rolling(window, min_periods=window).mean() / (4.0 * np.log(2.0))
        return np.sqrt(var * 252.0)
    if kind == "ewma":
        var = lr.pow(2).ewm(alpha=0.06, adjust=False, min_periods=window).mean()
        return np.sqrt(var * 252.0)
    if kind == "blend":
        a = estimate_vol(df, "rv", 10)
        b = estimate_vol(df, "rv", 60)
        return np.sqrt(0.5 * a.pow(2) + 0.5 * b.pow(2))
    raise ValueError(f"unknown estimator {kind}")


def daily_weights(df: pd.DataFrame, p: dict) -> pd.Series:
    """Daily TQQQ target weight, computed at each session's close."""
    vol = estimate_vol(df, p["estimator"], int(p["window"]))
    base = np.minimum(float(p["target"]) / vol.to_numpy(float), 1.0)
    base = np.where(np.isfinite(base), base, 0.0)
    if p.get("cut", True):
        hi = df["close"].rolling(int(p["dd_window"])).max()
        dd = 1.0 - df["close"] / hi
        brake = np.clip(1.0 - (dd.to_numpy(float) - p["dd_start"])
                        / (p["dd_end"] - p["dd_start"]), p["dd_floor"], 1.0)
        brake = np.where(np.isfinite(brake), brake, 1.0)
    else:
        brake = np.ones(len(df))
    w = pd.Series(base * brake, index=df.index)
    if p.get("smooth", 0):
        w = w.ewm(span=int(p["smooth"]), adjust=False).mean()
    return w


# --------------------------------------------------------------------------- #
# Weight construction (required entry point)
# --------------------------------------------------------------------------- #
def build_weights(ts, o, c, params: dict | None = None) -> np.ndarray:
    """Panel -> (n, 3) TQQQ/BIL weights, causal and next-open ready.

    The signal is loaded only through the session before the panel's last
    session, so a truncated panel cannot change any pre-cut weight.  Session
    j's target is the signal at j-1; the last bar of session j-1 carries it so
    the fill happens at the first bar's open of session j.
    """
    p = dict(BASE)
    if params:
        p.update(params)
    ts = pd.DatetimeIndex(ts)
    if len(ts) == 0:
        return np.zeros((0, 3))
    dates, first, last = bt.day_bounds(ts)
    sess = pd.DatetimeIndex(pd.to_datetime(dates[last]))
    signal_end = sess[-2] if len(sess) > 1 else sess[0] - pd.Timedelta(days=1)
    df = load_daily(signal_end)
    wd = daily_weights(df, p)
    at = wd.reindex(sess, method="ffill")
    prev = at.shift(1)
    before = wd[wd.index < sess[0]]
    prev.iloc[0] = float(before.iloc[-1]) if len(before) else 0.0
    counts = last - first + 1
    w_bar = np.repeat(prev.to_numpy(float), counts)
    w_bar = np.roll(w_bar, -1)
    w_bar[-1] = prev.to_numpy(float)[-1]
    w_bar = np.clip(w_bar, 0.0, 1.0)
    W = np.zeros((len(ts), 3))
    W[:, 1] = w_bar
    W[:, 2] = 1.0 - w_bar
    return W


def daily_panel_weights(tsd, p: dict) -> np.ndarray:
    """Weights for a 1D panel, same next-open convention as build_weights."""
    return build_weights(tsd, np.zeros((len(tsd), 3)), np.zeros((len(tsd), 3)), p)


# --------------------------------------------------------------------------- #
# Metrics
# --------------------------------------------------------------------------- #
def _daily_returns(r: dict):
    dates = bt.session_dates(r["ts"])
    _, last = bt.day_bounds_from_dates(dates)
    eq = r["equity"][last]
    idx = pd.DatetimeIndex(pd.to_datetime(dates[last]))
    return pd.Series(np.diff(eq) / eq[:-1], index=idx[1:]), eq, idx


def _path_stats(rets: pd.Series) -> dict:
    eq = np.r_[1.0, np.cumprod(1.0 + rets.to_numpy(float))]
    years = (rets.index[-1] - rets.index[0]).days / 365.25
    if years <= 0 or eq[-1] <= 0:
        return dict(cagr=None, max_drawdown=None, sharpe=None)
    dd = -(eq / np.maximum.accumulate(eq) - 1.0).min()
    sd = float(rets.std(ddof=0))
    return dict(
        cagr=_f(eq[-1] ** (1.0 / years) - 1.0),
        max_drawdown=_f(dd),
        sharpe=_f(float(rets.mean()) / sd * np.sqrt(252.0)) if sd > 0 else None,
    )


def metrics(ts, o, c, W, start: str = DEV_START, slip: float = 1.0,
            bars: float = BARS_1M) -> tuple[dict, dict]:
    r = bt.run(ts, o, c, W, start=start, band=BAND, slippage_bps=slip)
    s = bt.stats(r, bars)
    i0 = bt.start_index(ts, start)
    w = np.asarray(W[i0:, 1], dtype=float)

    dret, deq, ddates = _daily_returns(r)
    _, _, last = bt.day_bounds(r["ts"])
    tq = c[i0:, 1][last]
    tr = np.diff(tq) / tq[:-1]
    corr = float(np.corrcoef(dret.to_numpy(float), tr)[0, 1]) if len(tr) > 2 else 0.0

    eq = r["equity"]
    peak = np.maximum.accumulate(eq)
    dd = eq / peak - 1.0
    tr_i = int(np.argmin(dd))
    pk_i = int(np.argmax(eq[:tr_i + 1]))
    worst = dret.nsmallest(5)

    yearly = {}
    prev_s = float(deq[0])
    prev_t = float(tq[0])
    for y in sorted(set(ddates.year)):
        m = ddates.year == y
        es = float(deq[m][-1])
        et = float(tq[m][-1])
        yearly[str(int(y))] = {"strategy": _f(es / prev_s - 1.0),
                               "tqqq": _f(et / prev_t - 1.0)}
        prev_s, prev_t = es, et

    out = dict(
        cagr=_f(s["cagr"]),
        max_drawdown=_f(s["max_drawdown"]),
        sharpe=_f(s["sharpe"]),
        sortino=_f(s["sortino"]),
        volatility=_f(s["volatility"]),
        calmar=_f(s["cagr"] / s["max_drawdown"]) if s["max_drawdown"] > 0 else None,
        tqqq_exposure=_f(np.mean(w)),
        min_weight=_f(np.min(w)),
        pct_full=_f(np.mean(w >= 0.99)),
        pct_below_80=_f(np.mean(w < 0.80)),
        pct_below_50=_f(np.mean(w < 0.50)),
        fills=int(s["fills"]),
        turnover=_f(s["turnover"]),
        corr_tqqq=corr,
        max_dd_peak=str(ts[i0:][pk_i])[:19],
        max_dd_trough=str(ts[i0:][tr_i])[:19],
        ending_equity=_f(s["ending_equity"]),
        years=_f(s["years"]),
        yearly=yearly,
        worst_days={str(d.date()): _f(v) for d, v in worst.items()},
    )
    return out, r


def daily_marks(tsd, od, cd, p: dict, slip: float = 1.0) -> dict:
    W = daily_panel_weights(tsd, p)
    m, _ = metrics(tsd, od, cd, W, slip=slip, bars=BARS_1D)
    return {k: m[k] for k in ("cagr", "max_drawdown", "sharpe", "tqqq_exposure")}


def slice_metrics(r: dict, a: str, b: str) -> dict:
    m = (r["ts"] >= _ts(a)) & (r["ts"] < _ts(b))
    e = r["equity"][m]
    t = r["ts"][m]
    if len(e) < 2:
        return {}
    years = (t[-1] - t[0]).total_seconds() / (365.25 * 86400.0)
    rets = np.diff(e) / e[:-1]
    sd = float(np.std(rets))
    return dict(
        cagr=_f((e[-1] / e[0]) ** (1.0 / years) - 1.0) if e[0] > 0 else None,
        max_drawdown=_f(float(-(e / np.maximum.accumulate(e) - 1.0).min())),
        sharpe=_f(float(np.mean(rets)) / sd * np.sqrt(BARS_1M)) if sd > 0 else None,
        years=_f(years),
    )


# --------------------------------------------------------------------------- #
# Placebos
# --------------------------------------------------------------------------- #
def placebo_block(tsd, od, cd, w_dev: np.ndarray, real_stats: dict,
                  n_draws: int = 500, seed: int = 7) -> dict:
    n = len(tsd)
    const = float(np.mean(w_dev))
    Wc = np.zeros((n, 3))
    Wc[:, 1] = const
    Wc[:, 2] = 1.0 - const
    rc = bt.run(tsd, od, cd, Wc, start=DEV_START, band=BAND, slippage_bps=1.0)
    const_stats = _path_stats(_daily_returns(rc)[0])

    rng = np.random.default_rng(seed)
    shifts = rng.integers(60, n - 60, size=n_draws)
    Wlist = []
    for k in shifts:
        Wk = np.zeros((n, 3))
        wk = np.roll(w_dev, int(k))
        Wk[:, 1] = wk
        Wk[:, 2] = 1.0 - wk
        Wlist.append(Wk)
    results = bt.run_many(tsd, od, cd, Wlist, start=DEV_START, band=BAND,
                          slippage_bps=1.0, threads=1)
    pstats = [_path_stats(_daily_returns(x)[0]) for x in results]
    pc = np.array([s["cagr"] for s in pstats], dtype=float)
    pdd = np.array([s["max_drawdown"] for s in pstats], dtype=float)
    ps = np.array([s["sharpe"] for s in pstats], dtype=float)

    lags = {}
    for k in (5, 20, 60):
        wk = np.r_[np.full(k, w_dev[0]), w_dev[:-k]]
        Wk = np.zeros((n, 3))
        Wk[:, 1] = wk
        Wk[:, 2] = 1.0 - wk
        rk = bt.run(tsd, od, cd, Wk, start=DEV_START, band=BAND,
                    slippage_bps=1.0)
        lags[str(k)] = _path_stats(_daily_returns(rk)[0])

    return dict(
        marks="daily",
        matched_constant=dict(weight=_f(const), **const_stats),
        circular_shift=dict(
            draws=int(n_draws),
            cagr_mean=_f(pc.mean()),
            cagr_p05=_f(np.percentile(pc, 5)),
            cagr_p50=_f(np.percentile(pc, 50)),
            cagr_p95=_f(np.percentile(pc, 95)),
            dd_mean=_f(pdd.mean()),
            dd_p50=_f(np.percentile(pdd, 50)),
            sharpe_p50=_f(np.percentile(ps, 50)),
            frac_cagr_ge_real=_f(np.mean(pc >= real_stats["cagr"])),
            frac_both_ge_real=_f(np.mean(
                (pc >= real_stats["cagr"])
                & (pdd <= real_stats["max_drawdown"]))),
        ),
        lag=lags,
    )


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main() -> None:
    print("loading panels (development window only)", flush=True)
    ts1, o1, c1 = bt.panel(SYMS, DEV_START, DEV_END, "1min", warmup_days=0)
    tsd, od, cd = bt.panel(SYMS, DEV_START, DEV_END, "1D", warmup_days=0)
    i1 = bt.start_index(ts1, DEV_START)
    print(f"  1m {len(ts1):,} bars  {ts1[0]} .. {ts1[-1]}", flush=True)
    print(f"  1d {len(tsd):,} bars  {tsd[0]} .. {tsd[-1]}", flush=True)

    bench = dict(
        tqqq_1m=bt.benchmark(c1[i1:, 1], ts1[i1:], BARS_1M),
        tqqq_1d=bt.benchmark(cd[:, 1], tsd, BARS_1D),
        qqq_1m=bt.benchmark(c1[i1:, 0], ts1[i1:], BARS_1M),
    )
    for k, v in bench.items():
        print(f"  bench {k}: CAGR {v['cagr']*100:.2f}%  DD {v['max_drawdown']*100:.2f}%"
              f"  Sharpe {v['sharpe']:.2f}", flush=True)

    # ---- pre-registered grid ------------------------------------------------
    print("\n== grid (8 cells, 1m marks, 1 bp) ==", flush=True)
    grid = {}
    Wcand = rcand = rdcand = wd_cand = None
    for name, p in GRID.items():
        W = build_weights(ts1, o1, c1, p)
        m, r = metrics(ts1, o1, c1, W, slip=1.0)
        m["daily_marks_1bp"] = daily_marks(tsd, od, cd, p)
        grid[name] = m
        print(f"  {name:16s} CAGR {m['cagr']*100:6.2f}%  DD {m['max_drawdown']*100:5.2f}%"
              f"  Sharpe {m['sharpe']:4.2f}  TQQQ {m['tqqq_exposure']*100:5.1f}%"
              f"  fills {m['fills']:,}", flush=True)
        if name == CANDIDATE:
            Wcand, rcand = W, r
            wd_cand = daily_weights(load_daily(DEV_END), p)

    cand = grid[CANDIDATE]
    costs = {}
    for slip in (5.0, 10.0):
        costs[f"{int(slip)}bp"], _ = metrics(ts1, o1, c1, Wcand, slip=slip)
    print(f"  candidate 5bp  CAGR {costs['5bp']['cagr']*100:6.2f}%  DD "
          f"{costs['5bp']['max_drawdown']*100:5.2f}%", flush=True)
    print(f"  candidate 10bp CAGR {costs['10bp']['cagr']*100:6.2f}%  DD "
          f"{costs['10bp']['max_drawdown']*100:5.2f}%", flush=True)

    # ---- plateau ------------------------------------------------------------
    passing = [k for k, m in grid.items()
               if m["cagr"] > BAR_CAGR and m["max_drawdown"] < BAR_DD]
    dd60 = [k for k, m in grid.items() if m["max_drawdown"] < 0.60]
    cagrs = [m["cagr"] for m in grid.values()]
    dds = [m["max_drawdown"] for m in grid.values()]
    best_cagr = max(grid, key=lambda k: grid[k]["cagr"])
    plateau = dict(
        cells=len(grid),
        passing=len(passing),
        passing_ids=passing,
        meets_dd60_ids=dd60,
        cagr_min=_f(min(cagrs)),
        cagr_max=_f(max(cagrs)),
        dd_min=_f(min(dds)),
        dd_max=_f(max(dds)),
        primary_is_best_cagr=(best_cagr == PRIMARY),
        candidate_is_best_cagr=(best_cagr == CANDIDATE),
        best_cagr_id=best_cagr,
        candidate=dict(cagr=cand["cagr"], max_drawdown=cand["max_drawdown"]),
        pre_registered_primary=dict(cagr=cand["cagr"],
                                    max_drawdown=cand["max_drawdown"]),
    )
    print(f"\n  plateau: {len(passing)}/{len(grid)} pass  "
          f"CAGR {plateau['cagr_min']*100:.2f}-{plateau['cagr_max']*100:.2f}%  "
          f"DD {plateau['dd_min']*100:.2f}-{plateau['dd_max']*100:.2f}%", flush=True)

    # ---- neighbours ---------------------------------------------------------
    print("\n== neighbours (1m marks, 1 bp) ==", flush=True)
    neighbours = {}
    for name, p in {**TARGET_SWEEP, **ESTIMATOR_SWEEP, **BRAKE_SWEEP,
                    **SMOOTH_SWEEP}.items():
        W = build_weights(ts1, o1, c1, p)
        m, _ = metrics(ts1, o1, c1, W, slip=1.0)
        neighbours[name] = m
        print(f"  {name:14s} CAGR {m['cagr']*100:6.2f}%  DD {m['max_drawdown']*100:5.2f}%"
              f"  Sharpe {m['sharpe']:4.2f}  TQQQ {m['tqqq_exposure']*100:5.1f}%", flush=True)

    # ---- binary and vol-acceleration cut rivals ------------------------------
    print("\n== cut-shape rivals (1m marks, 1 bp) ==", flush=True)
    rivals = {}
    df_sig = load_daily(DEV_END)
    vol20 = estimate_vol(df_sig, "rv", 20)
    lr = np.log(df_sig["close"]).diff()
    rv5 = lr.rolling(5).std(ddof=1) * np.sqrt(252.0)
    base_series = np.minimum(0.80 / vol20.to_numpy(float), 1.0)
    base_series = np.where(np.isfinite(base_series), base_series, 0.0)
    hi15 = df_sig["close"].rolling(15).max()
    dd15 = (1.0 - df_sig["close"] / hi15).to_numpy(float)
    brake_bin = np.where(dd15 >= 0.12, 0.25, 1.0)
    brake_acc = np.where((rv5.to_numpy(float) > 1.5 * vol20.to_numpy(float))
                         & (rv5.to_numpy(float) > 0.70), 0.30, 1.0)
    for name, brake in (("binary_dd12", brake_bin), ("volaccel", brake_acc)):
        w = pd.Series(base_series * brake, index=df_sig.index)
        w = w.ewm(span=SMOOTH, adjust=False).mean()
        W = build_weights(ts1, o1, c1, dict(BASE))
        # replace the TQQQ weight with this rival series via the same mapping
        wm = pd.Series(w, index=df_sig.index)
        dates, first, last = bt.day_bounds(ts1)
        sess = pd.DatetimeIndex(pd.to_datetime(dates[last]))
        at = wm.reindex(sess, method="ffill")
        prev = at.shift(1)
        before = wm[wm.index < sess[0]]
        prev.iloc[0] = float(before.iloc[-1]) if len(before) else 0.0
        wb = np.repeat(prev.to_numpy(float), last - first + 1)
        wb = np.roll(wb, -1)
        wb[-1] = prev.to_numpy(float)[-1]
        W[:, 1] = np.clip(wb, 0.0, 1.0)
        W[:, 2] = 1.0 - W[:, 1]
        m, _ = metrics(ts1, o1, c1, W, slip=1.0)
        rivals[name] = m
        print(f"  {name:14s} CAGR {m['cagr']*100:6.2f}%  DD {m['max_drawdown']*100:5.2f}%"
              f"  Sharpe {m['sharpe']:4.2f}  TQQQ {m['tqqq_exposure']*100:5.1f}%", flush=True)

    # ---- constant blends ----------------------------------------------------
    print("\n== constant TQQQ blends ==", flush=True)
    blends = {}
    n1 = len(ts1)
    for b in BLENDS:
        W = np.zeros((n1, 3))
        W[:, 1] = b
        W[:, 2] = 1.0 - b
        m, _ = metrics(ts1, o1, c1, W, slip=1.0)
        blends[f"{int(round(b*100))}pct"] = m
        print(f"  {int(round(b*100)):3d}% TQQQ  CAGR {m['cagr']*100:6.2f}%  "
              f"DD {m['max_drawdown']*100:5.2f}%  Sharpe {m['sharpe']:4.2f}", flush=True)

    # ---- placebos -----------------------------------------------------------
    print("\n== placebos (daily marks, 500 circular shifts) ==", flush=True)
    dates_d = pd.DatetimeIndex(pd.to_datetime(bt.session_dates(tsd)))
    w_dev = wd_cand.reindex(dates_d, method="ffill").to_numpy(float)
    w_dev = np.where(np.isfinite(w_dev), w_dev, 0.0)
    r_daily = bt.run(tsd, od, cd, daily_panel_weights(tsd, BASE),
                     start=DEV_START, band=BAND, slippage_bps=1.0)
    real_daily = _path_stats(_daily_returns(r_daily)[0])
    placebo = placebo_block(tsd, od, cd, w_dev, real_daily)
    placebo["real"] = real_daily
    cs = placebo["circular_shift"]
    print(f"  real daily {real_daily}", flush=True)
    print(f"  matched constant {placebo['matched_constant']}", flush=True)
    print(f"  circular shift {cs}", flush=True)
    print(f"  lag {placebo['lag']}", flush=True)

    # ---- cut tests ----------------------------------------------------------
    print("\n== cut tests ==", flush=True)
    causal = {}
    for cut in CUT_TS:
        j = int(ts1.searchsorted(_ts(cut)))
        Wp = build_weights(ts1[:j], o1[:j], c1[:j], GRID[CANDIDATE])
        diff_m = float(np.max(np.abs(Wp - Wcand[:j]))) if j else 0.0
        jd = int(tsd.searchsorted(_ts(cut).normalize()))
        Wdp = daily_panel_weights(tsd[:jd], GRID[CANDIDATE])
        Wdf = daily_panel_weights(tsd, GRID[CANDIDATE])
        # The last daily bar carries the next session's target; a panel cut at
        # that session cannot contain that target, so compare all earlier bars.
        diff_d = (float(np.max(np.abs(Wdp[:-1] - Wdf[:jd - 1])))
                  if jd > 1 else 0.0)
        causal[cut] = dict(minute_bars=j, minute_max_abs_diff=_f(diff_m),
                           daily_dates=jd, daily_max_abs_diff=_f(diff_d),
                           pass_=bool(diff_m <= 1e-12 and diff_d <= 1e-12))
        print(f"  causal {cut}: {causal[cut]}", flush=True)

    dret, _, _ = _daily_returns(rcand)
    perf_cuts = {}
    for label, year in (("ex_best_year", None), ("ex_2020", 2020), ("ex_2022", 2022)):
        r2 = dret.copy()
        if label == "ex_best_year":
            yrs = sorted(set(dret.index.year))
            by = {y: float((1.0 + dret[dret.index.year == y]).prod() - 1.0)
                  for y in yrs}
            best = max(by, key=by.get)
            r2[dret.index.year == best] = 0.0
            perf_cuts[label] = dict(year=int(best), year_return=_f(by[best]),
                                    **{k: v for k, v in _path_stats(r2).items()})
        else:
            r2[dret.index.year == year] = 0.0
            perf_cuts[label] = _path_stats(r2)
    r2 = dret.copy()
    r2[dret.nlargest(20).index] = 0.0
    perf_cuts["ex_best_20_sessions"] = _path_stats(r2)
    for label in ("ex_2020", "ex_2022", "ex_best_20_sessions"):
        print(f"  {label}: {perf_cuts[label]}", flush=True)
    print(f"  {perf_cuts['ex_best_year']}", flush=True)

    starts = {}
    for s in ("2017-01-03", "2018-01-02"):
        m, _ = metrics(ts1, o1, c1, Wcand, start=s, slip=1.0)
        starts[s] = {k: m[k] for k in ("cagr", "max_drawdown", "sharpe",
                                       "tqqq_exposure")}
        print(f"  start {s}: CAGR {m['cagr']*100:.2f}%  DD "
              f"{m['max_drawdown']*100:.2f}%", flush=True)

    # ---- subperiods and episodes -------------------------------------------
    sub = {}
    for label, a, b in (("2016_19", "2016-01-04", "2020-01-01"),
                        ("2020_21", "2020-01-01", "2022-01-01"),
                        ("2022_23", "2022-01-01", "2023-12-30")):
        sub[label] = slice_metrics(rcand, a, b)

    eps = {}
    _, deq_p, ddates_p = _daily_returns(rcand)
    deq_p = pd.Series(deq_p, index=ddates_p)
    dfw = load_daily(DEV_END)
    for label, a, b in EPISODES:
        wseg = wd_cand.loc[a:b]
        row = dict(avg_weight=_f(wseg.mean()) if len(wseg) else None,
                   min_weight=_f(wseg.min()) if len(wseg) else None,
                   max_weight=_f(wseg.max()) if len(wseg) else None)
        row["tqqq_return"] = _f(float(dfw["close"].loc[b] / dfw["close"].loc[a] - 1.0))
        row["strategy_return"] = _f(float(deq_p.loc[:b].iloc[-1]
                                          / deq_p.loc[:a].iloc[-1] - 1.0))
        eps[label] = row
    print("\n== episodes ==", flush=True)
    for k, v in eps.items():
        print(f"  {k}: strat {v['strategy_return']*100:7.2f}%  "
              f"TQQQ {v['tqqq_return']*100:7.2f}%  avg w {v['avg_weight']*100:5.1f}%",
              flush=True)

    # ---- diagnostics --------------------------------------------------------
    _, deq_d, ddates_d = _daily_returns(rcand)
    _, _, last_d = bt.day_bounds(rcand["ts"])
    tq_d = c1[i1:, 1][last_d]
    tr_d = np.diff(tq_d) / tq_d[:-1]
    sr_d = dret.to_numpy(float)
    up_d, dn_d = tr_d > 0, tr_d < 0
    s_eq = pd.Series(deq_d, index=ddates_d)
    t_eq = pd.Series(tq_d, index=ddates_d)
    sm = s_eq.resample("ME").last().pct_change().dropna()
    tm = t_eq.resample("ME").last().pct_change().dropna()
    vol_c = estimate_vol(dfw, "rv", 20).reindex(wd_cand.index)
    vol_c = vol_c.loc[DEV_START:DEV_END]
    wd_q = wd_cand.loc[DEV_START:DEV_END]
    qq = pd.qcut(vol_c, 5, labels=False)
    quint = [
        dict(q=int(k), vol_min=_f(vol_c[qq == k].min()),
             vol_max=_f(vol_c[qq == k].max()),
             avg_weight=_f(wd_q[qq == k].mean()),
             n=int((qq == k).sum()))
        for k in range(5)
    ]
    key_dates = {
        dt: dict(vol=_f(vol_c.loc[dt]), weight=_f(wd_cand.loc[dt]))
        for dt in ("2020-02-19", "2020-03-12", "2020-03-23", "2020-04-30",
                   "2021-11-19", "2022-01-03", "2022-06-16", "2022-10-14",
                   "2022-12-28", "2023-01-03", "2023-12-29")
    }
    ep = (pd.Timestamp("2021-11-19"), pd.Timestamp("2023-01-06"))
    dd_ep = dict(
        strategy=_f(float(s_eq.loc[ep[0]:ep[1]].min()
                          / s_eq.loc[ep[0]:ep[1]].cummax().max() - 1.0)),
        tqqq=_f(float(t_eq.loc[ep[0]:ep[1]].min()
                      / t_eq.loc[ep[0]:ep[1]].cummax().max() - 1.0)),
    )
    diag = dict(
        beta_daily=_f(np.polyfit(tr_d, sr_d, 1)[0]),
        corr_daily=_f(np.corrcoef(sr_d, tr_d)[0, 1]),
        vol_strategy_daily=_f(np.std(sr_d, ddof=0) * np.sqrt(252.0)),
        vol_tqqq_daily=_f(np.std(tr_d, ddof=0) * np.sqrt(252.0)),
        up_capture_daily=_f(sr_d[up_d].mean() / tr_d[up_d].mean()),
        down_capture_daily=_f(sr_d[dn_d].mean() / tr_d[dn_d].mean()),
        beta_monthly=_f(np.polyfit(tm, sm, 1)[0]) if len(tm) > 2 else None,
        corr_monthly=_f(np.corrcoef(sm, tm)[0, 1]) if len(tm) > 2 else None,
        up_capture_monthly=_f(sm[sm > 0].mean() / tm[tm > 0].mean()) if (tm > 0).any() else None,
        down_capture_monthly=_f(sm[sm < 0].mean() / tm[tm < 0].mean()) if (tm < 0).any() else None,
        weight_by_vol_quintile=quint,
        key_dates=key_dates,
        dd_2021_11_19_2023_01_06=dd_ep,
        tqqq_yearly={int(y): float(v["tqqq"]) for y, v in cand["yearly"].items()},
        tqqq_ex_2020_cagr=_f(_path_stats(
            pd.Series(tr_d, index=dret.index).where(
                dret.index.year != 2020, 0.0))["cagr"]),
        tqqq_ex_2023_cagr=_f(_path_stats(
            pd.Series(tr_d, index=dret.index).where(
                dret.index.year != 2023, 0.0))["cagr"]),
    )
    full_years = (pd.Timestamp(FULL_END) - pd.Timestamp(FULL_START)).days / 365.25
    hold_years = (pd.Timestamp(FULL_END) - pd.Timestamp(HOLD_START)).days / 365.25
    dev_mult = (1.0 + cand["cagr"]) ** float(cand["years"])
    full_mult = (1.0 + FULL_BAR_CAGR) ** full_years
    diag["required_holdout_cagr_to_match_full_bar"] = _f(
        (full_mult / dev_mult) ** (1.0 / hold_years) - 1.0)
    diag["dev_years"] = _f(cand["years"])
    diag["dev_growth_multiple"] = _f(dev_mult)
    diag["full_bar_years"] = _f(full_years)
    diag["full_bar_multiple"] = _f(full_mult)
    diag["holdout_years"] = _f(hold_years)

    # ---- verdict ------------------------------------------------------------
    verdict = dict(
        bar_cagr=BAR_CAGR,
        bar_max_drawdown=BAR_DD,
        bar_sharpe=BAR_SHARPE,
        passes_bar=bool(cand["cagr"] > BAR_CAGR and cand["max_drawdown"] < BAR_DD),
        meets_dd_target=bool(cand["max_drawdown"] < 0.60),
        cagr_minus_bar_pp=_f((cand["cagr"] - BAR_CAGR) * 100.0),
        dd_minus_bar_pp=_f((cand["max_drawdown"] - BAR_DD) * 100.0),
        status="dev_pass" if (cand["cagr"] > BAR_CAGR
                              and cand["max_drawdown"] < 0.60) else "dev_partial",
        promoted_cell=CANDIDATE,
        pre_registered_primary_cell=PRIMARY,
        primary_is_best_cagr=plateau["primary_is_best_cagr"],
        candidate_is_best_cagr=plateau["candidate_is_best_cagr"],
        best_cagr_id=plateau["best_cagr_id"],
        five_bp_pass=bool(costs["5bp"]["cagr"] > BAR_CAGR
                          and costs["5bp"]["max_drawdown"] < 0.60),
        ten_bp_pass=bool(costs["10bp"]["cagr"] > BAR_CAGR
                         and costs["10bp"]["max_drawdown"] < 0.60),
    )

    result = dict(
        agent="tqqq-vol-target-aggressive",
        status=verdict["status"],
        window=dict(start=DEV_START, end=DEV_END,
                    sessions=int(len(tsd)),
                    marks="1-minute", fills="next-open", band=BAND),
        rules=dict(
            weight="EMA_3(clip(target_vol/sigma_t,0,1) * brake_t)",
            brake="clip(1-(dd15-0.06)/(0.12-0.06),0.25,1)",
            remainder="BIL",
            no_trend_filter=True,
            no_slow_gate=True,
            signal_lag="close t -> open t+1",
            candidate=dict(**{k: v for k, v in GRID[CANDIDATE].items()}),
            pre_registered_primary=dict(**{k: v for k, v in GRID[PRIMARY].items()}),
        ),
        verdict=verdict,
        candidate=dict(
            params={k: v for k, v in GRID[CANDIDATE].items()},
            **{"1bp": cand, "5bp": costs["5bp"], "10bp": costs["10bp"]},
        ),
        pre_registered_primary=dict(
            params={k: v for k, v in GRID[PRIMARY].items()},
            **{"1bp": grid[PRIMARY]},
        ),
        grid=grid,
        plateau=plateau,
        neighbours=neighbours,
        cut_rivals=rivals,
        constant_blends=blends,
        placebos=placebo,
        cut_tests=dict(causal=causal, performance=perf_cuts, starts=starts),
        subperiods=sub,
        episodes=eps,
        diagnostics=diag,
        benchmarks=bench,
        notes=[
            "Development window only; 2024-2026 is not read by the dev runner.",
            "The primary rv20_t080 is also the best CAGR cell; the 0.90/1.00 "
            "grid neighbours still pass the program bar, but the DD<60 target "
            "is met with margin only at 0.80.",
            "The fast crash brake is a 15-session drawdown scaler, not a slow "
            "trend gate; it is active often and costs upside in recoveries.",
            "bt.stats 'exposure' is ~1 because BIL is an asset; tqqq_exposure "
            "is the economic TQQQ weight.",
            "Pre-2016 daily bars (2015-01-02 onward) warm the estimators only.",
        ],
    )
    (HERE / "result.json").write_text(
        json.dumps(result, indent=1, default=float), encoding="utf-8")
    print(f"\nwrote {HERE / 'result.json'}", flush=True)


if __name__ == "__main__":
    main()
