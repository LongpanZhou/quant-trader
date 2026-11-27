"""Correct accounting: the overlay only replaces the INTRADAY leg.

Harness weights are set at bar i and filled at open(i+1).  A session-level
'out intraday' overlay keeps TQQQ over the night (close->open) and holds the
de-risk asset from 09:31 to 15:59.  So the session return is
    (1 + r_overnight_tqqq) * (1 + r_intraday_derisk) - 1
and the swap gain is log(1+r_intraday_q) - log(1+r_intraday_tqqq).
"""
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

START10 = "2017-01-03"


def sess_stats(eq, yrs):
    return eq[-1] ** (1 / yrs) - 1, -(eq / np.maximum.accumulate(eq) - 1).min()


def main():
    ts, opens, highs, lows, closes, vols = load_panel()
    w0, meta = baseline(ts, opens, closes)
    dates = meta["dates"][meta["first"]]
    first, last = meta["first"], meta["last"]
    n = len(dates)

    on = np.r_[False, meta["risk_on"][1:]]
    ron = np.full(n, np.nan)     # overnight TQQQ close->open
    rit = np.full(n, np.nan)     # intraday TQQQ open->close
    riq = np.full(n, np.nan)     # intraday QQQ
    for k in range(1, n):
        f, l = first[k], last[k]
        ron[k] = opens[f, 1] / closes[last[k - 1], 1] - 1
        rit[k] = closes[l, 1] / opens[f, 1] - 1
        riq[k] = closes[l, 0] / opens[f, 0] - 1
    df = pd.DataFrame({"date": dates, "on": on, "ron": ron, "rit": rit, "riq": riq,
                       "rb": np.r_[np.nan, closes[last, 2][1:] / closes[last, 2][:-1] - 1]}).iloc[1:]
    df = df[df["date"] >= pd.Timestamp(START10).date()].reset_index(drop=True)
    yrs = (df["date"].iloc[-1] - df["date"].iloc[0]).days / 365.25
    onv = df["on"].to_numpy()

    def curve(swap):
        r = np.where(onv, (1 + df["ron"].to_numpy()) * (1 + np.where(swap, df["riq"].to_numpy(), df["rit"].to_numpy())) - 1,
                     df["rb"].to_numpy())
        return np.cumprod(1 + r)

    ev = (set(cal.FOMC_DATES) | set(cal.CPI_DATES) | set(cal.NFP_DATES)
          | set(cal.opex_dates(2016, 2027)) | set(cal.pre_holiday_dates(2016, 2027)))
    none = np.zeros(len(df), bool)
    b = sess_stats(curve(none), yrs)
    print(f"sessions {len(df)} risk-on {onv.sum()} yrs {yrs:.2f}")
    print(f"proxy (no stop) baseline: CAGR {b[0]*100:.2f}%  DD {b[1]*100:.2f}%")

    print("\nintraday swap TQQQ->QQQ, risk-on sessions only:")
    sub = df[onv]
    lt = np.log1p(sub["rit"].to_numpy()); lq = np.log1p(sub["riq"].to_numpy())
    for name, s in (("fomc", set(cal.FOMC_DATES)), ("cpi", set(cal.CPI_DATES)),
                    ("nfp", set(cal.NFP_DATES)), ("opex", set(cal.opex_dates(2016, 2027))),
                    ("preh", set(cal.pre_holiday_dates(2016, 2027))), ("all", ev)):
        m = sub["date"].isin(s).to_numpy()
        g = lq[m] - lt[m]
        print(f"  {name:5s} n={m.sum():3d}  TQQQ o2c {lt[m].mean()*1e4:7.1f} bp  QQQ o2c {lq[m].mean()*1e4:7.1f} bp  "
              f"gain {g.sum()*100:7.2f}% total = {((np.exp(g.sum()))**(1/yrs)-1)*100:6.2f}%/yr")

    allmask = df["date"].isin(ev).to_numpy() & onv
    s_all = sess_stats(curve(allmask), yrs)
    print(f"\nall-event intraday de-risk (no stop): CAGR {s_all[0]*100:.2f}% ({100*(s_all[0]-b[0]):+.2f}pp)  "
          f"DD {s_all[1]*100:.2f}% ({100*(s_all[1]-b[1]):+.2f}pp)")
    only_o = df["date"].isin(set(cal.opex_dates(2016, 2027))).to_numpy() & onv
    s_o = sess_stats(curve(only_o), yrs)
    print(f"opex-only intraday de-risk (no stop): CAGR {s_o[0]*100:.2f}% ({100*(s_o[0]-b[0]):+.2f}pp)  "
          f"DD {s_o[1]*100:.2f}% ({100*(s_o[1]-b[1]):+.2f}pp)")

    # randomisation on the same k
    rng = np.random.default_rng(11)
    idx = np.flatnonzero(onv)
    out = []
    for k in range(400):
        m = np.zeros(len(df), bool)
        m[rng.choice(idx, size=int(allmask.sum()), replace=False)] = True
        out.append(sess_stats(curve(m), yrs))
    out = np.array(out)
    print(f"\nrandom {int(allmask.sum())}-session intraday de-risk (400 draws):")
    for i, nm in enumerate(("CAGR", "DD")):
        q = np.percentile(out[:, i], [1, 5, 50, 95, 99])
        print(f"  {nm:5s} p1 {q[0]*100:6.2f} p5 {q[1]*100:6.2f} p50 {q[2]*100:6.2f} p95 {q[3]*100:6.2f} p99 {q[4]*100:6.2f}"
              f"  | event {s_all[i]*100:6.2f}  pctile {(out[:,i] < s_all[i]).mean()*100:5.1f}")


if __name__ == "__main__":
    main()
