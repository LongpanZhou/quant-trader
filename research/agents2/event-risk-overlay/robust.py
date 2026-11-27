"""Robustness: randomisation for the OpEx set, timing windows, t-stats."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "research"))
sys.path.insert(0, str(HERE))
import cal  # noqa: E402
from explore import load_panel, baseline  # noqa: E402


def sess(eq, yrs):
    return eq[-1] ** (1 / yrs) - 1, -(eq / np.maximum.accumulate(eq) - 1).min()


def main():
    ts, opens, highs, lows, closes, vols = load_panel()
    w0, meta = baseline(ts, opens, closes)
    dates = meta["dates"][meta["first"]]
    first, last = meta["first"], meta["last"]
    n = len(dates)
    on = meta["risk_on"].copy()
    ron = np.full(n, np.nan); rit = np.full(n, np.nan); riq = np.full(n, np.nan)
    for k in range(1, n):
        f, l = first[k], last[k]
        ron[k] = opens[f, 1] / closes[last[k - 1], 1] - 1
        rit[k] = closes[l, 1] / opens[f, 1] - 1
        riq[k] = closes[l, 0] / opens[f, 0] - 1
    df = pd.DataFrame({"date": dates, "on": on, "ron": ron, "rit": rit, "riq": riq}).iloc[1:]
    df = df[df["date"] >= pd.Timestamp("2017-01-03").date()].reset_index(drop=True)
    yrs = (df["date"].iloc[-1] - df["date"].iloc[0]).days / 365.25
    onv = df["on"].to_numpy()

    def curve(swap):
        r = np.where(onv, (1 + df["ron"].to_numpy()) * (1 + np.where(swap, df["riq"].to_numpy(), df["rit"].to_numpy())) - 1, 0.0)
        return np.cumprod(1 + r)

    opex = set(cal.opex_dates(2016, 2027))
    fomc = set(cal.FOMC_DATES)
    rt = df["rit"].to_numpy(); rq = df["riq"].to_numpy()
    lt, lq = np.log1p(rt), np.log1p(rq)

    print("intraday (o2c) t-stats, risk-on sessions")
    for name, s in (("opex", opex), ("fomc", fomc), ("cpi", set(cal.CPI_DATES)),
                    ("nfp", set(cal.NFP_DATES)), ("preh", set(cal.pre_holiday_dates(2016, 2027)))):
        m = df["date"].isin(s).to_numpy() & onv
        g = lq[m] - lt[m]
        t = g.mean() / (g.std(ddof=1) / np.sqrt(m.sum()))
        print(f"  {name:5s} n={m.sum():3d} swap gain mean {g.mean()*1e4:7.1f} bp  sd {g.std()*1e4:6.1f}  t={t:5.2f}  "
              f"hit {(g>0).mean()*100:4.0f}%")

    print("\nrandomisation, OpEx-sized set (n=%d risk-on)" % (df["date"].isin(opex).to_numpy() & onv).sum())
    base = sess(curve(np.zeros(len(df), bool)), yrs)
    k = int((df["date"].isin(opex).to_numpy() & onv).sum())
    rng = np.random.default_rng(3)
    idx = np.flatnonzero(onv)
    out = np.array([sess(curve(np.isin(np.arange(len(df)), rng.choice(idx, k, replace=False))), yrs) for _ in range(600)])
    tgt = sess(curve(df["date"].isin(opex).to_numpy() & onv), yrs)
    print(f"  baseline {base[0]*100:.2f}%/{base[1]*100:.2f}%   opex {tgt[0]*100:.2f}%/{tgt[1]*100:.2f}%")
    for i, nm in enumerate(("CAGR", "DD")):
        q = np.percentile(out[:, i], [5, 50, 95])
        print(f"  {nm:4s} random p5 {q[0]*100:6.2f} p50 {q[1]*100:6.2f} p95 {q[2]*100:6.2f}  | opex {tgt[i]*100:6.2f}  pctile {(out[:,i]<tgt[i]).mean()*100:5.1f}")

    # --- how much of the OpEx gain is 2020?
    print("\nOpEx effect by sub-period (intraday swap, %/yr contribution):")
    for lab, lo, hi in (("2017-2019", "2017-01-01", "2019-12-31"), ("2020-2022", "2020-01-01", "2022-12-31"),
                        ("2023-2026", "2023-01-01", "2026-12-31")):
        m = df["date"].isin(opex).to_numpy() & onv & (df["date"] >= pd.Timestamp(lo).date()) & (df["date"] <= pd.Timestamp(hi).date())
        g = (lq[m] - lt[m]).sum()
        nd = ((df["date"] >= pd.Timestamp(lo).date()) & (df["date"] <= pd.Timestamp(hi).date())).sum() / 252
        print(f"  {lab}  n={m.sum():3d}  total {g*100:7.2f}%  ~{((np.exp(g))**(1/nd)-1)*100:6.2f}%/yr")

    # --- timing window sensitivity (mean o2c of TQQQ on opex, by exit time)
    print("\nOpEx intraday path robustness: mean TQQQ return from open to T on opex vs other days (bp)")
    tod = np.array([t.hour * 60 + t.minute for t in ts])
    for T in (600, 660, 720, 780, 840, 930, 959):
        vals_e, vals_n = [], []
        for k2, d in enumerate(dates):
            if d < pd.Timestamp("2017-01-03").date():
                continue
            f, l = first[k2], last[k2]
            m = tod[f:l + 1]
            j = np.searchsorted(m, T)
            if j >= len(m):
                j = len(m) - 1
            r = closes[f + j, 1] / opens[f, 1] - 1
            (vals_e if d in opex else vals_n).append(r)
        print(f"  09:30->{T//60:02d}:{T%60:02d}  opex {np.mean(vals_e)*1e4:7.1f}  other {np.mean(vals_n)*1e4:7.1f}  "
              f"diff {(np.mean(vals_e)-np.mean(vals_n))*1e4:7.1f}")


if __name__ == "__main__":
    main()
