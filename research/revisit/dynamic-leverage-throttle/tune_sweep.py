"""Tune step 3: pre-declared variant families, neighbourhood and placebo (dev only).

    python research/revisit/dynamic-leverage-throttle/tune_sweep.py

Writes tune_sweep.json.  Every variant evaluated here is counted.
"""
from __future__ import annotations

import itertools
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1]))
import bt  # noqa: E402
import strategy as S  # noqa: E402

SUBS = (("2016_19", "2016-01-04", "2019-12-31"),
        ("2020_21", "2020-01-02", "2021-12-31"),
        ("2022_23", "2022-01-03", "2023-12-29"))


def setup():
    ts, op, cl = S.load_dev_panel()
    assert ts[-1] < pd.Timestamp("2023-12-30", tz="America/New_York")
    i0 = bt.start_index(ts, S.DEV_START)
    dates = S.session_dates(ts)[i0:]
    base = S.baseline_165d_weights(ts, cl)
    rb = bt.run(ts, op, cl, base, S.DEV_START, band=0.02, slippage_bps=1.0)
    bd = pd.Series(rb["equity"], index=dates).groupby(level=0).last().pct_change().dropna()
    return ts, op, cl, i0, dates, bd


def evaluate(ctx, mats, slip=1.0):
    ts, op, cl, i0, dates, bd = ctx
    out = []
    for k in range(0, len(mats), 16):
        res = bt.run_many(ts, op, cl, mats[k:k + 16], start=S.DEV_START,
                          band=0.02, slippage_bps=slip)
        for r in res:
            s = bt.stats(r, S.BARS)
            eqd = pd.Series(r["equity"], index=dates).groupby(level=0).last()
            dr = eqd.pct_change().dropna()
            row = {"cagr": float(s["cagr"]), "dd": float(s["max_drawdown"]),
                   "sharpe": float(s["sharpe"]), "fills": int(s["fills"]),
                   "corr": float(np.corrcoef(dr, bd.loc[dr.index])[0, 1])}
            row["calmar"] = row["cagr"] / row["dd"] if row["dd"] > 0 else 0.0
            idx = pd.to_datetime(pd.Index(eqd.index))
            e = pd.Series(eqd.to_numpy(), index=idx)
            for tag, a, b in SUBS:
                pre = e[e.index < pd.Timestamp(a)]
                seg = e[(e.index >= pd.Timestamp(a)) & (e.index <= pd.Timestamp(b))]
                p0 = pre.iloc[-1] if len(pre) else seg.iloc[0]
                yrs = (seg.index[-1] - (pre.index[-1] if len(pre) else seg.index[0])).days / 365.25
                row[tag] = float((seg.iloc[-1] / p0) ** (1 / yrs) - 1)
            out.append(row)
    return out


def build(ctx, over):
    ts, op, cl = ctx[:3]
    w, info = S.build_weights(ts, op, cl, {**S.PARAMS, **over})
    return w, info


def main():
    ctx = setup()
    out = {"variants": [], "notes": []}
    families = {
        "A_before_fix": [{"warmup_daily": False}],
        "A_warmup_fix": [{}],
        "B_sizing": [{"target_vol": tv, "max_weight": mw}
                     for tv in (0.30, 0.45, 0.60, 0.90) for mw in (0.75, 1.0)],
        "C_reaccel_exit": [{"reaccel": r} for r in (1.10, 1.25, 1.50, 99.0)],
        "D_shock_entry": [{"shock_mult": m} for m in (1.0, 1.15, 1.25, 1.35)],
    }
    mats, meta = [], []
    for fam, lst in families.items():
        for over in lst:
            w, info = build(ctx, over)
            mats.append(w)
            mw = w[ctx[3]:, 1]
            meta.append({"family": fam, "params": over,
                         "entries": int(info.get("entry_count", 0)),
                         "frac_min_tqqq": float((mw > 0).mean()),
                         "mean_w_tqqq": float(mw.mean())})
    rows = evaluate(ctx, mats)
    for m, r in zip(meta, rows):
        out["variants"].append({**m, **r})
    for v in out["variants"]:
        print(f"{v['family']:15s} {json.dumps(v['params']):45s} n={v['entries']:2d} "
              f"exp={v['frac_min_tqqq']:.3f} CAGR={v['cagr']*100:6.2f}% DD={v['dd']*100:5.1f}% "
              f"Sh={v['sharpe']:.2f} corr={v['corr']:.3f} "
              f"sub={v['2016_19']*100:5.2f}/{v['2020_21']*100:5.2f}/{v['2022_23']*100:5.2f}")
    (HERE / "tune_sweep.json").write_text(json.dumps(out, indent=1), encoding="utf-8")


