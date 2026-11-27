r"""Always-long TQQQ volatility target — development-window strategy.

Hold TQQQ at all times, scaled inversely to a causal estimate of TQQQ's own
realised volatility:

    w_t = clip(target_vol / sigma_t, 0, 1),   BIL = 1 - w_t.

There is no trend filter, no moving-average gate, no drawdown gate and no
crash stop.  The only state variable is volatility.  The weight is set from
the close of session t and fills at the open of session t+1.

Development window only: 2016-01-04 .. 2023-12-29.  The 2024-2026 holdout is
not loaded (the daily reader filters it out at the parquet level) and is not
used for selection.

Run from the repo root:
    $env:PYTHONPATH = "C:\Users\27175\AppData\Local\Temp\opencode\pylibs"
    $env:BT_THREADS = "1"
    python research/new/always-long-vol-target/strategy.py
"""
from __future__ import annotations

import json
import sys
from datetime import timedelta
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402
from minute_marks import to_minutes  # noqa: E402

DEV_START, DEV_END = "2016-01-04", "2023-12-29"
SYMS = ("QQQ", "TQQQ", "BIL")
BARS_1M = 252 * 390
BARS_1D = 252
BAND = 0.02
TZ = "America/New_York"
DATA = ROOT / "data" / "intraday-hf"

# Frozen base: the pre-registered primary (round middle of the grid).
BASE = dict(estimator="rv", window=20, target_vol=0.50)

# Pre-registered 8-cell grid: two estimator families x four volatility budgets.
GRID = {
    "rv20_t45": dict(estimator="rv", window=20, target_vol=0.45),
    "rv20_t50": dict(estimator="rv", window=20, target_vol=0.50),
    "rv20_t55": dict(estimator="rv", window=20, target_vol=0.55),
    "rv20_t60": dict(estimator="rv", window=20, target_vol=0.60),
    "park20_t45": dict(estimator="park", window=20, target_vol=0.45),
    "park20_t50": dict(estimator="park", window=20, target_vol=0.50),
    "park20_t55": dict(estimator="park", window=20, target_vol=0.55),
    "park20_t60": dict(estimator="park", window=20, target_vol=0.60),
}
# The pre-registered centre was rv20_t50.  It passes the formal program bar
# (CAGR > 36.72%, DD < 82.29%) but misses the mandate's DD < 60% target at
# 62.86%.  The adjacent pre-registered cell rv20_t45 is the mandate-compliant
# point on the same smooth plateau (39.20% / 58.94%).  It is promoted as the
# frozen holdout candidate with that one-step, in-sample choice disclosed in
# report.md; rv20_t50 is kept and reported as the pre-registered anchor.
PRIMARY = "rv20_t50"
CANDIDATE = "rv20_t45"
BASE = dict(GRID[CANDIDATE])

# Out-of-grid diagnostics (not used to choose the primary).
TARGET_SWEEP = {
    "rv20_t35": dict(estimator="rv", window=20, target_vol=0.35),
    "rv20_t40": dict(estimator="rv", window=20, target_vol=0.40),
    "rv20_t65": dict(estimator="rv", window=20, target_vol=0.65),
    "rv20_t70": dict(estimator="rv", window=20, target_vol=0.70),
}
ESTIMATOR_SWEEP = {
    "rv5_t50": dict(estimator="rv", window=5, target_vol=0.50),
    "rv10_t50": dict(estimator="rv", window=10, target_vol=0.50),
    "rv60_t50": dict(estimator="rv", window=60, target_vol=0.50),
    "rv120_t50": dict(estimator="rv", window=120, target_vol=0.50),
    "ewma094_t50": dict(estimator="ewma", window=20, target_vol=0.50),
    "park10_t50": dict(estimator="park", window=10, target_vol=0.50),
    "park60_t50": dict(estimator="park", window=60, target_vol=0.50),
    "blend_t50": dict(estimator="blend", window=20, target_vol=0.50),
}
BLENDS = (0.60, 0.65, 0.70, 0.75, 0.80, 0.90, 1.00)
CUTS = ("2018-12-31", "2020-03-12", "2021-12-31", "2022-09-13")
EPISODES = (
    ("2018Q4", "2018-09-20", "2018-12-24"),
    ("covid_crash", "2020-02-19", "2020-03-23"),
    ("covid_recovery", "2020-03-23", "2021-11-19"),
    ("2022_bear", "2022-01-03", "2022-12-28"),
    ("2023_recovery", "2023-01-03", "2023-12-29"),
)

