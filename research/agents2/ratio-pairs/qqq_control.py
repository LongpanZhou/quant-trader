"""Controls: is ratio-extension just QQQ-extension or low volatility?"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bt_lib as L  # noqa: E402


def perf(wt, wq, r, valid):
    wt, wq = wt[valid], wq[valid]
    rt, rq, rb = r["tq"][valid], r["qq"][valid], r["bil"][valid]
    ret = wt * rt + wq * rq + (1 - wt - wq) * rb
    eq = np.cumprod(1 + ret)
    years = len(eq) / 252
    cagr = eq[-1] ** (1 / years) - 1
    peak = np.maximum.accumulate(eq)
    dd = float(-(eq / peak - 1).min())
    sharpe = np.mean(ret) / np.std(ret) * np.sqrt(252)
    return cagr, dd, sharpe


def main():
    ts, opens, closes = L.load_panel()
    d = L.add_ratio_features(L.daily_frame(ts, opens, closes))
    dates, first, last = L.day_bounds(ts)
    nd = len(first)
    o = opens[first]
    r = {
        "tq": np.r_[o[1:, 1] / o[:-1, 1] - 1, np.nan],
        "qq": np.r_[o[1:, 0] / o[:-1, 0] - 1, np.nan],
        "bil": np.r_[o[1:, 2] / o[:-1, 2] - 1, np.nan],
    }
    qqq_c = d["qqq_c"]
    for n in (100, 150, 200, 250):
        d[f"qqq_ext{n}"] = np.log(qqq_c / qqq_c.rolling(n).mean())
    d["realvol20"] = d["logr"].diff().rolling(20).std() * np.sqrt(252)
    d["realvol60"] = d["logr"].diff().rolling(60).std() * np.sqrt(252)

    valid = np.isfinite(r["tq"]) & (d.index >= pd.Timestamp(L.START10))
    ext = {k: d[k].shift(1).to_numpy() for k in d.columns if k.startswith(("ext", "qqq_ext"))}

    print("apples-to-apples: ratio ext200 threshold vs QQQ ext200 at half the threshold")
    for theta in (0.14, 0.16, 0.18, 0.20, 0.22):
        for lab, x in (("ratio", ext["ext200"]), ("qqq", ext["qqq_ext200"])):
            th = theta if lab == "ratio" else theta / 2
            f = (np.nan_to_num(x, nan=-9) > th) & valid
            print(f"  {lab:6s} >{th:5.3f}  n={f.sum():4d}  "
                  f"mean next-day TQQQ {r['tq'][f].mean()*100:+.4f}%  "
                  f"QQQ {r['qq'][f].mean()*100:+.4f}%")

    print("\n2x2 sort on prior-close extensions (TQQQ next-day mean, %/day)")
    q_hi = np.nan_to_num(ext["qqq_ext200"], nan=-9) > 0.09
    r_hi = np.nan_to_num(ext["ext200"], nan=-9) > 0.18
    for a, b, lab in (
        (True, True, "QQQ hi & ratio hi"),
        (True, False, "QQQ hi & ratio lo"),
        (False, True, "QQQ lo & ratio hi"),
        (False, False, "QQQ lo & ratio lo"),
    ):
        m = (q_hi == a) & (r_hi == b) & valid
        if m.sum():
            print(f"  {lab:20s} n={m.sum():4d}  TQQQ {r['tq'][m].mean()*100:+.4f}  "
                  f"QQQ {r['qq'][m].mean()*100:+.4f}  hit {np.mean(r['tq'][m] > 0)*100:4.1f}%")

    print("\nvol-only signal: de-risk when realised vol is LOW (the 'calm before the storm')")
    for q in (0.2, 0.3, 0.5):
        v = d["realvol20"].shift(1)
        thr = v.quantile(q)
        f = (v < thr).to_numpy() & valid
        print(f"  vol20 < q{q:.1f} ({thr*100:.1f}%)  n={f.sum():4d}  "
              f"TQQQ {r['tq'][f].mean()*100:+.4f}%  other {r['tq'][valid & ~f].mean()*100:+.4f}%")

    print("\ndaily-level swap rule (no costs): threshold sweep on each signal")
    for lab, x, ths in (
        ("ext200", ext["ext200"], (0.14, 0.16, 0.18, 0.20, 0.22)),
        ("ext120", ext["ext120"], (0.14, 0.16, 0.18, 0.20, 0.22)),
        ("qqq_ext200", ext["qqq_ext200"], (0.05, 0.07, 0.09, 0.11, 0.13)),
        ("qqq_ext150", ext["qqq_ext150"], (0.05, 0.07, 0.09, 0.11, 0.13)),
    ):
        for th in ths:
            f = np.nan_to_num(x, nan=-9) > th
            c, dd, sh = perf((~f).astype(float), f.astype(float), r, valid)
            print(f"  {lab:10s}>{th:5.2f} -> QQQ  CAGR {c*100:6.2f}  DD {dd*100:5.2f}  Sharpe {sh:4.2f}")

    print("\npermutation test: ext200>0.18 (n per year preserved), 2000 draws")
    f = (np.nan_to_num(ext["ext200"], nan=-9) > 0.18) & valid
    c0, dd0, sh0 = perf((~f).astype(float), f.astype(float), r, valid)
    print(f"  actual      CAGR {c0*100:6.2f}  DD {dd0*100:5.2f}  Sharpe {sh0:4.2f}")
    yrs = d.index.year.to_numpy()
    rng = np.random.default_rng(7)
    idx_by_year = {y: np.flatnonzero((yrs == y) & valid) for y in np.unique(yrs)}
    cs, dds = [], []
    for _ in range(2000):
        g = np.zeros(nd, bool)
        for y, idx in idx_by_year.items():
            k = int((f & (yrs == y)).sum())
            if k:
                g[rng.choice(idx, size=k, replace=False)] = True
        c, dd, _ = perf((~g).astype(float), g.astype(float), r, valid)
        cs.append(c)
        dds.append(dd)
    cs, dds = np.array(cs), np.array(dds)
    print(f"  random p50  CAGR {np.median(cs)*100:6.2f}  p95 {np.percentile(cs,95)*100:6.2f}  "
          f"share >= actual {(cs>=c0).mean()*100:5.1f}%")
    print(f"  random p50  DD   {np.median(dds)*100:6.2f}  p05 {np.percentile(dds,5)*100:6.2f}  "
          f"share <= actual DD {(dds<=dd0).mean()*100:5.1f}%")


if __name__ == "__main__":
    main()
