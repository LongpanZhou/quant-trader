"""Risk overlays on close-location.

Goal: CAGR > ratio-froth 62.21% and max DD < ratio-froth 36.65%.
Base targets are close-location's daily targets; an overlay replaces the
next-session target with BIL (or scales TQQQ) when the filter is off.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "research"))
sys.path.insert(0, str(ROOT / "research" / "new"))
import bt  # noqa: E402
import external  # noqa: E402
import run_holdout as R  # noqa: E402

BPY = 252 * 390
START, END = "2016-01-04", "2026-10-23"


def qqq_daily(dates):
    p = ROOT / "data" / "intraday-hf" / "QQQ-1d-yahoo.parquet"
    df = pd.read_parquet(p)
    df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None).dt.normalize()
    s = df.set_index("date")["adjclose"].astype(float).sort_index()
    s = s[~s.index.duplicated(keep="last")]
    return s.reindex(pd.DatetimeIndex(dates)).ffill()


def pct_rank_threshold(x, window=252, q=0.9):
    return x.rolling(window, min_periods=120).quantile(q)


def main():
    ts, o, c = bt.panel(("QQQ", "TQQQ", "BIL"), START, END, "1min", warmup_days=0)
    dates, first, last = bt.day_bounds(ts)
    sess = pd.DatetimeIndex(dates[first]).tz_localize(None).normalize()
    m = R.load("family-close-location")
    out = R.build_full(m, ts, o, c)
    w = out[0] if isinstance(out, tuple) else out
    w = np.asarray(w, float)
    if w.shape[1] == 2:
        w = R.tqqq_bil_to_three(w, len(ts))
    t = w[last].copy()  # daily target written at session close
    print("base target rows", t.shape, "TQQQ share", float(t[:, 1].mean()))

    qqq = qqq_daily(sess)
    ret = qqq.pct_change()
    vix = external.align(ts, ["^VIX"])["^VIX"].reindex(sess).ffill()

    filters = {}
    for n in (50, 100, 150, 200):
        ma = qqq.rolling(n, min_periods=max(20, n // 2)).mean()
        filters[f"qqq_ma{n}"] = (qqq < ma).to_numpy()
    for q in (0.80, 0.90, 0.95):
        vol = ret.rolling(20, min_periods=10).std()
        thr = pct_rank_threshold(vol, 252, q)
        filters[f"vol_q{int(q*100)}"] = (vol > thr).to_numpy()
    for dd in (0.10, 0.15, 0.20):
        peak = qqq.rolling(252, min_periods=60).max()
        filters[f"dd_{int(dd*100)}"] = ((qqq / peak - 1) < -dd).to_numpy()
    for v in (20, 25, 30):
        filters[f"vix_{v}"] = (vix > v).to_numpy()
    filters["ma200_or_vol90"] = filters["qqq_ma200"] | filters["vol_q90"]
    filters["ma200_or_vix25"] = filters["qqq_ma200"] | filters["vix_25"]
    filters["dd15_or_vol90"] = filters["dd_15"] | filters["vol_q90"]

    def stats(w2):
        r = bt.run(ts, o, c, w2, START, band=0.02, slippage_bps=1.0)
        s = bt.stats(r, BPY)
        return s

    rows = []
    base = stats(w)
    rows.append(("base", 1.0, base))
    for name, off in filters.items():
        for scale in (0.0, 0.25, 0.5):
            t2 = t.copy()
            idx = np.asarray(off, dtype=bool)
            if scale == 0.0:
                t2[idx] = np.array([0.0, 0.0, 1.0])
            else:
                t2[idx, 1] = t2[idx, 1] * scale
                t2[idx, 2] = 1.0 - t2[idx, 1]
            w2 = external.daily_targets_to_weights(ts, t2)
            s = stats(w2)
            rows.append((name, scale, s))

    rows.sort(key=lambda x: -x[2]["cagr"] / max(x[2]["max_drawdown"], 1e-9))
    print(f"{'filter':22s} {'scale':>5s} {'CAGR':>8s} {'DD':>8s} {'Sharpe':>7s} {'CAGR/DD':>8s} {'fills':>6s} {'beat':>5s}")
    for name, scale, s in rows[:30]:
        beat = s["cagr"] > 0.6221 and s["max_drawdown"] < 0.3665
        print(f"{name:22s} {scale:5.2f} {s['cagr']*100:7.2f}% {s['max_drawdown']*100:7.2f}% "
              f"{s['sharpe']:7.2f} {s['cagr']/max(s['max_drawdown'],1e-9):8.2f} "
              f"{int(s['fills']):6d} {str(beat):>5s}")

    best = [r for r in rows if r[2]["cagr"] > 0.6221 and r[2]["max_drawdown"] < 0.3665]
    print("BEATERS:", len(best))
    for name, scale, s in best:
        print(name, scale, s["cagr"], s["max_drawdown"], s["sharpe"])

    json.dump([{"filter": n, "scale": sc, **{k: float(v) for k, v in s.items()}}
               for n, sc, s in rows], open(ROOT / "research/new/close_overlay_results.json", "w"), indent=1)


if __name__ == "__main__":
    main()
