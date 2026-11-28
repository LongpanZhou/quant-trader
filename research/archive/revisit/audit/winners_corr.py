"""Daily-return and exposure correlation matrix across the winners and the old base."""
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


def main():
    ts, o, h, l, c = W.load_panel()
    mod_r, w_r, _ = W.load_ratio_froth(ts, o, c)
    mod_v, w_v, _, _, _, _ = W.load_vol(ts, o, h, l, c)
    w_gate = mod_r.build_weights(ts, o, c, use_overlay=False, use_stop=False)[0]
    w_base = mod_r.build_weights(ts, o, c, use_overlay=False)[0]
    w_gate_overlay = mod_r.build_weights(ts, o, c, use_stop=False)[0]
    variants = {
        "ratio_full": w_r,
        "ratio_old_base": w_base,
        "ratio_gate_only": w_gate,
        "ratio_gate_overlay": w_gate_overlay,
        "vol_full": w_v,
        "tqqq": np.tile(np.array([0.0, 1.0, 0.0]), (len(ts), 1)),
    }
    labels = list(variants)
    results = bt.run_many(ts, o, c, [variants[k] for k in labels], W.START,
                          band=0.02, slippage_bps=1.0)
    rets = {}
    wts = {}
    for k, r in zip(labels, results):
        d = W.daily_equity(r)
        rets[k] = W.daily_returns(d)
        dates = bt.session_dates(r["ts"])
        _, last = bt.day_bounds_from_dates(dates)
        wts[k] = pd.Series(r["ts"][last], index=pd.to_datetime(dates[last]))
        # daily mean TQQQ weight
        df = pd.Series(variants[k][bt.start_index(ts, W.START):, 1],
                       index=pd.DatetimeIndex(r["ts"]))
        wts[k] = df.groupby(df.index.date).mean()
    R = pd.DataFrame(rets).dropna()
    Wt = pd.DataFrame(wts).dropna()
    out = {
        "return_corr": R.corr().round(4).to_dict(),
        "weight_corr": Wt.corr().round(4).to_dict(),
    }
    print("return corr")
    print(R.corr().round(3).to_string())
    print("TQQQ weight corr")
    print(Wt.corr().round(3).to_string())
    W.save_json("winners_corr.json", out)


if __name__ == "__main__":
    main()