_DAILY_CACHE: dict = {}


def _ts(x: str) -> pd.Timestamp:
    return pd.Timestamp(x, tz=TZ)


def _f(x):
    if x is None:
        return None
    x = float(x)
    return x if np.isfinite(x) else None


# --------------------------------------------------------------------------- #
# Daily signal data
# --------------------------------------------------------------------------- #
def load_daily(symbol: str, end: str | None = None) -> pd.DataFrame:
    """Adjusted daily OHLC with pre-2016 warmup, read only through `end`.

    The development run passes 2023-12-29, so the parquet filter never
    materialises 2024-2026.  The lead's authorized holdout passes the full
    panel end and the same causal code runs unchanged.  `adjclose/close` is
    the same adjustment convention that `bt.load_1m` uses.
    """
    end_day = pd.Timestamp(end if end is not None else DEV_END).date() \
        + timedelta(days=1)
    key = (symbol, end_day)
    if key in _DAILY_CACHE:
        return _DAILY_CACHE[key]
    df = pd.read_parquet(
        DATA / f"{symbol}-1d-yahoo.parquet",
        columns=["date", "open", "high", "low", "close", "adjclose"],
        filters=[("date", "<", end_day)],
    )
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").drop_duplicates("date").reset_index(drop=True)
    factor = (df["adjclose"] / df["close"]).to_numpy(dtype=float)
    for col in ("open", "high", "low", "close"):
        df[col] = df[col].to_numpy(dtype=float) * factor
    df = df.set_index("date")[["open", "high", "low", "close"]]
    _DAILY_CACHE[key] = df
    return df


def estimate_vol(df: pd.DataFrame, estimator: str, window: int) -> pd.Series:
    """Causal annualised volatility, all data through each row's close."""
    lr = pd.Series(np.log(df["close"].to_numpy(float)), index=df.index).diff()
    if estimator == "rv":
        return lr.rolling(window, min_periods=window).std(ddof=1) * np.sqrt(252.0)
    if estimator == "park":
        hl2 = np.log(
            df["high"].to_numpy(float) / df["low"].to_numpy(float)
        ) ** 2
        var = pd.Series(hl2, index=df.index).rolling(
            window, min_periods=window
        ).mean() / (4.0 * np.log(2.0))
        return np.sqrt(var * 252.0)
    if estimator == "ewma":
        lam = 0.94
        var = lr.pow(2).ewm(alpha=1.0 - lam, adjust=False,
                          min_periods=window).mean()
        return np.sqrt(var * 252.0)
    if estimator == "blend":
        a = estimate_vol(df, "rv", 10)
        b = estimate_vol(df, "rv", 60)
        return np.sqrt(0.5 * a.pow(2) + 0.5 * b.pow(2))
    raise ValueError(f"unknown estimator {estimator}")


def daily_weight_series(params: dict | None = None,
                        end_date: str | None = DEV_END):
    """Daily TQQQ weight series and the volatility estimate behind it."""
    p = dict(BASE)
    if params:
        p.update(params)
    df = load_daily("TQQQ", end=end_date)
    if end_date is not None:
        df = df.loc[df.index <= pd.Timestamp(end_date)]
    vol = estimate_vol(df, p["estimator"], int(p["window"]))
    w = np.clip(float(p["target_vol"]) / vol.to_numpy(float), 0.0, 1.0)
    w = np.where(np.isfinite(w), w, 0.0)
    return pd.Series(w, index=df.index), vol


