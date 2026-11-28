"""Minute-level sleeve P&L attribution (approximate but bar-aligned)."""
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
    dates = bt.session_dates(ts)
    first, last = bt.day_bounds_from_dates(dates)
    idx = pd.to_datetime(dates[last])
    n_sess = len(first)
    years = (ts[-1] - ts[0]).total_seconds() / (365.25 * 86400)

    mod_r, w_r, _ = W.load_ratio_froth(ts, o, c)
    mod_v, w_v, _, _, _, _ = W.load_vol(ts, o, h, l, c)
    out = {}

    for name, w in (("ratio_froth", w_r), ("vol_scaled", w_v)):
        r = bt.run(ts, o, c, w, W.START, band=0.02, slippage_bps=1.0)
        eq = r["equity"]
        ret_bar = eq[1:] / eq[:-1] - 1.0
        contrib = {}
        for j, sym in enumerate(("qqq", "tqqq", "bil")):
            ar = c[1:, j] / c[:-1, j] - 1.0
            contrib[sym] = w[:-1, j] * ar
        total = sum(contrib.values())
        # annualised arithmetic means over all bars
        ann = {k: float(np.nanmean(v) * 252 * 390) for k, v in contrib.items()}
        ann_total = float(np.nanmean(total) * 252 * 390)
        out[name] = {
            "years": float(years),
            "strategy_bar_mean_ann": float(np.nanmean(ret_bar) * 252 * 390),
            "contrib_ann": ann,
            "sum_contrib_ann": ann_total,
            "residual_ann": ann_total - float(np.nanmean(ret_bar) * 252 * 390),
            "share": {k: float(v / ann_total) for k, v in ann.items()} if ann_total else {},
            "turnover_x_start": float(r["turnover"]),
            "mean_equity": float(np.nanmean(eq)),
            "turnover_x_mean_equity": float(r["turnover"] * W.bt.START_EQUITY / np.nanmean(eq)),
            "turnover_per_year_mean_equity": float(r["turnover"] * W.bt.START_EQUITY
                                                   / np.nanmean(eq) / years),
            "fills": int(r["fills"]),
            "fills_per_session": float(r["fills"] / n_sess),
        }
        print(name, json.dumps(out[name], indent=1))

    W.save_json("winners_return_attrib.json", out)


if __name__ == "__main__":
    main()
