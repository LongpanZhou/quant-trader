"""Volume-dispersion rotation TQQQ/QQQ - `family-vol-of-volume`.

DEVELOPMENT WINDOW ONLY (2016-01-04 .. 2023-12-29).  No 2024+ bar is loaded.

Primary object
--------------
The dispersion of minute volume, measured as the Shannon entropy of the
1-minute QQQ volume shares in the last 60 minutes of the session, ranked
against the prior 252 sessions.  This is a *shape / dispersion* object.  It
does not use the volume level, volume acceleration, price trend, volatility,
drawdown, opening range, close flow, ML or relative strength.

Hypothesis
----------
Participation concentrated in a few minutes (low entropy rank) is decisive,
stable participation and supports continuation of the session's move into the
next session.  Diffuse, unstable participation (high entropy rank) is fragile.
The strategy holds TQQQ for the next session when the rank is below the
pre-registered threshold, and QQQ otherwise.  QQQ, not BIL, is the defensive
leg: it keeps equity exposure and the positive drift, while cutting the 3x
amplification exactly when participation is diffuse.

Decision clock
--------------
At the 15:59 ET close of session k, use QQQ 1-minute volume from 15:00-15:59
(the last 60 bars of session k) and the prior 252 completed sessions only.
The target for session k+1 is written on the 15:59 bar and fills at the
09:30 open of session k+1.  The harness's next-open rule is unchanged.

Run:
    $env:PYTHONPATH = "C:\\Users\\27175\\AppData\\Local\\Temp\\opencode\\pylibs"
    python research/new/family-vol-of-volume/strategy.py
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
SYMBOLS = ("QQQ", "TQQQ", "BIL")
COL_Q, COL_T, COL_B = 0, 1, 2

# Pre-registered centre.
RANK_THRESHOLD = 0.60
ENTROPY_MINUTES = 60
RANK_SESSIONS = 252
DEFENSIVE = "QQQ"

BAR = {"cagr": 0.3672, "max_drawdown": 0.8229, "sharpe": 0.82}
WINNERS = [
    "ratio-froth",
    "vol-scaled-crash-stop",
    "relative-value-tqqq",
    "fomc-opex-window",
    "family-session-timing",
    "family-short-reversal",
    "family-rebalance-flow",
    "family-intraday-microstructure-day",
    "family-ml-microstructure",
]


# --------------------------------------------------------------------------- #
# data and signal
# --------------------------------------------------------------------------- #
def load_volume(ts) -> np.ndarray:
    """QQQ 1-minute volume aligned to the panel's regular-session bars."""
    q = pd.read_parquet(bt.DATA_DIR / "QQQ-1m.parquet")
    q["ts"] = pd.to_datetime(q["ts"], utc=True).dt.tz_convert("America/New_York")
    q = q[
        (q["ts"].dt.time >= pd.Timestamp("09:30").time())
        & (q["ts"].dt.time < pd.Timestamp("16:00").time())
    ].set_index("ts")
    return q["volume"].reindex(ts).to_numpy(dtype=float)


def volume_matrix(ts, volume: np.ndarray) -> np.ndarray:
    """(sessions, width) matrix of regular-session minute volume; NaN padding."""
    _, first, last = bt.day_bounds(ts)
    nd = len(first)
    width = int((last - first + 1).max())
    mat = np.full((nd, width), np.nan)
    for k in range(nd):
        a, b = int(first[k]), int(last[k])
        mat[k, : b - a + 1] = volume[a : b + 1]
    return mat


def entropy_share(x: np.ndarray) -> float:
    """Shannon entropy of volume shares, normalised by log(length)."""
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x) & (x > 0)]
    if len(x) < 2:
        return np.nan
    p = x / x.sum()
    p = p[p > 0]
    return float(-np.sum(p * np.log(p)) / np.log(len(x)))


def entropy_series(mat: np.ndarray, minutes: int) -> np.ndarray:
    """Entropy of the last `minutes` volume bars of each session."""
    return np.array([entropy_share(mat[k, -minutes:]) for k in range(len(mat))])