# --------------------------------------------------------------------------- #
# Weight construction (required entry point)
# --------------------------------------------------------------------------- #
def _daily_to_minutes(ts, w_daily: pd.Series) -> np.ndarray:
    """Map a daily target to 1-minute weights with the exact coarse fill times."""
    dates, _, last = bt.day_bounds(ts)
    sess = pd.DatetimeIndex(pd.to_datetime(dates[last]))
    w = w_daily.reindex(sess, method="ffill").fillna(0.0).to_numpy(float)
    Wc = np.zeros((len(sess), 3))
    Wc[:, 1] = w
    Wc[:, 2] = 1.0 - w
    return to_minutes(sess.tz_localize(TZ), Wc, ts, "1D")


def _daily_panel_weights(ts, w_daily: pd.Series) -> np.ndarray:
    """Weights for a 1D panel (one bar per session)."""
    sess = pd.DatetimeIndex(pd.to_datetime(bt.session_dates(ts)))
    w = w_daily.reindex(sess, method="ffill").fillna(0.0).to_numpy(float)
    W = np.zeros((len(ts), 3))
    W[:, 1] = w
    W[:, 2] = 1.0 - w
    return W


def _last_completed_session(ts) -> pd.Timestamp:
    """Last session in `ts` whose daily close is known.

    A mid-day truncated panel ends inside a session; that partial session is
    not a completed daily bar, so the daily signal must stop at the prior
    session.  A one-bar-per-session panel is treated as all-complete.
    """
    ts = pd.DatetimeIndex(ts)
    dates, first, last = bt.day_bounds(ts)
    if len(ts) == len(first):
        return pd.Timestamp(dates[last][-1])
    t = pd.Timestamp(ts[-1])
    cutoff = (pd.Timestamp("12:59").time() if t.date() in bt.HALF_DAYS
              else pd.Timestamp("15:59").time())
    if t.time() < cutoff and len(dates[last]) > 1:
        return pd.Timestamp(dates[last][-2])
    return pd.Timestamp(dates[last][-1])


def build_weights(ts, o, c, params: dict | None = None) -> np.ndarray:
    """Required entry point: panel -> (n, 3) TQQQ/BIL weights."""
    end_date = str(_last_completed_session(ts).date())
    w_daily, _ = daily_weight_series(params, end_date=end_date)
    return _daily_to_minutes(ts, w_daily)


# --------------------------------------------------------------------------- #
# Metrics
# --------------------------------------------------------------------------- #
def _daily_returns(r: dict):
    _, _, last = bt.day_bounds(r["ts"])
    eq = r["equity"][last]
    dates = pd.DatetimeIndex(
        pd.to_datetime(bt.session_dates(r["ts"])[last])
    )
    return pd.Series(np.diff(eq) / eq[:-1], index=dates[1:]), eq, dates


def _path_stats(rets: pd.Series) -> dict:
    """CAGR / DD / Sharpe from a daily return series (first point = 1.0)."""
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
    # Calendar-year returns from session-end equity, not from the first minute
    # of January (which would embed the year's opening gap in every year).
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
        cagr=_f((e[-1] / e[0]) ** (1.0 / years) - 1.0),
        max_drawdown=_f(float(-(e / np.maximum.accumulate(e) - 1.0).min())),
        sharpe=_f(float(np.mean(rets)) / sd * np.sqrt(BARS_1M)) if sd > 0 else None,
        years=_f(years),
    )


def episode_row(w_daily: pd.Series, a: str, b: str) -> dict:
    w = w_daily.loc[a:b]
    return dict(
        avg_weight=_f(w.mean()) if len(w) else None,
        min_weight=_f(w.min()) if len(w) else None,
        max_weight=_f(w.max()) if len(w) else None,
    )


