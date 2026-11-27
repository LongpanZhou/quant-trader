"""Multi-horizon quiet capitulation reversal — `capitulation-reversal-v2`.

DEVELOPMENT WINDOW ONLY (2016-01-04 .. 2023-12-29).  The 2024-2026 holdout is
never loaded.

Idea
----
A multi-session QQQ decline on *below-average* volume is a positioning / air
pocket, not an information event.  The reversal is realised in the next
session's close-to-close return, including the overnight gap, so the trade is
entered at the event-day close (15:59) and held for one session.

Event at 15:58 ET on session d:
    q3   = QQQ_close_1558[d] / QQQ_close_1558[d-3]  - 1
    q10  = QQQ_close_1558[d] / QQQ_close_1558[d-10] - 1
    q15  = QQQ_close_1558[d] / QQQ_close_1558[d-15] - 1
    rvol = volume_1558[d] / mean(volume_1558[d-20 .. d-1])
    event = (q3 <= -3.0% OR q10 <= -5.0% OR q15 <= -8.0%) AND rvol <= 1.2

Entry: TQQQ at the 15:59 open of the event day, size = clip(0.80/vol20, 0.25, 1).
Exit:  at the 15:59 open of the next session.  If that session is also an
event, the new entry chains and the position stays on for another session.

No 100-250 day moving average is used by the strategy.  The 165-day baseline is
computed only for the correlation/benchmark table.  No old weight matrix or
old `build_weights` is imported.

Run:
    $env:PYTHONPATH = "C:\\Users\\27175\\AppData\\Local\\Temp\\opencode\\pylibs"
    python research/new/capitulation-reversal-v2/strategy.py
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

DEV_START, DEV_END = "2016-01-04", "2023-12-29"
BARS_PER_YEAR = 252 * 390
OUT = Path(__file__).resolve().parent

# Pre-registered primary.  The grid in HYPOTHESIS.md varies q3 / rvol_max.
PARAMS = dict(
    q3=-0.030,
    q10=-0.050,
    q15=-0.080,
    rvol_max=1.20,
    hold=1,
    vol_target=0.80,
    size_floor=0.25,
)


# ---------------------------------------------------------------------------
# daily features (all known at 15:58)
# ---------------------------------------------------------------------------
def daily_volume_1558(ts: pd.DatetimeIndex) -> np.ndarray:
    """QQQ volume through 15:58, one value per session of `ts`."""
    q = bt.load_1m("QQQ")
    lo = pd.Timestamp(ts[0].date(), tz="America/New_York")
    hi = pd.Timestamp(ts[-1].date(), tz="America/New_York") + pd.Timedelta(days=1)
    q = q[(q["ts"] >= lo) & (q["ts"] < hi)].copy()
    q = q[q["ts"].dt.time < pd.Timestamp("15:59").time()]
    q["date"] = q["date"].astype("datetime64[ns]")
    sess = pd.DatetimeIndex(sorted(set(pd.Timestamp(t.date()) for t in ts)))
    return q.groupby("date")["volume"].sum().reindex(sess).to_numpy()


def daily_features(ts, o, c):
    """Return the daily signal frame aligned to `ts`'s sessions."""
    dates, first, last = bt.day_bounds(ts)
    nd = len(first)
    qc = c[last - 1, 0]                       # QQQ 15:58 close
    qret = np.r_[np.nan, qc[1:] / qc[:-1] - 1.0]
    q3 = pd.Series(qc).pct_change(3).to_numpy()
    q10 = pd.Series(qc).pct_change(10).to_numpy()
    q15 = pd.Series(qc).pct_change(15).to_numpy()
    vol20 = pd.Series(qret).rolling(20).std(ddof=0).to_numpy() * np.sqrt(252.0)
    qvol = daily_volume_1558(ts)
    rvol = qvol / pd.Series(qvol).shift(1).rolling(20).mean().to_numpy()
    return dict(dates=dates, first=first, last=last, nd=nd,
                q3=q3, q10=q10, q15=q15, vol20=vol20, rvol=rvol, qvol=qvol)


def event_mask(f: dict, p: dict) -> np.ndarray:
    """Pre-registered event mask.  None disables a leg (grid only)."""
    nd = f["nd"]
    ev = np.zeros(nd, dtype=bool)
    if p.get("q3") is not None:
        ev |= f["q3"] <= p["q3"]
    if p.get("q10") is not None:
        ev |= f["q10"] <= p["q10"]
    if p.get("q15") is not None:
        ev |= f["q15"] <= p["q15"]
    finite = (np.isfinite(f["rvol"]) & np.isfinite(f["vol20"]))
    return ev & (f["rvol"] <= p["rvol_max"]) & finite


