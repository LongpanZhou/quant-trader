"""Tuning sweep (2026-11-27). DEV WINDOW ONLY.  Writes tune_sweep.json.

    python research/revisit/gap-capitulation-reversal/tune_sweep.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

os.environ.setdefault("BT_THREADS", "1")
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import strategy as S  # noqa: E402
bt = S.bt

SUBS = (("2016-01-04", "2019-12-31"), ("2020-01-02", "2021-12-31"), ("2022-01-03", "2023-12-29"))


def daily(r):
    eq = pd.Series(r["equity"], index=r["ts"])
    return eq.groupby(eq.index.date).last()


def sub_cagr(de):
    out = {}
    for a, b in SUBS:
        lo, hi = pd.Timestamp(a).date(), pd.Timestamp(b).date()
        s = de[(de.index >= lo) & (de.index <= hi)]
        prev = de[de.index < lo]
        s0 = prev.iloc[-1] if len(prev) else S.bt.START_EQUITY
        y = (pd.Timestamp(b) - pd.Timestamp(a)).days / 365.25
        out[a[:4] + "-" + b[2:4]] = float((s.iloc[-1] / s0) ** (1 / y) - 1)
    return out


def evaluate(ts, o, c, qlow, qvol, params, base_ret, slips=(1.0,)):
    w, info = S.build_weights(ts, o, c, qlow, qvol, params)
    out = {"n_events": info["n_events"], "starts": info["n_trade_starts"],
           "el_stops": info["n_event_low_stops"], "hard_stops": info["n_hard_stops"],
           "exposure": info["exposure"]}
    for slip in slips:
        r = bt.run(ts, o, c, w, S.DEV_START, band=0.02, slippage_bps=slip)
        st = bt.stats(r, S.BARS_PER_YEAR)
        out[f"{int(slip)}bp"] = {"cagr": st["cagr"], "dd": st["max_drawdown"], "sharpe": st["sharpe"],
                                 "fills": st["fills"]}
        if slip == 1.0:
            de = daily(r)
            out["sub"] = sub_cagr(de)
            sr = de.pct_change().dropna()
            j = sr.index.intersection(base_ret.index)
            out["corr"] = float(np.corrcoef(sr.loc[j], base_ret.loc[j])[0, 1])
    return out


def grid(center):
    """Pre-registered one-at-a-time neighbourhood + ablations around `center`."""
    v = {"base": {}}
    steps = dict(drop=(0.015, 0.025), intraday=(0.025, 0.035), rvol_max=(1.0, 1.5),
                 oversold=(0.0, 0.05), hold=(1, 5), vol_max=(0.25, 0.35), hard_stop=(0.06, 0.10))
    for k, vals in steps.items():
        for x in vals:
            v[f"{k}={x}"] = {k: x}
    v["event_low_stop=" + str(not center.get("event_low_stop", True))] = {
        "event_low_stop": not center.get("event_low_stop", True)}
    v["abl:no_volume"] = {"rvol_max": np.inf}
    v["abl:no_oversold"] = {"oversold": -np.inf}
    v["abl:always_tqqq"] = {"vol_max": np.inf}
    v["abl:always_qqq"] = {"vol_max": -1.0}
    v["abl:no_hard_stop"] = {"hard_stop": 1.0}
    v["abl:half_tqqq_high_vol"] = {"high_vol": "HALF"}
    return {k: {**center, **x} for k, x in v.items()}


def main():
    ts, o, c = bt.panel(("QQQ", "TQQQ", "BIL"), S.DEV_START, S.DEV_END, "1min")
    assert ts[-1] < pd.Timestamp("2023-12-30", tz="America/New_York")
    qlow, qvol = S.daily_extras(ts)
    base_ret = daily(bt.run(ts, o, c, S.benchmark_weights(ts, c), S.DEV_START, 0.02, 1.0)).pct_change().dropna()
    centers = json.loads(os.environ.get("TUNE_CENTERS", "{}")) or {"fixed_base": dict(S.PARAMS)}
    res = {}
    for cname, center in centers.items():
        res[cname] = {}
        for vname, p in grid({**S.PARAMS, **center}).items():
            r = evaluate(ts, o, c, qlow, qvol, p, base_ret)
            res[cname][vname] = r
            print(cname, f"{vname:28s}", f"{r['1bp']['cagr']*100:6.2f} {r['1bp']['dd']*100:6.2f} "
                  f"{r['1bp']['sharpe']:5.2f} corr={r['corr']:.2f} ev={r['n_events']} st={r['el_stops']}",
                  " ".join(f"{k}:{x*100:5.2f}" for k, x in r["sub"].items()), flush=True)
    tag = os.environ.get("TUNE_TAG", "sweep")
    with open(HERE / f"tune_{tag}.json", "w", newline="\n", encoding="utf-8") as f:
        json.dump(res, f, indent=1, default=float)


if __name__ == "__main__":
    main()
