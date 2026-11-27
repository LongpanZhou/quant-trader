"""OpEx: average path, gap conditioning, dd attribution."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "research"))
sys.path.insert(0, str(HERE))
import bt  # noqa: E402
import cal  # noqa: E402
from explore import load_panel, baseline, event_study  # noqa: E402
from variants import overlay, metrics  # noqa: E402


def main():
    ts, opens, highs, lows, closes, vols = load_panel()
    w0, meta = baseline(ts, opens, closes)
    d = event_study(meta, opens, closes)
    d = d[d["date"] >= pd.Timestamp("2017-01-03").date()].copy()
    first, last = meta["first"], meta["last"]
    dates = meta["dates"][first]
    opex = set(cal.opex_dates(2016, 2027))
    tod = np.array([t.hour * 60 + t.minute for t in ts])
    buckets = [570, 600, 630, 660, 690, 720, 750, 780, 810, 840, 870, 900, 930, 960]

    rows = []
    for k, dt_ in enumerate(dates):
        if not meta["risk_on"][k]:
            continue
        f, l = first[k], last[k]
        m = tod[f:l + 1]
        o1 = opens[f:l + 1, 1]
        c1 = closes[f:l + 1, 1]
        rec = {"date": dt_, "opex": dt_ in opex, "year": dt_.year,
               "gap": o1[0] / (closes[last[k - 1], 1]) - 1.0 if k > 0 else 0.0}
        for i in range(len(buckets) - 1):
            idx = np.flatnonzero((m >= buckets[i]) & (m < buckets[i + 1]))
            rec[buckets[i]] = c1[idx[-1]] / o1[0] - 1.0 if len(idx) else np.nan
        rows.append(rec)
    df = pd.DataFrame(rows).dropna()
    ks = buckets[:-1]
    o = df[df.opex]
    n = df[~df.opex]
    print("average cumulative TQQQ return from session open (bp), risk-on")
    tab = pd.DataFrame({
        "t": [f"{b//60:02d}:{b%60:02d}" for b in ks],
        "opex": o[ks].mean().values * 1e4,
        "nonopex": n[ks].mean().values * 1e4,
    })
    tab["diff"] = tab.opex - tab.nonopex
    tab["se"] = [np.sqrt(o[b].var() / len(o) + n[b].var() / len(n)) * 1e4 for b in ks]
    print(tab.round(1).to_string(index=False))

    print("\n--- OpEx days split by opening gap (TQQQ open vs prior close) ---")
    df["o2c"] = df[930]
    bins = [-1.0, -0.02, -0.005, 0.005, 0.02, 1.0]
    df["gbin"] = pd.cut(df["gap"], bins)
    g = df.groupby(["opex", "gbin"], observed=True)["o2c"].agg(["count", "mean", "median"])
    g[["mean", "median"]] *= 1e4
    print(g.round(1).to_string())
    print("\nmeans (bp): opex vs non by gap bucket")
    piv = df.pivot_table(index="gbin", columns="opex", values="o2c", aggfunc="mean", observed=True)
    print((piv * 1e4).round(1).to_string())
    print("\ncounts:")
    print(df.pivot_table(index="gbin", columns="opex", values="o2c", aggfunc="count", observed=True).to_string())

    print("\n--- skip-overlay condition: no de-risk when gap < -X ---")
    o = df[df.opex]
    for x in (0.005, 0.01, 0.02, 0.03):
        sub = o[o["gap"] >= -x]
        skipped = o[o["gap"] < -x]
        print(f"  X={x*100:.1f}%: {len(sub)}/{len(o)} opex days kept, o2c mean {sub['o2c'].mean()*1e4:7.1f} bp; "
              f"skipped {len(skipped)} days mean o2c {(skipped['o2c'].mean()*1e4 if len(skipped) else float('nan')):7.1f} bp")

    print("\n--- 5y drawdown attribution: baseline vs opex-bil ---")
    w1, _ = overlay(ts, w0, meta, events=opex, asset="bil", frac=0.0)
    s0 = metrics(ts, opens, closes, w0, "2021-10-25")
    s1 = metrics(ts, opens, closes, w1, "2021-10-25")
    for tag, s in (("baseline", s0), ("opex-bil", s1)):
        eq = pd.Series(s["equity"], index=s["ts"])
        dd = eq / eq.cummax() - 1
        print(f"  {tag:9s} DD {s['max_drawdown']*100:5.2f}%  trough {s['dd_trough']}  "
              f"10 worst days: {[str(x.date()) for x in dd.nsmallest(10).index]}")


if __name__ == "__main__":
    main()
