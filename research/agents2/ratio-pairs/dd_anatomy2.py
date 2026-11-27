"""Where does the froth variant's P&L and drawdown come from?"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bt_lib as L  # noqa: E402


def main():
    import bt
    ts, opens, closes = L.load_panel()
    d = L.add_ratio_features(L.daily_frame(ts, opens, closes))
    dates, first, last = L.day_bounds(ts)
    nd = len(first)
    hold, risk_on, _, _ = L.winner_state(ts, opens, closes)
    ext = d["ext200"].shift(1).to_numpy()
    froth = np.nan_to_num(ext, nan=-9) > 0.18

    tgt = np.zeros((nd, 3))
    tgt[risk_on & ~froth, 1] = 1
    tgt[risk_on & froth, 0] = 1
    tgt[~risk_on, 2] = 1
    w = L.weights_from_daily(ts, tgt, first, last, stopped=~hold)
    r = bt.run(ts, opens, closes, w, L.START10, band=0.02, slippage_bps=1.0)
    t = r["ts"]
    eq = pd.Series(r["equity"], index=t)
    deq = eq.groupby(eq.index.date).last()
    deq.index = pd.to_datetime(deq.index)
    dd = deq / deq.cummax() - 1

    under = dd < -0.08
    grp = (under != under.shift()).cumsum()
    eps = []
    for g, seg in dd[under].groupby(grp[under]):
        eps.append((seg.index[0], seg.index[-1], seg.min(), (seg.index[-1] - seg.index[0]).days))
    print("worst drawdown episodes, froth variant")
    for a, b, m, days in sorted(eps, key=lambda x: x[2])[:10]:
        print(f"  {a.date()} -> {b.date()}  dd {m*100:6.2f}%  {days:4d}d")

    print("\nde-risk episodes (consecutive froth days) and what TQQQ did meanwhile")
    # per-day open-to-open returns
    o = opens[first]
    rt = np.r_[o[1:, 1] / o[:-1, 1] - 1, np.nan]
    rq = np.r_[o[1:, 0] / o[:-1, 0] - 1, np.nan]
    ep = []
    k = 0
    while k < nd:
        if froth[k] and risk_on[k]:
            j = k
            while j + 1 < nd and froth[j + 1] and risk_on[j + 1]:
                j += 1
            ep.append((k, j))
            k = j + 1
        else:
            k += 1
    tot_avoid = 0.0
    rows = []
    for a, b in ep:
        seg_t = np.nansum(rt[a:b + 1])
        seg_q = np.nansum(rq[a:b + 1])
        rows.append((d.index[a].date(), d.index[b].date(), b - a + 1, seg_t * 100, seg_q * 100))
        tot_avoid += seg_t
    print(f"  {len(ep)} episodes, total TQQQ return skipped {tot_avoid*100:+.1f}% (sum of daily)")
    for row in sorted(rows, key=lambda x: x[3])[:12]:
        print(f"  {row[0]} -> {row[1]}  {row[2]:3d}d  TQQQ {row[3]:+7.1f}%  QQQ {row[4]:+6.1f}%")
    print("  best 5 (cost of being out):")
    for row in sorted(rows, key=lambda x: -x[3])[:5]:
        print(f"  {row[0]} -> {row[1]}  {row[2]:3d}d  TQQQ {row[3]:+7.1f}%  QQQ {row[4]:+6.1f}%")

    print("\nyearly equity: winner vs froth variant")
    print("  year   winner   froth")
    for y in sorted(set(t.year)):
        m = t.year == y
        if m.sum() < 2:
            continue
        e = r["equity"][m]
        print(f"  {y}  {e[-1]/e[0]-1:8.2%}")


if __name__ == "__main__":
    main()
