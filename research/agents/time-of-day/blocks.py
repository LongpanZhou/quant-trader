"""Focused checks: TOM day-session stability, first-30 block stability."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import strategy as S  # noqa: E402


def main():
    ts, op, cl = S.load_panel()
    dates = pd.DatetimeIndex(sorted(set(ts.date)))
    df = pd.DataFrame({"date": ts.date, "minute": ts.hour * 60 + ts.minute})
    idx = df.groupby("date", sort=False).indices
    p10 = {}
    for k, dd in idx.items():
        j = int(np.searchsorted(df["minute"].to_numpy()[dd], 601))
        if j < len(dd):
            p10[k] = op[dd[j], 1]
    d = pd.DataFrame({
        "open": pd.Series(op[:, 1], index=ts).groupby(ts.date).first(),
        "close": pd.Series(cl[:, 1], index=ts).groupby(ts.date).last(),
        "p10": pd.Series(p10),
    })
    d.index = pd.to_datetime(d.index)
    d["night"] = d["open"] / d["close"].shift(1) - 1
    d["sess"] = d["close"] / d["open"] - 1
    d["first30"] = d["p10"] / d["open"] - 1
    d = d.dropna()
    d["year"] = d.index.year
    tom = S.tom_flags(dates, 3, 1)
    d["tom"] = [bool(tom.get(x.date(), False)) for x in d.index]

    print("--- day-session mean bp/day: TOM vs non-TOM, by year ---")
    rows = []
    for y, g in d.groupby("year"):
        dm = (g.loc[g.tom, "close"] / g.loc[g.tom, "open"] - 1).mean() * 1e4
        dn = (g.loc[~g.tom, "close"] / g.loc[~g.tom, "open"] - 1).mean() * 1e4
        rows.append({"year": y, "tom_bp": round(dm, 1), "nontom_bp": round(dn, 1),
                     "tom_better": dm > dn})
    t = pd.DataFrame(rows).set_index("year")
    print(t.to_string())
    print("TOM day session better in", int(t["tom_better"].sum()), "/", len(t), "years")

    print("\n--- block gross CAGR by era ---")
    for lo, hi, tag in (("2016-01-04", "2018-12-31", "2016-18"),
                        ("2019-01-01", "2021-12-31", "2019-21"),
                        ("2022-01-03", "2026-10-23", "2022-26"),
                        ("2017-01-03", "2026-10-23", "full")):
        s = d.loc[lo:hi]
        yrs = (s.index[-1] - s.index[0]).days / 365.25
        out = []
        for c in ("night", "first30", "sess"):
            out.append(f"{c} {((1 + s[c]).prod() ** (1 / yrs) - 1) * 100:6.2f}%")
        print(f"  {tag:8s} " + "  ".join(out))

    print("\n--- per calendar year: night vs first30 vs session ---")
    for y, g in d.groupby("year"):
        a = (1 + g["night"].dropna()).prod() - 1
        b = (1 + g["first30"]).prod() - 1
        c = (1 + g["sess"]).prod() - 1
        print(f"  {y}: night {a:+8.1%}   first30 {b:+8.1%}   session {c:+8.1%}")

    print("\n--- TOM effect on the whole c2c return, per-year t-stat of the "
          "difference (TOM - nonTOM) ---")
    diff = []
    for y, g in d.groupby("year"):
        r1 = g.loc[g.tom, "close"].pct_change().dropna()
        r0 = g.loc[~g.tom, "close"].pct_change().dropna()
        se = np.sqrt(r1.var() / len(r1) + r0.var() / len(r0))
        diff.append({"year": y, "diff_bp": round((r1.mean() - r0.mean()) * 1e4, 1),
                     "t": round((r1.mean() - r0.mean()) / se, 2)})
    print(pd.DataFrame(diff).set_index("year").to_string())


if __name__ == "__main__":
    main()
