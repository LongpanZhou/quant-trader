"""Intraday-close momentum with a volatility-gated weakness exit.

Standalone strategy, development window only (2016-01-04 .. 2023-12-29).

Rules
-----
Universe: QQQ (signal), TQQQ (position), cash. One decision per session at the
close of the 15:29 ET bar (15:30), filled at the 15:30 open; the target is held
until the next 15:30 open.

    r_k      QQQ full intraday return: close(15:29) / open(09:30) - 1
    sigma_k  annualised stdev of the last `win` completed QQQ daily log
             returns through session k-1 (lagged one session)
    base_k   min(1, line / sigma_k)
    w_k      0                      if r_k <= 0 and sigma_k >= line
             base_k                 otherwise

`line` is both the volatility target and the "elevated vol" line (one number,
not two). Long only, weights in [0, 1]; idle weight is cash at 0%.

The signal is causal: r_k uses the 15:29 close, sigma_k uses daily closes
through the prior session, and the weight is filled at the next open. No
2024+ bar is loaded: the 1-minute panel ends 2023-12-29 and the daily parquet
is truncated at 2023-12-29 before any rolling statistic is computed.

Warmup uses QQQ daily closes from 2015 (the 1-minute archive starts
2016-01-04), so the rule is live on the first development session.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402

DEV_START = "2016-01-04"
DEV_END = "2023-12-29"
BARS_1M = 252 * 390
SYMBOLS = ("QQQ", "TQQQ")
COL_Q, COL_T = 0, 1

# Pre-registered centre (HYPOTHESIS.md).
LINE = 0.20
VOL_WINDOW = 10
DECISION_MIN = 15 * 60 + 29
SIGNAL = "full_day"

# Pre-registered 8-cell grid: (line, vol_window).
GRID = [
    (0.20, 10),   # centre
    (0.18, 10),
    (0.22, 10),
    (0.20, 5),
    (0.20, 15),
    (0.20, 20),
    (0.18, 20),
    (0.22, 20),
]


# --------------------------------------------------------------------------- #
# data / signals
# --------------------------------------------------------------------------- #
def load_panel(start: str = DEV_START, end: str = DEV_END):
    return bt.panel(SYMBOLS, start, end, "1min", warmup_days=0)


def _completed_session_count(ts) -> int:
    """Number of sessions whose 15:29 decision bar is present.

    A mid-day truncated panel ends inside a session; that partial session has
    no completed decision bar, so it is excluded from the signal frame and its
    bars carry the prior session's target.  A one-bar-per-session panel is
    treated as all-complete.
    """
    ts = pd.DatetimeIndex(ts)
    dates, first, last = bt.day_bounds(ts)
    if len(ts) == len(first):
        return len(first)
    t = pd.Timestamp(ts[-1])
    cutoff = (pd.Timestamp("12:59").time() if t.date() in bt.HALF_DAYS
              else pd.Timestamp("15:59").time())
    return len(first) if t.time() >= cutoff else len(first) - 1


def _session_indices(ts, decision_min: int = DECISION_MIN):
    """First bar (09:30), decision bar (15:29) and last bar (15:59) per day."""
    tod = np.asarray(ts.hour * 60 + ts.minute)
    dates, first, last = bt.day_bounds(ts)
    n = _completed_session_count(ts)
    first, last = first[:n], last[:n]
    dec = np.array([
        s + int(np.searchsorted(tod[s:e], decision_min))
        for s, e in zip(first, last)
    ])
    return dates[first], first, last, dec


def _daily_vol(panel_dates, window: int, line: float | None = None):
    """Lagged annualised QQQ daily vol, aligned to the panel session dates.

    The daily read is truncated at the panel's actual last *completed* session
    before the rolling statistic, so the vol window follows the panel end
    without using a partial session.
    """
    daily = pd.read_parquet(bt.DATA_DIR / "QQQ-1d-yahoo.parquet")
    daily["date"] = pd.to_datetime(daily["date"]).dt.date
    daily = daily[daily["date"] <= pd.Timestamp(panel_dates[-1]).date()]
    daily = daily.drop_duplicates("date", keep="last").sort_values("date")
    logret = np.log(daily["adjclose"].to_numpy(dtype=float))
    logret = np.diff(logret, prepend=np.nan)
    vol = pd.Series(logret).rolling(window, min_periods=window).std(ddof=0)
    vol = vol.shift(1).to_numpy() * np.sqrt(252.0)
    by_date = pd.Series(vol, index=daily["date"].to_numpy())
    return by_date.reindex(panel_dates).to_numpy(dtype=float)


def _signal(ts, o, c, signal: str, decision_min: int = DECISION_MIN):
    """Per-session causal signal values (r and the decision bar)."""
    dates, first, last, dec = _session_indices(ts, decision_min)
    q_open = np.asarray(o)[first, COL_Q]
    q_dec = np.asarray(c)[dec, COL_Q]
    if signal == "full_day":
        r = q_dec / q_open - 1.0
    elif signal == "last30":
        tod = np.asarray(ts.hour * 60 + ts.minute)
        ref = np.array([s + int(np.searchsorted(tod[s:e], decision_min - 30))
                        for s, e in zip(first, last)])
        r = q_dec / np.asarray(c)[ref, COL_Q] - 1.0
    elif signal == "last60":
        tod = np.asarray(ts.hour * 60 + ts.minute)
        ref = np.array([s + int(np.searchsorted(tod[s:e], decision_min - 60))
                        for s, e in zip(first, last)])
        r = q_dec / np.asarray(c)[ref, COL_Q] - 1.0
    else:
        raise ValueError(f"unknown signal {signal}")
    return dates, first, last, dec, r


def build_targets(ts, o, c, line: float = LINE, window: int = VOL_WINDOW,
                  signal: str = SIGNAL, threshold: float = 0.0,
                  decision_min: int = DECISION_MIN,
                  use_exit: bool = True, use_vol: bool = True):
    """Per-session target weights and diagnostics.

    use_exit=False gives the vol-target-only control; use_vol=False gives the
    close-exit-only control (base weight 1, no vol gate on the exit).
    """
    dates, first, last, dec, r = _signal(ts, o, c, signal, decision_min)
    sigma = _daily_vol(dates, window)
    safe = np.where(np.isfinite(sigma), np.maximum(sigma, 1e-9), 1e9)
    base = np.minimum(1.0, line / safe) if use_vol else np.ones(len(sigma))
    gate = (sigma >= line) if use_vol else np.ones(len(sigma), dtype=bool)
    exit_mask = (use_exit & (r <= threshold) & gate
                 & np.isfinite(sigma))
    target = np.where(exit_mask, 0.0, base)
    target = np.where(np.isfinite(sigma), target, 0.0)
    target = np.clip(target, 0.0, 1.0)
    info = {
        "dates": dates, "first": first, "last": last, "dec": dec,
        "r": r, "sigma": sigma, "base": base, "exit": exit_mask,
        "target": target, "n_sessions": len(dates),
    }
    return target, info


def expand_targets(ts, target, dec):
    """Map one target per session to the (n, 2) bar weights."""
    n = len(ts)
    w = np.zeros((n, 2))
    ends = np.r_[dec[1:], n]
    for k in range(len(dec)):
        w[dec[k]:ends[k], 1] = target[k]
    return w


def build_weights(ts, o, c, line: float = LINE, window: int = VOL_WINDOW,
                  signal: str = SIGNAL, threshold: float = 0.0,
                  decision_min: int = DECISION_MIN,
                  use_exit: bool = True, use_vol: bool = True):
    """Required public API: (n, 2) weights, column 1 is TQQQ, rest cash."""
    target, info = build_targets(ts, o, c, line, window, signal, threshold,
                                 decision_min, use_exit, use_vol)
    w = expand_targets(ts, target, info["dec"])
    assert (w >= 0).all() and (w.sum(axis=1) <= 1.0 + 1e-9).all()
    return w


# --------------------------------------------------------------------------- #
# evaluation helpers
# --------------------------------------------------------------------------- #
def pack(s: dict) -> dict:
    keys = ("cagr", "max_drawdown", "sharpe", "sortino", "volatility",
            "exposure", "turnover", "fills", "ending_equity", "years")
    return {k: (int(s[k]) if k == "fills" else float(s[k])) for k in keys}


def run_weights(ts, o, c, w, slip=1.0, start=DEV_START):
    r = bt.run(ts, o, c, w, start, band=0.02, slippage_bps=slip)
    return r, bt.stats(r, BARS_1M)


def daily_returns(res: dict) -> pd.Series:
    s = pd.Series(res["equity"], index=res["ts"])
    return s.groupby(res["ts"].date).last().pct_change().dropna()


def dd_window(ts, equity):
    eq = np.asarray(equity, dtype=float)
    peak = np.maximum.accumulate(eq)
    dd = eq / peak - 1.0
    j = int(np.argmin(dd))
    i = int(np.argmax(eq[:j + 1]))
    return {"peak": str(ts[i])[:10], "trough": str(ts[j])[:10],
            "dd": float(-dd[j])}


def subperiod(ts, equity, lo, hi):
    m = ((ts >= pd.Timestamp(lo, tz="America/New_York"))
         & (ts < pd.Timestamp(hi, tz="America/New_York") + pd.Timedelta(days=1)))
    x, tt = np.asarray(equity)[m], ts[m]
    if len(x) < 2:
        return None
    years = (tt[-1] - tt[0]).total_seconds() / (365.25 * 86400)
    peak = np.maximum.accumulate(x)
    return {"cagr": float((x[-1] / x[0]) ** (1 / years) - 1),
            "max_drawdown": float(-(x / peak - 1).min()),
            "years": float(years)}


def calendar_year_cut(ts, equity, year: int) -> dict:
    s = pd.Series(np.asarray(equity, dtype=float), index=ts)
    d = s.groupby(ts.date).last()
    r = d.pct_change().dropna()
    r = r[np.array([x.year != year for x in r.index])]
    eq = np.cumprod(1.0 + r.to_numpy())
    years = len(r) / 252.0
    peak = np.maximum.accumulate(eq)
    return {"cagr": float(eq[-1] ** (1 / years) - 1),
            "max_drawdown": float(-(eq / peak - 1).min()),
            "years": float(years)}


def metrics(ts, o, c, w, slip=1.0):
    res, s = run_weights(ts, o, c, w, slip)
    i0 = bt.start_index(ts, DEV_START)
    bench = bt.benchmark(c[i0:, COL_T], ts[i0:], BARS_1M)
    dr = daily_returns(res)
    bd = pd.Series(c[i0:, COL_T], index=ts[i0:])
    bd = bd.groupby(bd.index.date).last().pct_change().dropna()
    out = pack(s)
    out["benchmark"] = {
        "cagr": float(bench["cagr"]),
        "max_drawdown": float(bench["max_drawdown"]),
        "sharpe": float(bench["sharpe"]),
        "volatility": float(bench["volatility"]),
    }
    out["corr_to_tqqq_daily"] = float(dr.corr(bd.reindex(dr.index)))
    out["dd_window"] = dd_window(res["ts"], res["equity"])
    # Yearly from daily closes (bt.yearly attributes the New Year overnight
    # gap to the first bar of the new year, which distorts the first session).
    daily_eq = pd.Series(res["equity"], index=res["ts"])
    daily_eq = daily_eq.groupby(res["ts"].date).last()
    daily_eq.index = pd.to_datetime(daily_eq.index)
    daily_b = pd.Series(c[i0:, COL_T], index=ts[i0:])
    daily_b = daily_b.groupby(daily_b.index.date).last()
    daily_b.index = pd.to_datetime(daily_b.index)
    yearly = {}
    for year in range(2016, 2024):
        e = daily_eq[daily_eq.index.year == year]
        b = daily_b[daily_b.index.year == year]
        if len(e) < 2 or len(b) < 2:
            continue
        yearly[str(year)] = {
            "strategy": float(e.iloc[-1] / e.iloc[0] - 1.0),
            "benchmark": float(b.iloc[-1] / b.iloc[0] - 1.0),
        }
    out["yearly"] = yearly
    return out, res


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def main():
    ts, o, c = load_panel()
    dates, first, last, dec = _session_indices(ts)
    print(f"panel {len(ts):,} bars, {len(first)} sessions, "
          f"{ts[0].date()} .. {ts[-1].date()}")

    target, info = build_targets(ts, o, c, LINE, VOL_WINDOW, SIGNAL)
    w = expand_targets(ts, target, info["dec"])

    out = {
        "agent": "intraday-close-momentum",
        "strategy": "TQQQ 24h close-anchored momentum with vol-gated weakness exit",
        "window": {"start": DEV_START, "end": DEV_END, "marks": "1m",
                   "fills": "next open, 2% band", "idle": "cash at 0%"},
        "rules": {
            "signal": "QQQ full intraday return, open(09:30) -> close(15:29)",
            "decision": "15:29 ET close, fill 15:30 open",
            "vol": f"annualised stdev of last {VOL_WINDOW} QQQ daily log "
                   "returns through prior session",
            "base": f"min(1, {LINE} / sigma)",
            "exit": f"0 if r <= 0 and sigma >= {LINE}",
            "hold": "15:30 open -> next 15:30 open",
            "line": LINE, "vol_window": VOL_WINDOW,
            "warmup": "QQQ daily closes 2015-01-02..2015-12-31",
            "band": 0.02,
            "slippage_bps": [1.0, 5.0, 10.0],
        },
        "benchmark_tqqq": {},
        "dev": {},
    }

    # ---- costs ------------------------------------------------------------
    results = {}
    for slip in (1.0, 5.0, 10.0):
        m, res = metrics(ts, o, c, w, slip)
        results[slip] = (m, res)
        out["dev"][f"{int(slip)}bp"] = m
        print(f"centre {slip:2.0f}bp  CAGR {m['cagr']*100:6.2f}%  "
              f"DD {m['max_drawdown']*100:5.2f}%  Sharpe {m['sharpe']:4.2f}  "
              f"fills {m['fills']:,}  turnover {m['turnover']:.0f}x  "
              f"exposure {m['exposure']*100:.1f}%")

    m1, res1 = results[1.0]
    i0 = bt.start_index(ts, DEV_START)
    bench = bt.benchmark(c[i0:, COL_T], ts[i0:], BARS_1M)
    out["benchmark_tqqq"] = {k: float(v) for k, v in bench.items()}
    out["benchmark_tqqq"]["bar_from_brief"] = {
        "cagr": 0.3672, "max_drawdown": 0.8229, "sharpe": 0.82}

    out["diagnostics"] = {
        "exit_days": int(info["exit"].sum()),
        "exit_days_pct": float(info["exit"].mean()),
        "eligible_high_vol_days": int((info["sigma"] >= LINE).sum()),
        "avg_target": float(np.mean(info["target"])),
        "days_with_position": float(np.mean(target > 0)),
        "avg_weight_when_in": float(target[target > 0].mean()),
        "mean_sigma": float(np.nanmean(info["sigma"])),
        "decision_bar": "15:29 ET",
        "signal_mean_bp": float(np.nanmean(info["r"]) * 1e4),
    }
    out["subperiods"] = {
        "2016_2019": subperiod(res1["ts"], res1["equity"], "2016-01-04", "2019-12-31"),
        "2020_2021": subperiod(res1["ts"], res1["equity"], "2020-01-02", "2021-12-31"),
        "2022_2023": subperiod(res1["ts"], res1["equity"], "2022-01-03", "2023-12-29"),
    }

    # ---- pre-registered grid ---------------------------------------------
    grid = []
    for line, window in GRID:
        wt = build_weights(ts, o, c, line, window)
        mg, _ = metrics(ts, o, c, wt, 1.0)
        mg5, _ = metrics(ts, o, c, wt, 5.0)
        mg10, _ = metrics(ts, o, c, wt, 10.0)
        grid.append({
            "line": line, "vol_window": window,
            "cagr_1bp": mg["cagr"], "cagr_5bp": mg5["cagr"],
            "cagr_10bp": mg10["cagr"],
            "max_drawdown": mg["max_drawdown"], "sharpe": mg["sharpe"],
            "exposure": mg["exposure"], "turnover": mg["turnover"],
            "fills": mg["fills"], "corr_to_tqqq_daily": mg["corr_to_tqqq_daily"],
        })
        print(f"grid line {line:.2f} win {window:2d}  1bp {mg['cagr']*100:6.2f}%  "
              f"5bp {mg5['cagr']*100:6.2f}%  10bp {mg10['cagr']*100:6.2f}%  "
              f"DD {mg['max_drawdown']*100:5.2f}%  Sh {mg['sharpe']:4.2f}  "
              f"exp {mg['exposure']*100:4.1f}%")
    out["grid"] = grid

    # ---- neighbours (robustness, not used to choose the centre) ----------
    neighbours = []
    for name, kw in [
        ("signal last30", {"signal": "last30"}),
        ("signal last60", {"signal": "last60"}),
        ("exit threshold -25bp", {"threshold": -0.0025}),
        ("exit threshold +25bp", {"threshold": 0.0025}),
        ("decision 15:58", {"decision_min": 15 * 60 + 58}),
        ("vol window 30", {"window": 30}),
        ("line 0.21", {"line": 0.21}),
    ]:
        wt = build_weights(ts, o, c, **kw)
        mn, _ = metrics(ts, o, c, wt, 1.0)
        neighbours.append({"name": name, **{k: mn[k] for k in (
            "cagr", "max_drawdown", "sharpe", "exposure", "turnover", "fills",
            "corr_to_tqqq_daily")}})
        print(f"neigh {name:24s} CAGR {mn['cagr']*100:6.2f}%  "
              f"DD {mn['max_drawdown']*100:5.2f}%  Sh {mn['sharpe']:4.2f}")
    out["neighbours"] = neighbours

    # ---- controls --------------------------------------------------------
    controls = {}
    # vol target only, no close exit
    vol_only = build_weights(ts, o, c, line=LINE, window=VOL_WINDOW,
                             signal=SIGNAL, use_exit=False)
    mv, _ = metrics(ts, o, c, vol_only, 1.0)
    controls["vol_target_only"] = {k: mv[k] for k in (
        "cagr", "max_drawdown", "sharpe", "exposure", "turnover", "fills")}

    # close exit only, no vol target / gate
    close_only = build_weights(ts, o, c, line=LINE, window=VOL_WINDOW,
                               signal=SIGNAL, threshold=0.0, use_vol=False)
    mc, _ = metrics(ts, o, c, close_only, 1.0)
    controls["close_exit_only"] = {k: mc[k] for k in (
        "cagr", "max_drawdown", "sharpe", "exposure", "turnover", "fills")}

    # constant exposure at the same average
    const = float(np.mean(target))
    w_const = np.zeros((len(ts), 2))
    w_const[:, COL_T] = const
    mconst, _ = metrics(ts, o, c, w_const, 1.0)
    controls["constant_exposure_same_mean"] = {
        **{k: mconst[k] for k in ("cagr", "max_drawdown", "sharpe",
                                  "exposure", "turnover", "fills")},
        "weight": const}

    # buy and hold
    w_bh = np.zeros((len(ts), 2))
    w_bh[:, COL_T] = 1.0
    mbh, _ = metrics(ts, o, c, w_bh, 1.0)
    controls["buy_and_hold"] = {k: mbh[k] for k in (
        "cagr", "max_drawdown", "sharpe", "exposure", "turnover", "fills")}
    out["controls"] = controls
    for k, v in controls.items():
        print(f"control {k:30s} CAGR {v['cagr']*100:6.2f}%  "
              f"DD {v['max_drawdown']*100:5.2f}%  Sh {v['sharpe']:4.2f}")

    # ---- diagnostics: what the exit days actually avoided -----------------
    # 24h TQQQ return owned by each session's decision: 15:30 -> next 15:30.
    o_t = np.asarray(o)[:, COL_T]
    fwd = np.full(len(dec), np.nan)
    for k in range(len(dec) - 1):
        a = dec[k] + 1
        b = dec[k + 1] + 1
        if b < len(o_t):
            fwd[k] = o_t[b] / o_t[a] - 1.0
    exit_mask = info["exit"]
    highvol = np.isfinite(info["sigma"]) & (info["sigma"] >= LINE)
    non_exit_hv = highvol & ~exit_mask
    diag = out["diagnostics"]
    diag["forward_24h_all_bp"] = float(np.nanmean(fwd) * 1e4)
    diag["forward_24h_exit_days_bp"] = float(np.nanmean(fwd[exit_mask]) * 1e4)
    diag["forward_24h_highvol_nonexit_bp"] = float(
        np.nanmean(fwd[non_exit_hv]) * 1e4)
    diag["forward_24h_calm_bp"] = float(
        np.nanmean(fwd[~highvol & np.isfinite(fwd)]) * 1e4)
    diag["exit_hit_rate"] = float(np.nanmean(fwd[exit_mask] < 0))
    diag["highvol_nonexit_hit_rate"] = float(np.nanmean(fwd[non_exit_hv] < 0))
    order = np.argsort(np.where(np.isfinite(fwd), fwd, np.inf))[:10]
    diag["worst10_24h_days"] = [
        {"date": str(info["dates"][i])[:10],
         "tqqq_24h": float(fwd[i]),
         "weight": float(info["target"][i]),
         "exit": bool(exit_mask[i])}
        for i in order
    ]
    w20 = order[:20]
    diag["worst20_log_full"] = float(np.nansum(np.log1p(fwd[w20])))
    diag["worst20_log_at_weight"] = float(
        np.nansum(np.log1p(info["target"][w20] * fwd[w20])))

    # ---- placebo: random exit days, same count, inside high-vol days -----
    rng = np.random.default_rng(17)
    sigma = info["sigma"]
    eligible = np.flatnonzero(np.isfinite(sigma) & (sigma >= LINE))
    n_exit = int(info["exit"].sum())
    real_cagr = m1["cagr"]
    real_dd = m1["max_drawdown"]
    draws, dds = [], []
    for _ in range(200):
        pick = rng.choice(eligible, size=min(n_exit, len(eligible)),
                          replace=False)
        t = info["base"].copy()
        t[pick] = 0.0
        t = np.where(np.isfinite(sigma), t, 0.0)
        wt = expand_targets(ts, t, dec)
        _, sp = run_weights(ts, o, c, wt, 1.0)
        draws.append(float(sp["cagr"]))
        dds.append(float(sp["max_drawdown"]))
    draws = np.asarray(draws)
    dds = np.asarray(dds)
    out["placebo"] = {
        "n_draws": 200, "real_cagr": float(real_cagr),
        "mean": float(draws.mean()), "median": float(np.median(draws)),
        "p95": float(np.percentile(draws, 95)),
        "p_value": float((draws >= real_cagr).mean()),
        "real_dd": float(real_dd),
        "dd_mean": float(dds.mean()),
        "dd_p05": float(np.percentile(dds, 5)),
        "dd_p_value": float((dds <= real_dd).mean()),
        "note": "random exit days with the same count drawn from the "
                "high-vol eligible set; tests the close-sign timing, not "
                "the vol regime",
    }
    print("placebo", {k: (round(float(v), 4) if not isinstance(v, str) else v)
                      for k, v in out["placebo"].items()})

    # ---- cut tests -------------------------------------------------------
    cuts = {}
    for year in (2016, 2020, 2022, 2023):
        cuts[str(year)] = {
            "strategy": calendar_year_cut(res1["ts"], res1["equity"], year),
            "benchmark_ex_year": calendar_year_cut(
                ts[i0:], c[i0:, COL_T], year),
        }
    out["cut_tests"] = cuts
    for y, v in cuts.items():
        print(f"cut ex-{y}: strat {v['strategy']['cagr']*100:6.2f}% / "
              f"{v['strategy']['max_drawdown']*100:5.2f}%  "
              f"bench {v['benchmark_ex_year']['cagr']*100:6.2f}% / "
              f"{v['benchmark_ex_year']['max_drawdown']*100:5.2f}%")

    # ---- causality: truncation at 2022-01-03 -----------------------------
    j = bt.start_index(ts, "2022-01-03")
    w_trunc = build_weights(ts[:j], o[:j], c[:j])
    out["causality"] = {
        "truncation_date": "2022-01-03",
        "prior_weights_unchanged": bool(np.allclose(w_trunc, w[:j])),
    }
    print("causality", out["causality"])

    # ---- pass flags ------------------------------------------------------
    out["pass"] = {
        "cagr_above_bar_1bp": bool(m1["cagr"] > 0.3672),
        "dd_below_bar_1bp": bool(m1["max_drawdown"] < 0.8229),
        "dd_below_60_1bp": bool(m1["max_drawdown"] < 0.60),
        "cagr_above_bar_5bp": bool(out["dev"]["5bp"]["cagr"] > 0.3672),
        "cagr_above_bar_10bp": bool(out["dev"]["10bp"]["cagr"] > 0.3672),
        "calmar_1bp": float(m1["cagr"] / m1["max_drawdown"]),
        "benchmark_calmar": float(bench["cagr"] / bench["max_drawdown"]),
    }

    # ---- finite check ----------------------------------------------------
    for key in ("1bp", "5bp", "10bp"):
        for k, v in out["dev"][key].items():
            if isinstance(v, float) and not np.isfinite(v):
                raise ValueError(f"non-finite dev {key} {k}")

    (HERE / "result.json").write_text(
        json.dumps(out, indent=2, default=float), encoding="utf-8")
    print("wrote", HERE / "result.json")


if __name__ == "__main__":
    main()
