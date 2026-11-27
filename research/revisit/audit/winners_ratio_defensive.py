"""Ratio-froth defensive-asset variants and old-base decomposition, full window."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import winners_lib as W  # noqa: E402
import bt  # noqa: E402


def main():
    ts, o, h, l, c = W.load_panel()
    mod, w_full, _ = W.load_ratio_froth(ts, o, c)
    variants = {
        "full_qqq_defensive": w_full,
        "full_bil_defensive": mod.build_weights(ts, o, c, defensive="BIL")[0],
        "old_base_gate_stop": mod.build_weights(ts, o, c, use_overlay=False)[0],
        "gate_stop_bil_no_overlay": mod.build_weights(
            ts, o, c, defensive="BIL", use_overlay=False)[0],
    }
    labels = list(variants)
    results = bt.run_many(ts, o, c, [variants[k] for k in labels], W.START,
                          band=0.02, slippage_bps=1.0)
    out = {}
    for k, r in zip(labels, results):
        d = W.daily_equity(r)
        out[k] = {"daily": W.metrics(d), "minute": W.minute_metrics(r),
                  "exposure": W.exposure(variants[k], ts),
                  "yearly": W.yearly_returns_eoy(d)}
        m = out[k]["daily"]
        print(f"{k:26s} CAGR {m['cagr']*100:6.2f}  DD {m['max_drawdown']*100:5.2f}  "
              f"Sharpe {m['sharpe']:4.2f}  TQQQw {out[k]['exposure']['mean_tqqq']:.3f}")
    W.save_json("winners_ratio_defensive.json", out)


if __name__ == "__main__":
    main()
