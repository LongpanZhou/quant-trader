"""Trend/VIX regime switch: close-location in calm, ratio-froth in stress.

Calm = QQQ above its 150-session moving average AND VIX <= 25.
Stress = either condition fails; use ratio-froth's weights for that session.
The regime is measured at the prior session close, so execution is causal.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "research"))
sys.path.insert(0, str(ROOT / "research" / "strategies"))
import bt  # noqa: E402
import external  # noqa: E402
import run_holdout as R  # noqa: E402

DEV_START, DEV_END = "2016-01-04", "2023-12-29"
BPY = 252 * 390
OUT = Path(__file__).resolve().parent
PARAMS = dict(ma=150, vix=25.0)


def _qqq_daily(dates):
    p = ROOT / "data" / "intraday-hf" / "QQQ-1d-yahoo.parquet"
    df = pd.read_parquet(p)
    df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None).dt.normalize()
    s = df.set_index("date")["adjclose"].astype(float).sort_index()
    s = s[~s.index.duplicated(keep="last")]
    return s.reindex(pd.DatetimeIndex(dates)).ffill()


def _weights(slug, ts, o, c):
    m = R.load(slug)
    out = R.build_full(m, ts, o, c)
    w = out[0] if isinstance(out, tuple) else out
    w = np.asarray(w, float)
    if w.shape[1] == 2:
        w = R.tqqq_bil_to_three(w, len(ts))
    return w


def build_weights(ts, o, c, params=None):
    p = dict(PARAMS)
    if params:
        p.update(params)
    wc = _weights("family-close-location", ts, o, c)
    wr = _weights("ratio-froth", ts, o, c)
    dates, first, last = bt.day_bounds(ts)
    sess = pd.DatetimeIndex(dates[first]).tz_localize(None).normalize()
    qqq = _qqq_daily(sess)
    ma = qqq.rolling(int(p["ma"]), min_periods=max(20, int(p["ma"]) // 2)).mean()
    vix = external.align(ts, ["^VIX"])["^VIX"].reindex(sess).ffill()
    stress = ((qqq < ma) | (vix > float(p["vix"]))).to_numpy()
    w = wc.copy()
    for j in range(1, len(first)):
        if bool(stress[j - 1]):
            a, b = int(first[j]), int(last[j])
            w[a:b + 1] = wr[a:b + 1]
    info = {"params": p, "stress_share": float(stress.mean()),
            "switches": int((np.diff(stress.astype(int)) != 0).sum())}
    return w, info


def run(w, ts, o, c, bps):
    r = bt.run(ts, o, c, w, DEV_START, band=0.02, slippage_bps=bps)
    s = bt.stats(r, BPY)
    return {k: float(s[k]) for k in ("cagr", "max_drawdown", "sharpe", "sortino",
                                     "volatility", "exposure", "turnover", "fills",
                                     "ending_equity", "years")}


def main():
    ts, o, c = bt.panel(("QQQ", "TQQQ", "BIL"), DEV_START, DEV_END, "1min", warmup_days=0)
    w, info = build_weights(ts, o, c)
    out = {"slug": "family-regime-switch", "family": "regime-switch",
           "idea": "Close-location in calm, ratio-froth in stress.",
           "window": {"dev": [DEV_START, DEV_END], "holdout": "not loaded"},
           "params": info["params"], "info": info,
           "dev": {f"{b}bp": run(w, ts, o, c, b) for b in (1, 5, 10)},
           "grid": []}
    for ma in (100, 150, 200):
        for vix in (20.0, 25.0, 30.0):
            ww, ii = build_weights(ts, o, c, dict(ma=ma, vix=vix))
            out["grid"].append({"ma": ma, "vix": vix, "switches": ii["switches"],
                                **run(ww, ts, o, c, 1)})
    (OUT / "result.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    s = out["dev"]["1bp"]
    print(f"family-regime-switch dev {s['cagr']*100:.2f}% CAGR "
          f"{s['max_drawdown']*100:.2f}% DD {s['sharpe']:.2f} Sharpe "
          f"fills {int(s['fills'])}")


if __name__ == "__main__":
    main()
