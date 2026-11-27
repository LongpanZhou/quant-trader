"""Shared 1-minute research backtester for the strategy agents.

Import from a script at the repo root:

    import sys
    sys.path.insert(0, "research")
    import bt

The data is the adjusted 1-minute QQQ/TQQQ/BIL archive under
`data/intraday-hf/`. Install requirements with:

    pip install -r scripts/requirements-intraday.txt

All fills are at the next bar's open. Weights are long-only fractions of
equity and must sum to <= 1. The remainder is cash. Slippage is charged on
traded notional.

Speed: `simulate` runs in compiled Rust (research/simcore) when its DLL is
built, which is about 100x faster than the Python loop and gives the same
results. Build it once with
    cargo build --release --manifest-path research/simcore/Cargo.toml
Without the DLL, or with BT_PURE_PYTHON=1, the original Python loop runs.
`simulate_many` runs a batch of weight matrices in parallel, for sweeps.
"""

from __future__ import annotations

import ctypes
import hashlib
import os
from datetime import date, time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "intraday-hf"
CACHE_DIR = ROOT / "data" / "cache" / "research_panels"
DEFAULT_START = "2021-10-25"
DEFAULT_END = "2026-10-23"
START_EQUITY = 100_000.0

_PANEL_CACHE: dict = {}

# NYSE half-days: keep bars through 13:00 and discard after-hours prints that
# leaked into the 2016-2020 files.
HALF_DAYS = {
    date(2016, 11, 25), date(2017, 7, 3), date(2017, 11, 24),
    date(2018, 7, 3), date(2018, 11, 23), date(2018, 12, 24),
    date(2019, 7, 3), date(2019, 11, 29), date(2019, 12, 24),
    date(2020, 11, 27), date(2020, 12, 24), date(2021, 11, 26),
    date(2022, 11, 25), date(2023, 7, 3), date(2023, 11, 24),
    date(2024, 7, 3), date(2024, 11, 29), date(2024, 12, 24),
    date(2025, 7, 3), date(2025, 11, 28), date(2025, 12, 24),
}


_LOAD_1M_CACHE: dict = {}


def load_1m(symbol: str) -> pd.DataFrame:
    """Adjusted 1-minute bars in US/Eastern, regular session only."""
    src = DATA_DIR / f"{symbol}-1m.parquet"
    key = (symbol, int(src.stat().st_mtime) if src.exists() else 0)
    cached = _LOAD_1M_CACHE.get(key)
    if cached is not None:
        return cached
    df = pd.read_parquet(src)
    df["ts"] = pd.to_datetime(df["ts"], utc=True).dt.tz_convert("America/New_York")
    df = df[
        (df["ts"].dt.time >= pd.Timestamp("09:30").time())
        & (df["ts"].dt.time < pd.Timestamp("16:00").time())
    ].copy()
    df["date"] = df["ts"].dt.date

    # Half-days: discard after-hours prints after 13:00.
    after_close = df["date"].isin(HALF_DAYS) & (df["ts"].dt.time > time(13, 0))
    if after_close.any():
        df = df.loc[~after_close].copy()

    # BIL is raw in the source and had a 1:2 reverse split on 2017-11-30.
    if symbol == "BIL":
        before = df["date"] < pd.Timestamp("2017-11-30").date()
        for column in ("open", "high", "low", "close"):
            df.loc[before, column] *= 2.0

    daily = pd.read_parquet(DATA_DIR / f"{symbol}-1d-yahoo.parquet")
    daily["date"] = pd.to_datetime(daily["date"]).dt.date
    daily["factor"] = daily["adjclose"] / daily["close"]
    df = df.merge(daily[["date", "factor"]], on="date", how="left")
    df["factor"] = df["factor"].ffill().bfill()
    for column in ("open", "high", "low", "close"):
        df[column] = df[column] * df["factor"]
    out = df[["ts", "date", "open", "high", "low", "close", "volume"]]
    _LOAD_1M_CACHE.clear()
    _LOAD_1M_CACHE[key] = out
    return out


