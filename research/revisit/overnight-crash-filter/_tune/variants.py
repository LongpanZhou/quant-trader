"""Step 3 variants, neighbourhood and placebo (dev only)."""
from __future__ import annotations

import json
import sys

import numpy as np
import pandas as pd

from common import SLUG, bt, panel, load_strategy, stats, daily_rets, sub_cagr, DEV_END

mod = load_strategy()
ts, o, c = panel()
n = len(ts)
bw = mod._benchmark_correlation_weights(ts, o, c)
rb = bt.simulate(ts, o, c, bw, band=0.02, slippage_bps=1)
base_d = daily_rets(ts, rb["equity"])
print("baseline (fixed)", {k: round(v, 4) for k, v in stats(rb).items()})

# other rebuilds' dev curves (read-only), clipped to dev
others = {}
for p in (SLUG.parent / "curves").glob("*.json"):
    if p.stem == SLUG.name:
        continue
    d = json.loads(p.read_text(encoding="utf-8"))
    s = pd.Series(d["values"], index=pd.to_datetime(d["dates"]).date)
    s = s[s.index <= pd.Timestamp(DEV_END).date()]
    others[p.stem] = s.pct_change().dropna()


def evaluate(name, w, full=True):
    row = {"name": name}
    r1 = bt.simulate(ts, o, c, w, band=0.02, slippage_bps=1)
    row |= {f"1bp_{k}": v for k, v in stats(r1).items()}
    dr = daily_rets(ts, r1["equity"])
    row["corr165"] = float(dr.corr(base_d))
    if full:
        for bp in (0, 5, 10):
            s = stats(bt.simulate(ts, o, c, w, band=0.02, slippage_bps=bp))
            row[f"{bp}bp_cagr"] = s["cagr"]
        row["sub"] = {k: (round(a, 4), round(b, 4)) for k, (a, b) in sub_cagr(ts, r1["equity"]).items()}
        cs = {k: float(dr.corr(v.reindex(dr.index))) for k, v in others.items()}
        top = sorted(cs.items(), key=lambda kv: -kv[1])[:3]
        row["max_corr_other"] = top
    return row


def show(row):
    s = (f"{row['name']:34s} 1bp {row['1bp_cagr']*100:6.2f}% DD {row['1bp_max_drawdown']*100:5.1f}% "
         f"Sh {row['1bp_sharpe']:4.2f} fills {row['1bp_fills']:5d} corr {row['corr165']:.3f}")
    if "0bp_cagr" in row:
        s += (f" | 0/5/10bp {row['0bp_cagr']*100:5.1f}/{row['5bp_cagr']*100:5.1f}/{row['10bp_cagr']*100:5.1f}"
              f" | sub {row['sub']} | other {[(k, round(v, 2)) for k, v in row['max_corr_other']]}")
    print(s, flush=True)


rows = []
VARIANTS = {
    "V0 frozen": {},
    "V1 night-only (sign cond)": {"day_leg": False},
    "V2 night unconditional": {"day_leg": False, "night_cond": False},
    "V3 V2 + morning 30": {"day_leg": False, "night_cond": False, "morning_min": 30},
    "V4 V2 no vol ceiling": {"day_leg": False, "night_cond": False, "vol_ceil": 9.9},
    "V5 V2 no budget (w=1, ceiling)": {"day_leg": False, "night_cond": False, "target_gap": 9.9},
    "V6 V2 + day leg": {"night_cond": False},
}
for name, kw in VARIANTS.items():
    w, info = mod.build_weights(ts, o, c, **kw)
    row = evaluate(name, w) | {"kw": kw, "night_days": info["night_days"], "night_w_mean": info["night_w_mean"]}
    rows.append(row)
    show(row)

# static references
for x in (0.25, 0.30):
    ws = np.zeros((n, 3)); ws[:, 1] = x
    row = evaluate(f"static TQQQ {x:.2f}", ws)
    rows.append(row); show(row)

if "--grid" in sys.argv:
    print("\nneighbourhood around V2")
    base = {"day_leg": False, "night_cond": False}
    grid = []
    for mm in (0, 15, 30, 45, 60):
        for tg in (0.03, 0.04, 0.05, 0.06):
            for vw in (10, 20, 40):
                for vc in (0.35, 0.40, 0.45):
                    grid.append({"morning_min": mm, "target_gap": tg, "vol_win": vw, "vol_ceil": vc})
    for kw in grid:
        w, info = mod.build_weights(ts, o, c, **base, **kw)
        row = evaluate(json.dumps(kw), w, full=False) | {"kw": kw}
        s3 = sub_cagr(ts, bt.simulate(ts, o, c, w, band=0.02, slippage_bps=1)["equity"])
        row["sub"] = {k: round(a, 4) for k, (a, b) in s3.items()}
        rows.append(row)
        print(f"{json.dumps(kw):75s} {row['1bp_cagr']*100:6.2f} {row['1bp_max_drawdown']*100:5.1f} "
              f"{row['1bp_sharpe']:4.2f} c{row['corr165']:.2f} sub {row['sub']}", flush=True)

if "--placebo" in sys.argv:
    print("\nplacebos")
    w2, _ = mod.build_weights(ts, o, c, day_leg=False, night_cond=False)
    s = mod.build_signals(ts, o, c)
    first, last, nd = s["first"], s["last"], s["nd"]
    nightw = w2[last - 1, 1]
    rng = np.random.default_rng(42)
    # (a) time-shift placebo: same weight, held in the DAY block 09:31 -> 15:59 instead of the night
    wp = np.zeros((n, 3))
    for k in range(1, nd):
        x = nightw[k - 1]
        if x > 0 and last[k] - first[k] > 2:
            wp[first[k]:last[k] - 1, 1] = x
    row = evaluate("placebo A: same size, day block", wp)
    rows.append(row); show(row)
    # (b) random-night subsets with the frozen V0/V1 night count (sign-condition placebo)
    w1, info1 = mod.build_weights(ts, o, c, day_leg=False)
    k_on = int((w1[last - 1, 1] > 0).sum())
    elig = np.flatnonzero(nightw > 0)
    res = []
    W = []
    for rep in range(200):
        pick = rng.choice(elig, size=min(k_on, len(elig)), replace=False)
        wr = np.zeros((n, 3))
        wr[last[pick] - 1, 1] = nightw[pick]
        W.append(wr)
    runs = bt.simulate_many(ts, o, c, W, band=0.02, slippage_bps=1)
    cg = np.array([stats(r)["cagr"] for r in runs])
    r1 = stats(bt.simulate(ts, o, c, w1, band=0.02, slippage_bps=1))["cagr"]
    print(f"placebo B: {k_on} random nights x200: CAGR mean {cg.mean()*100:.2f}% "
          f"p5 {np.percentile(cg,5)*100:.2f}% p95 {np.percentile(cg,95)*100:.2f}%; "
          f"V1 (sign-conditioned) {r1*100:.2f}%  share of placebos >= V1: {(cg >= r1).mean():.3f}")
    rows.append({"name": "placebo B", "mean": float(cg.mean()), "p5": float(np.percentile(cg, 5)),
                 "p95": float(np.percentile(cg, 95)), "v1": float(r1), "p": float((cg >= r1).mean())})

tag = "_".join(a.strip("-") for a in sys.argv[1:]) or "main"
with open(SLUG / "_tune" / f"variants_{tag}.json", "w", newline="\n", encoding="utf-8") as f:
    json.dump(rows, f, indent=1, default=float)
