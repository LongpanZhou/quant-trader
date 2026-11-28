"""Robustness checks for the policy-liquidity family (development window only).

Outputs robustness.json.  Run after strategy.py:
    python research/new/family-policy-liquidity/robustness.py
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
sys.path.insert(0, str(HERE))
import bt  # noqa: E402
import strategy as S  # noqa: E402

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


def simulate_panel(ts, o, c, w, slip=1.0, bpy=S.BPY_1M):
    r = bt.simulate(ts, o, c, w, band=S.BAND, slippage_bps=slip)
    return bt.stats(r, bpy), r


def simulate_1m(ts, o, c, w, slip=1.0):
    return simulate_panel(ts, o, c, w, slip=slip, bpy=S.BPY_1M)


def simulate_1d(ts, o, c, w, slip=1.0):
    return simulate_panel(ts, o, c, w, slip=slip, bpy=S.BPY_1D)


def grid(ts, o, c):
    rows = []
    for lo in (0.75, 1.00, 1.25):
        for hi in (3.50, 4.00, 4.50):
            for ft in (0.10, 0.15, 0.20, 0.25):
                for st in (0.25, 0.40, 0.55):
                    w = S.build_weights(ts, o, c, lo=lo, hi=hi,
                                        front_t=ft, slope_t=st)
                    s, _ = simulate_1m(ts, o, c, w)
                    rows.append({"lo": lo, "hi": hi, "front": ft, "slope": st,
                                 "cagr": float(s["cagr"]),
                                 "dd": float(s["max_drawdown"]),
                                 "sharpe": float(s["sharpe"]),
                                 "fills": int(s["fills"])})
    return rows


def placebo(tsd, od, cd, ts1, o1, c1, n_daily=300, n_1m=50, seed=7):
    _, on = S.build_weights(tsd, od, cd, return_state=True)
    n = len(on)
    rng = np.random.default_rng(seed)
    # Actual daily result.
    w = S.build_weights(tsd, od, cd)
    s_actual, _ = simulate_1d(tsd, od, cd, w)
    daily = []
    for _ in range(n_daily):
        shift = int(rng.integers(60, n - 60))
        shifted = np.roll(on, shift)
        w = S.build_weights(tsd, od, cd, state_override=shifted)
        s, _ = simulate_1d(tsd, od, cd, w)
        daily.append({"shift": shift, "cagr": float(s["cagr"]),
                      "sharpe": float(s["sharpe"]), "dd": float(s["max_drawdown"])})
    cagr = np.array([x["cagr"] for x in daily])
    sharpe = np.array([x["sharpe"] for x in daily])
    one_min = []
    for _ in range(n_1m):
        shift = int(rng.integers(60, n - 60))
        shifted = np.roll(on, shift)
        w = S.build_weights(ts1, o1, c1, state_override=shifted)
        s, _ = simulate_1m(ts1, o1, c1, w)
        one_min.append({"shift": shift, "cagr": float(s["cagr"]),
                        "sharpe": float(s["sharpe"]), "dd": float(s["max_drawdown"])})
    return {
        "actual_daily": {"cagr": float(s_actual["cagr"]),
                         "sharpe": float(s_actual["sharpe"]),
                         "dd": float(s_actual["max_drawdown"])},
        "daily": {
            "n": n_daily,
            "cagr_mean": float(cagr.mean()), "cagr_p50": float(np.median(cagr)),
            "cagr_p90": float(np.percentile(cagr, 90)),
            "cagr_p95": float(np.percentile(cagr, 95)),
            "cagr_max": float(cagr.max()),
            "p_value_cagr": float((cagr >= s_actual["cagr"]).mean()),
            "p_value_sharpe": float((sharpe >= s_actual["sharpe"]).mean()),
        },
        "one_minute": {
            "n": n_1m,
            "cagr_mean": float(np.mean([x["cagr"] for x in one_min])),
            "cagr_p95": float(np.percentile([x["cagr"] for x in one_min], 95)),
            "cagr_max": float(np.max([x["cagr"] for x in one_min])),
        },
        "draws_daily": daily,
    }


def clocks(ts1, o1, c1, tsd, od, cd):
    out = {}
    for clock, label in (("D", "daily"), ("W", "weekly"), ("M", "monthly")):
        w = S.build_weights(ts1, o1, c1, clock=clock)
        s, _ = simulate_1m(ts1, o1, c1, w)
        out[label] = {"cagr": float(s["cagr"]), "dd": float(s["max_drawdown"]),
                      "sharpe": float(s["sharpe"]), "fills": int(s["fills"])}
    return out


def ablations(ts1, o1, c1):
    cases = {
        "centre": {},
        "no_high_band": {"hi": 999.0},
        "no_low_band": {"lo": -999.0},
        "front_only": {"slope_t": 999.0},
        "slope_only": {"front_t": 999.0},
        "no_slow_tightening": {"slope_t": 999.0},
        "no_front_stress": {"front_t": 999.0},
    }
    out = {}
    for name, kw in cases.items():
        w = S.build_weights(ts1, o1, c1, **kw)
        s, _ = simulate_1m(ts1, o1, c1, w)
        out[name] = {"cagr": float(s["cagr"]), "dd": float(s["max_drawdown"]),
                     "sharpe": float(s["sharpe"]), "fills": int(s["fills"])}
    # TQQQ buy & hold on the same panel.
    w = np.tile([0.0, 1.0, 0.0], (len(ts1), 1))
    s, _ = simulate_1m(ts1, o1, c1, w)
    out["tqqq_buyhold"] = {"cagr": float(s["cagr"]), "dd": float(s["max_drawdown"]),
                           "sharpe": float(s["sharpe"]), "fills": int(s["fills"])}
    return out


def correlations(tsd, od, cd):
    w = S.build_weights(tsd, od, cd)
    r = bt.simulate(tsd, od, cd, w, band=S.BAND, slippage_bps=1.0)
    ours = S._session_end_equity(tsd, r["equity"])
    qqq = S._session_end_equity(tsd, cd[:, S.CT])
    ours_ret = ours.pct_change().dropna()
    qqq_ret = qqq.pct_change().dropna()
    rows = []
    for slug in WINNERS:
        path = ROOT / "research" / "new" / "curves" / f"{slug}.json"
        if not path.exists():
            rows.append({"slug": slug, "error": "missing"})
            continue
        d = json.loads(path.read_text())
        idx = pd.to_datetime(d["dates"])
        s = pd.Series(d["values"], index=idx).sort_index()
        s = s.loc["2016-01-04":"2023-12-29"]
        ret = s.pct_change().dropna()
        common = ours_ret.index.intersection(ret.index)
        x = ours_ret.loc[common].to_numpy()
        y = ret.loc[common].to_numpy()
        if len(common) < 100:
            rows.append({"slug": slug, "error": "short overlap", "n": len(common)})
            continue
        corr = float(np.corrcoef(x, y)[0, 1])
        beta = float(np.cov(x, y, ddof=0)[0, 1] / np.var(y, ddof=0))
        rows.append({"slug": slug, "corr": corr, "beta": beta, "n": len(common)})
    common = ours_ret.index.intersection(qqq_ret.index)
    tq = float(np.corrcoef(ours_ret.loc[common], qqq_ret.loc[common])[0, 1])
    return {"winners": rows, "tqqq_daily_corr": tq}


def main():
    ts1, o1, c1 = bt.panel(S.SYMBOLS, S.DEV_START, S.DEV_END, "1min", warmup_days=0)
    tsd, od, cd = bt.panel(S.SYMBOLS, S.DEV_START, S.DEV_END, "1D", warmup_days=0)
    out = {
        "window": {"start": S.DEV_START, "end": S.DEV_END},
        "centre": {"lo": S.LO, "hi": S.HI, "front": S.FRONT_T,
                   "slope": S.SLOPE_T},
        "grid": grid(ts1, o1, c1),
        "clocks": clocks(ts1, o1, c1, tsd, od, cd),
        "ablations": ablations(ts1, o1, c1),
        "correlations": correlations(tsd, od, cd),
        "placebo": placebo(tsd, od, cd, ts1, o1, c1),
    }
    (HERE / "robustness.json").write_text(json.dumps(out, indent=2) + "\n")
    print(json.dumps({k: out[k] for k in ("clocks", "ablations", "correlations")},
                     indent=2))
    g = pd.DataFrame(out["grid"])
    print("\ngrid summary")
    print(g["cagr"].describe().round(3).to_string())
    print("\ncentre neighbourhood (lo=1.0):")
    sub = g[(g.lo == 1.0)]
    print(sub.pivot_table(index="front", columns="slope", values="cagr").round(3).to_string())
    print("\nlo/hi at front=0.15 slope=0.40:")
    sub = g[(g.front == 0.15) & (g.slope == 0.40)]
    print(sub[["lo", "hi", "cagr", "dd", "sharpe", "fills"]].round(3).to_string(index=False))
    print("\nplacebo:", json.dumps(out["placebo"]["daily"], indent=2))


if __name__ == "__main__":
    main()
