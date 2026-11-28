"""Ratio froth: does the 4% TQQQ stop on QQQ days matter?

The published rule applies the TQQQ 4%-from-open stop even when the book holds
QQQ on froth days.  A 4% TQQQ move is only ~1.33% QQQ, so the QQQ leg is
effectively stopped at ~1.3%.  This script builds three diagnostics:

  tqqq_stop_on_qqq   published: TQQQ 4% trigger on every risk-on session
  qqq_asset_stop     fair: 4% trigger on the asset actually held (QQQ on froth)
  no_qqq_stop        stop only when holding TQQQ
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import winners_lib as W  # noqa: E402
import bt  # noqa: E402


def build(ts, o, c, mode):
    mod, _, _ = W.load_ratio_froth(ts, o, c)
    dates = bt.session_dates(ts)
    first, last = bt.day_bounds_from_dates(dates)
    qqq_close, tqqq_close = c[:, 0], c[:, 1]
    dc = qqq_close[last]
    sma = pd.Series(dc).rolling(mod.SMA_N).mean().to_numpy()
    ma20 = pd.Series(dc).rolling(mod.MA_FAST).mean().to_numpy()
    sma_prev = np.r_[np.nan, sma[:-1]]
    ma20_prev = np.r_[np.nan, ma20[:-1]]
    froth, ext = mod.froth_flag(c, last)
    n = len(ts)
    w = np.zeros((n, 3))
    stats = {"sessions": 0, "risk_on": 0, "froth": 0, "stops": 0,
             "stops_froth": 0, "stops_tqqq": 0}
    for k, (f, l) in enumerate(zip(first, last)):
        stats["sessions"] += 1
        risk_on = k > 0 and sma_prev[k] == sma_prev[k] and dc[k - 1] > sma_prev[k]
        if not risk_on:
            w[f:l + 1, 2] = 1.0
            continue
        stats["risk_on"] += 1
        is_froth = bool(froth[k])
        stats["froth"] += int(is_froth)
        held = 0 if is_froth else 1          # 0=QQQ, 1=TQQQ
        armed = bool(ma20_prev[k] == ma20_prev[k] and
                     qqq_close[f] < ma20_prev[k] * (1 + mod.ARM_BUF))
        stop = False
        trig = None
        if armed:
            if held == 1:
                base = o[f, 1]
                idx = np.flatnonzero(tqqq_close[f:l + 1] < base * (1 - mod.STOP))
                stats["stops_tqqq"] += 1 if len(idx) else 0
                if len(idx):
                    stop = True
                    trig = f + int(idx[0])
            elif mode == "tqqq_stop_on_qqq":
                base = o[f, 1]
                idx = np.flatnonzero(tqqq_close[f:l + 1] < base * (1 - mod.STOP))
                stats["stops_froth"] += 1 if len(idx) else 0
                if len(idx):
                    stop = True
                    trig = f + int(idx[0])
            elif mode == "qqq_asset_stop":
                base = o[f, 0]
                idx = np.flatnonzero(qqq_close[f:l + 1] < base * (1 - mod.STOP))
                stats["stops_froth"] += 1 if len(idx) else 0
                if len(idx):
                    stop = True
                    trig = f + int(idx[0])
            # no_qqq_stop: never stop the QQQ leg
        if stop:
            stats["stops"] += 1
            w[f:trig, held] = 1.0
            w[trig:l + 1, 2] = 1.0
        else:
            w[f:l + 1, held] = 1.0
    return w, stats


def main():
    ts, o, h, l, c = W.load_panel()
    out = {}
    variants = {}
    for mode in ("tqqq_stop_on_qqq", "qqq_asset_stop", "no_qqq_stop"):
        w, st = build(ts, o, c, mode)
        variants[mode] = w
        out[mode] = {"stats": st}
    labels = list(variants)
    results = bt.run_many(ts, o, c, [variants[k] for k in labels], W.START,
                          band=0.02, slippage_bps=1.0)
    for k, r in zip(labels, results):
        d = W.daily_equity(r)
        m = W.metrics(d)
        out[k].update({"daily": m, "minute": W.minute_metrics(r),
                       "exposure": W.exposure(variants[k], ts)})
        print(f"{k:20s} CAGR {m['cagr']*100:6.2f}  DD {m['max_drawdown']*100:5.2f}  "
              f"Sharpe {m['sharpe']:4.2f}  stats {out[k]['stats']}")
    W.save_json("winners_ratio_stop_asym.json", out)


if __name__ == "__main__":
    main()
