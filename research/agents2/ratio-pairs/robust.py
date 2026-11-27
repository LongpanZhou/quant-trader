"""Robustness: parameter surface, rolling windows, costs, episode jackknife."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bt_lib as L  # noqa: E402

OUT = Path(__file__).resolve().parent


def seg_stats(eq, ts, start, end=None):
    m = ts >= pd.Timestamp(start, tz="America/New_York")
    if end:
        m &= ts < pd.Timestamp(end, tz="America/New_York")
    e = eq[m]
    t = ts[m]
    if len(e) < 10:
        return None
    years = (t[-1] - t[0]).total_seconds() / (365.25 * 86400)
    peak = np.maximum.accumulate(e)
    rets = np.diff(e) / e[:-1]
    return {
        "cagr": float((e[-1] / e[0]) ** (1 / years) - 1),
        "dd": float(-(e / peak - 1).min()),
        "sharpe": float(np.mean(rets) / np.std(rets) * np.sqrt(L.BARS)),
    }


def main():
    import bt
    ts, opens, closes = L.load_panel()
    d = L.add_ratio_features(L.daily_frame(ts, opens, closes))
    dates, first, last = L.day_bounds(ts)
    nd = len(first)
    hold, risk_on, _, _ = L.winner_state(ts, opens, closes)

    def weights(froth, asset="QQQ", frac=1.0):
        tgt = np.zeros((nd, 3))
        tgt[risk_on & ~froth, 1] = 1
        if asset == "QQQ":
            tgt[risk_on & froth, 1] = 1 - frac
            tgt[risk_on & froth, 0] = frac
        tgt[~risk_on, 2] = 1
        if asset == "BIL":
            tgt[froth, :] = (0, 0, 1)
        return L.weights_from_daily(ts, tgt, first, last, stopped=~hold)

    def go(w, slip=1.0, start=L.START10):
        r = bt.run(ts, opens, closes, w, start, band=0.02, slippage_bps=slip)
        s = bt.stats(r, L.BARS)
        return r, s

    base = weights(np.zeros(nd, bool))
    rb, sb = go(base)

    rows = []
    print("parameter surface: ext{ma} > theta -> QQQ   (10y / 5y CAGR,DD from one run)")
    print("  ma  theta   n    10y CAGR/DD      5y CAGR/DD")
    for ma in (100, 120, 150, 200, 250):
        ext = d[f"ext{ma}"].shift(1).to_numpy()
        for th in (0.12, 0.14, 0.16, 0.18, 0.20, 0.22, 0.24):
            f = np.nan_to_num(ext, nan=-9) > th
            r, s = go(weights(f))
            s5 = seg_stats(r["equity"], r["ts"], L.START5)
            rows.append({"ma": ma, "theta": th, "n": int(f.sum()),
                         "cagr10": s["cagr"], "dd10": s["max_drawdown"],
                         "cagr5": s5["cagr"], "dd5": s5["dd"]})
            print(f"  {ma:3d}  {th:4.2f} {int(f.sum()):4d}  "
                  f"{s['cagr']*100:6.2f}/{s['max_drawdown']*100:5.2f}   "
                  f"{s5['cagr']*100:6.2f}/{s5['dd']*100:5.2f}")
    pd.DataFrame(rows).to_json(OUT / "surface.json", orient="records", indent=1)

    print("\nrolling 3-year windows (quarterly starts), TQQQ vs winner vs froth QQQ vs froth BIL")
    ext = d["ext200"].shift(1).to_numpy()
    froth = np.nan_to_num(ext, nan=-9) > 0.18
    rq, sq = go(weights(froth, "QQQ"))
    rl, sl = go(weights(froth, "BIL"))
    starts = pd.date_range("2017-01-03", "2023-10-23", freq="QS")
    rec = []
    for st in starts:
        s0 = seg_stats(rb["equity"], rb["ts"], str(st.date()), str((st + pd.DateOffset(years=3)).date()))
        s1 = seg_stats(rq["equity"], rq["ts"], str(st.date()), str((st + pd.DateOffset(years=3)).date()))
        s2 = seg_stats(rl["equity"], rl["ts"], str(st.date()), str((st + pd.DateOffset(years=3)).date()))
        m = (rb["ts"] >= pd.Timestamp(st.date(), tz="America/New_York")) & (
            rb["ts"] < pd.Timestamp((st + pd.DateOffset(years=3)).date(), tz="America/New_York"))
        tq = closes[bt.start_index(ts, L.START10):, 1][m]
        b = bt.benchmark(tq, rb["ts"][m], L.BARS)
        rec.append({"start": str(st.date()),
                    "tqqq_cagr": b["cagr"], "tqqq_dd": b["max_drawdown"],
                    "win_cagr": s0["cagr"], "win_dd": s0["dd"],
                    "fq_cagr": s1["cagr"], "fq_dd": s1["dd"],
                    "fb_cagr": s2["cagr"], "fb_dd": s2["dd"]})
    w = pd.DataFrame(rec)
    print(w.to_string(index=False, float_format=lambda v: f"{v*100:6.2f}" if abs(v) < 5 else f"{v:6.2f}"))
    print(f"\n  froth-QQQ beats TQQQ on CAGR {int((w.fq_cagr > w.tqqq_cagr).sum())}/{len(w)}, "
          f"on DD {int((w.fq_dd < w.tqqq_dd).sum())}/{len(w)}")
    print(f"  froth-QQQ beats winner on CAGR {int((w.fq_cagr > w.win_cagr).sum())}/{len(w)}, "
          f"on DD {int((w.fq_dd < w.win_dd).sum())}/{len(w)}")
    w.to_json(OUT / "rolling3y.json", orient="records", indent=1)

    print("\ncost sensitivity, froth ext200>0.18 -> QQQ")
    for slip in (0.0, 1.0, 5.0, 10.0):
        r, s = go(weights(froth), slip=slip)
        s5 = seg_stats(r["equity"], r["ts"], L.START5)
        print(f"  {slip:4.1f}bp  10y {s['cagr']*100:6.2f}/{s['max_drawdown']*100:5.2f}   "
              f"5y {s5['cagr']*100:6.2f}/{s5['dd']*100:5.2f}")

    print("\nsubsamples")
    for a, b in (("2017-01-03", "2021-12-31"), ("2022-01-01", "2026-10-23")):
        s0 = seg_stats(rb["equity"], rb["ts"], a, b)
        s1 = seg_stats(rq["equity"], rq["ts"], a, b)
        print(f"  {a}..{b}  winner {s0['cagr']*100:6.2f}/{s0['dd']*100:5.2f}   "
              f"froth {s1['cagr']*100:6.2f}/{s1['dd']*100:5.2f}")

    print("\njackknife: switch the froth rule OFF during the top-N avoided episodes")
    o = opens[first]
    rt = np.r_[o[1:, 1] / o[:-1, 1] - 1, np.nan]
    ep, k = [], 0
    while k < nd:
        if froth[k] and risk_on[k]:
            j = k
            while j + 1 < nd and froth[j + 1] and risk_on[j + 1]:
                j += 1
            ep.append((k, j, float(np.nansum(rt[k:j + 1]))))
            k = j + 1
        else:
            k += 1
    ep.sort(key=lambda x: x[2])
    for n_drop in (1, 2, 3, 5):
        f2 = froth.copy()
        for a, b, _ in ep[:n_drop]:
            f2[a:b + 1] = False
        r, s = go(weights(f2))
        s5 = seg_stats(r["equity"], r["ts"], L.START5)
        print(f"  drop {n_drop} worst avoided episodes: 10y {s['cagr']*100:6.2f}/{s['max_drawdown']*100:5.2f}  "
              f"5y {s5['cagr']*100:6.2f}/{s5['dd']*100:5.2f}")
    print("  episodes dropped:", [(str(d.index[a].date()), str(d.index[b].date()), round(v * 100, 1))
                                   for a, b, v in ep[:5]])

    print("\nyearly, froth QQQ vs winner vs TQQQ")
    y0 = bt.yearly(rb["ts"], rb["equity"], closes[bt.start_index(ts, L.START10):, 1])
    y1 = bt.yearly(rq["ts"], rq["equity"], closes[bt.start_index(ts, L.START10):, 1])
    for y in sorted(y0):
        print(f"  {y}  winner {y0[y]['strategy']*100:8.2f}%  froth {y1[y]['strategy']*100:8.2f}%  "
              f"TQQQ {y1[y]['benchmark']*100:9.2f}%")


if __name__ == "__main__":
    main()
