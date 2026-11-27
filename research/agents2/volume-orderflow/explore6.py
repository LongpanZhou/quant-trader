"""Step 7: causal early-session volume -> rest-of-day return (risk-on days)."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import engine  # noqa: E402

pd.set_option("display.width", 220)


def main():
    D = engine.Data()
    tc, to = D.tc, D.to
    # TQQQ close matrix for rest-of-day returns
    M = D.tc_m
    rows = []
    for m, tag in ((30, "10:00"), (60, "10:30"), (90, "11:00"), (120, "11:30")):
        c = np.array([M[d, m] if np.isfinite(M[d, m]) else np.nan for d in range(D.nd)])
        rest = tc / c - 1
        sofar = c / to - 1
        rows.append((tag, m, rest, sofar))

    print("== rest-of-day TQQQ return by early cumulative RVOL (risk-on only)")
    for tag, m, rest, sofar in rows:
        rv = D.rvol_cum_q[:, m]
        sub = D.reg & np.isfinite(rv) & np.isfinite(rest)
        e = np.nanquantile(rv[sub], [0, .2, .4, .6, .8, 1.0])
        e = np.unique(e)
        b = pd.cut(rv[sub], bins=e, include_lowest=True)
        df = pd.DataFrame({"rv": rv[sub], "rest": rest[sub]*100, "sofar": sofar[sub]*100,
                           "b": b})
        g = df.groupby("b", observed=True).agg(n=("rest", "size"), rest=("rest", "mean"),
                                               med=("rest", "median"),
                                               win=("rest", lambda x: 100*(x > 0).mean()),
                                               sofar=("sofar", "mean"))
        g["corr"] = [np.corrcoef(df[df.b == k]["rv"], df[df.b == k]["rest"])[0, 1]
                     for k in g.index]
        print(f"\n  cutoff {tag}: corr(rv,rest)={np.corrcoef(rv[sub], rest[sub])[0,1]:+.3f}")
        print(g.round(2).to_string())

    print("\n\n== joint: morning return bucket x early RVOL (10:00) -> rest of day")
    tag, m, rest, sofar = rows[0]
    rv = D.rvol_cum_q[:, m]
    sub = D.reg & np.isfinite(rv) & np.isfinite(rest)
    for lo, hi, lab in ((-1, -0.015, "down >1.5%"), (-0.015, -0.005, "down 0.5-1.5%"),
                        (-0.005, 0.005, "flat"), (0.005, 1, "up >0.5%")):
        s2 = sub & (sofar >= lo) & (sofar < hi)
        for rlo, rhi, rlab in ((0, 1.0, "rvol<1"), (1.0, 1.5, "rvol1-1.5"), (1.5, 99, "rvol>1.5")):
            s3 = s2 & (rv >= rlo) & (rv < rhi)
            y = rest[s3]
            if len(y) < 15:
                print(f"   {lab:14s} {rlab:10s} n={len(y):3d}")
                continue
            print(f"   {lab:14s} {rlab:10s} n={len(y):3d} mean {y.mean()*100:+6.2f}% "
                  f"med {np.median(y)*100:+6.2f}% win {100*(y>0).mean():4.1f}% "
                  f"p10 {np.quantile(y,0.1)*100:+6.2f}%")

    print("\n== same, but 5y window only (2021-10-25+)")
    cut = pd.Timestamp("2021-10-25").date()
    late = np.array([d >= cut for d in D.dates[D.first]])
    for lo, hi, lab in ((-1, -0.015, "down >1.5%"), (-0.015, -0.005, "down 0.5-1.5%"),
                        (-0.005, 0.005, "flat"), (0.005, 1, "up >0.5%")):
        s2 = sub & late & (sofar >= lo) & (sofar < hi)
        for rlo, rhi, rlab in ((0, 1.0, "rvol<1"), (1.0, 1.5, "rvol1-1.5"), (1.5, 99, "rvol>1.5")):
            y = rest[s2 & (rv >= rlo) & (rv < rhi)]
            if len(y) < 10:
                print(f"   {lab:14s} {rlab:10s} n={len(y):3d}")
                continue
            print(f"   {lab:14s} {rlab:10s} n={len(y):3d} mean {y.mean()*100:+6.2f}% "
                  f"med {np.median(y)*100:+6.2f}% win {100*(y>0).mean():4.1f}%")

    print("\n== by era: corr(rvol@10:00, rest-of-day) among risk-on")
    for lab, a, b_ in (("2017-2019", "2017-01-01", "2020-01-01"),
                       ("2020-2021", "2020-01-01", "2022-01-01"),
                       ("2022-2026", "2022-01-01", "2027-01-01")):
        mk = sub & np.array([(pd.Timestamp(a).date() <= d < pd.Timestamp(b_).date())
                             for d in D.dates[D.first]])
        print(f"   {lab}: n={mk.sum()} r={np.corrcoef(rv[mk], rest[mk])[0,1]:+.3f} "
              f"mean_rvol {rv[mk].mean():.2f}")


if __name__ == "__main__":
    main()
