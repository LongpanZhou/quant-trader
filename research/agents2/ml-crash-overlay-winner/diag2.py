"""Detailed diagnostics for the leading multi-horizon crash overlay."""
from __future__ import annotations

import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402

sys.path.insert(0, str(Path(__file__).parent))
from validate import build  # noqa: E402

START, END = "2017-01-03", "2026-10-23"
BARS = 252 * 390


def daily_eq(r, ts):
    eq = pd.Series(r["equity"], index=ts)
    d = eq.groupby(eq.index.date).last()
    d.index = pd.DatetimeIndex(d.index)
    return d


def yearly_from_daily(d, bench):
    out = {}
    for y in sorted(set(d.index.year)):
        m = d.index.year == y
        if m.sum() < 2:
            continue
        out[y] = (d[m].iloc[-1] / d[m].iloc[0] - 1, bench[m].iloc[-1] / bench[m].iloc[0] - 1)
    return out


def rolling3(d, years=3):
    out = []
    idx = d.index
    for start in pd.date_range(idx[0], idx[-1] - pd.Timedelta(days=365 * years), freq="QE"):
        end = start + pd.Timedelta(days=365 * years)
        seg = d[(d.index >= start) & (d.index <= end)]
        if len(seg) < 200:
            continue
        ret = seg.iloc[-1] / seg.iloc[0] - 1
        cagr = (1 + ret) ** (1 / years) - 1
        peak = np.maximum.accumulate(seg)
        dd = -(seg / peak - 1).min()
        out.append((start.date(), end.date(), cagr, dd))
    return out


def main():
    ts, o, c = bt.panel(("QQQ", "TQQQ", "BIL"), START, END, "1min")
    for tag, horizon, thr, q in (("h20 q90", 20, -0.15, 0.90), ("h20 q80", 20, -0.15, 0.80)):
        w, flag, opened, dts, f, p, rank = build(ts, o, c, horizon, thr, q, "bil")
        print(f"\n===== {tag} =====")
        for lab, st in (("10y", "2017-01-03"), ("5y", "2021-10-25")):
            r = bt.run(ts, o, c, w, st, band=0.02, slippage_bps=1.0)
            s = bt.stats(r, BARS)
            d = daily_eq(r, ts[bt.start_index(ts, st):])
            b = c[bt.start_index(ts, st):, 1]
            btq = pd.Series(b, index=ts[bt.start_index(ts, st):])
            bd = btq.groupby(btq.index.date).last()
            bd.index = pd.DatetimeIndex(bd.index)
            print(f"{lab} 1bp: CAGR {s['cagr']*100:.2f}% DD {s['max_drawdown']*100:.2f}% "
                  f"Sharpe {s['sharpe']:.2f} Sortino {s['sortino']:.2f} vol {s['volatility']*100:.1f}% "
                  f"fills {s['fills']}")
            print("  yearly (strat / tqqq):")
            for y, (a, b2) in yearly_from_daily(d, bd).items():
                print(f"    {y}: {a*100:8.1f}% / {b2*100:8.1f}%")
            if lab == "10y":
                rr = rolling3(d)
                print(f"  rolling 3y: {len(rr)} windows, median CAGR {np.median([x[2] for x in rr])*100:.1f}%, "
                      f"median DD {np.median([x[3] for x in rr])*100:.1f}%, "
                      f"worst DD {max(x[3] for x in rr)*100:.1f}%")

        # flagged-day return diagnostics
        m = dts >= pd.Timestamp("2017-01-03")
        tq = pd.Series(c[:, 1], index=ts)
        tqd = tq.groupby(tq.index.date).last()
        tqd.index = pd.DatetimeIndex(tqd.index)
        fwd = tqd.pct_change().shift(-1)
        fl = flag & opened
        print(f"  flagged {fl[m].sum()} days; mean next-day TQQQ ret "
              f"{fwd[fl & m].mean()*100:+.2f}% vs held {fwd[opened & ~fl & m].mean()*100:+.2f}%")
        print(f"  flagged hit rate (next-day < -2%): {(fwd[fl & m] < -0.02).mean()*100:.1f}% "
              f"vs {(fwd[opened & ~fl & m] < -0.02).mean()*100:.1f}%")


if __name__ == "__main__":
    warnings.filterwarnings("ignore")
    main()
