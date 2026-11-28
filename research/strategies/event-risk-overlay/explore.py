"""Dev-only exploration for the standalone OpEx rebuild (2016-01-04..2023-12-29)."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "research"))
sys.path.insert(0, str(ROOT / "research" / "agents2" / "event-risk-overlay"))
import bt  # noqa: E402
from cal import opex_dates  # noqa: E402

DEV0, DEV1 = "2016-01-04", "2023-12-29"
HERE = Path(__file__).resolve().parent


def day_bounds(dates):
    first = np.flatnonzero(np.r_[True, dates[1:] != dates[:-1]])
    return first, np.r_[first[1:] - 1, len(dates) - 1]


def main():
    ts, opens, closes = bt.panel(("QQQ", "TQQQ", "BIL"), DEV0, DEV1, "1min")
    print("bars", len(ts), ts[0], "->", ts[-1])
    assert ts[-1].date() <= pd.Timestamp(DEV1).date(), "holdout leaked"
    dates = bt.session_dates(ts)
    first, last = day_bounds(dates)
    n = len(first)
    opex = set(opex_dates(2015, 2024))
    d = pd.DataFrame({
        "date": dates[first],
        "t_o": opens[first, 1], "t_c": closes[last, 1],
        "q_o": opens[first, 0], "q_c": closes[last, 0],
    })
    d["t_o2c"] = d["t_c"] / d["t_o"] - 1
    d["q_o2c"] = d["q_c"] / d["q_o"] - 1
    d["t_c2c"] = d["t_c"] / d["t_c"].shift(1) - 1
    d["t_c2o"] = d["t_o"] / d["t_c"].shift(1) - 1
    d["opex"] = d["date"].isin(opex)
    d["dow"] = pd.to_datetime(d["date"]).dt.day_of_week
    d["year"] = pd.to_datetime(d["date"]).dt.year
    d["sess"] = np.arange(len(d))
    opex_idx = d.index[d["opex"]].to_numpy()

    print(f"sessions {len(d)}  opex {int(d['opex'].sum())}")

    def row(mask, label):
        s = d[mask]
        return (f"{label:22s} n={len(s):4d}  o2c {s['t_o2c'].mean()*1e4:7.1f}  "
                f"c2o {s['t_c2o'].mean()*1e4:7.1f}  c2c {s['t_c2c'].mean()*1e4:7.1f}  "
                f"sd {s['t_o2c'].std()*1e4:6.1f}  neg {(s['t_o2c']<0).mean()*100:3.0f}%")

    print("\n=== unconditional, all sessions ===")
    print(row(d["opex"], "OpEx day"))
    print(row(~d["opex"], "other days"))
    print(row(~d["opex"] & (d["dow"] == 4), "other Fridays"))
    print(row(d["opex"] & (d["dow"] == 4), "OpEx (all Fridays?)"))

    # t stat on the o2c difference OpEx vs other Fridays
    a = d.loc[d["opex"], "t_o2c"].to_numpy()
    b = d.loc[~d["opex"] & (d["dow"] == 4), "t_o2c"].to_numpy()
    se = np.sqrt(a.var(ddof=1) / len(a) + b.var(ddof=1) / len(b))
    print(f"OpEx vs other-Friday o2c diff {(a.mean()-b.mean())*1e4:.1f} bp  t={(a.mean()-b.mean())/se:.2f}")

    print("\n=== opex day by sub-period ===")
    for lo, hi in ((2016, 2019), (2020, 2021), (2022, 2023)):
        m = d["opex"] & d["year"].between(lo, hi)
        s = d[m]
        print(f"  {lo}-{hi}  n={len(s):2d}  o2c {s['t_o2c'].mean()*1e4:7.1f} bp  hit {(s['t_o2c']<0).mean()*100:3.0f}%")

    print("\n=== offset profile around OpEx (o2c, bp), unconditional ===")
    for off in range(-5, 6):
        vals, vals_n = [], []
        for k in opex_idx:
            j = k + off
            if 0 <= j < len(d):
                vals.append(d["t_o2c"].iloc[j])
            jn = k + off
        # placebo: same offset from a non-opex Friday
        fri = d.index[(~d["opex"]) & (d["dow"] == 4)].to_numpy()
        for k in fri:
            j = k + off
            if 0 <= j < len(d):
                vals_n.append(d["t_o2c"].iloc[j])
        v = np.array(vals)
        print(f"  off {off:+d}  n={len(v):3d}  mean {v.mean()*1e4:7.1f}  med {np.median(v)*1e4:7.1f}  "
              f"hit {(v<0).mean()*100:3.0f}%   [same offset from non-OpEx Fridays {np.mean(vals_n)*1e4:7.1f}]")

    print("\n=== c2o (overnight) around OpEx, bp ===")
    for off in range(-2, 3):
        vals = []
        for k in opex_idx:
            j = k + off
            if 0 <= j < len(d) and np.isfinite(d["t_c2o"].iloc[j]):
                vals.append(d["t_c2o"].iloc[j])
        v = np.array(vals)
        print(f"  off {off:+d}  n={len(v):3d}  mean {v.mean()*1e4:7.1f}")

    print("\n=== QQQ on OpEx ===")
    print(f"  q o2c opEx {d.loc[d['opex'],'q_o2c'].mean()*1e4:7.1f}  other {d.loc[~d['opex'],'q_o2c'].mean()*1e4:7.1f}")

    print("\n=== per-year OpEx o2c (bp) ===")
    for y in sorted(d["year"].unique()):
        s = d[d["opex"] & (d["year"] == y)]
        tot = d[d["year"] == y]
        print(f"  {y}  n={len(s):2d}  opex {s['t_o2c'].mean()*1e4:8.1f}  all-days {tot['t_o2c'].mean()*1e4:7.1f}")

    np.save(HERE / "dev_daily.npy", d[["sess", "t_o2c", "t_c2o", "t_c2c", "q_o2c"]].to_numpy())


if __name__ == "__main__":
    main()
