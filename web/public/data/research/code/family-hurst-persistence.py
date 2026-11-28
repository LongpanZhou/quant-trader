"""Rolling Hurst / variance ratio - `family-hurst-persistence`.

DEVELOPMENT WINDOW ONLY (2016-01-04 .. 2023-12-29).  The 2024-2026 holdout is
never loaded.

Primary object
--------------
The rolling Hurst exponent estimated from the variance ratio of QQQ daily
close-to-close returns:

    VR(q) = Var(q-day return) / (q * Var(1-day return))
    H     = 0.5 + log(VR(q)) / (2 * log(q))

with W = 252 daily returns and q = 5.  H < 0.5 is the mean-reverting side of
the family hypothesis; H > 0.5 is the persistent side.  QQQ's daily returns are
negatively autocorrelated over this sample, so the estimate is centred near
0.43-0.45, not 0.50.  The strategy therefore uses the *relative* Hurst state:
the expanding 30th and 70th percentiles of the prior 1,260 daily estimates
(minimum 60 estimates).

Rule (known at the 15:59 close of day d; fills at the next 09:30 open):
    H[d] <= q30[d]                  -> TQQQ 1.0   (strong mean reversion)
    q30 < H[d] < q70 and 5d ret > 0 -> TQQQ 1.0   (neutral, short-term drift up)
    otherwise                       -> BIL 1.0

No moving average is used.  The 5-day return is only the direction selector
inside the neutral Hurst band; the regime itself is the Hurst estimate.

Run:
    $env:PYTHONPATH = "C:\\Users\\27175\\AppData\\Local\\Temp\\opencode\\pylibs"
    $env:BT_THREADS = "1"
    python research/new/family-hurst-persistence/strategy.py
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
SLUG = "family-hurst-persistence"

PARAMS = dict(window=252, q=5, qlo=0.30, qhi=0.70, min_obs=60, look=1260)

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
    m5 = pd.Series(qc).pct_change(5).to_numpy()
    return dict(dates=dates, sess_dates=dates[first], first=first, last=last,
                nd=nd, qc=qc, r1=r1, m5=m5,
                tq=c[last, 1], tqo=o[first, 1], bil=c[last, 2])


# ---------------------------------------------------------------------------
# Hurst / variance ratio
# ---------------------------------------------------------------------------
def hurst_series(ret, W, q):
    n = len(ret)
    out = np.full(n, np.nan)
    for i in range(W, n):
        x = ret[i - W + 1:i + 1]
        if not np.isfinite(x).all():
            continue
        v1 = float(np.var(x, ddof=0))
        if v1 <= 0:
            continue
        xq = np.convolve(x, np.ones(q), "valid")
        vq = float(np.var(xq, ddof=0))
        if vq <= 0:
            continue
        out[i] = 0.5 + np.log(vq / (q * v1)) / (2.0 * np.log(q))
    return out


def rolling_quantile(x, q, min_obs, look):
    n = len(x)
    out = np.full(n, np.nan)
    for i in range(n):
        v = x[max(0, i - look):i + 1]
        v = v[np.isfinite(v)]
        if len(v) >= min_obs:
            out[i] = float(np.quantile(v, q))
    return out


def hurst_state(f, params):
    p = dict(PARAMS)
    if params:
        p.update(params)
    h = hurst_series(f["r1"], int(p["window"]), int(p["q"]))
    lo = rolling_quantile(h, float(p["qlo"]), int(p["min_obs"]), int(p["look"]))
    hi = rolling_quantile(h, float(p["qhi"]), int(p["min_obs"]), int(p["look"]))
    pos = np.where(h <= lo, 1.0,
                   np.where((h < hi) & (f["m5"] > 0), 1.0, 0.0))
    pos[~np.isfinite(h) | ~np.isfinite(lo) | ~np.isfinite(hi)] = 0.0
    pos[:WARM] = 0.0
    return pos, h, lo, hi


# ---------------------------------------------------------------------------
# weights and episodes
# ---------------------------------------------------------------------------
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


def build_weights(ts, o, c, params=None):
    p = dict(PARAMS)
    if params:
        p.update(params)
    f = daily_features(ts, o, c)
    pos, h, lo, hi = hurst_state(f, p)
    w = weights_from_pos(ts, f, pos)
    runs = episodes(f, pos)
    entries = np.flatnonzero((pos > 0) & (np.r_[0.0, pos[:-1]] == 0))
    info = dict(params=p, signal_days=int((pos > 0).sum()),
                entries=int(len(entries)), episodes=len(runs),
                tqqq_exposure=float(np.mean(w[:, 1])),
                h_mean=float(np.nanmean(h)), h_min=float(np.nanmin(h)),
                h_max=float(np.nanmax(h)),
                frac_low=float(np.nanmean(np.where(np.isfinite(h), (h <= lo), np.nan))),
                frac_high=float(np.nanmean(np.where(np.isfinite(h), (h >= hi), np.nan))),
                episode_stats=episode_stats(runs))
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
    pos_cut, _, _, _ = hurst_state(f, PARAMS)
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
    pos, h, lo, hi = hurst_state(F, PARAMS)
    F["pos"] = pos
    w = weights_from_pos(TS, F, pos)
    runs = episodes(F, pos)
    entries = np.flatnonzero((pos > 0) & (np.r_[0.0, pos[:-1]] == 0))
    info = dict(params=PARAMS, signal_days=int((pos > 0).sum()),
                entries=int(len(entries)), episodes=len(runs),
                tqqq_exposure=float(np.mean(w[:, 1])),
                h_mean=float(np.nanmean(h)), h_min=float(np.nanmin(h)),
                h_max=float(np.nanmax(h)),
                frac_low=float(np.nanmean(np.where(np.isfinite(h), (h <= lo), np.nan))),
                frac_high=float(np.nanmean(np.where(np.isfinite(h), (h >= hi), np.nan))),
                episode_stats=episode_stats(runs),
                entry_forward_20=_entry_forward(F, entries, 20))

    out = {
        "agent": SLUG,
        "family": "Hurst persistence / variance ratio",
        "idea": "The Hurst exponent of QQQ daily returns measures whether the "
                "series is persistent or mean-reverting. Low H (strong mean "
                "reversion) is a risk-on state for a long TQQQ sleeve; high H "
                "(persistent, often persistent downside) is a cash state.",
        "hypothesis": "Hurst above 0.5 favours trend continuation and below "
                      "0.5 favours mean reversion; near 0.5 is cash. On QQQ the "
                      "sample is uniformly below 0.5, so the test is whether "
                      "the relative Hurst state separates forward returns.",
        "universe": ["QQQ", "TQQQ", "BIL"],
        "window": {"dev": [DEV_START, DEV_END], "holdout": "not loaded"},
        "execution": {"engine": "research/bt.py", "marks": "1min",
                      "fills": "next open", "band": 0.02,
                      "headline_bps": 1.0, "also_bps": [5.0, 10.0],
                      "weight_cap": 1.0, "long_only": True,
                      "exposure_state": "TQQQ 1.0 in the low/neutral-up Hurst state, BIL otherwise"},
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
            "fewer than 100 fills or fewer than 30 entries",
            "pre-cut max weight difference > 1e-12",
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
        ("1 W252 q5 30/70 (primary)", dict(window=252, q=5, qlo=.30, qhi=.70)),
        ("2 W252 q2 30/70", dict(window=252, q=2, qlo=.30, qhi=.70)),
        ("3 W252 q10 30/70", dict(window=252, q=10, qlo=.30, qhi=.70)),
        ("4 W126 q5 30/70", dict(window=126, q=5, qlo=.30, qhi=.70)),
        ("5 W126 q2 30/70", dict(window=126, q=2, qlo=.30, qhi=.70)),
        ("6 W126 q10 30/70", dict(window=126, q=10, qlo=.30, qhi=.70)),
        ("7 W252 q5 25/75", dict(window=252, q=5, qlo=.25, qhi=.75)),
        ("8 W252 q5 35/65", dict(window=252, q=5, qlo=.35, qhi=.65)),
    ]
    for name, pp in cells:
        p = dict(PARAMS); p.update(pp)
        q, _, _, _ = hurst_state(F, p)
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
        "placebo": out["placebo"], "precut": out["precut"],
        "info": {k: v for k, v in info.items() if k != "episode_stats"},
    }, indent=2, default=float))
    print("wrote", OUT / "result.json")


def _entry_forward(f, entries, hold):
    rs = []
    nd = f["nd"]
    for d in entries:
        en = d + 1
        ex = min(d + 1 + hold, nd - 1)
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


if __name__ == "__main__":
    main()