# ---------------------------------------------------------------------------
# weights
# ---------------------------------------------------------------------------
def _size(f: dict, d: int, p: dict) -> float:
    return float(np.clip(p["vol_target"] / max(f["vol20"][d], 0.01),
                         p["size_floor"], 1.0))


def _weights_from_mask(ts, o, c, f: dict, mask: np.ndarray, p: dict):
    """Build the (n, 3) weight matrix for an arbitrary event mask."""
    n = len(ts)
    nd, first, last = f["nd"], f["first"], f["last"]
    hold = int(p["hold"])
    w = np.zeros((n, 3))
    w[:, 2] = 1.0                              # BIL by default
    for d in range(25, nd - hold):
        if not mask[d]:
            continue
        sz = _size(f, d, p)
        le = int(last[d])
        # Entry: target on the 15:58 bar -> fill at the 15:59 open.
        w[le - 1, 1] = sz
        w[le - 1, 2] = 1.0 - sz
        # Hold through the next `hold` sessions.
        for s in range(d + 1, d + hold + 1):
            fs, ls = int(first[s]), int(last[s])
            w[fs:ls, 1] = sz
            w[fs:ls, 2] = 1.0 - sz
        # Exit: target 0 on the 15:58 bar of the last held session.
        le2 = int(last[d + hold])
        w[le2 - 1, 1] = 0.0
        w[le2 - 1, 2] = 1.0
    return w


def build_weights(ts, o, c, params=None):
    """Return (weights (n,3), info).  See HYPOTHESIS.md for the exact rules."""
    p = dict(PARAMS)
    if params:
        p.update(params)
    f = daily_features(ts, o, c)
    mask = event_mask(f, p)
    w = _weights_from_mask(ts, o, c, f, mask, p)
    event_dates = [str(f["dates"][f["last"][d]]) for d in range(25, f["nd"] - p["hold"])
                   if mask[d]]
    sizes = [_size(f, d, p) for d in range(25, f["nd"] - p["hold"]) if mask[d]]
    info = dict(
        params=p,
        n_events=int(mask.sum()),
        event_dates=event_dates,
        exposure=float(np.mean(w[:, 1])),
        mean_size=float(np.mean(sizes)) if sizes else None,
        min_size=float(np.min(sizes)) if sizes else None,
    )
    return w, info


# ---------------------------------------------------------------------------
# benchmark only (not part of the strategy)
# ---------------------------------------------------------------------------
def benchmark_weights(ts, c, n=165):
    """165-day QQQ SMA baseline, used ONLY for the correlation/benchmark."""
    dates = bt.session_dates(ts)
    first = np.flatnonzero(np.r_[True, dates[1:] != dates[:-1]])
    last = np.r_[first[1:] - 1, len(ts) - 1]
    qc = c[last, 0]
    sma = pd.Series(qc).rolling(n).mean().to_numpy()
    reg = np.zeros(len(first), bool)
    reg[1:] = qc[:-1] > sma[:-1]
    day_id = np.repeat(np.arange(len(first)), np.diff(np.r_[first, len(ts)]))
    w = np.zeros((len(ts), 3))
    w[:, 1] = reg[day_id].astype(float)
    w[:, 2] = 1.0 - w[:, 1]
    return w


def daily_returns(result):
    eq = pd.Series(result["equity"], index=result["ts"])
    return eq.groupby(eq.index.date).last().pct_change().dropna()


# ---------------------------------------------------------------------------
# evaluation helpers
# ---------------------------------------------------------------------------
def _metrics(w, slip=1.0, start=DEV_START, end=DEV_END):
    if start == DEV_START and end == DEV_END:
        # The development panel already ends at DEV_END; using bt.run keeps
        # the last session, so yearly() sees the same index as the equity.
        r = bt.run(ts_global, o_global, c_global, w, start,
                   band=0.02, slippage_bps=slip)
        s = bt.stats(r, BARS_PER_YEAR)
        s["tqqq_exposure"] = float(np.mean(w[:, 1]))
        return r, s
    i = bt.start_index(ts_global, start)
    j = int(ts_global.searchsorted(pd.Timestamp(end, tz="America/New_York"), side="right"))
    r = bt.simulate(ts_global[i:j], o_global[i:j], c_global[i:j], w[i:j],
                    band=0.02, slippage_bps=slip)
    s = bt.stats(r, BARS_PER_YEAR)
    s["tqqq_exposure"] = float(np.mean(w[i:j, 1]))
    return r, s


