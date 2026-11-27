"""Why does the 5y drawdown move the wrong way?"""
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
from variants import overlay, metrics  # noqa: E402


def dd_info(s):
    eq = pd.Series(s["equity"], index=s["ts"])
    peak = eq.cummax()
    dd = eq / peak - 1
    j = dd.idxmin()
    p = eq[:j].idxmax()
    return eq, dd, p, j


def main():
    ts, opens, highs, lows, closes, vols = load_panel()
    w0, meta = baseline(ts, opens, closes)
    opex = set(cal.opex_dates(2016, 2027))
    w1, _ = overlay(ts, w0, meta, events=opex, asset="bil", frac=0.0)

    for tag, w in (("baseline", w0), ("opex-bil", w1)):
        s = metrics(ts, opens, closes, w, "2021-10-25")
        eq, dd, p, j = dd_info(s)
        print(f"\n{tag}: DD {s['max_drawdown']*100:.2f}% peak {p.date()} (${eq.loc[p]:,.0f}) trough {j.date()} (${eq.loc[j]:,.0f})")
        # top 5 drawdown episodes by depth (daily marks)
        deq = eq.groupby(eq.index.date).last()
        ddd = deq / deq.cummax() - 1
        # find local minima
        roll = ddd.rolling(5, center=True).min()
        mins = ddd[(ddd == roll) & (ddd < -0.10)].sort_values()
        print("  deep episodes:", [(str(k), round(v * 100, 1)) for k, v in mins.head(8).items()])

    # compare daily equity around the 2026 selloff
    a = metrics(ts, opens, closes, w0, "2021-10-25")
    b = metrics(ts, opens, closes, w1, "2021-10-25")
    ea = pd.Series(a["equity"], index=a["ts"]).groupby(a["ts"].date).last()
    eb = pd.Series(b["equity"], index=b["ts"]).groupby(b["ts"].date).last()
    idx = [d for d in ea.index if pd.Timestamp("2026-06-10").date() <= d <= pd.Timestamp("2026-08-05").date()]
    print("\n  date        base$      opex$     ratio")
    for d in idx:
        print(f"  {d}  {ea[d]/1e3:9.1f} {eb[d]/1e3:9.1f}  {eb[d]/ea[d]:.4f}")

    # per-OpEx-day contribution to the 5y window
    print("\nopex days 2021-10..2026-10 (risk-on), TQQQ c2c / o2c:")
    first, last = meta["first"], meta["last"]
    dates = meta["dates"][first]
    for k, d in enumerate(dates):
        if d in opex and d >= pd.Timestamp("2021-10-25").date() and meta["risk_on"][k]:
            f, l = first[k], last[k]
            c2o = opens[f, 1] / closes[last[k - 1], 1] - 1
            o2c = closes[l, 1] / opens[f, 1] - 1
            print(f"   {d}  {c2o*100:6.2f}% {o2c*100:6.2f}%")


if __name__ == "__main__":
    main()
