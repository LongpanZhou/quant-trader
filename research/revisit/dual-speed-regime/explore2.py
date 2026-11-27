"""Standalone 60m EMA rebuild: hysteresis + volatility targeting sweep (dev only)."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402
from explore import (DEV_START, DEV_END, BPY, day_index, bars_60m, ema, map_state,
                     weights_from_state, baseline_165, stats_dev)  # noqa: E402


def hyst_state(fast_ema, slow_ema, band):
    spread = fast_ema / slow_ema - 1.0
    on = False
    out = np.zeros(len(spread), bool)
    for j, s in enumerate(spread):
        if not np.isfinite(s):
            out[j] = False
            continue
        if on:
            if s < -band:
                on = False
        else:
            if s > band:
                on = True
        out[j] = on
    return out


def vol60(bar_close, span):
    r = np.diff(np.log(bar_close), prepend=np.nan)
    sd = pd.Series(r).ewm(span=span, adjust=False, min_periods=10).std().to_numpy()
    return sd * np.sqrt(252 * 6.5)


def map_weight(n, ends, day_of, bar_w, first):
    out = np.ones(n)
    prev = 1.0
    j = 0
    counts = np.bincount(day_of, minlength=len(first))
    for k, f in enumerate(first):
        nb = counts[k]
        out[f:ends[j]] = prev
        for m in range(nb - 1):
            out[ends[j + m]:ends[j + m + 1]] = bar_w[j + m]
        out[ends[j + nb - 1]] = bar_w[j + nb - 1]
        prev = bar_w[j + nb - 1]
        j += nb
    return out


def main():
    ts, opens, closes = bt.panel(("QQQ", "TQQQ", "BIL"), DEV_START, DEV_END, "1min",
                                 warmup_days=500)
    dates, first, last, day_id = day_index(ts)
    ends, bar_close, day_of = bars_60m(closes[:, 0], first, last)
    w_base = baseline_165(ts, closes, first, last, day_id)
    sb, rb = stats_dev(w_base, ts, opens, closes)
    base_daily = pd.Series(rb["equity"], index=rb["ts"]).resample("1D").last().pct_change().dropna()
    print(f"baseline dev {sb['cagr']*100:.2f}/{sb['max_drawdown']*100:.2f}", flush=True)

    pairs = [(10, 30), (15, 45), (10, 60), (20, 60), (20, 100)]
    bands = (0.0, 0.0005, 0.001, 0.002)
    targets = (0.30, 0.40, 0.50, 0.60)
    ws, labels = [], []
    vol_cache = {}
    for fast, slow in pairs:
        ef = ema(bar_close, fast)
        es = ema(bar_close, slow)
        for band in bands:
            st = hyst_state(ef, es, band)
            for vspan in (20, 40):
                if vspan not in vol_cache:
                    vol_cache[vspan] = vol60(bar_close, vspan)
                vol = vol_cache[vspan]
                for target in targets:
                    raw = np.where(np.isfinite(vol), np.minimum(1.0, target / np.maximum(vol, 1e-9)), 1.0)
                    bw = st.astype(float) * raw
                    wq = map_weight(len(ts), ends, day_of, bw, first)
                    w = np.zeros((len(ts), 3))
                    w[:, 1] = wq
                    w[:, 2] = 1.0 - wq
                    ws.append(w)
                    labels.append(f"{fast}/{slow} b{band*1e4:.0f} v{vspan} t{target:.0%}")
    rs = bt.run_many(ts, opens, closes, ws, start=DEV_START, band=0.02, slippage_bps=1.0,
                     threads=8)
    rows = []
    for lab, rr in zip(labels, rs):
        s = bt.stats(rr, BPY)
        a = pd.Series(rr["equity"], index=rr["ts"]).resample("1D").last().pct_change().dropna()
        corr = float(pd.concat([a, base_daily], axis=1, join="inner").dropna().corr().iloc[0, 1])
        rows.append((s["sharpe"], s["cagr"], s["max_drawdown"], s["fills"], corr, lab))
    rows.sort(reverse=True)
    for sh, cg, dd, fl, corr, lab in rows[:30]:
        print(f"{lab:28s} CAGR {cg*100:6.2f} DD {dd*100:5.2f} Sharpe {sh:5.2f} "
              f"fl {fl:5d} corr {corr:.3f}", flush=True)


if __name__ == "__main__":
    main()