def _event_stats(f, mask, hold=1):
    Rs = []
    for d in range(25, f["nd"] - hold):
        if not mask[d]:
            continue
        entry = o_global[f["last"][d], 1]       # 15:59 open of event day
        exit_ = o_global[f["last"][d + hold], 1]  # 15:59 open of exit day
        Rs.append(float(exit_ / entry - 1.0))
    Rs = np.asarray(Rs)
    if len(Rs) < 3:
        return {"n": int(len(Rs))}
    t = float(Rs.mean() / Rs.std(ddof=1) * np.sqrt(len(Rs))) if Rs.std(ddof=1) > 0 else None
    rng = np.random.default_rng(7)
    boot = rng.choice(Rs, (10000, len(Rs)), replace=True).mean(axis=1)
    return {
        "n": int(len(Rs)),
        "mean": float(Rs.mean()),
        "median": float(np.median(Rs)),
        "win": float((Rs > 0).mean()),
        "t": t,
        "bootstrap_p": float((boot <= 0).mean()),
        "ci95_low": float(np.quantile(boot, 0.025)),
        "ci95_high": float(np.quantile(boot, 0.975)),
        "worst": float(Rs.min()),
        "best": float(Rs.max()),
    }


def _placebo(f, n_events, n_draws=200, seed=11):
    rng = np.random.default_rng(seed)
    all_days = np.arange(25, f["nd"] - 1)
    cagrs = []
    for _ in range(n_draws):
        pick = rng.choice(all_days, n_events, replace=False)
        m = np.zeros(f["nd"], bool)
        m[pick] = True
        w = _weights_from_mask(ts_global, o_global, c_global, f, m, PARAMS)
        _, s = _metrics(w, 1.0)
        cagrs.append(s["cagr"])
    cagrs = np.asarray(cagrs)
    return {
        "n_draws": int(n_draws),
        "mean": float(cagrs.mean()),
        "std": float(cagrs.std(ddof=1)),
        "p95": float(np.quantile(cagrs, 0.95)),
        "max": float(cagrs.max()),
        "p_value": float((cagrs >= _metrics(build_weights(ts_global, o_global, c_global)[0], 1.0)[1]["cagr"]).mean()),
    }


def _cut(w, start, end, slip=1.0):
    return _metrics(w, slip, start, end)[1]


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
ts_global = o_global = c_global = None


