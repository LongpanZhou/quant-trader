"""Seasonality diagnostics: TOM / day-of-week / month, stability over time."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import strategy as S  # noqa: E402

import bt  # noqa: E402


def main():
    ts, op, cl = S.load_panel()
    dcl = S.daily_close(ts, cl[:, 0])
    dates = pd.DatetimeIndex(sorted(set(ts.date)))

    d = pd.DataFrame({
        "open": pd.Series(op[:, 1], index=ts).groupby(ts.date).first(),
        "close": pd.Series(cl[:, 1], index=ts).groupby(ts.date).last(),
        "qopen": pd.Series(op[:, 0], index=ts).groupby(ts.date).first(),
        "qclose": pd.Series(cl[:, 0], index=ts).groupby(ts.date).last(),
    })
    d.index = pd.to_datetime(d.index)
    d["c2c"] = d["close"] / d["close"].shift(1) - 1
    d["day"] = d["close"] / d["open"] - 1
    d["night"] = d["open"] / d["close"].shift(1) - 1
    d = d.dropna()

    tom5 = S.tom_flags(dates, 3, 1)
    d["tom"] = [bool(tom5.get(x.date(), False)) for x in d.index]
    d["dow"] = d.index.day_of_week
    d["month"] = d.index.month
    d["year"] = d.index.year

    print("=" * 100)
    print("Turn-of-month (last 1 + first 3 trading days): TQQQ per-day stats")
    g = d.groupby("tom")
    print(g[["c2c", "day", "night"]].agg(["mean", "count"]).to_string())
    print("\n  mean bp/day:")
    print((g[["c2c", "day", "night"]].mean() * 1e4).round(1).to_string())
    print("\n  hit rate:")
    print((d.assign(up=d["c2c"] > 0).groupby("tom")["up"].mean()).round(3).to_string())
    print("\n  by year (c2c total %), TOM vs rest:")
    rows = []
    for y, grp in d.groupby("year"):
        rows.append({"year": y,
                     "tom": (1 + grp.loc[grp.tom, "c2c"]).prod() - 1,
                     "rest": (1 + grp.loc[~grp.tom, "c2c"]).prod() - 1,
                     "tom_days": int(grp.tom.sum())})
    t = pd.DataFrame(rows).set_index("year")
    t["tom_win"] = t["tom"] > t["rest"]
    print((t * 100).round(1).to_string())
    print("  TOM beats rest in", int(t["tom_win"].sum()), "/", len(t), "years")

    print("\n" + "=" * 100)
    print("Day of week: TQQQ mean bp/day, by era")
    for lo, hi, tag in (("2017-01-03", "2021-12-31", "2017-2021"),
                        ("2022-01-03", "2026-10-23", "2022-2026")):
        sub = d.loc[lo:hi]
        m = sub.groupby("dow")[["c2c", "day", "night"]].mean() * 1e4
        print(f"\n  {tag} (bp/day)")
        print(m.round(1).to_string())
    print("\n  full period c2c total % by dow")
    print(((d.groupby("dow")["c2c"].apply(lambda x: (1 + x).prod() - 1)) * 100).round(1).to_string())

    print("\n" + "=" * 100)
    print("Month: TQQQ c2c mean bp/day and total % by month, two eras")
    for lo, hi, tag in (("2017-01-03", "2021-12-31", "2017-2021"),
                        ("2022-01-03", "2026-10-23", "2022-2026")):
        sub = d.loc[lo:hi]
        m = sub.groupby("month")["c2c"]
        print(f"\n  {tag}: mean bp {dict((k, round(v*1e4,1)) for k,v in m.mean().items())}")
        print(f"           total % {dict((k, round(((1+m.get_group(k)).prod()-1)*100,1)) for k in m.groups)}")

    print("\n" + "=" * 100)
    print("Block anatomy, per era (TQQQ, gross CAGR of each block held alone)")
    for lo, hi, tag in (("2017-01-03", "2021-12-31", "2017-2021"),
                        ("2022-01-03", "2026-10-23", "2022-2026"),
                        ("2017-01-03", "2026-10-23", "full")):
        sub = d.loc[lo:hi]
        yrs = (sub.index[-1] - sub.index[0]).days / 365.25
        out = {}
        for c in ("night", "day", "c2c"):
            out[c] = ((1 + sub[c]).prod() ** (1 / yrs) - 1) * 100
        print(f"  {tag:10s} night {out['night']:6.1f}%  day {out['day']:6.1f}%  "
              f"c2c {out['c2c']:6.1f}%")


if __name__ == "__main__":
    main()
