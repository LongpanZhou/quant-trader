"""SPY-confirmed TQQQ trend ladder - standalone strategy.

Development window ONLY: 2016-01-04 .. 2023-12-29.  The 1-minute panel is
requested with ``end=END`` and every daily parquet read is filtered with
``date <= END``; no 2024+ bar is loaded or inspected.

Rule (see HYPOTHESIS.md):
    qqq_up(k) = QQQ close(k) > SMA_150(QQQ)(k)
    spy_up(k) = SPY close(k) > SMA_200(SPY)(k)
    rv20(k)   = annualised 20-session stdev of TQQQ daily returns through k
    scale(k)  = min(1, 0.85 / rv20(k))
    brake(k)  = TQQQ close(k) <= 0.85 * max(TQQQ close, last 20 sessions)
                -> force BIL for the next 5 sessions; re-arm only after TQQQ
                   recovers above -7.5% from the 20-day high

    If brake:                      BIL 100%
    elif qqq_up and spy_up:        TQQQ scale(k), remainder BIL
    elif qqq_up:                   QQQ 100%
    else:                          BIL 100%

The target set at the close of session k is filled at the next session's open
with a 2% band.  Long-only, weights >= 0, row sum <= 1.

Run from the repo root:
    $env:PYTHONPATH = "C:\\Users\\27175\\AppData\\Local\\Temp\\opencode\\pylibs"
    $env:BT_THREADS = "1"
    python research/new/spy-confirmed-trend/strategy.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

HERE = Path(__file__).resolve().parent
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402

START = "2016-01-04"
END = "2023-12-29"
DEV_END = pd.Timestamp(END)
SYMBOLS = ("QQQ", "TQQQ", "BIL")
COL_Q, COL_T, COL_B = 0, 1, 2
DATA = ROOT / "data" / "intraday-hf"
SPY_PATH = ROOT / "data" / "round3" / "yahoo" / "SPY-1d-yahoo.parquet"

BAND = 0.02
HEADLINE_COST = 1.0
COSTS = (1.0, 5.0, 10.0)
BARS_1M = 252 * 390

# Primary parameters, frozen in HYPOTHESIS.md before the final 1-minute run.
# The literal mandate centre (QQQ 100 / SPY 200 / -10% brake) is grid cell A,
# reported in full; the delivered primary is the centre of the passing plateau.
PRIMARY = dict(
    qqq_sma=150,
    spy_sma=200,
    qqq_buffer=0.0,          # tolerance band below the QQQ SMA (diagnostic)
    vol_target=0.85,
    vol_n=20,
    brake_dd=0.15,
    brake_n=20,
    brake_cool=5,
    brake_scope="all",       # "all" -> BIL; "tqqq" -> only exits TQQQ
    qqq_fallback=1.0,        # QQQ weight when QQQ up but SPY not confirmed
    remainder="bil",         # BIL or cash for the unallocated TQQQ sleeve
    use_qqq=True,
    use_spy=True,
    spy_only_state="bil",    # "qqq" -> hold QQQ when only SPY is above trend
)

# Pre-registered 8-cell grid: one parameter at a time around the primary, plus
# the literal mandate centre as cell A.
GRID = [
    ("mandate_100_10", {"qqq_sma": 100, "brake_dd": 0.10}),
    ("primary_150_15", {}),
    ("qqq135", {"qqq_sma": 135}),
    ("qqq160", {"qqq_sma": 160}),
    ("spy180", {"spy_sma": 180}),
    ("spy220", {"spy_sma": 220}),
    ("vol70", {"vol_target": 0.70}),
    ("brake20", {"brake_dd": 0.20}),
]


# --------------------------------------------------------------------------- #
# data
# --------------------------------------------------------------------------- #
def _yahoo_dev(symbol: str, last_date: pd.Timestamp) -> pd.Series:
    """Yahoo adjusted close, physically sliced at ``last_date``."""
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
    if s.index.max() > pd.Timestamp(last_date):
        raise RuntimeError("daily read crossed the requested boundary")
    return s


def _daily_frame(ts: pd.DatetimeIndex, closes: np.ndarray) -> pd.DataFrame:
    """Daily total-return levels aligned to the panel's session dates.

    Panel closes are the 15:59 marks; pre-2016 history is spliced from Yahoo
    adjusted closes scaled to the first common session.  SPY is signal-only and
    never held or marked.
    """
    if len(ts) == 0:
        raise ValueError("empty panel")
    last_date = pd.Timestamp(ts[-1]).tz_localize(None).normalize()
    if last_date > DEV_END:
        raise RuntimeError(
            f"panel extends past the development window: {last_date}"
        )
    dates, _, last = bt.day_bounds(ts)
    sess = pd.to_datetime(dates[last])
    panel = pd.DataFrame(closes[last], index=sess, columns=list(SYMBOLS))

    levels = {}
    for symbol in SYMBOLS:
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
        {"QQQ": levels["QQQ"], "TQQQ": levels["TQQQ"], "BIL": levels["BIL"],
         "SPY": spy}, index=idx)
    if daily.isna().any().any():
        raise ValueError("daily signal frame contains NaN")
    return daily


# --------------------------------------------------------------------------- #
# signal
# --------------------------------------------------------------------------- #
def _session_targets(daily: pd.DataFrame, params: dict,
                     spy_up_override=None):
    """Per-session target weights decided at that session's close.

    Row k is the target set at the close of session k, filled at the open of
    session k+1.  Returns (targets n x 3, parts dict).

    ``spy_up_override`` is used only by the placebo diagnostic: the position
    state machine is rebuilt with a circularly shifted SPY gate.
    """
    p = dict(PRIMARY)
    p.update(params or {})

    q = daily["QQQ"]
    spy = daily["SPY"]
    t = daily["TQQQ"]

    q_ma = q.rolling(int(p["qqq_sma"]), min_periods=int(p["qqq_sma"])).mean()
    s_ma = spy.rolling(int(p["spy_sma"]), min_periods=int(p["spy_sma"])).mean()
    if p.get("use_qqq", True):
        qb = float(p.get("qqq_buffer", 0.0))
        qqq_up = (q > q_ma * (1.0 - qb)).fillna(False).to_numpy()
    else:
        qqq_up = np.ones(len(daily), dtype=bool)
    if spy_up_override is not None:
        spy_up = np.asarray(spy_up_override, dtype=bool)
    elif p.get("use_spy", True):
        spy_up = (spy > s_ma).fillna(False).to_numpy()
    else:
        spy_up = np.ones(len(daily), dtype=bool)

    r = t.pct_change()
    rv = r.rolling(int(p["vol_n"]), min_periods=int(p["vol_n"])).std(ddof=0) * np.sqrt(252.0)
    rv = rv.to_numpy(dtype=float)
    scale = np.clip(float(p["vol_target"]) / np.maximum(rv, 1e-9), 0.0, 1.0)
    scale = np.where(np.isfinite(rv), scale, 0.0)

    hi = t.rolling(int(p["brake_n"]), min_periods=int(p["brake_n"])).max()
    dd = (t / hi - 1.0).to_numpy(dtype=float)
    triggered_now = np.isfinite(dd) & (dd <= -float(p["brake_dd"]))

    n = len(daily)
    W = np.zeros((n, len(SYMBOLS)), dtype=float)
    state = np.zeros(n, dtype=np.int8)  # 0 BIL/brake, 1 TQQQ, 2 QQQ
    brake_flag = np.zeros(n, dtype=np.float64)
    lock = 0
    rearm = 0
    armed = True
    thr = float(p["brake_dd"])
    for k in range(n):
        # A fresh breach arms the brake; it does not re-arm until TQQQ has
        # recovered at least half of the trigger drawdown.  Without this the
        # brake would stay on for months during a slow recovery.
        if np.isfinite(dd[k]) and dd[k] > -0.5 * thr:
            armed = True
        if lock > 0:
            lock -= 1
            brake_flag[k] = 1.0
            state[k] = 0
        elif armed and triggered_now[k]:
            armed = False
            rearm += 1
            lock = int(p["brake_cool"]) - 1
            brake_flag[k] = 1.0
            state[k] = 0
        elif qqq_up[k] and spy_up[k]:
            state[k] = 1
            W[k, COL_T] = scale[k]
        elif qqq_up[k]:
            state[k] = 2
            W[k, COL_Q] = float(p["qqq_fallback"])
        elif spy_up[k] and p.get("spy_only_state", "bil") == "qqq":
            # Diagnostic alternative: broad market healthy, tech below its own
            # trend -> hold QQQ at 1x instead of BIL.
            state[k] = 2
            W[k, COL_Q] = float(p["qqq_fallback"])
        else:
            state[k] = 0

        if state[k] == 1 and p["remainder"] == "bil":
            W[k, COL_B] = 1.0 - W[k, COL_T]
        elif state[k] == 1:
            pass  # remainder in cash
        elif state[k] == 0:
            W[k, COL_B] = 1.0
        # state 2: QQQ 1.0, no BIL

        # "tqqq" brake scope: a brake only blocks the leveraged sleeve; when
        # QQQ is above its own trend the fallback still holds QQQ.
        if p.get("brake_scope") == "tqqq" and brake_flag[k] and qqq_up[k]:
            W[k] = 0.0
            W[k, COL_Q] = float(p["qqq_fallback"])
            state[k] = 2

    W = np.clip(np.nan_to_num(W, nan=0.0), 0.0, 1.0)
    total = W.sum(axis=1)
    over = total > 1.0
    if over.any():
        W[over] /= total[over, None]

    parts = dict(
        qqq_up=qqq_up.astype(float),
        spy_up=spy_up.astype(float),
        rv=rv,
        scale=scale,
        dd=dd,
        brake=brake_flag,
        state=state,
        brake_rearms=rearm,
        n_brake_days=int(brake_flag.sum()),
    )
    return W, parts


def _expand_to_bars(ts: pd.DatetimeIndex, W_daily: np.ndarray) -> np.ndarray:
    """Map one target row per session to one row per bar.

    Bars of session d carry the target set at the close of d-1; the final bar
    of session d carries the target set at d's close (filled next open).
    """
    nd = len(W_daily)
    _, first, last = bt.day_bounds(ts)
    if nd != len(first):
        raise ValueError("session count mismatch")
    if len(ts) == nd:
        return np.asarray(W_daily, dtype=float).copy()
    sid = bt.day_ids(ts)
    shifted = np.vstack([np.zeros((1, W_daily.shape[1])), W_daily[:-1]])
    out = shifted[sid].copy()
    out[last] = W_daily
    return out


def _check_dev_boundary(ts) -> None:
    """Refuse a panel that extends past the current development end.

    The lead's one-shot holdout runner catches this RuntimeError, lifts END to
    the full-window end and retries.  A normal development run never reaches
    the raise.
    """
    if len(ts) == 0:
        return
    last = pd.Timestamp(ts[-1])
    if last.tzinfo is None:
        last = last.tz_localize("America/New_York")
    limit = pd.Timestamp(END, tz="America/New_York").normalize() + pd.Timedelta(days=1)
    if last >= limit:
        raise RuntimeError(
            "panel extends past the development window; "
            "the holdout runner may lift END and retry"
        )


def build_weights(ts, o, c, params=None, return_daily=False,
                  spy_up_override=None):
    """Return (n, 3) QQQ/TQQQ/BIL target weights for the harness."""
    _check_dev_boundary(ts)
    daily = _daily_frame(ts, c)
    W_full, parts_full = _session_targets(daily, params or {},
                                          spy_up_override=spy_up_override)
    # The daily frame carries pre-2016 warm-up rows; the harness panel does not.
    dates, _, last = bt.day_bounds(ts)
    sess = pd.DatetimeIndex(dates[last])
    pos = daily.index.get_indexer(sess)
    if (pos < 0).any():
        raise ValueError("panel session missing from the daily signal frame")
    W_daily = W_full[pos]
    parts = {}
    for key, value in parts_full.items():
        if isinstance(value, np.ndarray) and value.ndim >= 1 and len(value) == len(daily):
            parts[key] = value[pos]
        else:
            parts[key] = value
    W = _expand_to_bars(ts, W_daily)
    if return_daily:
        return W, W_daily, parts, daily
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
    eq_d = bt.daily_last(r["equity"], r["ts"])
    b_d = bt.daily_last(c[i0:, COL_T], r["ts"])
    rets = np.diff(eq_d.to_numpy()) / eq_d.to_numpy()[:-1]
    bret = np.diff(b_d.to_numpy()) / b_d.to_numpy()[:-1]
    s["corr_tqqq"] = (float(np.corrcoef(rets, bret)[0, 1])
                      if len(rets) > 2 else float("nan"))
    for key in ("cagr", "max_drawdown", "sharpe", "exposure", "turnover",
                "volatility", "sortino", "years", "ending_equity"):
        if key in s:
            s[key] = float(s[key])
    s["fills"] = int(s["fills"])
    return s, r, eq_d, b_d


def _metrics_daily(ts_d, o_d, c_d, W, cost: float = HEADLINE_COST, start=START):
    return _metrics(ts_d, o_d, c_d, W, cost=cost, bars_per_year=252, start=start)


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
    keys = ("cagr", "max_drawdown", "sharpe", "sortino", "volatility",
            "exposure", "corr_tqqq", "fills", "turnover", "years",
            "ending_equity")
    return {k: s.get(k) for k in keys if k in s}


def _yearly(ts, eq, bench):
    return {str(y): {"strategy": v["strategy"], "benchmark": v["benchmark"]}
            for y, v in bt.yearly(ts, eq, bench).items()}


def _yearly_exposure(ts, r):
    eq = r["equity"]
    expo = (eq - r["cash"]) / eq
    out = {}
    for y in sorted(set(ts.year)):
        out[str(int(y))] = float(np.mean(expo[ts.year == y]))
    return out


def _pct_rank(dist, value):
    d = np.asarray(dist, dtype=float)
    return float((np.sum(d < value) + 0.5 * np.sum(d == value)) / len(d))


def _cagr_from_returns(dr: np.ndarray, periods_per_year: float = 252.0) -> float:
    if len(dr) == 0:
        return float("nan")
    return float(np.prod(1.0 + dr) ** (periods_per_year / len(dr)) - 1.0)


def _drop_year_cut(dr: pd.Series, bret: pd.Series, year: int) -> dict:
    keep = dr.index.year != year
    d = dr[keep].to_numpy()
    b = bret[keep].to_numpy()
    return {"strategy": _cagr_from_returns(d),
            "benchmark": _cagr_from_returns(b), "days": int(len(d))}


def _drop_best_days(dr: pd.Series, bret: pd.Series, n: int = 10) -> dict:
    idx = np.argsort(dr.to_numpy())[-n:]
    d = dr.to_numpy().copy()
    b = bret.to_numpy().copy()
    d[idx] = 0.0
    b[idx] = 0.0
    return {"strategy": _cagr_from_returns(d),
            "benchmark": _cagr_from_returns(b), "n_days": int(n)}


def _beta_capture(dr, bret) -> dict:
    dr = np.asarray(dr, dtype=float)
    bret = np.asarray(bret, dtype=float)
    var = float(np.var(bret))
    beta = float(np.cov(dr, bret, ddof=0)[0, 1] / var) if var > 0 else None
    up = bret > 0
    down = bret < 0
    return {
        "beta": beta,
        "upside_capture": (float(np.mean(dr[up]) / np.mean(bret[up]))
                           if up.any() else None),
        "downside_capture": (float(np.mean(dr[down]) / np.mean(bret[down]))
                             if down.any() else None),
    }


def _block_shuffle_rows(W: np.ndarray, block: int = 20, draws: int = 200,
                        seed: int = 7) -> np.ndarray:
    n = len(W)
    rng = np.random.default_rng(seed)
    out = np.empty((draws, n, W.shape[1]), dtype=float)
    for j in range(draws):
        nblocks = int(np.ceil(n / block))
        starts = rng.integers(0, n, nblocks)
        idx = np.concatenate([(np.arange(s, s + block) % n) for s in starts])[:n]
        out[j] = W[idx]
    return out


def _placebo_stats(ts_d, o_d, c_d, weights_list, cost=HEADLINE_COST):
    Ws = [np.clip(np.nan_to_num(np.asarray(w, dtype=float), nan=0.0), 0.0, 1.0)
          for w in weights_list]
    results = bt.simulate_many(ts_d, o_d, c_d, Ws, band=BAND,
                               slippage_bps=cost, threads=1)
    return [bt.stats(r, 252) for r in results]


def _max_dd_window(ts, eq):
    peak = np.maximum.accumulate(eq)
    dd = eq / peak - 1.0
    i = int(np.argmin(dd))
    j = int(np.argmax(eq[:i + 1]))
    return {
        "max_drawdown": float(-dd[i]),
        "peak_date": str(pd.Timestamp(ts[j]).date()),
        "trough_date": str(pd.Timestamp(ts[i]).date()),
    }


def _episode(ts, eq, bench, a, b):
    j0 = int(ts.searchsorted(pd.Timestamp(a, tz="America/New_York")))
    j1 = int(ts.searchsorted(pd.Timestamp(b, tz="America/New_York"), side="right"))
    e = eq[j0:j1]
    x = bench[j0:j1]
    if len(e) < 2:
        return None
    peak = np.maximum.accumulate(e)
    return {
        "strategy": float(e[-1] / e[0] - 1.0),
        "benchmark": float(x[-1] / x[0] - 1.0),
        "strategy_max_drawdown": float(-(e / peak - 1.0).min()),
    }


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
    W_primary, w_daily_1m, parts_1m, daily_1m = build_weights(
        ts, o, c, PRIMARY, return_daily=True)
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
    yearly_daily = {}
    for y in sorted(set(eq_d.index.year)):
        e = eq_d[eq_d.index.year == y]
        x = b_d[b_d.index.year == y]
        if len(e) > 1:
            yearly_daily[str(int(y))] = {
                "strategy": float(e.iloc[-1] / e.iloc[0] - 1.0),
                "benchmark": float(x.iloc[-1] / x.iloc[0] - 1.0),
            }
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
        print(f"  {name:16s} CAGR {s['cagr']*100:6.2f}%  DD "
              f"{s['max_drawdown']*100:5.2f}%  Sharpe {s['sharpe']:4.2f}  "
              f"expo {s['exposure']*100:5.1f}%", flush=True)

    # ---- structural ablations --------------------------------------------
    print("ablations ...", flush=True)
    ablations = {}
    ablation_specs = [
        ("primary", {}),
        ("mandate_100_10", {"qqq_sma": 100, "brake_dd": 0.10}),
        ("mandate_100_15", {"qqq_sma": 100, "brake_dd": 0.15}),
        ("mandate_100_15_buffer2", {"qqq_sma": 100, "brake_dd": 0.15,
                                    "qqq_buffer": 0.02}),
        ("no_spy_gate", {"use_spy": False}),
        ("spy_only", {"use_qqq": False}),
        ("no_gates", {"use_spy": False, "use_qqq": False}),
        ("no_qqq_fallback", {"qqq_fallback": 0.0}),
        ("spy_only_state_qqq", {"spy_only_state": "qqq"}),
        ("no_brake", {"brake_dd": 10.0}),
        ("no_vol", {"vol_target": 10.0}),
        ("brake_scope_tqqq", {"brake_scope": "tqqq"}),
        ("cash_remainder", {"remainder": "cash"}),
        ("qqq120", {"qqq_sma": 120}),
        ("qqq130", {"qqq_sma": 130}),
        ("qqq180", {"qqq_sma": 180}),
        ("spy100", {"spy_sma": 100}),
        ("spy150", {"spy_sma": 150}),
        ("spy250", {"spy_sma": 250}),
        ("vol70", {"vol_target": 0.70}),
        ("vol100", {"vol_target": 1.00}),
        ("vol_n10", {"vol_n": 10}),
        ("vol_n40", {"vol_n": 40}),
        ("brake12", {"brake_dd": 0.12}),
        ("brake20", {"brake_dd": 0.20}),
        ("brake_n10", {"brake_n": 10}),
        ("brake_n40", {"brake_n": 40}),
        ("brake_cool3", {"brake_cool": 3}),
        ("brake_cool10", {"brake_cool": 10}),
    ]
    for name, over in ablation_specs:
        p = dict(PRIMARY); p.update(over)
        W = build_weights(ts, o, c, p)
        s, _, _, _ = _metrics(ts, o, c, W, cost=HEADLINE_COST)
        ablations[name] = {"params": p, **_summary(s)}
        print(f"  {name:20s} CAGR {s['cagr']*100:6.2f}%  DD "
              f"{s['max_drawdown']*100:5.2f}%  Sharpe {s['sharpe']:4.2f}", flush=True)

    # ---- subperiods ------------------------------------------------------
    print("subperiods ...", flush=True)
    subperiods = {}
    for name, a, b in (("2016_2019", START, "2019-12-31"),
                       ("2020_2023", "2020-01-02", END),
                       ("2016_2020", START, "2020-12-31"),
                       ("2021_2023", "2021-01-04", END)):
        s, _, _, _ = _metrics(ts, o, c, W_primary, cost=HEADLINE_COST, start=a, end=b)
        subperiods[name] = _summary(s)
        print(f"  {name:10s} CAGR {s['cagr']*100:6.2f}%  DD "
              f"{s['max_drawdown']*100:5.2f}%  Sharpe {s['sharpe']:4.2f}", flush=True)

    # ---- cuts ------------------------------------------------------------
    print("cuts ...", flush=True)
    dr = eq_d.pct_change().dropna()
    bret = b_d.pct_change().dropna()
    cuts = {}
    for y in range(2016, 2024):
        cuts[f"drop_{y}"] = _drop_year_cut(dr, bret, y)
    cuts["drop_best_10_days"] = _drop_best_days(dr, bret, 10)
    cuts["drop_best_20_days"] = _drop_best_days(dr, bret, 20)
    risk_detail = _beta_capture(dr.to_numpy(), bret.to_numpy())

    # ---- placebo (daily marks for speed) --------------------------------
    print("placebo (daily marks) ...", flush=True)
    ts_d, o_d, c_d = bt.panel(SYMBOLS, START, END, "1D", warmup_days=0)
    W_d, w_daily_d, parts_d, daily_d = build_weights(
        ts_d, o_d, c_d, PRIMARY, return_daily=True)
    s_act, _, _, _ = _metrics_daily(ts_d, o_d, c_d, W_d, cost=HEADLINE_COST)
    nd = len(w_daily_d)
    print(f"  actual daily-mark CAGR {s_act['cagr']*100:.2f}%  "
          f"DD {s_act['max_drawdown']*100:.2f}%", flush=True)

    block_draws = _block_shuffle_rows(w_daily_d, block=20, draws=200, seed=7)
    block_stats = _placebo_stats(ts_d, o_d, c_d, block_draws)
    block_cagr = np.array([x["cagr"] for x in block_stats])
    block_dd = np.array([x["max_drawdown"] for x in block_stats])
    block_sharpe = np.array([x["sharpe"] for x in block_stats])
    block_expo = np.array([x["exposure"] for x in block_stats])

    # SPY-gate circular shift: keep the QQQ ladder and brake, break the
    # broad-market confirmation alignment.  Rebuild the state machine.
    dates_d, _, last_d = bt.day_bounds(ts_d)
    sess_d = pd.DatetimeIndex(dates_d[last_d])
    pos_d = daily_d.index.get_indexer(sess_d)
    s_ma_full = daily_d["SPY"].rolling(int(PRIMARY["spy_sma"]),
                                       min_periods=int(PRIMARY["spy_sma"])).mean()
    spy_up_full = (daily_d["SPY"] > s_ma_full).fillna(False).to_numpy()
    rng = np.random.default_rng(11)
    shift_draws = []
    shifts = []
    for _ in range(200):
        k = int(rng.integers(20, len(daily_d) - 20))
        shifts.append(k)
        W_full_s, _ = _session_targets(
            daily_d, PRIMARY, spy_up_override=np.roll(spy_up_full, k))
        shift_draws.append(W_full_s[pos_d])
    shift_stats = _placebo_stats(ts_d, o_d, c_d, shift_draws)
    shift_cagr = np.array([x["cagr"] for x in shift_stats])
    shift_dd = np.array([x["max_drawdown"] for x in shift_stats])
    shift_sharpe = np.array([x["sharpe"] for x in shift_stats])

    placebo = {
        "block_shuffle_20d": {
            "draws": 200,
            "actual_cagr": float(s_act["cagr"]),
            "actual_dd": float(s_act["max_drawdown"]),
            "actual_sharpe": float(s_act["sharpe"]),
            "cagr_pct_rank": _pct_rank(block_cagr, s_act["cagr"]),
            "cagr_mean": float(np.mean(block_cagr)),
            "cagr_p05": float(np.percentile(block_cagr, 5)),
            "cagr_p50": float(np.percentile(block_cagr, 50)),
            "cagr_p95": float(np.percentile(block_cagr, 95)),
            "dd_median": float(np.median(block_dd)),
            "sharpe_median": float(np.median(block_sharpe)),
            "exposure_mean": float(np.mean(block_expo)),
        },
        "spy_gate_shift": {
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
    print(f"  SPY-shift rank      {placebo['spy_gate_shift']['cagr_pct_rank']:.3f}  "
          f"(median {np.median(shift_cagr)*100:.2f}%)", flush=True)

    # ---- execution-delay diagnostic -------------------------------------
    lag_diag = {}
    for k in (0, 1, 2, 3, 5):
        wk = (w_daily_d.copy() if k == 0
              else np.vstack([np.zeros((k, len(SYMBOLS))), w_daily_d[:-k]]))
        sk, _, _, _ = _metrics_daily(ts_d, o_d, c_d, wk, cost=HEADLINE_COST)
        lag_diag[f"lag_{k}"] = _summary(sk)
        print(f"  lag {k}: CAGR {sk['cagr']*100:6.2f}%  DD "
              f"{sk['max_drawdown']*100:5.2f}%  Sharpe {sk['sharpe']:4.2f}", flush=True)

    # ---- neighbour surface (post-hoc robustness, daily marks) -----------
    print("neighbour surface (daily marks) ...", flush=True)
    surface = {}
    for qsma in (130, 140, 150, 160, 170):
        for brake in (0.12, 0.15, 0.20):
            p = dict(PRIMARY); p.update(qqq_sma=qsma, brake_dd=brake)
            Ws = build_weights(ts_d, o_d, c_d, p)
            ss, _, _, _ = _metrics_daily(ts_d, o_d, c_d, Ws, cost=HEADLINE_COST)
            surface[f"q{qsma}_b{int(brake*100)}"] = _summary(ss)
    for ssma in (180, 200, 220):
        p = dict(PRIMARY); p.update(spy_sma=ssma)
        Ws = build_weights(ts_d, o_d, c_d, p)
        ss, _, _, _ = _metrics_daily(ts_d, o_d, c_d, Ws, cost=HEADLINE_COST)
        surface[f"spy{ssma}"] = _summary(ss)
    for name, v in surface.items():
        print(f"  {name:14s} CAGR {v['cagr']*100:6.2f}%  DD "
              f"{v['max_drawdown']*100:5.2f}%", flush=True)

    # ---- exposure / state diagnostics -----------------------------------
    state_days = {str(k): int((parts_1m["state"] == k).sum()) for k in (0, 1, 2)}
    mean_weights = w_daily_1m.mean(axis=0)
    m1 = parts_1m["state"] == 1
    exposure_detail = {
        "mean_weight_qqq": float(mean_weights[COL_Q]),
        "mean_weight_tqqq": float(mean_weights[COL_T]),
        "mean_weight_bil": float(mean_weights[COL_B]),
        "mean_row_sum": float(w_daily_1m.sum(axis=1).mean()),
        "state_days": state_days,
        "state_switches": int(np.sum(np.diff(parts_1m["state"]) != 0)),
        "brake_days": int(parts_1m["brake"].sum()),
        "brake_triggers": int(parts_1m["brake_rearms"]),
        "tqqq_days": int(m1.sum()),
        "tqqq_mean_scale": float(parts_1m["scale"][m1].mean()),
        "tqqq_scale_bind_fraction": float(np.mean(parts_1m["scale"][m1] < 0.99)),
        "tqqq_scale_min": float(parts_1m["scale"][m1].min()) if m1.any() else None,
    }

    # ---- concentration / episodes ---------------------------------------
    top10 = np.sort(dr.to_numpy())[-10:]
    total_log = float(np.sum(np.log1p(dr.to_numpy())))
    concentration = {
        "top10_log_share_of_total": (float(np.sum(np.log1p(top10)) / total_log)
                                     if total_log != 0 else None),
        "best_day": float(top10[-1]),
        "worst_day": float(np.min(dr.to_numpy())),
        "positive_day_fraction": float(np.mean(dr.to_numpy() > 0)),
    }
    episodes = {}
    for name, a, b in (
        ("2018_q4", "2018-09-20", "2018-12-31"),
        ("2018_full", "2018-01-02", "2018-12-31"),
        ("2020_covid", "2020-02-19", "2020-03-23"),
        ("2020_recovery", "2020-03-23", "2020-06-30"),
        ("2022_bear", "2022-01-03", "2022-10-14"),
        ("2022_full", "2022-01-03", "2022-12-30"),
        ("2023_full", "2023-01-03", "2023-12-29"),
    ):
        episodes[name] = _episode(r1["ts"], r1["equity"], c[:, COL_T], a, b)

    max_dd_window = _max_dd_window(r1["ts"], r1["equity"])

    # ---- result ----------------------------------------------------------
    result = {
        "meta": {
            "slug": "spy-confirmed-trend",
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
                     "Signals use QQQ/TQQQ 15:59 closes and SPY adjusted daily "
                     "closes through the prior session; fills at the next "
                     "session open. SPY is signal-only and never held.",
        },
        "benchmark": _summary(bench),
        "headline": headline,
        "yearly": yearly,
        "yearly_daily": yearly_daily,
        "yearly_exposure": yearly_expo,
        "grid": grid,
        "ablations": ablations,
        "subperiods": subperiods,
        "cuts": cuts,
        "placebo": placebo,
        "lag_diagnostic": lag_diag,
        "neighbour_surface_daily": surface,
        "concentration": concentration,
        "exposure_detail": exposure_detail,
        "risk_detail": risk_detail,
        "max_drawdown_window": max_dd_window,
        "episodes": episodes,
    }
    result = _round(result)
    out_path = HERE / "result.json"
    with open(out_path, "w") as fh:
        json.dump(result, fh, indent=2, sort_keys=False)
    print(f"wrote {out_path}", flush=True)
    return result


if __name__ == "__main__":
    main()
