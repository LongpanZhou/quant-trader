"""Tuning sweep (2026-11-27), development window only.

    python research/revisit/drawdown-stop-overlay/tune_sweep.py

Every variant uses the corrected (TQQQ-priced) state machine in strategy.py.
Prints a JSON table: dev 1 bp CAGR / DD / Sharpe, sub-period CAGRs
(2016-19, 2020-21, 2022-23), TQQQ time-in-market, corr vs the 165-day base.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
spec = importlib.util.spec_from_file_location("s_tune", HERE / "strategy.py")
S = importlib.util.module_from_spec(spec)
spec.loader.exec_module(S)
bt = S.bt

P0 = dict(lookback=20, hold=5, stop=0.08, range_pos=0.50, size=1.00)
NOSTOP = 9.0  # a stop that can never trigger
GRID = {
    # one-at-a-time neighbourhood around the (fixed) primary
    "primary": {},
    "lookback10": dict(lookback=10), "lookback30": dict(lookback=30),
    "hold1": dict(hold=1), "hold2": dict(hold=2), "hold3": dict(hold=3), "hold10": dict(hold=10),
    "stop6": dict(stop=0.06), "stop10": dict(stop=0.10), "stop15": dict(stop=0.15),
    "nostop": dict(stop=NOSTOP),
    "range04": dict(range_pos=0.40), "range06": dict(range_pos=0.60),
    "size50": dict(size=0.50),
    # the no-stop direction, with its own neighbourhood
    "nostop_hold1": dict(stop=NOSTOP, hold=1), "nostop_hold3": dict(stop=NOSTOP, hold=3),
    "nostop_hold10": dict(stop=NOSTOP, hold=10),
    "nostop_lb10": dict(stop=NOSTOP, lookback=10), "nostop_lb30": dict(stop=NOSTOP, lookback=30),
    "nostop_r04": dict(stop=NOSTOP, range_pos=0.40), "nostop_r06": dict(stop=NOSTOP, range_pos=0.60),
}


def daily_eq(run):
    df = pd.DataFrame({"ts": run["ts"], "eq": run["equity"]})
    e = df.groupby(df.ts.dt.date)["eq"].last()
    e.index = pd.to_datetime(e.index)
    return e


def sub_cagr(e, lo, hi):
    prev = e[e.index.year < lo]
    s = e[(e.index.year >= lo) & (e.index.year <= hi)]
    a = prev.iloc[-1] if len(prev) else s.iloc[0]
    t0 = prev.index[-1] if len(prev) else s.index[0]
    yrs = (s.index[-1] - t0).days / 365.25
    return float((s.iloc[-1] / a) ** (1 / yrs) - 1)


def main():
    ts1, o1, c1 = bt.panel(("QQQ", "TQQQ", "BIL"), S.DEV0, S.DEV1, "1min")
    tsd, od, cd = bt.panel(("QQQ", "TQQQ", "BIL"), S.DEV0, S.DEV1, "1D")
    g = S.load_daily_qqq_ohlc(tsd)
    names, wl, info = [], [], {}
    for k, v in GRID.items():
        p = {**P0, **v}
        wd, inf = S.build_daily_weights(g, **p)
        names.append(k)
        wl.append(S.to_minutes(tsd, wd, ts1, "1D"))
        info[k] = inf
    wb = S.to_minutes(tsd, S.build_baseline(tsd, cd), ts1, "1D")
    eb = daily_eq(bt.run(ts1, o1, c1, wb, S.DEV0)).pct_change().dropna()
    out = {}
    for i in range(0, len(wl), 6):
        rs = bt.run_many(ts1, o1, c1, wl[i:i + 6], S.DEV0, band=0.02, slippage_bps=1.0)
        for k, w, r in zip(names[i:i + 6], wl[i:i + 6], rs):
            s = bt.stats(r, S.BARS_1M)
            e = daily_eq(r)
            out[k] = {"cagr": float(s["cagr"]), "dd": float(s["max_drawdown"]),
                      "sharpe": float(s["sharpe"]),
                      "16-19": sub_cagr(e, 2016, 2019), "20-21": sub_cagr(e, 2020, 2021),
                      "22-23": sub_cagr(e, 2022, 2023),
                      "tqqq_time": float((w[:, 1] > 0).mean()),
                      "entries": len(info[k]["entries"]), "exits": info[k]["exit_reasons"],
                      "corr165": float(e.pct_change().dropna().corr(eb))}
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