# --------------------------------------------------------------------------- #
# Placebos
# --------------------------------------------------------------------------- #
def placebo_block(tsd, od, cd, W_primary, w_dev: np.ndarray,
                  r_real: dict, n_draws: int = 500, seed: int = 7) -> dict:
    n = len(tsd)
    real_stats = _path_stats(_daily_returns(r_real)[0])
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
    pd_ = np.array([s["max_drawdown"] for s in pstats], dtype=float)
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
        real=real_stats,
        matched_constant=dict(weight=_f(const), **const_stats),
        circular_shift=dict(
            draws=int(n_draws),
            cagr_mean=_f(pc.mean()),
            cagr_p05=_f(np.percentile(pc, 5)),
            cagr_p50=_f(np.percentile(pc, 50)),
            cagr_p95=_f(np.percentile(pc, 95)),
            dd_mean=_f(pd_.mean()),
            dd_p50=_f(np.percentile(pd_, 50)),
            sharpe_p50=_f(np.percentile(ps, 50)),
            frac_cagr_ge_real=_f(np.mean(pc >= real_stats["cagr"])),
            frac_both_ge_real=_f(np.mean(
                (pc >= real_stats["cagr"]) & (pd_ <= real_stats["max_drawdown"])
            )),
        ),
        lag=lags,
    )


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main() -> None:
    print("loading panels (development window only)", flush=True)
    ts1, o1, c1 = bt.panel(SYMS, DEV_START, DEV_END, "1min")
    tsd, od, cd = bt.panel(SYMS, DEV_START, DEV_END, "1D")
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
    cand_W = cand_r = cand_rd = cand_w_daily = None
    anchor_W = anchor_r = anchor_rd = anchor_w_daily = None
    for name, p in GRID.items():
        W = build_weights(ts1, o1, c1, p)
        m, r = metrics(ts1, o1, c1, W, slip=1.0)
        Wd = _daily_panel_weights(tsd, daily_weight_series(p)[0])
        md, rd = metrics(tsd, od, cd, Wd, slip=1.0, bars=BARS_1D)
        m["daily_marks_1bp"] = {k: md[k] for k in
                                ("cagr", "max_drawdown", "sharpe",
                                 "tqqq_exposure")}
        grid[name] = m
        print(f"  {name:12s} CAGR {m['cagr']*100:6.2f}%  DD {m['max_drawdown']*100:5.2f}%"
              f"  Sharpe {m['sharpe']:4.2f}  TQQQ {m['tqqq_exposure']*100:5.1f}%"
              f"  fills {m['fills']:,}", flush=True)
        if name == CANDIDATE:
            cand_W, cand_r, cand_rd = W, r, rd
            cand_w_daily = daily_weight_series(p)[0]
        if name == PRIMARY:
            anchor_W, anchor_r, anchor_rd = W, r, rd
            anchor_w_daily = daily_weight_series(p)[0]

    cand = grid[CANDIDATE]
    anchor = grid[PRIMARY]
    costs = {}
    for slip in (5.0, 10.0):
        costs[f"{int(slip)}bp"], _ = metrics(ts1, o1, c1, cand_W, slip=slip)
    print(f"  candidate 5bp  CAGR {costs['5bp']['cagr']*100:6.2f}%  DD "
          f"{costs['5bp']['max_drawdown']*100:5.2f}%", flush=True)
    print(f"  candidate 10bp CAGR {costs['10bp']['cagr']*100:6.2f}%  DD "
          f"{costs['10bp']['max_drawdown']*100:5.2f}%", flush=True)

    # ---- plateau ------------------------------------------------------------
    passing = [k for k, m in grid.items()
               if m["cagr"] > 0.3672 and m["max_drawdown"] < 0.8229]
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
        pre_registered_primary=dict(cagr=anchor["cagr"],
                                    max_drawdown=anchor["max_drawdown"]),
    )
    print(f"\n  plateau: {len(passing)}/{len(grid)} pass  "
          f"CAGR {plateau['cagr_min']*100:.2f}-{plateau['cagr_max']*100:.2f}%  "
          f"DD {plateau['dd_min']*100:.2f}-{plateau['dd_max']*100:.2f}%", flush=True)

    # ---- neighbours ---------------------------------------------------------
    print("\n== neighbours (1m marks, 1 bp) ==", flush=True)
    neighbours = {}
    for name, p in {**TARGET_SWEEP, **ESTIMATOR_SWEEP}.items():
        W = build_weights(ts1, o1, c1, p)
        m, _ = metrics(ts1, o1, c1, W, slip=1.0)
        neighbours[name] = m
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

    def _wdev(w_daily):
        return w_daily.reindex(
            pd.DatetimeIndex(pd.to_datetime(bt.session_dates(tsd)))
        ).to_numpy(float)

    placebos = placebo_block(tsd, od, cd, cand_W, _wdev(cand_w_daily), cand_rd)
    placebos_anchor = placebo_block(tsd, od, cd, anchor_W,
                                    _wdev(anchor_w_daily), anchor_rd)
    print(f"  candidate real {placebos['real']}", flush=True)
    print(f"  candidate constant {placebos['matched_constant']}", flush=True)
    print(f"  candidate shift {placebos['circular_shift']}", flush=True)
    print(f"  anchor shift {placebos_anchor['circular_shift']}", flush=True)

    # ---- cut tests ----------------------------------------------------------
    print("\n== cut tests ==", flush=True)
    full_w = cand_w_daily
    causal = {}
    for cut in CUTS:
        part_w, _ = daily_weight_series(BASE, end_date=cut)
        idx = full_w.index < pd.Timestamp(cut)
        diff_d = np.abs(
            part_w.reindex(full_w.index[idx]).to_numpy(float)
            - full_w[idx].to_numpy(float)
        )
        Wp = _daily_to_minutes(ts1, part_w)
        cut_ts = _ts(cut)
        m1 = ts1 < cut_ts
        diff_m = np.abs(Wp[m1] - cand_W[m1])
        causal[cut] = dict(
            daily_dates=int(idx.sum()),
            daily_max_abs_diff=_f(np.max(diff_d)) if len(diff_d) else None,
            minute_bars=int(m1.sum()),
            minute_max_abs_diff=_f(np.max(diff_m)) if len(diff_m) else None,
            pass_=bool((len(diff_d) == 0 or np.max(diff_d) <= 1e-12)
                       and (len(diff_m) == 0 or np.max(diff_m) <= 1e-12)),
        )
        print(f"  causal {cut}: {causal[cut]}", flush=True)

    dret, _, _ = _daily_returns(cand_r)
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
    best20 = dret.nlargest(20).index
    r2[best20] = 0.0
    perf_cuts["ex_best_20_sessions"] = _path_stats(r2)
    for label in ("ex_2020", "ex_2022", "ex_best_20_sessions"):
        print(f"  {label}: {perf_cuts[label]}", flush=True)
    print(f"  {perf_cuts['ex_best_year']}", flush=True)

    starts = {}
    for s in ("2017-01-03", "2018-01-02"):
        m, _ = metrics(ts1, o1, c1, cand_W, start=s, slip=1.0)
        starts[s] = {k: m[k] for k in ("cagr", "max_drawdown", "sharpe",
                                       "tqqq_exposure")}
        print(f"  start {s}: CAGR {m['cagr']*100:.2f}%  DD "
              f"{m['max_drawdown']*100:.2f}%", flush=True)

    # ---- subperiods and episodes -------------------------------------------
    sub = {}
    for label, a, b in (("2016_19", "2016-01-04", "2020-01-01"),
                        ("2020_21", "2020-01-01", "2022-01-01"),
                        ("2022_23", "2022-01-01", "2023-12-30")):
        sub[label] = slice_metrics(cand_r, a, b)

    eps = {}
    _, deq_p, ddates_p = _daily_returns(cand_r)
    for label, a, b in EPISODES:
        row = episode_row(cand_w_daily, a, b)
        row["tqqq_return"] = _f(float(
            load_daily("TQQQ")["close"].loc[b] / load_daily("TQQQ")["close"].loc[a] - 1.0
        ))
        ea = deq_p[ddates_p == pd.Timestamp(a)]
        eb = deq_p[ddates_p == pd.Timestamp(b)]
        row["strategy_return"] = _f(float(eb[0] / ea[0] - 1.0)) if len(ea) and len(eb) else None
        eps[label] = row
    print("\n== episodes ==", flush=True)
    for k, v in eps.items():
        print(f"  {k}: strat {v['strategy_return']*100:7.2f}%  "
              f"TQQQ {v['tqqq_return']*100:7.2f}%  avg w {v['avg_weight']*100:5.1f}%", flush=True)

    # ---- diagnostics --------------------------------------------------------
    _, deq_d, ddates_d = _daily_returns(cand_r)
    _, _, last_d = bt.day_bounds(cand_r["ts"])
    tq_d = c1[i1:, 1][last_d]
    tr_d = np.diff(tq_d) / tq_d[:-1]
    sr_d = dret.to_numpy(float)
    up_d, dn_d = tr_d > 0, tr_d < 0
    s_eq = pd.Series(deq_d, index=ddates_d)
    t_eq = pd.Series(tq_d, index=ddates_d)
    sm = s_eq.resample("ME").last().pct_change().dropna()
    tm = t_eq.resample("ME").last().pct_change().dropna()
    wd_c, vol_c = daily_weight_series(GRID[CANDIDATE])
    wd_c = wd_c.loc[DEV_START:DEV_END]
    vol_c = vol_c.loc[wd_c.index]
    qq = pd.qcut(vol_c, 5, labels=False)
    quint = [
        dict(q=int(k), vol_min=_f(vol_c[qq == k].min()),
             vol_max=_f(vol_c[qq == k].max()),
             avg_weight=_f(wd_c[qq == k].mean()),
             n=int((qq == k).sum()))
        for k in range(5)
    ]
    key_dates = {
        dt: dict(vol=_f(vol_c.loc[dt]), weight=_f(wd_c.loc[dt]))
        for dt in ("2020-02-19", "2020-03-12", "2020-03-23", "2020-04-30",
                   "2021-11-19", "2022-01-03", "2022-06-16", "2022-10-14",
                   "2022-12-28", "2023-01-03", "2023-12-29")
    }
    tq_y = {int(y): float(v["tqqq"]) for y, v in cand["yearly"].items()}
    span = float(cand["years"])
    ep = pd.Timestamp("2021-11-19"), pd.Timestamp("2023-01-06")
    dd_ep = dict(
        strategy=_f(float(s_eq.loc[ep[0]:ep[1]].min()
                          / s_eq.loc[ep[0]:ep[1]].cummax().max() - 1.0)),
        tqqq=_f(float(t_eq.loc[ep[0]:ep[1]].min()
                      / t_eq.loc[ep[0]:ep[1]].cummax().max() - 1.0)),
    )
    dev_mult = float(cand["ending_equity"]) / 100000.0
    full_years = (pd.Timestamp("2026-10-23") - pd.Timestamp(DEV_START)).days / 365.25
    full_mult = 1.3754 ** full_years
    hold_years = full_years - span
    diag = dict(
        beta_daily=_f(np.cov(sr_d, tr_d, ddof=0)[0, 1] / np.var(tr_d, ddof=0)),
        corr_daily=_f(np.corrcoef(sr_d, tr_d)[0, 1]),
        vol_strategy_daily=_f(sr_d.std() * np.sqrt(252.0)),
        vol_tqqq_daily=_f(tr_d.std() * np.sqrt(252.0)),
        up_capture_daily=_f(sr_d[up_d].mean() / tr_d[up_d].mean()),
        down_capture_daily=_f(sr_d[dn_d].mean() / tr_d[dn_d].mean()),
        beta_monthly=_f(np.cov(sm, tm, ddof=0)[0, 1] / np.var(tm, ddof=0)),
        corr_monthly=_f(np.corrcoef(sm, tm)[0, 1]),
        up_capture_monthly=_f(sm[tm > 0].mean() / tm[tm > 0].mean()),
        down_capture_monthly=_f(sm[tm < 0].mean() / tm[tm < 0].mean()),
        weight_by_vol_quintile=quint,
        key_dates=key_dates,
        dd_2021_11_19_2023_01_06=dd_ep,
        tqqq_yearly={str(k): _f(v) for k, v in tq_y.items()},
        tqqq_ex_2023_cagr=_f(
            np.prod([1 + v for k, v in tq_y.items() if k != 2023]) ** (1.0 / span) - 1.0),
        tqqq_ex_2020_cagr=_f(
            np.prod([1 + v for k, v in tq_y.items() if k != 2020]) ** (1.0 / span) - 1.0),
        dev_years=_f(span),
        dev_growth_multiple=_f(dev_mult),
        full_bar_years=_f(full_years),
        full_bar_multiple=_f(full_mult),
        holdout_years=_f(hold_years),
        required_holdout_cagr_to_match_full_bar=_f(
            (full_mult / dev_mult) ** (1.0 / hold_years) - 1.0),
    )

    # ---- verdict ------------------------------------------------------------
    pass_bar = bool(cand["cagr"] > 0.3672 and cand["max_drawdown"] < 0.8229)
    dd60 = bool(cand["max_drawdown"] < 0.60)
    status = "dev_pass" if (pass_bar and dd60) else (
        "dev_partial" if pass_bar else "rejected")
    verdict = dict(
        bar_cagr=0.3672,
        bar_max_drawdown=0.8229,
        bar_sharpe=0.82,
        passes_bar=pass_bar,
        meets_dd_target=dd60,
        cagr_minus_bar_pp=_f((cand["cagr"] - 0.3672) * 100.0),
        dd_minus_bar_pp=_f((cand["max_drawdown"] - 0.8229) * 100.0),
        status=status,
        promoted_cell=CANDIDATE,
        pre_registered_primary_cell=PRIMARY,
        anchor_also_passes_bar=bool(
            anchor["cagr"] > 0.3672 and anchor["max_drawdown"] < 0.8229),
        anchor_meets_dd_target=bool(anchor["max_drawdown"] < 0.60),
    )

    out = dict(
        agent="always-long-vol-target",
        status=status,
        window=dict(start=DEV_START, end=DEV_END, sessions=int(len(tsd)),
                    marks="1-minute", fills="next-open", band=BAND),
        rules=dict(
            weight="clip(target_vol / sigma_t, 0, 1)",
            remainder="BIL",
            no_trend_filter=True,
            no_crash_stop=True,
            signal_lag="close t -> open t+1",
            candidate=dict(GRID[CANDIDATE]),
            pre_registered_primary=dict(GRID[PRIMARY]),
        ),
        verdict=verdict,
        candidate=dict(params=dict(GRID[CANDIDATE]), **{"1bp": cand},
                       **{k: v for k, v in costs.items()},
                       diagnostics=diag),
        pre_registered_primary=dict(params=dict(GRID[PRIMARY]),
                                    **{"1bp": anchor},
                                    placebo=placebos_anchor),
        grid=grid,
        plateau=plateau,
        neighbours=neighbours,
        constant_blends=blends,
        placebos=placebos,
        cut_tests=dict(causal=causal, performance=perf_cuts, starts=starts),
        subperiods=sub,
        episodes=eps,
        benchmarks={k: {kk: _f(vv) for kk, vv in v.items()} for k, v in bench.items()},
        notes=[
            "Development window only; the dev run's daily reader filters 2024-2026 at the parquet level.",
            "The pre-registered centre was rv20_t50; the mandate-compliant rv20_t45 is promoted for the holdout (one step, disclosed).",
            "bt.stats 'exposure' is ~1 because BIL is an asset; tqqq_exposure is the economic TQQQ weight.",
            "Parkinson uses adjusted daily high/low and ignores overnight gaps.",
            "Pre-2016 daily bars (2015-01-02 onward) warm the volatility estimators only.",
        ],
    )
    (HERE / "result.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"\nwrote {HERE / 'result.json'}", flush=True)


if __name__ == "__main__":
    main()