def rank_prior(x: np.ndarray, sessions: int) -> np.ndarray:
    """Causal percentile rank of each value among the prior `sessions`.

    For session k the rank is the fraction of prior values <= x[k].  The
    current value is not compared with itself.  The first `min_periods`
    sessions are NaN and therefore take the defensive asset.
    """
    s = pd.Series(np.asarray(x, dtype=float))
    return s.rolling(sessions, min_periods=max(30, sessions // 4)).apply(
        lambda a: float(np.mean(a[-1] >= a[:-1])), raw=True
    ).to_numpy()


def signal_from_rank(rank: np.ndarray, threshold: float) -> np.ndarray:
    """sig[k] = target TQQQ weight for session k, set at the close of k-1."""
    sig = np.zeros(len(rank))
    good = np.isfinite(rank) & (rank < threshold)
    sig[1:] = good[:-1].astype(float)
    return sig


def build_weights_params(ts, o, c, threshold: float = RANK_THRESHOLD,
                         minutes: int = ENTROPY_MINUTES,
                         sessions: int = RANK_SESSIONS,
                         vol: np.ndarray | None = None) -> np.ndarray:
    if vol is None:
        vol = load_volume(ts)
    mat = volume_matrix(ts, vol)
    ent = entropy_series(mat, minutes)
    rank = rank_prior(ent, sessions)
    sig = signal_from_rank(rank, threshold)
    return broadcast(ts, sig)


def broadcast(ts, sig: np.ndarray) -> np.ndarray:
    """Map per-session targets to the (n,3) 1-minute weight matrix.

    sig is the TQQQ share; the remainder is QQQ.  On the last bar of session k
    the target for k+1 is written, so the change fills at the next open.
    """
    day_id = bt.day_ids(ts)
    _, _, last = bt.day_bounds(ts)
    w = np.zeros((len(ts), 3))
    w[:, COL_T] = sig[day_id]
    w[:, COL_Q] = 1.0 - sig[day_id]
    w[last[:-1], COL_T] = sig[1:]
    w[last[:-1], COL_Q] = 1.0 - sig[1:]
    assert w.min() >= -1e-12
    assert np.all(w.sum(axis=1) <= 1.0 + 1e-9)
    return w


def build_weights(ts, opens, closes):
    """Pre-registered centre."""
    return build_weights_params(ts, opens, closes)


# --------------------------------------------------------------------------- #
# metrics
# --------------------------------------------------------------------------- #
def run_range(ts, o, c, w, lo=DEV_START, hi=DEV_END, bp=1.0):
    i = int(ts.searchsorted(pd.Timestamp(lo, tz="America/New_York")))
    j = int(ts.searchsorted(pd.Timestamp(hi, tz="America/New_York")
                            + pd.Timedelta(days=1)))
    return bt.simulate(ts[i:j], o[i:j], c[i:j], w[i:j], band=0.02,
                       slippage_bps=bp, start_equity=bt.START_EQUITY)


def pack(s: dict) -> dict:
    keys = ("cagr", "max_drawdown", "sharpe", "sortino", "volatility",
            "exposure", "turnover", "fills", "ending_equity", "years")
    return {k: (int(s[k]) if k == "fills" else float(s[k])) for k in keys}


def stats_block(ts, o, c, w, bp=1.0, lo=DEV_START, hi=DEV_END):
    res = run_range(ts, o, c, w, lo, hi, bp)
    return pack(bt.stats(res, BARS_1M)), res


def dd_window(ts, equity):
    peak = np.maximum.accumulate(equity)
    dd = equity / peak - 1.0
    j = int(np.argmin(dd))
    i = int(np.argmax(equity[: j + 1]))
    return {"peak": str(ts[i])[:10], "trough": str(ts[j])[:10],
            "dd": float(-dd[j])}


def subperiod(ts, equity, lo, hi):
    m = ((ts >= pd.Timestamp(lo, tz="America/New_York"))
         & (ts < pd.Timestamp(hi, tz="America/New_York") + pd.Timedelta(days=1)))
    x, tt = equity[m], ts[m]
    if len(x) < 2:
        return None
    years = (tt[-1] - tt[0]).total_seconds() / (365.25 * 86400)
    peak = np.maximum.accumulate(x)
    return {"cagr": float((x[-1] / x[0]) ** (1 / years) - 1),
            "max_drawdown": float(-(x / peak - 1).min()), "years": float(years)}


def daily_approx(sig: np.ndarray, t_open: np.ndarray,
                 q_open: np.ndarray) -> float:
    """Causal daily open-to-open approximation for placebos/controls.

    sig[k] is the TQQQ share for session k set at the close of k-1.  Session
    k's capturable return is open[k+1]/open[k]-1, so use sig[:-1] against the
    return array shifted by one.
    """
    t_oo = np.r_[np.nan, t_open[1:] / t_open[:-1] - 1.0]
    q_oo = np.r_[np.nan, q_open[1:] / q_open[:-1] - 1.0]
    s = np.asarray(sig, dtype=float)[:-1]
    r = np.nan_to_num(s * t_oo[1:] + (1.0 - s) * q_oo[1:])
    eq = np.cumprod(1.0 + r)
    years = len(r) / 252.0
    return float(eq[-1] ** (1.0 / years) - 1.0)


# --------------------------------------------------------------------------- #
# correlation with the nine current winners
# --------------------------------------------------------------------------- #
def archived_dev_returns(slug: str) -> pd.Series:
    d = json.loads((HERE.parent / "curves" / f"{slug}.json").read_text())
    dates = pd.to_datetime(d["dates"])
    vals = np.asarray(d["values"], dtype=float)
    keep = dates <= pd.Timestamp(DEV_END)
    return pd.Series(vals[keep], index=dates[keep]).pct_change()


def correlation_block(eqd: pd.Series, winners) -> dict:
    r = eqd.pct_change().dropna()
    out = {"winners": {}}
    for slug in winners:
        rr = archived_dev_returns(slug)
        idx = r.index.intersection(rr.dropna().index)
        out["winners"][slug] = {"corr": float(r.loc[idx].corr(rr.loc[idx])),
                                "n": int(len(idx))}
    vals = [v["corr"] for v in out["winners"].values()]
    out["min"] = float(min(vals))
    out["max"] = float(max(vals))
    out["mean"] = float(np.mean(vals))
    return out


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def main():
    ts, o, c = bt.panel(SYMBOLS, DEV_START, DEV_END, "1min", warmup_days=30)
    dates, first, last = bt.day_bounds(ts)
    nd = len(first)
    print(f"panel {len(ts):,} bars, {nd} sessions, {ts[0].date()} .. {ts[-1].date()}")

    vol = load_volume(ts)
    mat = volume_matrix(ts, vol)
    ent = entropy_series(mat, ENTROPY_MINUTES)
    rank = rank_prior(ent, RANK_SESSIONS)
    sig = signal_from_rank(rank, RANK_THRESHOLD)
    w = broadcast(ts, sig)

    out = {
        "strategy": "family-vol-of-volume",
        "family": "vol-of-volume",
        "directory": "research/new/family-vol-of-volume",
        "window": {"start": DEV_START, "end": DEV_END, "marks": "1m",
                   "fills": "next open, 2% band", "idle": DEFENSIVE,
                   "holdout": "not loaded"},
        "rules": {
            "primary": "dispersion (entropy) of minute QQQ volume",
            "signal": ("H = -sum p_i log p_i / log(60), p_i = share of QQQ "
                       "volume in minute i over 15:00-15:59 ET"),
            "normalisation": ("causal percentile rank of H among the prior "
                              f"{RANK_SESSIONS} sessions"),
            "decision": "15:59 ET close; target for next session",
            "threshold": RANK_THRESHOLD,
            "tqqq_weight": "1.0 if rank < threshold else 0.0",
            "defensive_asset": DEFENSIVE,
            "bar": BAR,
        },
        "dev": {},
    }

    results = {}
    for bp in (0.0, 1.0, 5.0, 10.0):
        s, res = stats_block(ts, o, c, w, bp)
        results[bp] = (s, res)
        if bp in (1.0, 5.0, 10.0):
            out["dev"][f"{int(bp)}bp"] = s
        print(f"centre {bp:2.0f}bp  CAGR {s['cagr']*100:6.2f}%  "
              f"DD {s['max_drawdown']*100:5.2f}%  Sharpe {s['sharpe']:4.2f}  "
              f"fills {s['fills']:,}  turnover {s['turnover']:.0f}  "
              f"exposure {s['exposure']*100:.1f}%")

    s1, res1 = results[1.0]
    eq_series = bt.daily_last(res1["equity"], res1["ts"])
    eq_series.index = pd.to_datetime(eq_series.index)

    # benchmark
    i0 = bt.start_index(ts, DEV_START)
    bench = bt.benchmark(c[i0:, COL_T], ts[i0:], BARS_1M)
    out["benchmark_tqqq"] = {k: float(v) for k, v in bench.items()}
    out["benchmark_qqq"] = {k: float(v) for k, v in
                            bt.benchmark(c[i0:, COL_Q], ts[i0:], BARS_1M).items()}
    print(f"bench TQQQ  CAGR {bench['cagr']*100:6.2f}%  "
          f"DD {bench['max_drawdown']*100:5.2f}%  Sharpe {bench['sharpe']:4.2f}")

    # exposure (bt.stats counts QQQ as invested; report TQQQ share separately)
    wsess = sig[1:]
    out["exposure"] = {
        "mean_tqqq_weight_session": float(np.mean(wsess)),
        "mean_tqqq_weight_bar": float(w[:, COL_T].mean()),
        "fraction_sessions_tqqq": float(np.mean(wsess > 0.99)),
        "fraction_sessions_qqq": float(np.mean(wsess < 1e-9)),
        "stats_exposure_incl_qqq": float(s1["exposure"]),
        "signal_changes": int(np.sum(np.diff(np.r_[0.0, sig]) != 0)),
    }

    bench_slice = c[i0 : i0 + len(res1["ts"]), COL_T]
    out["yearly"] = {
        str(k): {"strategy": float(v["strategy"]), "benchmark": float(v["benchmark"])}
        for k, v in bt.yearly(res1["ts"], res1["equity"], bench_slice).items()
    }
    out["dd_window"] = dd_window(res1["ts"], res1["equity"])
    out["subperiods"] = {
        "2016_2019": subperiod(res1["ts"], res1["equity"], "2016-01-04", "2019-12-31"),
        "2020_2021": subperiod(res1["ts"], res1["equity"], "2020-01-01", "2021-12-31"),
        "2022_2023": subperiod(res1["ts"], res1["equity"], "2022-01-03", "2023-12-29"),
    }

    # ---- pre-registered 8-cell rank grid -----------------------------------
    grid = []
    for thr in (0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70, 0.75):
        wt = build_weights_params(ts, o, c, threshold=thr, vol=vol)
        ss, _ = stats_block(ts, o, c, wt)
        grid.append({"rank_threshold": thr, **ss,
                     "tqqq_exposure": float(wt[:, COL_T].mean()),
                     "passes_bar": bool(ss["cagr"] > BAR["cagr"]
                                        and ss["max_drawdown"] < BAR["max_drawdown"])})
        print(f"grid rank<{thr:.2f}  CAGR {ss['cagr']*100:6.2f}%  "
              f"DD {ss['max_drawdown']*100:5.2f}%  Sh {ss['sharpe']:.2f}  "
              f"fills {ss['fills']:,}")
    out["grid"] = grid

    # ---- neighbours: entropy window, rank lookback, continuous weight ------
    neigh = []
    for mins in (30, 45, 60, 90, 120):
        wt = build_weights_params(ts, o, c, minutes=mins, vol=vol)
        ss, _ = stats_block(ts, o, c, wt)
        neigh.append({"name": f"entropy_minutes {mins}", **ss})
        print(f"neigh minutes {mins:3d}  CAGR {ss['cagr']*100:6.2f}%  "
              f"DD {ss['max_drawdown']*100:5.2f}%  Sh {ss['sharpe']:.2f}")
    for sess in (126, 252, 504):
        wt = build_weights_params(ts, o, c, sessions=sess, vol=vol)
        ss, _ = stats_block(ts, o, c, wt)
        neigh.append({"name": f"rank_sessions {sess}", **ss})
        print(f"neigh rank {sess:3d}     CAGR {ss['cagr']*100:6.2f}%  "
              f"DD {ss['max_drawdown']*100:5.2f}%  Sh {ss['sharpe']:.2f}")
    # continuous version: weight 1 below rank 0.40, 0 at rank 0.80
    cont = np.clip((0.80 - rank) / 0.40, 0.0, 1.0)
    cont_sig = np.r_[0.0, np.nan_to_num(cont[:-1])]
    wt = broadcast(ts, cont_sig)
    ss, _ = stats_block(ts, o, c, wt)
    neigh.append({"name": "continuous_rank_0.40_0.80", **ss,
                  "tqqq_exposure": float(np.mean(cont_sig))})
    print(f"neigh continuous      CAGR {ss['cagr']*100:6.2f}%  "
          f"DD {ss['max_drawdown']*100:5.2f}%  Sh {ss['sharpe']:.2f}  "
          f"exposure {np.mean(cont_sig):.2f}")
    out["neighbours"] = neigh

    # ---- controls ----------------------------------------------------------
    controls = {}
    wt = np.zeros((len(ts), 3))
    wt[:, COL_T] = 1.0
    ss, _ = stats_block(ts, o, c, wt)
    controls["tqqq_buy_hold"] = ss
    print(f"control TQQQ          CAGR {ss['cagr']*100:6.2f}%  "
          f"DD {ss['max_drawdown']*100:5.2f}%  Sh {ss['sharpe']:.2f}")
    wt = np.zeros((len(ts), 3))
    wt[:, COL_Q] = 1.0
    ss, _ = stats_block(ts, o, c, wt)
    controls["qqq_buy_hold"] = ss
    print(f"control QQQ           CAGR {ss['cagr']*100:6.2f}%  "
          f"DD {ss['max_drawdown']*100:5.2f}%  Sh {ss['sharpe']:.2f}")
    mean_w = float(np.mean(sig[1:]))
    wt = np.zeros((len(ts), 3))
    wt[:, COL_T] = mean_w
    wt[:, COL_Q] = 1.0 - mean_w
    ss, _ = stats_block(ts, o, c, wt)
    controls["constant_mix_same_mean"] = {**ss, "tqqq_weight": mean_w}
    print(f"control constant {mean_w:.2f}  CAGR {ss['cagr']*100:6.2f}%  "
          f"DD {ss['max_drawdown']*100:5.2f}%  Sh {ss['sharpe']:.2f}")

    # volume-level control: same construction on total-session QQQ volume.
    # This checks that the entropy signal is not just volume level.
    total = np.nansum(mat, axis=1)
    lvl_rank = rank_prior(total, RANK_SESSIONS)
    lvl_sig = signal_from_rank(lvl_rank, RANK_THRESHOLD)
    wt = broadcast(ts, lvl_sig)
    ss, _ = stats_block(ts, o, c, wt)
    controls["volume_level_gate"] = {**ss, "tqqq_exposure": float(np.mean(lvl_sig[1:]))}
    print(f"control volume level  CAGR {ss['cagr']*100:6.2f}%  "
          f"DD {ss['max_drawdown']*100:5.2f}%  Sh {ss['sharpe']:.2f}  "
          f"exposure {np.mean(lvl_sig[1:]):.2f}")
    out["controls"] = controls

    # ---- event study -------------------------------------------------------
    t_open = o[first, COL_T]
    q_open = o[first, COL_Q]
    t_oo = np.r_[np.nan, t_open[1:] / t_open[:-1] - 1.0]
    q_oo = np.r_[np.nan, q_open[1:] / q_open[:-1] - 1.0]
    # forward capturable return for a decision at close k: open k+1 to
    # open k+2 = t_oo[k+2].
    fwd_t = np.r_[t_oo[2:], np.nan, np.nan]
    fwd_q = np.r_[q_oo[2:], np.nan, np.nan]
    valid = np.isfinite(rank) & np.isfinite(fwd_t)
    low = valid & (rank < RANK_THRESHOLD)
    high = valid & (rank >= RANK_THRESHOLD)
    def desc(mask, fwd):
        x = fwd[mask]
        return {"n": int(mask.sum()), "mean_bp": float(np.mean(x) * 1e4),
                "median_bp": float(np.median(x) * 1e4),
                "win": float(np.mean(x > 0)),
                "t": float(np.mean(x) / (np.std(x) / np.sqrt(len(x))))}
    ev = {
        "tqqq_low_entropy": desc(low, fwd_t),
        "tqqq_high_entropy": desc(high, fwd_t),
        "tqqq_spread_bp": desc(low, fwd_t)["mean_bp"] - desc(high, fwd_t)["mean_bp"],
        "qqq_low_entropy": desc(low, fwd_q),
        "qqq_high_entropy": desc(high, fwd_q),
    }
    out["event_study"] = ev
    print("event study", ev)

    # signal diagnostics: correlation with volume level and same-day move
    dayret = c[last, COL_Q] / o[first, COL_Q] - 1.0
    out["signal_diagnostics"] = {
        "entropy_mean": float(np.nanmean(ent)),
        "entropy_std": float(np.nanstd(ent)),
        "rank_mean": float(np.nanmean(rank)),
        "rank_q10": float(np.nanpercentile(rank, 10)),
        "rank_q50": float(np.nanpercentile(rank, 50)),
        "rank_q90": float(np.nanpercentile(rank, 90)),
        "corr_rank_log_total_volume": float(pd.Series(rank).corr(
            pd.Series(np.log(np.maximum(total, 1))))),
        "corr_rank_same_day_qqq_return": float(pd.Series(rank).corr(
            pd.Series(dayret))),
    }
    print("signal diagnostics", out["signal_diagnostics"])

    # ---- placebo -----------------------------------------------------------
    rng = np.random.default_rng(20261127)
    real_daily = daily_approx(sig, t_open, q_open)
    draws = []
    for _ in range(300):
        k = int(rng.integers(30, nd - 30))
        draws.append(daily_approx(np.roll(sig, k), t_open, q_open))
    draws = np.asarray(draws)
    out["placebo"] = {
        "n_draws": int(len(draws)), "marks": "1D open-to-open approximation",
        "real_daily_cagr": float(real_daily),
        "real_1m_cagr_1bp": float(s1["cagr"]),
        "mean": float(draws.mean()), "p95": float(np.quantile(draws, 0.95)),
        "p99": float(np.quantile(draws, 0.99)), "max": float(draws.max()),
        "p_value": float((draws >= real_daily).mean()),
    }
    print("placebo", {k: (round(v, 4) if isinstance(v, float) else v)
                      for k, v in out["placebo"].items()})

    # ---- correlation vs nine winners ---------------------------------------
    corr = correlation_block(eq_series, WINNERS)
    out["corr_winners"] = corr["winners"]
    out["corr_summary"] = {"min": corr["min"], "max": corr["max"],
                           "mean": corr["mean"]}
    print("corr winners", {k: round(v["corr"], 3) for k, v in corr["winners"].items()})

    # ---- causality truncation ---------------------------------------------
    j = bt.start_index(ts, "2022-01-03")
    j2 = bt.start_index(ts, "2021-12-30")
    w_trunc = build_weights(ts[:j], o[:j], c[:j])
    out["causality"] = {
        "truncation_date": "2022-01-03",
        "compare_through": "2021-12-29",
        "prior_weights_unchanged": bool(np.allclose(w_trunc[:j2], w[:j2])),
    }
    print("causality", out["causality"])

    # ---- verdict / kill criteria ------------------------------------------
    passes = (s1["cagr"] > BAR["cagr"]
              and s1["max_drawdown"] < BAR["max_drawdown"])
    out["verdict"] = {
        "dev_pass_1bp": bool(passes),
        "cagr_margin_pp": float((s1["cagr"] - BAR["cagr"]) * 100),
        "dd_margin_pp": float((BAR["max_drawdown"] - s1["max_drawdown"]) * 100),
        "fills_floor": bool(s1["fills"] >= 100),
        "status": "PASS" if passes and s1["fills"] >= 100 else "FAIL",
    }
    out["kill_criteria"] = [
        "Kill if the 1 bp dev CAGR is at or below 36.72% or max DD at or above 82.29%.",
        "Kill if full-window fills are below 100.",
        "Kill if the circular-shift placebo p-value is above 0.10.",
        "Kill if the 5 bp result turns the CAGR below the bar or the DD above it.",
        "Kill if the sign flips in either 2016-2019 or 2022-2023.",
        "Kill if daily correlation with any current winner exceeds 0.90, which would mean the family is not distinct.",
        "Kill if the neighbour windows (entropy 30-120 min, rank lookback 126/252/504) are not all positive.",
    ]

    (HERE / "result.json").write_text(json.dumps(out, indent=1, default=float))
    print("wrote", HERE / "result.json")


if __name__ == "__main__":
    main()
