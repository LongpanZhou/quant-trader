"""Step 6: where does the winner actually lose, and was volume informative there?"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import engine  # noqa: E402

pd.set_option("display.width", 220)
pd.set_option("display.max_rows", 80)


def main():
    D = engine.Data()
    w, stop_bar = engine.winner_weights(D)
    i0 = engine.bt.start_index(D.ts, engine.START10)
    raw = engine.fastsim.fast_sim(D.op[i0:], D.cl[i0:], w[i0:], slippage_bps=1.0)
    eq = raw["equity"]
    print(f"winner 10y CAGR {((eq[-1]/eq[0])**(252*390/len(eq))-1)*100:.2f}%")
    idx = D.ts[i0:]
    dts = pd.Series(eq, index=idx).groupby(idx.date).last()
    dret = dts.pct_change()

    # per-day features aligned to the same days
    days = np.array([d for d in dts.index])
    pos = {d: k for k, d in enumerate(D.dates[D.first])}

    f = pd.DataFrame(index=pd.Index(days))
    for name in ("rvol_day", "qc", "qo", "tc", "to"):
        f[name] = [getattr(D, name)[pos[d]] for d in days]
    f["dev_close"] = [D.dev_q[pos[d], 359] for d in days]
    f["rvol_close"] = [D.rvol_cum_q[pos[d], 359] for d in days]
    f["reg"] = [D.reg[pos[d]] for d in days]
    f["ret"] = dret.to_numpy()
    f["ov"] = [D.fwd_open_return()[pos[d]] for d in days]

    print("worst 20 strategy days (10y, 1bp):")
    cols = ["ret", "ov", "rvol_day", "rvol_close", "dev_close", "reg"]
    print(f.sort_values("ret").head(20)[cols].to_string(
        formatters={c: (lambda x: f"{x*100:7.2f}%") for c in
                    ("ret", "ov", "dev_close")},
        float_format=lambda x: f"{x:6.2f}"))

    print("\nmean strategy day return by rvol_day bucket (within risk-on days):")
    sub = f[f["reg"] & f["rvol_day"].notna()]
    e = sub["rvol_day"].quantile([0, .2, .4, .6, .8, 1.0]).to_numpy()
    b = pd.cut(sub["rvol_day"], bins=np.unique(e), include_lowest=True)
    g = sub.groupby(b, observed=True).agg(n=("ret", "size"), mean_ret=("ret", "mean"),
                                          mean_ov=("ov", "mean"),
                                          worst=("ret", "min"))
    g["mean_ret"] *= 100
    g["mean_ov"] *= 100
    g["worst"] *= 100
    print(g.to_string())

    print("\nrvol -> overnight by era (risk-on):")
    for lab, a, bnd in (("2017-2019", "2017-01-01", "2020-01-01"),
                        ("2020-2021", "2020-01-01", "2022-01-01"),
                        ("2022-2026", "2022-01-01", "2027-01-01")):
        s = f[(f.index >= pd.Timestamp(a).date()) & (f.index < pd.Timestamp(bnd).date())
              & f["reg"] & f["rvol_day"].notna()]
        if len(s) < 50:
            continue
        hi = s[s["rvol_day"] > 1.5]
        lo = s[s["rvol_day"] <= 1.5]
        print(f"  {lab}: n_hi={len(hi):3d} ov_hi {hi['ov'].mean()*100:+6.2f}% "
              f"n_lo={len(lo):4d} ov_lo {lo['ov'].mean()*100:+6.2f}% "
              f"spread {(hi['ov'].mean()-lo['ov'].mean())*100:+6.2f}%")

    print("\n5y window only (2021-10-25+): rvol>1.5 overnight")
    s = f[(f.index >= pd.Timestamp("2021-10-25").date()) & f["reg"] & f["rvol_day"].notna()]
    hi = s[s["rvol_day"] > 1.5]
    print(f"  n={len(hi)} mean {hi['ov'].mean()*100:+.3f}% med {hi['ov'].median()*100:+.3f}% "
          f"win {100*(hi['ov']>0).mean():.1f}%")
    print(f"  all risk-on: n={len(s)} mean {s['ov'].mean()*100:+.3f}%")

    # how much of the 10y DD is in each era
    peak = np.maximum.accumulate(eq)
    dd = eq / peak - 1
    print(f"\nmax DD {dd.min()*100:.2f}% at {idx[dd.argmin()]}")
    print("worst 10 daily-mark drawdowns:")
    dpeak = np.maximum.accumulate(dts.to_numpy())
    ddd = dts.to_numpy() / dpeak - 1
    order = np.argsort(ddd)[:5]
    for j in order:
        print(f"   {days[j]}  dd {ddd[j]*100:6.2f}%")


if __name__ == "__main__":
    main()
