"""Valid regime switch using the actual minute weights of both strategies."""
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


def qqq_daily(dates):
    p = ROOT / "data" / "intraday-hf" / "QQQ-1d-yahoo.parquet"
    df = pd.read_parquet(p)
    df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None).dt.normalize()
    s = df.set_index("date")["adjclose"].astype(float).sort_index()
    s = s[~s.index.duplicated(keep="last")]
    return s.reindex(pd.DatetimeIndex(dates)).ffill()


def weights(slug, ts, o, c):
    m = R.load(slug)
    out = R.build_full(m, ts, o, c)
    w = out[0] if isinstance(out, tuple) else out
    w = np.asarray(w, float)
    if w.shape[1] == 2:
        w = R.tqqq_bil_to_three(w, len(ts))
    return w


def daily_stats(r):
    s = pd.Series(r["equity"], index=pd.to_datetime(r["ts"]))
    if s.index.tz is not None:
        s.index = s.index.tz_localize(None)
    d = s.groupby(s.index.normalize()).last()
    ret = d.pct_change().dropna()
    years = len(d) / 252
    cagr = (d.iloc[-1] / d.iloc[0]) ** (1 / years) - 1
    dd = abs(float((d / d.cummax() - 1).min()))
    sharpe = float(ret.mean() / ret.std() * np.sqrt(252)) if ret.std() > 0 else 0.0
    return {"cagr": float(cagr), "max_drawdown": dd, "sharpe": sharpe,
            "fills": int(r["fills"])}


def main():
    ts, o, c = bt.panel(("QQQ", "TQQQ", "BIL"), START, END, "1min", warmup_days=0)
    dates, first, last = bt.day_bounds(ts)
    sess = pd.DatetimeIndex(dates[first]).tz_localize(None).normalize()
    wc = weights("family-close-location", ts, o, c)
    wr = weights("ratio-froth", ts, o, c)
    qqq = qqq_daily(sess)
    ret = qqq.pct_change()
    vix = external.align(ts, ["^VIX"])["^VIX"].reindex(sess).ffill()

    rules = {}
    for n in (100, 150, 200):
        ma = qqq.rolling(n, min_periods=max(20, n // 2)).mean()
        rules[f"ma{n}"] = (qqq < ma).to_numpy()
    for v in (20, 25, 30):
        rules[f"vix{v}"] = (vix > v).to_numpy()
    vol = ret.rolling(20, min_periods=10).std()
    rules["vol90"] = (vol > vol.rolling(252, min_periods=120).quantile(0.9)).to_numpy()
    peak = qqq.rolling(252, min_periods=60).max()
    rules["dd10"] = ((qqq / peak - 1) < -0.10).to_numpy()
    rules["dd15"] = ((qqq / peak - 1) < -0.15).to_numpy()
    rules["ma200_or_vol90"] = rules["ma200"] | rules["vol90"]
    rules["ma150_or_vix25"] = rules["ma150"] | rules["vix25"]
    rules["ma200_or_vix25"] = rules["ma200"] | rules["vix25"]

    rows = []
    for name, stress in rules.items():
        st = np.asarray(stress, bool)
        w = wc.copy()
        for j in range(1, len(first)):
            if st[j - 1]:
                a, b = int(first[j]), int(last[j])
                w[a:b + 1] = wr[a:b + 1]
        r = bt.run(ts, o, c, w, START, band=0.02, slippage_bps=1.0)
        rows.append({"rule": name, **daily_stats(r)})
    for name, w in (("close", wc), ("ratio", wr)):
        r = bt.run(ts, o, c, w, START, band=0.02, slippage_bps=1.0)
        rows.append({"rule": name, **daily_stats(r)})

    rows.sort(key=lambda x: -x["cagr"] / max(x["max_drawdown"], 1e-9))
    print(f"{'rule':24s} {'CAGR':>8s} {'DD':>8s} {'Sharpe':>7s} {'CAGR/DD':>8s} {'beat_both':>9s}")
    for r in rows:
        beat = r["cagr"] > 0.6221 and r["max_drawdown"] < 0.3665
        print(f"{r['rule']:24s} {r['cagr']*100:7.2f}% {r['max_drawdown']*100:7.2f}% "
              f"{r['sharpe']:7.2f} {r['cagr']/max(r['max_drawdown'],1e-9):8.2f} {str(beat):>9s}")
    (ROOT / "research/new/close_switch2_results.json").write_text(json.dumps(rows, indent=1))


if __name__ == "__main__":
    main()
