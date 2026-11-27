"""Vol-of-vol risk-state timing (VVT) - standalone strategy.

Development window ONLY: 2016-01-04 .. 2023-12-29.  The 1-minute panel is
physically truncated at 2023-12-29 before any signal is computed, and the daily
high/low file is read with a ``date <= 2023-12-29`` parquet filter.  No holdout
bar is loaded or inspected.

The strategy holds TQQQ when range-based realised volatility is low and
stable, scales down when volatility is high, accelerates, or when vol-of-vol
spikes, and re-risks when high volatility is decelerating and vol-of-vol has
turned down from its 10-day peak (a V-recovery).

Run from the repo root:
    $env:PYTHONPATH = "C:\\Users\\27175\\AppData\\Local\\Temp\\opencode\\pylibs"
    python research/new/vol-of-vol-timing/strategy.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402

START = "2016-01-04"
END = "2023-12-29"
BARS_1M = 252 * 390
SYMS = ("QQQ", "TQQQ", "BIL")

# Primary parameters.  The grid in HYPOTHESIS.md changes one at a time.
P = dict(
    vol_lo=0.40,
    vol_hi=0.65,
    w10=0.25,
    w20=0.75,
    dec_ratio=0.80,
    dec_boost=0.50,
    vov_th=0.25,
    vov_stress=0.55,
    vov_drop=0.95,
    add=0.50,
    acc_ratio=1.30,
    acc_cut=0.70,
    vov_spike=0.45,
    vov_rise=1.20,
    vov_cut=0.70,
)

# The eight pre-registered grid cells: one parameter moved at a time.
GRID = [
    ("primary", {}),
    ("vol_hi_lo", dict(vol_hi=0.62)),
    ("vol_hi_hi", dict(vol_hi=0.68)),
    ("dec_lo", dict(dec_ratio=0.78)),
    ("dec_hi", dict(dec_ratio=0.82)),
    ("vov_hi", dict(vov_th=0.30)),
    ("blend_lo", dict(w10=0.20, w20=0.80)),
    ("blend_hi", dict(w10=0.30, w20=0.70)),
]

ABLATIONS = [
    ("L_level", dict(dec_boost=0.0, add=0.0, acc_cut=1.0, vov_cut=1.0)),
    ("D_level_dec", dict(add=0.0, acc_cut=1.0, vov_cut=1.0)),
    ("V_level_vov", dict(dec_boost=0.0, acc_cut=1.0, vov_cut=1.0)),
    ("DV_level_dec_vov", dict(acc_cut=1.0, vov_cut=1.0)),
    ("DVC_primary", {}),
]


def params(**over):
    out = dict(P)
    out.update(over)
    return out


def _rolling(a, k):
    return pd.Series(a).rolling(k, min_periods=k).mean().to_numpy()


def _rolling_std(a, k):
    return pd.Series(a).rolling(k, min_periods=k).std().to_numpy()


def _daily_high_low(ts: pd.DatetimeIndex, o: np.ndarray, c: np.ndarray,
                    dates, first, last) -> tuple[np.ndarray, np.ndarray]:
    """True TQQQ daily high/low, dev-filtered, with a 1-minute fallback.

    The daily parquet is read with a parquet predicate so only rows with
    date <= END are materialised.  The 1-minute fallback uses only the passed
    panel (max/min of each minute's open/close).
    """
    session_dates = pd.Series(dates[first])
    hi = np.full(len(session_dates), np.nan)
    lo = np.full(len(session_dates), np.nan)
    path = ROOT / "data" / "intraday-hf" / "TQQQ-1d-yahoo.parquet"
    try:
        d = pd.read_parquet(
            path, columns=["date", "high", "low"],
            # Extend the read to the passed panel's end.  The dev run stops at
            # 2023-12-29; the full holdout run reads true 2024-2026 highs/lows
            # instead of falling back to minute-bar proxies.
            filters=[("date", "<=", pd.Timestamp(dates[-1]).date())],
        )
        d["date"] = pd.to_datetime(d["date"]).dt.date
        d = d.drop_duplicates("date").set_index("date")
        d = d.reindex(session_dates)
        hi = d["high"].to_numpy(dtype=float).copy()
        lo = d["low"].to_numpy(dtype=float).copy()
    except Exception:
        pass
    # Fallback for any missing session: use the 1-minute path.
    bad = ~np.isfinite(hi) | ~np.isfinite(lo) | (hi <= 0) | (lo <= 0)
    if bad.any():
        for j in np.flatnonzero(bad):
            a, b = first[j], last[j] + 1
            hh = np.maximum(o[a:b, 1], c[a:b, 1])
            ll = np.minimum(o[a:b, 1], c[a:b, 1])
            hi[j] = float(np.max(hh))
            lo[j] = float(np.min(ll))
    return hi, lo


def _state(high: np.ndarray, low: np.ndarray, p: dict) -> dict:
    """Daily state variables.  All windows end at the current session."""
    ratio = np.log(np.maximum(high, 1e-12) / np.maximum(low, 1e-12))
    park = np.sqrt(ratio ** 2 / (4.0 * np.log(2.0)))
    rv5 = _rolling(park, 5) * np.sqrt(252.0)
    rv10 = _rolling(park, 10) * np.sqrt(252.0)
    rv20 = _rolling(park, 20) * np.sqrt(252.0)
    vov = _rolling_std(rv5, 20) / _rolling(rv5, 20)
    vov_peak = pd.Series(vov).rolling(10, min_periods=10).max().to_numpy()
    vov_10 = pd.Series(vov).shift(10).to_numpy()
    sig = p["w10"] * rv10 + p["w20"] * rv20
    return dict(park=park, rv5=rv5, rv10=rv10, rv20=rv20, vov=vov,
                vov_peak=vov_peak, vov_10=vov_10, sigma_s=sig)


def _add_mask(s: dict, p: dict) -> np.ndarray:
    sig = s["sigma_s"]
    if p["add"] <= 0:
        return np.zeros(len(sig), dtype=bool)
    return (
        np.isfinite(s["rv20"]) & np.isfinite(s["vov"]) & np.isfinite(s["vov_peak"])
        & np.isfinite(s["rv5"])
        & (s["rv20"] > p["vov_stress"])
        & (s["vov"] > p["vov_th"])
        & (s["vov"] <= p["vov_drop"] * s["vov_peak"])
        & (s["rv5"] <= s["rv20"])
    )


def _weights_from_state(s: dict, p: dict,
                        add_mask: np.ndarray | None = None) -> tuple[np.ndarray, dict]:
    """Map the daily state to a TQQQ weight in [0, 1]."""
    sig = s["sigma_s"]
    base = np.clip((p["vol_hi"] - sig) / (p["vol_hi"] - p["vol_lo"]), 0.0, 1.0)

    dec = np.isfinite(s["rv5"]) & np.isfinite(s["rv20"]) & (s["rv5"] < p["dec_ratio"] * s["rv20"])
    if p["dec_boost"] > 0:
        base = np.where(dec, base + (1.0 - base) * p["dec_boost"], base)

    add = _add_mask(s, p) if add_mask is None else add_mask
    if p["add"] > 0:
        base = np.where(add, base + (1.0 - base) * p["add"], base)

    acc = (
        np.isfinite(s["rv5"]) & np.isfinite(s["rv20"])
        & (s["rv5"] > p["acc_ratio"] * s["rv20"])
    ) if p["acc_cut"] < 1.0 else np.zeros(len(sig), dtype=bool)
    if p["acc_cut"] < 1.0:
        base = np.where(acc, base * p["acc_cut"], base)

    vspike = (
        np.isfinite(s["vov"]) & np.isfinite(s["vov_10"])
        & (s["vov"] > p["vov_spike"])
        & (s["vov"] > p["vov_rise"] * s["vov_10"])
    ) if p["vov_cut"] < 1.0 else np.zeros(len(sig), dtype=bool)
    if p["vov_cut"] < 1.0:
        base = np.where(vspike, base * p["vov_cut"], base)

    w = np.clip(base, 0.0, 1.0)
    w[~np.isfinite(w)] = 0.0
    info = dict(
        days=int(len(w)),
        avg_weight=float(np.mean(w)),
        dec_days=int(dec.sum()),
        vov_add_days=int(add.sum()),
        acc_cut_days=int(acc.sum()),
        vov_cut_days=int(vspike.sum()),
        flat_days=int((w <= 1e-9).sum()),
        full_days=int((w >= 1.0 - 1e-9).sum()),
    )
    return w, info


def _map_to_bars(w_daily: np.ndarray, first: np.ndarray, last: np.ndarray,
                 n_bars: int) -> np.ndarray:
    """Daily targets on intraday bars with next-open fill semantics.

    Every minute of session d carries session d-1's target; the last minute of
    session d carries d's target, which fills at d+1's open.
    """
    n_days = len(w_daily)
    src = np.repeat(np.arange(n_days), np.diff(np.r_[first, n_bars]))
    prev = np.r_[0, np.arange(n_days - 1)]
    return w_daily[prev[src]]


def build_weights(ts: pd.DatetimeIndex, o: np.ndarray, c: np.ndarray,
                  p: dict | None = None) -> tuple[np.ndarray, dict]:
    """Return ((n, 3) weights, info).  TQQQ is column 1, BIL column 2."""
    p = params() if p is None else p
    n = len(ts)
    intraday = n > 1 and (ts[1] - ts[0]) < pd.Timedelta(hours=23)
    if intraday:
        dates, first, last = bt.day_bounds(ts)
        high, low = _daily_high_low(ts, o, c, dates, first, last)
        s = _state(high, low, p)
        w_daily, info = _weights_from_state(s, p)
        w_t = _map_to_bars(w_daily, first, last, n)
        info["bars"] = int(n)
        info["days"] = int(len(w_daily))
        info["avg_weight"] = float(np.mean(w_t))
        info["tqqq_minutes"] = float(np.mean(w_t > 1e-9))
    else:
        dates = bt.session_dates(ts)
        high, low = _daily_high_low(ts, o, c, dates, np.arange(n), np.arange(n))
        s = _state(high, low, p)
        w_t, info = _weights_from_state(s, p)
        info["bars"] = int(n)
        info["tqqq_minutes"] = float(np.mean(w_t > 1e-9))

    w = np.zeros((n, 3))
    w[:, 1] = w_t
    w[:, 2] = 1.0 - w_t
    return w, info


def _clean(x):
    if isinstance(x, dict):
        return {str(k): _clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_clean(v) for v in x]
    if isinstance(x, (np.bool_, bool)):
        return bool(x)
    if isinstance(x, (np.integer, int)):
        return int(x)
    if isinstance(x, (np.floating, float)):
        v = float(x)
        return None if not np.isfinite(v) else v
    return x


def _metrics(res: dict, bars: float = BARS_1M) -> dict:
    s = bt.stats(res, bars)
    return dict(
        cagr=float(s["cagr"]), max_drawdown=float(s["max_drawdown"]),
        sharpe=float(s["sharpe"]), sortino=float(s["sortino"]),
        volatility=float(s["volatility"]), exposure=float(s["exposure"]),
        fills=int(s["fills"]), turnover=float(s["turnover"]),
        ending_equity=float(s["ending_equity"]), years=float(s["years"]),
    )


def _subperiod(res: dict, start: str, end: str) -> dict:
    ts = res["ts"]
    m = (ts >= pd.Timestamp(start, tz="America/New_York")) & (
        ts <= pd.Timestamp(end, tz="America/New_York") + pd.Timedelta(days=1))
    if m.sum() < 2:
        return {}
    eq = res["equity"][m]
    yrs = (ts[m][-1] - ts[m][0]).total_seconds() / (365.25 * 86400)
    peak = np.maximum.accumulate(eq)
    rets = np.diff(eq) / eq[:-1]
    std = float(np.std(rets, ddof=0))
    return dict(
        cagr=float((eq[-1] / eq[0]) ** (1 / yrs) - 1),
        max_drawdown=float(-(eq / peak - 1).min()),
        sharpe=float(np.mean(rets) / std * np.sqrt(BARS_1M)) if std > 0 else 0.0,
        days=int(m.sum()),
    )


def _daily_returns(res: dict, close: np.ndarray) -> tuple[pd.Series, pd.Series]:
    ts = res["ts"]
    dates, first, last = bt.day_bounds(ts)
    idx = pd.to_datetime(dates[last])
    eq = pd.Series(res["equity"][last], index=idx)
    px = pd.Series(close[last], index=idx)
    return eq.pct_change().dropna(), px.pct_change().dropna()


def _drawdowns(res: dict, top: int = 35) -> list[dict]:
    eq = res["equity"]
    ts = res["ts"]
    peak = np.maximum.accumulate(eq)
    dd = eq / peak - 1.0
    order = np.argsort(dd)
    out = []
    troughs: list[int] = []
    for k in order:
        if len(out) >= top:
            break
        if all(abs((ts[k] - ts[j]).total_seconds()) > 60 * 86400 for j in troughs):
            pk = int(np.argmax(eq[:k + 1]))
            troughs.append(int(k))
            out.append(dict(
                peak=str(pd.Timestamp(ts[pk]).date()),
                trough=str(pd.Timestamp(ts[k]).date()),
                depth=float(-dd[k]),
            ))
    return out


def _placebo_shuffle(w_daily: np.ndarray, first, last, n_bars, ts, o, c,
                     n_draws: int = 200, seed: int = 7) -> dict:
    rng = np.random.default_rng(seed)
    out = []
    for _ in range(n_draws):
        w = rng.permutation(w_daily)
        w1 = _map_to_bars(w, first, last, n_bars)
        ww = np.zeros((n_bars, 3))
        ww[:, 1] = w1
        ww[:, 2] = 1 - w1
        r = bt.run(ts, o, c, ww, START, band=0.02, slippage_bps=1.0)
        out.append(bt.stats(r, BARS_1M)["cagr"])
    out = np.array(out)
    return dict(n=n_draws, mean=float(out.mean()), std=float(out.std()),
                p05=float(np.percentile(out, 5)), p50=float(np.percentile(out, 50)),
                p95=float(np.percentile(out, 95)))


def _placebo_vov(s: dict, p: dict, first, last, n_bars,
                 ts, o, c, year: np.ndarray, n_draws: int = 200,
                 seed: int = 11) -> dict:
    """Permute the vov-add indicator within each calendar year."""
    rng = np.random.default_rng(seed)
    add = _add_mask(s, p)
    out = []
    for _ in range(n_draws):
        rand_add = add.copy()
        for y in np.unique(year):
            m = year == y
            vals = rand_add[m]
            rand_add[m] = rng.permutation(vals)
        w, _ = _weights_from_state(s, p, add_mask=rand_add)
        w1 = _map_to_bars(w, first, last, n_bars)
        ww = np.zeros((n_bars, 3)); ww[:, 1] = w1; ww[:, 2] = 1 - w1
        r = bt.run(ts, o, c, ww, START, band=0.02, slippage_bps=1.0)
        out.append(bt.stats(r, BARS_1M)["cagr"])
    out = np.array(out)
    return dict(n=n_draws, mean=float(out.mean()), std=float(out.std()),
                p05=float(np.percentile(out, 5)), p50=float(np.percentile(out, 50)),
                p95=float(np.percentile(out, 95)))


def _placebo_block(w_daily: np.ndarray, first, last, n_bars, ts, o, c,
                   block: int = 20, n_draws: int = 200, seed: int = 13) -> dict:
    """Circular block bootstrap of the daily weights (preserves local persistence)."""
    rng = np.random.default_rng(seed)
    n = len(w_daily)
    nblocks = int(np.ceil(n / block))
    out = []
    for _ in range(n_draws):
        starts = rng.integers(0, n, size=nblocks)
        idx = np.concatenate([(s + np.arange(block)) % n for s in starts])[:n]
        w = w_daily[idx]
        w1 = _map_to_bars(w, first, last, n_bars)
        ww = np.zeros((n_bars, 3)); ww[:, 1] = w1; ww[:, 2] = 1 - w1
        r = bt.run(ts, o, c, ww, START, band=0.02, slippage_bps=1.0)
        out.append(bt.stats(r, BARS_1M)["cagr"])
    out = np.array(out)
    return dict(n=n_draws, block=block, mean=float(out.mean()), std=float(out.std()),
                p05=float(np.percentile(out, 5)), p50=float(np.percentile(out, 50)),
                p95=float(np.percentile(out, 95)))


def _event_study(s: dict, p: dict, daily_open: np.ndarray) -> dict:
    """Forward TQQQ returns after each state signal (analysis, not selection)."""
    masks = {
        "vov_add": _add_mask(s, p),
        "dec_boost": (np.isfinite(s["rv5"]) & np.isfinite(s["rv20"])
                      & (s["rv5"] < p["dec_ratio"] * s["rv20"])),
        "acc_cut": (np.isfinite(s["rv5"]) & np.isfinite(s["rv20"])
                    & (s["rv5"] > p["acc_ratio"] * s["rv20"])),
        "vov_spike_cut": (np.isfinite(s["vov"]) & np.isfinite(s["vov_10"])
                          & (s["vov"] > p["vov_spike"])
                          & (s["vov"] > p["vov_rise"] * s["vov_10"])),
    }
    op = np.asarray(daily_open, float)
    out = {}
    for name, mask in masks.items():
        row = {"n": int(mask.sum())}
        for h in (1, 5, 10, 20):
            a, b = [], []
            for k in np.flatnonzero(mask):
                if k + h + 1 < len(op):
                    a.append(op[k + 1 + h] / op[k + 1] - 1.0)
            for k in np.flatnonzero(~mask):
                if k + h + 1 < len(op):
                    b.append(op[k + 1 + h] / op[k + 1] - 1.0)
            a = np.asarray(a); b = np.asarray(b)
            if len(a) and len(b):
                t = a.mean() / (a.std(ddof=1) / np.sqrt(len(a))) if a.std(ddof=1) > 0 else 0.0
                row[f"h{h}"] = dict(
                    mean=float(a.mean()), median=float(np.median(a)),
                    hit=float(np.mean(a > 0)), non_mean=float(b.mean()),
                    diff=float(a.mean() - b.mean()), t=float(t),
                )
        out[name] = row
    return out


def main() -> None:
    ts, o, c = bt.panel(SYMS, START, END, "1min", warmup_days=500)
    i0 = bt.start_index(ts, START)
    ts, o, c = ts[i0:], o[i0:], c[i0:]
    dates, first, last = bt.day_bounds(ts)
    year = pd.to_datetime(dates[first]).year

    w, info = build_weights(ts, o, c)
    # Daily target series for placebos: the target at each session's last bar.
    w_target = w[last, 1]

    runs = {}
    for bp in (1.0, 5.0, 10.0):
        r = bt.run(ts, o, c, w, START, band=0.02, slippage_bps=bp)
        runs[f"{bp:g}bp"] = dict(metrics=_metrics(r), result=r)

    r1 = runs["1bp"]["result"]
    # Benchmarks: buy-and-hold TQQQ and QQQ on the same 1-minute bars.
    bench = {}
    for j, name in ((1, "tqqq"), (0, "qqq")):
        wb = np.zeros((len(ts), 3)); wb[:, j] = 1.0
        rb = bt.run(ts, o, c, wb, START, band=0.02, slippage_bps=1.0)
        bench[name] = _metrics(rb)

    rs, rb = _daily_returns(r1, c[:, 1])
    rq = pd.Series(c[last, 0], index=pd.to_datetime(dates[last])).pct_change().dropna()
    corr_t = float(rs.corr(rb))
    corr_q = float(rs.corr(rq))

    ys = bt.yearly(ts, r1["equity"], c[:, 1])
    yearly = {}
    eq_d = pd.Series(r1["equity"][last], index=pd.to_datetime(dates[last]))
    for y in sorted(set(year)):
        m = year == y
        yearly[int(y)] = dict(
            strategy=float(ys.get(int(y), {}).get("strategy", np.nan)),
            tqqq=float(ys.get(int(y), {}).get("benchmark", np.nan)),
            avg_tqqq_weight=float(np.mean(w_target[m])),
            days=int(m.sum()),
        )

    # Pre-registered grid, 1 bp.
    grid = {}
    for name, over in GRID:
        wg, _ = build_weights(ts, o, c, params(**over))
        rg = bt.run(ts, o, c, wg, START, band=0.02, slippage_bps=1.0)
        grid[name] = dict(parameters=params(**over), **_metrics(rg))

    # Ablations, 1 bp.
    ablations = {}
    for name, over in ABLATIONS:
        wa, ai = build_weights(ts, o, c, params(**over))
        ra = bt.run(ts, o, c, wa, START, band=0.02, slippage_bps=1.0)
        ablations[name] = dict(info=ai, **_metrics(ra))

    # Subperiods.
    sub = {}
    for lab, a, b in (("2016_2019", "2016-01-04", "2019-12-31"),
                      ("2020_2021", "2020-01-01", "2021-12-31"),
                      ("2022_2023", "2022-01-01", "2023-12-29")):
        sub[lab] = _subperiod(r1, a, b)

    # Leave-one-year-out CAGR from the annual returns.
    rets = np.array([yearly[y]["strategy"] for y in sorted(yearly)])
    yrs = np.array([yearly[y]["days"] for y in sorted(yearly)]) / 252.0
    total_years = float(yrs.sum())
    loyo = {}
    for k, y in enumerate(sorted(yearly)):
        g = np.prod(1.0 + np.delete(rets, k))
        loyo[str(y)] = dict(
            cagr=float(g ** (1.0 / max(total_years - yrs[k], 1e-9)) - 1.0),
            year_return=float(rets[k]),
        )

    # Relative-wealth concentration: how much of the net excess over TQQQ
    # comes from each calendar year.
    rel = {int(y): (1.0 + yearly[y]["strategy"]) / (1.0 + yearly[y]["tqqq"])
           for y in sorted(yearly)}
    logrel = {y: float(np.log(v)) for y, v in rel.items()}
    total_log = float(sum(logrel.values()))
    concentration = dict(
        relative_wealth_total=float(np.exp(total_log)),
        log_excess_total=total_log,
        log_excess_share_2022=float(logrel[2022] / total_log),
        relative_wealth_ex_2022=float(np.prod([v for y, v in rel.items() if y != 2022])),
        relative_wealth_ex_2018=float(np.prod([v for y, v in rel.items() if y != 2018])),
        relative_wealth_ex_2018_2022=float(np.prod([v for y, v in rel.items()
                                                    if y not in (2018, 2022)])),
        yearly_relative=rel,
        yearly_log_share={str(y): float(v / total_log) for y, v in logrel.items()},
    )

    # Daily-panel cross-check (same signal, daily marks) for robustness.
    tsd, od, cd = bt.panel(SYMS, START, END, "1D", warmup_days=500)
    jd = bt.start_index(tsd, START)
    tsd, od, cd = tsd[jd:], od[jd:], cd[jd:]
    wd, _ = build_weights(tsd, od, cd)
    rd = bt.run(tsd, od, cd, wd, START, band=0.02, slippage_bps=1.0)
    daily_cross = _metrics(rd, 252)

    # Static exposure-matched mix.
    avg = float(np.mean(w_target))
    ws = np.zeros((len(ts), 3)); ws[:, 1] = avg; ws[:, 2] = 1 - avg
    rs_ = bt.run(ts, o, c, ws, START, band=0.02, slippage_bps=1.0)
    static = dict(weight=avg, **_metrics(rs_))

    # Placebos (1 bp, 1-minute marks).
    plac_shuffle = _placebo_shuffle(w_target, first, last, len(ts), ts, o, c, n_draws=200)
    plac_block = _placebo_block(w_target, first, last, len(ts), ts, o, c, block=20, n_draws=200)
    s = _state(*_daily_high_low(ts, o, c, dates, first, last), P)
    plac_vov = _placebo_vov(s, P, first, last, len(ts), ts, o, c, year, n_draws=200)
    event = _event_study(s, P, o[first, 1])

    # Simple look-ahead check: rebuilding on a panel truncated at the cut date
    # must leave all weights before the cut date unchanged.
    lookahead = {}
    for cut in ("2020-03-12", "2022-09-13"):
        tsc, oc, cc = bt.panel(SYMS, START, cut, "1min", warmup_days=500)
        j0 = bt.start_index(tsc, START)
        tsc, oc, cc = tsc[j0:], oc[j0:], cc[j0:]
        wc, _ = build_weights(tsc, oc, cc)
        cut_idx = int(np.searchsorted(ts, pd.Timestamp(cut, tz="America/New_York")))
        n = min(cut_idx, len(wc))
        lookahead[cut] = bool(np.allclose(w[:n, 1], wc[:n, 1], atol=1e-12))

    result = dict(
        agent="vol-of-vol-timing",
        window=dict(start=START, end=END, marks="1m", bars=int(len(ts)),
                    sessions=int(len(first))),
        parameters=P,
        primary=dict(
            info=info,
            tqqq_exposure=float(np.mean(w[:, 1])),
            tqqq_time=float(np.mean(w[:, 1] > 1e-9)),
            corr_tqqq_daily=corr_t,
            corr_qqq_daily=corr_q,
            avg_daily_target=avg,
            **runs["1bp"]["metrics"],
        ),
        costs={k: v["metrics"] for k, v in runs.items()},
        benchmarks=bench,
        task_bar=dict(tqqq_cagr=0.3672, tqqq_max_drawdown=0.8229,
                      tqqq_sharpe=0.82, note="given in the task brief"),
        yearly=yearly,
        drawdowns=_drawdowns(r1, top=8),
        grid=grid,
        ablations=ablations,
        subperiods=sub,
        leave_one_year_out=loyo,
        concentration=concentration,
        static_mix=static,
        daily_crosscheck=daily_cross,
        placebo=dict(shuffle_weights=plac_shuffle, block_bootstrap=plac_block,
                     permute_vov_add=plac_vov),
        event_study=event,
        lookahead_prefix_identical=lookahead,
        notes=(
            "Development window only; 1-minute panel truncated at 2023-12-29. "
            "Signals use completed daily bars through session d; target set at "
            "d's close fills at d+1's open. Costs 1/5/10 bp, 2% band."
        ),
    )
    out = HERE / "result.json"
    out.write_text(json.dumps(_clean(result), indent=2), encoding="utf-8")
    print(f"wrote {out}")
    print(f"primary 1bp: CAGR {runs['1bp']['metrics']['cagr']*100:.2f}%  "
          f"DD {runs['1bp']['metrics']['max_drawdown']*100:.2f}%  "
          f"Sharpe {runs['1bp']['metrics']['sharpe']:.3f}  "
          f"TQQQ exp {np.mean(w[:,1])*100:.1f}%  corr {corr_t:.3f}")
    print("grid:")
    for name, g in grid.items():
        print(f"  {name:12s} CAGR {g['cagr']*100:6.2f}  DD {g['max_drawdown']*100:5.2f}  "
              f"Sharpe {g['sharpe']:.3f}  fills {g['fills']}")


if __name__ == "__main__":
    main()