if __name__ == "__main__" and len(sys.argv) == 1:
    main()


def neighbourhood_and_placebo():
    """Part 2: is dropping the re-acceleration exit robust?  Plus placebo."""
    ctx = setup()
    grid = {"shock_mult": (1.15, 1.25, 1.35), "decay_ratio": (0.80, 0.85, 0.90),
            "dd_entry": (-0.06, -0.08, -0.10), "time_stop": (40, 60, 80)}
    keys = list(grid)
    cells = [dict(zip(keys, v)) for v in itertools.product(*grid.values())]
    mats, meta = [], []
    for c in cells:
        for r in (1.10, 99.0):
            w, info = build(ctx, {**c, "reaccel": r})
            mats.append(w)
            meta.append({**c, "reaccel": r, "entries": int(info["entry_count"])})
    rows = evaluate(ctx, mats)
    allrows = [{**m, **r} for m, r in zip(meta, rows)]
    pairs = [(allrows[i], allrows[i + 1]) for i in range(0, len(allrows), 2)]
    summ = {"n_cells": len(pairs)}
    for key in ("cagr", "sharpe", "calmar", "2016_19", "2020_21", "2022_23"):
        summ[f"frac_off_better_{key}"] = float(np.mean([b[key] > a[key] + 1e-9 for a, b in pairs]))
        summ[f"frac_off_worse_{key}"] = float(np.mean([b[key] < a[key] - 1e-9 for a, b in pairs]))
    summ["median_cagr_on"] = float(np.median([a["cagr"] for a, _ in pairs]))
    summ["median_cagr_off"] = float(np.median([b["cagr"] for _, b in pairs]))
    summ["median_sharpe_on"] = float(np.median([a["sharpe"] for a, _ in pairs]))
    summ["median_sharpe_off"] = float(np.median([b["sharpe"] for _, b in pairs]))
    summ["max_corr"] = float(max(r["corr"] for r in allrows))
    summ["entries_range"] = [min(r["entries"] for r in allrows), max(r["entries"] for r in allrows)]
    print(json.dumps(summ, indent=1))

    # placebo: same number of episodes, same lengths and weights, random start
    ts, op, cl, i0 = ctx[:4]
    out_p = {}
    for tag, over in (("primary_warmfix", {}), ("reaccel_off", {"reaccel": 99.0})):
        w, info = build(ctx, over)
        sig = S.daily_signals(ts, cl)
        first = sig["first"]
        nd = len(first)
        eps = [(en["session"], ex["session"] - en["session"], en["weight"])
               for en, ex in zip(info["entries"], info["exits"])]
        rng = np.random.default_rng(11)
        pm = []
        for _ in range(200):
            dw = np.zeros((nd, 3))
            dw[:, 2] = 1.0
            for _, L, wt in eps:
                s0 = int(rng.integers(130, nd - L - 1))  # dev sessions with room
                dw[s0:s0 + L, 1] = wt
                dw[s0:s0 + L, 2] = 1 - wt
            pm.append(S.to_minutes(sig, dw))
        pr = evaluate(ctx, pm)
        real = evaluate(ctx, [w])[0]
        pc = np.array([r["cagr"] for r in pr])
        out_p[tag] = {"real_cagr": real["cagr"], "placebo_median": float(np.median(pc)),
                      "placebo_p95": float(np.percentile(pc, 95)),
                      "p_placebo_ge_real": float((pc >= real["cagr"]).mean())}
        print(tag, json.dumps(out_p[tag]))
    (HERE / "tune_neigh.json").write_text(json.dumps(
        {"summary": summ, "rows": allrows, "placebo": out_p}, indent=1), encoding="utf-8")


if __name__ == "__main__" and len(sys.argv) > 1 and sys.argv[1] == "neigh":
    neighbourhood_and_placebo()
