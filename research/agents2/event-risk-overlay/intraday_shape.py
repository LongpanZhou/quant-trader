"""Intraday shape of the OpEx-day effect."""
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


def main():
    ts, opens, highs, lows, closes, vols = load_panel()
    w, meta = baseline(ts, opens, closes)
    d = event_study(meta, opens, closes)
    d = d[d["date"] >= pd.Timestamp("2017-01-03").date()].copy()
    first, last = meta["first"], meta["last"]
    dates = meta["dates"][first]
    opex = set(cal.opex_dates(2016, 2027))

    tod = np.array([t.hour * 60 + t.minute for t in ts])
    buckets = [570, 600, 630, 660, 690, 720, 750, 780, 810, 840, 870, 900, 930, 960]
    # bucket b covers [b, b+30)

    rows = []
    for k, dt_ in enumerate(dates):
        if not meta["risk_on"][k]:
            continue
        f, l = first[k], last[k]
        m = tod[f:l + 1]
        c = closes[f:l + 1, 1]
        o = opens[f:l + 1, 1]
        rec = {"date": dt_, "opex": dt_ in opex, "year": dt_.year}
        prev = o[0]
        for i in range(len(buckets) - 1):
            lo, hi = buckets[i], buckets[i + 1]
            idx = np.flatnonzero((m >= lo) & (m < hi))
            if len(idx) == 0:
                rec[lo] = np.nan
                continue
            rec[lo] = c[idx[-1]] / prev - 1.0
            prev = c[idx[-1]]
        rows.append(rec)
    df = pd.DataFrame(rows)

    print("TQQQ mean 30-min return (bp), risk-on sessions")
    tab = df.groupby("opex")[[b for b in buckets[:-1]]].mean().T * 1e4
    tab.columns = ["non-opex", "opex"]
    tab["diff"] = tab["opex"] - tab["non-opex"]
    tab["se_diff"] = [
        np.sqrt(df.loc[df.opex, b].var() / df.opex.sum() + df.loc[~df.opex, b].var() / (~df.opex).sum()) * 1e4
        for b in buckets[:-1]
    ]
    tab.index = [f"{b//60:02d}:{b%60:02d}" for b in buckets[:-1]]
    print(tab.round(1).to_string())

    print("\ncumulative from 09:30 (TQQQ, bp)")
    cum = (1 + df.groupby("opex")[[b for b in buckets[:-1]]].mean()).cumprod() - 1
    print((cum.T * 1e4).round(0).to_string())

    print("\nby era (TQQQ open->close bp, OpEx days)")
    df["o2c"] = df[[b for b in buckets[:-1]]].apply(lambda r: (1 + r).prod() - 1, axis=1)
    print(df.groupby(["era", "opex"])["o2c"].agg(["count", "mean", "median"]).assign(
        mean=lambda x: x["mean"] * 1e4, median=lambda x: x["median"] * 1e4).round(1)
        if "era" in df else "no era")
    df["era"] = pd.cut(df["year"], [2016, 2019, 2022, 2026], labels=["2017-19", "2020-22", "2023-26"])
    print(df.groupby(["era", "opex"], observed=True)["o2c"].agg(["count", "mean", "median"]).assign(
        mean=lambda x: x["mean"] * 1e4, median=lambda x: x["median"] * 1e4).round(1).to_string())

    print("\nPM-only (13:00->close) return, bp")
    pm = df[[750, 780, 810, 840, 870, 900, 930]].apply(lambda r: (1 + r).prod() - 1, axis=1)
    df["pm"] = pm
    print(df.groupby("opex")["pm"].agg(["count", "mean", "median"]).assign(
        mean=lambda x: x["mean"] * 1e4, median=lambda x: x["median"] * 1e4).round(1).to_string())
    print(df.groupby(["era", "opex"], observed=True)["pm"].agg(["count", "mean"]).assign(
        mean=lambda x: x["mean"] * 1e4).round(1).to_string())

    print("\nlast hour 15:00->close, bp")
    lh = df[[870, 900, 930]].apply(lambda r: (1 + r).prod() - 1, axis=1)
    df["lh"] = lh
    print(df.groupby("opex")["lh"].agg(["count", "mean", "median"]).assign(
        mean=lambda x: x["mean"] * 1e4, median=lambda x: x["median"] * 1e4).round(1).to_string())


if __name__ == "__main__":
    main()