def resample(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    """Resample an indexed OHLCV frame. `rule` is '1min', '5min', '1h', '1D'."""
    if rule == "1min":
        return df
    out = df.resample(rule, origin="start_day").agg(
        {
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "volume": "sum",
        }
    )
    return out.dropna(subset=["close"])


def panel(
    symbols: tuple[str, ...],
    start: str = DEFAULT_START,
    end: str = DEFAULT_END,
    rule: str = "1D",
    warmup_days: int = 500,
) -> tuple[pd.DatetimeIndex, np.ndarray, np.ndarray]:
    """Aligned opens/closes for `symbols`, including pre-start warmup.

    QQQ is the base calendar: every other symbol is reindexed to it and
    forward-filled. This avoids dropping most minutes because BIL did not
    trade in a given minute.

    The returned frame starts `warmup_days` before `start` so indicators can
    warm up. Slice it with `bt.start_index(ts, start)` or use `bt.run`.

    Panels are cached under `data/cache/` keyed by the request and the source
    parquet mtimes. This keeps repeated agent runs from re-reading and
    re-resampling the same 1-minute data.
    """
    mtimes = []
    for symbol in symbols:
        path = DATA_DIR / f"{symbol}-1m.parquet"
        mtimes.append(int(path.stat().st_mtime) if path.exists() else 0)
    key_src = f"{symbols}|{start}|{end}|{rule}|{warmup_days}|{mtimes}"
    key = hashlib.md5(key_src.encode("utf-8")).hexdigest()[:16]
    cache_path = CACHE_DIR / f"panel_{key}.npz"
    if key in _PANEL_CACHE:
        return _PANEL_CACHE[key]
    if cache_path.exists():
        try:
            z = np.load(cache_path)
            ts = pd.to_datetime(z["ts"], unit="ns", utc=True).tz_convert("America/New_York")
            out = (ts, np.array(z["opens"]), np.array(z["closes"]))
            _PANEL_CACHE.clear()
            _PANEL_CACHE[key] = out
            return out
        except Exception:
            pass

    start_ts = pd.Timestamp(start, tz="America/New_York")
    load_start = start_ts - pd.Timedelta(days=warmup_days)
    end_ts = pd.Timestamp(end, tz="America/New_York").normalize() + pd.Timedelta(days=1)
    frames: dict[str, pd.DataFrame] = {}
    for symbol in symbols:
        df = load_1m(symbol)
        df = df[(df["ts"] >= load_start) & (df["ts"] < end_ts)].set_index("ts")
        frames[symbol] = resample(df, rule)

    base = frames["QQQ"].index
    opens = []
    closes = []
    for symbol in symbols:
        f = frames[symbol].reindex(base).ffill().bfill()
        opens.append(f["open"].to_numpy())
        closes.append(f["close"].to_numpy())
    ts = base
    opens_arr = np.column_stack(opens)
    closes_arr = np.column_stack(closes)
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        ts_ns = ts.tz_convert("UTC").tz_localize(None).astype("datetime64[ns]").asi8
        np.savez(cache_path, ts=ts_ns, opens=opens_arr, closes=closes_arr)
    except Exception:
        pass
    _PANEL_CACHE.clear()
    _PANEL_CACHE[key] = (ts, opens_arr, closes_arr)
    return ts, opens_arr, closes_arr


def start_index(ts: pd.DatetimeIndex, start: str) -> int:
    """First bar at or after `start`."""
    return int(ts.searchsorted(pd.Timestamp(start, tz="America/New_York")))


_SESSION_DATE_CACHE: dict = {}


def session_dates(ts: pd.DatetimeIndex) -> np.ndarray:
    """Vectorized `np.array([t.date() for t in ts])`.

    The per-element conversion used to dominate strategy weight construction
    on the 780k-bar panel.  Normalising in one vectorized call is ~100x faster
    and returns the same Python `date` objects.  The one-entry cache matters
    for sweeps, which rebuild weights hundreds of times on the same panel.
    """
    i8 = ts.asi8
    key = (len(i8), int(i8[0]) if len(i8) else 0, int(i8[-1]) if len(i8) else 0,
           int(i8[::1000].sum()) if len(i8) else 0, str(ts.tz))
    cached = _SESSION_DATE_CACHE.get(key)
    if cached is not None:
        return cached
    local = ts.tz_localize(None) if getattr(ts, "tz", None) is not None else ts
    dates = local.normalize().values.astype("datetime64[D]").astype(object)
    _SESSION_DATE_CACHE.clear()
    _SESSION_DATE_CACHE[key] = dates
    return dates


def day_bounds_from_dates(dates: np.ndarray):
    """First/last bar index of each session from a session-date array."""
    if len(dates) == 0:
        return np.array([], dtype=int), np.array([], dtype=int)
    first = np.flatnonzero(np.r_[True, dates[1:] != dates[:-1]])
    last = np.r_[first[1:] - 1, len(dates) - 1]
    return first, last


_DAY_BOUNDS_CACHE: dict = {}


def day_bounds(ts: pd.DatetimeIndex):
    """Cached (dates, first, last) session bounds for a 1-minute panel."""
    dates = session_dates(ts)
    key = id(dates)
    cached = _DAY_BOUNDS_CACHE.get(key)
    if cached is not None:
        return cached
    first, last = day_bounds_from_dates(dates)
    out = (dates, first, last)
    _DAY_BOUNDS_CACHE.clear()
    _DAY_BOUNDS_CACHE[key] = out
    return out


_DAY_ID_CACHE: dict = {}


def day_ids(ts: pd.DatetimeIndex) -> np.ndarray:
    """Cached per-bar session index (0..n_sessions-1)."""
    dates, first, _ = day_bounds(ts)
    key = id(dates)
    cached = _DAY_ID_CACHE.get(key)
    if cached is not None:
        return cached
    out = np.repeat(np.arange(len(first)), np.diff(np.r_[first, len(dates)]))
    _DAY_ID_CACHE.clear()
    _DAY_ID_CACHE[key] = out
    return out


def daily_last(values, ts: pd.DatetimeIndex) -> pd.Series:
    """Last value of each session, indexed by session date."""
    values = np.asarray(values)
    dates = session_dates(ts)
    _, last = day_bounds_from_dates(dates)
    return pd.Series(values[last], index=pd.to_datetime(dates[last]))


def run(
    ts: pd.DatetimeIndex,
    opens: np.ndarray,
    closes: np.ndarray,
    weights: np.ndarray,
    start: str = DEFAULT_START,
    band: float = 0.02,
    slippage_bps: float = 1.0,
    start_equity: float = START_EQUITY,
    fill_log: bool = False,
) -> dict:
    """Slice a warmed-up panel to the test start and simulate it.

    `fill_log=True` also returns a per-fill log (see `simulate`).  The
    performance metrics still come from the compiled simulator when it is
    available; the Python pass is used only to produce the log.
    """
    i = start_index(ts, start)
    return simulate(
        ts[i:],
        opens[i:],
        closes[i:],
        weights[i:],
        band=band,
        slippage_bps=slippage_bps,
        start_equity=start_equity,
        fill_log=fill_log,
    )


def _load_simcore():
    if os.environ.get("BT_PURE_PYTHON") == "1":
        return None
    names = ("simcore.dll", "libsimcore.so", "libsimcore.dylib")
    base = Path(__file__).resolve().parent / "simcore" / "target" / "release"
    for name in names:
        path = base / name
        if not path.exists():
            continue
        lib = ctypes.CDLL(str(path))
        d, sz = ctypes.c_double, ctypes.c_size_t
        pd_, pi = ctypes.POINTER(ctypes.c_double), ctypes.POINTER(ctypes.c_int64)
        lib.simcore_simulate.argtypes = [sz, sz, pd_, pd_, pd_, d, d, d, pd_, pd_, pi, pd_]
        lib.simcore_simulate.restype = ctypes.c_int32
        lib.simcore_simulate_many.argtypes = [sz, sz, sz, pd_, pd_, pd_, d, d, d,
                                              pd_, pd_, pi, pd_, sz]
        lib.simcore_simulate_many.restype = ctypes.c_int32
        return lib
    return None


_SIMCORE = _load_simcore()


def _ptr(a: np.ndarray, ctype=ctypes.c_double):
    return a.ctypes.data_as(ctypes.POINTER(ctype))


def _check_inputs(opens, closes, weights):
    weights = np.ascontiguousarray(weights, dtype=np.float64)
    n, k = weights.shape[-2:]
    if opens.shape != (n, k) or closes.shape != (n, k):
        raise ValueError("opens/closes/weights shapes do not match")
    wmin = float(weights.min())
    if not np.isfinite(wmin):
        raise ValueError("weights contain non-finite values")
    if wmin < -1e-9:
        raise ValueError("weights must be non-negative and sum to <= 1")
    rowmax = float(weights.sum(axis=-1).max())
    if not np.isfinite(rowmax) or rowmax > 1.001:
        raise ValueError("weights must be non-negative and sum to <= 1")
    return weights, n, k


def simulate(
    ts: pd.DatetimeIndex,
    opens: np.ndarray,
    closes: np.ndarray,
    weights: np.ndarray,
    band: float = 0.02,
    slippage_bps: float = 1.0,
    start_equity: float = START_EQUITY,
    fill_log: bool = False,
) -> dict:
    """Long-only next-open simulator.

    `weights[i]` is the target set from the close of bar i and is executed at
    the open of bar i+1. Weights are fractions of current equity.

    With `fill_log=True`, the returned dict also has ``fills_log``: a list of
    ``{"ts", "notional", "symbol", "side"}`` dicts, one per trade, where
    ``symbol`` is the panel column index (0=QQQ, 1=TQQQ, 2=BIL) and
    ``notional`` is the post-slippage traded notional.  The metrics come from
    the compiled simulator when it is available; a Python pass is then used
    only for the log.  Without simcore, the Python result is used directly.
    """
    if _SIMCORE is None:
        return simulate_python(ts, opens, closes, weights, band, slippage_bps,
                               start_equity, fill_log=fill_log)
    weights, n, k = _check_inputs(opens, closes, weights)
    o = np.ascontiguousarray(opens, dtype=np.float64)
    c = np.ascontiguousarray(closes, dtype=np.float64)
    equity = np.full(n, np.nan)
    cash = np.full(n, np.nan)
    fills = np.zeros(1, dtype=np.int64)
    traded = np.zeros(1)
    rc = _SIMCORE.simcore_simulate(n, k, _ptr(o), _ptr(c), _ptr(weights), band,
                                   slippage_bps / 10_000.0, start_equity, _ptr(equity),
                                   _ptr(cash), _ptr(fills, ctypes.c_int64), _ptr(traded))
    if rc != 0:
        raise RuntimeError(f"simcore_simulate failed ({rc})")
    out = {"ts": ts, "equity": equity, "cash": cash, "fills": int(fills[0]),
           "turnover": float(traded[0]) / start_equity}
    if fill_log:
        out["fills_log"] = simulate_python(
            ts, opens, closes, weights, band, slippage_bps, start_equity,
            fill_log=True)["fills_log"]
    return out


def simulate_many(
    ts: pd.DatetimeIndex,
    opens: np.ndarray,
    closes: np.ndarray,
    weights_list,
    band: float = 0.02,
    slippage_bps: float = 1.0,
    start_equity: float = START_EQUITY,
    threads: int | None = None,
) -> list[dict]:
    """Simulate several weight matrices over the same prices, in parallel.

    Same results as calling `simulate` on each one. Memory: 8*n*k bytes per
    weight matrix plus 16*n per result (about 40 MB each on the 1-minute panel).
    """
    if _SIMCORE is None:
        return [simulate_python(ts, opens, closes, w, band, slippage_bps, start_equity)
                for w in weights_list]
    W, n, k = _check_inputs(opens, closes, np.stack([np.asarray(w, float) for w in weights_list]))
    m = W.shape[0]
    o = np.ascontiguousarray(opens, dtype=np.float64)
    c = np.ascontiguousarray(closes, dtype=np.float64)
    equity = np.full((m, n), np.nan)
    cash = np.full((m, n), np.nan)
    fills = np.zeros(m, dtype=np.int64)
    traded = np.zeros(m)
    threads = threads or int(os.environ.get("BT_THREADS", 0)) or os.cpu_count() or 1
    rc = _SIMCORE.simcore_simulate_many(m, n, k, _ptr(o), _ptr(c), _ptr(W), band,
                                        slippage_bps / 10_000.0, start_equity, _ptr(equity),
                                        _ptr(cash), _ptr(fills, ctypes.c_int64),
                                        _ptr(traded), threads)
    if rc != 0:
        raise RuntimeError(f"simcore_simulate_many failed ({rc})")
    return [{"ts": ts, "equity": equity[j], "cash": cash[j], "fills": int(fills[j]),
             "turnover": float(traded[j]) / start_equity} for j in range(m)]


def run_many(ts, opens, closes, weights_list, start=DEFAULT_START, band=0.02,
             slippage_bps=1.0, start_equity=START_EQUITY, threads=None) -> list[dict]:
    """`run` for a batch of weight matrices (see simulate_many)."""
    i = start_index(ts, start)
    return simulate_many(ts[i:], opens[i:], closes[i:], [np.asarray(w)[i:] for w in weights_list],
                         band, slippage_bps, start_equity, threads)


def simulate_python(
    ts: pd.DatetimeIndex,
    opens: np.ndarray,
    closes: np.ndarray,
    weights: np.ndarray,
    band: float = 0.02,
    slippage_bps: float = 1.0,
    start_equity: float = START_EQUITY,
    fill_log: bool = False,
) -> dict:
    """Reference pure-Python simulator (the original implementation).

    With `fill_log=True`, the result also contains ``fills_log``: one dict per
    trade with ``ts`` (the fill bar), ``notional`` (post-slippage), ``symbol``
    (panel column index) and ``side`` ("buy"/"sell").  The log is additive;
    the aggregate totals are this reference path's totals.
    """
    weights = np.asarray(weights, dtype=float)
    n, k = weights.shape
    if opens.shape != (n, k) or closes.shape != (n, k):
        raise ValueError("opens/closes/weights shapes do not match")
    if not np.isfinite(weights).all():
        raise ValueError("weights contain non-finite values")
    if (weights < -1e-9).any() or (weights.sum(axis=1) > 1.001).any():
        raise ValueError("weights must be non-negative and sum to <= 1")

    slip = slippage_bps / 10_000.0
    cash = start_equity
    shares = np.zeros(k)
    equity = np.full(n, np.nan)
    cash_curve = np.full(n, np.nan)
    fills = 0
    traded = 0.0
    fills_log: list[dict] = []

    def trade(i: int, target: np.ndarray) -> None:
        nonlocal cash, fills, traded
        px = opens[i]
        # Match the Rust simulator's sequential summation order.  Using
        # np.dot here can differ in the last bit and flip a borderline band
        # rebalance, which made the fill log disagree with the compiled count.
        book = cash
        for s in range(k):
            book += shares[s] * px[s]
        if not (book > 0):
            return
        # Sell side / exits first.
        for s in range(k):
            if shares[s] <= 0:
                continue
            if target[s] == 0:
                qty = shares[s]
            else:
                excess = shares[s] * px[s] - target[s] * book
                if excess <= band * book:
                    continue
                qty = excess / px[s]
            qty = min(qty, shares[s])
            if qty <= 0:
                continue
            price = px[s] * (1.0 - slip)
            notional = qty * price
            cash += notional
            traded += notional
            fills += 1
            if fill_log:
                fills_log.append({"ts": ts[i], "notional": float(notional),
                                  "symbol": int(s), "side": "sell"})
            shares[s] -= qty
            if shares[s] < 1e-10:
                shares[s] = 0.0
        # Buy side / resizes.
        for s in range(k):
            if target[s] <= 0:
                continue
            current = shares[s] * px[s]
            shortfall = target[s] * book - current
            is_new = shares[s] <= 0
            if not is_new and shortfall <= band * book:
                continue
            if shortfall <= 0:
                continue
            price = px[s] * (1.0 + slip)
            qty = min(shortfall / price, cash / price)
            if qty <= 1e-12:
                continue
            notional = qty * price
            cash -= notional
            traded += notional
            fills += 1
            if fill_log:
                fills_log.append({"ts": ts[i], "notional": float(notional),
                                  "symbol": int(s), "side": "buy"})
            shares[s] += qty

    equity[0] = start_equity
    cash_curve[0] = cash
    for i in range(n - 1):
        trade(i + 1, weights[i])
        equity[i + 1] = cash + float(np.dot(shares, closes[i + 1]))
        cash_curve[i + 1] = cash

    out = {
        "ts": ts,
        "equity": equity,
        "cash": cash_curve,
        "fills": fills,
        "turnover": traded / start_equity,
    }
    if fill_log:
        out["fills_log"] = fills_log
    return out


def stats(result: dict, bars_per_year: float) -> dict:
    eq = result["equity"]
    rets = np.diff(eq) / eq[:-1]
    years = (result["ts"][-1] - result["ts"][0]).total_seconds() / (365.25 * 86400)
    peak = np.maximum.accumulate(eq)
    downside = np.minimum(rets, 0.0)
    mean_ret = float(np.mean(rets))
    std_ret = float(np.std(rets, ddof=0))
    downside_sq = float(np.mean(downside**2))
    return {
        "cagr": (eq[-1] / eq[0]) ** (1.0 / years) - 1.0,
        "total_return": eq[-1] / eq[0] - 1.0,
        "max_drawdown": float(-(eq / peak - 1.0).min()),
        "volatility": std_ret * np.sqrt(bars_per_year),
        "sharpe": (
            mean_ret / std_ret * np.sqrt(bars_per_year)
        )
        if std_ret > 0
        else 0.0,
        "sortino": (
            mean_ret / np.sqrt(downside_sq) * np.sqrt(bars_per_year)
        )
        if downside_sq > 0
        else 0.0,
        "exposure": float(np.mean((eq - result["cash"]) / eq)),
        "fills": result["fills"],
        "turnover": result["turnover"],
        "ending_equity": float(eq[-1]),
        "years": years,
    }


def benchmark(close: np.ndarray, ts: pd.DatetimeIndex, bars_per_year: float) -> dict:
    rets = np.diff(close) / close[:-1]
    years = (ts[-1] - ts[0]).total_seconds() / (365.25 * 86400)
    peak = np.maximum.accumulate(close)
    return {
        "cagr": float((close[-1] / close[0]) ** (1.0 / years) - 1.0),
        "total_return": float(close[-1] / close[0] - 1.0),
        "max_drawdown": float(-(close / peak - 1.0).min()),
        "volatility": float(np.std(rets, ddof=0) * np.sqrt(bars_per_year)),
        "sharpe": float(np.mean(rets) / np.std(rets, ddof=0) * np.sqrt(bars_per_year)),
        "ending_equity": float(START_EQUITY * close[-1] / close[0]),
        "years": years,
    }


def yearly(ts: pd.DatetimeIndex, equity: np.ndarray, bench: np.ndarray) -> dict[int, dict]:
    out: dict[int, dict] = {}
    years = sorted(set(ts.year))
    for year in years:
        mask = ts.year == year
        e = equity[mask]
        b = bench[mask]
        if len(e) < 2:
            continue
        out[int(year)] = {
            "strategy": float(e[-1] / e[0] - 1.0),
            "benchmark": float(b[-1] / b[0] - 1.0),
        }
    return out


def print_summary(label: str, s: dict, b: dict) -> None:
    print(f"\n{label}")
    print(
        f"  CAGR {s['cagr']*100:6.2f}%  DD {s['max_drawdown']*100:5.2f}%  "
        f"vol {s['volatility']*100:5.2f}%  Sharpe {s['sharpe']:4.2f}  "
        f"end ${s['ending_equity']:,.0f}"
    )
    print(
        f"  bench CAGR {b['cagr']*100:6.2f}%  DD {b['max_drawdown']*100:5.2f}%  "
        f"vol {b['volatility']*100:5.2f}%  Sharpe {b['sharpe']:4.2f}  "
        f"end ${b['ending_equity']:,.0f}"
    )
    print(f"  fills {s['fills']:,}  turnover {s['turnover']:.1f}x  exposure {s['exposure']*100:.1f}%")
