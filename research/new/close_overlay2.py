"""Close-location overlays with QQQ / partial-TQQQ de-risk sleeves."""
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

START, END = "2016-01-04", "2026-10-23"
BPY = 252 * 390


def qqq_daily(dates):
    p = ROOT / "data" / "intraday-hf" / "QQQ-1d-yahoo.parquet"
    df = pd.read_parquet(p)
    df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None).dt.normalize()
    s = df.set_index("date")["adjclose"].astype(float).sort_index()
    s = s[~s.index.duplicated(keep="last")]
    return s.reindex(pd.DatetimeIndex(dates)).ffill()


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
    t = w[last].copy()

    qqq = qqq_daily(sess)
    ret = qqq.pct_change()
    vix = external.align(ts, ["^VIX"])["^VIX"].reindex(sess).ffill()
    filters = {}
    for n in (100, 150, 200):
        ma = qqq.rolling(n, min_periods=max(20, n // 2)).mean()
        filters[f"ma{n}"] = (qqq < ma).to_numpy()
    vol = ret.rolling(20, min_periods=10).std()
    filters["vol90"] = (vol > vol.rolling(252, min_periods=120).quantile(0.9)).to_numpy()
    peak = qqq.rolling(252, min_periods=60).max()
    filters["dd15"] = ((qqq / peak - 1) < -0.15).to_numpy()
    filters["vix25"] = (vix > 25).to_numpy()
    filters["ma200_or_vol90"] = filters["ma200"] | filters["vol90"]
    filters["ma200_or_vix25"] = filters["ma200"] | filters["vix25"]

    sleeves = {
        "bil": np.array([0.0, 0.0, 1.0]),
        "qqq": np.array([1.0, 0.0, 0.0]),
        "half_qqq": np.array([0.5, 0.0, 0.5]),
        "t25_q75": np.array([0.75, 0.25, 0.0]),
        "t50_q50": np.array([0.5, 0.5, 0.0]),
        "t75_q25": np.array([0.25, 0.75, 0.0]),
    }

    rows = []
    for name, off in filters.items():
        for sname, sleeve in sleeves.items():
            t2 = t.copy()
            t2[np.asarray(off, bool)] = sleeve
            w2 = external.daily_targets_to_weights(ts, t2)
            r = bt.run(ts, o, c, w2, START, band=0.02, slippage_bps=1.0)
            s = bt.stats(r, BPY)
            rows.append({"filter": name, "sleeve": sname, **{k: float(v) for k, v in s.items()}})

    rows.sort(key=lambda x: -x["cagr"] / max(x["max_drawdown"], 1e-9))
    print(f"{'filter':18s} {'sleeve':10s} {'CAGR':>8s} {'DD':>8s} {'Sharpe':>7s} {'CAGR/DD':>8s} {'beat':>5s}")
    for r in rows[:25]:
        beat = r["cagr"] > 0.6221 and r["max_drawdown"] < 0.3665
        print(f"{r['filter']:18s} {r['sleeve']:10s} {r['cagr']*100:7.2f}% "
              f"{r['max_drawdown']*100:7.2f}% {r['sharpe']:7.2f} "
              f"{r['cagr']/max(r['max_drawdown'],1e-9):8.2f} {str(beat):>5s}")
    beat = [r for r in rows if r["cagr"] > 0.6221 and r["max_drawdown"] < 0.3665]
    print("BEATERS", len(beat))
    (ROOT / "research/new/close_overlay2_results.json").write_text(json.dumps(rows, indent=1))


if __name__ == "__main__":
    main()
