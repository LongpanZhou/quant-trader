"""Dev-only grid: morning length x vol skip threshold, sub-periods, DD windows."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402
from explore import Days, build, load_dev, weights_from_positions, daily_returns, BARS  # noqa: E402

pd.set_option("display.width", 240)
DEV_START = "2016-01-04"


def ddwin(ts, eq):
    peak = np.maximum.accumulate(eq)
    dd = eq / peak - 1
    j = int(np.argmin(dd)); i = int(np.argmax(eq[:j + 1]))
    return f"{str(ts[i])[:10]}..{str(ts[j])[:10]}"


def stats_sub(ts, eq, a, b):
    s = pd.Series(eq, index=ts)
    m = (s.index >= pd.Timestamp(a, tz="America/New_York")) & (s.index < pd.Timestamp(b, tz="America/New_York"))
    x = s[m].to_numpy()
    yrs = (s.index[m][-1] - s.index[m][0]).days / 365.25
    peak = np.maximum.accumulate(x)
    return (x[-1] / x[0]) ** (1 / yrs) - 1, -(x / peak - 1).min()


def main():
    ts, o, c = load_dev()
    d = Days(ts, o, c)
    vol = d.vol(20, 0)
    g = d.sma_gate_165()
    p_t = np.zeros(len(ts)); p_b = np.zeros(len(ts))
    for k in range(d.nd):
        f, l = d.first[k], d.last[k]
        p_t[f:l + 1] = 1.0 if g[k] else 0.0
        p_b[f:l + 1] = 0.0 if g[k] else 1.0
    w_base = weights_from_positions(d, p_t, p_b)
    rb = daily_returns(ts, bt.run(ts, o, c, w_base, DEV_START, band=0.02, slippage_bps=1.0)["equity"])

    rows = []
    for m in (0, 30, 60, 90):
        for skip in (0.22, 0.25, 0.28, 0.30, 0.32, 0.35, 0.40, None):
            if m == 0 and skip not in (None, 0.30, 0.35):
                continue
            w = build(d, vol, m=m, vol_skip=skip)
            r = bt.run(ts, o, c, w, DEV_START, band=0.02, slippage_bps=1.0)
            s = bt.stats(r, BARS)
            rd = daily_returns(ts, r["equity"])
            row = {"m": m, "skip": skip if skip else 0,
                   "cagr": s["cagr"] * 100, "dd": s["max_drawdown"] * 100,
                   "sharpe": s["sharpe"], "fills": s["fills"], "corr": rd.corr(rb),
                   "ddwin": ddwin(ts, r["equity"])}
            for tag, a, b in (("s1619", "2016-01-04", "2020-01-01"),
                              ("s2021", "2020-01-01", "2022-01-01"),
                              ("s2223", "2022-01-01", "2023-12-30")):
                cc, dd = stats_sub(ts, r["equity"], a, b)
                row[f"{tag}_c"] = cc * 100
                row[f"{tag}_d"] = dd * 100
            rows.append(row)
            print(f"  m{m:02d} skip{row['skip']:.2f}  {row['cagr']:6.2f}/{row['dd']:5.2f}  "
                  f"Sh {row['sharpe']:4.2f}  corr {row['corr']:.3f}  "
                  f"sub {row['s1619_c']:5.1f}/{row['s1619_d']:4.1f} "
                  f"{row['s2021_c']:5.1f}/{row['s2021_d']:4.1f} "
                  f"{row['s2223_c']:5.1f}/{row['s2223_d']:4.1f}  {row['ddwin']}")
    df = pd.DataFrame(rows)
    df.to_csv(HERE / "grid_dev.csv", index=False)
    print("\npass (corr<0.60) sorted by dev DD:")
    ok = df[df["corr"] < 0.60]
    print(ok.sort_values("dd").head(12).to_string(index=False, float_format=lambda x: f"{x:6.2f}"))


if __name__ == "__main__":
    main()
