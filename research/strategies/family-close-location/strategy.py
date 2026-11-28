"""Close-location value (CLV) - `family-close-location`.

DEVELOPMENT WINDOW ONLY (2016-01-04 .. 2023-12-29).  The 2024-2026 holdout is
never loaded.

Primary signal
--------------
    CLV[d] = 2 * (QQQ_close[d] - QQQ_low[d]) / (QQQ_high[d] - QQQ_low[d]) - 1

where high/low are the maximum/minimum of the 1-minute QQQ closes over
09:30-15:59 ET and close is the 15:59 ET close.  A close at the session low is
CLV = -1; a close at the session high is +1.

Rule: when CLV[d] < -0.80 (close in the bottom tenth of the intraday range),
buy TQQQ at the next session's 09:30 open and hold for 5 sessions.  A new
signal while holding rolls the exit forward to 5 sessions from that signal.
Otherwise hold BIL.  Long-only, no leverage beyond 1.0 TQQQ.

The primary object is CLV, not the opening range and not VWAP.

Run:
    $env:PYTHONPATH = "C:\\Users\\27175\\AppData\\Local\\Temp\\opencode\\pylibs"
    $env:BT_THREADS = "1"
    python research/strategies/family-close-location/strategy.py
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
WARM = 20                      # data warm-up, not a trend filter
OUT = Path(__file__).resolve().parent
SLUG = "family-close-location"

# Pre-registered primary.  The 8-cell grid is fixed in HYPOTHESIS.md.
PARAMS = dict(clv_thr=-0.80, hold=5)

WINNERS = [
    "ratio-froth", "vol-scaled-crash-stop", "relative-value-tqqq",
    "fomc-opex-window", "family-session-timing", "family-short-reversal",
    "family-rebalance-flow", "family-intraday-microstructure-day",
    "family-ml-microstructure",
]


# ---------------------------------------------------------------------------
# daily features (all known at the 15:59 close)
# ---------------------------------------------------------------------------
def daily_features(ts, o, c):
    dates, first, last = bt.day_bounds(ts)
    nd = len(first)
    qc = c[last, 0]
    qo = o[first, 0]
    # high/low of the 1-minute closes inside each session
    qh = np.array([c[first[d]:last[d] + 1, 0].max() for d in range(nd)])
    ql = np.array([c[first[d]:last[d] + 1, 0].min() for d in range(nd)])
    rng = np.maximum(qh - ql, 1e-12)
    clv = 2.0 * (qc - ql) / rng - 1.0
    r1 = np.r_[np.nan, qc[1:] / qc[:-1] - 1.0]
    return dict(dates=dates, sess_dates=dates[first], first=first, last=last,
                nd=nd, qc=qc, qo=qo, qh=qh, ql=ql, clv=clv, r1=r1,
                tq=c[last, 1], tqo=o[first, 1], bil=c[last, 2])


def signal_mask(f, params):
    p = dict(PARAMS)
    if params:
        p.update(params)
    m = f["clv"] < p["clv_thr"]
    m[:WARM] = False
    return m


# ---------------------------------------------------------------------------
# position -> (n,3) weights
# ---------------------------------------------------------------------------
def positions_from_mask(f, mask, params):
    p = dict(PARAMS)
    if params:
        p.update(params)
    nd = f["nd"]
    hold = int(p["hold"])
    pos = np.zeros(nd)
    until = -1
    event_days = []
    for d in range(nd):
        if mask[d]:
            event_days.append(d)
            until = max(until, d + hold)   # rolling exit
        if d < until:
            pos[d] = 1.0
    return pos, event_days


def weights_from_pos(ts, f, pos):
    n = len(ts)
    w = np.zeros((n, 3))
    w[:, 2] = 1.0
    prev = 0.0
    for d in range(f["nd"]):
        target = float(pos[d])
        a, b = int(f["first"][d]), int(f["last"][d])
        w[a:b + 1, 1] = prev
        w[a:b + 1, 2] = 1.0 - prev
        w[b, 1] = target
        w[b, 2] = 1.0 - target
        prev = target
    return w


def build_weights(ts, o, c, params=None):
    p = dict(PARAMS)
    if params:
        p.update(params)
    f = daily_features(ts, o, c)
    mask = signal_mask(f, p)
    pos, event_days = positions_from_mask(f, mask, p)
    w = weights_from_pos(ts, f, pos)
    runs = episodes(f, pos)
    info = dict(
        params=p,
        signal_days=int(mask.sum()),
        events=int(len(event_days)),
        event_days=[str(f["dates"][f["first"][d]]) for d in event_days],
        open_at_end=bool(pos[-1] > 0),
        tqqq_exposure=float(np.mean(w[:, 1])),
        episodes=len(runs),
        episode_stats=episode_stats(runs),
        event_forward=forward_event_stats(f, event_days, p["hold"]),
    )
    return w, info


def episodes(f, pos):
    """Contiguous active runs -> (entry_day, exit_day, entry_px, exit_px).

    pos[d] is the target written at the close of day d and filled at the
    next open.  A run starting at s therefore enters at tqo[s+1] and exits
    at tqo[e+1].
    """
    runs = []
    d = 0
    nd = f["nd"]
    while d < nd:
        if pos[d] <= 0:
            d += 1
            continue
        s = d
        while d < nd and pos[d] > 0:
            d += 1
        e = d - 1
        en = s + 1
        ex = min(e + 2, nd - 1)
        if en >= nd:
            continue
        runs.append((s, e, float(f["tqo"][en]), float(f["tqo"][ex])))
    return runs


def forward_event_stats(f, event_days, hold):
    rs = []
    nd = f["nd"]
    for d in event_days:
        en = d + 1
        ex = min(d + 1 + int(hold), nd - 1)
        if en >= nd:
            continue
        rs.append(float(f["tqo"][ex] / f["tqo"][en] - 1.0))
    rs = np.asarray(rs, dtype=float)
    if len(rs) < 3:
        return {"n": int(len(rs))}
    t = float(rs.mean() / rs.std(ddof=1) * np.sqrt(len(rs))) if rs.std(ddof=1) > 0 else None
    rng = np.random.default_rng(7)
    boot = rng.choice(rs, (10000, len(rs)), replace=True).mean(axis=1)
    return {
        "n": int(len(rs)),
        "mean": float(rs.mean()),
        "median": float(np.median(rs)),
        "win": float((rs > 0).mean()),
        "t": t,
        "bootstrap_p": float((boot <= 0).mean()),
        "ci95_low": float(np.quantile(boot, 0.025)),
        "ci95_high": float(np.quantile(boot, 0.975)),
        "worst": float(rs.min()),
        "best": float(rs.max()),
    }


def episode_stats(runs):
    rs = np.array([b / a - 1.0 for _, _, a, b in runs if a > 0 and b > 0])
    if len(rs) < 3:
        return {"n": int(len(rs))}
    t = float(rs.mean() / rs.std(ddof=1) * np.sqrt(len(rs))) if rs.std(ddof=1) > 0 else None
    rng = np.random.default_rng(7)
    boot = rng.choice(rs, (10000, len(rs)), replace=True).mean(axis=1)
    return {
        "n": int(len(rs)),
        "mean": float(rs.mean()),
        "median": float(np.median(rs)),
        "win": float((rs > 0).mean()),
        "t": t,
        "bootstrap_p": float((boot <= 0).mean()),
        "ci95_low": float(np.quantile(boot, 0.025)),
        "ci95_high": float(np.quantile(boot, 0.975)),
        "worst": float(rs.min()),
        "best": float(rs.max()),
    }


# ---------------------------------------------------------------------------
# evaluation
# ---------------------------------------------------------------------------
def _slice(f, pos, start, end):
    i = bt.start_index(TS, start)
    j = int(TS.searchsorted(pd.Timestamp(end, tz="America/New_York"), side="right"))
    return i, j


def metrics(pos, slip=1.0, start=DEV_START, end=DEV_END, w=None):
    if w is None:
        w = weights_from_pos(TS, F, pos)
    if start == DEV_START and end == DEV_END:
        r = bt.run(TS, O, C, w, start, band=0.02, slippage_bps=slip)
        s = bt.stats(r, BARS_PER_YEAR)
        ww = w
    else:
        i, j = _slice(F, pos, start, end)
        r = bt.simulate(TS[i:j], O[i:j], C[i:j], w[i:j], band=0.02,
                        slippage_bps=slip)
        s = bt.stats(r, BARS_PER_YEAR)
        ww = w[i:j]
    return {
        "cagr": s["cagr"], "max_drawdown": s["max_drawdown"],
        "sharpe": s["sharpe"], "sortino": s["sortino"],
        "volatility": s["volatility"], "fills": s["fills"],
        "turnover": s["turnover"], "ending_equity": s["ending_equity"],
        "tqqq_exposure": float(np.mean(ww[:, 1])),
    }


def daily_returns(pos, slip=1.0):
    r = bt.run(TS, O, C, weights_from_pos(TS, F, pos), DEV_START,
               band=0.02, slippage_bps=slip)
    eq = pd.Series(r["equity"], index=r["ts"])
    return eq.groupby(eq.index.date).last().pct_change().dropna()


def load_winner_returns(slug):
    """Dev-only segment of a stored winner curve.

    The curve JSON runs to 2026.  Every entry after 2023-12-29 is dropped
    before any value is converted or inspected; only the development segment
    is used.
    """
    path = ROOT / "research" / "new" / "curves" / f"{slug}.json"
    d = json.loads(path.read_text())
    dates = pd.to_datetime(d["dates"])
    keep = dates <= pd.Timestamp(DEV_END)
    vals = np.asarray(d["values"], dtype=float)[keep]
    dates = dates[keep]
    return pd.Series(vals, index=dates).pct_change().dropna()


def correlations(pos):
    sr = daily_returns(pos)
    sr.index = pd.to_datetime(sr.index)
    out = {}
    for slug in WINNERS:
        wr = load_winner_returns(slug)
        j = sr.index.intersection(wr.index)
        out[slug] = float(np.corrcoef(sr.loc[j], wr.loc[j])[0, 1])
    tq = pd.Series(F["tq"], index=pd.to_datetime(F["sess_dates"]))
    tr = tq.pct_change().dropna()
    j = sr.index.intersection(tr.index)
    out["TQQQ"] = float(np.corrcoef(sr.loc[j], tr.loc[j])[0, 1])
    return out


def placebo(pos, mask, params, n_draw=100, seed=11):
    rng = np.random.default_rng(seed)
    real = metrics(pos)["cagr"]
    seg = pos[WARM:].copy()
    shifts, cagrs = [], []
    for _ in range(n_draw):
        sh = int(rng.integers(20, len(seg) - 20))
        q = np.r_[np.zeros(WARM), np.roll(seg, sh)]
        m = metrics(q)
        shifts.append(m["cagr"])
        cagrs.append(m["cagr"])

    # random event days: same count, same hold rule, timing destroyed
    pool = np.arange(WARM, F["nd"] - 1)
    n_ev = int(mask.sum())
    rand_cagrs, rand_exps = [], []
    for _ in range(n_draw):
        pick = rng.choice(pool, n_ev, replace=False)
        mm = np.zeros(F["nd"], dtype=bool)
        mm[pick] = True
        q, _ = positions_from_mask(F, mm, params)
        m = metrics(q)
        rand_cagrs.append(m["cagr"])
        rand_exps.append(m["tqqq_exposure"])

    def summ(v):
        a = np.asarray(v)
        return {"n_draws": int(len(a)), "mean_cagr": float(a.mean()),
                "std_cagr": float(a.std(ddof=1)),
                "p95_cagr": float(np.quantile(a, 0.95)),
                "max_cagr": float(a.max()),
                "p_value": float((a >= real).mean())}

    s = summ(shifts)
    s["note"] = "circular shift of the daily target vector; preserves exposure, event count and clustering."
    r = summ(rand_cagrs)
    r["mean_exposure"] = float(np.mean(rand_exps))
    r["note"] = "same number of event days drawn uniformly; destroys timing and clustering."
    return {"real_cagr": real, "signal_days": n_ev, "shift": s,
            "random_entry": r}


def precut_check():
    cut = bt.start_index(TS, "2020-03-12")
    w_cut, _ = build_weights(TS[:cut], O[:cut], C[:cut])
    w_full = weights_from_pos(TS, F, F["pos"]) if "pos" in F else None
    if w_full is None:
        return {"error": "no full weights"}
    pre = min(len(w_cut), cut)
    return {"cut": "2020-03-12 11:07 America/New_York",
            "bars_compared": int(pre),
            "max_abs_weight_diff": float(np.max(np.abs(
                w_cut[:pre, 1] - w_full[:pre, 1])))}


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
TS = O = C = F = None


def main():
    global TS, O, C, F
    TS, O, C = bt.panel(("QQQ", "TQQQ", "BIL"), DEV_START, DEV_END, "1min")
    F = daily_features(TS, O, C)

    mask = signal_mask(F, PARAMS)
    pos, event_days = positions_from_mask(F, mask, PARAMS)
    F["pos"] = pos
    w = weights_from_pos(TS, F, pos)
    info = {
        "params": PARAMS,
        "signal_days": int(mask.sum()),
        "events": int(len(event_days)),
        "tqqq_exposure": float(np.mean(w[:, 1])),
        "episodes": len(episodes(F, pos)),
        "episode_stats": episode_stats(episodes(F, pos)),
        "event_forward": forward_event_stats(F, event_days, PARAMS["hold"]),
    }

    out = {
        "agent": SLUG,
        "family": "close location value",
        "idea": "A close pinned at the session low marks forced selling / "
                "inventory imbalance; the next sessions mean-revert. TQQQ is "
                "the long instrument and BIL is the flat asset.",
        "hypothesis": "QQQ closes in the bottom tenth of its intraday range "
                      "are followed by positive next-open TQQQ returns over "
                      "the next five sessions.",
        "universe": ["QQQ", "TQQQ", "BIL"],
        "window": {"dev": [DEV_START, DEV_END], "holdout": "not loaded"},
        "execution": {
            "engine": "research/bt.py", "marks": "1min",
            "fills": "next open", "band": 0.02,
            "headline_bps": 1.0, "also_bps": [5.0, 10.0],
            "weight_cap": 1.0, "long_only": True,
            "exposure_state": "TQQQ 1.0 while the CLV event is on, BIL 1.0 otherwise",
        },
        "params": PARAMS,
        "info": info,
        "windows": {"dev": {}},
        "benchmarks": {},
        "yearly": {},
        "grid": [],
        "cuts": {},
        "placebo": {},
        "corr_winners": {},
        "corr_tqqq": None,
        "precut": {},
        "kill_criteria": [
            "dev 1 bp CAGR <= 36.72% or dev max drawdown >= 82.29%",
            "fewer than 5 of the 8 pre-registered grid cells clear the same bar",
            "10 bp CAGR <= 36.72%",
            "shift-placebo p > 0.05",
            "random-entry placebo p > 0.05",
            "ex-2020 CAGR <= 20%",
            "daily-return correlation to family-short-reversal > 0.85",
            "fewer than 100 fills or fewer than 30 independent events",
            "pre-cut max weight difference > 1e-12",
            "event-forward 5-session t <= 1.5 (CLV reversal absent at the event level)",
        ],
        "status": None,
    }

    for slip, lab in ((1.0, "1bp"), (5.0, "5bp"), (10.0, "10bp")):
        out["windows"]["dev"][lab] = metrics(pos, slip, w=w)
        if slip == 1.0:
            r1 = bt.run(TS, O, C, w, DEV_START, band=0.02, slippage_bps=1.0)

    out["benchmarks"]["tqqq"] = bt.benchmark(C[:, 1], TS, BARS_PER_YEAR)
    out["benchmarks"]["qqq"] = bt.benchmark(C[:, 0], TS, BARS_PER_YEAR)
    out["benchmarks"]["tqqq"]["note"] = (
        "1-minute marks; the task bar is 36.72% / 82.29% / 0.82 on daily closes.")

    out["yearly"] = {int(k): v for k, v in
                     bt.yearly(TS, r1["equity"], C[:, 1]).items()}

    cells = [
        ("1 clv -0.60 h5", dict(clv_thr=-0.60, hold=5)),
        ("2 clv -0.70 h5", dict(clv_thr=-0.70, hold=5)),
        ("3 primary clv -0.80 h5", dict(clv_thr=-0.80, hold=5)),
        ("4 clv -0.90 h5", dict(clv_thr=-0.90, hold=5)),
        ("5 clv -0.80 h3", dict(clv_thr=-0.80, hold=3)),
        ("6 clv -0.80 h4", dict(clv_thr=-0.80, hold=4)),
        ("7 clv -0.80 h6", dict(clv_thr=-0.80, hold=6)),
        ("8 clv -0.80 h8", dict(clv_thr=-0.80, hold=8)),
    ]
    for name, pp in cells:
        p = dict(PARAMS); p.update(pp)
        mm = signal_mask(F, p)
        q, _ = positions_from_mask(F, mm, p)
        m = metrics(q)
        out["grid"].append({"name": name, "params": pp, **m})

    for name, a, b in (("2016-2019", "2016-01-04", "2019-12-31"),
                       ("2020-2021", "2020-01-02", "2021-12-31"),
                       ("2022-2023", "2022-01-03", "2023-12-29")):
        out["cuts"][name] = metrics(pos, 1.0, a, b, w)
    for y in (2020, 2022):
        years = pd.Series(pd.to_datetime(list(F["dates"][F["first"]]))).dt.year.to_numpy()
        mm = mask & (years != y)
        q, _ = positions_from_mask(F, mm, PARAMS)
        out["cuts"][f"ex{y}"] = metrics(q)

    out["placebo"] = placebo(pos, mask, PARAMS)
    out["corr_winners"] = correlations(pos)
    out["corr_tqqq"] = out["corr_winners"]["TQQQ"]
    out["precut"] = precut_check()

    dev = out["windows"]["dev"]["1bp"]
    n_grid = sum(1 for g in out["grid"]
                 if g["cagr"] > 0.3672 and g["max_drawdown"] < 0.8229)
    passes = (dev["cagr"] > 0.3672 and dev["max_drawdown"] < 0.8229
              and n_grid >= 5 and out["placebo"]["shift"]["p_value"] <= 0.05)
    out["status"] = ("dev_pass" if passes and out["windows"]["dev"]["10bp"]["cagr"] > 0.3672
                     else "dev_pass_marginal" if passes else "dev_fail")
    out["grid_cells_above_bar"] = int(n_grid)

    (OUT / "result.json").write_text(json.dumps(out, indent=2, default=float))
    print(json.dumps({
        "status": out["status"],
        "primary": {k: out["windows"]["dev"][k] for k in ("1bp", "5bp", "10bp")},
        "grid_cells_above_bar": n_grid,
        "corr_tqqq": out["corr_tqqq"],
        "corr_range": [min(out["corr_winners"][s] for s in WINNERS),
                       max(out["corr_winners"][s] for s in WINNERS)],
        "placebo": out["placebo"],
        "precut": out["precut"],
    }, indent=2, default=float))
    print("wrote", OUT / "result.json")


if __name__ == "__main__":
    main()
