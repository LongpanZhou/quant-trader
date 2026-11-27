"""Standalone two-stream risk parity: calm QQQ carry + panic TQQQ reversal.

This is the revisit rebuild of `winner-ensemble-blend`. It does NOT use the
165-day QQQ/TQQQ/SPY/NDX moving-average gate, the round-1 4% stop, or the old
`build_weights`. The allocation idea (inverse-volatility blending) is rebuilt on
two genuinely different return streams:

  Stream A (calm carry):  70% QQQ / 30% BIL when QQQ 10-day realised vol is
                          below its trailing 60-day 40th percentile and QQQ's
                          5-day return is positive; otherwise BIL.
  Stream B (panic reversion): 100% TQQQ after a sharp QQQ selloff (3-day <= -5%,
                          or 1-day <= -3% with 10d/60d vol >= 1.5), held at most
                          3 sessions, exit on a close above the 10-day mean, an
                          8% close-based stop, or time; 2-session cooldown.

The blend weight is inverse trailing 20-day volatility of each stream, clipped
to [0.20, 0.80], with the residual in BIL. All signals are daily at the 15:59
close; targets fill at the next bar's open with a 2% band.

BACKTESTS ARE PAUSED. This file is written but must not be executed until the
lead authorises the new test.

Run (after authorisation):
    $env:PYTHONPATH = "C:\\Users\\27175\\AppData\\Local\\Temp\\opencode\\pylibs"
    python research/revisit/winner-ensemble-blend/strategy.py
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
from minute_marks import to_minutes  # noqa: E402

DEV_START, DEV_END = "2016-01-04", "2023-12-29"
SYMS = ("QQQ", "TQQQ", "BIL")
BPY = 252 * 390

DEFAULTS = dict(
    carry_vol_look=10,
    carry_rank_win=60,
    carry_rank_min=40,
    carry_rank_q=0.40,
    carry_mom_look=5,
    carry_qqq_weight=0.70,
    rev_drop3=-0.05,
    rev_drop1=-0.03,
    rev_vol_ratio=1.5,
    rev_hold=3,
    rev_stop=0.08,
    rev_cooldown=2,
    alloc_vol_look=20,
    alloc_vol_min=10,
    alloc_lo=0.20,
    alloc_hi=0.80,
)


# --------------------------------------------------------------------------- #
# data
# --------------------------------------------------------------------------- #
def daily_frame(sym: str) -> pd.DataFrame:
    d = pd.read_parquet(ROOT / "data" / "intraday-hf" / f"{sym}-1d-yahoo.parquet")
    d["date"] = pd.to_datetime(d["date"]).dt.date
    f = d["adjclose"] / d["close"]
    for c in ("open", "high", "low", "close"):
        d[c] = d[c] * f
    return d[["date", "open", "high", "low", "close"]].sort_values("date").reset_index(drop=True)


def session_dates(ts: pd.DatetimeIndex) -> np.ndarray:
    dates, first, _ = bt.day_bounds(ts)
    return dates[first]


def baseline_weights(qfull: pd.Series, dates: np.ndarray, dts: pd.DatetimeIndex,
                     ts: pd.DatetimeIndex) -> np.ndarray:
    """165-day QQQ baseline: benchmark / correlation only, never a strategy gate.

    The SMA is computed on the full daily history (2015+) and then mapped to the
    session dates, so the benchmark is defined from the first dev session.
    """
    sma = qfull.rolling(165).mean()
    on = (qfull > sma)
    on_dates = pd.Series(on, index=qfull.index).reindex(pd.Index(dates)).fillna(False).to_numpy()
    w = np.zeros((len(dates), 3))
    w[:, 1] = on_dates
    w[:, 2] = 1.0 - on_dates
    return to_minutes(dts, w, ts, "1D")


# --------------------------------------------------------------------------- #
# strategy
# --------------------------------------------------------------------------- #
def _signals(qc: pd.Series, p: dict):
    ret = qc.pct_change()
    vol = ret.rolling(p["carry_vol_look"]).std()
    vol60 = ret.rolling(60).std()
    q = vol.rolling(p["carry_rank_win"], min_periods=p["carry_rank_min"]).quantile(
        p["carry_rank_q"])
    r5 = qc / qc.shift(p["carry_mom_look"]) - 1.0
    r3 = qc / qc.shift(3) - 1.0
    r1 = qc.pct_change()
    sma10 = qc.rolling(10).mean()
    ratio = vol / vol60

    on_a = ((vol < q) & (r5 > 0)).fillna(False).to_numpy()
    entry_b = ((r3 <= p["rev_drop3"])
               | ((r1 <= p["rev_drop1"]) & (ratio >= p["rev_vol_ratio"]))).fillna(False).to_numpy()
    return on_a, entry_b, sma10.to_numpy()


def _build_from_signals(qc: pd.Series, tc: pd.Series, bc: pd.Series,
                        dates: np.ndarray, on_a: np.ndarray, entry_b: np.ndarray,
                        sma10: np.ndarray, p: dict):
    """Given daily signals, build the daily target rows (target for the next day).

    Row d is the target set at the close of day d and filled at day d+1's open.
    """
    nd = len(dates)
    wA = np.zeros((nd, 3))
    wB = np.zeros((nd, 3))
    wA[:, 2] = 1.0
    wB[:, 2] = 1.0
    wA[on_a, 0] = p["carry_qqq_weight"]
    wA[on_a, 2] = 1.0 - p["carry_qqq_weight"]

    holding = False
    held = 0
    cooldown = 0
    entry_ref = np.nan
    events = []
    qqq = qc.to_numpy()
    tqqq = tc.to_numpy()
    for d in range(nd):
        if holding:
            exit_now = False
            if np.isfinite(entry_ref):
                if qqq[d] > sma10[d] or tqqq[d] < entry_ref * (1.0 - p["rev_stop"]) \
                        or held >= p["rev_hold"]:
                    exit_now = True
            if exit_now:
                holding = False
                cooldown = p["rev_cooldown"]
                wB[d, 1], wB[d, 2] = 0.0, 1.0
            else:
                wB[d, 1], wB[d, 2] = 1.0, 0.0
                if not np.isfinite(entry_ref):
                    entry_ref = tqqq[d]  # first close after the entry fill
                held += 1
        elif cooldown > 0:
            wB[d, 1], wB[d, 2] = 0.0, 1.0
            cooldown -= 1
        elif entry_b[d]:
            holding = True
            held = 0
            entry_ref = np.nan
            events.append(d)
            wB[d, 1], wB[d, 2] = 1.0, 0.0
        else:
            wB[d, 1], wB[d, 2] = 0.0, 1.0

    # standalone stream daily returns (close-to-close), used only for sizing
    px = np.column_stack([qc.to_numpy(), tc.to_numpy(), bc.to_numpy()])
    aret = np.zeros_like(px)
    aret[1:] = px[1:] / px[:-1] - 1.0
    retA = np.zeros(nd)
    retB = np.zeros(nd)
    retA[1:] = (wA[:-1] * aret[1:]).sum(axis=1)
    retB[1:] = (wB[:-1] * aret[1:]).sum(axis=1)

    sA = pd.Series(retA).rolling(p["alloc_vol_look"], min_periods=p["alloc_vol_min"]).std().shift(1).to_numpy()
    sB = pd.Series(retB).rolling(p["alloc_vol_look"], min_periods=p["alloc_vol_min"]).std().shift(1).to_numpy()
    ok = np.isfinite(sA) & np.isfinite(sB) & (sA > 0) & (sB > 0)
    aA = np.full(nd, 0.5)
    aA[ok] = (1.0 / sA[ok]) / (1.0 / sA[ok] + 1.0 / sB[ok])
    aA = np.clip(aA, p["alloc_lo"], p["alloc_hi"])
    aB = 1.0 - aA

    w = aA[:, None] * wA + aB[:, None] * wB
    w[:, 2] = 1.0 - w[:, 0] - w[:, 1]

    info = {
        "days": int(nd),
        "carry_on_share": float(on_a.mean()),
        "carry_qqq_exposure_mean": float(wA[:, 0].mean()),
        "reversal_events": int(len(events)),
        "reversal_event_dates": [str(dates[i]) for i in events],
        "reversal_exposure_share": float((wB[:, 1] > 0).mean()),
        "alloc_mean_A": float(aA.mean()),
        "alloc_mean_B": float(aB.mean()),
        "alloc_min_A": float(aA.min()),
        "alloc_max_A": float(aA.max()),
        "blend_mean_qqq": float(w[:, 0].mean()),
        "blend_mean_tqqq": float(w[:, 1].mean()),
        "blend_mean_bil": float(w[:, 2].mean()),
    }
    return w, wA, wB, info, events


def build_weights(ts: pd.DatetimeIndex, opens: np.ndarray, closes: np.ndarray,
                  **overrides):
    """Return (1-minute target weights (n,3), info dict).

    Daily signals are computed from the adjusted daily QQQ/TQQQ/BIL closes
    through the session date; row d is the target for day d+1 and is mapped to
    minutes so the last bar of day d carries it (fill at d+1 open).
    """
    p = dict(DEFAULTS)
    p.update(overrides)
    dates = session_dates(ts)
    last = dates[-1]
    q = daily_frame("QQQ")
    t = daily_frame("TQQQ")
    b = daily_frame("BIL")
    q = q[q["date"] <= last].set_index("date")
    t = t[t["date"] <= last].set_index("date")
    b = b[b["date"] <= last].set_index("date")
    idx = pd.Index(dates)
    qc = q["close"].reindex(idx).ffill()
    tc = t["close"].reindex(idx).ffill()
    bc = b["close"].reindex(idx).ffill()
    # features need the pre-2016 daily history too: compute on the full frame,
    # then reindex the signals to the session dates.
    qfull = daily_frame("QQQ")
    qfull = qfull[qfull["date"] <= last].set_index("date")["close"]
    on_a_full, entry_b_full, sma10_full = _signals(qfull, p)
    on_a = pd.Series(on_a_full, index=qfull.index).reindex(idx).fillna(False).to_numpy()
    entry_b = pd.Series(entry_b_full, index=qfull.index).reindex(idx).fillna(False).to_numpy()
    sma10 = pd.Series(sma10_full, index=qfull.index).reindex(idx).ffill().to_numpy()

    w, wA, wB, info, events = _build_from_signals(qc, tc, bc, dates, on_a, entry_b, sma10, p)
    dts = pd.DatetimeIndex([pd.Timestamp(d, tz="America/New_York") for d in dates])
    w1 = to_minutes(dts, w, ts, "1D")
    info["params"] = {k: (list(v) if isinstance(v, tuple) else v) for k, v in p.items()}
    info["reversal_event_indices"] = [int(i) for i in events]
    return w1, info


# --------------------------------------------------------------------------- #
# evaluation
# --------------------------------------------------------------------------- #
def _run_window(ts, o, c, w, start, end, slip):
    i = bt.start_index(ts, start)
    j = int(ts.searchsorted(pd.Timestamp(end, tz="America/New_York"), side="right"))
    return bt.simulate(ts[i:j], o[i:j], c[i:j], w[i:j], band=0.02, slippage_bps=slip)


def _stats(r, tsx):
    s = bt.stats(r, BPY)
    return {
        "cagr": float(s["cagr"]), "max_drawdown": float(s["max_drawdown"]),
        "sharpe": float(s["sharpe"]), "sortino": float(s["sortino"]),
        "volatility": float(s["volatility"]), "exposure": float(s["exposure"]),
        "fills": int(s["fills"]), "turnover": float(s["turnover"]),
        "ending_equity": float(s["ending_equity"]),
    }


def _daily(ts, eq):
    d = bt.daily_last(eq, ts)
    return pd.DatetimeIndex(d.index), d.to_numpy(float)


def _corr(ts, eq_a, eq_b):
    _, a = _daily(ts, eq_a)
    _, b = _daily(ts, eq_b)
    ra = np.diff(a) / a[:-1]
    rb = np.diff(b) / b[:-1]
    n = min(len(ra), len(rb))
    return float(np.corrcoef(ra[-n:], rb[-n:])[0, 1])


def _run_many_chunked(ts, o, c, wlist, start, slip, chunk=24):
    out = []
    for i in range(0, len(wlist), chunk):
        out.extend(bt.run_many(ts, o, c, wlist[i:i + chunk], start=start, band=0.02,
                               slippage_bps=slip))
    return out


def _neighbourhood():
    rows = []
    base = dict(DEFAULTS)
    grid = [
        ("carry_vol_look", 5), ("carry_vol_look", 20),
        ("carry_rank_win", 40), ("carry_rank_win", 80),
        ("carry_rank_q", 0.30), ("carry_rank_q", 0.50),
        ("carry_mom_look", 3), ("carry_mom_look", 10),
        ("carry_qqq_weight", 0.50), ("carry_qqq_weight", 1.00),
        ("rev_drop3", -0.04), ("rev_drop3", -0.06),
        ("rev_drop1", -0.025), ("rev_drop1", -0.035),
        ("rev_vol_ratio", 1.3), ("rev_vol_ratio", 1.8),
        ("rev_hold", 2), ("rev_hold", 5),
        ("rev_stop", 0.06), ("rev_stop", 0.10),
        ("rev_cooldown", 1), ("rev_cooldown", 3),
        ("alloc_vol_look", 15), ("alloc_vol_look", 30),
        ("alloc_lo", 0.15), ("alloc_hi", 0.85),
        ("alloc_lo", 0.25), ("alloc_hi", 0.75),
    ]
    for k, v in grid:
        p = dict(base)
        p[k] = v
        rows.append((f"{k}={v}", p))
    return rows


def _placebo(ts, o, c, dates, qc, tc, bc, sma10, on_a, entry_b, p, n_draws=200, seed=7):
    rng = np.random.default_rng(seed)
    n_on = int(on_a.sum())
    n_ev = int(len(np.flatnonzero(entry_b)))
    out = []
    for _ in range(n_draws):
        ron = np.zeros_like(on_a)
        ron[rng.choice(len(on_a), size=n_on, replace=False)] = True
        # random entries spaced by at least hold+cooldown sessions
        step = p["rev_hold"] + p["rev_cooldown"]
        cand = np.arange(0, len(on_a), step)
        pick = rng.choice(cand, size=min(n_ev, len(cand)), replace=False)
        ren = np.zeros_like(entry_b)
        ren[pick] = True
        w, _, _, _, _ = _build_from_signals(qc, tc, bc, dates, ron, ren, sma10, p)
        w1 = to_minutes(pd.DatetimeIndex([pd.Timestamp(d, tz="America/New_York") for d in dates]),
                        w, ts, "1D")
        r = bt.run(ts, o, c, w1, start=DEV_START, band=0.02, slippage_bps=1.0)
        s = bt.stats(r, BPY)
        out.append({"cagr": float(s["cagr"]), "sharpe": float(s["sharpe"]),
                    "max_drawdown": float(s["max_drawdown"])})
    return out


def main():
    ts, o, c = bt.panel(SYMS, DEV_START, DEV_END, "1min")
    dates = session_dates(ts)
    dts = pd.DatetimeIndex([pd.Timestamp(d, tz="America/New_York") for d in dates])

    # daily closes for the correlation benchmark
    qfull = daily_frame("QQQ")
    qfull = qfull[qfull["date"] <= dates[-1]].set_index("date")["close"]
    w_base = baseline_weights(qfull, dates, dts, ts)

    w, info = build_weights(ts, o, c)

    # rebuild the two streams for the report (same signals, no allocation)
    p = dict(DEFAULTS)
    idx = pd.Index(dates)
    q = qfull.reindex(idx).ffill()
    on_a_full, entry_b_full, sma10_full = _signals(qfull, p)
    on_a = pd.Series(on_a_full, index=qfull.index).reindex(idx).fillna(False).to_numpy()
    entry_b = pd.Series(entry_b_full, index=qfull.index).reindex(idx).fillna(False).to_numpy()
    sma10 = pd.Series(sma10_full, index=qfull.index).reindex(idx).ffill().to_numpy()
    t = daily_frame("TQQQ").set_index("date")["close"].reindex(idx).ffill()
    b = daily_frame("BIL").set_index("date")["close"].reindex(idx).ffill()
    _, wA, wB, _, events = _build_from_signals(q, t, b, dates, on_a, entry_b, sma10, p)
    wA1 = to_minutes(dts, wA, ts, "1D")
    wB1 = to_minutes(dts, wB, ts, "1D")

    runs = _run_many_chunked(ts, o, c, [w, wA1, wB1, w_base], DEV_START, 1.0)
    cot = _run_many_chunked(ts, o, c, [w, wA1, wB1], DEV_START, 5.0)
    ten = _run_many_chunked(ts, o, c, [w], DEV_START, 10.0)

    blend, a, bb, base = runs
    n = len(ts)
    w_tq = np.zeros((n, 3)); w_tq[:, 1] = 1.0
    w_q = np.zeros((n, 3)); w_q[:, 0] = 1.0
    bench_runs = _run_many_chunked(ts, o, c, [w_tq, w_q], DEV_START, 1.0)
    tq_stats = _stats(bench_runs[0], ts)
    q_stats = _stats(bench_runs[1], ts)
    spy_path = ROOT / "data" / "round3" / "yahoo" / "SPY-1d-yahoo.parquet"
    spy_stats = None
    if spy_path.exists():
        spy = pd.read_parquet(spy_path)
        spy["date"] = pd.to_datetime(spy["date"]).dt.date
        spy["close"] = spy["close"] * (spy["adjclose"] / spy["close"])
        spy = spy[(spy["date"] >= pd.Timestamp(DEV_START).date())
                  & (spy["date"] <= dates[-1])]
        spy_ts = pd.DatetimeIndex([pd.Timestamp(d, tz="America/New_York") for d in spy["date"]])
        spy_stats = bt.benchmark(spy["close"].to_numpy(), spy_ts, 252)
        spy_stats["marks"] = "daily"
    dev = {
        "1bp": _stats(blend, ts), "5bp": _stats(cot[0], ts), "10bp": _stats(ten[0], ts),
        "stream_A_1bp": _stats(a, ts), "stream_B_1bp": _stats(bb, ts),
        "stream_A_5bp": _stats(cot[1], ts), "stream_B_5bp": _stats(cot[2], ts),
        "baseline_1bp": _stats(base, ts),
    }
    bil_stats = bt.benchmark(b.to_numpy(), dts, 252)
    corr_base = _corr(ts, blend["equity"], base["equity"])
    corr_A = _corr(ts, a["equity"], base["equity"])
    corr_B = _corr(ts, bb["equity"], base["equity"])
    corr_AB = _corr(ts, a["equity"], bb["equity"])

    # sub-periods
    subs = {}
    for name, s0, s1 in (("2016_2019", "2016-01-04", "2019-12-31"),
                         ("2020_2021", "2020-01-02", "2021-12-31"),
                         ("2022_2023", "2022-01-03", "2023-12-29")):
        r = _run_window(ts, o, c, w, s0, s1, 1.0)
        subs[name] = _stats(r, None)

    # neighbourhood
    nh = []
    for label, pv in _neighbourhood():
        wv, _ = build_weights(ts, o, c, **pv)
        rv = bt.run(ts, o, c, wv, start=DEV_START, band=0.02, slippage_bps=1.0)
        sv = bt.stats(rv, BPY)
        nh.append({"variant": label, "cagr": float(sv["cagr"]),
                   "max_drawdown": float(sv["max_drawdown"]),
                   "sharpe": float(sv["sharpe"]),
                   "corr_base": _corr(ts, rv["equity"], base["equity"])})

    # placebo
    plac = _placebo(ts, o, c, dates, q, t, b, sma10, on_a, entry_b, p)
    real_sharpe = dev["1bp"]["sharpe"]
    pct = float(np.mean([x["sharpe"] >= real_sharpe for x in plac]))

    # event study for Stream B: TQQQ return over the 3 sessions after the entry fill
    tc = t.to_numpy()
    fwd = np.full(len(tc), np.nan)
    fwd[:-4] = tc[4:] / tc[1:-3] - 1.0
    ev = [i for i in events if i < len(fwd) and np.isfinite(fwd[i])]
    ev_ret = np.array([fwd[i] for i in ev])
    all_ret = fwd[np.isfinite(fwd)]
    rng = np.random.default_rng(11)
    boot = np.array([rng.choice(ev_ret, size=len(ev_ret), replace=True).mean()
                     for _ in range(10000)]) if len(ev_ret) else np.array([])
    pval = float(np.mean(boot <= 0.0)) if len(boot) else None

    status = "passed"
    reasons = []
    if corr_base >= 0.60:
        status = "rejected"; reasons.append("corr_vs_baseline>=0.60")
    if dev["1bp"]["sharpe"] <= max(dev["stream_A_1bp"]["sharpe"], dev["stream_B_1bp"]["sharpe"]) \
            and dev["1bp"]["max_drawdown"] >= min(dev["stream_A_1bp"]["max_drawdown"],
                                                 dev["stream_B_1bp"]["max_drawdown"]):
        status = "rejected"; reasons.append("blend_adds_nothing")
    if dev["5bp"]["cagr"] <= 0 or dev["5bp"]["max_drawdown"] > 0.40:
        status = "rejected"; reasons.append("fails_5bp")
    if dev["stream_A_5bp"]["cagr"] <= bil_stats["cagr"] or dev["stream_A_1bp"]["sharpe"] <= 0:
        status = "rejected"; reasons.append("carry_stream_not_a_premium")
    if len(ev) < 25 or (pval is not None and pval > 0.10):
        status = "rejected"; reasons.append("reversal_event_study_weak")
    if pct > 0.10:
        status = "rejected"; reasons.append("placebo_beats_real")
    if subs["2022_2023"]["cagr"] < -0.10:
        status = "rejected"; reasons.append("2022_2023_below_-10pct")

    out = {
        "agent": "winner-ensemble-blend",
        "original": "research/agents2/winner-ensemble-blend",
        "status": status,
        "rejection_reasons": reasons,
        "idea": "Inverse-volatility allocation across two independent return streams: calm QQQ carry (1x) and panic-reversal TQQQ (3x).",
        "hypothesis": "The risk-parity blend earns a positive risk-adjusted return with a lower drawdown than either stream and <0.60 daily correlation with the old 165-day TQQQ baseline.",
        "universe": ["QQQ", "TQQQ", "BIL"],
        "frozen_commit": None,
        "variants_tried": 1 + len(nh),
        "corr_vs_165d_baseline": corr_base,
        "max_corr_vs_other_rebuilds": None,
        "windows": {
            "dev": {"1bp": dev["1bp"], "5bp": dev["5bp"], "10bp": dev["10bp"]},
            "holdout": None,
            "10y": None,
            "5y": None,
        },
        "marks": "1m",
        "benchmarks": {
            "tqqq": tq_stats, "qqq": q_stats, "spy": spy_stats, "bil": bil_stats,
            "original": json.loads((ROOT / "research/agents2/winner-ensemble-blend/result.json").read_text())["windows"],
        },
        "streams": {
            "A_calm_carry": {**dev["stream_A_1bp"], "corr_vs_baseline": corr_A,
                              "on_share": info["carry_on_share"]},
            "B_panic_reversal": {**dev["stream_B_1bp"], "corr_vs_baseline": corr_B,
                                  "events": info["reversal_events"],
                                  "exposure_share": info["reversal_exposure_share"]},
            "corr_A_B": corr_AB,
        },
        "sub_periods": subs,
        "neighbourhood_1bp": nh,
        "placebo": {"draws": len(plac), "real_sharpe": real_sharpe,
                     "pct_random_sharpe_ge_real": pct,
                     "random_sharpe_mean": float(np.mean([x["sharpe"] for x in plac])),
                     "random_sharpe_p90": float(np.percentile([x["sharpe"] for x in plac], 90))},
        "event_study": {"events": len(ev), "mean_3d_fwd": float(ev_ret.mean()) if len(ev_ret) else None,
                         "unconditional_mean_3d": float(all_ret.mean()),
                         "bootstrap_p": pval},
        "info": info,
        "notes": [
            "Dev window only (2016-01-04..2023-12-29). Holdout and the official 10y/5y are intentionally null; the lead runs them after freezing.",
            "No 165-day gate, no round-1 stop, no old build_weights.",
            "SPY is a benchmark only: local SPY history is daily and ~0.99 correlated with QQQ; no 2016-2023 1-minute SPY data.",
            "This file was written while backtests were paused; numbers above are produced only when the lead authorises main().",
        ],
    }
    (HERE / "result.json").write_text(json.dumps(out, indent=2, default=float))
    print(json.dumps({k: out[k] for k in ("status", "rejection_reasons",
                                         "corr_vs_165d_baseline", "windows")}, indent=2))


if __name__ == "__main__":
    main()
