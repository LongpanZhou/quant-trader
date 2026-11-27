"""Correlation of the vol system with its own 165-day baseline, clean dev and full."""
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


def corr_daily(a, b):
    ra = W.daily_returns(W.daily_equity(a))
    rb = W.daily_returns(W.daily_equity(b))
    j = pd.concat([ra.rename("a"), rb.rename("b")], axis=1).dropna()
    return float(j["a"].corr(j["b"])), int(len(j))


def main():
    ts, o, h, l, c = W.load_panel()
    out = {}

    # clean dev panel
    i_end = int(ts.searchsorted(pd.Timestamp("2023-12-30", tz="America/New_York")))
    tsd, od, hd, ld, cd = ts[:i_end], o[:i_end], h[:i_end], l[:i_end], c[:i_end]
    modv, wd, info, atr, first, last = W.load_vol(tsd, od, hd, ld, cd)
    base_w, reg = modv.baseline_weights(tsd, first, last)
    rb = bt.run(tsd, od, cd, base_w, "2016-01-04", band=0.02, slippage_bps=1.0)
    rp = bt.run(tsd, od, cd, wd, "2016-01-04", band=0.02, slippage_bps=1.0)
    out["dev"] = {
        "baseline_daily": W.metrics(W.daily_equity(rb)),
        "baseline_minute": W.minute_metrics(rb),
        "primary_daily": W.metrics(W.daily_equity(rp)),
        "primary_minute": W.minute_metrics(rp),
        "corr": corr_daily(rp, rb)[0],
        "n": corr_daily(rp, rb)[1],
        "primary_dd_vs_baseline_pp": float(
            (W.metrics(W.daily_equity(rb))["max_drawdown"]
             - W.metrics(W.daily_equity(rp))["max_drawdown"]) * 100),
    }
    print("dev", json.dumps(out["dev"], indent=1))

    # full panel: strategy baseline (stale after 2023) and causal gate-only
    modv2, wf, info2, atr2, first2, last2 = W.load_vol(ts, o, h, l, c)
    base_w2, reg2 = modv2.baseline_weights(ts, first2, last2)
    rb2 = bt.run(ts, o, c, base_w2, W.START, band=0.02, slippage_bps=1.0)
    rf = bt.run(ts, o, c, wf, W.START, band=0.02, slippage_bps=1.0)
    modr, wr, _ = W.load_ratio_froth(ts, o, c)
    gate_w = modr.build_weights(ts, o, c, use_overlay=False, use_stop=False)[0]
    rg = bt.run(ts, o, c, gate_w, W.START, band=0.02, slippage_bps=1.0)
    out["full"] = {
        "baseline_strategy_daily": W.metrics(W.daily_equity(rb2)),
        "baseline_strategy_minute": W.minute_metrics(rb2),
        "corr_vs_strategy_baseline": corr_daily(rf, rb2)[0],
        "corr_vs_causal_gate_only": corr_daily(rf, rg)[0],
        "corr_vs_causal_gate_only_minute": float(
            pd.Series(W.daily_returns(W.daily_equity(rf))).corr(
                pd.Series(W.daily_returns(W.daily_equity(rg))))),
    }
    print("full", json.dumps(out["full"], indent=1))

    W.save_json("winners_vol_baseline_corr.json", out)


if __name__ == "__main__":
    main()
