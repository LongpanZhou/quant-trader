"""52-week-high trend TQQQ — development backtest.

Frozen specification (see HYPOTHESIS.md):

  gate    : QQQ close within 8% of its 52-week intraday high
            and above its 20-session SMA
  exit    : QQQ 10% below the 52-week high (2 consecutive closes)
            or QQQ below its prior 20-session closing low (1 close)
  size    : TQQQ weight = min(1, 0.85 / 20-session annualised TQQQ vol)
  cash    : BIL

Signals use official adjusted daily OHLC through the session close; fills are
next-open on the daily panel derived from the 1-minute archive in research/bt.py.
Only 2016-01-04 .. 2023-12-29 is ever loaded.  2024-2026 is the lead's holdout
and is not read here.

Run:
    $env:PYTHONPATH = "C:\\Users\\27175\\AppData\\Local\\Temp\\opencode\\pylibs"
    $env:BT_THREADS = "1"
    python research/new/tqqq-52week-high/strategy.py
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

DEV_START = "2016-01-04"
DEV_END = "2023-12-29"
DATA_DIR = ROOT / "data" / "intraday-hf"
OUT_DIR = Path(__file__).resolve().parent

# Frozen base: mandate design point, fixed before the grid.  It happens to be
# the highest-CAGR cell in the 8-cell grid (disclosed in the report).
# Revision 2 (see HYPOTHESIS.md): the 20-day low is a 20-day *closing* low, the
# standard Donchian definition.  Revision 1 used intraday lows plus a 2% buffer
# and the low exit never fired, so it did not implement the mandate.
BASE = dict(
    entry_dist=0.08,
    entry_confirm=1,
    exit_dd=0.10,
    dd_confirm=2,
    low_n=20,
    low_source="close",
    low_buf=0.0,
    low_confirm=1,
    trend_n=20,
    high_n=252,
    high_source="high",
    target_vol=0.85,
    vol_window=20,
    signal_base="QQQ",
    use_trend=True,
)

# Pre-registered 8-cell grid (HYPOTHESIS.md, revision 2).
GRID = {
    "base": {},
    "entry_5": {"entry_dist": 0.05},
    "entry_10": {"entry_dist": 0.10},
    "exit_dd_8": {"exit_dd": 0.08},
    "exit_dd_12": {"exit_dd": 0.12},
    "dd_confirm_3": {"dd_confirm": 3},
    "low_buf_2": {"low_buf": 0.02},
    "tv_0.65": {"target_vol": 0.65},
}

_SIGNAL_CACHE: dict = {}


# --------------------------------------------------------------------------- data
def _daily_ohlc(symbol: str, end: str = DEV_END) -> pd.DataFrame:
    """Adjusted daily OHLC, hard-filtered at `end` (the holdout is never read)."""
    end_date = pd.Timestamp(end).date()
    d = pd.read_parquet(
        DATA_DIR / f"{symbol}-1d-yahoo.parquet",
        columns=["date", "open", "high", "low", "close", "adjclose"],
        filters=[("date", "<=", end_date)],
    )
    d["date"] = pd.to_datetime(d["date"])
    factor = d["adjclose"].astype(float) / d["close"].astype(float)
    out = pd.DataFrame({"date": d["date"]})
    for col in ("open", "high", "low", "close"):
        out[col] = d[col].astype(float) * factor
    return out.sort_values("date").reset_index(drop=True)


def _signal_data(end: str = DEV_END, signal_base: str = "QQQ") -> dict:
    """Daily arrays for the state machine and the vol target."""
    key = (end, signal_base)
    if key in _SIGNAL_CACHE:
        return _SIGNAL_CACHE[key]
    qq = _daily_ohlc("QQQ", end=end)
    tt = _daily_ohlc("TQQQ", end=end)
    if len(qq) != len(tt) or not (qq["date"].to_numpy() == tt["date"].to_numpy()).all():
        raise RuntimeError("QQQ/TQQQ daily calendars differ")
    base = qq if signal_base == "QQQ" else tt
    q = base["close"].to_numpy(float)
    high = base["high"].to_numpy(float)
    low = base["low"].to_numpy(float)
    rt = np.zeros(len(tt))
    rt[1:] = np.log(tt["close"].to_numpy(float)[1:] / tt["close"].to_numpy(float)[:-1])
    out = {
        "dates": pd.DatetimeIndex(qq["date"]),
        "close": q,
        "high": high,
        "low": low,
        "tqqq_close": tt["close"].to_numpy(float),
        "high_n_max": pd.Series(high).rolling(252).max().to_numpy(),
        "sma_trend": pd.Series(q).rolling(20).mean().to_numpy(),
        "vol": pd.Series(rt).rolling(20).std().to_numpy() * np.sqrt(252.0),
    }
    # The windows are parameters; cache the raw series and rebuild per params.
    _SIGNAL_CACHE[key] = out
    return out


# --------------------------------------------------------------------------- signal
def _rolling_high(x: np.ndarray, n: int) -> np.ndarray:
    return pd.Series(x).rolling(n).max().to_numpy()


def _rolling_low_prev(x: np.ndarray, n: int) -> np.ndarray:
    """Lowest low of the *prior* n sessions (current session excluded)."""
    return pd.Series(x).rolling(n).min().shift(1).to_numpy()


def _daily_state(sig: dict, p: dict):
    """State machine on the daily calendar, plus exit-cause counts."""
    q = sig["close"]
    high = sig["high"]
    low = sig["low"]
    n = len(q)
    warm = max(int(p["high_n"]), int(p["trend_n"]), int(p["low_n"]), 1) + 1
    high_ref = q if p.get("high_source", "high") == "close" else high
    high_n = _rolling_high(high_ref, int(p["high_n"]))
    trend = pd.Series(q).rolling(int(p["trend_n"])).mean().to_numpy() if int(p["trend_n"]) > 1 else q
    low_ref = q if p.get("low_source", "low") == "close" else low
    low_n = _rolling_low_prev(low_ref, int(p["low_n"]))
    state = np.zeros(n, dtype=np.int8)
    on = 0
    dd_run = 0
    low_run = 0
    ent_run = 0
    counts = {"entries": 0, "exits_dd": 0, "exits_low": 0}
    for i in range(warm, n):
        dist = q[i] / high_n[i] - 1.0
        if on == 0:
            trend_ok = (q[i] > trend[i]) if p["use_trend"] else True
            ent_run = ent_run + 1 if (dist >= -p["entry_dist"] and trend_ok) else 0
            if ent_run >= p.get("entry_confirm", 1):
                on = 1
                dd_run = low_run = 0
                ent_run = 0
                counts["entries"] += 1
        else:
            dd_hit = dist <= -p["exit_dd"]
            low_hit = q[i] < low_n[i] * (1.0 - p["low_buf"])
            dd_run = dd_run + 1 if dd_hit else 0
            low_run = low_run + 1 if low_hit else 0
            if dd_run >= p["dd_confirm"] or low_run >= p["low_confirm"]:
                on = 0
                if dd_run >= p["dd_confirm"]:
                    counts["exits_dd"] += 1
                else:
                    counts["exits_low"] += 1
                dd_run = low_run = 0
        state[i] = on
    return state, counts


def _to_panel(values: np.ndarray, sig_dates: pd.DatetimeIndex,
              panel_dates: pd.DatetimeIndex) -> np.ndarray:
    s = pd.Series(values, index=sig_dates)
    s = s[~s.index.duplicated(keep="last")]
    return s.reindex(panel_dates).ffill().to_numpy()


def build_weights(ts, o, c, params: dict | None = None, end: str | None = None,
                  always_on: bool = False) -> np.ndarray:
    """Target weights (n, 3) = [QQQ, TQQQ, BIL] for the panel bars.

    `params` overrides BASE; `end` is used only by the truncation test.
    `o` and `c` are accepted for the shared strategy signature; the signal is
    built from the official daily OHLC so that it is independent of the fill
    panel and identical in the truncation test.

    A panel that extends past `end` raises.  The lead's one-shot holdout lifts
    this by setting the module-level DEV_END before the second call, so the
    development path can never silently ffill 2024-2026 with a 2023 signal.
    """
    if end is None:
        end = DEV_END
    last_bar = pd.Timestamp(pd.to_datetime(ts[-1])).date()
    if last_bar > pd.Timestamp(end).date():
        raise ValueError(
            f"panel ends {last_bar}, past the development window {end}; "
            "the holdout must be authorized explicitly")
    p = dict(BASE)
    if params:
        p.update(params)
    sig = _signal_data(end=end, signal_base=p["signal_base"])
    state, _ = _daily_state(sig, p)

    # Session dates of the panel (works for both a daily panel and a 1-minute
    # panel).  The daily state is mapped to sessions, then expanded to bars with
    # a one-session lag so that a minute-panel call is also causal: every bar of
    # session k carries the state known at the close of k-1, and the last bar of
    # session k carries the state known at the close of k (executed at k+1 open).
    dates = bt.session_dates(ts)
    first, last = bt.day_bounds_from_dates(dates)
    sess = pd.DatetimeIndex(pd.to_datetime(dates[first]))
    s = _to_panel(state.astype(float), sig["dates"], sess)
    v = _to_panel(sig["vol"], sig["dates"], sess)
    s = np.nan_to_num(s, nan=0.0)
    if always_on:
        s = np.ones_like(s)
    vt = np.clip(p["target_vol"] / np.where(v > 0, v, np.inf), 0.0, 1.0)
    w_sess = np.clip(s * np.nan_to_num(vt, nan=0.0), 0.0, 1.0)

    w = np.zeros(len(ts))
    for k in range(len(first)):
        prev = w_sess[k - 1] if k > 0 else 0.0
        w[first[k]:last[k]] = prev
        w[last[k]] = w_sess[k]
    W = np.zeros((len(w), 3))
    W[:, 1] = w
    W[:, 2] = 1.0 - w
    return W


# --------------------------------------------------------------------------- metrics
def _series_stats(ts, equity) -> dict:
    eq = np.asarray(equity, float)
    rets = np.diff(eq) / eq[:-1]
    years = (ts[-1] - ts[0]).total_seconds() / (365.25 * 86400)
    peak = np.maximum.accumulate(eq)
    downside = np.minimum(rets, 0.0)
    std = float(np.std(rets, ddof=0))
    return {
        "cagr": float((eq[-1] / eq[0]) ** (1.0 / years) - 1.0),
        "total_return": float(eq[-1] / eq[0] - 1.0),
        "max_drawdown": float(-(eq / peak - 1.0).min()),
        "volatility": std * np.sqrt(252.0),
        "sharpe": float(np.mean(rets) / std * np.sqrt(252.0)) if std > 0 else 0.0,
        "sortino": float(np.mean(rets) / np.sqrt(np.mean(downside ** 2)) * np.sqrt(252.0))
        if np.mean(downside ** 2) > 0 else 0.0,
        "years": years,
    }


def _extras(ts, res, W, tqqq_close) -> dict:
    eq = res["equity"]
    s = _series_stats(ts, eq)
    dates = pd.DatetimeIndex(pd.to_datetime(ts)).normalize()
    er = np.diff(eq) / eq[:-1]
    tr = np.diff(tqqq_close) / tqqq_close[:-1]
    yearly = {}
    for y in sorted(set(dates.year)):
        m = dates.year == y
        e = eq[m]
        if len(e) > 1:
            yearly[str(int(y))] = float(e[-1] / e[0] - 1.0)
    peak = np.maximum.accumulate(eq)
    dd = eq / peak - 1.0
    itr = int(np.argmin(dd))
    ipk = int(np.argmax(eq[:itr + 1])) if itr > 0 else 0
    worst = np.argsort(er)[:5]
    s.update({
        "exposure": float(np.mean((eq - res["cash"]) / eq)),
        "tqqq_exposure": float(W[:, 1].mean()),
        "time_in_tqqq": float((W[:, 1] > 1e-12).mean()),
        "fills": int(res["fills"]),
        "turnover": float(res["turnover"]),
        "corr_tqqq": float(np.corrcoef(er, tr)[0, 1]),
        "ending_equity": float(eq[-1]),
        "yearly": yearly,
        "max_dd_peak": str(dates[ipk]),
        "max_dd_trough": str(dates[itr]),
        "worst_days": {str(dates[i + 1].date()): float(er[i]) for i in worst},
    })
    return s


def _run(ts, o, c, W, slippage_bps=1.0) -> dict:
    return bt.simulate(ts, o, c, W, band=0.02, slippage_bps=float(slippage_bps))


def _metrics(ts, o, c, W, tqqq_close, slip=1.0) -> dict:
    return _extras(ts, _run(ts, o, c, W, slip), W, tqqq_close)


def _cut(ts, o, c, W, start, tqqq_close) -> dict:
    i = bt.start_index(ts, start)
    res = _run(ts[i:], o[i:], c[i:], W[i:], 1.0)
    s = _series_stats(ts[i:], res["equity"])
    s["tqqq_exposure"] = float(W[i:, 1].mean())
    return s


# --------------------------------------------------------------------------- tests
def _grid(ts, o, c, tqqq_close) -> dict:
    out = {}
    for name, override in GRID.items():
        p = dict(BASE)
        p.update(override)
        W = build_weights(ts, o, c, p)
        m = _metrics(ts, o, c, W, tqqq_close)
        out[name] = {
            "params": p,
            "cagr": m["cagr"], "max_drawdown": m["max_drawdown"],
            "sharpe": m["sharpe"], "tqqq_exposure": m["tqqq_exposure"],
            "time_in_tqqq": m["time_in_tqqq"],
            "fills": m["fills"], "yearly": m["yearly"],
        }
    return out


def _ablations(ts, o, c, tqqq_close) -> dict:
    variants = {
        "no_vol_target": ({"target_vol": 99.0}, False),
        "no_low_exit": ({"low_confirm": 10_000}, False),
        "no_dd_exit": ({"dd_confirm": 10_000}, False),
        "no_52w_gate": ({"entry_dist": 9.99, "exit_dd": 9.99}, False),
        "no_trend_gate": ({"use_trend": False}, False),
        "close_52w_high": ({"high_source": "close"}, False),
        "tqqq_basis": ({"signal_base": "TQQQ", "entry_dist": 0.20,
                        "exit_dd": 0.25, "low_buf": 0.05}, False),
        "v1_intraday_low_2pct": ({"low_source": "low", "low_buf": 0.02,
                                  "low_confirm": 2}, False),
        "always_long": ({}, True),
    }
    out = {}
    for name, (override, always) in variants.items():
        p = dict(BASE)
        p.update(override)
        W = build_weights(ts, o, c, p, always_on=always)
        m = _metrics(ts, o, c, W, tqqq_close)
        _, counts = _daily_state(
            _signal_data(end=DEV_END, signal_base=p["signal_base"]), p)
        out[name] = {
            "params": p, "cagr": m["cagr"], "max_drawdown": m["max_drawdown"],
            "sharpe": m["sharpe"], "tqqq_exposure": m["tqqq_exposure"],
            "fills": m["fills"], "event_counts": counts,
        }
    return out


def _neighbourhood(ts, o, c, tqqq_close) -> dict:
    variants = {
        "entry_6": {"entry_dist": 0.06},
        "entry_7": {"entry_dist": 0.07},
        "entry_9": {"entry_dist": 0.09},
        "entry_11": {"entry_dist": 0.11},
        "exit_dd_9": {"exit_dd": 0.09},
        "exit_dd_11": {"exit_dd": 0.11},
        "low_buf_0.5": {"low_buf": 0.005},
        "low_buf_1": {"low_buf": 0.01},
        "low_buf_2": {"low_buf": 0.02},
        "low_n_15": {"low_n": 15},
        "low_n_25": {"low_n": 25},
        "trend_n_15": {"trend_n": 15},
        "trend_n_30": {"trend_n": 30},
        "vol_window_15": {"vol_window": 15},
        "vol_window_30": {"vol_window": 30},
        "tv_0.75": {"target_vol": 0.75},
        "tv_0.95": {"target_vol": 0.95},
    }
    out = {}
    for name, override in variants.items():
        p = dict(BASE)
        p.update(override)
        W = build_weights(ts, o, c, p)
        m = _metrics(ts, o, c, W, tqqq_close)
        out[name] = {
            "params": p, "cagr": m["cagr"], "max_drawdown": m["max_drawdown"],
            "sharpe": m["sharpe"], "tqqq_exposure": m["tqqq_exposure"],
            "fills": m["fills"],
        }
    return out


def _lag_placebo(ts, o, c, W, tqqq_close) -> dict:
    out = {}
    for lag in (1, 5, 10, 20):
        wd = np.r_[np.zeros(lag), W[:-lag, 1]]
        Wd = np.zeros_like(W)
        Wd[:, 1] = wd
        Wd[:, 2] = 1.0 - wd
        m = _metrics(ts, o, c, Wd, tqqq_close)
        out[f"lag_{lag}"] = {"cagr": m["cagr"], "max_drawdown": m["max_drawdown"],
                             "sharpe": m["sharpe"], "tqqq_exposure": m["tqqq_exposure"]}
    return out


def _circular_placebo(ts, o, c, W, tqqq_close, draws=200, seed=7) -> dict:
    rng = np.random.default_rng(seed)
    base = _metrics(ts, o, c, W, tqqq_close)
    w = W[:, 1]
    rows = []
    for _ in range(draws):
        k = int(rng.integers(20, len(w) - 20))
        wd = np.roll(w, k)
        Wd = np.zeros_like(W)
        Wd[:, 1] = wd
        Wd[:, 2] = 1.0 - wd
        s = _series_stats(ts, _run(ts, o, c, Wd, 1.0)["equity"])
        rows.append((s["cagr"], s["max_drawdown"], s["sharpe"]))
    arr = np.array(rows)
    return {
        "draws": draws,
        "cagr_median": float(np.median(arr[:, 0])),
        "cagr_p90": float(np.percentile(arr[:, 0], 90)),
        "cagr_p95": float(np.percentile(arr[:, 0], 95)),
        "cagr_max": float(arr[:, 0].max()),
        "dd_median": float(np.median(arr[:, 1])),
        "dd_min": float(arr[:, 1].min()),
        "sharpe_median": float(np.median(arr[:, 2])),
        "sharpe_max": float(arr[:, 2].max()),
        "base_cagr_percentile": float((arr[:, 0] < base["cagr"]).mean()),
        "base_sharpe_percentile": float((arr[:, 2] < base["sharpe"]).mean()),
    }


def _bernoulli_placebo(ts, o, c, W, tqqq_close, draws=200, seed=11) -> dict:
    """Same number of invested days, randomly placed; destroys clustering."""
    rng = np.random.default_rng(seed)
    base = _metrics(ts, o, c, W, tqqq_close)
    w = W[:, 1]
    p = float((w > 0).mean())
    rows = []
    for _ in range(draws):
        on = rng.random(len(w)) < p
        wd = np.where(on, w, 0.0)
        Wd = np.zeros_like(W)
        Wd[:, 1] = wd
        Wd[:, 2] = 1.0 - wd
        s = _series_stats(ts, _run(ts, o, c, Wd, 1.0)["equity"])
        rows.append((s["cagr"], s["max_drawdown"], s["sharpe"]))
    arr = np.array(rows)
    return {
        "draws": draws,
        "cagr_median": float(np.median(arr[:, 0])),
        "cagr_p90": float(np.percentile(arr[:, 0], 90)),
        "cagr_p95": float(np.percentile(arr[:, 0], 95)),
        "cagr_max": float(arr[:, 0].max()),
        "dd_median": float(np.median(arr[:, 1])),
        "dd_min": float(arr[:, 1].min()),
        "sharpe_median": float(np.median(arr[:, 2])),
        "sharpe_max": float(arr[:, 2].max()),
        "base_cagr_percentile": float((arr[:, 0] < base["cagr"]).mean()),
        "base_sharpe_percentile": float((arr[:, 2] < base["sharpe"]).mean()),
    }


def _subperiods(ts, eq) -> dict:
    dates = pd.DatetimeIndex(pd.to_datetime(ts)).normalize()
    out = {}
    for name, lo, hi in (
        ("2016_2019", 2016, 2019), ("2020_2021", 2020, 2021), ("2022_2023", 2022, 2023),
    ):
        m = (dates.year >= lo) & (dates.year <= hi)
        idx = np.flatnonzero(m)
        if len(idx) < 2:
            continue
        out[name] = _series_stats(ts[idx[0]:idx[-1] + 1], eq[idx[0]:idx[-1] + 1])
    return out


def _leave_one_year_out(ts, eq) -> dict:
    dates = pd.DatetimeIndex(pd.to_datetime(ts)).normalize()
    years = sorted(set(dates.year))
    eq = np.asarray(eq, float)
    total = eq[-1] / eq[0]
    ann = {}
    for y in years:
        m = dates.year == y
        e = eq[m]
        if len(e) > 1:
            ann[int(y)] = float(e[-1] / e[0])
    rows = {}
    for y, factor in ann.items():
        rows[str(y)] = float((total / factor) ** (1.0 / (len(years) - 1)) - 1.0)
    return {"annual_factors": {str(k): v for k, v in ann.items()},
            "cagr_without_year": rows,
            "min_cagr_without_year": float(min(rows.values())),
            "year_of_min": min(rows, key=rows.get)}


def _episodes(ts, eq, tqqq_close) -> dict:
    dates = pd.DatetimeIndex(pd.to_datetime(ts)).normalize().tz_localize(None)
    tq = np.asarray(tqqq_close, float)
    episodes = {
        "2018_q4_bear": ("2018-09-20", "2018-12-24"),
        "2020_covid": ("2020-02-19", "2020-03-23"),
        "2022_bear": ("2022-01-03", "2022-10-14"),
        "2019_recovery": ("2019-01-02", "2019-12-31"),
        "2023_recovery": ("2023-01-03", "2023-12-29"),
    }
    out = {}
    for name, (start, end) in episodes.items():
        i = int(np.searchsorted(dates, pd.Timestamp(start)))
        j = int(np.searchsorted(dates, pd.Timestamp(end), side="right")) - 1
        if i < 0 or j <= i or j >= len(eq):
            continue
        out[name] = {
            "start": str(dates[i].date()), "end": str(dates[j].date()),
            "strategy": float(eq[j] / eq[i] - 1.0),
            "tqqq": float(tq[j] / tq[i] - 1.0),
        }
    return out


def _causality(ts, o, c) -> dict:
    cut = "2021-12-31"
    i = bt.start_index(ts, cut)
    W_full = build_weights(ts, o, c)
    W_trunc = build_weights(ts[:i], o[:i], c[:i], end=cut)
    return {
        "truncation_date": cut,
        "bars_before_cut": int(i),
        "weight_prefix_equal": bool(np.allclose(W_full[:i], W_trunc, atol=0.0)),
        "max_abs_diff": float(np.max(np.abs(W_full[:i] - W_trunc))) if i else 0.0,
    }


def _sma_base(ts, o, c, tqqq_close) -> dict:
    """165-day QQQ SMA + TQQQ/BIL — benchmark/correlation only, never an input."""
    qq = _daily_ohlc("QQQ")
    panel_dates = pd.DatetimeIndex(pd.to_datetime(ts)).normalize().tz_localize(None)
    q = pd.Series(qq["close"].to_numpy(float), index=pd.DatetimeIndex(qq["date"]))
    q = q[~q.index.duplicated(keep="last")].reindex(panel_dates).ffill()
    sma = q.rolling(165).mean()
    w = np.nan_to_num(np.where(q.to_numpy() > sma.to_numpy(), 1.0, 0.0))
    W = np.column_stack([np.zeros(len(ts)), w, 1.0 - w])
    return _metrics(ts, o, c, W, tqqq_close)


# --------------------------------------------------------------------------- main
def main() -> None:
    ts, o, c = bt.panel(("QQQ", "TQQQ", "BIL"), DEV_START, DEV_END, "1D", warmup_days=0)
    assert len(ts) > 1500
    assert pd.Timestamp(ts[-1]).date() <= pd.Timestamp(DEV_END).date()
    tqqq_close = c[:, 1]

    W = build_weights(ts, o, c)
    primary = {}
    for bps in (1.0, 5.0, 10.0):
        primary[f"{int(bps)}bp"] = _metrics(ts, o, c, W, tqqq_close, slip=bps)

    # state-machine event counts (not a return calculation)
    p = dict(BASE)
    _, counts = _daily_state(_signal_data(end=DEV_END, signal_base=p["signal_base"]), p)

    grid = _grid(ts, o, c, tqqq_close)
    ablations = _ablations(ts, o, c, tqqq_close)
    neigh = _neighbourhood(ts, o, c, tqqq_close)
    lag = _lag_placebo(ts, o, c, W, tqqq_close)
    circ = _circular_placebo(ts, o, c, W, tqqq_close)
    bern = _bernoulli_placebo(ts, o, c, W, tqqq_close)
    cuts = {d: _cut(ts, o, c, W, d, tqqq_close)
            for d in ("2017-01-03", "2018-01-02", "2019-01-02",
                      "2020-01-02", "2021-01-04", "2022-01-03")}
    res1 = _run(ts, o, c, W, 1.0)
    sub = _subperiods(ts, res1["equity"])
    loyo = _leave_one_year_out(ts, res1["equity"])
    episodes = _episodes(ts, res1["equity"], tqqq_close)
    causality = _causality(ts, o, c)

    benchmarks = {}
    for idx, name in ((1, "tqqq_buy_hold"), (0, "qqq_buy_hold"), (2, "bil_buy_hold")):
        benchmarks[name] = bt.benchmark(c[:, idx], ts, 252)
    sma_base = _sma_base(ts, o, c, tqqq_close)
    eq_base = res1["equity"]
    # correlation to the 165-SMA benchmark curve
    qq = _daily_ohlc("QQQ")
    panel_dates = pd.DatetimeIndex(pd.to_datetime(ts)).normalize().tz_localize(None)
    qser = pd.Series(qq["close"].to_numpy(float), index=pd.DatetimeIndex(qq["date"]))
    qser = qser[~qser.index.duplicated(keep="last")].reindex(panel_dates).ffill()
    sma_w = np.nan_to_num(np.where(qser.to_numpy() > qser.rolling(165).mean().to_numpy(), 1.0, 0.0))
    W_sma = np.column_stack([np.zeros(len(ts)), sma_w, 1.0 - sma_w])
    eq_sma = _run(ts, o, c, W_sma, 1.0)["equity"]
    corr_sma = float(np.corrcoef(np.diff(eq_base) / eq_base[:-1],
                                 np.diff(eq_sma) / eq_sma[:-1])[0, 1])

    s1 = primary["1bp"]
    result = {
        "agent": "tqqq-52week-high",
        "status": "dev_pass" if (s1["cagr"] > 0.3672 and s1["max_drawdown"] < 0.8229) else "dev_fail",
        "window": {"start": DEV_START, "end": DEV_END, "sessions": int(len(ts)),
                   "marks": "1-minute-derived daily", "fills": "next-open", "band": 0.02},
        "verdict": {
            "bar_cagr": 0.3672, "bar_max_drawdown": 0.8229, "bar_sharpe": 0.82,
            "passes_bar": bool(s1["cagr"] > 0.3672 and s1["max_drawdown"] < 0.8229),
            "meets_dd_target_60": bool(s1["max_drawdown"] < 0.60),
            "cagr_minus_bar_pp": float((s1["cagr"] - 0.3672) * 100),
        },
        "params": BASE,
        "event_counts": counts,
        "primary": {k: {kk: vv for kk, vv in v.items()} for k, v in primary.items()},
        "grid": grid,
        "ablations": ablations,
        "neighbourhood": neigh,
        "lag_placebo": lag,
        "circular_shift_placebo": circ,
        "bernoulli_placebo": bern,
        "cut_tests": cuts,
        "subperiods": sub,
        "leave_one_year_out": loyo,
        "episodes": episodes,
        "causality": causality,
        "benchmarks": benchmarks,
        "sma165_base_benchmark_only": sma_base,
        "corr_to_sma165_base": corr_sma,
        "notes": {
            "signal": "official adjusted daily OHLC through the session close",
            "execution": "bt.panel daily bars from the 1-minute archive; next-open fills",
            "state": "QQQ within 8% of 252d high and above SMA20; exit 20d closing low"
                     " (1 close) or -10% from high (2 closes)",
            "vol_target": "w = state * min(1, 0.85 / annualised 20-session TQQQ vol)",
            "holdout": "2024-2026 never loaded",
            "grid": "pre-registered 8 cells; base is the mandate design point and"
                    " also the highest-CAGR cell in this grid (disclosed)",
            "spec_revision": "v2 uses the 20-day closing low; v1 (intraday low + 2%"
                             " buffer) never triggered the low exit and is reported as"
                             " an ablation (42.21% CAGR / 45.4% DD / 1.03 Sharpe)",
        },
    }
    with open(OUT_DIR / "result.json", "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2)

    print(f"\nDEV 2016-01-04..2023-12-29  sessions {len(ts)}")
    print(f"events {counts}")
    print(f"TQQQ buy-hold  CAGR {benchmarks['tqqq_buy_hold']['cagr']*100:.2f}%  "
          f"DD {benchmarks['tqqq_buy_hold']['max_drawdown']*100:.2f}%  "
          f"Sharpe {benchmarks['tqqq_buy_hold']['sharpe']:.2f}")
    for k in ("1bp", "5bp", "10bp"):
        m = primary[k]
        print(f"{k:4s} CAGR {m['cagr']*100:6.2f}%  DD {m['max_drawdown']*100:5.1f}%  "
              f"Sharpe {m['sharpe']:.2f}  TQQQ expo {m['tqqq_exposure']*100:5.1f}%  "
              f"fills {m['fills']:4d}  corr {m['corr_tqqq']:.3f}")
    print("\ngrid")
    for name, g in grid.items():
        print(f"  {name:16s} CAGR {g['cagr']*100:6.2f}%  DD {g['max_drawdown']*100:5.1f}%  "
              f"Sharpe {g['sharpe']:.2f}  expo {g['tqqq_exposure']*100:5.1f}%")
    print("\nablations")
    for name, g in ablations.items():
        print(f"  {name:22s} CAGR {g['cagr']*100:6.2f}%  DD {g['max_drawdown']*100:5.1f}%  "
              f"Sharpe {g['sharpe']:.2f}  expo {g['tqqq_exposure']*100:5.1f}%")
    print("\nneighbourhood")
    for name, g in neigh.items():
        print(f"  {name:16s} CAGR {g['cagr']*100:6.2f}%  DD {g['max_drawdown']*100:5.1f}%  "
              f"Sharpe {g['sharpe']:.2f}")
    print(f"\nplacebo (circular shift): median CAGR "
          f"{circ['cagr_median']*100:.2f}%  p95 {circ['cagr_p95']*100:.2f}%  "
          f"base pct {circ['base_cagr_percentile']*100:.1f}")
    print("placebo (random days):    median CAGR "
          f"{bern['cagr_median']*100:.2f}%  p95 {bern['cagr_p95']*100:.2f}%  "
          f"base pct {bern['base_cagr_percentile']*100:.1f}")
    print(f"\nleave-one-year-out: min CAGR {loyo['min_cagr_without_year']*100:.2f}% "
          f"(drop {loyo['year_of_min']})")
    print(f"causality: {causality}")
    print(f"\nwritten: {OUT_DIR / 'result.json'}")


if __name__ == "__main__":
    main()
