"""OpEx deep dive: is the negative OpEx-day drift real, where is it, and is it stable?"""
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
from explore import load_panel, baseline, event_study, START10, START5  # noqa: E402


def main():
    ts, opens, highs, lows, closes, vols = load_panel()
    w, meta = baseline(ts, opens, closes)
    d = event_study(meta, opens, closes)
    d = d[d["date"] >= pd.Timestamp("2017-01-03").date()].copy()
    d["dow"] = pd.to_datetime(d["date"]).dt.dayofweek
    d["year"] = pd.to_datetime(d["date"]).dt.year
    d["month"] = pd.to_datetime(d["date"]).dt.month

    ro = d[d["risk_on"]]
    print("TQQQ daily c2c sd (risk-on): %.1f bp" % (ro["tqqq_c2c"].std() * 1e4))

    print("\n--- day-of-week, risk-on days, TQQQ c2c (bp) ---")
    print(ro.groupby("dow")["tqqq_c2c"].agg(["count", "mean", "median"]).mul([1, 1e4, 1e4]).round(1))

    print("\n--- OpEx vs non-OpEx Friday, risk-on ---")
    fri = ro[ro["dow"] == 4]
    print("OpEx Fri  n=%d mean %.1f bp median %.1f" % (fri["opex"].sum(), fri.loc[fri["opex"], "tqqq_c2c"].mean() * 1e4, fri.loc[fri["opex"], "tqqq_c2c"].median() * 1e4))
    print("other Fri n=%d mean %.1f bp median %.1f" % ((~fri["opex"]).sum(), fri.loc[~fri["opex"], "tqqq_c2c"].mean() * 1e4, fri.loc[~fri["opex"], "tqqq_c2c"].median() * 1e4))

    print("\n--- OpEx decomposition, risk-on, bp ---")
    for c in ("tqqq_c2o", "tqqq_o2c", "tqqq_c2c", "qqq_c2o", "qqq_o2c"):
        print(f"  {c:10s} OpEx mean {ro.loc[ro['opex'], c].mean()*1e4:7.1f}  non {ro.loc[~ro['opex'], c].mean()*1e4:7.1f}")

    print("\n--- OpEx by year (all sessions, TQQQ c2c) ---")
    g = d.groupby(["year", "opex"])["tqqq_c2c"].agg(["count", "mean"]).unstack()
    g.columns = ["non_n", "opex_n", "non_mean", "opex_mean"]
    g[["non_mean", "opex_mean"]] *= 1e4
    print(g.round(1).to_string())

    print("\n--- OpEx by weekday-of-month / triple witching ---")
    tw = ro["opex"] & ro["month"].isin([3, 6, 9, 12])
    print("triple witching n=%d mean %.1f bp" % (tw.sum(), ro.loc[tw, "tqqq_c2c"].mean() * 1e4))
    print("other opex     n=%d mean %.1f bp" % ((ro["opex"] & ~tw).sum(), ro.loc[ro["opex"] & ~tw, "tqqq_c2c"].mean() * 1e4))

    print("\n--- window around OpEx (risk-on, TQQQ c2c bp, day offsets) ---")
    idx = pd.Series(np.arange(len(d)), index=pd.to_datetime(d["date"]))
    d2 = d.set_index(pd.to_datetime(d["date"]))
    offs = []
    for off in (-3, -2, -1, 0, 1, 2, 3):
        vals = []
        for dt_ in d2.index[d2["opex"].values]:
            j = d2.index.get_loc(dt_) + off
            if 0 <= j < len(d2):
                vals.append(d2["tqqq_c2c"].iloc[j])
        vals = np.array([v for v in vals if np.isfinite(v)])
        offs.append((off, len(vals), vals.mean() * 1e4, vals.std() / np.sqrt(len(vals)) * 1e4))
    for o in offs:
        print("  offset %+d  n=%3d  mean %7.1f bp  se %5.1f" % o)

    print("\n--- OpEx 2024-2026 detail (risk-on) ---")
    late = ro[(ro["year"] >= 2024) & ro["opex"]]
    print(late[["date", "tqqq_c2o", "tqqq_o2c", "tqqq_c2c", "weak"]].to_string(
        index=False, float_format=lambda x: f"{x*100:6.2f}%"))

    print("\n--- largest OpEx losses ---")
    print(ro[ro["opex"]].nsmallest(10, "tqqq_c2c")[["date", "tqqq_c2c", "tqqq_c2o", "tqqq_o2c", "weak"]]
          .to_string(index=False, float_format=lambda x: f"{x*100:7.2f}%"))

    # How many OpEx days coincide with another event?
    print("\n--- OpEx overlap ---")
    ov = ro[ro["opex"]]
    print("of %d risk-on OpEx days: fomc %d cpi %d nfp %d" % (
        len(ov), ov["fomc"].sum(), ov["cpi"].sum(), ov["nfp"].sum()))


if __name__ == "__main__":
    main()