def main():
    global ts_global, o_global, c_global
    ts_global, o_global, c_global = bt.panel(
        ("QQQ", "TQQQ", "BIL"), DEV_START, DEV_END, "1min")
    ts, o, c = ts_global, o_global, c_global

    w, info = build_weights(ts, o, c)
    f = daily_features(ts, o, c)
    mask = event_mask(f, PARAMS)

    out = {
        "agent": "capitulation-reversal-v2",
        "idea": "A multi-session QQQ decline on below-average volume is a "
                "positioning event, not news; it reverses in the next session's "
                "close-to-close return, so buy TQQQ at the event close and hold "
                "one session.",
        "hypothesis": "QQQ -3% over 3 sessions, -5% over 10, or -8% over 15, on "
                      "volume <= 1.2x the prior 20-day average, is followed by a "
                      "positive next-session TQQQ return large enough to beat "
                      "TQQQ's 36.72% development CAGR with a lower drawdown.",
        "universe": ["QQQ", "TQQQ", "BIL"],
        "window": {"dev": [DEV_START, DEV_END], "holdout": "not loaded"},
        "params": PARAMS,
        "info": info,
        "windows": {"dev": {}},
        "benchmarks": {},
        "event_study": _event_stats(f, mask),
        "event_study_by_year": {},
        "grid": [],
        "cuts": {},
        "yearly": {},
        "corr_tqqq": None,
        "corr_165d": None,
    }

    r1 = None
    for slip, lab in ((1.0, "1bp"), (5.0, "5bp"), (10.0, "10bp")):
        r, s = _metrics(w, slip)
        out["windows"]["dev"][lab] = {
            "cagr": s["cagr"], "max_drawdown": s["max_drawdown"],
            "sharpe": s["sharpe"], "sortino": s["sortino"],
            "volatility": s["volatility"], "fills": s["fills"],
            "turnover": s["turnover"], "ending_equity": s["ending_equity"],
            "tqqq_exposure": s["tqqq_exposure"],
        }
        if slip == 1.0:
            r1 = r

    # yearly and correlations
    y = bt.yearly(ts, r1["equity"], c[:, 1])
    out["yearly"] = {int(k): {"strategy": v["strategy"], "benchmark": v["benchmark"]}
                     for k, v in y.items()}
    sr = daily_returns(r1)
    tr = pd.Series(c[:, 1], index=ts)
    tr = tr.groupby(tr.index.date).last().pct_change().dropna()
    j = sr.index.intersection(tr.index)
    out["corr_tqqq"] = float(np.corrcoef(sr.loc[j], tr.loc[j])[0, 1])

    bw = benchmark_weights(ts, c)
    rb, sb = _metrics(bw, 1.0)
    br = daily_returns(rb)
    j2 = sr.index.intersection(br.index)
    out["corr_165d"] = float(np.corrcoef(sr.loc[j2], br.loc[j2])[0, 1])

    out["benchmarks"]["tqqq"] = bt.benchmark(c[:, 1], ts, BARS_PER_YEAR)
    out["benchmarks"]["qqq"] = bt.benchmark(c[:, 0], ts, BARS_PER_YEAR)
    out["benchmarks"]["baseline_165d"] = {
        "cagr": sb["cagr"], "max_drawdown": sb["max_drawdown"],
        "sharpe": sb["sharpe"], "volatility": sb["volatility"],
    }

    # event study by year
    years = {}
    for d in range(25, f["nd"] - 1):
        if not mask[d]:
            continue
        yr = int(pd.Timestamp(f["dates"][f["last"][d]]).year)
        yrs = years.setdefault(yr, [])
        yrs.append(float(o_global[f["last"][d + 1], 1] /
                         o_global[f["last"][d], 1] - 1.0))
    out["event_study_by_year"] = {
        int(yr): {"n": len(v), "mean": float(np.mean(v)),
                  "win": float((np.asarray(v) > 0).mean())}
        for yr, v in sorted(years.items())
    }

    # pre-registered grid
    grid = [
        ("1 core q10", dict(q3=None, q10=-0.05, q15=None, rvol_max=1.20, hold=1)),
        ("2 core q15", dict(q3=None, q10=None, q15=-0.08, rvol_max=1.20, hold=1)),
        ("3 core union", dict(q3=None, q10=-0.05, q15=-0.08, rvol_max=1.20, hold=1)),
        ("4 primary", dict(q3=-0.03, q10=-0.05, q15=-0.08, rvol_max=1.20, hold=1)),
        ("5 q3 -2.5%", dict(q3=-0.025, q10=-0.05, q15=-0.08, rvol_max=1.20, hold=1)),
        ("6 q3 -3.5%", dict(q3=-0.035, q10=-0.05, q15=-0.08, rvol_max=1.20, hold=1)),
        ("7 rvol 1.15", dict(q3=-0.03, q10=-0.05, q15=-0.08, rvol_max=1.15, hold=1)),
        ("8 rvol 1.25", dict(q3=-0.03, q10=-0.05, q15=-0.08, rvol_max=1.25, hold=1)),
    ]
    for name, pp in grid:
        p = dict(PARAMS); p.update(pp)
        m = event_mask(f, p)
        wg = _weights_from_mask(ts, o, c, f, m, p)
        _, sg = _metrics(wg, 1.0)
        out["grid"].append({
            "name": name, "params": {k: v for k, v in p.items() if k in
                                     ("q3", "q10", "q15", "rvol_max", "hold")},
            "n_events": int(m.sum()), "exposure": float(np.mean(wg[:, 1])),
            "cagr": sg["cagr"], "max_drawdown": sg["max_drawdown"],
            "sharpe": sg["sharpe"],
        })

    # cuts
    for name, st, en in (("2016-2019", "2016-01-04", "2019-12-31"),
                         ("2020-2021", "2020-01-02", "2021-12-31"),
                         ("2022-2023", "2022-01-03", "2023-12-29")):
        s = _cut(w, st, en)
        out["cuts"][name] = {k: s[k] for k in
                             ("cagr", "max_drawdown", "sharpe", "volatility")}
    for yr in (2020, 2022):
        m2 = mask.copy()
        for d in range(f["nd"]):
            if int(pd.Timestamp(f["dates"][f["last"][d]]).year) == yr:
                m2[d] = False
        w2 = _weights_from_mask(ts, o, c, f, m2, PARAMS)
        _, s2 = _metrics(w2, 1.0)
        out["cuts"][f"ex{yr}"] = {k: s2[k] for k in
                                  ("cagr", "max_drawdown", "sharpe", "volatility")}

    # placebo backtest (200 random event sets)
    out["placebo"] = _placebo(f, int(mask.sum()), n_draws=200)

    dev = out["windows"]["dev"]["1bp"]
    out["status"] = ("1bp_pass_marginal"
                     if dev["cagr"] > 0.3672 and dev["max_drawdown"] < 0.8229
                     else "risk_adjusted_only")

    (OUT / "result.json").write_text(json.dumps(out, indent=2, default=float))
    print(json.dumps({k: out[k] for k in ("status", "corr_tqqq", "corr_165d",
                                          "windows", "event_study")}, indent=2))
    print("wrote", OUT / "result.json")


if __name__ == "__main__":
    main()
