"""Shared helpers for the winners audit (read-only analysis)."""
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
CACHE = HERE / "cache"
START, END = "2016-01-04", "2026-10-23"
BARS = 252 * 390


def load_panel():
    z = np.load(CACHE / "full_panel_ohlc.npz")
    ts = pd.DatetimeIndex(pd.to_datetime(z["ts"], unit="ns", utc=True)
                          .tz_convert("America/New_York"))
    return (ts, z["opens"], z["highs"], z["lows"], z["closes"])


def daily_equity(res) -> pd.Series:
    eq = pd.Series(res["equity"], index=pd.DatetimeIndex(res["ts"]))
    d = eq.groupby(eq.index.date).last()
    d.index = pd.to_datetime(d.index)
    return d.dropna()


def metrics(daily: pd.Series) -> dict:
    """Headline metrics on daily marks, curve convention (first daily close=100)."""
    v = daily.dropna().to_numpy(dtype=float)
    idx = daily.dropna().index
    years = (idx[-1] - idx[0]).days / 365.25
    peak = np.maximum.accumulate(v)
    rets = np.diff(v) / v[:-1]
    dd = float(-(v / peak - 1.0).min())
    return {
        "start": str(idx[0].date()), "end": str(idx[-1].date()),
        "years": float(years),
        "cagr": float((v[-1] / v[0]) ** (1 / years) - 1.0) if years > 0 else 0.0,
        "max_drawdown": dd,
        "sharpe": float(rets.mean() / rets.std(ddof=1) * np.sqrt(252)) if rets.std(ddof=1) else 0.0,
        "volatility": float(rets.std(ddof=1) * np.sqrt(252)),
        "calmar": float(((v[-1] / v[0]) ** (1 / years) - 1.0) / dd) if dd > 0 and years > 0 else 0.0,
        "ending_multiple": float(v[-1] / v[0]),
    }


def minute_metrics(res) -> dict:
    s = bt.stats(res, BARS)
    return {
        "cagr": float(s["cagr"]),
        "max_drawdown_minute": float(s["max_drawdown"]),
        "sharpe_minute": float(s["sharpe"]),
        "volatility_minute": float(s["volatility"]),
        "fills": int(s["fills"]),
        "turnover": float(s["turnover"]),
        "exposure": float(s["exposure"]),
        "ending_equity": float(s["ending_equity"]),
    }


def daily_returns(s: pd.Series) -> pd.Series:
    return s.pct_change().dropna()


def beta_corr(sr: pd.Series, bench: pd.Series) -> dict:
    j = pd.concat([sr.rename("s"), bench.rename("b")], axis=1).dropna()
    if len(j) < 50:
        return {}
    cov = np.cov(j["s"], j["b"], ddof=1)
    beta = float(cov[0, 1] / cov[1, 1])
    corr = float(j["s"].corr(j["b"]))
    # annualised alpha vs the benchmark
    alpha = float((j["s"].mean() - beta * j["b"].mean()) * 252)
    return {"beta": beta, "corr": corr, "alpha_ann": alpha, "n": int(len(j))}


def updown_capture(sr: pd.Series, bench: pd.Series) -> dict:
    j = pd.concat([sr.rename("s"), bench.rename("b")], axis=1).dropna()
    up = j[j["b"] > 0]
    dn = j[j["b"] < 0]
    return {
        "up_capture": float(up["s"].mean() / up["b"].mean()) if len(up) and up["b"].mean() else None,
        "down_capture": float(dn["s"].mean() / dn["b"].mean()) if len(dn) and dn["b"].mean() else None,
        "n_up": int(len(up)), "n_down": int(len(dn)),
    }


def exposure(weights: np.ndarray, ts: pd.DatetimeIndex, k: int = 3) -> dict:
    names = ("QQQ", "TQQQ", "BIL")
    mean_w = weights.mean(axis=0)
    out = {"mean_" + n.lower(): float(mean_w[i]) for i, n in enumerate(names)}
    dates = bt.session_dates(ts)
    first, last = bt.day_bounds_from_dates(dates)
    sess_w = weights[last]  # session-end (close) target weights
    out["sessions"] = int(len(first))
    out["tqqq_sessions_any"] = float(np.mean(sess_w[:, 1] > 1e-9))
    out["tqqq_sessions_full"] = float(np.mean(sess_w[:, 1] > 0.999))
    out["qqq_sessions_any"] = float(np.mean(sess_w[:, 0] > 1e-9))
    out["cash_sessions_full"] = float(np.mean(sess_w[:, 2] > 0.999))
    out["mean_tqqq_when_held"] = float(sess_w[sess_w[:, 1] > 1e-9, 1].mean()) if (sess_w[:, 1] > 1e-9).any() else 0.0
    out["min_tqqq_when_held"] = float(sess_w[sess_w[:, 1] > 1e-9, 1].min()) if (sess_w[:, 1] > 1e-9).any() else 0.0
    out["max_tqqq"] = float(sess_w[:, 1].max())
    return out


def yearly_returns(daily: pd.Series) -> dict:
    out = {}
    idx = daily.index
    for y in sorted(set(idx.year)):
        m = idx.year == y
        v = daily[m]
        if len(v) < 2:
            continue
        # first session's return is from the prior year's last close
        out[int(y)] = float(v.iloc[-1] / v.iloc[0] - 1.0)
    return out


def yearly_returns_eoy(daily: pd.Series) -> dict:
    """Calendar-year close-to-close: last close of year / last close of prior year."""
    out = {}
    s = daily.copy()
    for y in sorted(set(s.index.year)):
        e = s[s.index.year == y]
        prev = s[s.index < e.index[0]]
        if len(prev):
            base = prev.iloc[-1]
        else:
            base = e.iloc[0]
        out[int(y)] = float(e.iloc[-1] / base - 1.0)
    return out


def subperiod(daily: pd.Series, lo: str, hi: str) -> dict:
    m = (daily.index >= pd.Timestamp(lo)) & (daily.index <= pd.Timestamp(hi))
    v = daily[m]
    if len(v) < 2:
        return {}
    return metrics(v)


def save_json(name: str, obj) -> None:
    (HERE / name).write_text(json.dumps(obj, indent=1, default=float), encoding="utf-8")
    print("wrote", HERE / name)


def load_ratio_froth(ts, o, c):
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "old_ratio_audit", ROOT / "research" / "agents2" / "ratio-pairs" / "strategy.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    w, diag = mod.build_weights(ts, o, c)
    return mod, w, diag


def load_vol(ts, o, h, l, c):
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "vol_audit", ROOT / "research" / "revisit" / "vol-scaled-crash-stop" / "strategy.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    dates = bt.session_dates(ts)
    first, last = bt.day_bounds_from_dates(dates)
    atr = mod.atr_series(h, l, c, first, last)
    w, info = mod.build_weights(ts, o, c, first, last, atr)
    return mod, w, info, atr, first, last
