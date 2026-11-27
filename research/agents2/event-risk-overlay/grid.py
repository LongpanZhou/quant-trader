"""Final variant grid: OpEx overlay + combinations, rolling 3y, yearly, costs."""
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
from explore import load_panel, baseline  # noqa: E402
from variants import overlay, metrics  # noqa: E402

START10, END = "2017-01-03", "2026-10-23"


def daily_marks(s):
    eq = pd.Series(s["equity"], index=s["ts"])
    return eq.groupby(eq.index.date).last()


def rolling3(s, years=3):
    """CAGR / maxDD over every rolling `years`-year window, daily marks."""
    deq = daily_marks(s)
    out = []
    d0 = deq.index[0]
    end = deq.index[-1]
    start = d0
    while True:
        stop = pd.Timestamp(start) + pd.DateOffset(years=years)
        if stop.date() > end:
            break
        w = deq[(deq.index >= start) & (deq.index < stop.date())]
        if len(w) > 200:
            yrs = (pd.Timestamp(w.index[-1]) - pd.Timestamp(w.index[0])).days / 365.25
            cagr = (w.iloc[-1] / w.iloc[0]) ** (1 / yrs) - 1
            dd = -(w / w.cummax() - 1).min()
            out.append((str(start), cagr, dd))
        start = (pd.Timestamp(start) + pd.DateOffset(months=3)).date()
    return out


def main():
    ts, opens, highs, lows, closes, vols = load_panel()
    w0, meta = baseline(ts, opens, closes)
    opex = set(cal.opex_dates(2016, 2027))
    fomc = set(cal.FOMC_DATES)

    cfgs = {
        "baseline": None,
        "opex-bil": dict(events=opex, asset="bil", frac=0.0),
        "opex-qqq": dict(events=opex, asset="qqq", frac=0.0),
        "opex-half": dict(events=opex, asset="bil", frac=0.5),
        "opex+fomc-bil": dict(events=opex | fomc, asset="bil", frac=0.0),
    }
    res = {}
    for name, kw in cfgs.items():
        w = w0 if kw is None else overlay(ts, w0, meta, **kw)[0]
        row = {}
        for start, tag in ((START10, "10y"), ("2021-10-25", "5y")):
            s = metrics(ts, opens, closes, w, start)
            row[tag] = s
        res[name] = (w, row)
        print(f"{name:16s} 10y {row['10y']['cagr']*100:6.2f}/{row['10y']['max_drawdown']*100:5.2f} "
              f"({row['10y']['sharpe']:.2f})  5y {row['5y']['cagr']*100:6.2f}/{row['5y']['max_drawdown']*100:5.2f} "
              f"({row['5y']['sharpe']:.2f})  fills {row['10y']['fills']}")

    print("\n--- daily-mark drawdown ---")
    for name in cfgs:
        a = daily_marks(res[name][1]["10y"]); b = daily_marks(res[name][1]["5y"])
        print(f"{name:16s} 10y {-(a/a.cummax()-1).min()*100:5.2f}   5y {-(b/b.cummax()-1).min()*100:5.2f}")

    print("\n--- rolling 3y (daily marks): CAGR / DD, count of windows ---")
    base_r3 = rolling3(res["baseline"][1]["10y"])
    for name in cfgs:
        r3 = rolling3(res[name][1]["10y"])
        wins = sum(1 for (b, r) in zip(base_r3, r3) if r[1] > b[1] and r[2] < b[2])
        print(f"{name:16s} n={len(r3):2d} meanCAGR {np.mean([x[1] for x in r3])*100:5.1f}% "
              f"worstDD {max(x[2] for x in r3)*100:5.1f}%  beats baseline on both in {wins}/{len(r3)}")

    print("\n--- yearly (1bp) ---")
    yrs = sorted(res["baseline"][1]["10y"]["yearly"])
    hdr = "year  " + "".join(f"{n[:11]:>12s}" for n in cfgs)
    print(hdr)
    for y in yrs:
        line = f"{y}  "
        for n in cfgs:
            line += f"{res[n][1]['10y']['yearly'][y]['strategy']*100:11.1f}%"
        print(line)

    print("\n--- cost grid ---")
    for name in ("opex-bil", "opex-qqq", "opex-half", "opex+fomc-bil"):
        w = res[name][0]
        for slip in (1.0, 5.0, 10.0):
            a = bt.stats(bt.run(ts, opens, closes, w, START10, band=0.02, slippage_bps=slip), 252 * 390)
            b = bt.stats(bt.run(ts, opens, closes, w, "2021-10-25", band=0.02, slippage_bps=slip), 252 * 390)
            print(f"{name:16s} {slip:4.0f}bp  10y {a['cagr']*100:6.2f}/{a['max_drawdown']*100:5.2f}  "
                  f"5y {b['cagr']*100:6.2f}/{b['max_drawdown']*100:5.2f}")


if __name__ == "__main__":
    main()
