"""Donchian two-sleeve TQQQ trend — development backtest.

Frozen specification (see HYPOTHESIS.md):

  fast sleeve : TQQQ 20-session high entry / 10-session low exit
  slow sleeve : QQQ 100-session high entry / 50-session low exit
  position    : TQQQ while either sleeve is long, sized by an 85% vol target
  remainder   : BIL

Signals use official adjusted daily OHLC through the session close; fills are
next-open on the 1-minute-derived daily panel from research/bt.py.  Only the
2016-01-04 .. 2023-12-29 development window is used; the panel returned by
bt.panel stops at 2023-12-29 and no 2024+ bar enters any weight or metric.

Run:
    $env:PYTHONPATH = "C:\\Users\\27175\\AppData\\Local\\Temp\\opencode\\pylibs"
    python research/new/donchian-trend/strategy.py
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

BASE = dict(
    fast_entry=20,
    fast_exit=10,
    slow_entry=100,
    slow_exit=50,
    target_vol=0.85,
    vol_window=20,
)


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


_SIGNAL_CACHE: dict = {}


def _signal_frame(ts: pd.DatetimeIndex, end: str = DEV_END):
    """Stitch pre-start warmup rows to the panel calendar for QQQ and TQQQ."""
    key = (str(pd.Timestamp(ts[0])), str(pd.Timestamp(ts[-1])), len(ts), end)
    cached = _SIGNAL_CACHE.get(key)
    if cached is not None:
        return cached
    dev_dates = pd.DatetimeIndex(pd.to_datetime(ts)).normalize().tz_localize(None)
    dev_dates = dev_dates[~dev_dates.duplicated()]
    first = dev_dates[0]
    frames = {}
    for sym in ("QQQ", "TQQQ"):
        full = _daily_ohlc(sym, end=end).drop_duplicates("date").sort_values("date")
        pre = full[full["date"] < first]
        dev = full.set_index("date").reindex(dev_dates).ffill()
        if dev.isna().any().any():
            raise RuntimeError(f"{sym}: missing dev dates in the daily file")
        stitched = pd.concat([pre.set_index("date"), dev]).sort_index()
        stitched = stitched[~stitched.index.duplicated(keep="last")]
        if stitched.index.has_duplicates:
            raise RuntimeError(f"{sym}: duplicate signal dates")
        frames[sym] = stitched
    out = (frames["QQQ"], frames["TQQQ"], len(pre))
    _SIGNAL_CACHE.clear()
    _SIGNAL_CACHE[key] = out
    return out


# --------------------------------------------------------------------------- signal
def _donchian_state(high, low, close, entry_n: int, exit_n: int) -> np.ndarray:
    """1 after a close above the prior `entry_n` high, 0 after a close below
    the prior `exit_n` low.  Current bar excluded from its own channel."""
    n = len(close)
    state = np.zeros(n, dtype=np.int8)
    on = 0
    warm = max(entry_n, exit_n) + 1
    for i in range(warm, n):
        if on == 0:
            if close[i] > high[i - entry_n:i].max():
                on = 1
        else:
            if close[i] < low[i - exit_n:i].min():
                on = 0
        state[i] = on
    return state


def build_weights(ts, o, c, params: dict | None = None, end: str = DEV_END) -> np.ndarray:
    """Target weights (n, 3) = [QQQ, TQQQ, BIL] for the panel bars.

    `params` overrides BASE; `end` is used only by the truncation test.
    """
    p = dict(BASE)
    if params:
        p.update(params)
    qq, tq, _ = _signal_frame(ts, end=end)
    n = len(ts)

    fast = _donchian_state(
        tq["high"].to_numpy(float), tq["low"].to_numpy(float),
        tq["close"].to_numpy(float), p["fast_entry"], p["fast_exit"],
    )
    slow = _donchian_state(
        qq["high"].to_numpy(float), qq["low"].to_numpy(float),
        qq["close"].to_numpy(float), p["slow_entry"], p["slow_exit"],
    )
    trend = np.maximum(fast, slow).astype(float)

    ret = np.zeros(len(tq))
    ret[1:] = np.log(tq["close"].to_numpy(float)[1:] / tq["close"].to_numpy(float)[:-1])
    vol = pd.Series(ret).rolling(p["vol_window"]).std().to_numpy() * np.sqrt(252.0)
    scale = np.clip(p["target_vol"] / np.where(vol > 0, vol, np.inf), 0.0, 1.0)

    w = np.nan_to_num(trend * scale, nan=0.0, posinf=0.0, neginf=0.0)[-n:]
    w = np.clip(w, 0.0, 1.0)
    W = np.zeros((n, 3))
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
    years = sorted(set(dates.year))
    yearly = {}
    for y in years:
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
    cells = {
        "base": {},
        "slow_entry_80": {"slow_entry": 80},
        "slow_entry_120": {"slow_entry": 120},
        "slow_exit_40": {"slow_exit": 40},
        "slow_exit_60": {"slow_exit": 60},
        "fast_entry_15": {"fast_entry": 15},
        "fast_entry_25": {"fast_entry": 25},
        "fast_exit_15": {"fast_exit": 15},
    }
    out = {}
    for name, override in cells.items():
        p = dict(BASE); p.update(override)
        W = build_weights(ts, o, c, p)
        m = _metrics(ts, o, c, W, tqqq_close)
        out[name] = {
            "params": p,
            "cagr": m["cagr"], "max_drawdown": m["max_drawdown"],
            "sharpe": m["sharpe"], "tqqq_exposure": m["tqqq_exposure"],
            "fills": m["fills"], "yearly": m["yearly"],
        }
    return out


def _ablations(ts, o, c, tqqq_close) -> dict:
    variants = {
        "no_vol_target": {"target_vol": 99.0},
        "fast_sleeve_only": {"slow_entry": 10_000, "slow_exit": 10_000},
        "slow_sleeve_only": {"fast_entry": 10_000, "fast_exit": 10_000},
        "strict_mandate_55_20": {"slow_entry": 55, "slow_exit": 20},
        "slow_55_50": {"slow_entry": 55, "slow_exit": 50},
        "slow_55_60": {"slow_entry": 55, "slow_exit": 60},
        "slow_80_60": {"slow_entry": 80, "slow_exit": 60},
        "slow_120_60": {"slow_entry": 120, "slow_exit": 60},
        "no_trend_constant": {"fast_entry": 10_000, "fast_exit": 10_000,
                              "slow_entry": 10_000, "slow_exit": 10_000},
    }
    out = {}
    for name, override in variants.items():
        p = dict(BASE); p.update(override)
        W = build_weights(ts, o, c, p)
        m = _metrics(ts, o, c, W, tqqq_close)
        out[name] = {
            "params": p, "cagr": m["cagr"], "max_drawdown": m["max_drawdown"],
            "sharpe": m["sharpe"], "tqqq_exposure": m["tqqq_exposure"],
            "fills": m["fills"],
        }
    return out


def _neighbourhood(ts, o, c, tqqq_close) -> dict:
    variants = {
        "tv_0.45": {"target_vol": 0.45},
        "tv_0.55": {"target_vol": 0.55},
        "tv_0.65": {"target_vol": 0.65},
        "tv_0.75": {"target_vol": 0.75},
        "tv_0.95": {"target_vol": 0.95},
        "vol_window_15": {"vol_window": 15},
        "vol_window_30": {"vol_window": 30},
        "fast_exit_5": {"fast_exit": 5},
        "slow_exit_55": {"slow_exit": 55},
        "slow_entry_90": {"slow_entry": 90},
        "slow_entry_110": {"slow_entry": 110},
    }
    out = {}
    for name, override in variants.items():
        p = dict(BASE); p.update(override)
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
        res = _run(ts, o, c, Wd, 1.0)
        s = _series_stats(ts, res["equity"])
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
    """Same number of invested days, randomly placed.  Destroys trend clustering."""
    rng = np.random.default_rng(seed)
    base = _metrics(ts, o, c, W, tqqq_close)
    w = W[:, 1]
    n_on = int((w > 0).sum())
    p = n_on / len(w)
    rows = []
    for _ in range(draws):
        on = rng.random(len(w)) < p
        wd = np.where(on, w, 0.0)  # keep the same vol-scaled sizes
        Wd = np.zeros_like(W)
        Wd[:, 1] = wd
        Wd[:, 2] = 1.0 - wd
        res = _run(ts, o, c, Wd, 1.0)
        s = _series_stats(ts, res["equity"])
        rows.append((s["cagr"], s["max_drawdown"], s["sharpe"]))
    arr = np.array(rows)
    return {
        "draws": draws,
        "cagr_median": float(np.median(arr[:, 0])),
        "cagr_p95": float(np.percentile(arr[:, 0], 95)),
        "cagr_max": float(arr[:, 0].max()),
        "dd_median": float(np.median(arr[:, 1])),
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
        seg_ts = ts[idx[0]:idx[-1] + 1]
        seg_eq = eq[idx[0]:idx[-1] + 1]
        out[name] = _series_stats(seg_ts, seg_eq)
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
    qq, _, _ = _signal_frame(ts)
    qclose = qq["close"].to_numpy(float)[-len(ts):]
    sma = pd.Series(qclose).rolling(165).mean().to_numpy()
    w = np.where(qclose > sma, 1.0, 0.0)
    w = np.nan_to_num(w)[-len(ts):]
    W = np.zeros((len(ts), 3))
    W[:, 1] = w
    W[:, 2] = 1.0 - w
    m = _metrics(ts, o, c, W, tqqq_close)
    return m


# --------------------------------------------------------------------------- main
def main() -> None:
    ts, o, c = bt.panel(("QQQ", "TQQQ", "BIL"), DEV_START, DEV_END, "1D", warmup_days=0)
    assert len(ts) > 1500
    assert pd.Timestamp(ts[-1]).date() <= pd.Timestamp(DEV_END).date()
    tqqq_close = c[:, 1]

    W = build_weights(ts, o, c)
    primary = {}
    for bps in (1.0, 5.0, 10.0):
        m = _metrics(ts, o, c, W, tqqq_close, slip=bps)
        primary[f"{int(bps)}bp"] = m

    grid = _grid(ts, o, c, tqqq_close)
    ablations = _ablations(ts, o, c, tqqq_close)
    neigh = _neighbourhood(ts, o, c, tqqq_close)
    lag = _lag_placebo(ts, o, c, W, tqqq_close)
    circ = _circular_placebo(ts, o, c, W, tqqq_close)
    bern = _bernoulli_placebo(ts, o, c, W, tqqq_close)
    cuts = {d: _cut(ts, o, c, W, d, tqqq_close)
            for d in ("2017-01-03", "2018-01-02", "2019-01-02",
                      "2020-01-02", "2021-01-04", "2022-01-03")}
    sub = _subperiods(ts, _run(ts, o, c, W, 1.0)["equity"])
    causality = _causality(ts, o, c)

    benchmarks = {}
    for idx, name in ((1, "tqqq_buy_hold"), (0, "qqq_buy_hold"), (2, "bil_buy_hold")):
        benchmarks[name] = bt.benchmark(c[:, idx], ts, 252)
    sma_base = _sma_base(ts, o, c, tqqq_close)

    # 165-day QQQ SMA base: benchmark/correlation only, never an input
    qq = _signal_frame(ts)[0]
    qclose = qq["close"].to_numpy(float)[-len(ts):]
    sma_w = np.nan_to_num(np.where(qclose > pd.Series(qclose).rolling(165).mean().to_numpy(), 1.0, 0.0))
    W_sma = np.column_stack([np.zeros(len(ts)), sma_w, 1.0 - sma_w])
    eq_sma = _run(ts, o, c, W_sma, 1.0)["equity"]
    eq_base = _run(ts, o, c, W, 1.0)["equity"]
    corr_sma = float(np.corrcoef(np.diff(eq_base) / eq_base[:-1], np.diff(eq_sma) / eq_sma[:-1])[0, 1])

    s1 = primary["1bp"]
    result = {
        "agent": "donchian-trend",
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
        "primary": {k: {kk: vv for kk, vv in v.items()} for k, v in primary.items()},
        "grid": grid,
        "ablations": ablations,
        "neighbourhood": neigh,
        "lag_placebo": lag,
        "circular_shift_placebo": circ,
        "bernoulli_placebo": bern,
        "cut_tests": cuts,
        "subperiods": sub,
        "causality": causality,
        "benchmarks": benchmarks,
        "sma165_base_benchmark_only": sma_base,
        "corr_to_sma165_base": corr_sma,
        "notes": {
            "signal": "official adjusted daily OHLC through the session close",
            "execution": "bt.panel daily bars from the 1-minute archive; next-open fills",
            "vol_target": "w = trend * min(1, 0.85 / annualised 20-session TQQQ vol)",
            "holdout": "2024-2026 never loaded",
            "grid": "pre-registered 8 cells; base is the centre, not the best cell",
        },
    }
    with open(OUT_DIR / "result.json", "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2)

    print(f"\nDEV 2016-01-04..2023-12-29  sessions {len(ts)}")
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
              f"Sharpe {g['sharpe']:.2f}")
    print("\nplacebo (circular shift): median CAGR "
          f"{circ['cagr_median']*100:.2f}%  p95 {circ['cagr_p95']*100:.2f}%  "
          f"base pct {circ['base_cagr_percentile']*100:.1f}")
    print("placebo (random days):    median CAGR "
          f"{bern['cagr_median']*100:.2f}%  p95 {bern['cagr_p95']*100:.2f}%  "
          f"base pct {bern['base_cagr_percentile']*100:.1f}")
    print(f"\ncausality: {causality}")
    print(f"\nwritten: {OUT_DIR / 'result.json'}")


if __name__ == "__main__":
    main()
