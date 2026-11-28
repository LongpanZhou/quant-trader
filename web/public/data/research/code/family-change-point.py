"""Two-sided CUSUM change-point - `family-change-point`.

DEVELOPMENT WINDOW ONLY (2016-01-04 .. 2023-12-29).  The 2024-2026 holdout is
never loaded.

Primary object
--------------
A Page CUSUM on the sign of QQQ daily returns:

    x[d]    = +1 if QQQ close[d] > close[d-1], -1 if lower, 0 if unchanged
    S+[d]   = max(0, S+[d-1] + x[d] - k)
    S-[d]   = max(0, S-[d-1] - x[d] - k)

A break is declared when S+ > h (up-break) or S- > h (down-break); the
triggered statistic resets to zero.  k = 0.00 and h = 3.0 in the primary, so
the statistic is the running excess of up days over down days (and its
mirror).  It is a bounded change-point statistic for the up/down balance and
does not need a volatility estimate.

Rule (the break is known at the 15:59 close of d; fills at the next open):
    up-break   -> TQQQ 1.0 for the next 20 sessions
    down-break -> BIL 1.0 for the next 20 sessions
    a new break while a window is active replaces the direction and restarts
    the 20-session clock.

The primary object is the break statistic, not a moving average.  The 20-day
window is a fixed holding period, not a trend gate.

Run:
    $env:PYTHONPATH = "C:\\Users\\27175\\AppData\\Local\\Temp\\opencode\\pylibs"
    $env:BT_THREADS = "1"
    python research/new/family-change-point/strategy.py
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
WARM = 20
OUT = Path(__file__).resolve().parent
SLUG = "family-change-point"

PARAMS = dict(k=0.00, h=3.0, hold=20, increment="sign")

WINNERS = [
    "ratio-froth", "vol-scaled-crash-stop", "relative-value-tqqq",
    "fomc-opex-window", "family-session-timing", "family-short-reversal",
    "family-rebalance-flow", "family-intraday-microstructure-day",
    "family-ml-microstructure",
]


# ---------------------------------------------------------------------------
# daily features
# ---------------------------------------------------------------------------
def daily_features(ts, o, c):
    dates, first, last = bt.day_bounds(ts)
    nd = len(first)
    qc = c[last, 0]
    r1 = np.r_[np.nan, qc[1:] / qc[:-1] - 1.0]
    sd = pd.Series(r1).rolling(20).std(ddof=0).to_numpy()
    return dict(dates=dates, sess_dates=dates[first], first=first, last=last,
                nd=nd, qc=qc, r1=r1, sigma20=sd,
                tq=c[last, 1], tqo=o[first, 1], bil=c[last, 2])


# ---------------------------------------------------------------------------
# CUSUM state
# ---------------------------------------------------------------------------
def cusum_state(f, params):
    p = dict(PARAMS)
    if params:
        p.update(params)
    k = float(p["k"]); h = float(p["h"]); hold = int(p["hold"])
    # Sign CUSUM: unit increments +1 on an up day, -1 on a down day.  This is
    # a change-point statistic for the up/down balance; it is bounded and does
    # not need a volatility estimate.
    inc = np.sign(f["r1"])
    inc[~np.isfinite(inc)] = 0.0
    nd = f["nd"]
    pos = np.zeros(nd)
    su = sd = 0.0
    long_until = -1
    flat_until = -1
    up_breaks, dn_breaks = [], []
    for d in range(WARM, nd):
        if d > WARM:
            su = max(0.0, su + inc[d] - k)
            sd = max(0.0, sd - inc[d] - k)
        if su > h:
            up_breaks.append(d)
            su = 0.0
            long_until = max(long_until, d + hold)
            flat_until = -1
        elif sd > h:
            dn_breaks.append(d)
            sd = 0.0
            flat_until = max(flat_until, d + hold)
            long_until = -1
        if d < long_until and d >= flat_until:
            pos[d] = 1.0
    return pos, up_breaks, dn_breaks


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


def episodes(f, pos):
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


def episode_stats(runs):
    rs = np.array([b / a - 1.0 for _, _, a, b in runs if a > 0 and b > 0])
    if len(rs) < 3:
        return {"n": int(len(rs))}
    t = float(rs.mean() / rs.std(ddof=1) * np.sqrt(len(rs))) if rs.std(ddof=1) > 0 else None
    rng = np.random.default_rng(7)
    boot = rng.choice(rs, (10000, len(rs)), replace=True).mean(axis=1)
    return {"n": int(len(rs)), "mean": float(rs.mean()),
            "median": float(np.median(rs)), "win": float((rs > 0).mean()),
            "t": t, "bootstrap_p": float((boot <= 0).mean()),
            "ci95_low": float(np.quantile(boot, 0.025)),
            "ci95_high": float(np.quantile(boot, 0.975)),
            "worst": float(rs.min()), "best": float(rs.max())}


def forward_break_stats(f, days, hold):
    rs = []
    nd = f["nd"]
    for d in days:
        en = d + 1
        ex = min(d + 1 + int(hold), nd - 1)
        if en >= nd:
            continue
        rs.append(float(f["tqo"][ex] / f["tqo"][en] - 1.0))
    rs = np.asarray(rs, dtype=float)
    if len(rs) < 3:
        return {"n": int(len(rs))}
    t = float(rs.mean() / rs.std(ddof=1) * np.sqrt(len(rs))) if rs.std(ddof=1) > 0 else None
    return {"n": int(len(rs)), "mean": float(rs.mean()),
            "median": float(np.median(rs)), "win": float((rs > 0).mean()),
            "t": t, "worst": float(rs.min()), "best": float(rs.max())}


def build_weights(ts, o, c, params=None):
    p = dict(PARAMS)
    if params:
        p.update(params)
    f = daily_features(ts, o, c)
    pos, up, dn = cusum_state(f, p)
    w = weights_from_pos(ts, f, pos)
    runs = episodes(f, pos)
    info = dict(params=p, up_breaks=len(up), down_breaks=len(dn),
                events=len(up) + len(dn), entries=len(up),
                episodes=len(runs), tqqq_exposure=float(np.mean(w[:, 1])),
                episode_stats=episode_stats(runs),
                up_forward=forward_break_stats(f, up, int(p["hold"])),
                down_forward=forward_break_stats(f, dn, int(p["hold"])))
    return w, info


# ---------------------------------------------------------------------------
# evaluation
# ---------------------------------------------------------------------------
def metrics(pos, slip=1.0, start=DEV_START, end=DEV_END, w=None):
    if w is None:
        w = weights_from_pos(TS, F, pos)
    if start == DEV_START and end == DEV_END:
        r = bt.run(TS, O, C, w, start, band=0.02, slippage_bps=slip)
        s = bt.stats(r, BARS_PER_YEAR)
        ww = w
    else:
        i = bt.start_index(TS, start)
        j = int(TS.searchsorted(pd.Timestamp(end, tz="America/New_York"), side="right"))
        r = bt.simulate(TS[i:j], O[i:j], C[i:j], w[i:j], band=0.02,
                        slippage_bps=slip)
        s = bt.stats(r, BARS_PER_YEAR)
        ww = w[i:j]
    return {"cagr": s["cagr"], "max_drawdown": s["max_drawdown"],
            "sharpe": s["sharpe"], "sortino": s["sortino"],
            "volatility": s["volatility"], "fills": s["fills"],
            "turnover": s["turnover"], "ending_equity": s["ending_equity"],
            "tqqq_exposure": float(np.mean(ww[:, 1]))}


def daily_returns(pos, slip=1.0):
    r = bt.run(TS, O, C, weights_from_pos(TS, F, pos), DEV_START,
               band=0.02, slippage_bps=slip)
    eq = pd.Series(r["equity"], index=r["ts"])
    return eq.groupby(eq.index.date).last().pct_change().dropna()


def load_winner_returns(slug):
    path = ROOT / "research" / "new" / "curves" / f"{slug}.json"
    d = json.loads(path.read_text())
    dates = pd.to_datetime(d["dates"])
    keep = dates <= pd.Timestamp(DEV_END)
    vals = np.asarray(d["values"], dtype=float)[keep]
    return pd.Series(vals, index=dates[keep]).pct_change().dropna()


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


def placebo(pos, n_draw=100, seed=11):
    rng = np.random.default_rng(seed)
    real = metrics(pos)["cagr"]
    seg = pos[WARM:]
    shift_c, shuffle_c = [], []
    for _ in range(n_draw):
        sh = int(rng.integers(20, len(seg) - 20))
        q = np.r_[np.zeros(WARM), np.roll(seg, sh)]
        shift_c.append(metrics(q)["cagr"])
        q2 = np.r_[np.zeros(WARM), rng.permutation(seg)]
        shuffle_c.append(metrics(q2)["cagr"])

    def summ(v):
        a = np.asarray(v)
        return {"n_draws": int(len(a)), "mean_cagr": float(a.mean()),
                "std_cagr": float(a.std(ddof=1)),
                "p95_cagr": float(np.quantile(a, 0.95)),
                "max_cagr": float(a.max()),
                "p_value": float((a >= real).mean())}

    s = summ(shift_c)
    s["note"] = "circular shift of the daily state vector; preserves durations and exposure."
    r = summ(shuffle_c)
    r["note"] = "random permutation of the daily state vector; preserves exposure, destroys clustering."
    return {"real_cagr": real, "active_days": int((pos > 0).sum()),
            "shift": s, "shuffle": r}


def precut_check():
    cut = bt.start_index(TS, "2020-03-12")
    f = daily_features(TS[:cut], O[:cut], C[:cut])
    pos_cut, _, _ = cusum_state(f, PARAMS)
    w_cut = weights_from_pos(TS[:cut], f, pos_cut)
    w_full = weights_from_pos(TS, F, F["pos"])
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
    pos, up, dn = cusum_state(F, PARAMS)
    F["pos"] = pos
    w = weights_from_pos(TS, F, pos)
    runs = episodes(F, pos)
    info = dict(params=PARAMS, up_breaks=len(up), down_breaks=len(dn),
                events=len(up) + len(dn), entries=len(up),
                episodes=len(runs), tqqq_exposure=float(np.mean(w[:, 1])),
                episode_stats=episode_stats(runs),
                up_forward=forward_break_stats(F, up, PARAMS["hold"]),
                down_forward=forward_break_stats(F, dn, PARAMS["hold"]))

    out = {
        "agent": SLUG,
        "family": "online change-point / CUSUM",
        "idea": "A CUSUM break in the QQQ up/down balance marks a new return "
                "regime. Up-breaks are traded as a long TQQQ window; "
                "down-breaks are a cash window.",
        "hypothesis": "A detected change in the up/down balance predicts the "
                      "direction of the next fixed holding window strongly "
                      "enough to beat TQQQ's development CAGR with a lower "
                      "drawdown.",
        "universe": ["QQQ", "TQQQ", "BIL"],
        "window": {"dev": [DEV_START, DEV_END], "holdout": "not loaded"},
        "execution": {"engine": "research/bt.py", "marks": "1min",
                      "fills": "next open", "band": 0.02,
                      "headline_bps": 1.0, "also_bps": [5.0, 10.0],
                      "weight_cap": 1.0, "long_only": True,
                      "exposure_state": "TQQQ after an up-break, BIL after a down-break"},
        "params": PARAMS, "info": info, "windows": {"dev": {}},
        "benchmarks": {}, "yearly": {}, "grid": [], "cuts": {},
        "placebo": {}, "corr_winners": {}, "corr_tqqq": None, "precut": {},
        "kill_criteria": [
            "dev 1 bp CAGR <= 36.72% or dev max drawdown >= 82.29%",
            "fewer than 5 of the 8 pre-registered grid cells clear the same bar",
            "10 bp CAGR <= 36.72%",
            "shift-placebo p > 0.05",
            "shuffle-placebo p > 0.05",
            "ex-2020 CAGR <= 25%",
            "daily-return correlation to any winner > 0.85",
            "fewer than 100 fills or fewer than 30 independent breaks",
            "pre-cut max weight difference > 1e-12",
            "down-break forward 20-session t > 2 (direction-down leg false)",
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
        ("1 k0.00 h3 H20 (primary)", dict(k=0.00, h=3.0, hold=20)),
        ("2 k0.00 h4 H20", dict(k=0.00, h=4.0, hold=20)),
        ("3 k0.00 h5 H20", dict(k=0.00, h=5.0, hold=20)),
        ("4 k0.00 h6 H20", dict(k=0.00, h=6.0, hold=20)),
        ("5 k0.10 h3 H20", dict(k=0.10, h=3.0, hold=20)),
        ("6 k0.10 h5 H20", dict(k=0.10, h=5.0, hold=20)),
        ("7 k0.20 h3 H20", dict(k=0.20, h=3.0, hold=20)),
        ("8 k0.10 h3 H15", dict(k=0.10, h=3.0, hold=15)),
    ]
    for name, pp in cells:
        p = dict(PARAMS); p.update(pp)
        q, _, _ = cusum_state(F, p)
        out["grid"].append({"name": name, "params": pp, **metrics(q)})

    for name, a, b in (("2016-2019", "2016-01-04", "2019-12-31"),
                       ("2020-2021", "2020-01-02", "2021-12-31"),
                       ("2022-2023", "2022-01-03", "2023-12-29")):
        out["cuts"][name] = metrics(pos, 1.0, a, b, w)
    years = pd.Series(pd.to_datetime(list(F["dates"][F["first"]]))).dt.year.to_numpy()
    for y in (2020, 2022):
        q = pos.copy(); q[years == y] = 0.0
        out["cuts"][f"ex{y}"] = metrics(q)

    out["placebo"] = placebo(pos)
    out["corr_winners"] = correlations(pos)
    out["corr_tqqq"] = out["corr_winners"]["TQQQ"]
    out["precut"] = precut_check()

    dev = out["windows"]["dev"]["1bp"]
    n_grid = sum(1 for g in out["grid"]
                 if g["cagr"] > 0.3672 and g["max_drawdown"] < 0.8229)
    primary_ok = dev["cagr"] > 0.3672 and dev["max_drawdown"] < 0.8229
    if primary_ok and n_grid >= 5 and out["placebo"]["shift"]["p_value"] <= 0.05:
        out["status"] = ("dev_pass" if out["windows"]["dev"]["10bp"]["cagr"] > 0.3672
                         else "dev_pass_marginal")
    elif primary_ok:
        out["status"] = "dev_pass_marginal"
    else:
        out["status"] = "dev_fail"
    out["grid_cells_above_bar"] = int(n_grid)

    (OUT / "result.json").write_text(json.dumps(out, indent=2, default=float))
    print(json.dumps({
        "status": out["status"],
        "primary": {k: out["windows"]["dev"][k] for k in ("1bp", "5bp", "10bp")},
        "grid_cells_above_bar": n_grid,
        "corr_tqqq": out["corr_tqqq"],
        "corr_range": [min(out["corr_winners"][s] for s in WINNERS),
                       max(out["corr_winners"][s] for s in WINNERS)],
        "placebo": out["placebo"], "precut": out["precut"],
        "info": {k: v for k, v in info.items() if k != "episode_stats"},
    }, indent=2, default=float))
    print("wrote", OUT / "result.json")


if __name__ == "__main__":
    main()
